import uuid
from django.db import models
from django.conf import settings
from taggit.managers import TaggableManager
from taggit.models import GenericUUIDTaggedItemBase, TaggedItemBase
from django.utils.translation import gettext_lazy as _

# Create your models here.

class TaskGroup(models.Model):
    STATUS_CHOICES = [
        ('ACTIVE', '활성'),
        ('ARCHIVED', '보관됨'),
    ]
    group_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='task_groups')
    workspace = models.ForeignKey(
        'workspace.Workspace', 
        on_delete=models.CASCADE, 
        related_name='task_groups',
        null=True, 
        blank=True,
        verbose_name='워크스페이스'
    )
    name = models.CharField(max_length=255, verbose_name='그룹명')
    description = models.TextField(blank=True, null=True, verbose_name='설명')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        workspace_name = f" ({self.workspace.name})" if self.workspace else ""
        return f"{self.name}{workspace_name} (User: {self.user.username if hasattr(self.user, 'username') else self.user.pk})"

    def can_user_access(self, user):
        """사용자가 이 그룹에 접근할 수 있는지 확인"""
        # 개인 그룹인 경우 (workspace가 없는 경우)
        if not self.workspace:
            return self.user == user
        
        # 워크스페이스 그룹인 경우
        return self.workspace.has_permission(user, 'view')

    def can_user_edit(self, user):
        """사용자가 이 그룹을 편집할 수 있는지 확인"""
        # 개인 그룹인 경우
        if not self.workspace:
            return self.user == user
        
        # 워크스페이스 그룹인 경우
        return self.workspace.has_permission(user, 'edit')

    class Meta:
        ordering = ['-created_at']



class UUIDTaggedItem(GenericUUIDTaggedItemBase, TaggedItemBase):
    """uuid를 id로 갖는 태그를 사용하는 모델을 위해 필요함."""
    # If you only inherit GenericUUIDTaggedItemBase, you need to define
    # a tag field. e.g.
    # tag = models.ForeignKey(Tag, related_name="uuid_tagged_items", on_delete=models.CASCADE)

    class Meta:
        verbose_name = _("Tag")
        verbose_name_plural = _("Tags")

class ProcessingJob(models.Model):
    STATUS_CHOICES = [
        ('PENDING', '대기 중'),
        ('DOWNLOADING', '다운로드 중'),
        ('PROCESSING', '처리 중'),
        ('COMPLETED', '완료됨'),
        ('FAILED', '실패'),
    ]

    job_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='processing_jobs', null=True, blank=True, verbose_name='요청 사용자')
    workspace = models.ForeignKey(
        'workspace.Workspace', 
        on_delete=models.CASCADE, 
        related_name='processing_jobs',
        null=True, 
        blank=True,
        verbose_name='워크스페이스'
    )
    group = models.ForeignKey(TaskGroup, related_name='jobs', on_delete=models.CASCADE, null=True, blank=True, verbose_name='소속 그룹')
    youtube_url = models.URLField(max_length=2048)
    video_title = models.CharField(max_length=500, blank=True, null=True, verbose_name='비디오 제목')
    downloaded_video_path = models.CharField(max_length=1024, blank=True, null=True) # yt-dlp로 다운로드된 원본 영상 경로
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    auto_start = models.BooleanField(default=True, verbose_name='자동 시작 여부') # True: 즉시 처리 시작, False: 대기 상태로 생성
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    tags = TaggableManager(blank=True, verbose_name='태그', through=UUIDTaggedItem)

    def __str__(self):
        workspace_name = f" ({self.workspace.name})" if self.workspace else ""
        return f"Job {self.job_id}{workspace_name} - {self.status}"

    def can_user_access(self, user):
        """사용자가 이 작업에 접근할 수 있는지 확인"""
        # 개인 작업인 경우 (workspace가 없는 경우)
        if not self.workspace:
            return self.user == user
        
        # 워크스페이스 작업인 경우
        return self.workspace.has_permission(user, 'view')

    def can_user_edit(self, user):
        """사용자가 이 작업을 편집할 수 있는지 확인"""
        # 개인 작업인 경우
        if not self.workspace:
            return self.user == user
        
        # 워크스페이스 작업인 경우
        return self.workspace.has_permission(user, 'edit')

    def save(self, *args, **kwargs):
        # group이 설정되어 있고 workspace가 설정되지 않은 경우, group의 workspace를 사용
        if self.group and not self.workspace:
            self.workspace = self.group.workspace
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']

class VideoSegment(models.Model):
    STATUS_CHOICES = [
        ('PENDING', '대기 중'),
        ('PROCESSING', '처리 중'),
        ('COMPLETED', '완료됨'),
        ('FAILED', '실패'),
    ]

    segment_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(ProcessingJob, related_name='segments', on_delete=models.CASCADE)
    start_time = models.BigIntegerField(verbose_name='시작 시간(초)')  # CharField에서 BigIntegerField로 변경
    end_time = models.BigIntegerField(verbose_name='종료 시간(초)')    # CharField에서 BigIntegerField로 변경
    output_filename_prefix = models.CharField(max_length=255, blank=True, null=True) # 사용자가 지정하는 ID 또는 자동 생성
    # category 필드는 TaskGroup의 name이나 description으로 대체되거나, Job 레벨에서 관리될 수 있으므로 여기서는 일단 유지 또는 제거 고려
    # category = models.CharField(max_length=100, blank=True, null=True)
    processed_file_path = models.CharField(max_length=1024, blank=True, null=True) # 잘린 영상 파일 경로
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Segment {self.segment_id} for Job {self.job.job_id} - {self.status}"

    def can_user_access(self, user):
        """사용자가 이 세그먼트에 접근할 수 있는지 확인"""
        return self.job.can_user_access(user)

    class Meta:
        ordering = ['-created_at']
