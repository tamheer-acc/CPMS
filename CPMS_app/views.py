import ast, decimal,  json, re, math
from itertools import groupby
from datetime import datetime, time
from django import forms
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.timezone import now, timedelta
from django.utils.decorators import method_decorator
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, CreateView, TemplateView
from django.views.generic.edit import UpdateView, DeleteView
from django.views.decorators.cache import never_cache
from django.http import HttpResponse, JsonResponse
from django.forms import BooleanField, ModelForm
from django.forms.models import model_to_dict  
from django.template.loader import render_to_string
from django.db.models import Q,F, Case,Exists, When, Value, IntegerField, OuterRef, Subquery, BooleanField,CharField, Avg, Count
from django.db.models.functions import Concat, Coalesce
from django.db.models.query import QuerySet
from django.contrib import messages
from django.contrib.auth import login, get_user_model
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin #class based view
from django.contrib.auth.decorators import login_required, user_passes_test #function based view
from django.core.exceptions import PermissionDenied
from functools import wraps
from django.db.models import Prefetch
from .forms import InitiativeForm, KPIForm, NoteForm, StrategicGoalForm, StrategicPlanForm, UserInitiativeForm
from .models import ( STATUS, Role, Department, User, StrategicPlan, StrategicGoal,
                        Initiative, UserInitiative, KPI, Note, Log, ProgressLog)
from .services import ( calc_goal_status, calc_initiative_status_by_avg, generate_KPIs,  create_log, get_plan_dashboard, calc_user_initiative_status, 
                        filter_queryset, get_page_numbers, model_to_dict_with_usernames, paginate_queryset, status_count, avg_calculator, 
                        calc_delayed, kpi_filter, weight_initiative, get_unread_notes_count, departments_progress_over_time, calc_goal_progress, calculate_goal_timeline)
from django.db.models import Count
from django.utils.safestring import mark_safe
import json



class LogMixin:
    def __init__(self, request=None):
        self.request = request

    def get_user(self):
        return self.request.user if self.request and self.request.user.is_authenticated else None

    def log_create(self, instance):
        create_log(
            user=self.request.user if self.request.user.is_authenticated else None,
            action="إضافة",
            instance=instance
        )

    def log_update(self, old_instance, new_instance, action="تعديل"):
            old_data = old_instance if isinstance(old_instance, dict) else model_to_dict_with_usernames(old_instance)
            create_log(
                user=self.request.user if self.request.user.is_authenticated else None,
                action=action,
                instance=new_instance,
                old_data=old_data
            )


    def log_delete(self, instance):
        create_log(
            user=self.request.user if self.request.user.is_authenticated else None,
            action="حذف",
            instance=instance,
            old_data=model_to_dict_with_usernames(instance)
        )



#Helper class that acts like UserPassesTestMixin:
class RoleRequiredMixin(UserPassesTestMixin):
    allowed_roles = []

    def test_func(self):
        return self.request.user.role.role_name in self.allowed_roles

    def handle_no_permission(self):
        raise PermissionDenied("ليست لديك صلاحية لرؤية هذه الصفحة")



class InitiativePermissionMixin:
    '''
    Users can only access initiatives they are allowed to
    GM: All initaitves
    M: initiatives in their department
    CM: initiatives in their department
    E: initiatives they are assigned to
    Raise PermissionDenied for any URL tampering!
    '''

    def get_initiative_queryset(self):

        qs = Initiative.objects.none()
        user = self.request.user
        role = user.role.role_name
        active_plan = StrategicPlan.objects.filter(is_active = True).first()
        goal_id = self.kwargs.get('goal_id')

        if goal_id:
            goal = get_object_or_404(StrategicGoal, id=goal_id)

            if role == 'GM':
                return Initiative.objects.filter(strategic_goal__strategicplan = active_plan, strategic_goal = goal)

            elif user.department != goal.department:
                raise PermissionDenied("ليست لديك صلاحية لرؤية هذه الصفحة")

            elif role in ['CM','M']:
                
                qs = Initiative.objects.filter( strategic_goal__strategicplan = active_plan, strategic_goal = goal , strategic_goal__department = user.department)

            elif role == 'E':
                qs = Initiative.objects.filter(strategic_goal__strategicplan = active_plan, strategic_goal = goal , userinitiative__user = user )

            else:
                raise PermissionDenied("ليست لديك صلاحية لرؤية هذه الصفحة")

        else: # No goal id

            if role == 'GM' and not goal_id:
                return Initiative.objects.filter(strategic_goal__strategicplan = active_plan)

            elif role in ['CM','M','E']:
                qs = Initiative.objects.filter(strategic_goal__strategicplan = active_plan,userinitiative__user=user)

            else:
                raise PermissionDenied("ليست لديك صلاحية لرؤية هذه الصفحة")

        return qs.distinct()

    def get_queryset(self): #what will be returned
        qs = self.get_initiative_queryset()

        pk = self.kwargs.get('pk')
        if pk: #delete, update, detail
            if not qs.filter(pk=pk).exists(): #trying to url tamper
                raise PermissionDenied("ليست لديك صلاحية لرؤية هذه الصفحة")
        return qs



#########################################################################################################################
#                                                    RENAD's Views                                                      #
#########################################################################################################################



# ---------------------------
#  Access Denied View done
# ---------------------------
def access_denied_view(request, exception=None):
    return render(request, 'access_denied.html', status=403)



# ---------------------------
#  Page not Found View done
# ---------------------------
def page_not_found_view(request, exception=None):
    return render(request, 'page_not_found.html', status=404)



