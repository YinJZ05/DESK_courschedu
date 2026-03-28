from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QProgressBar, QVBoxLayout, QWidget

from models import CourseProgress


def _progress_color(rate: float) -> str:
    if rate < 40:
        return "#fb7185"
    if rate < 80:
        return "#fbbf24"
    return "#34d399"


class CourseItemWidget(QWidget):
    increment_requested = Signal(str)
    decrement_requested = Signal(str)

    def __init__(self, progress: CourseProgress, parent: QWidget | None = None):
        super().__init__(parent)
        self.progress = progress

        self.setObjectName("courseItem")
        self.setMinimumWidth(280)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 10, 12, 10)
        root_layout.setSpacing(8)

        self.name_label = QLabel(progress.course_name)
        self.name_label.setObjectName("courseTitle")
        root_layout.addWidget(self.name_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setFixedHeight(12)
        root_layout.addWidget(self.progress_bar)

        stats_layout = QHBoxLayout()
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(8)

        self.percent_label = QLabel()
        self.percent_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        stats_layout.addWidget(self.percent_label, 1)

        self.learned_label = QLabel()
        self.learned_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stats_layout.addWidget(self.learned_label, 1)

        self.total_label = QLabel()
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        stats_layout.addWidget(self.total_label, 1)

        root_layout.addLayout(stats_layout)

        self.setStyleSheet(
            """
            QWidget#courseItem {
                background-color: rgba(63, 73, 82, 175);
                border: 1px solid rgba(148, 163, 184, 45);
                border-radius: 12px;
            }
            QLabel#courseTitle {
                color: #ffffff;
                font-size: 15px;
                font-weight: 700;
            }
            QLabel {
                color: #9ca3af;
                font-size: 12px;
            }
            QProgressBar {
                background-color: rgba(31, 41, 55, 200);
                border: none;
                border-radius: 6px;
            }
            """
        )

        self.update_progress(progress)

    def update_progress(self, progress: CourseProgress) -> None:
        self.progress = progress
        self.name_label.setText(progress.course_name)

        bar_color = _progress_color(progress.completion_rate)
        self.progress_bar.setStyleSheet(
            f"""
            QProgressBar {{
                background-color: rgba(31, 41, 55, 200);
                border: none;
                border-radius: 6px;
            }}
            QProgressBar::chunk {{
                background-color: {bar_color};
                border-radius: 6px;
            }}
            """
        )

        display_rate = max(0.0, min(progress.completion_rate, 100.0))
        self.progress_bar.setValue(int(round(display_rate)))
        self.percent_label.setText(f"{display_rate:.1f}%")
        self.learned_label.setText(
            f"<span style='color:#9ca3af;'>已学:</span> "
            f"<span style='color:#60a5fa; font-weight:700;'>{progress.learned_manual}</span>"
        )
        self.total_label.setText(
            f"<span style='color:#9ca3af;'>总计:</span> "
            f"<span style='color:#fbbf24; font-weight:700;'>{progress.total_to_date}</span>"
        )

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(
            """
            QMenu {
                background-color: rgba(17, 24, 39, 235);
                color: #e5e7eb;
                border: 1px solid rgba(148, 163, 184, 60);
            }
            QMenu::item:selected {
                background-color: rgba(75, 85, 99, 220);
            }
            """
        )

        add_action = menu.addAction("进度 +1")
        sub_action = menu.addAction("进度 -1")
        selected = menu.exec(event.globalPos())

        if selected == add_action:
            self.increment_requested.emit(self.progress.course_name)
        elif selected == sub_action:
            self.decrement_requested.emit(self.progress.course_name)
