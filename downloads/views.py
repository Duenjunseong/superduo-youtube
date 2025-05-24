import re
import uuid
import json
import subprocess
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse, FileResponse
from django.urls import reverse_lazy
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils import timezone
import os
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import render_to_string
from django.conf import settings
import logging
from pathlib import Path
import mimetypes

# 모델과 태스크 임포트
from .models import Job, File, Tag
from .forms import LinkForm
from .tasks.download import download_video

logger = logging.getLogger(__name__)

# YouTube URL 정규식 패턴
YOUTUBE_REGEX = re.compile(
    r'^(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11}).*$'
)


class LinksView(LoginRequiredMixin, TemplateView):
    """링크 업로드 및 작업 목록 페이지"""
    template_name = 'downloads/links.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 폼 추가
        context['form'] = LinkForm()
        
        # 페이지네이션 설정
        page = self.request.GET.get('page', 1)
        per_page = 10  # 페이지당 항목 수
        
        # 정렬 및 필터 옵션
        sort_option = self.request.GET.get('sort', '최신순')
        filters = self.request.GET.getlist('filters[]')
        
        # 작업 목록 조회
        jobs_query = Job.objects.filter(user=self.request.user)
        
        # 상태별 작업 리스트 조회
        active_jobs = jobs_query.filter(status__in=['queued', 'running', 'pending', 'processing'])
        completed_jobs = jobs_query.filter(status__in=['done', 'completed'])
        cancelled_jobs = jobs_query.filter(status__in=['cancelled', 'failed'])
        
        # 필터 적용
        if filters:
            jobs_query = jobs_query.filter(status__in=filters)
        
        # 정렬 적용
        if sort_option == '최신순':
            jobs_query = jobs_query.order_by('-created_at')
        elif sort_option == '오래된순':
            jobs_query = jobs_query.order_by('created_at')
        elif sort_option == '상태순_오름차순':
            jobs_query = jobs_query.order_by('status', '-created_at')
        elif sort_option == '상태순_내림차순':
            jobs_query = jobs_query.order_by('-status', '-created_at')
        elif sort_option == '완료일순_내림차순':
            jobs_query = jobs_query.order_by('-finished_at', '-created_at')
        elif sort_option == '완료일순_오름차순':
            jobs_query = jobs_query.order_by('finished_at', '-created_at')
        
        # 페이지네이션 적용
        paginator = Paginator(jobs_query, per_page)
        pagination = paginator.get_page(page)
        
        context.update({
            'pagination': pagination,
            'active_jobs': active_jobs,
            'completed_jobs': completed_jobs,
            'cancelled_jobs': cancelled_jobs,
            'all_jobs': jobs_query,
            'total_jobs_count': jobs_query.count(),
            'tags': Tag.objects.filter(user=self.request.user),
            'color_classes': [
                'pastel-blue', 'pastel-green', 'pastel-yellow', 'pastel-pink',
                'pastel-purple', 'pastel-orange', 'pastel-mint', 'pastel-gray'
            ]
        })
        
        return context
    
    def post(self, request, *args, **kwargs):
        form = LinkForm(request.POST)
        
        if form.is_valid():
            urls = form.cleaned_data['urls'].split('\n')
            quality = form.cleaned_data['quality']
            
            # 선택된 태그 처리
            selected_tags = request.POST.get('selected_tags', '')
            tag_ids = [tag_id.strip() for tag_id in selected_tags.split(',') if tag_id.strip()]
            
            jobs = []
            
            # 각 URL에 대해 작업 생성
            for url in urls:
                url = url.strip()
                
                # URL이 비어있는 경우 무시
                if not url:
                    continue
                
                # URL이 유효한지 확인
                if YOUTUBE_REGEX.match(url):
                    # 영상 제목 가져오기 시도
                    try:
                        # yt-dlp로 영상 정보 가져오기
                        cmd = [
                            'yt-dlp',
                            '--dump-json',
                            '--no-playlist',
                            url
                        ]
                        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                        video_info = json.loads(result.stdout)
                        video_title = video_info.get('title', '')
                    except Exception as e:
                        # 제목 가져오기 실패 시 빈 문자열 사용
                        video_title = ''
                    
                    # 작업 생성
                    job = Job.objects.create(
                        user=request.user,
                        url=url,
                        src_url=url,  # 표시용 URL 저장
                        title=video_title,  # 영상 제목 저장
                        status='pending',
                        quality=quality,
                        progress=0  # 초기 진행 상태 명시적 설정
                    )
                    
                    # 선택된 태그들을 작업에 추가
                    if tag_ids:
                        tags = Tag.objects.filter(id__in=tag_ids, user=request.user)
                        job.tags.add(*tags)
                    
                    # Celery 작업 시작
                    task = download_video.delay(url, request.user.id)
                    
                    # 작업 ID 업데이트
                    job.task_id = task.id
                    job.save()
                    
                    jobs.append({
                        'id': str(job.id),
                        'src_url': job.src_url,
                        'title': job.title,
                        'quality': job.get_quality_display()
                    })
            
            # AJAX 요청인 경우 JSON 응답
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'message': '다운로드 작업이 시작되었습니다.',
                    'jobs': jobs
                })
            
            # 일반 요청인 경우 리디렉션
            return redirect('downloads:links')
        
        # AJAX 요청인 경우 오류 메시지 JSON 응답
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            errors = []
            for field, error_list in form.errors.items():
                errors.extend(error_list)
                
            return JsonResponse({
                'status': 'error',
                'message': '입력값이 올바르지 않습니다.',
                'errors': errors
            }, status=400)
        
        # 폼이 유효하지 않은 경우, 컨텍스트에 폼 추가하여 템플릿 렌더링
        context = self.get_context_data()
        context['form'] = form
        return self.render_to_response(context)


