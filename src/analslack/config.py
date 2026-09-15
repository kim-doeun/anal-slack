from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    slack_bot_token: Optional[str]
    channel: str
    db_path: str
    timezone: ZoneInfo

    @classmethod
    def from_env(cls) -> "Config":
        channel = os.environ.get("SLACK_CHANNEL", "team-sales")
        db_path = os.environ.get("ANALSLACK_DB_PATH", "analslack.db")
        tz_name = os.environ.get("ANALSLACK_TIMEZONE", "Asia/Seoul")
        return cls(
            slack_bot_token=os.environ.get("SLACK_BOT_TOKEN"),
            channel=channel,
            db_path=db_path,
            timezone=ZoneInfo(tz_name),
        )

    def require_slack_token(self) -> str:
        if not self.slack_bot_token:
            raise RuntimeError(
                "SLACK_BOT_TOKEN 환경변수가 설정되어 있지 않습니다. "
                ".env 파일을 만들고 Slack Bot Token을 설정하세요 (.env.example 참고)."
            )
        return self.slack_bot_token
