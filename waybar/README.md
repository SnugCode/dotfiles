# Waybar Setup

This directory contains my Waybar configuration, CSS, icons, and helper scripts
for a Hyprland desktop. The bar is a detached dark top bar with workspace
buttons on the left, a centered clock, and network/Bluetooth/LocalSend/audio,
media, and battery controls on the right.

## Files

- `config.jsonc` - Waybar layout and module configuration
- `style.css` - bar styling, workspace styling, and right-module spacing
- `assets/` - SVG workspace indicator assets
- `scripts/` - custom GTK popups and status helpers
- `localsend/` - runtime state for the LocalSend companion, created on first use

## Prerequisites

Install Waybar and the desktop tools the modules expect:

```sh
sudo pacman -S waybar hyprland pipewire wireplumber networkmanager bluez blueman
sudo pacman -S playerctl brightnessctl wl-clipboard kitty xdg-utils
sudo pacman -S python python-gobject gtk3
```

Install the font used by the bar:

```sh
sudo pacman -S ttf-0xproto-nerd
```

If that package name is not available on your system, install `0xProto Nerd Font
Mono` and `0xProto` by another method. Nerd Font glyphs are required for the
workspace, audio, Bluetooth, LocalSend, battery, and media icons.

Optional but used by this setup:

```sh
sudo pacman -S cider
flatpak install flathub org.localsend.localsend_app
```

## Module Dependencies

- Workspaces: `hyprland/workspaces`, `hyprctl`
- Window title: `hyprland/window`
- Wi-Fi popup: `nmcli`, `kitty`, `nmtui-connect`
- Bluetooth popup: `bluetoothctl`, `blueman-manager`
- Audio status and popup: `wpctl`, `pactl`, `bluetoothctl`
- Media status and popup: `playerctl`, Python `gi.repository.Playerctl`
- Brightness helper: `brightnessctl`
- LocalSend menu: Python GTK, local HTTP listener, UDP multicast
- Downloads opener: `xdg-open`

For the media scripts, make sure your Python GObject setup includes Playerctl
introspection support. On Arch this may require the relevant Playerctl/GObject
introspection package in addition to `playerctl`, depending on how your system
is packaged.

## LocalSend Companion

The `custom/localsend` Waybar icon opens `scripts/localsend-menu.py`. The menu
controls a small companion service in `scripts/localsend-service.py`.

The companion is off by default. Turn it on from the menu when you want to
discover nearby LocalSend devices or receive transfer requests.

It provides:

- nearby device discovery
- file sending
- folder sending
- text sending as `message.txt`
- incoming request accept/reject
- received files saved under `~/Downloads/LocalSend`

Network notes:

- LocalSend discovery uses UDP multicast port `53317`
- The companion listens on TCP port `53318`
- Other devices must be on the same LAN
- Your firewall must allow inbound TCP `53318` and UDP multicast traffic

Manual service controls:

```sh
~/.config/waybar/scripts/localsend-service.py status
~/.config/waybar/scripts/localsend-service.py start
~/.config/waybar/scripts/localsend-service.py stop
```

## Installing This Setup

From a cloned copy of these dotfiles, back up any existing Waybar config and
copy this one into place:

```sh
mkdir -p ~/.config
mv ~/.config/waybar ~/.config/waybar.backup
cp -a /path/to/dotfiles/waybar ~/.config/waybar
chmod +x ~/.config/waybar/scripts/*
```

If you are already inside this repo, use:

```sh
mv ~/.config/waybar ~/.config/waybar.backup
cp -a ./waybar ~/.config/waybar
chmod +x ~/.config/waybar/scripts/*
```

Skip the `mv` command if there is no existing `~/.config/waybar`.

Make sure the scripts still point at the correct home path. The config uses
`~/.config/waybar/scripts/...`, so it should work for any user once copied into
their own `~/.config`.

## Starting And Reloading

Start Waybar:

```sh
waybar
```

Restart Waybar after config/module changes:

```sh
~/.config/waybar/scripts/launch.sh
```

Style changes usually reload live because `reload_style_on_change` is enabled
in `config.jsonc`. Module order, margins, and new modules usually need a Waybar
restart.

## Troubleshooting

If icons show as boxes, install the Nerd Font and restart Waybar.

If Wi-Fi or Bluetooth menus are empty, check:

```sh
nmcli device status
bluetoothctl show
```

If audio does not update, check:

```sh
wpctl get-volume @DEFAULT_AUDIO_SINK@
```

If media controls do not show anything, start an MPRIS-capable player and check:

```sh
playerctl -l
```

If LocalSend discovery does not find devices, turn on the companion in the menu,
then check:

```sh
~/.config/waybar/scripts/localsend-service.py status
```

Also confirm the firewall allows UDP `53317` and TCP `53318`.
