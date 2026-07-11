#!/usr/bin/env bash
ssid="$1"
kind="$2"   # "saved" or "available"

if [ "$kind" = "saved" ]; then
    nmcli connection up id "$ssid" &
else
    nmcli dev wifi connect "$ssid" &
fi
sleep 2
pkill -RTMIN+7 waybar
eww update network-data="$(~/.config/eww/scripts/network-data.sh)"
