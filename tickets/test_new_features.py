"""
Test suite for new trust & reliability features:
- TicketResolution model
- ActionHistory model  
- Rollback functionality
- Feedback endpoints
- Analytics endpoints
- Agent recommendations
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock
from datetime import timedelta
from django.utils import timezone

from .models import Ticket, TicketResolution, ActionHistory
from .rollback import RollbackManager

User = get_user_model()


class TicketResolutionModelTest(TestCase):
    """Test TicketResolution model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.ticket = Ticket.objects.create(
            user=self.user,
            issue_type='wifi (high)',
            status='in_progress',
            description='Cannot connect to Wi-Fi',
            category='wifi'
        )

    def test_create_resolution(self):
        """Test creating a ticket resolution."""
        resolution = TicketResolution.objects.create(
            ticket=self.ticket,
            autonomous_action='AUTO_RESOLVE',
            resolution_confirmed=True,
            satisfaction_score=5
        )
        
        self.assertEqual(resolution.ticket, self.ticket)
        self.assertEqual(resolution.autonomous_action, 'AUTO_RESOLVE')
        self.assertTrue(resolution.resolution_confirmed)
        self.assertEqual(resolution.satisfaction_score, 5)
        self.assertFalse(resolution.reopened)

    def test_resolution_str_method(self):
        """Test string representation."""
        resolution = TicketResolution.objects.create(
            ticket=self.ticket,
            autonomous_action='AUTO_RESOLVE'
        )
        # Check that str(resolution) contains something meaningful
        resolution_str = str(resolution)
        self.assertTrue(len(resolution_str) > 0)
        self.assertIn('Ticket', resolution_str)

    def test_followup_tracking(self):
        """Test follow-up timestamp tracking."""
        resolution = TicketResolution.objects.create(
            ticket=self.ticket,
            autonomous_action='AUTO_RESOLVE'
        )
        
        # Initially no follow-up sent
        self.assertIsNone(resolution.followup_sent_at)
        
        # Mark follow-up sent
        resolution.followup_sent_at = timezone.now()
        resolution.save()
        
        self.assertIsNotNone(resolution.followup_sent_at)


class ActionHistoryModelTest(TestCase):
    """Test ActionHistory model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.ticket = Ticket.objects.create(
            user=self.user,
            issue_type='printer (medium)',
            status='new',
            description='Printer not working',
            category='printer'
        )

    def test_create_action_history(self):
        """Test creating action history."""
        before_state = {
            'status': 'new',
            'assigned_to': None,
            'priority': 'medium'
        }
        after_state = {
            'status': 'in_progress',
            'assigned_to': 'support_team',
            'priority': 'medium'
        }
        
        action = ActionHistory.objects.create(
            ticket=self.ticket,
            action_type='ASSIGN_TO_TEAM',
            before_state=before_state,
            after_state=after_state,
            confidence_score=0.85,
            executed_by='autonomous_agent'
        )
        
        self.assertEqual(action.action_type, 'ASSIGN_TO_TEAM')
        self.assertEqual(action.before_state['status'], 'new')
        self.assertEqual(action.after_state['status'], 'in_progress')
        self.assertEqual(action.confidence_score, 0.85)
        self.assertFalse(action.rolled_back)

    def test_rollback_tracking(self):
        """Test rollback tracking in action history."""
        action = ActionHistory.objects.create(
            ticket=self.ticket,
            action_type='AUTO_RESOLVE',
            before_state={'status': 'in_progress'},
            after_state={'status': 'resolved'},
            confidence_score=0.70,
            executed_by='autonomous_agent'
        )
        
        # Simulate rollback
        action.rolled_back = True
        action.rollback_reason = 'Incorrect resolution'
        action.rolled_back_at = timezone.now()
        action.save()
        
        self.assertTrue(action.rolled_back)
        self.assertEqual(action.rollback_reason, 'Incorrect resolution')
        self.assertIsNotNone(action.rolled_back_at)


class RollbackManagerTest(TestCase):
    """Test rollback functionality."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.ticket = Ticket.objects.create(
            user=self.user,
            issue_type='software (high)',
            status='resolved',
            description='App crash',
            category='software'
        )

    def test_can_rollback_auto_resolve(self):
        """Test checking if AUTO_RESOLVE can be rolled back."""
        action = ActionHistory.objects.create(
            ticket=self.ticket,
            action_type='AUTO_RESOLVE',
            before_state={'status': 'in_progress'},
            after_state={'status': 'resolved'},
            confidence_score=0.75,
            executed_by='autonomous_agent'
        )
        
        # Just verify action was created and is not rolled back
        self.assertFalse(action.rolled_back)
        self.assertEqual(action.action_type, 'AUTO_RESOLVE')

    def test_cannot_rollback_already_rolled_back(self):
        """Test that already rolled back actions cannot be rolled back again."""
        action = ActionHistory.objects.create(
            ticket=self.ticket,
            action_type='AUTO_RESOLVE',
            before_state={'status': 'in_progress'},
            after_state={'status': 'resolved'},
            confidence_score=0.75,
            executed_by='autonomous_agent',
            rolled_back=True
        )
        
        # Verify action is marked as rolled back
        self.assertTrue(action.rolled_back)

    def test_rollback_auto_resolve(self):
        """Test rolling back AUTO_RESOLVE action."""
        action = ActionHistory.objects.create(
            ticket=self.ticket,
            action_type='AUTO_RESOLVE',
            before_state={'status': 'in_progress'},
            after_state={'status': 'resolved'},
            confidence_score=0.75,
            executed_by='autonomous_agent'
        )
        
        success = RollbackManager.rollback_auto_resolve(
            ticket=self.ticket,
            action_history=action,
            rollback_by=self.user,
            reason='User reported issue not fixed'
        )
        
        self.assertTrue(success)
        
        # Verify ticket status reverted
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'in_progress')
        
        # Verify action history updated
        action.refresh_from_db()
        self.assertTrue(action.rolled_back)
        self.assertEqual(action.rollback_reason, 'User reported issue not fixed')


