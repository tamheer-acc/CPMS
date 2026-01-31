import json
from statistics import mean
from datetime import date, timedelta
from statistics import mean
from django.utils import timezone
from django.utils.timezone import now
from django.core.serializers.json import DjangoJSONEncoder
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth import get_user_model
from django.forms.models import model_to_dict
from django.db.models import Count, Q, Case, When, Value, IntegerField, Avg, Prefetch,OuterRef, Subquery
from django.db.models.functions import TruncMonth
from .models import Note, StrategicGoal, Initiative, Log, UserInitiative, ProgressLog
from collections import defaultdict

def format_log_values(old_value, new_value, action, instance=None):
    """
    Return human-readable log text instead of raw JSON
    """
    def format_field(key, value):
        if instance:
            try:
                field = instance._meta.get_field(key)

                if hasattr(field, "choices") and field.choices:
                    for k, v in field.choices:
                        if str(k) == str(value):
                            value = v
                            break

                if field.is_relation and value is not None:
                    related_model = field.related_model
                    related_obj = related_model.objects.filter(pk=value).first()
                    if related_obj:
                        value = str(related_obj)
                    
                # if isinstance(field, models.BooleanField):
                #     value = "نعم" if value else "لا"

            except Exception:
                pass

        return f"• {key}: {value}"

    # إضافة
    if action == "إضافة" and new_value:
        data = json.loads(new_value)
        return "\n".join([format_field(k, v) for k, v in data.items()])

    # حذف
    if action == "حذف" and old_value:
        data = json.loads(old_value)
        return "\n".join([format_field(k, v) for k, v in data.items()])

    # تعديل
    if action == "تعديل" and old_value and new_value:
        old = json.loads(old_value)
        new = json.loads(new_value)

        changes = []
        for key in new:
            if old.get(key) != new.get(key):
                changes.append(
                    f"• {key}: {old.get(key)} → {new.get(key)}"
                )

        return "\n".join(changes) if changes else "لا يوجد تغييرات فعلية"

    return ""



def model_to_dict_with_usernames(instance):
    """
    Convert model to dict and convert FK user to username/full name.
    """
    User = get_user_model()
    data = model_to_dict(instance)

    for field in instance._meta.fields:
        if getattr(field, "related_model", None) == User:
            user_obj = getattr(instance, field.name)
            data[field.name] = user_obj.get_full_name() if user_obj else None
    
    # Convert M2M fields (مثل read_by)
    for field in instance._meta.many_to_many:
        if getattr(field, "related_model", None) == User:
            users = getattr(instance, field.name).all()
            data[field.name] = [u.get_full_name() for u in users]

    if hasattr(instance, "parent_note") and instance.parent_note:
        parent = instance.parent_note
        parent_title = parent.title or ""

        if not data.get("title"):
            data["title"] = f"رد:{parent_title} "


    return data



def create_log(user, action, instance=None, old_data=None, table_name=None, record_id=None):
    """
    General helper to log any action:
    - LOGIN/LOGOUT -> user only
    - CREATE -> new data
    - UPDATE -> old and new data
    - DELETE -> old data
    - OTHER -> event only (like star/unstar)
    """
    # LOGIN/LOGOUT
    if action in ["تسجيل دخول", "تسجيل خروج"]:
        Log.objects.create(
            user=user,
            action=action,
            table_name="User",
            record_id=None,
            old_value=None,
            new_value=None
        )
        return

    new_data = model_to_dict_with_usernames(instance) if instance else None

    if instance:
        table_name = instance.__class__.__name__
        record_id = instance.pk

    # CREATE
    if action == "إضافة":
        old_value = None
        new_value = json.dumps(new_data, ensure_ascii=False, cls=DjangoJSONEncoder)

    # UPDATE
    elif action == "تعديل":
        old_value = json.dumps(old_data, ensure_ascii=False, cls=DjangoJSONEncoder)
        new_value = json.dumps(new_data, ensure_ascii=False, cls=DjangoJSONEncoder)

    # DELETE
    elif action == "حذف":
        old_value = json.dumps(old_data, ensure_ascii=False, cls=DjangoJSONEncoder)
        new_value = None

    else:
        old_value = json.dumps(old_data, ensure_ascii=False, cls=DjangoJSONEncoder)
        new_value = json.dumps(new_data, ensure_ascii=False, cls=DjangoJSONEncoder)

    Log.objects.create(
        user=user,
        table_name=table_name,
        record_id=record_id,
        action=action,
        old_value=old_value,
        new_value=new_value
    )



