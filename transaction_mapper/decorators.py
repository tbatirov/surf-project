from functools import wraps
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse

def role_required(roles):
    """
    Decorator for views that checks whether a user has a particular role,
    redirecting to the login page if necessary. If the user is logged in but
    doesn't have the required role, raises PermissionDenied.
    """
    if isinstance(roles, str):
        roles = [roles]
    elif not isinstance(roles, (list, tuple)):
        roles = list(roles)

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'error': 'Authentication required'}, status=403)
                messages.error(request, "Please log in to access this page.")
                return redirect('login')
            
            try:
                if not hasattr(request.user, 'role') or request.user.role is None:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({'error': 'No role assigned'}, status=403)
                    messages.error(request, "Your account has no role assigned. Please contact an administrator.")
                    return redirect('login')
                
                if request.user.role.name not in roles and 'ADMIN' not in roles:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({'error': 'Insufficient permissions'}, status=403)
                    raise PermissionDenied(f"This action requires one of these roles: {', '.join(roles)}")
                
                return view_func(request, *args, **kwargs)
            except AttributeError:
                messages.error(request, "Role configuration error. Please contact an administrator.")
                return redirect('login')
        return _wrapped_view
    return decorator

def permission_required(permission_codename):
    """
    Decorator to check if user has specific permission
    Usage: @permission_required('add_transaction')
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, "Please log in to access this page.")
                return redirect('login')
                
            if not request.user.has_perm(permission_codename):
                raise PermissionDenied(f"You don't have the required permission: {permission_codename}")
                
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
