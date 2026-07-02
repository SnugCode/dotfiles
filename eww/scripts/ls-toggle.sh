#!/usr/bin/env bash
set -euo pipefail
running="$1"
if [ "$running" = "true" ]; then
    ~/.config/waybar/scripts/localsend-service.py stop
else
    ~/.config/waybar/scripts/localsend-service.py start
fi
eww update ls-data="$(~/.config/eww/scripts/ls-data.py)"
