#!/usr/bin/env python3

import re
import signal
import subprocess
import fcntl
import sys
import time
import math
import json
import threading

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402


SINK = "@DEFAULT_AUDIO_SINK@"
WAYBAR_SIGNAL = "RTMIN+8"
LOCK_PATH = "/tmp/waybar-volume-slider.lock"
OSD_ACTIVITY_PATH = "/tmp/waybar-volume-slider-osd.activity"
OSD_IDLE_SECONDS = 3
MANUAL_IDLE_SECONDS = 12

SEGMENTS      = 20
SEGMENT_W     = 14
SEGMENT_H     = 28
SEGMENT_GAP   = 3
PILL_PAD_X    = 16
PILL_PAD_Y    = 14


def run(*args):
    return subprocess.run(args, check=False, capture_output=True, text=True, timeout=5)


def audio_outputs():
    result = run("pactl", "--format=json", "list", "sinks")
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Audio service unavailable")
    return json.loads(result.stdout), run("pactl", "get-default-sink").stdout.strip()


def select_output(name):
    result = run("pactl", "set-default-sink", name)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Could not select output")
    result = run("pactl", "--format=json", "list", "sink-inputs")
    if result.returncode:
        raise RuntimeError("Output selected; could not read playing apps")
    failed = []
    for stream in json.loads(result.stdout):
        moved = run("pactl", "move-sink-input", str(stream["index"]), name)
        if moved.returncode:
            failed.append(str(stream["index"]))
    if failed:
        raise RuntimeError("Output selected; some apps could not be moved. Restart their playback.")


def current_volume():
    result = run("wpctl", "get-volume", SINK)
    match = re.search(r"Volume:\s*([0-9.]+)", result.stdout)
    if not match:
        return 50
    return max(0, min(150, round(float(match.group(1)) * 100)))


def is_muted():
    result = run("wpctl", "get-volume", SINK)
    return "[MUTED]" in result.stdout


def refresh_waybar():
    run("pkill", f"-{WAYBAR_SIGNAL}", "waybar")


def touch_osd_activity():
    with open(OSD_ACTIVITY_PATH, "w") as f:
        f.write(str(time.monotonic()))


