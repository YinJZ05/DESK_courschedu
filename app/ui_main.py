from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QEvent, QPoint, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QCursor, QGuiApplication, QMouseEvent, QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStyle,
    QSystemTrayIcon,
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
        start_minimized: bool,
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

        self.start_minimized_checkbox = QCheckBox("启动时侧边吸附隐藏")
        self.start_minimized_checkbox.setChecked(start_minimized)
        root.addWidget(self.start_minimized_checkbox)

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

    def selected_start_minimized(self) -> bool:
        return self.start_minimized_checkbox.isChecked()


class MainWindow(QWidget):
    def __init__(self, root_dir: Path, bundle_dir: Path, schedule_path: Path):
        super().__init__()

        self.root_dir = root_dir
        self.bundle_dir = bundle_dir
        self.schedule_path = schedule_path
        self.import_script_name = "Export-IcsSchedule.ps1"
        self.settings_store = SettingsStore(self.root_dir)
        self.has_positioned_on_startup = False
        self._drag_active = False
        self._drag_offset = QPoint()
        self._resize_active = False
        self._resize_start_global = QPoint()
        self._resize_start_width = 0
        self._resize_start_height = 0
        self._dock_mode_active = False
        self._dock_hidden = False
        self._dock_side = "right"
        self._dock_peek_width = 12
        self._dock_anchor_y = 0
        self._dock_auto_hide_timer = QTimer(self)
        self._dock_auto_hide_timer.setSingleShot(True)
        self._dock_auto_hide_timer.setInterval(550)
        self._dock_auto_hide_timer.timeout.connect(self._hide_to_side)
        self._dock_reveal_watch_timer = QTimer(self)
        self._dock_reveal_watch_timer.setInterval(120)
        self._dock_reveal_watch_timer.timeout.connect(self._check_dock_reveal_trigger)
        self._dock_animation = QPropertyAnimation(self, b"pos", self)
        self._dock_animation.setDuration(230)
        self._dock_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._suppress_minimize_hook = False
        self.tray_icon: QSystemTrayIcon | None = None
        self.schedule_missing = False
        self.schedule_status_message = ""

        self.settings: AppSettings = self.settings_store.load_settings()
        self.learned_progress: dict[str, int] = self.settings_store.load_learned_progress()
        self.courses: list[Course] = []
        self.course_progress: list[CourseProgress] = []
        self._load_courses()

        self.setWindowTitle("DESK Course 学习进度助手")
        self.setWindowFlags(
            Qt.WindowType.Tool
            |
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowOpacity(0.88)
        self.setMinimumWidth(300)
        self.setMinimumHeight(440)

        compact_width = min(max(self.settings.window_width, 320), 380)
        compact_height = min(max(self.settings.window_height, 480), 620)
        self.resize(compact_width, compact_height)

        self._setup_ui()
        self._setup_system_tray()
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
                padding: 4px 8px;
                font-size: 11px;
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

        self.header_bar = QWidget()
        self.header_bar.setStyleSheet("background: transparent;")
        header = QHBoxLayout(self.header_bar)
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)

        self.title_label = QLabel("课程学习进度")
        self.title_label.setStyleSheet("color:#ffffff; font-size:15px; font-weight:700;")
        header.addWidget(self.title_label)

        header.addStretch(1)

        self.minimize_button = QPushButton("_")
        self.minimize_button.setFixedWidth(28)
        self.minimize_button.setToolTip("侧边吸附隐藏")
        self.minimize_button.clicked.connect(self.minimize_to_side_dock)
        header.addWidget(self.minimize_button)

        self.settings_button = QPushButton("⚙")
        self.settings_button.setFixedWidth(28)
        self.settings_button.clicked.connect(self.open_settings_dialog)
        header.addWidget(self.settings_button)

        self.close_button = QPushButton("X")
        self.close_button.setFixedWidth(28)
        self.close_button.clicked.connect(self.close)
        header.addWidget(self.close_button)

        panel_layout.addWidget(self.header_bar)
        self.header_bar.installEventFilter(self)
        self.title_label.installEventFilter(self)

        self.meta_label = QLabel()
        self.meta_label.setStyleSheet("color:#9ca3af; font-size:11px;")
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

        resize_row = QHBoxLayout()
        resize_row.setContentsMargins(0, 0, 2, 0)
        resize_row.addStretch(1)
        self.resize_handle = QLabel("◢")
        self.resize_handle.setStyleSheet("color:#9ca3af; font-size:12px; padding:0;")
        self.resize_handle.setFixedSize(16, 16)
        self.resize_handle.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.resize_handle.setToolTip("拖拽可缩放窗口")
        self.resize_handle.installEventFilter(self)
        resize_row.addWidget(self.resize_handle, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        panel_layout.addLayout(resize_row)

    def _setup_system_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        icon = self.windowIcon()
        if icon.isNull():
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)

        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setToolTip("DESK Course 学习进度助手")

        menu = QMenu()
        show_action = menu.addAction("显示主界面")
        dock_action = menu.addAction("侧边吸附隐藏")
        import_action = menu.addAction("导入课表")
        quit_action = menu.addAction("退出")

        show_action.triggered.connect(self.restore_from_tray)
        dock_action.triggered.connect(self.minimize_to_side_dock)
        import_action.triggered.connect(self.import_schedule_from_ics)
        quit_action.triggered.connect(QApplication.instance().quit)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def refresh_progress(self, force: bool = False) -> None:
        today = date.today()
        if force or self.settings.last_refresh_date != today.isoformat():
            self.settings.last_refresh_date = today.isoformat()

        if self.schedule_missing:
            self.course_progress = []
        else:
            self.course_progress = build_course_progress(
                courses=self.courses,
                learned_progress=self.learned_progress,
                hidden_courses=self.settings.hidden_courses,
                today=today,
            )

        self._render_course_list()
        if self.schedule_missing:
            self.meta_label.setText(self.schedule_status_message)
        else:
            self.meta_label.setText(f"数据日期: {today.isoformat()} | 同名课程已自动合并")
        self._save_window_state()

    def _render_course_list(self) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        visible_items = [item for item in self.course_progress if item.visible]
        if self.schedule_missing:
            empty_label = QLabel("未检测到课程表，请在托盘菜单中点击“导入课表”。")
            empty_label.setStyleSheet("color:#9ca3af; font-size:13px;")
            self.list_layout.addWidget(empty_label)
        elif not visible_items:
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

    def _schedule_candidate_paths(self) -> list[Path]:
        return [
            self.root_dir / "schedule_summary.txt",
            self.root_dir / "summary_schedule.txt",
            self.bundle_dir / "schedule_summary.txt",
            self.bundle_dir / "summary_schedule.txt",
        ]

    def _load_courses(self) -> bool:
        self.courses = []
        self.schedule_missing = False
        self.schedule_status_message = ""

        selected_path: Path | None = None
        for candidate in self._schedule_candidate_paths():
            if candidate.exists():
                selected_path = candidate
                break

        if selected_path is None:
            self.schedule_missing = True
            self.schedule_path = self.root_dir / "schedule_summary.txt"
            self.schedule_status_message = "未检测到课程表，请先导入 .ics 文件"
            return False

        self.schedule_path = selected_path
        try:
            self.courses = parse_schedule_summary(self.schedule_path)
            return True
        except Exception as exc:
            self.schedule_missing = True
            self.schedule_status_message = f"课程表读取失败: {exc}"
            return False

    def _find_runtime_ics_file(self) -> Path | None:
        preferred = [
            self.root_dir / "schedule.ics",
            self.root_dir / "schedule_ansi.ics",
        ]
        for candidate in preferred:
            if candidate.exists():
                return candidate

        ics_files = sorted(self.root_dir.glob("*.ics"), key=lambda p: p.name.lower())
        if not ics_files:
            return None
        return ics_files[0]

    def _resolve_import_script_path(self) -> Path | None:
        candidates = [
            self.root_dir / self.import_script_name,
            self.bundle_dir / self.import_script_name,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _run_import_script(self, ics_path: Path, output_path: Path) -> tuple[bool, str]:
        script_path = self._resolve_import_script_path()
        if script_path is None:
            return False, "未找到导入脚本 Export-IcsSchedule.ps1"

        command_args = [
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            "-IcsPath",
            str(ics_path),
            "-OutputPath",
            str(output_path),
        ]

        for shell_cmd in ("powershell", "pwsh"):
            try:
                result = subprocess.run(
                    [shell_cmd, *command_args],
                    cwd=str(self.root_dir),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="ignore",
                    check=False,
                )
            except FileNotFoundError:
                continue

            if result.returncode == 0:
                return True, ""

            message = (result.stderr or result.stdout).strip()
            if not message:
                message = f"脚本执行失败，退出码 {result.returncode}"
            return False, message

        return False, "未找到可用的 PowerShell 运行环境"

    def _sync_summary_alias(self) -> None:
        source = self.root_dir / "schedule_summary.txt"
        alias = self.root_dir / "summary_schedule.txt"
        if not source.exists():
            return
        try:
            alias.write_bytes(source.read_bytes())
        except OSError:
            return

    def import_schedule_from_ics(self) -> None:
        ics_path = self._find_runtime_ics_file()
        if ics_path is None:
            QMessageBox.information(self, "导入课表", "未在 exe 同目录检测到 .ics 文件。")
            return

        output_path = self.root_dir / "schedule_summary.txt"
        alias_path = self.root_dir / "summary_schedule.txt"
        has_existing_schedule = (not self.schedule_missing) or output_path.exists() or alias_path.exists()
        if has_existing_schedule:
            answer = QMessageBox.question(
                self,
                "导入课表",
                "检测到已有课程表，导入将覆盖旧数据。是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        ok, message = self._run_import_script(ics_path=ics_path, output_path=output_path)
        if not ok:
            QMessageBox.warning(self, "导入课表", f"导入失败: {message}")
            return

        self._sync_summary_alias()
        self._load_courses()
        self.refresh_progress(force=True)
        QMessageBox.information(self, "导入课表", "导入成功，课程数据已更新。")

    def open_settings_dialog(self) -> None:
        course_names = [course.name for course in self.courses]
        dialog = SettingsDialog(
            course_names=course_names,
            hidden_courses=self.settings.hidden_courses,
            autostart_enabled=self.settings.autostart_enabled,
            start_minimized=self.settings.start_minimized,
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

        self.settings.start_minimized = dialog.selected_start_minimized()

        self.refresh_progress()

    def check_date_rollover(self) -> None:
        if self.settings.last_refresh_date != date.today().isoformat():
            self.refresh_progress(force=True)

    def eventFilter(self, watched: object, event: QEvent) -> bool:
        if watched in (self.header_bar, self.title_label):
            if event.type() == QEvent.Type.MouseButtonPress and isinstance(event, QMouseEvent):
                if event.button() == Qt.MouseButton.LeftButton:
                    if self._dock_mode_active and not self._dock_hidden:
                        self._dock_mode_active = False
                        self._dock_reveal_watch_timer.stop()
                        self._dock_auto_hide_timer.stop()
                    self._drag_active = True
                    self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                    return True
            elif event.type() == QEvent.Type.MouseMove and isinstance(event, QMouseEvent):
                if self._drag_active and not self.isMinimized():
                    self.move(event.globalPosition().toPoint() - self._drag_offset)
                    return True
            elif event.type() == QEvent.Type.MouseButtonRelease and isinstance(event, QMouseEvent):
                if event.button() == Qt.MouseButton.LeftButton:
                    self._drag_active = False
                    return True

        if watched is self.resize_handle:
            if event.type() == QEvent.Type.MouseButtonPress and isinstance(event, QMouseEvent):
                if event.button() == Qt.MouseButton.LeftButton:
                    self._resize_active = True
                    self._resize_start_global = event.globalPosition().toPoint()
                    self._resize_start_width = self.width()
                    self._resize_start_height = self.height()
                    return True
            elif event.type() == QEvent.Type.MouseMove and isinstance(event, QMouseEvent):
                if self._resize_active and not self.isMinimized():
                    delta = event.globalPosition().toPoint() - self._resize_start_global
                    new_width = max(self.minimumWidth(), self._resize_start_width + delta.x())
                    new_height = max(self.minimumHeight(), self._resize_start_height + delta.y())
                    self.resize(new_width, new_height)
                    return True
            elif event.type() == QEvent.Type.MouseButtonRelease and isinstance(event, QMouseEvent):
                if event.button() == Qt.MouseButton.LeftButton:
                    self._resize_active = False
                    return True

        return super().eventFilter(watched, event)

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.WindowStateChange and self.isMinimized() and not self._suppress_minimize_hook:
            QTimer.singleShot(0, self.minimize_to_side_dock)
        if event.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            self.check_date_rollover()
        super().changeEvent(event)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if not self.has_positioned_on_startup:
            self.has_positioned_on_startup = True
            QTimer.singleShot(0, self._move_to_bottom_right)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)

    def enterEvent(self, event: QEvent) -> None:
        if self._dock_mode_active:
            self._dock_auto_hide_timer.stop()
            if self._dock_hidden:
                self._show_from_side()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        if self._dock_mode_active and not self._dock_hidden:
            self._dock_auto_hide_timer.start()
        super().leaveEvent(event)

    def minimize_to_tray(self) -> None:
        if self.tray_icon is None:
            self.showMinimized()
            return

        self._dock_mode_active = False
        self._dock_hidden = False
        self._dock_reveal_watch_timer.stop()
        self._dock_auto_hide_timer.stop()
        self._dock_animation.stop()

        self._suppress_minimize_hook = True
        self.setWindowState(Qt.WindowState.WindowNoState)
        self._suppress_minimize_hook = False
        self.hide()

    def restore_from_tray(self) -> None:
        self._dock_animation.stop()

        self._suppress_minimize_hook = True
        self.setWindowState(Qt.WindowState.WindowNoState)
        self._suppress_minimize_hook = False

        self.show()

        # If currently docked/hidden, reveal from side instead of jumping to normal mode.
        if self._dock_mode_active:
            self._dock_auto_hide_timer.stop()
            self._dock_reveal_watch_timer.stop()
            if self._dock_hidden:
                self.move(self._dock_hidden_pos())
            self._show_from_side()
        else:
            self._dock_hidden = False
            self._dock_reveal_watch_timer.stop()
            self._dock_auto_hide_timer.stop()

        self.raise_()
        self.activateWindow()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.restore_from_tray()

    def minimize_to_side_dock(self) -> None:
        self._suppress_minimize_hook = True
        self.setWindowState(Qt.WindowState.WindowNoState)
        self._suppress_minimize_hook = False

        self._dock_mode_active = True
        self._dock_side = self._choose_dock_side()
        self._dock_anchor_y = self.y()
        self.show()
        self._hide_to_side()

    def start_to_side_dock_on_startup(self) -> None:
        self.show()
        QTimer.singleShot(120, self.minimize_to_side_dock)

    def _available_geometry(self):
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return None
        return screen.availableGeometry()

    def _choose_dock_side(self) -> str:
        available = self._available_geometry()
        if available is None:
            return "right"

        window_geo = self.frameGeometry()
        left_gap = abs(window_geo.left() - available.left())
        right_gap = abs(available.right() - window_geo.right())
        return "left" if left_gap < right_gap else "right"

    def _clamped_dock_y(self, available) -> int:
        top = available.top() + 12
        bottom = available.bottom() - self.height() - 12
        return max(top, min(self._dock_anchor_y, bottom))

    def _dock_shown_pos(self) -> QPoint:
        available = self._available_geometry()
        if available is None:
            return self.pos()

        y = self._clamped_dock_y(available)
        if self._dock_side == "left":
            x = available.left()
        else:
            x = available.right() - self.width() + 1
        return QPoint(x, y)

    def _dock_hidden_pos(self) -> QPoint:
        available = self._available_geometry()
        if available is None:
            return self.pos()

        y = self._clamped_dock_y(available)
        if self._dock_side == "left":
            x = available.left() - self.width() + self._dock_peek_width
        else:
            x = available.right() - self._dock_peek_width + 1
        return QPoint(x, y)

    def _animate_to_pos(self, target: QPoint) -> None:
        self._dock_animation.stop()
        self._dock_animation.setStartValue(self.pos())
        self._dock_animation.setEndValue(target)
        self._dock_animation.start()

    def _hide_to_side(self) -> None:
        if not self._dock_mode_active:
            return

        self._dock_hidden = True
        self._animate_to_pos(self._dock_hidden_pos())
        self._dock_reveal_watch_timer.start()

    def _show_from_side(self) -> None:
        if not self._dock_mode_active:
            return

        self._dock_hidden = False
        self._dock_reveal_watch_timer.stop()
        self._animate_to_pos(self._dock_shown_pos())

    def _check_dock_reveal_trigger(self) -> None:
        if not self._dock_mode_active or not self._dock_hidden:
            return

        available = self._available_geometry()
        if available is None:
            return

        cursor = QCursor.pos()
        in_y_band = self.y() <= cursor.y() <= (self.y() + self.height())
        if not in_y_band:
            return

        if self._dock_side == "right":
            if cursor.x() >= available.right() - 1:
                self._show_from_side()
        else:
            if cursor.x() <= available.left() + 1:
                self._show_from_side()

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
        if self.tray_icon is not None:
            self.tray_icon.hide()
        super().closeEvent(event)
