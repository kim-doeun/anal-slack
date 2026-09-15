import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analslack import db, reports

TZ = ZoneInfo("Asia/Seoul")


def _ts(y, m, d, h=10, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=TZ).timestamp()


def _make_db():
    conn = db.connect(":memory:")

    # 사업 A: 삼성전자-ERP고도화, 2주에 걸쳐 진행
    conn_thread_a = "1700000001.000001"
    db.upsert_thread(
        conn,
        db.ThreadRow(
            thread_ts=conn_thread_a,
            channel_id="C1",
            customer="삼성전자",
            project="ERP고도화",
            title_raw="[삼성전자-ERP고도화] 킥오프",
            title_matched=True,
            permalink="https://slack.example/a",
            created_ts=_ts(2025, 6, 2),  # 월요일
        ),
    )
    db.upsert_message(
        conn,
        db.MessageRow(
            ts=conn_thread_a,
            thread_ts=conn_thread_a,
            channel_id="C1",
            is_parent=True,
            user_id="U1",
            user_name="김영업",
            text="[삼성전자-ERP고도화] 킥오프",
            created_ts=_ts(2025, 6, 2),
        ),
    )
    db.upsert_message(
        conn,
        db.MessageRow(
            ts="1700000002.000001",
            thread_ts=conn_thread_a,
            channel_id="C1",
            is_parent=False,
            user_id="U2",
            user_name="박담당",
            text="요구사항 정의 완료했습니다.",
            created_ts=_ts(2025, 6, 4),  # 같은 주 수요일
        ),
    )
    db.upsert_message(
        conn,
        db.MessageRow(
            ts="1700000003.000001",
            thread_ts=conn_thread_a,
            channel_id="C1",
            is_parent=False,
            user_id="U2",
            user_name="박담당",
            text="다음 주 진행: 설계 착수",
            created_ts=_ts(2025, 6, 10),  # 다음 주 화요일
        ),
    )

    # 사업 B: LG전자-AI챗봇, 사업 A와 같은 주에 시작
    thread_b = "1700000010.000001"
    db.upsert_thread(
        conn,
        db.ThreadRow(
            thread_ts=thread_b,
            channel_id="C1",
            customer="LG전자",
            project="AI챗봇",
            title_raw="[LG전자-AI챗봇] 프로젝트 공유",
            title_matched=True,
            permalink="https://slack.example/b",
            created_ts=_ts(2025, 6, 3),
        ),
    )
    db.upsert_message(
        conn,
        db.MessageRow(
            ts=thread_b,
            thread_ts=thread_b,
            channel_id="C1",
            is_parent=True,
            user_id="U3",
            user_name="이영업",
            text="[LG전자-AI챗봇] 프로젝트 공유",
            created_ts=_ts(2025, 6, 3),
        ),
    )

    conn.commit()
    return conn


def test_weekly_report_scopes_to_week_and_groups_by_project():
    conn = _make_db()
    report = reports.build_weekly_report(conn, anchor=datetime(2025, 6, 2).date(), tz=TZ)

    assert set(report.projects.keys()) == {"삼성전자-ERP고도화", "LG전자-AI챗봇"}

    a_rows = report.projects["삼성전자-ERP고도화"]
    a_texts = [r["text"] for r in a_rows]
    assert "요구사항 정의 완료했습니다." in a_texts
    assert "다음 주 진행: 설계 착수" not in a_texts  # 다음 주 항목은 제외되어야 함


def test_weekly_report_next_week_only_has_followup_message():
    conn = _make_db()
    report = reports.build_weekly_report(conn, anchor=datetime(2025, 6, 9).date(), tz=TZ)

    assert list(report.projects.keys()) == ["삼성전자-ERP고도화"]
    texts = [r["text"] for r in report.projects["삼성전자-ERP고도화"]]
    assert texts == ["다음 주 진행: 설계 착수"]


def test_project_history_returns_full_cross_week_timeline():
    conn = _make_db()
    history = reports.build_project_history(conn, customer="삼성전자", project="ERP고도화")

    texts = [r["text"] for r in history.rows]
    assert texts == [
        "[삼성전자-ERP고도화] 킥오프",
        "요구사항 정의 완료했습니다.",
        "다음 주 진행: 설계 착수",
    ]


def test_project_history_filters_out_other_projects():
    conn = _make_db()
    history = reports.build_project_history(conn, customer="LG전자")

    assert len(history.rows) == 1
    assert history.rows[0]["project"] == "AI챗봇"


def test_markdown_rendering_smoke():
    conn = _make_db()
    report = reports.build_weekly_report(conn, anchor=datetime(2025, 6, 2).date(), tz=TZ)
    md = report.to_markdown(TZ)
    assert "삼성전자-ERP고도화" in md
    assert "박담당" in md

    history = reports.build_project_history(conn, customer="삼성전자", project="ERP고도화")
    md2 = history.to_markdown(TZ)
    assert "사업 이력" in md2
