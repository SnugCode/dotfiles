#!/usr/bin/env python3

import fcntl
import signal
import subprocess
import threading
import time

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402


LOCK_PATH = "/tmp/waybar-settings-menu.lock"


def run(*args):
    return subprocess.run(args, check=False, capture_output=True, text=True)


def notify(title, body, urgency="normal"):
    run("notify-send", "-u", urgency, title, body)


def update_count():
    result = run("pacman", "-Qu")
    return len([l for l in result.stdout.splitlines() if l.strip()])


class SettingsMenu(Gtk.Window):
    def __init__(self):
        super().__init__(title="Settings")

        self.last_activity = time.monotonic()
        self.updating = False

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

        .settings-icon {
            font-family: "0xProto Nerd Font Mono";
            font-size: 22px;
        }

        .item-icon {
            font-family: "0xProto Nerd Font Mono";
            font-size: 18px;
            min-width: 26px;
        }

        .item-name {
            font-weight: 600;
        }

        .item-desc {
            color: rgba(255, 255, 255, 0.55);
            font-size: 11px;
        }

        .updates-pending {
            color: #FF9800;
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

        button:disabled {
            color: rgba(255, 255, 255, 0.3);
            background: rgba(255, 255, 255, 0.04);
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

        count = update_count()

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon = Gtk.Label(label="󰒓")
        icon.get_style_context().add_class("settings-icon")
        header.pack_start(icon, False, False, 0)

        title = Gtk.Label(label="Settings")
        title.get_style_context().add_class("title")
        title.set_halign(Gtk.Align.START)
        header.pack_start(title, True, True, 0)
        self.root.pack_start(header, False, False, 0)

        self.root.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0
        )

        self.root.pack_start(
            self.action_row(icon="󰐥", name="Shutdown", callback=self.shutdown),
            False, False, 0,
        )

        self.root.pack_start(
            self.action_row(icon="󰜉", name="Restart", callback=self.restart),
            False, False, 0,
        )

        self.root.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0
        )

        self.root.pack_start(
            self.action_row(
                icon="󰮗",
                name="System Update" if not self.updating else "Updating…",
                callback=self.run_update,
                sensitive=not self.updating,
            ),
            False, False, 0,
        )

        self.show_all()
        return GLib.SOURCE_REMOVE

    def action_row(self, icon, name, callback, sensitive=True):
        btn = Gtk.Button()
        btn.set_relief(Gtk.ReliefStyle.NONE)
        btn.set_sensitive(sensitive)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.set_size_request(260, -1)

        icon_label = Gtk.Label(label=icon)
        icon_label.get_style_context().add_class("item-icon")
        row.pack_start(icon_label, False, False, 0)

        name_label = Gtk.Label(label=name)
        name_label.set_halign(Gtk.Align.START)
        name_label.get_style_context().add_class("item-name")
        row.pack_start(name_label, True, True, 0)

        btn.add(row)
        btn.connect("clicked", callback)
        return btn

    def run_update(self, _button):
        self.mark_active()
        self.updating = True
        notify("System Update", "Starting system update…")

        def do_update():
            result = subprocess.run(
                ["pkexec", "pacman", "-Syu", "--noconfirm"],
                capture_output=True,
                text=True,
            )
            self.updating = False
            if result.returncode == 0:
                GLib.idle_add(notify, "System Update", "Update complete.", "normal")
            else:
                GLib.idle_add(notify, "System Update", "Update failed.", "critical")

        threading.Thread(target=do_update, daemon=True).start()
        Gtk.main_quit()

    def restart(self, _button):
        self.mark_active()
        run("systemctl", "reboot")

    def shutdown(self, _button):
        self.mark_active()
        run("systemctl", "poweroff")

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
        self.move(geometry.x + geometry.width - width - 16, geometry.y + 34)
        self.present()


def main():
    lock_file = open(LOCK_PATH, "w")
    try:
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    window = SettingsMenu()
    window.present_near_top_right()
    Gtk.main()


if __name__ == "__main__":
    main()
