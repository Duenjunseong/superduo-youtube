#!/bin/bash

# YouTube Downloader 배포 스크립트
set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 배포 설정
PROJECT_NAME="youtube_downloader"
PROJECT_DIR="/var/www/$PROJECT_NAME"
REPO_URL="https://github.com/yourusername/youtube_downloader.git"  # 실제 저장소 URL로 변경 필요
DOMAIN="yourdomain.com"  # 실제 도메인으로 변경 필요

echo -e "${GREEN}YouTube Downloader 배포 시작...${NC}"
echo -e "${YELLOW}주의: Django 애플리케이션은 8001 포트로 구동됩니다 (8000 포트 충돌 방지)${NC}"

# 1. 시스템 패키지 업데이트
echo -e "${YELLOW}시스템 패키지 업데이트...${NC}"
sudo apt update && sudo apt upgrade -y

# 2. 필요한 패키지 설치
echo -e "${YELLOW}필요한 패키지 설치...${NC}"
sudo apt install -y python3 python3-pip python3-venv postgresql postgresql-contrib nginx redis-server git curl

# 3. PostgreSQL 데이터베이스 설정
echo -e "${YELLOW}PostgreSQL 데이터베이스 설정...${NC}"
sudo -u postgres createdb $PROJECT_NAME || echo "데이터베이스가 이미 존재합니다."
sudo -u postgres createuser --interactive --pwprompt $PROJECT_NAME || echo "사용자가 이미 존재합니다."

# 4. 프로젝트 디렉토리 생성
echo -e "${YELLOW}프로젝트 디렉토리 설정...${NC}"
sudo mkdir -p $PROJECT_DIR
sudo mkdir -p /var/log/$PROJECT_NAME
sudo mkdir -p /var/run/celery
sudo mkdir -p /var/log/celery

# 5. 프로젝트 클론 또는 업데이트
if [ -d "$PROJECT_DIR/.git" ]; then
    echo -e "${YELLOW}프로젝트 업데이트...${NC}"
    cd $PROJECT_DIR
    sudo git pull origin main
else
    echo -e "${YELLOW}프로젝트 클론...${NC}"
    sudo git clone $REPO_URL $PROJECT_DIR
    cd $PROJECT_DIR
fi

# 6. 가상환경 설정
echo -e "${YELLOW}가상환경 설정...${NC}"
sudo python3 -m venv venv
sudo $PROJECT_DIR/venv/bin/pip install --upgrade pip
sudo $PROJECT_DIR/venv/bin/pip install -r requirements.txt

# 7. 환경변수 파일 복사
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${YELLOW}환경변수 파일 생성...${NC}"
    sudo cp env.example $PROJECT_DIR/.env
    echo -e "${RED}주의: .env 파일을 편집하여 실제 설정값을 입력하세요!${NC}"
fi

# 8. Django 설정
echo -e "${YELLOW}Django 마이그레이션...${NC}"
cd $PROJECT_DIR
sudo $PROJECT_DIR/venv/bin/python manage.py collectstatic --noinput
sudo $PROJECT_DIR/venv/bin/python manage.py migrate

# 9. 권한 설정
echo -e "${YELLOW}권한 설정...${NC}"
sudo chown -R www-data:www-data $PROJECT_DIR
sudo chmod -R 755 $PROJECT_DIR
sudo chown -R www-data:www-data /var/log/$PROJECT_NAME
sudo chown -R www-data:www-data /var/run/celery
sudo chown -R www-data:www-data /var/log/celery

# 10. 시스템 서비스 설정
echo -e "${YELLOW}시스템 서비스 설정...${NC}"
sudo cp deploy/$PROJECT_NAME.service /etc/systemd/system/
sudo cp deploy/celery.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable $PROJECT_NAME
sudo systemctl enable celery

# 11. Nginx 설정
echo -e "${YELLOW}Nginx 설정...${NC}"
sudo cp deploy/nginx.conf /etc/nginx/sites-available/$PROJECT_NAME
sudo ln -sf /etc/nginx/sites-available/$PROJECT_NAME /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl enable nginx

# 12. Redis 시작
echo -e "${YELLOW}Redis 서비스 시작...${NC}"
sudo systemctl enable redis-server
sudo systemctl start redis-server

# 13. 서비스 시작
echo -e "${YELLOW}서비스 시작...${NC}"
sudo systemctl start $PROJECT_NAME
sudo systemctl start celery
sudo systemctl restart nginx

# 14. 방화벽 설정 (UFW)
echo -e "${YELLOW}방화벽 설정...${NC}"
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw allow 8001  # Django 애플리케이션 포트 추가
sudo ufw --force enable

echo -e "${GREEN}배포 완료!${NC}"
echo -e "${YELLOW}다음 단계를 진행하세요:${NC}"
echo "1. .env 파일을 편집하여 실제 설정값 입력"
echo "2. deploy/nginx.conf에서 도메인명을 실제 도메인으로 변경"
echo "3. SSL 인증서 설정 (Let's Encrypt 권장)"
echo "4. 관리자 계정 생성: sudo $PROJECT_DIR/venv/bin/python $PROJECT_DIR/manage.py createsuperuser"
echo "5. 서비스 상태 확인:"
echo "   - sudo systemctl status $PROJECT_NAME"
echo "   - sudo systemctl status celery"
echo "   - sudo systemctl status nginx"
echo ""
echo -e "${GREEN}애플리케이션 포트: 8001 (Nginx를 통해 80/443 포트로 서비스)${NC}" 