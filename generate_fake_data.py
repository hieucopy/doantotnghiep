import sqlite3
from faker import Faker
import random
import datetime
import pytz
import numpy as np

# Khởi tạo Faker và seed để đảm bảo tái tạo dữ liệu
fake = Faker('vi_VN')
fake.seed_instance(42)
np.random.seed(42)

# Kết nối đến cơ sở dữ liệu SQLite
conn = sqlite3.connect('fake_telecom_data.db')
cursor = conn.cursor()

# Tạo bảng (giữ nguyên cấu trúc gốc)
cursor.executescript("""
    DROP TABLE IF EXISTS users_customuser;
    CREATE TABLE users_customuser (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        email TEXT NOT NULL,
        phone_number TEXT NOT NULL,
        is_customer INTEGER NOT NULL,
        date_of_birth TEXT,
        address TEXT,
        date_joined TEXT,
        password TEXT NOT NULL,
        is_superuser INTEGER NOT NULL,
        is_staff INTEGER NOT NULL,
        is_active INTEGER NOT NULL,
        first_name TEXT,
        last_name TEXT
    );

    DROP TABLE IF EXISTS services_serviceplan;
    CREATE TABLE services_serviceplan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        plan_type TEXT NOT NULL,
        description TEXT,
        price REAL,
        duration_days INTEGER,
        data_volume INTEGER,
        data_speed TEXT,
        voice_minutes INTEGER,
        sms_count INTEGER,
        is_active INTEGER NOT NULL,
        priority INTEGER,
        created_at TEXT,
        updated_at TEXT
    );

    DROP TABLE IF EXISTS services_serviceusage;
    CREATE TABLE services_serviceusage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        service_plan_id INTEGER,
        package_name TEXT,
        start_date TEXT,
        end_date TEXT,
        data_usage REAL,
        remaining_data REAL,
        call_minutes INTEGER,
        remaining_minutes INTEGER,
        sms_used INTEGER,
        remaining_sms INTEGER,
        spent_amount REAL,
        is_active INTEGER NOT NULL
    );

    DROP TABLE IF EXISTS support_supportticket;
    CREATE TABLE support_supportticket (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        subject TEXT,
        description TEXT,
        priority TEXT,
        status TEXT,
        response TEXT,
        rating INTEGER,
        created_at TEXT,
        updated_at TEXT
    );
""")

# Định nghĩa khoảng thời gian
past_start_date = datetime.datetime(2020, 1, 1, tzinfo=pytz.UTC)
current_date = datetime.datetime(2025, 6, 1, tzinfo=pytz.UTC)
churn_start_date = datetime.datetime(2025, 1, 1, tzinfo=pytz.UTC)  # Bắt đầu tính tỷ lệ churn từ 01/2025

# Hàm xác định trạng thái rời bỏ
def assign_churn_status(date_joined):
    # Đảm bảo date_joined là offset-aware
    if date_joined.tzinfo is None:
        date_joined = date_joined.replace(tzinfo=pytz.UTC)
    days_since_joined = (current_date - date_joined).days
    if days_since_joined < 0:
        return False, current_date
    # Tỷ lệ rời bỏ tăng tuyến tính từ 15% (trước 01/2025) đến 30% (hiện tại)
    if date_joined < churn_start_date:
        churn_prob = 0.15
    else:
        days_since_churn_start = (current_date - date_joined).days / (current_date - churn_start_date).days
        churn_prob = 0.15 + (0.30 - 0.15) * days_since_churn_start
    is_churned = random.random() < churn_prob
    # Nếu rời bỏ, chọn ngẫu nhiên thời điểm rời bỏ từ max(date_joined, churn_start_date) đến current_date
    churn_threshold = fake.date_time_between(start_date=max(date_joined, churn_start_date), end_date=current_date)
    # Đảm bảo churn_threshold là offset-aware
    if churn_threshold.tzinfo is None:
        churn_threshold = churn_threshold.replace(tzinfo=pytz.UTC)
    return is_churned, churn_threshold

