#!/usr/bin/env python3

import argparse
import json
import mimetypes
import os
import secrets
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ALIAS = socket.gethostname() or "Waybar"
APP_DIR = Path.home() / ".config" / "waybar" / "localsend"
STATE_PATH = Path("/tmp/waybar-localsend-service.json")
PID_PATH = Path("/tmp/waybar-localsend-service.pid")
DOWNLOADS_PATH = Path.home() / "Downloads" / "LocalSend"
PORT = 53318
MULTICAST_PORT = 53317
MULTICAST_GROUP = "224.0.0.167"
VERSION = "2.1"


def ensure_app_dir():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if not (APP_DIR / "fingerprint").exists():
        (APP_DIR / "fingerprint").write_text(secrets.token_hex(16))


def fingerprint():
    ensure_app_dir()
    return (APP_DIR / "fingerprint").read_text().strip()


def local_info(announce=False):
    return {
        "alias": ALIAS,
        "version": VERSION,
        "deviceModel": "Linux",
        "deviceType": "desktop",
        "fingerprint": fingerprint(),
        "port": PORT,
        "protocol": "http",
        "download": False,
        "announce": announce,
    }


class LocalSendState:
    def __init__(self):
        self.lock = threading.Lock()
        self.devices = {}
        self.incoming = {}
        self.transfers = []
        self.stop_event = threading.Event()

    def snapshot(self):
        with self.lock:
            now = time.time()
            devices = [
                value
                for value in self.devices.values()
                if now - value.get("last_seen", 0) < 60
            ]
            return {
                "running": True,
                "alias": ALIAS,
                "port": PORT,
                "devices": sorted(devices, key=lambda item: item.get("alias", "")),
                "incoming": list(self.incoming.values()),
                "transfers": self.transfers[-8:],
            }

    def write_state(self):
        STATE_PATH.write_text(json.dumps(self.snapshot()))

    def add_device(self, host, info):
        if not isinstance(info, dict):
            return
        if info.get("fingerprint") == fingerprint():
            return

        port = int(info.get("port") or MULTICAST_PORT)
        protocol = info.get("protocol") or "http"
        key = info.get("fingerprint") or f"{host}:{port}"
        device = {
            "id": key,
            "alias": info.get("alias") or host,
            "deviceType": info.get("deviceType") or "desktop",
            "host": host,
            "port": port,
            "protocol": protocol,
            "download": bool(info.get("download")),
            "last_seen": time.time(),
        }
        with self.lock:
            self.devices[key] = device
        self.write_state()

    def add_transfer(self, label, status):
        with self.lock:
            self.transfers.append(
                {"time": time.strftime("%H:%M"), "label": label, "status": status}
            )
        self.write_state()


STATE = LocalSendState()


def shutdown():
    STATE.stop_event.set()
    STATE_PATH.unlink(missing_ok=True)
    PID_PATH.unlink(missing_ok=True)
    os.kill(os.getpid(), signal.SIGTERM)


def url_for(device, path):
    return f"{device['protocol']}://{device['host']}:{device['port']}{path}"


def http_request(url, method="GET", data=None, headers=None, timeout=30):
    context = ssl._create_unverified_context()
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        headers = {"Content-Type": "application/json", **(headers or {})}
    request = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    return urllib.request.urlopen(request, timeout=timeout, context=context)


def local_probe():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/waybar/state", timeout=0.4):
            return True
    except Exception:
        return False


def post_binary(url, path):
    context = ssl._create_unverified_context()
    headers = {"Content-Type": mimetypes.guess_type(path)[0] or "application/octet-stream"}
    request = urllib.request.Request(url, method="POST", headers=headers, data=Path(path).read_bytes())
    return urllib.request.urlopen(request, timeout=120, context=context)