# ---------------------------
#  Dashboard View done
# ---------------------------
@method_decorator(never_cache, name='dispatch')
class DashboardView(LoginRequiredMixin, TemplateView):
    '''
    - Displays the main dashboard with an overview of the system
    - Shows initiatives relevant to the logged-in user based on their role
        - General Manager sees all initiatives
        - Managers and Employees see initiatives they are assigned to
    - Lists KPIs related to the user’s initiatives
    - Displays notes created by the user
    - Optionally includes departments and strategic plans for managerial roles
    '''

    template_name = "dashboard.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        status_order = [s[0] for s in STATUS]
        active_plan = StrategicPlan.objects.filter(is_active = True).first()
        if not active_plan:
            context['active_plan'] = None
            context['department'] = user.department if user.role.role_name != 'GM' else None
            return context
        context['active_plan'] = active_plan
        context['vision'] = active_plan.vision
        context['mission'] = active_plan.mission


        # GENERAL MANAGER #
        if user.role.role_name == 'GM':
            
            goals = StrategicGoal.objects.filter(strategicplan = active_plan)
            departments = Department.objects.all()
            initiatives = Initiative.objects.filter(strategic_goal__strategicplan = active_plan)
            userinitiatives = UserInitiative.objects.filter(initiative__strategic_goal__strategicplan = active_plan)
            for goal in goals:
                goal.user_initiatives = initiatives.filter(strategic_goal=goal)

            # Bar Chart ( مدى اكتمال الأهداف ) : avg of progress for each goal
            goals_with_avg = goals.annotate(avg_progress=Avg('initiative__userinitiative__progress', filter=Q(initiative__userinitiative__user__role__role_name='E')))
            bar_chart_labels = [goal.goal_title for goal in goals_with_avg]
            bar_chart_data = [round(goal.avg_progress or 0) for goal in goals_with_avg]
            context['bar_chart_labels'] = bar_chart_labels
            context['bar_chart_data'] = bar_chart_data

            # Donut Chart ( الحالة الإجمالية للمبادرات ) : count of all user initiatives grouped by status
            if userinitiatives.exists():
                count = status_count(userinitiatives)                
                context['donut_chart_labels'] = [s[1] for s in STATUS]
                context['donut_chart_data'] = [count.get(key, 0) for key in status_order]                

            # Stacked Bar Chart ( مؤشرات الأداء الرئيسية ) : KPIs based on status, grouped by initiatives 
            goal_labels = []
            not_started_data = []
            in_progress_data = []
            achieved_data = []
            for goal in goals:
                goal_labels.append(goal.goal_title)                
                goal_initiatives = Initiative.objects.filter(strategic_goal=goal)
                ns_count, ip_count, a_count = 0, 0, 0
                for initiative in goal_initiatives:
                    kpis_for_initiative = KPI.objects.filter(initiative=initiative)
                    achieved, in_progress, not_started = kpi_filter(kpis_for_initiative)
                    ns_count += len(not_started)
                    ip_count += len(in_progress)
                    a_count += len(achieved)
                not_started_data.append(ns_count)
                in_progress_data.append(ip_count)
                achieved_data.append(a_count)
            stacked_bar_chart_data = {
                'labels': goal_labels,
                'datasets': [
                    {
                        'label': 'لم يبدأ بعد',
                        'data': not_started_data,
                        'backgroundColor': '#F2C75C',
                        'borderRadius': 4
                    },
                    {
                        'label': 'قيد التنفيذ',
                        'data': in_progress_data,
                        'backgroundColor': '#00A399',
                        'borderRadius': 4
                    },
                    {
                        'label': 'مكتمل',
                        'data': achieved_data,
                        'backgroundColor': '#00685E',
                        'borderRadius': 4
                    },
                ]
            }
            context['stacked_bar_chart_data'] = stacked_bar_chart_data
            
            context['plans'] = StrategicPlan.objects.all()                                              #  Plans
            context['goals'] = goals                                                                    #  Goals
            context['initiatives'] = initiatives                                                        #  initiative
            context['kpis'] = KPI.objects.filter(initiative__strategic_goal__strategicplan=active_plan) #  KPIs




        # MANAGERS #
        elif user.role.role_name in ['M', 'CM']:
            userinitiatives = UserInitiative.objects.filter(initiative__strategic_goal__strategicplan = active_plan, 
                                                            user__department = user.department, user__role__role_name = 'E' )
            initiatives = Initiative.objects.filter(strategic_goal__strategicplan = active_plan, userinitiative__user=user ).distinct()
            goals = StrategicGoal.objects.filter(strategicplan = active_plan, department = user.department) 
            for goal in goals:
                goal.user_initiatives = initiatives.filter(strategic_goal=goal)


            # Donut Chart ( حالة المبادرات  ) : count of all user initiatives grouped by status
            initiative_id = self.request.GET.get('initiative')  # if there is filter
            if initiative_id:
                userinitiatives = userinitiatives.filter(initiative_id=initiative_id)
            if userinitiatives.exists():
                count = status_count(userinitiatives)
                context['donut_chart_labels'] = [s[1] for s in STATUS]
                context['donut_chart_data'] = [count.get(key, 0) for key in status_order]


            # Bar Chart ( مدى اكتمال الأهداف ) : avg of progress in each goal
            bar_chart_labels = []
            bar_chart_data = []
            for goal in goals:
                avrage_goal_progress = avg_calculator(userinitiatives.filter(initiative__strategic_goal = goal, user__role__role_name = 'E' ))
                bar_chart_labels.append(goal.goal_title)
                bar_chart_data.append(avrage_goal_progress or 0)
            context['bar_chart_labels'] = bar_chart_labels
            context['bar_chart_data'] = bar_chart_data
            
            
            # Bar Chart ( توزيع العمل ) : each employee and the number of initiatives they're working on
            employees = User.objects.filter(role__role_name = 'E', department = user.department, 
                                            userinitiative__initiative__strategic_goal__strategicplan=active_plan).annotate(workload=Count('userinitiative')).order_by('workload')
            bar_chart2_labels = []
            bar_chart2_data = []
            for employee in employees:
                bar_chart2_labels.append(employee.get_full_name())
                bar_chart2_data.append(employee.workload)
            context['bar_chart2_labels'] = bar_chart2_labels
            context['bar_chart2_data'] = bar_chart2_data
            
            
            # Stacked Bar Chart ( مؤشرات الأداء الرئيسية ) : KPIs based on status, grouped by initiatives 
            kpis = KPI.objects.filter(initiative__strategic_goal__strategicplan=active_plan,initiative__strategic_goal__department = user.department)
            if kpis:
                achieved, in_progress, not_started = kpi_filter(kpis)
                initiative_labels = [initiative.title for initiative in (Initiative.objects.filter(userinitiative__user=user, strategic_goal__strategicplan=active_plan))]
                
                not_started_data = []
                in_progress_data = []
                achieved_data = []

                for initiative in initiatives:
                    kpis_for_initiative = KPI.objects.filter(initiative=initiative)
                    achieved, in_progress, not_started = kpi_filter(kpis_for_initiative)
                    not_started_data.append(len(not_started))
                    in_progress_data.append(len(in_progress))
                    achieved_data.append(len(achieved))
                
                stacked_bar_chart_data = {
                    'labels': initiative_labels,
                    'datasets': [
                        {
                            'label': 'لم يبدأ بعد',
                            'data': not_started_data,
                            'backgroundColor': '#F2C75C',
                            'borderRadius':4

                        },
                        {
                            'label': 'قيد التنفيذ',
                            'data': in_progress_data,
                            'backgroundColor': '#00A399',
                            'borderRadius':4
                        },
                        {
                            'label': 'مكتمل',
                            'data': achieved_data,
                            'backgroundColor': '#00685E',
                            'borderRadius':4
                        },
                    ],
                    
                }
                context['stacked_bar_chart_data'] = stacked_bar_chart_data

            context['plans'] = StrategicPlan.objects.all()                                                                                     #  Plans
            context['goals'] = goals                                                                                                           #  Goals
            context['initiatives'] = initiatives                                                                                               #  Initiative
            context['kpis'] = KPI.objects.filter(initiative__strategic_goal__strategicplan=active_plan, initiative__userinitiative__user=user) #  KPIs




        # EMPLOYEES #
        else: 

            initiatives = Initiative.objects.filter(strategic_goal__strategicplan = active_plan, userinitiative__user=user)
            userinitiatives = UserInitiative.objects.filter(initiative__strategic_goal__strategicplan = active_plan,user = user)
            goals = StrategicGoal.objects.filter(strategicplan = active_plan, initiative__userinitiative__user=user).distinct().prefetch_related('initiative_set__userinitiative_set')

            for goal in goals:
                goal.user_initiatives = initiatives.filter(strategic_goal=goal)

            # Donut Chart ( حالة المبادرات  ) : count of all user initiatives grouped by status
            if userinitiatives.exists():
                count = status_count(userinitiatives)                
                context['donut_chart_labels'] = [s[1] for s in STATUS]
                context['donut_chart_data'] = [count.get(key, 0) for key in status_order]                
            
            # Bar Chart ( متوسط الإنجاز في المبادرات ) : average of all user's progress in all of his/her initiatives 
            bar_chart_data = []
            bar_chart_labels = []
            for initiative in initiatives:
                ui = userinitiatives.filter(initiative = initiative)
                bar_chart_data.append(avg_calculator(ui))
                bar_chart_labels.append(initiative.title)
            context['bar_chart_data'] = bar_chart_data
            context['bar_chart_labels'] = bar_chart_labels
            
            # Card ( متوسط نسبة الإنجاز ) : Avrage Progress 
            avrage_progress = avg_calculator(userinitiatives)
            context['avrage_progress'] = avrage_progress
            
            # Card ( المبادرات الموشكة على الانتهاء & المبادرات المنتهية ) : Overdue and Delayed Initiatives 
            overdue, late = calc_delayed(initiatives)
            context['overdue'] = overdue
            context['late'] = late

            # Stacked Bar Chart ( مؤشرات الأداء الرئيسية ) : KPIs based on status, grouped by users initiatives 
            kpis = KPI.objects.filter(initiative__strategic_goal__strategicplan=active_plan, initiative__userinitiative__user = user)
            achieved, in_progress, not_started = kpi_filter(kpis)
            initiative_labels = [initiative.title for initiative in (initiatives)]
            
            not_started_data = []
            in_progress_data = []
            achieved_data = []

            for initiative in initiatives:
                kpis_for_initiative = KPI.objects.filter(initiative__strategic_goal__strategicplan=active_plan,initiative=initiative)
                achieved, in_progress, not_started = kpi_filter(kpis_for_initiative)
                not_started_data.append(len(not_started))
                in_progress_data.append(len(in_progress))
                achieved_data.append(len(achieved))
            
            stacked_bar_chart_data = {
                'labels': initiative_labels,
                'datasets': [
                    {
                        'label': 'لم يبدأ بعد',
                        'data': not_started_data,
                        'backgroundColor': '#F2C75C',
                        'borderRadius':4

                    },
                    {
                        'label': 'قيد التنفيذ',
                        'data': in_progress_data,
                        'backgroundColor': '#00A399',
                        'borderRadius':4
                    },
                    {
                        'label': 'مكتمل',
                        'data': achieved_data,
                        'backgroundColor': '#00685E',
                        'borderRadius':4
                    },
                ],
                
            }
            context['stacked_bar_chart_data'] = stacked_bar_chart_data
            
            context['plans'] = StrategicPlan.objects.filter(is_active = True)                                                                   #  plans
            context['goals'] = goals                                                                                                            #  goals
            context['initiatives'] = initiatives                                                                                                #  initiative
            context['kpis'] = KPI.objects.filter(initiative__strategic_goal__strategicplan=active_plan, initiative__userinitiative__user=user)  #  KPIs



        # Shared content #
        
        # List ( ترتيب أداء الإدارات ) : list of all departments ordered by performance  
        departments = Department.objects.all()
        goals = StrategicGoal.objects.filter(strategicplan = active_plan)
        departments_performance_dict = {dep.department_name: [] for dep in departments}            
        for goal in goals:
            goal_average = avg_calculator(UserInitiative.objects.filter(initiative__strategic_goal = goal, user__role__role_name = 'E' ))
            departments_performance_dict.setdefault(goal.department.department_name, []).append(float(goal_average))
        for key in departments_performance_dict:
            values = departments_performance_dict[key]
            departments_performance_dict[key] = sum(values) / len(values) if values else 0.0
        sorted_departments = dict( sorted(departments_performance_dict.items(), key=lambda x: x[1], reverse=True)) #sort deps based on performance percentage 
        context['departments_performance_dict'] = sorted_departments
        
        # Line Chart ( مدى تقدم الإدارات ) -> departments progress over time 
        context['line_chart_data'] = departments_progress_over_time(departments)

        # context['notes'] = Note.objects.filter(sender=user)
        active_plan = StrategicPlan.objects.filter(is_active=True).first()
        context['notes'] = Note.objects.filter(sender=user, created_at__date__range=(active_plan.start_date, active_plan.end_date)).filter(
                                                Q(receiver__isnull=False)|
                                                Q(strategic_goal__strategicplan=active_plan) |
                                                Q(initiative__strategic_goal__strategicplan=active_plan)
                                                ).distinct()

        context['departments'] = departments
        context['department'] = user.department if user.role.role_name != 'GM' else None

        return context



