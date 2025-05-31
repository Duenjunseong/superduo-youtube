"""
YouTube 트렌딩 쇼츠 수집 서비스 (Selenium + yt-dlp)
"""
import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple
import re
import os
import json
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from django.db import models

from .models import TrendingVideo, TrendingStats

# Selenium 관련 import
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# yt-dlp import
import yt_dlp

logger = logging.getLogger(__name__)

# 스레드 로컬 스토리지로 yt-dlp 인스턴스 관리
_thread_local = threading.local()


def get_thread_local_ydl():
    """스레드별 yt-dlp 인스턴스를 가져오거나 생성합니다."""
    if not hasattr(_thread_local, 'ydl'):
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'writeinfojson': False,
            'writethumbnail': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'skip_download': True,
            'ignoreerrors': True,
        }
        _thread_local.ydl = yt_dlp.YoutubeDL(ydl_opts)
    return _thread_local.ydl


class YouTubeTrendingScraper:
    """Selenium을 사용한 YouTube 트렌딩 쇼츠 스크래핑 서비스 (JSON 파싱 버전)"""
    
    def __init__(self, use_metadata_enhancement=True, max_retries=3):
        self.trending_url = "https://www.youtube.com/feed/trending"
        self.driver = None
        self.use_metadata_enhancement = use_metadata_enhancement
        self.max_retries = max_retries
        
        # Selenium 타임아웃 설정
        self.page_load_timeout = 30
        self.element_wait_timeout = 15
    
    def _setup_driver(self) -> webdriver.Chrome:
        """Chrome WebDriver를 설정하고 반환합니다."""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument(
                '--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            chrome_options.add_argument('--lang=ko-KR')
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.set_page_load_timeout(self.page_load_timeout)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("Chrome WebDriver 설정 완료")
            return driver
            
        except Exception as e:
            logger.error(f"WebDriver 설정 실패: {e}")
            raise
    
    def _add_random_delay(self, min_seconds=1, max_seconds=3):
        """랜덤 딜레이 추가 (봇 감지 방지)"""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
    
    def _scroll_to_load_content(self):
        """페이지를 스크롤하여 동적 콘텐츠를 모두 로드합니다."""
        try:
            logger.info("페이지 스크롤을 통한 동적 콘텐츠 로드 시작...")
            
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            scroll_attempts = 0
            max_scroll_attempts = 5
            
            while scroll_attempts < max_scroll_attempts:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                self._add_random_delay(2, 3)
                
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                
                last_height = new_height
                scroll_attempts += 1
                logger.debug(f"스크롤 완료 ({scroll_attempts}/{max_scroll_attempts})")
            
            self.driver.execute_script("window.scrollTo(0, 0);")
            self._add_random_delay(1, 2)
            logger.info(f"스크롤 완료 (총 {scroll_attempts}회)")
            
        except Exception as e:
            logger.warning(f"스크롤 중 오류: {e}")
    
    def extract_shorts_from_html(self, html_content: str) -> List[Dict]:
        """HTML에서 ytInitialData JSON을 추출하여 쇼츠 정보를 파싱합니다."""
        try:
            logger.info("ytInitialData JSON에서 쇼츠 정보 추출 시작...")
            
            # 1. ytInitialData JSON 추출
            match = re.search(r"ytInitialData\s*=\s*(\{.*?\});", html_content, re.S)
            if not match:
                logger.error("ytInitialData를 찾지 못했습니다")
                return []
            
            initial_json = match.group(1)
            data = json.loads(initial_json)
            logger.debug("ytInitialData JSON 파싱 완료")
            
            # 2. shortsLockupViewModel 노드들 찾기
            shorts_nodes = list(self._find_shorts_nodes(data))
            logger.info(f"발견된 shortsLockupViewModel 객체: {len(shorts_nodes)}개")
            
            # 3. 쇼츠 정보 추출
            shorts_data = []
            seen_ids = set()
            
            for i, shorts_node in enumerate(shorts_nodes, 1):
                try:
                    # video_id 추출
                    video_id = (
                        shorts_node.get("onTap", {})
                        .get("innertubeCommand", {})
                        .get("reelWatchEndpoint", {})
                        .get("videoId")
                    )
                    
                    if not video_id or video_id in seen_ids:
                        continue
                    
                    if not re.match(r'^[a-zA-Z0-9_-]{8,15}$', video_id):
                        continue
                    
                    seen_ids.add(video_id)
                    
                    # 썸네일 URL 추출
                    thumbnail_url = ""
                    thumbnail_sources = shorts_node.get("thumbnail", {}).get("sources", [])
                    if thumbnail_sources:
                        thumbnail_url = thumbnail_sources[0].get("url", "")
                    
                    # 제목 추출 (accessibilityText에서 첫 번째 부분)
                    accessibility_text = shorts_node.get("accessibilityText", "")
                    title = accessibility_text.split(",")[0].strip() if accessibility_text else f'쇼츠 {video_id}'
                    
                    shorts_info = {
                        'youtube_id': video_id,
                        'title': title[:500] if title else f'쇼츠 {video_id}',
                        'view_count': 0,  # 초기값, yt-dlp로 보강
                        'thumbnail_url': thumbnail_url,
                        'trending_rank': len(shorts_data) + 1,
                        'trending_date': date.today(),
                        'region_code': 'KR',
                        'is_shorts': True,
                        'category': 'other',
                        'channel_title': '',
                        'channel_id': '',
                        'like_count': 0,
                        'comment_count': 0,
                        'published_at': timezone.now(),
                        'duration': 'PT60S',
                        'description': '',
                        'tags': [],
                    }
                    
                    shorts_data.append(shorts_info)
                    logger.debug(f"JSON 파싱 [{i}]: {video_id} - {title[:30]}...")
                    
                except Exception as e:
                    logger.debug(f"쇼츠 노드 처리 실패 [{i}]: {e}")
                    continue
            
            logger.info(f"JSON 파싱 완료: {len(shorts_data)}개 쇼츠")
            return shorts_data
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}")
            return []
        except Exception as e:
            logger.error(f"쇼츠 추출 실패: {e}")
            return []
    
    def _find_shorts_nodes(self, node):
        """재귀 순회하며 shortsLockupViewModel 노드를 찾습니다."""
        if isinstance(node, dict):
            if "shortsLockupViewModel" in node:
                yield node["shortsLockupViewModel"]
            for value in node.values():
                yield from self._find_shorts_nodes(value)
        elif isinstance(node, list):
            for item in node:
                yield from self._find_shorts_nodes(item)
    
    def scrape_trending_shorts(self, enhance_metadata=True, max_shorts=50) -> List[Dict]:
        """YouTube 트렌딩 쇼츠를 수집합니다."""
        try:
            logger.info(f"YouTube 트렌딩 쇼츠 스크래핑 시작 (목표: {max_shorts}개)")
            
            # WebDriver 설정
            self.driver = self._setup_driver()
            
            # 트렌딩 페이지 로드
            logger.info("YouTube 트렌딩 페이지 로드 중...")
            self.driver.get(self.trending_url)
            
            # 페이지 기본 로딩 대기
            wait = WebDriverWait(self.driver, self.element_wait_timeout)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            self._add_random_delay(3, 5)
            
            # 스크롤로 콘텐츠 로드
            self._scroll_to_load_content()
            
            # HTML 소스 가져오기
            html_content = self.driver.page_source
            logger.info(f"페이지 소스 크기: {len(html_content):,} bytes")
            
            # 쇼츠 추출
            shorts_data = self.extract_shorts_from_html(html_content)
            
            if not shorts_data:
                logger.error("쇼츠를 찾지 못했습니다.")
                return []
            
            # 목표 수량으로 제한
            shorts_data = shorts_data[:max_shorts]
            logger.info(f"기본 스크래핑 완료: {len(shorts_data)}개 쇼츠")
            
            # yt-dlp를 사용한 메타데이터 보강
            if enhance_metadata and self.use_metadata_enhancement and shorts_data:
                logger.info("yt-dlp를 사용한 메타데이터 보강 시작...")
                try:
                    metadata_extractor = YouTubeMetadataExtractor()
                    enhanced_data = metadata_extractor.enhance_shorts_data(
                        shorts_data, 
                        use_parallel=len(shorts_data) > 3
                    )
                    
                    # 메타데이터 보강 후 조회수 기준 정렬
                    enhanced_data.sort(key=lambda x: x.get('view_count', 0), reverse=True)
                    
                    # 순위 재부여
                    for i, shorts in enumerate(enhanced_data, 1):
                        shorts['trending_rank'] = i
                    
                    shorts_data = enhanced_data
                    logger.info("메타데이터 보강 및 재정렬 완료")
                    
                except Exception as e:
                    logger.error(f"메타데이터 보강 실패, 기본 데이터 사용: {e}")
            
            # 데이터 검증
            validated_data = self._validate_shorts_data(shorts_data)
            
            logger.info(f"쇼츠 스크래핑 완료: {len(validated_data)}개")
            return validated_data
            
        except Exception as e:
            logger.error(f"쇼츠 스크래핑 실패: {e}")
            raise
        finally:
            # WebDriver 정리
            if self.driver:
                try:
                    self.driver.quit()
                    logger.debug("WebDriver 종료 완료")
                except Exception as e:
                    logger.warning(f"WebDriver 종료 중 오류: {e}")
                finally:
                    self.driver = None
    
    def _validate_shorts_data(self, shorts_data: List[Dict]) -> List[Dict]:
        """스크래핑된 데이터의 품질을 검증하고 필터링합니다."""
        validated_data = []
        
        logger.info(f"검증 시작: {len(shorts_data)}개 쇼츠 데이터")
        
        for i, shorts in enumerate(shorts_data, 1):
            try:
                # 필수 필드 검증
                if not shorts.get('youtube_id'):
                    logger.warning(f"[{i}] YouTube ID가 없는 데이터 스킵")
                    continue
                
                if not shorts.get('title'):
                    logger.warning(f"[{i}] 제목이 없는 데이터 스킵: {shorts['youtube_id']}")
                    continue
                
                # YouTube ID 형식 검증
                youtube_id = shorts['youtube_id']
                if not re.match(r'^[a-zA-Z0-9_-]{8,15}$', youtube_id):
                    logger.warning(f"[{i}] 잘못된 YouTube ID 형식: {youtube_id}")
                    continue
                
                # 조회수 검증
                view_count = shorts.get('view_count', 0)
                if not isinstance(view_count, int) or view_count < 0:
                    shorts['view_count'] = 0
                
                # 중복 제거
                if any(existing['youtube_id'] == youtube_id for existing in validated_data):
                    logger.warning(f"[{i}] 중복 데이터 스킵: {youtube_id}")
                    continue
                
                validated_data.append(shorts)
                
            except Exception as e:
                logger.warning(f"[{i}] 데이터 검증 중 오류: {e}")
                continue
        
        logger.info(f"데이터 검증 완료: {len(shorts_data)}개 → {len(validated_data)}개")
        return validated_data
    
    def save_scraped_shorts_to_db(self, shorts_data: List[Dict]) -> Tuple[int, int]:
        """스크래핑된 쇼츠 데이터를 데이터베이스에 저장합니다."""
        created_count = 0
        updated_count = 0
        error_count = 0
        skipped_count = 0
        
        for shorts_info in shorts_data:
            try:
                # 데이터 전처리
                processed_data = self._prepare_data_for_db(shorts_info)
                if not processed_data:
                    continue
                
                # 같은 날짜에 동일한 영상이 이미 있는지 확인 (중복 방지)
                existing_video = TrendingVideo.objects.filter(
                    youtube_id=processed_data['youtube_id'],
                    trending_date=processed_data['trending_date']
                ).first()
                
                if existing_video:
                    # 이미 오늘 수집된 영상은 스킵
                    skipped_count += 1
                    logger.debug(f"오늘 이미 수집된 쇼츠 스킵: {processed_data['youtube_id']}")
                    continue
                
                # 항상 새로운 데이터 생성 (날짜별 트렌드 추적을 위해)
                TrendingVideo.objects.create(**processed_data)
                created_count += 1
                logger.debug(f"새 쇼츠 생성: {processed_data['youtube_id']} (날짜: {processed_data['trending_date']})")
                
            except Exception as e:
                error_count += 1
                logger.error(f"쇼츠 데이터 저장 실패 ({shorts_info.get('youtube_id', 'Unknown')}): {e}")
                continue
        
        logger.info(f"데이터베이스 저장 완료 - 생성: {created_count}, 스킵: {skipped_count}, 오류: {error_count}")
        return created_count, 0  # updated_count는 항상 0
    
    def _prepare_data_for_db(self, shorts_info: Dict) -> Optional[Dict]:
        """데이터베이스 저장을 위한 데이터 전처리."""
        try:
            if not shorts_info.get('youtube_id'):
                return None
            
            # 기본값 설정
            defaults = {
                'title': '',
                'description': '',
                'channel_title': '',
                'channel_id': '',
                'view_count': 0,
                'like_count': 0,
                'comment_count': 0,
                'trending_rank': 999,
                'trending_date': date.today(),
                'region_code': 'KR',
                'is_shorts': True,
                'category': 'other',
                'published_at': timezone.now(),
                'duration': 'PT60S',
                'thumbnail_url': '',
                'tags': [],
            }
            
            prepared_data = {**defaults, **shorts_info}
            
            # 데이터 타입 검증
            prepared_data['view_count'] = max(0, int(prepared_data.get('view_count', 0)))
            prepared_data['like_count'] = max(0, int(prepared_data.get('like_count', 0)))
            prepared_data['comment_count'] = max(0, int(prepared_data.get('comment_count', 0)))
            prepared_data['trending_rank'] = max(1, int(prepared_data.get('trending_rank', 999)))
            
            # 문자열 길이 제한
            prepared_data['title'] = str(prepared_data['title'])[:500]
            prepared_data['channel_title'] = str(prepared_data['channel_title'])[:100]
            prepared_data['channel_id'] = str(prepared_data['channel_id'])[:50]
            
            if not isinstance(prepared_data['tags'], list):
                prepared_data['tags'] = []
            
            return prepared_data
            
        except Exception as e:
            logger.error(f"데이터 전처리 실패: {e}")
            return None