def file_metadata(paths):
    files = {}
    expanded = []
    for original in paths:
        path = Path(original)
        if path.is_dir():
            expanded.extend(item for item in path.rglob("*") if item.is_file())
        elif path.is_file():
            expanded.append(path)

    for index, path in enumerate(expanded):
        file_id = f"file-{index}-{secrets.token_hex(4)}"
        stat = path.stat()
        files[file_id] = {
            "id": file_id,
            "fileName": path.name,
            "size": stat.st_size,
            "fileType": mimetypes.guess_type(path)[0] or "application/octet-stream",
            "sha256": None,
            "preview": None,
            "path": str(path),
        }
    return files


def send_paths(device_id, paths, label=None):
    with STATE.lock:
        device = STATE.devices.get(device_id)
    if not device:
        STATE.add_transfer(label or "Send", "Device not found")
        return

    files = file_metadata(paths)
    if not files:
        STATE.add_transfer(label or "Send", "No files")
        return

    payload = {
        "info": local_info(False),
        "files": {
            file_id: {key: value for key, value in item.items() if key != "path"}
            for file_id, item in files.items()
        },
    }

    try:
        response = http_request(
            url_for(device, "/api/localsend/v2/prepare-upload"),
            method="POST",
            data=payload,
            timeout=120,
        )
        prepared = json.loads(response.read().decode() or "{}")
        session_id = prepared.get("sessionId")
        tokens = prepared.get("files", {})
        for file_id, token in tokens.items():
            item = files[file_id]
            query = urllib.parse.urlencode(
                {"sessionId": session_id, "fileId": file_id, "token": token}
            )
            post_binary(url_for(device, f"/api/localsend/v2/upload?{query}"), item["path"])
        STATE.add_transfer(label or f"Sent to {device['alias']}", "Sent")
    except urllib.error.HTTPError as error:
        STATE.add_transfer(label or f"Sent to {device['alias']}", f"Rejected ({error.code})")
    except Exception as error:
        STATE.add_transfer(label or f"Sent to {device['alias']}", str(error))


def send_text(device_id, text, label):
    temp_dir = Path(tempfile.mkdtemp(prefix="waybar-localsend-"))
    path = temp_dir / label
    path.write_text(text)
    try:
        send_paths(device_id, [str(path)], label=label)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def discover_loop():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

    listen = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listen.bind(("", MULTICAST_PORT))
    membership = socket.inet_aton(MULTICAST_GROUP) + socket.inet_aton("0.0.0.0")
    listen.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
    listen.settimeout(1)

    next_announce = 0
    while not STATE.stop_event.is_set():
        now = time.monotonic()
        if now >= next_announce:
            payload = json.dumps(local_info(True)).encode()
            sock.sendto(payload, (MULTICAST_GROUP, MULTICAST_PORT))
            next_announce = now + 5

        try:
            data, address = listen.recvfrom(8192)
            info = json.loads(data.decode())
            STATE.add_device(address[0], info)
        except (socket.timeout, json.JSONDecodeError, OSError):
            pass


