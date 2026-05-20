#!/usr/bin/env bash

set -euo pipefail

INTERNAL_PATTERN='^(eDP|LVDS|DSI)-'
SCALE="${HYPR_DISPLAY_SCALE:-1.25}"

hypr() {
    hyprctl "$@" >/dev/null 2>&1 || true
}

monitor_names() {
    hyprctl monitors all 2>/dev/null | awk '/^Monitor / {print $2}'
}

internal_monitor() {
    monitor_names | grep -E "$INTERNAL_PATTERN" | head -n 1 || true
}

external_monitors() {
    monitor_names | grep -Ev "$INTERNAL_PATTERN" || true
}

lid_is_closed() {
    grep -q closed /proc/acpi/button/lid/*/state 2>/dev/null
}

mirror_displays() {
    local internal="$1"
    shift

    hypr keyword monitor "$internal,preferred,0x0,$SCALE"

    local external
    for external in "$@"; do
        hypr keyword monitor "$external,preferred,auto,$SCALE,mirror,$internal"
    done
}

external_only() {
    local internal="$1"
    shift

    local external
    for external in "$@"; do
        hypr keyword monitor "$external,preferred,auto,$SCALE"
    done

    hypr keyword monitor "$internal,disable"
}

apply_mode() {
    local mode="${1:-auto}"
    local internal
    mapfile -t externals < <(external_monitors)
    internal="$(internal_monitor)"

    if [[ -z "$internal" ]]; then
        hypr keyword monitor ",preferred,auto,$SCALE"
        return
    fi

    if [[ "${#externals[@]}" -eq 0 ]]; then
        hypr keyword monitor "$internal,preferred,0x0,$SCALE"
        return
    fi

    if [[ "$mode" == "closed" || ( "$mode" == "auto" && lid_is_closed ) ]]; then
        external_only "$internal" "${externals[@]}"
    else
        mirror_displays "$internal" "${externals[@]}"
    fi
}

watch_hotplug() {
    apply_mode auto

    local socket="${XDG_RUNTIME_DIR:-}/hypr/${HYPRLAND_INSTANCE_SIGNATURE:-}/.socket2.sock"
    if [[ ! -S "$socket" ]] || ! command -v socat >/dev/null 2>&1; then
        return
    fi

    socat -u "UNIX-CONNECT:$socket" - | while read -r event; do
        case "$event" in
            monitoradded*|monitorremoved*)
                sleep 0.5
                apply_mode auto
                ;;
        esac
    done
}

case "${1:-auto}" in
    watch)
        watch_hotplug
        ;;
    open|mirror)
        apply_mode open
        ;;
    closed|external-only)
        apply_mode closed
        ;;
    *)
        apply_mode auto
        ;;
esac
