from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from .forms import CustomUserCreationForm, CustomUserLoginForm
from .models import CustomUser, CustomerProfile
from rest_framework import viewsets
from .serializers import CustomUserSerializer, CustomerProfileSerializer

def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            if user.is_customer:
                CustomerProfile.objects.create(user=user)
            # Xác thực người dùng trước khi đăng nhập
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, 'Đăng ký thành công! Chào mừng bạn.')
                return redirect('profile')
            else:
                messages.error(request, 'Có lỗi xảy ra khi đăng nhập tự động. Vui lòng đăng nhập thủ công.')
                return redirect('login')
        else:
            messages.error(request, 'Có lỗi xảy ra. Vui lòng kiểm tra lại thông tin.')
    else:
        form = CustomUserCreationForm()
    return render(request, 'users/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = CustomUserLoginForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, 'Đăng nhập thành công!')
            return redirect('profile')
        else:
            messages.error(request, 'Tên đăng nhập hoặc mật khẩu không đúng.')
    else:
        form = CustomUserLoginForm()
    return render(request, 'users/login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.success(request, 'Đăng xuất thành công!')
    return redirect('login')

def profile_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    try:
        profile = request.user.profile
    except CustomerProfile.DoesNotExist:
        profile = None
    
    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', '')
        request.user.last_name = request.POST.get('last_name', '')
        request.user.email = request.POST.get('email', '')
        request.user.address = request.POST.get('address', '')
        request.user.save()
        messages.success(request, 'Cập nhật hồ sơ thành công!')
        return redirect('profile')
    
    return render(request, 'users/profile.html', {'user': request.user, 'profile': profile})

# API views
class CustomUserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer

class CustomerProfileViewSet(viewsets.ModelViewSet):
    queryset = CustomerProfile.objects.all()
    serializer_class = CustomerProfileSerializer