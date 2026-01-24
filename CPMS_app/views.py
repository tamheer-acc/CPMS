from itertools import groupby
from django import forms
from django.utils import timezone
from django.utils.timezone import now, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, CreateView, TemplateView
from django.views.generic.edit import UpdateView, DeleteView
from django.http import HttpResponse, JsonResponse
from django.forms import BooleanField, ModelForm
from django.forms.models import model_to_dict  
from django.template.loader import render_to_string
from django.db.models import Q,F, Case,Exists, When, Value, IntegerField, OuterRef, Subquery, BooleanField,CharField, Avg, Count
from django.db.models.functions import Concat, Coalesce
from django.db.models import Q, Case, When, Value, IntegerField
from django.contrib import messages
from django.contrib.auth import login, get_user_model
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin #class based view
from django.contrib.auth.decorators import login_required, user_passes_test #function based view
from django.core.exceptions import PermissionDenied
from functools import wraps
from .forms import InitiativeForm, KPIForm, NoteForm, StrategicGoalForm, StrategicPlanForm, UserInitiativeForm
from .models import ( STATUS, Role, Department, User, StrategicPlan, StrategicGoal,
                        Initiative, UserInitiative, KPI, Note, Log, ProgressLog)
from .services import ( generate_KPIs,  create_log, get_plan_dashboard, calc_user_initiative_status, 
                        filter_queryset, get_page_numbers, paginate_queryset, status_count, avg_calculator, 
                        calc_delayed, kpi_filter, weight_initiative, get_unread_notes_count, departments_progress_over_time)




class LogMixin:
    '''
    - Mixin to automatically log all actions (CREATE, UPDATE, DELETE) for Class-Based Views (CBVs).
    '''

    # -----------------------------
    # Handle form submissions (CREATE or UPDATE)
    # -----------------------------
    def form_valid(self, form):
        '''
        This method is called when a valid form is submitted.
        - For UPDATE: captures old values before saving.
        - Saves the object first, then logs the action (CREATE or UPDATE).
        '''
        # Check if this is an UPDATE
        if hasattr(self, 'object') and self.object.pk:
            old_data = model_to_dict(self.object)
        else:
            old_data = None

        response = super().form_valid(form)

        # Log the action after saving
        create_log(
            user=self.request.user,
            action="CREATE" if self.request.method.lower() == "post" and not old_data else "UPDATE",
            instance=self.object,
            old_data=old_data
        )

        return response

    # -----------------------------
    # Handle object deletion
    # -----------------------------
    def delete(self, request, *args, **kwargs):
        '''
        This method is called when an object is deleted.
        - Captures all old values before deletion.
        - Deletes the object.
        - Logs the DELETE action with old values.
        '''
        # Get the object to delete
        self.object = self.get_object()

        # Save old values before deletion
        old_data = model_to_dict(self.object)

        # Delete the object by calling parent class's delete
        response = super().delete(request, *args, **kwargs)

        # Log the deletion
        create_log(
            user=self.request.user,
            action="DELETE",
            old_data=old_data
        )

        return response



def log_action(action_type="AUTO"):
    '''
    Decorator to log CREATE, UPDATE, DELETE actions for FBVs.
    - GET requests are ignored (no logging)
    '''
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Only log POST/PUT/DELETE
            if request.method.lower() in ["post", "put", "delete"]:
                # Try to get the object if FBV uses 'pk' in kwargs
                obj = None
                if hasattr(view_func, 'model') and kwargs.get('pk'):
                    obj = view_func.model.objects.filter(pk=kwargs['pk']).first()
                old_data = model_to_dict(obj) if obj else None

                response = view_func(request, *args, **kwargs)  # call the actual view

                # Determine action type
                action = action_type
                if action_type == "AUTO":
                    method = request.method.lower()
                    if method == "post":
                        action = "CREATE" if not old_data else "UPDATE"
                    elif method == "put":
                        action = "UPDATE"
                    elif method == "delete":
                        action = "DELETE"

                # Safely get instance for logging
                instance = obj if obj else getattr(response, 'instance', None)

                # Call logging function
                create_log(
                    user=request.user,
                    action=action,
                    instance=instance,
                    old_data=old_data
                )

                return response

            # For GET requests, just call the view normally
            return view_func(request, *args, **kwargs)

        return _wrapped_view
    return decorator



