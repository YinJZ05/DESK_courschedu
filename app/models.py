from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Course:
    name: str
    dates: list[date] = field(default_factory=list)
    total_sessions: int = 0


@dataclass
class CourseProgress:
    course_name: str
    total_to_date: int
    learned_manual: int
    completion_rate: float
    visible: bool

@dataclass
class TodoItem:
    id: int
    text: str
    completed: bool = False

@dataclass
class AppSettings:
    schedule_enabled: bool = True
    autostart_enabled: bool = False
    start_minimized: bool = False
    hidden_courses: list[str] = field(default_factory=list)
    window_width: int = 360
    window_height: int = 560
    last_refresh_date: str = ""
