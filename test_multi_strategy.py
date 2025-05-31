import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from youtube_trending.services import YouTubeTrendingScraper

def test_multi_strategy_scraping():
    print('=== 🚀 다중 전략 YouTube 쇼츠 스크래핑 테스트 ===')
    print('새로운 4단계 전략:')
    print('1️⃣ 기본 트렌딩 페이지 + button-next (개선)')
    print('2️⃣ YouTube Shorts 전용 페이지 수집')
    print('3️⃣ 다양한 트렌딩 카테고리 수집')
    print('4️⃣ 적극적 스크롤링 추가 수집')
    print()

    scraper = YouTubeTrendingScraper(use_metadata_enhancement=False, max_retries=2)
    
    try:
        # 목표: 더 많은 쇼츠 수집 (50개 목표)
        target_count = 50
        print(f'🎯 목표: {target_count}개 쇼츠 수집 (다중 전략 활용)')
        
        shorts_data = scraper.scrape_trending_shorts(enhance_metadata=False, max_shorts=target_count)
        
        print(f'✅ 수집 완료: {len(shorts_data)}개 쇼츠')
        
        if len(shorts_data) >= target_count:
            print(f'🎉 목표 달성! {target_count}개 이상 쇼츠 수집 성공')
        elif len(shorts_data) >= 30:
            print(f'👍 양호한 결과: {len(shorts_data)}/{target_count}개 ({(len(shorts_data)/target_count*100):.1f}%)')
        else:
            print(f'⚠️  목표 미달성: {len(shorts_data)}/{target_count}개 ({(len(shorts_data)/target_count*100):.1f}%)')
        
        print()
        
        # 수집된 데이터 상세 분석
        valid_count = 0
        invalid_count = 0
        id_lengths = {}
        view_counts = []
        
        print('=== 수집된 쇼츠 상위 20개 ===')
        for i, shorts in enumerate(shorts_data[:20], 1):
            youtube_id = shorts.get('youtube_id', '')
            title = shorts.get('title', '')[:35]
            view_count = shorts.get('view_count', 0)
            
            # 통계 수집
            id_len = len(youtube_id)
            id_lengths[id_len] = id_lengths.get(id_len, 0) + 1
            view_counts.append(view_count)
            
            # ID 유효성 검증
            is_valid_id = 8 <= len(youtube_id) <= 15
            if is_valid_id:
                valid_count += 1
            else:
                invalid_count += 1
            
            status = '✅' if is_valid_id else '❌'
            print(f'{status} [{i:2d}] {youtube_id:12} (L{id_len:2d}) | {view_count:9,}회 | {title}')
        
        if len(shorts_data) > 20:
            print(f'... 외 {len(shorts_data) - 20}개 더')
        
        print()
        print(f'=== 📊 수집 성과 분석 ===')
        print(f'🔢 전체 수집: {len(shorts_data)}개')
        print(f'✅ 유효한 ID: {valid_count}개')
        print(f'❌ 무효한 ID: {invalid_count}개')
        print(f'📈 성공률: {(valid_count/(valid_count+invalid_count)*100):.1f}%' if (valid_count+invalid_count) > 0 else '0%')
        print(f'📏 ID 길이 분포: {dict(sorted(id_lengths.items()))}')
        
        # 조회수 통계
        if view_counts:
            avg_views = sum(view_counts) / len(view_counts)
            max_views = max(view_counts)
            min_views = min(view_counts)
            print(f'👁️  조회수 통계: 평균 {avg_views:,.0f}회, 최고 {max_views:,}회, 최저 {min_views:,}회')
        
        # 데이터베이스 저장 테스트
        if shorts_data:
            print()
            print('=== 💾 데이터베이스 저장 테스트 ===')
            created, updated = scraper.save_scraped_shorts_to_db(shorts_data)
            print(f'📝 생성: {created}개, 업데이트: {updated}개')
            
            # 최종 성과 평가
            total_saved = created + updated
            if total_saved >= target_count:
                print('🏆 최종 대성공: 목표 초과 달성!')
            elif total_saved >= 30:
                print(f'🎯 최종 성공: {total_saved}개 쇼츠 데이터베이스 저장 완료!')
            else:
                print(f'📈 진전: {total_saved}개 쇼츠 저장 (이전 대비 향상)')
            
            # 이전 결과와 비교
            print()
            print('=== 📈 성능 비교 ===')
            previous_count = 25  # 이전 테스트 결과
            improvement = ((len(shorts_data) - previous_count) / previous_count) * 100
            if improvement > 0:
                print(f'🚀 성능 향상: +{improvement:.1f}% ({previous_count}개 → {len(shorts_data)}개)')
            else:
                print(f'📊 성능 유지: {len(shorts_data)}개 수집')
        
        # 추천사항
        print()
        print('=== 💡 다음 단계 추천 ===')
        if len(shorts_data) >= target_count:
            print('✨ 메타데이터 보강 (yt-dlp) 활성화')
            print('🔄 정기적 자동 수집 설정')
            print('📊 트렌드 분석 대시보드 구축')
        else:
            print('🔧 더 많은 수집 소스 추가')
            print('⏰ 수집 시간대 다변화')
            print('🎯 특정 카테고리 집중 수집')
        
    except Exception as e:
        print(f'❌ 테스트 실패: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_multi_strategy_scraping() 