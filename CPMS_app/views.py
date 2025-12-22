from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, CreateView
from django.views.generic.edit import UpdateView, DeleteView
from django.http import JsonResponse
from django.forms import ModelForm
from django.contrib.auth import login, get_user_model
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin #class based view 
from django.contrib.auth.decorators import login_required, user_passes_test #function based view
from django.core.exceptions import PermissionDenied
from .models import ( Role, Department, User, StrategicPlan, StrategicGoal, 
                        Initiative, UserInitiative, KPI, Note, Log, STATUS)
from .services import generate_KPIs
from .forms import KPIForm



########################################################################
#                           Initiative Views                           #
########################################################################



#Helper class that acts like UserPassesTestMixin:
class IsManagerUserMixin(UserPassesTestMixin):
    def test_func(self): #only managers access this view
        return self.request.user.role.role_name in ['M', 'CM']
    
    def handle_no_permission(self):
        return redirect('access_denied') 



class AllInitiativeView(ListView): 
    '''
    List all initiatives
    - General Manager sees all initiatives
    - Managers see their departments initiatives 
    - Employee see the initiatives they are assigned to
    '''
    model = Initiative 
    template_name = 'initiatives_list.html'
    context_object_name = 'initiatives'
    
    def get_queryset(self):
        goal_id = self.kwargs.get('goal_id')
        if goal_id:
            if self.request.user.role.role_name == 'GM':
                return Initiative.objects.all()
            else:  
                return Initiative.objects.filter( strategic_goal_id = goal_id , userinitiative__user = self.request.user )
        else:
            if self.request.user.role.role_name == 'GM':
                return Initiative.objects.all()
            else:  # Managers and Employees
                return Initiative.objects.filter( userinitiative__user=self.request.user )



class InitiativeDetailsView(DetailView):
    '''
    - Shows details of a single initiative
    '''
    model = Initiative
    template_name = "initiative_detail.html"
    context_object_name = "initiative"



class CreateInitiativeView(IsManagerUserMixin,CreateView): #only Managers 
    '''
    - Allows Managers to create a new initiative
    - Sets the strategic goal based on the goal_id in the URL
    - Automatically assigns the current user to the initiative via UserInitiative
    '''
    model = Initiative
    fields = ['title', 'description', 'start_date', 'end_date', 'priority', 'category']
    template_name = 'initiative_form.html'

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
        return reverse('goal_detail', kwargs={'goal_id': self.kwargs['goal_id']})



class UpdateInitiativeView(IsManagerUserMixin,UpdateView):  #managers only
    '''
    - Allows updating an existing initiative
    - Only the initiative fields are editable (title, description, dates, priority, category)
    - The strategic goal and assigned users remain unchanged
    '''
    model = Initiative
    template_name = 'initiative_form.html'
    fields = ['title', 'description', 'start_date', 'end_date', 'priority', 'category']
    
    def get_success_url(self):
        goal_id = self.kwargs.get('goal_id')
        if goal_id:
            return reverse('goal_initiatives_list', kwargs={'goal_id': goal_id})
        else:
            return reverse('initiatives_list')



class DeleteInitiativeView(IsManagerUserMixin, DeleteView):#managers only
    '''
    - Allows deletion of an initiative
    - All related UserInitiative entries are automatically deleted (on_delete=CASCADE)
    - After deletion redirects to Initiatives list
    '''
    model = Initiative
    template_name = 'initiative_confirm_delete.html'
    
    def get_success_url(self):
        goal_id = self.kwargs.get('goal_id')
        if goal_id:
            return reverse('goal_initiatives_list', kwargs={'goal_id': goal_id})
        else:
            return reverse('initiatives_list')



def is_manager(user):
    if user.role.role_name in ['M', 'CM']:
        return True
    return redirect('access_denied') 



