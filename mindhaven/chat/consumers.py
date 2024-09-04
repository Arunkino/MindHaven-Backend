import json
from openai import AsyncOpenAI
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import ChatMessage,Notification
from mentor.models import Appointment
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
import logging
from datetime import timedelta, datetime
from django.db.models import Q


User = get_user_model()
logger = logging.getLogger(__name__)

# Initialize the AsyncOpenAI client
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

class ChatConsumer(AsyncWebsocketConsumer):
 
 #created for celery notification
    async def send_notification(self, event):
        notification = event['notification']
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'notification': {
                'id': notification['id'],
                'content': notification['content'],
                'created_at': notification['created_at'].isoformat(),
            }
        }))
    async def connect(self):
        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.user_group_name = f'user_{self.user_id}'
        logger.info(f"WebSocket connection established for user {self.user_id}")

        # Join user group
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        logger.info(f"WebSocket disconnected for user {self.user_id}")
        await self.channel_layer.group_discard(
            self.user_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json['type']

        if message_type == 'video_call_event':
            event_data = text_data_json['data']
            await self.handle_video_call_event(event_data)
        
        elif message_type == 'chat_message':
            message_data = text_data_json['message']
            message_content = message_data['content']
            sender_id = message_data['sender']
            receiver_id = message_data['receiver']

            # AI moderation
            is_appropriate, ai_response = await self.moderate_message(message_content)

            if is_appropriate:
                # Save message to database
                message = await self.save_message(sender_id, receiver_id, message_content)

                # Create notification for the receiver
                notification_content = f"New message from {message.sender.first_name}"
                await self.create_notification(receiver_id, notification_content)

                # Send message to sender's group
                await self.channel_layer.group_send(
                    f'user_{sender_id}',
                    {
                        'type': 'chat_message',
                        'message': {
                            'id': message.id,
                            'content': message.content,
                            'sender': message.sender.id,
                            'receiver': message.receiver.id,
                            'timestamp': message.timestamp.isoformat(),
                        }
                    }
                )

                # Send message to receiver's group
                await self.channel_layer.group_send(
                    f'user_{receiver_id}',
                    {
                        'type': 'chat_message',
                        'message': {
                            'id': message.id,
                            'content': message.content,
                            'sender': message.sender.id,
                            'receiver': message.receiver.id,
                            'timestamp': message.timestamp.isoformat(),
                        }
                    }
                )
                # Send notification to receiver's group
                await self.channel_layer.group_send(
                    f'user_{receiver_id}',
                    {
                        'type': 'new_notification',
                        'notification': {
                            'content': notification_content,
                        }
                    }
                )
            
                # Send AI response to the sender
            else:
                # Send AI response to the sender
                await self.send(text_data=json.dumps({
                    'type': 'ai_moderation',
                    'message': ai_response,
                    'sender': 'AI Moderator'
                }))

    async def chat_message(self, event):
        message = event['message']
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': message
        }))

    @database_sync_to_async
    def save_message(self, sender_id, receiver_id, content):
        sender = User.objects.get(id=sender_id)
        receiver = User.objects.get(id=receiver_id)
        return ChatMessage.objects.create(sender=sender, receiver=receiver, content=content)

    async def moderate_message(self, message):
        try:
            response = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful AI moderator for a mental health support chat."},
                    {"role": "user", "content": f"Analyze the following message for negativity and inappropriate content: '{message}'\nIs this message appropriate for a mental health support chat? Respond with 'Yes' or 'No' followed by a brief explanation."}
                ],
                max_tokens=100
            )
            
            ai_response = response.choices[0].message.content.strip()
            is_appropriate = ai_response.lower().startswith('yes')
            
            return is_appropriate, ai_response
        except Exception as e:
            print(f"Error in AI moderation: {type(e).__name__}: {str(e)}")
            return self.fallback_moderation(message)

    def fallback_moderation(self, message):
        # List of keywords that might indicate inappropriate content
        inappropriate_keywords = ['suicide', 'kill', 'die', 'hurt', 'abuse', 'attack']
        
        # Check if any inappropriate keywords are in the message
        if any(keyword in message.lower() for keyword in inappropriate_keywords):
            return False, "This message may contain sensitive content. Please be mindful of the community guidelines."
        
        return True, "Message allowed (fallback moderation)"
    
