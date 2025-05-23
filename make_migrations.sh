#!/bin/bash

# 개발용 마이그레이션 생성 스크립트
set -e

echo "📝 새로운 마이그레이션 파일 생성 중..."

# 기존 마이그레이션 파일 정리
echo "🗑️  기존 마이그레이션 파일 정리 중..."
find . -path "*/migrations/0*.py" -delete 2>/dev/null || true
find . -path "*/migrations/__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# 현재 사용자의 UID/GID 설정 
USER_ID=$(id -u)
GROUP_ID=$(id -g)
export USER_ID
export GROUP_ID

# Django 웹 컨테이너가 실행 중인지 확인
if ! docker-compose ps web | grep -q "Up"; then
    echo "🚀 Django 웹 컨테이너 시작 중..."
    docker-compose up -d web
    sleep 10
fi

# 새로운 마이그레이션 파일 생성
echo "📝 마이그레이션 파일 생성 중..."
docker-compose exec -T web python manage.py makemigrations users
docker-compose exec -T web python manage.py makemigrations downloads  
docker-compose exec -T web python manage.py makemigrations

# 마이그레이션 적용
echo "🔄 마이그레이션 적용 중..."
docker-compose exec -T web python manage.py migrate

# 마이그레이션 상태 확인
echo "📋 현재 마이그레이션 상태:"
docker-compose exec -T web python manage.py showmigrations

echo "✅ 마이그레이션 생성 완료!" 