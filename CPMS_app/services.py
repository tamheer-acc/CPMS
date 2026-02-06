import json
import re
from statistics import mean
from datetime import date, timedelta
from datetime import datetime, time
from django.utils.timezone import make_aware
from statistics import mean
from django.utils import timezone
from django.utils.timezone import now
from django.core.serializers.json import DjangoJSONEncoder
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth import get_user_model
from django.forms.models import model_to_dict
from django.db.models import Count, Q, Case, When, Value, IntegerField, Avg, Prefetch,OuterRef, Subquery
from django.db.models.functions import TruncMonth
from .models import Note, StrategicGoal, Initiative, Log, StrategicPlan, User, UserInitiative, ProgressLog
from django.db.models import OuterRef, Subquery, Q
from collections import defaultdict
from django.utils.timezone import localtime
from itertools import groupby
from django.db.models import Case, When, F, Subquery, OuterRef
from django.db.models.functions import Coalesce
from django.db.models import CharField
from django.db.models.functions import Cast

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
    # '''
    last_reply_sender = Subquery(
    Note.objects.filter(
        parent_note=OuterRef('pk')
    )
    .order_by('-created_at')
    .values('sender_id')[:1],
    output_field=IntegerField()
)

    # GM never receives notes
    if user.role.role_name == 'GM':
        return 0

    role = user.role.role_name

    if role in ['M', 'CM']:
        return (
            Note.objects
            .filter(parent_note__isnull=True)
           .annotate(
               last_sender=Coalesce(
                   last_reply_sender,
                   F('sender_id'),
                   output_field=IntegerField()
                   )
            )

            .exclude(last_sender=user.id)
            .exclude(read_by=user)
            .filter(
                Q(receiver=user.id) |
                Q(sender=user.id) |
                Q(strategic_goal__department=user.department) |
                Q(initiative__userinitiative__user=user)
            )
            .values('pk').distinct().count()

        )

    # Employee
    return (
        Note.objects
        .filter(parent_note__isnull=True)
        .annotate(
               last_sender=Coalesce(
                   last_reply_sender,
                   F('sender_id'),
                   output_field=IntegerField()
                   )
            )
        .exclude(last_sender=user.id)
        .exclude(read_by=user)
        .filter(
            Q(receiver=user.id) |
            Q(initiative__userinitiative__user=user)
        )
        .values('pk').distinct().count()

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


# ---------- Helper to clean log values ----------
def clean_log_value(value):
    """Clean log value to convert datetime.date(...) into JSON-friendly string"""
    if not value:
        return "{}"

    def replace_date(match):
        y, m, d = map(int, match.groups())
        return f'"{y:04d}-{m:02d}-{d:02d}"'

    return re.sub(r"datetime\.date\((\d+),\s*(\d+),\s*(\d+)\)", replace_date, value)

def get_timeline_data(plan, user):
    timeline_data = []

    # ===== Select items based on user role =====
    if user.role.role_name == 'GM':
        items_qs = StrategicGoal.objects.filter(strategicplan=plan)
        table_name = 'StrategicGoal'
    elif user.role.role_name in ['CM', 'M']:
        items_qs = Initiative.objects.filter(strategic_goal__strategicplan=plan)
        table_name = 'Initiative'
    else:
        return timeline_data

    if not items_qs.exists():
        return timeline_data

    # ===== Fetch all related UserInitiatives =====
    if table_name == 'Initiative':
        user_initiatives = UserInitiative.objects.filter(initiative_id__in=items_qs.values_list('id', flat=True))
    else:
        initiatives = Initiative.objects.filter(strategic_goal_id__in=items_qs.values_list('id', flat=True))
        user_initiatives = UserInitiative.objects.filter(initiative__in=initiatives)

    # ===== Fetch logs for all UserInitiatives =====
    ui_ids = list(user_initiatives.values_list('id', flat=True))
    all_logs = Log.objects.filter(
        table_name='UserInitiative',
        record_id__in=[str(i) for i in ui_ids],
        action='تعديل'
    ).order_by('record_id', 'created_at')

    logs_grouped = {k: list(g) for k, g in groupby(all_logs, key=lambda log: log.record_id)}

    # ===== Map UserInitiative IDs by Initiative =====
    ui_by_initiative = {}
    for ui in user_initiatives:
        ui_by_initiative.setdefault(ui.initiative_id, []).append(ui.id)

    # ---------- Process each item ----------
    for item in items_qs:
        completed_time = None
        delayed_item = False

        if table_name == 'Initiative':
            # ===== Initiative =====
            title = item.title
            planned_end = item.end_date

            # ===== Calculate average progress =====
            avg_progress = avg_calculator(
                UserInitiative.objects.filter(initiative=item, user__role__role_name='E')
            )

            # ===== Get last completion time =====
            progress_list = []
            for ui_id in ui_by_initiative.get(item.id, []):
                for log in logs_grouped.get(str(ui_id), []):
                    try:
                        new_data = json.loads(clean_log_value(log.new_value))
                        progress = int(str(new_data.get('progress', '0')).strip() or 0)
                        if progress >= 100:
                            progress_list.append(localtime(log.created_at))
                    except Exception as e:
                        print(f"Error parsing log {log.id}: {e}")

            if progress_list:
                completed_time = max(progress_list)

            # ===== Determine status =====
            initiative_status = calc_initiative_status_for_Cards(item)
            if avg_progress >= 100:
                completion_status = 'completed'
                time_status = 'on_time' if initiative_status == 'C' else 'late'
            else:
                completion_status = 'not_completed'
                time_status = 'not_completed'

        else:
            # ===== Strategic Goal =====
            title = item.goal_title
            planned_end = item.end_date

            # ===== Calculate goal progress from initiatives =====
            avg_progress = calc_goal_progress(item)

            # ===== Get last completion time from all related UserInitiatives =====
            progress_list = []
            for initiative in item.initiative_set.all():
                for ui_id in ui_by_initiative.get(initiative.id, []):
                    for log in logs_grouped.get(str(ui_id), []):
                        try:
                            new_data = json.loads(clean_log_value(log.new_value))
                            old_data = json.loads(clean_log_value(log.old_value))

                            new_progress = int(str(new_data.get('progress', '0')).strip() or 0)
                            old_progress = int(str(old_data.get('progress', '0')).strip() or 0)
                            if new_progress >= 100 and old_progress < 100:
                                progress_list.append(localtime(log.created_at))
                        except Exception as e:
                            print(f"Error parsing log {log.id}: {e}")

            if progress_list:
                completed_time = max(progress_list)

            # ===== Determine status =====
            goal_status = calc_goal_status_for_cards(item)
            if avg_progress >= 100:
                completion_status = 'completed'
                time_status = 'on_time' if goal_status == 'C' else 'late'
            else:
                completion_status = 'not_completed'
                time_status = 'not_completed'

        # ===== Calculate delayed_item =====
        delayed_item = False
        if completed_time and planned_end and completion_status == 'completed':
            delayed_item = completed_time.date() > planned_end

        # ===== Add data to timeline =====
        timeline_data.append({
            'title': title,
            'start': item.start_date.isoformat() if item.start_date else None,
            'planned_end': planned_end.isoformat() if planned_end else None,
            'completed_time': completed_time.isoformat() if completed_time else None,
            'completion_status': completion_status,
            'time_status': time_status,
            'delayed_item': delayed_item,
            'average_progress': avg_progress
        })

    return timeline_data


def get_plan_dashboard(plan, user):
    role = user.role.role_name
 
    # ====== Goals (filter by role) ======
    goals = StrategicGoal.objects.filter(strategicplan=plan).prefetch_related('initiative_set')
    # if role in ['M', 'CM']:
    #     goals = goals.filter(department=user.department)
    
    # ====== Initiatives related to these goals ======
    initiatives_qs = Initiative.objects.filter(strategic_goal__in=goals)

    
    # ====== initiatives by goal (for display) ======
    initiatives_by_goal = {g.id: [] for g in goals}
    for ini in initiatives_qs:
        initiatives_by_goal[ini.strategic_goal_id].append(ini)

    # ====== Compute initiative status using avg_map ======
    initiative_status_map = {}
    for ini in initiatives_qs:
        status = calc_initiative_status_by_avg(ini)
        initiative_status_map[ini.id] = status

    # ======== top 5 employees / departments ============
    if role in ['M', 'CM']:
     employees_progress = (
        UserInitiative.objects
        .filter(initiative__in=initiatives_qs, user__role__role_name='E')
        .values('user__first_name', 'user__last_name')
        .annotate(avg_progress=Avg('progress'))
        .order_by('-avg_progress')[:5]
    )
     top5_labels = [ f"{e['user__first_name']} {e['user__last_name']}" for e in employees_progress]
     top5_progress = [round(float(e['avg_progress'] or 0),2) for e in employees_progress]

    elif role == 'GM':
     departments_progress = (
        goals.values('department_id', 'department__department_name')
             .annotate(avg_progress=Avg('initiative__userinitiative__progress'))
             .order_by('-avg_progress')[:5]
    )
     top5_labels = [d['department__department_name'] for d in departments_progress]
     top5_progress = [round(float(d['avg_progress'] or 0),2) for d in departments_progress]

    # ====== Goals total & status counts ======
    goals_not_started = goals.filter(goal_status='NS').count()
    goals_in_progress = goals.filter(goal_status='IP').count()
    goals_completed = goals.filter(goal_status='C').count()
    goals_delayed = goals.filter(goal_status='D').count()

    goals_total = goals.count()

    goals_status = [
        goals_not_started,
        goals_in_progress,
        goals_delayed,
          goals_completed,
    ]

    # ====== Initiatives total & status counts ======
    initiatives_total = len(initiatives_qs)
    initiative_status = []

    initiative_status_counts = {'NS': 0, 'IP': 0, 'C': 0, 'D': 0}
    for status in initiative_status_map.values():
     initiative_status_counts[status] += 1

     initiative_status = [
        initiative_status_counts['NS'],
        initiative_status_counts['IP'],
        initiative_status_counts['D'],
        initiative_status_counts['C'],
    ]

    # ========================= Plan avg =================================
    if goals_total == 0:
        plan_avg = 0
    else:
         plan_avg = calc_plan_progress(plan)

    plan_avg = plan_avg or 0
    avg_by_2 = plan_avg/2
    todays_date = timezone.now().date()
    is_plan_late = todays_date >= plan.end_date and plan_avg != 100
        
    # ===================== Donut data ======================================
    goals_data = [
        {"id": g.id, "status": g.goal_status}
        for g in goals
    ]

    initiatives_data = [
        {"id": ini.id, "status": initiative_status_map[ini.id]}
        for ini in initiatives_qs
    ]
    #================ Pie chart based on priority ==========================
    PRIORITY_MAP = {
    'C': 'حرجة',
    'H': 'عالية',
    'M': 'متوسطة',
    'L': 'منخفضة',
}
    priority_colors = {
    'C': "#A13525",  
    'H': "#E59256",  
    'M': "#F2C75C", 
    'L': "#00685E", 
    }
   
    priority_stats = defaultdict(list)

    for goal in goals:
       progress = calc_goal_progress(goal)
       priority_stats[goal.goal_priority].append(progress)

    chart_data = []

    for priority, progresses in priority_stats.items():
       avg_progress = round(sum(progresses)/len(progresses), 2) if progresses else 0
       chart_data.append({
        'priority_label': PRIORITY_MAP.get(priority, priority),
        'avg_progress': avg_progress,
        'count': len(progresses),
        'color': priority_colors.get(priority, '#bdc3c7')
    })
       
    #=========================== KPI Chart ==================================
    initiatives = initiatives_qs.prefetch_related('kpi_set', 'strategic_goal__department')
    kpi_chart_data = []

    for initiative in initiatives:
      for kpi in initiative.kpi_set.all():
        actual = float(kpi.actual_value) if kpi.actual_value is not None else 0
        target = float(kpi.target_value) if kpi.target_value is not None else 1  # لتجنب القسمة على صفر
        ratio = actual / target if target else 0

        if ratio < 0.25:
            color = "#A13525"  
        elif ratio < 0.5:
            color = "#E59256"  
        elif ratio < 0.75:
            color = "#F2C75C"  
        else:
            color = "#00685E"  

        kpi_chart_data.append({
            'initiative_title': initiative.title,
            'department': initiative.strategic_goal.department.department_name,
            'kpi_name': kpi.kpi,
            'unit': kpi.unit,
            'target': target,
            'actual': actual,
            'color': color
      })
    
    Kpi_length = len(kpi_chart_data)

    #===================== Timeline chart & cards ==================================
    timeline_data=get_timeline_data(plan, user)
    delayed_items = [item for item in timeline_data if item['delayed_item']]
    delayed_items_length = len(delayed_items)

    completed_on_time = sum(
          1 for x in timeline_data
          if x['completion_status'] == 'completed' and x['time_status'] == 'on_time'
       )

    completed_late = sum(
          1 for x in timeline_data
          if x['completion_status'] == 'completed' and x['time_status'] == 'late'
    )

    not_completed = sum(
          1 for x in timeline_data
          if x['completion_status'] != 'completed'
    )
    
    
    return {
        'goals': goals,
        'goals_total': goals_total,
        'initiatives_count': initiatives_total,
        'role':role,

        'goals_status_json': json.dumps(goals_data),
        'goals_length': len(goals_data),

        'initiative_status_json': json.dumps(initiatives_data),
        'initiatives_length': len(initiatives_data),

        'chart_goals_json': json.dumps(chart_data),
        'chart_length': len(chart_data),

        'kpi_chart_data_json': json.dumps(kpi_chart_data),
        'Kpi_length': Kpi_length,

        'timeline_json': json.dumps(timeline_data),
        'timeline_length': delayed_items_length,

        'completed_on_time': completed_on_time,
        'completed_late': completed_late,
        'not_completed': not_completed,

        'plan_avg': avg_by_2,
        'is_plan_late': is_plan_late,

        'goals_data_json': json.dumps(goals_status),
        'goals_data_length': len(goals_status),

        'initiatives_data_json': json.dumps(initiative_status),
        'initiative_data_length': len(initiative_status),

        'top5_labels_json': json.dumps(top5_labels),
        'top5_progress_json': json.dumps(top5_progress),
        'top5_length': len(top5_progress)
    }

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
       return 'C'        # Completed On Time

    # Not completed & time finished
    if days_left <= 0.10*total_days: #today > end_date and initiative_average < 100:
        return 'D'    
  
    # In progress
    if initiative_average > 0:
        return 'IP'

    # Not started
    return 'NS'

#---------------------------------------------------------------------------
def calc_initiative_status_for_Cards(initiative):

    initiative_average = avg_calculator(UserInitiative.objects.filter(initiative = initiative, user__role__role_name = 'E'))
    end_date = initiative.end_date
    today = date.today()

    # Completed
    if initiative_average >= 100:
        if today <= end_date:
            return 'C'        # Completed On Time
        else:
            return 'CL'       # Completed late

    # Not completed & time finished
    if today >= end_date and initiative_average < 100:
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

    if avg_progress >= 100:
        return 'C'

    if days_left <= 0.10*total_days: #today >= end_date and avg_progress < 100:
        return 'D'    

    if avg_progress > 0:
        return 'IP'

    return 'NS'

#==========================================================
def calc_goal_status_for_cards(goal):
    end_date = goal.end_date
    today = date.today()

    initiatives = goal.initiative_set.all()

    if not initiatives.exists():
        return 'NS'

    avg_progress = calc_goal_progress(goal)

    if today >= end_date and avg_progress < 100:
        return 'D'    

    if avg_progress >= 100:
        if today <= end_date:
            return 'C'        # Completed On Time
        else:
            return 'CL'
        
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

    return round(total / goals.count(),2)

#==================================================
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
    active_plan = StrategicPlan.objects.filter(is_active = True).first()
    for dept in departments:
        initiatives = Initiative.objects.filter(
            userinitiative__user__department=dept, strategic_goal__strategicplan = active_plan
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
