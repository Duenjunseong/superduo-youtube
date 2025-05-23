from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    # 함수 기반 뷰 URL
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),
    path('profile/', views.profile, name='profile'),
    
    # 클래스 기반 뷰 URL
    path('login-class/', views.CustomLoginView.as_view(), name='login_class'),
    path('logout-class/', views.CustomLogoutView.as_view(), name='logout_class'),
    path('signup/', views.SignupView.as_view(), name='signup'),
    path('profile-class/', views.ProfileView.as_view(), name='profile_class'),
    path('profile/update/', views.ProfileUpdateView.as_view(), name='profile_update'),
] 