from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from .services import create_log
from django.dispatch import receiver

def is_migration_running():
    import sys
    return 'makemigrations' in sys.argv or 'migrate' in sys.argv


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    if is_migration_running():
        return
    create_log(user=user, action="تسجيل دخول")

@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    if is_migration_running():
        return
    create_log(user=user, action="تسجيل خروج")