@user_passes_test(is_manager)
def assign_employee_to_initiative(request, initiative_id):
    '''
    - Allows assigning one or more employees to a given initiative
    - GET request: returns a list of employees in the current user's department to select from
    - POST request: receives a list of employee IDs from the form and creates UserInitiative entries
    - After successful assignment, redirects to the initiative detail page
    '''
    initiative = get_object_or_404(Initiative, id=initiative_id)
    employees = User.objects.filter(role__role_name='E', department = request.user.department)  
    
    if request.method == "POST": #Post request: receives a list of employees
        employees_ids_list = request.POST.getlist('user_ids') #$$use in template 
        if employees_ids_list:
            for employee_id in employees_ids_list:
                employee = get_object_or_404(User, id=employee_id)
                UserInitiative.objects.get_or_create(
                user=employee,
                initiative=initiative,
                status = STATUS[0][0],
                progress = 0
                )
        return redirect('initiative_detail', pk=initiative.id)
    
    else: #Get request: returns a list of the department employees 
        return render(request, 'assign_employee.html', {
        'initiative': initiative,
        'employees': employees
    })



######################################################################### 
#                               KPI Views                               # 
#########################################################################



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
    initiative = get_object_or_404(Initiative, id=initiative_id)
    if request.method == "POST":
        form = KPIForm(request.POST)
        if form.is_valid():
            kpi = form.save(commit=False)
            kpi.initiative = initiative
            kpi.save()
            return redirect('initiative_detail', pk=initiative.id)
        else:
            return render(request, 'kpi_create', {'initiative': initiative, 'form': form})

    else:
        form = KPIForm()
        ai_suggestion = generate_KPIs(initiative)

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':    # only return partial HTML if request is via JS
            return render(request, 'partials/kpi_form.html', {'form': form, 'suggestions': ai_suggestion})
        
        #if someone opens the url normally
        return render(request, 'kpi_page.html', {'initiative': initiative, 'form': form})



class DeleteKPIView(IsManagerUserMixin,DeleteView):
    '''
    - Allows users to delete a KPI
    - Confirms deletion using a template
    - Redirects to the Initiative detail page after successful deletion
    '''

    model = KPI
    template_name = 'confirm_delete.html'
    

    success_url = reverse_lazy('initiative_detail')
    def get_success_url(self):
        initiative_id = self.kwargs.get('initiative_id')
        return reverse('initiative_detail', kwargs={'pk': initiative_id})



class UpdateKPIView(IsManagerUserMixin,UpdateView):
    '''
    - Allows users to update an existing KPI
    - Lets users edit fields like kpi name, unit, target, and actual values
    - Redirects to the KPI detail after successful update
    '''
    model = KPI
    fields = ['kpi', 'unit', 'target_value','actual_value']
    template_name = 'kpi_form.html'
    def get_success_url(self):
        initiative_id = self.kwargs.get('initiative_id')
        return reverse('kpi_detail', kwargs={'initiative_id': initiative_id, 'pk': self.object.pk})



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
#LoginRequiredMixin,
class AllDepartmentsView(ListView): 
    model = Department 
    template_name = 'departments_list.html'
    context_object_name = 'departments'

    def get_queryset(self):
        return Department.objects.all()
    

# ---------------------------
#  StrategicPlan View
# ---------------------------
#LoginRequiredMixin, ListView
class AllPlansView(ListView): 
    model = StrategicPlan 
    template_name = 'plans_list.html'
    context_object_name = 'plans'

    def get_queryset(self):
        if self.request.user.role:
            if self.request.user.role.role_name in ['GM', 'CM', 'M']:
                return StrategicPlan.objects.all()
            else:
                raise PermissionDenied 

#LoginRequiredMixin, DetailView 
class PlanDetailsview(DetailView):
    model = StrategicPlan 
    template_name = 'plan_detail.html'
    context_object_name = 'plan'

    def get_queryset(self):
        if self.request.user.role:
            if self.request.user.role.role_name in ['GM', 'CM', 'M']:
                return StrategicPlan.objects.all()
            else:
                raise PermissionDenied
          
