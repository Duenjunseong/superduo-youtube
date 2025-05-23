from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.utils.translation import gettext_lazy as _

from django.contrib.auth.models import User


class CustomUserCreationForm(UserCreationForm):
    """회원가입 폼"""
    email = forms.EmailField(
        label=_("이메일"),
        required=True,
        help_text=_("유효한 이메일 주소를 입력하세요."),
    )
    
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'password1', 'password2')
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 필드 커스터마이징
        self.fields['username'].label = _("아이디")
        self.fields['username'].help_text = _("150자 이하, 문자, 숫자, @/./+/-/_ 만 가능합니다.")
        self.fields['password1'].label = _("비밀번호")
        self.fields['password2'].label = _("비밀번호 확인")


class CustomUserChangeForm(UserChangeForm):
    """프로필 수정 폼"""
    password = None  # 비밀번호 필드 제거
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')
        labels = {
            'username': _("아이디"),
            'email': _("이메일"),
            'first_name': _("이름"),
            'last_name': _("성"),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 필드 커스터마이징
        self.fields['username'].help_text = _("150자 이하, 문자, 숫자, @/./+/-/_ 만 가능합니다.") 