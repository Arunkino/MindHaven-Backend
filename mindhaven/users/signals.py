# users/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from chat.models import Notification

@receiver(post_save, sender=Notification)
def send_notification(sender, instance, created, **kwargs):
    if created:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{instance.user.id}",
            {
                "type": "send_notification",
                "notification": {
                    "id": instance.id,
                    "content": instance.content,
                    "created_at": instance.created_at,
                }
            }
        )