#!/usr/bin/env bash

set -u

# Paste your headphone icon between the quotes.
headphone_icon=""

icon_muted=""
icon_low=""
icon_medium=""
icon_high=""

json_escape() {
	printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

bluetooth_audio_connected() {
	local default_sink

	default_sink="$(pactl get-default-sink 2>/dev/null || true)"
	if [[ "$default_sink" == bluez_* || "$default_sink" == *bluez* ]]; then
		return 0
	fi

	bluetoothctl devices Connected 2>/dev/null | grep -qiE 'audio|headphone|headset|buds|speaker'
}

volume_status() {
	wpctl get-volume @DEFAULT_AUDIO_SINK@ 2>/dev/null || true
}

status="$(volume_status)"
volume="$(printf '%s\n' "$status" | sed -n 's/.*Volume:[[:space:]]*\([0-9.]\+\).*/\1/p')"
muted="false"

if [[ "$status" == *"[MUTED]"* ]]; then
	muted="true"
fi

if [[ "$muted" == "true" ]]; then
	icon="$icon_muted"
elif bluetooth_audio_connected && [[ -n "$headphone_icon" ]]; then
	icon="$headphone_icon"
elif awk "BEGIN { exit !($volume < 0.34) }" 2>/dev/null; then
	icon="$icon_low"
elif awk "BEGIN { exit !($volume < 0.67) }" 2>/dev/null; then
	icon="$icon_medium"
else
	icon="$icon_high"
fi

tooltip="Volume"
if [[ -n "$volume" ]]; then
	percent="$(awk "BEGIN { printf \"%d\", ($volume * 100) }" 2>/dev/null || printf '0')"
	tooltip="Volume ${percent}%"
fi

printf '{"text":"%s","tooltip":"%s","class":"%s"}\n' \
	"$(json_escape "$icon")" \
	"$(json_escape "$tooltip")" \
	"$([[ "$muted" == "true" ]] && printf muted || printf volume)"