# ---------------------------
#  Initiative Views done
# ---------------------------
@method_decorator(never_cache, name='dispatch')
class AllInitiativeView(LoginRequiredMixin, InitiativePermissionMixin, ListView): 
    '''
    List all initiatives
    - General Manager sees all initiatives
    - Managers see their departments initiatives 
    - Employee see the initiatives they are assigned to
    '''
    model = Initiative 
    template_name = 'initiatives_list.html'
    context_object_name = 'initiatives'
    allow_empty = True

    def get_paginate_by(self, queryset):
        return int(self.request.GET.get('per_page', 25))

    def get_queryset(self):
        qs = self.get_initiative_queryset()
        

        search = self.request.GET.get('search', '')
        priority = self.request.GET.get('priority', '')
        sort = self.request.GET.get('sort') 

        if search or priority:
            if search: 
                qs = qs.filter(title__icontains=search)
            if priority:
                qs = qs.filter(priority=priority)

        if sort == 'priority':
            priority_order = Case(
                When(priority='C', then=Value(1)),
                When(priority='H', then=Value(2)),
                When(priority='M', then=Value(3)),
                When(priority='L', then=Value(4)),
                default=Value(5),
                output_field=IntegerField(),
            )
            qs = qs.order_by(priority_order)

        return qs.distinct()


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        context['priority'] = self.request.GET.get('priority', '')
        context['per_page'] = self.request.GET.get('per_page', 25)

        page_obj = context['page_obj']
        total_pages = context['paginator'].num_pages
        current = page_obj.number

        page_numbers = []
        for num in range(1, total_pages + 1):
            if num == 1 or num == total_pages or abs(num - current) <= 2:
                page_numbers.append(num)
            elif page_numbers[-1] != '...':
                page_numbers.append('...')
        context['page_numbers'] = page_numbers
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string('partials/initiatives_table_rows.html', context, request=self.request)
            return JsonResponse({'html': html})
        return super().render_to_response(context, **response_kwargs)



@method_decorator(never_cache, name='dispatch')
class InitiativeDetailsView(LoginRequiredMixin, DetailView):
    '''
    - Shows details of a single initiative
    '''
    model = Initiative
    template_name = "initiative_detail.html"
    context_object_name = "initiative"
    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs) 
        user = self.request.user 
        initiative = self.get_object() 
        goal =  initiative.strategic_goal 
        plan = goal.strategicplan
        context['is_plan_active'] = plan.is_active
        
        #  Average 
        avg_progress = UserInitiative.objects.filter( initiative = initiative, user__role__role_name='E').aggregate ( avg = Avg('progress')) ['avg']
        avg_progress = avg_progress or 0
        avg_by_two = avg_progress/2
        
        #manager
        manager = User.objects.filter(role__role_name__in = ['CM', 'M'], userinitiative__initiative=initiative).distinct()         

        # Employeess
        employees = User.objects.filter(role__role_name ='E', userinitiative__initiative=initiative)
        employee_progress = []
        for emp in employees:
            ui = UserInitiative.objects.filter(user=emp, initiative=initiative).first()
            if ui:
                status = dict(STATUS)[calc_user_initiative_status(ui)]
                employee_progress.append([ emp, ui.progress, status, 'bg-red-500' if status == 'متأخر' else 'bg-teal-500'])
            else:
                employee_progress.append([emp, 0, 'NS','bg-gray-500'])
            
        assigned_employee_ids = set( UserInitiative.objects.filter(initiative=initiative, user__role__role_name = 'E').values_list('user_id', flat=True) ) 
        assigned_employees= User.objects.filter(id__in=assigned_employee_ids)
        unassigned_employees = User.objects.filter(role__role_name='E', department=user.department).exclude(id__in=assigned_employee_ids)
        # latency
        todays_date = timezone.now().date()
        is_initiative_late = todays_date >= initiative.end_date and avg_progress != 100
        
        context['avg'] = round(avg_progress or 0)
        context['avg_by_two'] = round(avg_by_two or 0)
        context['employee_progress'] = employee_progress
        context['employees'] = employees 
        context['manager'] = manager.first()
        context['is_initiative_late'] = is_initiative_late
        context['assigned_employees'] = assigned_employees
        
        #  الملاحظات المرتبطة بالمبادرة
        notes = Note.objects.filter(initiative=initiative, parent_note__isnull=True).order_by('-created_at')

        context['initiative_notes'] = notes


        if user.role.role_name == 'E':
            try:
                user_initiative = UserInitiative.objects.get(user=user, initiative=initiative)
                context['form'] = UserInitiativeForm(instance=user_initiative)
            except UserInitiative.DoesNotExist:
                context['form'] = UserInitiativeForm()
        elif user.role.role_name in ['M', 'CM'] and initiative.strategic_goal.department == user.department: 
            context['suggestions'] = generate_KPIs(initiative.strategic_goal,initiative, initiative.strategic_goal.department)
            context['form'] = KPIForm()
            context['unassigned_employees'] = unassigned_employees 
        elif user.role.role_name == 'GM':
            context['unassigned_employees'] = unassigned_employees 
            
        return context



@method_decorator(never_cache, name='dispatch')
class CreateInitiativeView(LoginRequiredMixin, RoleRequiredMixin, InitiativePermissionMixin, LogMixin, CreateView):
    '''
    - Allows Managers to create a new initiative
    - Sets the strategic goal based on the goal_id in the URL
    - Automatically assigns the current user to the initiative via UserInitiative
    '''
    model = Initiative
    form_class = InitiativeForm
    template_name = 'initiative_form.html'
    allowed_roles = ['M', 'CM']

    def form_valid(self, form): #overriding form valid to set strategic goal and employee
        form.instance.strategic_goal_id = self.kwargs['goal_id']
        response = super().form_valid(form)
        self.log_create(self.object)
        UserInitiative.objects.create(
            user=self.request.user,
            initiative=self.object,
            status = STATUS[0][0],
            progress = 0
        )
        messages.success(self.request, "تمت إضافة المبادرة بنجاح", extra_tags="create")

        return response

    def form_invalid(self, form):
        # Field-specific errors
        for field, errors in form.errors.items():
            if field != '__all__':
                for error in errors:
                    messages.error(self.request, f"{form.fields[field].label}: {error}", extra_tags="error")

        # Non-field errors
        for error in form.non_field_errors():
            messages.error(self.request, error, extra_tags='error')

        return super().form_invalid(form)

    def get_success_url(self):
        return reverse('initiatives_list')


    def test_func(self):
        user = self.request.user
        goal_id = self.kwargs.get('goal_id')
        if not goal_id:
            return False
        goal = get_object_or_404(StrategicGoal, id=goal_id)

        if user.role.role_name in ['M', 'CM'] and goal.department == user.department:
            return True
        return False

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('login')
        raise PermissionDenied("ليست لديك صلاحية لرؤية هذه الصفحة")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['goal'] = get_object_or_404(StrategicGoal, id=self.kwargs['goal_id'])
        return kwargs



@method_decorator(never_cache, name='dispatch')
class UpdateInitiativeView(LoginRequiredMixin, RoleRequiredMixin, InitiativePermissionMixin, LogMixin, UpdateView):  #managers only
    '''
    - Allows updating an existing initiative
    - Only the initiative fields are editable (title, description, dates, priority, category)
    - The strategic goal and assigned users remain unchanged
    '''
    model = Initiative
    template_name = 'initiative_form.html'
    form_class = InitiativeForm
    allowed_roles = ['M', 'CM']

    def get_queryset(self):
        # explicitly use the mixin’s logic
        return super().get_queryset()

    def form_valid(self, form):
        old_instance = self.get_object()
        response = super().form_valid(form)
        self.log_update(old_instance, self.object)
        messages.success(self.request, "تم تحديث المبادرة بنجاح", extra_tags="update")
        return response

    def form_invalid(self, form):
        for field, errors in form.errors.items():
            if field != '__all__':
                for error in errors:
                    messages.error(self.request, f"{form.fields[field].label}: {error}", extra_tags="error")

        for error in form.non_field_errors():
            messages.error(self.request, error, extra_tags="error")

        return super().form_invalid(form)

    def get_success_url(self):
        return reverse('initiatives_list')



@method_decorator(never_cache, name='dispatch')
class DeleteInitiativeView(LoginRequiredMixin, RoleRequiredMixin, InitiativePermissionMixin, LogMixin, DeleteView):#managers only
    '''
    - Allows deletion of an initiative
    - All related UserInitiative entries are automatically deleted (on_delete=CASCADE)
    - After deletion redirects to Initiatives list
    '''
    model = Initiative
    template_name = 'initiative_confirm_delete.html'
    allowed_roles = ['M', 'CM']

    def get_queryset(self):
        return InitiativePermissionMixin.get_queryset(self)

    # def delete(self, request, *args, **kwargs):
    #     obj = self.get_object()
    #     messages.success(request, f"تم حذف المبادرة: {obj.title}", extra_tags="delete")
    #     return super().delete(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('initiatives_list')
    
    def form_valid(self, form):
        obj = self.get_object()
        # Log after deletion
        self.log_delete(obj)
        # Delete
        super().form_valid(form)
        success_url = self.get_success_url()

        messages.success( self.request, f"تم حذف المبادرة: {obj.title} بنجاح", extra_tags="delete")
        return redirect(success_url)



def is_manager(user):
    return user.role and user.role.role_name in ['M', 'CM']



