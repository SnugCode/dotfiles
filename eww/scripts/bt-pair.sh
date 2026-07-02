#!/usr/bin/env bash
set -euo pipefail
mac="$1"

bluetoothctl pair "$mac" &
for i in $(seq 1 20); do
    if bluetoothctl devices Paired | grep -q "$mac"; then break; fi
    sleep 0.5
done

bluetoothctl connect "$mac" &
for i in $(seq 1 20); do
    if bluetoothctl devices Connected | grep -q "$mac"; then break; fi
    sleep 0.5
done

eww update bt-data="$(~/.config/eww/scripts/bt-data.py)"
