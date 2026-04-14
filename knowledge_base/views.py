from django.db.models import Q, Count, Sum, Case, When, IntegerField, F, FloatField, Prefetch, Exists, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.conf import settings
from django.core.files.storage import default_storage
from django.utils.text import get_valid_filename
from django.utils.text import slugify
from django.http import HttpResponse
from pathlib import Path
import uuid
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes, parser_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from .models import (
    KnowledgeBaseArticle,
    LLMResponse,
    KnowledgeBaseArticleVote,
    LLMResponseVote,
    KBQuestion,
    KBAnswer,
    KBComment,
    KBQuestionVote,
    KBAnswerVote,
    KBAttachment,
)
from .serializers import (
    KnowledgeBaseArticleSerializer,
    LLMResponseSerializer,
    KBQuestionSerializer,
    KBAnswerSerializer,
    KBCommentSerializer,
    KBAttachmentSerializer,
)
from .services import KnowledgeBaseService
import logging

logger = logging.getLogger(__name__)


def _get_public_urls(request):
    """
    Resolve canonical public domains.
    Defaults match production split-domain setup:
    - landing/marketing: resolvemeq.net
    - app/community: app.resolvemeq.net
    """
    default_app = "https://app.resolvemeq.net"
    default_marketing = "https://resolvemeq.net"

    app_base = (getattr(settings, "PUBLIC_APP_URL", "") or default_app).rstrip("/")
    marketing_base = (getattr(settings, "PUBLIC_MARKETING_URL", "") or default_marketing).rstrip("/")

    # In local/dev keep current host when explicit env values are absent.
    host = request.get_host() or ""
    if not getattr(settings, "PUBLIC_APP_URL", "") and "localhost" in host:
        app_base = request.build_absolute_uri("/").rstrip("/")
    if not getattr(settings, "PUBLIC_MARKETING_URL", "") and "localhost" in host:
        marketing_base = request.build_absolute_uri("/").rstrip("/")

    return app_base, marketing_base


def _bool_from_input(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        low = value.strip().lower()
        if low in {"true", "1", "yes", "y"}:
            return True
        if low in {"false", "0", "no", "n"}:
            return False
    return None


def _article_queryset_for_request(request):
    qs = KnowledgeBaseArticle.objects.all()
    if not request.user.is_authenticated:
        qs = qs.filter(is_published=True)
    return qs


_ATTACHMENT_MAX_BYTES = 10 * 1024 * 1024
_ATTACHMENT_ALLOWED_CT = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "application/pdf",
        "text/plain",
        "text/markdown",
        "application/json",
    }
)
_ATTACHMENT_ALLOWED_EXT = frozenset(
    {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".txt", ".md", ".json", ".log"}
)


def _attachment_upload_error(uploaded):
    if uploaded.size > _ATTACHMENT_MAX_BYTES:
        return "Attachment too large (max 10 MB)."
    content_type = (getattr(uploaded, "content_type", None) or "").split(";")[0].strip().lower()
    if content_type and content_type not in _ATTACHMENT_ALLOWED_CT:
        return "Unsupported file type."
    ext = Path(uploaded.name or "").suffix.lower()
    if ext and ext not in _ATTACHMENT_ALLOWED_EXT:
        return "Unsupported file extension."
    return None


def _create_in_app_notification(*, user, title, message, link, kind=None):
    """Best-effort in-app notification helper."""
    if not user:
        return
    try:
        from base.models import InAppNotification

        InAppNotification.objects.create(
            user=user,
            type=kind or InAppNotification.Type.INFO,
            title=(title or "")[:255],
            message=(message or "")[:2000],
            link=(link or "")[:500],
        )
    except Exception as exc:
        logger.warning("Failed to create KB in-app notification: %s", exc)


def _community_pref_enabled(user, field_name, default=True):
    """Read a user's community notification preference with a safe fallback."""
    if not user:
        return False
    try:
        from base.models import UserPreferences

        value = (
            UserPreferences.objects.filter(user=user)
            .values_list(field_name, flat=True)
            .first()
        )
        return default if value is None else bool(value)
    except Exception:
        return default


