import sqlite3
from faker import Faker
import random
import datetime
import pytz

# Khởi tạo Faker
fake = Faker('vi_VN')
fake.seed_instance(42)

# Kết nối đến cơ sở dữ liệu SQLite
conn = sqlite3.connect('fake_telecom_data.db')
cursor = conn.cursor()

# Tạo bảng tương ứng với mô hình Django
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
past_end_date = datetime.datetime(2025, 5, 15, tzinfo=pytz.UTC)
recent_start_date = datetime.datetime(2024, 11, 16, tzinfo=pytz.UTC)  # 6 tháng trước 15/05/2025

# Tạo dữ liệu CustomUser (10,000 người dùng)
users = []
for i in range(10000):
    username = f"user{i+1}"
    email = f"user{i+1}@example.com"
    phone_number = f"090{i+1:07d}"
    date_joined = fake.date_time_between(start_date=past_start_date, end_date=past_end_date).isoformat()
    password = fake.password(length=12)
    is_superuser = 0
    is_staff = 0
    is_active = 1
    first_name = fake.first_name()
    last_name = fake.last_name()
    user = (username, email, phone_number, 1, fake.date_of_birth(minimum_age=18, maximum_age=80).isoformat(), fake.address(), date_joined, password, is_superuser, is_staff, is_active, first_name, last_name)
    users.append(user)
    if i % 1000 == 0:
        print(f"Đã tạo CustomUser: {username}")
cursor.executemany("INSERT INTO users_customuser (username, email, phone_number, is_customer, date_of_birth, address, date_joined, password, is_superuser, is_staff, is_active, first_name, last_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", users)

# Tạo dữ liệu ServicePlan (5 gói cước)
service_plans = []
plan_types = ['DATA', 'VOICE', 'COMBO', 'DATA', 'COMBO']
data_speeds = ['4G', '5G', '4G', '5G', '4G']
for i in range(5):
    name = f"Plan {i+1} - {plan_types[i]}"
    created_at_dt = fake.date_time_between(start_date=past_start_date, end_date=past_end_date)
    updated_at_dt = fake.date_time_between(start_date=created_at_dt, end_date=past_end_date)
    created_at = created_at_dt.isoformat()
    updated_at = updated_at_dt.isoformat()
    plan = (name, plan_types[i], f"Mô tả gói cước {i+1}", round(random.uniform(50000, 500000), 2), 30,
            10000 if 'DATA' in plan_types[i] else None, data_speeds[i] if 'DATA' in plan_types[i] else None,
            200 if 'VOICE' in plan_types[i] or 'COMBO' in plan_types[i] else None,
            100 if 'COMBO' in plan_types[i] else None, 1, i, created_at, updated_at)
    service_plans.append(plan)
    print(f"Đã tạo ServicePlan: {name}")
cursor.executemany("INSERT INTO services_serviceplan (name, plan_type, description, price, duration_days, data_volume, data_speed, voice_minutes, sms_count, is_active, priority, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", service_plans)

# Tạo dữ liệu ServiceUsage (đảm bảo 85% khách hàng có hoạt động gần đây)
service_usages = []
active_users = random.sample(range(10000), int(10000 * 0.85))  # 85% khách hàng có hoạt động gần đây
for user in range(10000):
    num_usages = random.randint(1, 3)
    user_id = user + 1
    has_recent_activity = user in active_users

    for _ in range(num_usages):
        service_plan_id = random.randint(1, 5)

        # Nếu khách hàng cần có hoạt động gần đây, ít nhất 1 gói cước phải nằm trong 6 tháng gần đây
        if has_recent_activity and _ == 0:
            start_date_dt = fake.date_time_between(start_date=recent_start_date, end_date=past_end_date)
        else:
            start_date_dt = fake.date_time_between(start_date=past_start_date, end_date=past_end_date)

        end_date_dt = start_date_dt + datetime.timedelta(days=30)
        start_date = start_date_dt.isoformat()
        end_date = end_date_dt.isoformat()

        service_usage = (user_id, service_plan_id, f"Plan {service_plan_id}", start_date, end_date,
                        round(random.uniform(0, 10), 2) if random.choice([True, False]) else 0,
                        round(random.uniform(0, 10), 2) if random.choice([True, False]) else 0,
                        random.randint(0, 50) if random.choice([True, False]) else 0,
                        random.randint(0, 50) if random.choice([True, False]) else 0,
                        random.randint(0, 50) if random.choice([True, False]) else 0,
                        random.randint(0, 50) if random.choice([True, False]) else 0,
                        round(random.uniform(50000, 200000), 2), 1)
        service_usages.append(service_usage)
        print(f"Đã tạo ServiceUsage cho user_id: {user_id} với start_date: {start_date}")

cursor.executemany("INSERT INTO services_serviceusage (user_id, service_plan_id, package_name, start_date, end_date, data_usage, remaining_data, call_minutes, remaining_minutes, sms_used, remaining_sms, spent_amount, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", service_usages)

# Tạo dữ liệu SupportTicket (5,000 bản ghi)
support_tickets = []
for user in range(10000):
    if random.random() < 0.5:  # 50% khách hàng có SupportTicket
        num_tickets = random.randint(1, 2)
        for _ in range(num_tickets):
            user_id = user + 1
            created_at_dt = fake.date_time_between(start_date=past_start_date, end_date=past_end_date)
            updated_at_dt = fake.date_time_between(start_date=created_at_dt, end_date=past_end_date)
            created_at = created_at_dt.isoformat()
            updated_at = updated_at_dt.isoformat()
            support_ticket = (user_id, f"Vấn đề {random.randint(1, 100)}", f"Mô tả {random.randint(1, 100)}",
                            random.choice(['LOW', 'MEDIUM', 'HIGH']), random.choice(['PENDING', 'RESOLVED']),
                            f"Phản hồi {random.randint(1, 100)}" if random.random() < 0.7 else None,
                            random.randint(1, 5) if random.random() < 0.5 else None, created_at, updated_at)
            support_tickets.append(support_ticket)
            print(f"Đã tạo SupportTicket cho user_id: {user_id}")
cursor.executemany("INSERT INTO support_supportticket (user_id, subject, description, priority, status, response, rating, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", support_tickets)

# Lưu thay đổi và đóng kết nối
conn.commit()
conn.close()
print("Dữ liệu thử nghiệm đã được tạo trong fake_telecom_data.db")