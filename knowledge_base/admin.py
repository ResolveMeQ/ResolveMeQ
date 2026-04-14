from django.contrib import admin
from .models import (
    KnowledgeBaseArticle,
    KnowledgeBaseArticleVote,
    LLMResponse,
    LLMResponseVote,
    KBQuestion,
    KBAnswer,
    KBComment,
    KBQuestionVote,
    KBAnswerVote,
    KBAttachment,
)

admin.site.register(KnowledgeBaseArticle)
admin.site.register(KnowledgeBaseArticleVote)
admin.site.register(LLMResponse)
admin.site.register(LLMResponseVote)
admin.site.register(KBQuestion)
admin.site.register(KBAnswer)
admin.site.register(KBComment)
admin.site.register(KBQuestionVote)
admin.site.register(KBAnswerVote)
admin.site.register(KBAttachment)
