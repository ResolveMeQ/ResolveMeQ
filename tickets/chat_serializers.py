"""
Serializers for chat conversation API.
"""
from rest_framework import serializers
from .chat_models import Conversation, ChatMessage, QuickReply


class ChatMessageSerializer(serializers.ModelSerializer):
    """Serializer for chat messages."""

    show_feedback_prompt = serializers.SerializerMethodField()
    author_name = serializers.SerializerMethodField()

    def get_show_feedback_prompt(self, obj):
        """False once user rated helpful/not helpful — client should hide thumbs row."""
        if obj.sender_type != "ai":
            return False
        return obj.was_helpful is None

    def get_author_name(self, obj):
        """Display name for sender_type='agent' messages, e.g. 'Jane'."""
        if not obj.author_id:
            return None
        author = obj.author
        return author.get_full_name() or author.email or author.username

    class Meta:
        model = ChatMessage
        fields = [
            'id', 'sender_type', 'message_type', 'text', 'metadata',
            'confidence', 'created_at', 'was_helpful', 'feedback_comment',
            'show_feedback_prompt', 'author_name',
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
            'initial_solution_was_helpful',
            'messages', 'message_count',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'user']
    
    def get_message_count(self, obj):
        return obj.messages.count()


class QuickReplySerializer(serializers.ModelSerializer):
    """Serializer for quick reply suggestions."""
    
    class Meta:
        model = QuickReply
        fields = ['id', 'label', 'message_text', 'category']
