#!/usr/bin/env python3

import fcntl
import signal
import subprocess
import time

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402


LOCK_PATH = "/tmp/waybar-media-menu.lock"
PREFERRED_PLAYERS = ("cider", "cider2")
CIDER_ICON = ""


def run(*args):
    return subprocess.run(args, check=False, capture_output=True, text=True)


def players():
    result = run("playerctl", "-l")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def selected_player():
    available = players()
    for preferred in PREFERRED_PLAYERS:
        if preferred in available:
            return preferred
    return available[0] if available else ""


def playerctl(player, *args):
    if not player:
        return run("playerctl", *args)
    return run("playerctl", "-p", player, *args)


def metadata(player):
    if not player:
        return {
            "title": "No player",
            "artist": "Open Cider or start playback",
            "album": "",
            "playlist": "",
            "status": "Stopped",
            "length": 0,
            "position": 0,
        }

    fmt = "{{title}}\n{{artist}}\n{{album}}\n{{status}}\n{{mpris:length}}\n{{position}}"
    result = playerctl(player, "metadata", "--format", fmt)
    lines = result.stdout.splitlines()
    while len(lines) < 6:
        lines.append("")

    return {
        "title": lines[0] or "Unknown title",
        "artist": lines[1] or player,
        "album": lines[2],
        "playlist": playlist_name(player),
        "status": lines[3] or playerctl(player, "status").stdout.strip(),
        "length": microseconds(lines[4]),
        "position": microseconds(lines[5]),
    }


def playlist_name(player):
    result = playerctl(player, "metadata")
    fields = {}

    for line in result.stdout.splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) == 3:
            fields[parts[1]] = parts[2].strip()

    for key in (
        "xesam:playlist",
        "xesam:playlistName",
        "xesam:playlistTitle",
        "mpris:playlist",
        "xesam:context",
    ):
        value = fields.get(key, "")
        if value and not value.startswith(("http://", "https://")):
            return value

    return ""


def microseconds(value):
    try:
        return int(value)
    except ValueError:
        return 0


def time_label(value):
    seconds = max(0, round(value / 1_000_000))
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes}:{seconds:02d}"


