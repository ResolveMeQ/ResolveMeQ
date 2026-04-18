import logging
from django.contrib.auth import get_user_model
from django.db import DatabaseError, models
import requests
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

User = get_user_model()
logger = logging.getLogger(__name__)
# Create your models here.

class Ticket(models.Model):
    AWAITING_RESPONSE_CHOICES = [
        ("", "None"),
        ("support", "Support"),
        ("user", "User"),
    ]
    CATEGORY_CHOICES = [
        ("wifi", "Wi-Fi"),
        ("laptop", "Laptop"),
        ("vpn", "VPN"),
        ("printer", "Printer"),
        ("email", "Email"),
        ("software", "Software"),
        ("hardware", "Hardware"),
        ("network", "Network"),
        ("account", "Account"),
        ("access", "Access"),
        ("phone", "Phone"),
        ("server", "Server"),
        ("security", "Security"),
        ("cloud", "Cloud"),
        ("storage", "Storage"),
        ("other", "Other"),
    ]
    ticket_id = models.AutoField(primary_key=True)
    team = models.ForeignKey(
        "base.Team",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
        help_text="Workspace/team; set from creator's active team when applicable.",
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    issue_type = models.CharField(max_length=100)
    status = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)  # <-- Add this line
    screenshot = models.URLField(blank=True, null=True)  # Optional screenshot URL
    assigned_to = models.ForeignKey(
        User,
        related_name="assigned_tickets",
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default="other")
    tags = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    agent_response = models.JSONField(null=True, blank=True, help_text="Response from the AI agent analyzing this ticket")
    agent_processed = models.BooleanField(default=False, help_text="Whether the AI agent has processed this ticket")
    first_ai_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the ticket first received AI output (analyze task or first AI chat message).",
    )
    escalated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the ticket first moved to escalated status.",
    )
    awaiting_response_from = models.CharField(
        max_length=20,
        choices=AWAITING_RESPONSE_CHOICES,
        default="",
        blank=True,
        help_text="Conversation owner for next response: support or user.",
    )
    last_message_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the latest comment/message in the support thread.",
    )
    last_message_by = models.ForeignKey(
        User,
        related_name="last_ticket_messages",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="User who sent the latest comment/message.",
    )

    def __str__(self):
        return f"{self.issue_type} ({self.status})"

    def send_to_agent(self):
        """
        Sends the ticket to the AI agent for processing.
        Returns True if successful, False otherwise.
        """
        if self.agent_processed:
            return False

        try:
            agent_url = getattr(settings, 'AI_AGENT_URL', 'https://agent.resolvemeq.com/analyze/')
            payload = {
                'ticket_id': self.ticket_id,
                'issue_type': self.issue_type,
                'description': self.description,
                'category': self.category,
                'tags': self.tags,
                'user': {
                    'id': self.user.user_id,
                    'name': self.user.name,
                    'department': self.user.department
                }
            }

            response = requests.post(agent_url, json=payload)
            response.raise_for_status()

            self.agent_response = response.json()
            self.agent_processed = True
            self.save()
            return True

        except Exception as e:
            print(f"Error sending ticket {self.ticket_id} to AI agent: {str(e)}")
            return False

    def sync_to_knowledge_base(self):
        """
        Create or update a KnowledgeBaseArticle from this ticket when resolved.

        When the ticket has AI chat, **first** asks the FastAPI agent ``POST /tickets/kb-article/``
        to synthesize **Problem / Solution / Notes** markdown from the **full transcript**
        (best quality). If that fails or chat is too short, falls back to heuristics
        (``_kb_pick_final_assistant_text`` and related helpers), then Solution text, then
        analyze ``agent_response``.
        """
        from knowledge_base.models import KnowledgeBaseArticle

        if self.status != "resolved":
            return

        has_chat = _ticket_has_persisted_ai_chat(self)
        if not self.agent_response and not has_chat:
            return

        title = f"Resolved: {self.issue_type}"
        parts = [f"## Description\n{self.description or 'N/A'}"]
        ar = self.agent_response if isinstance(self.agent_response, dict) else {}

        if has_chat:
            synthesized = _kb_fetch_synthesized_kb_markdown(self)
            if synthesized:
                parts.append("\n" + synthesized.strip())
            else:
                from .chat_models import Conversation

                conv = Conversation.objects.filter(ticket=self).order_by("-updated_at").first()
                summary = (conv.summary or "").strip() if conv else ""
                if summary:
                    parts.append(f"\n## Summary\n{summary[:6000]}")

                final_text, final_msg = _kb_pick_final_assistant_text(self)
                meta_steps = _kb_metadata_steps_block(final_msg) or _kb_metadata_steps_from_recent_ticket(
                    self, prefer_message=final_msg
                )
                if final_text:
                    parts.append(f"\n## Resolution\n{final_text}")
                if meta_steps:
                    parts.append(f"\n## Steps\n{meta_steps}")

                used_chat_resolution = bool(final_text or meta_steps)

                if not used_chat_resolution:
                    sol_text = _kb_solution_text_for_ticket(self)
                    if sol_text:
                        parts.append(f"\n## Resolution\n{sol_text[:12000]}")
                        used_chat_resolution = True

                if not used_chat_resolution:
                    _kb_append_agent_analyze_sections(parts, self.agent_response)

            if isinstance(ar, dict):
                sol = ar.get("solution") or {}
                if isinstance(sol, dict) and sol.get("preventive_measures"):
                    parts.append("\n## Prevention")
                    for pm in (sol["preventive_measures"] or [])[:5]:
                        parts.append(f"- {pm}")
        else:
            _kb_append_agent_analyze_sections(parts, self.agent_response)

        content = "\n".join(parts)
        tags = [self.category] + (self.tags if self.tags else [])
        article, created = KnowledgeBaseArticle.objects.get_or_create(
            title=title,
            defaults={
                "content": content,
                "tags": tags,
            },
        )
        if not created:
            article.content = content
            article.tags = tags
            article.save()

    def save(self, *args, **kwargs):
        # If ticket is being marked as resolved and has agent_response, sync to KB and create Solution
        was_resolved = False
        if self.pk:
            orig = Ticket.objects.get(pk=self.pk)
            was_resolved = orig.status == "resolved"
        super().save(*args, **kwargs)
        if self.status == "resolved" and not was_resolved:
            if self.agent_response or _ticket_has_persisted_ai_chat(self):
                self.sync_to_knowledge_base()
            # Create or update Solution from agent_response (steps can be in solution.steps, resolution_steps, or steps)
            from solutions.models import Solution
            steps = None
            confidence = 0.0
            if isinstance(self.agent_response, dict):
                sol = self.agent_response.get("solution") or {}
                steps = (
                    self.agent_response.get("resolution_steps")
                    or self.agent_response.get("steps")
                    or (sol.get("steps") if isinstance(sol, dict) else None)
                )
                if steps and isinstance(steps, list):
                    steps = "\n".join(steps)
                confidence = float(self.agent_response.get("confidence", 0) or 0)
            if steps:
                Solution.objects.update_or_create(
                    ticket=self,
                    defaults={
                        "steps": steps,
                        "worked": True,
                        "created_by": self.user,
                        "confidence_score": confidence,
                    }
                )


