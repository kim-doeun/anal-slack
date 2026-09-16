import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analslack import db
from analslack.config import Config
from analslack.web import create_app

TZ = ZoneInfo("Asia/Seoul")


def _seed_project(db_path, customer, project, thread_ts):
    conn = db.connect(db_path)
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
    conn.commit()
    conn.close()


def _make_client(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.connect(db_path).close()  # 스키마 초기화
    cfg = Config(slack_bot_token=None, channel="test", db_path=db_path, timezone=TZ)
    app = create_app(cfg)
    app.testing = True
    return app.test_client(), db_path


def test_index_excludes_hidden_by_default(tmp_path):
    client, db_path = _make_client(tmp_path)
    _seed_project(db_path, "삼성전자", "ERP고도화", "1000.0001")
    _seed_project(db_path, "LG전자", "AI챗봇", "2000.0001")

    conn = db.connect(db_path)
    db.set_project_hidden(conn, "삼성전자", "ERP고도화", True)
    conn.commit()
    conn.close()

    resp = client.get("/")
    body = resp.get_data(as_text=True)
    # 상단 Top 15 차트는 hide와 무관하게 전체 활동 기준으로 보여주므로,
    # "숨김" 대상 여부는 전체 사업 목록 표 구간만 떼어서 검증한다.
    table_section = body.split("전체 사업 목록", 1)[1]
    assert "LG전자" in table_section
    assert "삼성전자" not in table_section
    assert "숨김 1개 제외" in table_section


def test_hiding_a_project_does_not_affect_top15_chart(tmp_path):
    # 의도된 동작: hide는 "전체 사업 목록" 표 노출 여부만 제어하고,
    # 활동 랭킹(Top 15)/추이 차트는 숨김과 무관하게 전체 데이터를 반영한다.
    client, db_path = _make_client(tmp_path)
    _seed_project(db_path, "삼성전자", "ERP고도화", "1000.0001")

    conn = db.connect(db_path)
    db.set_project_hidden(conn, "삼성전자", "ERP고도화", True)
    conn.commit()
    conn.close()

    resp = client.get("/")
    body = resp.get_data(as_text=True)
    chart_section = body.split("사업별 메시지 수", 1)[1].split("전체 사업 목록", 1)[0]
    assert "삼성전자" in chart_section


def test_index_show_hidden_includes_everything(tmp_path):
    client, db_path = _make_client(tmp_path)
    _seed_project(db_path, "삼성전자", "ERP고도화", "1000.0001")
    _seed_project(db_path, "LG전자", "AI챗봇", "2000.0001")

    conn = db.connect(db_path)
    db.set_project_hidden(conn, "삼성전자", "ERP고도화", True)
    conn.commit()
    conn.close()

    resp = client.get("/?show_hidden=1")
    body = resp.get_data(as_text=True)
    assert "LG전자" in body
    assert "삼성전자" in body
    assert "row-hidden" in body


def test_toggle_hidden_route_hides_project(tmp_path):
    client, db_path = _make_client(tmp_path)
    _seed_project(db_path, "삼성전자", "ERP고도화", "1000.0001")

    resp = client.post(
        "/project/삼성전자/ERP고도화/hidden",
        data={"hidden": "on", "next": "/"},
    )
    assert resp.status_code == 302

    conn = db.connect(db_path)
    rows = list(db.list_projects(conn))
    assert rows[0]["hidden"] == 1


def test_toggle_hidden_route_unhides_when_unchecked(tmp_path):
    client, db_path = _make_client(tmp_path)
    _seed_project(db_path, "삼성전자", "ERP고도화", "1000.0001")

    conn = db.connect(db_path)
    db.set_project_hidden(conn, "삼성전자", "ERP고도화", True)
    conn.commit()
    conn.close()

    # 체크 해제 시 브라우저는 "hidden" 필드를 아예 보내지 않는다
    resp = client.post("/project/삼성전자/ERP고도화/hidden", data={"next": "/"})
    assert resp.status_code == 302

    conn = db.connect(db_path)
    rows = list(db.list_projects(conn))
    assert rows[0]["hidden"] == 0


def test_toggle_hidden_redirects_to_next(tmp_path):
    client, db_path = _make_client(tmp_path)
    _seed_project(db_path, "삼성전자", "ERP고도화", "1000.0001")

    resp = client.post(
        "/project/삼성전자/ERP고도화/hidden",
        data={"hidden": "on", "next": "/?show_hidden=1"},
    )
    assert resp.headers["Location"] == "/?show_hidden=1"


def test_no_hidden_link_shown_when_nothing_hidden(tmp_path):
    client, db_path = _make_client(tmp_path)
    _seed_project(db_path, "LG전자", "AI챗봇", "2000.0001")

    resp = client.get("/")
    body = resp.get_data(as_text=True)
    assert "숨김 항목 포함" not in body
