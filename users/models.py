# users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    phone_number = models.CharField(max_length=15, unique=True, blank=True, null=True)
    address = models.TextField(blank=True)
    date_of_birth = models.DateField(blank=True, null=True)
    is_customer = models.BooleanField(default=True)  # True: khách hàng, False: admin/staff

    def __str__(self):
        return self.phone_number or self.username

    class Meta:
        verbose_name = "Người dùng"
        verbose_name_plural = "Người dùng"

class CustomerProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='profile')
    loyalty_points = models.IntegerField(default=0, verbose_name="Điểm tích lũy")
    registration_date = models.DateTimeField(auto_now_add=True, verbose_name="Ngày đăng ký")

    def __str__(self):
        return f"Hồ sơ của {self.user.phone_number or self.user.username}"

    class Meta:
        verbose_name = "Hồ sơ khách hàng"
        verbose_name_plural = "Hồ sơ khách hàng"