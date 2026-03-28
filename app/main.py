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


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("DESK Course 学习进度助手")

    root_dir = Path(__file__).resolve().parent.parent
    window = MainWindow(root_dir=root_dir)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
