#!/usr/bin/env python3

import fcntl
import os
import signal
import subprocess
import time
import threading
from pathlib import Path

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402


LOCK_PATH = "/tmp/waybar-battery-menu.lock"
PROFILE_FILE = os.path.expanduser("~/.local/state/power-profile")
PROFILE_SCRIPT = os.path.expanduser("~/.config/eww/scripts/battery-profile.sh")
CHARGE_HELPER = "/usr/local/bin/waybar-charge-limit"
CHARGE_LIMIT = Path("/sys/class/power_supply/BAT0/charge_control_end_threshold")

PROFILES = [
    {"id": "normal",  "icon": "󰓡", "name": "Normal",  "desc": "Balanced power"},
    {"id": "content", "icon": "󰿎", "name": "Content", "desc": "Audio & visual focus"},
    {"id": "coding",  "icon": "󰘧", "name": "Coding",  "desc": "Battery saver"},
]


def run(*args):
    return subprocess.run(args, check=False, capture_output=True, text=True)


def battery_info():
    try:
        with open("/sys/class/power_supply/BAT0/capacity") as f:
            capacity = int(f.read().strip())
        with open("/sys/class/power_supply/BAT0/status") as f:
            status = f.read().strip()
        charging = status == "Charging"
    except OSError:
        capacity = 0
        charging = False
    return {"capacity": capacity, "charging": charging}


def current_profile():
    try:
        with open(PROFILE_FILE) as f:
            return f.read().strip()
    except OSError:
        return "normal"


def battery_icon(capacity, charging):
    if charging:
        return ""
    if capacity >= 95:
        return ""
    if capacity >= 70:
        return ""
    if capacity >= 45:
        return ""
    if capacity >= 20:
        return ""
    return ""


