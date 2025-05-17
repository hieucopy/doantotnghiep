from faker import Faker
from django.utils import timezone
from users.models import CustomUser, CustomerProfile
from services.models import ServicePlan, ServiceUsage, Promotion, UserAccount, Transaction
from support.models import SupportTicket, FAQ
import random
import datetime
import pytz

# Khởi tạo Faker
fake = Faker('vi_VN')
fake.seed_instance(42)

# Xóa dữ liệu cũ (nếu có)
CustomUser.objects.all().delete()
CustomerProfile.objects.all().delete()
ServicePlan.objects.all().delete()
ServiceUsage.objects.all().delete()
Promotion.objects.all().delete()
UserAccount.objects.all().delete()
Transaction.objects.all().delete()
SupportTicket.objects.all().delete()
FAQ.objects.all().delete()
print("Dữ liệu cũ đã được xóa.")

# Hàm tạo danh sách ngẫu nhiên với giới hạn
def random_list(items, min_len=1, max_len=3):
    return random.sample(items, random.randint(min_len, max_len))

# Định nghĩa khoảng thời gian (2020 đến 15/05/2025)
past_start_date = timezone.make_aware(datetime.datetime(2020, 1, 1), timezone=pytz.UTC)
past_end_date = timezone.make_aware(datetime.datetime(2025, 5, 15), timezone=pytz.UTC)

# Tạo dữ liệu CustomUser (10,000 người dùng)
users = []
for i in range(10000):
    username = f"user{i+1}"
    email = f"user{i+1}@example.com"
    phone_number = f"090{i+1:07d}"  # Định dạng số điện thoại 10 chữ số
    user = CustomUser.objects.create(
        username=username,
        email=email,
        phone_number=phone_number,
        is_customer=True,
        date_of_birth=fake.date_of_birth(minimum_age=18, maximum_age=80),
        address=fake.address()
    )
    users.append(user)
    if i % 1000 == 0:
        print(f"Đã tạo CustomUser: {username}")

# Tạo dữ liệu CustomerProfile (10,000 hồ sơ)
for user in users:
    profile = CustomerProfile.objects.create(
        user=user,
        loyalty_points=random.randint(0, 500),
        registration_date=fake.date_time_between(start_date=past_start_date, end_date=past_end_date, tzinfo=pytz.UTC)
    )
    print(f"Đã tạo CustomerProfile cho {user.username} với registration_date: {profile.registration_date}")

# Tạo dữ liệu ServicePlan (5 gói cước)
service_plans = []
plan_types = ['DATA', 'VOICE', 'COMBO', 'DATA', 'COMBO']
data_speeds = ['4G', '5G', '4G', '5G', '4G']
for i in range(5):
    name = f"Plan {i+1} - {plan_types[i]}"
    plan = ServicePlan.objects.create(
        name=name,
        plan_type=plan_types[i],
        description=f"Mô tả gói cước {i+1}",
        price=round(random.uniform(50000, 500000), 2),
        duration_days=30,
        data_volume=10000 if 'DATA' in plan_types[i] else None,
        data_speed=data_speeds[i] if 'DATA' in plan_types[i] else None,
        voice_minutes=200 if 'VOICE' in plan_types[i] or 'COMBO' in plan_types[i] else None,
        sms_count=100 if 'COMBO' in plan_types[i] else None,
        is_active=True,
        priority=i,
        created_at=fake.date_time_between(start_date=past_start_date, end_date=past_end_date, tzinfo=pytz.UTC),
        updated_at=fake.date_time_between(start_date=past_start_date, end_date=past_end_date, tzinfo=pytz.UTC)
    )
    service_plans.append(plan)
    print(f"Đã tạo ServicePlan: {name}")

# Tạo dữ liệu Promotion (2 chương trình khuyến mãi)
for i in range(2):
    promo = Promotion.objects.create(
        title=f"Khuyến mãi mùa {['hè', 'đông'][i]}",
        description=f"Giảm giá {20 + i*10}% cho tất cả gói cước",
        discount_percentage=20.0 + i*10,
        start_date=fake.date_time_between(start_date=past_start_date, end_date=past_end_date, tzinfo=pytz.UTC),
        end_date=fake.date_time_between(start_date=past_start_date, end_date=past_end_date, tzinfo=pytz.UTC),
        is_active=True,
        created_at=fake.date_time_between(start_date=past_start_date, end_date=past_end_date, tzinfo=pytz.UTC),
        updated_at=fake.date_time_between(start_date=past_start_date, end_date=past_end_date, tzinfo=pytz.UTC)
    )
    promo.service_plans.set(service_plans)
    print(f"Đã tạo Promotion: {promo.title}")

