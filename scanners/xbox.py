r"""
Xbox / Microsoft Store (UWP) game scanner.

UWP games can't be launched by exe path — they're sandboxed. The only
reliable launch route is the AppUserModelID via:
  explorer.exe shell:AppsFolder\<AppUserModelID>

Identifying *which* UWP packages are games is the hard part: Windows ships
hundreds of system packages that all live under WindowsApps, so a blocklist
can never keep up. Instead we use an ALLOWLIST of positive game signals:

  1. The package installs under the Xbox games library root
     (default C:\XboxGames, or any drive's XboxGames / "Xbox Games" folder).
  2. The package signature kind is "Store" AND it is NOT published by
     Microsoft's system identity (system apps are signed differently and
     overwhelmingly sit in C:\Windows\SystemApps or %ProgramFiles%\WindowsApps
     with a Microsoft.* family).
  3. The manifest declares a hardware dependency / full-trust game runtime
     (gaming packages depend on Microsoft.GamingServices or the
     Microsoft.DirectX framework and carry an "xbox" app execution alias).

A package must hit signal (1), OR signal (2)+(3) together, to be treated as
a game. Everything else is dropped. include_all=True bypasses all filtering
for debugging.

Windows-only; returns [] elsewhere.
"""

import os
import json
import subprocess

from .common import Game, is_windows, env

# PowerShell: emit one row per launchable application with the fields we need
# to decide whether it's a game and how to launch it.
PS_SCRIPT = r"""
$ErrorActionPreference = 'SilentlyContinue'
$out = @()
Get-AppxPackage | Where-Object { -not $_.IsFramework -and -not $_.IsResourcePackage } | ForEach-Object {
    $pkg = $_
    $manifest = Get-AppxPackageManifest $pkg
    if ($manifest) {
        # Collect declared dependencies (framework package names).
        $deps = @()
        if ($manifest.Package.Dependencies.PackageDependency) {
            $deps = @($manifest.Package.Dependencies.PackageDependency | ForEach-Object { $_.Name })
        }
        $apps = $manifest.Package.Applications.Application
        foreach ($app in $apps) {
            if ($app.Id) {
                $cats = ''
                if ($app.VisualElements -and $app.VisualElements.AppListEntry) {
                    $cats = [string]$app.VisualElements.AppListEntry
                }
                $out += [PSCustomObject]@{
                    Name      = $pkg.Name
                    Family    = $pkg.PackageFamilyName
                    Publisher = $pkg.Publisher
                    SignatureKind = [string]$pkg.SignatureKind
                    AppId     = $app.Id
                    Install   = $pkg.InstallLocation
                    Deps      = ($deps -join ';')
                }
            }
        }
    }
}
$out | ConvertTo-Json -Compress
"""

# Framework dependencies that real Xbox/Game Pass games pull in.
GAME_DEP_HINTS = (
    "microsoft.gamingservices",
    "microsoft.directx",
    "microsoft.vclibs",   # weak on its own; only counts alongside others
)

# Microsoft's system-app publisher identity. System packages are signed under
# this CN. Real third-party (and most Game Pass) titles are not.
MS_SYSTEM_PUBLISHER = "cn=microsoft corporation, o=microsoft corporation"


def _xbox_library_roots():
    """Known Xbox games-library roots across all drives."""
    roots = []
    # Default + any per-drive XboxGames folder the user may have set.
    for drive in "CDEFGHIJ":
        for folder in ("XboxGames", "Xbox Games"):
            p = f"{drive}:\\{folder}"
            roots.append(p.lower())
    return roots


def _under_xbox_library(install: str, roots) -> bool:
    il = (install or "").lower()
    return any(il.startswith(r) for r in roots)


def _looks_like_game(entry, roots) -> bool:
    install = entry.get("Install", "") or ""
    publisher = (entry.get("Publisher", "") or "").lower()
    sig = (entry.get("SignatureKind", "") or "").lower()
    deps = (entry.get("Deps", "") or "").lower()
    name = (entry.get("Name", "") or "").lower()

    # Signal 1: lives in the Xbox games library — strongest signal, accept.
    if _under_xbox_library(install, roots):
        return True

    # Never accept anything installed under the Windows dir or system apps.
    il = install.lower()
    if "\\windows\\systemapps" in il or il.startswith(os.environ.get("WINDIR", "c:\\windows").lower()):
        return False

    # Signal 2: not a Microsoft system-signed package.
    is_system = (sig == "system") or (publisher == MS_SYSTEM_PUBLISHER and "gamingapp" not in name)
    if is_system:
        return False

    # Signal 3: declares a gaming framework dependency.
    dep_hits = sum(1 for h in GAME_DEP_HINTS if h in deps)
    has_gaming_services = "microsoft.gamingservices" in deps or "microsoft.directx" in deps

    # Accept store-signed, non-system packages that pull in gaming frameworks.
    if sig == "store" and (has_gaming_services or dep_hits >= 2):
        return True

    return False


def scan(include_all: bool = False):
    if not is_windows():
        return []

    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", PS_SCRIPT],
            capture_output=True, text=True, timeout=180,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"  [Xbox] PowerShell call failed: {e}")
        return []

    raw = (proc.stdout or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        data = [data]

    roots = _xbox_library_roots()
    games = []
    seen = set()
    for entry in data:
        family = entry.get("Family", "")
        app_id = entry.get("AppId", "")
        if not (family and app_id):
            continue

        if not include_all and not _looks_like_game(entry, roots):
            continue

        aumid = f"{family}!{app_id}"
        if aumid in seen:
            continue
        seen.add(aumid)

        install = entry.get("Install", "") or ""
        # Prefer a clean display name: use the install folder if it's an Xbox
        # library game (folder names there are human-readable), else the family.
        name = entry.get("Name", "")
        if _under_xbox_library(install, roots) and install:
            folder = os.path.basename(os.path.normpath(install))
            if folder:
                name = folder

        games.append(Game(
            name=name,
            launcher="Xbox",
            launch_uri=f"shell:AppsFolder\\{aumid}",
            exe='"explorer.exe"',
            install_dir=install,
            start_dir=f'"{install}"' if install else "",
        ))
    return games
