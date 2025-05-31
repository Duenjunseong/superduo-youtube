from django.shortcuts import render, redirect
from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from video_processor.forms import JobAndSegmentForm, TaskGroupForm
from video_processor.models import TaskGroup, ProcessingJob
from django.urls import reverse_lazy
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator


class IndexView(TemplateView):
    """메인 페이지 뷰"""
    # template_name = 'core/index.html' # 인증 안된 사용자는 로그인 페이지로 유도
    
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(reverse_lazy('core:dashboard'))
        return redirect(reverse_lazy('users:login')) # 인증 안된 사용자는 로그인 페이지로


@method_decorator(ensure_csrf_cookie, name='get')
@method_decorator(login_required, name='dispatch')
class DashboardView(LoginRequiredMixin, View):
    """워크스페이스 인식 대시보드 뷰"""
    template_name = 'core/dashboard.html'

    def get(self, request, *args, **kwargs):
        user = request.user
        job_form = JobAndSegmentForm(user=user)
        task_group_form = TaskGroupForm(user=user)
        
        # 현재 워크스페이스 모드에 따라 데이터 필터링
        if user.is_in_workspace_mode():
            # 워크스페이스 모드: 현재 워크스페이스의 데이터만
            task_groups = TaskGroup.objects.filter(
                workspace=user.current_workspace,
                status='ACTIVE'
            ).order_by('-created_at')[:5]  # 최근 5개만
            
            recent_jobs = ProcessingJob.objects.filter(
                Q(group__workspace=user.current_workspace) |
                Q(user=user, group__workspace=user.current_workspace) |
                Q(user=user, group__isnull=True, workspace=user.current_workspace)
            ).order_by('-created_at')[:5]
            
            workspace_context = {
                'current_workspace': user.current_workspace,
                'is_workspace_mode': True,
                'workspace_name': user.current_workspace.name,
                'can_create_group': user.current_workspace.has_permission(user, 'edit'),
            }
        else:
            # 개인 모드: 워크스페이스 없는 개인 데이터만
            task_groups = TaskGroup.objects.filter(
                user=user,
                workspace__isnull=True,
                status='ACTIVE'
            ).order_by('-created_at')[:5]
            
            recent_jobs = ProcessingJob.objects.filter(
                user=user,
                workspace__isnull=True
            ).order_by('-created_at')[:5]
            
            workspace_context = {
                'current_workspace': None,
                'is_workspace_mode': False,
                'can_create_group': True,  # 개인 모드에서는 항상 그룹 생성 가능
            }

        context = {
            'form': job_form,
            'task_group_form': task_group_form,
            'task_groups': task_groups,
            'recent_jobs': recent_jobs,
            **workspace_context,
        }
        return render(request, self.template_name, context)

def about(request):
    return render(request, 'core/about.html')
