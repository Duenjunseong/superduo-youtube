from django.db import models
from django.utils import timezone
import uuid
from datetime import date

class TrendingVideo(models.Model):
    """유튜브 인기 급상승 동영상 모델"""
    
    CATEGORY_CHOICES = [
        ('music', '음악'),
        ('gaming', '게임'),
        ('entertainment', '엔터테인먼트'),
        ('sports', '스포츠'),
        ('news', '뉴스'),
        ('education', '교육'),
        ('tech', '과학 기술'),
        ('comedy', '코미디'),
        ('lifestyle', '라이프스타일'),
        ('other', '기타'),
    ]
    
    trending_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    youtube_id = models.CharField(max_length=20, help_text="YouTube 동영상 ID")
    title = models.CharField(max_length=500, help_text="동영상 제목")
    description = models.TextField(blank=True, help_text="동영상 설명")
    channel_title = models.CharField(max_length=200, help_text="채널명")
    channel_id = models.CharField(max_length=50, help_text="채널 ID")
    
    # 통계 정보
    view_count = models.BigIntegerField(default=0, help_text="조회수")
    like_count = models.BigIntegerField(default=0, help_text="좋아요 수")
    comment_count = models.BigIntegerField(default=0, help_text="댓글 수")
    
    # 메타데이터
    published_at = models.DateTimeField(help_text="YouTube 발행일")
    duration = models.CharField(max_length=20, blank=True, help_text="영상 길이 (ISO 8601 format)")
    thumbnail_url = models.URLField(blank=True, help_text="썸네일 URL")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    tags = models.JSONField(default=list, blank=True, help_text="태그 목록")
    
    # 트렌딩 정보
    trending_rank = models.PositiveIntegerField(help_text="트렌딩 순위")
    trending_date = models.DateField(help_text="트렌딩 수집 날짜")
    region_code = models.CharField(max_length=2, default='KR', help_text="지역 코드")
    
    # 쇼츠 여부
    is_shorts = models.BooleanField(default=False, help_text="쇼츠 영상 여부")
    
    # 시스템 필드
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'youtube_trending_videos'
        verbose_name = '인기 급상승 동영상'
        verbose_name_plural = '인기 급상승 동영상'
        ordering = ['-trending_date', 'trending_rank']
        indexes = [
            models.Index(fields=['trending_date', 'trending_rank']),
            models.Index(fields=['is_shorts', 'trending_date']),
            models.Index(fields=['category', 'trending_date']),
            models.Index(fields=['youtube_id']),
        ]
        unique_together = ['youtube_id', 'trending_date']
    
    def __str__(self):
        return f"{self.title} (#{self.trending_rank} - {self.trending_date})"
    
    @property
    def youtube_url(self):
        """YouTube URL 반환"""
        return f"https://www.youtube.com/watch?v={self.youtube_id}"
    
    @property
    def formatted_view_count(self):
        """포맷팅된 조회수 반환"""
        if self.view_count >= 1000000:
            return f"{self.view_count / 1000000:.1f}M"
        elif self.view_count >= 1000:
            return f"{self.view_count / 1000:.1f}K"
        return str(self.view_count)
    
    @property
    def formatted_duration(self):
        """포맷팅된 영상 길이 반환"""
        if not self.duration:
            return "Unknown"
        
        # ISO 8601 duration 파싱 (예: PT4M13S -> 4:13)
        import re
        pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
        match = re.match(pattern, self.duration)
        if match:
            hours, minutes, seconds = match.groups()
            hours = int(hours) if hours else 0
            minutes = int(minutes) if minutes else 0
            seconds = int(seconds) if seconds else 0
            
            if hours > 0:
                return f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                return f"{minutes}:{seconds:02d}"
        
        return self.duration