def get_unread_notes_count(user):
    '''
    -  Returns unread notes count for the user   
    -  Use: inside AllNotesView, and NoteDetailview
    '''

    last_reply_sender = Note.objects.filter(
        parent_note=OuterRef('pk')
    ).order_by('-created_at').values('sender')[:1]

    # GM never receives notes
    if user.role.role_name == 'GM':
        return 0

    role = user.role.role_name

    if role in ['M', 'CM']:
        return (
            Note.objects
            .filter(parent_note__isnull=True)
            .annotate(last_sender=Subquery(last_reply_sender))
            .exclude(last_sender=user)
            .exclude(read_by=user)
            .filter(
                Q(receiver=user) |
                Q(strategic_goal__department=user.department) |
                Q(initiative__userinitiative__user=user)
            )
            .distinct()
            .count()
        )

    # Employee
    return (
        Note.objects
        .filter(parent_note__isnull=True)
        .annotate(last_sender=Subquery(last_reply_sender))
        .exclude(last_sender=user)
        .exclude(read_by=user)
        .filter(
            Q(receiver=user) |
            Q(initiative__userinitiative__user=user)
        )
        .distinct()
        .count()
    )



def generate_KPIs(goal, initiative, department):

# llm.create_chat_completion(
# 	messages = [
# 		{
# 			"role": "user",
# 			"content":
# "انت محلل استراتيجي خبير في وزارة النقل والخدمات اللوجستية في السعودية، اقترح لي كرؤوس أقلام فقط ثلاث
# مؤشرات قياس الأداء لمبادرة 
# (initiative.title)، 
# تحت الهدف الاستراتيجي
# (goal.title)،
# لإدارة 
# (department)
# 		}
# 	]
# )
    # text = response["choices"][0]["message"]["content"]

    # kpis = text.split("\n")
    # kpis = [kpi.strip() for kpi in kpis if kpi.strip()]  
    # print(kpis)
    return ['kpi suggestion1', 'kpi suggestion2', 'kpi suggestion3']




def donutChart_data():
    return



# def build_donut_data(not_started, in_progress, completed, delayed, total):
#     total = total or 1
#     data = [
#         ('لم تبدأ', '#9CA3AF', round(not_started / total * 100)),
#         ('جارية', '#3B82F6', round(in_progress / total * 100)),
#         ('مكتملة', '#10B981', round(completed / total * 100)),
#         ('متأخرة', '#EF4444', round(delayed / total * 100)),
#     ]

#     result = []
#     offset = 0
#     for label, color, value in data:
#         result.append({
#             'label': label,
#             'color': color,
#             'value': value,
#             'offset': offset
#         })
#         offset += value

#     return result




def get_time_based_progress_for_role(user_initiatives_qs, role):
    """
    Returns ready-to-use progress data for template based on role
    """

    today = date.today()

    employees = defaultdict(lambda: {
        'name': '',
        'department_id': None,
        'department_name': '',
        'scores': []
    })

    # ===== Calculate employees performance =====
    for ui in user_initiatives_qs.select_related(
        'user',
        'initiative',
        'user__department'
    ):
        start = ui.initiative.start_date
        end = ui.initiative.end_date
        progress = ui.progress or 0

        total_days = max((end - start).days, 1)
        elapsed_days = min(max((today - start).days, 0), total_days)

        time_ratio = elapsed_days / total_days
        actual_ratio = progress / 100

        score = 0 if time_ratio == 0 else (actual_ratio / time_ratio) * 100
        score = round(min(score, 100), 1)

        emp = employees[ui.user.id]
        emp['name'] = ui.user.get_full_name() or ui.user.username
        emp['department_id'] = ui.user.department_id
        emp['department_name'] = ui.user.department.department_name if ui.user.department else ''
        emp['scores'].append(score)

    # ===== Final employee progress =====
    employees_result = []
    for emp_id, data in employees.items():
        avg_score = round(sum(data['scores']) / len(data['scores']), 1)

        employees_result.append({
            'id': emp_id,
            'name': data['name'],
            'percentage': avg_score
        })

    emp_most = max(employees_result, key=lambda x: x['percentage'], default=None)
    emp_least = min(employees_result, key=lambda x: x['percentage'], default=None)

    # ===== Department progress (from employees) =====
    departments = defaultdict(list)
    for emp in employees_result:
        dept_id = next(
            (ui.user.department_id for ui in user_initiatives_qs if ui.user.id == emp['id']),
            None
        )
        departments[dept_id].append(emp['percentage'])

    departments_result = []
    for dept_id, scores in departments.items():
        dept_name = next(
            (ui.user.department.department_name
             for ui in user_initiatives_qs
             if ui.user.department_id == dept_id),
            ''
        )

        departments_result.append({
            'id': dept_id,
            'name': dept_name,
            'percentage': round(sum(scores) / len(scores), 1)
        })

    dept_most = max(departments_result, key=lambda x: x['percentage'], default=None)
    dept_least = min(departments_result, key=lambda x: x['percentage'], default=None)

    # ===== Return based on role =====
    if role == 'GM':
        return {
            'items': departments_result,
            'top': dept_most,
            'low': dept_least,
            'view_type': 'departments'
        }

    return {
        'items': employees_result,
        'top': emp_most,
        'low': emp_least,
        'view_type': 'employees'
    }



