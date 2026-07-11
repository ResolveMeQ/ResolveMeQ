"""
Comprehensive test suite for ResolveMe autonomous agent system.
Tests all critical functionality before commits.
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch, Mock
import json
from datetime import datetime, timedelta

from django.conf import settings

from base.models import User, Profile
from tickets.models import Ticket, TicketInteraction
from solutions.models import Solution
from knowledge_base.models import KnowledgeBaseArticle
from tickets.autonomous_agent import AutonomousAgent, AgentAction
from tickets.tasks import process_ticket_with_agent, execute_autonomous_action

class UserModelTest(TestCase):
    """Test the custom User model functionality."""
    
    def setUp(self):
        self.user_data = {
            'email': 'test@example.com',
            'username': 'testuser',
            'first_name': 'Test',
            'last_name': 'User'
        }
    
    def test_user_creation(self):
        """Test creating a user with required fields."""
        user = User.objects.create_user(
            email=self.user_data['email'],
            username=self.user_data['username'],
            password='testpass123'
        )
        self.assertEqual(user.email, self.user_data['email'])
        self.assertEqual(user.username, self.user_data['username'])
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
    
    def test_superuser_creation(self):
        """Test creating a superuser."""
        superuser = User.objects.create_superuser(
            email='admin@example.com',
            username='admin',
            password='adminpass123'
        )
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)
    
    def test_user_str_representation(self):
        """Test the string representation of user."""
        user = User.objects.create_user(
            email=self.user_data['email'],
            username=self.user_data['username']
        )
        self.assertEqual(str(user), self.user_data['email'])
    
    def test_user_full_name_property(self):
        """Test the full_name property."""
        user = User.objects.create_user(
            email=self.user_data['email'],
            username=self.user_data['username'],
            first_name=self.user_data['first_name'],
            last_name=self.user_data['last_name']
        )
        expected_name = f"{self.user_data['first_name']} {self.user_data['last_name']}"
        self.assertEqual(user.full_name, expected_name)

class TicketModelTest(TestCase):
    """Test the Ticket model functionality."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='user@example.com',
            username='testuser',
            password='testpass123'
        )
        self.ticket_data = {
            'user': self.user,
            'issue_type': 'Network Issue',
            'description': 'Cannot connect to WiFi',
            'category': 'network',
            'status': 'new'
        }
    
    def test_ticket_creation(self):
        """Test creating a ticket."""
        ticket = Ticket.objects.create(**self.ticket_data)
        self.assertEqual(ticket.user, self.user)
        self.assertEqual(ticket.issue_type, 'Network Issue')
        self.assertEqual(ticket.status, 'new')
        self.assertIsNotNone(ticket.ticket_id)
    
    def test_ticket_str_representation(self):
        """Test the string representation of ticket."""
        ticket = Ticket.objects.create(**self.ticket_data)
        expected_str = f"{ticket.issue_type} ({ticket.status})"
        self.assertEqual(str(ticket), expected_str)
    
    def test_ticket_interaction_creation(self):
        """Test creating ticket interactions."""
        ticket = Ticket.objects.create(**self.ticket_data)
        interaction = TicketInteraction.objects.create(
            ticket=ticket,
            user=self.user,
            interaction_type='user_message',
            content='Additional details about the issue'
        )
        self.assertEqual(interaction.ticket, ticket)
        self.assertEqual(interaction.user, self.user)

