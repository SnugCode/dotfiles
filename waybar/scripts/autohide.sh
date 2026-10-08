#!/bin/bash

SHOW_THRESHOLD=5   # px from top edge to trigger show
KEEP_THRESHOLD=40  # px from top to keep bar visible (covers bar + 8px margin)
HIDE_DELAY=2       # seconds before hiding after cursor leaves bar area
POLL=0.05          # poll interval in seconds

HIDDEN=false

toggle() { pkill -SIGUSR1 waybar 2>/dev/null; }

trap '{ $HIDDEN && toggle; }' EXIT

sleep "$HIDE_DELAY"
toggle
HIDDEN=true

last_active=$(date +%s%3N)

while true; do
    sleep "$POLL"

    y=$(hyprctl cursorpos 2>/dev/null | awk -F', ' '{print $2}')
    now=$(date +%s%3N)

    if $HIDDEN; then
        if [[ "${y:-9999}" -le "$SHOW_THRESHOLD" ]]; then
            toggle
            HIDDEN=false
            last_active=$now
        fi
    else
        if [[ "${y:-9999}" -le "$KEEP_THRESHOLD" ]]; then
            last_active=$now
        else
            elapsed=$(( now - last_active ))
            if (( elapsed >= HIDE_DELAY * 1000 )); then
                toggle
                HIDDEN=true
            fi
        fi
    fi
done
