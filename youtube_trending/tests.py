from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from unittest.mock import patch, Mock
from datetime import date, datetime, timedelta
import json

from .models import TrendingVideo, TrendingStats
from .services import YouTubeAPIService, TrendingVideoCollector

User = get_user_model()


class TrendingVideoModelTest(TestCase):
    """TrendingVideo 모델 테스트"""
    
    def setUp(self):
        self.video_data = {
            'youtube_id': 'test_video_123',
            'title': '테스트 쇼츠 영상',
            'description': '테스트용 설명',
            'channel_title': '테스트 채널',
            'channel_id': 'test_channel_123',
            'view_count': 1500000,
            'like_count': 75000,
            'comment_count': 2500,
            'published_at': datetime.now(),
            'duration': 'PT45S',
            'thumbnail_url': 'https://img.youtube.com/vi/test_video_123/maxresdefault.jpg',
            'category': 'music',
            'tags': ['음악', '쇼츠', 'test'],
            'trending_rank': 5,
            'trending_date': date.today(),
            'region_code': 'KR',
            'is_shorts': True,
        }
    
    def test_create_trending_video(self):
        """트렌딩 비디오 생성 테스트"""
        video = TrendingVideo.objects.create(**self.video_data)
        
        self.assertEqual(video.youtube_id, 'test_video_123')
        self.assertEqual(video.title, '테스트 쇼츠 영상')
        self.assertTrue(video.is_shorts)
        self.assertEqual(video.trending_rank, 5)
    
    def test_youtube_url_property(self):
        """YouTube URL 프로퍼티 테스트"""
        video = TrendingVideo.objects.create(**self.video_data)
        expected_url = 'https://www.youtube.com/watch?v=test_video_123'
        self.assertEqual(video.youtube_url, expected_url)
    
    def test_formatted_view_count(self):
        """포맷팅된 조회수 테스트"""
        video = TrendingVideo.objects.create(**self.video_data)
        self.assertEqual(video.formatted_view_count, '1.5M')
        
        # 1000 미만
        video.view_count = 999
        video.save()
        self.assertEqual(video.formatted_view_count, '999')
        
        # 1000 이상 1M 미만
        video.view_count = 15000
        video.save()
        self.assertEqual(video.formatted_view_count, '15.0K')
    
    def test_formatted_duration(self):
        """포맷팅된 영상 길이 테스트"""
        video = TrendingVideo.objects.create(**self.video_data)
        self.assertEqual(video.formatted_duration, '0:45')
        
        # 시간이 포함된 경우
        video.duration = 'PT1H30M25S'
        video.save()
        self.assertEqual(video.formatted_duration, '1:30:25')
        
        # 분만 있는 경우
        video.duration = 'PT2M30S'
        video.save()
        self.assertEqual(video.formatted_duration, '2:30')
    
    def test_unique_constraint(self):
        """unique_together 제약 조건 테스트"""
        TrendingVideo.objects.create(**self.video_data)
        
        # 같은 날짜에 같은 비디오 생성 시도
        with self.assertRaises(Exception):
            TrendingVideo.objects.create(**self.video_data)


class TrendingStatsModelTest(TestCase):
    """TrendingStats 모델 테스트"""
    
    def test_create_trending_stats(self):
        """트렌딩 통계 생성 테스트"""
        stats = TrendingStats.objects.create(
            collection_date=date.today(),
            total_videos_collected=50,
            shorts_count=30,
            regular_videos_count=20,
            collection_success=True
        )
        
        self.assertEqual(stats.total_videos_collected, 50)
        self.assertEqual(stats.shorts_count, 30)
        self.assertEqual(stats.regular_videos_count, 20)
        self.assertTrue(stats.collection_success)


