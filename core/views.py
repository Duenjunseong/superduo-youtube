from django.shortcuts import render, redirect
from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from video_processor.forms import JobAndSegmentForm, TaskGroupForm
from video_processor.models import TaskGroup, ProcessingJob
from django.urls import reverse_lazy


class IndexView(TemplateView):
    """메인 페이지 뷰"""
    # template_name = 'core/index.html' # 인증 안된 사용자는 로그인 페이지로 유도
    
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(reverse_lazy('core:dashboard'))
        return redirect(reverse_lazy('users:login')) # 인증 안된 사용자는 로그인 페이지로


class DashboardView(LoginRequiredMixin, View):
    """대시보드 뷰"""
    template_name = 'core/dashboard.html'

    def get(self, request, *args, **kwargs):
        job_form = JobAndSegmentForm(user=request.user)
        task_group_form = TaskGroupForm()
        task_groups = TaskGroup.objects.filter(user=request.user, status='ACTIVE')
        recent_jobs = request.user.processing_jobs.all().order_by('-created_at')[:5]

        context = {
            'form': job_form,
            'task_group_form': task_group_form,
            'task_groups': task_groups,
            'recent_jobs': recent_jobs,
        }
        return render(request, self.template_name, context)

def about(request):
    return render(request, 'core/about.html')
