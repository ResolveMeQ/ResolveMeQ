from rest_framework import serializers
from .models import (
    KnowledgeBaseArticle,
    LLMResponse,
    KBQuestion,
    KBAnswer,
    KBComment,
    KBAttachment,
)

class KnowledgeBaseArticleSerializer(serializers.ModelSerializer):
    helpfulness_score = serializers.FloatField(read_only=True)
    user_vote = serializers.SerializerMethodField()

    class Meta:
        model = KnowledgeBaseArticle
        fields = [
            'kb_id', 'title', 'content', 'tags', 'author', 'is_published', 'is_verified',
            'created_at', 'updated_at', 'views', 'helpful_votes', 'total_votes',
            'helpfulness_score', 'user_vote'
        ]
        read_only_fields = [
            'kb_id', 'created_at', 'updated_at', 'views',
            'helpful_votes', 'total_votes', 'helpfulness_score', 'user_vote'
        ]

    def get_user_vote(self, obj):
        request = self.context.get("request")
        if not request or not getattr(request, "user", None) or not request.user.is_authenticated:
            return None
        vote = obj.user_votes.filter(user=request.user).first()
        if not vote:
            return None
        return {"is_helpful": vote.is_helpful}

class LLMResponseSerializer(serializers.ModelSerializer):
    helpfulness_score = serializers.FloatField(read_only=True)
    related_kb_articles = KnowledgeBaseArticleSerializer(many=True, read_only=True)
    user_vote = serializers.SerializerMethodField()

    class Meta:
        model = LLMResponse
        fields = ['response_id', 'query', 'response', 'response_type', 'created_at',
                 'helpful_votes', 'total_votes', 'helpfulness_score', 
                 'related_kb_articles', 'ticket', 'user_vote']
        read_only_fields = ['response_id', 'created_at', 'helpful_votes', 
                           'total_votes', 'helpfulness_score', 'user_vote']

    def get_user_vote(self, obj):
        request = self.context.get("request")
        if not request or not getattr(request, "user", None) or not request.user.is_authenticated:
            return None
        vote = obj.user_votes.filter(user=request.user).first()
        if not vote:
            return None
        return {"is_helpful": vote.is_helpful}


class KBAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = KBAttachment
        fields = [
            "id",
            "original_name",
            "file_url",
            "content_type",
            "file_size",
            "created_at",
        ]
        read_only_fields = fields


class KBCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    attachments = KBAttachmentSerializer(many=True, read_only=True)
    attachment_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        write_only=True,
        required=False,
        default=list,
    )

    class Meta:
        model = KBComment
        fields = [
            "id",
            "body",
            "created_by",
            "author_name",
            "attachments",
            "attachment_ids",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "author_name", "attachments", "created_at", "updated_at"]

    def get_author_name(self, obj):
        user = getattr(obj, "created_by", None)
        if not user:
            return "Unknown"
        return (getattr(user, "get_full_name", lambda: "")() or getattr(user, "username", "User")).strip() or "User"

    def create(self, validated_data):
        # Handled in views after object creation.
        validated_data.pop("attachment_ids", None)
        return super().create(validated_data)


class KBAnswerSerializer(serializers.ModelSerializer):
    comments = KBCommentSerializer(many=True, read_only=True)
    author_name = serializers.SerializerMethodField()
    user_vote = serializers.SerializerMethodField()
    attachments = KBAttachmentSerializer(many=True, read_only=True)
    attachment_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        write_only=True,
        required=False,
        default=list,
    )

    class Meta:
        model = KBAnswer
        fields = [
            "id", "question", "body", "created_by", "author_name",
            "is_published", "is_accepted", "score", "comments", "attachments",
            "attachment_ids",
            "created_at", "updated_at", "user_vote"
        ]
        read_only_fields = [
            "id", "question", "created_by", "author_name", "is_accepted", "score",
            "comments", "attachments", "created_at", "updated_at", "user_vote"
        ]

    def get_author_name(self, obj):
        user = getattr(obj, "created_by", None)
        if not user:
            return "Unknown"
        return (getattr(user, "get_full_name", lambda: "")() or getattr(user, "username", "User")).strip() or "User"

    def get_user_vote(self, obj):
        request = self.context.get("request")
        if not request or not getattr(request, "user", None) or not request.user.is_authenticated:
            return None
        vote = obj.votes.filter(user=request.user).first()
        return vote.value if vote else None

    def create(self, validated_data):
        # Handled in views after object creation.
        validated_data.pop("attachment_ids", None)
        return super().create(validated_data)


class KBQuestionSerializer(serializers.ModelSerializer):
    answers = KBAnswerSerializer(many=True, read_only=True)
    comments = KBCommentSerializer(many=True, read_only=True)
    author_name = serializers.SerializerMethodField()
    user_vote = serializers.SerializerMethodField()
    has_accepted_answer = serializers.SerializerMethodField()
    duplicate_of_title = serializers.SerializerMethodField()
    attachments = KBAttachmentSerializer(many=True, read_only=True)
    attachment_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        write_only=True,
        required=False,
        default=list,
    )

    class Meta:
        model = KBQuestion
        fields = [
            "id", "title", "body", "tags", "created_by", "author_name",
            "is_published", "views", "score", "answer_count",
            "duplicate_of", "duplicate_of_title", "duplicate_note",
            "has_accepted_answer", "answers", "comments", "attachments", "attachment_ids",
            "created_at", "updated_at", "user_vote"
        ]
        read_only_fields = [
            "id", "created_by", "author_name", "views", "score", "answer_count",
            "duplicate_of_title", "has_accepted_answer", "answers", "comments", "attachments", "created_at", "updated_at", "user_vote"
        ]

    def get_author_name(self, obj):
        user = getattr(obj, "created_by", None)
        if not user:
            return "Unknown"
        return (getattr(user, "get_full_name", lambda: "")() or getattr(user, "username", "User")).strip() or "User"

    def get_user_vote(self, obj):
        request = self.context.get("request")
        if not request or not getattr(request, "user", None) or not request.user.is_authenticated:
            return None
        vote = obj.votes.filter(user=request.user).first()
        return vote.value if vote else None

    def get_has_accepted_answer(self, obj):
        return obj.answers.filter(is_accepted=True, is_published=True).exists()

    def get_duplicate_of_title(self, obj):
        if not obj.duplicate_of_id:
            return ""
        return obj.duplicate_of.title

    def create(self, validated_data):
        # Handled in views after object creation.
        validated_data.pop("attachment_ids", None)
        return super().create(validated_data)

    def validate_title(self, value):
        title = (value or "").strip()
        if len(title) < 15:
            raise serializers.ValidationError("Use a more descriptive title (at least 15 characters).")
        word_count = len([w for w in title.split() if w.strip()])
        if word_count < 4:
            raise serializers.ValidationError("Use at least 4 words so others can find this question.")
        return title