@login_required
@user_passes_test(is_manager)
@never_cache
def assign_employee_to_initiative(request, pk):
    initiative = get_object_or_404(Initiative, id=pk)
    employees = User.objects.filter(role__role_name='E', department=request.user.department)

    if request.user.role.role_name not in ['M', 'CM'] or initiative.strategic_goal.department != request.user.department:
        raise PermissionDenied("ليست لديك صلاحية لرؤية هذه الصفحة")

    assigned_employee_ids = set(
        UserInitiative.objects.filter(initiative=initiative, user__role__role_name='E').values_list('user_id', flat=True)
    )

    if request.method == "POST": #Post request: receives a list of employees
        employee_ids_to_add = request.POST.getlist('to_add[]')
        employee_ids_to_remove = request.POST.getlist('to_remove[]')
        logger = LogMixin(request=request)
        
        for emp_id in employee_ids_to_add:
            emp = get_object_or_404(User, id=emp_id)
            obj, created = UserInitiative.objects.get_or_create(user=emp, initiative=initiative, status=STATUS[0][0], progress=0)

            if created:
                # CREATE
                logger.log_create(obj)


        for emp_id in employee_ids_to_remove:
            relations = UserInitiative.objects.filter(user_id=emp_id, initiative=initiative)
            
            for obj in relations:
                #DELETE
                obj.delete()
                logger.log_delete(obj)

        
        if employee_ids_to_add or employee_ids_to_remove:
            text = ''
            if employee_ids_to_add:
                if len(employee_ids_to_add) == 1:
                    text += "تم تعيين موظف للمبادرة\n"
                elif len(employee_ids_to_add) == 2:
                    text += 'تم تعيين موظفان للمبادرة\n'
                else:
                    text += f"تم تعيين {len(employee_ids_to_add)} موظفين للمبادرة\n"
                    
            if employee_ids_to_remove:
                if len(employee_ids_to_remove) == 1:
                    text += "تم إلغاء تعيين موظف للمبادرة"
                elif len(employee_ids_to_remove) == 2:
                    text += 'تم إلغاء تعيين موظفان للمبادرة'
                else:
                    text += f"تم إلغاء تعيين {len(employee_ids_to_remove)} موظفين من المبادرة"
            messages.success(request, text, extra_tags="create")
        else:
            messages.error(request, "لم يتم تعديل أي موظف", extra_tags="error")


        return redirect('initiative_detail', pk=initiative.id)

    return render(request, 'assign_employee.html', { #Get request: returns a list of the department employees
        'initiative': initiative,
        'employees': employees,
        'assigned_employee_ids': assigned_employee_ids,
    })



@login_required
@never_cache
def add_progress(request, initiative_id):
    user = request.user
    initiative = get_object_or_404(Initiative, id=initiative_id)
    user_initiative = get_object_or_404(UserInitiative, initiative=initiative, user=user)
    
    if request.method == 'POST':
        # ===== OLD DATA  =====
        old_data = model_to_dict_with_usernames(user_initiative)

        form = UserInitiativeForm(request.POST, instance=user_initiative)
        if form.is_valid():
            obj = form.save()

            # ===== Update goal status =====
            goal = initiative.strategic_goal
            new_status = calc_goal_status(goal)
            goal.goal_status = new_status
            goal.save()


        #    # ===== Update Initiative Status =====
        #     old_status = initiative.initiative_status
        #     new_status = calc_initiative_status_by_avg(initiative)
        #     print("OLD STATUS:", old_status)
        #     print("NEW STATUS:", new_status)
        #     if old_status != new_status:
        #         initiative.initiative_status = new_status
        #         initiative.save()
        #         print("Status updated ✔")

            logger = LogMixin(request=request)
            logger.log_update(old_instance=old_data, new_instance=obj)

            ProgressLog.objects.create(
                user=user,
                initiative=initiative,
                department=user.department,
                progress=user_initiative.progress
            )

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            
            messages.success(request, 'تم تحديث التقدم بنجاح', extra_tags="update")
            return redirect('initiative_detail', pk=initiative_id)
    else:
        form = UserInitiativeForm(instance=user_initiative)

    return render(request, 'partials/update_initiative_modal.html', {
        'form': form,
        'object': user_initiative,
        'initiative': initiative,
        'user': user,
        'is_update': True,
    })



# ---------------------------
#  KPI Views
# ---------------------------
@method_decorator(never_cache, name='dispatch')
class KPIDetailsView(LoginRequiredMixin, DetailView):
    '''
    - Shows details of a single KPI
    '''
    model = KPI
    template_name = "KPI_detail.html"
    context_object_name = "KPI"



@login_required
@user_passes_test(is_manager)
@never_cache
def create_kpi_view(request, initiative_id):
    '''
    - Allows users to create a new KPI for a given initiative
    - Fills AI-generated KPI suggestions for editing or adding
    - Redirects on submission or renders form (full or partial) on GET, handling errors as needed
    '''

    if not is_manager(request.user):
        raise PermissionDenied("ليست لديك صلاحية لرؤية هذه الصفحة")

    initiative = get_object_or_404(Initiative, id=initiative_id)
    if request.method == "POST":
        form = KPIForm(request.POST)
        if form.is_valid():
            kpi = form.save(commit=False)
            kpi.initiative = initiative
            if kpi.start_value is None:
                kpi.start_value = kpi.actual_value

            kpi.save()
            logger = LogMixin(request=request)
            logger.log_create(kpi)
            
            messages.success(request, 'تم إضافة مؤشر قياس أداء بنجاح',extra_tags='create')
            return redirect('initiative_detail', pk=initiative.id)
        
        else:
            return render(request, 'kpi_form.html', {'initiative': initiative, 'form': form})

    else:
        form = KPIForm()
        ai_suggestion = generate_KPIs(initiative)

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':    # only return partial HTML if request is via JS
            return render(request, 'partials/kpi_modal.html', {'form': form, 'suggestions': ai_suggestion})

        #if someone opens the url normally
        return render(request, 'kpi_form.html', {'initiative': initiative, 'form': form})



@method_decorator(never_cache, name='dispatch')
class DeleteKPIView(LoginRequiredMixin, RoleRequiredMixin, LogMixin, DeleteView):
    '''
    - Allows users to delete a KPI
    - Confirms deletion using a template
    - Redirects to the Initiative detail page after successful deletion
    '''

    model = KPI
    template_name = 'confirm_delete.html'
    allowed_roles = ['M', 'CM']
    
    # def delete(self, request, *args, **kwargs):
    #     obj = self.get_object()
    #     messages.success(request, f"تم حذف مؤشر القياس: {obj.kpi}", extra_tags="delete")
    #     success_url = self.get_success_url()
    #     obj.delete() 
    #     return redirect(success_url)

    def get_success_url(self):
        initiative_id = self.kwargs.get('initiative_id')
        return reverse('initiative_detail', kwargs={'pk': initiative_id})
    
    
    def form_valid(self, form):
        obj = self.get_object()
        # Log after deletion
        self.log_delete(obj)
        # Delete
        super().form_valid(form)
        success_url = self.get_success_url()

        messages.success( self.request, f"تم حذف مؤشر القياس: {obj.kpi} بنجاح", extra_tags="delete")
        return redirect(success_url)



@login_required
@never_cache
def edit_kpi_view(request, initiative_id, kpi_id):
    kpi = get_object_or_404(KPI, id=kpi_id, initiative_id=initiative_id)
    
    if request.method == 'POST':
        old_data = model_to_dict_with_usernames(kpi)
        form = KPIForm(request.POST, instance=kpi)

        if form.is_valid():
            form.save()
            logger = LogMixin(request=request)
            logger.log_update(old_instance=old_data, new_instance=kpi)

            messages.success(request, f"تم تحديث مؤشر القياس: {kpi.kpi} بنجاح", extra_tags="update")
            return redirect('initiative_detail', pk=initiative_id)
    else:
        form = KPIForm(instance=kpi)

    return render(request, 'partials/kpi_modal.html', {
        'form': form,
        'object': kpi,
        'initiative': kpi.initiative,
        'is_update': True,
    })



@method_decorator(never_cache, name='dispatch')
class AllKPIsView(LoginRequiredMixin,ListView): #not needed but here we go
    '''
    - Displays a list of KPIs related to initiatives assigned to the current user
    - Filters KPIs based on the user's assigned initiatives
    - Renders the KPIs in the specified template
    '''
    model = KPI
    template_name = 'kpis_list.html'
    context_object_name = 'kpis'

    def get_queryset(self):
        return KPI.objects.filter(initiative__userinitiative__user=self.request.user)



#########################################################################################################################
#                                                    WALAA's Views                                                      #
#########################################################################################################################



# ---------------------------
#  Department View
# ---------------------------
@method_decorator(never_cache, name='dispatch')
class AllDepartmentsView(LoginRequiredMixin, ListView):
    '''
    - List all departments
    '''
    model = Department
    template_name = 'departments_list.html'
    context_object_name = 'departments'

    def get_queryset(self):
        return Department.objects.all()



# ---------------------------
#  StrategicPlan View
# ---------------------------
@method_decorator(never_cache, name='dispatch')
class AllPlansView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    model = StrategicPlan
    template_name = 'plans_list.html'
    context_object_name = 'plans'
    allowed_roles = ['M', 'CM', 'GM']  # Roles allowed to access this view

    def get_queryset(self):
        """
        - Retrieves the queryset of StrategicPlan objects.
        - Automatically updates any active plan that has passed its end_date to inactive.
        - Applies search and status filters if provided in GET parameters.
        """
        queryset = StrategicPlan.objects.all()

        today = timezone.now().date()
        queryset.filter(is_active=True, end_date__lt=today).update(is_active=False)

        queryset = filter_queryset(
            queryset=queryset,
            request=self.request,
            search_fields=['plan_name'],
            status_field='is_active',
            priority_field=None
        )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        per_page = 25

        page_list, page_obj, paginator = paginate_queryset(queryset, self.request, per_page)

        context['plans'] = page_list               
        context['page_obj'] = page_obj
        context['paginator'] = paginator
        context['page_numbers'] = get_page_numbers(page_obj, paginator)
        context['per_page'] = per_page
        context['is_paginated'] = True if paginator.num_pages > 1 else False
        context['active_plan_exists'] = StrategicPlan.objects.filter(is_active=True).exists()

        return context


    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string('partials/plans_table_rows.html', context, request=self.request)
            return JsonResponse({
                'html': html
            })
        return super().render_to_response(context, **response_kwargs)



