#!/usr/bin/env python3

import fcntl
import os
import re
import signal
import subprocess
import threading
import time

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402


LOCK_PATH = "/tmp/waybar-bluetooth-menu.lock"
LOCALSEND_SERVICE = os.path.join(os.path.dirname(os.path.realpath(__file__)), "localsend-service.py")
LOCALSEND_MENU = os.path.join(os.path.dirname(os.path.realpath(__file__)), "localsend-menu.py")

DEVICE_TYPE_ICONS = {
    "audio-headset": "󰋋",
    "audio-headphones": "󰋋",
    "audio-card": "󰓃",
    "input-keyboard": "󰌌",
    "input-mouse": "󰍽",
    "input-gaming": "󰖺",
    "phone": "",
    "computer": "󰍹",
}
DEVICE_DEFAULT_ICON = "󰂯"
SCAN_SECONDS = 8


def run(*args):
    try:
        return subprocess.run(args, check=False, capture_output=True, text=True)
    except FileNotFoundError as error:
        return subprocess.CompletedProcess(args, 127, "", str(error))


def controller_powered():
    result = run("bluetoothctl", "show")
    match = re.search(r"Powered:\s+(yes|no)", result.stdout)
    return match is not None and match.group(1) == "yes"


def parse_devices(output):
    devices = []
    for line in output.splitlines():
        match = re.match(r"Device\s+([0-9A-F:]{17})\s+(.+)", line)
        if match:
            devices.append({"mac": match.group(1), "name": match.group(2)})
    return devices


def device_type_icon(mac):
    result = run("bluetoothctl", "info", mac)
    match = re.search(r"Icon:\s+(\S+)", result.stdout)
    if match:
        return DEVICE_TYPE_ICONS.get(match.group(1), DEVICE_DEFAULT_ICON)
    return DEVICE_DEFAULT_ICON


def normalize(value):
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def compact_mac(mac):
    return mac.replace(":", "").lower()


def percent_value(value):
    match = re.search(r"(\d{1,3})\s*%", value)
    if not match:
        return None
    percent = int(match.group(1))
    if 0 <= percent <= 100:
        return percent
    return None


def parse_upower_info(output):
    fields = {}
    for line in output.splitlines():
        match = re.match(r"\s*([^:]+):\s*(.+)", line)
        if match:
            fields[match.group(1).strip().lower()] = match.group(2).strip()
    percent = percent_value(fields.get("percentage", ""))
    if percent is None:
        return None
    names = [
        fields.get("model", ""),
        fields.get("native-path", ""),
        fields.get("serial", ""),
        fields.get("vendor", ""),
        fields.get("detail", ""),
    ]
    return {"percent": percent, "names": [name for name in names if name]}


def upower_batteries():
    result = run("upower", "-e")
    batteries = []
    for path in result.stdout.splitlines():
        if not path:
            continue
        info = parse_upower_info(run("upower", "-i", path).stdout)
        if info:
            info["source"] = "upower"
            info["names"].append(path)
            batteries.append(info)
    return batteries


def solaar_batteries():
    result = run("solaar", "show")
    batteries = []
    current_name = None
    for line in result.stdout.splitlines():
        device_match = re.match(r"\s*(?:\d+:\s*)?(.+?)\s*$", line)
        if line.strip() and device_match and not line.startswith(" "):
            current_name = device_match.group(1)
            continue
        numbered_match = re.match(r"\s+\d+:\s+(.+?)\s*$", line)
        if numbered_match:
            current_name = numbered_match.group(1)
            continue
        battery_match = re.match(r"\s*Battery:\s+(.+)", line)
        if battery_match and current_name:
            percent = percent_value(battery_match.group(1))
            if percent is not None:
                batteries.append({"percent": percent, "source": "solaar", "names": [current_name]})
    return batteries


def battery_score(device, battery):
    device_name = normalize(device["name"])
    device_mac = compact_mac(device["mac"])
    score = 0
    for name in battery["names"]:
        candidate = normalize(name)
        if not candidate:
            continue
        if device_mac and device_mac in candidate:
            score = max(score, 100)
        elif candidate == device_name:
            score = max(score, 90)
        elif device_name in candidate or candidate in device_name:
            score = max(score, 80)
    return score


def attach_batteries(devices):
    batteries = upower_batteries() + solaar_batteries()
    for device in devices:
        matches = sorted(
            ((battery_score(device, battery), battery) for battery in batteries),
            key=lambda match: match[0],
            reverse=True,
        )
        if matches and matches[0][0] > 0:
            device["battery"] = matches[0][1]["percent"]
    return devices


def localsend_running():
    return run(LOCALSEND_SERVICE, "status").stdout.strip() == "running"


def fetch_devices():
    devices = parse_devices(run("bluetoothctl", "devices", "Paired").stdout)
    connected_macs = {
        device["mac"]
        for device in parse_devices(run("bluetoothctl", "devices", "Connected").stdout)
    }
    for device in devices:
        device["connected"] = device["mac"] in connected_macs
        device["type_icon"] = device_type_icon(device["mac"])
    devices.sort(key=lambda d: (not d["connected"], d["name"].lower()))
    return attach_batteries(devices)


