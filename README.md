# YouTube 다운로더

Django 기반의 YouTube 영상 다운로드 웹 애플리케이션입니다. 사용자는 YouTube URL을 입력하여 영상을 다운로드하고, 태그를 통해 관리할 수 있습니다.

## 주요 기능

- 🎥 YouTube 영상 다운로드 (다양한 품질 지원)
- 🏷️ 태그 시스템으로 다운로드 관리
- 📊 실시간 다운로드 진행률 표시
- 👤 사용자 인증 및 개인 작업 관리
- 🔄 백그라운드 작업 처리 (Celery)
- 📱 반응형 웹 디자인

## 기술 스택

- **Backend**: Django 5.0.6, Python 3.12
- **Database**: PostgreSQL (프로덕션), SQLite (개발)
- **Task Queue**: Celery + Redis
- **Web Server**: Nginx + Gunicorn
- **Frontend**: Bootstrap 5, jQuery
- **Download Engine**: yt-dlp

## 포트 설정

- **로컬 개발**: 8000 포트 (Django runserver)
- **Docker 배포**: 8000 포트 (Gunicorn in Container) → 외부 Nginx 리버스 프록시로 80/443 포트 서비스
- **수동 배포**: 8001 포트 (Gunicorn) → Nginx 리버스 프록시로 80/443 포트 서비스

## 시스템 요구사항

### 최소 요구사항

- Python 3.10+
- 4GB RAM
- 20GB 디스크 공간
- Ubuntu 20.04+ 또는 CentOS 8+

### 권장 요구사항

- Python 3.12
- 8GB RAM
- 100GB SSD 디스크
- Ubuntu 22.04 LTS

## 마이그레이션 관리

이 프로젝트는 **동적 마이그레이션 생성** 방식을 사용합니다. 마이그레이션 파일들은 Git에 저장되지 않고, 배포할 때마다 새로 생성됩니다.

### 🔄 마이그레이션 파일 관리 방식

- **Git에 저장되지 않음**: `*/migrations/0*.py` 파일들은 `.gitignore`에 포함
- **동적 생성**: 배포할 때마다 현재 모델 상태에 맞게 새로 생성
- **`__init__.py` 보존**: 마이그레이션 디렉토리 구조는 유지

### 📝 개발 중 마이그레이션 생성

```bash
# 모델 변경 후 마이그레이션 생성 및 적용
./make_migrations.sh
```

### 🚀 배포 시 마이그레이션

```bash
# 1. 일반 배포 (Docker 캐시 사용으로 빠름)
./deploy.sh

# 2. 전체 빌드 배포 (Docker 캐시 무시, 느리지만 확실)
./deploy.sh --full-build

# 3. 빠른 배포 (Docker 빌드 없이 컨테이너만 재시작)
./quick_deploy.sh
```

**배포 시 자동 처리 과정:**

1. 기존 마이그레이션 파일 삭제
2. 현재 모델 상태로 새 마이그레이션 생성
3. 데이터베이스에 마이그레이션 적용

### ⚡ 배포 성능 비교

| 배포 방법                  | 소요 시간 | 사용 시기              | 특징             |
| -------------------------- | --------- | ---------------------- | ---------------- |
| `./quick_deploy.sh`        | ~30초     | 소스 코드만 변경       | Docker 빌드 없음 |
| `./deploy.sh`              | ~2-3분    | 일반적인 변경          | Docker 캐시 활용 |
| `./deploy.sh --full-build` | ~5-10분   | 의존성 변경, 문제 해결 | 전체 재빌드      |

### ⚠️ 주의사항

- **프로덕션 데이터 손실 방지**: 중요한 데이터는 배포 전 백업
- **모델 변경 신중히**: 기존 데이터와 호환되지 않는 변경은 피하기
- **테스트 환경 활용**: 프로덕션 적용 전 테스트 환경에서 검증

## 로컬 개발 환경 설정

```bash
# 1. 프로젝트 클론
git clone https://github.com/yourusername/youtube_downloader.git
cd youtube_downloader

# 2. 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 로컬 환경변수 파일 생성
cp env.example .env.local

# 5. 데이터베이스 마이그레이션
python manage.py migrate

# 6. 관리자 계정 생성
python manage.py createsuperuser

# 7. 로컬 개발 서버 실행 (8000 포트)
python manage.py runserver

# 8. 또는 로컬 설정으로 실행
python manage.py runserver --settings=config.local_settings
```

