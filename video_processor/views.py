from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.generic import CreateView, ListView, DetailView
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin # 인증된 사용자만 접근
from django.conf import settings
from pathlib import Path
import re
from django.template.loader import render_to_string
from django.core.paginator import Paginator # Paginator 임포트
from django.db.models import Q # Q 객체 임포트
from taggit.models import Tag # Tag 모델 임포트
from django.db import transaction # 추가
from django.utils import timezone
from datetime import timedelta
import zipfile
import os
import tempfile
import logging

from .forms import TaskGroupForm, JobAndSegmentForm
from .models import ProcessingJob, VideoSegment, TaskGroup
from .tasks import download_and_process_video_task
from .utils import parse_time_range, time_to_seconds, get_youtube_video_title # 폼에서 입력받은 구간 문자열 파싱용

logger = logging.getLogger(__name__)

class TaskGroupListView(LoginRequiredMixin, ListView):
    model = TaskGroup
    template_name = 'video_processor/taskgroup_list.html'
    context_object_name = 'task_groups'

    def get_queryset(self):
        return TaskGroup.objects.filter(user=self.request.user, status='ACTIVE').order_by('-created_at')

    def get(self, request, *args, **kwargs):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('partial') == 'true':
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            # 부분 템플릿을 사용하여 HTML 문자열 생성
            html = render_to_string('video_processor/partials/task_group_list_partial.html', context, request=request)
            return HttpResponse(html) # HTML 조각을 직접 반환
        return super().get(request, *args, **kwargs)

class TaskGroupCreateView(LoginRequiredMixin, CreateView):
    model = TaskGroup
    form_class = TaskGroupForm
    template_name = 'video_processor/taskgroup_form.html'
    success_url = reverse_lazy('video_processor:group_list') # 성공 시 그룹 목록으로

    def form_valid(self, form):
        form.instance.user = self.request.user
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            self.object = form.save()
            return JsonResponse({'success': True, 'group_id': self.object.pk, 'name': self.object.name})
        else:
            messages.success(self.request, f"'{form.instance.name}' 그룹이 성공적으로 생성되었습니다.")
            return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors})
        return super().form_invalid(form)

class TaskGroupDetailView(LoginRequiredMixin, DetailView):
    model = TaskGroup
    template_name = 'video_processor/taskgroup_detail.html'
    context_object_name = 'group'
    pk_url_kwarg = 'group_id' # URL에서 group_id를 받음

    def get_queryset(self):
        return TaskGroup.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        group = self.object
        context['jobs'] = ProcessingJob.objects.filter(group=group).order_by('-created_at')
        # 그룹 내 대기 중인 작업 수 (auto_start=False인 PENDING 작업들)
        context['pending_jobs_count'] = ProcessingJob.objects.filter(
            group=group, 
            status='PENDING', 
            auto_start=False
        ).count()
        # 이 그룹에 새 Job을 추가하는 폼 (user와 group 인스턴스 전달)
        context['job_form'] = JobAndSegmentForm(user=self.request.user, initial={'group': group})
        return context

