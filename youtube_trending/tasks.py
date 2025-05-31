"""
YouTube 트렌딩 비디오 수집 Celery 태스크
"""
import logging
from celery import shared_task
from django.utils import timezone
from youtube_trending.models import TrendingVideo
from .services import TrendingDataService, YouTubeTrendingScraper


logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def collect_trending_videos(self):
    """
    YouTube 인기 급상승 동영상을 향상된 Selenium + yt-dlp 방식으로 수집하는 Celery 태스크
    
    - 매일 오후 11:58에 실행
    - Selenium + yt-dlp 메타데이터 보강 우선, API는 보조
    - 실패 시 최대 3회 재시도 (5분 간격)
    """
    task_id = self.request.id
    logger.info(f"YouTube 트렌딩 비디오 수집 태스크 시작 (향상된 Selenium + yt-dlp 방식) (Task ID: {task_id})")
    
    try:
        # 향상된 데이터 수집 서비스 사용 (Selenium + yt-dlp 우선)
        data_service = TrendingDataService()
        
        # 우선 향상된 스크래핑 시도
        scraping_success = False
        scraping_count = 0
        scraping_error = None
        
        try:
            logger.info("향상된 Selenium + yt-dlp 스크래핑 시작...")
            scraper = YouTubeTrendingScraper(use_metadata_enhancement=True)
            shorts_data = scraper.scrape_trending_shorts(enhance_metadata=True, max_shorts=50)
            
            if shorts_data:
                created, updated = scraper.save_scraped_shorts_to_db(shorts_data)
                scraping_count = created + updated
                scraping_success = True
                logger.info(f"향상된 스크래핑 성공: {scraping_count}개 수집")
            else:
                logger.warning("스크래핑에서 데이터를 가져오지 못했습니다")
                
        except Exception as e:
            scraping_error = str(e)
            logger.error(f"향상된 스크래핑 실패: {scraping_error}")
        
        # API 수집은 스크래핑이 실패했거나 데이터가 부족할 때만 수행
        api_success = False
        api_count = 0
        api_error = None
        
        if not scraping_success or scraping_count < 10:  # 스크래핑 실패 또는 10개 미만일 때 API 보완
            try:
                logger.info("API를 통한 추가 데이터 수집 시작...")
                api_videos = data_service.api_service.get_trending_videos()
                
                api_created, api_updated = 0, 0
                for idx, video in enumerate(api_videos, 1):
                    try:
                        video_data = data_service.api_service.parse_video_data(video, idx)
                        
                        existing_video = TrendingVideo.objects.filter(
                            youtube_id=video_data['youtube_id'],
                            trending_date=video_data['trending_date']
                        ).first()
                        
                        if existing_video:
                            for key, value in video_data.items():
                                setattr(existing_video, key, value)
                            existing_video.save()
                            api_updated += 1
                        else:
                            TrendingVideo.objects.create(**video_data)
                            api_created += 1
                        
                    except Exception as e:
                        logger.error(f"API 비디오 처리 실패: {e}")
                        continue
                
                api_count = api_created + api_updated
                api_success = True
                logger.info(f"API 수집 성공: {api_count}개 추가")
                
            except Exception as e:
                api_error = str(e)
                logger.error(f"API 수집 실패: {api_error}")
        
        # 결과 분석
        total_collected = scraping_count + api_count
        overall_success = scraping_success or api_success
        
        if overall_success and total_collected > 0:
            success_message = f"트렌딩 데이터 수집 완료: 총 {total_collected}개"
            if scraping_success:
                success_message += f" (향상된 스크래핑: {scraping_count}개"
                if api_success:
                    success_message += f", API 보완: {api_count}개)"
                else:
                    success_message += ")"
            elif api_success:
                success_message += f" (API만: {api_count}개)"
            
            logger.info(success_message)
            return {
                'success': True,
                'message': success_message,
                'results': {
                    'scraping_collection': {
                        'success': scraping_success,
                        'count': scraping_count,
                        'error': scraping_error,
                        'method': 'selenium_enhanced'
                    },
                    'api_collection': {
                        'success': api_success,
                        'count': api_count,
                        'error': api_error,
                        'method': 'youtube_api'
                    }
                },
                'total_collected': total_collected,
                'completed_at': timezone.now().isoformat(),
                'task_id': task_id,
            }
        else:
            # 둘 다 실패하거나 데이터가 없는 경우
            error_details = []
            if not scraping_success:
                error_details.append(f"향상된 스크래핑 실패: {scraping_error}")
            if not api_success and scraping_count < 10:
                error_details.append(f"API 수집 실패: {api_error}")
            
            error_message = f"데이터 수집 실패: {', '.join(error_details)}"
            logger.error(error_message)
            
            # 실패한 경우 재시도
            raise self.retry(countdown=300, exc=Exception(error_message))
            
    except Exception as exc:
        logger.error(f"트렌딩 비디오 수집 중 예외 발생: {exc}")
        
        # 최대 재시도 횟수에 도달한 경우
        if self.request.retries >= self.max_retries:
            logger.error(f"최대 재시도 횟수 도달. 태스크 실패로 처리. (Task ID: {task_id})")
            return {
                'success': False,
                'message': f'수집 실패 (최종): {str(exc)}',
                'results': {'total_collected': 0},
                'failed_at': timezone.now().isoformat(),
                'task_id': task_id,
                'retries': self.request.retries,
            }
        
        # 재시도
        logger.warning(f"트렌딩 비디오 수집 재시도 ({self.request.retries + 1}/{self.max_retries})")
        raise self.retry(countdown=300, exc=exc)


