from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
import uuid


class KnowledgeBaseArticle(models.Model):
    kb_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    content = models.TextField()
    tags = models.JSONField(default=list)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="kb_articles",
    )
    is_published = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    views = models.IntegerField(default=0)
    helpful_votes = models.IntegerField(default=0)
    total_votes = models.IntegerField(default=0)

    def __str__(self):
        return self.title

    @property
    def helpfulness_score(self):
        if self.total_votes == 0:
            return 0
        return (self.helpful_votes / self.total_votes) * 100

    class Meta:
        ordering = ["-created_at"]


class LLMResponse(models.Model):
    RESPONSE_TYPES = [
        ('TICKET', 'Ticket Resolution'),
        ('KB', 'Knowledge Base'),
        ('GENERAL', 'General Query')
    ]

    response_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    query = models.TextField()
    response = models.TextField()
    response_type = models.CharField(max_length=20, choices=RESPONSE_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    helpful_votes = models.IntegerField(default=0)
    total_votes = models.IntegerField(default=0)
    related_kb_articles = models.ManyToManyField(KnowledgeBaseArticle, blank=True)
    ticket = models.ForeignKey('tickets.Ticket', on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"{self.response_type} - {self.created_at}"

    @property
    def helpfulness_score(self):
        if self.total_votes == 0:
            return 0
        return (self.helpful_votes / self.total_votes) * 100

    class Meta:
        ordering = ["-created_at"]


class KnowledgeBaseArticleVote(models.Model):
    article = models.ForeignKey(
        KnowledgeBaseArticle,
        on_delete=models.CASCADE,
        related_name="user_votes",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="kb_article_votes",
    )
    is_helpful = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("article", "user")]
        ordering = ["-updated_at"]


class LLMResponseVote(models.Model):
    response = models.ForeignKey(
        LLMResponse,
        on_delete=models.CASCADE,
        related_name="user_votes",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="llm_response_votes",
    )
    is_helpful = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("response", "user")]
        ordering = ["-updated_at"]


class KBQuestion(models.Model):
    title = models.CharField(max_length=300)
    body = models.TextField()
    tags = models.JSONField(default=list)
    duplicate_of = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="duplicates",
    )
    duplicate_note = models.CharField(max_length=300, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="kb_questions",
    )
    is_published = models.BooleanField(default=True)
    views = models.IntegerField(default=0)
    score = models.IntegerField(default=0)
    answer_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class KBAnswer(models.Model):
    question = models.ForeignKey(
        KBQuestion,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    body = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="kb_answers",
    )
    is_published = models.BooleanField(default=True)
    is_accepted = models.BooleanField(default=False)
    score = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_accepted", "-score", "created_at"]

    def __str__(self):
        return f"Answer #{self.pk} for question #{self.question_id}"


class KBComment(models.Model):
    question = models.ForeignKey(
        KBQuestion,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    answer = models.ForeignKey(
        KBAnswer,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    body = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="kb_comments",
    )
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        target = f"question {self.question_id}" if self.question_id else f"answer {self.answer_id}"
        return f"Comment on {target}"

    def clean(self):
        if not self.question_id and not self.answer_id:
            raise ValidationError("A comment must target either a question or an answer.")
        if self.question_id and self.answer_id:
            raise ValidationError("A comment cannot target both a question and an answer.")


class KBQuestionVote(models.Model):
    VOTE_CHOICES = ((1, "Upvote"), (-1, "Downvote"))
    question = models.ForeignKey(
        KBQuestion,
        on_delete=models.CASCADE,
        related_name="votes",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="kb_question_votes",
    )
    value = models.SmallIntegerField(choices=VOTE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("question", "user")]
        ordering = ["-updated_at"]


class KBAnswerVote(models.Model):
    VOTE_CHOICES = ((1, "Upvote"), (-1, "Downvote"))
    answer = models.ForeignKey(
        KBAnswer,
        on_delete=models.CASCADE,
        related_name="votes",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="kb_answer_votes",
    )
    value = models.SmallIntegerField(choices=VOTE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("answer", "user")]
        ordering = ["-updated_at"]


class KBAttachment(models.Model):
    question = models.ForeignKey(
        KBQuestion,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    answer = models.ForeignKey(
        KBAnswer,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    comment = models.ForeignKey(
        KBComment,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="kb_attachments",
    )
    original_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    file_url = models.URLField(max_length=1000)
    content_type = models.CharField(max_length=100, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.original_name} ({self.uploaded_by_id})"

    def clean(self):
        attached_targets = [bool(self.question_id), bool(self.answer_id), bool(self.comment_id)]
        if sum(attached_targets) > 1:
            raise ValidationError("Attachment can belong to only one target.")
