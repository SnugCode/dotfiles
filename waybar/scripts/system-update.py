#!/usr/bin/env python3
"""Run the system update independently of the Waybar settings window."""

import subprocess


def notify(body, urgency="normal"):
    try:
        subprocess.run(
            ["notify-send", "-a", "System Update", "-u", urgency, "System Update", body],
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def main():
    notify("Starting system update…")
    try:
        result = subprocess.run(
            [
                "pkexec", "sh", "-c",
                "pacman -Syu --noconfirm && pacman -Scc --noconfirm",
            ],
            check=False,
        )
    except OSError as error:
        notify(f"Could not start update: {error}", "critical")
        return
    if result.returncode == 0:
        notify("Update and cache cleanup complete.")
    else:
        notify("Update or cache cleanup failed.", "critical")


if __name__ == "__main__":
    main()