def _annotate_community_question_list_qs(queryset, request):
    """select_related + vote/has-accepted annotations to avoid N+1 on list responses."""
    queryset = queryset.select_related("created_by", "duplicate_of")
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        vote_sq = KBQuestionVote.objects.filter(
            question_id=OuterRef("pk"),
            user_id=user.id,
        ).values("value")[:1]
        queryset = queryset.annotate(_my_question_vote=Subquery(vote_sq))
    queryset = queryset.annotate(
        _has_accepted_answer_flag=Exists(
            KBAnswer.objects.filter(
                question_id=OuterRef("pk"),
                is_accepted=True,
                is_published=True,
            )
        )
    )
    return queryset


def _prefetch_community_question_detail(queryset, user):
    """
    Prefetch answers → comments, attachments, votes and question-level relations
    for KBQuestionSerializer without per-row EXISTS / vote queries.
    """
    queryset = queryset.select_related("created_by", "duplicate_of")
    q_votes = KBQuestionVote.objects.none()
    a_votes = KBAnswerVote.objects.none()
    if user and getattr(user, "is_authenticated", False):
        q_votes = KBQuestionVote.objects.filter(user_id=user.id)
        a_votes = KBAnswerVote.objects.filter(user_id=user.id)
    # Match default related managers (no is_published filter) so list/detail payloads stay as before.
    answers_qs = (
        KBAnswer.objects.all()
        .select_related("created_by")
        .order_by("-is_accepted", "-score", "created_at")
        .prefetch_related(
            Prefetch("votes", queryset=a_votes),
            Prefetch(
                "comments",
                queryset=KBComment.objects.all()
                .select_related("created_by")
                .prefetch_related("attachments"),
            ),
            "attachments",
        )
    )
    comment_qs = KBComment.objects.all().select_related("created_by").prefetch_related("attachments")
    return queryset.prefetch_related(
        Prefetch("answers", queryset=answers_qs),
        Prefetch("comments", queryset=comment_qs),
        Prefetch("votes", queryset=q_votes),
        "attachments",
    )


def _notify_new_question_to_workspace_members(question, actor):
    """
    Notify relevant teammates when a new community question is created.
    Scope: actor's active team if set; else teams where actor is owner/member.
    """
    if not question or not actor:
        return
    try:
        from base.models import Team, User, UserPreferences, InAppNotification

        actor_pref = UserPreferences.objects.filter(user=actor).select_related("active_team").first()
        if actor_pref and actor_pref.active_team_id:
            team_ids = [actor_pref.active_team_id]
        else:
            team_ids = list(
                Team.objects.filter(Q(owner=actor) | Q(members=actor))
                .values_list("id", flat=True)
                .distinct()
            )
        if not team_ids:
            return

        recipients = (
            User.objects.filter(Q(owned_teams__id__in=team_ids) | Q(teams__id__in=team_ids), is_active=True)
            .exclude(id=actor.id)
            .distinct()
        )

        actor_name = actor.get_full_name() or actor.email or actor.username or "A teammate"
        for recipient in recipients:
            if not _community_pref_enabled(recipient, "community_new_questions", default=True):
                continue
            InAppNotification.objects.create(
                user=recipient,
                type=InAppNotification.Type.INFO,
                title="New community question",
                message=f"{actor_name} asked: {question.title}",
                link=f"/knowledge-base?view=community&question={question.id}",
            )
    except Exception as exc:
        logger.warning("Failed to notify workspace members of new question: %s", exc)