class BatteryMenu(Gtk.Window):
    def __init__(self):
        super().__init__(title="Battery")

        self.last_activity = time.monotonic()
        self.applying_limit = False

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

        .battery-icon {
            font-family: "0xProto Nerd Font Mono";
            font-size: 22px;
        }

        .profile-icon {
            font-family: "0xProto Nerd Font Mono";
            font-size: 18px;
            min-width: 26px;
        }

        .battery-pct {
            font-weight: 700;
            font-size: 20px;
        }

        .charging {
            color: #4CAF50;
        }

        .status-label {
            color: rgba(255, 255, 255, 0.55);
            font-size: 11px;
        }

        .status-charging {
            color: #4CAF50;
            font-size: 11px;
        }

        .profile-name {
            font-weight: 600;
        }

        .profile-desc {
            color: rgba(255, 255, 255, 0.55);
            font-size: 11px;
        }

        button {
            min-height: 28px;
            padding: 6px 10px;
            border-radius: 7px;
            background: rgba(255, 255, 255, 0.08);
            color: #ffffff;
        }

        button:hover {
            background: rgba(255, 255, 255, 0.18);
        }

        button.active {
            background: rgba(255, 255, 255, 0.22);
            border: 1px solid rgba(255, 255, 255, 0.28);
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

        info = battery_info()
        profile = current_profile()

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        bat_icon = Gtk.Label(label=battery_icon(info["capacity"], info["charging"]))
        bat_icon.get_style_context().add_class("battery-icon")
        if info["charging"]:
            bat_icon.get_style_context().add_class("charging")
        header.pack_start(bat_icon, False, False, 0)

        title = Gtk.Label(label="Battery")
        title.get_style_context().add_class("title")
        title.set_halign(Gtk.Align.START)
        header.pack_start(title, True, True, 0)

        pct = Gtk.Label(label=f"{info['capacity']}%")
        pct.get_style_context().add_class("battery-pct")
        if info["charging"]:
            pct.get_style_context().add_class("charging")
        header.pack_start(pct, False, False, 0)
        self.root.pack_start(header, False, False, 0)

        self.root.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0
        )

        profile_title = Gtk.Label(label="Power Profile")
        profile_title.get_style_context().add_class("title")
        profile_title.set_halign(Gtk.Align.START)
        self.root.pack_start(profile_title, False, False, 0)

        for p in PROFILES:
            btn = Gtk.Button()
            btn.set_relief(Gtk.ReliefStyle.NONE)
            if p["id"] == profile:
                btn.get_style_context().add_class("active")

            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

            icon = Gtk.Label(label=p["icon"])
            icon.get_style_context().add_class("profile-icon")
            row.pack_start(icon, False, False, 0)

            name = Gtk.Label(label=p["name"])
            name.set_halign(Gtk.Align.START)
            name.get_style_context().add_class("profile-name")
            row.pack_start(name, True, True, 0)
            btn.add(row)
            btn.connect("clicked", self.on_profile_clicked, p["id"])
            self.root.pack_start(btn, False, False, 0)

        self.root.pack_start(Gtk.Separator(), False, False, 0)
        title = Gtk.Label(label="Charging limit", xalign=0)
        title.get_style_context().add_class("title")
        self.root.pack_start(title, False, False, 0)
        self.charge_status = Gtk.Label(xalign=0)
        self.charge_status.set_line_wrap(True)
        self.charge_status.set_max_width_chars(42)
        try:
            limit = int(CHARGE_LIMIT.read_text().strip())
            self.limit_control = Gtk.SpinButton.new_with_range(50, 100, 5)
            self.limit_control.set_value(limit)
            self.limit_control.connect("value-changed", self.mark_active)
            row = Gtk.Box(spacing=8)
            row.pack_start(self.limit_control, True, True, 0)
            row.pack_start(Gtk.Label(label="%"), False, False, 0)
            self.apply_button = Gtk.Button(label="Apply")
            self.apply_button.connect("clicked", self.on_limit_clicked)
            self.apply_button.set_sensitive(Path(CHARGE_HELPER).is_file())
            row.pack_start(self.apply_button, False, False, 0)
            self.root.pack_start(row, False, False, 0)
            self.charge_status.set_text(f"Currently stops at {limit}%. Changes require authentication.")
        except (OSError, ValueError):
            self.charge_status.set_text("Charging limits are not available on this battery.")
        self.root.pack_start(self.charge_status, False, False, 0)

        self.show_all()
        return GLib.SOURCE_REMOVE

    def on_limit_clicked(self, _button):
        self.mark_active()
        limit = self.limit_control.get_value_as_int()
        self.applying_limit = True
        self.root.set_sensitive(False)
        self.charge_status.set_text("Authenticate to save the charging limit…")
        def work():
            try:
                result = subprocess.run(["pkexec", CHARGE_HELPER, str(limit)],
                                        capture_output=True, text=True, timeout=120)
                if result.returncode == 0:
                    message = result.stdout.strip()
                elif result.returncode in (126, 127):
                    message = "Authentication cancelled or denied. Limit was not changed."
                else:
                    message = result.stderr.strip() or "Could not change the charging limit."
            except (OSError, subprocess.SubprocessError) as error:
                message = str(error)
            GLib.idle_add(self.limit_applied, message)
        threading.Thread(target=work, daemon=True).start()

    def limit_applied(self, message):
        self.applying_limit = False
        self.mark_active()
        self.root.set_sensitive(True)
        try:
            self.limit_control.set_value(int(CHARGE_LIMIT.read_text().strip()))
        except (OSError, ValueError):
            pass
        self.charge_status.set_text(message)
        return GLib.SOURCE_REMOVE

    def on_profile_clicked(self, _button, profile_id):
        self.mark_active()
        subprocess.Popen([PROFILE_SCRIPT, profile_id])
        GLib.timeout_add(500, self.rebuild)

    def on_key_press(self, _window, event):
        self.mark_active()
        if event.keyval == Gdk.KEY_Escape:
            Gtk.main_quit()

    def mark_active(self, *_args):
        self.last_activity = time.monotonic()
        return False

    def close_if_idle(self):
        if self.applying_limit:
            return GLib.SOURCE_CONTINUE
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
        self.move(geometry.x + geometry.width - width - 16, geometry.y + 34)
        self.present()


def main():
    lock_file = open(LOCK_PATH, "w")
    try:
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    window = BatteryMenu()
    window.present_near_top_right()
    Gtk.main()


if __name__ == "__main__":
    main()
