from functools import wraps
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages

def role_required(*allowed_roles):
    """
    Decorator for views that checks whether a user has one of the required roles.
    Superusers automatically bypass role checks.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
                
            user_role = getattr(request.user, 'role', None)
            if user_role in allowed_roles:
                return view_func(request, *args, **kwargs)
                
            messages.error(request, f"Access denied: Your role '{user_role}' lacks permission for this action.")
            raise PermissionDenied(f"Role '{user_role}' not authorized for this resource.")
        return _wrapped_view
    return decorator

class RoleRequiredMixin:
    """Class-based view mixin ensuring user role matches allowed roles."""
    allowed_roles = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
            
        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)
            
        user_role = getattr(request.user, 'role', None)
        if user_role in self.allowed_roles:
            return super().dispatch(request, *args, **kwargs)
            
        messages.error(request, f"Access denied: Your role '{user_role}' lacks permission for this action.")
        raise PermissionDenied(f"Role '{user_role}' not authorized for this resource.")