# 기존 함수 기반 뷰 유지
def download_form(request):
    return render(request, 'downloads/download_form.html')

@login_required
@require_POST
def submit_url(request):
    url = request.POST.get('url')
    
    # 작업 생성
    job = Job.objects.create(user=request.user, url=url, status='pending')
    
    # Celery 작업 시작
    task = download_video.delay(url, request.user.id)
    
    # 작업 ID 업데이트
    job.task_id = task.id
    job.save()
    
    return JsonResponse({
        'status': 'success',
        'job_id': job.id,
        'message': '다운로드 작업이 시작되었습니다.'
    })

@login_required
def job_status(request, job_id):
    job = get_object_or_404(Job, id=job_id, user=request.user)
    
    files = []
    for file in job.files.all():
        files.append({
            'id': file.id,
            'filename': file.filename,
            'file_size': file.file_size,
            'file_type': file.file_type
        })
    
    # 완료된 작업일 경우 finished_at 포함
    finished_at = None
    if job.finished_at:
        finished_at = job.finished_at.strftime('%Y-%m-%d %H:%M:%S')
    
    return JsonResponse({
        'id': str(job.id),
        'status': job.status,
        'progress': job.progress if job.progress is not None else (100 if job.status == 'completed' else 0),
        'message': job.error_message or job.error_msg or f'작업 상태: {job.get_status_display()}',
        'files': files,
        'created_at': job.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'finished_at': finished_at,
        'quality': job.get_quality_display()
    })

@login_required
def download_list(request):
    jobs = Job.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'downloads/download_list.html', {'jobs': jobs})

