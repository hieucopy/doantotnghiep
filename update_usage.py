import pandas as pd
from sqlalchemy import create_engine, text
import random
from datetime import datetime, timedelta
import pytz

# Kết nối với MySQL
engine = create_engine('mysql+pymysql://root:hieu@localhost/my_telecom_db')

# Hàm mô tả việc sử dụng dữ liệu, cuộc gọi và tin nhắn
def describe_usage():
    try:
        # Trích xuất dữ liệu từ services_serviceusage
        service_usages = pd.read_sql("SELECT user_id, data_usage, call_minutes, sms_used FROM services_serviceusage WHERE start_date IS NOT NULL", engine)
        print(f"Đã trích xuất {len(service_usages)} bản ghi từ services_serviceusage")

        # Thay thế NULL bằng 0
        service_usages['data_usage'] = service_usages['data_usage'].fillna(0)
        service_usages['call_minutes'] = service_usages['call_minutes'].fillna(0)
        service_usages['sms_used'] = service_usages['sms_used'].fillna(0)

        # Tính tổng và trung bình sử dụng cho mỗi user_id
        usage_summary = service_usages.groupby('user_id').agg({
            'data_usage': ['sum', 'mean'],
            'call_minutes': ['sum', 'mean'],
            'sms_used': ['sum', 'mean']
        }).reset_index()

        # Đổi tên cột cho dễ đọc
        usage_summary.columns = ['user_id', 'total_data_usage (GB)', 'avg_data_usage (GB)', 
                                 'total_call_minutes', 'avg_call_minutes', 
                                 'total_sms_used', 'avg_sms_used']

        # Làm tròn các giá trị
        usage_summary = usage_summary.round(2)

        print("\nThống kê sử dụng dữ liệu, cuộc gọi và tin nhắn:")
        print(usage_summary)

        # Lưu thống kê vào file CSV
        usage_summary.to_csv('usage_summary.csv', index=False)
        print("Thống kê đã được lưu vào usage_summary.csv")

    except Exception as e:
        print(f"Lỗi khi mô tả việc sử dụng: {e}")

# Hàm cập nhật dữ liệu sử dụng
def update_usage(user_id, data_used=0, minutes_called=0, sms_sent=0):
    try:
        # Lấy bản ghi gói cước gần đây nhất của user_id
        query = f"""
        SELECT id, data_usage, call_minutes, sms_used, start_date, end_date 
        FROM services_serviceusage 
        WHERE user_id = {user_id} AND start_date IS NOT NULL 
        ORDER BY start_date DESC LIMIT 1
        """
        latest_usage = pd.read_sql(query, engine)

        if latest_usage.empty:
            print(f"Không tìm thấy gói cước nào cho user_id = {user_id}")
            return

        # Lấy thông tin gói cước gần đây nhất
        record_id = latest_usage.iloc[0]['id']
        current_data_usage = latest_usage.iloc[0]['data_usage'] or 0
        current_call_minutes = latest_usage.iloc[0]['call_minutes'] or 0
        current_sms_used = latest_usage.iloc[0]['sms_used'] or 0
        start_date = pd.to_datetime(latest_usage.iloc[0]['start_date'], utc=True)
        end_date = pd.to_datetime(latest_usage.iloc[0]['end_date'], utc=True)

        # Kiểm tra xem gói cước có còn hiệu lực không
        current_time = pd.to_datetime(datetime.now(), utc=True)
        if current_time < start_date or current_time > end_date:
            print(f"Gói cước của user_id = {user_id} không còn hiệu lực (start_date: {start_date}, end_date: {end_date})")
            return

        # Cập nhật giá trị
        new_data_usage = current_data_usage + data_used
        new_call_minutes = current_call_minutes + minutes_called
        new_sms_used = current_sms_used + sms_sent

        # Cập nhật vào cơ sở dữ liệu với tham số hóa
        update_query = text(
            "UPDATE services_serviceusage SET data_usage = :data_usage, call_minutes = :call_minutes, sms_used = :sms_used WHERE id = :record_id"
        )
        with engine.connect() as connection:
            connection.execute(
                update_query,
                {
                    "data_usage": new_data_usage,
                    "call_minutes": new_call_minutes,
                    "sms_used": new_sms_used,
                    "record_id": record_id
                }
            )
            connection.commit()

        print(f"Đã cập nhật sử dụng cho user_id = {user_id}:")
        print(f"- Data usage: {current_data_usage} -> {new_data_usage} GB")
        print(f"- Call minutes: {current_call_minutes} -> {new_call_minutes} phút")
        print(f"- SMS used: {current_sms_used} -> {new_sms_used} tin nhắn")

    except Exception as e:
        print(f"Lỗi khi cập nhật dữ liệu sử dụng cho user_id = {user_id}: {e}")

# Hàm giả lập hoạt động sử dụng
def simulate_usage(user_id, data_used=None, minutes_called=None, sms_sent=None):
    # Nếu không truyền tham số, tạo giá trị ngẫu nhiên
    if data_used is None:
        data_used = round(random.uniform(0.1, 5.0), 2)  # Sử dụng 0.1-5 GB
    if minutes_called is None:
        minutes_called = random.randint(0, 30)  # Gọi 0-30 phút
    if sms_sent is None:
        sms_sent = random.randint(0, 20)  # Gửi 0-20 tin nhắn

    print(f"\nHoạt động cho user_id = {user_id}:")
    print(f"- Sử dụng dữ liệu: {data_used} GB")
    print(f"- Gọi: {minutes_called} phút")
    print(f"- Nhắn tin: {sms_sent} tin nhắn")

    update_usage(user_id, data_used, minutes_called, sms_sent)

# Chạy chương trình
if __name__ == "__main__":
    # 1. Mô tả việc sử dụng
    describe_usage()

    # 2. Giả lập và cập nhật dữ liệu sử dụng (ví dụ cho user_id = 10001)
    user_id_to_update = 10001
    simulate_usage(user_id_to_update, data_used=5, minutes_called=0, sms_sent=0)

    # 3. Mô tả lại sau khi cập nhật
    print("\nSau khi cập nhật:")
    describe_usage()