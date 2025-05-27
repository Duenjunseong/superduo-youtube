from django import forms
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

class JobAndSegmentForm(forms.Form):
    # group 필드는 뷰에서 사용자의 그룹 목록을 queryset으로 받아 동적으로 설정
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
    # 각 줄에 "HH:MM:SS-HH:MM:SS [선택적_파일ID]" 형식으로 입력
    # 예: 
    # 00:01:10-00:01:45 intro_부분
    # 00:05:00-00:05:30 중요한_내용
    segments_input = forms.CharField(
        label='구간 정보 (시작시간-종료시간 [결과ID]) - 한 줄에 하나씩',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': '00:00:10-00:00:25 segment1\n00:01:00-00:01:15 segment2'}),
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
        initial=True,  # 기본값: 즉시 시작
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='체크 해제 시 작업을 대기 상태로 추가합니다. 나중에 일괄 처리로 시작할 수 있습니다.'
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None) # 뷰에서 현재 사용자를 받아옴
        super().__init__(*args, **kwargs)
        if user:
            self.fields['group'].queryset = TaskGroup.objects.filter(user=user, status='ACTIVE')

# 기존 DownloadAndSplitForm은 JobAndSegmentForm으로 대체되었으므로 주석 처리 또는 삭제
# class DownloadAndSplitForm(forms.Form):
#     youtube_url = forms.URLField(...)
#     segments_input = forms.CharField(...)
#     group_name = forms.CharField(...)

# 추후 split_project의 카테고리 기능도 여기에 추가할 수 있습니다.
# category = forms.ChoiceField(label='카테고리', choices=[('default', '기본'), ...], required=False) 