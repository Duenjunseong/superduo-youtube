import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from youtube_trending.services import YouTubeTrendingScraper

def test_improved_scraping():
    print('=== 개선된 YouTube 트렌딩 쇼츠 스크래핑 테스트 ===')
    print('최신 개선사항:')
    print('1. YouTube ID 검증 정규식 개선 (8-15자리)')
    print('2. button-next 클릭을 통한 더 많은 쇼츠 수집')
    print('3. 향상된 CSS 선택자 및 직접 링크 검색')
    print('4. 중복 제거 로직 개선')
    print()

    scraper = YouTubeTrendingScraper(use_metadata_enhancement=False, max_retries=2)
    
    try:
        # 목표: 최소 20개 쇼츠 수집 (더 적극적인 수집)
        print('🎯 목표: 최소 20개 쇼츠 수집')
        shorts_data = scraper.scrape_trending_shorts(enhance_metadata=False, max_shorts=25)
        
        print(f'✅ 수집 완료: {len(shorts_data)}개 쇼츠')
        
        if len(shorts_data) >= 20:
            print('🎉 목표 달성! 20개 이상 쇼츠 수집 성공')
        else:
            print(f'⚠️  목표 미달성: {len(shorts_data)}/20개 ({(len(shorts_data)/20*100):.1f}%)')
        
        print()
        
        # 수집된 데이터 상세 분석
        valid_count = 0
        invalid_count = 0
        id_lengths = {}
        
        print('=== 수집된 쇼츠 상위 15개 ===')
        for i, shorts in enumerate(shorts_data[:15], 1):
            youtube_id = shorts.get('youtube_id', '')
            title = shorts.get('title', '')[:40]
            view_count = shorts.get('view_count', 0)
            
            # ID 길이 통계
            id_len = len(youtube_id)
            id_lengths[id_len] = id_lengths.get(id_len, 0) + 1
            
            # ID 유효성 검증
            is_valid_id = 8 <= len(youtube_id) <= 15
            if is_valid_id:
                valid_count += 1
            else:
                invalid_count += 1
            
            status = '✅' if is_valid_id else '❌'
            print(f'{status} [{i:2d}] {youtube_id:15} (L{id_len:2d}) | {view_count:8,}회 | {title}')
        
        if len(shorts_data) > 15:
            print(f'... 외 {len(shorts_data) - 15}개 더')
        
        print()
        print(f'=== 분석 결과 ===')
        print(f'📊 전체 수집: {len(shorts_data)}개')
        print(f'✅ 유효한 ID: {valid_count}개')
        print(f'❌ 무효한 ID: {invalid_count}개')
        print(f'📈 성공률: {(valid_count/(valid_count+invalid_count)*100):.1f}%' if (valid_count+invalid_count) > 0 else '0%')
        
        # ID 길이 분포
        print(f'📏 ID 길이 분포: {dict(sorted(id_lengths.items()))}')
        
        # 데이터베이스 저장 테스트
        if shorts_data:
            print()
            print('=== 데이터베이스 저장 테스트 ===')
            created, updated = scraper.save_scraped_shorts_to_db(shorts_data)
            print(f'💾 생성: {created}개, 업데이트: {updated}개')
            
            # 최종 성과 평가
            total_saved = created + updated
            if total_saved >= 20:
                print('🏆 최종 성공: 20개 이상 쇼츠 데이터베이스 저장 완료!')
            else:
                print(f'📝 결과: {total_saved}개 쇼츠 저장 완료')
        
    except Exception as e:
        print(f'❌ 테스트 실패: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_improved_scraping() 