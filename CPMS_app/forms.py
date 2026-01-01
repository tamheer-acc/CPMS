from django import forms
from django.forms import ModelForm
from .models import KPI, StrategicPlan, StrategicGoal

#we are using this insted of creating another view BECAUSE we want it 
#to be viewd INSID the page, alongside everything else in that page
class KPIForm(ModelForm):
    class Meta():
        model = KPI
        fields = ['kpi', 'unit', 'target_value','actual_value']

# Base form with shared clean and save logic
class BaseForm(forms.ModelForm):
    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')
        if start and end and end <= start:
            raise forms.ValidationError("تاريخ النهاية يجب أن يكون بعد تاريخ البداية")
        return cleaned_data

    def save(self, user=None, plan_id=None, commit=True):
        obj = super().save(commit=False)

        if user and hasattr(obj, 'created_by'):
            obj.created_by = getattr(user, 'get_full_name', lambda: None)()

        if user and hasattr(obj, 'department'):
            obj.department = getattr(user, 'department', None)

        if plan_id and hasattr(obj, 'plan_id'):
            obj.plan_id = plan_id

        if commit:
            obj.save()
        return obj

# ===== Strategic Plan Form =====
class StrategicPlanForm(BaseForm):
    class Meta:
        model = StrategicPlan
        fields = ['plan_name', 'vision', 'mission', 'start_date', 'end_date']
        labels = {
            'plan_name': 'اسم الخطة',
            'vision': 'الرؤية',
            'mission': 'الرسالة',
            'start_date': 'تاريخ بداية الخطة',
            'end_date': 'تاريخ نهاية الخطة',
        }
        widgets = {
            'plan_name': forms.TextInput(attrs={'class': 'input'}),
            'vision': forms.Textarea(attrs={'rows': 1, 'class': 'textarea'}),
            'mission': forms.Textarea(attrs={'rows': 1, 'class': 'textarea'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'input'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'input'}),
        }

# ===== Strategic Goal Form =====
class StrategicGoalForm(BaseForm):
    class Meta:
        model = StrategicGoal
        fields = ['goal_title', 'description', 'start_date', 'end_date', 'goal_status', 'goal_priority']
        labels = {
            'goal_title': 'عنوان الهدف',
            'description': 'وصف الهدف',
            'start_date': 'تاريخ بداية الهدف',
            'end_date': 'تاريخ نهاية الهدف',
            'goal_status': 'حالة الهدف',
            'goal_priority': 'أهمية الهدف',
        }
        widgets = {
            'goal_title': forms.TextInput(attrs={'class': 'input'}),
            'description': forms.Textarea(attrs={'rows': 1, 'class': 'textarea'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'input'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'input'}),
            'goal_status': forms.Select(attrs={'class': 'select'}),
            'goal_priority': forms.Select(attrs={'class': 'select'}),
        }
