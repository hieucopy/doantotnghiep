from django.db import models
from django.conf import settings  # Thêm import này

class SupportTicket(models.Model):
    PRIORITY_CHOICES = (
        ('LOW', 'Thấp'),
        ('MEDIUM', 'Trung bình'),
        ('HIGH', 'Cao'),
    )
    STATUS_CHOICES = (
        ('PENDING', 'Đang xử lý'),
        ('RESOLVED', 'Đã giải quyết'),
        ('CLOSED', 'Đã đóng'),
    )

    # Sử dụng settings.AUTH_USER_MODEL thay vì User
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='support_tickets')
    subject = models.CharField(max_length=255)
    description = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    response = models.TextField(blank=True, null=True)
    rating = models.IntegerField(null=True, blank=True, choices=[(i, str(i)) for i in range(1, 6)])  # Đánh giá từ 1-5 sao
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Ticket #{self.id} - {self.subject}"

class FAQ(models.Model):
    question = models.CharField(max_length=255)
    answer = models.TextField()
    category = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.question