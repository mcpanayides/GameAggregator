r"""
Xbox / Microsoft Store (UWP) game scanner.

UWP games can't be launched by exe path — they're sandboxed. The only
reliable launch route is the AppUserModelID via:
  explorer.exe shell:AppsFolder\<AppUserModelID>

We enumerate installed packages with PowerShell (Get-AppxPackage) and
filter to ones that look like games. This is heuristic: Microsoft doesn't
flag "this is a game" cleanly, so we match against the Xbox/GamingApp
families and packages installed under the gaming WindowsApps roots.

Windows-only; returns [] elsewhere.
"""

import os
import json
import subprocess

from .common import Game, is_windows

# PowerShell: list packages with their family name and the app id from the
# manifest. We grab PackageFamilyName + the Applications Id to build the AUMID.
PS_SCRIPT = r"""
$ErrorActionPreference = 'SilentlyContinue'
$out = @()
Get-AppxPackage | ForEach-Object {
    $pkg = $_
    $manifest = Get-AppxPackageManifest $pkg
    if ($manifest) {
        $apps = $manifest.Package.Applications.Application
        foreach ($app in $apps) {
            if ($app.Id) {
                $out += [PSCustomObject]@{
                    Name   = $pkg.Name
                    Family = $pkg.PackageFamilyName
                    AppId  = $app.Id
                    Install= $pkg.InstallLocation
                }
            }
        }
    }
}
$out | ConvertTo-Json -Compress
"""

# Substrings that strongly suggest a game / are safe to skip (system apps).
SKIP_HINTS = (
    "Microsoft.Windows", "Microsoft.UI", "Microsoft.NET", "Microsoft.VCLibs",
    "Microsoft.Services", "Microsoft.Advertising", "Microsoft.Xbox" + "App",
    "windows.immersivecontrolpanel", "Microsoft.Store", "Microsoft.Edge",
    "Clipchamp", "Microsoft.Paint", "Microsoft.ScreenSketch",
)


def scan(include_all: bool = False):
    """
    include_all=False keeps only things that look game-ish (installed under a
    games WindowsApps folder, or not matching system app hints). Set True to
    dump everything and filter by hand.
    """
    if not is_windows():
        return []

    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", PS_SCRIPT],
            capture_output=True, text=True, timeout=120,
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
    if isinstance(data, dict):  # single result isn't wrapped in a list
        data = [data]

    games = []
    for entry in data:
        name = entry.get("Name", "")
        family = entry.get("Family", "")
        app_id = entry.get("AppId", "")
        install = entry.get("Install", "") or ""

        if not (family and app_id):
            continue
        if not include_all and any(h.lower() in name.lower() for h in SKIP_HINTS):
            continue
        # Heuristic: real games usually sit under a "WindowsApps" gaming root.
        looks_gamey = (
            include_all
            or "xboxgames" in install.lower()
            or "\\windowsapps\\" in install.lower()
        )
        if not looks_gamey:
            continue

        aumid = f"{family}!{app_id}"
        games.append(Game(
            name=name,
            launcher="Xbox",
            # Launch UWP via the apps folder shell path.
            launch_uri=f"shell:AppsFolder\\{aumid}",
            exe=f'"explorer.exe"',  # explorer resolves the shell: path
            install_dir=install,
            start_dir=f'"{install}"' if install else "",
        ))
    return games
