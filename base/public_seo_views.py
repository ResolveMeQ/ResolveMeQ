from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

from base.public_seo import (
    get_public_site_urls,
    render_api_robots_txt,
    render_app_robots_txt,
    render_blog_rss_xml,
    render_sitemap_xml,
)


@api_view(["GET"])
@permission_classes([AllowAny])
def public_sitemap_xml(request):
    """
    Live sitemap: marketing pages, blog posts, global KB, and community Q&A.
    Regenerated on every request — no frontend rebuild required.
    """
    app_base, marketing_base = get_public_site_urls(request)
    xml = render_sitemap_xml(app_base, marketing_base)
    response = HttpResponse(xml, content_type="application/xml")
    response["Cache-Control"] = "public, max-age=3600"
    return response


@api_view(["GET"])
@permission_classes([AllowAny])
def public_blog_rss_xml(request):
    """Live RSS feed for published marketing blog posts."""
    _, marketing_base = get_public_site_urls(request)
    xml = render_blog_rss_xml(marketing_base)
    response = HttpResponse(xml, content_type="application/rss+xml")
    response["Cache-Control"] = "public, max-age=1800"
    return response


@api_view(["GET"])
@permission_classes([AllowAny])
def public_robots_txt(request):
    host = (request.get_host() or "").lower()
    if host.startswith("api."):
        body = render_api_robots_txt()
    else:
        app_base, marketing_base = get_public_site_urls(request)
        body = render_app_robots_txt(app_base, marketing_base)
    return HttpResponse(body, content_type="text/plain")
