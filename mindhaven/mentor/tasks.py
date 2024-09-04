from time import sleep
from .models import Appointment
from chat.models import Notification
from django.utils import timezone
from datetime import timedelta
from celery import shared_task
import logging
from mindhaven.agora_utils import generate_agora_token
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import pytz

from django.conf import settings
logger = logging.getLogger(__name__)

@shared_task
def check_upcoming_appointments():
    logger.info("Task check_upcoming_appointments started")
    
    # Get the server's timezone
    server_tz = pytz.timezone('Asia/Kolkata')  # Replace with your server's timezone
    now = timezone.now().astimezone(server_tz)
    upcoming_time = now + timedelta(minutes=5)
    
    logger.info(f"Checking appointments between {now} and {upcoming_time}")

    upcoming_appointments = Appointment.objects.filter(
        date=upcoming_time.date(),
        start_time__gte=now.time(),
        start_time__lte=upcoming_time.time(),
        status='scheduled',
        notification_sent=False
    )

    logger.info(f"Found {upcoming_appointments.count()} upcoming appointments")

    channel_layer = get_channel_layer()

    for appointment in upcoming_appointments:
        logger.info(f"Processing appointment: {appointment}")

        try:
            # Generate Agora token if not already generated
            if not appointment.agora_token:
                channel_name = str(appointment.video_call_id)
                token = generate_agora_token(channel_name, 0)  # 0 is a placeholder UID
                appointment.agora_token = token
                logger.info(f"Generated Agora token: {token}")
            
            # Add video call link
            if not appointment.video_call_link:
                logger.info("Adding video call link")
                appointment.video_call_link = f"{settings.DOMAIN}video-call/{appointment.video_call_id}/"
                logger.info(f"Video call link: {appointment.video_call_link}")

            # Create and send notification for user
            user_notification = Notification.objects.create(
                user=appointment.user,
                content=f"Your appointment with {appointment.mentor.user.get_full_name()} starts in 5 minutes. Join here: {appointment.video_call_link}",
                appointment=appointment,
                notification_type='appointment_reminder'
            )
            async_to_sync(channel_layer.group_send)(
                f'user_{appointment.user.id}',
                {
                    'type': 'send_notification',
                    'notification': {
                        'content': user_notification.content,
                    }
                }
            )
            logger.info(f"Sent user notification: {user_notification}")

            # Create and send notification for mentor
            mentor_notification = Notification.objects.create(
                user=appointment.mentor.user,
                content=f"Your appointment with {appointment.user.get_full_name()} starts in 5 minutes. Join here: {appointment.video_call_link}",
                appointment=appointment,
                notification_type='appointment_reminder'
            )
            async_to_sync(channel_layer.group_send)(
                f'user_{appointment.mentor.user.id}',
                {
                    'type': 'new_notification',
                    'notification': {
                        'content': mentor_notification.content,
                    }
                }
            )
            logger.info(f"Sent mentor notification: {mentor_notification}")

            # Mark the appointment as notified
            appointment.notification_sent = True
            appointment.save()
            logger.info(f"Updated appointment: notification_sent = {appointment.notification_sent}")

        except Exception as e:
            logger.error(f"Error processing appointment {appointment.id}: {str(e)}")

    logger.info("Task check_upcoming_appointments completed")
@shared_task
def test_task():
    logger.info("Test task started")
    try:
        sleep(5)  # Simulate some work
        logger.info("Test task completed")
        return "Test task completed successfully"
    except Exception as e:
        logger.error(f"Error in test_task: {str(e)}")
        raise