from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Optional, Sequence

SCHEMA = """
CREATE TABLE IF NOT EXISTS threads (
    thread_ts   TEXT PRIMARY KEY,
    channel_id  TEXT NOT NULL,
    customer    TEXT NOT NULL,
    project     TEXT NOT NULL,
    title_raw   TEXT NOT NULL,
    title_matched INTEGER NOT NULL DEFAULT 0,
    permalink   TEXT,
    created_ts  REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_threads_project
    ON threads (customer, project);

CREATE TABLE IF NOT EXISTS messages (
    ts          TEXT PRIMARY KEY,
    thread_ts   TEXT NOT NULL,
    channel_id  TEXT NOT NULL,
    is_parent   INTEGER NOT NULL DEFAULT 0,
    user_id     TEXT,
    user_name   TEXT,
    text        TEXT,
    created_ts  REAL NOT NULL,
    FOREIGN KEY (thread_ts) REFERENCES threads (thread_ts)
);

CREATE INDEX IF NOT EXISTS idx_messages_thread
    ON messages (thread_ts);

CREATE INDEX IF NOT EXISTS idx_messages_created
    ON messages (created_ts);

CREATE TABLE IF NOT EXISTS sync_state (
    channel_id      TEXT PRIMARY KEY,
    last_synced_ts  REAL
);

-- 사용자 ID -> 이름 캐시. sync 시점(Slack API 접근 가능)에 채워두고,
-- weekly/history/serve처럼 Slack 토큰 없이 DB만 읽는 경로에서 메시지 본문의
-- <@U...> 멘션을 이름으로 치환하는 데 사용한다.
CREATE TABLE IF NOT EXISTS users (
    user_id  TEXT PRIMARY KEY,
    name     TEXT NOT NULL
);

-- 대시보드 "전체 사업 목록"에서 사용자가 숨김 처리한 사업(고객사-프로젝트).
-- 존재 = 숨김. sync/메시지 데이터에는 영향 없는 순수 화면 표시용 상태.
CREATE TABLE IF NOT EXISTS hidden_projects (
    customer  TEXT NOT NULL,
    project   TEXT NOT NULL,
    hidden_at REAL NOT NULL,
    PRIMARY KEY (customer, project)
);
"""


@dataclass(frozen=True)
class ThreadRow:
    thread_ts: str
    channel_id: str
    customer: str
    project: str
    title_raw: str
    title_matched: bool
    permalink: Optional[str]
    created_ts: float


@dataclass(frozen=True)
class MessageRow:
    ts: str
    thread_ts: str
    channel_id: str
    is_parent: bool
    user_id: Optional[str]
    user_name: Optional[str]
    text: str
    created_ts: float


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


@contextmanager
def open_db(db_path: str) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def upsert_thread(conn: sqlite3.Connection, thread: ThreadRow) -> None:
    conn.execute(
        """
        INSERT INTO threads
            (thread_ts, channel_id, customer, project, title_raw, title_matched, permalink, created_ts)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(thread_ts) DO UPDATE SET
            customer=excluded.customer,
            project=excluded.project,
            title_raw=excluded.title_raw,
            title_matched=excluded.title_matched,
            permalink=COALESCE(excluded.permalink, threads.permalink)
        """,
        (
            thread.thread_ts,
            thread.channel_id,
            thread.customer,
            thread.project,
            thread.title_raw,
            int(thread.title_matched),
            thread.permalink,
            thread.created_ts,
        ),
    )


def upsert_message(conn: sqlite3.Connection, message: MessageRow) -> None:
    conn.execute(
        """
        INSERT INTO messages
            (ts, thread_ts, channel_id, is_parent, user_id, user_name, text, created_ts)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ts) DO UPDATE SET
            user_name=excluded.user_name,
            text=excluded.text
        """,
        (
            message.ts,
            message.thread_ts,
            message.channel_id,
            int(message.is_parent),
            message.user_id,
            message.user_name,
            message.text,
            message.created_ts,
        ),
    )


def upsert_user(conn: sqlite3.Connection, user_id: str, name: str) -> None:
    conn.execute(
        """
        INSERT INTO users (user_id, name) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET name=excluded.name
        """,
        (user_id, name),
    )


def get_user_names(conn: sqlite3.Connection) -> "dict[str, str]":
    rows = conn.execute("SELECT user_id, name FROM users").fetchall()
    return {row["user_id"]: row["name"] for row in rows}


def get_last_synced_ts(conn: sqlite3.Connection, channel_id: str) -> Optional[float]:
    row = conn.execute(
        "SELECT last_synced_ts FROM sync_state WHERE channel_id = ?", (channel_id,)
    ).fetchone()
    return row["last_synced_ts"] if row else None