# Job 제출 뷰 (기존 SubmitDownloadView 대체 또는 확장)
class JobSubmitView(LoginRequiredMixin, View):
    template_name = 'video_processor/job_submit_form.html'
    MAX_SEGMENTS_PER_JOB = 100 # 작업 당 최대 세그먼트 수 제한

    def get(self, request, group_id=None):
        initial_data = {}
        current_group_object = None
        if group_id:
            current_group_object = get_object_or_404(TaskGroup, pk=group_id, user=request.user)
            initial_data['group'] = current_group_object
        
        form = JobAndSegmentForm(user=request.user, initial=initial_data)
        
        context = {
            'form': form, 
            'group_id': group_id,
            'current_group_object': current_group_object
        }
        return render(request, self.template_name, context)

    def post(self, request, group_id=None):
        form = JobAndSegmentForm(request.POST, user=request.user)
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        current_group_object = None
        if group_id:
            current_group_object = get_object_or_404(TaskGroup, pk=group_id, user=request.user)

        if form.is_valid():
            youtube_url = form.cleaned_data['youtube_url']
            segments_input = form.cleaned_data['segments_input']
            selected_group_from_form = form.cleaned_data.get('group')
            tags_input_str = form.cleaned_data.get('tags_input', '')
            auto_start = form.cleaned_data.get('auto_start', True)
            download_full_video = form.cleaned_data.get('download_full_video', False)
            full_video_prefix = form.cleaned_data.get('full_video_prefix', '')

            target_group = current_group_object or selected_group_from_form
            
            try:
                with transaction.atomic(): # 트랜잭션 시작
                    # YouTube 제목 가져오기
                    video_title = get_youtube_video_title(youtube_url)
                    
                    job = ProcessingJob.objects.create(
                        user=request.user, 
                        youtube_url=youtube_url, 
                        video_title=video_title,
                        group=target_group,
                        auto_start=auto_start
                    )
                    
                    if tags_input_str:
                        tag_names = [name.strip() for name in tags_input_str.split(',') if name.strip()]
                        if tag_names:
                            job.tags.add(*tag_names)
                    
                    if download_full_video:
                        # 전체 파일 다운로드: 더미 세그먼트 생성 (전체 영상을 나타냄)
                        VideoSegment.objects.create(
                            job=job,
                            start_time=0,  # 시작: 0초
                            end_time=-1,   # 끝: -1은 전체 영상을 의미하는 특별한 값
                            output_filename_prefix=full_video_prefix or 'full_video'
                        )
                        num_segments_created = 1
                    else:
                        # 기존 세그먼트 처리 로직
                        segment_lines = segments_input.strip().split('\n')
                        # 입력된 세그먼트 라인 수 자체에 대한 제한 (실제 유효 세그먼트 수는 아래에서 계산)
                        if len(segment_lines) > self.MAX_SEGMENTS_PER_JOB:
                            error_message = f"한 번에 최대 {self.MAX_SEGMENTS_PER_JOB}개의 구간 정보만 제출할 수 있습니다."
                            if is_ajax:
                                return JsonResponse({'success': False, 'message': error_message})
                            else:
                                messages.error(request, error_message)
                                context = {'form': form, 'group_id': group_id, 'current_group_object': current_group_object}
                                return render(request, self.template_name, context)

                        # 실제 유효한 세그먼트 정보가 있는지 확인 (모든 줄이 비어있거나 공백인지)
                        if not segment_lines or not any(line.strip() for line in segment_lines):
                            raise ValueError("구간 정보가 최소 한 개 이상 필요합니다.") 
                        
                        num_segments_created = 0
                        parse_errors = []
                        for line_number, line in enumerate(segment_lines, 1):
                            line = line.strip()
                            if not line: continue

                            parts = line.split(maxsplit=1)
                            time_range_str = parts[0]
                            output_id = parts[1] if len(parts) > 1 else None
                            try:
                                start_time_str_from_parse, end_time_str_from_parse = parse_time_range(time_range_str)
                                start_seconds_float = time_to_seconds(start_time_str_from_parse)
                                end_seconds_float = time_to_seconds(end_time_str_from_parse)
                                start_seconds_int = int(start_seconds_float)
                                end_seconds_int = int(end_seconds_float)

                                if start_seconds_int < 0 or end_seconds_int < 0:
                                    raise ValueError("시간 값은 음수가 될 수 없습니다.")
                                if end_seconds_int < start_seconds_int:
                                    raise ValueError("종료 시간은 시작 시간보다 빠를 수 없습니다.")

                                VideoSegment.objects.create(
                                    job=job, 
                                    start_time=start_seconds_int,
                                    end_time=end_seconds_int,
                                    output_filename_prefix=output_id
                                )
                                num_segments_created += 1
                            except ValueError as e:
                                parse_errors.append(f"'{line}': {e}")
                        
                        if parse_errors:
                            raise ValueError("잘못된 구간 정보 형식입니다: " + ", ".join(parse_errors))
                        
                        if num_segments_created == 0: # 유효한 세그먼트가 하나도 없는 경우
                            raise ValueError("유효한 구간 정보가 없어 작업을 시작할 수 없습니다.")

                    # auto_start가 True인 경우에만 Celery 작업 즉시 호출
                    if auto_start:
                        download_and_process_video_task.delay(job.job_id)
                        if download_full_video:
                            success_message = f'전체 영상 다운로드 작업이 성공적으로 제출되었습니다. Job ID: {job.job_id}'
                        else:
                            success_message = f'작업이 성공적으로 제출되었습니다. Job ID: {job.job_id}'
                    else:
                        if download_full_video:
                            success_message = f'전체 영상 다운로드 작업이 대기 상태로 추가되었습니다. Job ID: {job.job_id}'
                        else:
                            success_message = f'작업이 대기 상태로 추가되었습니다. Job ID: {job.job_id}'
                    
                    if is_ajax:
                        return JsonResponse({
                            'success': True, 
                            'message': success_message, 
                            'job_id': job.job_id,
                            'job_status_url': reverse('video_processor:job_status', kwargs={'job_id': job.job_id})
                        })
                    else:
                        messages.success(request, success_message)
                        return redirect(reverse('video_processor:job_status', kwargs={'job_id': job.job_id}))

            except ValueError as e: # 직접 발생시킨 ValueError 또는 하위 함수에서 발생한 ValueError
                # 트랜잭션에 의해 job 및 관련 segment 생성은 롤백됨
                error_message = str(e)
                if is_ajax:
                    return JsonResponse({'success': False, 'message': error_message})
                else:
                    messages.error(request, error_message)
                    context = {'form': form, 'group_id': group_id, 'current_group_object': current_group_object}
                    return render(request, self.template_name, context)
            # 예측 못한 다른 예외는 Django 기본 오류 처리 또는 별도 미들웨어에서 처리

        else: # form is not valid
            if is_ajax:
                return JsonResponse({'success': False, 'errors': form.errors})
            else:
                context = {
                    'form': form, 
                    'group_id': group_id, 
                    'current_group_object': current_group_object
                }
                return render(request, self.template_name, context)