@login_required
def download_file(request, file_id):
    try:
        # UUID 유효성 검사
        try:
            uuid.UUID(file_id)  # UUID 형식 검증
        except ValueError:
            logger.error(f"잘못된 UUID 형식: {file_id}")
            return HttpResponse("잘못된 파일 ID입니다.", status=400)
        
        file = get_object_or_404(File, id=file_id, job__user=request.user)
        
        # 상세한 디버깅 정보 로깅
        logger.info(f"다운로드 요청 - File ID: {file_id}, User: {request.user.username}")
        logger.info(f"파일 정보 - filename: {file.filename}, file_path: {file.file_path}")
        logger.info(f"MEDIA_ROOT: {settings.MEDIA_ROOT}")
        logger.info(f"USE_X_ACCEL_REDIRECT: {getattr(settings, 'USE_X_ACCEL_REDIRECT', False)}")
        
        # 파일 경로 정규화
        file_path = Path(file.file_path)
        if not file_path.is_absolute():
            # 상대 경로인 경우 MEDIA_ROOT와 결합
            file_path = Path(settings.MEDIA_ROOT) / file.file_path
        
        logger.info(f"최종 파일 경로: {file_path}")
        
        # 파일 존재 확인
        if not file_path.exists():
            logger.error(f"파일이 존재하지 않음: {file_path}")
            return HttpResponse(f"파일을 찾을 수 없습니다: {file_path}", status=404)
        
        # 파일 읽기 권한 확인
        if not os.access(file_path, os.R_OK):
            logger.error(f"파일 읽기 권한 없음: {file_path}")
            return HttpResponse("파일에 대한 읽기 권한이 없습니다.", status=403)
        
        # 파일 크기 확인
        file_size = file_path.stat().st_size
        logger.info(f"파일 크기: {file_size} bytes")
        
        if file_size == 0:
            logger.error(f"파일 크기가 0: {file_path}")
            return HttpResponse("파일이 비어있습니다.", status=400)
        
        # Content-Type 결정 (mimetypes 모듈 사용)
        content_type, _ = mimetypes.guess_type(file.filename)
        if not content_type:
            content_type = 'application/octet-stream'
        
        logger.info(f"Content-Type: {content_type}")
        
        # 운영환경에서는 X-Accel-Redirect 사용
        if getattr(settings, 'USE_X_ACCEL_REDIRECT', False):
            logger.info("X-Accel-Redirect 방식 사용")
            response = HttpResponse()
            
            # 파일 경로를 nginx가 이해할 수 있는 형태로 변환
            media_root = Path(settings.MEDIA_ROOT)
            try:
                relative_path = file_path.relative_to(media_root)
                internal_url = f"/protected-files/{relative_path}"
                logger.info(f"Internal URL: {internal_url}")
                
                response['X-Accel-Redirect'] = internal_url
                response['Content-Disposition'] = f'attachment; filename="{file.filename}"'
                response['Content-Type'] = content_type
                
                return response
            except ValueError as e:
                logger.error(f"경로 변환 실패: {e}")
                # X-Accel-Redirect 실패 시 일반 방식으로 폴백
        
        # 개발환경 또는 X-Accel-Redirect 실패 시 직접 전송
        logger.info("FileResponse 방식 사용")
        
        try:
            # 파일을 바이너리 모드로 열기
            file_handle = open(file_path, 'rb')
            
            response = FileResponse(
                file_handle,
                as_attachment=True,
                filename=file.filename
            )
            
            response['Content-Length'] = file_size
            response['Content-Type'] = content_type
            
            # 캐시 헤더 추가
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            
            logger.info(f"FileResponse 생성 완료 - Content-Length: {file_size}")
            return response
            
        except Exception as e:
            logger.error(f"FileResponse 생성 실패: {str(e)}")
            return HttpResponse(f"파일 읽기 중 오류가 발생했습니다: {str(e)}", status=500)
        
    except Exception as e:
        logger.error(f"파일 다운로드 중 예외 발생: {str(e)}", exc_info=True)
        return HttpResponse(f"파일 다운로드 중 오류가 발생했습니다: {str(e)}", status=500)


@login_required
def cancel_job(request, job_id):
    """작업 취소 뷰"""
    job = get_object_or_404(Job, id=job_id, user=request.user)
    
    # 취소 가능한 상태인지 확인 (대기 중인 작업만 취소 가능)
    if job.status not in ['pending', 'queued']:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'error',
                'message': '진행 중이거나 완료된 작업은 취소할 수 없습니다.'
            }, status=400)
        return redirect('downloads:links')
    
    # 작업 상태 업데이트
    job.status = 'cancelled'
    job.error_message = '사용자에 의해 취소됨'
    job.finished_at = timezone.now()  # 취소 시간 기록
    job.save()
    
    # AJAX 요청에 대한 응답
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'success',
            'message': '작업이 취소되었습니다.'
        })
    
    # 일반 요청에 대한 응답
    return redirect('downloads:links')


class JobsListView(LoginRequiredMixin, ListView):
    """모든 작업 목록 뷰"""
    model = Job
    template_name = 'downloads/jobs_list.html'
    context_object_name = 'jobs'
    
    def get_queryset(self):
        return Job.objects.filter(user=self.request.user).order_by('-created_at')


@login_required
@require_POST
def save_job_memo(request):
    """작업 메모 저장 뷰"""
    job_id = request.POST.get('job_id')
    memo = request.POST.get('memo', '')
    
    try:
        job = get_object_or_404(Job, id=job_id, user=request.user)
        job.memo = memo
        job.save()
        
        return JsonResponse({
            'status': 'success',
            'message': '메모가 저장되었습니다.'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'메모 저장 중 오류가 발생했습니다: {str(e)}'
        }, status=400)

