from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.db.models import Count
from django.contrib.admin import SimpleListFilter
from .models import ServicePlan, ServiceUsage, Promotion, UserAccount, Transaction
from users.models import CustomUser

class ServiceTypeFilter(SimpleListFilter):
    title = 'Loại dịch vụ'
    parameter_name = 'service_type'

    def lookups(self, request, model_admin):
        return [
            ('DATA', 'Gói Data'),
            ('VOICE', 'Gói Thoại'),
            ('SMS', 'Gói SMS'),
            ('COMBO', 'Gói Combo'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(service_plan__plan_type=self.value())
        return queryset

class StatusFilter(SimpleListFilter):
    title = 'Trạng thái'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return [
            ('active', 'Đang hoạt động'),
            ('expired', 'Đã hết hạn'),
            ('cancelled', 'Đã hủy'),
        ]

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == 'active':
            return queryset.filter(is_active=True, end_date__gt=now)
        elif self.value() == 'expired':
            return queryset.filter(end_date__lte=now)
        elif self.value() == 'cancelled':
            return queryset.filter(is_active=False)
        return queryset

@admin.register(ServicePlan)
class ServicePlanAdmin(admin.ModelAdmin):
    list_display = ('name_with_description', 'plan_type_display', 'data_display', 'voice_sms_display', 'price_display', 'duration_display', 'status_display', 'priority')
    list_filter = ('plan_type', 'is_active', 'data_speed')
    search_fields = ('name', 'description')
    list_editable = ('priority',)
    list_per_page = 20
    ordering = ('-priority', 'name')
    readonly_fields = ['plan_details_view']
    change_list_template = 'admin/services/serviceplan/change_list.html'
    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('name', 'plan_type', 'description', 'price', 'priority', 'is_active')
        }),
        ('Thông tin dịch vụ', {
            'fields': ('duration_days', 'data_volume', 'data_speed', 'voice_minutes', 'sms_count')
        }),
        ('Xem trước', {
            'fields': ('plan_details_view',)
        }),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        self.data_count = queryset.filter(plan_type='DATA').count()
        self.voice_count = queryset.filter(plan_type='VOICE').count()
        self.sms_count = queryset.filter(plan_type='SMS').count()
        self.combo_count = queryset.filter(plan_type='COMBO').count()
        return queryset

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.update({
            'data_count': getattr(self, 'data_count', 0),
            'voice_count': getattr(self, 'voice_count', 0),
            'sms_count': getattr(self, 'sms_count', 0),
            'combo_count': getattr(self, 'combo_count', 0),
        })
        return super().changelist_view(request, extra_context=extra_context)
        
    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['now'] = timezone.now()
        return super().change_view(
            request, object_id, form_url, extra_context=extra_context,
        )

    def name_with_description(self, obj):
        return f"{obj.name}\n{obj.description[:50]}..." if len(obj.description) > 50 else f"{obj.name}\n{obj.description}"
    name_with_description.short_description = "Tên gói cước"

    def plan_type_display(self, obj):
        type_labels = {
            'DATA': 'Gói Data',
            'VOICE': 'Gói Thoại',
            'SMS': 'Gói SMS',
            'COMBO': 'Gói Combo'
        }
        return type_labels.get(obj.plan_type, obj.plan_type)
    plan_type_display.short_description = "Loại gói"

    def data_display(self, obj):
        if obj.data_volume:
            data_gb = obj.data_volume / 1024 if obj.data_volume >= 1024 else None
            data_text = f"{data_gb:.1f} GB" if data_gb else f"{obj.data_volume} MB"
            speed = f" - {obj.data_speed}" if obj.data_speed else ""
            return f"{data_text}{speed}"
        return "Không có data"
    data_display.short_description = "Dung lượng Data"

    def voice_sms_display(self, obj):
        parts = []
        if obj.voice_minutes:
            parts.append(f"{obj.voice_minutes:,} phút")
        if obj.sms_count:
            parts.append(f"{obj.sms_count:,} SMS")
        return " | ".join(parts) if parts else "Không có"
    voice_sms_display.short_description = "Phút gọi & SMS"

    def price_display(self, obj):
        return f"{int(obj.price):,} VNĐ"
    price_display.short_description = "Giá gói cước"

    def duration_display(self, obj):
        if obj.duration_days == 30:
            return "1 tháng"
        elif obj.duration_days == 90:
            return "3 tháng"
        elif obj.duration_days == 180:
            return "6 tháng"
        elif obj.duration_days == 365:
            return "1 năm"
        return f"{obj.duration_days} ngày"
    duration_display.short_description = "Thời hạn"

    def status_display(self, obj):
        return "Đang hoạt động" if obj.is_active else "Ngừng cung cấp"
    status_display.short_description = "Trạng thái"

    def plan_details_view(self, obj):
        if not obj:
            return "Lưu để xem trước"
            
        # Tính giá theo ngày
        daily_price = int(obj.price) / obj.duration_days
        
        # Xử lý dữ liệu data
        data_info = ""
        if obj.data_volume:
            data_gb = obj.data_volume / 1024 if obj.data_volume >= 1024 else None
            data_display = f"{data_gb:.1f} GB" if data_gb else f"{obj.data_volume} MB"
            speed = f"{obj.data_speed}" if obj.data_speed else "Không xác định"
            data_info = f"""
            <div class="detail-item">
                <i class="fas fa-wifi" style="color:#3498db;"></i>
                <div>
                    <strong>Dung lượng:</strong> {data_display}<br>
                    <strong>Tốc độ:</strong> {speed}
                </div>
            </div>
            """
            
        # Xử lý dữ liệu phút gọi
        voice_info = ""
        if obj.voice_minutes:
            voice_info = f"""
            <div class="detail-item">
                <i class="fas fa-phone-alt" style="color:#27ae60;"></i>
                <div>
                    <strong>Phút gọi:</strong> {obj.voice_minutes:,} phút
                </div>
            </div>
            """
            
        # Xử lý dữ liệu SMS
        sms_info = ""
        if obj.sms_count:
            sms_info = f"""
            <div class="detail-item">
                <i class="fas fa-sms" style="color:#16a085;"></i>
                <div>
                    <strong>SMS:</strong> {obj.sms_count:,} tin nhắn
                </div>
            </div>
            """
            
        # Định dạng thời hạn
        if obj.duration_days == 30:
            period = "1 tháng"
        elif obj.duration_days == 90:
            period = "3 tháng"
        elif obj.duration_days == 180:
            period = "6 tháng"
        elif obj.duration_days == 365:
            period = "1 năm"
        else:
            period = f"{obj.duration_days} ngày"
            
        # Trạng thái
        status_color = "#2ecc71" if obj.is_active else "#e74c3c"
        status_text = "Đang hoạt động" if obj.is_active else "Ngừng cung cấp"
        
        # Loại gói
        plan_type_colors = {
            'DATA': '#3498db',
            'VOICE': '#27ae60',
            'SMS': '#e67e22',
            'COMBO': '#9b59b6'
        }
        plan_type_color = plan_type_colors.get(obj.plan_type, '#777')
        plan_type_text = dict(ServicePlan.PLAN_TYPES).get(obj.plan_type)
        
        return mark_safe(f"""
        <style>
            .plan-preview {{
                max-width: 600px;
                border: 1px solid #ddd;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                font-family: 'Segoe UI', Arial, sans-serif;
            }}
            .plan-header {{
                background: linear-gradient(135deg, #4568dc, #b06ab3);
                color: white;
                padding: 15px 20px;
                position: relative;
            }}
            .plan-badge {{
                position: absolute;
                top: 15px;
                right: 15px;
                background-color: {plan_type_color};
                padding: 5px 10px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            }}
            .plan-title {{
                font-size: 24px;
                font-weight: bold;
                margin: 0;
                padding: 0;
            }}
            .plan-price {{
                font-size: 28px;
                font-weight: bold;
                margin: 10px 0 5px;
            }}
            .plan-price-daily {{
                font-size: 14px;
                opacity: 0.8;
            }}
            .plan-body {{
                padding: 20px;
                background: white;
            }}
            .plan-description {{
                margin-bottom: 20px;
                color: #555;
                line-height: 1.5;
                border-bottom: 1px solid #eee;
                padding-bottom: 15px;
            }}
            .plan-details {{
                display: flex;
                flex-direction: column;
                gap: 15px;
            }}
            .detail-item {{
                display: flex;
                align-items: flex-start;
                gap: 15px;
            }}
            .detail-item i {{
                font-size: 20px;
                margin-top: 3px;
            }}
            .plan-footer {{
                background: #f9f9f9;
                padding: 15px 20px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                border-top: 1px solid #eee;
            }}
            .status-badge {{
                background-color: {status_color};
                color: white;
                padding: 5px 10px;
                border-radius: 4px;
                font-size: 12px;
            }}
        </style>
        <div class="plan-preview">
            <div class="plan-header">
                <div class="plan-badge">{plan_type_text}</div>
                <h2 class="plan-title">{obj.name}</h2>
                <div class="plan-price">{int(obj.price):,} VNĐ</div>
                <div class="plan-price-daily">≈ {int(daily_price):,} VNĐ/ngày</div>
            </div>
            <div class="plan-body">
                <div class="plan-description">{obj.description}</div>
                <div class="plan-details">
                    <div class="detail-item">
                        <i class="far fa-calendar-alt" style="color:#8e44ad;"></i>
                        <div>
                            <strong>Thời hạn:</strong> {period}
                        </div>
                    </div>
                    {data_info}
                    {voice_info}
                    {sms_info}
                </div>
            </div>
            <div class="plan-footer">
                <div class="status-badge">{status_text}</div>
                <div><strong>Độ ưu tiên:</strong> {obj.priority}</div>
            </div>
        </div>
        """)
    plan_details_view.short_description = "Xem trước gói cước"

    class Media:
        css = {
            'all': [
                'https://use.fontawesome.com/releases/v5.15.4/css/all.css',
                'https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap',
            ]
        }
        js = [
            'https://use.fontawesome.com/releases/v5.15.4/js/all.js',
        ]

