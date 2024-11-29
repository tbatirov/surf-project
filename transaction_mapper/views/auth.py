from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, UpdateView
from django.contrib.auth.views import (
    LoginView, LogoutView, PasswordChangeView,
    PasswordResetView, PasswordResetConfirmView
)

from ..forms import (
    CustomAuthenticationForm, CustomUserCreationForm,
    UserProfileForm, CustomPasswordChangeForm,
    PasswordResetRequestForm
)
from ..models import User, UserProfile
from ..decorators import role_required

class CustomLoginView(LoginView):
    """Custom login view with enhanced security"""
    form_class = CustomAuthenticationForm
    template_name = 'transaction_mapper/auth/login.html'
    
    def form_valid(self, form):
        # Reset failed login attempts on successful login
        user = form.get_user()
        user.failed_login_attempts = 0
        user.save()
        
        # Get client IP
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
            
        # Update last login IP
        user.last_login_ip = ip
        user.save()
        
        return super().form_valid(form)
    
    def form_invalid(self, form):
        # Increment failed login attempts
        username = form.cleaned_data.get('username')
        if username:
            try:
                user = User.objects.get(username=username)
                user.failed_login_attempts += 1
                user.save()
                
                # Lock account after 5 failed attempts
                if user.failed_login_attempts >= 5:
                    user.is_active = False
                    user.save()
                    messages.error(self.request, 
                        "Account locked due to too many failed login attempts. "
                        "Please contact an administrator."
                    )
            except User.DoesNotExist:
                pass
                
        return super().form_invalid(form)

class CustomLogoutView(LogoutView):
    """Custom logout view"""
    next_page = 'login'

class RegisterView(CreateView):
    """User registration view"""
    form_class = CustomUserCreationForm
    template_name = 'transaction_mapper/auth/register.html'
    success_url = reverse_lazy('login')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        # Create user profile
        UserProfile.objects.create(user=self.object)
        messages.success(self.request, "Registration successful. Please login.")
        return response

@method_decorator(login_required, name='dispatch')
class ProfileUpdateView(UpdateView):
    """User profile update view"""
    model = UserProfile
    form_class = UserProfileForm
    template_name = 'transaction_mapper/auth/profile.html'
    success_url = reverse_lazy('profile')
    
    def get_object(self, queryset=None):
        return self.request.user.profile

@method_decorator(login_required, name='dispatch')
class CustomPasswordChangeView(PasswordChangeView):
    """Custom password change view with enhanced validation"""
    form_class = CustomPasswordChangeForm
    template_name = 'transaction_mapper/auth/password_change.html'
    success_url = reverse_lazy('profile')
    
    def form_valid(self, form):
        messages.success(self.request, "Password successfully changed.")
        return super().form_valid(form)

@method_decorator(role_required(['ADMIN']), name='dispatch')
class UserManagementView(UpdateView):
    """Admin view for managing users"""
    model = User
    template_name = 'transaction_mapper/auth/user_management.html'
    fields = ['is_active', 'role']
    success_url = reverse_lazy('user_management')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['users'] = User.objects.all().select_related('role')
        return context