class MediaMenu(Gtk.Window):
    def __init__(self):
        super().__init__(title="Media")

        self.last_activity = time.monotonic()
        self.player = selected_player()
        self.position_scale = None
        self.position_changing = False

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
        GLib.timeout_add_seconds(2, self.refresh_if_open)

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

        .player-icon {
            font-family: "0xProto Nerd Font Mono";
            font-size: 28px;
        }

        .title {
            font-weight: 700;
            font-size: 14px;
        }

        .meta {
            color: rgba(255, 255, 255, 0.68);
            font-size: 11px;
        }

        .control {
            font-family: "0xProto Nerd Font Mono";
            font-size: 18px;
            min-width: 38px;
            min-height: 34px;
            padding: 0;
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

        scale trough {
            min-height: 5px;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.22);
        }

        scale highlight {
            border-radius: 999px;
            background: #ffffff;
        }

        scale slider {
            min-width: 12px;
            min-height: 12px;
            border-radius: 999px;
            background: #ffffff;
            box-shadow: none;
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
        self.player = selected_player()
        info = metadata(self.player)

        for child in self.root.get_children():
            self.root.remove(child)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon = Gtk.Label(label=CIDER_ICON if self.player in PREFERRED_PLAYERS else "🎜")
        icon.get_style_context().add_class("player-icon")
        header.pack_start(icon, False, False, 0)

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        title = Gtk.Label(label=info["title"])
        title.set_halign(Gtk.Align.START)
        title.set_ellipsize(Pango.EllipsizeMode.END)
        title.get_style_context().add_class("title")
        labels.pack_start(title, False, False, 0)

        artist = Gtk.Label(label=self.artist_album_text(info))
        artist.set_halign(Gtk.Align.START)
        artist.set_ellipsize(Pango.EllipsizeMode.END)
        artist.get_style_context().add_class("meta")
        labels.pack_start(artist, False, False, 0)

        if info["playlist"]:
            playlist = Gtk.Label(label=info["playlist"])
            playlist.set_halign(Gtk.Align.START)
            playlist.set_ellipsize(Pango.EllipsizeMode.END)
            playlist.get_style_context().add_class("meta")
            labels.pack_start(playlist, False, False, 0)

        header.pack_start(labels, True, True, 0)
        header.set_size_request(320, -1)
        self.root.pack_start(header, False, False, 0)

        self.root.pack_start(self.progress_row(info), False, False, 0)
        self.root.pack_start(self.controls_row(info), False, False, 0)
        self.root.pack_start(self.footer_row(), False, False, 0)
        self.show_all()

    def artist_album_text(self, info):
        if info["artist"] and info["album"]:
            return f"{info['artist']} | {info['album']}"
        return info["artist"] or info["album"]

    def progress_row(self, info):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        self.position_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.position_scale.set_draw_value(False)
        self.position_scale.set_sensitive(bool(self.player and info["length"]))
        if info["length"]:
            self.position_scale.set_value(min(100, info["position"] / info["length"] * 100))
        self.position_scale.connect("button-press-event", self.on_seek_start)
        self.position_scale.connect("button-release-event", self.on_seek_finish, info)
        box.pack_start(self.position_scale, False, False, 0)

        times = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        current = Gtk.Label(label=time_label(info["position"]))
        current.get_style_context().add_class("meta")
        times.pack_start(current, False, False, 0)

        total = Gtk.Label(label=time_label(info["length"]))
        total.get_style_context().add_class("meta")
        times.pack_end(total, False, False, 0)
        box.pack_start(times, False, False, 0)

        return box

    def controls_row(self, info):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.set_halign(Gtk.Align.CENTER)

        previous = self.control_button("", self.previous)
        play_pause = self.control_button("" if info["status"] == "Playing" else "", self.play_pause)
        next_track = self.control_button("", self.next_track)

        row.pack_start(previous, False, False, 0)
        row.pack_start(play_pause, False, False, 0)
        row.pack_start(next_track, False, False, 0)
        return row

    def footer_row(self):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        refresh = Gtk.Button(label="Refresh")
        refresh.connect("clicked", self.refresh_clicked)
        row.pack_start(refresh, True, True, 0)

        open_cider = Gtk.Button(label="Open Cider")
        open_cider.connect("clicked", self.open_cider)
        row.pack_start(open_cider, True, True, 0)
        return row

    def control_button(self, label, callback):
        button = Gtk.Button(label=label)
        button.get_style_context().add_class("control")
        button.set_sensitive(bool(self.player))
        button.connect("clicked", callback)
        return button

    def on_seek_start(self, *_args):
        self.mark_active()
        self.position_changing = True
        return False

    def on_seek_finish(self, _scale, _event, info):
        self.mark_active()
        self.position_changing = False
        if self.player and info["length"] and self.position_scale is not None:
            target = int((self.position_scale.get_value() / 100) * info["length"])
            playerctl(self.player, "position", str(target / 1_000_000))
            GLib.timeout_add(250, self.refresh)
        return False

    def previous(self, _button):
        self.run_action("previous")

    def play_pause(self, _button):
        self.run_action("play-pause")

    def next_track(self, _button):
        self.run_action("next")

    def run_action(self, action):
        self.mark_active()
        if self.player:
            playerctl(self.player, action)
            GLib.timeout_add(250, self.refresh)

    def refresh_clicked(self, _button):
        self.mark_active()
        self.refresh()

    def refresh(self):
        if not self.position_changing:
            self.rebuild()
        return GLib.SOURCE_REMOVE

    def refresh_if_open(self):
        if not self.position_changing:
            self.rebuild()
        return GLib.SOURCE_CONTINUE

    def open_cider(self, _button):
        self.mark_active()
        run("hyprctl", "dispatch", "exec", "cider")
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
    window = MediaMenu()
    window.present_near_top_right()
    Gtk.main()


if __name__ == "__main__":
    main()