class YouTubeMetadataExtractor:
    """yt-dlp를 사용한 YouTube 메타데이터 추출 클래스"""
    
    def __init__(self, max_workers=4, use_cache=True, cache_timeout=3600):
        self.max_workers = max_workers
        self.use_cache = use_cache
        self.cache_timeout = cache_timeout
    
    def _extract_single_metadata(self, youtube_id: str) -> Optional[Dict]:
        """단일 비디오의 메타데이터를 추출합니다."""
        try:
            # 캐시 확인
            if self.use_cache:
                cache_key = f"youtube_metadata_{youtube_id}"
                cached_data = cache.get(cache_key)
                if cached_data:
                    logger.debug(f"캐시에서 메타데이터 반환: {youtube_id}")
                    return cached_data
            
            # yt-dlp로 추출
            url = f"https://www.youtube.com/watch?v={youtube_id}"
            ydl = get_thread_local_ydl()
            info = ydl.extract_info(url, download=False)
            
            if not info:
                return None
            
            # 메타데이터 정리
            metadata = self._process_video_info(info, youtube_id)
            
            # 캐시에 저장
            if self.use_cache:
                cache.set(cache_key, metadata, self.cache_timeout)
            
            logger.debug(f"메타데이터 추출 완료: {youtube_id}")
            return metadata
            
        except Exception as e:
            logger.error(f"yt-dlp 메타데이터 추출 실패 ({youtube_id}): {e}")
            return None
    
    def _process_video_info(self, info: Dict, youtube_id: str) -> Dict:
        """yt-dlp 정보를 처리하여 메타데이터를 생성합니다."""
        metadata = {
            'youtube_id': youtube_id,
            'title': info.get('title', ''),
            'description': info.get('description', ''),
            'channel_title': info.get('uploader', '') or info.get('channel', ''),
            'channel_id': info.get('uploader_id', '') or info.get('channel_id', ''),
            'view_count': info.get('view_count', 0) or 0,
            'like_count': info.get('like_count', 0) or 0,
            'comment_count': info.get('comment_count', 0) or 0,
            'duration': info.get('duration', 0),
            'upload_date': info.get('upload_date', ''),
            'thumbnail_url': info.get('thumbnail', ''),
            'tags': info.get('tags', []) or [],
            'categories': info.get('categories', []) or [],
        }
        
        # 업로드 날짜 파싱
        if metadata['upload_date']:
            try:
                upload_date = datetime.strptime(metadata['upload_date'], '%Y%m%d')
                metadata['published_at'] = timezone.make_aware(upload_date)
            except ValueError:
                metadata['published_at'] = timezone.now()
        else:
            metadata['published_at'] = timezone.now()
        
        # 카테고리 매핑
        if metadata['categories']:
            category_name = metadata['categories'][0].lower()
            category_mapping = {
                'music': 'music',
                'gaming': 'gaming',
                'entertainment': 'entertainment',
                'sports': 'sports',
                'news': 'news',
                'education': 'education',
                'science': 'tech',
                'technology': 'tech',
                'comedy': 'comedy',
                'howto': 'lifestyle',
                'style': 'lifestyle',
                'travel': 'lifestyle',
            }
            metadata['category'] = category_mapping.get(category_name, 'other')
        else:
            metadata['category'] = 'other'
        
        # 쇼츠 여부 판단
        metadata['is_shorts'] = metadata['duration'] > 0 and metadata['duration'] <= 60
        
        # ISO 8601 duration 생성
        if metadata['duration'] > 0:
            duration_seconds = metadata['duration']
            if duration_seconds < 60:
                metadata['duration_iso'] = f"PT{duration_seconds}S"
            elif duration_seconds < 3600:
                minutes = duration_seconds // 60
                seconds = duration_seconds % 60
                metadata['duration_iso'] = f"PT{minutes}M{seconds}S"
            else:
                hours = duration_seconds // 3600
                minutes = (duration_seconds % 3600) // 60
                seconds = duration_seconds % 60
                metadata['duration_iso'] = f"PT{hours}H{minutes}M{seconds}S"
        else:
            metadata['duration_iso'] = 'PT0S'
        
        return metadata
    
    def enhance_shorts_data(self, shorts_data: List[Dict], use_parallel=True) -> List[Dict]:
        """스크래핑된 쇼츠 데이터를 yt-dlp로 보강합니다."""
        if not shorts_data:
            return []
        
        enhanced_data = []
        
        if use_parallel and len(shorts_data) > 1:
            enhanced_data = self._enhance_parallel(shorts_data)
        else:
            enhanced_data = self._enhance_sequential(shorts_data)
        
        logger.info(f"메타데이터 보강 완료: {len(enhanced_data)}개 쇼츠")
        return enhanced_data
    
    def _enhance_parallel(self, shorts_data: List[Dict]) -> List[Dict]:
        """병렬 처리로 메타데이터 보강"""
        enhanced_data = []
        youtube_ids = [shorts['youtube_id'] for shorts in shorts_data]
        
        logger.info(f"병렬 처리로 {len(youtube_ids)}개 메타데이터 추출 시작")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_data = {
                executor.submit(self._extract_single_metadata, youtube_id): (youtube_id, shorts_data[i])
                for i, youtube_id in enumerate(youtube_ids)
            }
            
            for future in as_completed(future_to_data):
                youtube_id, original_shorts_info = future_to_data[future]
                
                try:
                    metadata = future.result()
                    
                    if metadata:
                        enhanced_shorts_info = self._merge_data(original_shorts_info, metadata)
                        enhanced_data.append(enhanced_shorts_info)
                    else:
                        enhanced_data.append(original_shorts_info)
                        
                except Exception as e:
                    logger.error(f"병렬 처리 중 오류 ({youtube_id}): {e}")
                    enhanced_data.append(original_shorts_info)
        
        # 원본 순서대로 정렬
        youtube_id_to_data = {data['youtube_id']: data for data in enhanced_data}
        ordered_data = [youtube_id_to_data.get(shorts['youtube_id'], shorts) for shorts in shorts_data]
        
        return ordered_data
    
    def _enhance_sequential(self, shorts_data: List[Dict]) -> List[Dict]:
        """순차 처리로 메타데이터 보강"""
        enhanced_data = []
        
        for i, shorts_info in enumerate(shorts_data, 1):
            try:
                youtube_id = shorts_info['youtube_id']
                logger.info(f"순차 처리 중 ({i}/{len(shorts_data)}): {youtube_id}")
                
                metadata = self._extract_single_metadata(youtube_id)
                
                if metadata:
                    enhanced_shorts_info = self._merge_data(shorts_info, metadata)
                    enhanced_data.append(enhanced_shorts_info)
                else:
                    enhanced_data.append(shorts_info)
                
                time.sleep(0.3)  # API 요청 제한
                
            except Exception as e:
                logger.error(f"순차 처리 중 오류 ({shorts_info.get('youtube_id', 'Unknown')}): {e}")
                enhanced_data.append(shorts_info)
                continue
        
        return enhanced_data
    
    def _merge_data(self, original_shorts_info: Dict, metadata: Dict) -> Dict:
        """기존 스크래핑 데이터와 yt-dlp 메타데이터를 병합합니다."""
        return {
            'youtube_id': metadata['youtube_id'],
            'title': metadata['title'] or original_shorts_info['title'],
            'description': metadata['description'],
            'channel_title': metadata['channel_title'] or original_shorts_info['channel_title'],
            'channel_id': metadata['channel_id'],
            'view_count': metadata['view_count'] or original_shorts_info['view_count'],
            'like_count': metadata['like_count'],
            'comment_count': metadata['comment_count'],
            'published_at': metadata['published_at'],
            'duration': metadata['duration_iso'],
            'thumbnail_url': metadata['thumbnail_url'] or original_shorts_info['thumbnail_url'],
            'category': metadata['category'],
            'tags': metadata['tags'],
            'trending_rank': original_shorts_info['trending_rank'],
            'trending_date': original_shorts_info['trending_date'],
            'region_code': original_shorts_info['region_code'],
            'is_shorts': metadata['is_shorts'],
        }


