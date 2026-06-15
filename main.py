#!/usr/bin/env python3
"""
GameAggregator — scans all game launchers and registers installed games as
non-Steam shortcuts so Steam becomes your single library.

Usage:
    python main.py                # normal run (uses config.toml)
    python main.py --dry-run      # scan + report only, write nothing
    python main.py --list         # just list what was found, grouped

Run with Steam CLOSED. Steam rewrites shortcuts.vdf on exit, so any changes
made while it's open are discarded.
"""

import os
import sys
import argparse

try:
    import tomllib  # Python 3.11+
    def load_toml(p):
        with open(p, "rb") as f:
            return tomllib.load(f)
except ModuleNotFoundError:
    import tomli  # pip install tomli  (for 3.10 and earlier)
    def load_toml(p):
        with open(p, "rb") as f:
            return tomli.load(f)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from scanners import gog, epic, ubisoft, ea, xbox, battlenet
from scanners.common import is_windows
from steam import shortcuts as sc


def steam_running():
    if not is_windows():
        return False
    try:
        import subprocess
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq steam.exe"],
            capture_output=True, text=True,
        )
        return "steam.exe" in out.stdout.lower()
    except Exception:
        return False


def run_scanners(cfg):
    L = cfg.get("launchers", {})
    P = cfg.get("paths", {})
    X = cfg.get("xbox", {})
    found = []

    def attempt(label, fn):
        try:
            games = fn()
            print(f"  {label:<11}: {len(games)} found")
            return games
        except Exception as e:
            print(f"  {label:<11}: ERROR {e}")
            return []

    print("Scanning launchers...")
    if L.get("gog", True):
        found += attempt("GOG", lambda: gog.scan(P.get("gog_db") or None))
    if L.get("epic", True):
        found += attempt("Epic", lambda: epic.scan(P.get("epic_manifests") or None))
    if L.get("ubisoft", True):
        found += attempt("Ubisoft", ubisoft.scan)
    if L.get("ea", True):
        found += attempt("EA", ea.scan)
    if L.get("xbox", True):
        found += attempt("Xbox", lambda: xbox.scan(include_all=X.get("include_all", False)))
    if L.get("battlenet", True):
        found += attempt("Battle.net",
                         lambda: battlenet.scan(P.get("battlenet_config") or None))
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    ap.add_argument("--list", action="store_true", help="list found games and exit")
    ap.add_argument("--config", default=os.path.join(HERE, "config.toml"))
    args = ap.parse_args()

    cfg = load_toml(args.config) if os.path.exists(args.config) else {}
    behaviour = cfg.get("behaviour", {})
    steam_cfg = cfg.get("steam", {})
    dry = args.dry_run or behaviour.get("dry_run", False)

    games = run_scanners(cfg)
    print(f"\nTotal games found: {len(games)}")

    if args.list:
        for g in sorted(games, key=lambda x: (x.launcher, x.name.lower())):
            print(f"  [{g.launcher}] {g.name}")
        return

    if not games:
        print("Nothing to import. Exiting.")
        return

    # Locate Steam
    steam_path = sc.find_steam_path(steam_cfg.get("path", ""))
    if not steam_path:
        print("ERROR: couldn't find Steam. Set steam.path in config.toml.")
        sys.exit(1)
    print(f"Steam: {steam_path}")

    if steam_cfg.get("require_steam_closed", True) and steam_running():
        print("ERROR: Steam is running. Close it first (it overwrites shortcuts on exit).")
        sys.exit(1)

    targets = sc.find_shortcuts_files(steam_path)
    if not targets:
        print("ERROR: no Steam user profiles found under userdata.")
        sys.exit(1)

    for uid, path in targets:
        existing = sc.load(path)
        merged, added, skipped = sc.merge(
            existing, games, default_tag=behaviour.get("tag_by_launcher", True)
        )
        print(f"\nUser {uid}: {added} new, {skipped} already present "
              f"({len(merged)} total shortcuts)")
        if dry:
            print("  [dry-run] not writing.")
            continue
        if behaviour.get("backup", True):
            b = sc.backup(path)
            if b:
                print(f"  backup: {b}")
        sc.save(path, merged)
        print(f"  written: {path}")

    if dry:
        print("\nDry run complete. No files changed.")
    else:
        print("\nDone. Restart Steam to see your imported games.")


if __name__ == "__main__":
    main()