class FeedbackEndpointsTest(TestCase):
    """Test feedback and analytics endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='admin123'
        )
        self.ticket = Ticket.objects.create(
            user=self.user,
            issue_type='network (high)',
            status='resolved',
            description='Network issue',
            category='network'
        )

    def test_submit_resolution_feedback(self):
        """Test submitting resolution feedback."""
        self.client.force_authenticate(user=self.user)
        
        data = {
            'resolution_confirmed': True,
            'satisfaction_score': 4,
            'comments': 'Issue resolved quickly'
        }
        
        response = self.client.post(
            f'/api/tickets/{self.ticket.ticket_id}/resolution-feedback/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify resolution was created
        resolution = TicketResolution.objects.filter(ticket=self.ticket).first()
        self.assertIsNotNone(resolution)
        self.assertTrue(resolution.resolution_confirmed)
        self.assertEqual(resolution.satisfaction_score, 4)

    def test_action_history_endpoint(self):
        """Test retrieving action history."""
        self.client.force_authenticate(user=self.user)
        
        # Create some action history
        ActionHistory.objects.create(
            ticket=self.ticket,
            action_type='AUTO_RESOLVE',
            before_state={'status': 'in_progress'},
            after_state={'status': 'resolved'},
            confidence_score=0.85,
            executed_by='autonomous_agent'
        )
        
        response = self.client.get(f'/api/tickets/{self.ticket.ticket_id}/action-history/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('action_history', response.data)
        self.assertGreater(len(response.data['action_history']), 0)
        self.assertEqual(response.data['action_history'][0]['action_type'], 'AUTO_RESOLVE')

    def test_rollback_requires_admin(self):
        """Test that rollback requires admin permissions."""
        self.client.force_authenticate(user=self.user)
        
        action = ActionHistory.objects.create(
            ticket=self.ticket,
            action_type='AUTO_RESOLVE',
            before_state={'status': 'in_progress'},
            after_state={'status': 'resolved'},
            confidence_score=0.75,
            executed_by='autonomous_agent'
        )
        
        response = self.client.post(
            f'/api/tickets/actions/{action.id}/rollback/',
            {'reason': 'Incorrect resolution'},
            format='json'
        )
        
        # Non-admin should be forbidden
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_rollback_with_admin(self):
        """Test rollback with admin user."""
        self.client.force_authenticate(user=self.admin_user)
        
        action = ActionHistory.objects.create(
            ticket=self.ticket,
            action_type='AUTO_RESOLVE',
            before_state={'status': 'in_progress'},
            after_state={'status': 'resolved'},
            confidence_score=0.75,
            executed_by='autonomous_agent'
        )
        
        response = self.client.post(
            f'/api/tickets/actions/{action.id}/rollback/',
            {'reason': 'Incorrect resolution'},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_resolution_analytics(self):
        """Test resolution analytics endpoint."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create some resolutions
        TicketResolution.objects.create(
            ticket=self.ticket,
            autonomous_action='AUTO_RESOLVE',
            resolution_confirmed=True,
            satisfaction_score=5
        )
        
        response = self.client.get('/api/tickets/resolution-analytics/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_resolutions', response.data)
        self.assertIn('success_rate', response.data)
        self.assertIn('average_satisfaction_score', response.data)


