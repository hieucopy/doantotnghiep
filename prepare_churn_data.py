import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime
import pytz

# Kết nối với MySQL
engine = create_engine('mysql+pymysql://root:hieu@localhost/my_telecom_db')

# Trích xuất dữ liệu và kiểm tra
try:
    users = pd.read_sql("SELECT id, date_joined FROM users_customuser", engine)
    print(f"Đã trích xuất {len(users)} bản ghi từ users_customuser")
    if 'date_joined' not in users.columns:
        raise ValueError("Cột 'date_joined' không tồn tại trong users_customuser")
except Exception as e:
    print(f"Lỗi khi trích xuất users_customuser: {e}")
    users = pd.DataFrame(columns=['id', 'date_joined'])

try:
    service_usages = pd.read_sql("SELECT user_id, service_plan_id, start_date, data_usage, call_minutes, sms_used, spent_amount FROM services_serviceusage", engine)
    print(f"Đã trích xuất {len(service_usages)} bản ghi từ services_serviceusage")
    required_columns = ['user_id', 'start_date', 'data_usage', 'call_minutes', 'sms_used', 'spent_amount']
    missing_cols = [col for col in required_columns if col not in service_usages.columns]
    if missing_cols:
        raise ValueError(f"Các cột thiếu trong services_serviceusage: {missing_cols}")
except Exception as e:
    print(f"Lỗi khi trích xuất services_serviceusage: {e}")
    service_usages = pd.DataFrame(columns=['user_id', 'service_plan_id', 'start_date', 'data_usage', 'call_minutes', 'sms_used', 'spent_amount'])

try:
    support_tickets = pd.read_sql("SELECT user_id, rating FROM support_supportticket", engine)
    print(f"Đã trích xuất {len(support_tickets)} bản ghi từ support_supportticket")
    if 'rating' not in support_tickets.columns:
        raise ValueError("Cột 'rating' không tồn tại trong support_supportticket")
except Exception as e:
    print(f"Lỗi khi trích xuất support_supportticket: {e}")
    support_tickets = pd.DataFrame(columns=['user_id', 'rating'])

# Đảm bảo các cột datetime đều là tz-aware (UTC)
if not users.empty and 'date_joined' in users.columns:
    users['date_joined'] = pd.to_datetime(users['date_joined'], utc=True)
if not service_usages.empty and 'start_date' in service_usages.columns:
    # Đảm bảo start_date là tz-aware UTC
    service_usages['start_date'] = pd.to_datetime(service_usages['start_date'], utc=True, errors='coerce')

# Định nghĩa ngày kết thúc dữ liệu và ngày cắt (cut-off date) để kiểm tra rời bỏ
current_date = pd.to_datetime("2025-05-17 23:59:59", utc=True)  # Ngày hiện tại, bao gồm cả cuối ngày
end_date = current_date  # Sử dụng ngày hiện tại làm end_date
cutoff_date = pd.to_datetime("2024-11-17 00:00:00", utc=True)  # 6 tháng trước 17/05/2025

# Tạo đặc trưng
features = pd.DataFrame(users['id']).rename(columns={'id': 'user_id'})

# 1. Số tháng từ ngày lập tài khoản
if not users.empty and 'date_joined' in users.columns:
    features = features.merge(users[['id', 'date_joined']], left_on='user_id', right_on='id', how='left')
    features['months_since_joined'] = ((end_date - features['date_joined']).dt.days / 30.42).round(2)
    # Đảm bảo không có giá trị âm
    features['months_since_joined'] = features['months_since_joined'].clip(lower=0)
    features = features.drop(columns=['id', 'date_joined'])
else:
    print("Không thể tính months_since_joined do thiếu dữ liệu từ users_customuser")
    features['months_since_joined'] = 0

# 2. Số gói cước đã đăng ký (chỉ đếm các bản ghi có start_date hợp lệ)
if not service_usages.empty:
    # Lọc các bản ghi có start_date không phải NULL
    valid_service_usages = service_usages.dropna(subset=['start_date'])
    # Sử dụng merge để khớp chính xác user_id
    features = features.merge(valid_service_usages.groupby('user_id').size().reset_index(name='num_service_plans'), on='user_id', how='left').fillna({'num_service_plans': 0})
else:
    print("Không thể tính num_service_plans do thiếu dữ liệu từ services_serviceusage")
    features['num_service_plans'] = 0

# 3. Số tiền đã chi trả
if not service_usages.empty and 'spent_amount' in service_usages.columns:
    # Thay thế NULL bằng 0 trước khi tính tổng
    service_usages['spent_amount'] = service_usages['spent_amount'].fillna(0)
    features = features.merge(service_usages.groupby('user_id')['spent_amount'].sum().reset_index(name='total_spent'), on='user_id', how='left').fillna({'total_spent': 0})
