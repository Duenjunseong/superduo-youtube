FROM python:3.12-slim

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    ffmpeg \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# yt-dlp 최신 버전 설치
RUN pip install --upgrade yt-dlp

# 작업 디렉토리 설정
WORKDIR /app

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 프로젝트 파일 복사
COPY . .

# 필요한 디렉토리 생성
RUN mkdir -p /app/logs /app/media /app/static /app/staticfiles

# 권한 설정
RUN useradd -m -s /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# 포트 노출
EXPOSE 8001

# Gunicorn으로 애플리케이션 실행
CMD ["gunicorn", "--config", "gunicorn.conf.py", "config.wsgi:application"] 