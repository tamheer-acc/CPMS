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


from django.contrib import admin
from django.urls import path, include
from CPMS_app.views import (AllDepartmentsView, AllPlansView,PlanDetailsview,CreatePlanView,
                            UpdatePlanView, DeletePlanView,
                            CreateGoalView, UpdateGoalView,DeleteGoalView)
# AllGoalsView, GoalDetailsview,        
urlpatterns = [
    path('admin/', admin.site.urls),
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