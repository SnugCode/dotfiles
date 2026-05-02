#!/bin/bash

LOW=15
CRITICAL=10

LOW_TRIGGERED=0
CRITICAL_TRIGGERED=0

while true; do
    BAT=$(acpi -b | grep -P -o '[0-9]+(?=%)')
    STATUS=$(acpi -b | awk '{print $3}' | tr -d ',')

    if [[ "$STATUS" == "Discharging" ]]; then

        if [[ $BAT -le $CRITICAL && $CRITICAL_TRIGGERED -eq 0 ]]; then
            notify-send -u critical "Battery Critical" "Battery at ${BAT}%! Plug in NOW."
            CRITICAL_TRIGGERED=1
        elif [[ $BAT -le $LOW && $LOW_TRIGGERED -eq 0 ]]; then
            notify-send -u normal "Low Battery" "Battery at ${BAT}%"
            LOW_TRIGGERED=1
        fi

    fi

    # Reset triggers when charging or battery goes back up
    if [[ "$STATUS" != "Discharging" || $BAT -gt $LOW ]]; then
        LOW_TRIGGERED=0
        CRITICAL_TRIGGERED=0
    fi

    sleep 60
done