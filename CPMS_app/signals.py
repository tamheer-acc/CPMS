from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from .services import create_log
from django.db.models.signals import pre_save, post_save, pre_delete
from django.dispatch import receiver
from .models import Log
from .middleware import get_current_user
from .services import model_to_dict_with_usernames



@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    create_log(user=user, action="LOGIN")

@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    create_log(user=user, action="LOGOUT")


# ======= Capture old instance before update =======
@receiver(pre_save)
def capture_old_instance(sender, instance, **kwargs):
    if sender.__name__ == "Log":
        return

    if instance.pk:
        instance._old_instance = sender.objects.get(pk=instance.pk)


# ======= CREATE & UPDATE =======
@receiver(post_save)
def log_create_update(sender, instance, created, **kwargs):
    if sender.__name__ == "Log":
        return

    user = get_current_user()

    # ===== CREATE =====
    if created:
        Log.objects.create(
            user=user,
            table_name=sender.__name__,
            record_id=instance.pk,
            action="CREATE",
            old_value=None,
            new_value=str(model_to_dict_with_usernames(instance))
        )
        return

    # ===== UPDATE =====
    old_instance = getattr(instance, "_old_instance", None)
    if old_instance:
        Log.objects.create(
            user=user,
            table_name=sender.__name__,
            record_id=instance.pk,
            action="UPDATE",
            old_value=str(model_to_dict_with_usernames(old_instance)),
            new_value=str(model_to_dict_with_usernames(instance))
        )


# ======= DELETE =======
@receiver(pre_delete)
def log_delete(sender, instance, **kwargs):
    if sender.__name__ == "Log":
        return

    user = get_current_user()
    Log.objects.create(
        user=user,
        table_name=sender.__name__,
        record_id=instance.pk,
        action="DELETE",
        old_value=str(model_to_dict_with_usernames(instance)),
        new_value=None
    )
