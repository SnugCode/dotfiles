#!/usr/bin/env bash
if [ "$1" = "true" ]; then
    protonvpn disconnect
    pkill -RTMIN+7 waybar
    sleep 1
    pkill -RTMIN+7 waybar
    eww update network-data="$(~/.config/eww/scripts/network-data.sh)"
else
    (
        protonvpn connect
        sleep 2
        pkill -RTMIN+7 waybar
        eww update network-data="$(~/.config/eww/scripts/network-data.sh)"
    ) &
fi
