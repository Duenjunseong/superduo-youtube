#!/bin/bash

# Nginx 설정 자동 복사 및 설정 스크립트
set -e

echo "🌐 Nginx 설정 시작..."

# 현재 프로젝트 경로 확인
PROJECT_PATH=$(pwd)
echo "📁 프로젝트 경로: $PROJECT_PATH"

# Docker 환경인지 확인
if docker-compose ps > /dev/null 2>&1; then
    echo "🐳 Docker 환경 감지됨"
    CONFIG_FILE="deploy/nginx-docker.conf"
    SITE_NAME="youtube_downloader"
else
    echo "🖥️  수동 배포 환경"
    CONFIG_FILE="deploy/nginx.conf"
    SITE_NAME="superduo_youtube"
fi

# nginx 설정 파일 복사
echo "📋 Nginx 설정 복사 중..."
sudo cp "$CONFIG_FILE" "/etc/nginx/sites-available/$SITE_NAME"

# 도메인명 확인 및 수정 안내
echo "⚠️  도메인명을 확인하고 수정하세요:"
echo "sudo nano /etc/nginx/sites-available/$SITE_NAME"

read -p "도메인명을 수정했나요? (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # 기존 사이트 비활성화 (선택사항)
    read -p "기본 nginx 사이트를 비활성화할까요? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo rm -f /etc/nginx/sites-enabled/default
        echo "✅ 기본 사이트 비활성화됨"
    fi
    
    # 심볼릭 링크 생성
    echo "🔗 사이트 활성화 중..."
    sudo ln -sf "/etc/nginx/sites-available/$SITE_NAME" "/etc/nginx/sites-enabled/"
    
    # nginx 설정 테스트
    echo "🔍 Nginx 설정 테스트 중..."
    if sudo nginx -t; then
        echo "✅ Nginx 설정이 올바릅니다!"
        
        # nginx 재시작
        echo "🔄 Nginx 재시작 중..."
        sudo systemctl reload nginx
        echo "🎉 Nginx 설정 완료!"
        
        echo ""
        echo "📋 다음 단계:"
        echo "1. 웹사이트 확인: curl -I http://ewr.kr"
        echo "2. SSL 인증서 설정: sudo certbot --nginx -d ewr.kr"
        echo "3. 로그 확인: sudo tail -f /var/log/nginx/error.log"
        
    else
        echo "❌ Nginx 설정에 오류가 있습니다. 설정을 확인해주세요."
        exit 1
    fi
else
    echo "⏸️  도메인명을 먼저 수정한 후 다시 실행해주세요."
    echo "sudo nano /etc/nginx/sites-available/$SITE_NAME"
    exit 1
fi 