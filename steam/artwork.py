r"""
Artwork resolution for imported shortcuts.

Two distinct things Steam shows, handled by two different mechanisms:

  1. icon  -> goes in the shortcut's `icon` field in shortcuts.vdf.
              Points at a local .exe / .ico / .png. Fixes the "blue computer"
              small icons. Sourced entirely from local files on disk.

  2. grid artwork (big library tiles, hero banner, logo) -> CANNOT live in
              shortcuts.vdf. Steam reads them from:
                <steam>/userdata/<uid>/config/grid/
              named by appid:
                <appid>.png        (vertical capsule / library tile, 600x900)
                <appid>p.png       (vertical capsule, alt)
                <appid>_hero.png   (hero banner)
                <appid>_logo.png   (logo)
                <appid>.png (landscape 460x215 in older clients via <appid>.png)
              We download these from SteamGridDB when an API key is provided.

find_local_icon() is free and always runs. fetch_grid() only runs when a
SteamGridDB key is configured.
"""

import os
import json
import urllib.request
import urllib.parse

from scanners.common import iter_files

ICON_EXTS = (".ico", ".png", ".exe")


# ---------------------------------------------------------------------------
# Local icon discovery (free, no network)
# ---------------------------------------------------------------------------

def find_local_icon(game) -> str:
    """
    Return a local path Steam can use as the shortcut icon, or "".
    Priority:
      1. an explicit icon_source the scanner already found (e.g. EA main exe)
      2. a UWP logo PNG in the install dir (Xbox)
      3. a launcher-cached icon
      4. the largest plausible .exe in the install dir
    """
    # 1. scanner-provided
    src = (getattr(game, "icon_source", "") or "").strip('"')
    if src and os.path.exists(src):
        return src

    install = (game.install_dir or "").strip('"')
    if not install or not os.path.isdir(install):
        return ""

    # 2. Xbox/UWP ships logo PNGs right in the package folder.
    if game.launcher == "Xbox":
        logo = _find_uwp_logo(install)
        if logo:
            return logo

    # 3 & 4. Look for an .ico, else the best .exe.
    ico = _find_first(install, (".ico",))
    if ico:
        return ico
    exe = _find_best_exe(install)
    if exe:
        return exe
    return ""


def _find_uwp_logo(install: str) -> str:
    # UWP logos: Square150x150Logo / Square310x310Logo / *Logo*.png etc.
    wanted = ("square150x150", "square310x310", "logo", "storelogo")
    candidates = [
        f for f in iter_files(install, max_depth=3)
        if f.lower().endswith(".png")
        and any(w in os.path.basename(f).lower() for w in wanted)
    ]
    if not candidates:
        return ""
    # Prefer the largest file (usually the highest-res logo).
    candidates.sort(key=lambda p: os.path.getsize(p) if os.path.exists(p) else 0,
                    reverse=True)
    return candidates[0]


def _find_first(install: str, exts) -> str:
    for full in iter_files(install, max_depth=2):
        if full.lower().endswith(exts):
            return full
    return ""


def _find_best_exe(install: str) -> str:
    best = ""
    best_score = -1
    for full in iter_files(install, max_depth=2):
        low = os.path.basename(full).lower()
        if not low.endswith(".exe"):
            continue
        try:
            score = os.path.getsize(full)
        except OSError:
            score = 0
        if any(b in low for b in (
            "unins", "setup", "crash", "redist", "vcredist", "directx",
            "dotnet", "launcher", "cleanup", "touchup", "config",
        )):
            score //= 100
        if score > best_score:
            best_score, best = score, full
    return best


# ---------------------------------------------------------------------------
# SteamGridDB (optional, networked)
# ---------------------------------------------------------------------------

SGDB_BASE = "https://www.steamgriddb.com/api/v2"


class SteamGridDB:
    def __init__(self, api_key: str):
        self.key = api_key

    def _get(self, path: str):
        req = urllib.request.Request(
            SGDB_BASE + path,
            headers={"Authorization": f"Bearer {self.key}"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))

    def search_game_id(self, name: str):
        q = urllib.parse.quote(name)
        try:
            data = self._get(f"/search/autocomplete/{q}")
        except Exception as e:
            print(f"    [SGDB] search failed for '{name}': {e}")
            return None
        results = data.get("data") or []
        return results[0]["id"] if results else None

    def _first_url(self, path: str):
        try:
            data = self._get(path)
        except Exception:
            return None
        items = data.get("data") or []
        return items[0]["url"] if items else None

    def grid_url(self, gid):       # vertical library capsule 600x900
        return self._first_url(f"/grids/game/{gid}?dimensions=600x900")

    def hero_url(self, gid):
        return self._first_url(f"/heroes/game/{gid}")

    def logo_url(self, gid):
        return self._first_url(f"/logos/game/{gid}")


def _download(url: str, dest: str) -> bool:
    if not url:
        return False
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GameAggregator"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        with open(dest, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        print(f"    [SGDB] download failed: {e}")
        return False


def fetch_grid(game, appid: int, grid_dir: str, sgdb: "SteamGridDB") -> int:
    """
    Download grid/hero/logo art for one game into grid_dir. Returns count of
    files written. Skips any that already exist (so re-runs are cheap).
    """
    os.makedirs(grid_dir, exist_ok=True)
    appid_u = appid & 0xFFFFFFFF

    targets = {
        f"{appid_u}p.png":     None,  # vertical capsule
        f"{appid_u}_hero.png": None,
        f"{appid_u}_logo.png": None,
    }
    # Skip work if all already present.
    if all(os.path.exists(os.path.join(grid_dir, n)) for n in targets):
        return 0

    gid = sgdb.search_game_id(game.name)
    if not gid:
        return 0

    written = 0
    plan = {
        f"{appid_u}p.png":     sgdb.grid_url(gid),
        f"{appid_u}_hero.png": sgdb.hero_url(gid),
        f"{appid_u}_logo.png": sgdb.logo_url(gid),
    }
    for fname, url in plan.items():
        dest = os.path.join(grid_dir, fname)
        if os.path.exists(dest):
            continue
        if _download(url, dest):
            written += 1
    return written