@login_required
@require_POST
def delete_job(request, job_id):
    """작업 삭제 뷰"""
    try:
        job = get_object_or_404(Job, id=job_id, user=request.user)
        
        # 파일 삭제
        for file in job.files.all():
            try:
                if os.path.exists(file.file_path):
                    os.remove(file.file_path)
            except Exception as e:
                # 파일 삭제 실패 시 로깅만 하고 계속 진행
                print(f"파일 삭제 실패: {file.file_path}, 오류: {str(e)}")
        
        # 작업과 관련 파일 레코드 삭제
        job_title = job.title or job.url
        job.delete()
        
        # 응답
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': f'작업 "{job_title}"이(가) 삭제되었습니다.'
            })
        
        # AJAX가 아닌 경우 리디렉션
        return redirect('downloads:links')
    
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'error',
                'message': f'작업 삭제 중 오류가 발생했습니다: {str(e)}'
            }, status=500)
        
        # AJAX가 아닌 경우 리디렉션
        return redirect('downloads:links')

@login_required
@csrf_exempt
def job_counts(request):
    """작업 상태별 카운트를 반환하는 API"""
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        jobs_query = Job.objects.filter(user=request.user)
        
        # 상태별 카운트
        active_jobs = jobs_query.filter(status__in=['queued', 'running', 'pending', 'processing']).count()
        completed_jobs = jobs_query.filter(status__in=['done', 'completed']).count()
        cancelled_jobs = jobs_query.filter(status__in=['cancelled', 'failed']).count()
        total_jobs = jobs_query.count()
        
        return JsonResponse({
            'active': active_jobs,
            'completed': completed_jobs,
            'cancelled': cancelled_jobs,
            'total': total_jobs
        })
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def job_list_ajax(request):
    """AJAX로 작업 목록을 반환하는 API"""
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        status = request.GET.get('status', 'all')
        jobs_query = Job.objects.filter(user=request.user)
        
        # 상태별 필터링
        if status == 'active':
            jobs = jobs_query.filter(status__in=['queued', 'running', 'pending', 'processing'])
        elif status == 'completed':
            jobs = jobs_query.filter(status__in=['done', 'completed'])
        elif status == 'cancelled':
            jobs = jobs_query.filter(status__in=['cancelled', 'failed'])
        else:
            jobs = jobs_query
        
        # 템플릿 렌더링
        html = render_to_string('downloads/job_list_fragment.html', {
            'jobs': jobs,
            'status': status
        }, request=request)
        
        return JsonResponse({'html': html})
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

@require_POST
@login_required
def create_tag(request):
    name = request.POST.get('name')
    color = request.POST.get('color', 'pastel-blue')
    if not name:
        return JsonResponse({'status': 'error', 'message': '태그 이름을 입력해주세요.'})
    if Tag.objects.filter(name=name, user=request.user).exists():
        return JsonResponse({'status': 'error', 'message': '이미 존재하는 태그입니다.'})
    tag = Tag.objects.create(name=name, color=color, user=request.user)
    return JsonResponse({
        'status': 'success',
        'tag': {
            'id': tag.id,
            'name': tag.name,
            'color': tag.color
        }
    })

@require_POST
@login_required
def delete_tag(request, tag_id):
    try:
        tag = Tag.objects.get(id=tag_id, user=request.user)
        tag_name = tag.name
        
        # 이 태그가 적용된 작업 수 확인
        related_jobs_count = tag.jobs.count()
        
        # 태그 삭제 (ManyToManyField 관계도 자동으로 삭제됨)
        tag.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': f'태그 "{tag_name}"이(가) 삭제되었습니다.',
            'deleted_tag': {
                'id': tag_id,
                'name': tag_name,
                'related_jobs_count': related_jobs_count
            }
        })
    except Tag.DoesNotExist:
        return JsonResponse({
            'status': 'error', 
            'message': '태그를 찾을 수 없습니다.'
        }, status=404)

@require_POST
@login_required
def update_job_tags(request):
    job_id = request.POST.get('job_id')
    tag_ids = request.POST.getlist('tags')
    
    try:
        job = Job.objects.get(id=job_id)
        # 기존 태그 제거
        job.tags.clear()
        # 새 태그 추가
        if tag_ids:
            tags = Tag.objects.filter(id__in=tag_ids)
            job.tags.add(*tags)
        return JsonResponse({'status': 'success'})
    except Job.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '작업을 찾을 수 없습니다.'})

@require_POST
@login_required
def tag_update(request, tag_id):
    """태그 이름 업데이트 뷰"""
    try:
        tag = Tag.objects.get(id=tag_id)
        new_name = request.POST.get('name')
        new_color = request.POST.get('color')
        
        if not new_name and not new_color:
            return JsonResponse({'status': 'error', 'message': '태그 이름이나 색상 중 하나는 입력해주세요.'})
        
        # 이미 존재하는 태그인지 확인
        if Tag.objects.filter(name=new_name).exclude(id=tag_id).exists():
            return JsonResponse({'status': 'error', 'message': '이미 존재하는 태그입니다.'})
        
        if new_name:
            tag.name = new_name
        if new_color:
            tag.color = new_color
        tag.save()
        
        return JsonResponse({
            'status': 'success',
            'tag': {
                'id': tag.id,
                'name': tag.name,
                'color': tag.color
            }
        })
    except Tag.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '태그를 찾을 수 없습니다.'})

