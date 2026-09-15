import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analslack.config import DEFAULT_DB_PATH


def test_default_db_path_lives_outside_repo_in_home_dir():
    # 저장소를 재clone/재설치해도 analslack sync로 모아둔 데이터가 유지되도록
    # 기본 DB 경로는 저장소 디렉터리가 아니라 홈 디렉터리 아래여야 한다.
    home = str(Path.home())
    assert DEFAULT_DB_PATH.startswith(home)
    assert DEFAULT_DB_PATH.endswith("analslack.db")


def test_from_env_creates_db_parent_dir(monkeypatch, tmp_path):
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    target = tmp_path / "nested" / "dir" / "analslack.db"
    monkeypatch.setenv("ANALSLACK_DB_PATH", str(target))

    from analslack.config import Config

    cfg = Config.from_env()

    assert cfg.db_path == str(target)
    assert target.parent.is_dir()
