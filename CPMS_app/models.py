from django import apps
from django.db import models
from django.contrib.auth.models import AbstractUser
from datetime import date
from django.utils import timezone


ROLES = (
    ('GM', 'المدير العام'), #General Manager
    ('CM','مدير لجنة الخطط'), #Committee Manager
    ('M', 'مدير'), #Manager
    ('E', 'موظف') #Employee
)



STATUS = (
    ('NS', 'لم يبدأ بعد'),
    ('IP', 'قيد التنفيذ'),
    ('D', 'متأخر'),
    ('C', 'مكتمل'),
)


PRIORITY = (
    ('C', 'حرجة'),
    ('H', 'عالية'),
    ('M', 'متوسطة'),
    ('L', 'منخفضة'),
)

READ = 'R'
UNREAD = 'U'

NOTE_STATUS = (
    (READ, 'مقروءة'),
    (UNREAD, 'غير مقروءة')
)



# ---------------------------
#  Role Model
# ---------------------------
class Role(models.Model): # 1 : M Relationship with User (One Side)
    role_name = models.CharField(max_length=2, choices=ROLES, default=ROLES[0][0])
    def __str__(self):
        return self.get_role_name_display()



# ---------------------------
#  Departments Model
# ---------------------------
class Department (models.Model): 
    department_name = models.CharField(max_length=100, unique=True)  
    
    class Meta:
        verbose_name = "Department"
        verbose_name_plural = "Departments"

    def __str__(self):
        return self.department_name



