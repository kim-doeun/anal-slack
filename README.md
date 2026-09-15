# anal-slack

Slack `#team-sales` 채널에서 사업(고객사-프로젝트)별로 공유되는 스레드를 수집하여,
**주간 단위 취합 리포트**와 **사업별 전체 이력**을 만들어주는 도구입니다.

## 전제 (운영 규칙)

`#team-sales` 채널은 사업/공유 주제 단위로 스레드를 열고, 스레드 제목(최초 메시지)을
`[고객사-프로젝트] ...` 형식으로 남긴 뒤, 이후 진행 내용을 그 스레드의 **댓글(답글)**로
공유하는 방식으로 운영됩니다. 이 도구는 이 규칙을 전제로:

- 제목이 `[고객사-프로젝트]` 형식과 매칭되는 스레드만 수집 대상으로 삼습니다.
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

```bash
pip install -r requirements.txt
# 또는
pip install -e .
```

## Slack App 설정

1. https://api.slack.com/apps 에서 새 앱 생성 (Manifest 대신 From scratch로 진행)
2. **OAuth & Permissions** → Bot Token Scopes 에 아래 권한 추가:
   - `channels:history`, `channels:read` (공개 채널)
   - `groups:history`, `groups:read` (비공개 채널인 경우)
   - `users:read` (작성자 이름 표시용)
3. 워크스페이스에 앱 설치 후 발급된 **Bot User OAuth Token**(`xoxb-...`) 복사
4. `#team-sales` 채널에 해당 봇 초대: `/invite @봇이름`

## 환경 설정

```bash
cp .env.example .env
# .env 파일에 SLACK_BOT_TOKEN, SLACK_CHANNEL 값 입력
```

| 변수 | 설명 | 기본값 |
|---|---|---|
| `SLACK_BOT_TOKEN` | Bot User OAuth Token (`sync` 실행 시 필수) | - |
| `SLACK_CHANNEL` | 채널명 또는 채널 ID | `team-sales` |
| `ANALSLACK_DB_PATH` | SQLite DB 파일 경로 | `analslack.db` |
| `ANALSLACK_TIMEZONE` | 주 단위 집계 기준 시간대 | `Asia/Seoul` |

## 사용법

### 1. 데이터 수집 (증분 동기화)

```bash
analslack sync
```

이전 실행 이후 새로 생긴 메시지만 가져옵니다. 처음부터 전체를 다시 수집하려면:

```bash
analslack sync --full
```

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

## 테스트

Slack 연결 없이 파싱/취합 로직만 검증합니다.

```bash
pip install pytest
pytest
```

## 향후 확장 아이디어

- 주간 리포트를 Slack 채널/DM으로 자동 게시 (`chat.postMessage`)
- LLM을 이용한 사업별 요약 자동 생성
- 웹 대시보드로 사업별 진행 현황 시각화