def _kb_agent_kb_article_url():
    raw = getattr(
        settings,
        "AI_AGENT_URL",
        "https://agent.resolvemeq.net/tickets/analyze/",
    )
    u = str(raw).strip()
    if "kb-article" in u.lower():
        return u
    u2 = (
        u.replace("/tickets/analyze/", "/tickets/kb-article/")
        .replace("/tickets/analyze", "/tickets/kb-article")
    )
    if u2 != u:
        return u2
    u3 = u.replace("/api/analyze/", "/tickets/kb-article/").replace("/api/analyze", "/tickets/kb-article")
    if u3 != u:
        return u3
    base = u.rstrip("/")
    return f"{base}/tickets/kb-article/"


def _kb_conversation_history_payload(ticket):
    """Chronological transcript for the agent (user / assistant roles)."""
    from .chat_models import ChatMessage

    try:
        msgs = list(
            ChatMessage.objects.filter(conversation__ticket=ticket).order_by("created_at")[:120]
        )
    except DatabaseError:
        return []
    out = []
    for m in msgs:
        if m.sender_type == "user":
            role = "user"
        elif m.sender_type in ("ai", "system"):
            role = "assistant"
        else:
            continue
        t = (m.text or "").strip()
        if not t:
            continue
        if len(t) > 2000:
            t = t[:1997] + "..."
        out.append({"role": role, "text": t})
    return out


