# dotfiles

Personal Linux desktop configuration files for an Arch + Hyprland Wayland setup.

The current look is a dark, minimal desktop with white text, 0xProto fonts,
Waybar workspace motion, a custom Rofi launcher panel, Hyprlock, and a custom
Fastfetch ASCII logo.

## Main Dependencies

- `hyprland` - Wayland compositor
- `hyprpaper` - wallpaper daemon used by Hyprland autostart
- `hyprlock` - lock screen
- `hypridle` - idle lock handling
- `waybar` - top status bar
- `rofi` - app launcher and clipboard menu
- `kitty` - terminal emulator
- `fastfetch` - terminal system info
- `dolphin` - file manager
- `firefox` - browser
- `codium` - editor/IDE
- `spotify-launcher` - Spotify launcher

## Wayland / Hyprland Helpers

- `hyprctl` - Hyprland control utility used by keybinds and Waybar scripts
- `hyprshot` - screenshot tool bound to Print
- `wl-clipboard` - provides `wl-copy` and `wl-paste`
- `cliphist` - clipboard history storage and Rofi clipboard menu
- `brightnessctl` - brightness keybinds
- `playerctl` - media keys and Waybar media status/control popup
- `wireplumber` / `wpctl` - audio volume, mute keybinds, and Waybar volume popup
- `pipewire` - audio stack used by the Waybar audio module
- `networkmanager` / `nmcli` - network status and Waybar Wi-Fi popup
- `bluez` / `bluetoothctl` - Bluetooth status and Waybar Bluetooth popup
- `blueman` - provides `blueman-manager` for deeper Bluetooth settings

## Fonts

- `0xProto Nerd Font Mono` - used by Kitty, Rofi, and Waybar
- `0xProto` - used by Waybar styling
- Nerd Font symbols are expected for workspace, audio, battery, Bluetooth, and app icons.

## Configured Areas

- `hypr/` - Hyprland, Hyprpaper, Hypridle, and Hyprlock configuration
- `waybar/` - Waybar config, CSS, scripts, and small SVG assets
- `rofi/` - Rofi launcher theme with a left image panel
- `kitty/` - Kitty terminal configuration
- `fastfetch/` - Fastfetch module layout and custom ASCII logo
- `gtk-3.0/`, `dconf/`, `dolphinrc`, `baloofileinformationrc` - desktop/app settings

## Desktop Notes

- Hyprland starts Waybar, Hyprpaper, clipboard watchers, Hypridle, and the KDE
  polkit authentication agent.
- Startup workspaces open Kitty, VSCodium, Firefox, Dolphin, and Spotify.
- Hyprlock uses a blurred screenshot background, a centered clock, the
  `User` label, and an image from `~/Images/Mechanicus-Icon.png`.
- Hyprpaper uses `~/Images/MechAdept-Entertainment.jpg`.
- Waybar uses local helpers in `waybar/scripts/`.
- Waybar right modules open GTK popups for media, Wi-Fi, Bluetooth, and volume.
  The media module uses MPRIS/playerctl, Wi-Fi uses NetworkManager/nmcli,
  Bluetooth uses bluetoothctl, and volume uses wpctl.
- Rofi references `~/Images/AdeptusMechanicus-Tarrot.jpg`.
- Fastfetch uses `fastfetch/logo.txt` as a raw text logo. The current logo is
  about 100 columns wide, so it looks best in a wide Kitty window.

## Generated App State

These directories are mostly application-generated state and caches rather than hand-written config:

- `GIMP/`
- `VSCodium/`
- `obsidian/`
- `spotify/`
- `mozilla/`
- `pulse/`
- `session/`
- `trashrc`

## Quick Checks

- `hyprctl reload` - reload Hyprland after config edits
- `waybar` - test the bar from a terminal
- `rofi -show drun` - test the launcher
- `fastfetch --config ~/.config/fastfetch/config.jsonc` - preview Fastfetch
