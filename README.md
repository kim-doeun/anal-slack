# anal-slack

Slack `#team-sales` 채널에서 사업(고객사-프로젝트)별로 공유되는 스레드를 수집하여,
**주간 단위 취합 리포트**와 **사업별 전체 이력**을 만들어주는 도구입니다.

## 전제 (운영 규칙)

`#team-sales` 채널은 사업/공유 주제 단위로 스레드를 열고, 스레드 제목(최초 메시지)에
고객사/프로젝트를 남긴 뒤, 이후 진행 내용을 그 스레드의 **댓글(답글)**로 공유하는
방식으로 운영됩니다. 작성자마다 표기가 조금씩 달라서 아래 두 형식을 모두 인식합니다
(대괄호 안/뒤 공백 유무는 무시):

- **형식 1** `[고객사-프로젝트명]` — 예: `[삼성전자-ERP고도화]`, `[삼성전자 - ERP고도화]`
- **형식 2** `[고객사]프로젝트명` — 예: `[삼성전자]ERP고도화`, `[삼성전자] ERP고도화`
  (형식 2는 닫는 대괄호 바로 뒤 텍스트를 프로젝트명으로 사용하므로,
  프로젝트명 외의 다른 말이 같은 줄에 더 붙으면 함께 프로젝트명으로 인식됩니다.)

두 형식 다 매칭되지 않는(대괄호가 없거나, 대괄호 뒤에 프로젝트명으로 볼 텍스트가 없는)
스레드는 취합 대상에서 제외됩니다.

- 각 스레드의 최초 메시지 + 모든 답글을 시간순으로 저장합니다.

## 아키텍처

```
Slack API (conversations.history / conversations.replies)
        │
        ▼
   sync (증분 수집) ──▶ SQLite DB (threads, messages)
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
     weekly (주간 취합 리포트)         history (사업별 전체 이력)
```

- **수집**: Slack Bot Token으로 채널 히스토리를 읽어와 SQLite에 누적 저장 (증분 동기화 지원)
- **파싱**: 스레드 제목에서 정규식으로 `고객사`/`프로젝트`를 추출
- **주간 리포트**: 지정한 주(월~일)에 새로 올라온 댓글을 사업별로 그룹핑해 Markdown 생성
- **사업별 이력**: 같은 고객사/프로젝트로 열린 모든 스레드의 전체 메시지를 시간순으로 취합

## 설치

최근 Debian/Ubuntu 계열은 시스템 Python에 직접 `pip install`을 금지합니다
(`error: externally-managed-environment`). 가상환경(venv)을 만들어 그 안에서
설치/실행하세요.

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

pip install -e .
# 또는
pip install -r requirements.txt
```

이후 모든 `analslack ...` / `pytest` 명령은 가상환경이 활성화된 상태(`source .venv/bin/activate`)에서 실행하면 됩니다.
새 터미널을 열 때마다 다시 활성화해야 합니다.

## Slack App 설정

`#team-sales`는 비공개(private) 채널이므로 아래 기준으로 설정합니다.

1. https://api.slack.com/apps 에서 새 앱 생성 (Manifest 대신 From scratch로 진행)
2. **OAuth & Permissions** → Bot Token Scopes 에 아래 권한 추가:
   - `groups:history`, `groups:read` (비공개 채널 읽기 — 필수)
   - `users:read` (작성자 이름 표시용)
   - (만약 향후 공개 채널도 함께 수집한다면 `channels:history`, `channels:read`도 추가)
3. 워크스페이스에 앱 설치 후 발급된 **Bot User OAuth Token**(`xoxb-...`) 복사
4. `#team-sales` 채널에 해당 봇을 **반드시 초대**: `/invite @봇이름`
   - 비공개 채널은 봇이 멤버로 초대되어 있지 않으면 API 자체가 채널을 조회할 수 없습니다
     (공개 채널과 달리 스코프만으로는 부족합니다).

## 환경 설정

```bash
cp .env.example .env
# .env 파일에 SLACK_BOT_TOKEN, SLACK_CHANNEL 값 입력
```

| 변수 | 설명 | 기본값 |
|---|---|---|
| `SLACK_BOT_TOKEN` | Bot User OAuth Token (`sync` 실행 시 필수) | - |
| `SLACK_CHANNEL` | 채널명 또는 채널 ID | `team-sales` |
| `ANALSLACK_DB_PATH` | SQLite DB 파일 경로 | `~/.analslack/analslack.db` (홈 디렉터리, 저장소 밖) |
| `ANALSLACK_TIMEZONE` | 주 단위 집계 기준 시간대 | `Asia/Seoul` |

`ANALSLACK_DB_PATH`가 저장소 밖(홈 디렉터리)을 기본값으로 쓰는 이유: 저장소를
재clone하거나 패키지를 재설치해도 이 값을 따로 건드리지 않는 한 이전에
`analslack sync`로 모아둔 데이터를 그대로 이어서 사용할 수 있게 하기 위해서입니다.
여러 사람이 같은 DB를 공유하고 싶거나 특정 위치에 두고 싶다면 이 값을 원하는
경로로 지정하세요 (새 환경에서도 같은 값으로 맞추면 데이터가 유지됩니다).

