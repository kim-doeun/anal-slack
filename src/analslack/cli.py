from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from typing import Optional

from . import db, reports
from .config import Config
from .slack_client import SlackChannelClient
from .sync import sync_channel


def _write_output(text: str, output: str | None) -> None:
    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"저장됨: {output}", file=sys.stderr)
    else:
        print(text)


def cmd_sync(args: argparse.Namespace) -> None:
    cfg = Config.from_env()

    since_ts: Optional[float] = None
    if args.since:
        try:
            since_date = date.fromisoformat(args.since)
        except ValueError:
            raise RuntimeError(
                f"--since 값 '{args.since}'을(를) 날짜(YYYY-MM-DD)로 해석할 수 없습니다."
            )
        since_ts = datetime(
            since_date.year, since_date.month, since_date.day, tzinfo=cfg.timezone
        ).timestamp()

    slack = SlackChannelClient.from_token(cfg.require_slack_token())
    channel_id = slack.resolve_channel_id(cfg.channel)

    with db.open_db(cfg.db_path) as conn:
        count = sync_channel(
            conn, slack, channel_id, full_resync=args.full, since_ts=since_ts
        )

    print(f"동기화 완료: 메시지 {count}건 처리 (channel={cfg.channel})")


def cmd_weekly(args: argparse.Namespace) -> None:
    cfg = Config.from_env()
    anchor = date.fromisoformat(args.week_of) if args.week_of else date.today()

    with db.open_db(cfg.db_path) as conn:
        report = reports.build_weekly_report(conn, anchor, cfg.timezone)
        user_names = db.get_user_names(conn)

    _write_output(report.to_markdown(cfg.timezone, user_names), args.output)


def cmd_serve(args: argparse.Namespace) -> None:
    cfg = Config.from_env()
    from .web import create_app  # Flask 의존성은 serve 실행 시에만 필요

    app = create_app(cfg)
    print(f"대시보드 실행: http://{args.host}:{args.port} (DB: {cfg.db_path})")
    app.run(host=args.host, port=args.port, debug=args.debug)


def cmd_history(args: argparse.Namespace) -> None:
    cfg = Config.from_env()

    with db.open_db(cfg.db_path) as conn:
        if args.list:
            rows = db.list_projects(conn)
            for row in rows:
                owner = row["owner_name"] or row["owner_id"] or "-"
                print(
                    f"{row['customer']}-{row['project']}\t"
                    f"담당자={owner}\t"
                    f"threads={row['thread_count']}\t"
                    f"last={datetime.fromtimestamp(row['last_ts'], tz=cfg.timezone):%Y-%m-%d}"
                )
            return

        history = reports.build_project_history(
            conn, customer=args.customer, project=args.project
        )
        user_names = db.get_user_names(conn)

    _write_output(history.to_markdown(cfg.timezone, user_names), args.output)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="analslack",
        description="#team-sales 채널의 사업별 공유 스레드 수집/취합 도구",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_sync = sub.add_parser("sync", help="Slack 채널에서 새 스레드/메시지를 수집")
    p_sync.add_argument(
        "--full", action="store_true", help="처음부터 전체 재수집 (기존 sync 지점 무시)"
    )
    p_sync.add_argument(
        "--since",
        metavar="YYYY-MM-DD",
        help=(
            "이 날짜 이후 메시지만 수집 (최초 실행 시 채널 히스토리가 너무 많을 때 유용). "
            "지정하면 기존 sync 지점/--full과 무관하게 이 날짜부터 가져오며, "
            "이후 sync 실행 시에는 이번에 수집된 지점부터 이어서 증분 동기화된다."
        ),
    )
    p_sync.set_defaults(func=cmd_sync)

    p_weekly = sub.add_parser("weekly", help="주간 사업별 공유 내역 취합")
    p_weekly.add_argument(
        "--week-of",
        help="이 날짜(YYYY-MM-DD)가 속한 주 기준으로 집계 (기본값: 오늘)",
    )
    p_weekly.add_argument("--output", "-o", help="결과를 파일로 저장 (기본: 표준출력)")
    p_weekly.set_defaults(func=cmd_weekly)

    p_serve = sub.add_parser("serve", help="사업별 진행 현황을 볼 수 있는 웹 대시보드 실행")
    p_serve.add_argument("--host", default="127.0.0.1", help="바인딩할 호스트 (기본: 127.0.0.1)")
    p_serve.add_argument("--port", type=int, default=5000, help="포트 (기본: 5000)")
    p_serve.add_argument("--debug", action="store_true", help="Flask 디버그 모드로 실행")
    p_serve.set_defaults(func=cmd_serve)

    p_history = sub.add_parser("history", help="사업별 전체 이력 조회")
    p_history.add_argument("--customer", help="고객사명으로 필터")
    p_history.add_argument("--project", help="프로젝트명으로 필터")
    p_history.add_argument(
        "--list", action="store_true", help="필터 없이 전체 사업 목록만 출력"
    )
    p_history.add_argument("--output", "-o", help="결과를 파일로 저장 (기본: 표준출력)")
    p_history.set_defaults(func=cmd_history)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except RuntimeError as e:
        print(f"오류: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
