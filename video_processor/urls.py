from django.urls import path
from .views import (
    TaskGroupListView, TaskGroupCreateView, TaskGroupDetailView,
    JobSubmitView, JobStatusView,
    UserJobListView, RetryJobView, DeleteJobView, GroupBatchStartView, StartJobView, ProcessingInfoView
)

app_name = 'video_processor'

urlpatterns = [
    # 그룹 관련 URL
    path('groups/', TaskGroupListView.as_view(), name='group_list'),
    path('groups/create/', TaskGroupCreateView.as_view(), name='group_create'),
    path('groups/<uuid:group_id>/', TaskGroupDetailView.as_view(), name='group_detail'),
    path('groups/<uuid:group_id>/add-job/', JobSubmitView.as_view(), name='job_submit_to_group'), # 특정 그룹에 Job 추가
    path('groups/<uuid:group_id>/batch-start/', GroupBatchStartView.as_view(), name='group_batch_start'), # 그룹 일괄 처리 시작

    # Job 관련 URL (그룹 미지정 또는 일반 제출)
    path('submit/', JobSubmitView.as_view(), name='job_submit'), # 기존 submit_download 대체
    path('status/<uuid:job_id>/', JobStatusView.as_view(), name='job_status'),
    path('job/<uuid:job_id>/retry/', RetryJobView.as_view(), name='job_retry'),
    path('job/<uuid:job_id>/delete/', DeleteJobView.as_view(), name='job_delete'),
    path('job/<uuid:job_id>/start/', StartJobView.as_view(), name='job_start'), # 개별 작업 시작
    path('ajax/jobs/', UserJobListView.as_view(), name='ajax_user_job_list'), # 사용자의 모든 작업 목록 (AJAX용)
    path('ajax/processing-info/', ProcessingInfoView.as_view(), name='ajax_processing_info'), # 처리 개요 정보 (AJAX용)
    # path('jobs/', UserJobListView.as_view(), name='user_job_list'), # 추후 사용자의 모든 작업 목록 뷰 추가 시
] 