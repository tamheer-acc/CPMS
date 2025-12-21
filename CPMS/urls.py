"""
URL configuration for CPMS project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from CPMS_app.views import (AllDepartmentsView, AllPlansView,PlanDetailsview,CreatePlanView,
                            UpdatePlanView, DeletePlanView, AllGoalsView, GoalDetailsview,
                            CreateGoalView, UpdateGoalView,DeleteGoalView,AllNotesView,
                            NoteDetailsview, CreateNoteView, UpdateNoteView, DeleteNoteView)
   
urlpatterns = [
    path('admin/', admin.site.urls),
    path('departmets',AllDepartmentsView.as_view(), name='departments_list'),
    path('plans', AllPlansView.as_view(), name='plans_list'),
    path('plans/<int:pk>/detail', PlanDetailsview.as_view(), name='plan_detail'),
    path('plans/create', CreatePlanView.as_view(), name='create_plan'),
    path('plans/<int:pk>/update', UpdatePlanView.as_view(), name='update_plan'),
    path('plans/<int:pk>/delete', DeletePlanView.as_view(), name='delete_plan'),
    path('goals', AllGoalsView.as_view(), name='goals_list'),
    path('goals/<int:pk>/detail', GoalDetailsview.as_view(), name='goal_detail'),
    path('goals/add', CreateGoalView.as_view(), name='add_goal'),
    path('goals/<int:pk>/update', UpdateGoalView.as_view(), name='update_goal'),
    path('goals/<int:pk>/delete', DeleteGoalView.as_view(), name='delete_goal'),
    path('notes', AllNotesView.as_view(), name='notes_list'),
    path('notes/<int:pk>/detail', NoteDetailsview.as_view(), name='note_detail'),
    path('notes/create', CreateNoteView.as_view(), name='create_note'),
    path('notes/<int:pk>/update', UpdateNoteView.as_view(), name='update_note'),
    path('notes/<int:pk>/delete', DeleteNoteView.as_view(), name='delete_note'),

]