@method_decorator(never_cache, name='dispatch')
class PlanDetailsview(LoginRequiredMixin, RoleRequiredMixin, DetailView):
     '''
     - Displays details of a single strategic plan
     '''
     model = StrategicPlan
     template_name = 'plan_detail.html'
     context_object_name = 'plan'
     allowed_roles = ['M', 'CM', 'GM']  # Roles allowed to access this view

     def get_queryset(self):
         return StrategicPlan.objects.all()

     def get_context_data(self, **kwargs):
      context = super().get_context_data(**kwargs)
      user = self.request.user
      role = user.role.role_name
      goals_qs = StrategicGoal.objects.filter(strategicplan=self.object)
      per_page = 10
      dashboard_data = get_plan_dashboard(self.object, self.request.user)
      context.update(dashboard_data)

    # search & filter
      goals_qs = filter_queryset(
        queryset=goals_qs,
        request=self.request,
        search_fields=['goal_title'],
        status_field='goal_status',
        priority_field='goal_priority'
    )

      if role in ['M', 'CM']:
        goals_qs = goals_qs.filter(department=user.department)
        goals_qs.prefetch_related(
            Prefetch(
                'initiative_set',
                queryset=Initiative.objects.prefetch_related(
                    Prefetch(
                        'userinitiative_set',
                        queryset=UserInitiative.objects.filter(user=user),
                        to_attr='user_initiative'
                    )
               ), to_attr='_prefetched_initiatives'  
            )
        )

      goal_list, page_obj, paginator = paginate_queryset(goals_qs, self.request, per_page)
      
      context['show_initiatives'] = True
      context['goals'] = goal_list
      context['page_obj'] = page_obj
      context['paginator'] = paginator
      context['per_page'] = per_page
      context['is_paginated'] = True if paginator.num_pages > 1 else False
      context['page_numbers'] = get_page_numbers(page_obj, paginator)
      return context
      
     def render_to_response(self, context, **response_kwargs):
         if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
             html = render_to_string('partials/goals_table_rows.html', context, request=self.request)
             return JsonResponse({
                 'html': html
             })
         return super().render_to_response(context, **response_kwargs)



@method_decorator(never_cache, name='dispatch')
class CreatePlanView(LoginRequiredMixin, LogMixin, CreateView):
    '''
    - Only Committee Manager can create a new strategic plan
    - Redirects to plan list after creation
    '''
    form_class = StrategicPlanForm
    template_name = 'plan_form.html'
    success_url = reverse_lazy('plans_list')

    def dispatch(self, request, *args, **kwargs):
        if request.user.role.role_name != 'CM':
            raise PermissionDenied("ليس لديك الصلاحية لإنشاء هذه الخطة.")
        if  StrategicPlan.objects.filter(is_active=True):
            raise PermissionDenied("توجد خطة نشطة حاليًا")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(user=self.request.user)  
        self.log_create(self.object)
        messages.success(self.request, "تم إنشاء الخطة بنجاح", extra_tags="create")
        return redirect(self.get_success_url())
    
    def form_invalid(self, form):
        # Field-specific errors
        for field, errors in form.errors.items():
            if field != '__all__':
                for error in errors:
                    messages.error(self.request, f"{form.fields[field].label}: {error}", extra_tags="error")

        # Non-field errors
        for error in form.non_field_errors():
            messages.error(self.request, error, extra_tags='error')

        return super().form_invalid(form)



@method_decorator(never_cache, name='dispatch')
class UpdatePlanView(LoginRequiredMixin, LogMixin, UpdateView):
    '''
    - Only Committee Manager can update an existing plan
    - Redirects to plans list after update
    '''
    model = StrategicPlan
    form_class = StrategicPlanForm
    template_name = 'plan_form.html'
    success_url = reverse_lazy('plans_list')

    def dispatch(self, request, *args, **kwargs):
        plan = self.get_object()
        if request.user.role.role_name != 'CM':
            raise PermissionDenied("ليس لديك الصلاحية لتعديل هذه الخطة.")
        if not plan.is_active:
            raise PermissionDenied("يمكنك تعديل الخطط النشطة فقط")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        old_instance = self.get_object()
        response = super().form_valid(form)
        self.log_update(old_instance, self.object)

        messages.success(self.request, "تم تحديث الخطة بنجاح", extra_tags="update")
        return response



@method_decorator(never_cache, name='dispatch')
class DeletePlanView(LoginRequiredMixin, RoleRequiredMixin, LogMixin, DeleteView):
    '''
    - Only Committee Manager can delete a plan
    - Redirects to plans list after deletion
    '''
    model = StrategicPlan
    success_url = reverse_lazy('plans_list')
    allowed_roles = ['CM']  # Roles allowed to access this view

    def form_valid(self, form):
        """Custom deletion logic inside form_valid"""
        obj = self.get_object()
        self.log_delete(obj)
        response = super().form_valid(form)
        messages.success(self.request, "تم حذف الخطة بنجاح", extra_tags="delete")
        return response



# ---------------------------
#  StrategicGoal View
# ---------------------------
@method_decorator(never_cache, name='dispatch')
class AllGoalsView(LoginRequiredMixin, ListView):
    '''
    Displays a list of all strategic plans
    - General Manager sees all goals
    - Managers and Committee Managers see goals of their department
    - Employees see goals linked to their initiatives
    '''
    model = StrategicGoal
    template_name = 'goals_list.html'
    context_object_name = 'goals'



    def get_queryset(self):
        user = self.request.user
        role = user.role.role_name
        plan = StrategicPlan.objects.filter(is_active = True).first()

        if role == 'GM':
            qs = StrategicGoal.objects.filter(strategicplan=plan)
        elif role in ['M','CM']:
            qs = StrategicGoal.objects.filter(strategicplan=plan, department = user.department)
        elif role == 'E':
            qs = StrategicGoal.objects.filter(strategicplan=plan, initiative__userinitiative__user=user).distinct()
        else:
            qs = StrategicGoal.objects.none()
        

        #search & filter function
        qs = filter_queryset(
           queryset=qs,
           request=self.request,
           search_fields=['goal_title'],
           status_field='goal_status',
           priority_field='goal_priority'
         )

        return qs
      
    def get_context_data(self, **kwargs):
      context = super().get_context_data(**kwargs)
      context['show_initiatives'] = False
      queryset = self.get_queryset()
      per_page = 25

      goal_list, page_obj, paginator = paginate_queryset(queryset, self.request, per_page)

     
     # ====== Get active plan ======
      active_plan = StrategicPlan.objects.filter(is_active=True).first()

      context['active_plan'] = active_plan
      context['active_plan_exists'] = bool(active_plan)
      context['goals'] = goal_list
      context['page_obj'] = page_obj
      context['paginator'] = paginator
      context['per_page'] = per_page
      context['is_paginated'] = True if paginator.num_pages > 1 else False
      context['page_numbers'] = get_page_numbers(page_obj, paginator)
      return context
    
    
    def render_to_response(self, context, **response_kwargs):
        """
        - Handles AJAX requests differently: returns only partial HTML for the table.
        - For normal requests, renders the full template as usual.
        """
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string('partials/goals_table_rows.html', context, request=self.request)
            return JsonResponse({
                'html': html
            })
        return super().render_to_response(context, **response_kwargs)



@method_decorator(never_cache, name='dispatch')
class GoalDetailsview(LoginRequiredMixin, DetailView):
    '''
    - Shows details of a single goal
    '''
    model = StrategicGoal
    template_name = 'goal_detail.html'
    context_object_name = 'goal'
    def get_context_data(self, **kwargs):
        user = self.request.user 
        strategic_goal = self.get_object() 
        context = super().get_context_data(**kwargs)
        
        initiatives = Initiative.objects.filter(strategic_goal = strategic_goal)
        initiatives_count = initiatives.count()
        context['initiatives'] = initiatives
        context['initiatives_count'] = initiatives_count
        context['goal'] = strategic_goal
        
        goal_progress = calc_goal_progress(strategic_goal)
        context['progress'] = goal_progress
        
        status_value = calc_goal_status(strategic_goal)
        status_display = {
            'NS': 'لم يبدأ بعد',
            'IP': 'قيد التنفيذ',
            'D': 'متأخر',
            'C': 'مكتمل'
        }.get(status_value, '')
        context['status'] = status_display

        timeline = calculate_goal_timeline(strategic_goal)
        context['passed'] = timeline['passed']
        context['duration'] = timeline['duration']
        context["remaining_duration"] = timeline["remaining_duration"]
        context["passed_duration_percent"] = timeline["passed_duration_percent"]
        # svg_size = 48  # in px
        # radius = 0.45 * svg_size
        # circumference = 2 * math.pi * radius
        # context["circumference"] = circumference
        # context["circle_offset"] = round(circumference * (1 - timeline["passed_duration_percent"]/100), 2)
        # context["circle_offset_for_progress"] = round(circumference * (1 - goal_progress/100), 2)

        return context



@method_decorator(never_cache, name='dispatch')
class CreateGoalView(LoginRequiredMixin, RoleRequiredMixin, LogMixin, CreateView):
    '''
    - Allows Managers and Committee Managers to create a new goal
    - Links the goal to the plan and the user's department
    - Redirects to the goals list after creation
    '''
    model = StrategicGoal
    form_class = StrategicGoalForm
    template_name = 'goal_form.html'
    allowed_roles = ['M', 'CM']  # Roles allowed to access this view

    def form_valid(self, form):
        goal = form.instance
        today = timezone.localdate()

        if goal.end_date:
         if today > goal.end_date:
            goal.goal_status = 'D'
        else:
            goal.goal_status = 'NS'

        self.object = form.save(user=self.request.user, plan_id=self.kwargs['plan_id'])
        self.log_create(self.object)
        messages.success(self.request, "تمت إضافة الهدف بنجاح", extra_tags="create")
        return redirect(self.get_success_url())
    
    def form_invalid(self, form):
        # Field-specific errors
        for field, errors in form.errors.items():
            if field != '__all__':
                for error in errors:
                    messages.error(self.request, f"{form.fields[field].label}: {error}", extra_tags="error")

        # Non-field errors
        for error in form.non_field_errors():
            messages.error(self.request, error, extra_tags='error')

        return super().form_invalid(form)
    
    def get_success_url(self):
        return reverse('goals_list')



