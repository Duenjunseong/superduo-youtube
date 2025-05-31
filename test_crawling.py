#!/usr/bin/env python3
"""
크롤링 코드 테스트 스크립트
"""
import os
import sys
import django

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from youtube_trending.services import YouTubeTrendingScraper

def test_crawling():
    print('=== 크롤링 코드 테스트 시작 ===')
    
    scraper = YouTubeTrendingScraper(use_metadata_enhancement=False)
    
    try:
        # 1. WebDriver 설정 테스트
        print('1. WebDriver 설정 중...')
        scraper.driver = scraper._setup_driver()
        print('✅ WebDriver 설정 성공')
        
        # 2. 페이지 로드 테스트
        print('2. YouTube 트렌딩 페이지 로드 중...')
        scraper.driver.get('https://www.youtube.com/feed/trending')
        
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        wait = WebDriverWait(scraper.driver, 15)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        scraper._add_random_delay(3, 5)
        
        html_content = scraper.driver.page_source
        print(f'✅ 페이지 로드 성공: {len(html_content):,} bytes')
        
        # 3. 쇼츠 추출 테스트
        print('3. 쇼츠 데이터 추출 중...')
        shorts_data = scraper.extract_shorts_from_html(html_content)
        
        print(f'✅ 추출된 쇼츠: {len(shorts_data)}개')
        
        # 상위 5개 출력
        for i, shorts in enumerate(shorts_data[:5], 1):
            youtube_id = shorts.get('youtube_id', '')
            title = shorts.get('title', '')[:50]
            view_count = shorts.get('view_count', 0)
            print(f'  {i}. {youtube_id} - {title}... (조회수: {view_count:,})')
        
        # 4. 결과 요약
        print(f'\n=== 테스트 결과 ===')
        print(f'총 수집된 쇼츠: {len(shorts_data)}개')
        
        if len(shorts_data) >= 5:
            print('✅ 크롤링 성공: 충분한 데이터 수집')
            return True
        elif len(shorts_data) > 0:
            print('⚠️  크롤링 부분 성공: 일부 데이터 수집')
            return True
        else:
            print('❌ 크롤링 실패: 데이터 없음')
            return False
            
    except Exception as e:
        print(f'❌ 크롤링 테스트 실패: {e}')
        return False
        
    finally:
        if scraper.driver:
            try:
                scraper.driver.quit()
                print('WebDriver 종료 완료')
            except Exception as e:
                print(f'WebDriver 종료 중 오류: {e}')

if __name__ == '__main__':
    success = test_crawling()
    sys.exit(0 if success else 1) 