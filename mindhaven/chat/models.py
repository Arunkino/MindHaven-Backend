from django.db import models
from django.contrib.auth import get_user_model

from mentor.models import Appointment

User = get_user_model()

class ChatMessage(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.sender} to {self.receiver}: {self.content[:50]}"
    

class Notification(models.Model):
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='notifications')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    appointment = models.ForeignKey(Appointment, on_delete=models.SET_NULL, null=True, blank=True)
    notification_type = models.CharField(max_length=50, default='general')

    def __str__(self):
        return f"Notification for {self.user.first_name}: {self.content[:50]}..."