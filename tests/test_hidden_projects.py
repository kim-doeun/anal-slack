import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analslack import db


def _seed_project(conn, customer, project, thread_ts="1000.0001"):
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
            created_ts=1000.0,
        ),
    )
    db.upsert_message(
        conn,
        db.MessageRow(
            ts=thread_ts,
            thread_ts=thread_ts,
            channel_id="C1",
            is_parent=True,
            user_id="U1",
            user_name="담당자",
            text=f"[{customer}-{project}]",
            created_ts=1000.0,
        ),
    )


def test_projects_are_not_hidden_by_default():
    conn = db.connect(":memory:")
    _seed_project(conn, "삼성전자", "ERP고도화")
    conn.commit()

    rows = list(db.list_projects(conn))
    assert rows[0]["hidden"] == 0


def test_set_project_hidden_true():
    conn = db.connect(":memory:")
    _seed_project(conn, "삼성전자", "ERP고도화")
    conn.commit()

    db.set_project_hidden(conn, "삼성전자", "ERP고도화", True)
    conn.commit()

    rows = list(db.list_projects(conn))
    assert rows[0]["hidden"] == 1


def test_unhide_reverts():
    conn = db.connect(":memory:")
    _seed_project(conn, "삼성전자", "ERP고도화")
    conn.commit()

    db.set_project_hidden(conn, "삼성전자", "ERP고도화", True)
    conn.commit()
    db.set_project_hidden(conn, "삼성전자", "ERP고도화", False)
    conn.commit()

    rows = list(db.list_projects(conn))
    assert rows[0]["hidden"] == 0


def test_hiding_twice_does_not_error():
    conn = db.connect(":memory:")
    _seed_project(conn, "삼성전자", "ERP고도화")
    conn.commit()

    db.set_project_hidden(conn, "삼성전자", "ERP고도화", True)
    db.set_project_hidden(conn, "삼성전자", "ERP고도화", True)
    conn.commit()

    rows = list(db.list_projects(conn))
    assert rows[0]["hidden"] == 1


def test_hidden_is_per_project_not_global():
    conn = db.connect(":memory:")
    _seed_project(conn, "삼성전자", "ERP고도화", thread_ts="1000.0001")
    _seed_project(conn, "LG전자", "AI챗봇", thread_ts="2000.0001")
    conn.commit()

    db.set_project_hidden(conn, "삼성전자", "ERP고도화", True)
    conn.commit()

    rows = {r["customer"]: r["hidden"] for r in db.list_projects(conn)}
    assert rows["삼성전자"] == 1
    assert rows["LG전자"] == 0
