import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import os

def workspace_icon_upload_path(instance, filename):
    """워크스페이스 아이콘 업로드 경로"""
    ext = filename.split('.')[-1]
    filename = f'workspace_icon_{instance.workspace_id}.{ext}'
    return os.path.join('workspace_icons', filename)

class Workspace(models.Model):
    """워크스페이스 모델"""
    STATUS_CHOICES = [
        ('ACTIVE', '활성'),
        ('INACTIVE', '비활성'),
        ('ARCHIVED', '보관됨'),
    ]
    
    workspace_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True, verbose_name='워크스페이스명')
    description = models.TextField(blank=True, null=True, verbose_name='설명')
    icon = models.ImageField(
        upload_to=workspace_icon_upload_path, 
        blank=True, 
        null=True, 
        verbose_name='워크스페이스 아이콘',
        help_text='정사각형 이미지를 권장합니다 (권장 크기: 512x512px)'
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='owned_workspaces',
        verbose_name='소유자'
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ACTIVE')
    is_public = models.BooleanField(default=False, verbose_name='공개 여부')
    max_members = models.PositiveIntegerField(default=10, verbose_name='최대 멤버 수')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (Owner: {self.owner.username if hasattr(self.owner, 'username') else self.owner.pk})"

    @property
    def member_count(self):
        """현재 멤버 수"""
        return self.memberships.filter(status='ACTIVE').count()

    @property
    def is_full(self):
        """최대 멤버 수에 도달했는지 확인"""
        return self.member_count >= self.max_members

    @property
    def icon_url(self):
        """아이콘 URL 반환 (없으면 기본값)"""
        if self.icon and hasattr(self.icon, 'url'):
            return self.icon.url
        return None

    def get_user_role(self, user):
        """특정 사용자의 워크스페이스 내 역할 반환"""
        if self.owner == user:
            return 'OWNER'
        try:
            membership = self.memberships.get(user=user, status='ACTIVE')
            return membership.role
        except WorkspaceMembership.DoesNotExist:
            return None

    def has_permission(self, user, permission):
        """사용자의 권한 확인"""
        role = self.get_user_role(user)
        if not role:
            return False
        
        permissions = {
            'OWNER': ['view', 'edit', 'delete', 'invite', 'remove_member', 'manage_roles'],
            'ADMIN': ['view', 'edit', 'invite', 'remove_member'],
            'MEMBER': ['view'],
            'VIEWER': ['view'],
        }
        return permission in permissions.get(role, [])

    class Meta:
        ordering = ['-created_at']
        verbose_name = '워크스페이스'
        verbose_name_plural = '워크스페이스들'


class WorkspaceMembership(models.Model):
    """워크스페이스 멤버십 모델"""
    ROLE_CHOICES = [
        ('OWNER', '소유자'),
        ('ADMIN', '관리자'),
        ('MEMBER', '멤버'),
        ('VIEWER', '뷰어'),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE', '활성'),
        ('INACTIVE', '비활성'),
        ('REMOVED', '제거됨'),
    ]
    
    membership_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        Workspace, 
        on_delete=models.CASCADE, 
        related_name='memberships'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='workspace_memberships'
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='MEMBER')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ACTIVE')
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username if hasattr(self.user, 'username') else self.user.pk} - {self.workspace.name} ({self.get_role_display()})"

    class Meta:
        unique_together = ['workspace', 'user']
        ordering = ['-joined_at']
        verbose_name = '워크스페이스 멤버십'
        verbose_name_plural = '워크스페이스 멤버십들'


class Invitation(models.Model):
    """워크스페이스 초대 모델"""
    STATUS_CHOICES = [
        ('PENDING', '대기 중'),
        ('ACCEPTED', '수락됨'),
        ('DECLINED', '거절됨'),
        ('EXPIRED', '만료됨'),
        ('CANCELLED', '취소됨'),
    ]
    
    invitation_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        Workspace, 
        on_delete=models.CASCADE, 
        related_name='invitations'
    )
    inviter = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='sent_invitations',
        verbose_name='초대자'
    )
    invitee_email = models.EmailField(verbose_name='초대받을 이메일')
    invitee = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        related_name='received_invitations',
        null=True, 
        blank=True,
        verbose_name='초대받은 사용자'
    )
    role = models.CharField(
        max_length=10, 
        choices=WorkspaceMembership.ROLE_CHOICES[1:],  # OWNER 제외
        default='MEMBER'
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    message = models.TextField(blank=True, null=True, verbose_name='초대 메시지')
    expires_at = models.DateTimeField(verbose_name='만료 일시')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)  # 기본 7일 후 만료
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        """초대가 만료되었는지 확인"""
        return timezone.now() > self.expires_at

    def accept(self, user):
        """초대 수락"""
        if self.status != 'PENDING':
            raise ValueError("이미 처리된 초대입니다.")
        if self.is_expired:
            self.status = 'EXPIRED'
            self.save()
            raise ValueError("만료된 초대입니다.")
        if self.workspace.is_full:
            raise ValueError("워크스페이스가 가득 차서 초대를 수락할 수 없습니다.")
        
        # 멤버십 생성
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=user,
            role=self.role
        )
        
        self.status = 'ACCEPTED'
        self.invitee = user
        self.save()

    def decline(self, user):
        """초대 거절"""
        if self.status != 'PENDING':
            raise ValueError("이미 처리된 초대입니다.")
        
        self.status = 'DECLINED'
        self.invitee = user
        self.save()

    def cancel(self):
        """초대 취소"""
        if self.status != 'PENDING':
            raise ValueError("이미 처리된 초대입니다.")
        
        self.status = 'CANCELLED'
        self.save()

    def __str__(self):
        return f"Invitation to {self.invitee_email} for {self.workspace.name} ({self.get_status_display()})"

    class Meta:
        ordering = ['-created_at']
        verbose_name = '워크스페이스 초대'
        verbose_name_plural = '워크스페이스 초대들'