def osd_activity_time():
    try:
        with open(OSD_ACTIVITY_PATH) as f:
            return float(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 0


def change_volume(direction):
    if direction == "up":
        run("wpctl", "set-mute", SINK, "0")
        run("wpctl", "set-volume", "-l", "1", SINK, "5%+")
    elif direction == "down":
        run("wpctl", "set-mute", SINK, "0")
        run("wpctl", "set-volume", SINK, "5%-")
    elif direction == "mute":
        run("wpctl", "set-mute", SINK, "toggle")
    else:
        raise ValueError(f"Unknown direction: {direction}")
    refresh_waybar()


_TEXT = "︎"  # variation selector: force text (monochrome) presentation

def volume_icon(volume, muted):
    if muted or volume == 0:
        return "\U0001F507" + _TEXT   # 🔇 muted
    elif volume < 34:
        return "\U0001F508" + _TEXT   # 🔈 low
    elif volume < 67:
        return "\U0001F509" + _TEXT   # 🔉 medium
    else:
        return "\U0001F50A" + _TEXT   # 🔊 high


class HSegmentBar(Gtk.DrawingArea):
    """Horizontal row of rounded segment pills."""

    def __init__(self):
        super().__init__()
        self._volume = 0
        self._muted  = False
        bar_w = SEGMENTS * SEGMENT_W + (SEGMENTS - 1) * SEGMENT_GAP
        self.set_size_request(bar_w, SEGMENT_H)
        self.connect("draw", self._on_draw)

    def set_volume(self, volume, muted):
        self._volume = volume
        self._muted  = muted
        self.queue_draw()

    def _on_draw(self, _widget, cr):
        filled = round(self._volume / 100 * SEGMENTS)
        filled = max(0, min(SEGMENTS, filled))
        r = 3.5

        for i in range(SEGMENTS):
            x = i * (SEGMENT_W + SEGMENT_GAP)
            y = 0
            w = SEGMENT_W
            h = SEGMENT_H

            active = (i < filled) and not self._muted
            if active:
                cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
            else:
                cr.set_source_rgba(1.0, 1.0, 1.0, 0.18)

            cr.new_sub_path()
            cr.arc(x + r,     y + r,     r, math.pi,           3 * math.pi / 2)
            cr.arc(x + w - r, y + r,     r, 3 * math.pi / 2,   0)
            cr.arc(x + w - r, y + h - r, r, 0,                  math.pi / 2)
            cr.arc(x + r,     y + h - r, r, math.pi / 2,        math.pi)
            cr.close_path()
            cr.fill()

        return False


class VolumeOSD(Gtk.Window):
    def __init__(self, osd_mode=False):
        super().__init__(title="Volume")

        self.osd_mode     = osd_mode
        self.last_volume  = current_volume()
        self.last_muted   = is_muted()
        self.last_activity = osd_activity_time() if osd_mode else time.monotonic()

        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_accept_focus(not osd_mode)
        self.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)

        if not osd_mode:
            self.connect("key-press-event",      self.on_key_press)
            self.connect("enter-notify-event",   self.mark_active)
            self.connect("motion-notify-event",  self.mark_active)
            self.connect("button-press-event",   self.mark_active)
            self.connect("scroll-event",         self.on_scroll)

        # ── layout ──────────────────────────────────────────────────
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        outer.set_margin_top(PILL_PAD_Y)
        outer.set_margin_bottom(PILL_PAD_Y)
        outer.set_margin_start(PILL_PAD_X)
        outer.set_margin_end(PILL_PAD_X)
        self.add(outer)

        # large centered icon
        self.icon_label = Gtk.Label()
        self.icon_label.get_style_context().add_class("vol-icon")
        self.icon_label.set_halign(Gtk.Align.CENTER)
        outer.pack_start(self.icon_label, False, False, 0)

        # horizontal segment bar
        self.seg_bar = HSegmentBar()
        outer.pack_start(self.seg_bar, False, False, 0)

        # percentage below the bar
        self.pct_label = Gtk.Label()
        self.pct_label.get_style_context().add_class("vol-pct")
        self.pct_label.set_halign(Gtk.Align.CENTER)
        outer.pack_start(self.pct_label, False, False, 0)

        self._sync_display()

        if not osd_mode:
            outer.pack_start(Gtk.Separator(), False, False, 0)
            heading = Gtk.Label(label="Audio output", xalign=0)
            outer.pack_start(heading, False, False, 0)
            self.output_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            outer.pack_start(self.output_box, False, False, 0)
            self.output_status = Gtk.Label(xalign=0)
            self.output_status.set_line_wrap(True)
            self.output_status.set_max_width_chars(45)
            outer.pack_start(self.output_status, False, False, 0)
            bluetooth = Gtk.Button(label="Connect Bluetooth headphones…")
            bluetooth.connect("clicked", self.open_bluetooth)
            outer.pack_start(bluetooth, False, False, 0)
            self.outputs_busy = False
            self.output_signature = None
            self.refresh_outputs()
            GLib.timeout_add_seconds(2, self.refresh_outputs)

        css = b"""
        window {
            background: rgba(28, 28, 30, 0.90);
            border: 1px solid rgba(255, 255, 255, 0.10);
            border-radius: 16px;
        }

        .vol-icon {
            font-size: 52px;
            color: #ffffff;
        }

        .vol-pct {
            font-size: 12px;
            font-weight: 600;
            color: rgba(255, 255, 255, 0.50);
        }
        label { color: #ffffff; }
        button { padding: 7px 10px; border-radius: 7px; color: #ffffff;
                 background: rgba(255,255,255,0.08); }
        button:hover { background: rgba(255,255,255,0.18); }
        button.active { background: rgba(80,150,240,0.3); }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        GLib.timeout_add_seconds(1, self.close_if_idle)
        if osd_mode:
            GLib.timeout_add(100, self.sync_osd_volume)

    # ── display sync ────────────────────────────────────────────────

    def open_bluetooth(self, _button):
        self.mark_active()
        subprocess.Popen(["blueman-manager"])

    def refresh_outputs(self):
        if self.outputs_busy:
            return GLib.SOURCE_CONTINUE
        self.outputs_busy = True
        def work():
            try:
                sinks, default = audio_outputs()
                GLib.idle_add(self.show_outputs, sinks, default, None)
            except (OSError, ValueError, subprocess.SubprocessError, RuntimeError) as error:
                GLib.idle_add(self.show_outputs, [], "", str(error))
        threading.Thread(target=work, daemon=True).start()
        return GLib.SOURCE_CONTINUE

    def show_outputs(self, sinks, default, error):
        self.outputs_busy = False
        if error:
            self.output_status.set_text(error)
            return GLib.SOURCE_REMOVE
        signature = [(s["name"], s.get("description"), s["name"] == default) for s in sinks]
        if signature != self.output_signature:
            self.output_signature = signature
            for child in self.output_box.get_children():
                child.destroy()
            for sink in sinks:
                active = sink["name"] == default
                button = Gtk.Button()
                row = Gtk.Box(spacing=8)
                icon = "audio-headphones" if "head" in sink.get("description", "").lower() or "airpod" in sink.get("description", "").lower() else "audio-speakers"
                row.pack_start(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.BUTTON), False, False, 0)
                row.pack_start(Gtk.Label(label=sink.get("description", sink["name"]), xalign=0), True, True, 0)
                if active:
                    row.pack_end(Gtk.Label(label="✓"), False, False, 0)
                    button.get_style_context().add_class("active")
                button.add(row)
                button.connect("clicked", self.on_output_clicked, sink["name"])
                self.output_box.pack_start(button, False, False, 0)
            self.output_box.show_all()
        self.last_volume, self.last_muted = current_volume(), is_muted()
        self._sync_display()
        return GLib.SOURCE_REMOVE

    def on_output_clicked(self, _button, name):
        self.mark_active()
        self.output_box.set_sensitive(False)
        self.output_status.set_text("Switching output…")
        def work():
            message = "Output selected"
            try:
                select_output(name)
                refresh_waybar()
            except (OSError, ValueError, subprocess.SubprocessError, RuntimeError) as error:
                message = str(error)
            GLib.idle_add(self.output_switched, message)
        threading.Thread(target=work, daemon=True).start()

    def output_switched(self, message):
        self.mark_active()
        self.output_box.set_sensitive(True)
        self.output_status.set_text(message)
        self.refresh_outputs()
        return GLib.SOURCE_REMOVE

    def _sync_display(self):
        self.icon_label.set_text(volume_icon(self.last_volume, self.last_muted))
        self.seg_bar.set_volume(self.last_volume, self.last_muted)
        label = "Muted" if self.last_muted else f"{self.last_volume}%"
        self.pct_label.set_text(label)

    # ── event handlers ───────────────────────────────────────────────

    def on_scroll(self, _widget, event):
        self.mark_active()
        if event.direction == Gdk.ScrollDirection.UP:
            change_volume("up")
        elif event.direction == Gdk.ScrollDirection.DOWN:
            change_volume("down")
        self.last_volume = current_volume()
        self.last_muted  = is_muted()
        self._sync_display()
        return True

    def on_key_press(self, _window, event):
        self.mark_active()
        if event.keyval == Gdk.KEY_Escape:
            Gtk.main_quit()

    def mark_active(self, *_args):
        self.last_activity = time.monotonic()
        return False

    def sync_osd_volume(self):
        self.last_activity = max(self.last_activity, osd_activity_time())
        volume = current_volume()
        muted  = is_muted()
        if volume != self.last_volume or muted != self.last_muted:
            self.last_volume = volume
            self.last_muted  = muted
            self._sync_display()
        return GLib.SOURCE_CONTINUE

    def close_if_idle(self):
        idle = OSD_IDLE_SECONDS if self.osd_mode else MANUAL_IDLE_SECONDS
        if time.monotonic() - self.last_activity > idle:
            Gtk.main_quit()
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    # ── positioning ──────────────────────────────────────────────────

    def present_top_center(self):
        self.show_all()
        self.realize()
        self.queue_resize()

        display  = Gdk.Display.get_default()
        monitor  = display.get_primary_monitor() or display.get_monitor(0)
        geometry = monitor.get_geometry()
        width, height = self.get_size()

        x = geometry.x + (geometry.width - width) // 2
        y = geometry.y + 40
        self.move(x, y)
        self.present()


def main():
    osd_mode = len(sys.argv) == 3 and sys.argv[1] == "--osd"
    if osd_mode:
        change_volume(sys.argv[2])
        touch_osd_activity()

    lock_file = open(LOCK_PATH, "w")
    try:
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    window = VolumeOSD(osd_mode=osd_mode)
    window.present_top_center()
    Gtk.main()


if __name__ == "__main__":
    main()
