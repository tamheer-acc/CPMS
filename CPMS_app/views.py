from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView
from django.views.generic.edit import UpdateView, DeleteView
from .models import ( Role, Department, User, StrategicPlan, StrategicGoal, 
                    Initiative, UserInitiative, KPI, Note, Log)
from django.contrib.auth.forms import UserCreationForm, UserChangeForm#!!
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin #class based view 
from django.contrib.auth.decorators import login_required #function based view
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from django.forms import ModelForm
from .models import STATUS


# Custom User Handling:  
#User = get_user_model()
# class CustomUserCreationForm(UserCreationForm):
#     class Meta(UserCreationForm.Meta):
#         model = User
#         fields = ('username', 'email', 'employee_number', 'role', 'department')

# class CustomUserChangeForm(UserChangeForm):
#     class Meta(UserChangeForm.Meta):
#         model = User
#         fields = ('username', 'email', 'employee_number', 'role', 'department')



########################################################################
#                           Initiative Views                           #
########################################################################

class AllInitiativeView(ListView): 
    '''
    List all initiatives
    - General Manager sees all initiatives
    - Other users see only initiatives they are assigned to
    '''
    #ListView: query all of the objects in our view? from our database
    model = Initiative 
    template_name = 'initiatives_list.html'
    context_object_name = 'initiatives'
    
    def get_queryset(self):
        if self.request.user.role:
            if self.request.user.role.role_name == 'GM':
                return Initiative.objects.all()
            else:
                return Initiative.objects.filter( userinitiative__user = self.request.user )



class InitiativeDetailsView(DetailView):
    '''
    - Shows details of a single initiative
    '''
    model = Initiative
    template_name = "initiative_detail.html"
    context_object_name = "initiative"
    #retreave the users related in the template 



class CreateInitiativeView(CreateView): #Managers 
    '''
    - Allows Managers to create a new initiative
    - Sets the strategic goal based on the goal_id in the URL
    - Automatically assigns the current user to the initiative via UserInitiative
    '''
    model = Initiative
    fields = ['title', 'description', 'start_date', 'end_date', 'priority', 'category']
    template_name = 'initiative_form.html'
    success_url = reverse_lazy('PATH@')

    def form_valid(self, form): #overriding form valid to set strategic goal and employee
        form.instance.strategic_goal_id = self.kwargs['goal_id']#kwargs = from the URL@
        response = super().form_valid(form)
        UserInitiative.objects.create(
            user=self.request.user,
            initiative=self.object,
            status = STATUS[0][0],
            progress = 0
        )
        
        return response



class UpdateInitiativeView(UpdateView):
    '''
    - Allows updating an existing initiative
    - Only the initiative fields are editable (title, description, dates, priority, category)
    - The strategic goal and assigned users remain unchanged
    '''
    model = Initiative
    fields = ['title', 'description', 'start_date', 'end_date', 'priority', 'category']
    template_name = 'initiative_form.html'
    success_url = reverse_lazy('PATH@')



class DeleteInitiativeView(DeleteView):
    '''
    - Allows deletion of an initiative
    - All related UserInitiative entries are automatically deleted (on_delete=CASCADE)
    - After deletion redirects to PATH@
    '''
    model = Initiative
    template_name = 'initiative_confirm_delete.html'
    success_url = reverse_lazy('PATH@')




