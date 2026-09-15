"""스레드 제목 [고객사-프로젝트] 파싱.

#team-sales 채널의 운영 규칙: 사업(또는 공유 주제) 단위로 스레드를 열고,
스레드 제목(최초 메시지)을 `[고객사-프로젝트] ...` 형식으로 남긴 뒤
이후 댓글(스레드 답글)로 진행 내용을 공유한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

_BRACKET_RE = re.compile(r"\[([^\[\]]+)\]")

UNCATEGORIZED_CUSTOMER = "미분류"
UNCATEGORIZED_PROJECT = "미분류"


@dataclass(frozen=True)
class ThreadTitle:
    customer: str
    project: str
    raw_title: str
    matched: bool

    @property
    def project_key(self) -> str:
        """사업(고객사-프로젝트) 단위 식별 키."""
        return f"{self.customer}-{self.project}"


def parse_title(text: str) -> ThreadTitle:
    """스레드 최초 메시지 텍스트에서 [고객사-프로젝트]를 추출한다.

    첫 번째 대괄호 블록만 사용하며, 블록 내부는 첫 '-' 기준으로
    고객사/프로젝트를 나눈다 (프로젝트명 자체에 '-'가 들어가도 안전).
    형식에 맞지 않으면 matched=False 와 함께 미분류로 처리한다.
    """
    text = (text or "").strip()
    match = _BRACKET_RE.search(text)
    if not match:
        return ThreadTitle(
            customer=UNCATEGORIZED_CUSTOMER,
            project=UNCATEGORIZED_PROJECT,
            raw_title=text,
            matched=False,
        )

    content = match.group(1).strip()
    if "-" not in content:
        return ThreadTitle(
            customer=UNCATEGORIZED_CUSTOMER,
            project=content or UNCATEGORIZED_PROJECT,
            raw_title=text,
            matched=False,
        )

    customer, project = content.split("-", 1)
    customer = customer.strip() or UNCATEGORIZED_CUSTOMER
    project = project.strip() or UNCATEGORIZED_PROJECT
    return ThreadTitle(customer=customer, project=project, raw_title=text, matched=True)
