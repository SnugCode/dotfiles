#!/usr/bin/env bash
wifi_state=$(nmcli -t -f WIFI radio 2>/dev/null)
if [[ "$wifi_state" == "enabled" ]]; then
    essid=$(iwgetid -r 2>/dev/null || true)
    wifi_on=true
else
    essid=""
    wifi_on=false
fi

vpn_on=false
protonvpn status 2>/dev/null | grep -q "^Status: Connected" && vpn_on=true

wifi_icon=$''
vpn_icon=$''
no_wifi=$'\U000f092d'

if [[ "$wifi_on" != "true" ]]; then
    printf '{"text":"%s","tooltip":"No network","class":"disconnected"}\n' "$wifi_icon"
elif [[ "$vpn_on" == "true" ]]; then
    printf '{"text":"%s","tooltip":"WiFi: %s | VPN: On","class":"vpn"}\n' "$vpn_icon" "$essid"
elif [[ -n "$essid" ]]; then
    printf '{"text":"%s","tooltip":"WiFi: %s","class":"connected"}\n' "$wifi_icon" "$essid"
else
    printf '{"text":"%s","tooltip":"WiFi on","class":"on"}\n' "$wifi_icon"
fi