def _parse_attachment_ids(raw):
    if raw is None:
        return []
    if isinstance(raw, list):
        values = raw
    elif isinstance(raw, str):
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        values = parts
    else:
        return []
    parsed = []
    for v in values:
        try:
            parsed.append(int(v))
        except (TypeError, ValueError):
            continue
    # Preserve order, remove duplicates
    seen = set()
    deduped = []
    for item in parsed:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _attach_uploaded_files(*, attachment_ids, user, question=None, answer=None, comment=None):
    if not attachment_ids:
        return
    attachments = list(
        KBAttachment.objects.filter(id__in=attachment_ids, uploaded_by=user).select_for_update()
    )
    if len(attachments) != len(set(attachment_ids)):
        raise ValueError("Some attachments were not found or not owned by user.")
    for attachment in attachments:
        if attachment.question_id or attachment.answer_id or attachment.comment_id:
            raise ValueError("One or more attachments are already linked.")
    for attachment in attachments:
        attachment.question = question
        attachment.answer = answer
        attachment.comment = comment
        attachment.save(update_fields=["question", "answer", "comment"])


class KnowledgeBaseArticleViewSet(viewsets.ModelViewSet):
    queryset = KnowledgeBaseArticle.objects.all()
    serializer_class = KnowledgeBaseArticleSerializer
    lookup_field = 'kb_id'

    def get_permissions(self):
        if self.action in {"list", "retrieve", "search"}:
            return [AllowAny()]
        if self.action == "rate":
            return [IsAuthenticated()]
        return [IsAuthenticated()]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    @action(detail=False, methods=['post'])
    def search(self, request):
        query = (request.data.get('query') or '').strip().lower()
        if not query:
            return Response({'error': 'Query parameter is required'}, status=status.HTTP_400_BAD_REQUEST)

        # SQLite-compatible search: filter in Python for tags, then rank.
        base_articles = list(_article_queryset_for_request(request))
        articles = [a for a in base_articles if (
            query in a.title.lower() or
            query in a.content.lower() or
            any(query in str(tag).lower() for tag in a.tags)
        )]
        articles = sorted(
            articles,
            key=lambda a: (
                -(a.helpfulness_score if a.total_votes else 0),
                -a.helpful_votes,
                -a.views,
                -(a.updated_at.timestamp() if a.updated_at else 0),
            ),
        )
        serializer = self.get_serializer(articles, many=True)
        return Response({'results': serializer.data})

    def get_queryset(self):
        queryset = _article_queryset_for_request(self.request).annotate(
            helpful_ratio=Case(
                When(total_votes__gt=0, then=(100.0 * F("helpful_votes")) / F("total_votes")),
                default=0.0,
                output_field=FloatField(),
            )
        )
        q = self.request.query_params.get('q', '').strip()
        if q:
            queryset = queryset.filter(
                Q(title__icontains=q) | Q(content__icontains=q)
            )
        tags = self.request.query_params.get('tags')
        if tags:
            tag = tags.lower()
            queryset = [
                a for a in queryset if tag in [str(t).lower() for t in (a.tags or [])]
            ]
            return sorted(
                queryset,
                key=lambda a: (
                    -(a.helpfulness_score if a.total_votes else 0),
                    -a.helpful_votes,
                    -a.views,
                    -(a.updated_at.timestamp() if a.updated_at else 0),
                ),
            )
        return queryset

    @action(detail=True, methods=['post'])
    def rate(self, request, kb_id=None):
        article = self.get_object()
        is_helpful = _bool_from_input(request.data.get('is_helpful', None))
        if is_helpful is None:
            return Response({'error': 'is_helpful parameter is required'}, status=status.HTTP_400_BAD_REQUEST)

        vote, _ = KnowledgeBaseArticleVote.objects.update_or_create(
            article=article,
            user=request.user,
            defaults={"is_helpful": is_helpful},
        )
        agg = article.user_votes.aggregate(
            total=Count("id"),
            helpful=Count("id", filter=Q(is_helpful=True)),
        )
        article.total_votes = agg["total"] or 0
        article.helpful_votes = agg["helpful"] or 0
        article.save(update_fields=["total_votes", "helpful_votes", "updated_at"])

        return Response({'status': 'success', 'is_helpful': vote.is_helpful})

