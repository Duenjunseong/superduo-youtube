from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """확장된 사용자 모델"""
    # 추가 필드 정의
    bio = models.TextField(_("자기소개"), blank=True, default="")
    
    # 현재 워크스페이스 (None이면 개인 모드)
    current_workspace = models.ForeignKey(
        'workspace.Workspace',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='current_users',
        verbose_name=_("현재 워크스페이스"),
        help_text=_("사용자가 현재 작업 중인 워크스페이스입니다. 비어있으면 개인 모드입니다.")
    )
    
    class Meta(AbstractUser.Meta):
        swappable = "AUTH_USER_MODEL"
        
    def __str__(self):
        return self.username
        
    def get_full_name(self):
        """사용자의 전체 이름 반환"""
        return f"{self.first_name} {self.last_name}".strip() or self.username
        
    def is_in_workspace_mode(self):
        """현재 워크스페이스 모드인지 확인"""
        return self.current_workspace is not None
        
    def is_in_personal_mode(self):
        """현재 개인 모드인지 확인"""
        return self.current_workspace is None
        
    def get_accessible_workspaces(self):
        """접근 가능한 워크스페이스 목록 반환"""
        from workspace.models import Workspace
        return Workspace.objects.filter(
            models.Q(owner=self) |
            models.Q(memberships__user=self, memberships__status='ACTIVE'),
            status='ACTIVE'
        ).distinct().order_by('name')
        
    def can_access_workspace(self, workspace):
        """특정 워크스페이스에 접근할 수 있는지 확인"""
        if not workspace:
            return True  # 개인 모드는 항상 접근 가능
        return workspace.has_permission(self, 'view')
        
    def switch_to_workspace(self, workspace):
        """워크스페이스로 전환"""
        if workspace and not self.can_access_workspace(workspace):
            return False
        self.current_workspace = workspace
        self.save(update_fields=['current_workspace'])
        return True
        
    def switch_to_personal_mode(self):
        """개인 모드로 전환"""
        self.current_workspace = None
        self.save(update_fields=['current_workspace'])
        return True
