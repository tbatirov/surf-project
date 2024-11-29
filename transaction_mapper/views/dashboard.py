from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def dashboard_view(request):
    """Main dashboard view"""
    context = {
        'title': 'Dashboard',
    }
    return render(request, 'transaction_mapper/dashboard.html', context)
