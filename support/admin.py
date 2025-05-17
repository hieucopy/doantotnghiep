from django.contrib import admin
from .models import SupportTicket, FAQ

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'subject', 'user', 'priority', 'status', 'created_at', 'rating')
    list_filter = ('priority', 'status', 'created_at')
    search_fields = ('subject', 'description', 'response')
    list_per_page = 20
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'category', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('question', 'answer')
    list_per_page = 20
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)