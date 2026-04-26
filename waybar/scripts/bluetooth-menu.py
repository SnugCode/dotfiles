#!/usr/bin/env python3

import fcntl
import re
import signal
import subprocess
import time

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402


LOCK_PATH = "/tmp/waybar-bluetooth-menu.lock"


def run(*args):
    return subprocess.run(args, check=False, capture_output=True, text=True)


def controller_powered():
    result = run("bluetoothctl", "show")
    match = re.search(r"Powered:\s+(yes|no)", result.stdout)
    return match is not None and match.group(1) == "yes"


def parse_devices(output):
    devices = []
    for line in output.splitlines():
        match = re.match(r"Device\s+([0-9A-F:]{17})\s+(.+)", line)
        if match:
            devices.append({"mac": match.group(1), "name": match.group(2)})
    return devices


def paired_devices():
    devices = parse_devices(run("bluetoothctl", "devices", "Paired").stdout)
    connected = {
        device["mac"]
        for device in parse_devices(run("bluetoothctl", "devices", "Connected").stdout)
    }

    for device in devices:
        device["connected"] = device["mac"] in connected

    return devices


class BluetoothMenu(Gtk.Window):
    def __init__(self):
        super().__init__(title="Bluetooth")

        self.last_activity = time.monotonic()

        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_border_width(12)
        self.add_events(
            Gdk.EventMask.ENTER_NOTIFY_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.BUTTON_PRESS_MASK
        )

        self.root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(self.root)

        self.connect("enter-notify-event", self.mark_active)
        self.connect("motion-notify-event", self.mark_active)
        self.connect("button-press-event", self.mark_active)
        self.connect("key-press-event", self.on_key_press)
        GLib.timeout_add_seconds(1, self.close_if_idle)

        self.apply_css()
        self.rebuild()

    def apply_css(self):
        css = b"""
        window {
            background: rgba(18, 18, 18, 0.96);
            border: 1px solid rgba(255, 255, 255, 0.14);
            border-radius: 8px;
            color: #ffffff;
        }

        .title {
            font-weight: 700;
            font-size: 14px;
        }

        .bluetooth-icon {
            font-family: "0xProto Nerd Font Mono";
            font-size: 22px;
        }

        .device-name {
            font-weight: 700;
        }

        .device-status {
            color: rgba(255, 255, 255, 0.68);
            font-size: 11px;
        }

        button {
            min-height: 28px;
            padding: 0 10px;
            border-radius: 7px;
            background: rgba(255, 255, 255, 0.12);
            color: #ffffff;
        }

        button:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        separator {
            background: rgba(255, 255, 255, 0.12);
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def rebuild(self):
        for child in self.root.get_children():
            self.root.remove(child)

        powered = controller_powered()

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon = Gtk.Label(label="󰂯" if powered else "󰂲")
        icon.get_style_context().add_class("bluetooth-icon")
        header.pack_start(icon, False, False, 0)

        title = Gtk.Label(label="Bluetooth")
        title.get_style_context().add_class("title")
        title.set_halign(Gtk.Align.START)
        header.pack_start(title, True, True, 0)

        power = Gtk.Switch()
        power.set_active(powered)
        power.connect("notify::active", self.on_power_changed)
        header.pack_start(power, False, False, 0)
        self.root.pack_start(header, False, False, 0)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.root.pack_start(separator, False, False, 0)

        if powered:
            devices = paired_devices()
            if devices:
                for device in devices:
                    self.root.pack_start(self.device_row(device), False, False, 0)
            else:
                empty = Gtk.Label(label="No paired devices")
                empty.set_halign(Gtk.Align.START)
                empty.get_style_context().add_class("device-status")
                self.root.pack_start(empty, False, False, 0)
        else:
            off = Gtk.Label(label="Bluetooth is off")
            off.set_halign(Gtk.Align.START)
            off.get_style_context().add_class("device-status")
            self.root.pack_start(off, False, False, 0)

        manager = Gtk.Button(label="Open Manager")
        manager.connect("clicked", self.open_manager)
        self.root.pack_start(manager, False, False, 0)
        self.show_all()

    def device_row(self, device):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.set_size_request(260, -1)

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        name = Gtk.Label(label=device["name"])
        name.set_halign(Gtk.Align.START)
        name.set_ellipsize(Pango.EllipsizeMode.END)
        name.get_style_context().add_class("device-name")
        labels.pack_start(name, False, False, 0)

        status = Gtk.Label(label="Connected" if device["connected"] else "Paired")
        status.set_halign(Gtk.Align.START)
        status.get_style_context().add_class("device-status")
        labels.pack_start(status, False, False, 0)
        row.pack_start(labels, True, True, 0)

        action = Gtk.Button(label="Disconnect" if device["connected"] else "Connect")
        action.connect("clicked", self.toggle_device, device)
        row.pack_start(action, False, False, 0)

        return row

    def on_power_changed(self, switch, _param):
        self.mark_active()
        state = "on" if switch.get_active() else "off"
        run("bluetoothctl", "power", state)
        GLib.timeout_add(350, self.refresh)

    def toggle_device(self, _button, device):
        self.mark_active()
        command = "disconnect" if device["connected"] else "connect"
        run("bluetoothctl", command, device["mac"])
        GLib.timeout_add(600, self.refresh)

    def refresh(self):
        self.rebuild()
        return GLib.SOURCE_REMOVE

    def open_manager(self, _button):
        self.mark_active()
        subprocess.Popen(["blueman-manager"])
        Gtk.main_quit()

    def on_key_press(self, _window, event):
        self.mark_active()
        if event.keyval == Gdk.KEY_Escape:
            Gtk.main_quit()

    def mark_active(self, *_args):
        self.last_activity = time.monotonic()
        return False

    def close_if_idle(self):
        if time.monotonic() - self.last_activity > 15:
            Gtk.main_quit()
            return GLib.SOURCE_REMOVE

        return GLib.SOURCE_CONTINUE

    def present_near_top_right(self):
        self.show_all()

        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        geometry = monitor.get_geometry()

        width, _height = self.get_size()
        self.move(
            geometry.x + geometry.width - width - 12,
            geometry.y + 34,
        )
        self.present()


def main():
    lock_file = open(LOCK_PATH, "w")
    try:
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    window = BluetoothMenu()
    window.present_near_top_right()
    Gtk.main()


if __name__ == "__main__":
    main()
