from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.generic import CreateView, ListView, DetailView, UpdateView, DeleteView
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.core.paginator import Paginator
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator

from .models import Workspace, WorkspaceMembership, Invitation
from .forms import WorkspaceForm, InvitationForm, WorkspaceMembershipForm, WorkspaceJoinForm

User = get_user_model()

class WorkspaceContextMixin:
    """워크스페이스 컨텍스트를 제공하는 믹스인"""
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        if user.is_authenticated:
            context['current_workspace'] = user.current_workspace
            context['accessible_workspaces'] = user.get_accessible_workspaces()
            context['is_workspace_mode'] = user.is_in_workspace_mode()
            context['is_personal_mode'] = user.is_in_personal_mode()
        return context

@method_decorator(ensure_csrf_cookie, name='dispatch')
class SwitchWorkspaceView(LoginRequiredMixin, View):
    """워크스페이스 전환 뷰"""
    
    def post(self, request):
        workspace_id = request.POST.get('workspace_id', '').strip()
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        user = request.user
        
        try:
            # 개인 모드로 전환
            if not workspace_id:
                success = user.switch_to_personal_mode()
                message = '개인 모드로 전환했습니다.' if success else '개인 모드 전환에 실패했습니다.'
                
                if is_ajax:
                    return JsonResponse({
                        'success': success,
                        'message': message,
                        'workspace_id': None,
                        'workspace_name': '개인 모드'
                    })
                else:
                    if success:
                        messages.success(request, message)
                    else:
                        messages.error(request, message)
                    return redirect('core:dashboard')
            
            # 특정 워크스페이스로 전환
            try:
                workspace = Workspace.objects.get(workspace_id=workspace_id, status='ACTIVE')
            except Workspace.DoesNotExist:
                message = '존재하지 않는 워크스페이스입니다.'
                if is_ajax:
                    return JsonResponse({'success': False, 'message': message})
                else:
                    messages.error(request, message)
                    return redirect('core:dashboard')
            
            # 접근 권한 확인
            if not user.can_access_workspace(workspace):
                message = f'"{workspace.name}" 워크스페이스에 접근 권한이 없습니다.'
                if is_ajax:
                    return JsonResponse({'success': False, 'message': message})
                else:
                    messages.error(request, message)
                    return redirect('core:dashboard')
            
            # 워크스페이스 전환 수행
            success = user.switch_to_workspace(workspace)
            if success:
                message = f'"{workspace.name}" 워크스페이스로 전환했습니다.'
                if is_ajax:
                    return JsonResponse({
                        'success': True,
                        'message': message,
                        'workspace_id': str(workspace.workspace_id),
                        'workspace_name': workspace.name
                    })
                else:
                    messages.success(request, message)
                    return redirect('core:dashboard')
            else:
                message = f'"{workspace.name}" 워크스페이스 전환에 실패했습니다.'
                if is_ajax:
                    return JsonResponse({'success': False, 'message': message})
                else:
                    messages.error(request, message)
                    return redirect('core:dashboard')
                    
        except Exception as e:
            message = f'워크스페이스 전환 중 오류가 발생했습니다: {str(e)}'
            if is_ajax:
                return JsonResponse({'success': False, 'message': message})
            else:
                messages.error(request, message)
                return redirect('core:dashboard')

class WorkspaceListView(LoginRequiredMixin, WorkspaceContextMixin, ListView):
    """사용자가 참여한 워크스페이스 목록"""
    model = Workspace
    template_name = 'workspace/workspace_list.html'
    context_object_name = 'workspaces'
    paginate_by = 10

    def get_queryset(self):
        # 사용자가 소유하거나 멤버인 워크스페이스들
        user_workspaces = Workspace.objects.filter(
            Q(owner=self.request.user) |
            Q(memberships__user=self.request.user, memberships__status='ACTIVE'),
            status='ACTIVE'
        ).distinct().order_by('-created_at')
        
        return user_workspaces

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 사용자가 받은 초대들
        context['pending_invitations'] = Invitation.objects.filter(
            invitee_email=self.request.user.email,
            status='PENDING'
        ).order_by('-created_at')
        return context

