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


LOCK_PATH = "/tmp/waybar-wifi-menu.lock"


def run(*args):
    return subprocess.run(args, check=False, capture_output=True, text=True)


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


def wifi_enabled():
    return run("nmcli", "-t", "-f", "WIFI", "g").stdout.strip() == "enabled"


def wifi_device():
    status = run("nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status")
    for line in status.stdout.splitlines():
        fields = split_nmcli_line(line)
        if len(fields) >= 2 and fields[1] == "wifi":
            return {
                "name": fields[0],
                "state": fields[2] if len(fields) > 2 else "",
                "connection": fields[3] if len(fields) > 3 else "",
            }

    return {"name": "", "state": "unavailable", "connection": ""}


def known_connections():
    result = run("nmcli", "-t", "--escape", "yes", "-f", "NAME,TYPE", "connection", "show")
    known = set()
    for line in result.stdout.splitlines():
        fields = split_nmcli_line(line)
        if len(fields) >= 2 and fields[1] == "802-11-wireless":
            known.add(fields[0])
    return known


def wifi_networks():
    result = run(
        "nmcli",
        "-t",
        "--escape",
        "yes",
        "-f",
        "IN-USE,SSID,SIGNAL,SECURITY",
        "device",
        "wifi",
        "list",
        "--rescan",
        "no",
    )
    known = known_connections()
    networks = []
    seen = set()

    for line in result.stdout.splitlines():
        fields = split_nmcli_line(line)
        if len(fields) < 4:
            continue

        active, ssid, signal_strength, security = fields[:4]
        if not ssid or ssid in seen:
            continue

        seen.add(ssid)
        networks.append(
            {
                "active": active == "*",
                "ssid": ssid,
                "signal": signal_strength,
                "security": security or "Open",
                "known": ssid in known,
            }
        )

    return networks


def signal_icon(signal_strength):
    try:
        signal_value = int(signal_strength)
    except ValueError:
        return "󰤯"

    if signal_value >= 75:
        return "󰤨"
    if signal_value >= 50:
        return "󰤥"
    if signal_value >= 25:
        return "󰤢"
    return "󰤟"


class WifiMenu(Gtk.Window):
    def __init__(self):
        super().__init__(title="Wi-Fi")

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

        .wifi-icon {
            font-family: "0xProto Nerd Font Mono";
            font-size: 20px;
        }

        .network-name {
            font-weight: 700;
        }

        .network-status {
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

        enabled = wifi_enabled()
        device = wifi_device()

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon = Gtk.Label(label="")
        icon.get_style_context().add_class("wifi-icon")
        header.pack_start(icon, False, False, 0)

        title = Gtk.Label(label="Wi-Fi")
        title.get_style_context().add_class("title")
        title.set_halign(Gtk.Align.START)
        header.pack_start(title, True, True, 0)

        power = Gtk.Switch()
        power.set_active(enabled)
        power.connect("notify::active", self.on_power_changed)
        header.pack_start(power, False, False, 0)
        self.root.pack_start(header, False, False, 0)

        status = Gtk.Label(label=self.status_text(enabled, device))
        status.set_halign(Gtk.Align.START)
        status.get_style_context().add_class("network-status")
        self.root.pack_start(status, False, False, 0)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.root.pack_start(separator, False, False, 0)

        if enabled:
            networks = wifi_networks()
            if networks:
                for network in networks[:8]:
                    self.root.pack_start(self.network_row(network, device), False, False, 0)
            else:
                empty = Gtk.Label(label="No networks found")
                empty.set_halign(Gtk.Align.START)
                empty.get_style_context().add_class("network-status")
                self.root.pack_start(empty, False, False, 0)
        else:
            off = Gtk.Label(label="Wi-Fi is off")
            off.set_halign(Gtk.Align.START)
            off.get_style_context().add_class("network-status")
            self.root.pack_start(off, False, False, 0)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        refresh = Gtk.Button(label="Refresh")
        refresh.connect("clicked", self.refresh_scan)
        footer.pack_start(refresh, True, True, 0)

        manager = Gtk.Button(label="Open TUI")
        manager.connect("clicked", self.open_manager)
        footer.pack_start(manager, True, True, 0)
        self.root.pack_start(footer, False, False, 0)

        self.show_all()

    def status_text(self, enabled, device):
        if not enabled:
            return "Disabled"
        if device["state"] == "connected" and device["connection"]:
            return f"Connected to {device['connection']}"
        if device["state"]:
            return device["state"].replace("-", " ").title()
        return "No Wi-Fi adapter"

    def network_row(self, network, device):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.set_size_request(300, -1)

        icon = Gtk.Label(label=signal_icon(network["signal"]))
        icon.get_style_context().add_class("wifi-icon")
        row.pack_start(icon, False, False, 0)

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        name = Gtk.Label(label=network["ssid"])
        name.set_halign(Gtk.Align.START)
        name.set_ellipsize(Pango.EllipsizeMode.END)
        name.get_style_context().add_class("network-name")
        labels.pack_start(name, False, False, 0)

        detail = self.network_detail(network)
        status = Gtk.Label(label=detail)
        status.set_halign(Gtk.Align.START)
        status.get_style_context().add_class("network-status")
        labels.pack_start(status, False, False, 0)
        row.pack_start(labels, True, True, 0)

        action = Gtk.Button(label=self.action_label(network))
        action.connect("clicked", self.on_network_action, network, device)
        row.pack_start(action, False, False, 0)

        return row

    def network_detail(self, network):
        if network["active"]:
            return f"Connected · {network['signal']}%"
        if network["known"]:
            return f"Known · {network['signal']}%"
        return f"{network['security']} · {network['signal']}%"

    def action_label(self, network):
        if network["active"]:
            return "Disconnect"
        if network["known"]:
            return "Connect"
        return "Join..."

    def on_power_changed(self, switch, _param):
        self.mark_active()
        state = "on" if switch.get_active() else "off"
        run("nmcli", "radio", "wifi", state)
        GLib.timeout_add(800, self.refresh)

    def on_network_action(self, _button, network, device):
        self.mark_active()
        if network["active"]:
            if device["name"]:
                run("nmcli", "device", "disconnect", device["name"])
            GLib.timeout_add(800, self.refresh)
            return

        if network["known"]:
            run("nmcli", "connection", "up", "id", network["ssid"])
            GLib.timeout_add(1200, self.refresh)
            return

        self.open_manager()

    def refresh_scan(self, _button):
        self.mark_active()
        run("nmcli", "device", "wifi", "rescan")
        GLib.timeout_add(1200, self.refresh)

    def refresh(self):
        self.rebuild()
        return GLib.SOURCE_REMOVE

    def open_manager(self, *_args):
        self.mark_active()
        subprocess.Popen(["kitty", "-e", "nmtui-connect"])
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
    window = WifiMenu()
    window.present_near_top_right()
    Gtk.main()


if __name__ == "__main__":
    main()
