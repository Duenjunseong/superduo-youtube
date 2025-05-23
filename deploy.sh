#!/bin/bash

# YouTube Downloader 서버 배포 스크립트
set -e

echo "🚀 YouTube Downloader 배포 시작..."

# 현재 사용자의 UID/GID 설정
export UID=$(id -u)
export GID=$(id -g)
echo "📋 사용자 권한: UID=$UID, GID=$GID"

# 1. 기존 컨테이너 정리
echo "📦 기존 컨테이너 정리 중..."
docker-compose down 2>/dev/null || true

# 기존 권한 문제 파일들 정리
echo "🧹 기존 권한 문제 파일들 정리 중..."
if [ -d "data/static" ]; then
    sudo rm -rf data/static/* 2>/dev/null || true
fi
if [ -d "data/media" ]; then
    sudo chown -R $USER:$USER data/media/ 2>/dev/null || true
fi
if [ -d "logs" ]; then
    sudo chown -R $USER:$USER logs/ 2>/dev/null || true
fi

# 2. 최신 코드 받기
echo "📥 최신 코드 업데이트 중..."
git pull origin main

# 3. 디렉토리 구조 생성
echo "📁 디렉토리 구조 생성 중..."
mkdir -p data/postgres data/media data/static logs
chmod -R 755 data/
chmod -R 777 logs/

# 4. 환경 파일 확인
if [ ! -f .env ]; then
    echo "⚠️  .env 파일이 없습니다. env.example을 복사합니다."
    cp env.example .env
    echo "❗ .env 파일을 수정해주세요!"
    exit 1
fi

# 5. Docker 빌드 및 실행
echo "🐳 Docker 컨테이너 빌드 중..."
docker-compose build --no-cache

echo "🚀 컨테이너 시작 중..."
docker-compose up -d

# 6. 데이터베이스 준비 대기
echo "⏳ 데이터베이스 시작 대기 중..."
sleep 15

# 7. 데이터베이스 생성 (에러 무시)
echo "🗄️  데이터베이스 생성 중..."
docker exec -it superduo_youtube-db-1 psql -U superduo -d postgres -c "CREATE DATABASE superduo_youtube;" 2>/dev/null || echo "데이터베이스가 이미 존재하거나 생성할 수 없습니다."

# 8. 마이그레이션
echo "🔄 데이터베이스 마이그레이션 중..."
docker-compose exec -T web python manage.py makemigrations
docker-compose exec -T web python manage.py migrate

# 9. 정적 파일 수집
echo "📂 정적 파일 수집 중..."
docker-compose exec -T web python manage.py collectstatic --noinput

# 10. 권한 수정 (collectstatic 후 생성된 파일들)
echo "🔐 파일 권한 확인 중..."
chmod -R 755 data/static/ data/media/ 2>/dev/null || true
chmod -R 777 logs/ 2>/dev/null || true

# 11. 상태 확인
echo "✅ 배포 완료! 컨테이너 상태 확인:"
docker-compose ps

echo "🎉 배포가 완료되었습니다!"
echo "🌐 웹사이트: https://ewr.kr"
echo "📊 관리자: https://ewr.kr/admin"

# 로그 확인 안내
echo ""
echo "📋 로그 확인 명령어:"
echo "  전체 로그: docker-compose logs -f"
echo "  웹 로그: docker-compose logs -f web"
echo "  Celery 로그: docker-compose logs -f celery" 