@method_decorator(never_cache, name='dispatch')
class UpdateGoalView(LoginRequiredMixin, RoleRequiredMixin, LogMixin, UpdateView):
    '''
    - Managers and Committee Managers can update goals in their department
    - Updates goal details
    - Redirects to goals list
    '''
    model = StrategicGoal
    form_class = StrategicGoalForm
    template_name = 'goal_form.html'
    success_url = reverse_lazy('goals_list') 
    allowed_roles = ['M', 'CM']  # Roles allowed to access this view

    def form_valid(self, form):
        old_instance = self.get_object()
        response = super().form_valid(form)
        self.log_update(old_instance, self.object)
        messages.success(self.request, "تم تحديث الهدف بنجاح", extra_tags="update")
        return response



@method_decorator(never_cache, name='dispatch')
class DeleteGoalView(LoginRequiredMixin, RoleRequiredMixin, LogMixin, DeleteView):
    '''
    - Managers and Committee Managers can delete goals in their department
    - Shows confirmation before deletion
    - Redirects to goals list
    '''
    model = StrategicGoal
    success_url = reverse_lazy('goals_list') 
    allowed_roles = ['M', 'CM']  # Roles allowed to access this view

    def form_valid(self, form):
        """Custom deletion logic inside form_valid"""
        obj = self.get_object()
        self.log_delete(obj)
        response = super().form_valid(form)
        messages.success(self.request, "تم حذف الهدف بنجاح", extra_tags="delete")
        return response



