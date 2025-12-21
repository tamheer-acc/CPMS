from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from .views import (AllInitiativeView, AllLogsView, InitiativeDetailsView, CreateInitiativeView,
                    UpdateInitiativeView, DeleteInitiativeView, AllKPIsView, KPIDetailsView,
                    create_kpi_view , UpdateKPIView,  DeleteKPIView, AllDepartmentsView,
                    AllDepartmentsView, AllPlansView,PlanDetailsview,CreatePlanView,
                    UpdatePlanView, DeletePlanView, AllGoalsView, GoalDetailsview, 
                    CreateGoalView, UpdateGoalView,DeleteGoalView,AllNotesView,
                    NoteDetailsview, CreateNoteView, UpdateNoteView, DeleteNoteView,
                    PlanDetailsview, CreatePlanView,UpdatePlanView, DeletePlanView,
                    AllLogsView)


#Only this is what supposed to be here, the rest in CPMS_app/url.py
# urlpatterns = [
#     path('admin/', admin.site.urls),
#     path('', include('CPMS_app.urls')),    
#     path('accounts/', include('django.contrib.auth.urls')) #importing all of these down below!
# ]


#all of these are imported!
# accounts/login/ [name='login']
# accounts/logout/ [name='logout']
# accounts/password_change/ [name='password_change']
# accounts/password_change/done/ [name='password_change_done']
# accounts/password_reset/ [name='password_reset']
# accounts/password_reset/done/ [name='password_reset_done']
# accounts/reset/<uidb64>/<token>/ [name='password_reset_confirm']
# accounts/reset/done/ [name='password_reset_complete']

urlpatterns = [
    path('admin/', admin.site.urls),
    path('departmets',AllDepartmentsView.as_view(), name='departments_list'), #departments (typo)
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

    path('initiatives/',AllInitiativeView.as_view(), name='initiatives_list' ),          
    path('initiatives/<int:pk>/',InitiativeDetailsView.as_view(), name='initiative_detail' ),
    path('goals/<int:goal_id>/initiatives/add/',CreateInitiativeView.as_view(), name='initiative_create' ),
    path('initiatives/<int:pk>/update/',UpdateInitiativeView.as_view(), name='initiative_update' ),
    path('initiatives/<int:pk>/delete/',DeleteInitiativeView.as_view(), name='initiative_delete' ),

    path('goals/<int:goal_id>/initiatives/',AllInitiativeView.as_view(), name='goal_initiatives_list' ),
    path('goals/<int:goal_id>/initiatives/<int:pk>/',InitiativeDetailsView.as_view(), name='goal_initiative_detail' ),
    path('goals/<int:goal_id>/initiatives/<int:pk>/update/',UpdateInitiativeView.as_view(), name='goal_initiative_update' ),
    path('goals/<int:goal_id>/initiatives/<int:pk>/delete/',DeleteInitiativeView.as_view(), name='goal_initiative_delete' ),

    path('initiatives/<int:initiative_id>/kpis/',AllKPIsView.as_view(), name='kpis_list' ),
    path('initiatives/<int:initiative_id>/kpis/<int:pk>/',KPIDetailsView.as_view(), name='kpi_detail' ),
    path('initiatives/<int:initiative_id>/kpis/add/',create_kpi_view, name='kpi_create' ),
    path('initiatives/<int:initiative_id>/kpis/<int:pk>/update/',UpdateKPIView.as_view(), name='kpi_update' ),
    path('initiatives/<int:initiative_id>/kpis/<int:pk>/delete/',DeleteKPIView.as_view(), name='kpi_delete' ),


]

