from __future__ import annotations

import sys
from typing import Dict, Iterator, Optional

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackChannelClient:
    """Slack 채널의 스레드/메시지를 읽어오는 얇은 래퍼.

    conversations.history / conversations.replies API는 공개/비공개 채널을
    동일하게 다루므로 이 클래스는 그대로 비공개 채널에도 쓸 수 있다.
    단, 비공개 채널의 경우 Bot Token에 groups:history, groups:read 스코프가
    필요하고, 봇이 해당 채널에 멤버로 초대되어 있어야 한다.

    Bot Token 필요 스코프 (공개 채널): channels:history, channels:read, users:read
    Bot Token 필요 스코프 (비공개 채널): groups:history, groups:read, users:read
    """

    def __init__(self, client: WebClient):
        self.client = client
        self._user_name_cache: Dict[str, str] = {}

    @classmethod
    def from_token(cls, token: str) -> "SlackChannelClient":
        return cls(WebClient(token=token))

    def resolve_channel_id(self, channel: str) -> str:
        """채널명 또는 ID를 받아 채널 ID를 반환한다."""
        channel = channel.lstrip("#")
        if channel.startswith(("C", "G")) and channel.isupper():
            return channel

        cursor: Optional[str] = None
        while True:
            resp = self.client.conversations_list(
                types="public_channel,private_channel",
                limit=200,
                cursor=cursor,
            )
            for ch in resp["channels"]:
                if ch["name"] == channel:
                    return ch["id"]
            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        raise ValueError(f"채널 '{channel}'을(를) 찾을 수 없습니다 (봇이 채널에 초대되어 있는지 확인하세요).")

    def resolve_user_name(self, user_id: Optional[str]) -> Optional[str]:
        """user_id -> 표시할 이름. 우선순위: 표시 이름 > 실명 > Slack 아이디(핸들).

        전부 실패하면(users:read 권한 없음 등) None을 반환한다 — 실패를
        사용자 ID 문자열로 위장해서 캐시하면, DB에는 "이름"처럼 저장되지만
        실제로는 실패 흔적이라 다음 sync에서도 재시도 없이 영구히 그 값에
        고정돼버린다. None으로 두면 다음 sync 실행 때 다시 시도된다.
        """
        if not user_id:
            return None
        if user_id in self._user_name_cache:
            return self._user_name_cache[user_id]
        name: Optional[str] = None
        try:
            resp = self.client.users_info(user=user_id)
            profile = resp["user"]
            name = (
                profile.get("profile", {}).get("display_name")
                or profile.get("real_name")
                or profile.get("name")
                or None
            )
        except SlackApiError as e:
            error_code = e.response.get("error") if e.response else str(e)
            print(
                f"경고: 사용자 {user_id} 이름 조회 실패 ({error_code}) — 멘션/작성자 표시에 ID가 그대로 남습니다. "
                f"Bot Token에 users:read 권한이 있는지 확인하세요.",
                file=sys.stderr,
            )
        self._user_name_cache[user_id] = name
        return name

    def iter_root_messages(
        self, channel_id: str, oldest: Optional[float] = None
    ) -> Iterator[dict]:
        """채널의 최상위(스레드 시작) 메시지를 오래된 순으로 순회한다."""
        cursor: Optional[str] = None
        messages: list[dict] = []
        while True:
            resp = self.client.conversations_history(
                channel=channel_id,
                oldest=str(oldest) if oldest else None,
                limit=200,
                cursor=cursor,
            )
            messages.extend(resp["messages"])
            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        for msg in sorted(messages, key=lambda m: float(m["ts"])):
            if msg.get("subtype") is not None:
                continue
            yield msg

    def iter_thread_messages(self, channel_id: str, thread_ts: str) -> Iterator[dict]:
        """스레드의 최초 메시지 + 모든 답글을 오래된 순으로 순회한다."""
        cursor: Optional[str] = None
        while True:
            resp = self.client.conversations_replies(
                channel=channel_id,
                ts=thread_ts,
                limit=200,
                cursor=cursor,
            )
            for msg in resp["messages"]:
                if msg.get("subtype") is not None:
                    continue
                yield msg
            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

    def get_permalink(self, channel_id: str, ts: str) -> Optional[str]:
        try:
            resp = self.client.chat_getPermalink(channel=channel_id, message_ts=ts)
            return resp.get("permalink")
        except SlackApiError:
            return None
