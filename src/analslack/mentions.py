"""Slack 메시지 본문에 들어있는 멘션 마크업을 사람이 읽을 수 있는 텍스트로 치환.

Slack은 메시지 본문 안의 사용자 멘션을 `<@U0B2UGNL3HU>` (또는 구버전 클라이언트
호환용 `<@U0B2UGNL3HU|표시이름>`) 형태로 보내고, 클라이언트가 실제 이름으로
그려주는 걸 기대한다. 이 프로젝트는 Slack 클라이언트가 아니라 저장된 텍스트를
그대로 보여주므로, 별도로 치환해줘야 "<@U0B2UGNL3HU>"가 그대로 노출된다.
"""

from __future__ import annotations

import re
from typing import Mapping, Optional

_USER_MENTION_RE = re.compile(r"<@([UW][A-Z0-9]+)(?:\|([^>]*))?>")
_SPECIAL_MENTION_RE = re.compile(r"<!(here|channel|everyone)>")
_CHANNEL_MENTION_RE = re.compile(r"<#[CG][A-Z0-9]+\|([^>]+)>")


def extract_mentioned_user_ids(text: Optional[str]) -> "set[str]":
    """메시지 본문에서 <@USERID> 형태로 언급된 사용자 ID 목록을 뽑는다.

    sync 시점에 (작성자뿐 아니라) 본문에 언급된 사용자도 이름을 캐시해두기
    위해 사용한다 — 그래야 그 사람이 채널에 직접 글을 쓴 적 없어도
    <@U...>가 이름으로 치환될 수 있다.
    """
    if not text:
        return set()
    return {m.group(1) for m in _USER_MENTION_RE.finditer(text)}


def resolve_mentions(text: Optional[str], user_names: Mapping[str, str]) -> str:
    """<@USERID> 등을 실제 이름으로 치환한다.

    user_names에 없는 사용자 ID는 멘션에 포함된 표시이름(있는 경우) 또는
    사용자 ID 자체로 대체한다 (완전히 알 수 없는 것보다는 낫다).
    """
    if not text:
        return text or ""

    def _sub_user(m: re.Match) -> str:
        user_id, fallback = m.group(1), m.group(2)
        name = user_names.get(user_id) or fallback or user_id
        return f"@{name}"

    text = _USER_MENTION_RE.sub(_sub_user, text)
    text = _SPECIAL_MENTION_RE.sub(lambda m: f"@{m.group(1)}", text)
    text = _CHANNEL_MENTION_RE.sub(lambda m: f"#{m.group(1)}", text)
    return text
