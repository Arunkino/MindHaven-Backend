from rest_framework import serializers
from .models import MentorAvailability,Mentor
from users.serializers import UserSerializer

from rest_framework import serializers
from .models import MentorAvailability, AvailabilitySlot, Appointment

class MentorAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = MentorAvailability
        fields = ['id', 'mentor', 'day_of_week', 'start_time', 'end_time', 'is_recurring']

class AvailabilitySlotSerializer(serializers.ModelSerializer):
    mentor_name = serializers.CharField(source='mentor_availability.mentor.user.get_full_name', read_only=True)
    specialization = serializers.CharField(source='mentor_availability.mentor.specialization', read_only=True)

    class Meta:
        model = AvailabilitySlot
        fields = ['id', 'mentor_availability', 'date', 'start_time', 'end_time', 'status', 'mentor_name', 'specialization']
class AppointmentSerializer(serializers.ModelSerializer):
    mentor_name = serializers.CharField(source='mentor.user.get_full_name', read_only=True)
    user_name = serializers.CharField(source='user.first_name', read_only=True)
    specialization = serializers.CharField(source='mentor.specialization', read_only=True)

    class Meta:
        model = Appointment
        fields = ['id', 'date', 'start_time', 'end_time', 'status', 'mentor_name', 'specialization','user_name','video_call_link']

class MentorSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = Mentor
        fields = ['id','user', 'specialization', 'qualifications', 'hourly_rate', 'certificate', 'is_verified']