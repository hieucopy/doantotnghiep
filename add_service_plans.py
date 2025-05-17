import os
import django

# Thiết lập môi trường Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_telecom.settings')
django.setup()

from services.models import ServicePlan

from django.utils import timezone
from datetime import timedelta
from services.models import ServicePlan, ServiceUsage, Promotion
from users.models import CustomUser
from django.contrib.auth.models import User

# Kiểm tra và tạo người dùng nếu chưa có
from django.utils import timezone
from datetime import timedelta
from services.models import ServicePlan, ServiceUsage, Promotion
from users.models import CustomUser

from django.utils import timezone
from datetime import timedelta
from users.models import CustomUser, CustomerProfile
from services.models import ServicePlan, ServiceUsage, Promotion

# Thêm dữ liệu cho CustomUser
try:
    # Tạo người dùng
    user1 = CustomUser.objects.create(
        username='user1',
        email='user1@example.com',
        first_name='User',
        last_name='One',
        phone_number='0901234567',
        is_customer=True
    )
    user1.set_password('password123')
    user1.save()

    user2 = CustomUser.objects.create(
        username='user2',
        email='user2@example.com',
        first_name='User',
        last_name='Two',
        phone_number='0901234568',
        is_customer=True
    )
    user2.set_password('password123')
    user2.save()

    admin_user = CustomUser.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='admin123',
        phone_number='0901234569',
        is_customer=False
    )

    print("Đã tạo người dùng thành công!")
except Exception as e:
    print(f"Error creating users: {e}")

# Thêm dữ liệu cho CustomerProfile
try:
    CustomerProfile.objects.create(
        user=user1,
        loyalty_points=100
    )

    CustomerProfile.objects.create(
        user=user2,
        loyalty_points=50
    )

    # Admin không cần CustomerProfile (vì is_customer=False)
    print("Đã tạo CustomerProfile thành công!")
except Exception as e:
    print(f"Error creating CustomerProfile: {e}")

# Thêm dữ liệu cho ServicePlan
try:
    plan1 = ServicePlan.objects.create(
        name="4G 30GB",
        plan_type="DATA",
        description="Gói cước 4G với 30GB dữ liệu tốc độ cao.",
        price=150000,
        duration_days=30,
        data_volume=30720,
        data_speed="4G",
        voice_minutes=None,
        sms_count=None,
        is_active=True,
        priority=3
    )

    plan2 = ServicePlan.objects.create(
        name="Thoại 500 Phút",
        plan_type="VOICE",
        description="Gói cước thoại với 500 phút gọi nội mạng.",
        price=50000,
        duration_days=30,
        data_volume=None,
        data_speed=None,
        voice_minutes=500,
        sms_count=None,
        is_active=True,
        priority=2
    )

    plan3 = ServicePlan.objects.create(
        name="SMS 200 Tin",
        plan_type="SMS",
        description="Gói cước SMS với 200 tin nhắn miễn phí.",
        price=20000,
        duration_days=15,
        data_volume=None,
        data_speed=None,
        voice_minutes=None,
        sms_count=200,
        is_active=True,
        priority=1
    )

    plan4 = ServicePlan.objects.create(
        name="Combo 10GB + 300 Phút",
        plan_type="COMBO",
        description="Gói combo với 10GB dữ liệu và 300 phút gọi.",
        price=120000,
        duration_days=30,
        data_volume=10240,
        data_speed="4G",
        voice_minutes=300,
        sms_count=50,
        is_active=True,
        priority=4
    )

    plan5 = ServicePlan.objects.create(
        name="4G 5GB (Ngừng cung cấp)",
        plan_type="DATA",
        description="Gói cước 4G với 5GB dữ liệu (đã ngừng cung cấp).",
        price=50000,
        duration_days=30,
        data_volume=5120,
        data_speed="4G",
        voice_minutes=None,
        sms_count=None,
        is_active=False,
        priority=0
    )

    print("Đã thêm dữ liệu vào ServicePlan thành công!")
except Exception as e:
    print(f"Error adding ServicePlan data: {e}")

# Thêm dữ liệu cho ServiceUsage
try:
    usage1 = ServiceUsage.objects.create(
        user=user1,
        service_plan=plan1,
        spent_amount=150000,
        is_active=True,
        start_date=timezone.now() - timedelta(days=10),
        data_usage=10.5,
        call_minutes=0,
        sms_used=0
    )

    usage2 = ServiceUsage.objects.create(
        user=user1,
        service_plan=plan2,
        spent_amount=50000,
        is_active=True,
        start_date=timezone.now() - timedelta(days=5),
        data_usage=0,
        call_minutes=200,
        sms_used=0
    )

    usage3 = ServiceUsage.objects.create(
        user=user2,
        service_plan=plan4,
        spent_amount=120000,
        is_active=True,
        start_date=timezone.now() - timedelta(days=25),
        data_usage=8.0,
        call_minutes=250,
        sms_used=40
    )

    print("Đã thêm dữ liệu vào ServiceUsage thành công!")
except Exception as e:
    print(f"Error adding ServiceUsage data: {e}")

# Thêm dữ liệu cho Promotion
try:
    promo1 = Promotion.objects.create(
        title="Khuyến mãi 20% cho gói 4G",
        description="Giảm 20% cho tất cả gói cước 4G trong tháng này!",
        discount_percentage=20,
        start_date=timezone.now() - timedelta(days=5),
        end_date=timezone.now() + timedelta(days=25),
        is_active=True
    )
    promo1.service_plans.add(plan1, plan4)

    promo2 = Promotion.objects.create(
        title="Tặng 100 phút gọi",
        description="Tặng thêm 100 phút gọi khi đăng ký gói thoại bất kỳ.",
        discount_percentage=0,
        start_date=timezone.now() - timedelta(days=10),
        end_date=timezone.now() + timedelta(days=20),
        is_active=True
    )
    promo2.service_plans.add(plan2, plan4)

    print("Đã thêm dữ liệu vào Promotion thành công!")
except Exception as e:
    print(f"Error adding Promotion data: {e}")