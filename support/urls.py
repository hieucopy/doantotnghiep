from django.urls import path
from . import views

urlpatterns = [
    path('', views.support_home, name='support_home'),
    path('create-ticket/', views.create_ticket, name='support_create_ticket'),
    path('tickets/', views.ticket_list, name='support_ticket_list'),
    path('tickets/<int:ticket_id>/', views.ticket_detail, name='support_ticket_detail'),
    path('tickets/<int:ticket_id>/rate/', views.rate_ticket, name='support_rate_ticket'),
    path('faq/', views.faq_list, name='support_faq'),
]