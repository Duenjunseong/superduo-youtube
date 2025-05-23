from django.urls import path
from . import views

app_name = 'downloads'

urlpatterns = [
    path('', views.download_form, name='download_form'),
    path('submit/', views.submit_url, name='submit_url'),
    path('status/<str:job_id>/', views.job_status, name='job_status'),
    path('list/', views.download_list, name='download_list'),
    path('file/<int:file_id>/', views.download_file, name='download_file'),
    path('cancel/<int:job_id>/', views.cancel_job, name='cancel_job'),
    path('links/', views.LinksView.as_view(), name='links'),
    path('jobs/', views.JobsListView.as_view(), name='jobs_list'),
    path('job/memo/', views.save_job_memo, name='job_memo'),
    path('delete/<int:job_id>/', views.delete_job, name='delete_job'),
    path('job_counts/', views.job_counts, name='job_counts'),
    path('job_list/', views.job_list_ajax, name='job_list_ajax'),
    path('job_progress/', views.job_progress_update, name='job_progress_update'),
    
    # 태그 관련 URL
    path('create_tag/', views.create_tag, name='create_tag'),
    path('tag/delete/<int:tag_id>/', views.delete_tag, name='delete_tag'),
    path('job/tags/', views.update_job_tags, name='update_job_tags'),
    path('tag/update/<int:tag_id>/', views.tag_update, name='tag_update'),
    path('tag/update/<int:tag_id>/', views.update_tag, name='update_tag'),
    path('job/tag/toggle/', views.toggle_job_tag, name='toggle_job_tag'),
] 