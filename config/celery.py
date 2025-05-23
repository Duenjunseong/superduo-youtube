import os
from celery import Celery

# 'DJANGO_SETTINGS_MODULE' 환경 변수를 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Celery 앱 생성
app = Celery('django_youtube')

# 설정 모듈에서 Celery 관련 설정값 가져오기
app.config_from_object('django.conf:settings', namespace='CELERY')

# Django 앱 설정에서 작업(Task)들을 자동으로 발견
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}') 