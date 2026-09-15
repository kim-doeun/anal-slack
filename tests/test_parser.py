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


def test_bracket_without_dash_is_unmatched():
    t = parse_title("[공지] 다음주 워크샵 있습니다")
    assert not t.matched
    assert t.project == "공지"


def test_extra_text_after_bracket_ignored_for_matching():
    t = parse_title("내용 [현대차-차세대플랫폼] 관련 공유드립니다")
    assert t.matched
    assert t.customer == "현대차"
    assert t.project == "차세대플랫폼"


def test_whitespace_trimmed():
    t = parse_title("[  카카오 -  결제시스템개선  ] 진행상황 공유")
    assert t.customer == "카카오"
    assert t.project == "결제시스템개선"
