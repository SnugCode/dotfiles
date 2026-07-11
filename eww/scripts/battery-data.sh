#!/usr/bin/env bash
python3 << 'EOF'
import json, os

profile_file = os.path.expanduser('~/.local/state/power-profile')
try:
    with open(profile_file) as f:
        profile = f.read().strip()
except Exception:
    profile = 'normal'

labels = {
    'normal':  'Normal',
    'content': 'Content',
    'coding':  'Coding',
}

try:
    with open('/sys/class/power_supply/BAT0/capacity') as f:
        capacity = int(f.read().strip())
    with open('/sys/class/power_supply/BAT0/status') as f:
        status = f.read().strip()
    charging = status == 'Charging'
except Exception:
    capacity = 0
    charging = False

print(json.dumps({
    'capacity':      capacity,
    'charging':      charging,
    'profile':       profile,
    'profile_label': labels.get(profile, 'Normal'),
}))
EOF