# Tạo dữ liệu CustomUser (10,000 người dùng)
users = []
for i in range(10000):
    username = f"user{i+1}"
    email = f"user{i+1}@example.com"
    phone_number = f"090{i+1:07d}"
    date_joined_dt = fake.date_time_between(start_date=past_start_date, end_date=current_date)
    date_joined = date_joined_dt.isoformat()
    password = fake.password(length=12)
    is_superuser = 0
    is_staff = 0
    is_active = 1
    first_name = fake.first_name()
    last_name = fake.last_name()
    user = (username, email, phone_number, 1, fake.date_of_birth(minimum_age=18, maximum_age=80).isoformat(),
            fake.address(), date_joined, password, is_superuser, is_staff, is_active, first_name, last_name)
    users.append(user)
    if i % 1000 == 0:
        print(f"Đã tạo CustomUser: {username}")
cursor.executemany("INSERT INTO users_customuser (username, email, phone_number, is_customer, date_of_birth, address, date_joined, password, is_superuser, is_staff, is_active, first_name, last_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", users)

# Tạo dữ liệu ServicePlan (20 gói cước)
service_plans = []
plan_types = ['DATA'] * 8 + ['VOICE'] * 6 + ['COMBO'] * 6
data_speeds = ['4G', '5G'] * 10
for i in range(20):
    name = f"Plan {i+1} - {plan_types[i]}"
    created_at_dt = fake.date_time_between(start_date=past_start_date, end_date=current_date)
    updated_at_dt = fake.date_time_between(start_date=created_at_dt, end_date=current_date)
    created_at = created_at_dt.isoformat()
    updated_at = updated_at_dt.isoformat()
    duration_days = random.choice([7, 30, 90])  # Gói 7 ngày, 30 ngày, hoặc 90 ngày
    plan = (name, plan_types[i], f"Mô tả gói cước {i+1}", round(random.uniform(30000, 1000000), 2), duration_days,
            random.randint(5000, 50000) if 'DATA' in plan_types[i] else None,
            data_speeds[i] if 'DATA' in plan_types[i] else None,
            random.randint(100, 1000) if 'VOICE' in plan_types[i] or 'COMBO' in plan_types[i] else None,
            random.randint(50, 500) if 'COMBO' in plan_types[i] else None, 1, i, created_at, updated_at)
    service_plans.append(plan)
    print(f"Đã tạo ServicePlan: {name}")
cursor.executemany("INSERT INTO services_serviceplan (name, plan_type, description, price, duration_days, data_volume, data_speed, voice_minutes, sms_count, is_active, priority, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", service_plans)

# Tạo dữ liệu ServiceUsage (trung bình 8 gói cước mỗi người)
service_usages = []
for user in range(10000):
    user_id = user + 1
    date_joined_dt = datetime.datetime.fromisoformat(users[user][6])  # Lấy date_joined từ vị trí 6
    if date_joined_dt.tzinfo is None:
        date_joined_dt = date_joined_dt.replace(tzinfo=pytz.UTC)
    is_churned, churn_threshold = assign_churn_status(date_joined_dt)
    # Số lượng gói cước theo phân phối Poisson, trung bình 8
    num_usages = max(1, np.random.poisson(8))
    
    for _ in range(num_usages):
        service_plan_id = random.randint(1, 20)
        duration_days = service_plans[service_plan_id - 1][4]
        # Phân bổ từ date_joined đến churn_threshold hoặc current_date
        start_date_dt = fake.date_time_between(start_date=date_joined_dt, end_date=churn_threshold if is_churned else current_date)
        if start_date_dt.tzinfo is None:
            start_date_dt = start_date_dt.replace(tzinfo=pytz.UTC)
        end_date_dt = start_date_dt + datetime.timedelta(days=duration_days)
        if is_churned:
            end_date_dt = min(end_date_dt, churn_threshold)
        if end_date_dt.tzinfo is None:
            end_date_dt = end_date_dt.replace(tzinfo=pytz.UTC)
        start_date = start_date_dt.isoformat()
        end_date = end_date_dt.isoformat()
        
        data_volume = service_plans[service_plan_id - 1][5] or 0
        voice_minutes = service_plans[service_plan_id - 1][7] or 0
        sms_count = service_plans[service_plan_id - 1][8] or 0
        price = service_plans[service_plan_id - 1][3]
        # Khách hàng rời bỏ có xu hướng sử dụng ít tài nguyên hơn
        usage_factor = 0.5 if is_churned else 0.8
        service_usage = (user_id, service_plan_id, f"Plan {service_plan_id}", start_date, end_date,
                        round(random.uniform(0, data_volume * usage_factor), 2) if data_volume else 0,
                        round(random.uniform(0, data_volume * (1 - usage_factor)), 2) if data_volume else 0,
                        random.randint(0, int(voice_minutes * usage_factor)) if voice_minutes else 0,
                        random.randint(0, int(voice_minutes * (1 - usage_factor))) if voice_minutes else 0,
                        random.randint(0, int(sms_count * usage_factor)) if sms_count else 0,
                        random.randint(0, int(sms_count * (1 - usage_factor))) if sms_count else 0,
                        round(random.uniform(price * 0.5, price * 1.2), 2), 1 if end_date_dt > current_date else 0)
        service_usages.append(service_usage)
        print(f"Đã tạo ServiceUsage cho user_id: {user_id} với start_date: {start_date}")