def calculate_goal_timeline(goal):
    today = timezone.now().date()
    start = goal.start_date
    end = goal.end_date
    duration = (end - start).days

    if today <= start:
        return {
            'passed': 0,
            'duration' : duration,
            "remaining_duration": (end - start).days,
            "passed_duration_percent": 0
        }

    if today >= end:
        return {
            'passed': (end - start).days,
            'duration' : duration,
            "remaining_duration": 0,
            "passed_duration_percent": 100
        }

    passed = (today - start).days

    return {
        'passed':passed,
        'duration' : duration,
        "remaining_duration": (end - today).days,
        "passed_duration_percent": round((passed / duration) * 100)
    }



def get_plan_dashboard(plan, user):
    role = user.role.role_name
    can_edit = False

    # ====== Goals (filter by role) ======
    goals = StrategicGoal.objects.filter(strategicplan=plan).prefetch_related('initiative_set')


    if role in ['M', 'CM']:
        goals = goals.filter(department=user.department)

    # ====== Initiatives related to these goals ======
    initiatives_qs = Initiative.objects.filter(strategic_goal__in=goals)

    # ====== If normal user (not manager), show only their initiatives ======
    if role not in ['M', 'CM', 'GM']:
        initiatives_qs = initiatives_qs.filter(userinitiative__user=user).distinct()

    # ====== Precompute avg progress for each initiative (efficient) ======
    
    # ====== Compute initiative status using avg_map ======
    initiative_status_map = {}
    for ini in initiatives_qs:
        initiative_status_map[ini.id] = calc_initiative_status_by_avg(ini)

    # ====== initiatives by goal (for display) ======
    initiatives_by_goal = {g.id: [] for g in goals}
    for ini in initiatives_qs:
        initiatives_by_goal[ini.strategic_goal_id].append(ini)

   # ====== USER INITIATIVES QS (important) ======
    user_initiatives_qs = UserInitiative.objects.filter(
        initiative__in=initiatives_qs
    ).select_related('user', 'user__department', 'initiative')

    # ====== Progress data (employees or departments) ======
    if role in ['M', 'CM']:
        # filter only employees of that department (exclude managers)
        user_initiatives_qs = user_initiatives_qs.filter(
            user__department=user.department
        ).exclude(
            user__role__role_name__in=['M', 'CM', 'GM']
        )

    progress_data = get_time_based_progress_for_role(user_initiatives_qs, role)
    # ====== Limit to Top 5 ======
    progress_data['items'] = sorted(
      progress_data['items'],
      key=lambda x: x['percentage'],
      reverse=True
)[:5]
    progress_data_json = {
    "labels": [x['name'] for x in progress_data['items']],
    "values": [x['percentage'] for x in progress_data['items']],
    "view_type": progress_data['view_type']
}



    # ====== Progress / top 5 etc ======
    employees_progress = None
    departments_progress = None

    if role in ['M', 'CM']:
        employees_progress = (
            initiatives_qs.values('userinitiative__user__username')
                          .annotate(completed_initiatives=Count('id', filter=Q(userinitiative__status='C')))
                          .order_by('-completed_initiatives')[:5]
        )
    elif role == 'GM':
        departments_progress = (
            goals.values('department__department_name')
                 .annotate(total_goals=Count('id'),
                           completed_goals=Count('id', filter=Q(goal_status='C')))
                 .order_by('-completed_goals')[:5]
        )

    # ====== Goals status counts ======
    goals_not_started = goals.filter(goal_status='NS').count()
    goals_in_progress = goals.filter(goal_status='IP').count()
    goals_completed = goals.filter(goal_status='C').count()
    goals_delayed = goals.filter(goal_status='D').count()

    goals_total = goals.count()

    goals_status = [
        goals_not_started,
        goals_in_progress,
        goals_completed,
        goals_delayed
    ]

    # ====== Initiatives totals & status counts ======
    initiatives_total = initiatives_qs.count()

    initiative_status_counts = {
        'NS': 0, 'IP': 0, 'C': 0, 'D': 0
    }
    for status in initiative_status_map.values():
        initiative_status_counts[status] += 1

    initiative_status = [
        initiative_status_counts['NS'],
        initiative_status_counts['IP'],
        initiative_status_counts['C'],
        initiative_status_counts['D']
    ]


    labels = ['لم تبدأ', 'قيد التنفيذ', 'مكتملة', 'متأخرة']


    # ====== Top goals & initiatives by priority ======
    priority_map = {'C': 1, 'H': 2, 'M': 3, 'L': 4}

    top_3_goals = sorted(goals, key=lambda g: priority_map.get(g.goal_priority, 99))[:3]
    top_3_initiative = sorted(initiatives_qs, key=lambda g: priority_map.get(g.priority, 99))[:3]

    # ====== Delayed monthly ======
    delayed_goals_list = get_delayed_goals_with_days(goals)

    delayed_titles = [g["goal_title"] for g in delayed_goals_list]
    delayed_days = [g["delay_days"] for g in delayed_goals_list]


    # ====== Plan avg ======
    if goals_total == 0:
        plan_avg = 0
    else:
       
       plan_avg = calc_plan_progress(plan)

  
    return {
        'goals': goals,
        'goals_total': goals_total,
        'initiatives_count': initiatives_total,

        'goals_status_json': json.dumps(goals_status),
        'labels_json': json.dumps(labels),
        'initiative_status_json': json.dumps(initiative_status),

        "delayed_goals_list": delayed_goals_list,
        "delayed_goals_titles_json": json.dumps(delayed_titles),
        "delayed_goals_delay_days_json": json.dumps(delayed_days),
        'plan_avg': plan_avg,

        'progress_data_json': json.dumps(progress_data_json),

        'departments_progress': json.dumps(list(departments_progress)) if departments_progress else "[]",
        'employees_progress': json.dumps(list(employees_progress)) if employees_progress else "[]"
    }


