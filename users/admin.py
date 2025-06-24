from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from django.contrib.admin import SimpleListFilter
from .models import CustomUser, CustomerProfile
from services.models import ServiceUsage
from support.models import SupportTicket

class UserTypeFilter(SimpleListFilter):
    title = 'Loại người dùng'
    parameter_name = 'user_type'

    def lookups(self, request, model_admin):
        return [
            ('customer', 'Khách hàng'),
            ('staff', 'Nhân viên'),
            ('admin', 'Quản trị viên'),
            ('inactive', 'Ngừng hoạt động'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'customer':
            return queryset.filter(is_customer=True, is_staff=False, is_active=True)
        elif self.value() == 'staff':
            return queryset.filter(is_staff=True, is_superuser=False, is_active=True)
        elif self.value() == 'admin':
            return queryset.filter(is_superuser=True, is_active=True)
        elif self.value() == 'inactive':
            return queryset.filter(is_active=False)
        return queryset

class SpendingRangeFilter(SimpleListFilter):
    title = 'Tổng chi tiêu'
    parameter_name = 'spending_range'

    def lookups(self, request, model_admin):
        return [
            ('low', 'Dưới 1 triệu'),
            ('medium', 'Từ 1-10 triệu'),
            ('high', 'Trên 10 triệu'),
            ('none', 'Chưa chi tiêu'),
        ]

    def queryset(self, request, queryset):
        queryset = queryset.annotate(
            total_spent=Sum('service_usages__spent_amount')
        )
        
        if self.value() == 'low':
            return queryset.filter(total_spent__lt=1000000)
        elif self.value() == 'medium':
            return queryset.filter(total_spent__gte=1000000, total_spent__lt=10000000)
        elif self.value() == 'high':
            return queryset.filter(total_spent__gte=10000000)
        elif self.value() == 'none':
            return queryset.filter(Q(total_spent__isnull=True) | Q(total_spent=0))
        return queryset

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = [
        'user_info',
        'contact_info',
        'account_status',
        'service_summary',
        'support_summary',
        'last_activity'
    ]
    list_filter = [
        UserTypeFilter,
        SpendingRangeFilter,
        'is_active',
    ]
    search_fields = [
        'phone_number',
        'username',
        'email',
        'first_name',
        'last_name'
    ]
    ordering = ['-date_joined']
    readonly_fields = ['last_login', 'date_joined']

    fieldsets = (
        ('Thông tin tài khoản', {
            'fields': ('username', 'password', 'is_active')
        }),
        ('Thông tin cá nhân', {
            'fields': (
                'phone_number',
                'email',
                'first_name',
                'last_name',
                'date_of_birth',
                'address'
            )
        }),
        ('Phân quyền', {
            'fields': (
                'is_customer',
                'is_staff',
                'is_superuser',
                'groups',
                'user_permissions'
            ),
            'classes': ('collapse',)
        }),
        ('Thông tin hệ thống', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username',
                'phone_number',
                'email',
                'password1',
                'password2',
                'is_customer',
                'is_staff'
            ),
        }),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            total_spent=Sum('service_usages__spent_amount'),
            avg_rating=Avg('support_tickets__rating'),
            active_services_count=Count(
                'service_usages',
                filter=Q(
                    service_usages__is_active=True,
                    service_usages__end_date__gt=timezone.now()
                )
            )
        )
        return queryset

    def user_info(self, obj):
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        name_display = full_name if full_name else obj.username
        
        user_type = "👑 Admin" if obj.is_superuser else "👤 Nhân viên" if obj.is_staff else "🧑 Khách hàng"
        
        return format_html(
            '<div style="min-width:200px;">'
            '<div style="font-weight:bold;color:#2c3e50;">{}</div>'
            '<div style="color:#7f8c8d;font-size:12px;">{}</div>'
            '<div style="color:#3498db;font-size:12px;">{}</div>'
            '</div>',
            name_display,
            obj.username,
            user_type
        )
    user_info.short_description = "Người dùng"
    user_info.admin_order_field = 'username'

    def contact_info(self, obj):
        return format_html(
            '<div style="min-width:200px;">'
            '<div><i class="fas fa-phone"></i> {}</div>'
            '<div><i class="fas fa-envelope"></i> {}</div>'
            '<div><i class="fas fa-map-marker-alt"></i> {}</div>'
            '</div>',
            obj.phone_number or '—',
            obj.email or '—',
            obj.address[:30] + '...' if obj.address and len(obj.address) > 30 else (obj.address or '—')
        )
    contact_info.short_description = "Thông tin liên hệ"
    contact_info.admin_order_field = 'phone_number'

    def account_status(self, obj):
        status_color = '#2ecc71' if obj.is_active else '#e74c3c'
        status_text = 'Đang hoạt động' if obj.is_active else 'Ngừng hoạt động'
        
        if hasattr(obj, 'customerprofile'):
            points = obj.customerprofile.loyalty_points
            points_color = '#27ae60' if points > 1000 else '#f1c40f' if points > 0 else '#95a5a6'
        else:
            points = 0
            points_color = '#95a5a6'
            
        return format_html(
            '<div style="min-width:150px;">'
            '<div><span style="color:{};">⬤</span> {}</div>'
            '<div style="color:{};">🎯 {} điểm</div>'
            '</div>',
            status_color, status_text,
            points_color, points
        )
    account_status.short_description = "Trạng thái"
    account_status.admin_order_field = 'is_active'

    def service_summary(self, obj):
        active_services = getattr(obj, 'active_services_count', 0)
        total_spent = getattr(obj, 'total_spent', 0) or 0
        
        formatted_amount = "{:,.0f}".format(total_spent)
        
        return format_html(
            '<div style="min-width:150px;">'
            '<div>📱 {} gói đang dùng</div>'
            '<div style="color:#e67e22;">💰 {} VNĐ</div>'
            '</div>',
            active_services,
            formatted_amount
        )
    service_summary.short_description = "Dịch vụ"
    service_summary.admin_order_field = 'total_spent'

    def support_summary(self, obj):
        tickets = SupportTicket.objects.filter(user=obj)
        total_tickets = tickets.count()
        pending_tickets = tickets.filter(status='PENDING').count()
        avg_rating = getattr(obj, 'avg_rating', None)
        
        if avg_rating:
            stars = '★' * int(round(avg_rating)) + '☆' * (5 - int(round(avg_rating)))
        else:
            stars = '—'
            
        return format_html(
            '<div style="min-width:150px;">'
            '<div>📝 {} yêu cầu ({} chờ)</div>'
            '<div style="color:#f1c40f;">{}</div>'
            '</div>',
            total_tickets, pending_tickets,
            stars
        )
    support_summary.short_description = "Hỗ trợ"
    support_summary.admin_order_field = 'avg_rating'

    def last_activity(self, obj):
        if not obj.last_login:
            return '—'
            
        time_diff = timezone.now() - obj.last_login
        days_diff = time_diff.days
        
        if days_diff == 0:
            hours_diff = time_diff.seconds // 3600
            if hours_diff == 0:
                minutes_diff = time_diff.seconds // 60
                return f"{minutes_diff} phút trước"
            return f"{hours_diff} giờ trước"
        elif days_diff < 30:
            return f"{days_diff} ngày trước"
        else:
            months_diff = days_diff // 30
            return f"{months_diff} tháng trước"
    last_activity.short_description = "Hoạt động cuối"
    last_activity.admin_order_field = 'last_login'

    class Media:
        css = {
            'all': [
                'https://use.fontawesome.com/releases/v5.15.4/css/all.css',
                'https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap',
            ]
        }

class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'loyalty_points', 'registration_date']
    list_filter = ['registration_date']
    search_fields = ['user__phone_number', 'user__username']
    fieldsets = (
        (None, {'fields': ('user', 'loyalty_points')}),
        ('Thông tin bổ sung', {'fields': ()}),
    )
    readonly_fields = ['registration_date']

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(CustomerProfile, CustomerProfileAdmin)