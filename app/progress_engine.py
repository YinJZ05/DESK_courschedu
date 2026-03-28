from __future__ import annotations

from datetime import date

from models import Course, CourseProgress


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))


def build_course_progress(
    courses: list[Course],
    learned_progress: dict[str, int],
    hidden_courses: list[str],
    today: date | None = None,
) -> list[CourseProgress]:
    today = today or date.today()
    hidden_set = set(hidden_courses)

    results: list[CourseProgress] = []
    for course in courses:
        total_to_date = sum(1 for d in course.dates if d <= today)
        learned_manual = max(0, int(learned_progress.get(course.name, 0)))
        learned_for_rate = clamp(learned_manual, 0, total_to_date)

        completion_rate = 0.0
        if total_to_date > 0:
            completion_rate = (learned_for_rate / total_to_date) * 100.0

        results.append(
            CourseProgress(
                course_name=course.name,
                total_to_date=total_to_date,
                learned_manual=learned_manual,
                completion_rate=completion_rate,
                visible=course.name not in hidden_set,
            )
        )

    return results