class WorkspaceCreateView(LoginRequiredMixin, WorkspaceContextMixin, CreateView):
    """워크스페이스 생성"""
    model = Workspace
    form_class = WorkspaceForm
    template_name = 'workspace/workspace_form.html'
    success_url = reverse_lazy('workspace:workspace_list')

    def form_valid(self, form):
        with transaction.atomic():
            form.instance.owner = self.request.user
            response = super().form_valid(form)
            
            # 소유자 멤버십 자동 생성
            WorkspaceMembership.objects.create(
                workspace=self.object,
                user=self.request.user,
                role='OWNER'
            )
            
            messages.success(self.request, f"'{self.object.name}' 워크스페이스가 성공적으로 생성되었습니다.")
            return response

class WorkspaceDetailView(LoginRequiredMixin, WorkspaceContextMixin, DetailView):
    """워크스페이스 상세 보기"""
    model = Workspace
    template_name = 'workspace/workspace_detail.html'
    context_object_name = 'workspace'
    pk_url_kwarg = 'workspace_id'

    def get_queryset(self):
        # 사용자가 접근할 수 있는 워크스페이스만
        return Workspace.objects.filter(
            Q(owner=self.request.user) |
            Q(memberships__user=self.request.user, memberships__status='ACTIVE'),
            status='ACTIVE'
        ).distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        workspace = self.object
        user = self.request.user
        
        # 사용자 역할 정보
        context['user_role'] = workspace.get_user_role(user)
        context['can_edit'] = workspace.has_permission(user, 'edit')
        context['can_invite'] = workspace.has_permission(user, 'invite')
        context['can_manage'] = workspace.has_permission(user, 'manage_roles')
        
        # 멤버 목록
        context['members'] = workspace.memberships.filter(status='ACTIVE').select_related('user')
        
        # 대기 중인 초대 목록
        context['pending_invitations'] = workspace.invitations.filter(status='PENDING').order_by('-created_at')
        
        # 초대 폼
        if context['can_invite']:
            context['invitation_form'] = InvitationForm(workspace=workspace)
        
        # 워크스페이스 내 작업 그룹들
        context['task_groups'] = workspace.task_groups.filter(status='ACTIVE').order_by('-created_at')
        
        # 워크스페이스 내 최근 작업들
        context['recent_jobs'] = workspace.processing_jobs.order_by('-created_at')[:10]
        
        return context

class WorkspaceUpdateView(LoginRequiredMixin, WorkspaceContextMixin, UpdateView):
    """워크스페이스 수정"""
    model = Workspace
    form_class = WorkspaceForm
    template_name = 'workspace/workspace_form.html'
    pk_url_kwarg = 'workspace_id'

    def get_queryset(self):
        # 편집 권한이 있는 워크스페이스만
        return Workspace.objects.filter(
            Q(owner=self.request.user) |
            Q(memberships__user=self.request.user, memberships__role__in=['ADMIN'], memberships__status='ACTIVE')
        ).distinct()

    def get_success_url(self):
        return reverse('workspace:workspace_detail', kwargs={'workspace_id': self.object.workspace_id})

    def form_valid(self, form):
        messages.success(self.request, f"'{self.object.name}' 워크스페이스가 수정되었습니다.")
        return super().form_valid(form)

class InviteUserView(LoginRequiredMixin, View):
    """사용자 초대"""
    
    def post(self, request, workspace_id):
        workspace = get_object_or_404(Workspace, workspace_id=workspace_id)
        
        # 초대 권한 확인
        if not workspace.has_permission(request.user, 'invite'):
            messages.error(request, "초대 권한이 없습니다.")
            return redirect('workspace:workspace_detail', workspace_id=workspace_id)
        
        form = InvitationForm(request.POST, workspace=workspace)
        if form.is_valid():
            invitation = form.save(commit=False)
            invitation.workspace = workspace
            invitation.inviter = request.user
            invitation.save()
            
            user_name = form.user_to_invite.get_full_name() or form.user_to_invite.username
            messages.success(request, f"{user_name}님({invitation.invitee_email})에게 초대가 발송되었습니다.")
        else:
            for field, errors in form.errors.items():
                field_name = form.fields[field].label if field in form.fields else field
                for error in errors:
                    messages.error(request, f"{field_name}: {error}")
        
        return redirect('workspace:workspace_detail', workspace_id=workspace_id)