#LoginRequiredMixin, UserPassesTestMixin, CreateView            
class CreatePlanView(CreateView):
    model = StrategicPlan
    fields = ['plan_name', 'vision', 'mission', 'start_date', 'end_date']
    template_name = 'plan_form.html'
    success_url = reverse_lazy('')
    
    def test_func(self):
        return self.request.user.role.role_name == 'CM'  #مدير لجنة الخطط

    def form_valid(self, form):
        form.instance.user = self.request.user 
        return super().form_valid(form) 

#LoginRequiredMixin, UserPassesTestMixin, CreateView   
class UpdatePlanView(UpdateView):
    model = StrategicPlan
    fields = ['plan_name', 'vision', 'mission', 'start_date', 'end_date']
    template_name = 'plan_form.html'
    success_url = reverse_lazy('')
    
    def test_func(self):
        return self.request.user.role.role_name == 'CM' 

class DeletePlanView(DeleteView):
    model = StrategicPlan
    template_name = 'plan_confirm_delete.html'
    success_url = reverse_lazy('')

    def test_func(self):
        return self.request.user.role.role_name == 'CM' 

# ---------------------------
#  StrategicGoal View
# ---------------------------
#LoginRequiredMixin, ListView
class AllGoalsView(ListView): 
    model = StrategicGoal 
    template_name = 'goals_list.html'
    context_object_name = 'goals'
        
    def get_queryset(self):
     user = self.request.user
     role = user.role.role_name

     if role == 'GM':
        return StrategicGoal.objects.all()
     elif role in ['M','CM']:
        return StrategicGoal.objects.filter(department = user.department)
     elif role == 'E':
        return StrategicGoal.objects.filter(initiative__userinitiative__user = user).distinct()
     
     return StrategicGoal.objects.none()

        
#LoginRequiredMixin, DetailView 
class GoalDetailsview(DetailView):
    model = StrategicGoal 
    template_name = 'goal_detail.html'
    context_object_name = 'goal'     
        
#LoginRequiredMixin, UserPassesTestMixin, CreateView            
class CreateGoalView(CreateView):
    model = StrategicGoal
    fields = ['goal_title', 'description', 'start_date', 'end_date', 'goal_status', 'goal_priority']
    template_name = 'goal_form.html'
    success_url = reverse_lazy('')
    
    def test_func(self):
        return self.request.user.role.role_name in ['CM','M'] 

    def form_valid(self, form):
       form.instance.plan_id = self.kwargs['plan_id']   # ربط بالخطة
       form.instance.department = self.request.user.department  # ربط بالإدارة
       return super().form_valid(form) 

   
#LoginRequiredMixin, UserPassesTestMixin, CreateView   
class UpdateGoalView(UpdateView):
    model = StrategicGoal
    fields = ['goal_title', 'description', 'start_date', 'end_date', 'goal_status', 'goal_priority']
    template_name = 'goal_form.html'
    success_url = reverse_lazy('')

    def get_queryset(self):
        user = self.request.user
        role = user.role.role_name

        if role in ['M', 'CM']:
            return StrategicGoal.objects.filter(department=user.department)
        return StrategicGoal.objects.none()

    def dispatch(self, request, *args, **kwargs):
        if not self.get_queryset().filter(pk=self.kwargs['pk']).exists():
            raise PermissionDenied("ليس لديك صلاحية تعديل هذا الهدف.")
        return super().dispatch(request, *args, **kwargs)
     
    