class LLMResponseViewSet(viewsets.ModelViewSet):
    queryset = LLMResponse.objects.all()
    serializer_class = LLMResponseSerializer
    lookup_field = 'response_id'

    def get_permissions(self):
        if self.action in {"list", "retrieve", "search"}:
            return [AllowAny()]
        if self.action == "rate":
            return [IsAuthenticated()]
        return [IsAuthenticated()]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def create(self, request, *args, **kwargs):
        try:
            response = KnowledgeBaseService.store_llm_response(
                query=request.data.get('query'),
                response=request.data.get('response'),
                response_type=request.data.get('response_type'),
                ticket=request.data.get('ticket'),
                related_kb_articles=request.data.get('related_kb_articles')
            )
            serializer = self.get_serializer(response)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error creating LLM response: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def rate(self, request, response_id=None):
        try:
            response = self.get_object()
            is_helpful = _bool_from_input(request.data.get('is_helpful'))
            
            if is_helpful is None:
                return Response({'error': 'is_helpful parameter is required'}, status=status.HTTP_400_BAD_REQUEST)

            updated_response = KnowledgeBaseService.update_response_rating(
                response.response_id,
                is_helpful,
                user=request.user,
            )
            serializer = self.get_serializer(updated_response)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error rating LLM response: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def search(self, request):
        query = request.data.get('query', '')
        if not query:
            return Response({'error': 'Query parameter is required'}, status=status.HTTP_400_BAD_REQUEST)

        responses = KnowledgeBaseService.get_related_responses(query)
        serializer = self.get_serializer(responses, many=True)
        return Response({'results': serializer.data})

# API endpoints for FastAPI agent access
@api_view(['GET'])
@permission_classes([AllowAny])  # You can add authentication later
def kb_articles_for_agent(request):
    """
    Public API endpoint for FastAPI agent to access Knowledge Base articles.
    Returns all articles with basic fields for AI processing.
    """
    articles = KnowledgeBaseArticle.objects.filter(is_published=True).values(
        'kb_id', 'title', 'content', 'tags',
        'created_at', 'updated_at', 'helpful_votes', 'total_votes', 'views'
    )
    return Response(list(articles))

@api_view(['POST'])
@permission_classes([AllowAny])  # You can add authentication later
def search_kb_for_agent(request):
    """
    Search Knowledge Base articles for FastAPI agent.
    POST body: {"query": "search term", "limit": 10}
    """
    query = request.data.get('query', '')
    limit = request.data.get('limit', 10)
    
    if not query:
        return Response({'error': 'Query parameter is required'}, status=400)
    
    articles_qs = KnowledgeBaseArticle.objects.filter(
        is_published=True
    ).filter(
        Q(title__icontains=query) |
        Q(content__icontains=query)
    ).annotate(
        helpful_ratio=Case(
            When(total_votes__gt=0, then=(100.0 * F("helpful_votes")) / F("total_votes")),
            default=0.0,
            output_field=FloatField(),
        )
    ).order_by('-helpful_ratio', '-helpful_votes', '-views', '-updated_at')[:limit]

    community_questions = KBQuestion.objects.filter(
        is_published=True
    ).filter(
        Q(title__icontains=query) | Q(body__icontains=query)
    ).annotate(
        comment_count=Count("comments", distinct=True),
    ).order_by("-score", "-answer_count", "-views", "-updated_at")[:limit]
    
    serializer = KnowledgeBaseArticleSerializer(articles_qs, many=True)
    community_serialized = [
        {
            "kb_id": f"qna-{q.id}",
            "id": q.id,
            "title": q.title,
            "content": q.body,
            "tags": q.tags or [],
            "category": "community_qna",
            "created_at": q.created_at,
            "updated_at": q.updated_at,
            "helpful_votes": max(q.score, 0),
            "total_votes": abs(q.score) if q.score != 0 else 1,
            "views": q.views,
            "answer_count": q.answer_count,
            "comment_count": q.comment_count,
            "source_type": "community_question",
        }
        for q in community_questions
    ]
    merged_results = [*serializer.data, *community_serialized]
    return Response({
        'query': query,
        'results': merged_results,
        'count': len(merged_results)
    })

