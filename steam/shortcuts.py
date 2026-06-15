r"""
Manages reading/writing Steam's shortcuts.vdf for the active user(s).

Finds the file at:
  <SteamPath>\userdata\<steamID3>\config\shortcuts.vdf
SteamPath comes from the registry (Windows) or config override.

Always backs up before writing. Dedupes by appid so re-running the tool
won't create duplicate shortcuts.
"""

import os
import glob
import shutil
import time

from . import vdf
from scanners.common import steam_appid, is_windows, env


def find_steam_path(override: str = "") -> str:
    if override:
        return override
    if is_windows():
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
            path, _ = winreg.QueryValueEx(key, "SteamPath")
            winreg.CloseKey(key)
            return os.path.normpath(path)
        except (ImportError, FileNotFoundError, OSError):
            pass
    # Common fallbacks
    for guess in [
        os.path.join(env("PROGRAMFILES(X86)", r"C:\Program Files (x86)"), "Steam"),
        os.path.join(env("PROGRAMFILES", r"C:\Program Files"), "Steam"),
    ]:
        if os.path.exists(guess):
            return guess
    return ""


def find_shortcuts_files(steam_path: str):
    """Returns list of (userid, shortcuts.vdf path) for every Steam user."""
    results = []
    userdata = os.path.join(steam_path, "userdata")
    if not os.path.isdir(userdata):
        return results
    for uid_dir in glob.glob(os.path.join(userdata, "*")):
        uid = os.path.basename(uid_dir)
        cfg = os.path.join(uid_dir, "config")
        os.makedirs(cfg, exist_ok=True)
        results.append((uid, os.path.join(cfg, "shortcuts.vdf")))
    return results


def load(path: str):
    if not os.path.exists(path):
        return []
    with open(path, "rb") as f:
        return vdf.parse(f.read())


def backup(path: str):
    if os.path.exists(path):
        stamp = time.strftime("%Y%m%d-%H%M%S")
        dst = f"{path}.{stamp}.bak"
        shutil.copy2(path, dst)
        return dst
    return None


def merge(existing, games, default_tag=True):
    """
    Merge Game objects into the existing shortcut list.
    Returns (merged_list, added_count, skipped_count).
    Dedupe key = appid (derived from exe+name, same as Steam's own).
    """
    by_appid = {}
    for e in existing:
        if "appid" in e:
            by_appid[e["appid"] & 0xFFFFFFFF] = e

    added = skipped = 0
    for g in games:
        exe = g.steam_exe()
        appid = steam_appid(g.name, exe)
        if (appid & 0xFFFFFFFF) in by_appid:
            skipped += 1
            continue
        entry = {
            "appid": appid,
            "AppName": g.name,
            "Exe": exe,
            "StartDir": g.steam_start_dir(),
            "icon": "",
            "ShortcutPath": "",
            "LaunchOptions": "",
            "IsHidden": 0,
            "AllowDesktopConfig": 1,
            "AllowOverlay": 1,
            "OpenVR": 0,
            "Devkit": 0,
            "DevkitGameID": "",
            "LastPlayTime": 0,
        }
        if default_tag:
            entry["tags"] = {"0": g.launcher}
        existing.append(entry)
        by_appid[appid & 0xFFFFFFFF] = entry
        added += 1
    return existing, added, skipped


def save(path: str, shortcuts):
    data = vdf.dump(shortcuts)
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)  # atomic on same volume
