import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analslack.parser import parse_title


def test_basic_title():
    t = parse_title("[삼성전자-ERP고도화] 킥오프 미팅 진행했습니다.")
    assert t.matched
    assert t.customer == "삼성전자"
    assert t.project == "ERP고도화"
    assert t.project_key == "삼성전자-ERP고도화"


def test_project_name_contains_dash():
    t = parse_title("[LG전자-AI-챗봇 구축] 1차 미팅 공유")
    assert t.matched
    assert t.customer == "LG전자"
    assert t.project == "AI-챗봇 구축"


def test_no_brackets_is_unmatched():
    t = parse_title("오늘 점심 뭐 먹지")
    assert not t.matched
    assert t.customer == "미분류"


def test_bracket_only_without_trailing_text_is_unmatched():
    t = parse_title("[공지]")
    assert not t.matched


def test_no_dash_no_brackets_body_is_unmatched():
    t = parse_title("오늘 점심 뭐 먹지 [완료]")
    # 대괄호는 있지만 '-'도 없고 뒤에 프로젝트명으로 볼 텍스트도 없는 경우는 아님:
    # 여기서는 대괄호 뒤에 아무 텍스트도 없어 미분류 처리된다.
    assert not t.matched


def test_extra_text_after_bracket_ignored_for_matching():
    t = parse_title("내용 [현대차-차세대플랫폼] 관련 공유드립니다")
    assert t.matched
    assert t.customer == "현대차"
    assert t.project == "차세대플랫폼"


def test_whitespace_trimmed():
    t = parse_title("[  카카오 -  결제시스템개선  ] 진행상황 공유")
    assert t.customer == "카카오"
    assert t.project == "결제시스템개선"


# 포맷 2: [고객사]프로젝트명 (대괄호 안에 '-' 없음)

def test_format2_no_space_after_bracket():
    t = parse_title("[삼성전자]ERP고도화")
    assert t.matched
    assert t.customer == "삼성전자"
    assert t.project == "ERP고도화"


def test_format2_with_space_after_bracket():
    t = parse_title("[삼성전자] ERP고도화")
    assert t.matched
    assert t.customer == "삼성전자"
    assert t.project == "ERP고도화"


def test_format2_customer_whitespace_trimmed():
    t = parse_title("[  삼성전자  ]ERP고도화")
    assert t.customer == "삼성전자"
    assert t.project == "ERP고도화"


def test_format2_project_key_matches_format1_for_same_business():
    t1 = parse_title("[삼성전자-ERP고도화] 킥오프")
    t2 = parse_title("[삼성전자]ERP고도화")
    assert t1.project_key == t2.project_key == "삼성전자-ERP고도화"
