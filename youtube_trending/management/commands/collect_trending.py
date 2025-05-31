from django.core.management.base import BaseCommand
from django.utils import timezone
from youtube_trending.services import TrendingVideoCollector


class Command(BaseCommand):
    """YouTube 트렌딩 영상 수집 명령어"""
    help = 'YouTube 트렌딩 영상을 수집합니다'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--max-results',
            type=int,
            default=50,
            help='수집할 최대 비디오 수 (기본값: 50)'
        )
        parser.add_argument(
            '--region',
            type=str,
            default='KR',
            help='지역 코드 (기본값: KR)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='실제로 저장하지 않고 시뮬레이션만 실행'
        )
        parser.add_argument(
            '--test-api',
            action='store_true',
            help='API 연결 테스트만 실행'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='상세한 정보 출력'
        )
    
    def handle(self, *args, **options):
        max_results = options['max_results']
        region = options['region']
        dry_run = options['dry_run']
        test_api = options['test_api']
        verbose = options['verbose']
        
        self.stdout.write(
            self.style.HTTP_INFO(f"🚀 YouTube 트렌딩 영상 수집 시작: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")
        )
        
        if test_api or dry_run:
            self._test_api_connection(region, verbose)
            return
        
        try:
            collector = TrendingVideoCollector()
            start_time = timezone.now()
            
            self.stdout.write("📥 트렌딩 영상 수집 중...")
            
            result = collector.collect_and_save_trending_videos(
                max_results=max_results,
                region_code=region
            )
            
            end_time = timezone.now()
            duration = (end_time - start_time).total_seconds()
            
            if result['success']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ 수집 완료! (소요시간: {duration:.2f}초)\n"
                        f"   📊 수집된 총 영상: {result['collected_count']}개\n"
                        f"   🩳 쇼츠 영상: {result['shorts_count']}개\n"
                        f"   ❌ 실패: {result.get('failed_count', 0)}개"
                    )
                )
                
                if verbose and result['collected_count'] > 0:
                    self._show_collection_details(collector)
                    
            else:
                self.stdout.write(
                    self.style.ERROR(f"❌ 수집 실패: {result['message']}")
                )
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"💥 오류 발생: {e}")
            )
            if verbose:
                import traceback
                traceback.print_exc()
    
    def _test_api_connection(self, region, verbose):
        """API 연결 테스트"""
        self.stdout.write("🔍 API 연결 테스트 중...")
        
        try:
            collector = TrendingVideoCollector()
            start_time = timezone.now()
            
            # YouTube API 서비스 초기화 테스트
            youtube_service = collector.youtube_service
            test_videos = youtube_service.get_trending_videos(max_results=5, region_code=region)
            
            end_time = timezone.now()
            duration = (end_time - start_time).total_seconds()
            
            if test_videos:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ API 연결 성공! {len(test_videos)}개 영상 조회 완료 (소요시간: {duration:.2f}초)"
                    )
                )
                
                # 샘플 영상 정보 출력
                self.stdout.write("\n📋 샘플 영상 정보:")
                self.stdout.write("=" * 80)
                
                for i, video in enumerate(test_videos[:3], 1):
                    parsed_data = youtube_service.parse_video_data(video, i)
                    
                    title = parsed_data.get('title', '제목 없음')[:50]
                    channel = parsed_data.get('channel_title', '채널 없음')
                    duration = parsed_data.get('formatted_duration', '시간 정보 없음')
                    is_shorts = parsed_data.get('is_shorts', False)
                    view_count = parsed_data.get('view_count', 0)
                    category = parsed_data.get('category', 'other')
                    
                    self.stdout.write(
                        f"  {i}. 🎬 {title}{'...' if len(title) >= 50 else ''}\n"
                        f"     📺 채널: {channel}\n"
                        f"     ⏱️  길이: {duration} | 👀 조회수: {view_count:,}회\n"
                        f"     🏷️  카테고리: {category} | 🩳 쇼츠: {'Yes' if is_shorts else 'No'}"
                    )
                    if i < len(test_videos[:3]):
                        self.stdout.write("-" * 80)
                
            else:
                self.stdout.write(
                    self.style.ERROR("❌ API 연결 실패 또는 데이터 없음")
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"💥 API 테스트 중 오류: {e}")
            )
    
    def _show_collection_details(self, collector):
        """수집된 데이터의 상세 정보 표시"""
        self.stdout.write("\n📈 수집 통계:")
        self.stdout.write("=" * 50)
        
        try:
            # 오늘 수집된 최신 쇼츠 조회
            latest_shorts = collector.get_latest_shorts(days=1)[:5]
            
            if latest_shorts:
                self.stdout.write("🔥 오늘의 TOP 5 쇼츠:")
                for i, video in enumerate(latest_shorts, 1):
                    self.stdout.write(
                        f"  {i}. {video.title[:40]}{'...' if len(video.title) > 40 else ''}\n"
                        f"     👀 {video.formatted_view_count} | ⏱️ {video.formatted_duration}"
                    )
            
            # 통계 정보
            stats = collector.get_trending_stats_summary(days=1)
            self.stdout.write(f"\n📊 오늘의 통계:")
            self.stdout.write(f"   🩳 총 쇼츠: {stats['total_shorts_collected']}개")
            self.stdout.write(f"   📥 수집 횟수: {stats['successful_collections']}회")
            self.stdout.write(f"   📅 마지막 수집: {stats['latest_collection'] or 'N/A'}")
            
        except Exception as e:
            self.stdout.write(f"⚠️  상세 정보 조회 실패: {e}") 