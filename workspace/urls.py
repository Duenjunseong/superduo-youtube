from django.urls import path
from .views import (
    WorkspaceListView, WorkspaceCreateView, WorkspaceDetailView, WorkspaceUpdateView,
    InviteUserView, InvitationResponseView, RemoveMemberView, ChangeRoleView,
    PublicWorkspaceListView, JoinWorkspaceView, CancelInvitationView, SwitchWorkspaceView,
    WorkspaceDeleteView
)

app_name = 'workspace'

urlpatterns = [
    # 워크스페이스 기본 관리
    path('', WorkspaceListView.as_view(), name='workspace_list'),
    path('create/', WorkspaceCreateView.as_view(), name='workspace_create'),
    path('<uuid:workspace_id>/', WorkspaceDetailView.as_view(), name='workspace_detail'),
    path('<uuid:workspace_id>/edit/', WorkspaceUpdateView.as_view(), name='workspace_edit'),
    path('<uuid:workspace_id>/delete/', WorkspaceDeleteView.as_view(), name='workspace_delete'),
    
    # 워크스페이스 전환
    path('switch/', SwitchWorkspaceView.as_view(), name='switch_workspace'),
    
    # 멤버 관리
    path('<uuid:workspace_id>/invite/', InviteUserView.as_view(), name='invite_user'),
    path('<uuid:workspace_id>/members/<uuid:membership_id>/remove/', RemoveMemberView.as_view(), name='remove_member'),
    path('<uuid:workspace_id>/members/<uuid:membership_id>/change-role/', ChangeRoleView.as_view(), name='change_role'),
    
    # 초대 관리
    path('invitations/<uuid:invitation_id>/respond/', InvitationResponseView.as_view(), name='invitation_response'),
    path('invitations/<uuid:invitation_id>/cancel/', CancelInvitationView.as_view(), name='cancel_invitation'),
    
    # 공개 워크스페이스
    path('public/', PublicWorkspaceListView.as_view(), name='public_workspaces'),
    path('<uuid:workspace_id>/join/', JoinWorkspaceView.as_view(), name='join_workspace'),
] 