#Helper class that acts like UserPassesTestMixin:
class RoleRequiredMixin(UserPassesTestMixin):
    allowed_roles = []

    def test_func(self):
        return self.request.user.role.role_name in self.allowed_roles

    def handle_no_permission(self):
        return redirect('access_denied')



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
        goal_id = self.kwargs.get('goal_id')

        if goal_id:
            goal = get_object_or_404(StrategicGoal, id=goal_id)

            if role == 'GM':
                return Initiative.objects.filter(strategic_goal = goal)

            elif user.department != goal.department:
                raise PermissionDenied("ليست لديك صلاحية لرؤية هذه الصفحة")

            elif role in ['CM','M']:
                qs = Initiative.objects.filter( strategic_goal = goal , strategic_goal__department = user.department)

            elif role == 'E':
                qs = Initiative.objects.filter( strategic_goal = goal , userinitiative__user = user )

            else:
                raise PermissionDenied("ليست لديك صلاحية لرؤية هذه الصفحة")

        else: # No goal id

            if role == 'GM' and not goal_id:
                return Initiative.objects.all()

            elif role in ['CM','M','E']:
                qs = Initiative.objects.filter(userinitiative__user=user)

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
#  Access Denied View
# ---------------------------
def access_denied_view(request, exception=None):
    return render(request, 'access_denied.html', status=403)



# ---------------------------
#  Access Denied View
# ---------------------------
def page_not_found_view(request, exception=None):
    return render(request, 'page_not_found.html', status=404)



