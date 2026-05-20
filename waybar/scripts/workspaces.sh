#!/usr/bin/env bash

set -u

declare -A icons=(
	[1]=""
	[2]=""
	[3]=""
	[4]=""
	[5]=""
)

workspace_count=5
last_active=""

active_workspace() {
	local active

	active="$(hyprctl -j activeworkspace 2>/dev/null | sed -n 's/.*"id"[[:space:]]*:[[:space:]]*\([0-9]\+\).*/\1/p')"

	if [[ -z "$active" ]]; then
		active="$(hyprctl activeworkspace 2>/dev/null | sed -n 's/^workspace ID \([0-9]\+\).*/\1/p')"
	fi

	printf '%s\n' "${active:-1}"
}

emit() {
	local active="$1"
	local direction="${2:-}"
	local text=""
	local classes="\"workspace-${active}\""
	local icon

	if [[ -n "$direction" ]]; then
		classes+=",\"moving-${direction}\""
	fi

	for ((workspace = 1; workspace <= workspace_count; workspace++)); do
		icon="${icons[$workspace]}"

		if [[ "$workspace" == "$active" ]]; then
			text+="<span foreground='#000000'>${icon}</span>"
		else
			text+="<span foreground='#ffffff'>${icon}</span>"
		fi

		if (( workspace < workspace_count )); then
			text+="  "
		fi
	done

	printf '{"text":"%s","class":[%s],"tooltip":"Workspace %s"}\n' "$text" "$classes" "$active"
}

while true; do
	active="$(active_workspace)"

	if [[ "$active" != "$last_active" ]]; then
		if [[ -n "$last_active" && "$active" =~ ^[0-9]+$ && "$last_active" =~ ^[0-9]+$ ]]; then
			if (( active > last_active )); then
				emit "$active" "right"
			else
				emit "$active" "left"
			fi

			sleep 0.22
		fi

		emit "$active"
		last_active="$active"
	fi

	sleep 0.12
done
