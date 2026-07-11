#!/usr/bin/env bash
set -euo pipefail
if eww active-windows 2>/dev/null | grep -q "audio"; then
    eww update audio-popup-visible=false
    eww close audio
else
    eww update audio-popup-visible=true
    eww open audio
fi
