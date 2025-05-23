#!/bin/bash

# YouTube Downloader 서버 배포 스크립트
set -e

echo "🚀 YouTube Downloader 배포 시작..."

# 전체 빌드 옵션 체크 (deploy.sh --full-build 로 실행 시)
FULL_BUILD=false
if [[ "$1" == "--full-build" ]]; then
    FULL_BUILD=true
    echo "🔨 전체 빌드 모드 (캐시 무시)"
fi

# 현재 사용자의 UID/GID 설정
USER_ID=$(id -u)
GROUP_ID=$(id -g)
export USER_ID
export GROUP_ID
echo "📋 사용자 권한: USER_ID=$USER_ID, GROUP_ID=$GROUP_ID"

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

# 3. 기존 마이그레이션 파일 정리 (동적 생성을 위해)
echo "🗑️  기존 마이그레이션 파일 정리 중..."
find . -path "*/migrations/0*.py" -delete 2>/dev/null || true
find . -path "*/migrations/__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# 4. 디렉토리 구조 생성
echo "📁 디렉토리 구조 생성 중..."
mkdir -p data/postgres data/media data/static logs
chmod -R 755 data/
chmod -R 777 logs/

# 5. 환경 파일 확인
if [ ! -f .env ]; then
    echo "⚠️  .env 파일이 없습니다. env.example을 복사합니다."
    cp env.example .env
    echo "❗ .env 파일을 수정해주세요!"
    exit 1
fi

# 6. Docker 빌드 및 실행
echo "🐳 Docker 컨테이너 빌드 중..."
if [[ "$FULL_BUILD" == "true" ]]; then
    docker-compose build --no-cache
else
    docker-compose build
fi

echo "🚀 데이터베이스 컨테이너 시작 중..."
docker-compose up -d db redis

# 7. 데이터베이스 준비 대기
echo "⏳ 데이터베이스 시작 대기 중..."
sleep 15

# 8. 데이터베이스 생성 (에러 무시)
echo "🗄️  데이터베이스 생성 중..."
docker exec -it $(docker-compose ps -q db) psql -U superduo -d postgres -c "CREATE DATABASE superduo_youtube;" 2>/dev/null || echo "데이터베이스가 이미 존재합니다."

# 9. Django 웹 컨테이너 시작
echo "🐳 Django 웹 컨테이너 시작 중..."
docker-compose up -d web

# 10. 새로운 마이그레이션 파일 생성
echo "📝 새로운 마이그레이션 파일 생성 중..."
sleep 10
docker-compose exec -T web python manage.py makemigrations users
docker-compose exec -T web python manage.py makemigrations downloads
docker-compose exec -T web python manage.py makemigrations

# 11. 마이그레이션 적용
echo "🔄 데이터베이스 마이그레이션 중..."
docker-compose exec -T web python manage.py migrate

# 12. 정적 파일 수집
echo "📂 정적 파일 수집 중..."
docker-compose exec -T web python manage.py collectstatic --noinput

# 13. Celery 컨테이너 시작
echo "🎯 Celery 컨테이너 시작 중..."
docker-compose up -d celery

# 14. 권한 확인 (collectstatic 후 생성된 파일들)
echo "🔐 파일 권한 확인 중..."
chmod -R 755 data/static/ data/media/ 2>/dev/null || true
chmod -R 777 logs/ 2>/dev/null || true

# 15. 상태 확인
echo "✅ 배포 완료! 컨테이너 상태 확인:"
docker-compose ps

echo "🎉 배포가 완료되었습니다!"
echo "🌐 웹사이트: https://ewr.kr"
echo "📊 관리자: https://ewr.kr/admin"

# 마이그레이션 상태 확인
echo ""
echo "📋 현재 마이그레이션 상태:"
docker-compose exec -T web python manage.py showmigrations

# 로그 확인 안내
echo ""
echo "📋 로그 확인 명령어:"
echo "  전체 로그: docker-compose logs -f"
echo "  웹 로그: docker-compose logs -f web"
echo "  Celery 로그: docker-compose logs -f celery" 