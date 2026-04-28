#!/usr/bin/env python3

import fcntl
import signal
import subprocess
import sys
import time

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402


LOCK_PATH = "/tmp/waybar-brightness-slider.lock"
OSD_ACTIVITY_PATH = "/tmp/waybar-brightness-slider-osd.activity"
OSD_IDLE_SECONDS = 3
MANUAL_IDLE_SECONDS = 12


def run(*args):
    return subprocess.run(args, check=False, capture_output=True, text=True)


def brightness_value(command):
    result = run("brightnessctl", command)
    try:
        return int(result.stdout.strip())
    except ValueError:
        return 0


def current_brightness():
    current = brightness_value("get")
    maximum = brightness_value("max")
    if maximum <= 0:
        return 50

    return max(0, min(100, round((current / maximum) * 100)))


def touch_osd_activity():
    with open(OSD_ACTIVITY_PATH, "w") as activity_file:
        activity_file.write(str(time.monotonic()))


def osd_activity_time():
    try:
        with open(OSD_ACTIVITY_PATH) as activity_file:
            return float(activity_file.read().strip())
    except (FileNotFoundError, ValueError):
        return 0


def change_brightness(direction):
    if direction == "up":
        run("brightnessctl", "-e4", "-n2", "set", "5%+")
    elif direction == "down":
        run("brightnessctl", "-e4", "-n2", "set", "5%-")
    else:
        raise ValueError(f"Unknown brightness direction: {direction}")


class BrightnessSlider(Gtk.Window):
    def __init__(self, osd_mode=False):
        super().__init__(title="Brightness")

        self.osd_mode = osd_mode
        self.last_brightness = current_brightness()
        self.last_activity = osd_activity_time() if osd_mode else time.monotonic()
        self.syncing_scale = False

        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_accept_focus(not osd_mode)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_border_width(12)
        if not osd_mode:
            self.add_events(
                Gdk.EventMask.ENTER_NOTIFY_MASK
                | Gdk.EventMask.POINTER_MOTION_MASK
                | Gdk.EventMask.BUTTON_PRESS_MASK
            )

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.add(box)

        icon = Gtk.Label(label="󰝩")
        icon.get_style_context().add_class("brightness-icon")
        icon.set_halign(Gtk.Align.CENTER)
        box.pack_start(icon, False, False, 0)

        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.scale.set_value(self.last_brightness)
        self.scale.set_draw_value(False)
        self.scale.set_can_focus(not osd_mode)
        self.scale.set_size_request(210, -1)
        self.scale.connect("value-changed", self.on_value_changed)
        if osd_mode:
            self.scale.connect("button-press-event", self.suppress_user_input)
            self.scale.connect("button-release-event", self.suppress_user_input)
            self.scale.connect("motion-notify-event", self.suppress_user_input)
            self.scale.connect("scroll-event", self.suppress_user_input)
        box.pack_start(self.scale, True, True, 0)

        if not osd_mode:
            self.connect("enter-notify-event", self.mark_active)
            self.connect("motion-notify-event", self.mark_active)
            self.connect("button-press-event", self.mark_active)
            self.connect("key-press-event", self.on_key_press)
        GLib.timeout_add_seconds(1, self.close_if_idle)
        if osd_mode:
            GLib.timeout_add(100, self.sync_osd_brightness)

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

        .brightness-icon {
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
        if self.syncing_scale:
            return

        self.mark_active()
        brightness = round(scale.get_value())
        if brightness == self.last_brightness:
            return

        self.last_brightness = brightness
        run("brightnessctl", "-e4", "-n2", "set", f"{brightness}%")

    def on_key_press(self, _window, event):
        self.mark_active()
        if event.keyval == Gdk.KEY_Escape:
            Gtk.main_quit()

    def mark_active(self, *_args):
        self.last_activity = time.monotonic()
        return False

    def suppress_user_input(self, *_args):
        return True

    def sync_osd_brightness(self):
        self.last_activity = max(self.last_activity, osd_activity_time())
        brightness = current_brightness()
        if brightness != self.last_brightness:
            self.last_brightness = brightness
            self.syncing_scale = True
            self.scale.set_value(brightness)
            self.syncing_scale = False

        return GLib.SOURCE_CONTINUE

    def close_if_idle(self):
        idle_seconds = OSD_IDLE_SECONDS if self.osd_mode else MANUAL_IDLE_SECONDS
        if time.monotonic() - self.last_activity > idle_seconds:
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
    osd_mode = len(sys.argv) == 3 and sys.argv[1] == "--osd"
    if osd_mode:
        change_brightness(sys.argv[2])
        touch_osd_activity()

    lock_file = open(LOCK_PATH, "w")
    try:
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    window = BrightnessSlider(osd_mode=osd_mode)
    window.present_near_top_right()
    Gtk.main()


if __name__ == "__main__":
    main()
