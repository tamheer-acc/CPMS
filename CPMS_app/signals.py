from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from .services import create_log

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    create_log(user=user, action="LOGIN")

@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    create_log(user=user, action="LOGOUT")