def _kb_fetch_synthesized_kb_markdown(ticket):
    """
    Full-transcript KB body via FastAPI ``/tickets/kb-article/`` (preferred over heuristics).
    """
    history = _kb_conversation_history_payload(ticket)
    if len(history) < 2:
        return None
    kb_url = _kb_agent_kb_article_url()
    if "kb-article" not in kb_url.lower():
        logger.warning("KB article URL missing kb-article path (AI_AGENT_URL may be misconfigured)")
        return None
    try:
        from base.agent_http import get_agent_service_headers

        resp = requests.post(
            kb_url,
            json={
                "ticket_id": ticket.ticket_id,
                "issue_type": ticket.issue_type or "",
                "description": ticket.description or "",
                "category": ticket.category or "",
                "conversation_history": history,
            },
            headers=get_agent_service_headers(),
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json() or {}
        md = (data.get("markdown") or "").strip()
        if len(md) < 40:
            return None
        return md[:24000]
    except Exception as e:
        logger.warning(
            "KB synthesis from agent failed ticket_id=%s: %s",
            getattr(ticket, "ticket_id", None),
            e,
        )
        return None


def _ticket_has_persisted_ai_chat(ticket):
    """
    True if any persisted AI chat row exists for this ticket.

    Tests (or partial DBs) may not migrate chat tables; treat as "no chat" instead of
    erroring during Ticket.save() / KB sync.
    """
    from .chat_models import ChatMessage

    try:
        return ChatMessage.objects.filter(
            conversation__ticket=ticket,
            sender_type="ai",
        ).exists()
    except DatabaseError:
        return False


def _kb_pick_final_assistant_text(ticket):
    """
    Pick one assistant ``ChatMessage`` for the KB **Resolution** body.

    The chronologically **last** AI message is often wrong (thanks, errors, short
    follow-ups). We use explicit product signals first, then a score, then recency
    as a tie-breaker (newer wins when scores match).
    """
    from .chat_models import ChatMessage

    fallback_needle = "having trouble processing"
    try:
        candidates = list(
            ChatMessage.objects.filter(
                conversation__ticket=ticket,
                sender_type="ai",
            )
            .exclude(text="")
            .order_by("-created_at")[:24]
        )
    except DatabaseError:
        return None, None
    if not candidates:
        return None, None
    pool = [m for m in candidates if fallback_needle not in (m.text or "").lower()]
    if not pool:
        pool = candidates

    typed = [m for m in pool if m.message_type in ("steps", "solution")]
    if typed:
        picked = max(typed, key=lambda m: m.created_at)
        text = (picked.text or "").strip()
        return (text[:12000] if text else None), picked

    helpful = [m for m in pool if m.was_helpful is True]
    if helpful:
        picked = max(helpful, key=lambda m: m.created_at)
        text = (picked.text or "").strip()
        return (text[:12000] if text else None), picked

    picked = max(pool, key=lambda m: (_kb_chat_message_kb_score(m), m.created_at.timestamp()))
    text = (picked.text or "").strip()
    return (text[:12000] if text else None), picked


def _kb_chat_message_kb_score(message):
    """
    Higher = more likely substantive resolution (vs. closing line or soft nudge).
    """
    text = (message.text or "").strip()
    low = text.lower()
    L = len(text)
    score = 0.0
    if _kb_metadata_steps_block(message):
        score += 120.0
    if message.message_type in ("steps", "solution"):
        score += 80.0
    score += min(L, 3500) * 0.04
    if message.was_helpful is True:
        score += 60.0
    if message.was_helpful is False:
        score -= 40.0
    if L < 180:
        closings = (
            "you're welcome",
            "youre welcome",
            "glad i could",
            "glad to help",
            "happy to help",
            "anytime",
            "let me know if you need",
            "let me know if anything",
            "feel free to reach out",
        )
        if any(c in low for c in closings):
            score -= 200.0
    if L < 35:
        score -= 120.0
    data = message.agent_response_data if isinstance(message.agent_response_data, dict) else {}
    ra = (data.get("recommended_action") or "").lower()
    if ra in ("request_clarification", "clarification_only", "clarification") and L < 450:
        score -= 90.0
    return score


def _kb_metadata_steps_block(message):
    if not message:
        return ""
    md = message.metadata if isinstance(message.metadata, dict) else {}
    raw = md.get("steps") or md.get("immediate_actions")
    if not raw:
        return ""
    if isinstance(raw, str) and raw.strip():
        return raw.strip()[:4000]
    if isinstance(raw, list):
        lines = []
        for i, s in enumerate(raw[:15], 1):
            if s:
                lines.append(f"{i}. {s}")
        return "\n".join(lines)
    return ""


def _kb_metadata_steps_from_recent_ticket(ticket, prefer_message=None):
    """
    Prefer structured steps on the chosen resolution message; otherwise newest AI
    message that has metadata steps (body text may come from a different turn).
    """
    if prefer_message:
        blk = _kb_metadata_steps_block(prefer_message)
        if blk:
            return blk
    from .chat_models import ChatMessage

    try:
        recent = ChatMessage.objects.filter(
            conversation__ticket=ticket,
            sender_type="ai",
        ).order_by("-created_at")[:15]
    except DatabaseError:
        return ""
    for m in recent:
        blk = _kb_metadata_steps_block(m)
        if blk:
            return blk
    return ""


def _kb_solution_text_for_ticket(ticket):
    from solutions.models import Solution

    row = Solution.objects.filter(ticket=ticket).first()
    if not row:
        return ""
    return (row.steps or "").strip()


def _kb_append_agent_analyze_sections(parts, agent_response):
    """Legacy path: article body from initial analyze JSON only."""
    if not agent_response:
        return
    if isinstance(agent_response, dict):
        if agent_response.get("reasoning"):
            parts.append(f"\n## Analysis\n{agent_response['reasoning']}")
        sol = agent_response.get("solution") or {}
        if isinstance(sol, dict):
            steps = sol.get("steps") or sol.get("immediate_actions") or []
            if steps:
                parts.append("\n## Resolution Steps")
                for i, s in enumerate(steps[:10], 1):
                    parts.append(f"{i}. {s}")
            if sol.get("preventive_measures"):
                parts.append("\n## Prevention")
                for pm in (sol["preventive_measures"] or [])[:5]:
                    parts.append(f"- {pm}")
        elif isinstance(sol, list):
            parts.append("\n## Resolution Steps")
            for i, s in enumerate(sol[:10], 1):
                parts.append(f"{i}. {s}")
    else:
        parts.append(f"\n## Agent Response\n{str(agent_response)[:2000]}")


class AgentConfidenceLog(models.Model):
    """
    Snapshot of LLM-reported confidence for calibration and analytics (analyze vs chat).
    """

    SOURCE_ANALYZE = "analyze"
    SOURCE_CHAT = "chat"
    SOURCE_CHOICES = [
        (SOURCE_ANALYZE, "Analyze"),
        (SOURCE_CHAT, "Chat"),
    ]

    id = models.AutoField(primary_key=True)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="confidence_logs")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, db_index=True)
    confidence = models.FloatField(null=True, blank=True)
    recommended_action = models.CharField(max_length=120, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["ticket", "created_at"]),
            models.Index(fields=["source", "created_at"]),
        ]

    def __str__(self):
        return f"{self.source} conf={self.confidence} ticket={self.ticket_id}"