class YouTubeAPIServiceTest(TestCase):
    """YouTubeAPIService 테스트"""
    
    def setUp(self):
        self.mock_video_data = {
            'id': 'test_video_123',
            'snippet': {
                'title': '테스트 쇼츠',
                'description': '테스트 설명',
                'channelTitle': '테스트 채널',
                'channelId': 'test_channel_123',
                'categoryId': '10',
                'publishedAt': '2024-01-01T12:00:00Z',
                'tags': ['음악', '쇼츠'],
                'thumbnails': {
                    'high': {'url': 'https://img.youtube.com/vi/test_video_123/hqdefault.jpg'}
                }
            },
            'statistics': {
                'viewCount': '1500000',
                'likeCount': '75000',
                'commentCount': '2500'
            },
            'contentDetails': {
                'duration': 'PT45S'
            }
        }
    
    @patch('youtube_trending.services.build')
    def test_youtube_api_service_initialization(self, mock_build):
        """YouTubeAPIService 초기화 테스트"""
        with patch('django.conf.settings.YOUTUBE_API_KEY', 'test_api_key'):
            service = YouTubeAPIService()
            self.assertIsNotNone(service.service)
            mock_build.assert_called_once()
    
    def test_parse_video_data(self):
        """비디오 데이터 파싱 테스트"""
        with patch('django.conf.settings.YOUTUBE_API_KEY', 'test_api_key'):
            service = YouTubeAPIService()
            parsed_data = service.parse_video_data(self.mock_video_data, 1)
            
            self.assertEqual(parsed_data['youtube_id'], 'test_video_123')
            self.assertEqual(parsed_data['title'], '테스트 쇼츠')
            self.assertEqual(parsed_data['trending_rank'], 1)
            self.assertTrue(parsed_data['is_shorts'])  # 45초이므로 쇼츠로 판단
            self.assertEqual(parsed_data['category'], 'music')
    
    def test_is_shorts_video(self):
        """쇼츠 영상 판단 테스트"""
        with patch('django.conf.settings.YOUTUBE_API_KEY', 'test_api_key'):
            service = YouTubeAPIService()
            
            # 60초 이하
            self.assertTrue(service._is_shorts_video('PT45S', '일반 제목'))
            
            # 60초 초과
            self.assertFalse(service._is_shorts_video('PT2M30S', '일반 제목'))
            
            # #shorts 해시태그 포함
            self.assertTrue(service._is_shorts_video('PT2M30S', '제목에 #shorts 포함'))
            self.assertTrue(service._is_shorts_video('PT90S', '제목에 #short 포함'))
    
    def test_parse_duration(self):
        """ISO 8601 duration 파싱 테스트"""
        with patch('django.conf.settings.YOUTUBE_API_KEY', 'test_api_key'):
            service = YouTubeAPIService()
            
            self.assertEqual(service._parse_duration('PT45S'), 45)
            self.assertEqual(service._parse_duration('PT2M30S'), 150)
            self.assertEqual(service._parse_duration('PT1H30M25S'), 5425)


class TrendingVideoCollectorTest(TestCase):
    """TrendingVideoCollector 테스트"""
    
    @patch('youtube_trending.services.YouTubeAPIService')
    def test_collect_and_save_trending_videos_success(self, mock_youtube_service):
        """트렌딩 비디오 수집 성공 테스트"""
        # Mock YouTube API 응답
        mock_service_instance = mock_youtube_service.return_value
        mock_service_instance.get_trending_videos.return_value = [
            {
                'id': 'video1',
                'snippet': {'title': '쇼츠1', 'channelTitle': '채널1'},
                'statistics': {'viewCount': '1000'},
                'contentDetails': {'duration': 'PT30S'}
            }
        ]
        mock_service_instance.parse_video_data.return_value = {
            'youtube_id': 'video1',
            'title': '쇼츠1',
            'channel_title': '채널1',
            'view_count': 1000,
            'trending_rank': 1,
            'trending_date': date.today(),
            'is_shorts': True,
            'category': 'other',
            'like_count': 0,
            'comment_count': 0,
            'published_at': None,
            'duration': 'PT30S',
            'thumbnail_url': '',
            'tags': [],
            'region_code': 'KR',
        }
        
        collector = TrendingVideoCollector()
        success, message, stats = collector.collect_and_save_trending_videos()
        
        self.assertTrue(success)
        self.assertIn('성공적으로', message)
        self.assertEqual(stats['total_videos'], 1)
        self.assertEqual(stats['shorts_count'], 1)
    
    def test_get_latest_shorts(self):
        """최신 쇼츠 가져오기 테스트"""
        # 테스트 데이터 생성
        TrendingVideo.objects.create(
            youtube_id='shorts1',
            title='쇼츠1',
            channel_title='채널1',
            trending_rank=1,
            trending_date=date.today(),
            is_shorts=True
        )
        TrendingVideo.objects.create(
            youtube_id='video1',
            title='일반영상1',
            channel_title='채널2',
            trending_rank=2,
            trending_date=date.today(),
            is_shorts=False
        )
        
        collector = TrendingVideoCollector()
        shorts = collector.get_latest_shorts(limit=10)
        
        self.assertEqual(len(shorts), 1)
        self.assertTrue(shorts[0].is_shorts)
        self.assertEqual(shorts[0].title, '쇼츠1')


