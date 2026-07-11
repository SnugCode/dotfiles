#!/usr/bin/env python3
import subprocess, json

PLAYER_ICONS = {
    "cider": "", "cider2": "",
    "spotify": "", "mpv": "󰝚", "vlc": "󰕼",
    "firefox": "", "chromium": "󰖟",
    "google-chrome": "󰖟", "chrome": "󰖟",
}
DEFAULT_ICON = "󰝚"

def run(*args):
    try:
        return subprocess.run(args, capture_output=True, text=True).stdout.strip()
    except Exception:
        return ""

def select_player():
    players = [p.strip() for p in run("playerctl", "-l").splitlines() if p.strip()]
    if not players:
        return None
    for p in players:
        if run("playerctl", "-p", p, "status") == "Playing":
            return p
    for p in players:
        if run("playerctl", "-p", p, "status") == "Paused":
            return p
    return players[0]

def microseconds(s):
    try: return int(s)
    except: return 0

def time_label(us):
    secs = max(0, round(us / 1_000_000))
    m, s = divmod(secs, 60)
    return f"{m}:{s:02d}"

def main():
    empty = {
        "has_player": False, "player": "", "player_icon": DEFAULT_ICON,
        "title": "Nothing playing", "artist": "", "album": "",
        "status": "Stopped", "status_icon": "󰐊",
        "progress": 0.0, "position_str": "0:00", "length_str": "0:00", "length_us": 0,
    }
    player = select_player()
    if not player:
        print(json.dumps(empty))
        return

    status = run("playerctl", "-p", player, "status") or "Stopped"

    fmt = "{{title}}\n{{artist}}\n{{album}}\n{{mpris:length}}\n{{position}}"
    out = run("playerctl", "-p", player, "metadata", "--format", fmt)
    lines = out.splitlines()
    while len(lines) < 5:
        lines.append("")

    title       = lines[0] or "Unknown"
    artist      = lines[1] or ""
    album       = lines[2] or ""
    length_us   = microseconds(lines[3])
    position_us = microseconds(lines[4])
    progress = round(min(100.0, position_us / length_us * 100), 1) if length_us > 0 else 0.0

    player_base = player.split(".")[0].lower()
    player_icon = PLAYER_ICONS.get(player_base, DEFAULT_ICON)
    status_icon = "󰏤" if status == "Playing" else "󰐊"

    print(json.dumps({
        "has_player": True,
        "player": player,
        "player_icon": player_icon,
        "title": title,
        "artist": artist,
        "album": album,
        "status": status,
        "status_icon": status_icon,
        "progress": progress,
        "position_str": time_label(position_us),
        "length_str": time_label(length_us),
        "length_us": length_us,
    }))

main()
