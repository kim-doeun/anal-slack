from __future__ import annotations

from datetime import date, datetime, timedelta

from flask import Flask, abort, jsonify, render_template, request, url_for

from . import charts, db, reports
from .config import Config
from .mentions import resolve_mentions

TOP_PROJECTS_LIMIT = 15
TREND_WEEKS = 12


def create_app(cfg: Config) -> Flask:
    app = Flask(__name__)

    def ts_date(ts) -> str:
        if ts is None:
            return "-"
        return datetime.fromtimestamp(ts, tz=cfg.timezone).strftime("%Y-%m-%d")

    def ts_datetime(ts) -> str:
        if ts is None:
            return "-"
        return datetime.fromtimestamp(ts, tz=cfg.timezone).strftime("%Y-%m-%d %H:%M")

    app.jinja_env.filters["ts_date"] = ts_date
    app.jinja_env.filters["ts_datetime"] = ts_datetime
    app.jinja_env.filters["mentions"] = resolve_mentions

    @app.route("/")
    def index():
        show_hidden = request.args.get("show_hidden") == "1"

        with db.open_db(cfg.db_path) as conn:
            all_projects = db.list_projects(conn)
            trend = reports.weekly_activity_series(conn, cfg.timezone, weeks=TREND_WEEKS)

        hidden_count = sum(1 for p in all_projects if p["hidden"])
        projects = all_projects if show_hidden else [p for p in all_projects if not p["hidden"]]

        trend_chart = charts.line_chart_svg(
            [(p.week_start.strftime("%m/%d"), p.count) for p in trend],
            aria_label="주간 전체 활동 추이",
        )

        top_items = sorted(all_projects, key=lambda p: p["message_count"], reverse=True)[
            :TOP_PROJECTS_LIMIT
        ]
        top_chart = charts.bar_chart_svg(
            [
                charts.BarItem(
                    label=f"{p['customer']}-{p['project']}",
                    value=p["message_count"],
                    href=url_for(
                        "project_detail", customer=p["customer"], project=p["project"]
                    ),
                )
                for p in top_items
            ],
            aria_label="사업별 메시지 수 Top 15",
        )

        return render_template(
            "index.html",
            projects=projects,
            trend_chart=trend_chart,
            top_chart=top_chart,
            show_hidden=show_hidden,
            hidden_count=hidden_count,
        )

    @app.route("/project/hidden", methods=["POST"])
    def set_project_hidden():
        # customer/project는 URL 경로가 아니라 쿼리스트링으로 받는다 — Slack
        # 메시지에서 그대로 뽑아낸 이름이라 '/'나 줄바꿈 등 경로 라우팅을 깨는
        # 문자가 섞여 있을 수 있고(예: 잘못 파싱된 프로젝트명), 쿼리스트링/폼
        # 값으로 다루면 그런 문자가 있어도 깨지지 않는다.
        customer = request.args.get("customer", "")
        project = request.args.get("project", "")
        if not customer or not project:
            abort(400)
        hidden = request.form.get("hidden") == "on"
        with db.open_db(cfg.db_path) as conn:
            db.set_project_hidden(conn, customer, project, hidden)
        return jsonify(ok=True, hidden=hidden)

    @app.route("/project")
    def project_detail():
        customer = request.args.get("customer", "")
        project = request.args.get("project", "")
        if not customer or not project:
            abort(404)
        with db.open_db(cfg.db_path) as conn:
            history = reports.build_project_history(conn, customer=customer, project=project)
            if not history.rows:
                abort(404)
            trend = reports.weekly_activity_series(
                conn, cfg.timezone, weeks=TREND_WEEKS, customer=customer, project=project
            )
            user_names = db.get_user_names(conn)

        chart = charts.line_chart_svg(
            [(p.week_start.strftime("%m/%d"), p.count) for p in trend],
            aria_label=f"{customer}-{project} 주간 활동",
        )

        return render_template(
            "project.html",
            customer=customer,
            project=project,
            history=history,
            chart=chart,
            user_names=user_names,
        )

    @app.route("/weekly")
    def weekly():
        week_of = request.args.get("week_of")
        try:
            anchor = date.fromisoformat(week_of) if week_of else date.today()
        except ValueError:
            abort(400, "week_of는 YYYY-MM-DD 형식이어야 합니다.")

        with db.open_db(cfg.db_path) as conn:
            report = reports.build_weekly_report(conn, anchor, cfg.timezone)
            owners = {
                (p["customer"], p["project"]): (p["owner_name"], p["owner_id"])
                for p in db.list_projects(conn)
            }
            user_names = db.get_user_names(conn)

        summary_rows = []
        for project_key, rows in report.projects.items():
            first = rows[0]
            owner_name, owner_id = owners.get((first["customer"], first["project"]), (None, None))
            summary_rows.append(
                {
                    "key": project_key,
                    "customer": first["customer"],
                    "project": first["project"],
                    "owner_name": owner_name,
                    "owner_id": owner_id,
                    "message_count": len(rows),
                }
            )

        return render_template(
            "weekly.html",
            report=report,
            summary_rows=summary_rows,
            user_names=user_names,
            anchor=anchor,
            prev_week=(anchor - timedelta(days=7)).isoformat(),
            next_week=(anchor + timedelta(days=7)).isoformat(),
        )

    return app


def create_wsgi_app() -> Flask:
    """gunicorn 등 WSGI 서버에서 팩토리로 바로 사용할 수 있는 진입점.

    예) gunicorn "analslack.web:create_wsgi_app()" -w 2 -b 127.0.0.1:8080
    (괄호를 붙여 호출 형태로 넘기면 gunicorn이 팩토리 함수로 인식한다)
    """
    return create_app(Config.from_env())
