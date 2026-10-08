#!/usr/bin/env bash
count=$(pacman -Qu 2>/dev/null | wc -l)
if [[ "$count" -eq 0 ]]; then
    printf '{"text":"󰒓","tooltip":"System up to date","class":"updated"}\n'
else
    printf '{"text":"󰒓 %d","tooltip":"%d update(s) available","class":"pending"}\n' "$count" "$count"
fi
