#!/usr/bin/env bash
if [ "$1" = "true" ]; then
    nmcli radio wifi off
    pkill -RTMIN+7 waybar
    (sleep 1 && pkill -RTMIN+7 waybar) &
else
    nmcli radio wifi on
    pkill -RTMIN+7 waybar
    (
        for _ in 1 2 3 4 5 6 7 8 9 10; do
            sleep 0.5
            state=$(nmcli -t -f WIFI radio 2>/dev/null)
            pkill -RTMIN+7 waybar
            [[ "$state" == "enabled" ]] && break
        done
    ) &
fi