# notification create
    async def new_notification(self, event):
        await self.send(text_data=json.dumps({
            'type': 'new_notification',
            'notification': event['notification']
        }))

    @database_sync_to_async
    def create_notification(self, user_id, content):
        user = User.objects.get(id=user_id)
        return Notification.objects.create(user=user, content=content)
    




    # video call event handler
    
    async def handle_video_call_event(self, event_data):

        logger.info(f"Handling video call event: {event_data}")
        event_type = event_data['event_type']
        video_call_id = event_data['appointment_id']
        user_role = event_data['user_role']
        
        if event_type == 'user_joined':
            appointment_data = await self.user_joined_call(video_call_id, user_role)
            logger.info(f"User joined call. Appointment data: {appointment_data}")
            await self.channel_layer.group_send(
                f"video_call_{video_call_id}",
                {
                    'type': 'video_call_update',
                    'data': appointment_data
                }
            )
        elif event_type == 'call_ended':
            call_duration = event_data['call_duration']
            await self.end_call(video_call_id, call_duration, user_role)
            logger.info(f"Call ended. Video Call ID: {video_call_id}, Duration: {call_duration}")
            await self.channel_layer.group_send(
                f"video_call_{video_call_id}",
                {
                    'type': 'video_call_update',
                    'data': {'call_ended': True, 'call_duration': call_duration}
                }
            )

    async def connect(self):
        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.user_group_name = f'user_{self.user_id}'
        
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)
        await self.accept()

        # Fetch active appointments for this user
        appointments = await self.get_active_appointments(self.user_id)
        for appointment in appointments:
            group_name = f"video_call_{appointment.video_call_id}"
            await self.channel_layer.group_add(group_name, self.channel_name)

    @database_sync_to_async
    def get_active_appointments(self, user_id):
        return list(Appointment.objects.filter(
            Q(user_id=user_id) | Q(mentor__user_id=user_id),
            status='scheduled'
        ))

    @database_sync_to_async
    def user_joined_call(self, video_call_id, user_role):
        logger.info(f"User joined call. Video Call ID: {video_call_id}, User Role: {user_role}")
        appointment = Appointment.objects.get(video_call_id=video_call_id)
        if user_role == 'normal':
            appointment.user_joined = True
        elif user_role == 'mentor':
            appointment.mentor_joined = True
        
        if appointment.user_joined and appointment.mentor_joined and not appointment.call_start_time:
            appointment.call_start_time = timezone.now()
        
        appointment.save()
        logger.info(f"Updated appointment: user_joined={appointment.user_joined}, mentor_joined={appointment.mentor_joined}, call_start_time={appointment.call_start_time}")

        return {
            'user_joined': appointment.user_joined,
            'mentor_joined': appointment.mentor_joined,
            'call_started': appointment.call_start_time is not None
        }

    @database_sync_to_async
    def end_call(self, video_call_id, call_duration, user_role):
        logger.info(f"Ending call. Video Call ID: {video_call_id}, Duration: {call_duration}")
        appointment = Appointment.objects.get(video_call_id=video_call_id)
        appointment.call_duration = timedelta(seconds=call_duration)
        appointment.call_end_time = timezone.now()
        appointment.user_joined = False
        appointment.mentor_joined = False
        appointment.status = 'completed'
        appointment.save()
        logger.info(f"Call ended. Appointment updated: call_duration={appointment.call_duration}, call_end_time={appointment.call_end_time}")

    async def video_call_update(self, event):
        logger.info(f"Sending video call update: {event['data']}")
        await self.send(text_data=json.dumps({
            'type': 'video_call_update',
            'data': event['data']
        }))