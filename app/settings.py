from __future__ import annotations

import json
from pathlib import Path

from models import AppSettings


class SettingsStore:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.data_dir = self.root_dir / "data"
        self.settings_path = self.data_dir / "settings.json"
        self.learned_progress_path = self.data_dir / "learned_progress.json"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def load_settings(self) -> AppSettings:
        if not self.settings_path.exists():
            return AppSettings()

        try:
            payload = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return AppSettings()

        hidden_courses_raw = payload.get("hidden_courses", [])
        hidden_courses = [str(x) for x in hidden_courses_raw] if isinstance(hidden_courses_raw, list) else []

        return AppSettings(
            autostart_enabled=bool(payload.get("autostart_enabled", False)),
            start_minimized=bool(payload.get("start_minimized", False)),
            hidden_courses=hidden_courses,
            window_width=int(payload.get("window_width", 360)),
            window_height=int(payload.get("window_height", 560)),
            last_refresh_date=str(payload.get("last_refresh_date", "")),
        )

    def save_settings(self, settings: AppSettings) -> None:
        payload = {
            "autostart_enabled": settings.autostart_enabled,
            "start_minimized": settings.start_minimized,
            "hidden_courses": settings.hidden_courses,
            "window_width": settings.window_width,
            "window_height": settings.window_height,
            "last_refresh_date": settings.last_refresh_date,
        }
        self.settings_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_learned_progress(self) -> dict[str, int]:
        if not self.learned_progress_path.exists():
            return {}

        try:
            payload = json.loads(self.learned_progress_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

        if not isinstance(payload, dict):
            return {}

        learned: dict[str, int] = {}
        for name, value in payload.items():
            try:
                learned[str(name)] = max(0, int(value))
            except (TypeError, ValueError):
                continue
        return learned

    def save_learned_progress(self, learned_progress: dict[str, int]) -> None:
        normalized = {str(k): max(0, int(v)) for k, v in learned_progress.items()}
        self.learned_progress_path.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
