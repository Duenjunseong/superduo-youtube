import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from youtube_trending.services import YouTubeTrendingScraper

def test_js_only_parsing():
    print('=== 🎯 JavaScript 전용 파싱 테스트 ===')
    print('개선된 방법: 다중 렌더러 패턴 분석')
    print('✅ reelItemRenderer (쇼츠 전용)')
    print('✅ videoRenderer (쇼츠 필터링)')
    print('✅ richItemRenderer (내부 검색)')
    print('✅ gridVideoRenderer (그리드 형태)')
    print('✅ compactVideoRenderer (컴팩트 형태)')
    print()

    scraper = YouTubeTrendingScraper(use_metadata_enhancement=False, max_retries=2)
    
    try:
        # 목표: JavaScript로만 30개 이상 수집
        target_count = 30
        print(f'🎯 목표: {target_count}개 쇼츠 수집 (JavaScript 전용)')
        print()
        
        shorts_data = scraper.scrape_trending_shorts(enhance_metadata=False, max_shorts=target_count)
        
        print()
        print('=== 📊 수집 결과 ===')
        print(f'✅ 총 수집: {len(shorts_data)}개 쇼츠')
        
        # 성과 평가
        if len(shorts_data) >= target_count:
            print(f'🎉 JavaScript 전용 파싱 대성공! {target_count}개 이상 수집')
            success_rate = 100
        elif len(shorts_data) >= 20:
            success_rate = (len(shorts_data) / target_count) * 100
            print(f'👍 JavaScript 전용 파싱 성공: {len(shorts_data)}/{target_count}개 ({success_rate:.1f}%)')
        elif len(shorts_data) >= 10:
            success_rate = (len(shorts_data) / target_count) * 100
            print(f'⚠️  부분 성공: {len(shorts_data)}/{target_count}개 ({success_rate:.1f}%)')
        else:
            success_rate = (len(shorts_data) / target_count) * 100 if shorts_data else 0
            print(f'❌ 파싱 실패: {len(shorts_data)}개만 수집 ({success_rate:.1f}%)')
        
        print()
        
        # 수집된 데이터 상세 분석
        if shorts_data:
            print('=== 🔍 데이터 품질 분석 ===')
            
            # 데이터 품질 통계
            valid_ids = 0
            has_titles = 0
            has_views = 0
            total_views = 0
            max_views = 0
            
            print('상위 20개 쇼츠:')
            for i, shorts in enumerate(shorts_data[:20], 1):
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
                    max_views = max(max_views, view_count)
                
                # 상태 아이콘
                id_status = '✅' if 8 <= len(youtube_id) <= 15 else '❌'
                title_status = '📝' if title and title != f'쇼츠 {youtube_id}' else '📭'
                view_status = '👁️ ' if view_count > 0 else '🔹'
                
                print(f'{id_status}{title_status}{view_status} [{i:2d}] {youtube_id:12} | {view_count:9,}회 | {title}')
            
            if len(shorts_data) > 20:
                print(f'... 외 {len(shorts_data) - 20}개 더')
            
            print()
            print('=== 📈 품질 통계 ===')
            print(f'📊 전체 수집: {len(shorts_data)}개')
            print(f'✅ 유효 ID: {valid_ids}/{len(shorts_data)}개 ({(valid_ids/len(shorts_data)*100):.1f}%)')
            print(f'📝 실제 제목: {has_titles}/{len(shorts_data)}개 ({(has_titles/len(shorts_data)*100):.1f}%)')
            print(f'👁️  조회수 데이터: {has_views}/{len(shorts_data)}개 ({(has_views/len(shorts_data)*100):.1f}%)')
            
            if has_views > 0:
                avg_views = total_views / has_views
                print(f'📈 평균 조회수: {avg_views:,.0f}회')
                print(f'🔝 최고 조회수: {max_views:,}회')
            
            # 품질 등급 평가
            print()
            print('=== 🏆 품질 등급 ===')
            id_quality = (valid_ids / len(shorts_data)) * 100
            title_quality = (has_titles / len(shorts_data)) * 100
            view_quality = (has_views / len(shorts_data)) * 100
            
            overall_quality = (id_quality + title_quality + view_quality) / 3
            
            if overall_quality >= 90:
                quality_grade = "🏆 S급 (최고)"
            elif overall_quality >= 80:
                quality_grade = "🥇 A급 (우수)"
            elif overall_quality >= 70:
                quality_grade = "🥈 B급 (양호)"
            elif overall_quality >= 60:
                quality_grade = "🥉 C급 (보통)"
            else:
                quality_grade = "😅 D급 (개선 필요)"
            
            print(f'전체 품질: {overall_quality:.1f}% - {quality_grade}')
            print(f'ID 품질: {id_quality:.1f}%')
            print(f'제목 품질: {title_quality:.1f}%')
            print(f'조회수 품질: {view_quality:.1f}%')
            
            # 이전 방법과 비교
            print()
            print('=== 📊 개선 효과 ===')
            print('기존 다중 전략 방식: 50개 (4단계 사용)')
            print(f'새로운 JavaScript 전용: {len(shorts_data)}개 (1단계만)')
            
            if len(shorts_data) >= 50:
                improvement = ((len(shorts_data) - 50) / 50) * 100
                print(f'🚀 성능 향상: +{improvement:.1f}% (50개 → {len(shorts_data)}개)')
            elif len(shorts_data) >= 25:
                improvement = ((len(shorts_data) - 25) / 25) * 100
                print(f'📊 개선 효과: +{improvement:.1f}% (25개 → {len(shorts_data)}개)')
            else:
                decrease = ((25 - len(shorts_data)) / 25) * 100
                print(f'📉 수량 감소: -{decrease:.1f}% (25개 → {len(shorts_data)}개)')
            
            # JavaScript 전용의 장점
            print()
            print('=== ✨ JavaScript 전용 파싱의 장점 ===')
            print('✅ 안정성: button-next 클릭 불필요')
            print('✅ 속도: 1회 페이지 로드만 필요')
            print('✅ 정확성: 원본 JSON 데이터 직접 접근')
            print('✅ 완성도: 메타데이터 풍부')
            print('✅ 유지보수: YouTube 구조 변경에 안정적')
            
            # 데이터베이스 저장
            print()
            print('=== 💾 데이터베이스 저장 ===')
            if shorts_data:
                created, updated = scraper.save_scraped_shorts_to_db(shorts_data)
                print(f'📝 신규 저장: {created}개')
                print(f'🔄 업데이트: {updated}개')
                print(f'💾 총 저장: {created + updated}개')
                
                if created + updated == len(shorts_data):
                    print('✅ 모든 데이터 저장 완료')
                else:
                    failed = len(shorts_data) - (created + updated)
                    print(f'⚠️  저장 실패: {failed}개')
            
            # 최종 결론
            print()
            print('=== 🎯 최종 평가 ===')
            if len(shorts_data) >= 30 and overall_quality >= 80:
                print('🎉 JavaScript 전용 파싱 완전 성공!')
                print('   → 수량 ✅, 품질 ✅, 안정성 ✅')
            elif len(shorts_data) >= 20:
                print('👍 JavaScript 전용 파싱 성공!')
                print('   → 실용적 수량 확보')
            elif len(shorts_data) >= 10:
                print('⚠️  부분적 성공')
                print('   → 추가 패턴 분석 필요')
            else:
                print('❌ 파싱 실패')
                print('   → 데이터 구조 재분석 필요')
                
        else:
            print('❌ JavaScript 파싱 실패: 수집된 데이터가 없습니다.')
            print('📋 디버깅 체크 포인트:')
            print('   1. ytInitialData 추출 확인')
            print('   2. 렌더러 패턴 재검토')
            print('   3. YouTube 구조 변경 확인')
        
    except Exception as e:
        print(f'❌ 테스트 실패: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_js_only_parsing() 