def get_delayed_goals_with_days(goals_qs):
    today = date.today()
    delayed = []

    for goal in goals_qs.filter(goal_status='D'):
        delay_days = (today - goal.end_date).days
        if delay_days < 0:
            delay_days = 0

        delayed.append({
            "goal_id": goal.id,
            "goal_title": goal.goal_title,
            "delay_days": delay_days,
            "end_date": goal.end_date.strftime("%Y-%m-%d"),
            "goal_status": goal.goal_status,
        })

    delayed.sort(key=lambda x: x['delay_days'], reverse=True)

    return delayed


# def get_plan_dashboard(plan, user):
#     role = user.role.role_name
#     can_edit = False  # Read only

#     goals = plan.goals.prefetch_related(
#     Prefetch(
#         'initiative_set__userinitiative_set',
#         queryset=UserInitiative.objects.select_related('user')
#         ))
#     i = [
#      initiative
#      for goal in goals
#      for initiative in goal.initiative_set.all()
#      if any(
#         ui.user_id == user.id
#         for ui in initiative.userinitiative_set.all()
#      )
#     ]

#     initiatives_qs = Initiative.objects.filter(strategic_goal__in=goals)

#     employees_progress = None
#     departments_progress = None

#     if role in ['M', 'CM']:
#         goals = goals.filter(department=user.department)
#         initiatives_qs = initiatives_qs.filter(strategic_goal__department=user.department)
#         employees_progress = (
#             initiatives_qs.values('userinitiative__user__username')
#                           .annotate(completed_initiatives=Count('id', filter=Q(userinitiative__status='C')))
#                           .order_by('-completed_initiatives')[:5]
#         )
#     elif role == 'GM':
#         departments_progress = (
#             goals.values('department__department_name')
#                  .annotate(total_goals=Count('id'),
#                            completed_goals=Count('id', filter=Q(goal_status='C')))
#                  .order_by('-completed_goals')[:5]
#         )

