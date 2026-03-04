"""
URLs for chat conversation API.
"""
from django.urls import path
from .chat_views import (
    start_or_get_conversation,
    send_chat_message,
    get_conversation_history,
    submit_message_feedback,
    get_suggested_questions,
)

urlpatterns = [
    # Chat conversation endpoints
    path('<int:ticket_id>/chat/', send_chat_message, name='chat-send-message'),
    path('<int:ticket_id>/chat/start/', start_or_get_conversation, name='chat-start'),
    path('<int:ticket_id>/chat/history/', get_conversation_history, name='chat-history'),
    path('<int:ticket_id>/chat/<uuid:message_id>/feedback/', submit_message_feedback, name='chat-feedback'),
    path('<int:ticket_id>/chat/suggestions/', get_suggested_questions, name='chat-suggestions'),
]