class TrendingViewsTest(TestCase):
    """트렌딩 뷰 테스트"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        
        # 테스트 데이터 생성
        self.trending_video = TrendingVideo.objects.create(
            youtube_id='test_shorts',
            title='테스트 쇼츠',
            channel_title='테스트 채널',
            view_count=1000000,
            trending_rank=1,
            trending_date=date.today(),
            is_shorts=True,
            category='music'
        )
    
    def test_trending_shorts_api_view(self):
        """인기 쇼츠 API 뷰 테스트"""
        url = reverse('youtube_trending:api_shorts')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['shorts']), 1)
        self.assertEqual(data['shorts'][0]['title'], '테스트 쇼츠')
    
    def test_trending_shorts_api_with_filters(self):
        """필터가 있는 인기 쇼츠 API 테스트"""
        url = reverse('youtube_trending:api_shorts')
        response = self.client.get(url, {
            'category': 'music',
            'days': 7,
            'limit': 10
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['shorts']), 1)
    
    def test_trending_categories_api_view(self):
        """카테고리 API 뷰 테스트"""
        url = reverse('youtube_trending:api_categories')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIsInstance(data['categories'], list)
        # '전체' 옵션과 실제 사용된 카테고리가 있어야 함
        category_values = [cat['value'] for cat in data['categories']]
        self.assertIn('all', category_values)
        self.assertIn('music', category_values)
    
    def test_trending_stats_api_view(self):
        """통계 API 뷰 테스트"""
        # 통계 데이터 생성
        TrendingStats.objects.create(
            collection_date=date.today(),
            total_videos_collected=10,
            shorts_count=7,
            regular_videos_count=3,
            collection_success=True
        )
        
        url = reverse('youtube_trending:api_stats')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('stats', data)
    
    def test_unauthorized_access(self):
        """인증되지 않은 접근 테스트"""
        self.client.logout()
        
        url = reverse('youtube_trending:api_shorts')
        response = self.client.get(url)
        
        # 로그인 페이지로 리다이렉트되어야 함
        self.assertEqual(response.status_code, 302)


class YouTubeAPIIntegrationTest(TestCase):
    """YouTube API 통합 테스트 (실제 API 호출 없이 Mock 사용)"""
    
    @patch('youtube_trending.services.build')
    def test_youtube_api_integration(self, mock_build):
        """YouTube API 통합 테스트"""
        # Mock YouTube API 서비스
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        # Mock API 응답
        mock_response = {
            'items': [
                {
                    'id': 'test_video',
                    'snippet': {
                        'title': 'Test Shorts',
                        'channelTitle': 'Test Channel',
                        'categoryId': '10',
                        'publishedAt': '2024-01-01T12:00:00Z',
                        'tags': ['test'],
                        'thumbnails': {'high': {'url': 'test_url'}}
                    },
                    'statistics': {
                        'viewCount': '1000',
                        'likeCount': '100',
                        'commentCount': '10'
                    },
                    'contentDetails': {
                        'duration': 'PT30S'
                    }
                }
            ]
        }
        
        mock_request = Mock()
        mock_request.execute.return_value = mock_response
        mock_service.videos.return_value.list.return_value = mock_request
        
        with patch('django.conf.settings.YOUTUBE_API_KEY', 'test_key'):
            collector = TrendingVideoCollector()
            success, message, stats = collector.collect_and_save_trending_videos()
            
            self.assertTrue(success)
            self.assertGreater(stats['total_videos'], 0)


class TrendingTasksTest(TestCase):
    """Celery 태스크 테스트"""
    
    @patch('youtube_trending.tasks.TrendingVideoCollector')
    def test_collect_trending_videos_task(self, mock_collector_class):
        """트렌딩 비디오 수집 태스크 테스트"""
        from .tasks import collect_trending_videos
        
        # Mock collector 인스턴스
        mock_collector = mock_collector_class.return_value
        mock_collector.collect_and_save_trending_videos.return_value = (
            True, 
            "성공적으로 수집되었습니다.", 
            {'total_videos': 10, 'shorts_count': 7}
        )
        
        # 태스크 실행 (실제 Celery 없이 함수로 호출)
        result = collect_trending_videos()
        
        # 결과 검증
        self.assertIn('성공', result)
        mock_collector.collect_and_save_trending_videos.assert_called_once()