#     # -----------------------------
#     goals_not_started = goals.filter(goal_status='NS').count()
#     goals_in_progress = goals.filter(goal_status='IP').count()
#     goals_completed = goals.filter(goal_status='C').count()
#     goals_delayed = goals.filter(goal_status='D').count()

#     # -----------------------------
#     # initiatives_not_started = initiatives_qs.filter(initiative_status='NS').count()
#     # initiatives_in_progress = initiatives_qs.filter(initiative_status='IP').count()
#     # initiatives_completed = initiatives_qs.filter(initiative_status='C').count()
#     # initiatives_delayed = initiatives_qs.filter(initiative_status='D').count()

#     # -----------------------------
#     priority_map = {'C': 1, 'H': 2, 'M': 3, 'L': 4}

#     top_3_goals = sorted(goals, key=lambda g: priority_map.get(g.goal_priority, 99))[:3]
#     top_3_initiative = sorted(initiatives_qs, key=lambda g: priority_map.get(g.priority, 99))[:3]

#     # ----------------------------
#     goals_total = goals.count()

#     goals_status = [
#      goals_not_started,
#      goals_in_progress,
#      goals_completed,
#      goals_delayed
#     ]

#     initiatives_total = len(i)

#     # initiative_status = [
#     # initiatives_not_started,
#     # initiatives_in_progress,
#     # initiatives_completed,
#     # initiatives_delayed
#     # ]
    
#     departments_progress_json = json.dumps(list(departments_progress)) if departments_progress else "[]"
#     employees_progress_json = json.dumps(list(employees_progress)) if employees_progress else "[]"
    
#     delayed_goals_monthly = get_delayed_goals_monthly(goals, role, user)
#     if goals_total == 0:
#         plan_avg = 0
#     else:
#         sum_progress = sum(
#             goal_progress_from_status(g.goal_status) for g in goals
#         )
#         plan_avg = sum_progress / goals_total


#     return {
#         'goals': goals,
#         'goals_total': goals_total,
#         'initiatives_count':initiatives_total,
#         'goals_status': goals_status,
#         # 'initiative_status': initiative_status,
#         'delayed_goals_monthly': delayed_goals_monthly,
#         'plan_avg': round(plan_avg),
#         'plan_avg_by_two': round(plan_avg / 2),

#         'can_edit': can_edit,

#         # # goals status
#         # 'goals_not_started': goals_not_started,
#         # 'goals_in_progress': goals_in_progress,
#         # 'goals_completed': goals_completed,
#         # 'goals_delayed': goals_delayed,

#         # # initiatives status
#         # 'initiatives_not_started': initiatives_not_started,
#         # 'initiatives_in_progress': initiatives_in_progress,
#         # 'initiatives_completed': initiatives_completed,
#         # 'initiatives_delayed': initiatives_delayed,

#         # top 3 goals and initiatives based on priority
#         'top_3_goals': top_3_goals,
#         'top_3_initiative': top_3_initiative,
    
#         'departments_progress': departments_progress_json,
#         'employees_progress': employees_progress_json

#     }


def calc_user_initiative_status(user_initiative):
    """
    Calculate the status of a user initiative
    """

    start_date = user_initiative.initiative.start_date
    end_date = user_initiative.initiative.end_date
    progress = user_initiative.progress
    today = date.today()
    total_days = max((end_date - start_date).days, 1)
    days_left = 0 if end_date < today else (end_date - today).days
    
    if progress >= 100:
        return 'C'

    if days_left <= 0.10*total_days: #if the user is in last 10% of the duration, then they're late
        return 'D'
    
    if progress > 0:
        return 'IP'
    
    return 'NS'

#=============================initiative status=======================================
def calc_initiative_status_by_avg(initiative):

    initiative_average = avg_calculator(UserInitiative.objects.filter(initiative = initiative, user__role__role_name = 'E'))
    start_date = initiative.start_date
    end_date = initiative.end_date
    today = date.today()

    total_days = max((end_date - start_date).days, 1)
    days_left = (end_date - today).days

    # Completed
    if initiative_average >= 100:
        return 'C'

    # Delayed (if in last 10% of time and progress not enough)
    if days_left <= 0.10 * total_days and initiative_average < 100:
        return 'D'
  
    # In progress
    if initiative_average > 0:
        return 'IP'

    # Not started
    return 'NS'


