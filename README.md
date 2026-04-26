# dotfiles

Personal Linux desktop configuration files.

## Main Dependencies

- `hyprland` - Wayland compositor
- `hyprpaper` - wallpaper daemon used by Hyprland autostart
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
- `playerctl` - media keys and Waybar media click actions
- `wireplumber` / `wpctl` - audio volume and mute keybinds
- `pipewire` - audio stack used by the Waybar audio module
- `networkmanager` - network status and `nmtui-connect`
- `bluez` / `bluetoothctl` - Bluetooth status detection
- `blueman` - provides `blueman-manager`

## Fonts

- `0xProto Nerd Font Mono` - used by Kitty, Rofi, and Waybar
- `0xProto` - used by Waybar styling
- Nerd Font symbols are expected for workspace, audio, battery, Bluetooth, and app icons.

## Configured Areas

- `hypr/` - Hyprland and Hyprpaper configuration
- `waybar/` - Waybar config, CSS, scripts, and small SVG assets
- `rofi/` - Rofi launcher theme
- `kitty/` - Kitty terminal configuration
- `fastfetch/` - Fastfetch module layout
- `gtk-3.0/`, `dconf/`, `dolphinrc`, `baloofileinformationrc` - desktop/app settings

## Generated App State

These directories are mostly application-generated state and caches rather than hand-written config:

- `VSCodium/`
- `obsidian/`
- `spotify/`
- `mozilla/`
- `pulse/`
- `session/`
- `trashrc`

## Notes

- Hyprland launches Kitty, VSCodium, Firefox, Dolphin, and Spotify on startup workspaces.
- Waybar uses local scripts in `waybar/scripts/` and `waybar/apps/`.
- Rofi references images from `/home/snugcode/Images/`, including `AdeptusMechanicus-Tarrot.jpg`.
