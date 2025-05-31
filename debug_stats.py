#!/usr/bin/env python
import os
import django
import sys

# Django 설정
sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from youtube_trending.services import TrendingDataService
from youtube_trending.models import TrendingStats, TrendingVideo
from datetime import date

def debug_stats_api():
    print('=== TrendingStats 모델 확인 ===')
    try:
        stats_count = TrendingStats.objects.count()
        print(f'TrendingStats 총 개수: {stats_count}')
        
        if stats_count > 0:
            latest_stats = TrendingStats.objects.latest('collection_date')
            print(f'최신 통계: {latest_stats.collection_date}')
            print(f'- 성공 수집: {latest_stats.successful_collections}')
            print(f'- 실패 수집: {latest_stats.failed_collections}')
            print(f'- 총 비디오: {latest_stats.total_videos_collected}')
            print(f'- 쇼츠 수: {latest_stats.shorts_collected}')
        else:
            print('TrendingStats 데이터가 없습니다.')
            
    except Exception as e:
        print(f'TrendingStats 조회 오류: {e}')
        import traceback
        traceback.print_exc()

    print()
    print('=== TrendingVideo 쇼츠 확인 ===')
    try:
        today = date.today()
        shorts_today = TrendingVideo.objects.filter(
            is_shorts=True,
            trending_date=today
        )
        print(f'오늘({today}) 쇼츠 개수: {shorts_today.count()}')
        
        if shorts_today.exists():
            sample_short = shorts_today.first()
            print(f'샘플 쇼츠: {sample_short.title[:50]}... (조회수: {sample_short.view_count:,})')
            print(f'- 좋아요: {sample_short.like_count:,}')
            print(f'- 댓글: {sample_short.comment_count:,}')
            print(f'- 채널: {sample_short.channel_title}')
            print(f'- 카테고리: {sample_short.category}')
            print(f'- 순위: {sample_short.trending_rank}')
        
    except Exception as e:
        print(f'TrendingVideo 조회 오류: {e}')
        import traceback
        traceback.print_exc()

    print()
    print('=== TrendingDataService 테스트 ===')
    try:
        service = TrendingDataService()
        stats = service.get_trending_stats_summary(days=1)
        print(f'통계 요약: {stats}')
        
    except Exception as e:
        print(f'TrendingDataService 오류: {e}')
        import traceback
        traceback.print_exc()

    print()
    print('=== API 시뮬레이션 테스트 ===')
    try:
        from youtube_trending.views import TrendingStatsAPIView
        from django.test import RequestFactory
        from users.models import User
        
        # 가짜 요청 생성
        factory = RequestFactory()
        request = factory.get('/trending/api/stats/?date=2025-05-31')
        
        # 사용자 생성 (테스트용)
        try:
            user = User.objects.first()
            if not user:
                user = User.objects.create_user('testuser', 'test@test.com', 'testpass')
        except:
            user = User.objects.create_user('testuser2', 'test2@test.com', 'testpass')
        
        request.user = user
        
        # API 뷰 실행
        view = TrendingStatsAPIView()
        response = view.get(request)
        print(f'API 응답 상태: {response.status_code}')
        if hasattr(response, 'content'):
            print(f'API 응답 내용: {response.content.decode()[:500]}...')
        
    except Exception as e:
        print(f'API 시뮬레이션 오류: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    debug_stats_api() 