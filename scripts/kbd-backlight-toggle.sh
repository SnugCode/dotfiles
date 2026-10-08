#!/bin/bash
current=$(brightnessctl -d 'tpacpi::kbd_backlight' get)
if [ "$current" -eq 0 ]; then
    brightnessctl -d 'tpacpi::kbd_backlight' set 2
else
    brightnessctl -d 'tpacpi::kbd_backlight' set 0
fi