class InvitationResponseView(LoginRequiredMixin, View):
    """초대 응답 (수락/거절)"""
    
    def post(self, request, invitation_id):
        invitation = get_object_or_404(Invitation, invitation_id=invitation_id)
        action = request.POST.get('action')
        
        # 초대받은 사용자인지 확인
        if invitation.invitee_email != request.user.email:
            messages.error(request, "해당 초대에 응답할 권한이 없습니다.")
            return redirect('workspace:workspace_list')
        
        try:
            if action == 'accept':
                invitation.accept(request.user)
                messages.success(request, f"'{invitation.workspace.name}' 워크스페이스에 참여했습니다.")
                return redirect('workspace:workspace_detail', workspace_id=invitation.workspace.workspace_id)
            elif action == 'decline':
                invitation.decline(request.user)
                messages.info(request, "초대를 거절했습니다.")
            else:
                messages.error(request, "잘못된 요청입니다.")
        except ValueError as e:
            messages.error(request, str(e))
        
        return redirect('workspace:workspace_list')

class RemoveMemberView(LoginRequiredMixin, View):
    """멤버 제거"""
    
    def post(self, request, workspace_id, membership_id):
        workspace = get_object_or_404(Workspace, workspace_id=workspace_id)
        membership = get_object_or_404(WorkspaceMembership, membership_id=membership_id, workspace=workspace)
        
        # 제거 권한 확인
        if not workspace.has_permission(request.user, 'remove_member'):
            messages.error(request, "멤버 제거 권한이 없습니다.")
            return redirect('workspace:workspace_detail', workspace_id=workspace_id)
        
        # 소유자는 제거할 수 없음
        if membership.role == 'OWNER':
            messages.error(request, "워크스페이스 소유자는 제거할 수 없습니다.")
            return redirect('workspace:workspace_detail', workspace_id=workspace_id)
        
        # 자기 자신을 제거하는 경우 (나가기)
        if membership.user == request.user:
            membership.status = 'REMOVED'
            membership.save()
            messages.success(request, f"'{workspace.name}' 워크스페이스에서 나왔습니다.")
            return redirect('workspace:workspace_list')
        
        # 다른 멤버 제거
        username = membership.user.username if hasattr(membership.user, 'username') else str(membership.user.pk)
        membership.status = 'REMOVED'
        membership.save()
        messages.success(request, f"'{username}' 사용자가 워크스페이스에서 제거되었습니다.")
        
        return redirect('workspace:workspace_detail', workspace_id=workspace_id)

class ChangeRoleView(LoginRequiredMixin, View):
    """멤버 역할 변경"""
    
    def post(self, request, workspace_id, membership_id):
        workspace = get_object_or_404(Workspace, workspace_id=workspace_id)
        membership = get_object_or_404(WorkspaceMembership, membership_id=membership_id, workspace=workspace)
        
        # 역할 관리 권한 확인
        if not workspace.has_permission(request.user, 'manage_roles'):
            messages.error(request, "역할 관리 권한이 없습니다.")
            return redirect('workspace:workspace_detail', workspace_id=workspace_id)
        
        # 소유자의 역할은 변경할 수 없음
        if membership.role == 'OWNER':
            messages.error(request, "소유자의 역할은 변경할 수 없습니다.")
            return redirect('workspace:workspace_detail', workspace_id=workspace_id)
        
        form = WorkspaceMembershipForm(request.POST, instance=membership)
        if form.is_valid():
            form.save()
            username = membership.user.username if hasattr(membership.user, 'username') else str(membership.user.pk)
            messages.success(request, f"'{username}' 사용자의 역할이 '{membership.get_role_display()}'로 변경되었습니다.")
        else:
            messages.error(request, "역할 변경에 실패했습니다.")
        
        return redirect('workspace:workspace_detail', workspace_id=workspace_id)

class PublicWorkspaceListView(LoginRequiredMixin, WorkspaceContextMixin, ListView):
    """공개 워크스페이스 목록 (참여 가능한)"""
    model = Workspace
    template_name = 'workspace/public_workspace_list.html'
    context_object_name = 'workspaces'
    paginate_by = 12

    def get_queryset(self):
        # 공개 워크스페이스 중 아직 참여하지 않은 것들
        return Workspace.objects.filter(
            status='ACTIVE',
            is_public=True
        ).exclude(
            Q(owner=self.request.user) |
            Q(memberships__user=self.request.user, memberships__status='ACTIVE')
        ).order_by('-created_at')

