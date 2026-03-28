from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication


def _ensure_app_dir_in_path() -> None:
    app_dir = Path(__file__).resolve().parent
    app_dir_str = str(app_dir)
    if app_dir_str not in sys.path:
        sys.path.insert(0, app_dir_str)


_ensure_app_dir_in_path()

from ui_main import MainWindow  # noqa: E402


def _get_runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _get_bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent.parent


def _resolve_schedule_path(runtime_root: Path, bundle_root: Path) -> Path:
    runtime_schedule = runtime_root / "schedule_summary.txt"
    if runtime_schedule.exists():
        return runtime_schedule
    return bundle_root / "schedule_summary.txt"


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("DESK Course 学习进度助手")

    runtime_root = _get_runtime_root()
    bundle_root = _get_bundle_root()
    schedule_path = _resolve_schedule_path(runtime_root, bundle_root)

    window = MainWindow(root_dir=runtime_root, schedule_path=schedule_path)
    if window.settings.start_minimized:
        window.start_to_tray_on_startup()
    else:
        window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