@admin.register(ServiceUsage)
class ServiceUsageAdmin(admin.ModelAdmin):
    list_display = (
        'user_info', 
        'package_info', 
        'time_info',
        'usage_info', 
        'remaining_info',
        'status_badge'
    )
    list_filter = [
        ServiceTypeFilter,
        StatusFilter,
        ('service_plan', admin.RelatedFieldListFilter),
        ('start_date', admin.DateFieldListFilter),
        ('end_date', admin.DateFieldListFilter),
        'is_active'
    ]
    search_fields = [
        'user__username', 
        'user__email',
        'user__phone_number',
        'package_name',
        'service_plan__name'
    ]
    list_per_page = 20
    date_hierarchy = 'start_date'
    ordering = ['-start_date']

    def user_info(self, obj):
        return format_html(
            '<div style="min-width:150px;">'
            '<strong style="color:#2c3e50;">{}</strong><br>'
            '<span style="color:#7f8c8d; font-size:12px;">{}</span>'
            '</div>',
            obj.user.username,
            obj.user.email or obj.user.phone_number
        )
    user_info.short_description = "Người dùng"
    user_info.admin_order_field = 'user__username'

    def package_info(self, obj):
        return format_html(
            '<div style="min-width:200px;">'
            '<strong style="color:#2c3e50;">{}</strong><br>'
            '<span style="color:#7f8c8d; font-size:12px;">{}</span>'
            '</div>',
            obj.package_name,
            obj.service_plan.description if obj.service_plan else "Gói cước đã bị xóa"
        )
    package_info.short_description = "Gói cước"
    package_info.admin_order_field = 'package_name'

    def time_info(self, obj):
        days_left = (obj.end_date.date() - timezone.now().date()).days
        status_color = "#27ae60" if days_left > 0 else "#e74c3c"
        
        return format_html(
            '<div style="min-width:180px;">'
            '<div style="margin-bottom:5px;">'
            '<i class="fas fa-calendar-alt" style="color:#3498db;"></i> '
            '<span style="color:#34495e;">Bắt đầu: {}</span>'
            '</div>'
            '<div>'
            '<i class="fas fa-hourglass-half" style="color:{};"></i> '
            '<span style="color:{};">Còn {} ngày</span>'
            '</div>'
            '</div>',
            obj.start_date.strftime("%d/%m/%Y"),
            status_color,
            status_color,
            max(days_left, 0)
        )
    time_info.short_description = "Thời gian"
    time_info.admin_order_field = 'start_date'

    def usage_info(self, obj):
        data_text = f"{obj.data_usage:.1f} GB" if obj.data_usage else "0 GB"
        minutes_text = f"{obj.call_minutes:,} phút" if obj.call_minutes else "0 phút"
        sms_text = f"{obj.sms_used:,} SMS" if obj.sms_used else "0 SMS"
        
        return format_html(
            '<div style="min-width:150px;">'
            '<div><i class="fas fa-database" style="color:#3498db;"></i> {}</div>'
            '<div><i class="fas fa-phone" style="color:#27ae60;"></i> {}</div>'
            '<div><i class="fas fa-sms" style="color:#e67e22;"></i> {}</div>'
            '</div>',
            data_text, minutes_text, sms_text
        )
    usage_info.short_description = "Đã sử dụng"

    def remaining_info(self, obj):
        data_text = f"{obj.remaining_data:.1f} GB" if obj.remaining_data else "0 GB"
        minutes_text = f"{obj.remaining_minutes:,} phút" if obj.remaining_minutes else "0 phút"
        sms_text = f"{obj.remaining_sms:,} SMS" if obj.remaining_sms else "0 SMS"
        
        return format_html(
            '<div style="min-width:150px;">'
            '<div><i class="fas fa-database" style="color:#3498db;"></i> {}</div>'
            '<div><i class="fas fa-phone" style="color:#27ae60;"></i> {}</div>'
            '<div><i class="fas fa-sms" style="color:#e67e22;"></i> {}</div>'
            '</div>',
            data_text, minutes_text, sms_text
        )
    remaining_info.short_description = "Còn lại"

    def status_badge(self, obj):
        days_left = (obj.end_date.date() - timezone.now().date()).days
        if not obj.is_active:
            badge_color = "#95a5a6"
            status_text = "Đã hủy"
        elif days_left <= 0:
            badge_color = "#e74c3c"
            status_text = "Hết hạn"
        else:
            badge_color = "#27ae60"
            status_text = "Đang hoạt động"
            
        return format_html(
            '<span style="background-color:{}; color:white; padding:5px 10px; '
            'border-radius:15px; font-size:12px;">{}</span>',
            badge_color, status_text
        )
    status_badge.short_description = "Trạng thái"

    class Media:
        css = {
            'all': [
                'https://use.fontawesome.com/releases/v5.15.4/css/all.css',
                'https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap',
            ]
        }
        js = [
            'https://use.fontawesome.com/releases/v5.15.4/js/all.js',
        ]

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