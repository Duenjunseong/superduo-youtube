from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from youtube_trending.models import TrendingVideo, TrendingStats


class Command(BaseCommand):
    """30일 이상 된 트렌딩 비디오 정리 명령어"""
    help = '30일 이상 된 트렌딩 비디오를 삭제합니다'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='삭제할 기준 일수 (기본값: 30일)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='실제로 삭제하지 않고 시뮬레이션만 실행'
        )
        parser.add_argument(
            '--keep-stats',
            action='store_true',
            help='통계 데이터는 유지 (기본: 함께 삭제)',
            default=True
        )
    
    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        keep_stats = options['keep_stats']
        
        cutoff_date = date.today() - timedelta(days=days)
        
        self.stdout.write(
            self.style.HTTP_INFO(f"🧹 트렌딩 비디오 정리 시작: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")
        )
        self.stdout.write(f"📅 기준 날짜: {cutoff_date} (이전 데이터 삭제)")
        
        # 삭제 대상 조회
        old_videos = TrendingVideo.objects.filter(trending_date__lt=cutoff_date)
        old_stats = TrendingStats.objects.filter(collection_date__lt=cutoff_date)
        
        videos_count = old_videos.count()
        stats_count = old_stats.count()
        
        self.stdout.write(f"📊 삭제 대상:")
        self.stdout.write(f"   📹 비디오: {videos_count:,}개")
        if not keep_stats:
            self.stdout.write(f"   📈 통계: {stats_count:,}개")
        else:
            self.stdout.write(f"   📈 통계: 유지 (삭제하지 않음)")
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING("🔍 드라이 런 모드: 실제로 삭제하지 않습니다")
            )
            
            # 삭제될 데이터 샘플 보여주기
            if videos_count > 0:
                self.stdout.write("\n📋 삭제될 비디오 샘플 (최신 5개):")
                sample_videos = old_videos.order_by('-trending_date')[:5]
                for video in sample_videos:
                    self.stdout.write(
                        f"   • {video.trending_date} - {video.title[:50]}... "
                        f"(순위: {video.trending_rank}, 쇼츠: {'Yes' if video.is_shorts else 'No'})"
                    )
            
            # 날짜별 데이터 분포 보여주기
            date_distribution = old_videos.values('trending_date').distinct().order_by('trending_date')
            if date_distribution:
                self.stdout.write(f"\n📊 날짜별 분포:")
                for item in date_distribution[:10]:  # 최대 10개만 표시
                    date_count = old_videos.filter(trending_date=item['trending_date']).count()
                    self.stdout.write(f"   • {item['trending_date']}: {date_count}개")
                
                if len(date_distribution) > 10:
                    self.stdout.write(f"   ... 외 {len(date_distribution) - 10}개 날짜")
            
            return
        
        # 실제 삭제 실행
        self.stdout.write("🗑️ 데이터 삭제 중...")
        
        deleted_videos = 0
        deleted_stats = 0
        
        try:
            # 비디오 삭제
            if videos_count > 0:
                deleted_count, _ = old_videos.delete()
                deleted_videos = deleted_count
                self.stdout.write(f"   ✅ 비디오 {deleted_videos:,}개 삭제 완료")
            
            # 통계 삭제 (옵션에 따라)
            if not keep_stats and stats_count > 0:
                deleted_count, _ = old_stats.delete()
                deleted_stats = deleted_count
                self.stdout.write(f"   ✅ 통계 {deleted_stats:,}개 삭제 완료")
            
            # 결과 요약
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n🎉 정리 완료!\n"
                    f"   🗑️ 삭제된 비디오: {deleted_videos:,}개\n"
                    f"   🗑️ 삭제된 통계: {deleted_stats:,}개\n"
                    f"   💾 DB 용량 절약 완료"
                )
            )
            
            # 남은 데이터 정보
            remaining_videos = TrendingVideo.objects.count()
            remaining_stats = TrendingStats.objects.count()
            
            self.stdout.write(f"\n📊 남은 데이터:")
            self.stdout.write(f"   📹 비디오: {remaining_videos:,}개")
            self.stdout.write(f"   📈 통계: {remaining_stats:,}개")
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ 삭제 중 오류 발생: {e}")
            )
            raise
        
        self.stdout.write(
            self.style.WARNING(
                f"\n💡 팁: 이 명령어를 cron에 등록하여 자동화할 수 있습니다:\n"
                f"   0 2 * * * python manage.py cleanup_old_videos"
            )
        ) 