#==============================goal progress=======================================
def calc_goal_progress(goal):
    initiatives = goal.initiative_set.all()

    initiatives_average_list = []
    for initiative in initiatives:
        initiatives_average_list.append(avg_calculator(UserInitiative.objects.filter(initiative = initiative, user__role__role_name = 'E')))
    goal_progress= mean(initiatives_average_list) if initiatives_average_list else 0
    return round(goal_progress, 2)
#=====================================================================
# def calc_goal_progress(goal, user):
#     qs = goal.initiative_set.all()

#     if user.role.role_name == 'E':
#         qs = qs.filter(userinitiative__user=user)

#     if not qs.exists():
#         return 0

#     avg = qs.aggregate(
#         avg=Avg('userinitiative__progress')
#     )['avg'] or 0

#     return round(float(avg), 2)

def calc_goal_progress(goal):
    initiatives = goal.initiative_set.all()

    initiatives_average_list = []
    for initiative in initiatives:
        initiatives_average_list.append(avg_calculator(UserInitiative.objects.filter(initiative = initiative, user__role__role_name = 'E')))

    goal_progress = mean(initiatives_average_list) if initiatives_average_list else 0
    

    return round(goal_progress, 2)


#==============================goal status=======================================
def calc_goal_status(goal):
    start_date = goal.start_date
    end_date = goal.end_date
    today = date.today()
    total_days = max((end_date - start_date).days, 1)
    days_left = (end_date - today).days

    initiatives = goal.initiative_set.all()

    if not initiatives.exists():
        return 'NS'

    avg_progress = calc_goal_progress(goal)

    if days_left <= 0.10 * total_days and avg_progress < 100:
        return 'D'

    if avg_progress >= 100:
        return 'C'

    if avg_progress > 0:
        return 'IP'

    return 'NS'

#==========================================================
def calc_plan_progress(plan):
    goals = plan.goals.all()

    if not goals.exists():
        return 0

    total = 0
    for goal in goals:
        total += calc_goal_progress(goal)

    return round(total / goals.count())




def filter_queryset(queryset, request, search_fields=None, status_field=None, priority_field=None):

    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', '').strip()
    priority = request.GET.get('priority', '').strip()
    sort = request.GET.get('sort', '').strip()
    q = Q()

    if search and search_fields:
        for field in search_fields:
            q |= Q(**{f"{field}__icontains": search})

    if status and status_field:
        field = queryset.model._meta.get_field(status_field)
        if field.get_internal_type() == 'BooleanField':
            q &= Q(**{status_field: status.lower() == 'active'})
        elif field.choices:
            q &= Q(**{status_field: status})

    if priority and priority_field:
      q &= Q(**{priority_field: priority})

    queryset = queryset.filter(q)

    if sort == 'priority' and priority_field:
        priority_order = Case(
            When(**{priority_field: 'C'}, then=Value(1)),
            When(**{priority_field: 'H'}, then=Value(2)),
            When(**{priority_field: 'M'}, then=Value(3)),
            When(**{priority_field: 'L'}, then=Value(4)),
            default=Value(5),
            output_field=IntegerField()
        )
        queryset = queryset.order_by(priority_order)

    if sort == 'date':
        queryset = queryset.order_by('-start_date')


    return queryset.distinct()



def paginate_queryset(queryset, request, per_page):
    """
    Returns paginated objects for a given QuerySet.
    """
    page = request.GET.get('page', 1)
    paginator = Paginator(queryset, per_page)
    
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    return page_obj.object_list, page_obj, paginator



def get_page_numbers(page_obj, paginator, max_surrounding=1):
    """
    Returns a list of page numbers for pagination, including:
    - always first and last page
    - pages around current page (max_surrounding before/after)
    - ellipsis ('...') where pages are skipped
    """
    if not page_obj or not paginator:
        return []
        
    total_pages = paginator.num_pages
    current = page_obj.number
    page_numbers = []

    for num in range(1, total_pages + 1):
        if num == 1 or num == total_pages or abs(num - current) <= max_surrounding:
            page_numbers.append(num)
        elif page_numbers[-1] != '...':
            page_numbers.append('...')

    return page_numbers


