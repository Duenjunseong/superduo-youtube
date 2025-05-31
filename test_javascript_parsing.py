import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from youtube_trending.services import YouTubeTrendingScraper

def test_javascript_parsing():
    print('=== 🎯 JavaScript 소스코드 파싱 테스트 ===')
    print('새로운 방법: shortsLockupViewModel 배열 분석')
    print('기존 button-next 방식 → JavaScript 데이터 직접 파싱')
    print()

    scraper = YouTubeTrendingScraper(use_metadata_enhancement=False, max_retries=2)
    
    try:
        print('🔍 테스트 진행 단계:')
        print('1️⃣ YouTube 트렌딩 페이지 로드')
        print('2️⃣ HTML 소스코드에서 ytInitialData 추출')
        print('3️⃣ shortsLockupViewModel 배열 탐색')
        print('4️⃣ 쇼츠 정보 추출 및 검증')
        print()
        
        # 목표: JavaScript 파싱으로 쇼츠 수집
        target_count = 30
        print(f'🎯 목표: {target_count}개 쇼츠 수집 (JavaScript 파싱 중심)')
        
        shorts_data = scraper.scrape_trending_shorts(enhance_metadata=False, max_shorts=target_count)
        
        print(f'✅ 수집 완료: {len(shorts_data)}개 쇼츠')
        
        # 성과 평가
        if len(shorts_data) >= target_count:
            print(f'🎉 JavaScript 파싱 대성공! {target_count}개 이상 수집')
        elif len(shorts_data) >= 20:
            print(f'👍 JavaScript 파싱 성공: {len(shorts_data)}/{target_count}개 ({(len(shorts_data)/target_count*100):.1f}%)')
        elif len(shorts_data) >= 10:
            print(f'⚠️  부분 성공: {len(shorts_data)}/{target_count}개 ({(len(shorts_data)/target_count*100):.1f}%)')
        else:
            print(f'❌ 파싱 실패: {len(shorts_data)}개만 수집')
        
        print()
        
        # 수집된 데이터 상세 분석
        if shorts_data:
            print('=== 📊 JavaScript 파싱 결과 분석 ===')
            
            # 데이터 품질 분석
            valid_ids = 0
            has_titles = 0
            has_views = 0
            total_views = 0
            
            print('상위 15개 쇼츠:')
            for i, shorts in enumerate(shorts_data[:15], 1):
                youtube_id = shorts.get('youtube_id', '')
                title = shorts.get('title', '')[:40]
                view_count = shorts.get('view_count', 0)
                
                # 통계 수집
                if 8 <= len(youtube_id) <= 15:
                    valid_ids += 1
                if title and title != f'쇼츠 {youtube_id}':
                    has_titles += 1
                if view_count > 0:
                    has_views += 1
                    total_views += view_count
                
                # 출력 형식
                status = '✅' if 8 <= len(youtube_id) <= 15 else '❌'
                title_status = '📝' if title and title != f'쇼츠 {youtube_id}' else '📭'
                view_status = '👁️ ' if view_count > 0 else '🔹'
                
                print(f'{status}{title_status}{view_status} [{i:2d}] {youtube_id:12} | {view_count:9,}회 | {title}')
            
            if len(shorts_data) > 15:
                print(f'... 외 {len(shorts_data) - 15}개 더')
            
            print()
            print('=== 🔍 데이터 품질 분석 ===')
            print(f'📊 전체 수집: {len(shorts_data)}개')
            print(f'✅ 유효 ID: {valid_ids}/{len(shorts_data)}개 ({(valid_ids/len(shorts_data)*100):.1f}%)')
            print(f'📝 제목 있음: {has_titles}/{len(shorts_data)}개 ({(has_titles/len(shorts_data)*100):.1f}%)')
            print(f'👁️  조회수 있음: {has_views}/{len(shorts_data)}개 ({(has_views/len(shorts_data)*100):.1f}%)')
            
            if has_views > 0:
                avg_views = total_views / has_views
                max_views = max(s.get('view_count', 0) for s in shorts_data)
                print(f'📈 평균 조회수: {avg_views:,.0f}회')
                print(f'🔝 최고 조회수: {max_views:,}회')
            
            # JavaScript vs HTML 파싱 비교
            print()
            print('=== ⚖️ 파싱 방법 분석 ===')
            js_sourced = sum(1 for s in shorts_data if s.get('view_count', 0) > 0)  # 조회수가 있으면 JS에서 추출
            html_sourced = len(shorts_data) - js_sourced
            
            if js_sourced > 0:
                print(f'🎯 JavaScript 파싱: {js_sourced}개 ({(js_sourced/len(shorts_data)*100):.1f}%)')
            if html_sourced > 0:
                print(f'🔍 HTML DOM 파싱: {html_sourced}개 ({(html_sourced/len(shorts_data)*100):.1f}%)')
            
            # shortsLockupViewModel 성공 여부
            if js_sourced >= 15:
                print('🎉 shortsLockupViewModel 파싱 대성공!')
            elif js_sourced >= 5:
                print('👍 shortsLockupViewModel 파싱 성공')
            else:
                print('⚠️  shortsLockupViewModel 파싱 부족')
            
            # 데이터베이스 저장
            print()
            print('=== 💾 데이터베이스 저장 ===')
            created, updated = scraper.save_scraped_shorts_to_db(shorts_data)
            print(f'📝 신규: {created}개, 업데이트: {updated}개')
            print(f'💾 총 저장: {created + updated}개')
            
            # 이전 방법과 비교
            print()
            print('=== 📈 이전 결과와 비교 ===')
            print('기존 button-next 방식: 25개 → 50개 (4단계 전략)')
            print(f'새로운 JavaScript 파싱: {len(shorts_data)}개 (1단계 만으로)')
            
            if len(shorts_data) >= 50:
                improvement = ((len(shorts_data) - 50) / 50) * 100
                print(f'🚀 성능 향상: +{improvement:.1f}% (50개 → {len(shorts_data)}개)')
            elif len(shorts_data) >= 25:
                improvement = ((len(shorts_data) - 25) / 25) * 100
                print(f'📊 개선 결과: +{improvement:.1f}% (25개 → {len(shorts_data)}개)')
            else:
                print(f'📉 이전보다 감소: {len(shorts_data)}개')
            
            # 장점 분석
            print()
            print('=== ✨ JavaScript 파싱의 장점 ===')
            print('✅ button-next 클릭 불필요 (안정성 향상)')
            print('✅ 페이지 로딩 1회만으로 충분 (속도 향상)')
            print('✅ 원본 데이터 직접 접근 (정확성 향상)')
            print('✅ 조회수, 제목 등 풍부한 메타데이터')
            print('✅ YouTube 구조 변경에 더 안정적')
            
        else:
            print('❌ 수집된 데이터가 없습니다.')
            print('디버깅이 필요합니다.')
        
    except Exception as e:
        print(f'❌ 테스트 실패: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_javascript_parsing() 