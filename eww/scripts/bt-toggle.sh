#!/usr/bin/env bash
set -euo pipefail
if eww active-windows 2>/dev/null | grep -q "bluetooth"; then
    eww update bt-popup-visible=false
    eww close bluetooth
else
    eww update bt-popup-visible=true
    eww open bluetooth
    eww update bt-data="$(~/.config/eww/scripts/bt-data.py)"
fi