# ---------------------------
#  Note View
# ---------------------------
@method_decorator(never_cache, name='dispatch')
class AllNotesView(LoginRequiredMixin, ListView):
    '''
    - Displays a list of notes for the current user
    - GM sees only notes they sent
    - M and CM see notes they sent plus notes sent by GM in their department
    - E sees notes they sent and notes related to initiatives they are part of, or notes sent to them by their manager
    '''
    model = Note
    template_name = 'notes_list.html'
    context_object_name = 'notes'

    def get_queryset(self):
        user = self.request.user
        role = user.role.role_name
        current_box = self.request.GET.get('box', 'all-notes')
        current_filter = self.request.GET.get('filter', '')
        initiative_id = self.request.GET.get('initiative')


        # GM sees only notes he sent
        if role == 'GM':
            qs = Note.objects.filter(sender=user)

        # Manager roles
        elif role in ['M', 'CM']:
            qs = Note.objects.filter(
                Q(sender=user) |                     # notes sent by user
                Q(receiver=user) |                   # notes received by user
                Q(strategic_goal__department=user.department) |  # same department
                Q(initiative__userinitiative__user=user),        # related initiatives
                parent_note__isnull=True
            ).distinct()

        # Employee
        elif role == 'E':
            qs = Note.objects.filter(
                Q(sender=user) |                     # notes sent by user
                Q(receiver=user) |                   # notes received by user
                Q(initiative__userinitiative__user=user),  # initiative notes
                parent_note__isnull=True
            ).distinct()
        else:
            qs = Note.objects.none()


        # annotate last sender (for unread)
        last_note_qs = Note.objects.filter(
           Q(parent_note=OuterRef('pk')) | Q(pk=OuterRef('pk'))).order_by('-created_at')
        qs = qs.annotate(
        last_note_id=Subquery(last_note_qs.values('pk')[:1]),
        last_note_created_at=Subquery(last_note_qs.values('created_at')[:1]),
        last_sender_id=Subquery(last_note_qs.values('sender_id')[:1]),
        last_receiver_id=Subquery(last_note_qs.values('receiver_id')[:1])
        )
        
        # annotate participant (receiver/goal/initiative)
        initiative_exists = UserInitiative.objects.filter(
            initiative=OuterRef('initiative_id'),
            user=user
         )
        
        # Check if the user is a participant (sender, receiver, department member, or linked initiative)
        qs = qs.annotate(
            is_user_participant=Case(
                When(sender=user, then=Value(True)),
                When(receiver=user, then=Value(True)),
                When(Exists(initiative_exists), then=Value(True)),
                When(strategic_goal__department=user.department, then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
                )
        )
        
        # Determine if the message belongs to the user's inbox (they are a participant and not the last sender)
        qs = qs.annotate(
        is_inbox=Case(
            When(
                Q(is_user_participant=True) &
                ~Q(last_sender_id=user.id),
                then=Value(True)
            ),
            default=Value(False),
            output_field=BooleanField(),
        )
    )
        
        # Determine if the message was sent by the user (they are a participant and the last sender)
        qs = qs.annotate(
        is_sent=Case(
            When(
                Q(is_user_participant=True) & Q(last_sender_id=user.id),
                then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        )
    )
        
        # Set which user ID should be displayed (sender for inbox, current user for sent, or original sender)
        qs = qs.annotate(
           display_user_id=Case(
           When(is_inbox=True, then=F('last_sender_id')),
           When(is_sent=True, then=Value(user.id)),
          default=F('sender_id'),
          output_field=IntegerField()
          )
    )
        
        # Get the full name of the display user, falling back to first name or username if needed
        qs = qs.annotate(
             display_user_name=Subquery(
                 User.objects.filter(
                 id=OuterRef('display_user_id')
                 ).annotate(
                      full_name=Coalesce(
                        Concat( F('first_name'), Value(' '), F('last_name'), output_field=CharField()),
                        F('first_name'),
                        F('username'),
                        )
                 ).values('full_name')[:1]
             )
        )
       
        # Mark if the message is a reply (sent by user, but original sender is someone else)
        qs = qs.annotate(
             is_reply=Case(
                 When(
                      Q(is_sent=True) & Q(last_sender_id=user.id) & ~Q(sender=user),
                        then=Value(True)
                        ),
                default=Value(False),
                output_field=BooleanField()
                )
            )
        
        reply_exists = Note.objects.filter(parent_note=OuterRef('pk'))
        qs = qs.annotate(
            has_replies=Exists(reply_exists)
            )

        # Received notes
        if current_box == 'received-notes': 
            qs = qs.filter(is_inbox=True)

        # Sent notes
        if current_box == 'sent-notes':
            qs = qs.filter(is_sent=True)
            
        # Starred notes box
        if current_box == 'starred-notes':
            qs = qs.filter(is_starred=True)

        # Filters
        if current_filter == "starred":
            qs = qs.filter(is_starred=True)

        if current_filter == "unstarred":
            qs = qs.filter(is_starred=False)

        if current_filter == "goal":
            qs = qs.filter(strategic_goal__isnull=False)

        if current_filter == "initiative":
            qs = qs.filter(initiative__isnull=False)
            
        if initiative_id:
           qs = qs.filter(initiative_id=initiative_id)


        # Search field
        qs = filter_queryset(
            queryset=qs,
            request=self.request,
            search_fields=['title', 'sender__first_name', 'sender__last_name'],
            status_field=None,
            priority_field=None
        )

        qs = qs.order_by('-last_note_created_at')
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['today'] = timezone.localdate()
        context['yesterday'] = timezone.localdate() - timezone.timedelta(days=1)
        user = self.request.user

        # Count unread notes
        context['unread_count'] = get_unread_notes_count(user)

        # Mark unread notes
        for note in context['notes']:
    
            #last sender in chat
           note.is_sent_box = note.is_sent
           note.is_received_box = note.is_inbox

           note.unread = (
                note.last_sender_id != user.id 
                 and
               ( note.receiver == user or
                 note.initiative or
                 note.strategic_goal
                )
                and
                 not note.read_by.filter(id=user.id).exists())
           
           # last sender name
           last_sender = User.objects.filter(id=note.last_sender_id).first()
           note.last_sender = last_sender
           


           # display sender
           if note.has_replies:
               if last_sender.id == user.id:
                   note.display_sender = "رد: أنت"
               else:
                   note.display_sender = f"رد: {last_sender.get_full_name()}"
           else:
                 # no replies → show normal sender
                if last_sender.id == user.id:
                   note.display_sender = "أنت"
                else:
                   note.display_sender = note.sender.get_full_name()



       # box/filter/search values
        current_box = self.request.GET.get('box', 'all-notes')
        current_filter = self.request.GET.get('filter', 'all')
        search = self.request.GET.get('search', '')

        context['current_box'] = current_box
        context['current_filter'] = current_filter
        context['search'] = search

        # Set an empty message for each filter/box when the queryset is empty
        empty_message = "لا توجد ملاحظات لعرضها"
        if not context['notes']:
            if search:
                empty_message = "لا توجد نتائج مطابقة لبحثك"
            elif current_filter == 'read':
                empty_message = "لا توجد ملاحظات مقروءة"
            elif current_filter == 'unread':
                empty_message = "لا توجد ملاحظات غير مقروءة"
            elif current_filter == 'initiative':
                empty_message = "لا توجد ملاحظات مرتبطة بمبادرات"
            elif current_filter == 'goal':
                empty_message = "لا توجد ملاحظات مرتبطة بأهداف"
            elif current_filter == 'starred':
                empty_message = "لا توجد ملاحظات مميزة بنجمة"
            elif current_filter == 'unstarred':
                empty_message = "لا توجد ملاحظات غير مميزة بنجمة"
            elif current_box == 'sent-notes':
                empty_message = "لم ترسل أي ملاحظات بعد"
            elif current_box == 'received-notes':
                empty_message = "لا توجد ملاحظات واردة"
            elif current_box == 'starred-notes':
                empty_message = "لا توجد ملاحظات مميزة بنجمة"

        context['empty_message'] = empty_message

        return context
    
    def render_to_response(self, context, **response_kwargs):
         if self.request.headers.get("HX-Request"):
             return render(self.request, "partials/notes_table_rows.html", context)
         return super().render_to_response(context, **response_kwargs)



@method_decorator(never_cache, name='dispatch')
class NoteDetailsview(LoginRequiredMixin, LogMixin, DetailView):
    model = Note
    template_name = 'partials/note_detail.html'
    context_object_name = 'note'

  
    def get_object(self, queryset=None):
        note = super().get_object(queryset)
        user = self.request.user
   
        # Mark this note as read by the current user
        if not note.read_by.filter(id=user.id).exists():
            note.read_by.add(user)

        return note
            
    
    def can_reply(self, note, user):
        # GM notes cannot be replied to
        if note.sender.role.role_name == 'GM':  
            return False
        
        # Allow reply if the user is part of the initiative
        if note.initiative:
           return UserInitiative.objects.filter(initiative=note.initiative, user=user).exists()
        
        # Allow reply if the user is sender or receiver
        return note.receiver == user or note.sender == user
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        note = self.object
        user = self.request.user

        replies = note.replies.all().order_by('created_at')

        # Group replies by date
        grouped_replies = []
        for date, notes in groupby(replies, key=lambda r: r.created_at.date()):
            grouped_replies.append({
                "date": date,
                "notes": list(notes)
            })
       
        if note.receiver:
           context['is_read_by_receiver'] = note.read_by.filter(id=note.receiver.id).exists()
        else:
           context['is_read_by_receiver'] = False
        
        plan_ended = False
        if note.initiative and note.initiative.strategic_goal.strategicplan.is_active is False:
           plan_ended = True
        elif note.strategic_goal and note.strategic_goal.strategicplan.is_active is False:
           plan_ended = True
        
        context['plan_ended'] = plan_ended
        context['grouped_replies'] = grouped_replies
        context['can_reply'] = self.can_reply(note, user)
        return context

    def post(self, request, *args, **kwargs):
     note = self.get_object()
     user = request.user
     action = request.POST.get("action")

    # Toggle Star (HTMX)
     if action == "toggle_star" and request.headers.get("HX-Request"):
      
        old_data = model_to_dict_with_usernames( note)
        note.is_starred = not note.is_starred
        note.save()
         
        event = "التمييز بنجمة" if note.is_starred else "إزالة التمييز"
         
        logger = LogMixin(request=request)
        logger.log_update(old_instance=old_data, new_instance=note, action=event)


        return render(request, "partials/star_icon.html", {
            "note": note
        })

    # Return unread count (HTMX)
     if action == "unread_count" and request.headers.get("HX-Request"):
        unread_count = get_unread_notes_count(user)
        return HttpResponse(unread_count)

    # Add a reply (HTMX)
     if action == "reply" and self.can_reply(note, user) and request.headers.get("HX-Request"):
        content = request.POST.get("reply_content", "").strip()
        receiver = None

        if note.receiver:
           receiver = note.receiver if note.sender == user else note.sender

        if content:
           reply = Note.objects.create(
            content=content,
            receiver=receiver,
            sender=user,
            parent_note=note,
            initiative=note.initiative,
            strategic_goal=note.strategic_goal
        )
        logger = LogMixin(request=request)
        logger.log_create(reply)

        # make parent note unread again for everyone
        note.read_by.clear()
        note.read_by.add(user)

        return render(request, "partials/note_chat_message.html", {
            "reply": reply
        })
    
     return HttpResponse(status=204)



@method_decorator(never_cache, name='dispatch')
class CreateNoteView(LoginRequiredMixin, LogMixin, CreateView):
    model = Note
    form_class = NoteForm
    template_name = 'partials/note_form.html'
    success_url = reverse_lazy('notes_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        goal_id = self.request.GET.get('goal_id')
        initiative_id = self.request.GET.get('initiative_id')
        

        if goal_id:
            initial['strategic_goal'] = goal_id
        if initiative_id:
            initial['initiative'] = initiative_id


        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        user = self.request.user
        role = user.role.role_name
        plan =  StrategicPlan.objects.filter(is_active = True).first()

        form.fields['receiver'].required = False
        form.fields['initiative'].required = False
        form.fields['strategic_goal'].required = False

        form.fields['receiver'].widget = forms.HiddenInput()
        form.fields['initiative'].widget = forms.HiddenInput()
        form.fields['strategic_goal'].widget = forms.HiddenInput()

        if role == 'GM':
            form.fields['receiver'].widget = forms.Select()
            form.fields['receiver'].queryset = User.objects.filter(role__role_name__in=['M', 'CM'])
            form.fields['strategic_goal'].widget = forms.Select()
            form.fields['strategic_goal'].queryset = StrategicGoal.objects.filter(strategicplan=plan)

        elif role in ['M', 'CM']:
            form.fields['receiver'].widget = forms.Select()
            form.fields['receiver'].queryset = User.objects.filter(department=user.department, role__role_name='E')

            form.fields['initiative'].widget = forms.Select()
            form.fields['initiative'].queryset = Initiative.objects.filter(
                strategic_goal__strategicplan=plan,
                userinitiative__user__department=user.department
            ).distinct()

        elif role == 'E':
            form.fields['initiative'].widget = forms.Select()
            form.fields['initiative'].queryset = Initiative.objects.filter(strategic_goal__strategicplan=plan, userinitiative__user=user).distinct()

      
        if self.request.GET.get('goal_id'):
            form.fields['strategic_goal'].widget = forms.HiddenInput()
            form.fields['receiver'].widget = forms.HiddenInput()
            form.fields['initiative'].widget = forms.HiddenInput()

        if self.request.GET.get('initiative_id'):
            form.fields['strategic_goal'].widget = forms.HiddenInput()
            form.fields['receiver'].widget = forms.HiddenInput()
            form.fields['initiative'].widget = forms.HiddenInput()

        return form
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        goal_id = self.request.GET.get('goal_id')
        initiative_id = self.request.GET.get('initiative_id')

        if goal_id:
            context['selected_goal'] = StrategicGoal.objects.get(id=goal_id)
        if initiative_id:
           context['selected_initiative'] = Initiative.objects.get(id=initiative_id)

        return context

    def form_valid(self, form):
        goal_id = self.request.GET.get('goal_id')
        initiative_id = self.request.GET.get('initiative_id')
        if goal_id:
            form.instance.strategic_goal = StrategicGoal.objects.get(id=goal_id)
            form.instance.receiver = None
            form.instance.initiative = None
        elif initiative_id:
            form.instance.initiative = Initiative.objects.get(id=initiative_id)
            form.instance.receiver = None
            form.instance.strategic_goal = None
    

        self.object = form.save(sender=self.request.user)
        self.log_create(self.object)
        messages.success(self.request, "تم إرسال الملاحظة بنجاح", extra_tags="create")
        
        next_url = self.request.GET.get('next')
        if next_url:
           return redirect(next_url)
        
        return super().form_valid(form)



@method_decorator(never_cache, name='dispatch')
class UpdateNoteView(LoginRequiredMixin, LogMixin, UpdateView):
    '''
    - Allows updating a note
    - Only the sender can update their own notes
    - Only content fields is editable
    - Redirects to notes list
    '''
    model = Note
    fields = ['content']
    template_name = 'partials/note_form.html'
    success_url = reverse_lazy('notes_list')

    def get_queryset(self):
        user = self.request.user

        qs = Note.objects.filter(sender=user)
        if not qs.filter(pk=self.kwargs['pk']).exists():
            raise PermissionDenied("ليس لديك صلاحية تعديل هذه الملاحظة.")
        return qs

    def form_valid(self, form):
        old_instance = self.get_object()
        response = super().form_valid(form)
        self.log_update(old_instance, self.object)
        messages.success(self.request, "تم تحديث الملاحظة بنجاح", extra_tags="update")
        return response



@method_decorator(never_cache, name='dispatch')
class DeleteNoteView(LoginRequiredMixin, LogMixin, DeleteView):
    '''
    - Allows deleting a note
    - Only the sender can delete their own notes
    - Prevents deleting notes sent by others
    - Redirects to notes list
    '''
    model = Note
    success_url = reverse_lazy('notes_list')

    def get_queryset(self):
        user = self.request.user

        qs = Note.objects.filter(sender=user)
        if not qs.filter(pk=self.kwargs['pk']).exists():
            raise PermissionDenied("ليس لديك صلاحية حذف هذه الملاحظة.")
        return qs

    def form_valid(self, form):
        """Custom deletion logic inside form_valid"""
        obj = self.get_object()
        self.log_delete(obj)
        response = super().form_valid(form)
        messages.success(self.request, "تم حذف الملاحظة بنجاح", extra_tags="delete")
        return response



# ---------------------------
#  Log View
# ---------------------------
@method_decorator(never_cache, name='dispatch')
class AllLogsView(LoginRequiredMixin,ListView):
    model = Log
    template_name = 'log.html'
    context_object_name = 'logs'
    
    def get_paginate_by(self, queryset):
        return int(self.request.GET.get('per_page', 25))  # default 25


    ACTION_MAP = {
        'CREATE': 'إنشاء',
        'UPDATE': 'تعديل',
        'DELETE': 'حذف',
        'LOGIN': 'تسجيل الدخول',
        'LOGOUT': 'تسجيل الخروج',
        }
    TABLE_MAP = {
        'User':'نشاط المستخدم',
        'Role': 'المنصب',
        'Department': 'الإدارة',
        'StrategicPlan': 'الخطة الاستراتيجية',
        'StrategicGoal': 'الهدف الاستراتيجي',
        'Initiative': 'المبادرة',
        'UserInitiative': 'تقدم المبادرة',
        'KPI': 'مؤشر الأداء الرئيسي',
        'Note': 'الملاحظات'
    }
    NOTE_FIELD_MAP = {
        'title': 'عنوان الملاحظة',
        'content': 'المحتوى',
        'sender': 'المرسل',
        'receiver': 'المستلم',
        'initiative': 'المبادرة',
        'strategic_goal': 'الهدف الاستراتيجي',
        'parent_note': 'نوع الملاحظة',
        'created_at': 'تاريخ الإنشاء',
        'read_by': 'مقروء من قبل',
        'is_starred': 'مميزة بنجمة',
    }
    KPI_FIELD_MAP = {
        'kpi': 'مؤشر الأداء',
        'unit': 'الوحدة',
        'target_value': 'القيمة المستهدفة',
        'actual_value': 'القيمة الفعلية',
        'start_value': 'قيمة البداية',
        'initiative': 'المبادرة',
    }
    INITIATIVE_FIELD_MAP = {
        # Initiative fields
        'title': 'عنوان المبادرة',
        'description': 'وصف المبادرة',
        'start_date': 'تاريخ البداية',
        'end_date': 'تاريخ النهاية',
        'priority': 'الأولوية',
        'category': 'الفئة',
        'strategic_goal': 'الهدف الاستراتيجي المرتبط',
        
        # UserInitiative fields
        'status': 'حالة المبادرة للموظف',
        'progress': 'نسبة التقدم',
        'initiative': 'المبادرة',
        'user': 'الموظف',
    }
    STRATEGIC_GOAL_FIELD_MAP = {
        'strategicplan': 'الخطة الاستراتيجية',
        'department': 'الإدارة',
        'goal_title': 'عنوان الهدف الاستراتيجي',
        'description': 'وصف الهدف الاستراتيجي',
        'start_date': 'تاريخ بداية الهدف',
        'end_date': 'تاريخ نهاية الهدف',
        'goal_status': 'حالة الهدف',
        'goal_priority': 'أهمية الهدف',
    }
    STRATEGIC_PLAN_FIELD_MAP = {
        'plan_name': 'اسم الخطة الاستراتيجية',
        'vision': 'الرؤية',
        'mission': 'الرسالة',
        'start_date': 'تاريخ بداية الخطة',
        'end_date': 'تاريخ نهاية الخطة',
        'created_by': 'أنشئ بواسطة',
        'is_active': 'نشطة',
    }
    USER_DEPARTMENT_ROLE_FIELD_MAP = {
        'username': 'اسم المستخدم',
        'first_name': 'الاسم الأول',
        'last_name': 'اسم العائلة',
        'email': 'البريد الإلكتروني',
        'employee_number': 'رقم الموظف',
        'role': 'المنصب',
        'department': 'الإدارة',
        'is_staff': 'موظف إداري',
        'is_active': 'نشط',
        'date_joined': 'تاريخ الانضمام',
    }
    STATUS_VALUE_MAP = {
        'NS': 'لم يبدأ بعد',
        'IP': 'قيد التنفيذ',
        'D' : 'متأخر',
        'C': 'مكتمل'
    }
    PRIORITY_VALUE_MAP = {
        'L': 'منخفضة',
        'M': 'متوسطة',
        'H': 'عالية',
        'C': 'حرجة'
    }



    def safe_eval(self, value):
        if not value:
            return {}
        # value = value.replace('""', '"')

        # replace Decimal(...) to float
        value = value.replace("Decimal('", "").replace("')", "")

        # replace datetime.date(...) to string
        value = re.sub(r"datetime\.date\((\d+),\s*(\d+),\s*(\d+)\)", r"'\1-\2-\3'", value)

        # replace <User: ...> with string
        value = re.sub(r"<User: ([^>]+)>", r'"\1"', value)

        # try JSON first
        try:
            return json.loads(value)
        except Exception:
            pass

        # fallback to ast.literal_eval
        try:
            return ast.literal_eval(value)
        except Exception:
            return {}



    def map_value(self, field, value):
        if value is None:
            return None

        if isinstance(value, (dict, list, tuple)):
            return value

        if field in ['status', 'goal_status']:
            return self.STATUS_VALUE_MAP.get(value, value)

        if field in ['priority', 'goal_priority']:
            return self.PRIORITY_VALUE_MAP.get(value, value)

        return value



    def make_friendly_details(self, log):
        """
        Returns a list of friendly strings for a log record:
        - CREATE/DELETE: show all fields as "Field: Value"
        - UPDATE: show only changed fields as "Field: Old → New"
        """
        import ast
        import decimal
        from datetime import datetime

        if not log.old_value and not log.new_value:
            return []

        old_dict = self.safe_eval(log.old_value)
        new_dict = self.safe_eval(log.new_value)

        if log.table_name == 'User':
            field_map = self.USER_DEPARTMENT_ROLE_FIELD_MAP
        elif log.table_name in ['Initiative', 'UserInitiative']:
            field_map = self.INITIATIVE_FIELD_MAP
        elif log.table_name == 'KPI':
            field_map = self.KPI_FIELD_MAP
        elif log.table_name == 'Note':
            field_map = self.NOTE_FIELD_MAP
        elif log.table_name == 'StrategicGoal':
            field_map = self.STRATEGIC_GOAL_FIELD_MAP
        elif log.table_name == 'StrategicPlan':
            field_map = self.STRATEGIC_PLAN_FIELD_MAP
        else:
            field_map = {}

        details = []

        if log.action.upper() in ['إضافة', 'حذف','CREATE', 'DELETE']:
            source = new_dict if log.action == 'إضافة' or log.action.upper() == 'CREATE'  else old_dict
            for key, val in source.items():
                val = self.map_value(key, val)
                # handle types
                if key == 'id': #skip id
                    continue
                if key == 'read_by':
                    if len(val) == 0:
                        val = 'لم تُقرأ بعد'
                    else:
                        val = '، '.join(str(v) for v in val)

                if key == 'initiative':
                    if val:
                        initiative = Initiative.objects.filter(id=val).first()
                        val = initiative.title if initiative else 'مبادرة'
                    else:
                        val = 'لا يوجد'

                if key == 'strategic_goal':
                    if val:
                        strategic_goal = StrategicGoal.objects.filter(id=val).first()
                        val = strategic_goal.goal_title if strategic_goal else 'هدف استراتيجي'
                    else:
                        val = 'لا يوجد'

                if key == 'parent_note':
                    if val is None:
                        val = 'ملاحظة رئيسية'
                    else:
                        parent = Note.objects.filter(id=val).first()
                        if parent:
                            val = f"رد على ملاحظة: {parent.title or f'#{parent.id}'}"
                        else:
                            val = "رد على ملاحظة"
                if val is None:
                    val = 'لا يوجد'
                if val is False:
                    val = 'لا'
                if val is True:
                    val = 'نعم'
                if isinstance(val, decimal.Decimal):
                    val = float(val)
                if isinstance(val, datetime):
                    val = val.strftime("%Y-%m-%d %H:%M")
                if hasattr(val, '__str__'):
                    try:
                        val = str(val)
                    except:
                        pass
                arabic_name = field_map.get(key, key)
                details.append(f"{arabic_name}: {val}")


        elif log.action.upper() == 'UPDATE' or log.action == 'تعديل' :
            for key in set(old_dict.keys()).union(new_dict.keys()):
                old_val = self.map_value(key, old_dict.get(key))
                new_val = self.map_value(key, new_dict.get(key))

                # handle read_by
                if isinstance(old_val, (list, tuple, QuerySet)):
                    old_val = '، '.join(str(u) for u in old_val) if old_val else 'لم تُقرأ بعد'
                if isinstance(new_val, (list, tuple, QuerySet)):
                    new_val = '، '.join(str(u) for u in new_val) if new_val else 'لم تُقرأ بعد'

                # booleans
                if old_val is True:
                    old_val = 'نعم'
                elif old_val is False:
                    old_val = 'لا'
                if new_val is True:
                    new_val = 'نعم'
                elif new_val is False:
                    new_val = 'لا'

                if old_val != new_val:
                    arabic_name = field_map.get(key, key)
                    arrow_svg = """<svg xmlns="http://www.w3.org/2000/svg" fill="none"
                        viewBox="0 0 24 24" stroke-width="1.5"
                        stroke="currentColor" class="size-6 inline mx-1">
                    <path stroke-linecap="round" stroke-linejoin="round"
                            d="M6.75 15.75 3 12m0 0 3.75-3.75M3 12h18" />
                    </svg>"""
                    details.append(mark_safe(f"{arabic_name}: {old_val} {arrow_svg} {new_val}"))

        return details



    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(
                'partials/logs_table_rows.html',
                context,
                request=self.request
            )
            return JsonResponse({'html': html})
        return super().render_to_response(context, **response_kwargs)



    def get_queryset(self):
        qs = Log.objects.filter(table_name__in=self.TABLE_MAP.keys()).order_by('-created_at')        
        user_id = self.request.GET.get('user','')
        search = self.request.GET.get('search', '')
        action = self.request.GET.get('action', '')
        log_date = self.request.GET.get('log_date','')        
        if user_id:
            qs = qs.filter(user_id=user_id)
        if search: 
            qs = qs.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(action__icontains=search) |
                Q(table_name__icontains=search)
            )
        if action:
            qs = qs.filter(action=action)
        if log_date:
            try:
                date_obj = datetime.strptime(log_date, "%Y-%m-%d").date()
                qs = qs.filter(created_at__date=date_obj)
            except ValueError:
                pass  # invalid date input, ignore filter

        for log in qs:
            log.user_friendly_action = self.ACTION_MAP.get(log.action.upper(), log.action)
            log.user_friendly_table_name = self.TABLE_MAP.get(log.table_name, log.table_name)
            log.details = self.make_friendly_details(log)

        return qs



    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['users'] = User.objects.all()
        context['search'] = self.request.GET.get('search', '')
        context['action'] = self.request.GET.get('action', '')

        context['action_map'] = self.ACTION_MAP
        context['current_filters'] = self.request.GET
        context['per_page'] = self.request.GET.get('per_page', 25)
        page_obj = context['page_obj']
        total_pages = context['paginator'].num_pages
        current = page_obj.number

        page_numbers = []
        for num in range(1, total_pages + 1):
            if num == 1 or num == total_pages or abs(num - current) <= 2:
                page_numbers.append(num)
            elif page_numbers[-1] != '...':
                page_numbers.append('...')
        context['page_numbers'] = page_numbers
        return context



