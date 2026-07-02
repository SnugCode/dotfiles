#!/usr/bin/env python3
import json, urllib.request

DEVICE_ICONS = {
    "desktop": "󰍹",
    "mobile": "",
    "web": "󰖟",
    "tablet": "󰓶",
}
DEFAULT_ICON = "󰙜"
MAX_LS = 4
MAX_INC = 2
EMPTY_LS  = {"visible": False, "id": "", "alias": "", "type_icon": ""}
EMPTY_INC = {"visible": False, "id": "", "sender": "", "files": ""}

def get_state():
    try:
        r = urllib.request.urlopen("http://127.0.0.1:53318/waybar/state", timeout=0.5)
        return json.loads(r.read().decode())
    except Exception:
        return None

def main():
    state = get_state()
    empty = {
        "running": False, "has_devices": False, "has_incoming": False,
        **{f"ls{i}": dict(EMPTY_LS) for i in range(MAX_LS)},
        **{f"inc{i}": dict(EMPTY_INC) for i in range(MAX_INC)},
    }
    if not state:
        print(json.dumps(empty))
        return

    devices = state.get("devices", [])
    incoming = [x for x in state.get("incoming", []) if x.get("status") == "pending"]

    ls_slots = {}
    for i in range(MAX_LS):
        if i < len(devices):
            d = devices[i]
            ls_slots[f"ls{i}"] = {
                "visible": True,
                "id": d.get("id", ""),
                "alias": d.get("alias", "Unknown"),
                "type_icon": DEVICE_ICONS.get(d.get("deviceType", ""), DEFAULT_ICON),
            }
        else:
            ls_slots[f"ls{i}"] = dict(EMPTY_LS)

    inc_slots = {}
    for i in range(MAX_INC):
        if i < len(incoming):
            inc = incoming[i]
            files = inc.get("files", [])
            file_list = ", ".join(f.get("fileName", "?") for f in files[:2])
            if len(files) > 2:
                file_list += f" +{len(files) - 2}"
            inc_slots[f"inc{i}"] = {
                "visible": True,
                "id": inc.get("id", ""),
                "sender": inc.get("sender", "Unknown"),
                "files": file_list or "file",
            }
        else:
            inc_slots[f"inc{i}"] = dict(EMPTY_INC)

    print(json.dumps({
        "running": True,
        "has_devices": len(devices) > 0,
        "has_incoming": len(incoming) > 0,
        **ls_slots,
        **inc_slots,
    }))

main()
