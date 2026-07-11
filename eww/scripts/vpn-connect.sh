#!/usr/bin/env bash
arg="$1"
(
    case "$arg" in
        fastest) protonvpn connect ;;
        p2p)     protonvpn connect --p2p ;;
        *)       protonvpn connect --country "$arg" ;;
    esac
    sleep 2
    pkill -RTMIN+7 waybar
    eww update network-data="$(~/.config/eww/scripts/network-data.sh)"
) &
