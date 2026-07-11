#!/usr/bin/env bash
python3 << 'EOF'
import subprocess, json

def run(*args):
    try:
        return subprocess.run(args, capture_output=True, text=True).stdout.strip()
    except Exception:
        return ''

WIFI_ICON = chr(0xF1EB)
EMPTY = {'visible': False, 'ssid': '', 'signal': 0, 'signal_str': '', 'icon': WIFI_ICON}

def slot(nets, i):
    if i < len(nets):
        s = nets[i]['signal']
        return {'visible': True, 'ssid': nets[i]['ssid'], 'signal': s,
                'signal_str': f'{s}%', 'icon': WIFI_ICON}
    return EMPTY

# WiFi enabled?
wifi_enabled = run('nmcli', 'radio', 'wifi').lower() == 'enabled'

if not wifi_enabled:
    print(json.dumps({
        'wifi_enabled': False, 'net_icon': WIFI_ICON,
        'connected_ssid': '', 'connected_signal': 0, 'connected_signal_str': '',
        'has_known': False, 'has_available': False,
        'k0': EMPTY, 'k1': EMPTY, 'k2': EMPTY,
        'a0': EMPTY, 'a1': EMPTY, 'a2': EMPTY,
        'vpn_connected': False, 'vpn_server': '',
    }))
    exit()

# Visible networks — use cached scan (faster)
visible = {}
wifi_out = run('nmcli', '-t', '-f', 'IN-USE,SSID,SIGNAL,SECURITY',
               'dev', 'wifi', 'list', '--rescan', 'no')
for line in wifi_out.splitlines():
    parts = line.split(':', 3)
    if len(parts) < 3:
        continue
    in_use = parts[0].strip() == '*'
    ssid = parts[1].strip()
    if not ssid:
        continue
    signal = int(parts[2]) if parts[2].strip().isdigit() else 0
    # Keep best signal per SSID; always update if in-use
    if ssid not in visible or in_use or signal > visible[ssid]['signal']:
        visible[ssid] = {'in_use': in_use, 'signal': signal}

# Saved WiFi connections
saved = set()
for line in run('nmcli', '-t', '-f', 'NAME,TYPE', 'connection', 'show').splitlines():
    parts = line.split(':', 1)
    if len(parts) == 2 and '802-11-wireless' in parts[1]:
        saved.add(parts[0].strip())

# Categorize
connected_ssid, connected_signal = '', 0
known, available = [], []
for ssid, info in visible.items():
    if info['in_use']:
        connected_ssid, connected_signal = ssid, info['signal']
    elif ssid in saved:
        known.append({'ssid': ssid, 'signal': info['signal']})
    else:
        available.append({'ssid': ssid, 'signal': info['signal']})

known.sort(key=lambda x: -x['signal'])
available.sort(key=lambda x: -x['signal'])

# VPN
vpn_status = run('protonvpn', 'status')
vpn_connected = 'Status: Connected' in vpn_status
vpn_server = ''
if vpn_connected:
    for line in vpn_status.splitlines():
        if 'server:' in line.lower():
            vpn_server = line.split(':', 1)[-1].strip()
            break
    vpn_server = vpn_server or 'Connected'

print(json.dumps({
    'wifi_enabled': wifi_enabled,
    'net_icon': WIFI_ICON,
    'connected_ssid': connected_ssid,
    'connected_signal': connected_signal,
    'connected_signal_str': f'{connected_signal}%' if connected_ssid else '',
    'has_known': len(known) > 0,
    'has_available': len(available) > 0,
    'k0': slot(known, 0), 'k1': slot(known, 1), 'k2': slot(known, 2),
    'a0': slot(available, 0), 'a1': slot(available, 1), 'a2': slot(available, 2),
    'vpn_connected': vpn_connected,
    'vpn_server': vpn_server,
}))
EOF
