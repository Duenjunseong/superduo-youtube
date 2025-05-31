import os
import sys
import django
import json
import re
from collections import Counter

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from youtube_trending.services import YouTubeTrendingScraper

def debug_youtube_structure():
    print('=== 🔍 YouTube 데이터 구조 디버깅 ===')
    print('실제 YouTube 트렌딩 페이지의 JSON 구조를 분석합니다.')
    print()

    scraper = YouTubeTrendingScraper(use_metadata_enhancement=False, max_retries=2)
    
    try:
        # WebDriver 설정
        scraper.driver = scraper._setup_driver_with_retry()
        
        # 트렌딩 페이지 로드
        print('1️⃣ YouTube 트렌딩 페이지 로드 중...')
        scraper.driver.get(scraper.trending_url)
        
        # 페이지 로딩 대기
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        wait = WebDriverWait(scraper.driver, 15)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        scraper._add_random_delay(3, 5)
        
        # 스크롤
        scraper._scroll_to_load_content()
        
        # HTML 소스 가져오기
        html_content = scraper.driver.page_source
        print(f'2️⃣ HTML 소스 크기: {len(html_content):,} bytes')
        
        # ytInitialData 추출
        print('3️⃣ ytInitialData 추출 중...')
        yt_initial_data = scraper._extract_yt_initial_data(html_content)
        
        if not yt_initial_data:
            print('❌ ytInitialData를 찾을 수 없습니다.')
            return
        
        print(f'✅ ytInitialData 추출 성공 (크기: {len(str(yt_initial_data)):,} bytes)')
        
        # 4️⃣ 모든 키 수집 및 분석
        print('4️⃣ 전체 키 구조 분석 중...')
        all_keys = []
        video_related_keys = []
        
        def collect_keys(data, path="", depth=0):
            if depth > 10:  # 깊이 제한
                return
            
            if isinstance(data, dict):
                for key, value in data.items():
                    current_path = f"{path}.{key}" if path else key
                    all_keys.append(key.lower())
                    
                    # 비디오/쇼츠 관련 키 필터링
                    key_lower = key.lower()
                    if any(pattern in key_lower for pattern in [
                        'video', 'reel', 'shorts', 'item', 'renderer', 'content', 'watch'
                    ]):
                        video_related_keys.append(current_path)
                    
                    if isinstance(value, (dict, list)) and depth < 8:
                        collect_keys(value, current_path, depth + 1)
                        
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    if isinstance(item, (dict, list)) and depth < 8:
                        collect_keys(item, f"{path}[{i}]" if path else f"[{i}]", depth + 1)
        
        collect_keys(yt_initial_data)
        
        # 키 통계
        key_counter = Counter(all_keys)
        print(f'✅ 총 {len(all_keys)}개 키 발견, 고유 키 {len(key_counter)}개')
        
        # 5️⃣ 비디오 관련 키 분석
        print()
        print('5️⃣ 비디오/쇼츠 관련 키 분석:')
        
        # 렌더러 관련 키 찾기
        renderer_keys = [key for key in video_related_keys if 'renderer' in key.lower()]
        print(f'📦 렌더러 키: {len(renderer_keys)}개')
        
        for key in sorted(set(renderer_keys))[:20]:  # 상위 20개만
            print(f'   - {key}')
        
        if len(renderer_keys) > 20:
            print(f'   ... 외 {len(renderer_keys) - 20}개 더')
        
        # 6️⃣ 특정 패턴 검색
        print()
        print('6️⃣ 특정 패턴 검색:')
        
        patterns_to_search = [
            'reelitemrenderer',
            'videorenderer', 
            'richitemrenderer',
            'gridvideorenderer',
            'compactvideorenderer',
            'shortsrenderer',
            'shortslockup',
            'reelwatchendpoint',
            'thumbnailoverlay'
        ]
        
        for pattern in patterns_to_search:
            matches = [key for key in video_related_keys if pattern in key.lower()]
            print(f'🔍 {pattern}: {len(matches)}개')
            if matches:
                for match in matches[:5]:  # 상위 5개만
                    print(f'   → {match}')
                if len(matches) > 5:
                    print(f'   ... 외 {len(matches) - 5}개 더')
        
        # 7️⃣ 실제 데이터 샘플 추출
        print()
        print('7️⃣ 실제 데이터 샘플 추출:')
        
        def find_sample_data(data, target_patterns, path="", depth=0, samples=None):
            if samples is None:
                samples = {}
            if depth > 15 or len(samples) >= 3:  # 각 패턴당 3개씩만
                return samples
            
            if isinstance(data, dict):
                for key, value in data.items():
                    current_path = f"{path}.{key}" if path else key
                    key_lower = key.lower()
                    
                    for pattern in target_patterns:
                        if pattern in key_lower and pattern not in samples:
                            samples[pattern] = {
                                'path': current_path,
                                'data': value,
                                'type': type(value).__name__
                            }
                            print(f'📍 {pattern} 샘플 발견: {current_path}')
                            if isinstance(value, dict):
                                sample_keys = list(value.keys())[:10]
                                print(f'   키들: {sample_keys}')
                            elif isinstance(value, list) and value:
                                print(f'   배열 크기: {len(value)}')
                                if isinstance(value[0], dict):
                                    first_keys = list(value[0].keys())[:10]
                                    print(f'   첫 항목 키들: {first_keys}')
                    
                    if isinstance(value, (dict, list)) and depth < 10:
                        find_sample_data(value, target_patterns, current_path, depth + 1, samples)
                        
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    if isinstance(item, (dict, list)) and depth < 10:
                        find_sample_data(item, target_patterns, f"{path}[{i}]" if path else f"[{i}]", depth + 1, samples)
            
            return samples
        
        # 샘플 데이터 찾기
        target_patterns = ['videorenderer', 'reelitemrenderer', 'richitemrenderer']
        samples = find_sample_data(yt_initial_data, target_patterns)
        
        # 8️⃣ /shorts/ URL 검색
        print()
        print('8️⃣ /shorts/ URL 직접 검색:')
        
        def find_shorts_urls(data, path="", depth=0, urls=None):
            if urls is None:
                urls = []
            if depth > 10 or len(urls) >= 10:
                return urls
            
            if isinstance(data, str) and '/shorts/' in data:
                urls.append({'url': data, 'path': path})
            elif isinstance(data, dict):
                for key, value in data.items():
                    current_path = f"{path}.{key}" if path else key
                    find_shorts_urls(value, current_path, depth + 1, urls)
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    current_path = f"{path}[{i}]" if path else f"[{i}]"
                    find_shorts_urls(item, current_path, depth + 1, urls)
            
            return urls
        
        shorts_urls = find_shorts_urls(yt_initial_data)
        print(f'🔗 발견된 /shorts/ URL: {len(shorts_urls)}개')
        
        for i, url_info in enumerate(shorts_urls[:10], 1):
            url = url_info['url']
            if '/shorts/' in url:
                video_id = url.split('/shorts/')[-1].split('?')[0]
                if len(video_id) >= 8:
                    print(f'   {i}. {video_id} → {url_info["path"]}')
        
        if len(shorts_urls) > 10:
            print(f'   ... 외 {len(shorts_urls) - 10}개 더')
        
        # 9️⃣ 결론 및 권장사항
        print()
        print('9️⃣ 분석 결론:')
        
        if samples:
            print('✅ 비디오 렌더러 패턴 발견됨')
            print('💡 권장사항: 발견된 패턴으로 파싱 로직 수정')
        elif shorts_urls:
            print('⚠️  렌더러 패턴 없음, URL만 발견')
            print('💡 권장사항: URL 기반 추출 로직 구현')
        else:
            print('❌ 쇼츠 관련 데이터 발견되지 않음')
            print('💡 권장사항: YouTube 구조 변경, 다른 접근 방법 필요')
        
        # 🔟 가장 유망한 패턴 제안
        print()
        print('🔟 가장 유망한 패턴:')
        
        if samples:
            for pattern, info in samples.items():
                print(f'🎯 {pattern}: {info["path"]}')
        
        if shorts_urls:
            print(f'🎯 /shorts/ URL 패턴: {len(shorts_urls)}개 발견')
    
    except Exception as e:
        print(f'❌ 디버깅 실패: {e}')
        import traceback
        traceback.print_exc()
    
    finally:
        if scraper.driver:
            scraper.driver.quit()

if __name__ == '__main__':
    debug_youtube_structure() 