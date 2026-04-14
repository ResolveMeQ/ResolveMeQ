from rest_framework import serializers
from solutions.models import Solution,KnowledgeBaseEntry
from tickets.models import Ticket, TicketInteraction, ActionHistory, ResolutionTemplate


class SolutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Solution
        fields = [
            'id', 'ticket', 'resolution', 'worked',
            'created_by', 'verified_by', 'verification_date',
            'confidence_score', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

class KnowledgeBaseEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeBaseEntry
        fields = [
            'id', 'ticket', 'issue_type', 'description',
            'solution', 'category', 'tags', 'confidence_score',
            'verified', 'verified_by', 'verification_date',
            'created_at', 'updated_at', 'last_used', 'usage_count'
        ]
        read_only_fields = [
            'created_at', 'updated_at', 'last_used', 'usage_count'
        ]

class KnowledgeBaseEntryListSerializer(serializers.ModelSerializer):
    """
    A simplified serializer for listing KB entries
    """
    class Meta:
        model = KnowledgeBaseEntry
        fields = [
            'id', 'issue_type', 'category', 'confidence_score',
            'verified', 'usage_count', 'last_used'
        ]

class TicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = [
            'ticket_id', 'team', 'user', 'issue_type', 'status', 'description', 'screenshot',
            'assigned_to', 'category', 'tags', 'created_at', 'updated_at', 'agent_response', 'agent_processed',
            'first_ai_at', 'escalated_at', 'awaiting_response_from', 'last_message_at', 'last_message_by',
        ]
        read_only_fields = [
            'ticket_id', 'team', 'created_at', 'updated_at', 'agent_response', 'agent_processed',
            'first_ai_at', 'escalated_at', 'awaiting_response_from', 'last_message_at', 'last_message_by',
        ]

class TicketInteractionSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    class Meta:
        model = TicketInteraction
        fields = ['id', 'ticket', 'user', 'interaction_type', 'content', 'created_at']
        read_only_fields = ['id', 'created_at']


class ActionHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for action history audit trail.
    """
    ticket_id = serializers.IntegerField(source='ticket.ticket_id', read_only=True)
    rolled_back_by_username = serializers.CharField(source='rolled_back_by.username', read_only=True, allow_null=True)
    
    class Meta:
        model = ActionHistory
        fields = [
            'id', 'ticket', 'ticket_id', 'action_type', 'action_params',
            'executed_at', 'executed_by', 'confidence_score', 'agent_reasoning',
            'rollback_possible', 'rollback_steps', 'rolled_back', 'rolled_back_at',
            'rolled_back_by', 'rolled_back_by_username', 'rollback_reason',
            'before_state', 'after_state'
        ]
        read_only_fields = [
            'id', 'executed_at', 'rolled_back_at'
        ]


class ResolutionTemplateSerializer(serializers.ModelSerializer):
    """
    Full serializer for Resolution Templates with all fields.
    """
    success_rate = serializers.ReadOnlyField()
    avg_resolution_time = serializers.ReadOnlyField()
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    
    class Meta:
        model = ResolutionTemplate
        fields = [
            'id', 'name', 'description', 'category', 'issue_types', 'tags',
            'steps', 'estimated_time', 'created_by', 'created_by_username',
            'created_at', 'updated_at', 'use_count', 'success_count',
            'success_rate', 'avg_resolution_time', 'is_active',
            'is_ai_generated', 'custom_params'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'use_count', 'success_count',
            'success_rate', 'avg_resolution_time'
        ]


class ResolutionTemplateListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing templates (for UI dropdowns/lists).
    """
    success_rate = serializers.ReadOnlyField()
    
    class Meta:
        model = ResolutionTemplate
        fields = [
            'id', 'name', 'category', 'estimated_time',
            'use_count', 'success_rate', 'is_active'
        ]


class ApplyTemplateSerializer(serializers.Serializer):
    """
    Serializer for applying a template to a ticket.
    """
    template_id = serializers.UUIDField(required=True)
    custom_params = serializers.JSONField(required=False, default=dict)
    
    def validate_template_id(self, value):
        """Ensure template exists and is active."""
        try:
            template = ResolutionTemplate.objects.get(id=value, is_active=True)
        except ResolutionTemplate.DoesNotExist:
            raise serializers.ValidationError("Template not found or inactive")
        return value
