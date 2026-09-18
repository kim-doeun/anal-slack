FROM python:3.11-slim

WORKDIR /app

# 의존성만 먼저 복사해 레이어 캐시를 살린다 (소스만 바뀌면 pip install 재실행 안 됨)
COPY pyproject.toml requirements.txt ./
COPY src ./src
RUN pip install --no-cache-dir -e ".[prod]"

# DB 기본 경로(~/.analslack)를 컨테이너 안에서도 쓰되, 실제로는 아래 볼륨으로
# 덮어써서 컨테이너를 지워도 데이터가 남게 한다.
ENV ANALSLACK_DB_PATH=/data/analslack.db
VOLUME ["/data"]

EXPOSE 8080

CMD ["gunicorn", "analslack.web:create_wsgi_app()", "-w", "2", "-b", "0.0.0.0:8080"]