# ---------------------------
#  Dashboard View
# ---------------------------
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


        # GENERAL MANAGER #
        if user.role.role_name == 'GM':
            
            goals = StrategicGoal.objects.all()
            departments = Department.objects.all()
            initiatives = Initiative.objects.all()
            userinitiatives = UserInitiative.objects.all()
            for goal in goals:
                goal.user_initiatives = initiatives.filter(strategic_goal=goal)

            # Bar Chart ( مدى اكتمال الأهداف ) : avg of progress for each goal
            goals_with_avg = StrategicGoal.objects.annotate( avg_progress=Avg('initiative__userinitiative__progress', filter=Q(initiative__userinitiative__user__role__role_name='E')))
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
                initiatives = Initiative.objects.filter(strategic_goal=goal)
                ns_count, ip_count, a_count = 0, 0, 0
                for initiative in initiatives:
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
            
            context['plans'] = StrategicPlan.objects.all()      #  Plans
            context['goals'] = goals                            #  Goals
            context['initiatives'] = Initiative.objects.all()   #  initiative
            context['kpis'] = KPI.objects.all()                 #  KPIs




        # MANAGERS #
        elif user.role.role_name in ['M', 'CM']:
            userinitiatives = UserInitiative.objects.filter(user__department = user.department, user__role__role_name = 'E' )
            initiatives = Initiative.objects.filter(userinitiative__user=user )
            goals = StrategicGoal.objects.filter(department = user.department) 
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
                avrage_goal_progress = avg_calculator(UserInitiative.objects.filter(initiative__strategic_goal = goal, user__role__role_name = 'E' ))
                bar_chart_labels.append(goal.goal_title)
                bar_chart_data.append(avrage_goal_progress or 0)
            context['bar_chart_labels'] = bar_chart_labels
            context['bar_chart_data'] = bar_chart_data
            
            
            # Bar Chart ( توزيع العمل ) : each employee and the number of initiatives they're working on
            employees = User.objects.filter(role__role_name = 'E', department = user.department).annotate(workload=Count('userinitiative')).order_by('workload')
            bar_chart2_labels = []
            bar_chart2_data = []
            for employee in employees:
                bar_chart2_labels.append(employee.get_full_name())
                bar_chart2_data.append(employee.workload)
            context['bar_chart2_labels'] = bar_chart2_labels
            context['bar_chart2_data'] = bar_chart2_data
            
            
            # Stacked Bar Chart ( مؤشرات الأداء الرئيسية ) : KPIs based on status, grouped by initiatives 
            kpis = KPI.objects.filter(initiative__strategic_goal__department = user.department)
            achieved, in_progress, not_started = kpi_filter(kpis)
            initiative_labels = [initiative.title for initiative in (Initiative.objects.filter(userinitiative__user=user))]
            
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

            context['plans'] = StrategicPlan.objects.all()                              #  Plans
            context['goals'] = goals                                                    #  Goals
            context['initiatives'] = initiatives                                        #  Initiative
            context['kpis'] = KPI.objects.filter(initiative__userinitiative__user=user) #  KPIs




        # EMPLOYEES #
        else: 
            
            initiatives = Initiative.objects.filter(userinitiative__user=user)
            userinitiatives = UserInitiative.objects.filter(user = user)
            goals = StrategicGoal.objects.filter(initiative__userinitiative__user=user).distinct().prefetch_related('initiative_set__userinitiative_set')

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
                ui = UserInitiative.objects.filter(initiative = initiative)
                bar_chart_data.append(avg_calculator(ui))
                bar_chart_labels.append(initiative.title)
            context['bar_chart_data'] = bar_chart_data
            context['bar_chart_labels'] = bar_chart_labels
            
            # Card ( متوسط نسبة الإنجاز ) : Avrage Progress 
            avrage_progress = avg_calculator(userinitiatives)
            context['avrage_progress'] = avrage_progress
            
            # Card ( المبادرات الموشكة على الانتهاء & المبادرات المنتهية ) : Overdue and Delayed Initiatives 
            overdue, late = calc_delayed(Initiative.objects.filter(userinitiative__user=user))
            context['overdue'] = overdue
            context['late'] = late

            # Stacked Bar Chart ( مؤشرات الأداء الرئيسية ) : KPIs based on status, grouped by users initiatives 
            kpis = KPI.objects.filter(initiative__userinitiative__user = user)
            achieved, in_progress, not_started = kpi_filter(kpis)
            initiative_labels = [initiative.title for initiative in (Initiative.objects.filter(userinitiative__user=user))]
            
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
            
            context['plans'] = StrategicPlan.objects.filter(is_active = True)  #  plans
            context['goals'] = goals
            context['initiatives'] = Initiative.objects.filter(userinitiative__user=user)  #  initiative
            context['kpis'] = KPI.objects.filter(initiative__userinitiative__user=user)  #  KPIs



        # Shared content #
        
        # List ( ترتيب أداء الإدارات ) : list of all departments ordered by performance  
        departments = Department.objects.all()
        goals = StrategicGoal.objects.all()
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

        context['notes'] = Note.objects.filter(sender=user)
        context['departments'] = departments
        context['department'] = user.department if user.role.role_name != 'GM' else None

        return context



# ---------------------------
#  Initiative Views
# ---------------------------
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



class InitiativeDetailsView(LoginRequiredMixin, InitiativePermissionMixin, DetailView):
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
            context['form'] = KPIForm()
            context['unassigned_employees'] = unassigned_employees 
        elif user.role.role_name == 'GM':
            context['unassigned_employees'] = unassigned_employees 
            
        return context



class CreateInitiativeView(LoginRequiredMixin, RoleRequiredMixin, InitiativePermissionMixin, CreateView):
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



