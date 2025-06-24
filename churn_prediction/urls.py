from django.urls import path
from . import views

app_name = 'churn_prediction'

urlpatterns = [
    path('prepare-data/', views.prepare_data, name='prepare_data'),
] 