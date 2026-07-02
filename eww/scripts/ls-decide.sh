#!/usr/bin/env bash
set -euo pipefail
action="$1"   # accept or reject
session_id="$2"

python3 - "$action" "$session_id" <<'EOF'
import sys, urllib.request
req = urllib.request.Request(
    f"http://127.0.0.1:53318/waybar/{sys.argv[1]}?id={sys.argv[2]}",
    data=b"", method="POST")
urllib.request.urlopen(req, timeout=5)
EOF
eww update ls-data="$(~/.config/eww/scripts/ls-data.py)"
