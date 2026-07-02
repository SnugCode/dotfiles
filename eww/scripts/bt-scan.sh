#!/usr/bin/env bash
set -euo pipefail

eww update bt-scanning=true

# Run the entire scan in a detached background process so eww's onclick
# subprocess exits immediately and can't be killed before bt-scanning resets
(
    bluetoothctl scan on &
    BT_PID=$!
    sleep 8
    kill "$BT_PID" 2>/dev/null || true
    wait "$BT_PID" 2>/dev/null || true
    bluetoothctl scan off 2>/dev/null || true
    eww update bt-scanning=false
    eww update bt-data="$(~/.config/eww/scripts/bt-data.py)"
) &
