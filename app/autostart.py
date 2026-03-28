from __future__ import annotations

import os
import sys
from pathlib import Path

if os.name == "nt":
    import winreg


APP_NAME = "DESKCourseProgressAssistant"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def build_start_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    main_script = Path(__file__).resolve().parent / "main.py"
    return f'"{sys.executable}" "{main_script}"'


def is_autostart_enabled() -> bool:
    if os.name != "nt":
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(str(value).strip())
    except FileNotFoundError:
        return False
    except OSError:
        return False


def set_autostart(enabled: bool, command: str) -> tuple[bool, str]:
    if os.name != "nt":
        return False, "Autostart is only supported on Windows."

    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            if enabled:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
        return True, ""
    except OSError as exc:
        return False, str(exc)