@shared_task
def manual_collect_trending_videos():
    """
    수동으로 트렌딩 비디오를 수집하는 태스크 (Selenium 방식)
    """
    logger.info("수동 YouTube 트렌딩 비디오 수집 시작 (Selenium 방식)")
    
    try:
        # 통합 데이터 수집 서비스 사용
        data_service = TrendingDataService()
        results = data_service.collect_all_trending_data()
        
        total_collected = results.get('total_collected', 0)
        api_success = results.get('api_collection', {}).get('success', False)
        scraping_success = results.get('scraping_collection', {}).get('success', False)
        
        overall_success = api_success or scraping_success
        
        if overall_success:
            success_message = f"수동 수집 완료: 총 {total_collected}개"
            logger.info(success_message)
        else:
            success_message = "수동 수집 실패: 데이터를 가져올 수 없습니다"
            logger.error(success_message)
        
        return {
            'success': overall_success,
            'message': success_message,
            'results': results,
            'total_collected': total_collected,
            'completed_at': timezone.now().isoformat(),
        }
        
    except Exception as exc:
        error_message = f"수동 수집 중 예외 발생: {str(exc)}"
        logger.error(error_message)
        
        return {
            'success': False,
            'message': error_message,
            'results': {'total_collected': 0},
            'failed_at': timezone.now().isoformat(),
        }


@shared_task
def collect_trending_shorts_only():
    """
    Selenium + yt-dlp를 사용해 쇼츠만 수집하는 태스크 (날짜별 축적 버전)
    매일 11:55에 실행하여 새로운 데이터를 축적
    """
    logger.info("YouTube 트렌딩 쇼츠 전용 수집 시작 (Selenium + yt-dlp)")
    
    try:
        # 새로운 날짜별 축적 서비스 사용
        data_service = TrendingDataService()
        results = data_service.collect_trending_shorts()
        
        if results['success']:
            success_message = f"쇼츠 수집 완료: {results['count']}개 (새로 생성: {results['created']}개, 스킵: {results['skipped']}개)"
            logger.info(success_message)
            
            return {
                'success': True,
                'total_collected': results['count'],
                'new_created': results['created'],
                'skipped': results['skipped'],
                'message': success_message,
                'method': 'selenium_ydl_daily_accumulation'
            }
        else:
            error_message = results.get('error', '알 수 없는 오류')
            logger.warning(f"쇼츠 수집 실패: {error_message}")
            
            return {
                'success': False,
                'total_collected': 0,
                'new_created': 0,
                'skipped': 0,
                'message': f"쇼츠 수집 실패: {error_message}",
                'error': error_message
            }
            
    except Exception as e:
        error_message = f"쇼츠 수집 중 오류 발생: {str(e)}"
        logger.error(error_message, exc_info=True)
        
        return {
            'success': False,
            'total_collected': 0,
            'new_created': 0,
            'skipped': 0,
            'message': error_message,
            'error': str(e)
        }


@shared_task
def cleanup_old_trending_data(days_to_keep=30):
    """
    오래된 트렌딩 데이터를 정리하는 태스크
    
    Args:
        days_to_keep: 유지할 데이터 일수 (기본값: 30일)
    """
    from django.utils import timezone
    from datetime import timedelta
    from .models import TrendingVideo, TrendingStats
    
    cutoff_date = timezone.now().date() - timedelta(days=days_to_keep)
    
    logger.info(f"{cutoff_date} 이전의 트렌딩 데이터 정리 시작")
    
    try:
        # 오래된 비디오 데이터 삭제
        deleted_videos = TrendingVideo.objects.filter(
            trending_date__lt=cutoff_date
        ).delete()
        
        # 오래된 통계 데이터 삭제
        deleted_stats = TrendingStats.objects.filter(
            collection_date__lt=cutoff_date
        ).delete()
        
        message = f"정리 완료: 비디오 {deleted_videos[0]}개, 통계 {deleted_stats[0]}개 삭제"
        logger.info(message)
        
        return {
            'success': True,
            'message': message,
            'deleted_videos': deleted_videos[0] if deleted_videos else 0,
            'deleted_stats': deleted_stats[0] if deleted_stats else 0,
            'cutoff_date': cutoff_date.isoformat(),
            'completed_at': timezone.now().isoformat(),
        }
        
    except Exception as exc:
        error_message = f"데이터 정리 중 오류 발생: {str(exc)}"
        logger.error(error_message)
        
        return {
            'success': False,
            'message': error_message,
            'completed_at': timezone.now().isoformat(),
        } 