@api_view(['GET'])
@permission_classes([AllowAny])  # You can add authentication later
def kb_article_by_id(request, kb_id):
    """
    Get specific Knowledge Base article by ID for FastAPI agent.
    """
    try:
        article = KnowledgeBaseArticle.objects.get(kb_id=kb_id, is_published=True)
        serializer = KnowledgeBaseArticleSerializer(article)
        return Response(serializer.data)
    except KnowledgeBaseArticle.DoesNotExist:
        return Response({'error': 'Article not found'}, status=404)


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def community_questions(request):
    if request.method == "POST":
        if not request.user.is_authenticated:
            return Response({"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
        duplicate_of = request.data.get("duplicate_of")
        if duplicate_of not in (None, "", "null"):
            try:
                dup_id = int(duplicate_of)
            except (TypeError, ValueError):
                return Response({"error": "duplicate_of must be a valid question id."}, status=status.HTTP_400_BAD_REQUEST)
            if not KBQuestion.objects.filter(id=dup_id, is_published=True).exists():
                return Response({"error": "Selected duplicate target does not exist."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = KBQuestionSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            question = serializer.save(created_by=request.user)
            attachment_ids = serializer.validated_data.get("attachment_ids", [])
            try:
                _attach_uploaded_files(attachment_ids=attachment_ids, user=request.user, question=question)
            except ValueError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            _notify_new_question_to_workspace_members(question, request.user)
            question = (
                _prefetch_community_question_detail(
                    KBQuestion.objects.filter(id=question.id),
                    request.user,
                ).first()
                or question
            )
            return Response(
                KBQuestionSerializer(question, context={"request": request}).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    queryset = KBQuestion.objects.all()
    if not request.user.is_authenticated:
        queryset = queryset.filter(is_published=True)
    q = (request.query_params.get("q") or "").strip()
    if q:
        queryset = queryset.filter(Q(title__icontains=q) | Q(body__icontains=q))
    queryset = _annotate_community_question_list_qs(queryset, request)
    queryset = _prefetch_community_question_detail(queryset, getattr(request, "user", None))

    tag = (request.query_params.get("tag") or "").strip().lower()
    filter_by = (request.query_params.get("filter") or "all").strip().lower()
    if tag:
        queryset = [item for item in queryset if tag in [str(t).lower() for t in (item.tags or [])]]
    if isinstance(queryset, list):
        if filter_by == "unanswered":
            queryset = [item for item in queryset if item.answer_count == 0]
        elif filter_by in {"accepted", "has_accepted"}:
            queryset = [item for item in queryset if getattr(item, "_has_accepted_answer_flag", False)]
    else:
        if filter_by == "unanswered":
            queryset = queryset.filter(answer_count=0)
        elif filter_by in {"accepted", "has_accepted"}:
            queryset = queryset.filter(_has_accepted_answer_flag=True)
    sort = (request.query_params.get("sort") or "newest").lower()
    if isinstance(queryset, list):
        if sort == "votes":
            queryset = sorted(queryset, key=lambda i: (-i.score, -i.answer_count, -i.views))
        elif sort == "active":
            queryset = sorted(queryset, key=lambda i: (-(i.answer_count + i.views), -i.updated_at.timestamp()))
        elif sort == "unanswered":
            queryset = sorted([i for i in queryset if i.answer_count == 0], key=lambda i: -i.created_at.timestamp())
        else:
            queryset = sorted(queryset, key=lambda i: -i.created_at.timestamp())
    else:
        if sort == "votes":
            queryset = queryset.order_by("-score", "-answer_count", "-views", "-created_at")
        elif sort == "active":
            queryset = queryset.order_by("-updated_at", "-answer_count", "-views")
        elif sort == "unanswered":
            queryset = queryset.filter(answer_count=0).order_by("-created_at")
        else:
            queryset = queryset.order_by("-created_at")
    return Response(KBQuestionSerializer(queryset, many=True, context={"request": request}).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def community_question_detail(request, question_id):
    qs = KBQuestion.objects.all()
    if not request.user.is_authenticated:
        qs = qs.filter(is_published=True)
    qs = _prefetch_community_question_detail(qs, getattr(request, "user", None))
    question = qs.filter(id=question_id).first()
    if not question:
        return Response({"error": "Question not found."}, status=status.HTTP_404_NOT_FOUND)
    KBQuestion.objects.filter(id=question.id).update(views=F("views") + 1)
    question.views = (question.views or 0) + 1
    return Response(KBQuestionSerializer(question, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_question_answer(request, question_id):
    question = KBQuestion.objects.filter(id=question_id, is_published=True).first()
    if not question:
        return Response({"error": "Question not found."}, status=status.HTTP_404_NOT_FOUND)
    serializer = KBAnswerSerializer(data=request.data, context={"request": request})
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    answer = serializer.save(created_by=request.user, question=question)
    attachment_ids = serializer.validated_data.get("attachment_ids", [])
    try:
        _attach_uploaded_files(attachment_ids=attachment_ids, user=request.user, answer=answer)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    question.answer_count = question.answers.filter(is_published=True).count()
    question.save(update_fields=["answer_count", "updated_at"])
    owner_allows_answer_alerts = _community_pref_enabled(question.created_by, "community_answers", default=True) or _community_pref_enabled(
        question.created_by, "community_comments", default=True
    )
    if (
        question.created_by_id
        and question.created_by_id != request.user.id
        and owner_allows_answer_alerts
    ):
        actor_name = request.user.get_full_name() or request.user.email or request.user.username or "Someone"
        _create_in_app_notification(
            user=question.created_by,
            kind="success",
            title="New answer on your question",
            message=f"{actor_name} answered: {question.title}",
            link=f"/knowledge-base?view=community&question={question.id}",
        )
    return Response(KBAnswerSerializer(answer, context={"request": request}).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_question_comment(request, question_id):
    question = KBQuestion.objects.filter(id=question_id, is_published=True).first()
    if not question:
        return Response({"error": "Question not found."}, status=status.HTTP_404_NOT_FOUND)
    serializer = KBCommentSerializer(data=request.data, context={"request": request})
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    comment = serializer.save(created_by=request.user, question=question)
    attachment_ids = serializer.validated_data.get("attachment_ids", [])
    try:
        _attach_uploaded_files(attachment_ids=attachment_ids, user=request.user, comment=comment)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    if (
        question.created_by_id
        and question.created_by_id != request.user.id
        and _community_pref_enabled(question.created_by, "community_comments", default=True)
    ):
        actor_name = request.user.get_full_name() or request.user.email or request.user.username or "Someone"
        _create_in_app_notification(
            user=question.created_by,
            kind="info",
            title="New comment on your question",
            message=f"{actor_name} commented on: {question.title}",
            link=f"/knowledge-base?view=community&question={question.id}",
        )
    return Response(KBCommentSerializer(comment, context={"request": request}).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_answer_comment(request, answer_id):
    answer = KBAnswer.objects.filter(id=answer_id, is_published=True).first()
    if not answer:
        return Response({"error": "Answer not found."}, status=status.HTTP_404_NOT_FOUND)
    serializer = KBCommentSerializer(data=request.data, context={"request": request})
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    comment = serializer.save(created_by=request.user, answer=answer)
    attachment_ids = serializer.validated_data.get("attachment_ids", [])
    try:
        _attach_uploaded_files(attachment_ids=attachment_ids, user=request.user, comment=comment)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    actor_name = request.user.get_full_name() or request.user.email or request.user.username or "Someone"
    if (
        answer.created_by_id
        and answer.created_by_id != request.user.id
        and _community_pref_enabled(answer.created_by, "community_comments", default=True)
    ):
        _create_in_app_notification(
            user=answer.created_by,
            kind="info",
            title="New comment on your answer",
            message=f"{actor_name} commented on your answer in: {answer.question.title}",
            link=f"/knowledge-base?view=community&question={answer.question_id}",
        )
    if (
        answer.question.created_by_id
        and answer.question.created_by_id != request.user.id
        and answer.question.created_by_id != answer.created_by_id
        and _community_pref_enabled(answer.question.created_by, "community_comments", default=True)
    ):
        _create_in_app_notification(
            user=answer.question.created_by,
            kind="info",
            title="New comment in your question thread",
            message=f"{actor_name} commented on an answer in: {answer.question.title}",
            link=f"/knowledge-base?view=community&question={answer.question_id}",
        )
    return Response(KBCommentSerializer(comment, context={"request": request}).data, status=status.HTTP_201_CREATED)


def _update_question_score(question):
    agg = question.votes.aggregate(score=Coalesce(Sum("value"), 0))
    score = int(agg["score"] or 0)
    KBQuestion.objects.filter(id=question.id).update(score=score)
    return score


def _update_answer_score(answer):
    agg = answer.votes.aggregate(score=Coalesce(Sum("value"), 0))
    score = int(agg["score"] or 0)
    KBAnswer.objects.filter(id=answer.id).update(score=score)
    return score


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def vote_question(request, question_id):
    question = KBQuestion.objects.filter(id=question_id, is_published=True).first()
    if not question:
        return Response({"error": "Question not found."}, status=status.HTTP_404_NOT_FOUND)
    try:
        value = int(request.data.get("value"))
    except Exception:
        return Response({"error": "value must be 1 or -1"}, status=status.HTTP_400_BAD_REQUEST)
    if value not in (1, -1):
        return Response({"error": "value must be 1 or -1"}, status=status.HTTP_400_BAD_REQUEST)
    KBQuestionVote.objects.update_or_create(
        question=question,
        user=request.user,
        defaults={"value": value},
    )
    score = _update_question_score(question)
    return Response({"status": "success", "score": score, "user_vote": value})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def vote_answer(request, answer_id):
    answer = KBAnswer.objects.filter(id=answer_id, is_published=True).first()
    if not answer:
        return Response({"error": "Answer not found."}, status=status.HTTP_404_NOT_FOUND)
    try:
        value = int(request.data.get("value"))
    except Exception:
        return Response({"error": "value must be 1 or -1"}, status=status.HTTP_400_BAD_REQUEST)
    if value not in (1, -1):
        return Response({"error": "value must be 1 or -1"}, status=status.HTTP_400_BAD_REQUEST)
    KBAnswerVote.objects.update_or_create(
        answer=answer,
        user=request.user,
        defaults={"value": value},
    )
    score = _update_answer_score(answer)
    return Response({"status": "success", "score": score, "user_vote": value})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def accept_answer(request, answer_id):
    answer = KBAnswer.objects.select_related("question").filter(id=answer_id, is_published=True).first()
    if not answer:
        return Response({"error": "Answer not found."}, status=status.HTTP_404_NOT_FOUND)
    question = answer.question
    if request.user != question.created_by and not request.user.is_staff:
        return Response({"error": "Only the question author can accept an answer."}, status=status.HTTP_403_FORBIDDEN)
    KBAnswer.objects.filter(question=question, is_accepted=True).update(is_accepted=False)
    answer.is_accepted = True
    answer.save(update_fields=["is_accepted", "updated_at"])
    question.updated_at = answer.updated_at
    question.save(update_fields=["updated_at"])
    if (
        answer.created_by_id
        and answer.created_by_id != request.user.id
        and _community_pref_enabled(answer.created_by, "community_answers", default=True)
    ):
        actor_name = request.user.get_full_name() or request.user.email or request.user.username or "Question author"
        _create_in_app_notification(
            user=answer.created_by,
            kind="success",
            title="Your answer was accepted",
            message=f"{actor_name} accepted your answer in: {question.title}",
            link=f"/knowledge-base?view=community&question={question.id}",
        )
    return Response({"status": "success", "accepted_answer_id": answer.id})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def upload_community_attachment(request):
    uploaded = request.FILES.get("file")
    if not uploaded:
        return Response({"error": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)
    err = _attachment_upload_error(uploaded)
    if err:
        return Response({"error": err}, status=status.HTTP_400_BAD_REQUEST)

    safe_name = get_valid_filename(uploaded.name or "attachment")
    ext = Path(safe_name).suffix.lower()
    if ext and ext not in _ATTACHMENT_ALLOWED_EXT:
        safe_name = f"{Path(safe_name).stem}.txt"
    rel_path = default_storage.save(f"kb_community/{uuid.uuid4().hex}_{safe_name}", uploaded)
    file_url = default_storage.url(rel_path)
    abs_url = file_url if file_url.startswith(("http://", "https://")) else request.build_absolute_uri(file_url)
    attachment = KBAttachment.objects.create(
        uploaded_by=request.user,
        original_name=safe_name,
        file_path=rel_path,
        file_url=abs_url,
        content_type=(uploaded.content_type or "")[:100],
        file_size=uploaded.size,
    )
    return Response(KBAttachmentSerializer(attachment).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([AllowAny])
def community_question_public(request, question_id, slug=None):
    question = (
        _prefetch_community_question_detail(
            KBQuestion.objects.filter(id=question_id, is_published=True),
            getattr(request, "user", None),
        ).first()
    )
    if not question:
        return Response({"error": "Question not found."}, status=status.HTTP_404_NOT_FOUND)
    serializer = KBQuestionSerializer(question, context={"request": request})
    data = dict(serializer.data)
    safe_slug = slugify(question.title)[:120] or f"question-{question.id}"
    app_base, _ = _get_public_urls(request)
    data["public_url"] = f"{app_base}/community/q/{safe_slug}-{question.id}"
    return Response(data)


@api_view(["GET"])
@permission_classes([AllowAny])
def public_sitemap_xml(request):
    app_base, marketing_base = _get_public_urls(request)

    question_items = KBQuestion.objects.filter(is_published=True).order_by("-updated_at")[:5000]
    article_items = KnowledgeBaseArticle.objects.filter(is_published=True).order_by("-updated_at")[:5000]

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]

    lines.append(f"<url><loc>{marketing_base}</loc></url>")
    lines.append(f"<url><loc>{app_base}/knowledge-base?view=community</loc></url>")
    lines.append(f"<url><loc>{app_base}/knowledge-base</loc></url>")

    for q in question_items:
        slug = slugify(q.title)[:120] or f"question-{q.id}"
        loc = f"{app_base}/community/q/{slug}-{q.id}"
        lastmod = q.updated_at.date().isoformat() if q.updated_at else None
        if lastmod:
            lines.append(f"<url><loc>{loc}</loc><lastmod>{lastmod}</lastmod></url>")
        else:
            lines.append(f"<url><loc>{loc}</loc></url>")

    for a in article_items:
        article_slug = slugify(a.title)[:120] or "article"
        loc = f"{app_base}/knowledge-base/article/{article_slug}~{a.kb_id}"
        lastmod = a.updated_at.date().isoformat() if a.updated_at else None
        if lastmod:
            lines.append(f"<url><loc>{loc}</loc><lastmod>{lastmod}</lastmod></url>")
        else:
            lines.append(f"<url><loc>{loc}</loc></url>")

    lines.append("</urlset>")
    return HttpResponse("\n".join(lines), content_type="application/xml")


@api_view(["GET"])
@permission_classes([AllowAny])
def public_robots_txt(request):
    host = (request.get_host() or "").lower()
    if host.startswith("api.resolvemeq.net"):
        body = "\n".join(
            [
                "User-agent: *",
                "Disallow: /",
            ]
        )
        return HttpResponse(body, content_type="text/plain")

    app_base, _ = _get_public_urls(request)
    body = "\n".join(
        [
            "User-agent: *",
            "Allow: /knowledge-base",
            "Allow: /community/",
            "Disallow: /api/",
            f"Sitemap: {app_base}/sitemap.xml",
        ]
    )
    return HttpResponse(body, content_type="text/plain")
