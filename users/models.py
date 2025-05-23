from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """확장된 사용자 모델"""
    # 추가 필드 정의
    bio = models.TextField(_("자기소개"), blank=True, default="")
    
    class Meta(AbstractUser.Meta):
        swappable = "AUTH_USER_MODEL"
        
    def __str__(self):
        return self.username
        
    def get_full_name(self):
        """사용자의 전체 이름 반환"""
        return f"{self.first_name} {self.last_name}".strip() or self.username