cursor.executemany("INSERT INTO services_serviceusage (user_id, service_plan_id, package_name, start_date, end_date, data_usage, remaining_data, call_minutes, remaining_minutes, sms_used, remaining_sms, spent_amount, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", service_usages)

# Tạo dữ liệu SupportTicket (khoảng 10,000 bản ghi)
support_tickets = []
for user in range(10000):
    user_id = user + 1
    date_joined_dt = datetime.datetime.fromisoformat(users[user][6])  # Lấy date_joined từ vị trí 6
    if date_joined_dt.tzinfo is None:
        date_joined_dt = date_joined_dt.replace(tzinfo=pytz.UTC)
    is_churned, churn_threshold = assign_churn_status(date_joined_dt)
    # Khách hàng rời bỏ có xác suất tạo vé cao hơn
    num_tickets = random.randint(1, 3) if is_churned else random.randint(0, 2)
    for _ in range(num_tickets):
        created_at_dt = fake.date_time_between(start_date=date_joined_dt, end_date=churn_threshold if is_churned else current_date)
        if created_at_dt.tzinfo is None:
            created_at_dt = created_at_dt.replace(tzinfo=pytz.UTC)
        updated_at_dt = fake.date_time_between(start_date=created_at_dt, end_date=churn_threshold if is_churned else current_date)
        if updated_at_dt.tzinfo is None:
            updated_at_dt = updated_at_dt.replace(tzinfo=pytz.UTC)
        created_at = created_at_dt.isoformat()
        updated_at = updated_at_dt.isoformat()
        # Khách hàng rời bỏ có xu hướng để vé ở trạng thái PENDING
        status = random.choice(['PENDING', 'RESOLVED']) if not is_churned else random.choices(['PENDING', 'RESOLVED'], weights=[0.7, 0.3])[0]
        support_ticket = (user_id, f"Vấn đề {random.randint(1, 100)}", f"Mô tả {random.randint(1, 100)}",
                         random.choice(['LOW', 'MEDIUM', 'HIGH']), status,
                         f"Phản hồi {random.randint(1, 100)}" if status == 'RESOLVED' else None,
                         random.randint(1, 5) if status == 'RESOLVED' and random.random() < 0.5 else None,
                         created_at, updated_at)
        support_tickets.append(support_ticket)
        print(f"Đã tạo SupportTicket cho user_id: {user_id}")
cursor.executemany("INSERT INTO support_supportticket (user_id, subject, description, priority, status, response, rating, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", support_tickets)

# Lưu thay đổi và đóng kết nối
conn.commit()
conn.close()
print("Dữ liệu thử nghiệm đã được tạo trong fake_telecom_data.db")