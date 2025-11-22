# stock/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User  # Импортируем стандартного User
from django.utils import timezone
from .models import UserProfile, Product, StockMovement, CampaignDailyStats, AdvertisingCampaign, GoalNote, CampaignGoal


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'class': 'form-control',
        'placeholder': 'Email'
    }))
    
    class Meta:
        model = User  # Используем стандартного User
        fields = ('username', 'email', 'password1', 'password2')
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control',
                'placeholder': self.fields[field].label
            })


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ('company_name', 'contact_email', 'avatar', 'notification_enabled')  # Добавляем avatar
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control'}),
            'notification_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'company_name': 'Название компании',
            'contact_email': 'Контактный email', 
            'avatar': 'Аватар профиля',
            'notification_enabled': 'Уведомления включены'
        }


class APITokenForm(forms.Form):
    wb_api_token = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите ваш API токен Wildberries',
            'autocomplete': 'new-password'
        }),
        label="API токен Wildberries",
        required=False,
        help_text="Токен будет зашифрован и безопасно сохранен"
    )

    def save(self, user_profile):
        token = self.cleaned_data.get('wb_api_token')
        if token:  # Сохраняем только если передан новый токен
            user_profile.set_api_token(token)
        # Если поле пустое - не делаем ничего (не стираем существующий токен)

class ProductForm(forms.ModelForm):
    """Форма для добавления/редактирования товара"""
    class Meta:
        model = Product
        fields = ['name', 'article', 'initial_quantity', 'image', 'purchase_date']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название товара'
            }),
            'article': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Артикул WB'
            }),
            'initial_quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Начальное количество'
            }),
            'purchase_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control'
            })
        }
        labels = {
            'name': 'Название товара',
            'article': 'Артикул WB',
            'initial_quantity': 'Начальное количество',
            'image': 'Фото товара',
            'purchase_date': 'Дата закупки'
        }


class StockMovementForm(forms.ModelForm):
    """Форма для добавления движения товара"""
    class Meta:
        model = StockMovement
        fields = ['movement_type', 'quantity', 'date', 'notes']
        widgets = {
            'movement_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Количество'
            }),
            'date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Примечания (необязательно)',
                'rows': 3
            })
        }
        labels = {
            'movement_type': 'Тип операции',
            'quantity': 'Количество',
            'date': 'Дата операции',
            'notes': 'Примечания'
        }


class AdvertisingCampaignForm(forms.ModelForm):
    """Форма создания/редактирования рекламной кампании"""
    products = forms.ModelMultipleChoiceField(
        queryset=Product.objects.none(),
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
        required=True,
        label="Товары"
    )
    
    class Meta:
        model = AdvertisingCampaign
        fields = ['name', 'campaign_type', 'products', 'start_date', 'end_date', 'status']  # Убрали daily_budget и bid
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите название кампании'}),
            'campaign_type': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'name': 'Название кампании',
            'campaign_type': 'Тип кампании',
            'start_date': 'Дата начала',
            'end_date': 'Дата окончания',
            'status': 'Статус',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user:
            # Показываем только товары текущего пользователя
            self.fields['products'].queryset = Product.objects.filter(user=self.user)
            
            # Устанавливаем начальную дату по умолчанию
            if not self.instance.pk:
                self.fields['start_date'].initial = timezone.now().date()


class CampaignDailyStatsForm(forms.ModelForm):
    """Форма для ввода ежедневной статистики"""
    class Meta:
        model = CampaignDailyStats
        fields = ['date', 'views', 'clicks', 'cart_adds', 'orders', 'spent']  # Добавили cart_adds
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'views': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
            'clicks': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
            'cart_adds': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
            'orders': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
            'spent': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
        }
        labels = {
            'date': 'Дата',
            'views': 'Показы',
            'clicks': 'Клики',
            'cart_adds': 'Добавления в корзину',
            'orders': 'Заказы',
            'spent': 'Затраты (руб)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['date'].initial = timezone.now().date()


class CampaignGoalForm(forms.ModelForm):
    """Форма для создания/редактирования целей"""
    class Meta:
        model = CampaignGoal
        fields = ['title', 'goal_type', 'description', 'target_value', 'current_value', 'deadline', 'campaigns']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название цели'}),
            'goal_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Подробное описание цели...'}),
            'target_value': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Целевое значение'}),
            'current_value': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Текущее значение'}),
            'deadline': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'campaigns': forms.CheckboxSelectMultiple(attrs={
                'class': 'form-check-input'
            }),
        }
        labels = {
            'title': 'Название цели',
            'goal_type': 'Тип цели',
            'description': 'Описание цели',
            'target_value': 'Целевое значение',
            'current_value': 'Текущее значение',
            'deadline': 'Дедлайн',
            'campaigns': 'Связанные кампании',
        }


class GoalNoteForm(forms.ModelForm):
    """Форма для заметок к целям"""
    class Meta:
        model = GoalNote
        fields = ['title', 'content']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Заголовок заметки'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 8, 'placeholder': 'Подробное содержание заметки...'}),
        }
        labels = {
            'title': 'Заголовок',
            'content': 'Содержание',
        }
