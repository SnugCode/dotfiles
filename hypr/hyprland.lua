-- Hyprland config
-- https://wiki.hypr.land/Configuring/Start/


--------------------
---- MONITORS ----
--------------------

hl.monitor({
    output   = "eDP-1",
    mode     = "preferred",
    position = "0x0",
    scale    = 1.25,
})

hl.monitor({
    output   = "DP-1",
    mode     = "1920x1080@180",
    position = "0x0",
    scale    = 1,
})

hl.config({
    xwayland = {
        force_zero_scaling = true,
    },
})


---------------------
---- MY PROGRAMS ----
---------------------

local terminal    = "kitty"
local fileManager = "dolphin"
local menu        = "rofi -show drun"
local browser     = "firefox"


-------------------
---- AUTOSTART ----
-------------------

hl.on("hyprland.start", function()
    -- DE
    hl.exec_cmd("hyprpaper")
    hl.exec_cmd("waybar")
    hl.exec_cmd("dunst")
    hl.exec_cmd("~/.config/hypr/scripts/display-mode.sh watch")

    -- Clipboard
    hl.exec_cmd("wl-paste --type text --watch cliphist store")
    hl.exec_cmd("wl-paste --type image --watch cliphist store")

    -- Authentication
    hl.exec_cmd("/usr/lib/polkit-kde-authentication-agent-1")
    hl.exec_cmd("gnome-keyring-daemon --start --components=secrets,pkcs11")

    -- Hyprlock
    hl.exec_cmd("dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP")
    hl.exec_cmd("systemctl --user import-environment WAYLAND_DISPLAY XDG_CURRENT_DESKTOP")
    hl.exec_cmd("hypridle")

    -- Battery monitor
    hl.exec_cmd("~/.config/scripts/battery-monitor.sh")

    -- Mobile
    hl.exec_cmd("kdeconnect-indicator")
end)


-------------------------------
---- ENVIRONMENT VARIABLES ----
-------------------------------

hl.env("XCURSOR_SIZE",               "24")
hl.env("HYPRCURSOR_SIZE",            "24")
hl.env("NIXOS_OZONE_WL",             "1")
hl.env("ELECTRON_OZONE_PLATFORM_HINT", "auto")


-----------------------
---- LOOK AND FEEL ----
-----------------------

hl.config({
    general = {
        gaps_in  = 2,
        gaps_out = 6,

        border_size = 2,

        col = {
            active_border   = { colors = { "rgba(33ccffee)", "rgba(00ff99ee)" }, angle = 45 },
            inactive_border = "rgba(595959aa)",
        },

        resize_on_border = false,
        allow_tearing    = false,
        layout           = "dwindle",
    },

    decoration = {
        rounding       = 10,
        rounding_power = 2,

        active_opacity   = 1.0,
        inactive_opacity = 1.0,

        shadow = {
            enabled      = true,
            range        = 4,
            render_power = 3,
            color        = "rgba(1a1a1aee)",
        },

        blur = {
            enabled           = true,
            size              = 10,
            passes            = 3,
            noise             = 0.015,
            contrast          = 1.0,
            brightness        = 1.0,
            vibrancy          = 0.25,
            vibrancy_darkness = 0.5,
            xray              = false,
        },
    },

    animations = {
        enabled = true,
    },
})


------------------------
---- CURVES & ANIMS ----
------------------------

-- Custom bezier curves
hl.curve("spring",   { type = "bezier", points = { { 0.25, 1.15 }, { 0.35, 1.0  } } })
hl.curve("quickOut", { type = "bezier", points = { { 0.1,  0.9  }, { 0.2,  1.0  } } })
hl.curve("swipe",    { type = "bezier", points = { { 0.2,  1.0  }, { 0.25, 1.0  } } })
hl.curve("linear",   { type = "bezier", points = { { 0,    0    }, { 1,    1    } } })

