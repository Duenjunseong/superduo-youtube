from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
import random
from youtube_trending.models import TrendingVideo, TrendingStats


class Command(BaseCommand):
    """인기쇼츠 UI 테스트용 더미 데이터 생성 명령어"""
    help = '인기쇼츠 UI 테스트를 위한 더미 데이터를 생성합니다'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=30,
            help='생성할 더미 쇼츠 수 (기본값: 30)'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='생성할 날짜 범위 (기본값: 7일)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='기존 더미 데이터 삭제 후 새로 생성'
        )
    
    def handle(self, *args, **options):
        count = options['count']
        days = options['days']
        clear_existing = options['clear']
        
        self.stdout.write(
            self.style.HTTP_INFO(f"🎬 더미 쇼츠 데이터 생성 시작: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")
        )
        
        if clear_existing:
            self.stdout.write("🧹 기존 더미 데이터 삭제 중...")
            deleted_count = TrendingVideo.objects.filter(youtube_id__startswith='DUMMY_').delete()[0]
            self.stdout.write(f"   ✅ {deleted_count}개 더미 데이터 삭제 완료")
        
        # 더미 데이터 템플릿
        dummy_shorts = [
            {
                'title': '🔥 이것만 알면 당신도 요리 고수! #요리팁 #쇼츠',
                'channel': '맛있는 요리교실',
                'category': 'entertainment',
                'duration_range': (15, 45)
            },
            {
                'title': '💃 1분만에 배우는 댄스 챌린지 #댄스 #챌린지',
                'channel': '댄스스튜디오',
                'category': 'entertainment', 
                'duration_range': (30, 60)
            },
            {
                'title': '😂 웃음터지는 고양이 리액션 모음 #고양이 #웃긴영상',
                'channel': '펫TV',
                'category': 'entertainment',
                'duration_range': (20, 50)
            },
            {
                'title': '⚡ 10초만에 스마트폰 배터리 절약하는 법!',
                'channel': '테크리뷰어',
                'category': 'tech',
                'duration_range': (25, 55)
            },
            {
                'title': '🎵 [MV] 신곡 미리듣기 - 아티스트X',
                'channel': '뮤직레이블',
                'category': 'music',
                'duration_range': (30, 60)
            },
            {
                'title': '🏃‍♂️ 집에서 하는 5분 운동루틴 #홈트 #운동',
                'channel': '헬스트레이너',
                'category': 'sports',
                'duration_range': (35, 60)
            },
            {
                'title': '🎮 게임 꿀팁! 이거 모르면 손해 #게임팁',
                'channel': '게임매니아',
                'category': 'gaming',
                'duration_range': (20, 45)
            },
            {
                'title': '📚 영어 단어 1분 암기법 #영어공부 #교육',
                'channel': '영어선생님',
                'category': 'education',
                'duration_range': (40, 60)
            },
            {
                'title': '🍰 30초 디저트 만들기 #디저트 #간단요리',
                'channel': '베이킹마스터',
                'category': 'entertainment',
                'duration_range': (25, 40)
            },
            {
                'title': '💄 5분 메이크업 완성하기 #메이크업 #뷰티',
                'channel': '뷰티구루',
                'category': 'lifestyle',
                'duration_range': (45, 60)
            },
            {
                'title': '🌱 식물 키우기 초보자 가이드 #식물 #가드닝',
                'channel': '가드닝라이프',
                'category': 'lifestyle',
                'duration_range': (30, 50)
            },
            {
                'title': '🎨 1분 드로잉 챌린지 #그림 #아트',
                'channel': '아트스튜디오',
                'category': 'entertainment',
                'duration_range': (35, 60)
            },
            {
                'title': '🚗 자동차 관리 꿀팁 공개! #자동차 #꿀팁',
                'channel': '카센터',
                'category': 'other',
                'duration_range': (40, 60)
            },
            {
                'title': '📱 숨겨진 스마트폰 기능 TOP 5',
                'channel': '스마트리뷰',
                'category': 'tech',
                'duration_range': (50, 60)
            },
            {
                'title': '🎪 마술 트릭 배우기 #마술 #신기한',
                'channel': '마술사',
                'category': 'entertainment',
                'duration_range': (20, 45)
            }
        ]
        
        created_count = 0
        
        for day_offset in range(days):
            target_date = date.today() - timedelta(days=day_offset)
            daily_count = count // days + (1 if day_offset < count % days else 0)
            
            self.stdout.write(f"📅 {target_date} 데이터 생성 중... ({daily_count}개)")
            
            for rank in range(1, daily_count + 1):
                # 랜덤 템플릿 선택
                template = random.choice(dummy_shorts)
                
                # 조회수 생성 (상위 순위일수록 더 높은 조회수)
                base_views = random.randint(50000, 200000)
                rank_multiplier = max(1, (daily_count - rank + 1) / daily_count * 3)
                view_count = int(base_views * rank_multiplier)
                
                # 좋아요/댓글 수 생성
                like_count = int(view_count * random.uniform(0.02, 0.08))
                comment_count = int(view_count * random.uniform(0.005, 0.02))
                
                # 영상 길이 생성
                duration_seconds = random.randint(*template['duration_range'])
                duration_iso = f"PT{duration_seconds}S"
                
                # 발행 시간 생성 (최근 1-30일 내)
                published_days_ago = random.randint(1, 30)
                published_at = timezone.now() - timedelta(days=published_days_ago)
                
                # 더미 유튜브 ID 생성
                youtube_id = f"DUMMY_{target_date.strftime('%Y%m%d')}_{rank:03d}"
                
                # 더미 썸네일 URL (picsum 사용)
                thumbnail_url = f"https://picsum.photos/480/360?random={youtube_id}"
                
                # 제목에 변화 추가
                title_variations = [
                    template['title'],
                    f"{template['title']} 🔥HOT",
                    f"✨ {template['title']}",
                    f"{template['title']} 【화제】",
                    f"🌟 {template['title']} 🌟"
                ]
                title = random.choice(title_variations)
                
                # 더미 비디오 생성
                trending_video = TrendingVideo.objects.create(
                    youtube_id=youtube_id,
                    title=title,
                    channel_title=template['channel'],
                    channel_id=f"UC{youtube_id}",
                    view_count=view_count,
                    like_count=like_count,
                    comment_count=comment_count,
                    published_at=published_at,
                    duration=duration_iso,
                    thumbnail_url=thumbnail_url,
                    category=template['category'],
                    trending_rank=rank,
                    trending_date=target_date,
                    is_shorts=True  # 모두 쇼츠로 설정
                )
                
                created_count += 1
                
                if rank <= 3:  # TOP 3만 출력
                    self.stdout.write(
                        f"   {rank}. {title[:40]}{'...' if len(title) > 40 else ''} "
                        f"(👀 {view_count:,}회)"
                    )
        
        # 통계 업데이트
        for day_offset in range(days):
            target_date = date.today() - timedelta(days=day_offset)
            daily_shorts = TrendingVideo.objects.filter(
                trending_date=target_date,
                is_shorts=True
            ).count()
            
            stats, created = TrendingStats.objects.get_or_create(
                collection_date=target_date,
                defaults={
                    'total_videos_collected': daily_shorts,
                    'successful_collections': 1,
                    'failed_collections': 0,
                    'shorts_collected': daily_shorts
                }
            )
            
            if not created:
                stats.shorts_collected = daily_shorts
                stats.save()
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ 더미 데이터 생성 완료!\n"
                f"   📊 생성된 쇼츠: {created_count}개\n"
                f"   📅 기간: {days}일\n"
                f"   🎯 이제 웹사이트에서 인기쇼츠를 확인해보세요!"
            )
        )
        
        self.stdout.write(
            self.style.WARNING(
                f"\n💡 팁: 더미 데이터 삭제는 다음 명령어로 가능합니다:\n"
                f"   python manage.py create_dummy_shorts --clear --count 0"
            )
        ) 