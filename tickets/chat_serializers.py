"""
Serializers for chat conversation API.
"""
from rest_framework import serializers
from .chat_models import Conversation, ChatMessage, QuickReply


class ChatMessageSerializer(serializers.ModelSerializer):
    """Serializer for chat messages."""
    
    class Meta:
        model = ChatMessage
        fields = [
            'id', 'sender_type', 'message_type', 'text', 'metadata',
            'confidence', 'created_at', 'was_helpful', 'feedback_comment'
        ]
        read_only_fields = ['id', 'created_at']


class ConversationSerializer(serializers.ModelSerializer):
    """Serializer for conversations with messages."""
    messages = ChatMessageSerializer(many=True, read_only=True)
    message_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = [
            'id', 'ticket', 'user', 'created_at', 'updated_at',
            'is_active', 'summary', 'resolved', 'resolution_applied',
            'messages', 'message_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'user']
    
    def get_message_count(self, obj):
        return obj.messages.count()


class QuickReplySerializer(serializers.ModelSerializer):
    """Serializer for quick reply suggestions."""
    
    class Meta:
        model = QuickReply
        fields = ['id', 'label', 'message_text', 'category']