## 설치 및 배포

### 방법 1: 자동 배포 스크립트 사용 (권장)

```bash
# 1. 프로젝트 클론
git clone https://github.com/yourusername/youtube_downloader.git
cd youtube_downloader

# 2. 배포 스크립트 실행 (Django는 8001 포트로 구동됨)
chmod +x deploy/deploy.sh
sudo ./deploy/deploy.sh

# 3. 환경변수 설정
sudo nano /var/www/youtube_downloader/.env
# env.example을 참고하여 실제 값으로 수정

# 4. Nginx 설정에서 도메인명 변경
sudo nano /etc/nginx/sites-available/youtube_downloader
# yourdomain.com을 실제 도메인으로 변경

# 5. 관리자 계정 생성
sudo /var/www/youtube_downloader/venv/bin/python /var/www/youtube_downloader/manage.py createsuperuser

# 6. SSL 인증서 설정 (Let's Encrypt)
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

### 방법 2: Docker Compose 사용 (외부 Nginx 리버스 프록시)

```bash
# 1. 프로젝트 클론
git clone https://github.com/yourusername/youtube_downloader.git
cd youtube_downloader

# 2. 환경변수 설정
cp env.example .env
# .env 파일을 편집하여 실제 값으로 수정

# 3. Docker Compose로 실행 (Django는 8000 포트로 구동됨)
docker-compose up -d

# 4. 관리자 계정 생성
docker-compose exec web python manage.py createsuperuser

# 5. 외부 Nginx 설정 (서버에 설치된 nginx 사용)
sudo cp deploy/nginx.conf /etc/nginx/sites-available/youtube_downloader
sudo nano /etc/nginx/sites-available/youtube_downloader  # 도메인명 변경
sudo ln -s /etc/nginx/sites-available/youtube_downloader /etc/nginx/sites-enabled/
sudo nginx -t  # 설정 파일 검증
sudo systemctl reload nginx
```

**주의사항:**

- Docker Compose는 nginx 컨테이너 없이 Django 애플리케이션을 8000 포트로 실행합니다
- 서버에 설치된 nginx가 도커 컨테이너로 리버스 프록시합니다
- 정적/미디어 파일은 도커 볼륨에서 직접 서빙됩니다
- 볼륨 경로: `/var/lib/docker/volumes/django_youtube_*_files/_data/`

### 방법 3: 수동 설치

#### 1. 시스템 패키지 설치

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip python3-venv postgresql postgresql-contrib nginx redis-server git

# CentOS/RHEL
sudo yum install python3 python3-pip postgresql postgresql-server nginx redis git
```

#### 2. PostgreSQL 설정

```bash
sudo -u postgres createdb youtube_downloader
sudo -u postgres createuser --interactive --pwprompt youtube_user
```

#### 3. 프로젝트 설정

```bash
# 프로젝트 클론
git clone https://github.com/yourusername/youtube_downloader.git
cd youtube_downloader

# 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp env.example .env
# .env 파일 편집

# 데이터베이스 마이그레이션
python manage.py migrate

# 정적 파일 수집
python manage.py collectstatic

# 관리자 계정 생성
python manage.py createsuperuser
```

#### 4. 서비스 설정

```bash
# Systemd 서비스 파일 복사
sudo cp deploy/youtube_downloader.service /etc/systemd/system/
sudo cp deploy/celery.service /etc/systemd/system/

# 서비스 활성화 및 시작
sudo systemctl daemon-reload
sudo systemctl enable youtube_downloader celery
sudo systemctl start youtube_downloader celery

# Nginx 설정 (도메인명 수정 필요)
sudo cp deploy/nginx.conf /etc/nginx/sites-available/youtube_downloader
sudo nano /etc/nginx/sites-available/youtube_downloader  # 도메인명 변경
sudo ln -s /etc/nginx/sites-available/youtube_downloader /etc/nginx/sites-enabled/
sudo systemctl restart nginx
```

## 환경변수 설정

`.env` 파일에 다음 환경변수들을 설정해야 합니다:

