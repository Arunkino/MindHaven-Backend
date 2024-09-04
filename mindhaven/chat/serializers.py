from rest_framework import serializers
from .models import ChatMessage,Notification

class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['id', 'sender', 'receiver', 'content', 'timestamp']
        read_only_fields = ['sender', 'timestamp']

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'content', 'created_at']