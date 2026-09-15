from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from . import db
from .mentions import resolve_mentions


def week_bounds(anchor: date, tz: ZoneInfo) -> tuple[float, float, date, date]:
    """anchor 날짜가 속한 주(월~일)의 [시작, 끝) epoch 초 범위를 반환한다."""
    monday = anchor - timedelta(days=anchor.weekday())
    next_monday = monday + timedelta(days=7)
    start = datetime(monday.year, monday.month, monday.day, tzinfo=tz)
    end = datetime(next_monday.year, next_monday.month, next_monday.day, tzinfo=tz)
    sunday = next_monday - timedelta(days=1)
    return start.timestamp(), end.timestamp(), monday, sunday


@dataclass(frozen=True)
class WeekPoint:
    week_start: date
    week_end: date
    count: int


def weekly_activity_series(
    conn: sqlite3.Connection,
    tz: ZoneInfo,
    weeks: int = 12,
    customer: Optional[str] = None,
    project: Optional[str] = None,
    anchor: Optional[date] = None,
) -> "list[WeekPoint]":
    """최근 N주(오늘이 속한 주 포함)의 주별 메시지 건수 추이를 반환한다.

    activity 없는 주도 0건으로 포함해 연속된 시계열을 만든다.
    customer/project를 지정하면 해당 사업으로 범위를 좁힌다.
    """
    anchor = anchor or date.today()
    points: list[WeekPoint] = []
    for i in range(weeks - 1, -1, -1):
        week_anchor = anchor - timedelta(weeks=i)
        start_ts, end_ts, monday, sunday = week_bounds(week_anchor, tz)
        count = db.count_messages_in_range(
            conn, start_ts, end_ts, customer=customer, project=project
        )
        points.append(WeekPoint(week_start=monday, week_end=sunday, count=count))
    return points


def _fmt_ts(ts: float, tz: ZoneInfo) -> str:
    return datetime.fromtimestamp(ts, tz=tz).strftime("%m/%d %H:%M")


def _snippet(text: str, limit: int = 300) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


@dataclass
class WeeklyReport:
    week_start: date
    week_end: date
    projects: "dict[str, list[sqlite3.Row]]"  # key: "고객사-프로젝트"

    def to_markdown(self, tz: ZoneInfo, user_names: "Optional[dict[str, str]]" = None) -> str:
        user_names = user_names or {}
        lines = [
            f"# 주간 공유 취합 ({self.week_start.isoformat()} ~ {self.week_end.isoformat()})",
            "",
        ]
        if not self.projects:
            lines.append("_이번 주 공유된 내용이 없습니다._")
            return "\n".join(lines)

        for project_key, rows in self.projects.items():
            lines.append(f"## {project_key}")
            permalink = next((r["permalink"] for r in rows if r["permalink"]), None)
            if permalink:
                lines.append(f"스레드: {permalink}")
            lines.append("")
            for row in rows:
                who = row["user_name"] or row["user_id"] or "unknown"
                when = _fmt_ts(row["created_ts"], tz)
                text = resolve_mentions(row["text"], user_names)
                lines.append(f"- `{when}` **{who}**: {_snippet(text)}")
            lines.append("")
        return "\n".join(lines)


def build_weekly_report(
    conn: sqlite3.Connection, anchor: date, tz: ZoneInfo
) -> WeeklyReport:
    start_ts, end_ts, monday, sunday = week_bounds(anchor, tz)
    rows = db.messages_in_range(conn, start_ts, end_ts)

    projects: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        key = f"{row['customer']}-{row['project']}"
        projects[key].append(row)

    return WeeklyReport(week_start=monday, week_end=sunday, projects=dict(projects))


@dataclass
class ProjectHistory:
    customer: Optional[str]
    project: Optional[str]
    rows: "list[sqlite3.Row]"

    def to_markdown(self, tz: ZoneInfo, user_names: "Optional[dict[str, str]]" = None) -> str:
        user_names = user_names or {}
        title = self.project or self.customer or "전체"
        lines = [f"# 사업 이력: {title}", ""]
        if not self.rows:
            lines.append("_이력이 없습니다._")
            return "\n".join(lines)

        current_thread: Optional[str] = None
        for row in self.rows:
            if row["thread_ts"] != current_thread:
                current_thread = row["thread_ts"]
                lines.append(f"## {row['customer']}-{row['project']} ({row['title_raw']})")
                if row["permalink"]:
                    lines.append(f"스레드: {row['permalink']}")
                lines.append("")
            who = row["user_name"] or row["user_id"] or "unknown"
            when = _fmt_ts(row["created_ts"], tz)
            marker = "📌" if row["is_parent"] else "-"
            text = resolve_mentions(row["text"], user_names)
            lines.append(f"{marker} `{when}` **{who}**: {_snippet(text, limit=1000)}")
        lines.append("")
        return "\n".join(lines)


def build_project_history(
    conn: sqlite3.Connection,
    customer: Optional[str] = None,
    project: Optional[str] = None,
) -> ProjectHistory:
    rows = db.messages_for_project(conn, customer=customer, project=project)
    return ProjectHistory(customer=customer, project=project, rows=list(rows))