class JobStatusView(LoginRequiredMixin, View):
    template_name = 'video_processor/job_status.html'

    def get(self, request, job_id):
        try:
            # UUID 문자열로 직접 조회하여 쿼리 최적화
            job = ProcessingJob.objects.get(job_id=job_id, user=request.user)
        except ProcessingJob.DoesNotExist:
            messages.error(request, "해당 작업을 찾을 수 없습니다.")
            return redirect(reverse('core:dashboard'))
        
        segments = job.segments.all().order_by('created_at')
        media_url = settings.MEDIA_URL if settings.MEDIA_URL.endswith('/') else settings.MEDIA_URL + '/'
        return render(request, self.template_name, {'job': job, 'segments': segments, 'media_url': media_url})

class UserJobListView(LoginRequiredMixin, ListView):
    model = ProcessingJob
    context_object_name = 'jobs'
    paginate_by = 10
    valid_sort_fields = ['created_at', '-created_at', 'status', '-status', 'youtube_url', '-youtube_url']

    def get_queryset(self):
        queryset = ProcessingJob.objects.filter(user=self.request.user)
        
        # 최근 작업 목록 요청인지 확인
        is_recent_request = self.request.GET.get('recent') == 'true'
        if is_recent_request:
            limit = int(self.request.GET.get('limit', 10)) # 기본 10개
            return queryset.order_by('-created_at')[:limit]

        # 기존 필터링 및 정렬 로직 (최근 작업 요청이 아닐 때만 적용)
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(youtube_url__icontains=search_query) |
                Q(group__name__icontains=search_query) |
                Q(tags__name__icontains=search_query)
            ).distinct()
            
        tag_filter = self.request.GET.get('tag')
        if tag_filter:
            queryset = queryset.filter(tags__name__in=[tag_filter])
            
        sort_by = self.request.GET.get('sort_by', '-created_at')
        if sort_by not in self.valid_sort_fields:
            sort_by = '-created_at'
        
        queryset = queryset.order_by(sort_by)
        if 'status' in sort_by: 
            queryset = queryset.order_by(sort_by, '-created_at')
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        is_recent_request = self.request.GET.get('recent') == 'true'
        
        if is_recent_request:
            context.pop(self.context_object_name, []) # jobs를 recent_jobs로 변경
        else:
            # 일반 목록 요청 시 필요한 컨텍스트
            context['job_status_choices'] = ProcessingJob.STATUS_CHOICES
            context['current_search_query'] = self.request.GET.get('search', '')
            context['current_status_filter'] = self.request.GET.get('status', '')
            context['current_sort_by'] = self.request.GET.get('sort_by', '-created_at')
            context['current_tag_filter'] = self.request.GET.get('tag', '')
            user_tags = Tag.objects.filter(processingjob__user=self.request.user).distinct().order_by('name')
            context['available_tags'] = user_tags
        return context

    def get(self, request, *args, **kwargs):
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'AJAX request required.'}, status=400)

        self.object_list = self.get_queryset()
        context = self.get_context_data()
        
        is_recent_request = request.GET.get('recent') == 'true'
        
        if is_recent_request:
            # 최근 작업 목록 요청 시, 다른 partial 템플릿 사용 및 HTML 직접 반환
            html = render_to_string('video_processor/partials/recent_job_list_partial.html', context, request=request)
            return HttpResponse(html)
        else:
            # 기존 전체 작업 목록 로직 (JSON 응답)
            page_obj = context.get('page_obj')
            html = render_to_string('video_processor/partials/job_list_partial.html', context, request=request)
            total_jobs_for_current_filter = page_obj.paginator.count if page_obj else self.object_list.count()

            return JsonResponse({
                'success': True, 
                'html': html,
                'has_next': page_obj.has_next() if page_obj else False,
                'next_page_number': page_obj.next_page_number() if page_obj and page_obj.has_next() else None,
                'current_page': page_obj.number if page_obj else 1,
                'total_pages': page_obj.paginator.num_pages if page_obj else 1,
                'total_jobs': total_jobs_for_current_filter
            })

