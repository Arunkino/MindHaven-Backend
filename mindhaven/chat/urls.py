from django.urls import path
from .views import ChatMessageListCreate, RandomOnlineUserView, RecentChatsView

urlpatterns = [
    path('', ChatMessageListCreate.as_view(), name='chat-messages'),
    path('recent-chats/', RecentChatsView.as_view(), name='recent-chats'),
    path('random-online-user/', RandomOnlineUserView.as_view(), name='random-online-user'),
]