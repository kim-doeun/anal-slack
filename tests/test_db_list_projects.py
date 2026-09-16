import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analslack import db


def _thread_with_parent(conn, thread_ts, customer, project, created_ts, user_id, user_name):
    db.upsert_thread(
        conn,
        db.ThreadRow(
            thread_ts=thread_ts,
            channel_id="C1",
            customer=customer,
            project=project,
            title_raw=f"[{customer}-{project}]",
            title_matched=True,
            permalink=None,
            created_ts=created_ts,
        ),
    )
    db.upsert_message(
        conn,
        db.MessageRow(
            ts=thread_ts,
            thread_ts=thread_ts,
            channel_id="C1",
            is_parent=True,
            user_id=user_id,
            user_name=user_name,
            text=f"[{customer}-{project}]",
            created_ts=created_ts,
        ),
    )


def test_owner_is_creator_of_single_thread():
    conn = db.connect(":memory:")
    _thread_with_parent(conn, "1000.0001", "LG전자", "AI챗봇", 1000.0, "U_B", "B담당자")
    conn.commit()

    rows = {r["customer"] + "-" + r["project"]: r for r in db.list_projects(conn)}
    row = rows["LG전자-AI챗봇"]
    assert row["owner_name"] == "B담당자"
    assert row["owner_id"] == "U_B"


def test_owner_is_creator_of_earliest_thread_when_reopened():
    conn = db.connect(":memory:")
    _thread_with_parent(conn, "1000.0001", "삼성전자", "ERP고도화", 1000.0, "U_FIRST", "최초담당자")
    _thread_with_parent(conn, "2000.0001", "삼성전자", "ERP고도화", 2000.0, "U_SECOND", "나중사람")
    conn.commit()

    rows = {r["customer"] + "-" + r["project"]: r for r in db.list_projects(conn)}
    row = rows["삼성전자-ERP고도화"]
    assert row["owner_name"] == "최초담당자"
    assert row["owner_id"] == "U_FIRST"
    assert row["thread_count"] == 2


def test_owner_falls_back_to_id_when_name_unresolved():
    conn = db.connect(":memory:")
    _thread_with_parent(conn, "1000.0001", "카카오", "결제개선", 1000.0, "U_X", None)
    conn.commit()

    rows = {r["customer"] + "-" + r["project"]: r for r in db.list_projects(conn)}
    row = rows["카카오-결제개선"]
    assert row["owner_name"] is None
    assert row["owner_id"] == "U_X"
