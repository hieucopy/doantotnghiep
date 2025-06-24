from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

class ServicePlan(models.Model):
    PLAN_TYPES = (
        ('DATA', 'Data'),
        ('VOICE', 'Thoại'),
        ('SMS', 'SMS'),
        ('COMBO', 'Combo'),
    )

    DATA_SPEEDS = (
        ('3G', '3G'),
        ('4G', '4G'),
        ('5G', '5G'),
    )

    name = models.CharField(max_length=100, unique=True)  # Tên gói cước (VD: "4G 30GB")
    plan_type = models.CharField(max_length=5, choices=PLAN_TYPES)  # Loại gói
    description = models.TextField()  # Mô tả chi tiết
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(0)],  # Giá không âm
    )  # Giá (VNĐ)
    duration_days = models.IntegerField(
        validators=[MinValueValidator(1)],  # Thời hạn ít nhất 1 ngày
    )  # Thời hạn (số ngày)
    data_volume = models.IntegerField(null=True, blank=True)  # Dung lượng data (MB, nếu có)
    data_speed = models.CharField(max_length=3, choices=DATA_SPEEDS, null=True, blank=True)  # Tốc độ dữ liệu
    voice_minutes = models.IntegerField(null=True, blank=True)  # Phút gọi (nếu có)
    sms_count = models.IntegerField(null=True, blank=True)  # Số SMS (nếu có)
    is_active = models.BooleanField(default=True)  # Trạng thái gói (còn cung cấp hay không)
    priority = models.IntegerField(default=0)  # Độ ưu tiên (cao hơn sẽ hiển thị trước)
    created_at = models.DateTimeField(auto_now_add=True)  # Thời gian tạo
    updated_at = models.DateTimeField(auto_now=True)  # Thời gian cập nhật

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-priority', 'name']  # Sắp xếp theo độ ưu tiên giảm dần, sau đó theo tên

class ServiceUsage(models.Model):
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='service_usages')
    service_plan = models.ForeignKey(ServicePlan, on_delete=models.SET_NULL, null=True, related_name='usages')  # Liên kết với ServicePlan
    package_name = models.CharField(max_length=100)  # Tên gói cước (lưu lại để tránh mất thông tin nếu ServicePlan bị xóa)
    start_date = models.DateTimeField(auto_now_add=True)  # Thời gian bắt đầu
    end_date = models.DateTimeField()  # Thời gian kết thúc (tính dựa trên duration_days)
    data_usage = models.FloatField(default=0.0)  # Dung lượng data đã dùng (GB)
    remaining_data = models.FloatField(default=0.0)  # Dung lượng data còn lại (GB)
    call_minutes = models.IntegerField(default=0)  # Số phút gọi đã dùng
    remaining_minutes = models.IntegerField(default=0)  # Số phút gọi còn lại
    sms_used = models.IntegerField(default=0)  # Số SMS đã dùng
    remaining_sms = models.IntegerField(default=0)  # Số SMS còn lại
    spent_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  # Số tiền chi tiêu
    is_active = models.BooleanField(default=True)  # Trạng thái hoạt động

    def save(self, *args, **kwargs):
        # Tính end_date dựa trên start_date và duration_days
        if not self.pk:  # Chỉ tính khi tạo mới
            self.package_name = self.service_plan.name
            self.end_date = self.start_date + timezone.timedelta(days=self.service_plan.duration_days)
            # Khởi tạo giá trị remaining từ ServicePlan
            if self.service_plan.data_volume:
                self.remaining_data = self.service_plan.data_volume / 1024  # Chuyển từ MB sang GB
            if self.service_plan.voice_minutes:
                self.remaining_minutes = self.service_plan.voice_minutes
            if self.service_plan.sms_count:
                self.remaining_sms = self.service_plan.sms_count
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.package_name}"

class Promotion(models.Model):
    title = models.CharField(max_length=200)  # Tiêu đề khuyến mãi
    description = models.TextField()  # Mô tả chi tiết
    service_plans = models.ManyToManyField(ServicePlan, related_name='promotions')  # Áp dụng cho các gói cước
    discount_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        validators=[MinValueValidator(0), MaxValueValidator(100)],  # Giảm giá từ 0-100%
    )  # Phần trăm giảm giá
    start_date = models.DateTimeField()  # Thời gian bắt đầu
    end_date = models.DateTimeField()  # Thời gian kết thúc
    is_active = models.BooleanField(default=True)  # Trạng thái khuyến mãi
    created_at = models.DateTimeField(auto_now_add=True)  # Thời gian tạo
    updated_at = models.DateTimeField(auto_now=True)  # Thời gian cập nhật

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-start_date']  # Sắp xếp theo ngày bắt đầu mới nhất

class UserAccount(models.Model):
    user = models.OneToOneField('users.CustomUser', on_delete=models.CASCADE, related_name='account')
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])

    def __str__(self):
        return f"Tài khoản của {self.user.username} - Số dư: {self.balance} VNĐ"

class Transaction(models.Model):
    TRANSACTION_TYPES = (
        ('deposit', 'Nạp tiền'),
        ('withdraw', 'Thanh toán'),
    )
    
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField()

    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.amount} VNĐ - {self.created_at}"