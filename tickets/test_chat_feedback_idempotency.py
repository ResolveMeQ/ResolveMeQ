"""Idempotency tests for chat feedback endpoints."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from tickets.chat_models import ChatMessage, Conversation
from tickets.models import Ticket, TicketInteraction
from base.models import Team

User = get_user_model()


class ChatFeedbackIdempotencyTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="fbuser",
            email="fbuser@example.com",
            password="pass12345",
        )
        self.team = Team.objects.create(name="FB Team", owner=self.user)
        self.ticket = Ticket.objects.create(
            user=self.user,
            team=self.team,
            issue_type="VPN issue",
            description="Cannot connect",
            category="network",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_initial_solution_feedback_is_idempotent(self):
        url = f"/api/tickets/{self.ticket.ticket_id}/chat/initial-solution-feedback/"
        first = self.client.post(url, {"rating": "helpful"}, format="json")
        self.assertEqual(first.status_code, 200)
        self.assertFalse(first.data.get("already_recorded"))

        second = self.client.post(url, {"rating": "helpful"}, format="json")
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.data.get("already_recorded"))
        self.assertEqual(
            TicketInteraction.objects.filter(
                ticket=self.ticket, interaction_type="feedback"
            ).count(),
            1,
        )

    def test_message_feedback_is_idempotent(self):
        conversation = Conversation.objects.create(
            ticket=self.ticket,
            user=self.user,
            summary="Chat",
        )
        message = ChatMessage.objects.create(
            conversation=conversation,
            sender_type="ai",
            message_type="text",
            text="Try restarting the VPN client.",
        )
        url = f"/api/tickets/{self.ticket.ticket_id}/chat/{message.id}/feedback/"
        first = self.client.post(url, {"rating": "not_helpful"}, format="json")
        self.assertEqual(first.status_code, 200)
        self.assertFalse(first.data.get("already_recorded", False))

        second = self.client.post(url, {"rating": "not_helpful"}, format="json")
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.data.get("already_recorded"))
        message.refresh_from_db()
        self.assertFalse(message.was_helpful)
