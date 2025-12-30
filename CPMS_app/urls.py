from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView
from .views import (
    AllPlansView, PlanDetailsview, CreatePlanView, UpdatePlanView, DeletePlanView, 
    AllGoalsView, GoalDetailsview, CreateGoalView, UpdateGoalView, DeleteGoalView, 
    AllInitiativeView, InitiativeDetailsView, CreateInitiativeView, UpdateInitiativeView,
    DeleteInitiativeView, AllKPIsView, KPIDetailsView, create_kpi_view, UpdateKPIView,
    DeleteKPIView, AllDepartmentsView, AllNotesView, NoteDetailsview, CreateNoteView,
    UpdateNoteView, DeleteNoteView,  AllLogsView,
    assign_employee_to_initiative
)


urlpatterns = [

    path('access-denied/', TemplateView.as_view(template_name='access_denied.html'), name='access_denied'),

    #Departments
    path('departments/',AllDepartmentsView.as_view(), name='departments_list'), 

    # Plans
    path('plans/', AllPlansView.as_view(), name='plans_list'),
    path('plans/<int:pk>/detail/', PlanDetailsview.as_view(), name='plan_detail'),
    path('plans/create/', CreatePlanView.as_view(), name='plan_create'),
    path('plans/<int:pk>/update/', UpdatePlanView.as_view(), name='plan_update'),
    path('plans/<int:pk>/delete/', DeletePlanView.as_view(), name='plan_delete'),
    
    # Goals
    path('goals/', AllGoalsView.as_view(), name='goals_list'),
    path('goals/<int:pk>/detail/', GoalDetailsview.as_view(), name='goal_detail'),
    path('plans/<int:plan_id>/goals/add/',CreateGoalView.as_view(), name='goal_create'),
    path('goals/<int:pk>/update/', UpdateGoalView.as_view(), name='goal_update'),
    path('goals/<int:pk>/delete/', DeleteGoalView.as_view(), name='goal_delete'),

    # Goals under a specific plan
    path('plans/<int:plan_id>/goals/',AllGoalsView.as_view(), name='plan_goals_list'),
    path('plans/<int:plan_id>/goals/<int:pk>/',GoalDetailsview.as_view(), name='plan_goal_detail'),
    path('plans/<int:plan_id>/goals/<int:pk>/update/',UpdateGoalView.as_view(), name='plan_goal_update'),
    path('plans/<int:plan_id>/goals/<int:pk>/delete/',DeleteGoalView.as_view(), name='plan_goal_delete'),

    #Notes
    path('notes/', AllNotesView.as_view(), name='notes_list'),
    path('notes/<int:pk>/detail/', NoteDetailsview.as_view(), name='note_detail'),
    path('notes/create/', CreateNoteView.as_view(), name='note_create'),
    path('notes/<int:pk>/update/', UpdateNoteView.as_view(), name='note_update'),
    path('notes/<int:pk>/delete/', DeleteNoteView.as_view(), name='note_delete'),

    #Initiatives
    path('initiatives/',AllInitiativeView.as_view(), name='initiatives_list'),          
    path('initiatives/<int:pk>/',InitiativeDetailsView.as_view(), name='initiative_detail'),
    path('goals/<int:goal_id>/initiatives/add/',CreateInitiativeView.as_view(), name='initiative_create'),
    path('initiatives/<int:pk>/update/',UpdateInitiativeView.as_view(), name='initiative_update'),
    path('initiatives/<int:pk>/delete/',DeleteInitiativeView.as_view(), name='initiative_delete'),
    path('initiatives/<int:pk>/assign/',assign_employee_to_initiative, name = 'initiative_assign'),
    
    # Initiatives under a specific goal
    path('goals/<int:goal_id>/initiatives/',AllInitiativeView.as_view(), name='goal_initiatives_list'),
    path('goals/<int:goal_id>/initiatives/<int:pk>/',InitiativeDetailsView.as_view(), name='goal_initiative_detail'),
    path('goals/<int:goal_id>/initiatives/<int:pk>/update/',UpdateInitiativeView.as_view(), name='goal_initiative_update'),
    path('goals/<int:goal_id>/initiatives/<int:pk>/delete/',DeleteInitiativeView.as_view(), name='goal_initiative_delete'),
    path('goals/<int:goal_id>/initiatives/<int:pk>/assign/',assign_employee_to_initiative, name = 'goal_initiative_assign'),

    #KPIs under a specific initiative
    path('initiatives/<int:initiative_id>/kpis/',AllKPIsView.as_view(), name='kpis_list'),
    path('initiatives/<int:initiative_id>/kpis/<int:pk>/',KPIDetailsView.as_view(), name='kpi_detail'),
    path('initiatives/<int:initiative_id>/kpis/add/',create_kpi_view, name='kpi_create'),
    path('initiatives/<int:initiative_id>/kpis/<int:pk>/update/',UpdateKPIView.as_view(), name='kpi_update'),
    path('initiatives/<int:initiative_id>/kpis/<int:pk>/delete/',DeleteKPIView.as_view(), name='kpi_delete'),
    
    #Logs
    path('logs/',AllLogsView.as_view(), name='logs_list'),  

]