class RetryJobView(LoginRequiredMixin, View):
    def post(self, request, job_id):
        try:
            # UUID 문자열로 직접 조회하여 쿼리 최적화
            job = ProcessingJob.objects.get(job_id=job_id, user=request.user)
        except ProcessingJob.DoesNotExist:
            messages.error(request, "해당 작업을 찾을 수 없습니다.")
            return redirect(reverse('core:dashboard'))
        
        if job.status == 'FAILED' or job.status == 'PENDING': # 실패했거나, 펜딩 상태에서 멈춘 경우도 재시도 가능하게 (선택적)
            # 모든 세그먼트 상태를 PENDING으로, 결과 파일 경로 초기화
            job.segments.update(status='PENDING', processed_file_path=None)
            
            job.status = 'PENDING' # Job 상태도 변경
            job.downloaded_video_path = None # 원본 다운로드 경로도 초기화 (다시 다운로드 받도록)
            job.save()
            
            download_and_process_video_task.delay(job.job_id)
            messages.success(request, f"작업(ID: {job.job_id}) 재시도를 요청했습니다.")
        else:
            messages.warning(request, f"작업(ID: {job.job_id})은 현재 재시도할 수 있는 상태가 아닙니다.")
        
        # 현재 페이지로 리디렉션하거나, 대시보드로 리디렉션 할 수 있습니다.
        # 여기서는 작업 상태 페이지로 리디렉션합니다. AJAX 요청이라면 다른 응답이 필요할 수 있습니다.
        referer_url = request.META.get('HTTP_REFERER')
        if referer_url:
             # 대시보드에서 AJAX로 최근 작업 목록을 업데이트하는 경우,
             # 이 리디렉션은 전체 페이지를 새로고침하게 됩니다.
             # dashboard.html의 최근 작업 목록은 AJAX로 업데이트되므로,
             # 이 뷰는 주로 Job 상세 페이지나 전체 목록 페이지에서 사용될 것으로 가정합니다.
             # 만약 대시보드 최근 목록에서 직접 호출되고 AJAX 업데이트가 필요하다면 JsonResponse를 반환해야합니다.
            return redirect(referer_url) 
        return redirect(reverse('video_processor:job_status', kwargs={'job_id': job.job_id}))

