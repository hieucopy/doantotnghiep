from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, CustomerProfile

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['phone_number', 'username', 'email', 'is_customer', 'is_staff', 'is_active']
    list_filter = ['is_customer', 'is_staff', 'is_active']
    search_fields = ['phone_number', 'username', 'email']
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Thông tin cá nhân', {'fields': ('phone_number', 'email', 'first_name', 'last_name', 'address', 'date_of_birth')}),
        ('Quyền', {'fields': ('is_customer', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Ngày quan trọng', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'phone_number', 'email', 'password1', 'password2', 'is_customer', 'is_staff'),
        }),
    )
    ordering = ['phone_number']
    readonly_fields = ['last_login', 'date_joined']
    # change_form_template = 'admin/users/customuser/change_form.html'

    def get_form(self, request, obj=None, **kwargs):
        print(f"Rendering form for CustomUser - Add: {obj is None}")
        return super().get_form(request, obj, **kwargs)

class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'loyalty_points', 'registration_date']
    list_filter = ['registration_date']
    search_fields = ['user__phone_number', 'user__username']
    fieldsets = (
        (None, {'fields': ('user', 'loyalty_points')}),
        # Xóa registration_date khỏi fieldsets vì nó không thể chỉnh sửa
        ('Thông tin bổ sung', {'fields': ()}),
    )
    readonly_fields = ['registration_date']  # Hiển thị registration_date dưới dạng chỉ đọc
    # change_form_template = 'admin/users/customerprofile/change_form.html'

    def get_form(self, request, obj=None, **kwargs):
        print(f"Rendering form for CustomerProfile - Add: {obj is None}")
        return super().get_form(request, obj, **kwargs)

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(CustomerProfile, CustomerProfileAdmin)