#!/usr/bin/env bash
set -euo pipefail
device_id="$1"

# Pick file with rofi browsing common dirs
file=$(find ~/Documents ~/Downloads ~/Desktop ~/Pictures -maxdepth 3 -type f 2>/dev/null \
    | sort | rofi -dmenu -p "Send file" -theme-str 'window {width: 65%;}') || true

[ -z "$file" ] && exit 0
[ ! -f "$file" ] && exit 0

python3 - "$device_id" "$file" <<'EOF'
import sys, json, urllib.request
payload = json.dumps({"device_id": sys.argv[1], "paths": [sys.argv[2]]}).encode()
req = urllib.request.Request(
    "http://127.0.0.1:53318/waybar/send", data=payload, method="POST",
    headers={"Content-Type": "application/json"})
urllib.request.urlopen(req, timeout=5)
EOF
eww update ls-data="$(~/.config/eww/scripts/ls-data.py)"
