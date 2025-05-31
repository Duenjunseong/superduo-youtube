#!/usr/bin/env python3
"""
최종 리팩토링 테스트 스크립트
"""
import os
import sys
import django

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from youtube_trending.services import YouTubeTrendingScraper, TrendingDataService
from youtube_trending.tasks import collect_trending_shorts_only
from youtube_trending.models import TrendingVideo

def test_complete_pipeline():
    """전체 파이프라인 테스트"""
    print('=== 최종 리팩토링 테스트 ===\n')
    
    # 1. 기본 크롤링 테스트
    print('1. 기본 크롤링 테스트 시작...')
    scraper = YouTubeTrendingScraper(use_metadata_enhancement=False)
    
    try:
        shorts_data = scraper.scrape_trending_shorts(enhance_metadata=False, max_shorts=3)
        print(f'✅ 기본 크롤링 성공: {len(shorts_data)}개 쇼츠')
    except Exception as e:
        print(f'❌ 기본 크롤링 실패: {e}')
        return False
    
    # 2. yt-dlp 메타데이터 보강 테스트
    print('\n2. yt-dlp 메타데이터 보강 테스트 시작...')
    try:
        enhanced_scraper = YouTubeTrendingScraper(use_metadata_enhancement=True)
        enhanced_data = enhanced_scraper.scrape_trending_shorts(enhance_metadata=True, max_shorts=3)
        
        # 메타데이터 품질 확인
        has_detailed_metadata = any(
            shorts.get('channel_title') and 
            shorts.get('description') and 
            shorts.get('published_at')
            for shorts in enhanced_data
        )
        
        if has_detailed_metadata:
            print(f'✅ 메타데이터 보강 성공: {len(enhanced_data)}개 쇼츠 (상세 정보 포함)')
        else:
            print(f'⚠️  메타데이터 보강 부분 성공: {len(enhanced_data)}개 쇼츠 (기본 정보만)')
            
    except Exception as e:
        print(f'❌ 메타데이터 보강 실패: {e}')
        return False
    
    # 3. 데이터베이스 저장 테스트
    print('\n3. 데이터베이스 저장 테스트 시작...')
    try:
        created, updated = enhanced_scraper.save_scraped_shorts_to_db(enhanced_data)
        print(f'✅ 데이터베이스 저장 성공: 생성 {created}개, 업데이트 {updated}개')
    except Exception as e:
        print(f'❌ 데이터베이스 저장 실패: {e}')
        return False
    
    # 4. Celery 태스크 테스트
    print('\n4. Celery 태스크 테스트 시작...')
    try:
        task_result = collect_trending_shorts_only()
        if task_result['success']:
            print(f'✅ Celery 태스크 성공: {task_result["total_collected"]}개 수집')
        else:
            print(f'❌ Celery 태스크 실패: {task_result.get("message", "Unknown error")}')
            return False
    except Exception as e:
        print(f'❌ Celery 태스크 실패: {e}')
        return False
    
    # 5. 데이터 검증
    print('\n5. 최종 데이터 검증...')
    try:
        stored_shorts = TrendingVideo.objects.filter(is_shorts=True)
        total_count = stored_shorts.count()
        
        if total_count > 0:
            print(f'✅ 데이터베이스 검증 성공: {total_count}개 쇼츠 저장됨')
            
            # 상위 3개 출력
            top_shorts = stored_shorts.order_by('-view_count')[:3]
            print('\n📊 상위 3개 쇼츠:')
            for i, shorts in enumerate(top_shorts, 1):
                print(f'  {i}. {shorts.youtube_id} - {shorts.title[:40]}... (조회수: {shorts.view_count:,})')
            
            return True
        else:
            print('❌ 데이터베이스에 쇼츠가 없습니다')
            return False
            
    except Exception as e:
        print(f'❌ 데이터 검증 실패: {e}')
        return False


def test_service_integration():
    """서비스 통합 테스트"""
    print('\n=== 서비스 통합 테스트 ===')
    
    try:
        service = TrendingDataService()
        result = service.collect_trending_shorts()
        
        if result['success']:
            print(f'✅ 통합 서비스 성공: {result["count"]}개 수집')
        else:
            print(f'❌ 통합 서비스 실패: {result.get("error", "Unknown error")}')
            return False
            
        return True
        
    except Exception as e:
        print(f'❌ 통합 서비스 오류: {e}')
        return False


if __name__ == '__main__':
    print('YouTube 트렌딩 쇼츠 시스템 최종 테스트를 시작합니다...\n')
    
    pipeline_success = test_complete_pipeline()
    service_success = test_service_integration()
    
    print('\n=== 최종 결과 ===')
    if pipeline_success and service_success:
        print('🎉 모든 테스트 통과! 리팩토링이 성공적으로 완료되었습니다.')
        print('\n✅ 성공한 기능:')
        print('  - Selenium 기반 HTML DOM 파싱')
        print('  - yt-dlp 메타데이터 보강')
        print('  - 데이터베이스 저장')
        print('  - Celery 태스크 실행')
        print('  - 서비스 통합')
        print('\n🕒 스케줄링: 매일 23:55에 자동 실행')
        sys.exit(0)
    else:
        print('❌ 일부 테스트 실패. 추가 디버깅이 필요합니다.')
        sys.exit(1) 