class TrendingStats(models.Model):
    """트렌딩 수집 통계"""
    collection_date = models.DateField("수집 날짜", default=date.today)
    total_videos_collected = models.IntegerField("수집된 총 비디오 수", default=0)
    successful_collections = models.IntegerField("성공한 수집 횟수", default=0)
    failed_collections = models.IntegerField("실패한 수집 횟수", default=0)
    shorts_collected = models.IntegerField("수집된 쇼츠 수", default=0)
    created_at = models.DateTimeField("생성 시간", auto_now_add=True)
    updated_at = models.DateTimeField("수정 시간", auto_now=True)
    
    class Meta:
        db_table = 'trending_stats'
        verbose_name = "트렌딩 수집 통계"
        verbose_name_plural = "트렌딩 수집 통계들"
        unique_together = ['collection_date']  # 날짜별로 하나의 통계만
        
    def __str__(self):
        return f"{self.collection_date} 통계 (총 {self.total_videos_collected}개)"


class FavoriteShorts(models.Model):
    """인기 쇼츠 즐겨찾기 모델 (워크스페이스별)"""
    
    favorite_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='favorite_shorts',
        verbose_name='사용자'
    )
    workspace = models.ForeignKey(
        'workspace.Workspace',
        on_delete=models.CASCADE,
        related_name='favorite_shorts',
        null=True,
        blank=True,
        verbose_name='워크스페이스',
        help_text='워크스페이스별 즐겨찾기 관리. null이면 개인 즐겨찾기'
    )
    trending_video = models.ForeignKey(
        TrendingVideo,
        on_delete=models.CASCADE,
        related_name='favorites',
        verbose_name='트렌딩 비디오'
    )
    note = models.TextField(
        blank=True,
        null=True,
        max_length=500,
        verbose_name='메모',
        help_text='즐겨찾기에 대한 개인 메모'
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        verbose_name='개인 태그',
        help_text='개인적으로 추가한 태그들'
    )
    
    # 즐겨찾기 시점의 정보 저장 (나중에 비교용)
    favorited_rank = models.PositiveIntegerField(
        verbose_name='즐겨찾기 당시 순위',
        help_text='즐겨찾기를 추가한 시점의 트렌딩 순위'
    )
    favorited_view_count = models.BigIntegerField(
        verbose_name='즐겨찾기 당시 조회수',
        help_text='즐겨찾기를 추가한 시점의 조회수'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='즐겨찾기 추가일')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일')
    
    class Meta:
        db_table = 'favorite_shorts'
        verbose_name = '인기 쇼츠 즐겨찾기'
        verbose_name_plural = '인기 쇼츠 즐겨찾기들'
        ordering = ['-created_at']
        unique_together = ['user', 'workspace', 'trending_video']
        indexes = [
            models.Index(fields=['user', 'workspace']),
            models.Index(fields=['trending_video']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        workspace_name = f" ({self.workspace.name})" if self.workspace else " (개인)"
        return f"{self.trending_video.title[:50]}... - {self.user.username}{workspace_name}"
    
    @property
    def view_count_change(self):
        """즐겨찾기 당시와 현재 조회수 비교"""
        return self.trending_video.view_count - self.favorited_view_count
    
    @property
    def rank_change(self):
        """즐겨찾기 당시와 현재 순위 비교 (음수: 순위 상승, 양수: 순위 하락)"""
        return self.trending_video.trending_rank - self.favorited_rank
    
    def can_user_access(self, user):
        """사용자가 이 즐겨찾기에 접근할 수 있는지 확인"""
        # 개인 즐겨찾기인 경우
        if not self.workspace:
            return self.user == user
        
        # 워크스페이스 즐겨찾기인 경우
        return self.workspace.has_permission(user, 'view')
    
    def can_user_edit(self, user):
        """사용자가 이 즐겨찾기를 편집할 수 있는지 확인"""
        # 개인 즐겨찾기인 경우
        if not self.workspace:
            return self.user == user
        
        # 워크스페이스 즐겨찾기인 경우 (작성자이거나 편집 권한이 있는 경우)
        if self.user == user:
            return True
        return self.workspace.has_permission(user, 'edit')