hl.animation({ leaf = "border",        enabled = true, speed = 6,   bezier = "spring"   })
hl.animation({ leaf = "windows",       enabled = true, speed = 5.5, bezier = "spring"   })
hl.animation({ leaf = "windowsIn",     enabled = true, speed = 5.5, bezier = "spring",   style = "popin 82%" })
hl.animation({ leaf = "windowsOut",    enabled = true, speed = 7,   bezier = "quickOut", style = "popin 82%" })
hl.animation({ leaf = "fade",          enabled = true, speed = 5,   bezier = "quickOut" })
hl.animation({ leaf = "fadeIn",        enabled = true, speed = 5,   bezier = "quickOut" })
hl.animation({ leaf = "fadeOut",       enabled = true, speed = 7,   bezier = "quickOut" })
hl.animation({ leaf = "layers",        enabled = true, speed = 5,   bezier = "spring"   })
hl.animation({ leaf = "layersIn",      enabled = true, speed = 5,   bezier = "spring",   style = "fade" })
hl.animation({ leaf = "layersOut",     enabled = true, speed = 6,   bezier = "quickOut", style = "fade" })
hl.animation({ leaf = "fadeLayersIn",  enabled = true, speed = 5,   bezier = "quickOut" })
hl.animation({ leaf = "fadeLayersOut", enabled = true, speed = 6,   bezier = "quickOut" })
hl.animation({ leaf = "workspaces",    enabled = true, speed = 5,   bezier = "swipe",    style = "slidefade 20%" })
hl.animation({ leaf = "workspacesIn",  enabled = true, speed = 5,   bezier = "swipe",    style = "slidefade 20%" })
hl.animation({ leaf = "workspacesOut", enabled = true, speed = 5,   bezier = "swipe",    style = "slidefade 20%" })


-----------------
---- LAYOUTS ----
-----------------

hl.config({
    dwindle = {
        preserve_split = true,
    },

    master = {
        new_status = "master",
    },
})


--------------
---- MISC ----
--------------

hl.config({
    misc = {
        force_default_wallpaper = -1,
        disable_hyprland_logo   = true,
        vrr                     = 2,
    },
})


---------------
---- INPUT ----
---------------

hl.config({
    input = {
        kb_layout  = "us",
        kb_variant = "",
        kb_model   = "",
        kb_options = "",
        kb_rules   = "",

        follow_mouse   = 1,
        sensitivity    = 0,
        force_no_accel = true,
        accel_profile  = "flat",

        touchpad = {
            natural_scroll = true,
        },
    },
})

hl.gesture({
    fingers   = 3,
    direction = "horizontal",
    action    = "workspace",
})

hl.device({
    name        = "epic-mouse-v1",
    sensitivity = -0.5,
})


---------------------
---- KEYBINDINGS ----
---------------------

local mainMod = "SUPER"

-- Actions
hl.bind(mainMod .. " + Q", hl.dsp.window.close())
hl.bind(mainMod .. " + M", hl.dsp.exec_cmd("command -v hyprshutdown >/dev/null 2>&1 && hyprshutdown || hyprctl dispatch exit"))

-- Refresh Waybar
hl.bind(mainMod .. " + R", hl.dsp.exec_cmd("bash ~/.config/waybar/scripts/launch.sh"))

-- Open programs
hl.bind(mainMod .. " + E",     hl.dsp.exec_cmd(fileManager))
hl.bind(mainMod .. " + SPACE", hl.dsp.exec_cmd(menu))
hl.bind(mainMod .. " + equal", hl.dsp.exec_cmd("rofi -show calc -no-show-match -no-sort"))
hl.bind(mainMod .. " + C",     hl.dsp.exec_cmd(terminal))
hl.bind(mainMod .. " + X",     hl.dsp.exec_cmd(browser))
hl.bind(mainMod .. " + B",     hl.dsp.exec_cmd(browser))
hl.bind(mainMod .. " + I",     hl.dsp.exec_cmd("codium"))
hl.bind(mainMod .. " + N",     hl.dsp.exec_cmd("cider"))

-- Clipboard history
hl.bind(mainMod .. " + V", hl.dsp.exec_cmd('cliphist list | rofi -dmenu -display-columns -p "Search Clipboard" | cliphist decode | wl-copy'))

-- Screenshot
hl.bind("PRINT", hl.dsp.exec_cmd("hyprshot -m region"))

-- Move focus
hl.bind(mainMod .. " + left",  hl.dsp.focus({ direction = "left"  }))
hl.bind(mainMod .. " + right", hl.dsp.focus({ direction = "right" }))
hl.bind(mainMod .. " + up",    hl.dsp.focus({ direction = "up"    }))
hl.bind(mainMod .. " + down",  hl.dsp.focus({ direction = "down"  }))