class DeleteJobView(LoginRequiredMixin, View):
    def post(self, request, job_id):
        try:
            # UUID 문자열로 직접 조회하여 쿼리 최적화
            job = ProcessingJob.objects.get(job_id=job_id, user=request.user)
        except ProcessingJob.DoesNotExist:
            messages.error(request, "해당 작업을 찾을 수 없습니다.")
            return redirect(reverse('core:dashboard'))
        
        job_id_str = str(job.job_id) # 삭제 메시지에 사용하기 위해 저장

        # TODO: 파일 시스템에서 관련 파일(원본, 세그먼트) 삭제 로직 추가 (선택 사항)
        # 예:
        # if job.downloaded_video_path:
        #     try:
        #         (Path(settings.MEDIA_ROOT) / job.downloaded_video_path).unlink(missing_ok=True)
        #     except Exception as e:
        #         logger.error(f"원본 파일 삭제 실패 ({job.downloaded_video_path}): {e}")
        # for segment in job.segments.all():
        #     if segment.processed_file_path:
        #         try:
        #             (Path(settings.MEDIA_ROOT) / segment.processed_file_path).unlink(missing_ok=True)
        #         except Exception as e:
        #             logger.error(f"세그먼트 파일 삭제 실패 ({segment.processed_file_path}): {e}")
        #
        # # 관련된 디렉토리도 삭제 (주의: 다른 파일이 없는지 확인 필요)
        # original_videos_dir = Path(settings.MEDIA_ROOT) / 'original_videos' / job_id_str
        # processed_segments_dir = Path(settings.MEDIA_ROOT) / 'processed_segments' / job_id_str
        # try:
        #     if original_videos_dir.exists():
        #          shutil.rmtree(original_videos_dir) # shutil import 필요
        #     if processed_segments_dir.exists():
        #          shutil.rmtree(processed_segments_dir)
        # except Exception as e:
        #     logger.error(f"작업 디렉토리 삭제 실패 (Job ID: {job_id_str}): {e}")

        # 관련 객체들을 먼저 삭제하여 복잡한 CASCADE 쿼리 방지
        try:
            # 먼저 연관된 세그먼트들을 삭제
            job.segments.all().delete()
            # 태그 연결 해제
            job.tags.clear()
            # 마지막으로 작업 삭제
            job.delete()
            messages.success(request, f"작업(ID: {job_id_str})이 삭제되었습니다.")
        except Exception as e:
            messages.error(request, f"작업 삭제 중 오류가 발생했습니다: {str(e)}")
        
        # 대시보드로 리디렉션 또는 작업 목록 페이지로 리디렉션
        # 여기서는 대시보드 내 최근 작업 목록에서 호출된다고 가정하고, 대시보드로 리디렉션합니다.
        # 실제로는 AJAX 응답 후 JS에서 해당 항목을 DOM에서 제거하는 것이 더 사용자 친화적입니다.
        # 이 뷰가 AJAX 전용이 아니라면, 일반적인 리디렉션.
        # dashboard.html의 최근 작업 목록이 AJAX로 업데이트되므로, 이 뷰가 직접 호출될 경우
        # 대시보드 URL로 리디렉션합니다.
        return redirect(reverse('core:dashboard')) # 또는 'video_processor:group_list' 등 적절한 곳으로

class GroupBatchStartView(LoginRequiredMixin, View):
    """그룹 내 대기 중인(PENDING) 작업들을 일괄 처리 시작"""
    def post(self, request, group_id):
        group = get_object_or_404(TaskGroup, pk=group_id, user=request.user)
        
        # 해당 그룹 내 PENDING 상태인 작업들 가져오기
        pending_jobs = ProcessingJob.objects.filter(
            group=group, 
            status='PENDING', 
            auto_start=False  # 대기 상태로 생성된 작업들만
        )
        
        if not pending_jobs.exists():
            messages.warning(request, f"'{group.name}' 그룹에 처리 대기 중인 작업이 없습니다.")
        else:
            # 모든 대기 중인 작업을 Celery로 처리 시작
            started_count = 0
            for job in pending_jobs:
                try:
                    download_and_process_video_task.delay(job.job_id)
                    started_count += 1
                except Exception as e:
                    # 개별 작업 시작 실패 시 로그 기록 (import logging 필요)
                    logger.error(f"그룹 일괄 처리 시작 실패 (Job ID: {job.job_id}): {e}")
            
            if started_count > 0:
                messages.success(request, f"'{group.name}' 그룹의 {started_count}개 작업이 처리 시작되었습니다.")
            else:
                messages.error(request, f"'{group.name}' 그룹의 작업들을 시작하는 데 실패했습니다.")
        
        # 그룹 상세 페이지로 리디렉션
        return redirect(reverse('video_processor:group_detail', kwargs={'group_id': group_id}))