class BluetoothMenu(Gtk.Window):
    def __init__(self):
        super().__init__(title="Bluetooth")

        self.last_activity = time.monotonic()
        self.scanning = False

        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_border_width(12)
        self.add_events(
            Gdk.EventMask.ENTER_NOTIFY_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.BUTTON_PRESS_MASK
        )

        self.root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(self.root)

        self.connect("enter-notify-event", self.mark_active)
        self.connect("motion-notify-event", self.mark_active)
        self.connect("button-press-event", self.mark_active)
        self.connect("key-press-event", self.on_key_press)
        GLib.timeout_add_seconds(1, self.close_if_idle)

        self.apply_css()
        self.rebuild()

    def apply_css(self):
        css = b"""
        window {
            background: rgba(18, 18, 18, 0.96);
            border: 1px solid rgba(255, 255, 255, 0.14);
            border-radius: 8px;
            color: #ffffff;
        }

        .title {
            font-weight: 700;
            font-size: 14px;
        }

        .bluetooth-icon {
            font-family: "0xProto Nerd Font Mono";
            font-size: 22px;
            color: #2196F3;
        }

        .device-type-icon {
            font-family: "0xProto Nerd Font Mono";
            font-size: 18px;
            min-width: 26px;
        }

        .localsend-icon {
            font-family: "0xProto Nerd Font Mono";
            font-size: 18px;
        }

        .device-name {
            font-weight: 700;
        }

        .device-status {
            color: rgba(255, 255, 255, 0.55);
            font-size: 11px;
        }

        .status-connected {
            color: #4CAF50;
        }

        button {
            min-height: 28px;
            padding: 0 10px;
            border-radius: 7px;
            background: rgba(255, 255, 255, 0.12);
            color: #ffffff;
        }

        button:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        button:disabled {
            color: rgba(255, 255, 255, 0.3);
            background: rgba(255, 255, 255, 0.06);
        }

        button.destructive {
            background: rgba(244, 67, 54, 0.18);
            color: #ef9a9a;
        }

        button.destructive:hover {
            background: rgba(244, 67, 54, 0.32);
        }

        separator {
            background: rgba(255, 255, 255, 0.12);
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def rebuild(self, show_spinner=True):
        """Fetch data in a background thread, then populate the UI on the main thread."""
        if show_spinner:
            self._show_spinner()

        def fetch():
            powered = controller_powered()
            devices = fetch_devices() if powered else []
            ls_running = localsend_running()
            GLib.idle_add(self._populate, powered, devices, ls_running)

        threading.Thread(target=fetch, daemon=True).start()

    def _show_spinner(self):
        for child in self.root.get_children():
            self.root.remove(child)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        row.set_margin_top(12)
        row.set_margin_bottom(12)
        spinner = Gtk.Spinner()
        spinner.start()
        row.pack_start(spinner, True, True, 0)
        self.root.pack_start(row, False, False, 0)
        self.show_all()

    def _populate(self, powered, devices, ls_running):
        for child in self.root.get_children():
            self.root.remove(child)

        # Header
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon = Gtk.Label(label="󰂯" if powered else "󰂲")
        icon.get_style_context().add_class("bluetooth-icon")
        header.pack_start(icon, False, False, 0)

        title = Gtk.Label(label="Bluetooth")
        title.get_style_context().add_class("title")
        title.set_halign(Gtk.Align.START)
        header.pack_start(title, True, True, 0)

        power = Gtk.Switch()
        power.set_active(powered)
        power.connect("notify::active", self.on_power_changed)
        header.pack_start(power, False, False, 0)
        self.root.pack_start(header, False, False, 0)

        self.root.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        if powered:
            if devices:
                for device in devices:
                    self.root.pack_start(self.device_row(device), False, False, 0)
                self.root.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)
            else:
                hint = Gtk.Label(label="No paired devices")
                hint.set_halign(Gtk.Align.START)
                hint.get_style_context().add_class("device-status")
                self.root.pack_start(hint, False, False, 0)

            scan_btn = Gtk.Button(label="Scanning..." if self.scanning else "Scan for Devices")
            scan_btn.set_sensitive(not self.scanning)
            scan_btn.connect("clicked", self.start_scan)
            self.root.pack_start(scan_btn, False, False, 0)
        else:
            off = Gtk.Label(label="Bluetooth is off")
            off.set_halign(Gtk.Align.START)
            off.get_style_context().add_class("device-status")
            self.root.pack_start(off, False, False, 0)

        self.root.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        # LocalSend section
        ls_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        ls_icon = Gtk.Label(label="")
        ls_icon.get_style_context().add_class("localsend-icon")
        ls_header.pack_start(ls_icon, False, False, 0)

        ls_labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        ls_title = Gtk.Label(label="LocalSend")
        ls_title.get_style_context().add_class("title")
        ls_title.set_halign(Gtk.Align.START)
        ls_labels.pack_start(ls_title, False, False, 0)
        ls_status = Gtk.Label(label="Running" if ls_running else "Stopped")
        ls_status.set_halign(Gtk.Align.START)
        ls_status.get_style_context().add_class("device-status")
        if ls_running:
            ls_status.get_style_context().add_class("status-connected")
        ls_labels.pack_start(ls_status, False, False, 0)
        ls_header.pack_start(ls_labels, True, True, 0)

        open_ls = Gtk.Button(label="Open")
        open_ls.connect("clicked", self.open_localsend)
        ls_header.pack_start(open_ls, False, False, 0)

        ls_switch = Gtk.Switch()
        ls_switch.set_active(ls_running)
        ls_switch.connect("notify::active", self.on_localsend_changed)
        ls_header.pack_start(ls_switch, False, False, 0)

        self.root.pack_start(ls_header, False, False, 0)
        self.show_all()

    def device_row(self, device):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.set_size_request(300, -1)

        type_icon = Gtk.Label(label=device.get("type_icon", DEVICE_DEFAULT_ICON))
        type_icon.get_style_context().add_class("device-type-icon")
        row.pack_start(type_icon, False, False, 0)

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

        name = Gtk.Label(label=device["name"])
        name.set_halign(Gtk.Align.START)
        name.set_ellipsize(Pango.EllipsizeMode.END)
        name.get_style_context().add_class("device-name")
        labels.pack_start(name, False, False, 0)

        if device["connected"]:
            parts = ["● Connected"]
            if "battery" in device:
                parts.append(f"{device['battery']}%")
            status_text = " · ".join(parts)
        else:
            status_text = "○ Paired"

        status = Gtk.Label(label=status_text)
        status.set_halign(Gtk.Align.START)
        status.get_style_context().add_class("device-status")
        if device["connected"]:
            status.get_style_context().add_class("status-connected")
        labels.pack_start(status, False, False, 0)
        row.pack_start(labels, True, True, 0)

        action = Gtk.Button(label="Disconnect" if device["connected"] else "Connect")
        if device["connected"]:
            action.get_style_context().add_class("destructive")
        action.connect("clicked", self.toggle_device, device)
        row.pack_start(action, False, False, 0)

        return row

    def on_power_changed(self, switch, _param):
        self.mark_active()
        switch.set_sensitive(False)

        def work():
            run("bluetoothctl", "power", "on" if switch.get_active() else "off")
            GLib.idle_add(self.rebuild)

        threading.Thread(target=work, daemon=True).start()

    def toggle_device(self, button, device):
        self.mark_active()
        button.set_sensitive(False)
        button.set_label("Disconnecting..." if device["connected"] else "Connecting...")

        def work():
            run("bluetoothctl", "disconnect" if device["connected"] else "connect", device["mac"])
            GLib.idle_add(self.rebuild, False)

        threading.Thread(target=work, daemon=True).start()

    def start_scan(self, button):
        self.mark_active()
        self.scanning = True
        button.set_sensitive(False)
        button.set_label("Scanning...")

        def do_scan():
            subprocess.run(
                ["bluetoothctl", "--timeout", str(SCAN_SECONDS), "scan", "on"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.scanning = False
            GLib.idle_add(self.rebuild, False)

        threading.Thread(target=do_scan, daemon=True).start()
        GLib.timeout_add_seconds(2, self._poll_scan)

    def _poll_scan(self):
        if not self.scanning:
            return GLib.SOURCE_REMOVE
        self.rebuild(show_spinner=False)
        return GLib.SOURCE_CONTINUE

    def on_localsend_changed(self, switch, _param):
        self.mark_active()
        switch.set_sensitive(False)

        def work():
            run(LOCALSEND_SERVICE, "start" if switch.get_active() else "stop")
            GLib.idle_add(self.rebuild, False)

        threading.Thread(target=work, daemon=True).start()

    def open_localsend(self, _button):
        self.mark_active()
        subprocess.Popen([LOCALSEND_MENU])
        Gtk.main_quit()

    def on_key_press(self, _window, event):
        self.mark_active()
        if event.keyval == Gdk.KEY_Escape:
            Gtk.main_quit()

    def mark_active(self, *_args):
        self.last_activity = time.monotonic()
        return False

    def close_if_idle(self):
        if time.monotonic() - self.last_activity > 15:
            Gtk.main_quit()
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def present_near_top_right(self):
        self.show_all()
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        geometry = monitor.get_geometry()
        width, _height = self.get_size()
        self.move(geometry.x + geometry.width - width - 12, geometry.y + 34)
        self.present()


def main():
    lock_file = open(LOCK_PATH, "w")
    try:
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    window = BluetoothMenu()
    window.present_near_top_right()
    Gtk.main()


if __name__ == "__main__":
    main()
