from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QGuiApplication, QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from autostart import build_start_command, set_autostart
from models import AppSettings, Course, CourseProgress
from parser import parse_schedule_summary
from progress_engine import build_course_progress
from settings import SettingsStore
from ui_course_item import CourseItemWidget


class SettingsDialog(QDialog):
    def __init__(
        self,
        course_names: list[str],
        hidden_courses: list[str],
        autostart_enabled: bool,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(360)

        hidden_set = set(hidden_courses)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        self.autostart_checkbox = QCheckBox("开机自启动")
        self.autostart_checkbox.setChecked(autostart_enabled)
        root.addWidget(self.autostart_checkbox)

        title = QLabel("课程显示开关")
        title.setStyleSheet("color:#e5e7eb; font-size:13px; font-weight:600;")
        root.addWidget(title)

        self.course_checkboxes: dict[str, QCheckBox] = {}
        for course_name in course_names:
            checkbox = QCheckBox(course_name)
            checkbox.setChecked(course_name not in hidden_set)
            checkbox.setStyleSheet("color:#d1d5db;")
            self.course_checkboxes[course_name] = checkbox
            root.addWidget(checkbox)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        root.addWidget(button_box)

        self.setStyleSheet(
            """
            QDialog {
                background-color: #2b3239;
                border-radius: 10px;
            }
            """
        )

    def selected_hidden_courses(self) -> list[str]:
        hidden: list[str] = []
        for course_name, checkbox in self.course_checkboxes.items():
            if not checkbox.isChecked():
                hidden.append(course_name)
        return hidden

    def selected_autostart_enabled(self) -> bool:
        return self.autostart_checkbox.isChecked()


class MainWindow(QWidget):
    def __init__(self, root_dir: Path):
        super().__init__()

        self.root_dir = root_dir
        self.schedule_path = self.root_dir / "schedule_summary.txt"
        self.settings_store = SettingsStore(self.root_dir)

        self.settings: AppSettings = self.settings_store.load_settings()
        self.learned_progress: dict[str, int] = self.settings_store.load_learned_progress()
        self.courses: list[Course] = parse_schedule_summary(self.schedule_path)
        self.course_progress: list[CourseProgress] = []

        self.setWindowTitle("DESK Course 学习进度助手")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowOpacity(0.92)
        self.setMinimumWidth(300)
        self.setMinimumHeight(440)

        compact_width = min(max(self.settings.window_width, 320), 380)
        compact_height = min(max(self.settings.window_height, 480), 620)
        self.resize(compact_width, compact_height)

        self._setup_ui()
        self.refresh_progress(force=True)
        QTimer.singleShot(0, self._move_to_bottom_right)

        self.date_check_timer = QTimer(self)
        self.date_check_timer.setInterval(60 * 1000)
        self.date_check_timer.timeout.connect(self.check_date_rollover)
        self.date_check_timer.start()

    def _setup_ui(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                color: #e5e7eb;
                font-family: "Segoe UI", "Microsoft YaHei";
            }
            QWidget#panelCard {
                background-color: rgba(59, 66, 74, 210);
                border: 1px solid rgba(148, 163, 184, 50);
                border-radius: 16px;
            }
            QPushButton {
                background-color: rgba(31, 41, 55, 220);
                color: #ffffff;
                border: none;
                border-radius: 10px;
                padding: 6px 10px;
            }
            QPushButton:hover {
                background-color: rgba(17, 24, 39, 240);
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(0)

        self.panel = QWidget()
        self.panel.setObjectName("panelCard")
        root.addWidget(self.panel)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 8)
        shadow.setColor(Qt.GlobalColor.black)
        self.panel.setGraphicsEffect(shadow)

        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(14, 14, 14, 14)
        panel_layout.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        title = QLabel("课程学习进度")
        title.setStyleSheet("color:#ffffff; font-size:18px; font-weight:700;")
        header.addWidget(title)

        header.addStretch(1)

        self.settings_button = QPushButton("⚙")
        self.settings_button.setFixedWidth(34)
        self.settings_button.clicked.connect(self.open_settings_dialog)
        header.addWidget(self.settings_button)

        panel_layout.addLayout(header)

        self.meta_label = QLabel()
        self.meta_label.setStyleSheet("color:#9ca3af; font-size:12px;")
        panel_layout.addWidget(self.meta_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setStyleSheet(
            """
            QScrollArea {
                background: transparent;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            QScrollBar:vertical {
                width: 8px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                border-radius: 4px;
                background: rgba(156, 163, 175, 120);
            }
            """
        )

        self.list_host = QWidget()
        self.list_layout = QVBoxLayout(self.list_host)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(10)
        self.scroll.setWidget(self.list_host)

        panel_layout.addWidget(self.scroll, 1)

    def refresh_progress(self, force: bool = False) -> None:
        today = date.today()
        if force or self.settings.last_refresh_date != today.isoformat():
            self.settings.last_refresh_date = today.isoformat()

        self.course_progress = build_course_progress(
            courses=self.courses,
            learned_progress=self.learned_progress,
            hidden_courses=self.settings.hidden_courses,
            today=today,
        )

        self._render_course_list()
        self.meta_label.setText(f"数据日期: {today.isoformat()} | 同名课程已自动合并")
        self._save_window_state()

    def _render_course_list(self) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        visible_items = [item for item in self.course_progress if item.visible]
        if not visible_items:
            empty_label = QLabel("当前没有可显示课程，请在设置中开启课程显示。")
            empty_label.setStyleSheet("color:#9ca3af; font-size:13px;")
            self.list_layout.addWidget(empty_label)
        else:
            for item in visible_items:
                row = CourseItemWidget(item)
                row.increment_requested.connect(self.on_increment_course)
                row.decrement_requested.connect(self.on_decrement_course)
                self.list_layout.addWidget(row)

        self.list_layout.addStretch(1)

    def on_increment_course(self, course_name: str) -> None:
        self._adjust_learned_progress(course_name, delta=1)

    def on_decrement_course(self, course_name: str) -> None:
        self._adjust_learned_progress(course_name, delta=-1)

    def _adjust_learned_progress(self, course_name: str, delta: int) -> None:
        current = int(self.learned_progress.get(course_name, 0))
        total_to_date = self._course_total_to_date(course_name)

        updated = max(0, min(current + delta, total_to_date))
        self.learned_progress[course_name] = updated
        self.settings_store.save_learned_progress(self.learned_progress)
        self.refresh_progress()

    def _course_total_to_date(self, course_name: str) -> int:
        today = date.today()
        for course in self.courses:
            if course.name == course_name:
                return sum(1 for d in course.dates if d <= today)
        return 0

    def open_settings_dialog(self) -> None:
        course_names = [course.name for course in self.courses]
        dialog = SettingsDialog(
            course_names=course_names,
            hidden_courses=self.settings.hidden_courses,
            autostart_enabled=self.settings.autostart_enabled,
            parent=self,
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self.settings.hidden_courses = dialog.selected_hidden_courses()

        requested_autostart = dialog.selected_autostart_enabled()
        if requested_autostart != self.settings.autostart_enabled:
            ok, message = set_autostart(requested_autostart, build_start_command())
            if ok:
                self.settings.autostart_enabled = requested_autostart
            else:
                QMessageBox.warning(self, "开机自启动", f"设置失败: {message}")

        self.refresh_progress()

    def check_date_rollover(self) -> None:
        if self.settings.last_refresh_date != date.today().isoformat():
            self.refresh_progress(force=True)

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            self.check_date_rollover()
        super().changeEvent(event)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._move_to_bottom_right)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._move_to_bottom_right()

    def _move_to_bottom_right(self) -> None:
        margin = 14
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return

        available = screen.availableGeometry()
        x = available.right() - self.width() - margin
        y = available.bottom() - self.height() - margin
        self.move(max(available.left() + margin, x), max(available.top() + margin, y))

    def _save_window_state(self) -> None:
        self.settings.window_width = max(self.width(), 320)
        self.settings.window_height = max(self.height(), 480)
        self.settings_store.save_settings(self.settings)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_window_state()
        super().closeEvent(event)
