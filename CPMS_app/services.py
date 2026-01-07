from django.forms.models import model_to_dict
from django.db.models import Count, Q
from .models import StrategicGoal, Initiative, Log, UserInitiative
from django.db.models import Prefetch

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

def get_plan_dashboard(plan, user):
    role = user.role.role_name
    can_edit = False  # Read only

    goals = plan.goals.prefetch_related(
    Prefetch(
        'initiative_set__userinitiative_set',
        queryset=UserInitiative.objects.select_related('user')
        ))

    initiatives_qs = Initiative.objects.filter(strategic_goal__in=goals)

    employees_progress = None
    departments_progress = None

    if role in ['M', 'CM']:
        goals = goals.filter(department=user.department)
        initiatives_qs = initiatives_qs.filter(strategic_goal__department=user.department)
        employees_progress = (
            initiatives_qs.values('userinitiative__user__username')
                          .annotate(completed_initiatives=Count('id', filter=Q(userinitiative__status='C')))
                          .order_by('-completed_initiatives')
        )
    elif role == 'GM':
        departments_progress = (
            goals.values('department__department_name')
                 .annotate(total_goals=Count('id'),
                           completed_goals=Count('id', filter=Q(goal_status='C')))
                 .order_by('-completed_goals')
        )

    # -----------------------------
    goals_not_started = goals.filter(goal_status='NS').count()
    goals_in_progress = goals.filter(goal_status='IP').count()
    goals_completed = goals.filter(goal_status='C').count()
    goals_delayed = goals.filter(goal_status='D').count()

    # -----------------------------
    initiatives_not_started = initiatives_qs.filter(userinitiative__status='NS').count()
    initiatives_in_progress = initiatives_qs.filter(userinitiative__status='IP').count()
    initiatives_completed = initiatives_qs.filter(userinitiative__status='C').count()
    initiatives_delayed = initiatives_qs.filter(userinitiative__status='D').count()

    # -----------------------------
    priority_map = {'C': 1, 'H': 2, 'M': 3, 'L': 4}

    top_3_goals = sorted(goals, key=lambda g: priority_map.get(g.goal_priority, 99))[:3]
    top_3_initiative = sorted(initiatives_qs, key=lambda g: priority_map.get(g.priority, 99))[:3]

    # ----------------------------

    return {
        'goals': goals,
        'goals_count': goals.count(),
        'initiatives_count': initiatives_qs.count(),

        'can_edit': can_edit,

        # goals status
        'goals_not_started': goals_not_started,
        'goals_in_progress': goals_in_progress,
        'goals_completed': goals_completed,
        'goals_delayed': goals_delayed,

        # initiatives status
        'initiatives_not_started': initiatives_not_started,
        'initiatives_in_progress': initiatives_in_progress,
        'initiatives_completed': initiatives_completed,
        'initiatives_delayed': initiatives_delayed,

        # top 3 goals and initiatives based on priority
        'top_3_goals': top_3_goals,
        'top_3_initiative': top_3_initiative,
    
        'departments_progress': departments_progress,
        'employees_progress': employees_progress
    }
