r"""
Ubisoft Connect (Uplay) scanner.

Installed games are registered under:
  HKLM\SOFTWARE\WOW6432Node\Ubisoft\Launcher\Installs\<gameId>
each with an InstallDir value. The game's display name is not in that key,
so we fall back to the install folder name, and launch via the
uplay://launch/<gameId>/0 URI.

Registry access only works on Windows. On other OSes scan() returns [].
"""

import os

from .common import Game, is_windows, env

REG_PATH = r"SOFTWARE\WOW6432Node\Ubisoft\Launcher\Installs"


def scan():
    if not is_windows():
        return []
    try:
        import winreg
    except ImportError:
        return []

    games = []
    try:
        root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_PATH)
    except FileNotFoundError:
        return []

    i = 0
    while True:
        try:
            game_id = winreg.EnumKey(root, i)
        except OSError:
            break
        i += 1
        try:
            sub = winreg.OpenKey(root, game_id)
            install_dir, _ = winreg.QueryValueEx(sub, "InstallDir")
            winreg.CloseKey(sub)
        except (FileNotFoundError, OSError):
            continue

        # Folder name is the most reliable human-readable label we have.
        name = os.path.basename(os.path.normpath(install_dir)) or f"Ubisoft {game_id}"
        games.append(Game(
            name=name,
            launcher="Ubisoft",
            launch_uri=f"uplay://launch/{game_id}/0",
            install_dir=install_dir,
            start_dir=f'"{install_dir}"' if install_dir else "",
        ))
    winreg.CloseKey(root)
    return games
