from __future__ import annotations

import sqlite3
from typing import Optional

from . import db
from .parser import parse_title
from .slack_client import SlackChannelClient


def sync_channel(
    conn: sqlite3.Connection,
    slack: SlackChannelClient,
    channel_id: str,
    full_resync: bool = False,
) -> int:
    """채널의 스레드/메시지를 DB로 동기화한다.

    [고객사-프로젝트] 형식의 스레드(최초 메시지 기준)만 대상으로 하며,
    각 스레드의 최초 메시지 + 답글 전체를 저장한다.
    반환값: 새로 저장/갱신된 메시지 수.
    """
    oldest = None if full_resync else db.get_last_synced_ts(conn, channel_id)

    updated_count = 0
    max_ts_seen = oldest or 0.0

    for root in slack.iter_root_messages(channel_id, oldest=oldest):
        root_ts = float(root["ts"])
        max_ts_seen = max(max_ts_seen, root_ts)

        title = parse_title(root.get("text", ""))
        if not title.matched:
            # 사업 공유 스레드 형식이 아닌 일반 메시지는 취합 대상에서 제외
            continue

        permalink = slack.get_permalink(channel_id, root["ts"])
        db.upsert_thread(
            conn,
            db.ThreadRow(
                thread_ts=root["ts"],
                channel_id=channel_id,
                customer=title.customer,
                project=title.project,
                title_raw=title.raw_title,
                title_matched=title.matched,
                permalink=permalink,
                created_ts=root_ts,
            ),
        )

        for msg in slack.iter_thread_messages(channel_id, root["ts"]):
            msg_ts = float(msg["ts"])
            is_parent = msg["ts"] == root["ts"]
            user_id = msg.get("user")
            db.upsert_message(
                conn,
                db.MessageRow(
                    ts=msg["ts"],
                    thread_ts=root["ts"],
                    channel_id=channel_id,
                    is_parent=is_parent,
                    user_id=user_id,
                    user_name=slack.resolve_user_name(user_id),
                    text=msg.get("text", ""),
                    created_ts=msg_ts,
                ),
            )
            updated_count += 1

    if max_ts_seen:
        db.set_last_synced_ts(conn, channel_id, max_ts_seen)

    return updated_count
