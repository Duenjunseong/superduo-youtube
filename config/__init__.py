# Celery 앱을 이 파일에서 가져와서 Django가 시작될 때 Celery 앱도 함께 로드

from .celery import app as celery_app

__all__ = ('celery_app',)

