import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analslack import db
from analslack.sync import sync_channel


class FakeSlackClient:
    """실제 Slack API 호출 없이 sync_channel의 oldest 파라미터 전달만 검증하는 더블."""

    def __init__(self, root_messages=None, thread_messages=None, user_names=None):
        self.requested_oldest = "not-called"
        self._root_messages = root_messages or []
        self._thread_messages = thread_messages or {}
        self._user_names = user_names or {}

    def iter_root_messages(self, channel_id, oldest=None):
        self.requested_oldest = oldest
        return iter(self._root_messages)

    def iter_thread_messages(self, channel_id, thread_ts):
        return iter(self._thread_messages.get(thread_ts, []))

    def get_permalink(self, channel_id, ts):
        return None

    def resolve_user_name(self, user_id):
        return self._user_names.get(user_id)


def test_since_ts_overrides_stored_watermark():
    conn = db.connect(":memory:")
    db.set_last_synced_ts(conn, "C1", 5000.0)
    conn.commit()

    slack = FakeSlackClient()
    sync_channel(conn, slack, "C1", since_ts=1700000000.0)

    assert slack.requested_oldest == 1700000000.0


def test_since_ts_overrides_full_resync_flag():
    conn = db.connect(":memory:")
    slack = FakeSlackClient()

    sync_channel(conn, slack, "C1", full_resync=True, since_ts=1700000000.0)

    assert slack.requested_oldest == 1700000000.0


def test_no_since_ts_uses_stored_watermark():
    conn = db.connect(":memory:")
    db.set_last_synced_ts(conn, "C1", 5000.0)
    conn.commit()

    slack = FakeSlackClient()
    sync_channel(conn, slack, "C1")

    assert slack.requested_oldest == 5000.0


def test_no_since_ts_and_no_watermark_fetches_from_beginning():
    conn = db.connect(":memory:")
    slack = FakeSlackClient()

    sync_channel(conn, slack, "C1")

    assert slack.requested_oldest is None


def test_full_resync_without_since_ignores_watermark():
    conn = db.connect(":memory:")
    db.set_last_synced_ts(conn, "C1", 5000.0)
    conn.commit()

    slack = FakeSlackClient()
    sync_channel(conn, slack, "C1", full_resync=True)

    assert slack.requested_oldest is None


def test_sync_caches_author_and_mentioned_users_into_db():
    # 실제 Slack 사용자 ID 형식(U로 시작, 대문자/숫자)을 따라야 멘션 정규식에 매칭된다.
    root = {"ts": "1700000001.000001", "text": "[삼성전자-ERP고도화] 킥오프"}
    reply = {
        "ts": "1700000002.000001",
        "user": "UAUTHOR001",
        "text": "<@UMENTION02> 님 확인 부탁드립니다",
    }
    slack = FakeSlackClient(
        root_messages=[root],
        thread_messages={root["ts"]: [root, reply]},
        user_names={"UAUTHOR001": "작성자", "UMENTION02": "멘션대상"},
    )

    conn = db.connect(":memory:")
    sync_channel(conn, slack, "C1")
    conn.commit()

    user_names = db.get_user_names(conn)
    assert user_names["UAUTHOR001"] == "작성자"
    assert user_names["UMENTION02"] == "멘션대상"


def test_sync_skips_caching_when_name_unresolved():
    root = {"ts": "1700000001.000001", "text": "[삼성전자-ERP고도화] 킥오프"}
    slack = FakeSlackClient(
        root_messages=[root],
        thread_messages={root["ts"]: [root]},
        user_names={},  # resolve_user_name이 None을 반환하는 경우
    )

    conn = db.connect(":memory:")
    sync_channel(conn, slack, "C1")
    conn.commit()

    assert db.get_user_names(conn) == {}