class StartJobView(LoginRequiredMixin, View):
    """개별 작업을 시작하는 뷰 (대기 중인 작업에 대해)"""
    def post(self, request, job_id):
        try:
            # UUID 문자열로 직접 조회하여 쿼리 최적화
            job = ProcessingJob.objects.get(job_id=job_id, user=request.user)
        except ProcessingJob.DoesNotExist:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': '해당 작업을 찾을 수 없습니다.'})
            messages.error(request, "해당 작업을 찾을 수 없습니다.")
            return redirect(reverse('core:dashboard'))
        
        # 작업이 PENDING 상태이고 auto_start=False인 경우에만 시작 가능
        if job.status == 'PENDING' and not job.auto_start:
            try:
                download_and_process_video_task.delay(job.job_id)
                success_message = f"작업(ID: {job.job_id})이 시작되었습니다."
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'message': success_message})
                else:
                    messages.success(request, success_message)
            except Exception as e:
                error_message = f"작업 시작 중 오류가 발생했습니다: {str(e)}"
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'message': error_message})
                else:
                    messages.error(request, error_message)
        else:
            error_message = f"작업(ID: {job.job_id})은 현재 시작할 수 있는 상태가 아닙니다."
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': error_message})
            else:
                messages.warning(request, error_message)
        
        # AJAX 요청이 아닌 경우 리디렉션
        referer_url = request.META.get('HTTP_REFERER')
        if referer_url:
            return redirect(referer_url)
        return redirect(reverse('core:dashboard'))

# (선택 사항) 사용자의 모든 Job 목록을 보여주는 뷰
# class UserJobListView(View): ...

class ProcessingInfoView(LoginRequiredMixin, View):
    """사용자의 작업 처리 개요 정보를 AJAX로 반환하는 뷰"""
    def get(self, request):
        user = request.user
        
        # 현재 처리 중/대기 중인 작업 수
        processing_jobs_count = ProcessingJob.objects.filter(
            user=user,
            status__in=['PROCESSING', 'DOWNLOADING', 'PENDING']
        ).count()
        
        # 최근 24시간 내 완료된 작업 수
        twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
        recent_completed_jobs_count = ProcessingJob.objects.filter(
            user=user,
            status='COMPLETED',
            updated_at__gte=twenty_four_hours_ago
        ).count()
        
        # 추가 정보: 실패한 작업 수
        failed_jobs_count = ProcessingJob.objects.filter(
            user=user,
            status='FAILED'
        ).count()
        
        # 전체 작업 수
        total_jobs_count = ProcessingJob.objects.filter(user=user).count()
        
        return JsonResponse({
            'success': True,
            'processing_jobs_count': processing_jobs_count,
            'recent_completed_jobs_count': recent_completed_jobs_count,
            'failed_jobs_count': failed_jobs_count,
            'total_jobs_count': total_jobs_count,
            'timestamp': timezone.now().isoformat()
        })

class DownloadJobZipView(LoginRequiredMixin, View):
    """개별 작업의 모든 완료된 세그먼트를 압축하여 다운로드하는 뷰"""
    def get(self, request, job_id):
        try:
            job = ProcessingJob.objects.get(job_id=job_id, user=request.user)
        except ProcessingJob.DoesNotExist:
            messages.error(request, "해당 작업을 찾을 수 없습니다.")
            return redirect(reverse('core:dashboard'))
        
        # 완료된 세그먼트들만 가져오기
        completed_segments = job.segments.filter(
            status='COMPLETED',
            processed_file_path__isnull=False
        ).exclude(processed_file_path='')
        
        if not completed_segments.exists():
            messages.warning(request, "다운로드할 완료된 세그먼트가 없습니다.")
            return redirect(reverse('video_processor:job_status', kwargs={'job_id': job_id}))
        
        try:
            # 임시 ZIP 파일 생성
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_zip:
                with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for segment in completed_segments:
                        file_path = Path(settings.MEDIA_ROOT) / segment.processed_file_path
                        if file_path.exists():
                            # ZIP 내부 파일명 생성
                            original_filename = file_path.name
                            if segment.output_filename_prefix:
                                zip_filename = f"{segment.output_filename_prefix}_{original_filename}"
                            else:
                                zip_filename = f"segment_{segment.segment_id}_{original_filename}"
                            
                            zipf.write(file_path, zip_filename)
                        else:
                            logger.warning(f"세그먼트 파일을 찾을 수 없습니다: {segment.processed_file_path}")
                
                # ZIP 파일 다운로드 응답 생성
                temp_zip.seek(0)
                with open(temp_zip.name, 'rb') as zip_file:
                    response = HttpResponse(zip_file.read(), content_type='application/zip')
                    
                    # 파일명 생성 (비디오 제목 또는 Job ID 사용)
                    if job.video_title and job.video_title != '제목 미탐지':
                        safe_title = re.sub(r'[^\w\s-]', '', job.video_title).strip()
                        safe_title = re.sub(r'[-\s]+', '-', safe_title)
                        filename = f"{safe_title}_segments.zip"
                    else:
                        filename = f"job_{job.job_id}_segments.zip"
                    
                    response['Content-Disposition'] = f'attachment; filename="{filename}"'
                    
                # 임시 파일 정리
                os.unlink(temp_zip.name)
                return response
                
        except Exception as e:
            logger.error(f"작업 압축 다운로드 실패 (Job ID: {job_id}): {e}")
            messages.error(request, "압축 파일 생성 중 오류가 발생했습니다.")
            return redirect(reverse('video_processor:job_status', kwargs={'job_id': job_id}))

