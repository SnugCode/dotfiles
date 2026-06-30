#!/usr/bin/env python3

import fcntl
import re
import signal
import subprocess
import time

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402


LOCK_PATH = "/tmp/waybar-protonvpn-menu.lock"


def run(*args):
    try:
        return subprocess.run(args, check=False, capture_output=True, text=True)
    except FileNotFoundError as error:
        return subprocess.CompletedProcess(args, 127, "", str(error))


def split_nmcli_line(line):
    fields = []
    current = []
    escaped = False

    for char in line:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            fields.append("".join(current))
            current = []
        else:
            current.append(char)

    fields.append("".join(current))
    return fields


def vpn_connections(active_only=False):
    command = [
        "nmcli",
        "-t",
        "--escape",
        "yes",
        "-f",
        "NAME,TYPE,DEVICE",
        "connection",
        "show",
    ]
    if active_only:
        command.append("--active")

    result = run(*command)
    connections = []

    for line in result.stdout.splitlines():
        fields = split_nmcli_line(line)
        if len(fields) < 3:
            continue

        name, connection_type, device = fields[:3]
        if (
            connection_type in {"vpn", "wireguard"}
            or re.match(r"^(tun|wg|ppp)", device)
            or "proton" in name.lower()
        ):
            connections.append(
                {"name": name, "type": connection_type, "device": device}
            )

    return connections

class ProtonVpnMenu(Gtk.Window):
    def __init__(self):
        super().__init__(title="Proton VPN")

        self.last_activity = time.monotonic()

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

        .vpn-icon {
            font-family: "0xProto Nerd Font Mono";
            font-size: 20px;
        }

        .vpn-name {
            font-weight: 700;
        }

        .vpn-status {
            color: rgba(255, 255, 255, 0.68);
            font-size: 11px;
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

    def rebuild(self):
        for child in self.root.get_children():
            self.root.remove(child)

        active = vpn_connections(active_only=True)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon = Gtk.Label(label="" if active else "")
        icon.get_style_context().add_class("vpn-icon")
        header.pack_start(icon, False, False, 0)

        title = Gtk.Label(label="Proton VPN")
        title.get_style_context().add_class("title")
        title.set_halign(Gtk.Align.START)
        header.pack_start(title, True, True, 0)
        self.root.pack_start(header, False, False, 0)

        status = Gtk.Label(label=self.status_text(active))
        status.set_halign(Gtk.Align.START)
        status.get_style_context().add_class("vpn-status")
        self.root.pack_start(status, False, False, 0)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.root.pack_start(separator, False, False, 0)

        if active:
            for connection in active:
                self.root.pack_start(self.connection_row(connection), False, False, 0)
        else:
            empty = Gtk.Label(label="No active VPN tunnel")
            empty.set_halign(Gtk.Align.START)
            empty.get_style_context().add_class("vpn-status")
            self.root.pack_start(empty, False, False, 0)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        open_app = Gtk.Button(label="Open Proton")
        open_app.connect("clicked", self.open_proton)
        footer.pack_start(open_app, True, True, 0)

        refresh = Gtk.Button(label="Refresh")
        refresh.connect("clicked", self.refresh_clicked)
        footer.pack_start(refresh, True, True, 0)
        self.root.pack_start(footer, False, False, 0)

        self.show_all()

    def status_text(self, active):
        if active:
            names = ", ".join(connection["name"] for connection in active)
            return f"Connected: {names}"
        return "Disconnected"

    def connection_row(self, connection):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.set_size_request(280, -1)

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        name = Gtk.Label(label=connection["name"])
        name.set_halign(Gtk.Align.START)
        name.set_ellipsize(Pango.EllipsizeMode.END)
        name.get_style_context().add_class("vpn-name")
        labels.pack_start(name, False, False, 0)

        detail = connection["device"] or connection["type"] or "VPN"
        status = Gtk.Label(label=detail)
        status.set_halign(Gtk.Align.START)
        status.get_style_context().add_class("vpn-status")
        labels.pack_start(status, False, False, 0)
        row.pack_start(labels, True, True, 0)

        action = Gtk.Button(label="Disconnect")
        action.connect("clicked", self.disconnect, connection)
        row.pack_start(action, False, False, 0)

        return row

    def disconnect(self, _button, connection):
        self.mark_active()
        run("nmcli", "connection", "down", "id", connection["name"])
        GLib.timeout_add(800, self.refresh)

    def refresh_clicked(self, _button):
        self.mark_active()
        self.refresh()

    def refresh(self):
        self.rebuild()
        subprocess.Popen(["pkill", "-RTMIN+9", "waybar"])
        return GLib.SOURCE_REMOVE

    def open_proton(self, _button):
        self.mark_active()
        subprocess.Popen(["protonvpn-app"])
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
        self.move(
            geometry.x + geometry.width - width - 12,
            geometry.y + 34,
        )
        self.present()


def main():
    lock_file = open(LOCK_PATH, "w")
    try:
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    window = ProtonVpnMenu()
    window.present_near_top_right()
    Gtk.main()


if __name__ == "__main__":
    main()
