from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path

from models import Course


COURSE_PATTERN = re.compile(r"^Course\s*:\s*(.+)$")
SESSIONS_PATTERN = re.compile(r"^Sessions\s*:\s*(\d+)$")


def _normalize_course_name(raw_name: str) -> str:
    return raw_name.strip()


def _read_text_auto_encoding(file_path: Path) -> str:
    raw = file_path.read_bytes()

    for encoding in ("utf-8-sig", "utf-8", "gbk", "cp936"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue

    return raw.decode("utf-8", errors="replace")


def parse_schedule_summary(file_path: Path) -> list[Course]:
    if not file_path.exists():
        raise FileNotFoundError(f"schedule file not found: {file_path}")

    lines = _read_text_auto_encoding(file_path).splitlines()

    aggregated: dict[str, dict[str, object]] = {}

    current_name: str | None = None
    current_sessions = 0
    current_dates: list[date] = []
    in_dates_section = False

    def flush_current() -> None:
        nonlocal current_name, current_sessions, current_dates
        if not current_name:
            return
        entry = aggregated.setdefault(
            current_name,
            {
                "dates": set(),
                "sessions_sum": 0,
            },
        )
        cast_dates: set[date] = entry["dates"]  # type: ignore[assignment]
        cast_dates.update(current_dates)
        entry["sessions_sum"] = int(entry["sessions_sum"]) + int(current_sessions)

    for line in lines:
        stripped = line.strip()

        course_match = COURSE_PATTERN.match(stripped)
        if course_match:
            flush_current()
            current_name = _normalize_course_name(course_match.group(1))
            current_sessions = 0
            current_dates = []
            in_dates_section = False
            continue

        if current_name is None:
            continue

        sessions_match = SESSIONS_PATTERN.match(stripped)
        if sessions_match:
            current_sessions = int(sessions_match.group(1))
            continue

        if stripped.startswith("Dates"):
            in_dates_section = True
            continue

        if in_dates_section and stripped.startswith("-"):
            candidate = stripped.lstrip("-").strip()
            first_token = candidate.split()[0] if candidate else ""
            try:
                current_dates.append(date.fromisoformat(first_token))
            except ValueError:
                logging.warning("Ignored invalid date token: %s", first_token)
            continue

        if in_dates_section and stripped and not stripped.startswith("-"):
            in_dates_section = False

    flush_current()

    courses: list[Course] = []
    for name, data in aggregated.items():
        dates = sorted(data["dates"])  # type: ignore[arg-type]
        sessions_sum = int(data["sessions_sum"])
        total_sessions = len(dates) if dates else sessions_sum
        courses.append(
            Course(
                name=name,
                dates=dates,
                total_sessions=total_sessions,
            )
        )

    return courses
