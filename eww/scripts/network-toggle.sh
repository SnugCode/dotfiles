#!/usr/bin/env bash
if eww active-windows 2>/dev/null | grep -q "network"; then
    eww update network-popup-visible=false
    eww close network
else
    eww update network-popup-visible=true
    eww open network
fi