class TrendingDataService:
    """트렌딩 데이터 통합 서비스 (간소화 버전)"""
    
    def __init__(self):
        self.scraper_service = YouTubeTrendingScraper()
    
    def collect_trending_shorts(self) -> Dict[str, any]:
        """트렌딩 쇼츠를 수집합니다."""
        results = {
            'success': False,
            'count': 0,
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'error': None
        }
        
        try:
            logger.info("트렌딩 쇼츠 수집 시작...")
            scraped_shorts = self.scraper_service.scrape_trending_shorts(
                enhance_metadata=True, 
                max_shorts=50
            )
            
            if scraped_shorts:
                created, _ = self.scraper_service.save_scraped_shorts_to_db(scraped_shorts)
                
                results = {
                    'success': True,
                    'count': created,
                    'created': created,
                    'updated': 0,  # 더 이상 업데이트하지 않음
                    'skipped': len(scraped_shorts) - created,  # 전체에서 생성된 것을 뺀 나머지
                    'error': None
                }
                
                logger.info(f"트렌딩 쇼츠 수집 완료: {results['count']}개 생성")
            else:
                results['error'] = "쇼츠 데이터를 가져올 수 없습니다"
                logger.warning(results['error'])
            
        except Exception as e:
            results['error'] = str(e)
            logger.error(f"트렌딩 쇼츠 수집 실패: {e}")
        
        return results
    
    def get_latest_shorts(self, days=1, include_music=False):
        """최신 트렌딩 쇼츠를 가져옵니다."""
        from .models import TrendingVideo
        from django.utils import timezone
        from datetime import timedelta
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days-1)
        
        queryset = TrendingVideo.objects.filter(
            is_shorts=True,
            trending_date__range=[start_date, end_date]
        ).order_by('-trending_date', 'trending_rank')
        
        if not include_music:
            queryset = queryset.exclude(category='music')
        
        return queryset
    
    def get_shorts_with_rank_changes(self, days=7, include_music=False):
        """순위 변동이 포함된 쇼츠 데이터를 가져옵니다."""
        from .models import TrendingVideo
        from django.utils import timezone
        from datetime import timedelta
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days-1)
        
        # 최신 데이터 가져오기
        latest_shorts = TrendingVideo.objects.filter(
            is_shorts=True,
            trending_date=end_date
        ).order_by('trending_rank')
        
        if not include_music:
            latest_shorts = latest_shorts.exclude(category='music')
        
        # 이전 데이터와 비교하여 순위 변동 계산
        videos_with_changes = []
        for video in latest_shorts:
            try:
                # 이전 날짜의 동일 비디오 찾기
                previous_video = TrendingVideo.objects.filter(
                    youtube_id=video.youtube_id,
                    trending_date__lt=end_date,
                    trending_date__gte=start_date
                ).order_by('-trending_date').first()
                
                if previous_video:
                    rank_change = previous_video.trending_rank - video.trending_rank
                    is_new = False
                    previous_rank = previous_video.trending_rank
                else:
                    rank_change = None
                    is_new = True
                    previous_rank = None
                
                videos_with_changes.append({
                    'video': video,
                    'rank_change': rank_change,
                    'is_new': is_new,
                    'previous_rank': previous_rank
                })
                
            except Exception as e:
                logger.error(f"순위 변동 계산 중 오류 ({video.youtube_id}): {e}")
                videos_with_changes.append({
                    'video': video,
                    'rank_change': None,
                    'is_new': False,
                    'previous_rank': None
                })
        
        return videos_with_changes
    
    def get_trending_stats_summary(self, days=7):
        """트렌딩 통계 요약을 가져옵니다."""
        from .models import TrendingVideo, TrendingStats
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Count, Avg, Sum
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days-1)
        
        # 기본 통계
        total_shorts = TrendingVideo.objects.filter(
            is_shorts=True,
            trending_date__range=[start_date, end_date]
        ).count()
        
        # 최근 수집 통계
        recent_stats = TrendingStats.objects.filter(
            collection_date__range=[start_date, end_date]
        ).aggregate(
            total_successful=Sum('successful_collections'),
            total_failed=Sum('failed_collections'),
            total_collected=Sum('total_videos_collected'),
            total_shorts=Sum('shorts_collected')
        )
        
        return {
            'total_shorts_collected': total_shorts,
            'total_videos_collected': recent_stats.get('total_collected', 0) or 0,
            'successful_collections': recent_stats.get('total_successful', 0) or 0,
            'failed_collections': recent_stats.get('total_failed', 0) or 0,
            'shorts_collected': recent_stats.get('total_shorts', 0) or 0,
            'collection_days': days,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d')
        }