class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode())

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/localsend/v2/info":
            self.send_json(local_info(False))
        elif parsed.path == "/waybar/state":
            self.send_json(STATE.snapshot())
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/api/localsend/v2/register":
            data = self.read_json()
            host = self.client_address[0]
            STATE.add_device(host, data)
            self.send_json(local_info(False))
        elif parsed.path == "/api/localsend/v2/prepare-upload":
            self.prepare_upload()
        elif parsed.path == "/api/localsend/v2/upload":
            self.receive_upload(query)
        elif parsed.path == "/waybar/accept":
            self.decide(query, "accepted")
        elif parsed.path == "/waybar/reject":
            self.decide(query, "rejected")
        elif parsed.path == "/waybar/send":
            self.start_send()
        elif parsed.path == "/waybar/stop":
            self.send_json({"ok": True})
            threading.Thread(target=shutdown, daemon=True).start()
        else:
            self.send_error(404)

    def prepare_upload(self):
        data = self.read_json()
        session_id = secrets.token_urlsafe(12)
        files = data.get("files", {})
        sender = data.get("info", {})
        tokens = {file_id: secrets.token_urlsafe(16) for file_id in files}
        pending = {
            "id": session_id,
            "sender": sender.get("alias", self.client_address[0]),
            "files": list(files.values()),
            "status": "pending",
            "created": time.time(),
            "tokens": tokens,
        }

        with STATE.lock:
            STATE.incoming[session_id] = pending
        STATE.write_state()

        deadline = time.time() + 120
        while time.time() < deadline:
            with STATE.lock:
                status = STATE.incoming.get(session_id, {}).get("status")
            if status == "accepted":
                self.send_json({"sessionId": session_id, "files": tokens})
                return
            if status == "rejected":
                with STATE.lock:
                    STATE.incoming.pop(session_id, None)
                STATE.write_state()
                self.send_error(403, "Rejected")
                return
            time.sleep(0.3)

        with STATE.lock:
            STATE.incoming.pop(session_id, None)
        STATE.write_state()
        self.send_error(403, "Timed out")

    def receive_upload(self, query):
        session_id = query.get("sessionId", [""])[0]
        file_id = query.get("fileId", [""])[0]
        token = query.get("token", [""])[0]
        with STATE.lock:
            session = STATE.incoming.get(session_id)
        if not session or session["tokens"].get(file_id) != token:
            self.send_error(403)
            return

        file_info = next((item for item in session["files"] if item.get("id") == file_id), {})
        target_dir = DOWNLOADS_PATH / time.strftime("%Y-%m-%d_%H-%M-%S")
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / Path(file_info.get("fileName") or file_id).name
        length = int(self.headers.get("Content-Length", "0"))
        with target.open("wb") as output:
            remaining = length
            while remaining > 0:
                chunk = self.rfile.read(min(1024 * 256, remaining))
                if not chunk:
                    break
                output.write(chunk)
                remaining -= len(chunk)

        self.send_response(200)
        self.end_headers()
        STATE.add_transfer(f"Received {target.name}", "Saved")

    def decide(self, query, status):
        session_id = query.get("id", [""])[0]
        with STATE.lock:
            if session_id in STATE.incoming:
                STATE.incoming[session_id]["status"] = status
                ok = True
            else:
                ok = False
        STATE.write_state()
        self.send_json({"ok": ok})

    def start_send(self):
        data = self.read_json()
        device_id = data.get("device_id")
        if data.get("text"):
            label = data.get("label") or "message.txt"
            threading.Thread(
                target=send_text,
                args=(device_id, data["text"], label),
                daemon=True,
            ).start()
        else:
            paths = data.get("paths") or []
            threading.Thread(
                target=send_paths,
                args=(device_id, paths, None),
                daemon=True,
            ).start()
        self.send_json({"ok": True})


def serve():
    ensure_app_dir()
    PID_PATH.write_text(str(os.getpid()))
    STATE.write_state()

    def stop(_signum, _frame):
        STATE.stop_event.set()
        STATE_PATH.unlink(missing_ok=True)
        PID_PATH.unlink(missing_ok=True)
        sys.exit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    threading.Thread(target=discover_loop, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    while not STATE.stop_event.is_set():
        server.handle_request()


def service_running():
    if not PID_PATH.exists():
        return local_probe()
    try:
        os.kill(int(PID_PATH.read_text().strip()), 0)
        return True
    except (OSError, ValueError):
        return local_probe()


def start_service():
    if service_running():
        return
    subprocess.Popen(
        [sys.executable, __file__, "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def stop_service():
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{PORT}/waybar/stop",
            data=b"",
            method="POST",
        )
        urllib.request.urlopen(request, timeout=0.4).close()
        return
    except Exception:
        pass

    if not PID_PATH.exists():
        return
    try:
        os.kill(int(PID_PATH.read_text().strip()), signal.SIGTERM)
    except (OSError, ValueError):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["serve", "start", "stop", "status"])
    args = parser.parse_args()

    if args.command == "serve":
        serve()
    elif args.command == "start":
        start_service()
    elif args.command == "stop":
        stop_service()
    elif args.command == "status":
        print("running" if service_running() else "stopped")


if __name__ == "__main__":
    main()
