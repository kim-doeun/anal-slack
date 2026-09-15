from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

# 저장소 디렉터리가 아니라 홈 디렉터리 아래에 둔다. 저장소를 새로 clone하거나
# 패키지를 재설치해도(ANALSLACK_DB_PATH를 따로 지정하지 않는 한) 이전에
# `analslack sync`로 모아둔 데이터를 그대로 이어서 쓸 수 있게 하기 위함.
DEFAULT_DB_PATH = str(Path.home() / ".analslack" / "analslack.db")


@dataclass(frozen=True)
class Config:
    slack_bot_token: Optional[str]
    channel: str
    db_path: str
    timezone: ZoneInfo

    @classmethod
    def from_env(cls) -> "Config":
        channel = os.environ.get("SLACK_CHANNEL", "team-sales")
        db_path = os.environ.get("ANALSLACK_DB_PATH", DEFAULT_DB_PATH)
        tz_name = os.environ.get("ANALSLACK_TIMEZONE", "Asia/Seoul")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
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
