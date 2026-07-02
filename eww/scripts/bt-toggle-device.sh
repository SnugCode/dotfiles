#!/usr/bin/env bash
set -euo pipefail
mac="$1"
connected="$2"

if [ "$connected" = "true" ]; then
    bluetoothctl disconnect "$mac" &
    for i in $(seq 1 20); do
        if ! bluetoothctl devices Connected | grep -q "$mac"; then break; fi
        sleep 0.5
    done
else
    bluetoothctl connect "$mac" &
    for i in $(seq 1 20); do
        if bluetoothctl devices Connected | grep -q "$mac"; then break; fi
        sleep 0.5
    done
fi

eww update bt-data="$(~/.config/eww/scripts/bt-data.py)"
