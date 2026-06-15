r"""
EA app (formerly Origin) scanner.

The EA app records installed content under the registry:
  HKLM\SOFTWARE\WOW6432Node\Electronic Arts\EA Desktop\...   (varies)
and also keeps per-game install metadata. The most portable signal across
EA app versions is the InstallDir registry values under EA's keys, plus
the installed-games registry under "Origin"/"EA Games".

We try a few known registry locations and fall back to scanning the
default install root. Launch is via origin2:// deep link when a content id
is known, else direct exe.

Windows-only; returns [] elsewhere.
"""

import os

from .common import Game, is_windows, env

# Common parent keys that have held EA/Origin install entries over the years.
CANDIDATE_KEYS = [
    r"SOFTWARE\WOW6432Node\Origin Games",
    r"SOFTWARE\WOW6432Node\EA Games",
    r"SOFTWARE\WOW6432Node\Electronic Arts\EA Games",
]


def scan():
    if not is_windows():
        return []
    try:
        import winreg
    except ImportError:
        return []

    games = []
    seen_dirs = set()
    for key_path in CANDIDATE_KEYS:
        try:
            root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
        except FileNotFoundError:
            continue

        i = 0
        while True:
            try:
                content_id = winreg.EnumKey(root, i)
            except OSError:
                break
            i += 1
            try:
                sub = winreg.OpenKey(root, content_id)
                install_dir, _ = winreg.QueryValueEx(sub, "Install Dir")
                winreg.CloseKey(sub)
            except (FileNotFoundError, OSError):
                # Some entries use "InstallLocation" instead.
                try:
                    sub = winreg.OpenKey(root, content_id)
                    install_dir, _ = winreg.QueryValueEx(sub, "InstallLocation")
                    winreg.CloseKey(sub)
                except (FileNotFoundError, OSError):
                    continue

            install_dir = os.path.normpath(install_dir)
            if not install_dir or install_dir in seen_dirs:
                continue
            seen_dirs.add(install_dir)

            name = os.path.basename(install_dir) or content_id
            games.append(Game(
                name=name,
                launcher="EA",
                # origin2:// still works in the EA app for launch-by-offerId.
                launch_uri=f"origin2://game/launch?offerIds={content_id}",
                install_dir=install_dir,
                start_dir=f'"{install_dir}"',
            ))
        winreg.CloseKey(root)
    return games
