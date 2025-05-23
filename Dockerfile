FROM python:3.12-slim

# 시스템 패키지 설치 (캐시 레이어 1)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    ffmpeg \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# yt-dlp 최신 버전 설치 (캐시 레이어 2)
RUN pip install --upgrade yt-dlp

# 작업 디렉토리 설정
WORKDIR /app

# Python 의존성 먼저 설치 (캐시 레이어 3 - requirements.txt가 변경될 때만 재빌드)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 필요한 디렉토리 생성 (캐시 레이어 4)
RUN mkdir -p /app/logs /app/media /app/static /app/staticfiles

# 사용자 생성 및 권한 설정 (캐시 레이어 5)
RUN useradd -m -s /bin/bash appuser && \
    chown -R appuser:appuser /app

# 프로젝트 파일 복사 (가장 마지막 - 소스 코드 변경 시에만 이 레이어부터 재빌드)
COPY --chown=appuser:appuser . .

# 사용자 전환
USER appuser

# 포트 노출
EXPOSE 8001

# Gunicorn으로 애플리케이션 실행
CMD ["gunicorn", "--config", "gunicorn.conf.py", "config.wsgi:application"] 