class TicketInteraction(models.Model):
    """
    Tracks all user and agent interactions related to a ticket for analytics and knowledge base enrichment.
    Types include:
    - clarification: User provides more info or clarification via Slack modal.
    - feedback: User rates the agent's response (helpful/not helpful).
    - agent_response: The AI agent's response to the ticket is logged.
    - user_message: Ticket creation or user-initiated messages.
    This model enables auditing, analytics, and future knowledge extraction from real support conversations.
    """
    INTERACTION_TYPES = [
        ("clarification", "Clarification"),
        ("feedback", "Feedback"),
        ("agent_response", "Agent Response"),
        ("user_message", "User Message"),
    ]
    id = models.AutoField(primary_key=True)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    interaction_type = models.CharField(max_length=50, choices=INTERACTION_TYPES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.interaction_type} for Ticket {self.ticket.ticket_id} by {self.user.user_id}"


class TicketResolution(models.Model):
    """
    Track resolution outcomes for learning and validation.
    Enables feedback loop validation to verify autonomous resolutions actually worked.
    """
    
    ticket = models.OneToOneField(
        Ticket, 
        on_delete=models.CASCADE,
        related_name='resolution_tracking'
    )
    autonomous_action = models.CharField(max_length=50, help_text="Type of autonomous action taken")
    
    # User Feedback
    resolution_confirmed = models.BooleanField(
        null=True, 
        blank=True,
        help_text="User confirmed resolution worked (True) or failed (False)"
    )
    user_feedback_text = models.TextField(blank=True)
    satisfaction_score = models.IntegerField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="User satisfaction rating 1-5 stars"
    )
    
    # Follow-up Tracking
    followup_sent_at = models.DateTimeField(null=True, blank=True)
    response_received_at = models.DateTimeField(null=True, blank=True)
    
    # Reopening Tracking
    reopened = models.BooleanField(default=False)
    reopened_at = models.DateTimeField(null=True, blank=True)
    reopened_reason = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ticket_resolution'
        indexes = [
            models.Index(fields=['autonomous_action', 'resolution_confirmed']),
            models.Index(fields=['satisfaction_score']),
        ]
    
    @property
    def was_successful(self):
        """Did this resolution actually work?"""
        if self.reopened:
            return False
        if self.resolution_confirmed is True:
            return True
        if self.satisfaction_score and self.satisfaction_score >= 4:
            return True
        return None  # Unknown
    
    def __str__(self):
        return f"Resolution tracking for Ticket #{self.ticket.ticket_id}"


