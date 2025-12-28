from django.contrib import admin
from .models import ( Role, Department, User, StrategicPlan, StrategicGoal, 
                    Initiative, UserInitiative, KPI, Note, Log)

from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    
    # for editing a user
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Extra Info', {'fields': ('employee_number', 'role', 'department')}),
    )

    # creating a user via admin
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Extra Info', {'fields': ('employee_number', 'role', 'department')}),
    )

    list_display = ('username', 'email', 'first_name', 'last_name', 'employee_number', 'role', 'department', 'is_staff')
    list_filter = ('role', 'department', 'is_staff')


admin.site.register(Role)
admin.site.register(Department)
# admin.site.register(User, UserAdmin)
admin.site.register(StrategicPlan)
admin.site.register(StrategicGoal)
admin.site.register(Initiative)
admin.site.register(UserInitiative)
admin.site.register(KPI)
admin.site.register(Note)
admin.site.register(Log)