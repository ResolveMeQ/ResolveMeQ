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
    assigned_to_name = serializers.SerializerMethodField()
    team_name = serializers.SerializerMethodField()
    reporter_name = serializers.SerializerMethodField()
    is_internal_request = serializers.SerializerMethodField()
    external_references = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            'ticket_id', 'team', 'team_name', 'user', 'reporter_name', 'is_internal_request',
            'issue_type', 'status', 'description', 'screenshot',
            'reported_platform',
            'assigned_to', 'assigned_to_name', 'category', 'tags', 'created_at', 'updated_at',
            'agent_response', 'agent_processed',
            'first_ai_at', 'escalated_at', 'awaiting_response_from', 'last_message_at', 'last_message_by',
            'escalation_priority', 'claimed_at', 'sla_due_at', 'external_references',
        ]
        read_only_fields = [
            'ticket_id', 'team', 'created_at', 'updated_at', 'agent_response', 'agent_processed',
            'first_ai_at', 'escalated_at', 'awaiting_response_from', 'last_message_at', 'last_message_by',
            'escalation_priority', 'claimed_at', 'sla_due_at',
        ]

    def get_team_name(self, obj):
        """Lets ResolveMeQ platform agents tell customers apart in a cross-tenant queue."""
        if not obj.team_id:
            return None
        return obj.team.name

    def get_reporter_name(self, obj):
        if not obj.user_id:
            return None
        reporter = getattr(obj, "user", None)
        if reporter is None:
            from base.models import User
            reporter = User.objects.filter(pk=obj.user_id).first()
        if not reporter:
            return None
        return reporter.get_full_name() or reporter.email or reporter.username

    def get_is_internal_request(self, obj):
        request = self.context.get("request")
        if not request or not getattr(request.user, "is_authenticated", False):
            return False
        from tickets.scoping import is_internal_workspace_request

        return is_internal_workspace_request(request.user, obj)

    def get_assigned_to_name(self, obj):
        if not obj.assigned_to_id:
            return None
        agent = obj.assigned_to
        return agent.get_full_name() or agent.email or agent.username

    def get_external_references(self, obj):
        refs = getattr(obj, "_prefetched_objects_cache", {}).get("external_references")
        if refs is None:
            refs = obj.external_references.all()
        return [
            {
                "system": r.system,
                "external_id": r.external_id,
                "external_url": r.external_url,
                "metadata": r.metadata or {},
            }
            for r in refs
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
