from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone
from datetime import datetime, timedelta
import random
import pytz

class Command(BaseCommand):
    help = 'Tạo thêm dữ liệu churn có ý nghĩa vào database'

    def add_arguments(self, parser):
        parser.add_argument('--num_churn', type=int, default=1000,
                          help='Số lượng khách hàng churn cần tạo')

    def handle(self, *args, **options):
        num_churn = options['num_churn']
        self.stdout.write(f"Bắt đầu tạo {num_churn} khách hàng churn...")

        # Lấy danh sách khách hàng hiện tại
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT u.id, u.date_joined, u.last_login,
                       COUNT(DISTINCT su.id) as num_service_plans,
                       AVG(su.spent_amount) as avg_spent,
                       AVG(st.rating) as avg_rating,
                       COUNT(DISTINCT st.id) as num_tickets
                FROM users_customuser u
                LEFT JOIN services_serviceusage su ON u.id = su.user_id
                LEFT JOIN support_supportticket st ON u.id = st.user_id
                WHERE u.id NOT IN (
                    SELECT user_id 
                    FROM churn_prediction_churnprediction 
                    WHERE churn_probability > 0.7
                )
                GROUP BY u.id, u.date_joined, u.last_login
                HAVING COUNT(DISTINCT su.id) > 0
            """)
            users = cursor.fetchall()

        if not users:
            self.stdout.write(self.style.ERROR("Không tìm thấy khách hàng phù hợp để tạo dữ liệu churn"))
            return

        # Chọn ngẫu nhiên num_churn khách hàng
        selected_users = random.sample(users, min(num_churn, len(users)))
        
        # Tạo dữ liệu churn cho các khách hàng được chọn
        current_time = timezone.now()
        churn_date = current_time - timedelta(days=random.randint(30, 90))  # Churn từ 1-3 tháng trước
        
        for user in selected_users:
            user_id, date_joined, last_login, num_plans, avg_spent, avg_rating, num_tickets = user
            
            # Cập nhật last_login để tạo dấu hiệu churn
            new_last_login = churn_date - timedelta(days=random.randint(60, 180))  # Không đăng nhập từ 2-6 tháng
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE users_customuser 
                    SET last_login = %s 
                    WHERE id = %s
                """, [new_last_login, user_id])

            # Tạo service usage giảm dần trong 3 tháng trước khi churn
            for i in range(3):
                usage_date = churn_date - timedelta(days=30 * (i + 1))
                spent_amount = float(avg_spent) * (1 - (i + 1) * 0.2) if avg_spent else random.uniform(50, 200)
                data_usage = random.uniform(1, 5) * (1 - (i + 1) * 0.2)
                call_minutes = random.uniform(30, 120) * (1 - (i + 1) * 0.2)
                sms_used = random.randint(10, 50) * (1 - (i + 1) * 0.2)
                with connection.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO services_serviceusage 
                        (user_id, service_plan_id, start_date, end_date, data_usage, 
                         call_minutes, sms_used, spent_amount, package_name, remaining_data, 
                         remaining_minutes, remaining_sms, is_active)
                        SELECT %s, sp.id, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        FROM services_serviceplan sp
                        ORDER BY RAND()
                        LIMIT 1
                    """, [user_id, usage_date, usage_date + timedelta(days=30),
                          data_usage, call_minutes, sms_used, spent_amount, "Churn_Package", 
                          data_usage, call_minutes, sms_used, 1])

            # Tạo một số ticket hỗ trợ với rating thấp
            num_new_tickets = random.randint(1, 3)
            for _ in range(num_new_tickets):
                ticket_date = churn_date - timedelta(days=random.randint(1, 30))
                rating = random.uniform(1, 3)  # Rating thấp
                with connection.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO support_supportticket 
                        (user_id, subject, description, status, created_at, updated_at, rating, priority)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, [user_id, f"Vấn đề dịch vụ {random.randint(1, 100)}",
                          "Không hài lòng với chất lượng dịch vụ", 'CLOSED',
                          ticket_date, ticket_date, rating, "MEDIUM"])

        self.stdout.write(self.style.SUCCESS(
            f"Đã tạo thành công dữ liệu churn cho {len(selected_users)} khách hàng"
        )) 