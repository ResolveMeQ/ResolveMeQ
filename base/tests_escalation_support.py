"""Tests for escalation queue access and billing support → ticket flow."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from base.escalation_access import user_can_access_escalation_queue
from base.models import Profile, SupportContactSubmission, Team
from tickets.models import Ticket

User = get_user_model()


class EscalationAccessTests(TestCase):
    def setUp(self):
        self.member = User.objects.create_user(
            email='member@test.com', username='member', password='pw', is_verified=True
        )
        self.owner = User.objects.create_user(
            email='owner@test.com', username='owner', password='pw', is_verified=True
        )
        self.agent = User.objects.create_user(
            email='agent@test.com',
            username='agent',
            password='pw',
            is_verified=True,
            is_platform_agent=True,
        )
        self.team = Team.objects.create(name='Acme', owner=self.owner)
        self.team.members.add(self.member)

    def test_platform_agent_can_access_queue(self):
        self.assertTrue(user_can_access_escalation_queue(self.agent))

    def test_team_owner_can_access_queue(self):
        self.assertTrue(user_can_access_escalation_queue(self.owner))

    def test_regular_member_cannot_access_queue(self):
        self.assertFalse(user_can_access_escalation_queue(self.member))

    def test_escalation_queue_api_forbidden_for_member(self):
        client = APIClient()
        client.force_authenticate(self.member)
        resp = client.get('/api/tickets/escalated/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_profile_includes_access_flags(self):
        Profile.objects.get_or_create(user=self.agent)
        client = APIClient()
        client.force_authenticate(self.agent)
        resp = client.get('/api/auth/profile/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.get('is_platform_agent'))
        self.assertTrue(resp.data.get('can_access_escalation_queue'))


@override_settings(TEST_DISABLE_AGENT=True)
class BillingSupportTicketTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='billing-support@test.com',
            username='billingsupport',
            password='pw',
            is_verified=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @patch('base.tasks.dispatch_send_email_with_template')
    @patch('tickets.notifications.notify_support_escalation')
    def test_billing_support_creates_linked_escalated_ticket(
        self, mock_ops_escalation, mock_dispatch_mail
    ):
        resp = self.client.post(
            '/api/billing/support-contact/',
            {
                'message': 'I need help understanding my invoice for last month please.',
                'subject': 'Invoice question',
                'page_context': 'billing',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, getattr(resp, 'data', resp.content))
        self.assertIsNotNone(resp.data.get('ticket_id'))
        submission = SupportContactSubmission.objects.get(pk=resp.data['id'])
        self.assertIsNotNone(submission.ticket_id)
        self.assertEqual(submission.status, SupportContactSubmission.Status.OPEN)
        ticket = Ticket.objects.get(pk=submission.ticket_id)
        self.assertEqual(ticket.status, 'escalated')
        self.assertEqual(ticket.category, 'billing_account')
        self.assertTrue(ticket.agent_processed)

    def test_submission_status_syncs_when_ticket_claimed(self):
        ticket = Ticket.objects.create(
            user=self.user,
            issue_type='Billing help',
            description='test',
            category='billing_account',
            status='escalated',
            agent_processed=True,
        )
        submission = SupportContactSubmission.objects.create(
            user=self.user,
            email=self.user.email,
            message='help',
            ticket=ticket,
            status=SupportContactSubmission.Status.OPEN,
        )
        agent = User.objects.create_user(
            email='claimer@test.com', username='claimer', password='pw', is_platform_agent=True
        )
        ticket.assigned_to = agent
        ticket.claimed_at = ticket.created_at
        ticket.save()
        submission.refresh_from_db()
        self.assertEqual(submission.status, SupportContactSubmission.Status.IN_PROGRESS)
        self.assertEqual(submission.assigned_to_id, agent.id)
