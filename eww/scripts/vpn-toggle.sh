#!/usr/bin/env bash
if [ "$1" = "true" ]; then
    notify-send "ProtonVPN" "Disconnecting…"
    protonvpn disconnect
    if [[ $? -eq 0 ]]; then
        notify-send "ProtonVPN" "Disconnected."
    else
        notify-send -u critical "ProtonVPN" "Disconnect failed."
    fi
    pkill -RTMIN+7 waybar
    sleep 1
    pkill -RTMIN+7 waybar
    eww update network-data="$(~/.config/eww/scripts/network-data.sh)"
else
    (
        notify-send "ProtonVPN" "Connecting to fastest server…"
        protonvpn connect
        if [[ $? -eq 0 ]]; then
            notify-send "ProtonVPN" "Connected."
        else
            notify-send -u critical "ProtonVPN" "Connection failed."
        fi
        sleep 2
        pkill -RTMIN+7 waybar
        eww update network-data="$(~/.config/eww/scripts/network-data.sh)"
    ) &
fi
