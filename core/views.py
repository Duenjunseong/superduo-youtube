from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin


class IndexView(TemplateView):
    """메인 페이지 뷰"""
    template_name = 'core/index.html'
    
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('downloads:links')
        return super().get(request, *args, **kwargs)


class DashboardView(LoginRequiredMixin, TemplateView):
    """대시보드 뷰"""
    template_name = 'core/dashboard.html'

def about(request):
    return render(request, 'core/about.html')
