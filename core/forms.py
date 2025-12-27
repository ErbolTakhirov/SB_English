from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import Income, Expense, Event, Document


class IncomeForm(forms.ModelForm):
    amount = forms.FloatField(
        required=True,
        min_value=0.01,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01',
            'min': '0.01'
        }),
        label='Сумма',
        help_text='Обязательное поле'
    )
    date = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label='Дата',
        help_text='Обязательное поле'
    )
    category = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'list': 'income-categories',
            'placeholder': 'Выберите или введите новую категорию',
            'autocomplete': 'off'
        }),
        label='Категория',
        help_text='Выберите из существующих или введите новую'
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Автоматизация, бонус, продажа курса...',
            'style': 'resize: vertical; min-height: 80px;'
        }),
        label='Описание',
        help_text='Необязательное поле'
    )
    
    class Meta:
        model = Income
        fields = ['amount', 'date', 'category', 'description']
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None or amount <= 0:
            raise forms.ValidationError('Сумма должна быть больше нуля')
        return amount
    
    def clean_date(self):
        date = self.cleaned_data.get('date')
        if date is None:
            raise forms.ValidationError('Дата обязательна для заполнения')
        return date


class ExpenseForm(forms.ModelForm):
    amount = forms.FloatField(
        required=True,
        min_value=0.01,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01',
            'min': '0.01'
        }),
        label='Сумма',
        help_text='Обязательное поле'
    )
    date = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label='Дата',
        help_text='Обязательное поле'
    )
    category = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'list': 'expense-categories',
            'placeholder': 'Выберите или введите новую категорию',
            'autocomplete': 'off'
        }),
        label='Категория',
        help_text='Выберите из существующих или введите новую'
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Автоматизация, бонус, продажа курса...',
            'style': 'resize: vertical; min-height: 80px;'
        }),
        label='Описание',
        help_text='Необязательное поле'
    )
    auto_categorize = forms.BooleanField(
        initial=True, 
        required=False, 
        label='Автокатегоризация',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    class Meta:
        model = Expense
        fields = ['amount', 'date', 'category', 'description']
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None or amount <= 0:
            raise forms.ValidationError('Сумма должна быть больше нуля')
        return amount
    
    def clean_date(self):
        date = self.cleaned_data.get('date')
        if date is None:
            raise forms.ValidationError('Дата обязательна для заполнения')
        return date


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['date', 'title', 'description']


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['doc_type', 'params', 'generated_text']


class CustomUserCreationForm(UserCreationForm):
    """
    Форма регистрации с поддержкой анонимной регистрации.
    Email опционален для приватности.
    """
    email = forms.EmailField(required=False, label='Email (опционально)')
    anonymous_mode = forms.BooleanField(
        required=False, 
        initial=False,
        label='Анонимная регистрация (без email)',
        help_text='Создать аккаунт без email для максимальной приватности'
    )
    seed_phrase = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'readonly': True}),
        label='Seed Phrase (сохраните для восстановления)',
        help_text='Сохраните эту фразу в безопасном месте. Она нужна для восстановления доступа.'
    )
    bio = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Tell us about yourself (occupation, hobbies)...'}),
        label='Bio / Occupation',
        help_text='Helps AI provide better recommendations'
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Имя пользователя'})
        self.fields['email'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Email (опционально)'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Пароль'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Подтверждение пароля'})
        self.fields['anonymous_mode'].widget.attrs.update({'class': 'form-check-input'})
    
    def clean(self):
        cleaned_data = super().clean()
        anonymous_mode = cleaned_data.get('anonymous_mode')
        email = cleaned_data.get('email')
        
        # Если анонимный режим, email не обязателен
        if anonymous_mode and not email:
            cleaned_data['email'] = ''
        
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data.get('email')
        if email:
            user.email = email
        if commit:
            user.save()
            # Создаём профиль пользователя
            from .models import UserProfile
            bio = self.cleaned_data.get('bio')
            profile = UserProfile.objects.create(
                user=user,
                bio=bio
            )
        return user


class CustomAuthenticationForm(AuthenticationForm):
    """
    Форма входа с поддержкой приватного токена.
    """
    private_token = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Приватный токен (альтернатива паролю)'}),
        label='Приватный токен (опционально)',
        help_text='Используйте приватный токен вместо пароля для входа'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Имя пользователя или Email'})
        self.fields['password'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Пароль'})
        self.fields['password'].required = False  # Пароль не обязателен, если есть токен
    
    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')
        private_token = cleaned_data.get('private_token')
        
        # Если передан приватный токен, проверяем его
        if private_token:
            from .models import UserProfile
            try:
                profile = UserProfile.objects.get(private_token=private_token)
                from django.contrib.auth import authenticate
                user = authenticate(self.request, username=profile.user.username, password=None)
                if user:
                    cleaned_data['user'] = user
                    return cleaned_data
            except UserProfile.DoesNotExist:
                raise forms.ValidationError('Неверный приватный токен')
        
        # Обычная проверка пароля
        if not password:
            raise forms.ValidationError('Введите пароль или приватный токен')
        
        return cleaned_data

