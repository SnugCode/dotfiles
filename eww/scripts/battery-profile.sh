#!/usr/bin/env bash
profile="$1"

mkdir -p ~/.local/state
echo "$profile" > ~/.local/state/power-profile

case "$profile" in
    normal)
        powerprofilesctl set balanced
        brightnessctl set 70%
        iw dev wlan0 set power_save off
        dunstctl set-paused false
        ;;
    content)
        powerprofilesctl set performance
        brightnessctl set 100%
        iw dev wlan0 set power_save off
        dunstctl set-paused false
        ;;
    coding)
        powerprofilesctl set power-saver
        brightnessctl set 50%
        iw dev wlan0 set power_save on
        dunstctl set-paused true
        ;;
esac

eww update battery-data="$(~/.config/eww/scripts/battery-data.sh)"
