from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import date, timedelta
import logging
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

from .models import TrendingVideo, TrendingStats, FavoriteShorts
from .services import TrendingDataService, YouTubeTrendingScraper, YouTubeTagExtractor

logger = logging.getLogger(__name__)


class TrendingShortsAPIView(LoginRequiredMixin, View):
    """인기 쇼츠 API 뷰 (AJAX용)"""
    
    def get(self, request):
        try:
            # 쿼리 파라미터
            limit = int(request.GET.get('limit', 20))
            limit = min(limit, 50)  # 최대 50개 제한
            
            page = int(request.GET.get('page', 1))
            category = request.GET.get('category', '')
            
            # date 파라미터 우선, 없으면 days 파라미터 사용
            date_param = request.GET.get('date')
            if date_param:
                try:
                    from datetime import datetime
                    target_date = datetime.strptime(date_param, '%Y-%m-%d').date()
                    days = 1  # 특정 날짜는 하루만
                except ValueError:
                    target_date = date.today()
                    days = 1
            else:
                days = int(request.GET.get('days', 1))  # 기본값을 1로 변경 (오늘)
                target_date = date.today()
            
            include_music = request.GET.get('include_music', 'false').lower() == 'true'
            
            collector = TrendingDataService()
            
            if date_param or days == 1:
                # 특정 날짜 또는 오늘만 보는 경우
                queryset = collector.get_latest_shorts(days=1, include_music=include_music)
                
                # 카테고리 필터링
                if category and category != 'all':
                    queryset = queryset.filter(category=category)
                
                # 날짜 필터링 (특정 날짜 또는 오늘)
                queryset = queryset.filter(trending_date=target_date)
                
                # 페이지네이션
                paginator = Paginator(queryset, limit)
                page_obj = paginator.get_page(page)
                
                # 즐겨찾기 상태를 효율적으로 조회 (N+1 문제 해결)
                user = request.user
                workspace = user.current_workspace if user.is_in_workspace_mode() else None
                video_ids = [video.youtube_id for video in page_obj]
                
                # 현재 페이지 비디오들의 즐겨찾기 상태를 한 번에 조회
                favorite_videos = {}
                if video_ids:
                    # 해당 영상들에 대한 TrendingVideo 객체들을 찾기
                    trending_videos = TrendingVideo.objects.filter(
                        youtube_id__in=video_ids,
                        is_shorts=True
                    ).order_by('-trending_date')
                    
                    # 각 youtube_id에 대해 가장 최근 TrendingVideo 매핑
                    trending_video_map = {}
                    for tv in trending_videos:
                        if tv.youtube_id not in trending_video_map:
                            trending_video_map[tv.youtube_id] = tv
                    
                    # 즐겨찾기 조회
                    from .models import FavoriteShorts
                    favorites = FavoriteShorts.objects.filter(
                        user=user,
                        workspace=workspace,
                        trending_video__youtube_id__in=video_ids
                    ).select_related('trending_video')
                    
                    favorite_videos = {fav.trending_video.youtube_id: str(fav.favorite_id) for fav in favorites}
                
                # 데이터 직렬화
                shorts_data = []
                for video in page_obj:
                    shorts_data.append({
                        'youtube_id': video.youtube_id,
                        'title': video.title,
                        'channel_title': video.channel_title,
                        'thumbnail_url': video.thumbnail_url,
                        'youtube_url': video.youtube_url,
                        'view_count': video.view_count,
                        'formatted_view_count': video.formatted_view_count,
                        'like_count': video.like_count,
                        'comment_count': video.comment_count,
                        'duration': video.formatted_duration,
                        'trending_rank': video.trending_rank,
                        'trending_date': video.trending_date.strftime('%Y-%m-%d'),
                        'category': video.get_category_display(),
                        'published_at': video.published_at.strftime('%Y-%m-%d %H:%M') if video.published_at else '',
                        'is_new': False,  # 오늘만 보는 경우는 NEW 표시 안함
                        'rank_change': None,  # 오늘만 보는 경우는 순위 변동 안함
                        'is_favorite': video.youtube_id in favorite_videos,  # 즐겨찾기 상태 추가
                        'favorite_id': favorite_videos.get(video.youtube_id),  # 즐겨찾기 ID 추가
                    })
                
                # 가짜 페이지네이션 객체 생성
                pagination_info = {
                    'current_page': page,
                    'total_pages': paginator.num_pages,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous(),
                    'total_count': paginator.count,
                }
            
            else:
                # 여러 날 보는 경우 (순위 변동 포함)
                videos_with_changes = collector.get_shorts_with_rank_changes(days=days, include_music=include_music)
                
                # 카테고리 필터링
                if category and category != 'all':
                    videos_with_changes = [
                        item for item in videos_with_changes 
                        if item['video'].category == category
                    ]
                
                # 페이지네이션을 위한 처리
                start_index = (page - 1) * limit
                end_index = start_index + limit
                page_items = videos_with_changes[start_index:end_index]
                
                # 즐겨찾기 상태를 효율적으로 조회 (N+1 문제 해결)
                user = request.user
                workspace = user.current_workspace if user.is_in_workspace_mode() else None
                video_ids = [item['video'].youtube_id for item in page_items]
                
                # 현재 페이지 비디오들의 즐겨찾기 상태를 한 번에 조회
                favorite_videos = {}
                if video_ids:
                    from .models import FavoriteShorts
                    favorites = FavoriteShorts.objects.filter(
                        user=user,
                        workspace=workspace,
                        trending_video__youtube_id__in=video_ids
                    ).select_related('trending_video')
                    
                    favorite_videos = {fav.trending_video.youtube_id: str(fav.favorite_id) for fav in favorites}
                
                # 페이지네이션 정보 생성
                total_count = len(videos_with_changes)
                total_pages = (total_count + limit - 1) // limit
                has_next = page < total_pages
                has_previous = page > 1
                
                # 데이터 직렬화
                shorts_data = []
                for item in page_items:
                    video = item['video']
                    shorts_data.append({
                        'youtube_id': video.youtube_id,
                        'title': video.title,
                        'channel_title': video.channel_title,
                        'thumbnail_url': video.thumbnail_url,
                        'youtube_url': video.youtube_url,
                        'view_count': video.view_count,
                        'formatted_view_count': video.formatted_view_count,
                        'like_count': video.like_count,
                        'comment_count': video.comment_count,
                        'duration': video.formatted_duration,
                        'trending_rank': video.trending_rank,
                        'trending_date': video.trending_date.strftime('%Y-%m-%d'),
                        'category': video.get_category_display(),
                        'published_at': video.published_at.strftime('%Y-%m-%d %H:%M') if video.published_at else '',
                        'is_new': item['is_new'],
                        'rank_change': item['rank_change'],
                        'previous_rank': item['previous_rank'],
                        'is_favorite': video.youtube_id in favorite_videos,  # 즐겨찾기 상태 추가
                        'favorite_id': favorite_videos.get(video.youtube_id),  # 즐겨찾기 ID 추가
                    })
                
                # 가짜 페이지네이션 객체 생성
                pagination_info = {
                    'current_page': page,
                    'total_pages': total_pages,
                    'has_next': has_next,
                    'has_previous': has_previous,
                    'total_count': total_count,
                }
            
            if days == 1:
                pagination_info = {
                    'current_page': page_obj.number,
                    'total_pages': paginator.num_pages,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous(),
                    'total_count': paginator.count,
                }
            
            return JsonResponse({
                'success': True,
                'shorts': shorts_data,
                'pagination': pagination_info
            })
            
        except Exception as e:
            logger.error(f"트렌딩 쇼츠 API 오류: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class TrendingStatsAPIView(LoginRequiredMixin, View):
    """트렌딩 수집 통계 API 뷰"""
    
    def get(self, request):
        try:
            # date 파라미터 우선, 없으면 days 파라미터 사용
            date_param = request.GET.get('date')
            if date_param:
                try:
                    from datetime import datetime
                    target_date = datetime.strptime(date_param, '%Y-%m-%d').date()
                    days = 1
                except ValueError:
                    target_date = date.today()
                    days = 1
            else:
                days = int(request.GET.get('days', 7))
                target_date = date.today()
            
            collector = TrendingDataService()
            
            if date_param:
                # 특정 날짜의 통계
                stats = collector.get_trending_stats_summary(days=1)
                # 특정 날짜의 쇼츠 수 조회
                shorts_count = TrendingVideo.objects.filter(
                    is_shorts=True,
                    trending_date=target_date
                ).count()
                stats['total_shorts_collected'] = shorts_count
            else:
                # 기존 days 기반 통계
                stats = collector.get_trending_stats_summary(days=days)
            
            return JsonResponse({
                'success': True,
                'stats': stats
            })
            
        except Exception as e:
            logger.error(f"트렌딩 통계 API 오류: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@method_decorator(staff_member_required, name='dispatch')
class AdminCollectTrendingView(View):
    """관리자용 수동 트렌딩 수집 뷰"""
    
    def post(self, request):
        try:
            from .tasks import manual_collect_trending_videos
            
            # Celery 태스크 실행
            task = manual_collect_trending_videos.delay()
            
            return JsonResponse({
                'success': True,
                'message': '트렌딩 비디오 수집이 시작되었습니다.',
                'task_id': task.id
            })
            
        except Exception as e:
            logger.error(f"수동 트렌딩 수집 오류: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@method_decorator(staff_member_required, name='dispatch')
class AdminTrendingStatsView(View):
    """관리자용 트렌딩 통계 뷰"""
    
    def get(self, request):
        # 최근 30일간의 수집 통계
        recent_stats = TrendingStats.objects.filter(
            collection_date__gte=date.today() - timedelta(days=30)
        ).order_by('-collection_date')
        
        # 최근 수집된 쇼츠들
        recent_shorts = TrendingVideo.objects.filter(
            is_shorts=True,
            trending_date__gte=date.today() - timedelta(days=7)
        ).order_by('-trending_date', 'trending_rank')[:20]
        
        context = {
            'recent_stats': recent_stats,
            'recent_shorts': recent_shorts,
            'total_shorts': TrendingVideo.objects.filter(is_shorts=True).count(),
            'total_videos': TrendingVideo.objects.count(),
        }
        
        return render(request, 'youtube_trending/admin_stats.html', context)


class TrendingCategoriesAPIView(LoginRequiredMixin, View):
    """사용 가능한 카테고리 목록 API"""
    
    def get(self, request):
        try:
            # 최근 데이터에서 실제 사용된 카테고리들만 반환
            # date 파라미터 우선, 없으면 days 파라미터 사용
            date_param = request.GET.get('date')
            if date_param:
                try:
                    from datetime import datetime
                    target_date = datetime.strptime(date_param, '%Y-%m-%d').date()
                    days = 1
                except ValueError:
                    target_date = date.today()
                    days = 1
            else:
                days = int(request.GET.get('days', 1))  # 기본값을 1로 변경
                target_date = date.today()
                
            include_music = request.GET.get('include_music', 'false').lower() == 'true'
            
            if date_param or days == 1:
                # 특정 날짜 또는 오늘만 보는 경우
                queryset = TrendingVideo.objects.filter(
                    is_shorts=True,
                    trending_date=target_date
                )
            else:
                # 여러 날 보는 경우
                start_date = target_date - timedelta(days=days-1)
                queryset = TrendingVideo.objects.filter(
                    is_shorts=True,
                    trending_date__gte=start_date
                )
            
            # 음악 비디오 필터링
            if not include_music:
                queryset = queryset.exclude(
                    Q(category='Music') | 
                    Q(title__icontains='MV') |
                    Q(title__icontains='M/V') |
                    Q(title__icontains='뮤직비디오') |
                    Q(title__icontains='Music Video')
                )
            
            # categories를 Set으로 중복 제거하고 정렬
            categories = sorted(set(queryset.values_list('category', flat=True).distinct()))
            
            category_choices = dict(TrendingVideo.CATEGORY_CHOICES)
            available_categories = [
                {'value': 'all', 'label': '전체'},
            ]
            
            for category in categories:
                if category and category in category_choices:
                    available_categories.append({
                        'value': category,
                        'label': category_choices[category]
                    })
            
            return JsonResponse({
                'success': True,
                'categories': available_categories
            })
            
        except Exception as e:
            logger.error(f"카테고리 목록 API 오류: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class TrendingShortsListView(LoginRequiredMixin, View):
    """트렌딩 쇼츠 리스트 페이지 뷰 (조회수 기준 정렬)"""
    template_name = 'youtube_trending/trending_shorts_list.html'
    
    def get(self, request):
        user = request.user
        context = {
            'current_workspace': user.current_workspace,
            'is_workspace_mode': user.is_in_workspace_mode(),
            'page_title': '인기 트렌딩 쇼츠',
            'today': timezone.now().date()
        }
        return render(request, self.template_name, context)


class ShortsComparisonView(LoginRequiredMixin, View):
    """쇼츠 비교 페이지 뷰"""
    template_name = 'youtube_trending/shorts_comparison.html'
    
    def get(self, request):
        user = request.user
        context = {
            'current_workspace': user.current_workspace,
            'is_workspace_mode': user.is_in_workspace_mode(),
            'page_title': '인기 쇼츠 비교 & 즐겨찾기'
        }
        return render(request, self.template_name, context)


class ShortsComparisonAPIView(LoginRequiredMixin, View):
    """쇼츠 비교 API (날짜별 비교)"""
    
    def get(self, request):
        try:
            # 비교할 날짜들
            date1 = request.GET.get('date1')
            date2 = request.GET.get('date2')
            include_music = request.GET.get('include_music', 'false').lower() == 'true'
            limit = int(request.GET.get('limit', 20))
            limit = min(limit, 50)
            
            if not date1:
                return JsonResponse({'error': '첫 번째 날짜가 필요합니다.'}, status=400)
            
            try:
                from datetime import datetime
                target_date1 = datetime.strptime(date1, '%Y-%m-%d').date()
                target_date2 = datetime.strptime(date2, '%Y-%m-%d').date() if date2 else None
            except ValueError:
                return JsonResponse({'error': '올바른 날짜 형식이 아닙니다. (YYYY-MM-DD)'}, status=400)
            
            collector = TrendingDataService()
            
            # 첫 번째 날짜 데이터
            queryset1 = TrendingVideo.objects.filter(
                is_shorts=True,
                trending_date=target_date1
            )
            
            if not include_music:
                queryset1 = queryset1.exclude(
                    Q(category='Music') | 
                    Q(title__icontains='MV') |
                    Q(title__icontains='M/V') |
                    Q(title__icontains='뮤직비디오') |
                    Q(title__icontains='Music Video')
                )
            
            videos1 = queryset1.order_by('trending_rank')[:limit]
            
            # 두 번째 날짜 데이터 (있을 경우)
            videos2 = []
            if target_date2:
                queryset2 = TrendingVideo.objects.filter(
                    is_shorts=True,
                    trending_date=target_date2
                )
                
                if not include_music:
                    queryset2 = queryset2.exclude(
                        Q(category='Music') | 
                        Q(title__icontains='MV') |
                        Q(title__icontains='M/V') |
                        Q(title__icontains='뮤직비디오') |
                        Q(title__icontains='Music Video')
                    )
                
                videos2 = queryset2.order_by('trending_rank')[:limit]
            
            # 비교 데이터 생성
            comparison_data = []
            
            for video1 in videos1:
                video_data = {
                    'video1': {
                        'youtube_id': video1.youtube_id,
                        'title': video1.title,
                        'channel_title': video1.channel_title,
                        'thumbnail_url': video1.thumbnail_url,
                        'youtube_url': video1.youtube_url,
                        'view_count': video1.view_count,
                        'formatted_view_count': video1.formatted_view_count,
                        'trending_rank': video1.trending_rank,
                        'trending_date': video1.trending_date.strftime('%Y-%m-%d'),
                        'category': video1.get_category_display(),
                    },
                    'video2': None,
                    'rank_change': None,
                    'view_change': None,
                    'is_same_video': False
                }
                
                # 같은 비디오가 두 번째 날짜에도 있는지 확인
                if target_date2:
                    video2 = next((v for v in videos2 if v.youtube_id == video1.youtube_id), None)
                    if video2:
                        video_data['video2'] = {
                            'youtube_id': video2.youtube_id,
                            'title': video2.title,
                            'channel_title': video2.channel_title,
                            'thumbnail_url': video2.thumbnail_url,
                            'youtube_url': video2.youtube_url,
                            'view_count': video2.view_count,
                            'formatted_view_count': video2.formatted_view_count,
                            'trending_rank': video2.trending_rank,
                            'trending_date': video2.trending_date.strftime('%Y-%m-%d'),
                            'category': video2.get_category_display(),
                        }
                        video_data['is_same_video'] = True
                        video_data['rank_change'] = video1.trending_rank - video2.trending_rank  # 양수: 순위 하락, 음수: 순위 상승
                        video_data['view_change'] = video2.view_count - video1.view_count
                
                comparison_data.append(video_data)
            
            # 두 번째 날짜에만 있는 비디오들 추가
            if target_date2:
                date1_youtube_ids = {v.youtube_id for v in videos1}
                for video2 in videos2:
                    if video2.youtube_id not in date1_youtube_ids:
                        video_data = {
                            'video1': None,
                            'video2': {
                                'youtube_id': video2.youtube_id,
                                'title': video2.title,
                                'channel_title': video2.channel_title,
                                'thumbnail_url': video2.thumbnail_url,
                                'youtube_url': video2.youtube_url,
                                'view_count': video2.view_count,
                                'formatted_view_count': video2.formatted_view_count,
                                'trending_rank': video2.trending_rank,
                                'trending_date': video2.trending_date.strftime('%Y-%m-%d'),
                                'category': video2.get_category_display(),
                            },
                            'rank_change': None,
                            'view_change': None,
                            'is_same_video': False,
                            'is_new': True
                        }
                        comparison_data.append(video_data)
            
            return JsonResponse({
                'success': True,
                'comparison_data': comparison_data,
                'date1': date1,
                'date2': date2,
                'total_count': len(comparison_data)
            })
            
        except Exception as e:
            logger.error(f"쇼츠 비교 API 오류: {e}")
            return JsonResponse({'error': '데이터를 가져오는 중 오류가 발생했습니다.'}, status=500)


class FavoriteShortsAPIView(LoginRequiredMixin, View):
    """즐겨찾기 관리 API"""
    
    def get(self, request):
        """즐겨찾기 목록 조회"""
        try:
            user = request.user
            limit = int(request.GET.get('limit', 20))
            limit = min(limit, 50)
            page = int(request.GET.get('page', 1))
            
            # 현재 워크스페이스에 따른 즐겨찾기 조회
            if user.is_in_workspace_mode():
                favorites = FavoriteShorts.objects.filter(
                    workspace=user.current_workspace
                ).select_related('trending_video', 'user').order_by('-created_at')
            else:
                favorites = FavoriteShorts.objects.filter(
                    user=user,
                    workspace__isnull=True
                ).select_related('trending_video', 'user').order_by('-created_at')
            
            # 페이지네이션
            paginator = Paginator(favorites, limit)
            page_obj = paginator.get_page(page)
            
            favorites_data = []
            for favorite in page_obj:
                favorites_data.append({
                    'favorite_id': str(favorite.favorite_id),
                    'note': favorite.note or '',
                    'tags': favorite.tags,
                    'favorited_rank': favorite.favorited_rank,
                    'favorited_view_count': favorite.favorited_view_count,
                    'view_count_change': favorite.view_count_change,
                    'rank_change': favorite.rank_change,
                    'created_at': favorite.created_at.strftime('%Y-%m-%d %H:%M'),
                    'user_name': favorite.user.get_full_name() or favorite.user.username,
                    'can_edit': favorite.can_user_edit(user),
                    'video': {
                        'youtube_id': favorite.trending_video.youtube_id,
                        'title': favorite.trending_video.title,
                        'channel_title': favorite.trending_video.channel_title,
                        'thumbnail_url': favorite.trending_video.thumbnail_url,
                        'youtube_url': favorite.trending_video.youtube_url,
                        'view_count': favorite.trending_video.view_count,
                        'formatted_view_count': favorite.trending_video.formatted_view_count,
                        'trending_rank': favorite.trending_video.trending_rank,
                        'trending_date': favorite.trending_video.trending_date.strftime('%Y-%m-%d'),
                        'category': favorite.trending_video.get_category_display(),
                    }
                })
            
            return JsonResponse({
                'success': True,
                'favorites': favorites_data,
                'pagination': {
                    'current_page': page_obj.number,
                    'total_pages': paginator.num_pages,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous(),
                    'total_count': paginator.count,
                }
            })
            
        except Exception as e:
            logger.error(f"즐겨찾기 조회 API 오류: {e}")
            return JsonResponse({'error': '데이터를 가져오는 중 오류가 발생했습니다.'}, status=500)
    
    def post(self, request):
        """즐겨찾기 추가"""
        try:
            import json
            data = json.loads(request.body)
            
            youtube_id = data.get('youtube_id')
            note = data.get('note', '')
            tags = data.get('tags', [])
            
            if not youtube_id:
                return JsonResponse({'error': 'YouTube ID가 필요합니다.'}, status=400)
            
            # 트렌딩 비디오 찾기 (가장 최근 데이터)
            try:
                trending_video = TrendingVideo.objects.filter(
                    youtube_id=youtube_id,
                    is_shorts=True
                ).order_by('-trending_date').first()
                
                if not trending_video:
                    return JsonResponse({'error': '해당 쇼츠를 찾을 수 없습니다.'}, status=404)
            except TrendingVideo.DoesNotExist:
                return JsonResponse({'error': '해당 쇼츠를 찾을 수 없습니다.'}, status=404)
            
            user = request.user
            workspace = user.current_workspace if user.is_in_workspace_mode() else None
            
            # 중복 확인
            if FavoriteShorts.objects.filter(
                user=user,
                workspace=workspace,
                trending_video=trending_video
            ).exists():
                return JsonResponse({'error': '이미 즐겨찾기에 추가된 영상입니다.'}, status=400)
            
            # 즐겨찾기 생성
            favorite = FavoriteShorts.objects.create(
                user=user,
                workspace=workspace,
                trending_video=trending_video,
                note=note,
                tags=tags,
                favorited_rank=trending_video.trending_rank,
                favorited_view_count=trending_video.view_count
            )
            
            return JsonResponse({
                'success': True,
                'message': '즐겨찾기에 추가되었습니다.',
                'favorite_id': str(favorite.favorite_id)
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': '잘못된 JSON 형식입니다.'}, status=400)
        except Exception as e:
            logger.error(f"즐겨찾기 추가 API 오류: {e}")
            return JsonResponse({'error': '즐겨찾기 추가 중 오류가 발생했습니다.'}, status=500)
    
    def put(self, request):
        """즐겨찾기 수정"""
        try:
            import json
            data = json.loads(request.body)
            
            favorite_id = data.get('favorite_id')
            note = data.get('note', '')
            tags = data.get('tags', [])
            
            if not favorite_id:
                return JsonResponse({'error': '즐겨찾기 ID가 필요합니다.'}, status=400)
            
            try:
                favorite = FavoriteShorts.objects.get(favorite_id=favorite_id)
            except FavoriteShorts.DoesNotExist:
                return JsonResponse({'error': '즐겨찾기를 찾을 수 없습니다.'}, status=404)
            
            # 수정 권한 확인
            if not favorite.can_user_edit(request.user):
                return JsonResponse({'error': '수정 권한이 없습니다.'}, status=403)
            
            # 업데이트
            favorite.note = note
            favorite.tags = tags
            favorite.save()
            
            return JsonResponse({
                'success': True,
                'message': '즐겨찾기가 수정되었습니다.'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': '잘못된 JSON 형식입니다.'}, status=400)
        except Exception as e:
            logger.error(f"즐겨찾기 수정 API 오류: {e}")
            return JsonResponse({'error': '즐겨찾기 수정 중 오류가 발생했습니다.'}, status=500)
    
    def delete(self, request):
        """즐겨찾기 삭제"""
        try:
            import json
            data = json.loads(request.body)
            
            favorite_id = data.get('favorite_id')
            
            if not favorite_id:
                return JsonResponse({'error': '즐겨찾기 ID가 필요합니다.'}, status=400)
            
            try:
                favorite = FavoriteShorts.objects.get(favorite_id=favorite_id)
            except FavoriteShorts.DoesNotExist:
                return JsonResponse({'error': '즐겨찾기를 찾을 수 없습니다.'}, status=404)
            
            # 삭제 권한 확인
            if not favorite.can_user_edit(request.user):
                return JsonResponse({'error': '삭제 권한이 없습니다.'}, status=403)
            
            favorite.delete()
            
            return JsonResponse({
                'success': True,
                'message': '즐겨찾기가 삭제되었습니다.'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': '잘못된 JSON 형식입니다.'}, status=400)
        except Exception as e:
            logger.error(f"즐겨찾기 삭제 API 오류: {e}")
            return JsonResponse({'error': '즐겨찾기 삭제 중 오류가 발생했습니다.'}, status=500)


class FavoriteStatusBatchAPIView(LoginRequiredMixin, View):
    """즐겨찾기 상태 배치 조회 API (깜빡임 방지)"""
    
    def post(self, request):
        try:
            import json
            data = json.loads(request.body)
            
            youtube_ids = data.get('youtube_ids', [])
            if not youtube_ids:
                return JsonResponse({'error': 'YouTube ID 목록이 필요합니다.'}, status=400)
            
            user = request.user
            workspace = user.current_workspace if user.is_in_workspace_mode() else None
            
            # 즐겨찾기 상태를 효율적으로 조회
            favorite_videos = {}
            if youtube_ids:
                from .models import FavoriteShorts
                favorites = FavoriteShorts.objects.filter(
                    user=user,
                    workspace=workspace,
                    trending_video__youtube_id__in=youtube_ids
                ).select_related('trending_video')
                
                favorite_videos = {
                    fav.trending_video.youtube_id: {
                        'is_favorite': True,
                        'favorite_id': str(fav.favorite_id)
                    } for fav in favorites
                }
            
            # 요청된 모든 YouTube ID에 대한 상태 반환
            status_data = {}
            for youtube_id in youtube_ids:
                if youtube_id in favorite_videos:
                    status_data[youtube_id] = favorite_videos[youtube_id]
                else:
                    status_data[youtube_id] = {
                        'is_favorite': False,
                        'favorite_id': None
                    }
            
            return JsonResponse({
                'success': True,
                'favorite_status': status_data
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': '잘못된 JSON 형식입니다.'}, status=400)
        except Exception as e:
            logger.error(f"즐겨찾기 상태 배치 조회 API 오류: {e}")
            return JsonResponse({'error': '상태 조회 중 오류가 발생했습니다.'}, status=500)


class TrendMatrixAPIView(LoginRequiredMixin, View):
    """트렌드 매트릭스 API (날짜별 순위 변화 매트릭스)"""
    
    def get(self, request):
        try:
            days = int(request.GET.get('days', 7))
            limit = int(request.GET.get('limit', 20))
            include_music = request.GET.get('include_music', 'false').lower() == 'true'
            
            from datetime import date, timedelta
            
            # 날짜 범위 생성
            end_date = date.today()
            start_date = end_date - timedelta(days=days-1)
            date_range = []
            current_date = start_date
            while current_date <= end_date:
                date_range.append(current_date)
                current_date += timedelta(days=1)
            
            # 각 날짜별 쇼츠 데이터 조회
            queryset = TrendingVideo.objects.filter(
                is_shorts=True,
                trending_date__gte=start_date,
                trending_date__lte=end_date
            )
            
            if not include_music:
                queryset = queryset.exclude(
                    Q(category='Music') | 
                    Q(title__icontains='MV') |
                    Q(title__icontains='M/V') |
                    Q(title__icontains='뮤직비디오') |
                    Q(title__icontains='Music Video')
                )
            
            # 날짜별로 그룹화
            videos_by_date = {}
            for video in queryset:
                if video.trending_date not in videos_by_date:
                    videos_by_date[video.trending_date] = {}
                videos_by_date[video.trending_date][video.youtube_id] = video
            
            # 모든 고유한 영상 ID 수집 (기간 내에 등장한 모든 영상)
            all_video_ids = set()
            for videos in videos_by_date.values():
                all_video_ids.update(videos.keys())
            
            # 매트릭스 데이터 생성
            matrix_data = []
            video_info_cache = {}
            
            # 즐겨찾기 상태를 효율적으로 조회 (N+1 문제 해결)
            user = request.user
            workspace = user.current_workspace if user.is_in_workspace_mode() else None
            
            # 현재 모든 비디오들의 즐겨찾기 상태를 한 번에 조회
            favorite_videos = {}
            if all_video_ids:
                from .models import FavoriteShorts
                favorites = FavoriteShorts.objects.filter(
                    user=user,
                    workspace=workspace,
                    trending_video__youtube_id__in=all_video_ids
                ).select_related('trending_video')
                
                favorite_videos = {fav.trending_video.youtube_id: str(fav.favorite_id) for fav in favorites}
            
            for youtube_id in all_video_ids:
                # 각 영상의 기본 정보 (가장 최근 데이터 사용)
                video_info = None
                for date_item in reversed(date_range):
                    if date_item in videos_by_date and youtube_id in videos_by_date[date_item]:
                        video_info = videos_by_date[date_item][youtube_id]
                        break
                
                if not video_info:
                    continue
                
                # 날짜별 순위 데이터
                date_rankings = []
                for date_item in date_range:
                    if date_item in videos_by_date and youtube_id in videos_by_date[date_item]:
                        video = videos_by_date[date_item][youtube_id]
                        date_rankings.append({
                            'date': date_item.strftime('%Y-%m-%d'),
                            'rank': video.trending_rank,
                            'view_count': video.view_count,
                            'formatted_view_count': video.formatted_view_count,
                            'has_data': True
                        })
                    else:
                        date_rankings.append({
                            'date': date_item.strftime('%Y-%m-%d'),
                            'rank': None,
                            'view_count': None,
                            'formatted_view_count': None,
                            'has_data': False
                        })
                
                # 순위 변화 계산
                first_rank = None
                last_rank = None
                for ranking in date_rankings:
                    if ranking['has_data']:
                        if first_rank is None:
                            first_rank = ranking['rank']
                        last_rank = ranking['rank']
                
                rank_change = None
                if first_rank is not None and last_rank is not None and first_rank != last_rank:
                    rank_change = first_rank - last_rank  # 양수: 순위 상승, 음수: 순위 하락
                
                matrix_data.append({
                    'video_info': {
                        'youtube_id': video_info.youtube_id,
                        'title': video_info.title,
                        'channel_title': video_info.channel_title,
                        'thumbnail_url': video_info.thumbnail_url,
                        'youtube_url': video_info.youtube_url,
                        'category': video_info.get_category_display(),
                        'is_favorite': video_info.youtube_id in favorite_videos,  # 즐겨찾기 상태 추가
                        'favorite_id': favorite_videos.get(video_info.youtube_id),  # 즐겨찾기 ID 추가
                    },
                    'date_rankings': date_rankings,
                    'rank_change': rank_change,
                    'first_rank': first_rank,
                    'last_rank': last_rank,
                    'appeared_days': sum(1 for r in date_rankings if r['has_data'])
                })
            
            # 최근 순위나 등장 빈도로 정렬
            matrix_data.sort(key=lambda x: (
                x['last_rank'] if x['last_rank'] is not None else 999,
                -x['appeared_days']
            ))
            
            # 상위 N개만 반환
            matrix_data = matrix_data[:limit]
            
            return JsonResponse({
                'success': True,
                'matrix_data': matrix_data,
                'date_range': [d.strftime('%Y-%m-%d') for d in date_range],
                'total_videos': len(matrix_data),
                'days': days
            })
            
        except Exception as e:
            logger.error(f"트렌드 매트릭스 API 오류: {e}")
            return JsonResponse({'error': '데이터를 가져오는 중 오류가 발생했습니다.'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def extract_tags_api(request):
    """YouTube URL에서 태그 추출 API"""
    try:
        data = json.loads(request.body)
        youtube_url = data.get('url', '').strip()
        
        if not youtube_url:
            return JsonResponse({
                'success': False,
                'error': 'URL이 필요합니다.'
            }, status=400)
        
        # 태그 추출 서비스 실행
        extractor = YouTubeTagExtractor()
        result = extractor.extract_tags_from_url(youtube_url)
        
        if result['success']:
            return JsonResponse(result)
        else:
            return JsonResponse(result, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': '잘못된 JSON 형식입니다.'
        }, status=400)
    except Exception as e:
        logger.error(f"태그 추출 API 오류: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': '서버 오류가 발생했습니다.'
        }, status=500)