#  Dashboaed Helper Functions <3
def avg_calculator( data , field=None ):
    '''
    Docstring for avg_calculator
        calculates the average, ususally used for user initatives record but can be used for others
    :param data: data should be a queryset result
    :param field: field can be none if the average calculated is progress, other than that mst be specified
    '''
    # Book.objects.aggregate(Avg("price", default=0))
    # Book.objects << data 
    if field:
        key = f"{field}__avg"
        avrage = data.aggregate(Avg( field, default=0 ))[key]
    else:
        avrage  = data.aggregate(Avg('progress', default=0))['progress__avg']
    if avrage is None:
        return 0
    return round( avrage or 0 )



def order( data , key=None , reverse=False ): 
    '''
    Docstring for order
        order an iterable  
    :param data: to be sorted list 
    :param key: how to sort
    :param reverse: reversed or not, boolean
    :return: returns a sorted list
    :rtype: list
    '''
    return sorted( data , key=key , reverse=reverse )



def status_count( data ):
    '''
    Docstring for status_count
        calculates how many status occured 
    :param data: user initiatives objectS
    '''
    count  = { 'NS':0 , 'IP':0 , 'D':0 , 'C':0 }
    
    for user_initiative in data:
        status = calc_user_initiative_status(user_initiative)
        count[status] += 1
        
    return count 



def calc_delayed( data ):
    '''
    Docstring for calc_delayed
        categorize initiatives into overdue , late ( next 7 days ), and on time

    :param data: set of initiative, with end_date attribute 
    :return: 3 lists, overdue, late, and on_time
    '''
    overdue = []
    late = []
    on_time =[]
    
    today = date.today()
    next_week = today + timedelta(days=7)
    
    for initiative in data:
        if initiative.end_date < today:
            overdue.append(initiative) 

        elif initiative.end_date <= next_week:
            late.append(initiative)
            
        else:
            on_time.append(initiative)
            
    return overdue, late



def kpi_filter( list_of_kpis ):
    achieved = []
    in_progress = []
    not_started = [] 
    
    if not list_of_kpis:
        return [],[],[]
    
    for kpi in list_of_kpis:
        if kpi.start_value:
            
            # just created, not modified
            if kpi.start_value == kpi.actual_value:
                not_started.append(kpi.kpi)
                continue
            
            # the target is to reduce
            if kpi.start_value > kpi.target_value: 
                if kpi.actual_value <= kpi.target_value:
                    achieved.append(kpi.kpi)
                else:
                    in_progress.append(kpi.kpi)
                    
            # the target is to increase
            else: 
                if kpi.actual_value >= kpi.target_value:
                    achieved.append(kpi.kpi)
                else:
                    in_progress.append(kpi.kpi)
        else:
            not_started.append(kpi.kpi)
        
    return achieved, in_progress, not_started



def weight_initiative(initiative):
    user_initiatives = UserInitiative.objects.filter(initiative=initiative)
    if not user_initiatives.exists():
        return 0  # no progress 
    
    total_weight = 0
    for ui in user_initiatives:
        status = calc_user_initiative_status(ui)
        if status == 'C':  
            weight = 1
        elif status == 'IP':  
            weight = 0.5
        elif status == 'D':  
            weight = 0.2
        else:  # NS
            weight = 0
        total_weight += weight

    weighted_score = (total_weight / user_initiatives.count()) * 100
    return round(weighted_score, 2)



def departments_progress_over_time(departments, days_count=30):
    days = [(now() - timedelta(days=i)).date() for i in range(days_count - 1, -1, -1)]
    chart_data = {}

    for dept in departments:
        initiatives = Initiative.objects.filter(
            userinitiative__user__department=dept
        ).distinct()

        total_initiatives = initiatives.count()
        chart_data[dept.department_name] = []

        for day in days:
            total_progress = 0

            for initiative in initiatives:
                last_log = ProgressLog.objects.filter(
                    initiative=initiative,
                    timestamp__date__lte=day
                ).order_by('-timestamp').first()

                total_progress += last_log.progress if last_log else 0

            avg = total_progress / total_initiatives if total_initiatives else 0

            chart_data[dept.department_name].append({
                'date': day,
                'avg': round(avg, 2)
            })

    return chart_data

# def kpi_progress( list_of_kpis ):
#     # check logs for start 
#     for kpi in list_of_kpis:
#         logs = Log.objects.filter(table_name = 'KPI', record_id = kpi.pk).first
#         if logs:
#             # start_value = 
#             pass