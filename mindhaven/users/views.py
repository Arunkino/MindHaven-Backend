from rest_framework import generics, status,viewsets
from rest_framework.permissions import AllowAny
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.models import update_last_login
from .serializers import UserRegistrationSerializer, MentorRegistrationSerializer
from .models import User
from .serializers import UserSerializer
from mentor.models import Mentor
from mentor.serializers import MentorSerializer
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    def get_queryset(self):
        role = self.request.query_params.get('role')
        if role:
            
            return self.queryset.filter(role=role)
        return self.queryset

class MentorViewSet(viewsets.ModelViewSet):
    queryset = Mentor.objects.all()
    serializer_class = MentorSerializer

    @action(detail=False, methods=['get'])
    def pending(self, request):
        pending_mentors = self.queryset.filter(is_verified=False)
        serializer = self.get_serializer(pending_mentors, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def approved(self, request):
        approved_mentors = self.queryset.filter(is_verified=True)
        serializer = self.get_serializer(approved_mentors, many=True)
        return Response(serializer.data)
class UserRegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'role': user.role,
                'phone': user.phone
            }
        }, status=status.HTTP_201_CREATED)

class MentorRegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = MentorRegistrationSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        logger.info(f"Received data: {request.data}")
        logger.info(f"Received files: {request.FILES}")


        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        user = User.objects.select_related('mentor_profile').get(id=user.id)

        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'role': user.role,
                'phone': user.phone,
                'is_verified':user.mentor_profile.is_verified
            }
        }, status=status.HTTP_201_CREATED)

class LoginView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):

        email = request.data.get('email', '')
        password = request.data.get('password', '')
        
        user = authenticate(email=email, password=password)

        if user:
            user = User.objects.select_related('mentor_profile').get(id=user.id)
            update_last_login(None, user)
            refresh = RefreshToken.for_user(user)

            # Update last activity timestamp
            user.last_activity = timezone.now()
            user.save()
            print(f"Last activity: {user.last_activity}")
            
            user_data = {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'role': user.role,
                'is_superuser': user.is_superuser
            }
            
            print("checkkkk")
            if hasattr(user, 'mentor_profile'):
                print("Check for is_verified")
                user_data['is_verified'] = user.mentor_profile.is_verified
                user_data['mentor_id'] = user.mentor_profile.id 
            
            

            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': user_data
            }, status=status.HTTP_200_OK)
        
        return Response({'error': 'Invalid email or password. Please try again.'}, status=status.HTTP_401_UNAUTHORIZED)
    

    