r"""
EA app (formerly Origin) scanner.

Installed games appear in the registry under one of several parents that
have shifted across EA app / Origin versions:
  HKLM\SOFTWARE\WOW6432Node\Origin Games\<id>
  HKLM\SOFTWARE\WOW6432Node\EA Games\<id>
  HKLM\SOFTWARE\WOW6432Node\Electronic Arts\EA Games\<id>

The subkey name is NOT a reliable offer id — under some parents it's the
numeric offer id, under others it's the game name. Launching with the wrong
value silently fails (e.g. origin2://...?offerIds=STAR WARS Squadrons does
nothing). So we resolve the launch target in priority order:

  1. A numeric offer id read from inside the key (or a numeric key name) ->
     origin2://game/launch?offerIds=<id>     (cleanest; EA app handles it)
  2. Otherwise, the game's main executable on disk ->
     launch the exe directly so the shortcut at least WORKS.

We also try to find the game's primary .exe regardless, to use for the
Steam icon later.

Windows-only; returns [] elsewhere.
"""

import os
import glob

from .common import Game, is_windows, env

CANDIDATE_KEYS = [
    r"SOFTWARE\WOW6432Node\Origin Games",
    r"SOFTWARE\WOW6432Node\EA Games",
    r"SOFTWARE\WOW6432Node\Electronic Arts\EA Games",
]

# Registry value names that, across versions, have held the install path.
INSTALL_VALUE_NAMES = ("Install Dir", "InstallLocation", "InstallDir", "DisplayPath")
# Registry value names that have held the numeric offer / content id.
OFFER_VALUE_NAMES = ("OfferId", "OfferIds", "ContentId", "InstallerId")


def _read_first_value(winreg, key, names):
    for n in names:
        try:
            val, _ = winreg.QueryValueEx(key, n)
            if val:
                return str(val)
        except (FileNotFoundError, OSError):
            continue
    return ""


def _looks_numeric_offer(s: str) -> bool:
    # EA offer ids are numeric, sometimes comma-joined (e.g. "1076612,1234").
    s = (s or "").strip()
    if not s:
        return False
    parts = [p for p in s.replace(" ", "").split(",") if p]
    return bool(parts) and all(p.isdigit() for p in parts)


def _find_main_exe(install_dir: str) -> str:
    """Best-guess the game's primary exe inside its install folder."""
    if not install_dir or not os.path.isdir(install_dir):
        return ""
    exes = []
    for root, _dirs, files in os.walk(install_dir):
        depth = root[len(install_dir):].count(os.sep)
        if depth > 2:  # don't descend too far
            continue
        for f in files:
            if f.lower().endswith(".exe"):
                full = os.path.join(root, f)
                low = f.lower()
                # Penalise obvious non-game exes.
                score = os.path.getsize(full) if os.path.exists(full) else 0
                if any(b in low for b in (
                    "unins", "setup", "crash", "report", "redist", "vcredist",
                    "directx", "dotnet", "launcher", "cleanup", "touchup",
                    "activation", "config", "settings",
                )):
                    score //= 100  # heavy penalty but not disqualifying
                exes.append((score, full))
    if not exes:
        return ""
    exes.sort(reverse=True)  # biggest plausible exe wins
    return exes[0][1]


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
                subkey_name = winreg.EnumKey(root, i)
            except OSError:
                break
            i += 1
            try:
                sub = winreg.OpenKey(root, subkey_name)
            except (FileNotFoundError, OSError):
                continue

            install_dir = _read_first_value(winreg, sub, INSTALL_VALUE_NAMES)
            offer_id = _read_first_value(winreg, sub, OFFER_VALUE_NAMES)
            winreg.CloseKey(sub)

            if not install_dir:
                continue
            install_dir = os.path.normpath(install_dir)
            if install_dir in seen_dirs:
                continue
            seen_dirs.add(install_dir)

            # Resolve a usable offer id:
            #   prefer an explicit numeric value, else a numeric subkey name.
            if not offer_id and _looks_numeric_offer(subkey_name):
                offer_id = subkey_name

            name = os.path.basename(install_dir) or subkey_name
            main_exe = _find_main_exe(install_dir)

            if offer_id and _looks_numeric_offer(offer_id):
                # Path 1: clean deep-link launch via EA app.
                g = Game(
                    name=name,
                    launcher="EA",
                    launch_uri=f"origin2://game/launch?offerIds={offer_id}",
                    install_dir=install_dir,
                    start_dir=f'"{install_dir}"',
                )
            elif main_exe:
                # Path 2: no valid offer id -> launch the exe directly so it works.
                g = Game(
                    name=name,
                    launcher="EA",
                    exe=f'"{main_exe}"',
                    install_dir=install_dir,
                    start_dir=f'"{os.path.dirname(main_exe)}"',
                )
            else:
                # Nothing launchable found; skip rather than add a dead shortcut.
                print(f"  [EA] no offer id or exe for '{name}', skipped")
                continue

            # Stash exe for icon use even when launching via URI.
            g.icon_source = main_exe
            games.append(g)
        winreg.CloseKey(root)
    return games