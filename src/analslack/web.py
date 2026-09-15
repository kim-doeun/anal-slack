from __future__ import annotations

from datetime import date, datetime, timedelta

from flask import Flask, abort, render_template, request, url_for

from . import charts, db, reports
from .config import Config

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

    @app.route("/")
    def index():
        with db.open_db(cfg.db_path) as conn:
            projects = db.list_projects(conn)
            trend = reports.weekly_activity_series(conn, cfg.timezone, weeks=TREND_WEEKS)

        trend_chart = charts.line_chart_svg(
            [(p.week_start.strftime("%m/%d"), p.count) for p in trend],
            aria_label="주간 전체 활동 추이",
        )

        top_items = sorted(projects, key=lambda p: p["message_count"], reverse=True)[
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
        )

    @app.route("/project/<customer>/<project>")
    def project_detail(customer: str, project: str):
        with db.open_db(cfg.db_path) as conn:
            history = reports.build_project_history(conn, customer=customer, project=project)
            if not history.rows:
                abort(404)
            trend = reports.weekly_activity_series(
                conn, cfg.timezone, weeks=TREND_WEEKS, customer=customer, project=project
            )

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

        return render_template(
            "weekly.html",
            report=report,
            anchor=anchor,
            prev_week=(anchor - timedelta(days=7)).isoformat(),
            next_week=(anchor + timedelta(days=7)).isoformat(),
        )

    return app