else:
    print("Không thể tính total_spent do thiếu dữ liệu hoặc cột spent_amount không tồn tại")
    features['total_spent'] = 0

# 4. Tổng số data từ các gói cước
if not service_usages.empty and 'data_usage' in service_usages.columns:
    # Thay thế NULL bằng 0 trước khi tính tổng
    service_usages['data_usage'] = service_usages['data_usage'].fillna(0)
    features = features.merge(service_usages.groupby('user_id')['data_usage'].sum().reset_index(name='total_data_usage'), on='user_id', how='left').fillna({'total_data_usage': 0})
else:
    print("Không thể tính total_data_usage do thiếu dữ liệu hoặc cột data_usage không tồn tại")
    features['total_data_usage'] = 0

# 5. Tổng số cuộc gọi từ các gói cước
if not service_usages.empty and 'call_minutes' in service_usages.columns:
    # Thay thế NULL bằng 0 trước khi tính tổng
    service_usages['call_minutes'] = service_usages['call_minutes'].fillna(0)
    features = features.merge(service_usages.groupby('user_id')['call_minutes'].sum().reset_index(name='total_call_minutes'), on='user_id', how='left').fillna({'total_call_minutes': 0})
else:
    print("Không thể tính total_call_minutes do thiếu dữ liệu hoặc cột call_minutes không tồn tại")
    features['total_call_minutes'] = 0

# 6. Tổng số tin nhắn từ các gói cước
if not service_usages.empty and 'sms_used' in service_usages.columns:
    # Thay thế NULL bằng 0 trước khi tính tổng
    service_usages['sms_used'] = service_usages['sms_used'].fillna(0)
    features = features.merge(service_usages.groupby('user_id')['sms_used'].sum().reset_index(name='total_sms_used'), on='user_id', how='left').fillna({'total_sms_used': 0})
else:
    print("Không thể tính total_sms_used do thiếu dữ liệu hoặc cột sms_used không tồn tại")
    features['total_sms_used'] = 0

# 7. Số lần gửi yêu cầu hỗ trợ
if not support_tickets.empty:
    features = features.merge(support_tickets.groupby('user_id').size().reset_index(name='num_support_tickets'), on='user_id', how='left').fillna({'num_support_tickets': 0})
else:
    print("Không thể tính num_support_tickets do thiếu dữ liệu từ support_supportticket")
    features['num_support_tickets'] = 0

# 8. Điểm đánh giá trung bình từ các lần hỗ trợ
if not support_tickets.empty and 'rating' in support_tickets.columns:
    # Thay thế NULL bằng 0 trước khi tính trung bình
    support_tickets['rating'] = support_tickets['rating'].fillna(0)
    features = features.merge(support_tickets.groupby('user_id')['rating'].mean().reset_index(name='avg_rating'), on='user_id', how='left').fillna({'avg_rating': 0})
else:
    print("Không thể tính avg_rating do thiếu dữ liệu hoặc cột rating không tồn tại")
    features['avg_rating'] = 0

# Kiểm tra hoạt động gần đây (ServiceUsage từ 17/11/2024 đến 17/05/2025)
if not service_usages.empty and 'start_date' in service_usages.columns:
    # Kiểm tra dữ liệu trước khi lọc
    print("Trước khi lọc, số bản ghi trong service_usages:", len(service_usages))
    print("Số bản ghi có start_date không NULL:", len(service_usages.dropna(subset=['start_date'])))
    
    recent_service_usages = service_usages[(service_usages['start_date'] >= cutoff_date) & (service_usages['start_date'] <= end_date)]
    print(f"Số bản ghi trong recent_service_usages: {len(recent_service_usages)}")
    print(f"Số khách hàng có hoạt động gần đây: {len(recent_service_usages['user_id'].unique())}")
    print(f"Tổng số khách hàng: {len(features)}")

    # Tạo cột chỉ báo hoạt động gần đây
    features['has_recent_service_usage'] = features['user_id'].isin(recent_service_usages['user_id']).astype(int)

    # Định nghĩa nhãn rời bỏ: không sử dụng dịch vụ trong 6 tháng gần đây
    features['churned'] = (features['has_recent_service_usage'] == 0).astype(int)

    # Xóa cột tạm
    features = features.drop(columns=['has_recent_service_usage'])
else:
    print("Không thể tính nhãn rời bỏ do thiếu dữ liệu từ services_serviceusage")
    features['churned'] = 0

# Lưu dữ liệu để huấn luyện
features.to_csv('churn_data.csv', index=False)
print("Dữ liệu đã được lưu vào churn_data.csv")
print(f"Tỉ lệ rời bỏ: {features['churned'].mean():.2%}")