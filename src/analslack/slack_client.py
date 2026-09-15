from __future__ import annotations

from typing import Dict, Iterator, Optional

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackChannelClient:
    """Slack 채널의 스레드/메시지를 읽어오는 얇은 래퍼.

    Bot Token 필요 스코프: channels:history, channels:read
    (비공개 채널이면 groups:history, groups:read), users:read
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
        if not user_id:
            return None
        if user_id in self._user_name_cache:
            return self._user_name_cache[user_id]
        try:
            resp = self.client.users_info(user=user_id)
            profile = resp["user"]
            name = profile.get("profile", {}).get("display_name") or profile.get("real_name") or user_id
        except SlackApiError:
            name = user_id
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
