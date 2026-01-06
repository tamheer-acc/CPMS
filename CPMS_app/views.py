from django.contrib import messages
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, CreateView
from django.views.generic.edit import UpdateView, DeleteView
from django.http import JsonResponse
from django.forms import ModelForm
from django.forms.models import model_to_dict  
from django.contrib.auth import login, get_user_model
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin #class based view 
from django.contrib.auth.decorators import login_required, user_passes_test #function based view
from django.core.exceptions import PermissionDenied
from functools import wraps
from .models import ( Role, Department, User, StrategicPlan, StrategicGoal, 
                        Initiative, UserInitiative, KPI, Note, Log, STATUS)
from .services import generate_KPIs,  create_log, get_plan_dashboard
from .forms import KPIForm, StrategicGoalForm, StrategicPlanForm
from django.template.loader import render_to_string
from django.db.models import Q




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



@login_required
def dashboard_view(request):
    '''
    - Displays the main dashboard with an overview of the system
    - Shows initiatives relevant to the logged-in user based on their role
        - General Manager sees all initiatives
        - Managers and Employees see initiatives they are assigned to
    - Lists KPIs related to the user’s initiatives
    - Displays notes created by the user
    - Optionally includes departments and strategic plans for managerial roles
    '''

    user = request.user

    # Initiatives
    if user.role.role_name == 'GM':
        initiatives = Initiative.objects.all()
    elif user.role.role_name in ['M', 'CM']:
        initiatives = Initiative.objects.filter(userinitiative__user=user)
    else:
        initiatives = Initiative.objects.filter(userinitiative__user=user)

    # KPIs assigned to user's initiatives
    kpis = KPI.objects.filter(initiative__userinitiative__user=user)

    # Notes
    notes = Note.objects.filter(sender=user)

    # Departments (optional)
    departments = Department.objects.all() if user.role.role_name in ['GM', 'CM', 'M'] else None
    department = user.department
    
    # Strategic Plans
    plans = StrategicPlan.objects.all() if user.role.role_name in ['GM', 'CM', 'M'] else None

    context = {
        'initiatives': initiatives,
        'kpis': kpis,
        'notes': notes,
        'departments': departments,
        'department': department,
        'plans': plans,
    }

    return render(request, 'dashboard.html', context)



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
        
        if user.role.role_name in ['M', 'CM'] and initiative.strategic_goal.department == user.department: 
            employees = User.objects.filter(role__role_name='E', department=user.department) 
            assigned_employee_ids = set( 
                                        UserInitiative.objects.filter(initiative=initiative)
                                        .values_list('user_id', flat=True) ) 
            
            context['employees'] = employees 
            context['assigned_employee_ids'] = assigned_employee_ids 
            context['form'] = KPIForm()
        else:
            context['employees'] = [] 
            context['assigned_employee_ids'] = set() 
        
        return context



class CreateInitiativeView(LoginRequiredMixin, RoleRequiredMixin, InitiativePermissionMixin, CreateView, LogMixin): #only Managers 
    '''
    - Allows Managers to create a new initiative
    - Sets the strategic goal based on the goal_id in the URL
    - Automatically assigns the current user to the initiative via UserInitiative
    '''    
    model = Initiative
    fields = ['title', 'description', 'start_date', 'end_date', 'priority', 'category']
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
        
        return response
    
    def get_success_url(self):
        # return reverse('goal_detail', kwargs={'goal_id': self.kwargs['goal_id']})
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



class UpdateInitiativeView(LoginRequiredMixin, RoleRequiredMixin, InitiativePermissionMixin, UpdateView, LogMixin):  #managers only
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
    
    def get_success_url(self):
        goal_id = self.kwargs.get('goal_id')
        # if goal_id:
        #     return reverse('goal_initiatives_list', kwargs={'goal_id': goal_id})
        # else:
        return reverse('initiatives_list')



class DeleteInitiativeView(LoginRequiredMixin, RoleRequiredMixin, InitiativePermissionMixin, DeleteView, LogMixin):#managers only
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

    def get_success_url(self):
        goal_id = self.kwargs.get('goal_id')
        # if goal_id:
        #     return reverse('goal_initiatives_list', kwargs={'goal_id': goal_id})
        # else:
        return reverse('initiatives_list')



def is_manager(user):
    return user.role and user.role.role_name in ['M', 'CM']



