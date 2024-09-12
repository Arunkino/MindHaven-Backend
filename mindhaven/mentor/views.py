#mentor/views.py
from django.shortcuts import render
from rest_framework import viewsets
from .models import MentorAvailability,Appointment
from rest_framework import viewsets, permissions
from rest_framework.exceptions import PermissionDenied
from .serializers import MentorAvailabilitySerializer
from rest_framework.decorators import api_view, permission_classes
from mindhaven.agora_utils import generate_agora_token
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Appointment, Payment
from mindhaven.razorpay_utils import create_razorpay_order, verify_razorpay_payment
from django.shortcuts import get_object_or_404

from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_payment(request, appointment_id):
    logger.debug(f"Creating payment for appointment_id: {appointment_id}")
    
    appointment = get_object_or_404(Appointment, video_call_id=appointment_id, user=request.user)
    logger.debug(f"Appointment found: {appointment}")
    
    # Calculate amount based on call duration
    call_duration_minutes = appointment.call_duration.total_seconds() / 60
    logger.debug(f"Call duration in minutes: {call_duration_minutes}")
    
    hourly_rate = appointment.mentor.hourly_rate
    logger.debug(f"Mentor's hourly rate: {hourly_rate}")
    
    # Convert call_duration_minutes to Decimal for precise calculation
    amount = Decimal(str(call_duration_minutes)) * hourly_rate / Decimal('60')
    amount = amount.quantize(Decimal('0.01'))  # Round to 2 decimal places
    if amount < 50:
        amount = 50
    logger.debug(f"Calculated amount: {amount}")
    
    try:
        order = create_razorpay_order(float(amount))
        logger.debug(f"Razorpay order created: {order}")
    except Exception as e:
        logger.error(f"Error creating Razorpay order: {str(e)}")
        return Response({'error': 'Failed to create Razorpay order'}, status=500)
    
    try:
        payment = Payment.objects.create(
            appointment=appointment,
            user=request.user,
            mentor=appointment.mentor,
            amount=amount,
            razorpay_order_id=order['id']
        )
        logger.debug(f"Payment object created: {payment}")
    except Exception as e:
        logger.error(f"Error creating Payment object: {str(e)}")
        return Response({'error': 'Failed to create Payment object'}, status=500)
    
    response_data = {
        'payment_id': payment.id,
        'razorpay_order_id': order['id'],
        'amount': float(amount),  # Convert Decimal to float for JSON serialization
        'currency': 'INR',
    }
    logger.debug(f"Returning response: {response_data}")
    return Response(response_data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_payment(request):
    logger.debug(f"Received payment verification request from user: {request.user.id}")
    logger.debug(f"Request data: {request.data}")

    payment_id = request.data.get('payment_id')
    razorpay_order_id = request.data.get('razorpay_order_id')
    razorpay_payment_id = request.data.get('razorpay_payment_id')
    razorpay_signature = request.data.get('razorpay_signature')

    logger.debug(f"Payment ID: {payment_id}")
    logger.debug(f"Razorpay Order ID: {razorpay_order_id}")
    logger.debug(f"Razorpay Payment ID: {razorpay_payment_id}")
    logger.debug(f"Razorpay Signature: {razorpay_signature}")

    try:
        payment = get_object_or_404(Payment, id=payment_id, user=request.user)
        logger.debug(f"Found payment: {payment.id}")
    except Payment.DoesNotExist:
        logger.error(f"Payment not found for ID: {payment_id} and user: {request.user.id}")
        return Response({'status': 'Payment not found'}, status=404)

    if verify_razorpay_payment(razorpay_order_id, razorpay_payment_id, razorpay_signature):
        logger.debug("Razorpay payment verification successful")
        payment.status = Payment.COMPLETED
        payment.razorpay_payment_id = razorpay_payment_id
        payment.razorpay_signature = razorpay_signature
        payment.save()
        logger.info(f"Payment {payment.id} marked as completed")
        return Response({'status': 'Payment successful'})
    else:
        logger.warning(f"Razorpay payment verification failed for payment {payment.id}")
        payment.status = Payment.FAILED
        payment.save()
        logger.info(f"Payment {payment.id} marked as failed")
        return Response({'status': 'Payment failed'}, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_agora_token(request, appointment_id):
    try:
        appointment = Appointment.objects.get(video_call_id=appointment_id)
        if request.user != appointment.user and request.user != appointment.mentor.user:
            logger.info(f"User {request.user.id} is not authorized to join call {appointment_id}")
            return Response({'error': 'You are not authorized to join this call'}, status=403)
        
        # Generate a fresh token for each request
        token = generate_agora_token(str(appointment.video_call_id), 0)
        
        return Response({
            'token': token,
            'user': appointment.user.id,
            'mentor': appointment.mentor_user_id
            })
    except Appointment.DoesNotExist:
        return Response({'error': 'Appointment not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)

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
            serializer.save(mentor=self.request.user.mentor_profile)
        else:
            raise PermissionDenied("Only mentors can create availabilities.")