class YouTubeTagExtractor:
    """YouTube 비디오 태그 추출 서비스"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def extract_tags_from_url(self, youtube_url):
        """
        YouTube URL에서 태그와 메타데이터를 추출합니다.
        
        Args:
            youtube_url (str): YouTube 비디오 URL
            
        Returns:
            dict: 추출된 태그와 메타데이터
        """
        try:
            # URL 유효성 검사
            if not self._is_valid_youtube_url(youtube_url):
                return {
                    'success': False,
                    'error': '유효하지 않은 YouTube URL입니다.'
                }
            
            # yt-dlp를 사용해서 메타데이터 추출
            metadata = self._extract_metadata_with_ytdlp(youtube_url)
            
            if not metadata:
                return {
                    'success': False,
                    'error': '비디오 정보를 가져올 수 없습니다.'
                }
            
            # 태그 정리 및 포맷팅
            formatted_tags = self._format_tags(metadata.get('tags', []))
            
            result = {
                'success': True,
                'data': {
                    'title': metadata.get('title', '제목 없음'),
                    'description': metadata.get('description', ''),
                    'tags': formatted_tags,
                    'channel': metadata.get('uploader', '채널 정보 없음'),
                    'duration': self._format_duration(metadata.get('duration', 0)),
                    'view_count': metadata.get('view_count', 0),
                    'like_count': metadata.get('like_count'),
                    'upload_date': metadata.get('upload_date', ''),
                    'thumbnail': metadata.get('thumbnail', ''),
                    'categories': metadata.get('categories', []),
                    'url': youtube_url
                }
            }
            
            self.logger.info(f"태그 추출 성공: {len(formatted_tags)}개 태그 발견")
            return result
            
        except Exception as e:
            self.logger.error(f"태그 추출 오류: {str(e)}")
            return {
                'success': False,
                'error': f'태그 추출 중 오류 발생: {str(e)}'
            }
    
    def _is_valid_youtube_url(self, url):
        """YouTube URL 유효성 검사"""
        youtube_patterns = [
            r'https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+',
            r'https?://youtu\.be/[\w-]+',
            r'https?://(?:www\.)?youtube\.com/shorts/[\w-]+',
            r'https?://m\.youtube\.com/watch\?v=[\w-]+'
        ]
        
        return any(re.match(pattern, url) for pattern in youtube_patterns)
    
    def _extract_metadata_with_ytdlp(self, url):
        """yt-dlp를 사용해서 메타데이터 추출"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'writeinfojson': False,
                'writesubtitles': False,
                'writeautomaticsub': False,
                'skip_download': True,
                'format': 'worst',  # 빠른 처리를 위해 최저화질 선택
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self.logger.info(f"yt-dlp로 메타데이터 추출 시작: {url}")
                info = ydl.extract_info(url, download=False)
                self.logger.info("yt-dlp 메타데이터 추출 완료")
                return info
                
        except Exception as e:
            self.logger.error(f"yt-dlp 메타데이터 추출 실패: {str(e)}")
            return None
    
    def _format_tags(self, raw_tags):
        """태그를 정리하고 포맷팅"""
        if not raw_tags:
            return []
        
        formatted_tags = []
        for tag in raw_tags:
            if isinstance(tag, str) and tag.strip():
                # 태그 정리: 공백 제거, 소문자 변환, 특수문자 제거
                clean_tag = tag.strip()
                if len(clean_tag) > 1 and len(clean_tag) <= 50:  # 1-50자 길이 제한
                    formatted_tags.append({
                        'text': clean_tag,
                        'length': len(clean_tag),
                        'category': self._categorize_tag(clean_tag)
                    })
        
        # 길이순으로 정렬하고 중복 제거
        seen = set()
        unique_tags = []
        for tag in sorted(formatted_tags, key=lambda x: x['length']):
            if tag['text'].lower() not in seen:
                seen.add(tag['text'].lower())
                unique_tags.append(tag)
        
        return unique_tags[:30]  # 최대 30개로 제한
    
    def _categorize_tag(self, tag):
        """태그 카테고리 분류"""
        tag_lower = tag.lower()
        
        # 한국어 키워드
        korean_keywords = ['한국', '한글', 'korea', 'korean']
        tech_keywords = ['tech', 'technology', 'programming', 'code', 'developer', 'ai', 'ml']
        music_keywords = ['music', 'song', 'mv', 'cover', 'sing', 'band', 'musician']
        gaming_keywords = ['game', 'gaming', 'play', 'gamer', 'stream', 'lol', 'fps']
        entertainment_keywords = ['funny', 'comedy', 'entertainment', 'viral', 'trend', 'meme']
        
        if any(keyword in tag_lower for keyword in korean_keywords):
            return 'korean'
        elif any(keyword in tag_lower for keyword in tech_keywords):
            return 'tech'
        elif any(keyword in tag_lower for keyword in music_keywords):
            return 'music'
        elif any(keyword in tag_lower for keyword in gaming_keywords):
            return 'gaming'
        elif any(keyword in tag_lower for keyword in entertainment_keywords):
            return 'entertainment'
        else:
            return 'general'
    
    def _format_duration(self, duration_seconds):
        """초를 시간:분:초 형식으로 변환"""
        if not duration_seconds:
            return "알 수 없음"
        
        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        seconds = duration_seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}" 