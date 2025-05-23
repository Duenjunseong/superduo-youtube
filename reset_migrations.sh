#!/bin/bash

# 마이그레이션 파일 초기화 스크립트
set -e

echo "🔄 마이그레이션 파일 초기화 시작..."

# 1. 컨테이너 중지
echo "📦 컨테이너 중지 중..."
docker-compose down 2>/dev/null || true

# 2. 기존 마이그레이션 파일 삭제 (0001_initial.py 제외하고 __init__.py는 보존)
echo "🗑️  기존 마이그레이션 파일 삭제 중..."

# users 앱 마이그레이션 정리
if [ -d "users/migrations" ]; then
    find users/migrations -name "*.py" ! -name "__init__.py" -delete 2>/dev/null || true
    rm -rf users/migrations/__pycache__ 2>/dev/null || true
fi

# downloads 앱 마이그레이션 정리  
if [ -d "downloads/migrations" ]; then
    find downloads/migrations -name "*.py" ! -name "__init__.py" -delete 2>/dev/null || true
    rm -rf downloads/migrations/__pycache__ 2>/dev/null || true
fi

# core 앱 마이그레이션 정리
if [ -d "core/migrations" ]; then
    find core/migrations -name "*.py" ! -name "__init__.py" -delete 2>/dev/null || true
    rm -rf core/migrations/__pycache__ 2>/dev/null || true
fi

# 3. 데이터베이스 초기화 (기존 데이터 삭제)
echo "🗄️  데이터베이스 초기화 중..."
if [ -d "data/postgres" ]; then
    sudo rm -rf data/postgres/* 2>/dev/null || true
fi

# 4. 사용자 권한 설정
export UID=$(id -u)
export GID=$(id -g)
echo "📋 사용자 권한: UID=$UID, GID=$GID"

# 5. 컨테이너 시작 (데이터베이스만)
echo "🚀 데이터베이스 컨테이너 시작 중..."
docker-compose up -d db redis

# 6. 데이터베이스 준비 대기
echo "⏳ 데이터베이스 시작 대기 중..."
sleep 20

# 7. 데이터베이스 생성
echo "🗄️  데이터베이스 생성 중..."
docker exec -it $(docker-compose ps -q db) psql -U superduo -d postgres -c "DROP DATABASE IF EXISTS superduo_youtube;" 2>/dev/null || true
docker exec -it $(docker-compose ps -q db) psql -U superduo -d postgres -c "CREATE DATABASE superduo_youtube;" 2>/dev/null || true

# 8. Django 앱 컨테이너 시작
echo "🐳 Django 컨테이너 시작 중..."
docker-compose up -d web

# 9. 새로운 마이그레이션 파일 생성
echo "📝 새로운 마이그레이션 파일 생성 중..."
sleep 10
docker-compose exec -T web python manage.py makemigrations users
docker-compose exec -T web python manage.py makemigrations downloads
docker-compose exec -T web python manage.py makemigrations

# 10. 마이그레이션 적용
echo "🔄 마이그레이션 적용 중..."
docker-compose exec -T web python manage.py migrate

# 11. Celery 컨테이너 시작
echo "🎯 Celery 컨테이너 시작 중..."
docker-compose up -d celery

# 12. 슈퍼유저 생성 안내
echo "👤 슈퍼유저를 생성하려면 다음 명령어를 실행하세요:"
echo "docker-compose exec web python manage.py createsuperuser"

echo "✅ 마이그레이션 초기화 완료!"
echo "🌐 웹사이트: http://localhost:8001"

# 현재 마이그레이션 상태 확인
echo ""
echo "📋 현재 마이그레이션 상태:"
docker-compose exec -T web python manage.py showmigrations 