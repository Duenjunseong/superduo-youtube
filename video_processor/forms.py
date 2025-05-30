from django import forms
from django.db.models import Q
from .models import TaskGroup, ProcessingJob, VideoSegment

class TaskGroupForm(forms.ModelForm):
    class Meta:
        model = TaskGroup
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: 프로젝트 A 하이라이트'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': '그룹에 대한 간단한 설명 (선택 사항)'}),
        }
        labels = {
            'name': '그룹명',
            'description': '설명',
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.user = user

class JobAndSegmentForm(forms.Form):
    # group 필드는 뷰에서 사용자의 현재 워크스페이스 모드에 맞는 그룹 목록을 queryset으로 받아 동적으로 설정
    group = forms.ModelChoiceField(
        queryset=TaskGroup.objects.none(), # 뷰에서 재정의 필요
        required=False,
        label='소속 그룹 (선택)',
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='이 작업을 특정 그룹에 추가할 수 있습니다. 선택하지 않으면 그룹 없이 생성됩니다.'
    )
    youtube_url = forms.URLField(
        label='유튜브 URL',
        widget=forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://www.youtube.com/watch?v=...'})
    )
    
    # 전체 파일 다운로드 옵션
    download_full_video = forms.BooleanField(
        label='전체 파일 가져오기',
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_download_full_video'}),
        help_text='체크하면 전체 영상을 다운로드합니다. 세그먼트 구간 설정은 무시됩니다.'
    )
    
    # 전체 파일 다운로드 시 사용할 파일명 접두사
    full_video_prefix = forms.CharField(
        label='전체 파일 접두사',
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': '예: full_video',
            'id': 'id_full_video_prefix',
            'value': 'VIDEO-',
        }),
        help_text='전체 파일 다운로드 시 사용할 파일명 접두사를 입력하세요.'
    )
    
    # 각 줄에 "HH:MM:SS-HH:MM:SS [선택적_파일ID]" 형식으로 입력
    # 예: 
    # 00:01:10-00:01:45 intro_부분
    # 00:05:00-00:05:30 중요한_내용
    segments_input = forms.CharField(
        label='구간 정보 (시작시간-종료시간 [결과ID]) - 한 줄에 하나씩',
        required=False,  # 전체 파일 다운로드 시에는 필수가 아님
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 4, 
            'placeholder': '00:00:10-00:00:25 segment1\n00:01:00-00:01:15 segment2',
            'id': 'id_segments_input'
        }),
        help_text='예시: 00:00:10-00:00:25 영상부분A (결과ID는 선택 사항이며, 공백으로 구분합니다.)'
    )
    tags_input = forms.CharField(
        label='태그 (쉼표로 구분)',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: 중요, 편집용, 발표자료'}),
        help_text='여러 태그를 쉼표(,)로 구분하여 입력하세요.'
    )
    auto_start = forms.BooleanField(
        label='작업 즉시 시작',
        required=False,
        initial=False,  # 기본값: 즉시 시작
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='체크 해제 시 작업을 대기 상태로 추가합니다. 나중에 일괄 처리로 시작할 수 있습니다.'
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None) # 뷰에서 현재 사용자를 받아옴
        super().__init__(*args, **kwargs)
        if user:
            # 현재 워크스페이스 모드에 따라 그룹 목록 필터링
            if user.is_in_workspace_mode():
                # 워크스페이스 모드: 현재 워크스페이스의 그룹들만
                self.fields['group'].queryset = TaskGroup.objects.filter(
                    workspace=user.current_workspace,
                    status='ACTIVE'
                ).order_by('name')
                self.fields['group'].help_text = f'현재 워크스페이스 "{user.current_workspace.name}"의 그룹 목록입니다.'
            else:
                # 개인 모드: 워크스페이스 없는 개인 그룹들만
                self.fields['group'].queryset = TaskGroup.objects.filter(
                    user=user,
                    workspace__isnull=True,
                    status='ACTIVE'
                ).order_by('name')
                self.fields['group'].help_text = '개인 그룹 목록입니다.'

    def clean(self):
        cleaned_data = super().clean()
        download_full_video = cleaned_data.get('download_full_video')
        segments_input = cleaned_data.get('segments_input')
        
        # 전체 파일 다운로드가 체크되지 않았고, 세그먼트 입력도 없는 경우
        if not download_full_video and not segments_input:
            raise forms.ValidationError(
                "전체 파일 가져오기를 체크하거나 구간 정보를 입력해야 합니다."
            )
        
        # 전체 파일 다운로드가 체크되었지만 세그먼트 입력도 있는 경우 (경고)
        if download_full_video and segments_input and segments_input.strip():
            # 세그먼트 입력을 무시한다는 것을 명시
            cleaned_data['segments_input'] = ''
        
        return cleaned_data

# 기존 DownloadAndSplitForm은 JobAndSegmentForm으로 대체되었으므로 주석 처리 또는 삭제
# class DownloadAndSplitForm(forms.Form):
#     youtube_url = forms.URLField(...)
#     segments_input = forms.CharField(...)
#     group_name = forms.CharField(...)

# 추후 split_project의 카테고리 기능도 여기에 추가할 수 있습니다.
# category = forms.ChoiceField(label='카테고리', choices=[('default', '기본'), ...], required=False) 