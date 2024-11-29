from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def profile_view(request):
    """User profile view"""
    context = {
        'title': 'Profile',
        'user': request.user,
    }
    return render(request, 'transaction_mapper/profile.html', context)
