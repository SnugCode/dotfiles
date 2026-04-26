#!/usr/bin/env python3

import re
import signal
import subprocess
import fcntl
import time

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402


SINK = "@DEFAULT_AUDIO_SINK@"
WAYBAR_SIGNAL = "RTMIN+8"
LOCK_PATH = "/tmp/waybar-volume-slider.lock"


def run(*args):
    return subprocess.run(args, check=False, capture_output=True, text=True)


def current_volume():
    result = run("wpctl", "get-volume", SINK)
    match = re.search(r"Volume:\s*([0-9.]+)", result.stdout)
    if not match:
        return 50

    return max(0, min(150, round(float(match.group(1)) * 100)))


def refresh_waybar():
    run("pkill", f"-{WAYBAR_SIGNAL}", "waybar")


class VolumeSlider(Gtk.Window):
    def __init__(self):
        super().__init__(title="Volume")

        self.last_volume = current_volume()
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

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.add(box)

        icon = Gtk.Label(label="")
        icon.get_style_context().add_class("volume-icon")
        icon.set_halign(Gtk.Align.CENTER)
        box.pack_start(icon, False, False, 0)

        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 150, 1)
        self.scale.set_value(self.last_volume)
        self.scale.set_draw_value(False)
        self.scale.set_size_request(210, -1)
        self.scale.connect("value-changed", self.on_value_changed)
        box.pack_start(self.scale, True, True, 0)

        self.connect("enter-notify-event", self.mark_active)
        self.connect("motion-notify-event", self.mark_active)
        self.connect("button-press-event", self.mark_active)
        self.connect("key-press-event", self.on_key_press)
        GLib.timeout_add_seconds(1, self.close_if_idle)

        css = b"""
        window {
            background: rgba(18, 18, 18, 0.96);
            border: 1px solid rgba(255, 255, 255, 0.14);
            border-radius: 8px;
            color: #ffffff;
        }

        scale trough {
            min-height: 6px;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.22);
        }

        scale highlight {
            border-radius: 999px;
            background: #ffffff;
        }

        scale slider {
            min-width: 14px;
            min-height: 14px;
            border-radius: 999px;
            background: #ffffff;
            box-shadow: none;
        }

        .volume-icon {
            font-family: "0xProto Nerd Font Mono";
            font-size: 64px;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def on_value_changed(self, scale):
        self.mark_active()
        volume = round(scale.get_value())
        if volume == self.last_volume:
            return

        self.last_volume = volume
        run("wpctl", "set-mute", SINK, "0")
        run("wpctl", "set-volume", SINK, f"{volume}%")
        refresh_waybar()

    def on_key_press(self, _window, event):
        self.mark_active()
        if event.keyval == Gdk.KEY_Escape:
            Gtk.main_quit()

    def mark_active(self, *_args):
        self.last_activity = time.monotonic()
        return False

    def close_if_idle(self):
        if time.monotonic() - self.last_activity > 12:
            Gtk.main_quit()
            return GLib.SOURCE_REMOVE

        return GLib.SOURCE_CONTINUE

    def present_near_top_right(self):
        self.show_all()

        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        geometry = monitor.get_geometry()

        width, height = self.get_size()
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
    window = VolumeSlider()
    window.present_near_top_right()
    Gtk.main()


if __name__ == "__main__":
    main()