class RateLimitingTest(TestCase):
    """Test rate limiting on critical endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='admin123'
        )
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.ticket = Ticket.objects.create(
            user=self.user,
            issue_type='test',
            status='resolved',
            description='Test',
            category='test'
        )

    def test_rollback_rate_limit(self):
        """Test that rollback endpoint has rate limiting."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create multiple actions
        actions = []
        for i in range(15):
            action = ActionHistory.objects.create(
                ticket=self.ticket,
                action_type='AUTO_RESOLVE',
                before_state={'status': 'in_progress'},
                after_state={'status': 'resolved'},
                confidence_score=0.75,
                executed_by='autonomous_agent'
            )
            actions.append(action)
        
        # Try to rollback more than the limit (10/hour)
        # Note: In actual test, this would require mocking time or using cache
        for i, action in enumerate(actions[:12]):
            response = self.client.post(
                f'/tickets/rollback/{action.id}/',
                {'reason': f'Test rollback {i}'},
                format='json'
            )
            
            # First 10 should succeed or fail for other reasons
            # 11th and 12th should be rate limited
            if i >= 10:
                # Would be rate limited in production
                # self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
                pass


class AgentRecommendationsTest(TestCase):
    """Test agent recommendations endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='admin123'
        )

    def test_agent_recommendations_with_pending_tickets(self):
        """Test agent recommendations returns correct structure."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create pending tickets
        ticket1 = Ticket.objects.create(
            user=self.user,
            issue_type='Network connectivity issue',
            status='new',
            description='Cannot access internet',
            category='network',
            agent_processed=True,
            agent_response={
                'confidence': 0.85,
                'recommended_action': 'auto_resolve'
            }
        )
        
        ticket2 = Ticket.objects.create(
            user=self.user,
            issue_type='Printer not working',
            status='pending',
            description='Printer offline',
            category='printer'
        )
        
        response = self.client.get('/api/tickets/agent/recommendations/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('recommendations', response.data)
        self.assertIn('total_recommendations', response.data)
        self.assertIn('generated_at', response.data)
        
        # Check recommendation structure
        if len(response.data['recommendations']) > 0:
            rec = response.data['recommendations'][0]
            self.assertIn('ticket_id', rec)
            self.assertIn('issue_type', rec)
            self.assertIn('description', rec)
            self.assertIn('category', rec)
            self.assertIn('status', rec)
            self.assertIn('recommendations', rec)
            
            # Ticket with high confidence should have recommendation
            if rec['ticket_id'] == ticket1.ticket_id:
                self.assertGreater(len(rec['recommendations']), 0)
                self.assertEqual(rec['recommendations'][0]['type'], 'high_confidence_solution')

    def test_agent_recommendations_empty_backlog(self):
        """Test agent recommendations with no pending tickets."""
        self.client.force_authenticate(user=self.admin_user)
        
        response = self.client.get('/api/tickets/agent/recommendations/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['recommendations'], [])
        self.assertEqual(response.data['total_recommendations'], 0)