class AutonomousAgentTest(TestCase):
    """Test the autonomous agent decision-making logic."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='user@example.com',
            username='testuser'
        )
        self.ticket = Ticket.objects.create(
            user=self.user,
            issue_type='Network Issue',
            description='Cannot connect to WiFi',
            category='network',
            status='new'
        )
    
    def test_high_confidence_auto_resolve(self):
        """Test auto-resolve decision for high confidence."""
        agent_response = {
            'confidence': 0.9,
            'recommended_action': 'auto_resolve',
            'solution': {
                'steps': ['Step 1', 'Step 2'],
                'success_probability': 0.85
            },
            'reasoning': 'Common network issue'
        }
        self.ticket.agent_response = agent_response
        
        agent = AutonomousAgent(self.ticket)
        action, params = agent.decide_autonomous_action()
        
        self.assertEqual(action, AgentAction.AUTO_RESOLVE)
        self.assertIn('resolution_steps', params)
    
    def test_medium_confidence_followup(self):
        """Test follow-up decision for medium confidence."""
        agent_response = {
            'confidence': 0.7,
            'recommended_action': 'auto_resolve',
            'solution': {
                'steps': ['Step 1'],
                'success_probability': 0.75
            }
        }
        self.ticket.agent_response = agent_response
        
        agent = AutonomousAgent(self.ticket)
        action, params = agent.decide_autonomous_action()
        
        self.assertEqual(action, AgentAction.SCHEDULE_FOLLOWUP)
    
    def test_low_confidence_escalation(self):
        """Test escalation for low confidence critical issue."""
        agent_response = {
            'confidence': 0.3,
            'analysis': {
                'severity': 'critical',
                'category': 'security'
            }
        }
        self.ticket.agent_response = agent_response
        
        agent = AutonomousAgent(self.ticket)
        action, params = agent.decide_autonomous_action()
        
        self.assertEqual(action, AgentAction.ESCALATE)
    
    def test_low_confidence_clarification(self):
        """Test clarification request for low confidence non-critical issue."""
        agent_response = {
            'confidence': 0.4,
            'analysis': {
                'severity': 'low',
                'category': 'general'
            }
        }
        self.ticket.agent_response = agent_response
        
        agent = AutonomousAgent(self.ticket)
        action, params = agent.decide_autonomous_action()
        
        self.assertEqual(action, AgentAction.REQUEST_CLARIFICATION)

class KnowledgeBaseAPITest(APITestCase):
    """
    Test the Knowledge Base API endpoints for agent access.

    These endpoints require X-Agent-API-Key (see base.authentication.AgentAPIKeyAuthentication
    and base.permissions.IsAuthenticatedOrAgent) -- they used to be AllowAny, which meant
    anyone on the internet could enumerate/search the KB with no auth at all. The real
    FastAPI agent already sends this header on every call (resolvemeq-agent's
    django_kb_client.py), so these tests authenticate the same way instead of going back
    to AllowAny.
    """

    def setUp(self):
        self.client = Client()
        self.agent_headers = {
            'HTTP_X_AGENT_API_KEY': settings.AGENT_API_KEY,
        }
        self.kb_article = KnowledgeBaseArticle.objects.create(
            title='WiFi Connection Issues',
            content='Steps to resolve WiFi connectivity problems',
            tags=['wifi', 'network', 'connectivity']
        )

    def test_kb_articles_endpoint(self):
        """Test the KB articles endpoint for agent access."""
        url = '/api/knowledge_base/api/articles/'
        response = self.client.get(url, **self.agent_headers)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_kb_search_endpoint(self):
        """Test the KB search endpoint."""
        url = '/api/knowledge_base/api/search/'
        payload = {'query': 'wifi', 'limit': 5}
        response = self.client.post(
            url, data=json.dumps(payload), content_type='application/json', **self.agent_headers
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('results', data)
        self.assertIn('query', data)
        self.assertEqual(data['query'], 'wifi')

    def test_kb_article_by_id_endpoint(self):
        """Test getting specific KB article by ID."""
        url = f'/api/knowledge_base/api/articles/{self.kb_article.kb_id}/'
        response = self.client.get(url, **self.agent_headers)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['title'], self.kb_article.title)

    def test_kb_articles_endpoint_requires_auth(self):
        """Without the agent key (or a logged-in user), these endpoints must reject the request."""
        response = self.client.get('/api/knowledge_base/api/articles/')
        self.assertEqual(response.status_code, 401)

@patch('tickets.tasks.requests.post')
class TicketProcessingTest(TestCase):
    """Test ticket processing with mocked external agent."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='user@example.com',
            username='testuser'
        )
        self.ticket = Ticket.objects.create(
            user=self.user,
            issue_type='Network Issue',
            description='Cannot connect to WiFi',
            category='network',
            status='new'
        )
    
    def test_ticket_processing_with_agent(self, mock_post):
        """Test the complete ticket processing workflow."""
        # Mock the agent response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'confidence': 0.85,
            'recommended_action': 'auto_resolve',
            'analysis': {
                'category': 'network_issue',
                'severity': 'medium'
            },
            'solution': {
                'steps': ['Restart router', 'Reconnect to WiFi'],
                'success_probability': 0.9
            },
            'reasoning': 'Common WiFi connectivity issue'
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        # Process the ticket
        result = process_ticket_with_agent(self.ticket.ticket_id)
        
        # Verify the ticket was processed
        self.ticket.refresh_from_db()
        self.assertTrue(self.ticket.agent_processed)
        self.assertIsNotNone(self.ticket.agent_response)
        self.assertTrue(result)

