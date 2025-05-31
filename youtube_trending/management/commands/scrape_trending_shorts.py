"""
YouTube 트렌딩 페이지에서 쇼츠 정보를 스크래핑하는 관리 명령어
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from youtube_trending.services import YouTubeTrendingScraper, TrendingDataService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Selenium을 사용하여 YouTube 트렌딩 페이지에서 쇼츠 정보를 스크래핑합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--scrape-only',
            action='store_true',
            help='스크래핑만 수행 (API 수집 제외)',
        )
        parser.add_argument(
            '--api-only',
            action='store_true',
            help='API 수집만 수행 (스크래핑 제외)',
        )
        parser.add_argument(
            '--test-mode',
            action='store_true',
            help='테스트 모드 (실제 저장하지 않음)',
        )
        parser.add_argument(
            '--save-html',
            action='store_true',
            help='렌더링된 HTML을 파일로 저장 (디버깅용)',
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            help='디버그 모드 (상세한 로그 출력)',
        )
        parser.add_argument(
            '--no-enhancement',
            action='store_true',
            help='yt-dlp 메타데이터 보강 비활성화',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='수집할 최대 쇼츠 수 (기본값: 50)',
        )
        parser.add_argument(
            '--retries',
            type=int,
            default=3,
            help='재시도 횟수 (기본값: 3)',
        )
        parser.add_argument(
            '--workers',
            type=int,
            default=6,
            help='병렬 처리 워커 수 (기본값: 6)',
        )
        parser.add_argument(
            '--no-parallel',
            action='store_true',
            help='병렬 처리 비활성화 (순차 처리)',
        )

    def handle(self, *args, **options):
        start_time = timezone.now()
        
        # 옵션 저장
        self.options = options
        
        # 디버그 모드 설정
        if options['debug']:
            logging.getLogger('youtube_trending.services').setLevel(logging.DEBUG)
        
        self.stdout.write(
            self.style.HTTP_INFO('=' * 60)
        )
        self.stdout.write(
            self.style.HTTP_INFO('🤖 Selenium YouTube 트렌딩 쇼츠 스크래핑 시작')
        )
        self.stdout.write(
            self.style.HTTP_INFO(f'시작 시간: {start_time.strftime("%Y-%m-%d %H:%M:%S")}')
        )
        if options['test_mode']:
            self.stdout.write(
                self.style.WARNING('🧪 테스트 모드 활성화 - 데이터베이스에 저장하지 않습니다')
            )
        if options['save_html']:
            self.stdout.write(
                self.style.HTTP_INFO('💾 HTML 저장 모드 활성화')
            )
        self.stdout.write(
            self.style.HTTP_INFO('=' * 60)
        )

        try:
            if options['scrape_only']:
                # Selenium 스크래핑만 수행
                result = self.run_selenium_scraping_only(options['test_mode'], options['save_html'])
            elif options['api_only']:
                # API만 수행 (기존 기능)
                result = self.run_api_only()
            else:
                # 통합 수집 (API + Selenium 스크래핑)
                result = self.run_integrated_collection(options['test_mode'])
            
            self.display_results(result, start_time)
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ 스크래핑 중 오류 발생: {str(e)}')
            )
            logger.error(f'스크래핑 명령어 실행 실패: {e}', exc_info=True)
            raise CommandError(f'스크래핑 실패: {str(e)}')

    def run_selenium_scraping_only(self, test_mode=False, save_html=False):
        """향상된 Selenium을 사용한 스크래핑만 수행"""
        enhance_metadata = not self.options.get('no_enhancement', False)
        limit = self.options.get('limit', 50)
        retries = self.options.get('retries', 3)
        workers = self.options.get('workers', 6)
        use_parallel = not self.options.get('no_parallel', False)
        
        # 설정 정보 출력
        settings_info = []
        settings_info.append(f"메타데이터 보강: {'✅ 활성화' if enhance_metadata else '❌ 비활성화'}")
        settings_info.append(f"최대 쇼츠 수: {limit}개")
        settings_info.append(f"재시도 횟수: {retries}회")
        if enhance_metadata:
            settings_info.append(f"병렬 처리: {'✅ 활성화' if use_parallel else '❌ 비활성화'}")
            if use_parallel:
                settings_info.append(f"워커 수: {workers}개")
        
        self.stdout.write(f'🤖 향상된 Selenium 쇼츠 스크래핑 시작...')
        self.stdout.write(f'⚙️  설정: {" | ".join(settings_info)}')
        self.stdout.write(f'📊 현재 페이지에서 쇼츠 수집 (조회수 기준 정렬, 최대 {limit}개)')
        
        # 향상된 스크래퍼 생성
        scraper = YouTubeTrendingScraper(
            use_metadata_enhancement=enhance_metadata,
            max_retries=retries
        )
        
        # 메타데이터 추출기 설정 조정
        if enhance_metadata:
            scraper.metadata_extractor.max_workers = workers
        
        # 1. Chrome WebDriver 준비 상태 확인
        self.stdout.write('🔧 Chrome WebDriver 설정 확인 중...')
        
        # 2. YouTube 트렌딩 페이지 접근 및 쇼츠 수집
        self.stdout.write('🌐 현재 페이지에서 쇼츠 수집 시작...')
        try:
            shorts_data = scraper.scrape_trending_shorts(
                enhance_metadata=enhance_metadata, 
                max_shorts=limit
            )
            self.stdout.write(f'✅ 수집 완료: {len(shorts_data)}개 쇼츠 (조회수 기준 정렬됨)')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ 수집 실패: {e}'))
            raise
        
        # 3. 데이터 검증
        self.stdout.write('🔍 데이터 품질 검증 중...')
        validated_data = scraper._validate_shorts_data(shorts_data)
        if len(validated_data) != len(shorts_data):
            self.stdout.write(f'🔄 검증 완료: {len(shorts_data)}개 → {len(validated_data)}개')
        
        # 4. 결과 미리보기
        if validated_data:
            self.stdout.write('\n📊 수집된 쇼츠 미리보기:')
            for i, shorts in enumerate(validated_data[:3], 1):
                title = shorts.get('title', '')[:50]
                view_count = shorts.get('view_count', 0)
                channel = shorts.get('channel_title', '')[:20]
                enhancement_status = "🔥 향상됨" if enhance_metadata and shorts.get('like_count', 0) > 0 else "📋 기본"
                
                self.stdout.write(f'  {i}. {title}... | 조회수: {view_count:,} | 채널: {channel} | {enhancement_status}')
            
            if len(validated_data) > 3:
                self.stdout.write(f'  ... 외 {len(validated_data) - 3}개 더')
        
        # 5. 데이터베이스 저장 (테스트 모드가 아닌 경우)
        if not test_mode and validated_data:
            self.stdout.write('\n💾 데이터베이스 저장 중...')
            try:
                created, updated = scraper.save_scraped_shorts_to_db(validated_data)
                self.stdout.write(f'✅ 저장 완료: 새로 생성 {created}개, 업데이트 {updated}개')
                
                return {
                    'total_scraped': len(validated_data),
                    'created': created,
                    'updated': updated,
                    'total_saved': created + updated,
                    'enhancement_used': enhance_metadata,
                    'parallel_used': use_parallel and enhance_metadata,
                }
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ 데이터베이스 저장 실패: {e}'))
                raise
        
        elif test_mode:
            self.stdout.write('\n🧪 테스트 모드: 데이터베이스에 저장하지 않음')
            return {
                'total_scraped': len(validated_data),
                'created': 0,
                'updated': 0,
                'total_saved': 0,
                'enhancement_used': enhance_metadata,
                'parallel_used': use_parallel and enhance_metadata,
                'test_mode': True,
            }
        
        else:
            self.stdout.write('ℹ️  수집된 데이터가 없어 저장하지 않음')
            return {
                'total_scraped': 0,
                'created': 0,
                'updated': 0,
                'total_saved': 0,
                'enhancement_used': enhance_metadata,
                'parallel_used': use_parallel and enhance_metadata,
            }

    def run_api_only(self):
        """API만 수행"""
        self.stdout.write('🔑 YouTube API를 통한 트렌딩 동영상 수집 시작...')
        
        # 기존 API 서비스 사용
        from youtube_trending.services import YouTubeAPIService
        api_service = YouTubeAPIService()
        
        try:
            videos = api_service.get_trending_videos()
            self.stdout.write(
                self.style.SUCCESS(f'✅ API에서 {len(videos)}개 동영상 수집 완료')
            )
            
            # 여기서 실제 저장 로직을 구현해야 함 (기존 collect_trending.py 참고)
            return {
                'api_collection': {
                    'success': True,
                    'count': len(videos),
                    'error': None
                },
                'total_collected': len(videos)
            }
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ API 수집 실패: {str(e)}')
            )
            raise

    def run_integrated_collection(self, test_mode=False):
        """통합 수집 (API + Selenium 스크래핑)"""
        self.stdout.write('🚀 통합 트렌딩 데이터 수집 시작 (API + Selenium)...')
        
        if test_mode:
            # 테스트 모드에서는 Selenium 스크래핑만 수행
            return self.run_selenium_scraping_only(test_mode=True)
        
        integrated_service = TrendingDataService()
        
        try:
            results = integrated_service.collect_all_trending_data()
            return results
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ 통합 수집 실패: {str(e)}')
            )
            raise

    def display_results(self, results, start_time):
        """결과 표시"""
        end_time = timezone.now()
        duration = end_time - start_time
        
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(
            self.style.SUCCESS('🎉 스크래핑 완료!')
        )
        self.stdout.write(f'⏱️  소요 시간: {duration.total_seconds():.1f}초')
        
        # API 결과
        if 'api_collection' in results:
            api_result = results['api_collection']
            if api_result['success']:
                self.stdout.write(
                    self.style.SUCCESS(f'📊 API 수집: {api_result["count"]}개')
                )
                if 'created' in api_result and 'updated' in api_result:
                    self.stdout.write(f'   - 새로 생성: {api_result["created"]}개')
                    self.stdout.write(f'   - 업데이트: {api_result["updated"]}개')
            else:
                self.stdout.write(
                    self.style.ERROR(f'❌ API 수집 실패: {api_result.get("error", "Unknown error")}')
                )
        
        # 스크래핑 결과
        if 'scraping_collection' in results:
            scraping_result = results['scraping_collection']
            method = scraping_result.get('method', 'unknown')
            method_icon = '🤖' if method == 'selenium' else '📱'
            
            if scraping_result['success']:
                self.stdout.write(
                    self.style.SUCCESS(f'{method_icon} 스크래핑 ({method}): {scraping_result["count"]}개')
                )
                if 'created' in scraping_result and 'updated' in scraping_result:
                    self.stdout.write(f'   - 새로 생성: {scraping_result["created"]}개')
                    self.stdout.write(f'   - 업데이트: {scraping_result["updated"]}개')
            else:
                self.stdout.write(
                    self.style.ERROR(f'❌ 스크래핑 실패: {scraping_result.get("error", "Unknown error")}')
                )
        
        # 전체 결과
        total = results.get('total_collected', 0)
        if total > 0:
            self.stdout.write(
                self.style.HTTP_INFO(f'📈 총 수집된 항목: {total}개')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'⚠️  수집된 항목이 없습니다.')
            )
        
        self.stdout.write('=' * 60) 