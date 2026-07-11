#!/usr/bin/env bash
status=$(wpctl get-volume @DEFAULT_AUDIO_SINK@ 2>/dev/null || echo "Volume: 0.50")
python3 -c "
import re, json, sys
status = sys.argv[1]
m = re.search(r'Volume: ([\d.]+)', status)
vol = round(float(m.group(1)) * 100) if m else 50
muted = '[MUTED]' in status
if muted:       icon = chr(0xEEE8)
elif vol < 34:  icon = chr(0xF026)
elif vol < 67:  icon = chr(0xF027)
else:           icon = chr(0xF028)
print(json.dumps({'volume': vol, 'muted': muted, 'icon': icon, 'percent': f'{vol}%'}))
" "$status"
