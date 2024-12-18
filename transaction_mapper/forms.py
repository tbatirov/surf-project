from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from django.core.exceptions import ValidationError
from .models import User, UserProfile, Role

class CustomAuthenticationForm(AuthenticationForm):
    """Custom login form with enhanced validation"""
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Username'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control',
        'placeholder': 'Password'
    }))

class CustomUserCreationForm(UserCreationForm):
    """Custom user registration form"""
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'class': 'form-control',
        'placeholder': 'Email'
    }))
    role = forms.ModelChoiceField(
        queryset=Role.objects.all(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'role')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Username'
            })
        }
    
    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email is already registered.")
        return email<tr>
            <th>Date</th>
            <th>Description</th>
            <th>Amount</th>
            <th>Debit Account</th>
            <th>Credit Account</th>
            <th>Status</th>
            <th>Actions</th>
        </tr><td>{{ transaction.debit_account.account_id }} - {{ transaction.debit_account.name }}</td>
        <td>{{ transaction.credit_account.account_id }} - {{ transaction.credit_account.name }}</td><div class="mb-3">
            <label for="debitAccount{{ transaction.transaction_id }}" class="form-label">Debit Account</label>
            <select class="form-select" id="debitAccount{{ transaction.transaction_id }}" required>
                <option value="">Choose debit account...</option>
                {% for account in accounts %}
                <option value="{{ account.account_id }}">{{ account.account_id }} - {{ account.name }}</option>
                {% endfor %}
            </select>
        </div>
        <div class="mb-3">
            <label for="creditAccount{{ transaction.transaction_id }}" class="form-label">Credit Account</label>
            <select class="form-select" id="creditAccount{{ transaction.transaction_id }}" required>
                <option value="">Choose credit account...</option>
                {% for account in accounts %}
                <option value="{{ account.account_id }}">{{ account.account_id }} - {{ account.name }}</option>
                {% endfor %}
            </select>
        </div>

class UserProfileForm(forms.ModelForm):
    """Form for user profile information"""
    class Meta:
        model = UserProfile
        fields = ('department', 'phone_number', 'timezone')
        widgets = {
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'timezone': forms.Select(attrs={'class': 'form-control'})
        }

class PasswordResetRequestForm(forms.Form):
    """Form for requesting password reset"""
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'class': 'form-control',
        'placeholder': 'Enter your email'
    }))

    def clean_email(self):
        email = self.cleaned_data['email']
        if not User.objects.filter(email=email).exists():
            raise ValidationError("No user found with this email address.")
        return email

class CustomPasswordChangeForm(PasswordChangeForm):
    """Custom password change form with enhanced validation"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})
            
    def clean_new_password2(self):
        password1 = self.cleaned_data.get('new_password1')
        password2 = self.cleaned_data.get('new_password2')
        if password1 and password2:
            if len(password1) < 8:
                raise ValidationError("Password must be at least 8 characters long.")
            if password1 != password2:
                raise ValidationError("The two password fields didn't match.")
        return password2