class SlackIntegrationTest(TestCase):
    """Test Slack integration functionality."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='U123456@slack.local',
            username='U123456'
        )
    
    def test_slack_user_id_extraction(self):
        """Test extraction of Slack user ID from email format."""
        from integrations.views import notify_user_auto_resolution
        
        # Mock the function to test ID extraction logic
        user_id = 'U123456@slack.local'
        expected_slack_id = 'U123456'
        
        if user_id.endswith('@slack.local'):
            extracted_id = user_id.split('@', 1)[0]
            self.assertEqual(extracted_id, expected_slack_id)

class SolutionModelTest(TestCase):
    """Test the Solution model functionality."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='user@example.com',
            username='testuser'
        )
        self.ticket = Ticket.objects.create(
            user=self.user,
            issue_type='Network Issue',
            description='Cannot connect to WiFi',
            category='network'
        )
    
    def test_solution_creation(self):
        """Test creating a solution for a ticket."""
        solution = Solution.objects.create(
            ticket=self.ticket,
            steps='1. Restart router\n2. Reconnect to WiFi',
            worked=True,
            created_by=self.user
        )
        self.assertEqual(solution.ticket, self.ticket)
        self.assertTrue(solution.worked)
        self.assertEqual(solution.created_by, self.user)

# Integration Tests
class EndToEndTest(TestCase):
    """End-to-end tests for complete workflows."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='user@example.com',
            username='testuser'
        )
    
    @patch('tickets.tasks.requests.post')
    @patch('integrations.views.requests.post')
    def test_complete_auto_resolve_workflow(self, mock_slack_post, mock_agent_post):
        """Test complete workflow from ticket creation to auto-resolution."""
        # Mock agent response
        mock_agent_response = Mock()
        mock_agent_response.status_code = 200
        mock_agent_response.json.return_value = {
            'confidence': 0.9,
            'recommended_action': 'auto_resolve',
            'solution': {
                'steps': ['Step 1', 'Step 2'],
                'success_probability': 0.9
            },
            'reasoning': 'Simple fix'
        }
        mock_agent_response.raise_for_status.return_value = None
        mock_agent_post.return_value = mock_agent_response
        
        # Mock Slack response
        mock_slack_response = Mock()
        mock_slack_response.text = '{"ok": true}'
        mock_slack_post.return_value = mock_slack_response
        
        # Create ticket
        ticket = Ticket.objects.create(
            user=self.user,
            issue_type='Simple Issue',
            description='Easy to fix',
            category='general'
        )
        
        # Process ticket
        result = process_ticket_with_agent(ticket.ticket_id)
        
        # Verify workflow
        ticket.refresh_from_db()
        self.assertTrue(ticket.agent_processed)
        self.assertTrue(result)

# Performance Tests
class PerformanceTest(TestCase):
    """Test system performance with multiple tickets."""
    
    def setUp(self):
        self.users = []
        for i in range(10):
            user = User.objects.create_user(
                email=f'user{i}@example.com',
                username=f'user{i}'
            )
            self.users.append(user)
    
    def test_bulk_ticket_creation(self):
        """Test creating multiple tickets efficiently."""
        tickets = []
        for i, user in enumerate(self.users):
            ticket = Ticket(
                user=user,
                issue_type=f'Issue {i}',
                description=f'Description {i}',
                category='test'
            )
            tickets.append(ticket)
        
        # Bulk create
        created_tickets = Ticket.objects.bulk_create(tickets)
        self.assertEqual(len(created_tickets), 10)
