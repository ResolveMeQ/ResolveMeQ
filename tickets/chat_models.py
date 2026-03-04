"""
Chat conversation models for AI assistant interaction.
Allows persistent, contextual conversations with the AI agent.
"""
from django.db import models
from django.utils import timezone
from base.models import User
from .models import Ticket
import uuid


class Conversation(models.Model):
    """
    A conversation thread between a user and the AI assistant about a ticket.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='conversations')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    # Summary/context
    summary = models.TextField(blank=True, help_text="AI-generated summary of conversation")
    resolved = models.BooleanField(default=False)
    resolution_applied = models.BooleanField(default=False, help_text="Did user apply suggested solution?")
    
    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['ticket', '-updated_at']),
            models.Index(fields=['user', '-updated_at']),
        ]
    
    def __str__(self):
        return f"Conversation for Ticket #{self.ticket.ticket_id} by {self.user.username}"


class ChatMessage(models.Model):
    """
    Individual messages within a conversation.
    """
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('steps', 'Step-by-step guide'),
        ('question', 'Question with choices'),
        ('solution', 'Proposed solution'),
        ('file_request', 'File upload request'),
        ('similar_tickets', 'Similar tickets'),
        ('kb_article', 'Knowledge base article'),
    ]
    
    SENDER_TYPES = [
        ('user', 'User'),
        ('ai', 'AI Assistant'),
        ('system', 'System'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender_type = models.CharField(max_length=10, choices=SENDER_TYPES)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    
    # Content
    text = models.TextField()
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional data (steps, choices, attachments, etc.)")
    
    # AI-specific fields
    confidence = models.FloatField(null=True, blank=True, help_text="AI confidence score (0.0-1.0)")
    agent_response_data = models.JSONField(null=True, blank=True, help_text="Full agent response")
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    
    # User interaction
    was_helpful = models.BooleanField(null=True, blank=True, help_text="User feedback on AI message")
    feedback_comment = models.TextField(blank=True)
    feedback_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.sender_type} message in {self.conversation.id}"
    
    def save(self, *args, **kwargs):
        # Update conversation timestamp
        if self.conversation:
            self.conversation.updated_at = timezone.now()
            self.conversation.save(update_fields=['updated_at'])
        super().save(*args, **kwargs)


class QuickReply(models.Model):
    """
    Predefined quick replies/suggestions for common questions.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.CharField(max_length=50, help_text="Ticket category this applies to")
    label = models.CharField(max_length=100, help_text="Button text shown to user")
    message_text = models.TextField(help_text="Message sent when clicked")
    priority = models.IntegerField(default=0, help_text="Higher priority shown first")
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-priority', 'label']
    
    def __str__(self):
        return f"{self.label} ({self.category})"
