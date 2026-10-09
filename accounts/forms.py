from django import forms
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm, UserCreationForm
from .models import User


class LocalizedAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, language='th', **kwargs):
        super().__init__(*args, **kwargs)
        self.language = language
        if language == 'en':
            self.fields['username'].label = 'Username'
            self.fields['password'].label = 'Password'
        else:
            self.fields['username'].label = 'ชื่อผู้ใช้'
            self.fields['password'].label = 'รหัสผ่าน'


class LocalizedSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, language='th', **kwargs):
        super().__init__(*args, **kwargs)
        if language == 'en':
            self.fields['new_password1'].label = 'New password'
            self.fields['new_password2'].label = 'Confirm new password'
        else:
            self.fields['new_password1'].label = 'รหัสผ่านใหม่'
            self.fields['new_password2'].label = 'ยืนยันรหัสผ่านใหม่'


class RegistrationForm(UserCreationForm):
    role = forms.ChoiceField(choices=User.Role.choices, widget=forms.RadioSelect)
    room_number = forms.CharField(max_length=20, required=False, label='Room number')

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'username', 'email', 'role', 'room_number', 'password1', 'password2')

    def __init__(self, *args, language='th', **kwargs):
        super().__init__(*args, **kwargs)
        if language == 'en':
            labels = {
                'first_name': 'First name',
                'last_name': 'Last name',
                'username': 'Username',
                'email': 'Email address',
                'role': 'I am a',
                'room_number': 'Room number',
                'password1': 'Password',
                'password2': 'Confirm password',
            }
            self.fields['role'].choices = (
                (User.Role.STUDENT, 'Student'),
            )
        else:
            labels = {
                'first_name': 'ชื่อ',
                'last_name': 'นามสกุล',
                'username': 'ชื่อผู้ใช้',
                'email': 'อีเมล',
                'role': 'ประเภทผู้ใช้งาน',
                'room_number': 'ห้องพัก',
                'password1': 'รหัสผ่าน',
                'password2': 'ยืนยันรหัสผ่าน',
            }
            self.fields['role'].choices = (
                (User.Role.STUDENT, 'นักศึกษา'),
            )
        for name, label in labels.items():
            self.fields[name].label = label

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('role') == User.Role.STUDENT and not cleaned.get('room_number'):
            message = 'Students must provide a room number.' if self.language == 'en' else 'นักศึกษาต้องระบุห้องพัก'
            self.add_error('room_number', message)
        return cleaned
