from datetime import date
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from base.models import BlogPost


class BlogPostAPITest(TestCase):
    def setUp(self):
        BlogPost.objects.create(
            slug="test-post",
            title="Test Post",
            excerpt="Short excerpt.",
            body="## Intro\n\nBody text.",
            category="Analytics",
            read_time_minutes=8,
            author_name="Editor",
            published_at=date(2026, 1, 15),
            is_published=True,
        )
        BlogPost.objects.create(
            slug="draft-post",
            title="Draft",
            excerpt="Hidden.",
            body="Hidden body.",
            category="Strategy",
            published_at=date(2026, 1, 10),
            is_published=False,
        )

    def test_list_published_only(self):
        res = self.client.get("/api/blog/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["ok"])
        slugs = [p["slug"] for p in data["posts"]]
        self.assertIn("test-post", slugs)
        self.assertNotIn("draft-post", slugs)

    def test_detail_found(self):
        res = self.client.get("/api/blog/test-post/")
        self.assertEqual(res.status_code, 200)
        post = res.json()["post"]
        self.assertEqual(post["title"], "Test Post")
        self.assertIn("body", post)
        self.assertEqual(post["readTime"], "8 min read")

    def test_detail_not_found(self):
        res = self.client.get("/api/blog/missing/")
        self.assertEqual(res.status_code, 404)


@override_settings(BLOG_AUTHOR_NAME="Test Author")
class BlogGenerationTest(TestCase):
    @patch("base.blog_generation.fetch_blog_draft_from_agent")
    def test_generate_daily_skips_when_exists(self, mock_fetch):
        from base.blog_generation import generate_daily_blog_post

        today = timezone.now().date()
        BlogPost.objects.create(
            slug="existing",
            title="Existing",
            excerpt="Excerpt",
            body="Body",
            category="Strategy",
            published_at=today,
            is_ai_generated=True,
        )
        result = generate_daily_blog_post(force=False)
        self.assertIsNone(result)
        mock_fetch.assert_not_called()

    @patch("base.blog_generation.fetch_blog_draft_from_agent")
    def test_generate_daily_creates_post(self, mock_fetch):
        from base.blog_generation import generate_daily_blog_post

        mock_fetch.return_value = {
            "title": "New AI Article",
            "slug": "new-ai-article",
            "excerpt": "Fresh insight.",
            "category": "AI & Automation",
            "body": "## Section\n\nContent here.",
            "read_time_minutes": 10,
            "image_url": "https://images.unsplash.com/photo-example",
            "author_name": "Test Author",
        }
        post = generate_daily_blog_post(force=False)
        self.assertIsNotNone(post)
        self.assertEqual(post.slug, "new-ai-article")
        self.assertTrue(post.is_ai_generated)
        self.assertEqual(post.image_url, "https://images.unsplash.com/photo-example")

    @patch("base.blog_generation.fetch_blog_draft_from_agent")
    def test_unique_slug_on_collision(self, mock_fetch):
        from base.blog_generation import generate_daily_blog_post

        BlogPost.objects.create(
            slug="duplicate-slug",
            title="Old",
            excerpt="Old",
            body="Old",
            category="Strategy",
            published_at=date(2025, 1, 1),
        )
        mock_fetch.return_value = {
            "title": "Duplicate",
            "slug": "duplicate-slug",
            "excerpt": "Again.",
            "category": "Strategy",
            "body": "Body",
            "read_time_minutes": 7,
            "image_url": None,
        }
        post = generate_daily_blog_post(force=True)
        self.assertEqual(post.slug, "duplicate-slug-2")
