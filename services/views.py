from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import ServicePlan, ServiceUsage, Promotion, UserAccount, Transaction
from decimal import Decimal
import random

@login_required
def services_view(request):
    plan_type = request.GET.get('plan_type', '')
    is_active = request.GET.get('is_active', '')
    packages = ServicePlan.objects.all()
    if plan_type:
        packages = packages.filter(plan_type=plan_type)
    if is_active:
        packages = packages.filter(is_active=True)
    promotions = Promotion.objects.filter(
        is_active=True,
        start_date__lte=timezone.now(),
        end_date__gte=timezone.now()
    )
    return render(request, 'services/services.html', {
        'packages': packages,
        'promotions': promotions
    })

@login_required
@require_POST
def register_service_view(request, package_id):
    try:
        package = get_object_or_404(ServicePlan, id=package_id)
        if not package.is_active:
            return JsonResponse({'status': 'error', 'message': 'Gói cước này hiện không khả dụng để đăng ký.'}, status=400)

        existing_usage = ServiceUsage.objects.filter(
            user=request.user,
            service_plan=package,
            is_active=True,
            end_date__gte=timezone.now()
        ).exists()
        if existing_usage:
            return JsonResponse({'status': 'error', 'message': f'Bạn đã đăng ký gói "{package.name}" và gói vẫn đang hoạt động.'}, status=400)

        # Kiểm tra số dư tài khoản
        user_account, created = UserAccount.objects.get_or_create(user=request.user)
        promotion = package.promotions.filter(
            is_active=True,
            start_date__lte=timezone.now(),
            end_date__gte=timezone.now()
        ).first()
        final_price = package.price
        success_message = f'Đăng ký gói "{package.name}" thành công!'
        if promotion:
            discount = package.price * (promotion.discount_percentage / 100)
            final_price = package.price - discount
            success_message = f'Đăng ký gói "{package.name}" thành công! Bạn đã được giảm {promotion.discount_percentage}% nhờ khuyến mãi "{promotion.title}".'

        if user_account.balance < final_price:
            return JsonResponse({'status': 'error', 'message': 'Số dư không đủ. Vui lòng nạp thêm tiền vào tài khoản.'}, status=400)

        # Trừ tiền từ tài khoản
        user_account.balance -= final_price
        user_account.save()

        # Ghi lại giao dịch
        Transaction.objects.create(
            user=request.user,
            amount=final_price,
            transaction_type='withdraw',
            description=f'Thanh toán gói cước "{package.name}"'
        )

        # Tạo bản ghi ServiceUsage
        ServiceUsage.objects.create(
            user=request.user,
            service_plan=package,
            spent_amount=final_price,
            is_active=True,
            start_date=timezone.now(),
            end_date=timezone.now() + timezone.timedelta(days=package.duration_days),
            data_usage=0,
            call_minutes=0,
            sms_used=0,
            remaining_data=package.data_volume / 1024 if package.data_volume else 0,
            remaining_minutes=package.voice_minutes or 0,
            remaining_sms=package.sms_count or 0
        )

        return JsonResponse({'status': 'success', 'message': success_message})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Đã có lỗi xảy ra: {str(e)}'}, status=500)

@login_required
def usage_history_view(request):
    usage_history = ServiceUsage.objects.filter(user=request.user).order_by('-start_date')
    total_packages = usage_history.count()
    total_spent = sum(usage.spent_amount for usage in usage_history)
    total_original_price = sum(usage.service_plan.price for usage in usage_history) if usage_history else 0
    total_savings = total_original_price - total_spent

    return render(request, 'services/usage_history.html', {
        'usage_history': usage_history,
        'now': timezone.now(),
        'total_packages': total_packages,
        'total_spent': total_spent,
        'total_savings': total_savings,
    })

@login_required
def account_management_view(request):
    user_account, created = UserAccount.objects.get_or_create(user=request.user)
    transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'services/account_management.html', {
        'user_account': user_account,
        'transactions': transactions,
    })

