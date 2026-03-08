from django.conf import settings
from django.db import models
from tickets.models import Ticket
from django.core.validators import MinValueValidator, MaxValueValidator

User = settings.AUTH_USER_MODEL

class Solution(models.Model):
    solution_id = models.AutoField(primary_key=True)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    steps = models.TextField()
    worked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_solutions'
    )
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_solutions'
    )
    verification_date = models.DateTimeField(null=True, blank=True)
    confidence_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence score of the solution (0.0 to 1.0)"
    )

    def __str__(self):
        return f"Solution for Ticket {self.ticket.ticket_id}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # When solution is marked as worked, create/update KB entry (for new and existing)
        if self.worked and self.ticket_id:
            tags = getattr(self.ticket, 'tags', None)
            if tags is None or not isinstance(tags, list):
                tags = []
            KnowledgeBaseEntry.objects.update_or_create(
                ticket=self.ticket,
                defaults={
                    'issue_type': self.ticket.issue_type or '',
                    'description': self.ticket.description or '',
                    'solution': self.steps,
                    'category': self.ticket.category or 'other',
                    'tags': tags,
                    'confidence_score': self.confidence_score,
                    'verified': bool(self.verified_by),
                    'verified_by': self.verified_by,
                    'verification_date': self.verification_date
                }
            )

class KnowledgeBaseEntry(models.Model):
    ticket = models.OneToOneField(
        Ticket,
        on_delete=models.CASCADE,
        related_name='kb_entry',
        null=True,
        blank=True,
        help_text="Reference to the original ticket (if this entry came from a ticket)"
    )
    issue_type = models.CharField(max_length=100)
    description = models.TextField()
    solution = models.TextField()
    category = models.CharField(max_length=30, choices=Ticket.CATEGORY_CHOICES, default="other")
    tags = models.JSONField(default=list, blank=True)
    confidence_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence score of the solution (0.0 to 1.0)"
    )
    verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_kb_entries'
    )
    verification_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_used = models.DateTimeField(null=True, blank=True)
    usage_count = models.IntegerField(default=0)

    def __str__(self):
        return f"KB Entry: {self.issue_type}"

    class Meta:
        verbose_name = "Knowledge Base Entry"
        verbose_name_plural = "Knowledge Base Entries"
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['issue_type']),
            models.Index(fields=['confidence_score']),
            models.Index(fields=['verified']),
        ]
