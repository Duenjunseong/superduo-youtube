from django import forms
from django.utils.translation import gettext_lazy as _

class LinkForm(forms.Form):
    """YouTube 링크 다운로드 폼"""
    QUALITY_CHOICES = (
        ('highest', '최상 품질'),
        ('720p', '720p'),
        ('480p', '480p'),
        ('360p', '360p'),
        ('audio', '오디오만'),
    )
    
    urls = forms.CharField(
        label=_('YouTube URL'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'https://youtube.com/watch?v=...\n여러 URL을 입력하려면 줄바꿈으로 구분해 주세요.'
        }),
        help_text=_('여러 YouTube URL을 한 번에 입력할 수 있습니다. 각 URL은 새 줄로 구분해 주세요.')
    )
    
    quality = forms.ChoiceField(
        label=_('품질 선택'),
        choices=QUALITY_CHOICES,
        initial='highest',
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    def clean_urls(self):
        """URL 유효성 검사"""
        urls = self.cleaned_data.get('urls', '').strip()
        if not urls:
            raise forms.ValidationError(_('하나 이상의 URL을 입력해주세요.'))
        return urls 