-- Switch workspaces / move windows (1-10, key 0 = workspace 10)
for i = 1, 10 do
    local key = i % 10
    hl.bind(mainMod .. " + " .. key,         hl.dsp.focus({ workspace = i }))
    hl.bind(mainMod .. " + SHIFT + " .. key, hl.dsp.window.move({ workspace = i }))
end

-- Mouse workspace switching (thumb buttons)
hl.bind("mouse:275", hl.dsp.focus({ workspace = "e-1" }))
hl.bind("mouse:276", hl.dsp.focus({ workspace = "e+1" }))

-- Scroll through workspaces
hl.bind(mainMod .. " + mouse_down", hl.dsp.focus({ workspace = "e+1" }))
hl.bind(mainMod .. " + mouse_up",   hl.dsp.focus({ workspace = "e-1" }))

-- Move/resize windows with mouse
hl.bind(mainMod .. " + mouse:272", hl.dsp.window.drag(),   { mouse = true })
hl.bind(mainMod .. " + mouse:273", hl.dsp.window.resize(), { mouse = true })

-- Volume
hl.bind("XF86AudioRaiseVolume", hl.dsp.exec_cmd("~/.config/waybar/scripts/volume-slider.py --osd up"),   { locked = true, repeating = true })
hl.bind("XF86AudioLowerVolume", hl.dsp.exec_cmd("~/.config/waybar/scripts/volume-slider.py --osd down"), { locked = true, repeating = true })
hl.bind("XF86AudioMute",        hl.dsp.exec_cmd("~/.config/waybar/scripts/volume-slider.py --osd mute"), { locked = true, repeating = true })
hl.bind("XF86AudioMicMute",     hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"),          { locked = true })

-- Brightness
hl.bind("XF86MonBrightnessUp",   hl.dsp.exec_cmd("~/.config/waybar/scripts/brightness-slider.py --osd up"),   { locked = true, repeating = true })
hl.bind("XF86MonBrightnessDown", hl.dsp.exec_cmd("~/.config/waybar/scripts/brightness-slider.py --osd down"), { locked = true, repeating = true })

-- Media
hl.bind("XF86AudioNext",  hl.dsp.exec_cmd("playerctl next"),       { locked = true })
hl.bind("XF86AudioPause", hl.dsp.exec_cmd("playerctl play-pause"), { locked = true })
hl.bind("XF86AudioPlay",  hl.dsp.exec_cmd("playerctl play-pause"), { locked = true })
hl.bind("XF86AudioPrev",  hl.dsp.exec_cmd("playerctl previous"),   { locked = true })

-- Lid switch
hl.bind("switch:on:Lid Switch",  hl.dsp.exec_cmd("~/.config/hypr/scripts/display-mode.sh closed"), { locked = true })
hl.bind("switch:off:Lid Switch", hl.dsp.exec_cmd("~/.config/hypr/scripts/display-mode.sh open"),   { locked = true })


-------------------
---- LAYER RULES --
-------------------

hl.layer_rule({
    name        = "waybar-blur",
    match       = { namespace = "waybar" },
    blur        = true,
    blur_popups = true,
})

hl.layer_rule({
    name  = "dunst-blur",
    match = { namespace = "notifications" },
    blur  = true,
})


---------------------
---- WINDOW RULES ---
---------------------

hl.window_rule({
    name           = "suppress-maximize-events",
    match          = { class = ".*" },
    suppress_event = "maximize",
})

hl.window_rule({
    name  = "fix-xwayland-drags",
    match = {
        class      = "^$",
        title      = "^$",
        xwayland   = true,
        float      = true,
        fullscreen = false,
        pin        = false,
    },
    no_focus = true,
})

hl.window_rule({
    name  = "move-hyprland-run",
    match = { class = "hyprland-run" },
    move  = "20 monitor_h-120",
    float = true,
})

hl.window_rule({
    name       = "rofi-float",
    match      = { class = "^Rofi$" },
    float      = true,
    center     = true,
    dim_around = true,
})

hl.window_rule({
    name      = "codium-workspace",
    match     = { class = "^codium$" },
    workspace = "2",
})
