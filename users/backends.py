# users/backends.py
from django.contrib.auth.backends import ModelBackend
from .models import CustomUser

class PhoneNumberBackend(ModelBackend):
    def authenticate(self, request, phone_number=None, password=None, **kwargs):
        try:
            user = CustomUser.objects.get(phone_number=phone_number)
            if user.check_password(password):
                return user
        except CustomUser.DoesNotExist:
            return None