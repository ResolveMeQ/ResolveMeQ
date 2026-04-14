from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    KnowledgeBaseArticleViewSet,
    LLMResponseViewSet,
    kb_articles_for_agent,
    search_kb_for_agent,
    kb_article_by_id,
    community_questions,
    community_question_detail,
    add_question_answer,
    add_question_comment,
    add_answer_comment,
    vote_question,
    vote_answer,
    accept_answer,
    upload_community_attachment,
    community_question_public,
)

router = DefaultRouter()
router.register(r'articles', KnowledgeBaseArticleViewSet)
router.register(r'responses', LLMResponseViewSet)

urlpatterns = [
    path('', include(router.urls)),
    # API endpoints for FastAPI agent
    path('api/articles/', kb_articles_for_agent, name='kb-articles-for-agent'),
    path('api/search/', search_kb_for_agent, name='search-kb-for-agent'),
    path('api/articles/<str:kb_id>/', kb_article_by_id, name='kb-article-by-id'),
    # Community Q&A endpoints
    path('community/questions/', community_questions, name='community-questions'),
    path('community/questions/<int:question_id>/', community_question_detail, name='community-question-detail'),
    path('community/questions/<int:question_id>/answers/', add_question_answer, name='community-question-answer'),
    path('community/questions/<int:question_id>/comments/', add_question_comment, name='community-question-comment'),
    path('community/answers/<int:answer_id>/comments/', add_answer_comment, name='community-answer-comment'),
    path('community/questions/<int:question_id>/vote/', vote_question, name='community-question-vote'),
    path('community/answers/<int:answer_id>/vote/', vote_answer, name='community-answer-vote'),
    path('community/answers/<int:answer_id>/accept/', accept_answer, name='community-accept-answer'),
    path('community/attachments/upload/', upload_community_attachment, name='community-attachment-upload'),
    path('community/public/questions/<int:question_id>/', community_question_public, name='community-question-public'),
    path('community/public/questions/<slug:slug>-<int:question_id>/', community_question_public, name='community-question-public-slug'),
]
