from django import forms
from django.forms import ModelForm
from .models import Initiative, KPI, StrategicPlan, StrategicGoal

# ============== Base Form =================
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
            obj.created_by = user.get_full_name()

        if user:
           obj.department = user.department

        if plan_id and hasattr(obj, 'strategicplan_id'):
            obj.strategicplan_id = plan_id

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
        error_messages = {
            'plan_name': {
                'required': 'يرجى إدخال اسم الخطة',
                'max_length': 'اسم الخطة طويل جدًا',
                'unique': 'اسم الخطة موجود مسبقًا، الرجاء اختيار اسم آخر'
            },
            'vision': {
                'required': 'يرجى إدخال الرؤية',
            },
            'mission': {
                'required': 'يرجى إدخال الرسالة',
            },
            'start_date': {
                'required': 'يرجى تحديد تاريخ البداية',
            },
            'end_date': {
                'required': 'يرجى تحديد تاريخ النهاية',
            }
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
        error_messages = {
            'goal_title': {
                'required': 'يرجى إدخال عنوان الهدف',
                'max_length': 'اسم الهدف طويل جدًا',
            },
            'description': {
                'required': 'يرجى إدخال وصف الهدف',
                'max_length': 'الوصف طويل جداً، الرجاء اختصاره'
            },
            'start_date': {
                'required': 'يرجى تحديد تاريخ البداية',
            },
            'end_date': {
                'required': 'يرجى تحديد تاريخ النهاية',
            },
            'goal_status': {
                'required': 'يرجى تحديد حالة الهدف',
            },
            'goal_priority': {
                'required': 'يرجى تحديد أهمية الهدف',
            },
        }

        widgets = {
            'goal_title': forms.TextInput(attrs={'class': 'input'}),
            'description': forms.Textarea(attrs={'rows': 1, 'class': 'textarea'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'input'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'input'}),
            'goal_status': forms.Select(attrs={'class':'rounded-xl border px-12 py-2 text-sm text-gray-900 bg-gray-50 hover:border-gray-400 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-blue-500'}),
            'goal_priority': forms.Select(attrs={'class':'rounded-xl border px-12 py-2 text-sm text-gray-900 bg-gray-50 hover:border-gray-400 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-blue-500'}),
        }


# ===== KPI Form =====
class KPIForm(BaseForm):
    class Meta:
        model = KPI
        fields = ['kpi', 'unit', 'target_value', 'actual_value']

        error_messages = {
            'kpi': {
                'required': 'يرجى إدخال اسم مؤشر الأداء',
                'max_length': 'اسم المؤشر طويل جداً'
            },
            'unit': {
                'required': 'يرجى تحديد وحدة القياس',
            },
            'target_value': {
                'required': 'يرجى إدخال القيمة المستهدفة',
                'invalid': 'القيمة المستهدفة غير صحيحة'
            },
            'actual_value': {
                'required': 'يرجى إدخال القيمة الفعلية',
                'invalid': 'القيمة الفعلية غير صحيحة'
            }
        }

        labels = {
            'kpi': 'اسم مؤشر الأداء',
            'unit': 'وحدة القياس',
            'target_value': 'القيمة المستهدفة',
            'actual_value': 'القيمة الحالية',
        }

        widgets = {
            'kpi': forms.TextInput(attrs={
                'placeholder': 'مثال: نسبة إنجاز المشاريع',
                'class': (
                    'block w-full p-2.5 text-sm text-gray-900 '
                    'bg-gray-50 border border-gray-300 rounded-xl shadow-sm '
                    'focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-blue-500 '
                    'hover:border-gray-400 transition-all duration-200'
                )
            }),

            'unit': forms.TextInput(attrs={
                'placeholder': 'مثال: % ، عدد ، أيام',
                'class': (
                    'block w-full p-2.5 text-sm text-gray-900 '
                    'bg-gray-50 border border-gray-300 rounded-xl shadow-sm '
                    'focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-blue-500 '
                    'hover:border-gray-400 transition-all duration-200'
                )
            }),

            'target_value': forms.NumberInput(attrs={
                'class': (
                    'block w-full p-2.5 text-sm text-gray-900 '
                    'bg-gray-50 border border-gray-300 rounded-xl shadow-sm '
                    'focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-blue-500 '
                    'hover:border-gray-400 transition-all duration-200'
                )
            }),

            'actual_value': forms.NumberInput(attrs={
                'class': (
                    'block w-full p-2.5 text-sm text-gray-900 '
                    'bg-gray-50 border border-gray-300 rounded-xl shadow-sm '
                    'focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-blue-500 '
                    'hover:border-gray-400 transition-all duration-200'
                )
            }),
        }



# ===== Initiative Form =====
class InitiativeForm(BaseForm):
    class Meta:
        model = Initiative
        fields = ['title', 'description', 'start_date', 'end_date', 'priority', 'category']
        error_messages = {
            'title': {
                'required': 'يرجى إدخال عنوان المبادرة',
                'max_length': 'العنوان طويل جداً، الرجاء اختصاره'
            },
            'description': {
                'required': 'يرجى إدخال وصف المبادرة',
                'max_length': 'الوصف طويل جداً، الرجاء اختصاره'
            },
            'start_date': {
                'required': 'يرجى تحديد تاريخ البداية',
            },
            'end_date': {
                'required': 'يرجى تحديد تاريخ النهاية',
            },
            'priority': {
                'required': 'يرجى تحديد أهمية المبادرة',
            },
            'category': {
                'required': 'يرجى إدخال فئة المبادرة',
                'max_length': 'اختر اسم أقصر للفئة'
            }
        }

        labels = {
            'title': 'عنوان المبادرة',
            'description': 'وصف المبادرة',
            'start_date': 'تاريخ بداية المبادرة',
            'end_date': 'تاريخ نهاية المبادرة',
            'priority': 'أهمية المبادرة',
            'category': 'فئة المبادرة',
            'strategic_goal': 'الهدف الاستراتيجي',
        }

        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': 'مثال: مبادرة إطلاق مشاريع لتعزيز اللوجستيات',
            'class': (
                'block w-full p-2.5 text-sm text-gray-900 '       
                'bg-gray-50 border border-gray-300 rounded-xl shadow-sm '  
                'focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-blue-500 '  
                'hover:border-gray-400 transition-all duration-200'  
            )            
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'صف المبادرة باختصار',
                'class': 'w-full bg-gray-50 border border-gray-300 rounded-xl p-2.5 focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-blue-500 hover:border-gray-400'
            }),
            'start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full bg-gray-50 border border-gray-300 rounded-xl p-2.5 focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-blue-500 hover:border-gray-400'
            }),
            'end_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full bg-gray-50 border border-gray-300 rounded-xl p-2.5 focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-blue-500 hover:border-gray-400'
            }),
            'priority': forms.Select(attrs={
                'class': 'block w-full bg-gray-50 border border-gray-300 rounded-xl p-2.5 focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-blue-500 hover:border-gray-400'
            }),           

            'category': forms.TextInput(attrs={
                'placeholder': 'مثال: تطوير، إدارة ',
                'class': 'w-full bg-gray-50 border border-gray-300 rounded-xl p-2.5 focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-blue-500 hover:border-gray-400'
            }),
        }