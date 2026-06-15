"""Shared data structures and helpers for launcher scanners."""

import os
import binascii
from dataclasses import dataclass, field


@dataclass
class Game:
    name: str
    launcher: str          # "GOG", "Epic", "Ubisoft", "EA", "Xbox", "Battle.net"
    # Either a direct exe...
    exe: str = ""          # quoted path to launch directly, OR
    # ...or a launcher URI (preferred — hands off to the right launcher)
    launch_uri: str = ""
    start_dir: str = ""
    install_dir: str = ""
    # Local file (exe/ico/png) a scanner already found for use as the icon.
    icon_source: str = ""

    def steam_exe(self):
        """What goes in the Steam shortcut's Exe field."""
        if self.launch_uri:
            return self.launch_uri
        return self.exe

    def steam_start_dir(self):
        if self.start_dir:
            return self.start_dir
        if self.install_dir:
            return f'"{self.install_dir}"'
        return ""


def steam_appid(name: str, exe: str) -> int:
    """
    Steam derives the non-Steam shortcut appid from a CRC32 of exe+name
    with the high bit set. Replicating it keeps shortcuts stable across runs
    so we don't create duplicates.
    """
    key = (exe + name).encode("utf-8")
    crc = binascii.crc32(key) & 0xFFFFFFFF
    return crc | 0x80000000


def is_windows():
    return os.name == "nt"


def env(name, default=""):
    return os.environ.get(name, default)


# Top-level / system directories we must never recursively walk.
_NON_GAME_DIRS = {
    "program files", "program files (x86)", "programdata",
    "windows", "users", "system32", "appdata",
}


def is_game_dir(path: str) -> bool:
    """
    True only if `path` looks like a specific game install folder that's safe
    to walk recursively. Rejects drive roots and broad system/top-level
    directories, so a bogus registry value (e.g. DisplayPath = "C:\\") can't
    trigger a full-disk traversal that looks like a system hang.
    """
    if not path:
        return False
    p = os.path.normpath(path)
    if not os.path.isdir(p):
        return False
    _drive, tail = os.path.splitdrive(p)
    parts = [seg for seg in tail.split(os.sep) if seg]
    if not parts:                       # drive root, e.g. C:\
        return False
    if parts[-1].lower() in _NON_GAME_DIRS:
        return False
    return True


def iter_files(root: str, max_depth: int = 2):
    """
    Yield full paths of files under `root`, descending at most `max_depth`
    directory levels below it. Prunes the walk in place (and refuses unsafe
    roots), so a deep, huge, or root-like directory can't stall the scan.
    """
    if not is_game_dir(root):
        return
    root = os.path.normpath(root)
    base = root.rstrip(os.sep).count(os.sep)
    for dirpath, dirs, files in os.walk(root):
        if dirpath.rstrip(os.sep).count(os.sep) - base >= max_depth:
            dirs[:] = []  # prune: descend no further
        for f in files:
            yield os.path.join(dirpath, f)