class UpdateInitiativeView(LoginRequiredMixin, RoleRequiredMixin, InitiativePermissionMixin, UpdateView):  #managers only
    '''
    - Allows updating an existing initiative
    - Only the initiative fields are editable (title, description, dates, priority, category)
    - The strategic goal and assigned users remain unchanged
    '''
    model = Initiative
    template_name = 'initiative_form.html'
    fields = ['title', 'description', 'start_date', 'end_date', 'priority', 'category']
    allowed_roles = ['M', 'CM']

    def get_queryset(self):
        # explicitly use the mixin’s logic
        return super().get_queryset()

    def form_valid(self, form):
        response = super().form_valid(form)
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



class DeleteInitiativeView(LoginRequiredMixin, RoleRequiredMixin, InitiativePermissionMixin, DeleteView):#managers only
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

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        messages.success(request, f"تم حذف المبادرة: {obj.title}", extra_tags="delete")
        return super().delete(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('initiatives_list')



def is_manager(user):
    return user.role and user.role.role_name in ['M', 'CM']



@login_required

@user_passes_test(is_manager)
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

        for emp_id in employee_ids_to_add:
            emp = get_object_or_404(User, id=emp_id)
            UserInitiative.objects.get_or_create(user=emp, initiative=initiative, status=STATUS[0][0], progress=0)

        for emp_id in employee_ids_to_remove:
            UserInitiative.objects.filter(user_id=emp_id, initiative=initiative).delete()
        
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


def add_progress(request, initiative_id):
    user = request.user
    initiative = get_object_or_404(Initiative, id=initiative_id)
    user_initiative = get_object_or_404(UserInitiative, initiative=initiative, user=user)
    
    if request.method == 'POST':
        form = UserInitiativeForm(request.POST, instance=user_initiative)
        if form.is_valid():
            form.save()
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
class KPIDetailsView(DetailView):
    '''
    - Shows details of a single KPI
    '''
    model = KPI
    template_name = "KPI_detail.html"
    context_object_name = "KPI"


@user_passes_test(is_manager)
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



class DeleteKPIView(RoleRequiredMixin, DeleteView):
    '''
    - Allows users to delete a KPI
    - Confirms deletion using a template
    - Redirects to the Initiative detail page after successful deletion
    '''

    model = KPI
    template_name = 'confirm_delete.html'
    allowed_roles = ['M', 'CM']
    
    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        messages.success(request, f"تم حذف مؤشر القياس: {obj.kpi}", extra_tags="delete")
        success_url = self.get_success_url()
        obj.delete() 
        return redirect(success_url)

    def get_success_url(self):
        initiative_id = self.kwargs.get('initiative_id')
        return reverse('initiative_detail', kwargs={'pk': initiative_id})



def edit_kpi_view(request, initiative_id, kpi_id):
    kpi = get_object_or_404(KPI, id=kpi_id, initiative_id=initiative_id)
    
    if request.method == 'POST':
        form = KPIForm(request.POST, instance=kpi)
        if form.is_valid():
            form.save()
            messages.success(request, f"تم تعديل مؤشر القياس: {kpi.kpi} بنجاح", extra_tags="update")
            return redirect('initiative_detail', pk=initiative_id)
    else:
        form = KPIForm(instance=kpi)

    return render(request, 'partials/kpi_modal.html', {
        'form': form,
        'object': kpi,
        'initiative': kpi.initiative,
        'is_update': True,
    })



class AllKPIsView(ListView): #not needed but here we go
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



# Paths and URLs [done]
# conditioning (depending on Role) [done]
# AI Model Handling



#########################################################################################################################
#                                                    WALAA's Views                                                      #
#########################################################################################################################

# ---------------------------
#  Department View
# ---------------------------
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
      per_page = 5

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
         dashboard_data = get_plan_dashboard(self.object, self.request.user)
         context.update(dashboard_data)
         user = self.request.user
         role = user.role.role_name
         goals_qs = StrategicGoal.objects.filter(strategicplan=self.object)

         #search & filter function
         goals_qs = filter_queryset(
           queryset=goals_qs,
           request=self.request,
           search_fields=['goal_title'],
           status_field='goal_status',
           priority_field='goal_priority'
         )

         if role in ['M', 'CM']:
            goals_qs = goals_qs.filter(department=user.department)

         per_page = 5
         goal_list, page_obj, paginator = paginate_queryset(goals_qs, self.request, per_page)

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


class CreatePlanView(LoginRequiredMixin, CreateView):
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
        messages.success(self.request, "تم إنشاء الخطة بنجاح", extra_tags="create")
        return super().form_valid(form)


class UpdatePlanView(LoginRequiredMixin, UpdateView):
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
        messages.success(self.request, "تم تحديث الخطة بنجاح", extra_tags="update")
        return super().form_valid(form)


class DeletePlanView(LoginRequiredMixin, RoleRequiredMixin, DeleteView):
    '''
    - Only Committee Manager can delete a plan
    - Redirects to plans list after deletion
    '''
    model = StrategicPlan
    success_url = reverse_lazy('plans_list')
    allowed_roles = ['CM']  # Roles allowed to access this view

    def form_valid(self, form):
        """Custom deletion logic inside form_valid"""
        response = super().form_valid(form)
        messages.success(self.request, "تم حذف الخطة بنجاح", extra_tags="delete")
        return response


# ---------------------------
#  StrategicGoal View
# ---------------------------
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

        if role == 'GM':
            qs = StrategicGoal.objects.all()
        elif role in ['M','CM']:
            qs = StrategicGoal.objects.filter(department = user.department)
        elif role == 'E':
            qs = StrategicGoal.objects.all().prefetch_related('initiative_set__userinitiative_set')

        search = self.request.GET.get('search', '').strip()

        if search:
                qs = qs.filter(goal_title__icontains=search)


        return qs
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


class GoalDetailsview(LoginRequiredMixin, DetailView):
    '''
    - Shows details of a single goal
    '''
    model = StrategicGoal
    template_name = 'goal_detail.html'
    context_object_name = 'goal'


class CreateGoalView(LoginRequiredMixin, RoleRequiredMixin, CreateView):
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
        self.object = form.save(user=self.request.user, plan_id=self.kwargs['plan_id'])
        messages.success(self.request, "تمت إضافة الهدف بنجاح", extra_tags="create")
        return super().form_valid(form)
    def get_success_url(self):
        return reverse('plan_detail', kwargs={'pk': self.kwargs['plan_id']})


class UpdateGoalView(LoginRequiredMixin, RoleRequiredMixin, UpdateView):
    '''
    - Managers and Committee Managers can update goals in their department
    - Updates goal details
    - Redirects to goals list
    '''
    model = StrategicGoal
    form_class = StrategicGoalForm
    template_name = 'goal_form.html'
    success_url = reverse_lazy('plan_goals_list')
    allowed_roles = ['M', 'CM']  # Roles allowed to access this view

    def form_valid(self, form):
        self.object = form.save(user=self.request.user)
        messages.success(self.request, "تم تحديث الهدف بنجاح", extra_tags="update")
        return super().form_valid(form)


class DeleteGoalView(LoginRequiredMixin, RoleRequiredMixin, DeleteView):
    '''
    - Managers and Committee Managers can delete goals in their department
    - Shows confirmation before deletion
    - Redirects to goals list
    '''
    model = StrategicGoal
    success_url = reverse_lazy('plan_goals_list')
    allowed_roles = ['M', 'CM']  # Roles allowed to access this view

    def form_valid(self, form):
        """Custom deletion logic inside form_valid"""
        response = super().form_valid(form)
        messages.success(self.request, "تم حذف الهدف بنجاح", extra_tags="delete")
        return response

# ---------------------------
#  Note View
# ---------------------------
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

        qs = qs.annotate(
        is_sent=Case(
            When(
                Q(is_user_participant=True) & Q(last_sender_id=user.id),
                then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        )
    )
        qs = qs.annotate(
           display_user_id=Case(
           When(is_inbox=True, then=F('last_sender_id')),
           When(is_sent=True, then=Value(user.id)),
          default=F('sender_id'),
          output_field=IntegerField()
          )
    )
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

            if current_filter == "read":
                qs = qs.filter(read_by=user)  # read notes

            elif current_filter == "unread":
                qs = qs.exclude(read_by=user)  # unread notes

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



class NoteDetailsview(LoginRequiredMixin, DetailView):
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

        context['grouped_replies'] = grouped_replies
        context['can_reply'] = self.can_reply(note, user)
        return context

    def post(self, request, *args, **kwargs):
     note = self.get_object()
     user = request.user
     action = request.POST.get("action")

    # Toggle Star (HTMX)
     if action == "toggle_star" and request.headers.get("HX-Request"):
        note.is_starred = not note.is_starred
        note.save()

        return render(request, "partials/star_icon.html", {
            "note": note
        })

    # Return unread count (HTMX)
     if action == "unread_count" and request.headers.get("HX-Request"):
        unread_count = get_unread_notes_count(user)
        return HttpResponse(unread_count)

        # if unread_count == 0:
        #   return HttpResponse("""
        #     <span id="unread-dot" class="hidden"></span>
        #     <span id="unread-badge" class="hidden"></span>""")

        # return HttpResponse(f"""
        #   <span id="unread-dot"
        #       class="absolute top-[10px] right-[10px]
        #              w-2 h-2 bg-red-500 rounded-full group-hover:hidden">
        #   </span>
        #   <span id="unread-badge"
        #       class="hidden group-hover:inline whitespace-nowrap
        #              ml-2 text-xs font-semibold text-red-500
        #              bg-red-100 px-2 py-1 rounded-full">
        #      {unread_count}
        #   </span> """)

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

        # make parent note unread again for everyone
        note.read_by.clear()
        note.read_by.add(user)

        return render(request, "partials/note_chat_message.html", {
            "reply": reply
        })
    
     return HttpResponse(status=204)


class CreateNoteView(LoginRequiredMixin, CreateView):
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
            form.fields['strategic_goal'].queryset = StrategicGoal.objects.all()

        elif role in ['M', 'CM']:
            form.fields['receiver'].widget = forms.Select()
            form.fields['receiver'].queryset = User.objects.filter(department=user.department, role__role_name='E')

            form.fields['initiative'].widget = forms.Select()
            form.fields['initiative'].queryset = Initiative.objects.filter(
                userinitiative__user__department=user.department
            ).distinct()

        elif role == 'E':
            form.fields['initiative'].widget = forms.Select()
            form.fields['initiative'].queryset = Initiative.objects.filter(userinitiative__user=user).distinct()

        # إذا دخلنا من الهدف hide كل شيء
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
        messages.success(self.request, "تم إرسال الملاحظة بنجاح", extra_tags="create")
        
        next_url = self.request.GET.get('next')
        if next_url:
           return redirect(next_url)
        
        return super().form_valid(form)


class UpdateNoteView(LoginRequiredMixin, UpdateView):
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
        self.object = form.save(user=self.request.user)
        messages.success(self.request, "تم تحديث الملاحظة بنجاح", extra_tags="update")
        return super().form_valid(form)


class DeleteNoteView(LoginRequiredMixin, DeleteView):
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
        response = super().form_valid(form)
        messages.success(self.request, "تم حذف الملاحظة بنجاح", extra_tags="delete")
        return response

# ---------------------------
#  Log View
# ---------------------------
class AllLogsView(ListView):
    model = Log
    template_name = 'log.html'
    context_object_name = 'logs'
    paginate_by = 20  # لو تبي تقسيم صفحات

    def get_queryset(self):
        return Log.objects.all().order_by('-created_at')







