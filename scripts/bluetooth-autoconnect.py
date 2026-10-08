#!/usr/bin/env python3
"""
Auto-connect trusted/paired bluetooth devices when they come in range.
Listens for two BlueZ D-Bus events:
  - InterfacesAdded  : device freshly discovered
  - PropertiesChanged: device already known, RSSI appearing = came in range
"""
import signal
import subprocess

import dbus
import dbus.mainloop.glib
from gi.repository import GLib


_pending = set()


def mac_from_path(path):
    """'/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF' → 'AA:BB:CC:DD:EE:FF'"""
    last = str(path).split("/")[-1]
    if last.startswith("dev_"):
        return last[4:].replace("_", ":")
    return ""


def do_connect(mac):
    _pending.discard(mac)
    subprocess.run(["bluetoothctl", "connect", mac], capture_output=True, timeout=15)
    return False  # don't repeat GLib timeout


def schedule_connect(mac):
    if mac in _pending:
        return
    _pending.add(mac)
    GLib.timeout_add(1500, lambda: do_connect(mac))


def is_connectable(mac):
    """Return True if device is trusted/paired and not already connected."""
    result = subprocess.run(
        ["bluetoothctl", "info", mac], capture_output=True, text=True
    )
    info = result.stdout
    if "Connected: yes" in info:
        return False
    return "Trusted: yes" in info or "Paired: yes" in info


def on_interfaces_added(path, interfaces):
    if "org.bluez.Device1" not in interfaces:
        return
    props = interfaces["org.bluez.Device1"]
    mac = str(props.get("Address", "")) or mac_from_path(path)
    if not mac:
        return
    trusted = bool(props.get("Trusted", False))
    paired = bool(props.get("Paired", False))
    connected = bool(props.get("Connected", False))
    if (trusted or paired) and not connected:
        schedule_connect(mac)


def on_properties_changed(interface, changed, _invalidated, path=None):
    if interface != "org.bluez.Device1" or "RSSI" not in changed:
        return
    mac = mac_from_path(path or "")
    if mac and is_connectable(mac):
        schedule_connect(mac)


def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    bus.add_signal_receiver(
        on_interfaces_added,
        signal_name="InterfacesAdded",
        dbus_interface="org.freedesktop.DBus.ObjectManager",
        bus_name="org.bluez",
        path="/",
    )
    bus.add_signal_receiver(
        on_properties_changed,
        signal_name="PropertiesChanged",
        dbus_interface="org.freedesktop.DBus.Properties",
        bus_name="org.bluez",
        path_keyword="path",
    )

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    GLib.MainLoop().run()


if __name__ == "__main__":
    main()
