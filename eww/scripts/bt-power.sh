#!/usr/bin/env bash
set -euo pipefail
powered="$1"

if [ "$powered" = "true" ]; then
    bluetoothctl power off
    expected="no"
else
    bluetoothctl power on
    expected="yes"
fi

# Poll until adapter state matches (max ~3s)
for i in $(seq 1 10); do
    state=$(bluetoothctl show | grep "Powered:" | awk '{print $2}')
    if [ "$state" = "$expected" ]; then break; fi
    sleep 0.3
done

eww update bt-data="$(~/.config/eww/scripts/bt-data.py)"
