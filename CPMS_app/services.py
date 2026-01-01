from django.forms.models import model_to_dict
from CPMS_app.models import Log


def get_changed_fields(old_data, new_data):
    '''
    - Compare old and new data dictionaries and return only changed fields    
    '''
    diff = {}
    for field, new_value in new_data.items():
        old_value = old_data.get(field)
        if old_value != new_value:
            diff[field] = {"old_value": old_value, "new_value": new_value}
    return diff


def create_log(user, action, instance=None, old_data=None):
    new_data = model_to_dict(instance) if instance and action != "DELETE" else None
    changed_fields = {}
    if action == "UPDATE" and old_data:
        changed_fields = get_changed_fields(old_data, new_data)
        Log.objects.create(
            user = user,
            table_name = instance.__class__.__name__ if instance else "User",
            record_id = instance.id if instance else user.id,
            action = action,
            old_value = changed_fields if changed_fields else old_data,
            new_value = new_data if changed_fields else None
        )


def generate_KPIs(initiative):
    pass




