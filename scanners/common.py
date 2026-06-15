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
