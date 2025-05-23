# Gunicorn 설정 파일
import multiprocessing
import os

# 서버 설정
bind = "0.0.0.0:8001"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
preload_app = True
timeout = 30
keepalive = 2

# 로깅 설정
accesslog = "./logs/gunicorn_access.log"
errorlog = "./logs/gunicorn_error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# 프로세스 이름
proc_name = "youtube_downloader"

# 보안 설정
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# 파일 업로드 크기 제한
max_requests = 0  # 무제한 요청 처리

# 사용자 및 그룹 (배포 시 설정)
# user = "www-data"
# group = "www-data"

# 환경 변수
raw_env = [
    "DJANGO_SETTINGS_MODULE=config.settings",
] 