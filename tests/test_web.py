import sys
from datetime import datetime
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
    assert 'id="hidden-count-a">1<' in table_section


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
        "/project/hidden?customer=삼성전자&project=ERP고도화",
        data={"hidden": "on"},
    )
    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True, "hidden": True}

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
    resp = client.post("/project/hidden?customer=삼성전자&project=ERP고도화", data={})
    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True, "hidden": False}

    conn = db.connect(db_path)
    rows = list(db.list_projects(conn))
    assert rows[0]["hidden"] == 0


def test_toggle_hidden_missing_params_is_bad_request(tmp_path):
    client, _ = _make_client(tmp_path)
    resp = client.post("/project/hidden", data={"hidden": "on"})
    assert resp.status_code == 400


def test_toggle_hidden_survives_slash_and_newline_in_project_name(tmp_path):
    # 실제로 겪은 버그: Format 2 파싱이 잘못 걸려 프로젝트명에 메시지 본문
    # 전체(멘션 목록, 줄바꿈, '/' 등)가 그대로 들어간 경우에도, customer/project를
    # URL 경로가 아니라 쿼리스트링으로 넘기므로 라우팅이 깨지지 않아야 한다.
    weird_project = "* <@U0B78M35BAR>\n<@U06ULC4CARJ>\nA/B 안건\n<@U0B4CTL8PKR>"
    client, db_path = _make_client(tmp_path)
    _seed_project(db_path, "가격 정책 초안 공유 미팅", weird_project, "1000.0001")

    resp = client.post(
        "/project/hidden",
        query_string={"customer": "가격 정책 초안 공유 미팅", "project": weird_project},
        data={"hidden": "on"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True

    conn = db.connect(db_path)
    rows = list(db.list_projects(conn))
    assert rows[0]["hidden"] == 1


def test_project_detail_survives_slash_and_newline_in_project_name(tmp_path):
    weird_project = "* <@U0B78M35BAR>\n<@U06ULC4CARJ>\nA/B 안건"
    client, db_path = _make_client(tmp_path)
    _seed_project(db_path, "가격 정책 초안 공유 미팅", weird_project, "1000.0001")

    resp = client.get(
        "/project", query_string={"customer": "가격 정책 초안 공유 미팅", "project": weird_project}
    )
    assert resp.status_code == 200


def test_no_hidden_link_shown_when_nothing_hidden(tmp_path):
    client, db_path = _make_client(tmp_path)
    _seed_project(db_path, "LG전자", "AI챗봇", "2000.0001")

    resp = client.get("/")
    body = resp.get_data(as_text=True)
    assert "숨김 항목 포함" not in body


def test_index_table_has_sortable_headers_in_requested_order(tmp_path):
    client, db_path = _make_client(tmp_path)
    _seed_project(db_path, "삼성전자", "ERP고도화", "1000.0001")

    resp = client.get("/")
    body = resp.get_data(as_text=True)
    thead = body.split("<thead>", 1)[1].split("</thead>", 1)[0]
    headers = [h.split("<", 1)[0] for h in thead.split(">") if h.strip() and "<th" not in h]
    # data-sortable 테이블인지, 요청한 순서(고객사,프로젝트,담당자,시작일,최근활동,메시지,숨김)인지 확인
    assert 'table class="data-table" data-sortable' in body
    assert thead.index("고객사") < thead.index("프로젝트") < thead.index("담당자")
    assert thead.index("담당자") < thead.index("시작일") < thead.index("최근 활동")
    assert thead.index("최근 활동") < thead.index("메시지") < thead.index("숨김")
    assert 'data-sort="number">메시지' in thead
    assert 'data-sort="text">고객사' in thead


def _seed_project_at(db_path, customer, project, thread_ts, created_ts, owner_name="담당자"):
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
            user_id="U1",
            user_name=owner_name,
            text=f"[{customer}-{project}] 킥오프",
            created_ts=created_ts,
        ),
    )
    db.upsert_message(
        conn,
        db.MessageRow(
            ts=thread_ts + ".0002",
            thread_ts=thread_ts,
            channel_id="C1",
            is_parent=False,
            user_id="U2",
            user_name="다른사람",
            text="댓글",
            created_ts=created_ts + 3600,
        ),
    )
    conn.commit()
    conn.close()


def test_weekly_page_renders_summary_table(tmp_path):
    client, db_path = _make_client(tmp_path)
    ts_this_week = datetime.now(TZ).replace(hour=10, minute=0, second=0, microsecond=0).timestamp()
    _seed_project_at(db_path, "삼성전자", "ERP고도화", "5000.0001", ts_this_week, owner_name="김영업")

    resp = client.get("/weekly")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "주간 사업별 공유 현황" in body
    assert "table class=\"data-table\" data-sortable" in body
    assert "삼성전자" in body
    assert "ERP고도화" in body
    assert "김영업" in body
    # _seed_project_at은 메시지 2건(작성자 킥오프 + 댓글)을 같은 주에 만든다
    assert ">2<" in body.split("ERP고도화", 1)[1][:300]


def test_weekly_page_headers_match_requested_columns(tmp_path):
    client, db_path = _make_client(tmp_path)
    ts_this_week = datetime.now(TZ).replace(hour=10, minute=0, second=0, microsecond=0).timestamp()
    _seed_project_at(db_path, "LG전자", "AI챗봇", "6000.0001", ts_this_week)

    resp = client.get("/weekly")
    body = resp.get_data(as_text=True)
    thead = body.split("<thead>", 1)[1].split("</thead>", 1)[0]
    assert thead.index("고객사") < thead.index("프로젝트") < thead.index("담당자") < thead.index("메시지")
    assert 'data-sort="number">메시지' in thead


def test_weekly_page_has_expandable_detail_rows_with_messages(tmp_path):
    client, db_path = _make_client(tmp_path)
    ts_this_week = datetime.now(TZ).replace(hour=10, minute=0, second=0, microsecond=0).timestamp()
    _seed_project_at(db_path, "삼성전자", "ERP고도화", "7000.0001", ts_this_week)

    resp = client.get("/weekly")
    body = resp.get_data(as_text=True)

    # 펼치기 버튼 + 연결된 상세 행(.detail-row, 기본은 hidden)이 있어야 한다
    assert 'class="expand-toggle"' in body
    assert 'data-detail-target="wk-detail-0"' in body
    assert 'id="wk-detail-0" class="detail-row" hidden' in body
    # 상세 행 안에 그 주 메시지(킥오프 텍스트, 댓글)가 실제로 들어있어야 한다
    detail_section = body.split('id="wk-detail-0"', 1)[1].split("</tr>", 1)[0]
    assert "킥오프" in detail_section
    assert "댓글" in detail_section


def test_weekly_sort_script_moves_detail_rows_with_their_summary_row():
    # 정렬 시 상세 행이 본행을 따라가도록 하는 로직이 base.html에 있는지 확인
    # (실제 재정렬 동작 자체는 JS라 Playwright로 별도 확인함 — 여기서는 회귀 방지용).
    base_html = (Path(__file__).resolve().parents[1] / "src" / "analslack" / "templates" / "base.html").read_text()
    assert "detail-row" in base_html
    assert "data-detail-target" in base_html
