#!/usr/bin/env python3

import json
import re
import subprocess


DISCONNECTED_ICON = ""
CONNECTED_ICON = ""


def run(*args):
    try:
        return subprocess.run(args, check=False, capture_output=True, text=True)
    except FileNotFoundError as error:
        return subprocess.CompletedProcess(args, 127, "", str(error))


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


def active_vpn():
    result = run(
        "nmcli",
        "-t",
        "--escape",
        "yes",
        "-f",
        "NAME,TYPE,DEVICE",
        "connection",
        "show",
        "--active",
    )

    if result.returncode != 0:
        return None

    for line in result.stdout.splitlines():
        fields = split_nmcli_line(line)
        if len(fields) < 3:
            continue

        name, connection_type, device = fields[:3]
        if (
            connection_type in {"vpn", "wireguard"}
            or re.match(r"^(tun|wg|ppp)", device)
            or "proton" in name.lower()
        ):
            return name

    return None


def main():
    name = active_vpn()
    if name:
        payload = {
            "text": CONNECTED_ICON,
            "tooltip": f"VPN connected: {name}",
            "class": "connected",
        }
    else:
        payload = {
            "text": DISCONNECTED_ICON,
            "tooltip": "VPN disconnected",
            "class": "disconnected",
        }

    print(json.dumps(payload))


if __name__ == "__main__":
    main()
