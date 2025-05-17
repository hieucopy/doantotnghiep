from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from services.models import ServicePlan, Promotion, ServiceUsage, UserAccount
from django.utils import timezone
from django.db.models import Count

def home_view(request):
    # Lấy danh sách gói cước nổi bật (dựa trên số lượng đăng ký)
    featured_packages = ServicePlan.objects.annotate(
        usage_count=Count('usages')
    ).order_by('-usage_count')[:3]

    # Lấy danh sách khuyến mãi đang hoạt động
    promotions = Promotion.objects.filter(
        is_active=True,
        start_date__lte=timezone.now(),
        end_date__gte=timezone.now()
    )[:2]

    # Lấy thông tin gói cước đang sử dụng của người dùng (nếu đã đăng nhập)
    active_usage = None
    user_account = None
    if request.user.is_authenticated:
        active_usage = ServiceUsage.objects.filter(
            user=request.user,
            is_active=True,
            end_date__gte=timezone.now()
        ).first()
        # Lấy số dư tài khoản
        user_account, created = UserAccount.objects.get_or_create(user=request.user)

    return render(request, 'home.html', {
        'featured_packages': featured_packages,
        'promotions': promotions,
        'active_usage': active_usage,
        'user_account': user_account,
        'now': timezone.now()
    })

@login_required
def profile_view(request):
    return render(request, 'profile.html', {})