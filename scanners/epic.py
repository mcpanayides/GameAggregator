r"""
Epic Games Launcher scanner.

Epic stores one JSON manifest per installed game in:
  C:\ProgramData\Epic\EpicGamesLauncher\Data\Manifests\*.item

Each .item is JSON with DisplayName, InstallLocation, LaunchExecutable,
and AppName (the catalog id used for the com.epicgames.launcher:// URI).
"""

import os
import json
import glob

from .common import Game, env

DEFAULT_MANIFEST_DIR = os.path.join(
    env("PROGRAMDATA", r"C:\ProgramData"),
    "Epic", "EpicGamesLauncher", "Data", "Manifests",
)


def scan(manifest_dir: str = None):
    manifest_dir = manifest_dir or DEFAULT_MANIFEST_DIR
    if not os.path.isdir(manifest_dir):
        return []

    games = []
    for item in glob.glob(os.path.join(manifest_dir, "*.item")):
        try:
            with open(item, "r", encoding="utf-8") as f:
                m = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"  [Epic] skipped {os.path.basename(item)}: {e}")
            continue

        name = m.get("DisplayName") or m.get("AppName")
        app_name = m.get("AppName") or m.get("MainGameAppName")
        install = m.get("InstallLocation", "")
        if not (name and app_name):
            continue

        # Launch through Epic so it handles auth/EAC; deep-link URI.
        uri = (f"com.epicgames.launcher://apps/{app_name}"
               "?action=launch&silent=true")
        games.append(Game(
            name=name,
            launcher="Epic",
            launch_uri=uri,
            install_dir=install,
            start_dir=f'"{install}"' if install else "",
        ))
    return games
