import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analslack.mentions import extract_mentioned_user_ids, resolve_mentions


def test_resolve_known_user_mention():
    text = "<@U0B2UGNL3HU> 님 확인 부탁드립니다"
    result = resolve_mentions(text, {"U0B2UGNL3HU": "김영업"})
    assert result == "@김영업 님 확인 부탁드립니다"


def test_resolve_unknown_user_falls_back_to_id():
    text = "<@U0B2UGNL3HU> 님 확인 부탁드립니다"
    result = resolve_mentions(text, {})
    assert result == "@U0B2UGNL3HU 님 확인 부탁드립니다"


def test_resolve_uses_inline_fallback_display_name_when_unresolved():
    text = "<@U0B2UGNL3HU|doeun.kim> 확인 부탁드려요"
    result = resolve_mentions(text, {})
    assert result == "@doeun.kim 확인 부탁드려요"


def test_inline_fallback_ignored_when_db_name_available():
    text = "<@U0B2UGNL3HU|old.name> 확인 부탁드려요"
    result = resolve_mentions(text, {"U0B2UGNL3HU": "현재이름"})
    assert result == "@현재이름 확인 부탁드려요"


def test_multiple_mentions_in_one_message():
    text = "<@U1> 그리고 <@U2> 둘 다 확인해주세요"
    result = resolve_mentions(text, {"U1": "철수", "U2": "영희"})
    assert result == "@철수 그리고 @영희 둘 다 확인해주세요"


def test_special_mentions():
    assert resolve_mentions("<!here> 공지입니다", {}) == "@here 공지입니다"
    assert resolve_mentions("<!channel>", {}) == "@channel"


def test_channel_mention():
    text = "자세한 내용은 <#C123ABC|team-sales> 참고"
    assert resolve_mentions(text, {}) == "자세한 내용은 #team-sales 참고"


def test_empty_or_none_text():
    assert resolve_mentions(None, {}) == ""
    assert resolve_mentions("", {}) == ""


def test_text_without_mentions_unchanged():
    text = "그냥 평범한 업데이트 메시지입니다."
    assert resolve_mentions(text, {"U1": "누군가"}) == text


def test_extract_mentioned_user_ids():
    text = "<@U1> 그리고 <@U2|fallback> 확인"
    assert extract_mentioned_user_ids(text) == {"U1", "U2"}


def test_extract_mentioned_user_ids_empty():
    assert extract_mentioned_user_ids(None) == set()
    assert extract_mentioned_user_ids("멘션 없음") == set()
