from django.urls import path
from . import views

# app_name = 'services'  # Đăng ký namespace 'services'

urlpatterns = [
    path('', views.services_view, name='services'),
    path('register-service/<int:package_id>/', views.register_service_view, name='register_service'),
    path('usage-history/', views.usage_history_view, name='usage_history'),
    path('cancel-service/<int:usage_id>/', views.cancel_service_view, name='cancel_service'),
    path('renew-service/<int:usage_id>/', views.renew_service_view, name='renew_service'),
    path('account-management/', views.account_management_view, name='account_management'),
    path('deposit/', views.deposit_view, name='deposit'),
    path('check-usage/', views.check_usage_view, name='check_usage'),
]