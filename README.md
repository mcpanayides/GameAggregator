# 🎮 GameAggregator

> One Steam library to rule them all.

![Platform](https://img.shields.io/badge/platform-Windows-0078D6?logo=windows&logoColor=white)
![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![Dependencies](https://img.shields.io/badge/dependencies-none-success)
![License](https://img.shields.io/badge/license-MIT-blue)

GameAggregator scans every game launcher on your PC — **GOG, Epic, Ubisoft, EA, Xbox, and Battle.net** — and registers every installed game into Steam as a non-Steam shortcut. The result: Steam becomes your single, unified game library, with each game tagged by its launcher so you can filter at a glance.

Run it once, or set it to run at every logon so newly installed games show up in Steam automatically.

---

## ✨ Features

- **Six launchers, one library** — GOG, Epic, Ubisoft, EA, Xbox, Battle.net
- **Smart launching** — shortcuts point at each game's launcher URI, so cloud saves, anti-cheat, and DRM keep working
- **Auto-tagged** — every imported game is categorised by launcher in Steam
- **Idempotent** — run it daily; already-imported games are skipped, never duplicated
- **Safe by default** — timestamped backup of `shortcuts.vdf` before every write; nothing is ever deleted
- **Run at startup** — optional scheduled task picks up new installs automatically
- **Zero dependencies** — pure Python standard library

---

## 📋 Requirements

- Windows
- Python 3.11+ *(for 3.10 and earlier: `pip install tomli`)*

---

## 🚀 Quick start

> [!IMPORTANT]
> **Close Steam completely before importing.** Steam rewrites `shortcuts.vdf` when it exits, so any changes made while it's running are discarded.

```bash
# 1. See what it finds — changes nothing
python main.py --dry-run

# 2. Happy with the counts? Do the real import
python main.py

# 3. Start Steam — your games are now in the library, tagged by launcher
```

### Run at startup

```bash
python install_startup.py             # register logon task (1-min delay)
python install_startup.py --uninstall # remove it
```

The startup task detects whether Steam is already running and skips the write if so — it won't clobber anything mid-session.

---

## ⚙️ Configuration

Everything lives in [`config.toml`](config.toml). Paths auto-detect, so you usually don't need to touch it. Edit it to:

| Want to... | Setting |
|---|---|
| Disable a launcher | `gog = false` under `[launchers]` |
| Fix a wrong path | the relevant key under `[paths]` |
| Always report-only | `dry_run = true` under `[behaviour]` |
| Catch missing Xbox games | `include_all = true` under `[xbox]` |

---

## 🔍 How it works

Each launcher stores its installed-games list differently. GameAggregator reads each one natively:

| Launcher | Source | Notes |
|---|---|---|
| **GOG** | `galaxy-2.0.db` (SQLite) | Requires GOG Galaxy |
| **Epic** | `*.item` JSON manifests | Very reliable |
| **Ubisoft** | Registry: `Ubisoft\Launcher\Installs` | Name derived from install folder |
| **EA** | Registry (Origin / EA Games keys) | Keys vary between EA app versions |
| **Xbox** | `Get-AppxPackage` (PowerShell) | Heuristic; flip `include_all` if needed |
| **Battle.net** | `Battle.net.config` (JSON) | Friendly names from a built-in code map |

It then builds a unified list, dedupes against what's already in Steam (by the same appid hash Steam itself uses), and writes the result into each Steam user's `shortcuts.vdf` — pointing every shortcut at the game's launcher deep-link so launching from Steam hands off to the correct launcher.

---

## 🩹 Troubleshooting

**A launcher found 0 games?**

1. Confirm that launcher actually has games installed.
2. Run `python main.py --list` for the per-launcher breakdown.
3. The expected path may differ on your setup — open an issue with where that launcher installed and it can be patched.

> EA and Xbox are the two finicky ones — EA shuffles its registry keys between versions, and Xbox UWP titles are sandboxed. If either comes up empty, that's the usual culprit.

---

## 🗂️ Project structure

```
GameAggregator/
├── main.py              # orchestrator: scan → dedupe → write
├── install_startup.py   # registers the logon scheduled task
├── config.toml          # all settings (paths auto-detect)
├── scanners/
│   ├── gog.py
│   ├── epic.py
│   ├── ubisoft.py
│   ├── ea.py
│   ├── xbox.py
│   ├── battlenet.py
│   └── common.py        # shared Game type + appid hashing
└── steam/
    ├── vdf.py           # binary shortcuts.vdf reader/writer
    └── shortcuts.py     # locate, back up, merge, save
```

---

## 🤝 Contributing

Contributions welcome — especially:

- Additional launchers (Amazon Games, itch.io, Rockstar…)
- Better game-name resolution for Ubisoft / EA
- Artwork fetching (Steam grid images) for imported shortcuts

Open an issue or PR. Keep it dependency-free where possible.

---

## ⚠️ Disclaimer

GameAggregator only **adds** non-Steam shortcuts and **backs up** your config before every write. It never deletes games or modifies your installations. Use at your own discretion; always keep the automatic backups until you're confident.

---

## 📄 License

Released under the [MIT License](LICENSE).
