from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (AllInitiativeView, InitiativeDetailsView, CreateInitiativeView, UpdateInitiativeView, DeleteInitiativeView,
                    AllKPIsView, KPIDetailsView, create_kpi_view , UpdateKPIView,  DeleteKPIView, 
                    AllDepartmentsView, 
                    AllPlansView, PlanDetailsview, CreatePlanView,UpdatePlanView, DeletePlanView,
                    CreateGoalView, UpdateGoalView, DeleteGoalView,
                    AllLogsView)

urlpatterns = [
    path('departmets',AllDepartmentsView.as_view(), name='departments_list'),
    path('plans', AllPlansView.as_view(), name='plans_list'),
    path('plans/<int:pk>/detail', PlanDetailsview.as_view(), name='plan_detail'),
    path('plans/create', CreatePlanView.as_view(), name='create_plan'),
    path('plans/<int:pk>/update', UpdatePlanView.as_view(), name='update_plan'),
    path('plans/<int:pk>/delete', DeletePlanView.as_view(), name='delete_plan'),
    # path('goals', AllGoalsView.as_view(), name='goals_list'),
    # path('goals/<int:pk>/detail', GoalDetailsview.as_view(), name='goal_detail'),
    path('goals/add', CreateGoalView.as_view(), name='add_goal'),
    path('goals/<int:pk>/update', UpdateGoalView.as_view(), name='update_goal'),
    path('goals/<int:pk>/delete', DeleteGoalView.as_view(), name='delete_goal'),

]
