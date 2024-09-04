from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView,TokenVerifyView
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework import viewsets, permissions, status,serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta,datetime
from mentor.models import MentorAvailability, AvailabilitySlot, Appointment
from mentor.serializers import MentorAvailabilitySerializer, AvailabilitySlotSerializer, AppointmentSerializer
from django.db.models import Q
from users.models import User
from users.serializers import UserSerializer
from mentor.models import Mentor
from mentor.serializers import MentorSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from dateutil.parser import parse
from django.db import IntegrityError

import logging

logger = logging.getLogger(__name__)

# admin dashboard viewset for verifying mentor and handling users
class AdminDashboardViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAdminUser]

    @action(detail=False, methods=['get'])
    def pending_mentors(self, request):
        pending_mentors = Mentor.objects.filter(is_verified=False)
        serializer = MentorSerializer(pending_mentors, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def approved_mentors(self, request):
        approved_mentors = Mentor.objects.filter(is_verified=True)
        serializer = MentorSerializer(approved_mentors, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def users(self, request):
        users = User.objects.filter(role='normal')
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def approve_mentor(self, request, pk=None):
        try:
            mentor = Mentor.objects.get(pk=pk)
            mentor.is_verified = True
            mentor.save()
            serializer = MentorSerializer(mentor)
            return Response(serializer.data)
        except Mentor.DoesNotExist:
            return Response({"error": "Mentor not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def reject_mentor(self, request, pk=None):
        try:
            mentor = Mentor.objects.get(pk=pk)
            mentor.delete()
            return Response({"message": "Mentor application rejected and deleted"}, status=status.HTTP_204_NO_CONTENT)
        except Mentor.DoesNotExist:
            return Response({"error": "Mentor not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def block_user(self, request, pk=None):
        try:
            user = User.objects.get(pk=pk)
            user.is_active = False
            user.save()
            serializer = UserSerializer(user)
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def unblock_user(self, request, pk=None):
        try:
            user = User.objects.get(pk=pk)
            user.is_active = True
            user.save()
            serializer = UserSerializer(user)
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)


class MentorAvailabilityViewSet(viewsets.ModelViewSet):
    queryset = MentorAvailability.objects.all()
    serializer_class = MentorAvailabilitySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'mentor_profile'):
            return MentorAvailability.objects.filter(mentor=user.mentor_profile)
        else:
            return MentorAvailability.objects.none()

    def perform_create(self, serializer):
        if hasattr(self.request.user, 'mentor_profile'):
            is_recurring = self.request.data.get('is_recurring', False)
            current_date = timezone.now()
            if 'current_date' in self.request.data:
                current_date = parse(self.request.data['current_date'])
            
            # Check for existing availability
            existing_availability = MentorAvailability.objects.filter(
                mentor=self.request.user.mentor_profile,
                day_of_week=self.request.data['day_of_week'],
                start_time=self.request.data['start_time'],
                end_time=self.request.data['end_time']
            ).first()

            if existing_availability:
                # Update existing availability if it exists
                existing_availability.is_recurring = is_recurring
                existing_availability.save()
                availability = existing_availability
            else:
                # Create new availability if it doesn't exist
                availability = serializer.save(mentor=self.request.user.mentor_profile)

            self.generate_availability_slots(availability, is_recurring, current_date)
        else:
            raise PermissionDenied("Only mentors can create availabilities.")

    def generate_availability_slots(self, availability, is_recurring, current_date):
        start_date = current_date.date()
        end_date = start_date + timedelta(weeks=4 if is_recurring else 1)
        current_date = start_date

        while current_date <= end_date:
            if current_date.weekday() == availability.day_of_week:
                slot_start = timezone.make_aware(datetime.combine(current_date, availability.start_time))
                slot_end = timezone.make_aware(datetime.combine(current_date, availability.end_time))

                # Handle same-day creation
                now = timezone.now()
                if slot_start < now:
                    if current_date == start_date:
                        slot_start = now.replace(minute=(now.minute // 30) * 30, second=0, microsecond=0) + timedelta(minutes=30)
                    else:
                        current_date += timedelta(days=1)
                        continue

                while slot_start < slot_end:
                    next_slot = slot_start + timedelta(minutes=30)
                    
                    # Check for existing slots
                    existing_slot = AvailabilitySlot.objects.filter(
                        mentor_availability__mentor=availability.mentor,
                        date=current_date,
                        start_time__lt=next_slot.time(),
                        end_time__gt=slot_start.time()
                    ).first()

                    if not existing_slot:
                        AvailabilitySlot.objects.create(
                            mentor_availability=availability,
                            date=current_date,
                            start_time=slot_start.time(),
                            end_time=next_slot.time(),
                            status='available'
                        )
                    slot_start = next_slot

            current_date += timedelta(days=1)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        slots = AvailabilitySlot.objects.filter(mentor_availability=instance)
        booked_slots = slots.filter(status='booked')
        
        if booked_slots.exists():
            return Response({"error": "Cannot delete availability with booked slots."}, status=status.HTTP_400_BAD_REQUEST)
        
        slots.delete()
        return super().destroy(request, *args, **kwargs)
class AvailabilitySlotViewSet(viewsets.ModelViewSet):
    queryset = AvailabilitySlot.objects.all()
    serializer_class = AvailabilitySlotSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'mentor_profile'):
            return AvailabilitySlot.objects.filter(mentor_availability__mentor=user.mentor_profile)
        else:
            return AvailabilitySlot.objects.filter(status='available')

    @action(detail=True, methods=['post'])
    def book(self, request, pk=None):
        slot = self.get_object()
        logger.debug(f"Attempting to book slot: {slot.id}")
        if slot.status == 'available':
            slot.status = 'booked'
            slot.save()
            try:
                appointment = Appointment.objects.create(
                    availability_slot=slot,
                    user=request.user,
                    mentor=slot.mentor_availability.mentor,
                    mentor_user_id = slot.mentor_availability.mentor.user_id,
                    date=slot.date,
                    start_time=slot.start_time,
                    end_time=slot.end_time
                )
                logger.debug(f"Appointment created: {appointment.id}")
                return Response({'status': 'slot booked', 'appointment_id': appointment.id})
            except IntegrityError as e:
                logger.error(f"IntegrityError when creating appointment: {str(e)}")
                return Response({'status': 'Error creating appointment', 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'status': 'slot is not available'}, status=status.HTTP_400_BAD_REQUEST)
    @action(detail=False, methods=['get'])
    def available(self, request):
        date = request.query_params.get('date')
        specialization = request.query_params.get('specialization')

        available_slots = AvailabilitySlot.objects.filter(
            status='available',
            date__gte=timezone.now().date()
        )

        if date:
            available_slots = available_slots.filter(date=date)

        if specialization:
            available_slots = available_slots.filter(
                mentor_availability__mentor__specialization__icontains=specialization
            )

        available_slots = available_slots.order_by('date', 'start_time')
        serializer = self.get_serializer(available_slots, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def block(self, request, pk=None):
        slot = self.get_object()
        if slot.status == 'available':
            slot.status = 'blocked'
            slot.save()
            return Response({'status': 'slot blocked'})
        return Response({'status': 'slot is not available'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def unblock(self, request, pk=None):
        slot = self.get_object()
        if slot.status == 'blocked':
            slot.status = 'available'
            slot.save()
            return Response({'status': 'slot unblocked'})
        return Response({'status': 'slot is not blocked'}, status=status.HTTP_400_BAD_REQUEST)

    

class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'mentor_profile'):
            return Appointment.objects.filter(mentor=user.mentor_profile)
        else:
            return Appointment.objects.filter(user=user)

# for cancelling an appointment    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        appointment = self.get_object()
        user = request.user

        if hasattr(user, 'mentor_profile'):
            if appointment.mentor != user.mentor_profile:
                return Response({"error": "You are not authorized to cancel this appointment."}, status=403)
            appointment.status = 'cancelled_by_mentor'
        else:
            if appointment.user != user:
                return Response({"error": "You are not authorized to cancel this appointment."}, status=403)
            appointment.status = 'cancelled_by_user'

        appointment.save()

        # Update the availability slot
        availability_slot = appointment.availability_slot
        availability_slot.status = 'available'
        availability_slot.save()

        return Response({"message": "Appointment cancelled successfully."})

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        user = request.user
        now = timezone.now().date()  # Using date only
        current_time = timezone.now().time()
        print(f"Current date: {now}, Current time: {current_time}")

        is_mentor = hasattr(user, 'mentor_profile')
        print(f"User has mentor profile: {is_mentor}")

        if is_mentor:
            # Fetch appointments for mentors
            upcoming_appointments = Appointment.objects.filter(
                mentor=user.mentor_profile,
                date__gte=now
            ).order_by('date', 'start_time')
        else:
            # Fetch appointments for users
            upcoming_appointments = Appointment.objects.filter(
                user=user,
                date__gte=now
            ).order_by('date', 'start_time')

        # If today, filter by time
        if upcoming_appointments and upcoming_appointments[0].date == now:
            upcoming_appointments = upcoming_appointments.filter(start_time__gte=current_time)

        print(upcoming_appointments)
        serializer = self.get_serializer(upcoming_appointments, many=True)
        return Response(serializer.data)


# Serializer for toke pair
class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        return token
class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

class CustomTokenVerifyView(TokenVerifyView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            user = request.user
            refresh = RefreshToken.for_user(user)
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'role': user.role,
                    # Add any other user details you want to include
                }
            })
        return Response({'detail': 'Token is invalid or expired'}, status=status.HTTP_401_UNAUTHORIZED)