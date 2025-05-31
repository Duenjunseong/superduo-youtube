from django.contrib import admin
from .models import TrendingVideo, TrendingStats, FavoriteShorts

@admin.register(TrendingVideo)
class TrendingVideoAdmin(admin.ModelAdmin):
    list_display = ('title', 'channel_title', 'trending_rank', 'trending_date', 'is_shorts', 'view_count', 'category')
    list_filter = ('is_shorts', 'trending_date', 'category', 'region_code')
    search_fields = ('title', 'channel_title', 'youtube_id')
    readonly_fields = ('trending_id', 'created_at', 'updated_at')
    ordering = ('-trending_date', 'trending_rank')
    list_per_page = 25

    fieldsets = (
        ('기본 정보', {
            'fields': ('youtube_id', 'title', 'description', 'channel_title', 'channel_id')
        }),
        ('통계', {
            'fields': ('view_count', 'like_count', 'comment_count')
        }),
        ('메타데이터', {
            'fields': ('published_at', 'duration', 'thumbnail_url', 'category', 'tags')
        }),
        ('트렌딩 정보', {
            'fields': ('trending_rank', 'trending_date', 'region_code', 'is_shorts')
        }),
        ('시스템', {
            'fields': ('trending_id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(TrendingStats)
class TrendingStatsAdmin(admin.ModelAdmin):
    list_display = ('collection_date', 'total_videos_collected', 'successful_collections', 'failed_collections', 'shorts_collected')
    list_filter = ('collection_date',)
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-collection_date',)

@admin.register(FavoriteShorts)
class FavoriteShortsAdmin(admin.ModelAdmin):
    list_display = ('get_video_title', 'user', 'workspace', 'favorited_rank', 'created_at')
    list_filter = ('created_at', 'workspace', 'favorited_rank')
    search_fields = ('trending_video__title', 'trending_video__channel_title', 'user__username', 'note')
    readonly_fields = ('favorite_id', 'created_at', 'updated_at')
    ordering = ('-created_at',)
    list_per_page = 25

    fieldsets = (
        ('기본 정보', {
            'fields': ('user', 'workspace', 'trending_video')
        }),
        ('즐겨찾기 정보', {
            'fields': ('note', 'tags', 'favorited_rank', 'favorited_view_count')
        }),
        ('시스템', {
            'fields': ('favorite_id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_video_title(self, obj):
        return obj.trending_video.title[:50] + '...' if len(obj.trending_video.title) > 50 else obj.trending_video.title
    get_video_title.short_description = '영상 제목'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('trending_video', 'user', 'workspace')