# Tạo dữ liệu UserAccount (10,000 tài khoản)
for user in users:
    account = UserAccount.objects.create(
        user=user,
        balance=round(random.uniform(0, 100000), 2)
    )
    print(f"Đã tạo UserAccount cho {user.username} với balance: {account.balance}")

# Tạo dữ liệu ServiceUsage (15,000 bản ghi) với thời gian dàn trải
for user in users:
    if random.random() < 0.9:  # 90% khách hàng có ServiceUsage
        num_usages = random.randint(1, 3)
        for _ in range(num_usages):
            service_plan = random.choice(service_plans)
            start_date = fake.date_time_between(start_date=past_start_date, end_date=past_end_date, tzinfo=pytz.UTC)
            end_date = start_date + datetime.timedelta(days=30)
            usage = ServiceUsage.objects.create(
                user=user,
                service_plan=service_plan,
                package_name=service_plan.name,
                start_date=start_date,
                end_date=end_date,
                data_usage=round(random.uniform(0, 10), 2) if service_plan.data_volume else 0,
                remaining_data=max(0, round((service_plan.data_volume / 1024 if service_plan.data_volume else 0) - random.uniform(0, 10), 2)),
                call_minutes=round(random.uniform(0, 50), 2) if service_plan.voice_minutes else 0,
                remaining_minutes=max(0, (service_plan.voice_minutes or 0) - round(random.uniform(0, 50), 2)),
                sms_used=round(random.uniform(0, 50), 2) if service_plan.sms_count else 0,
                remaining_sms=max(0, (service_plan.sms_count or 0) - round(random.uniform(0, 50), 2)),
                spent_amount=round(random.uniform(50000, 200000), 2),
                is_active=True
            )
            print(f"Đã tạo ServiceUsage cho {user.username} với start_date: {usage.start_date}")

# Tạo dữ liệu Transaction (20,000 giao dịch)
for user in users:
    if random.random() < 0.9:  # 90% khách hàng có Transaction
        num_transactions = random.randint(1, 3)
        for _ in range(num_transactions):
            transaction = Transaction.objects.create(
                user=user,
                amount=round(random.uniform(50000, 200000), 2),
                transaction_type=random.choice(['deposit', 'withdraw']),
                description=f"Giao dịch {random.randint(1, 100)} của {user.username}",
                created_at=fake.date_time_between(start_date=past_start_date, end_date=past_end_date, tzinfo=pytz.UTC)
            )
            print(f"Đã tạo Transaction cho {user.username} với amount: {transaction.amount}")

# Tạo dữ liệu SupportTicket (5,000 yêu cầu hỗ trợ)
for user in users:
    if random.random() < 0.5:  # 50% khách hàng có SupportTicket
        num_tickets = random.randint(1, 2)
        for _ in range(num_tickets):
            ticket = SupportTicket.objects.create(
                user=user,
                subject=f"Vấn đề {random.randint(1, 100)} của {user.username}",
                description=f"Mô tả vấn đề {random.randint(1, 100)}",
                priority=random.choice(['LOW', 'MEDIUM', 'HIGH']),
                status=random.choice(['PENDING', 'RESOLVED']),
                response=f"Phản hồi {random.randint(1, 100)}" if random.random() < 0.7 else None,
                rating=random.randint(1, 5) if random.random() < 0.5 else None,
                created_at=fake.date_time_between(start_date=past_start_date, end_date=past_end_date, tzinfo=pytz.UTC),
                updated_at=fake.date_time_between(start_date=past_start_date, end_date=past_end_date, tzinfo=pytz.UTC)
            )
            print(f"Đã tạo SupportTicket cho {user.username} với subject: {ticket.subject}")

# Tạo dữ liệu FAQ (10 câu hỏi)
for i in range(10):
    faq = FAQ.objects.create(
        question=f"Câu hỏi {i+1}?",
        answer=f"Trả lời cho câu hỏi {i+1}.",
        category=random.choice(["Billing", "Technical", "Support"]),
        created_at=fake.date_time_between(start_date=past_start_date, end_date=past_end_date, tzinfo=pytz.UTC)
    )
    print(f"Đã tạo FAQ: {faq.question}")

print("Dữ liệu thử nghiệm (2020-15/05/2025) đã được tạo và nhập vào cơ sở dữ liệu MySQL.")