```bash
# Django 설정
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# 데이터베이스 (PostgreSQL)
DATABASE_URL=postgres://username:password@localhost:5432/youtube_downloader

# Redis (Celery)
REDIS_URL=redis://localhost:6379/0

# 파일 경로 (로컬 스토리지 사용)
MEDIA_ROOT=/var/www/youtube_downloader/media
STATIC_ROOT=/var/www/youtube_downloader/static

# 로깅
LOG_LEVEL=INFO
LOG_FILE=./logs/django.log

# 보안 설정 (HTTPS 사용 시)
SECURE_SSL_REDIRECT=True
CSRF_COOKIE_SECURE=True
SESSION_COOKIE_SECURE=True
```

## 관리 및 모니터링

### 서비스 상태 확인

```bash
# 서비스 상태 확인
sudo systemctl status youtube_downloader
sudo systemctl status celery
sudo systemctl status nginx
sudo systemctl status redis

# 포트 확인
sudo netstat -tlnp | grep :8001  # Django 애플리케이션
sudo netstat -tlnp | grep :80    # Nginx HTTP
sudo netstat -tlnp | grep :443   # Nginx HTTPS

# 로그 확인
sudo journalctl -u youtube_downloader -f
sudo journalctl -u celery -f
tail -f /var/log/youtube_downloader/django.log
```

### 업데이트 배포

```bash
cd /var/www/youtube_downloader
sudo git pull origin main
sudo /var/www/youtube_downloader/venv/bin/pip install -r requirements.txt
sudo /var/www/youtube_downloader/venv/bin/python manage.py migrate
sudo /var/www/youtube_downloader/venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart youtube_downloader celery
```

### 백업

```bash
# 데이터베이스 백업
sudo -u postgres pg_dump youtube_downloader > backup_$(date +%Y%m%d).sql

# 미디어 파일 백업 (로컬 스토리지)
sudo tar -czf media_backup_$(date +%Y%m%d).tar.gz /var/www/youtube_downloader/media/
```

## 보안 설정

### 방화벽 설정

```bash
sudo ufw allow 22      # SSH
sudo ufw allow 80      # HTTP
sudo ufw allow 443     # HTTPS
sudo ufw allow 8001    # Django 애플리케이션 (필요시)
sudo ufw enable
```

### SSL 인증서 (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# 자동 갱신 설정
sudo crontab -e
# 다음 라인 추가:
# 0 12 * * * /usr/bin/certbot renew --quiet
```

## 문제 해결

### 일반적인 문제들

1. **Celery 작업이 실행되지 않음**

   ```bash
   sudo systemctl restart redis
   sudo systemctl restart celery
   ```

2. **정적 파일이 로드되지 않음**

   ```bash
   python manage.py collectstatic --noinput
   sudo systemctl restart nginx
   ```

3. **권한 오류**

   ```bash
   sudo chown -R www-data:www-data /var/www/youtube_downloader
   sudo chmod -R 755 /var/www/youtube_downloader
   ```

4. **포트 충돌**

   ```bash
   # 8001 포트 사용 확인
   sudo netstat -tlnp | grep :8001

   # 필요시 다른 포트로 변경
   sudo nano /var/www/youtube_downloader/gunicorn.conf.py
   sudo nano /etc/nginx/sites-available/youtube_downloader
   ```

5. **yt-dlp 업데이트**
   ```bash
   source /var/www/youtube_downloader/venv/bin/activate
   pip install --upgrade yt-dlp
   sudo systemctl restart youtube_downloader celery
   ```

### 로그 분석

```bash
# Django 애플리케이션 로그
tail -f /var/log/youtube_downloader/django.log

# Nginx 로그
tail -f /var/log/nginx/youtube_downloader_access.log
tail -f /var/log/nginx/youtube_downloader_error.log

# 시스템 로그
sudo journalctl -u youtube_downloader -f
sudo journalctl -u celery -f
```

## 개발 팁

### 로컬 개발 환경에서 다른 설정 사용하기

```bash
# 로컬 개발용 설정으로 실행 (8000 포트)
python manage.py runserver --settings=config.local_settings

# Celery 워커도 로컬 설정으로 실행
celery -A config worker --loglevel=info --settings=config.local_settings
```

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 기여하기

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 지원

문제가 발생하면 GitHub Issues에 보고해주세요.
