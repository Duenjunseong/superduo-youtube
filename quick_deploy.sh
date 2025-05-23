#!/bin/bash

# YouTube Downloader 빠른 배포 스크립트 (소스 코드 변경만 있을 때)
set -e

echo "⚡ YouTube Downloader 빠른 배포 시작..."

# 현재 사용자의 UID/GID 설정
USER_ID=$(id -u)
GROUP_ID=$(id -g)
export USER_ID
export GROUP_ID
echo "📋 사용자 권한: USER_ID=$USER_ID, GROUP_ID=$GROUP_ID"

# 1. 최신 코드 받기
echo "📥 최신 코드 업데이트 중..."
git pull origin main

# 2. 기존 마이그레이션 파일 정리 (동적 생성을 위해)
echo "🗑️  기존 마이그레이션 파일 정리 중..."
find . -path "*/migrations/0*.py" -delete 2>/dev/null || true
find . -path "*/migrations/__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# 3. 컨테이너 재시작 (빌드 없이)
echo "🔄 컨테이너 재시작 중..."
docker-compose down
docker-compose up -d

# 4. 웹 컨테이너 준비 대기
echo "⏳ 웹 컨테이너 준비 대기 중..."
sleep 15

# 5. 새로운 마이그레이션 파일 생성 및 적용
echo "📝 마이그레이션 처리 중..."
docker-compose exec -T web python manage.py makemigrations users
docker-compose exec -T web python manage.py makemigrations downloads
docker-compose exec -T web python manage.py makemigrations
docker-compose exec -T web python manage.py migrate

# 6. 정적 파일 수집
echo "📂 정적 파일 수집 중..."
docker-compose exec -T web python manage.py collectstatic --noinput

# 7. 상태 확인
echo "✅ 빠른 배포 완료! 컨테이너 상태:"
docker-compose ps

echo "🎉 빠른 배포가 완료되었습니다!"
echo "🌐 웹사이트: https://ewr.kr"

echo ""
echo "📋 로그 확인 명령어:"
echo "  전체 로그: docker-compose logs -f"
echo "  웹 로그: docker-compose logs -f web"
echo "  Celery 로그: docker-compose logs -f celery" 