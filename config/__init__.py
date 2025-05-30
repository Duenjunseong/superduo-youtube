# Django의 기본 설정을 위한 초기화 파일

try:
    # Celery가 설치된 경우에만 import
    from .celery import app as celery_app
    __all__ = ('celery_app',)
except ImportError:
    # Celery가 설치되지 않은 경우 무시
    pass

