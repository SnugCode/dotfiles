#!/usr/bin/env bash
arg="$1"
(
    case "$arg" in
        fastest)
            notify-send "ProtonVPN" "Connecting to fastest server…"
            protonvpn connect
            ;;
        p2p)
            notify-send "ProtonVPN" "Connecting via P2P…"
            protonvpn connect --p2p
            ;;
        *)
            notify-send "ProtonVPN" "Connecting to $arg…"
            protonvpn connect --country "$arg"
            ;;
    esac

    if [[ $? -eq 0 ]]; then
        notify-send "ProtonVPN" "Connected."
    else
        notify-send -u critical "ProtonVPN" "Connection failed."
    fi

    sleep 2
    pkill -RTMIN+7 waybar
    eww update network-data="$(~/.config/eww/scripts/network-data.sh)"
) &
