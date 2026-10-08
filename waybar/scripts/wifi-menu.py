#!/usr/bin/env python3

import fcntl
import os
import re
import signal
import subprocess
import time

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402


LOCK_PATH = "/tmp/waybar-wifi-menu.lock"
VPN_CONNECT_SCRIPT = os.path.expanduser("~/.config/eww/scripts/vpn-connect.sh")
VPN_TOGGLE_SCRIPT  = os.path.expanduser("~/.config/eww/scripts/vpn-toggle.sh")

VPN_COUNTRIES = [
    ("Streaming", ["US", "CA", "JP"]),
    ("Torrenting", ["SG", "RO", "ES"]),
    ("Privacy",    ["CH", "IS", "PA"]),
    ("Misc",       ["LK", "PG", "NZ", "AU"]),
]


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


def vpn_active():
    result = run(
        "nmcli", "-t", "--escape", "yes",
        "-f", "NAME,TYPE,DEVICE",
        "connection", "show", "--active",
    )
    for line in result.stdout.splitlines():
        fields = split_nmcli_line(line)
        if len(fields) < 3:
            continue
        name, conn_type, device = fields[:3]
        if (
            conn_type in {"vpn", "wireguard"}
            or re.match(r"^(tun|wg|ppp)", device)
            or "proton" in name.lower()
        ):
            return name
    return None


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

        button:disabled {
            color: rgba(255, 255, 255, 0.3);
            background: rgba(255, 255, 255, 0.06);
        }

        separator {
            background: rgba(255, 255, 255, 0.12);
        }

        .vpn-icon {
            font-family: "0xProto Nerd Font Mono";
            font-size: 20px;
        }

        .vpn-connected {
            color: #4CAF50;
        }

        .country-btn {
            min-height: 24px;
            padding: 0 6px;
            font-size: 11px;
            font-weight: 600;
        }

        .section-label {
            color: rgba(255, 255, 255, 0.45);
            font-size: 11px;
            font-weight: 600;
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

        # ── VPN section ──────────────────────────────────────────────
        self.root.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0
        )

        active_vpn = vpn_active()

        vpn_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        vpn_icon = Gtk.Label(label="" if active_vpn else "")
        vpn_icon.get_style_context().add_class("vpn-icon")
        if active_vpn:
            vpn_icon.get_style_context().add_class("vpn-connected")
        vpn_header.pack_start(vpn_icon, False, False, 0)

        vpn_title = Gtk.Label(label="ProtonVPN")
        vpn_title.get_style_context().add_class("title")
        vpn_title.set_halign(Gtk.Align.START)
        vpn_header.pack_start(vpn_title, True, True, 0)
        self.root.pack_start(vpn_header, False, False, 0)

        if active_vpn:
            conn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            conn_row.set_size_request(300, -1)
            conn_name = Gtk.Label(label=active_vpn)
            conn_name.set_halign(Gtk.Align.START)
            conn_name.set_ellipsize(Pango.EllipsizeMode.END)
            conn_name.get_style_context().add_class("network-name")
            conn_row.pack_start(conn_name, True, True, 0)

            disc_btn = Gtk.Button(label="Disconnect")
            disc_btn.connect("clicked", self.vpn_disconnect)
            conn_row.pack_start(disc_btn, False, False, 0)
            self.root.pack_start(conn_row, False, False, 0)
        else:
            quick = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            fastest_btn = Gtk.Button(label="Fastest")
            fastest_btn.connect("clicked", self.vpn_connect, "fastest")
            quick.pack_start(fastest_btn, True, True, 0)

            p2p_btn = Gtk.Button(label="P2P")
            p2p_btn.connect("clicked", self.vpn_connect, "p2p")
            quick.pack_start(p2p_btn, True, True, 0)
            self.root.pack_start(quick, False, False, 0)

            for label, countries in VPN_COUNTRIES:
                cat_label = Gtk.Label(label=label)
                cat_label.set_halign(Gtk.Align.START)
                cat_label.get_style_context().add_class("section-label")
                self.root.pack_start(cat_label, False, False, 0)

                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
                for cc in countries:
                    btn = Gtk.Button(label=cc)
                    btn.get_style_context().add_class("country-btn")
                    btn.connect("clicked", self.vpn_connect, cc)
                    row.pack_start(btn, True, True, 0)
                self.root.pack_start(row, False, False, 0)

        self.show_all()

    def network_row(self, network, device):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.set_size_request(300, -1)

        icon = Gtk.Label(label=signal_icon(network["signal"]))
        icon.get_style_context().add_class("wifi-icon")
        row.pack_start(icon, False, False, 0)

        name = Gtk.Label(label=network["ssid"])
        name.set_halign(Gtk.Align.START)
        name.set_ellipsize(Pango.EllipsizeMode.END)
        name.get_style_context().add_class("network-name")
        row.pack_start(name, True, True, 0)

        action = Gtk.Button(label=self.action_label(network))
        action.connect("clicked", self.on_network_action, network, device)
        row.pack_start(action, False, False, 0)

        return row

    def action_label(self, network):
        if network["active"]:
            return "Disconnect"
        if network["known"]:
            return "Connect"
        return "Join..."

    def vpn_connect(self, _button, arg):
        self.mark_active()
        subprocess.Popen([VPN_CONNECT_SCRIPT, arg])
        Gtk.main_quit()

    def vpn_disconnect(self, _button):
        self.mark_active()
        subprocess.Popen([VPN_TOGGLE_SCRIPT, "true"])
        Gtk.main_quit()

    def on_power_changed(self, switch, _param):
        self.mark_active()
        state = "on" if switch.get_active() else "off"
        run("nmcli", "radio", "wifi", state)
        GLib.timeout_add(800, self.refresh)

    def on_network_action(self, button, network, device):
        self.mark_active()
        if network["active"]:
            button.set_label("Disconnecting…")
            button.set_sensitive(False)
            if device["name"]:
                run("nmcli", "device", "disconnect", device["name"])
            GLib.timeout_add(800, self.refresh)
            return

        if network["known"]:
            button.set_label("Connecting…")
            button.set_sensitive(False)
            run("nmcli", "connection", "up", "id", network["ssid"])
            GLib.timeout_add(1200, self.refresh)
            return

        self.open_manager()

    def refresh_scan(self, button):
        self.mark_active()
        button.set_label("Scanning…")
        button.set_sensitive(False)
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
            geometry.x + geometry.width - width - 16,
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
