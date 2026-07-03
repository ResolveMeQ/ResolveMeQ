from django.contrib.auth import get_user_model
from django.test import TestCase

from tickets.chat_context import derive_rag_search_query, enrich_agent_chat_payload
from tickets.chat_models import Conversation, ChatMessage
from tickets.models import Ticket

User = get_user_model()


class ChatContextTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ctxuser", email="ctx@example.com", password="pw"
        )
        self.ticket = Ticket.objects.create(
            user=self.user,
            issue_type="blue screen (high)",
            description="PC shows blue screen after memory diagnostic",
            category="hardware",
            status="in_progress",
        )
        self.conversation = Conversation.objects.create(
            ticket=self.ticket,
            user=self.user,
            summary="User ran memory diagnostic; agent gave RAM steps.",
        )
        ChatMessage.objects.create(
            conversation=self.conversation,
            sender_type="ai",
            text="Try reseating the RAM module and run the diagnostic again.",
        )

    def test_rag_query_uses_issue_not_closure_phrase(self):
        q = derive_rag_search_query(
            ticket=self.ticket,
            conversation=self.conversation,
            latest_message="it has worked o haha",
        )
        self.assertIn("blue screen", q.lower())
        self.assertNotIn("worked", q.lower())

    def test_enrich_payload_sets_follow_up_fields(self):
        payload = enrich_agent_chat_payload(
            {"ticket_id": self.ticket.ticket_id},
            ticket=self.ticket,
            conversation=self.conversation,
            latest_message="what is step 2?",
        )
        self.assertEqual(payload["latest_user_message"], "what is step 2?")
        self.assertTrue(payload["is_chat_follow_up"])
        self.assertIn("Latest user message", payload["conversation_guidance"])
        self.assertTrue(payload["rag_search_query"])
