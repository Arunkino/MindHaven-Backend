from rest_framework import generics, permissions
from .models import ChatMessage, Notification
from .serializers import ChatMessageSerializer, NotificationSerializer
from django.db.models import Q, Max, F, Subquery, OuterRef
from rest_framework.views import APIView
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from rest_framework.response import Response
from rest_framework import status

User = get_user_model()

class RandomOnlineUserView(APIView):
    def get(self, request):
        active_threshold = timezone.now() - timedelta(minutes=5)
        online_users = User.objects.filter(last_activity__gte=active_threshold).exclude(id=request.user.id)
        
        if not online_users.exists():
            return Response({"message": "No online users available"}, status=status.HTTP_404_NOT_FOUND)
        
        random_user = online_users.order_by('?').first()
        return Response({
            "id": random_user.id,
            "username": random_user.username,
            "name" : random_user.first_name
        })

class ChatMessageListCreate(generics.ListCreateAPIView):
    serializer_class = ChatMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        other_user_id = self.request.query_params.get('other_user_id')
        if other_user_id:
            return ChatMessage.objects.filter(
                (Q(sender=user, receiver_id=other_user_id) |
                 Q(sender_id=other_user_id, receiver=user))
            ).order_by('timestamp')
        return ChatMessage.objects.filter(Q(sender=user) | Q(receiver=user)).order_by('timestamp')

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)


class RecentChatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Subquery to get the latest message for each chat
        latest_message = ChatMessage.objects.filter(
            Q(sender=OuterRef('pk'), receiver=user) | 
            Q(sender=user, receiver=OuterRef('pk'))
        ).order_by('-timestamp')

        # Get recent chat partners
        recent_chats = User.objects.filter(
            Q(sent_messages__receiver=user) | Q(received_messages__sender=user)
        ).distinct().annotate(
            last_message=Subquery(latest_message.values('content')[:1]),
            last_message_time=Subquery(latest_message.values('timestamp')[:1])
        ).order_by('-last_message_time')[:10]

        result = [{
            'id': chat.id,
            'name': chat.first_name,
            'last_message': chat.last_message,
            'timestamp': chat.last_message_time
        } for chat in recent_chats]

        print("Recent chats data:", result)  # Debug print
        return Response(result)
    
class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user, is_read=False)

class MarkNotificationReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, notification_id):
        try:
            notification = Notification.objects.get(id=notification_id, user=request.user)
            notification.is_read = True
            notification.save()
            return Response({"status": "success"}, status=status.HTTP_200_OK)
        except Notification.DoesNotExist:
            return Response({"status": "error", "message": "Notification not found"}, status=status.HTTP_404_NOT_FOUND)


class ClearAllNotificationsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        notifications = Notification.objects.filter(user=request.user, is_read=False)
        notifications.update(is_read=True)
        return Response({"status": "success", "message": "All notifications cleared"}, status=status.HTTP_200_OK)