# ---------------------------
#  User Model
# ---------------------------
class User(AbstractUser):
    # employee_number = models.DecimalField(max_digits=10,decimal_places=0)
    # role = models.ForeignKey(Role, on_delete=models.PROTECT)
    employee_number = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    role = models.ForeignKey(Role, on_delete=models.PROTECT, null=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"



# ---------------------------
#  StrategicPlan Model
# ---------------------------
class StrategicPlan (models.Model):
    plan_name = models.CharField(max_length=200,unique=True, null=False, blank=False, help_text="اسم الخطة الاستراتيجية")
    vision = models.TextField(null=False, blank=False, help_text="الرؤية")
    mission = models.TextField(null=False, blank=False, help_text="الرسالة")
    start_date = models.DateField(null=True, blank=True, default=date.today, help_text="تاريخ بداية الخطة")
    end_date = models.DateField(null=True, blank=True, help_text="تاريخ نهاية الخطة")
    created_by = models.CharField(max_length=200, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "StrategicPlan"
        verbose_name_plural = "StrategicPlans"
        ordering = ['-start_date'] 


    def __str__(self):
        return self.plan_name


# ---------------------------
#  StrategicGoal Model
# ---------------------------
class StrategicGoal (models.Model):
    strategicplan= models.ForeignKey(StrategicPlan, on_delete=models.CASCADE, related_name="goals")
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="goals")
    goal_title = models.CharField(max_length=200, null=False, blank=False, help_text="عنوان الهدف الاستراتيجي")
    description = models.TextField(null=False, blank=False, help_text="وصف الهدف الاستراتيجي")
    start_date = models.DateField(null=True, blank=True, default=date.today, help_text="تاريخ بداية الهدف")
    end_date = models.DateField(null=True, blank=True, help_text="تاريخ نهاية الهدف")
    goal_status = models.CharField(max_length=2, choices=STATUS, default=STATUS[0][0], help_text="حالة الهدف")
    goal_priority = models.CharField(max_length=1, choices=PRIORITY, default=PRIORITY[0][0], help_text="أهمية الهدف")
    
    class Meta:
        verbose_name = "StrategicGoal"
        verbose_name_plural = "StrategicGoals"
        ordering = ['-start_date']  

    def __str__(self):
        return f"{self.goal_title} ({self.department.department_name})"



# ---------------------------
#  Initiative Model
# ---------------------------
class Initiative(models.Model):  # 1 : M Relationship with StrategicGoal (Many Side)
    title = models.CharField(max_length=200)
    description = models.TextField()
    start_date = models.DateField()
    end_date = models.DateField()
    priority = models.CharField( max_length = 1, choices = PRIORITY, default= PRIORITY[3][0])
    # initiative_status = models.CharField(max_length=2, choices=STATUS, default=STATUS[0][0])
    category = models.CharField(max_length=50)
    strategic_goal = models.ForeignKey(StrategicGoal, on_delete=models.CASCADE )
    
    class Meta:
        verbose_name = "Initiative"
        verbose_name_plural = "Initiatives"

    def __str__(self):
        return self.title



# ---------------------------
#  UserInitiative Model
# ---------------------------
class UserInitiative(models.Model): # M : M relationshp  
    status = models.CharField(max_length=2, choices=STATUS)
    progress = models.DecimalField(max_digits=10, decimal_places=0)
    initiative = models.ForeignKey(Initiative, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    def __str__(self):
        return f'{ self.user.username } - { self.initiative.title } ({ self.status })'



# ---------------------------
#  KPI Model
# ---------------------------
class KPI(models.Model): # 1 : M relationshp with Initiative (Many Side) 
    kpi = models.CharField(max_length=255)
    unit = models.CharField(max_length=20)
    target_value = models.DecimalField(max_digits=18, decimal_places=2)
    actual_value = models.DecimalField(max_digits=18, decimal_places=2,null=True, blank=True)
    start_value = models.DecimalField(max_digits=18, decimal_places=2,null=True, blank=True)
    initiative = models.ForeignKey(Initiative, on_delete=models.CASCADE)
    def __str__(self):
        return self.kpi



# ---------------------------
#  Note Model
# ---------------------------
class Note (models.Model):
    title = models.CharField(max_length=255, null=True, blank=True)
    content = models.TextField(null=False, blank=False, help_text="محتوى الملاحظة")
    sender = models.ForeignKey(User, on_delete=models.CASCADE,  related_name="sent_notes")
    receiver = models.ForeignKey(User, null=True, on_delete=models.CASCADE,  related_name="received_notes")
    initiative = models.ForeignKey(Initiative, null=True, blank=True, on_delete=models.CASCADE, related_name="notes")
    strategic_goal = models.ForeignKey(StrategicGoal, null=True, blank=True, on_delete=models.CASCADE, related_name="notes")
    parent_note = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')
    created_at =  models.DateTimeField(auto_now_add=True, null=True)
    read_by = models.ManyToManyField(User, related_name='read_notes', null=True, blank=True)
    is_starred = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at'] 

    class Meta:
        verbose_name = "Note"
        verbose_name_plural = "Notes" 

    def __str__(self):
        return  f"Note #{self.id}"


# ---------------------------
#  Log Model
# ---------------------------
class Log (models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="logs")
    table_name = models.CharField(max_length=50, null=True)
    record_id = models.CharField(null=True)
    action = models.CharField(max_length=100, null=False)
    old_value = models.TextField(null=True)
    new_value = models.TextField(null=True)
    created_at =  models.DateTimeField(auto_now_add=True)    

    class Meta:
        verbose_name = "Log"
        verbose_name_plural = "Logs"

    def __str__(self):
        return f"{self.table_name} - {self.action}"
    
    def get_instance(self):
        if not self.table_name or not self.record_id:
            return None
        try:
            model = apps.get_model('CPMS_app', self.table_name)
            return model.objects.filter(pk=self.record_id).first()
        except Exception:
            return None

    @property
    def formatted_details(self):
        from .services import format_log_values
        instance = self.get_instance()
        return format_log_values(self.old_value, self.new_value, self.action, instance)

# ---------------------------
#     ProgressLog Model
# ---------------------------
class ProgressLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    initiative = models.ForeignKey(Initiative, on_delete=models.CASCADE)
    department = models.ForeignKey(Department,null=True, on_delete=models.SET_NULL)
    progress = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name = "Progress Log"
        verbose_name_plural = "Progress Logs"

    def __str__(self):
        return f"{self.initiative.title} - {self.progress} - {self.timestamp}"
