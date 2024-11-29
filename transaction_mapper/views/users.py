from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from ..decorators import role_required

User = get_user_model()

@login_required
@role_required('ADMIN')
def user_management_view(request):
    """User management view - Admin only"""
    users = User.objects.all()
    context = {
        'title': 'User Management',
        'users': users,
    }
    return render(request, 'transaction_mapper/users/management.html', context)

def register_view(request):
    """User registration view"""
    if request.method == 'POST':
        # Handle registration logic here
        pass
    return render(request, 'transaction_mapper/users/register.html', {'title': 'Register'})