def set_last_synced_ts(conn: sqlite3.Connection, channel_id: str, ts: float) -> None:
    conn.execute(
        """
        INSERT INTO sync_state (channel_id, last_synced_ts)
        VALUES (?, ?)
        ON CONFLICT(channel_id) DO UPDATE SET last_synced_ts=excluded.last_synced_ts
        """,
        (channel_id, ts),
    )


def messages_in_range(
    conn: sqlite3.Connection, start_ts: float, end_ts: float
) -> Sequence[sqlite3.Row]:
    return conn.execute(
        """
        SELECT m.*, t.customer, t.project, t.title_raw, t.permalink
        FROM messages m
        JOIN threads t ON t.thread_ts = m.thread_ts
        WHERE m.created_ts >= ? AND m.created_ts < ?
        ORDER BY t.customer, t.project, m.created_ts
        """,
        (start_ts, end_ts),
    ).fetchall()


def messages_for_project(
    conn: sqlite3.Connection,
    customer: Optional[str] = None,
    project: Optional[str] = None,
) -> Sequence[sqlite3.Row]:
    query = """
        SELECT m.*, t.customer, t.project, t.title_raw, t.permalink
        FROM messages m
        JOIN threads t ON t.thread_ts = m.thread_ts
        WHERE 1=1
    """
    params: list[str] = []
    if customer:
        query += " AND t.customer = ?"
        params.append(customer)
    if project:
        query += " AND t.project = ?"
        params.append(project)
    query += " ORDER BY t.thread_ts, m.created_ts"
    return conn.execute(query, params).fetchall()


def list_projects(conn: sqlite3.Connection) -> Sequence[sqlite3.Row]:
    """사업(고객사-프로젝트) 목록. 담당자는 가장 먼저 생성된 스레드(재개된 경우

    포함, 최초 스레드 기준)를 연 사람 — 즉 그 스레드의 최초 메시지 작성자다.
    hidden(0/1)은 대시보드에서 사용자가 숨김 처리했는지 여부 (필터링은
    호출자가 한다 — 이 함수는 항상 전체를 반환).
    """
    return conn.execute(
        """
        WITH first_thread AS (
            SELECT customer, project, thread_ts,
                   ROW_NUMBER() OVER (
                       PARTITION BY customer, project ORDER BY created_ts ASC
                   ) AS rn
            FROM threads
        )
        SELECT t.customer, t.project,
               COUNT(DISTINCT t.thread_ts) AS thread_count,
               COUNT(m.ts) AS message_count,
               MIN(t.created_ts) AS first_ts,
               MAX(t.created_ts) AS last_ts,
               owner_msg.user_name AS owner_name,
               owner_msg.user_id AS owner_id,
               CASE WHEN hp.customer IS NOT NULL THEN 1 ELSE 0 END AS hidden
        FROM threads t
        LEFT JOIN messages m ON m.thread_ts = t.thread_ts
        LEFT JOIN first_thread ft
            ON ft.customer = t.customer AND ft.project = t.project AND ft.rn = 1
        LEFT JOIN messages owner_msg
            ON owner_msg.thread_ts = ft.thread_ts AND owner_msg.is_parent = 1
        LEFT JOIN hidden_projects hp
            ON hp.customer = t.customer AND hp.project = t.project
        GROUP BY t.customer, t.project
        ORDER BY last_ts DESC
        """
    ).fetchall()


def set_project_hidden(conn: sqlite3.Connection, customer: str, project: str, hidden: bool) -> None:
    if hidden:
        conn.execute(
            """
            INSERT INTO hidden_projects (customer, project, hidden_at)
            VALUES (?, ?, ?)
            ON CONFLICT(customer, project) DO NOTHING
            """,
            (customer, project, time.time()),
        )
    else:
        conn.execute(
            "DELETE FROM hidden_projects WHERE customer = ? AND project = ?",
            (customer, project),
        )


def count_messages_in_range(
    conn: sqlite3.Connection,
    start_ts: float,
    end_ts: float,
    customer: Optional[str] = None,
    project: Optional[str] = None,
) -> int:
    query = """
        SELECT COUNT(*) FROM messages m
        JOIN threads t ON t.thread_ts = m.thread_ts
        WHERE m.created_ts >= ? AND m.created_ts < ?
    """
    params: list = [start_ts, end_ts]
    if customer:
        query += " AND t.customer = ?"
        params.append(customer)
    if project:
        query += " AND t.project = ?"
        params.append(project)
    row = conn.execute(query, params).fetchone()
    return row[0] if row else 0
