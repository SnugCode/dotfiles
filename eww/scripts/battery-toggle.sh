#!/usr/bin/env bash
if eww active-windows 2>/dev/null | grep -q "battery"; then
    eww update battery-popup-visible=false
    eww close battery
else
    eww update battery-popup-visible=true
    eww open battery
fi
