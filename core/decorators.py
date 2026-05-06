from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import Profile


def role_required(required_role):
    def decorator(view_func):
        @login_required(login_url='/login/')
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            try:
                role = request.user.profile.user_type
            except Profile.DoesNotExist:
                messages.warning(request, 'Profile not found. Please contact support.')
                return redirect('home')

            if role != required_role:
                if role == 'seller':
                    messages.warning(request, 'You are not authorized to access buyer features.')
                    return redirect('seller_dashboard')
                messages.warning(request, 'You are not authorized to access seller features.')
                return redirect('dashboard')

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


buyer_required = role_required('buyer')
seller_required = role_required('seller')
