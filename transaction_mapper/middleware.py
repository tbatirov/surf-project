from django.utils import timezone
from .models import UserActivity
import json

class UserActivityMiddleware:
    """Middleware to track user activities"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Code to be executed before the view
        
        response = self.get_response(request)
        
        # Code to be executed after the view
        if hasattr(request, 'user') and request.user.is_authenticated:
            # Track certain activities based on the request
            if request.method in ['POST', 'PUT', 'DELETE']:
                activity_type = f"{request.method}_{request.resolver_match.url_name}"
                description = {
                    'path': request.path,
                    'method': request.method,
                    'view': request.resolver_match.url_name
                }
                
                UserActivity.objects.create(
                    user=request.user,
                    activity_type=activity_type,
                    description=json.dumps(description),
                    ip_address=self.get_client_ip(request)
                )
                
                # Update last login IP
                if not request.user.last_login_ip:
                    request.user.last_login_ip = self.get_client_ip(request)
                    request.user.save()
        
        return response
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')