class JoinWorkspaceView(LoginRequiredMixin, View):
    """공개 워크스페이스 참여"""
    
    def post(self, request, workspace_id):
        workspace = get_object_or_404(Workspace, workspace_id=workspace_id, status='ACTIVE')
        
        # 공개 워크스페이스인지 확인
        if not workspace.is_public:
            messages.error(request, "비공개 워크스페이스입니다.")
            return redirect('workspace:public_workspaces')
        
        # 이미 멤버인지 확인
        if workspace.memberships.filter(user=request.user, status='ACTIVE').exists():
            messages.warning(request, "이미 이 워크스페이스의 멤버입니다.")
            return redirect('workspace:workspace_detail', workspace_id=workspace_id)
        
        # 정원 확인
        if workspace.is_full:
            messages.error(request, "워크스페이스가 가득 차서 참여할 수 없습니다.")
            return redirect('workspace:public_workspaces')
        
        # 멤버십 생성
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=request.user,
            role='MEMBER'
        )
        
        messages.success(request, f"'{workspace.name}' 워크스페이스에 참여했습니다.")
        return redirect('workspace:workspace_detail', workspace_id=workspace_id)

class CancelInvitationView(LoginRequiredMixin, View):
    """초대 취소"""
    
    def post(self, request, invitation_id):
        invitation = get_object_or_404(Invitation, invitation_id=invitation_id)
        
        # 초대 취소 권한 확인 (초대한 사람 또는 워크스페이스 관리자)
        if not (invitation.inviter == request.user or 
                invitation.workspace.has_permission(request.user, 'invite')):
            messages.error(request, "초대 취소 권한이 없습니다.")
            return redirect('workspace:workspace_detail', workspace_id=invitation.workspace.workspace_id)
        
        try:
            invitation.cancel()
            messages.success(request, f"{invitation.invitee_email}에게 보낸 초대가 취소되었습니다.")
        except ValueError as e:
            messages.error(request, str(e))
        
        return redirect('workspace:workspace_detail', workspace_id=invitation.workspace.workspace_id)

class WorkspaceDeleteView(LoginRequiredMixin, View):
    """워크스페이스 삭제 (소유자만 가능)"""
    
    def get(self, request, workspace_id):
        workspace = get_object_or_404(Workspace, workspace_id=workspace_id)
        
        # 소유자만 삭제 가능
        if workspace.owner != request.user:
            messages.error(request, "워크스페이스를 삭제할 권한이 없습니다. 소유자만 삭제할 수 있습니다.")
            return redirect('workspace:workspace_detail', workspace_id=workspace_id)
        
        context = {
            'workspace': workspace,
            'member_count': workspace.memberships.filter(status='ACTIVE').count(),
            'group_count': workspace.task_groups.filter(status='ACTIVE').count(),
            'job_count': workspace.processing_jobs.count(),
            'pending_invitations_count': workspace.invitations.filter(status='PENDING').count(),
        }
        
        return render(request, 'workspace/workspace_delete.html', context)
    
    def post(self, request, workspace_id):
        workspace = get_object_or_404(Workspace, workspace_id=workspace_id)
        
        # 소유자만 삭제 가능
        if workspace.owner != request.user:
            messages.error(request, "워크스페이스를 삭제할 권한이 없습니다.")
            return redirect('workspace:workspace_detail', workspace_id=workspace_id)
        
        # 확인 텍스트 검증
        confirmation_text = request.POST.get('confirmation_text', '').strip()
        if confirmation_text != '워크스페이스 삭제':
            messages.error(request, "'워크스페이스 삭제'를 정확히 입력해주세요.")
            return redirect('workspace:workspace_delete', workspace_id=workspace_id)
        
        workspace_name = workspace.name
        
        try:
            with transaction.atomic():
                # 현재 워크스페이스로 설정된 사용자들을 개인 모드로 전환
                from django.contrib.auth import get_user_model
                User = get_user_model()
                users_in_workspace = User.objects.filter(current_workspace=workspace)
                for user in users_in_workspace:
                    user.switch_to_personal_mode()
                
                # 관련 초대들을 취소 상태로 변경
                workspace.invitations.filter(status='PENDING').update(status='CANCELLED')
                
                # 멤버십을 제거 상태로 변경
                workspace.memberships.filter(status='ACTIVE').update(status='REMOVED')
                
                # 태스크 그룹들을 보관 상태로 변경
                workspace.task_groups.filter(status='ACTIVE').update(status='ARCHIVED')
                
                # 워크스페이스를 보관 상태로 변경 (완전 삭제 대신)
                workspace.status = 'ARCHIVED'
                workspace.save()
                
                messages.success(request, f"'{workspace_name}' 워크스페이스가 성공적으로 삭제되었습니다.")
                return redirect('workspace:workspace_list')
                
        except Exception as e:
            messages.error(request, f"워크스페이스 삭제 중 오류가 발생했습니다: {str(e)}")
            return redirect('workspace:workspace_delete', workspace_id=workspace_id)
