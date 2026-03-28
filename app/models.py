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
class AppSettings:
    autostart_enabled: bool = False
    hidden_courses: list[str] = field(default_factory=list)
    window_width: int = 420
    window_height: int = 760
    last_refresh_date: str = ""
