from django.urls import path
from .views import UserRegisterView, MentorRegisterView, LoginView

urlpatterns = [
    path('register/user/', UserRegisterView.as_view(), name='user-register'),
    path('register/mentor/', MentorRegisterView.as_view(), name='mentor-register'),
    path('login/', LoginView.as_view(), name='login'),
]