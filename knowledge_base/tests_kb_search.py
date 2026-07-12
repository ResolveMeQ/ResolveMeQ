"""Tests for KB tokenized search."""

from django.test import TestCase

from knowledge_base.kb_search import build_kb_content_filter, kb_search_terms
from knowledge_base.models import KnowledgeBaseArticle


class KBSearchTokenTest(TestCase):
    def test_tokenizes_multi_word_agent_query(self):
        terms = kb_search_terms(
            "network connectivity Cannot connect to corporate VPN from home wifi"
        )
        self.assertIn("vpn", terms)
        self.assertIn("wifi", terms)
        self.assertNotIn("cannot", terms)

    def test_build_filter_matches_partial_title(self):
        KnowledgeBaseArticle.objects.create(
            title="Connect to corporate VPN",
            content="Use the VPN client and enter your credentials.",
            is_published=True,
        )
        qs = KnowledgeBaseArticle.objects.filter(
            build_kb_content_filter("vpn home network cannot connect")
        )
        self.assertEqual(qs.count(), 1)
