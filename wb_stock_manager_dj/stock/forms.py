# stock/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User  # Импортируем стандартного User
from .models import UserProfile, Product, StockMovement

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
    """Отдельная форма для API токена"""
    wb_api_token = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите ваш API токен Wildberries'
        }),
        required=False,
        label='API Токен Wildberries',
        max_length=500
    )
    
    def save(self, profile):
        """Сохраняем токен в профиль"""
        token = self.cleaned_data.get('wb_api_token')
        if token:
            profile.set_api_token(token)
            profile.save()
        return profile

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
