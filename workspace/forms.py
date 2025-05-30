from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from .models import Workspace, WorkspaceMembership, Invitation

User = get_user_model()

class WorkspaceForm(forms.ModelForm):
    class Meta:
        model = Workspace
        fields = ['name', 'description', 'icon', 'is_public', 'max_members']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': '예: 마케팅팀 프로젝트'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3, 
                'placeholder': '워크스페이스에 대한 설명을 입력하세요.'
            }),
            'icon': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'is_public': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'max_members': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 100,
                'value': 10
            }),
        }
        labels = {
            'name': '워크스페이스명',
            'description': '설명',
            'icon': '워크스페이스 아이콘',
            'is_public': '공개 워크스페이스',
            'max_members': '최대 멤버 수',
        }
        help_texts = {
            'icon': '정사각형 이미지를 권장합니다. (권장 크기: 512x512px, 최대 5MB)',
            'is_public': '체크하면 다른 사용자들이 워크스페이스를 검색할 수 있습니다.',
            'max_members': '이 워크스페이스에 참여할 수 있는 최대 멤버 수입니다.',
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            # 수정 시에는 자기 자신은 제외하고 중복 확인
            queryset = Workspace.objects.filter(name=name, status='ACTIVE')
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            
            if queryset.exists():
                raise ValidationError('이미 사용 중인 워크스페이스명입니다.')
        return name

    def clean_icon(self):
        icon = self.cleaned_data.get('icon')
        if icon:
            # 새로 업로드된 파일인지 확인 (UploadedFile 타입)
            if hasattr(icon, 'content_type'):
                # 파일 크기 제한 (5MB)
                if hasattr(icon, 'size') and icon.size > 5 * 1024 * 1024:  # 5MB
                    raise ValidationError('파일 크기는 5MB를 초과할 수 없습니다.')
                
                # 이미지 파일 형식 확인
                if not icon.content_type.startswith('image/'):
                    raise ValidationError('이미지 파일만 업로드할 수 있습니다.')
            # 기존 파일인 경우 (ImageFieldFile 타입) - 검증 건너뛰기
                
        return icon

class InvitationForm(forms.ModelForm):
    user_identifier = forms.CharField(
        label='초대할 사용자',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '이메일 주소 또는 사용자명을 입력하세요'
        }),
        help_text='등록된 사용자의 이메일 주소 또는 사용자명을 입력하세요.'
    )
    
    class Meta:
        model = Invitation
        fields = ['role', 'message']
        widgets = {
            'role': forms.Select(attrs={
                'class': 'form-select'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3, 
                'placeholder': '초대 메시지를 입력하세요 (선택사항)'
            }),
        }
        labels = {
            'role': '역할',
            'message': '초대 메시지',
        }

    def __init__(self, *args, **kwargs):
        self.workspace = kwargs.pop('workspace', None)
        super().__init__(*args, **kwargs)

    def clean_user_identifier(self):
        user_identifier = self.cleaned_data['user_identifier'].strip()
        
        if not user_identifier:
            raise ValidationError('이메일 주소 또는 사용자명을 입력해주세요.')
        
        # 이메일 또는 사용자명으로 사용자 찾기
        user = None
        if '@' in user_identifier:
            # 이메일로 검색
            try:
                user = User.objects.get(email=user_identifier)
            except User.DoesNotExist:
                raise ValidationError(f'이메일 주소 "{user_identifier}"로 등록된 사용자를 찾을 수 없습니다.')
        else:
            # 사용자명으로 검색
            try:
                user = User.objects.get(username=user_identifier)
            except User.DoesNotExist:
                raise ValidationError(f'사용자명 "{user_identifier}"을 찾을 수 없습니다.')
        
        # 추가 검증
        if self.workspace:
            # 이미 멤버인지 확인
            if self.workspace.memberships.filter(user=user, status='ACTIVE').exists():
                raise ValidationError(f'{user.get_full_name() or user.username}님은 이미 이 워크스페이스의 멤버입니다.')
            
            # 이미 초대받은 상태인지 확인
            existing_invitation = self.workspace.invitations.filter(
                invitee_email=user.email,
                status='PENDING'
            ).first()
            if existing_invitation:
                raise ValidationError(f'{user.email}로 이미 대기 중인 초대가 있습니다.')
            
            # 워크스페이스 소유자인지 확인
            if self.workspace.owner == user:
                raise ValidationError('워크스페이스 소유자는 초대할 수 없습니다.')
        
        # 사용자 정보를 폼에 저장
        self.user_to_invite = user
        return user_identifier

    def save(self, commit=True):
        invitation = super().save(commit=False)
        
        # 찾은 사용자의 이메일을 설정
        if hasattr(self, 'user_to_invite'):
            invitation.invitee_email = self.user_to_invite.email
            invitation.invitee = self.user_to_invite
        
        if commit:
            invitation.save()
        return invitation

class WorkspaceMembershipForm(forms.ModelForm):
    """멤버의 역할을 변경하는 폼"""
    class Meta:
        model = WorkspaceMembership
        fields = ['role']
        widgets = {
            'role': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
        labels = {
            'role': '역할',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # OWNER 역할은 선택할 수 없도록 제외
        self.fields['role'].choices = [
            choice for choice in WorkspaceMembership.ROLE_CHOICES 
            if choice[0] != 'OWNER'
        ]

class WorkspaceJoinForm(forms.Form):
    """워크스페이스 참여 폼 (공개 워크스페이스용)"""
    workspace_id = forms.UUIDField(
        widget=forms.HiddenInput()
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_workspace_id(self):
        workspace_id = self.cleaned_data['workspace_id']
        try:
            workspace = Workspace.objects.get(workspace_id=workspace_id, status='ACTIVE')
        except Workspace.DoesNotExist:
            raise forms.ValidationError("존재하지 않거나 비활성화된 워크스페이스입니다.")
        
        if not workspace.is_public:
            raise forms.ValidationError("비공개 워크스페이스입니다.")
        
        if workspace.is_full:
            raise forms.ValidationError("워크스페이스가 가득 차서 참여할 수 없습니다.")
        
        # 이미 멤버인지 확인
        if self.user and workspace.memberships.filter(user=self.user, status='ACTIVE').exists():
            raise forms.ValidationError("이미 이 워크스페이스의 멤버입니다.")
        
        return workspace_id 