class DownloadGroupZipView(LoginRequiredMixin, View):
    """그룹 내 모든 작업의 완료된 세그먼트를 폴더별로 구분하여 압축 다운로드하는 뷰"""
    def get(self, request, group_id):
        try:
            group = TaskGroup.objects.get(group_id=group_id, user=request.user)
        except TaskGroup.DoesNotExist:
            messages.error(request, "해당 그룹을 찾을 수 없습니다.")
            return redirect(reverse('core:dashboard'))
        
        # 그룹 내 모든 작업의 완료된 세그먼트들 가져오기
        completed_segments = VideoSegment.objects.filter(
            job__group=group,
            job__user=request.user,
            status='COMPLETED',
            processed_file_path__isnull=False
        ).exclude(processed_file_path='').select_related('job')
        
        if not completed_segments.exists():
            messages.warning(request, "다운로드할 완료된 세그먼트가 없습니다.")
            return redirect(reverse('video_processor:group_detail', kwargs={'group_id': group_id}))
        
        try:
            # 임시 ZIP 파일 생성
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_zip:
                with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for segment in completed_segments:
                        file_path = Path(settings.MEDIA_ROOT) / segment.processed_file_path
                        if file_path.exists():
                            # 작업별 폴더 구조 생성
                            job = segment.job
                            if job.video_title and job.video_title != '제목 미탐지':
                                safe_job_title = re.sub(r'[^\w\s-]', '', job.video_title).strip()
                                safe_job_title = re.sub(r'[-\s]+', '-', safe_job_title)
                                job_folder = f"{safe_job_title}_{str(job.job_id)[:8]}"
                            else:
                                job_folder = f"job_{str(job.job_id)[:8]}"
                            
                            # ZIP 내부 파일명 생성 (폴더/파일명)
                            original_filename = file_path.name
                            if segment.output_filename_prefix:
                                zip_filename = f"{job_folder}/{segment.output_filename_prefix}_{original_filename}"
                            else:
                                zip_filename = f"{job_folder}/segment_{str(segment.segment_id)[:8]}_{original_filename}"
                            
                            zipf.write(file_path, zip_filename)
                        else:
                            logger.warning(f"세그먼트 파일을 찾을 수 없습니다: {segment.processed_file_path}")
                
                # ZIP 파일 다운로드 응답 생성
                temp_zip.seek(0)
                with open(temp_zip.name, 'rb') as zip_file:
                    response = HttpResponse(zip_file.read(), content_type='application/zip')
                    
                    # 파일명 생성 (그룹명 사용)
                    safe_group_name = re.sub(r'[^\w\s-]', '', group.name).strip()
                    safe_group_name = re.sub(r'[-\s]+', '-', safe_group_name)
                    filename = f"{safe_group_name}_all_segments.zip"
                    
                    response['Content-Disposition'] = f'attachment; filename="{filename}"'
                    
                # 임시 파일 정리
                os.unlink(temp_zip.name)
                return response
                
        except Exception as e:
            logger.error(f"그룹 압축 다운로드 실패 (Group ID: {group_id}): {e}")
            messages.error(request, "압축 파일 생성 중 오류가 발생했습니다.")
            return redirect(reverse('video_processor:group_detail', kwargs={'group_id': group_id}))