@login_required
@log_action()
@user_passes_test(is_manager)
def assign_employee_to_initiative(request, pk):
    initiative = get_object_or_404(Initiative, id=pk)
    employees = User.objects.filter(role__role_name='E', department=request.user.department)

    if request.user.role.role_name not in ['M', 'CM'] or initiative.strategic_goal.department != request.user.department:
        raise PermissionDenied("ليست لديك صلاحية لرؤية هذه الصفحة")

    assigned_employee_ids = set(
        UserInitiative.objects.filter(initiative=initiative).values_list('user_id', flat=True)
    )

    if request.method == "POST": #Post request: receives a list of employees
        employee_ids_to_add = request.POST.getlist('to_add[]')
        employee_ids_to_remove = request.POST.getlist('to_remove[]')

        for emp_id in employee_ids_to_add:
            emp = get_object_or_404(User, id=emp_id)
            UserInitiative.objects.get_or_create(user=emp, initiative=initiative, status=STATUS[0][0], progress=0)

        for emp_id in employee_ids_to_remove:
            UserInitiative.objects.filter(user_id=emp_id, initiative=initiative).delete()

        return redirect('initiative_detail', pk=initiative.id)

    return render(request, 'assign_employee.html', { #Get request: returns a list of the department employees 
        'initiative': initiative,
        'employees': employees,
        'assigned_employee_ids': assigned_employee_ids,
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


@log_action()
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
            kpi.save()
            return redirect('initiative_detail', pk=initiative.id)
        else:
            return render(request, 'kpi_form.html', {'initiative': initiative, 'form': form})

    else:
        form = KPIForm()
        ai_suggestion = generate_KPIs(initiative)

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':    # only return partial HTML if request is via JS
            return render(request, 'partials/kpi_form.html', {'form': form, 'suggestions': ai_suggestion})
        
        #if someone opens the url normally
        return render(request, 'kpi_form.html', {'initiative': initiative, 'form': form})



class DeleteKPIView(RoleRequiredMixin, DeleteView, LogMixin):
    '''
    - Allows users to delete a KPI
    - Confirms deletion using a template
    - Redirects to the Initiative detail page after successful deletion
    '''

    model = KPI
    template_name = 'confirm_delete.html'
    allowed_roles = ['M', 'CM']

    success_url = reverse_lazy('initiative_detail')
    def get_success_url(self):
        initiative_id = self.kwargs.get('initiative_id')
        return reverse('initiative_detail', kwargs={'pk': initiative_id})



class UpdateKPIView(RoleRequiredMixin, UpdateView, LogMixin):
    '''
    - Allows users to update an existing KPI
    - Lets users edit fields like kpi name, unit, target, and actual values
    - Redirects to the KPI detail after successful update
    '''
    model = KPI
    fields = ['kpi', 'unit', 'target_value','actual_value']
    template_name = 'kpi_form.html'
    allowed_roles = ['M', 'CM']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['initiative'] = self.object.initiative
        context['is_update'] = True
        return context

    def get_success_url(self):
        initiative_id = self.kwargs.get('initiative_id')
        return reverse('initiative_detail', kwargs={'pk': initiative_id})



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
    paginate_by = 2 # Number of plans to display per page
    allowed_roles = ['M', 'CM', 'GM']  # Roles allowed to access this view

    def get_queryset(self):
        """
        - Retrieves the queryset of StrategicPlan objects.
        - Automatically updates any active plan that has passed its end_date to inactive.
        - Applies search and status filters if provided in GET parameters.
        """
        queryset = StrategicPlan.objects.all()
        
        # Update plans that ended to inactive
        today = timezone.now().date()
        queryset.filter(is_active=True, end_date__lt=today).update(is_active=False)

        # Handle search and status filtering
        search = self.request.GET.get('search', '')
        status = self.request.GET.get('status', '')
        if search or status:
            q = Q(plan_name__icontains=search) if search else Q()
            if status == 'active':
                q &= Q(is_active=True)
            elif status == 'inactive':
                q &= Q(is_active=False)
            queryset = queryset.filter(q)

        return queryset

    def get_context_data(self, **kwargs):
        """
        - Adds extra context to the template, such as custom pagination page numbers.
        - Shows first, last, and surrounding pages (for better pagination navigation).
        """
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
        """
        - Handles AJAX requests differently: returns only partial HTML for the table.
        - For normal requests, renders the full template as usual.
        """
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string('partials/plans_table_rows.html', context, request=self.request)
            return JsonResponse({
                'html': html,
                'has_plans': context['page_obj'].object_list.exists()
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
        return context

            
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
        messages.success(self.request, "تمت إضافة الخطة بنجاح")
        return super().form_valid(form)
 

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
        messages.success(self.request, "تم تحديث الخطة بنجاح")
        return super().form_valid(form)


class DeletePlanView(LoginRequiredMixin, RoleRequiredMixin, DeleteView):
    '''
    - Only Committee Manager can delete a plan 
    - Redirects to plans list after deletion
    '''
    model = StrategicPlan
    success_url = reverse_lazy('plans_list')
    allowed_roles = ['CM']  # Roles allowed to access this view

   
       
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
    template_name = 'partials/goals_list.html'
    context_object_name = 'goals'
        
    def get_queryset(self):
        user = self.request.user
        role = user.role.role_name

        if role == 'GM':
            return StrategicGoal.objects.all()
        elif role in ['M','CM']:
            return StrategicGoal.objects.filter(department = user.department)
        elif role == 'E':
            return StrategicGoal.objects.all().prefetch_related('initiative_set__userinitiative_set')

        
        return StrategicGoal.objects.none()

 
class GoalDetailsview(LoginRequiredMixin, DetailView):
    '''
    - Shows details of a single goal
    '''
    model = StrategicGoal 
    template_name = 'goal_detail.html'
    context_object_name = 'goal'     


class CreateGoalView(LoginRequiredMixin, RoleRequiredMixin, LogMixin, CreateView):
    '''
    - Allows Managers and Committee Managers to create a new goal
    - Links the goal to the plan and the user's department
    - Redirects to the goals list after creation
    '''
    model = StrategicGoal
    form_class = StrategicGoalForm
    template_name = 'goal_form.html'
    success_url = reverse_lazy('partials\goals_list.html')
    allowed_roles = ['M', 'CM']  # Roles allowed to access this view

    def form_valid(self, form):
        self.object = form.save(user=self.request.user, plan_id=self.kwargs['plan_id'])
        return super().form_valid(form)


class UpdateGoalView(LoginRequiredMixin, RoleRequiredMixin, LogMixin, UpdateView):
    '''
    - Managers and Committee Managers can update goals in their department
    - Updates goal details
    - Redirects to goals list
    '''
    model = StrategicGoal
    form_class = StrategicGoalForm
    template_name = 'goal_form.html'
    success_url = reverse_lazy('partials\goals_list.html')
    allowed_roles = ['M', 'CM']  # Roles allowed to access this view

    def form_valid(self, form):
        self.object = form.save(user=self.request.user)
        return super().form_valid(form)
    

class DeleteGoalView(LoginRequiredMixin, RoleRequiredMixin, LogMixin, DeleteView):
    '''
    - Managers and Committee Managers can delete goals in their department
    - Shows confirmation before deletion
    - Redirects to goals list
    '''
    model = StrategicGoal
    success_url = reverse_lazy('partials\goals_list.html')
    allowed_roles = ['M', 'CM']  # Roles allowed to access this view

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

        if role == 'GM':
            # All notes sent by the General Manager
            return Note.objects.filter(user=user)
        elif role in ['M','CM']:
            # All notes sent by the user and those received from the General Manager
            return Note.objects.filter(user=user,department=user.department)
        elif role == 'E':
            # All notes sent by the user and those received for the same initiative or sent to them by the manager
            return Note.objects.filter(user=user,initiative__userinitiative__user=user,department=user.department).distinct()

        return Note.objects.none()
        

class NoteDetailsview(LoginRequiredMixin, DetailView):
    '''
    - Shows details of a single note
    '''
    model = Note 
    template_name = 'note_detail.html'
    context_object_name = 'note'
        
        
class CreateNoteView(LoginRequiredMixin, LogMixin, CreateView):
    '''
    - Allows creating a new note
    - Sets sender as current user
    - Receiver options filtered based on sender's role
    '''
    model = Note
    fields = ['content', 'initiative', 'department', 'receiver']
    template_name = 'note_form.html'
    success_url = reverse_lazy('notes_list')
    
    # This is to set the receiver's name from a custom dropdown
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        user = self.request.user
        role = user.role.role_name

        if role == 'GM':
            form.fields['receiver'].queryset = User.objects.filter(role__role_name='M')
        elif role in ['M','CM']:
            form.fields['receiver'].queryset = User.objects.filter(department=user.department, role__role_name='E')
        elif role == 'E':
            form.fields['receiver'].queryset = User.objects.filter(
                userinitiative__initiative__in=Initiative.objects.filter(
                    userinitiative__user=user)
                        ).distinct()
        return form

    def form_valid(self, form):
        form.instance.sender = self.request.user
        return super().form_valid(form) 


class UpdateNoteView(LoginRequiredMixin, LogMixin, UpdateView):
    '''
    - Allows updating a note
    - Only the sender can update their own notes
    - Only content fields is editable
    - Redirects to notes list
    '''
    model = Note
    fields = ['content']
    template_name = 'note_form.html'
    success_url = reverse_lazy('notes_list')

    def get_queryset(self):
        user = self.request.user

        qs = Note.objects.filter(sender=user)
        if not qs.filter(pk=self.kwargs['pk']).exists():
            raise PermissionDenied("ليس لديك صلاحية تعديل هذه الملاحظة.")
        return qs
    
    def form_valid(self, form):
        form.instance.sender = self.request.user
        return super().form_valid(form)
    

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
    
    
# ---------------------------
#  Log View
# ---------------------------
class AllLogsView(ListView): 
    model = Log 
    template_name = 'logs_list.html'
    context_object_name = 'logs'

    def get_queryset(self):
        return Log.objects.all()
    