class DeleteGoalView(DeleteView):
    model = StrategicGoal
    template_name = 'goal_confirm_delete.html'
    success_url = reverse_lazy('')

    def get_queryset(self):
        user = self.request.user
        role = user.role.role_name

        if role in ['M', 'CM']:
            return StrategicGoal.objects.filter(department=user.department)
        return StrategicGoal.objects.none()

    def dispatch(self, request, *args, **kwargs):
        if not self.get_queryset().filter(pk=self.kwargs['pk']).exists():
            raise PermissionDenied("ليس لديك صلاحية حذف هذا الهدف.")
        return super().dispatch(request, *args, **kwargs)
    
# ---------------------------
#  Note View
# ---------------------------
#LoginRequiredMixin, ListView
class AllNotesView(ListView): 
    model = Note 
    template_name = 'notes_list.html'
    context_object_name = 'notes'
        
    def get_queryset(self):
        user = self.request.user
        role = user.role.role_name

        if role == 'GM':
            #كل الملاحظات اللي ارسلها
            return Note.objects.filter(user=user)
        elif role in ['M','CM']:
            #كل الملاحظات اللي ارسلها واللي اسلتمها من المدير العام
            return Note.objects.filter(user=user,department=user.department)
        elif role == 'E':
            #كل الملاحظات اللي ارسلها واللي استلمهاعلى نفس المبادرة أو ارسلها له المدير 
            return Note.objects.filter(user=user,initiative__userinitiative__user=user,department=user.department).distinct()

        return Note.objects.none()
        
#LoginRequiredMixin, DetailView 
class NoteDetailsview(DetailView):
    model = Note 
    template_name = 'note_detail.html'
    context_object_name = 'note'

    """اعتقد مالها داعي يمكن احذفها
    def get_queryset(self):
      
        user = self.request.user
        return Note.objects.filter(sender=user, receiver=user, initiative__userinitiative__user=user).distinct()

            def dispatch(self, request, *args, **kwargs):
        if not self.get_queryset().filter(pk=self.kwargs['pk']).exists():
            raise PermissionDenied("ليس لديك صلاحية عرض هذه الملاحظة.")
        return super().dispatch(request, *args, **kwargs)
     """

        
#LoginRequiredMixin, UserPassesTestMixin, CreateView            
class CreateNoteView(CreateView):
    model = Note
    fields = ['content', 'initiative', 'department', 'receiver']
    template_name = 'note_form.html'
    success_url = reverse_lazy('')
    
    #هذا عشان يسجل اسم المستلم من dropdown مخصصة
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

   
#LoginRequiredMixin, UserPassesTestMixin, CreateView   
class UpdateNoteView(UpdateView):
    model = Note
    fields = ['content', 'initiative', 'department', 'receiver']
    template_name = 'note_form.html'
    success_url = reverse_lazy('')

    def get_queryset(self):
        return Note.objects.filter(sender=self.request.user)
    
    def dispatch(self, request, *args, **kwargs):
        if not self.get_queryset().filter(pk=self.kwargs['pk']).exists():
            raise PermissionDenied("ليس لديك صلاحية تعديل هذه الملاحظة.")
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        form.instance.sender = self.request.user
        return super().form_valid(form)
    

class DeleteNoteView(DeleteView):
    model = Note
    template_name = 'note_confirm_delete.html'
    success_url = reverse_lazy('')

    def get_queryset(self):
        return Note.objects.filter(sender=self.request.user)

    def dispatch(self, request, *args, **kwargs):
        if not self.get_queryset().filter(pk=self.kwargs['pk']).exists():
            raise PermissionDenied("ليس لديك صلاحية حذف هذه الملاحظة.")
        return super().dispatch(request, *args, **kwargs)

# ---------------------------
#  Log View
# ---------------------------
#LoginRequiredMixin,
class AllLogsView(ListView): 
    model = Log 
    template_name = 'logs_list.html'
    context_object_name = 'logs'
#نحط شرط لللادمن ممكن
    def get_queryset(self):
        return Log.objects.all()
    

    #الداش بورد والتفاصيل هذي اتوقع لازم لها فيو
    #برضو التوجية
    #وانه البيانات تبان فصفحات ثانية للباقين