> **이전 버전(이 변경 전)을 이미 쓰고 있었다면**: 그때는 DB가 저장소 안
> `./analslack.db`에 있었습니다. 새로 clone한 저장소에서도 기존 데이터를 이어
> 쓰려면, 기존 저장소의 `analslack.db`를 `~/.analslack/analslack.db`로
> 한 번만 옮기거나(`mkdir -p ~/.analslack && mv analslack.db ~/.analslack/`),
> `.env`에 `ANALSLACK_DB_PATH=/기존/경로/analslack.db`를 지정해 계속 그 경로를
> 쓰면 됩니다.

## 사용법

> `analslack` 명령은 서브커맨드 방식입니다 (`analslack --weekly` (X) → `analslack weekly` (O)).
> `analslack: command not found`가 나면 가상환경이 활성화되어 있는지 확인하세요
> (`source .venv/bin/activate`, 새 터미널을 열었다면 매번 다시 실행). venv 활성화 여부와
> 무관하게 항상 되는 대안: `python3 -m analslack weekly` 처럼 `python3 -m analslack <서브커맨드>`로 실행.

### 1. 데이터 수집 (증분 동기화)

```bash
analslack sync
```

이전 실행 이후 새로 생긴 메시지만 가져옵니다. 처음부터 전체를 다시 수집하려면:

```bash
analslack sync --full
```

**채널에 메시지가 너무 많아 처음부터 전체를 가져오고 싶지 않다면** `--since`로
동기화 시작일을 지정하세요 (특히 최초 실행 시 유용):

```bash
analslack sync --since 2025-01-01
```

`--since`를 지정하면 기존 동기화 지점이나 `--full` 여부와 무관하게 해당 날짜부터
가져옵니다. 이렇게 최초 실행을 하고 나면, 이후에는 `--since` 없이 `analslack sync`만
실행해도 이번에 수집된 지점부터 자동으로 이어서 증분 동기화됩니다.

주기적으로 실행하려면 cron 등으로 스케줄링하세요 (예: 매일 아침 1회).

### 2. 주간 취합 리포트

```bash
analslack weekly                       # 이번 주 (오늘 기준)
analslack weekly --week-of 2025-06-02  # 해당 날짜가 속한 주
analslack weekly -o weekly_report.md   # 파일로 저장
```

사업(고객사-프로젝트)별로 해당 주에 올라온 공유 내용을 모아 Markdown으로 출력합니다.

### 3. 사업별 전체 이력

```bash
analslack history --list                                  # 전체 사업 목록
analslack history --customer 삼성전자 --project ERP고도화   # 특정 사업 전체 이력
analslack history --customer 삼성전자                       # 고객사 단위로도 조회 가능
analslack history --project ERP고도화 -o history.md         # 파일로 저장
```

같은 고객사-프로젝트로 열린 모든 스레드의 메시지를 시간순으로 모아 보여줍니다
(스레드가 여러 번 재개돼도 하나의 사업 이력으로 합쳐집니다).

### 4. 웹 대시보드

```bash
analslack serve                    # http://127.0.0.1:5000
analslack serve --port 8080        # 포트 지정
analslack serve --host 0.0.0.0     # 다른 기기에서도 접속 허용 (사내망 등 신뢰된 환경에서만)
```

로컬에서 뜨는 Flask 앱으로, `sync`로 모아둔 SQLite DB를 읽기 전용으로 보여줍니다
(별도 인증 없음 — `--host 0.0.0.0`으로 열 경우 접근 범위에 주의하세요).

- **전체 사업 목록** (`/`) — 주간 전체 활동 추이 그래프, 사업별 메시지 수 Top 15 막대
  그래프, 사업 목록 표 (스레드 수/메시지 수/시작일/최근 활동일)
- **사업별 상세** (`/project/<고객사>/<프로젝트>`) — 해당 사업의 주간 활동 추이 +
  전체 이력 타임라인 (Slack 스레드 링크 포함)
- **주간 리포트** (`/weekly`) — 이전 주/다음 주 이동 가능한 주간 취합 뷰

`sync`로 데이터가 갱신된 후 대시보드를 새로고침하면 최신 상태가 반영됩니다
(별도 캐시 없이 매 요청마다 SQLite를 직접 조회).

## 테스트

Slack 연결 없이 파싱/취합 로직만 검증합니다. (가상환경 활성화된 상태에서)

```bash
pip install pytest
pytest
```

## 향후 확장 아이디어

- 주간 리포트를 Slack 채널/DM으로 자동 게시 (`chat.postMessage`)
- LLM을 이용한 사업별 요약 자동 생성
- 대시보드에 인증/접근 제어 추가 (사내망 밖에서도 안전하게 열람하려는 경우)
