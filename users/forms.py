from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, SetPasswordForm
from .models import CustomUser

class CustomUserCreationForm(UserCreationForm):
    phone_number = forms.CharField(max_length=15, required=True, label="Số điện thoại")
    email = forms.EmailField(required=True, label="Email")
    
    class Meta:
        model = CustomUser
        fields = ['username', 'phone_number', 'email', 'password1', 'password2']

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if CustomUser.objects.filter(phone_number=phone_number).exists():
            raise forms.ValidationError("Số điện thoại đã được sử dụng.")
        return phone_number

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("Email đã được sử dụng.")
        return email

class CustomUserLoginForm(AuthenticationForm):
    username = forms.CharField(label="Tên đăng nhập hoặc số điện thoại")

    def clean_username(self):
        username = self.cleaned_data.get('username')
        try:
            user = CustomUser.objects.get(phone_number=username)
            return user.username
        except CustomUser.DoesNotExist:
            return username

class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(label="Email", max_length=254)

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("Email này không tồn tại trong hệ thống.")
        return email

class CustomSetPasswordForm(SetPasswordForm):
    pass