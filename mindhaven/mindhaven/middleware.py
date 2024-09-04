from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from datetime import timedelta
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from django.contrib.auth.models import AnonymousUser

User = get_user_model()

class JWTMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip JWT authentication for login, register, token, media, and static paths
        if (request.path.startswith('/media/') or 
            request.path.startswith('/static/') or
            request.path in ['/login/','/register/user/','/register/mentor/', '/api/token/', '/api/token/refresh/']):
            return self.get_response(request)
        
        jwt_auth = JWTAuthentication()
        try:
            user, validated_token = jwt_auth.authenticate(request)
            if user is not None:
                request.user = user
                request.auth = validated_token
            else:
                request.user = AnonymousUser()
        except (InvalidToken, AuthenticationFailed):
            request.user = AnonymousUser()
            request.auth = None
        
        return self.get_response(request)

class UserActivityMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # print("UserActivityMiddleware: process_request")
        # print(f"User authenticated: {request.user.is_authenticated}")
        # print(f"User: {request.user}")

        if request.user.is_authenticated:
            now = timezone.now()
            last_activity_threshold = now - timedelta(minutes=1)

            # print(f"Last activity: {request.user.last_activity}")
            if request.user.last_activity is None or request.user.last_activity < last_activity_threshold:
                User.objects.filter(id=request.user.id).update(last_activity=now)
                # print("UserActivityMiddleware: Last activity updated")