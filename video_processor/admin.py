# video_processor/admin.py
from django.contrib import admin
from .models import TaskGroup, ProcessingJob, VideoSegment

@admin.register(TaskGroup)
class TaskGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'status', 'created_at', 'get_job_count')
    list_filter = ('status', 'user')
    search_fields = ('name', 'description', 'user__username')
    readonly_fields = ('group_id', 'created_at', 'updated_at')

    def get_job_count(self, obj):
        return obj.jobs.count()
    get_job_count.short_description = '연관된 작업 수'

@admin.register(ProcessingJob)
class ProcessingJobAdmin(admin.ModelAdmin):
    list_display = ('job_id', 'video_title_short', 'group', 'youtube_url_short', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'group')
    search_fields = ('youtube_url', 'video_title', 'group__name')
    readonly_fields = ('job_id', 'downloaded_video_path', 'created_at', 'updated_at')
    autocomplete_fields = ['group'] # TaskGroup 검색 기능

    def video_title_short(self, obj):
        if obj.video_title:
            return obj.video_title[:50] + '...' if len(obj.video_title) > 50 else obj.video_title
        return '제목 미탐지'
    video_title_short.short_description = '비디오 제목'

    def youtube_url_short(self, obj):
        return obj.youtube_url[:50] + '...' if len(obj.youtube_url) > 50 else obj.youtube_url
    youtube_url_short.short_description = 'YouTube URL'


@admin.register(VideoSegment)
class VideoSegmentAdmin(admin.ModelAdmin):
    list_display = ('segment_id', 'job_id_display', 'start_time', 'end_time', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('job__job_id', 'output_filename_prefix')
    readonly_fields = ('segment_id', 'processed_file_path', 'created_at', 'updated_at')
    # raw_id_fields = ['job'] # Job이 많을 경우 드롭다운 대신 ID 직접 입력

    def job_id_display(self, obj):
        return obj.job.job_id
    job_id_display.short_description = 'Parent Job ID'
