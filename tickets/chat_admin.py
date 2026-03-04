"""
Admin interface for chat models.
"""
from django.contrib import admin
from .chat_models import Conversation, ChatMessage, QuickReply


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['id', 'ticket', 'user', 'created_at', 'is_active', 'resolved', 'message_count']
    list_filter = ['is_active', 'resolved', 'resolution_applied', 'created_at']
    search_fields = ['ticket__ticket_id', 'ticket__issue_type', 'user__username', 'summary']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description =  'Messages'


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'conversation', 'sender_type', 'message_type', 'created_at', 'was_helpful']
    list_filter = ['sender_type', 'message_type', 'was_helpful', 'created_at']
    search_fields = ['text', 'conversation__ticket__issue_type']
    readonly_fields = ['id', 'created_at', 'feedback_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Message Info', {
            'fields': ('id', 'conversation', 'sender_type', 'message_type', 'created_at')
        }),
        ('Content', {
            'fields': ('text', 'metadata', 'confidence', 'agent_response_data')
        }),
        ('Feedback', {
            'fields': ('was_helpful', 'feedback_comment', 'feedback_at')
        }),
    )


@admin.register(QuickReply)
class QuickReplyAdmin(admin.ModelAdmin):
    list_display = ['label', 'category', 'priority', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['label', 'message_text']
    list_editable = ['priority', 'is_active']
