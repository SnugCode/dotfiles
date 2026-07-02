#!/usr/bin/env python3
import json, re, subprocess, os

LOCALSEND_SERVICE = os.path.expanduser("~/.config/waybar/scripts/localsend-service.py")

TYPE_ICONS = {
    "audio-headset": "󰋋", "audio-headphones": "󰋋",
    "audio-card": "󰓃", "input-keyboard": "󰌌",
    "input-mouse": "󰍽", "input-gaming": "󰖺",
    "phone": "", "computer": "󰍹",
}
DEFAULT_ICON = "󰂯"
MAX_SLOTS = 4
EMPTY    = {"visible": False, "name": "", "mac": "", "type_icon": "",
            "connected": False, "status": "", "action_label": ""}
EMPTY_AV = {"visible": False, "name": "", "mac": "", "type_icon": ""}

def run(*args):
    try:
        return subprocess.run(args, capture_output=True, text=True).stdout
    except FileNotFoundError:
        return ""

def powered():
    m = re.search(r"Powered:\s+(yes|no)", run("bluetoothctl", "show"))
    return m and m.group(1) == "yes"

def type_icon(mac):
    m = re.search(r"Icon:\s+(\S+)", run("bluetoothctl", "info", mac))
    return TYPE_ICONS.get(m.group(1), DEFAULT_ICON) if m else DEFAULT_ICON

def devices():
    paired = re.findall(r"Device\s+([0-9A-F:]{17})\s+(.+)", run("bluetoothctl", "devices", "Paired"))
    connected_macs = set(re.findall(r"Device\s+([0-9A-F:]{17})", run("bluetoothctl", "devices", "Connected")))
    result = []
    for mac, name in paired:
        conn = mac in connected_macs
        result.append({
            "mac": mac, "name": name,
            "type_icon": type_icon(mac),
            "connected": conn,
            "status": "● Connected" if conn else "○ Paired",
            "action_label": "Disconnect" if conn else "Connect",
        })
    result.sort(key=lambda d: (not d["connected"], d["name"].lower()))
    return result

def localsend_running():
    try:
        return subprocess.run([LOCALSEND_SERVICE, "status"],
                              capture_output=True, text=True).stdout.strip() == "running"
    except FileNotFoundError:
        return False

def available_devices(paired_macs):
    all_devs = re.findall(r"Device\s+([0-9A-F:]{17})\s+(.+)", run("bluetoothctl", "devices"))
    result = []
    for mac, name in all_devs:
        if mac not in paired_macs:
            result.append({"mac": mac, "name": name, "type_icon": type_icon(mac)})
    return result


def main():
    is_powered = powered()
    devs = devices() if is_powered else []
    paired_macs = {d["mac"] for d in devs}

    slots = {}
    for i in range(MAX_SLOTS):
        if i < len(devs):
            d = devs[i]
            slots[f"d{i}"] = {"visible": True, **d}
        else:
            slots[f"d{i}"] = dict(EMPTY)

    av_devs = available_devices(paired_macs) if is_powered else []
    av_slots = {}
    for i in range(MAX_SLOTS):
        if i < len(av_devs):
            av_slots[f"av{i}"] = {"visible": True, **av_devs[i]}
        else:
            av_slots[f"av{i}"] = dict(EMPTY_AV)

    print(json.dumps({
        "powered": is_powered,
        "has_devices": len(devs) > 0,
        "has_available": len(av_devs) > 0,
        **slots,
        **av_slots,
    }))

main()
