from rest_framework import serializers
from django.contrib.auth import get_user_model
from mentor.models import Mentor

User = get_user_model()

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['first_name', 'email', 'phone', 'password']
        extra_kwargs = {'phone': {'required': False}}

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            phone=validated_data.get('phone', ''),
            role=User.NORMAL
        )
        return user
    
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'phone', 'role', 'is_active','first_name']

class MentorRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    specialization = serializers.CharField(required=False)
    qualifications = serializers.CharField(required=False)
    hourly_rate = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    certificate = serializers.ImageField(required=False)
    is_verified = serializers.BooleanField(default=False,required=False)

    class Meta:
        model = User
        fields = ['first_name', 'email', 'phone', 'password', 'specialization', 'qualifications', 'hourly_rate', 'certificate','is_verified']

    def create(self, validated_data):
        mentor_data = {
            'specialization': validated_data.pop('specialization'),
            'qualifications': validated_data.pop('qualifications', ''),
            'hourly_rate': validated_data.pop('hourly_rate'),
            'certificate': validated_data.pop('certificate', None)
        }
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            phone=validated_data.get('phone', ''),
            role=User.MENTOR
        )
        Mentor.objects.create(user=user, **mentor_data)
        return user