class ActionHistory(models.Model):
    """
    Audit trail for all autonomous actions with rollback capability.
    Enables compliance, debugging, and recovery from incorrect agent decisions.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='action_history')
    
    # Action Details
    action_type = models.CharField(max_length=50, help_text="AUTO_RESOLVE, ESCALATE, etc.")
    action_params = models.JSONField(default=dict)
    executed_at = models.DateTimeField(auto_now_add=True)
    executed_by = models.CharField(max_length=50, default='autonomous_agent')
    
    # AI Decision Context
    confidence_score = models.FloatField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    agent_reasoning = models.TextField(blank=True)
    
    # Rollback Capability
    rollback_possible = models.BooleanField(default=False)
    rollback_steps = models.JSONField(null=True, blank=True)
    rolled_back = models.BooleanField(default=False)
    rolled_back_at = models.DateTimeField(null=True, blank=True)
    rolled_back_by = models.ForeignKey(
        User, 
        null=True, 
        blank=True,
        on_delete=models.SET_NULL,
        related_name='rollbacks_performed'
    )
    rollback_reason = models.TextField(blank=True)
    
    # State Snapshots for Rollback
    before_state = models.JSONField(null=True, blank=True)
    after_state = models.JSONField(null=True, blank=True)
    
    class Meta:
        db_table = 'action_history'
        ordering = ['-executed_at']
        indexes = [
            models.Index(fields=['ticket', 'action_type']),
            models.Index(fields=['executed_at']),
            models.Index(fields=['rolled_back']),
        ]
    
    def __str__(self):
        return f"{self.action_type} on Ticket #{self.ticket.ticket_id} at {self.executed_at}"


class ResolutionTemplate(models.Model):
    """
    Reusable resolution templates for common IT issues.
    Tracks success rates and usage statistics.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, help_text="Template name (e.g., 'Email Sync - Outlook')")
    description = models.TextField(help_text="Description of when to use this template")
    
    # Categorization
    category = models.CharField(
        max_length=30, 
        choices=Ticket.CATEGORY_CHOICES,
        help_text="Primary category this template applies to"
    )
    issue_types = models.JSONField(
        default=list,
        help_text="List of issue types this template can resolve"
    )
    tags = models.JSONField(default=list, blank=True, help_text="Tags for filtering")
    
    # Resolution steps
    steps = models.JSONField(
        help_text="Array of resolution steps: [{step: 1, action: '...', description: '...'}]"
    )
    estimated_time = models.CharField(
        max_length=50,
        default="10 minutes",
        help_text="Estimated time to complete (e.g., '5-10 minutes')"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_templates',
        help_text="User who created this template"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Usage statistics
    use_count = models.IntegerField(
        default=0,
        help_text="Number of times this template has been applied"
    )
    success_count = models.IntegerField(
        default=0,
        help_text="Number of successful resolutions using this template"
    )
    
    # Flags
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this template is active and can be used"
    )
    is_ai_generated = models.BooleanField(
        default=False,
        help_text="Whether this template was generated by AI"
    )
    
    # Optional parameters
    custom_params = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom parameters that can be filled when applying template"
    )
    
    class Meta:
        db_table = 'resolution_templates'
        ordering = ['-use_count', '-created_at']
        indexes = [
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['use_count']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.category})"
    
    @property
    def success_rate(self):
        """Calculate success rate as a percentage."""
        if self.use_count == 0:
            return 0.0
        return round((self.success_count / self.use_count) * 100, 1)
    
    @property
    def avg_resolution_time(self):
        """Return the estimated time."""
        return self.estimated_time
    
    def increment_usage(self, success=True):
        """Increment usage count and optionally success count."""
        self.use_count += 1
        if success:
            self.success_count += 1
        self.save(update_fields=['use_count', 'success_count'])
