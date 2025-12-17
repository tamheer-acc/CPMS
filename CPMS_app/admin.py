from django.contrib import admin
from .models import ( Role, Department, User, StrategicPlan, StrategicGoal, 
                    Initiative, UserInitiative, KPI, Note, Log)

from django.contrib.auth.admin import UserAdmin

# Register your models here.
admin.site.register(Role)
admin.site.register(Department)
admin.site.register(User, UserAdmin)
admin.site.register(StrategicPlan)
admin.site.register(StrategicGoal)
admin.site.register(Initiative)
admin.site.register(UserInitiative)
admin.site.register(KPI)
admin.site.register(Note)
admin.site.register(Log)