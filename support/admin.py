from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.contrib.admin import SimpleListFilter
from .models import SupportTicket, FAQ

class ResponseStatusFilter(SimpleListFilter):
    title = 'Trạng thái phản hồi'
    parameter_name = 'response_status'

    def lookups(self, request, model_admin):
        return [
            ('pending', 'Chưa phản hồi'),
            ('responded', 'Đã phản hồi'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'pending':
            return queryset.filter(response__isnull=True)
        if self.value() == 'responded':
            return queryset.filter(response__isnull=False)
        return queryset

class RatingFilter(SimpleListFilter):
    title = 'Đánh giá'
    parameter_name = 'rating'

    def lookups(self, request, model_admin):
        return [
            ('unrated', 'Chưa đánh giá'),
            ('1', '★ - Rất không hài lòng'),
            ('2', '★★ - Không hài lòng'),
            ('3', '★★★ - Bình thường'),
            ('4', '★★★★ - Hài lòng'),
            ('5', '★★★★★ - Rất hài lòng'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'unrated':
            return queryset.filter(rating__isnull=True)
        if self.value() in ('1', '2', '3', '4', '5'):
            return queryset.filter(rating=int(self.value()))
        return queryset

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = (
        'ticket_info',
        'user_info',
        'priority_badge',
        'status_badge',
        'response_info',
        'rating_stars'
    )
    list_filter = [
        'priority',
        'status',
        ResponseStatusFilter,
        RatingFilter,
        ('created_at', admin.DateFieldListFilter),
    ]
    search_fields = [
        'subject',
        'description',
        'response',
        'user__username',
        'user__email',
        'user__phone_number'
    ]
    list_per_page = 20
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Thông tin ticket', {
            'fields': ('subject', 'description', 'user', 'priority', 'status')
        }),
        ('Phản hồi', {
            'fields': ('response', 'rating')
        }),
        ('Thông tin thời gian', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def ticket_info(self, obj):
        priority_colors = {
            'LOW': '#3498db',
            'MEDIUM': '#f1c40f',
            'HIGH': '#e67e22',
            'URGENT': '#e74c3c'
        }
        return format_html(
            '<div style="min-width:300px;">'
            '<span style="font-weight:bold;color:{};margin-right:10px;">#{}</span>'
            '<span style="color:#2c3e50;">{}</span><br>'
            '<span style="color:#7f8c8d;font-size:12px;">{}</span>'
            '</div>',
            priority_colors.get(obj.priority, '#777'),
            obj.id,
            obj.subject,
            obj.description[:100] + '...' if len(obj.description) > 100 else obj.description
        )
    ticket_info.short_description = 'Thông tin ticket'

    def user_info(self, obj):
        return format_html(
            '<div style="min-width:200px;">'
            '<div style="font-weight:bold;color:#2c3e50;">{}</div>'
            '<div style="color:#7f8c8d;font-size:12px;">{}</div>'
            '</div>',
            obj.user.username,
            obj.user.email or obj.user.phone_number
        )
    user_info.short_description = 'Người dùng'

    def priority_badge(self, obj):
        colors = {
            'LOW': ('#3498db', 'Thấp'),
            'MEDIUM': ('#f1c40f', 'Trung bình'),
            'HIGH': ('#e67e22', 'Cao'),
            'URGENT': ('#e74c3c', 'Khẩn cấp')
        }
        color, label = colors.get(obj.priority, ('#777', obj.priority))
        return format_html(
            '<span style="background-color:{}; color:white; padding:5px 10px; '
            'border-radius:15px; font-size:12px;">{}</span>',
            color, label
        )
    priority_badge.short_description = 'Độ ưu tiên'

    def status_badge(self, obj):
        colors = {
            'PENDING': ('#f1c40f', 'Đang chờ'),
            'IN_PROGRESS': ('#3498db', 'Đang xử lý'),
            'RESOLVED': ('#2ecc71', 'Đã giải quyết'),
            'CLOSED': ('#95a5a6', 'Đã đóng')
        }
        color, label = colors.get(obj.status, ('#777', obj.status))
        return format_html(
            '<span style="background-color:{}; color:white; padding:5px 10px; '
            'border-radius:15px; font-size:12px;">{}</span>',
            color, label
        )
    status_badge.short_description = 'Trạng thái'

    def response_info(self, obj):
        if not obj.response:
            return format_html(
                '<span style="color:#e74c3c;">Chưa phản hồi</span>'
            )
        response_preview = obj.response[:100] + '...' if len(obj.response) > 100 else obj.response
        time_diff = timezone.now() - obj.updated_at
        hours_diff = time_diff.total_seconds() / 3600
        
        if hours_diff < 24:
            time_text = f"{int(hours_diff)} giờ trước"
        else:
            days = int(hours_diff / 24)
            time_text = f"{days} ngày trước"
            
        return format_html(
            '<div style="min-width:200px;">'
            '<div style="color:#2c3e50;">{}</div>'
            '<div style="color:#7f8c8d;font-size:12px;">{}</div>'
            '</div>',
            response_preview,
            time_text
        )
    response_info.short_description = 'Phản hồi'

    def rating_stars(self, obj):
        if obj.rating is None:
            return '-'
        stars = '★' * obj.rating + '☆' * (5 - obj.rating)
        colors = {
            1: '#e74c3c',  # Đỏ
            2: '#e67e22',  # Cam
            3: '#f1c40f',  # Vàng
            4: '#2ecc71',  # Xanh lá
            5: '#27ae60',  # Xanh lá đậm
        }
        return format_html(
            '<span style="color:{};font-size:16px;">{}</span>',
            colors.get(obj.rating, '#777'),
            stars
        )
    rating_stars.short_description = 'Đánh giá'

    class Media:
        css = {
            'all': [
                'https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap',
            ]
        }

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'category', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('question', 'answer')
    list_per_page = 20
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)