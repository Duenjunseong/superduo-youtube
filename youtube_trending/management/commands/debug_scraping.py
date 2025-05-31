"""
YouTube 트렌딩 페이지 HTML 구조 디버깅 명령어
"""

from django.core.management.base import BaseCommand
from youtube_trending.services import YouTubeTrendingScraper
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'YouTube 트렌딩 페이지 HTML 구조를 디버깅합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--save-html',
            action='store_true',
            help='HTML을 파일로 저장',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.HTTP_INFO('YouTube 트렌딩 페이지 HTML 디버깅 시작')
        )

        try:
            scraper = YouTubeTrendingScraper()
            
            # HTML 콘텐츠 가져오기
            html_content = scraper.get_trending_page_content()
            
            if options['save_html']:
                # HTML을 파일로 저장
                with open('youtube_trending_debug.html', 'w', encoding='utf-8') as f:
                    f.write(html_content)
                self.stdout.write(
                    self.style.SUCCESS('HTML이 youtube_trending_debug.html 파일로 저장되었습니다.')
                )
            
            # BeautifulSoup으로 파싱
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 쇼츠 관련 요소들 찾기
            self.stdout.write('\n=== 쇼츠 관련 요소 찾기 ===')
            
            # 1. "Shorts" 텍스트가 포함된 요소들
            shorts_elements = soup.find_all(string=lambda text: text and 'shorts' in text.lower())
            self.stdout.write(f'📍 "Shorts" 텍스트 포함 요소: {len(shorts_elements)}개')
            for i, elem in enumerate(shorts_elements[:5]):  # 처음 5개만
                self.stdout.write(f'  {i+1}. {elem.strip()[:100]}...')
            
            # 2. reel 관련 클래스들
            reel_elements = soup.find_all(class_=lambda x: x and 'reel' in x.lower())
            self.stdout.write(f'\n📍 "reel" 클래스 요소: {len(reel_elements)}개')
            for i, elem in enumerate(reel_elements[:5]):
                classes = elem.get('class', [])
                self.stdout.write(f'  {i+1}. 클래스: {classes}')
            
            # 3. shorts 관련 클래스들
            shorts_class_elements = soup.find_all(class_=lambda x: x and 'shorts' in x.lower())
            self.stdout.write(f'\n📍 "shorts" 클래스 요소: {len(shorts_class_elements)}개')
            for i, elem in enumerate(shorts_class_elements[:5]):
                classes = elem.get('class', [])
                self.stdout.write(f'  {i+1}. 클래스: {classes}')
            
            # 4. shelf 관련 요소들
            shelf_elements = soup.find_all(class_=lambda x: x and 'shelf' in x.lower())
            self.stdout.write(f'\n📍 "shelf" 클래스 요소: {len(shelf_elements)}개')
            for i, elem in enumerate(shelf_elements[:5]):
                classes = elem.get('class', [])
                self.stdout.write(f'  {i+1}. 클래스: {classes}')
            
            # 5. trending 관련 요소들
            trending_elements = soup.find_all(class_=lambda x: x and 'trending' in x.lower())
            self.stdout.write(f'\n📍 "trending" 클래스 요소: {len(trending_elements)}개')
            for i, elem in enumerate(trending_elements[:5]):
                classes = elem.get('class', [])
                self.stdout.write(f'  {i+1}. 클래스: {classes}')
            
            # 6. 동영상 링크들 (shorts 포함)
            video_links = soup.find_all('a', href=lambda x: x and ('/shorts/' in x or '/watch' in x))
            self.stdout.write(f'\n📍 동영상 링크: {len(video_links)}개')
            
            shorts_links = [link for link in video_links if '/shorts/' in link.get('href', '')]
            self.stdout.write(f'📍 쇼츠 링크: {len(shorts_links)}개')
            
            for i, link in enumerate(shorts_links[:5]):
                href = link.get('href', '')
                title_elem = link.find(string=True)
                title = title_elem.strip() if title_elem else 'No title'
                self.stdout.write(f'  {i+1}. {href} - {title[:50]}...')
            
            # 7. 특별한 구조 찾기
            self.stdout.write('\n=== 특별한 구조 찾기 ===')
            
            # ytd- 태그들
            ytd_elements = soup.find_all(lambda tag: tag.name and tag.name.startswith('ytd-'))
            unique_ytd_tags = set(elem.name for elem in ytd_elements)
            self.stdout.write(f'📍 ytd- 태그 종류: {len(unique_ytd_tags)}개')
            for tag in list(unique_ytd_tags)[:10]:
                count = len(soup.find_all(tag))
                self.stdout.write(f'  - {tag}: {count}개')
            
            # ytm- 태그들
            ytm_elements = soup.find_all(lambda tag: tag.name and tag.name.startswith('ytm-'))
            unique_ytm_tags = set(elem.name for elem in ytm_elements)
            self.stdout.write(f'\n📍 ytm- 태그 종류: {len(unique_ytm_tags)}개')
            for tag in list(unique_ytm_tags)[:10]:
                count = len(soup.find_all(tag))
                self.stdout.write(f'  - {tag}: {count}개')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'디버깅 중 오류 발생: {str(e)}')
            )
            logger.error(f'HTML 디버깅 실패: {e}', exc_info=True) 