@login_required
@require_POST
def deposit_view(request):
    try:
        amount_str = request.POST.get('amount')
        if not amount_str:
            return JsonResponse({'status': 'error', 'message': 'Vui lòng nhập số tiền.'}, status=400)

        # Chuyển đổi amount thành Decimal thay vì float
        amount = Decimal(amount_str)
        if amount <= 0:
            return JsonResponse({'status': 'error', 'message': 'Số tiền nạp phải lớn hơn 0.'}, status=400)

        # Cộng tiền vào tài khoản
        user_account, created = UserAccount.objects.get_or_create(user=request.user)
        user_account.balance += amount  # Bây giờ cả hai đều là Decimal
        user_account.save()

        # Ghi lại giao dịch
        Transaction.objects.create(
            user=request.user,
            amount=amount,
            transaction_type='deposit',
            description='Nạp tiền vào tài khoản qua phương thức thanh toán'
        )

        return JsonResponse({'status': 'success', 'message': f'Nạp {amount} VNĐ thành công!'})

    except ValueError:
        return JsonResponse({'status': 'error', 'message': 'Số tiền không hợp lệ.'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Đã có lỗi xảy ra: {str(e)}'}, status=500)

@login_required
@require_POST
def cancel_service_view(request, usage_id):
    try:
        usage = ServiceUsage.objects.get(id=usage_id, user=request.user)
        if usage.end_date < timezone.now():
            return JsonResponse({'message': 'Gói cước đã hết hạn, không thể hủy.'}, status=400)
            
        usage.end_date = timezone.now()
        usage.is_active = False
        usage.save()
        return JsonResponse({'message': 'Hủy gói cước thành công!'})
    except ServiceUsage.DoesNotExist:
        return JsonResponse({'message': 'Gói cước không tồn tại.'}, status=400)

@login_required
@require_POST
def renew_service_view(request, usage_id):
    try:
        usage = ServiceUsage.objects.get(id=usage_id, user=request.user)
        if usage.end_date >= timezone.now():
            return JsonResponse({'message': 'Gói cước chưa hết hạn, không thể gia hạn.'}, status=400)

        service_plan = usage.service_plan
        if not service_plan:
            return JsonResponse({'message': 'Gói cước không còn tồn tại.'}, status=400)
        if not service_plan.is_active:
            return JsonResponse({'message': 'Gói cước không còn khả dụng.'}, status=400)

        existing_usage = ServiceUsage.objects.filter(
            user=request.user,
            service_plan=service_plan,
            is_active=True,
            end_date__gte=timezone.now()
        ).exists()
        if existing_usage:
            return JsonResponse({'message': f'Bạn đã có một gói "{service_plan.name}" đang hoạt động. Vui lòng hủy gói hiện tại trước khi gia hạn.'}, status=400)

        # Kiểm tra số dư tài khoản
        user_account, created = UserAccount.objects.get_or_create(user=request.user)
        if user_account.balance < service_plan.price:
            return JsonResponse({'message': 'Số dư không đủ. Vui lòng nạp thêm tiền vào tài khoản.'}, status=400)

        # Trừ tiền từ tài khoản
        user_account.balance -= service_plan.price
        user_account.save()

        # Ghi lại giao dịch
        Transaction.objects.create(
            user=request.user,
            amount=service_plan.price,
            transaction_type='withdraw',
            description=f'Gia hạn gói cước "{service_plan.name}"'
        )

        # Tạo bản ghi ServiceUsage mới khi gia hạn
        new_usage = ServiceUsage(
            user=request.user,
            service_plan=service_plan,
            spent_amount=service_plan.price,
            is_active=True,
            start_date=timezone.now(),
            end_date=timezone.now() + timezone.timedelta(days=service_plan.duration_days),
            data_usage=0,
            call_minutes=0,
            sms_used=0,
            remaining_data=service_plan.data_volume / 1024 if service_plan.data_volume else 0,
            remaining_minutes=service_plan.voice_minutes or 0,
            remaining_sms=service_plan.sms_count or 0
        )
        new_usage.save()
        return JsonResponse({'message': 'Gia hạn gói cước thành công!'})
    except ServiceUsage.DoesNotExist:
        return JsonResponse({'message': 'Gói cước không tồn tại.'}, status=400)

@login_required
def check_usage_view(request):
    # Lấy gói cước đang hoạt động gần đây nhất của người dùng
    usage = ServiceUsage.objects.filter(
        user=request.user,
        is_active=True,
        end_date__gte=timezone.now()
    ).order_by('-start_date').first()

    if request.method == "POST":
        if usage:
            # Giả lập sử dụng ngẫu nhiên dựa trên lưu lượng còn lại
            max_data_to_use = min(usage.remaining_data, 2.0)  # Tối đa 2 GB, nhưng không vượt quá remaining_data
            max_minutes_to_use = min(usage.remaining_minutes, 20)  # Tối đa 20 phút
            max_sms_to_use = min(usage.remaining_sms, 10)  # Tối đa 10 SMS

            # Tạo ngẫu nhiên trong phạm vi khả dụng
            data_used = round(random.uniform(0.01, max_data_to_use), 2) if max_data_to_use > 0 else 0
            minutes_called = random.randint(0, max_minutes_to_use) if max_minutes_to_use > 0 else 0
            sms_sent = random.randint(0, max_sms_to_use) if max_sms_to_use > 0 else 0

            # Kiểm tra xem có sử dụng được không
            if data_used > 0 or minutes_called > 0 or sms_sent > 0:
                usage.data_usage += data_used
                usage.call_minutes += minutes_called
                usage.sms_used += sms_sent
                usage.remaining_data = max(0, usage.remaining_data - data_used)
                usage.remaining_minutes = max(0, usage.remaining_minutes - minutes_called)
                usage.remaining_sms = max(0, usage.remaining_sms - sms_sent)
                usage.save()
                messages.success(request, f"Giả lập sử dụng thành công: {data_used} GB, {minutes_called} phút, {sms_sent} tin nhắn.")
            else:
                messages.error(request, "Không đủ lưu lượng để giả lập sử dụng. Tất cả lưu lượng đã cạn kiệt.")
        else:
            messages.error(request, "Bạn không có gói cước đang hoạt động.")

    if usage:
        context = {
            'data_usage': usage.data_usage,
            'call_minutes': usage.call_minutes,
            'sms_used': usage.sms_used,
            'remaining_data': usage.remaining_data,
            'remaining_minutes': usage.remaining_minutes,
            'remaining_sms': usage.remaining_sms,
            'max_data': usage.service_plan.data_volume / 1024 if usage.service_plan.data_volume else 0,
            'max_minutes': usage.service_plan.voice_minutes or 0,
            'max_sms': usage.service_plan.sms_count or 0,
        }
    else:
        context = {
            'error': "Bạn không có gói cước đang hoạt động."
        }

    return render(request, 'services/check_usage.html', context)