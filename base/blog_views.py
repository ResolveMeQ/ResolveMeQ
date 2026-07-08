"""Public marketing blog API (no auth)."""
from __future__ import annotations

from django.conf import settings
from django.utils.formats import date_format
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import permissions, status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from base.models import BlogPost


def _format_display_date(d) -> str:
    return date_format(d, format="F Y")


def _serialize_post(post: BlogPost, *, include_body: bool) -> dict:
    author = (post.author_name or "").strip() or getattr(settings, "BLOG_AUTHOR_NAME", "Nyuydine Bill")
    payload = {
        "slug": post.slug,
        "title": post.title,
        "excerpt": post.excerpt,
        "category": post.category,
        "isoDate": post.published_at.isoformat(),
        "date": _format_display_date(post.published_at),
        "readTime": post.read_time_label,
        "authorName": author,
        "imageUrl": post.image_url or None,
        "ogImage": post.image_url or None,
        "isAiGenerated": post.is_ai_generated,
    }
    if include_body:
        payload["body"] = post.body
    return payload


class BlogPostListView(GenericAPIView):
    """List published blog posts (newest first)."""

    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        operation_description="List published marketing blog posts",
        responses={200: openapi.Response(description="Blog post summaries")},
    )
    def get(self, request):
        qs = BlogPost.objects.filter(is_published=True).order_by("-published_at", "-created_at")
        posts = [_serialize_post(p, include_body=False) for p in qs]
        return Response({"ok": True, "posts": posts})


class BlogPostDetailView(GenericAPIView):
    """Single published blog post by slug."""

    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        operation_description="Get one published blog post",
        responses={
            200: openapi.Response(description="Blog post detail"),
            404: openapi.Response(description="Not found"),
        },
    )
    def get(self, request, slug):
        post = BlogPost.objects.filter(slug=slug, is_published=True).first()
        if post is None:
            return Response({"ok": False, "error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"ok": True, "post": _serialize_post(post, include_body=True)})
