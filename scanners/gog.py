r"""
GOG Galaxy scanner.

GOG Galaxy keeps everything in a SQLite database:
  C:\ProgramData\GOG.com\Galaxy\storage\galaxy-2.0.db

We read installed builds + their play tasks (which contain the exe path).
If the DB isn't present or Galaxy isn't installed, returns [].
"""

import os
import sqlite3
import tempfile
import shutil

from .common import Game, env

DEFAULT_DB = os.path.join(
    env("PROGRAMDATA", r"C:\ProgramData"),
    "GOG.com", "Galaxy", "storage", "galaxy-2.0.db",
)


def scan(db_path: str = None):
    db_path = db_path or DEFAULT_DB
    if not os.path.exists(db_path):
        return []

    games = []
    # Copy the DB first — Galaxy may hold a lock on the live file.
    tmp = os.path.join(tempfile.gettempdir(), "gog_galaxy_copy.db")
    try:
        shutil.copy2(db_path, tmp)
        con = sqlite3.connect(tmp)
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        # InstalledBaseProducts gives installed productIds + install paths.
        # LimitedDetails holds the human title.
        cur.execute("""
            SELECT ibp.productId   AS pid,
                   ibp.installationPath AS path,
                   ld.title        AS title
            FROM InstalledBaseProducts ibp
            LEFT JOIN LimitedDetails ld ON ld.productId = ibp.productId
        """)
        for row in cur.fetchall():
            title = row["title"] or f"GOG {row['pid']}"
            install = row["path"] or ""
            games.append(Game(
                name=title,
                launcher="GOG",
                # Launch via Galaxy so cloud saves / overlay still work.
                launch_uri=f'"{_galaxy_exe()}" /command=runGame /gameId={row["pid"]}',
                install_dir=install,
                start_dir=f'"{install}"' if install else "",
            ))
        con.close()
    except sqlite3.Error as e:
        print(f"  [GOG] DB read error: {e}")
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    return games


def _galaxy_exe():
    candidates = [
        os.path.join(env("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
                     "GOG Galaxy", "GalaxyClient.exe"),
        os.path.join(env("PROGRAMFILES", r"C:\Program Files"),
                     "GOG Galaxy", "GalaxyClient.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0]  # best guess; user can fix in config
