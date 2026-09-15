import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analslack import db
from analslack.sync import sync_channel


class FakeSlackClient:
    """실제 Slack API 호출 없이 sync_channel의 oldest 파라미터 전달만 검증하는 더블."""

    def __init__(self):
        self.requested_oldest = "not-called"

    def iter_root_messages(self, channel_id, oldest=None):
        self.requested_oldest = oldest
        return iter(())  # 메시지 내용 자체는 이 테스트의 관심사가 아님

    def iter_thread_messages(self, channel_id, thread_ts):
        return iter(())

    def get_permalink(self, channel_id, ts):
        return None

    def resolve_user_name(self, user_id):
        return None


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
