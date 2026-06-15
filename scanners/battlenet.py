r"""
Battle.net scanner.

Battle.net records installed products in:
  C:\ProgramData\Battle.net\Agent\product.db        (protobuf, awkward)
and more readably in each game's install via the launcher config:
  C:\ProgramData\Battle.net\Battle.net.config        (JSON)

The cleanest cross-version signal is the JSON config's "Games" section,
which lists product codes + last-known install paths. We launch via the
battlenet:// URI using the product code.

Known product codes (uid -> friendly name) for nicer labels:
"""

import os
import json

from .common import Game, env

CONFIG = os.path.join(
    env("PROGRAMDATA", r"C:\ProgramData"),
    "Battle.net", "Battle.net.config",
)

PRODUCT_NAMES = {
    "wow": "World of Warcraft",
    "d3": "Diablo III",
    "d4": "Diablo IV",
    "pro": "Overwatch",
    "s1": "StarCraft Remastered",
    "s2": "StarCraft II",
    "hero": "Heroes of the Storm",
    "hs": "Hearthstone",
    "w3": "Warcraft III Reforged",
    "viper": "Call of Duty: Black Ops 4",
    "odin": "Call of Duty: Modern Warfare",
    "zeus": "Call of Duty: Black Ops Cold War",
    "fore": "Call of Duty: Vanguard",
    "auks": "Call of Duty",
    "wlby": "Crash Bandicoot 4",
    "anbs": "Diablo Immortal",
    "rtro": "Blizzard Arcade Collection",
}


def scan(config_path: str = None):
    config_path = config_path or CONFIG
    if not os.path.exists(config_path):
        return []

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"  [Battle.net] config read error: {e}")
        return []

    games = []
    games_section = cfg.get("Games", {})
    for code, info in games_section.items():
        if code in ("battle_net", ""):  # the client itself
            continue
        install = info.get("LastActionLocation") or info.get("InstallPath") or ""
        name = PRODUCT_NAMES.get(code, code)
        games.append(Game(
            name=name,
            launcher="Battle.net",
            launch_uri=f'"{_bnet_exe()}" --exec="launch {code}"',
            install_dir=install,
            start_dir=f'"{install}"' if install else "",
        ))
    return games


def _bnet_exe():
    candidates = [
        os.path.join(env("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
                     "Battle.net", "Battle.net.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0]