@login_required
def update_tag(request, tag_id):
    if request.method == 'POST':
        try:
            tag = Tag.objects.get(id=tag_id, user=request.user)
            
            # name과 color 중 어떤 것이 변경되는지 확인
            name_provided = 'name' in request.POST and request.POST.get('name', '').strip()
            color_provided = 'color' in request.POST and request.POST.get('color', '').strip()
            
            # 이름이 제공된 경우에만 이름 변경 및 검증
            if name_provided:
                name = request.POST.get('name', '').strip()
                if not name:
                    return JsonResponse({'status': 'error', 'message': '이름을 입력해 주세요'}, status=400)
                
                # 중복 이름 검사 (자신 제외)
                if Tag.objects.filter(name=name, user=request.user).exclude(id=tag_id).exists():
                    return JsonResponse({'status': 'error', 'message': '이미 존재하는 태그 이름입니다.'}, status=400)
                
                tag.name = name
            
            # 색상이 제공된 경우 색상 변경
            if color_provided:
                color = request.POST.get('color')
                tag.color = color
            
            # 이름도 색상도 제공되지 않은 경우
            if not name_provided and not color_provided:
                return JsonResponse({'status': 'error', 'message': '변경할 내용이 없습니다.'}, status=400)
            
            tag.save()
            return JsonResponse({
                'status': 'success',
                'tag': {
                    'id': tag.id,
                    'name': tag.name,
                    'color': tag.color
                }
            })
        except Tag.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': '태그를 찾을 수 없습니다.'
            }, status=404)
    return JsonResponse({
        'status': 'error',
        'message': '잘못된 요청입니다.'
    }, status=400)

@login_required
def toggle_job_tag(request):
    """작업에 태그를 토글하는 뷰"""
    if request.method == 'POST':
        job_id = request.POST.get('job_id')
        tag_id = request.POST.get('tag_id')
        
        try:
            job = get_object_or_404(Job, id=job_id, user=request.user)
            tag = get_object_or_404(Tag, id=tag_id, user=request.user)
            
            if tag in job.tags.all():
                job.tags.remove(tag)
                action = 'removed'
            else:
                job.tags.add(tag)
                action = 'added'
            
            return JsonResponse({
                'status': 'success',
                'action': action,
                'job_id': job_id,
                'tag_id': tag_id,
                'tag_name': tag.name
            })
        except (Job.DoesNotExist, Tag.DoesNotExist):
            return JsonResponse({
                'status': 'error',
                'message': '작업 또는 태그를 찾을 수 없습니다.'
            })
    
    return JsonResponse({'status': 'error', 'message': '잘못된 요청입니다.'})

@login_required
def job_progress_update(request):
    """작업 진행도를 실시간으로 확인하는 API"""
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        jobs_query = Job.objects.filter(user=request.user)
        
        # 진행 중인 작업들의 상태와 진행도 반환
        active_jobs = jobs_query.filter(status__in=['pending', 'processing', 'queued', 'running'])
        
        job_updates = []
        for job in active_jobs:
            job_updates.append({
                'id': job.id,
                'status': job.status,
                'progress': job.progress,
                'title': job.title or job.url[:50] + '...' if len(job.url) > 50 else job.url,
                'error_message': job.error_message
            })
        
        # 최근 완료된 작업들도 포함 (마지막 갱신 이후 완료된 것들)
        recently_completed = jobs_query.filter(
            status__in=['completed', 'done', 'failed', 'cancelled']
        ).order_by('-updated_at')[:5]
        
        completed_updates = []
        for job in recently_completed:
            completed_updates.append({
                'id': job.id,
                'status': job.status,
                'progress': job.progress,
                'title': job.title or job.url[:50] + '...' if len(job.url) > 50 else job.url,
                'error_message': job.error_message,
                'files': [{'id': f.id, 'filename': f.filename, 'file_size': f.file_size} for f in job.files.all()]
            })
        
        return JsonResponse({
            'active_jobs': job_updates,
            'completed_jobs': completed_updates,
            'timestamp': timezone.now().isoformat()
        })
    
    return JsonResponse({'error': 'Invalid request'}, status=400)
