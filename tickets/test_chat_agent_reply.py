"""
Tests for merging human-agent replies into the customer's existing AI chat thread
(instead of the separate Comments/TicketInteraction thread), and for suppressing the
automatic AI reply once a ticket has been claimed by a teammate.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .chat_models import ChatMessage, Conversation
from .models import Ticket, TicketInteraction
from .models import _ticket_has_persisted_ai_chat, _kb_pick_final_assistant_text

User = get_user_model()


class ChatAgentReplyTest(TestCase):
    def setUp(self):
        from base.models import Team, UserPreferences

        self.client = APIClient()
        self.requester = User.objects.create_user(
            username="customer1", email="customer1@example.com", password="testpass123"
        )
        self.agent = User.objects.create_user(
            username="agent1", email="agent1@example.com", password="testpass123"
        )
        self.outsider = User.objects.create_user(
            username="outsider1", email="outsider1@example.com", password="testpass123"
        )

        self.team = Team.objects.create(name="Support Team A", owner=self.requester)
        self.team.members.add(self.agent)
        prefs, _ = UserPreferences.objects.get_or_create(user=self.agent)
        prefs.active_team = self.team
        prefs.save()

        self.ticket = Ticket.objects.create(
            user=self.requester, team=self.team, issue_type="vpn (high)", status="escalated",
            description="VPN keeps dropping", category="vpn",
        )

    def _claim(self):
        self.ticket.claimed_at = timezone.now()
        self.ticket.assigned_to = self.agent
        self.ticket.save()

    @patch("tickets.chat_views.dispatch_ticket_comment_email")
    def test_agent_reply_lands_in_customer_conversation(self, mock_email):
        self._claim()
        self.client.force_authenticate(user=self.agent)

        resp = self.client.post(
            f"/api/tickets/{self.ticket.ticket_id}/chat/agent-reply/",
            {"message": "I've reset your VPN profile, please try reconnecting."},
            format="json",
        )

        self.assertEqual(resp.status_code, 200)
        conversation = Conversation.objects.get(ticket=self.ticket, user=self.requester)
        message = conversation.messages.get(sender_type="agent")
        self.assertEqual(message.author_id, self.agent.id)
        self.assertIn("reset your VPN profile", message.text)
        self.assertTrue(
            TicketInteraction.objects.filter(ticket=self.ticket, interaction_type="agent_response").exists()
        )
        mock_email.assert_called_once()

    def test_ticket_owner_cannot_use_agent_reply_endpoint(self):
        self._claim()
        self.client.force_authenticate(user=self.requester)

        resp = self.client.post(
            f"/api/tickets/{self.ticket.ticket_id}/chat/agent-reply/", {"message": "hi"}, format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_non_team_member_cannot_use_agent_reply_endpoint(self):
        self._claim()
        self.client.force_authenticate(user=self.outsider)

        resp = self.client.post(
            f"/api/tickets/{self.ticket.ticket_id}/chat/agent-reply/", {"message": "hi"}, format="json",
        )
        self.assertEqual(resp.status_code, 403)

    @patch("tickets.chat_views.dispatch_ticket_comment_email")
    def test_unclaimed_ticket_reply_auto_claims_it(self, mock_email):
        # Not claimed yet -- self.agent is a valid team member. Replying is an explicit
        # act of taking ownership, so it should claim the ticket instead of blocking.
        self.client.force_authenticate(user=self.agent)

        resp = self.client.post(
            f"/api/tickets/{self.ticket.ticket_id}/chat/agent-reply/", {"message": "hi"}, format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertIsNotNone(self.ticket.claimed_at)
        self.assertEqual(self.ticket.assigned_to_id, self.agent.id)

    @patch("tickets.chat_views.try_consume_agent_operation")
    def test_customer_message_on_claimed_ticket_skips_ai_and_quota(self, mock_quota):
        self._claim()
        self.client.force_authenticate(user=self.requester)

        resp = self.client.post(
            f"/api/tickets/{self.ticket.ticket_id}/chat/", {"message": "any update?"}, format="json",
        )

        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data["ai_message"])
        self.assertTrue(resp.data["routed_to_human"])
        mock_quota.assert_not_called()
        conversation = Conversation.objects.get(ticket=self.ticket, user=self.requester)
        self.assertFalse(conversation.messages.filter(sender_type="ai").exists())
        self.assertTrue(conversation.messages.filter(sender_type="user").exists())

    @patch("tickets.chat_views._get_ai_chat_response")
    @patch("tickets.chat_views.try_consume_agent_operation")
    def test_customer_message_on_unclaimed_ticket_still_gets_ai_response(self, mock_quota, mock_ai):
        mock_quota.return_value = type("Q", (), {"allowed": True, "used": 1, "limit": 100})()
        mock_ai.return_value = {
            "text": "Try restarting your VPN client.",
            "message_type": "text",
            "confidence": 0.8,
            "metadata": {},
        }
        self.client.force_authenticate(user=self.requester)

        resp = self.client.post(
            f"/api/tickets/{self.ticket.ticket_id}/chat/", {"message": "it's still broken"}, format="json",
        )

        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.data["ai_message"])
        mock_quota.assert_called_once()

    @patch("tickets.chat_views.dispatch_ticket_comment_email")
    def test_history_endpoint_shows_both_ai_and_agent_messages_in_order(self, mock_email):
        self._claim()
        conversation = Conversation.objects.create(ticket=self.ticket, user=self.requester)
        ChatMessage.objects.create(conversation=conversation, sender_type="user", text="help")
        ChatMessage.objects.create(conversation=conversation, sender_type="ai", text="here are some steps")

        self.client.force_authenticate(user=self.agent)
        self.client.post(
            f"/api/tickets/{self.ticket.ticket_id}/chat/agent-reply/",
            {"message": "Following up personally on this."},
            format="json",
        )

        self.client.force_authenticate(user=self.requester)
        resp = self.client.get(f"/api/tickets/{self.ticket.ticket_id}/chat/history/")

        self.assertEqual(resp.status_code, 200)
        types = [m["sender_type"] for m in resp.data["messages"]]
        self.assertEqual(types, ["user", "ai", "agent"])
        self.assertEqual(resp.data["messages"][-1]["author_name"], self.agent.get_full_name() or self.agent.email)

    @patch("tickets.chat_views._get_ai_chat_response")
    @patch("tickets.chat_views.try_consume_agent_operation")
    def test_ai_unreachable_returns_200_with_fallback_message(self, mock_quota, mock_ai):
        """Regression guard: the fallback message used to come back as HTTP 503,
        which made the frontend discard it and show a generic client-side error
        instead -- retries never recovered and the fallback was never persisted."""
        mock_quota.return_value = type("Q", (), {"allowed": True, "used": 1, "limit": 100})()
        mock_ai.side_effect = RuntimeError("agent unreachable")
        self.client.force_authenticate(user=self.requester)

        resp = self.client.post(
            f"/api/tickets/{self.ticket.ticket_id}/chat/", {"message": "still broken"}, format="json",
        )

        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.data["ai_message"])
        self.assertEqual(resp.data["ai_message"]["sender_type"], "system")
        conversation = Conversation.objects.get(ticket=self.ticket, user=self.requester)
        self.assertTrue(conversation.messages.filter(sender_type="system").exists())

    @patch("tickets.chat_views.dispatch_ticket_comment_email")
    def test_agent_message_counts_as_persisted_chat_for_kb_sync(self, mock_email):
        """Regression guard for the KB-synthesis blind spot: a resolution that came
        entirely from a human reply (no AI message at all) must still be picked up."""
        self._claim()
        conversation = Conversation.objects.create(ticket=self.ticket, user=self.requester)
        ChatMessage.objects.create(conversation=conversation, sender_type="user", text="VPN is down")
        ChatMessage.objects.create(
            conversation=conversation, sender_type="agent", author=self.agent,
            text="Restarted the VPN gateway on our end, you're all set.",
        )

        self.assertTrue(_ticket_has_persisted_ai_chat(self.ticket))
        picked_text, picked_msg = _kb_pick_final_assistant_text(self.ticket)
        self.assertIn("Restarted the VPN gateway", picked_text)
