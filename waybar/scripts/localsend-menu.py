#!/usr/bin/env python3

import fcntl
import json
import os
import signal
import subprocess
import time
import urllib.error
import urllib.request

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402


SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
SERVICE = os.path.join(SCRIPT_DIR, "localsend-service.py")
SERVICE_URL = "http://127.0.0.1:53318"
LOCK_PATH = "/tmp/waybar-localsend-menu.lock"
DOWNLOADS_PATH = os.path.expanduser("~/Downloads/LocalSend")


def run(*args):
    return subprocess.run(args, check=False, capture_output=True, text=True)


def service_running():
    return run(SERVICE, "status").stdout.strip() == "running"


def service_state():
    if not service_running():
        return {"running": False, "devices": [], "incoming": [], "transfers": []}
    try:
        with urllib.request.urlopen(f"{SERVICE_URL}/waybar/state", timeout=1) as response:
            return json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return {"running": True, "devices": [], "incoming": [], "transfers": []}


def post_json(path, data=None):
    body = json.dumps(data or {}).encode()
    request = urllib.request.Request(
        f"{SERVICE_URL}{path}",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return json.loads(response.read().decode() or "{}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return {}


def post_empty(path):
    request = urllib.request.Request(f"{SERVICE_URL}{path}", data=b"", method="POST")
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return json.loads(response.read().decode() or "{}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return {}


class LocalSendMenu(Gtk.Window):
    def __init__(self):
        super().__init__(title="LocalSend")

        self.last_activity = time.monotonic()

        self.set_decorated(False)
        self.set_default_size(460, -1)
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

        self.root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.add(self.root)

        self.connect("enter-notify-event", self.mark_active)
        self.connect("motion-notify-event", self.mark_active)
        self.connect("button-press-event", self.mark_active)
        self.connect("key-press-event", self.on_key_press)
        GLib.timeout_add_seconds(1, self.close_if_idle)
        GLib.timeout_add_seconds(3, self.refresh_if_open)

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

        .localsend-icon {
            font-family: "0xProto Nerd Font Mono";
            font-size: 28px;
        }

        .title {
            font-weight: 700;
            font-size: 16px;
        }

        .section-title {
            color: rgba(255, 255, 255, 0.72);
            font-size: 11px;
            font-weight: 700;
        }

        .name {
            font-weight: 700;
        }

        .meta {
            color: rgba(255, 255, 255, 0.68);
            font-size: 11px;
        }

        button {
            min-height: 30px;
            padding: 0 10px;
            border-radius: 7px;
            background: rgba(255, 255, 255, 0.12);
            color: #ffffff;
        }

        button:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        .compact {
            min-width: 54px;
            padding: 0 8px;
        }

        .power-switch {
            min-width: 36px;
            min-height: 18px;
        }

        separator {
            background: rgba(255, 255, 255, 0.12);
        }

        textview {
            background: rgba(255, 255, 255, 0.08);
            color: #ffffff;
            border-radius: 7px;
            padding: 8px;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def rebuild(self):
        for child in self.root.get_children():
            self.root.remove(child)

        state = service_state()
        running = bool(state.get("running"))

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon = Gtk.Label(label="")
        icon.get_style_context().add_class("localsend-icon")
        header.pack_start(icon, False, False, 0)

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(label="LocalSend")
        title.get_style_context().add_class("title")
        title.set_halign(Gtk.Align.START)
        labels.pack_start(title, False, False, 0)

        status = Gtk.Label(label="Companion running" if running else "Companion stopped")
        status.get_style_context().add_class("meta")
        status.set_halign(Gtk.Align.START)
        labels.pack_start(status, False, False, 0)
        header.pack_start(labels, True, True, 0)

        power = Gtk.Switch()
        power.set_size_request(36, 18)
        power.get_style_context().add_class("power-switch")
        power.set_active(running)
        power.connect("notify::active", self.on_power_changed)
        header.pack_start(power, False, False, 0)
        self.root.pack_start(header, False, False, 0)

        self.root.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        if running:
            self.add_incoming_section(state)
            self.add_devices_section(state)
            self.add_history_section(state)
        else:
            hint = Gtk.Label(label="Turn it on to discover devices and receive transfer requests.")
            hint.set_halign(Gtk.Align.START)
            hint.set_line_wrap(True)
            hint.get_style_context().add_class("meta")
            self.root.pack_start(hint, False, False, 0)

        self.add_app_section(running)
        self.show_all()

    def section_label(self, text):
        label = Gtk.Label(label=text)
        label.set_halign(Gtk.Align.START)
        label.get_style_context().add_class("section-title")
        return label

    def add_incoming_section(self, state):
        self.root.pack_start(self.section_label("Incoming"), False, False, 0)
        incoming = state.get("incoming", [])
        if not incoming:
            empty = Gtk.Label(label="No pending requests")
            empty.set_halign(Gtk.Align.START)
            empty.get_style_context().add_class("meta")
            self.root.pack_start(empty, False, False, 0)
            return

        for item in incoming:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            sender = Gtk.Label(label=item.get("sender", "Unknown sender"))
            sender.set_halign(Gtk.Align.START)
            sender.get_style_context().add_class("name")
            labels.pack_start(sender, False, False, 0)

            count = len(item.get("files", []))
            meta = Gtk.Label(label=f"{count} item{'s' if count != 1 else ''}")
            meta.set_halign(Gtk.Align.START)
            meta.get_style_context().add_class("meta")
            labels.pack_start(meta, False, False, 0)
            row.pack_start(labels, True, True, 0)

            accept = Gtk.Button(label="Accept")
            accept.get_style_context().add_class("compact")
            accept.connect("clicked", self.accept_incoming, item["id"])
            row.pack_start(accept, False, False, 0)

            reject = Gtk.Button(label="Reject")
            reject.get_style_context().add_class("compact")
            reject.connect("clicked", self.reject_incoming, item["id"])
            row.pack_start(reject, False, False, 0)
            self.root.pack_start(row, False, False, 0)

        self.root.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

    def add_devices_section(self, state):
        self.root.pack_start(self.section_label("Devices"), False, False, 0)
        devices = state.get("devices", [])
        if not devices:
            empty = Gtk.Label(label="Looking for nearby devices...")
            empty.set_halign(Gtk.Align.START)
            empty.get_style_context().add_class("meta")
            self.root.pack_start(empty, False, False, 0)
            self.root.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)
            return

        for device in devices:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            name = Gtk.Label(label=device.get("alias", "Unknown"))
            name.set_halign(Gtk.Align.START)
            name.set_ellipsize(Pango.EllipsizeMode.END)
            name.get_style_context().add_class("name")
            labels.pack_start(name, False, False, 0)

            meta = Gtk.Label(label=f"{device.get('deviceType', 'device')} at {device.get('host', '')}")
            meta.set_halign(Gtk.Align.START)
            meta.get_style_context().add_class("meta")
            labels.pack_start(meta, False, False, 0)
            row.pack_start(labels, True, True, 0)

            file_button = Gtk.Button(label="File")
            file_button.get_style_context().add_class("compact")
            file_button.connect("clicked", self.choose_files, device["id"])
            row.pack_start(file_button, False, False, 0)

            folder_button = Gtk.Button(label="Folder")
            folder_button.get_style_context().add_class("compact")
            folder_button.connect("clicked", self.choose_folders, device["id"])
            row.pack_start(folder_button, False, False, 0)

            text_button = Gtk.Button(label="Text")
            text_button.get_style_context().add_class("compact")
            text_button.connect("clicked", self.write_text, device["id"])
            row.pack_start(text_button, False, False, 0)

            self.root.pack_start(row, False, False, 0)

        self.root.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

    def add_history_section(self, state):
        transfers = state.get("transfers", [])
        if not transfers:
            return
        self.root.pack_start(self.section_label("Recent"), False, False, 0)
        for transfer in transfers[-3:]:
            label = Gtk.Label(
                label=f"{transfer.get('time', '')}  {transfer.get('label', '')}: {transfer.get('status', '')}"
            )
            label.set_halign(Gtk.Align.START)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            label.get_style_context().add_class("meta")
            self.root.pack_start(label, False, False, 0)
        self.root.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

    def add_app_section(self, running):
        self.root.pack_start(self.section_label("App"), False, False, 0)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        open_downloads = Gtk.Button(label="Downloads")
        open_downloads.connect("clicked", self.open_downloads)
        row.pack_start(open_downloads, True, True, 0)

        stop = Gtk.Button(label="Stop" if running else "Start")
        stop.connect("clicked", self.toggle_service_button, running)
        row.pack_start(stop, True, True, 0)
        self.root.pack_start(row, False, False, 0)

    def on_power_changed(self, switch, _param):
        self.mark_active()
        if switch.get_active():
            run(SERVICE, "start")
        else:
            run(SERVICE, "stop")
        GLib.timeout_add(400, self.refresh_once)

    def toggle_service_button(self, _button, running):
        self.mark_active()
        run(SERVICE, "stop" if running else "start")
        GLib.timeout_add(400, self.refresh_once)

    def accept_incoming(self, _button, session_id):
        self.mark_active()
        post_empty(f"/waybar/accept?id={session_id}")
        self.refresh_once()

    def reject_incoming(self, _button, session_id):
        self.mark_active()
        post_empty(f"/waybar/reject?id={session_id}")
        self.refresh_once()

    def choose_files(self, _button, device_id):
        self.choose_paths(device_id, "Send Files", Gtk.FileChooserAction.OPEN)

    def choose_folders(self, _button, device_id):
        self.choose_paths(device_id, "Send Folders", Gtk.FileChooserAction.SELECT_FOLDER)

    def choose_paths(self, device_id, title, action):
        self.mark_active()
        dialog = Gtk.FileChooserDialog(title=title, parent=self, action=action)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, "Send", Gtk.ResponseType.OK)
        dialog.set_select_multiple(True)
        response = dialog.run()
        paths = dialog.get_filenames() if response == Gtk.ResponseType.OK else []
        dialog.destroy()
        if paths:
            post_json("/waybar/send", {"device_id": device_id, "paths": paths})
            self.refresh_once()

    def write_text(self, _button, device_id):
        self.mark_active()
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        initial_text = clipboard.wait_for_text() or ""
        dialog = Gtk.Dialog(title="Send Text", parent=self, flags=Gtk.DialogFlags.MODAL)
        dialog.set_default_size(420, 240)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, "Send", Gtk.ResponseType.OK)
        box = dialog.get_content_area()
        box.set_spacing(10)
        box.set_border_width(10)

        text_view = Gtk.TextView()
        text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        text_view.set_size_request(380, 150)
        buffer = text_view.get_buffer()
        buffer.set_text(initial_text)
        box.pack_start(text_view, True, True, 0)

        dialog.show_all()
        response = dialog.run()
        start, end = buffer.get_bounds()
        text = buffer.get_text(start, end, True).strip()
        dialog.destroy()
        if response == Gtk.ResponseType.OK and text:
            post_json(
                "/waybar/send",
                {"device_id": device_id, "text": text, "label": "message.txt"},
            )
            self.refresh_once()

    def open_downloads(self, _button):
        self.mark_active()
        subprocess.Popen(["xdg-open", DOWNLOADS_PATH])
        Gtk.main_quit()

    def refresh_once(self):
        self.rebuild()
        return GLib.SOURCE_REMOVE

    def refresh_if_open(self):
        self.rebuild()
        return GLib.SOURCE_CONTINUE

    def on_key_press(self, _window, event):
        self.mark_active()
        if event.keyval == Gdk.KEY_Escape:
            Gtk.main_quit()

    def mark_active(self, *_args):
        self.last_activity = time.monotonic()
        return False

    def close_if_idle(self):
        if time.monotonic() - self.last_activity > 30:
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
    window = LocalSendMenu()
    window.present_near_top_right()
    Gtk.main()


if __name__ == "__main__":
    main()
