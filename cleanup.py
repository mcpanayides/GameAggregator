#!/usr/bin/env python3
r"""
cleanup.py — remove junk shortcuts a previous (too-loose) import added.

Targets the UWP system packages that the old Xbox scanner wrongly imported:
anything whose launch target is a `shell:AppsFolder\Microsoft.<system>` AUMID
matching a known-junk pattern. Only touches shortcuts that look like our own
imports; leaves everything else (real games, your manual shortcuts) alone.

Usage:
    python cleanup.py --dry-run     # show what WOULD be removed (default-safe)
    python cleanup.py               # actually remove (after a backup)

Always backs up shortcuts.vdf first. Run with Steam CLOSED.
"""

import os
import sys
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from steam import shortcuts as sc

# Substrings in the Exe / AppName that mark a shortcut as system junk.
# These are the UWP system packages the old scanner swept in.
JUNK_MARKERS = (
    "microsoft.desktopappinstaller",
    "microsoft.gamingapp",
    "microsoft.gamingservices",
    "microsoft.windows",
    "microsoft.ui",
    "microsoft.net",
    "microsoft.vclibs",
    "microsoft.services",
    "microsoft.advertising",
    "microsoft.store",
    "microsoft.edge",
    "microsoft.microsoftedge",
    "microsoft.mspaint",
    "microsoft.paint",
    "microsoft.screensketch",
    "microsoft.onedrivesync",
    "microsoft.office",
    "microsoft.powertoys",
    "microsoft.mixedreality",
    "microsoft.languageexperiencepack",
    "microsoft.hevcvideoextension",
    "microsoft.heifimageextension",
    "microsoft.rawimageextension",
    "microsoft.mpeg2videoextension",
    "microsoft.webpimageextension",
    "microsoft.vp9videoextensions",
    "microsoft.sechealthui",
    "microsoft.ink.handwriting",
    "microsoft.limitless",
    "microsoft.windowssubsystemforlinux",
    "microsoft.microsoftofficehub",
    "microsoft.microsoftfamily",
    "microsoft.winappruntime",
    "windows.immersivecontrolpanel",
    "clipchamp",
)


def is_junk(entry) -> bool:
    hay = (str(entry.get("Exe", "")) + " " + str(entry.get("AppName", ""))).lower()
    # Only consider shortcuts that launch via the UWP apps folder — that's
    # what our Xbox importer produced. Real game shortcuts won't match this.
    if "shell:appsfolder" not in hay and "appsfolder" not in hay:
        # Also catch ones where AppName alone is a known system package.
        return any(m in hay for m in JUNK_MARKERS) and "microsoft." in hay
    return any(m in hay for m in JUNK_MARKERS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="list what would be removed, change nothing")
    ap.add_argument("--config", default=os.path.join(HERE, "config.toml"))
    args = ap.parse_args()

    steam_path = sc.find_steam_path("")
    if not steam_path:
        print("ERROR: couldn't find Steam.")
        sys.exit(1)

    targets = sc.find_shortcuts_files(steam_path)
    if not targets:
        print("No Steam user profiles found.")
        return

    total_removed = 0
    for uid, path in targets:
        existing = sc.load(path)
        if not existing:
            continue
        keep, junk = [], []
        for e in existing:
            (junk if is_junk(e) else keep).append(e)

        print(f"\nUser {uid}: {len(existing)} shortcuts, {len(junk)} junk found")
        for j in junk:
            print(f"   - {j.get('AppName','?')}")

        if not junk:
            continue
        if args.dry_run:
            print("   [dry-run] nothing removed.")
            continue

        b = sc.backup(path)
        if b:
            print(f"   backup: {b}")
        sc.save(path, keep)
        print(f"   removed {len(junk)}, kept {len(keep)}")
        total_removed += len(junk)

    if args.dry_run:
        print("\nDry run — no changes made. Re-run without --dry-run to apply.")
    else:
        print(f"\nDone. Removed {total_removed} junk shortcuts. Restart Steam.")


if __name__ == "__main__":
    main()
