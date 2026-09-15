import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from slack_sdk.errors import SlackApiError

from analslack.slack_client import SlackChannelClient


class FakeWebClient:
    def __init__(self, users=None, raise_error=None):
        self._users = users or {}
        self._raise_error = raise_error

    def users_info(self, user):
        if self._raise_error:
            raise SlackApiError("boom", {"error": self._raise_error})
        return {"user": self._users[user]}


def test_prefers_display_name():
    client = SlackChannelClient(
        FakeWebClient({"U1": {"profile": {"display_name": "표시이름", "real_name": "실명"}, "name": "handle"}})
    )
    assert client.resolve_user_name("U1") == "표시이름"


def test_falls_back_to_real_name_when_no_display_name():
    # Slack users.info 응답은 real_name을 user 객체 최상위에도 담아준다
    # (profile.real_name과 별개로 profile 밖에도 존재) — 코드가 보는 위치와 맞춰야 한다.
    client = SlackChannelClient(
        FakeWebClient({"U1": {"profile": {"display_name": ""}, "real_name": "실명", "name": "handle"}})
    )
    assert client.resolve_user_name("U1") == "실명"


def test_falls_back_to_slack_username_when_no_display_or_real_name():
    # 봇 계정 등 display_name/real_name이 비어있는 경우 — 사용자가 요청한
    # "slack user명을 그대로 보여달라"에 해당하는 마지막 성공 경로.
    client = SlackChannelClient(
        FakeWebClient({"U1": {"profile": {"display_name": "", "real_name": ""}, "name": "raw.handle"}})
    )
    assert client.resolve_user_name("U1") == "raw.handle"


def test_api_error_returns_none_instead_of_faking_id_as_name():
    # 이전 버그: 조회 실패 시 user_id를 "이름"인 것처럼 반환해서 DB에
    # 영구 캐시되는 바람에 재동기화해도 @U0B2UGNL3HU 그대로 남았음.
    client = SlackChannelClient(FakeWebClient(raise_error="missing_scope"))
    assert client.resolve_user_name("U1") is None


def test_none_user_id_returns_none_without_api_call():
    client = SlackChannelClient(FakeWebClient())
    assert client.resolve_user_name(None) is None
    assert client.resolve_user_name("") is None


def test_result_is_cached_per_instance():
    fake = FakeWebClient({"U1": {"profile": {"display_name": "이름"}, "name": "handle"}})
    client = SlackChannelClient(fake)
    assert client.resolve_user_name("U1") == "이름"
    # users 딕셔너리를 비워도 캐시된 값이 그대로 반환되어야 함(추가 API 호출 없음)
    fake._users = {}
    assert client.resolve_user_name("U1") == "이름"


def test_error_result_is_also_cached_to_avoid_repeated_failing_calls():
    client = SlackChannelClient(FakeWebClient(raise_error="missing_scope"))
    assert client.resolve_user_name("U1") is None
    assert "U1" in client._user_name_cache
    assert client._user_name_cache["U1"] is None
