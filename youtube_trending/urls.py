from django.urls import path
from .views import (
    TrendingShortsAPIView,
    TrendingStatsAPIView,
    AdminCollectTrendingView,
    AdminTrendingStatsView,
    TrendingCategoriesAPIView,
    TrendingShortsListView,
    ShortsComparisonView,
    ShortsComparisonAPIView,
    FavoriteShortsAPIView,
    FavoriteStatusBatchAPIView,
    TrendMatrixAPIView,
    extract_tags_api,
)

app_name = 'youtube_trending'

urlpatterns = [
    # 메인 페이지
    path('', TrendingShortsListView.as_view(), name='trending_shorts_list'),
    
    # API 엔드포인트
    path('api/shorts/', TrendingShortsAPIView.as_view(), name='trending_shorts_api'),
    path('api/stats/', TrendingStatsAPIView.as_view(), name='trending_stats_api'),
    path('api/categories/', TrendingCategoriesAPIView.as_view(), name='trending_categories_api'),
    path('api/matrix/', TrendMatrixAPIView.as_view(), name='api_matrix'),
    path('api/extract-tags/', extract_tags_api, name='extract_tags_api'),
    
    # 새로운 비교 및 즐겨찾기 기능
    path('comparison/', ShortsComparisonView.as_view(), name='shorts_comparison'),
    path('api/comparison/', ShortsComparisonAPIView.as_view(), name='api_comparison'),
    path('api/favorites/', FavoriteShortsAPIView.as_view(), name='api_favorites'),
    path('api/favorites/batch-status/', FavoriteStatusBatchAPIView.as_view(), name='api_favorite_batch_status'),
    
    # 관리자 전용 뷰
    path('admin/collect/', AdminCollectTrendingView.as_view(), name='admin_collect'),
    path('admin/stats/', AdminTrendingStatsView.as_view(), name='admin_stats'),
] 