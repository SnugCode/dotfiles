#!/usr/bin/env bash
set -euo pipefail
pct="$1"

player=$(playerctl -l 2>/dev/null | head -1 || true)
[ -z "$player" ] && exit 0

length_us=$(playerctl -p "$player" metadata mpris:length 2>/dev/null || echo 0)
[ "${length_us:-0}" -le 0 ] && exit 0

position=$(python3 -c "print(round($pct * $length_us / 100000000.0, 2))")
playerctl -p "$player" position "$position"
