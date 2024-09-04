# mentor/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MentorAvailabilityViewSet

router = DefaultRouter()
router.register(r'availabilities', MentorAvailabilityViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
