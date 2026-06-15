r"""
install_startup.py — register GameAggregator to run at Windows logon.

Creates a Scheduled Task (not a registry Run key) so we can add a short delay,
letting the launchers' background services settle before we scan. The task
runs main.py with pythonw (no console window).

Run once:   python install_startup.py
Remove:     python install_startup.py --uninstall

Requires Windows. Does nothing on other OSes.
"""

import os
import sys
import subprocess

TASK_NAME = "GameAggregator-Startup"
HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "main.py")


def pythonw_path():
    # Prefer pythonw.exe (no console flash) sitting next to python.exe
    exe = sys.executable
    cand = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return cand if os.path.exists(cand) else exe


def install(delay_minutes: int = 1):
    pyw = pythonw_path()
    # /SC ONLOGON with a delay so launcher services finish starting.
    cmd = [
        "schtasks", "/Create", "/TN", TASK_NAME,
        "/TR", f'"{pyw}" "{MAIN}"',
        "/SC", "ONLOGON",
        "/DELAY", f"0000:{delay_minutes:02d}",
        "/RL", "LIMITED",
        "/F",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0:
        print(f"Installed scheduled task '{TASK_NAME}'.")
        print(f"It will run at logon (after a {delay_minutes} min delay):")
        print(f"  {pyw} {MAIN}")
        print("\nTip: run 'python main.py --dry-run' now to verify it finds your games.")
    else:
        print("Failed to create task:")
        print(r.stderr or r.stdout)
        print("\nIf you see an access error, run this from an elevated terminal,")
        print("or use /RL LIMITED (already set) which usually avoids needing admin.")


def uninstall():
    r = subprocess.run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
                       capture_output=True, text=True)
    if r.returncode == 0:
        print(f"Removed scheduled task '{TASK_NAME}'.")
    else:
        print(r.stderr or r.stdout)


if __name__ == "__main__":
    if os.name != "nt":
        print("This installer only works on Windows.")
        sys.exit(0)
    if "--uninstall" in sys.argv:
        uninstall()
    else:
        install()
