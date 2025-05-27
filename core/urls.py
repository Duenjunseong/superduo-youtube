from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # path('', views.IndexView.as_view(), name='index'), # 기존 인덱스는 주석 처리 또는 다른 경로로 변경
    path('', views.DashboardView.as_view(), name='dashboard'), # 루트를 대시보드로 변경
    path('about/', views.about, name='about'),
    # 만약 IndexView를 다른 이름으로 계속 사용하고 싶다면:
    # path('old-index/', views.IndexView.as_view(), name='old_index'), 
] 