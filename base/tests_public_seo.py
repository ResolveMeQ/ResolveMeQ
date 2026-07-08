from datetime import date

from django.test import RequestFactory, TestCase

from base.models import BlogPost
from base.public_seo import render_blog_rss_xml, render_sitemap_xml
from base.public_seo_views import public_blog_rss_xml, public_sitemap_xml


class LiveSitemapTest(TestCase):
    def setUp(self):
        BlogPost.objects.create(
            slug="live-sitemap-post",
            title="Live Sitemap Post",
            excerpt="Excerpt for RSS.",
            body="Body",
            category="Analytics",
            published_at=date(2026, 3, 1),
            is_published=True,
        )
        self.factory = RequestFactory()

    def test_sitemap_includes_blog_url(self):
        request = self.factory.get("/sitemap.xml", HTTP_HOST="api.resolvemeq.net")
        response = public_sitemap_xml(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/xml", response["Content-Type"])
        self.assertIn("https://resolvemeq.net/blog/live-sitemap-post", response.content.decode())

    def test_render_sitemap_has_marketing_and_blog(self):
        xml = render_sitemap_xml("https://app.resolvemeq.net", "https://resolvemeq.net")
        self.assertIn("https://resolvemeq.net/blog", xml)
        self.assertIn("https://resolvemeq.net/blog/live-sitemap-post", xml)
        self.assertIn("https://app.resolvemeq.net/knowledge-base", xml)

    def test_rss_includes_blog_item(self):
        request = self.factory.get("/rss.xml", HTTP_HOST="api.resolvemeq.net")
        response = public_blog_rss_xml(request)
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("Live Sitemap Post", body)
        self.assertIn("live-sitemap-post", body)

    def test_render_rss_xml(self):
        xml = render_blog_rss_xml("https://resolvemeq.net")
        self.assertIn("Live Sitemap Post", xml)
        self.assertIn("https://resolvemeq.net/rss.xml", xml)
