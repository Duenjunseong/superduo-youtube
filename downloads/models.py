from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
import uuid

class Tag(models.Model):
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=20, default='pastel-blue')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tags')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('name', 'user')
        ordering = ['name']

    def __str__(self):
        return self.name

class Job(models.Model):
    STATUS_CHOICES = (
        ('queued', '대기 중'),
        ('running', '진행 중'),
        ('done', '완료'),
        ('cancelled', '취소'),
        ('pending', '대기 중'),  # 기존 호환성 유지
        ('processing', '처리 중'),  # 기존 호환성 유지
        ('completed', '완료'),  # 기존 호환성 유지
        ('failed', '실패'),  # 기존 호환성 유지
    )
    
    QUALITY_CHOICES = (
        ('highest', '최상 품질'),
        ('720p', '720p'),
        ('480p', '480p'),
        ('360p', '360p'),
        ('audio', '오디오만'),
    )
    
    # id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='jobs')
    url = models.URLField(max_length=2000)
    src_url = models.URLField(max_length=2000, blank=True, null=True)  # links.html용 추가 필드
    title = models.CharField(max_length=500, blank=True, null=True)  # YouTube 영상 제목
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    quality = models.CharField(max_length=20, choices=QUALITY_CHOICES, default='highest')
    task_id = models.CharField(max_length=100, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    error_msg = models.TextField(blank=True, null=True)  # 호환성을 위한 필드
    memo = models.TextField(blank=True, null=True)
    progress = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finished_at = models.DateTimeField(blank=True, null=True)  # 작업 완료/취소 시간
    tags = models.ManyToManyField(Tag, related_name='jobs', blank=True)
    
    def __str__(self):
        return f"Job {self.id} - {self.url[:50]}"
    
    def get_status_display(self):
        for key, value in self.STATUS_CHOICES:
            if key == self.status:
                return value
        return self.status
    
    def get_quality_display(self):
        for key, value in self.QUALITY_CHOICES:
            if key == self.quality:
                return value
        return self.quality
    
    class Meta:
        ordering = ['-created_at']

class File(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='files')
    filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=1000)
    file_size = models.BigIntegerField(default=0)
    file_type = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.filename
    
    class Meta:
        ordering = ['-created_at']

class DownloadJob(models.Model):
    STATUS_CHOICES = [
        ('pending', '대기 중'),
        ('queued', '대기 중'),
        ('running', '진행 중'),
        ('processing', '처리 중'),
        ('completed', '완료'),
        ('done', '완료'),
        ('cancelled', '취소'),
        ('failed', '실패'),
    ]
    
    QUALITY_CHOICES = [
        ('best', '최고 품질'),
        ('1080p', '1080p'),
        ('720p', '720p'),
        ('480p', '480p'),
        ('360p', '360p'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    src_url = models.URLField()
    title = models.CharField(max_length=200, blank=True)
    quality = models.CharField(max_length=10, choices=QUALITY_CHOICES, default='best')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress = models.FloatField(default=0)
    error_msg = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    memo = models.TextField(blank=True)
    tags = models.ManyToManyField(Tag, blank=True)
    
    def __str__(self):
        return f"{self.title or self.src_url} ({self.get_status_display()})"
