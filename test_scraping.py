import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from youtube_trending.services import YouTubeTrendingScraper

def test_scraping():
    print('=== YouTube 트렌딩 쇼츠 스크래핑 테스트 시작 ===')
    print('개선사항:')
    print('2번: YouTube ID 검증 정규식 개선 (8-15자리)')
    print('3번: button-next 클릭을 통한 더 많은 쇼츠 수집')
    print()

    scraper = YouTubeTrendingScraper(use_metadata_enhancement=False, max_retries=2)
    try:
        # 목표: 최소 20개 쇼츠 수집
        shorts_data = scraper.scrape_trending_shorts(enhance_metadata=False, max_shorts=20)
        
        print(f'✅ 수집 완료: {len(shorts_data)}개 쇼츠')
        print()
        
        # 수집된 데이터 검증
        valid_count = 0
        invalid_count = 0
        
        for i, shorts in enumerate(shorts_data[:10], 1):  # 상위 10개만 출력
            youtube_id = shorts.get('youtube_id', '')
            title = shorts.get('title', '')[:50]
            view_count = shorts.get('view_count', 0)
            
            # ID 길이 검증
            is_valid_id = 8 <= len(youtube_id) <= 15
            if is_valid_id:
                valid_count += 1
            else:
                invalid_count += 1
            
            status = '✅' if is_valid_id else '❌'
            print(f'{status} [{i:2d}] {youtube_id} (길이:{len(youtube_id)}) | {view_count:8,}회 | {title}')
        
        print()
        print(f'=== 검증 결과 ===')
        print(f'전체 수집: {len(shorts_data)}개')
        print(f'유효한 ID: {valid_count}개')
        print(f'무효한 ID: {invalid_count}개')
        print(f'성공률: {(valid_count/(valid_count+invalid_count)*100):.1f}%' if (valid_count+invalid_count) > 0 else '0%')
        
        # 데이터베이스 저장 테스트
        if shorts_data:
            print()
            print('=== 데이터베이스 저장 테스트 ===')
            created, updated = scraper.save_scraped_shorts_to_db(shorts_data)
            print(f'생성: {created}개, 업데이트: {updated}개')
        
    except Exception as e:
        print(f'❌ 테스트 실패: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_scraping() 