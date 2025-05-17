from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import ServicePlan, ServiceUsage, Promotion, UserAccount, Transaction

@admin.register(ServicePlan)
class ServicePlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'plan_type', 'price_colored', 'duration_days', 'data_volume_display', 'voice_minutes', 'sms_count', 'data_speed', 'is_active', 'is_active_colored', 'priority')
    list_filter = ('plan_type', 'is_active', 'data_speed')
    search_fields = ('name', 'description')
    list_editable = ('priority', 'is_active')  # Đã sửa: is_active có trong list_display
    list_per_page = 20
    ordering = ('-priority', 'name')

    def price_colored(self, obj):
        return format_html('<span style="color: #dc3545;">{} VNĐ</span>', obj.price)
    price_colored.short_description = "Giá"

    def data_volume_display(self, obj):
        return f"{obj.data_volume} MB" if obj.data_volume else "N/A"
    data_volume_display.short_description = "Dung lượng Data"

    def is_active_colored(self, obj):
        color = "green" if obj.is_active else "red"
        return format_html('<span style="color: {};">{}</span>', color, "Hoạt động" if obj.is_active else "Không hoạt động")
    is_active_colored.short_description = "Trạng thái"

@admin.register(ServiceUsage)
class ServiceUsageAdmin(admin.ModelAdmin):
    list_display = ('user', 'package_name', 'start_date', 'end_date', 'status', 'remaining_data', 'remaining_minutes', 'remaining_sms', 'spent_amount_colored', 'is_active')
    list_filter = ('is_active', 'start_date', 'end_date')
    search_fields = ('package_name', 'user__username')
    list_per_page = 20
    date_hierarchy = 'start_date'

    def status(self, obj):
        if obj.is_active and obj.end_date >= timezone.now():
            return format_html('<span style="color: green;">Đang hoạt động</span>')
        return format_html('<span style="color: red;">Hết hạn</span>')
    status.short_description = "Trạng thái"

    def spent_amount_colored(self, obj):
        return format_html('<span style="color: #dc3545;">{} VNĐ</span>', obj.spent_amount)
    spent_amount_colored.short_description = "Chi tiêu"

@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ('title', 'discount_percentage_colored', 'start_date', 'end_date', 'is_active_colored', 'service_plans_list')
    list_filter = ('is_active', 'start_date', 'end_date')
    search_fields = ('title', 'description')
    filter_horizontal = ('service_plans',)  # Dễ dàng chọn nhiều gói cước
    list_per_page = 20
    date_hierarchy = 'start_date'

    def discount_percentage_colored(self, obj):
        return format_html('<span style="color: #28a745;">{}%</span>', obj.discount_percentage)
    discount_percentage_colored.short_description = "Giảm giá"

    def is_active_colored(self, obj):
        color = "green" if obj.is_active else "red"
        return format_html('<span style="color: {};">{}</span>', color, "Hoạt động" if obj.is_active else "Hết hiệu lực")
    is_active_colored.short_description = "Trạng thái"

    def service_plans_list(self, obj):
        return ", ".join([plan.name for plan in obj.service_plans.all()])
    service_plans_list.short_description = "Gói cước áp dụng"

@admin.register(UserAccount)
class UserAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance_colored')
    search_fields = ('user__username',)
    list_per_page = 20

    def balance_colored(self, obj):
        color = "green" if obj.balance > 0 else "red"
        return format_html('<span style="color: {};">{} VNĐ</span>', color, obj.balance)
    balance_colored.short_description = "Số dư"

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'transaction_type_colored', 'amount_colored', 'created_at', 'description')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('user__username', 'description')
    list_per_page = 20
    date_hierarchy = 'created_at'

    def transaction_type_colored(self, obj):
        color = "green" if obj.transaction_type == 'deposit' else "red"
        return format_html('<span style="color: {};">{}</span>', color, obj.get_transaction_type_display())
    transaction_type_colored.short_description = "Loại giao dịch"

    def amount_colored(self, obj):
        color = "green" if obj.transaction_type == 'deposit' else "red"
        return format_html('<span style="color: {};">{} VNĐ</span>', color, obj.amount)
    amount_colored.short_description = "Số tiền"