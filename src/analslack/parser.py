"""스레드 제목 파싱.

#team-sales 채널의 운영 규칙: 사업(또는 공유 주제) 단위로 스레드를 열고,
스레드 제목(최초 메시지)에 고객사/프로젝트를 남긴 뒤 이후 댓글(스레드 답글)로
진행 내용을 공유한다. 작성자마다 아래 두 형식을 섞어서 쓴다.

  1. [고객사-프로젝트명]           예: [삼성전자-ERP고도화], [삼성전자 - ERP고도화]
  2. [고객사]프로젝트명            예: [삼성전자]ERP고도화, [삼성전자] ERP고도화

대괄호 안에 '-'가 있으면 1번, 없으면 2번으로 판단한다. 공백 유무는
모두 trim으로 흡수한다.
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


def _unmatched(text: str) -> ThreadTitle:
    return ThreadTitle(
        customer=UNCATEGORIZED_CUSTOMER,
        project=UNCATEGORIZED_PROJECT,
        raw_title=text,
        matched=False,
    )


def parse_title(text: str) -> ThreadTitle:
    """스레드 최초 메시지 텍스트에서 고객사/프로젝트를 추출한다.

    첫 번째 대괄호 블록만 사용한다.
      - 블록 안에 '-'가 있으면 [고객사-프로젝트명] 형식으로 보고 첫 '-' 기준으로 나눈다
        (프로젝트명 자체에 '-'가 들어가도 안전하도록 첫 '-'만 구분자로 사용).
      - 블록 안에 '-'가 없으면 [고객사]프로젝트명 형식으로 보고, 닫는 대괄호
        이후의 텍스트를 프로젝트명으로 사용한다.
    둘 다 고객사/프로젝트명이 비어 있지 않아야 매칭으로 인정하며,
    형식에 맞지 않으면 matched=False 와 함께 미분류로 처리한다.
    """
    text = (text or "").strip()
    match = _BRACKET_RE.search(text)
    if not match:
        return _unmatched(text)

    content = match.group(1).strip()

    if "-" in content:
        customer, project = content.split("-", 1)
        customer = customer.strip()
        project = project.strip()
    else:
        customer = content
        project = text[match.end():].strip()

    if not customer or not project:
        return _unmatched(text)

    return ThreadTitle(customer=customer, project=project, raw_title=text, matched=True)
