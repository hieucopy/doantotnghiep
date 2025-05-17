from rest_framework import serializers
from .models import CustomUser, CustomerProfile

class CustomerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerProfile
        fields = ['user', 'loyalty_points', 'registration_date']

class CustomUserSerializer(serializers.ModelSerializer):
    customer_profile = CustomerProfileSerializer(read_only=True)

    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'phone_number', 'email', 'first_name', 'last_name', 'address', 'is_customer', 'customer_profile']