import os
import django
from django.db import connections
from django.utils import timezone
import sqlite3
import datetime
import pytz

# Thiết lập môi trường Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_telecom.settings')  # Thay nếu cần
django.setup()

# Kết nối đến cơ sở dữ liệu SQLite
sqlite_conn = sqlite3.connect('fake_telecom_data.db')
sqlite_cursor = sqlite_conn.cursor()

# Kết nối đến cơ sở dữ liệu MySQL của Django
mysql_conn = connections['default']
mysql_cursor = mysql_conn.cursor()

# Xóa dữ liệu cũ trong các bảng
mysql_cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
mysql_cursor.execute("TRUNCATE TABLE support_supportticket;")
mysql_cursor.execute("TRUNCATE TABLE services_serviceusage;")
mysql_cursor.execute("TRUNCATE TABLE services_serviceplan;")
mysql_cursor.execute("TRUNCATE TABLE users_customuser;")
mysql_cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

# Hàm xử lý thời gian
def parse_datetime(dt_str):
    dt = datetime.datetime.fromisoformat(dt_str.replace('Z', '+00:00'))  # Xử lý định dạng 'Z'
    if dt.tzinfo is None:
        return timezone.make_aware(dt, timezone=pytz.UTC)
    return dt

# Nhập dữ liệu từ users_customuser
sqlite_cursor.execute("SELECT username, email, phone_number, is_customer, date_of_birth, address, date_joined, password, is_superuser, is_staff, is_active, first_name, last_name FROM users_customuser")
for row in sqlite_cursor.fetchall():
    username, email, phone_number, is_customer, date_of_birth, address, date_joined, password, is_superuser, is_staff, is_active, first_name, last_name = row
    date_joined_dt = parse_datetime(date_joined)
    mysql_cursor.execute(
        "INSERT INTO users_customuser (username, email, phone_number, is_customer, date_of_birth, address, date_joined, password, is_superuser, is_staff, is_active, first_name, last_name) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE date_joined=VALUES(date_joined), password=VALUES(password), is_superuser=VALUES(is_superuser), is_staff=VALUES(is_staff), is_active=VALUES(is_active), first_name=VALUES(first_name), last_name=VALUES(last_name)",
        [username, email, phone_number, is_customer, date_of_birth, address, date_joined_dt, password, is_superuser, is_staff, is_active, first_name, last_name]
    )

# Nhập dữ liệu từ services_serviceplan
sqlite_cursor.execute("SELECT id, name, plan_type, description, price, duration_days, data_volume, data_speed, voice_minutes, sms_count, is_active, priority, created_at, updated_at FROM services_serviceplan")
for row in sqlite_cursor.fetchall():
    id, name, plan_type, description, price, duration_days, data_volume, data_speed, voice_minutes, sms_count, is_active, priority, created_at, updated_at = row
    created_at_dt = parse_datetime(created_at)
    updated_at_dt = parse_datetime(updated_at)
    mysql_cursor.execute(
        "INSERT INTO services_serviceplan (id, name, plan_type, description, price, duration_days, data_volume, data_speed, voice_minutes, sms_count, is_active, priority, created_at, updated_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE created_at=VALUES(created_at), updated_at=VALUES(updated_at)",
        [id, name, plan_type, description, price, duration_days, data_volume, data_speed, voice_minutes, sms_count, is_active, priority, created_at_dt, updated_at_dt]
    )

# Nhập dữ liệu từ services_serviceusage
sqlite_cursor.execute("SELECT user_id, service_plan_id, package_name, start_date, end_date, data_usage, remaining_data, call_minutes, remaining_minutes, sms_used, remaining_sms, spent_amount, is_active FROM services_serviceusage")
for row in sqlite_cursor.fetchall():
    user_id, service_plan_id, package_name, start_date, end_date, data_usage, remaining_data, call_minutes, remaining_minutes, sms_used, remaining_sms, spent_amount, is_active = row
    start_date_dt = parse_datetime(start_date)
    end_date_dt = parse_datetime(end_date)
    mysql_cursor.execute(
        "INSERT INTO services_serviceusage (user_id, service_plan_id, package_name, start_date, end_date, data_usage, remaining_data, call_minutes, remaining_minutes, sms_used, remaining_sms, spent_amount, is_active) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE start_date=VALUES(start_date), end_date=VALUES(end_date)",
        [user_id, service_plan_id, package_name, start_date_dt, end_date_dt, data_usage, remaining_data, call_minutes, remaining_minutes, sms_used, remaining_sms, spent_amount, is_active]
    )

# Nhập dữ liệu từ support_supportticket
sqlite_cursor.execute("SELECT user_id, subject, description, priority, status, response, rating, created_at, updated_at FROM support_supportticket")
for row in sqlite_cursor.fetchall():
    user_id, subject, description, priority, status, response, rating, created_at, updated_at = row
    created_at_dt = parse_datetime(created_at)
    updated_at_dt = parse_datetime(updated_at)
    mysql_cursor.execute(
        "INSERT INTO support_supportticket (user_id, subject, description, priority, status, response, rating, created_at, updated_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE created_at=VALUES(created_at), updated_at=VALUES(updated_at)",
        [user_id, subject, description, priority, status, response, rating, created_at_dt, updated_at_dt]
    )

# Lưu thay đổi và đóng kết nối
mysql_conn.commit()
sqlite_conn.close()
mysql_conn.close()
print("Dữ liệu đã được nhập vào cơ sở dữ liệu Django.")