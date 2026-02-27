from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from .models import KnowledgeBaseArticle
from tickets.models import Ticket
import json
User = get_user_model()

class KnowledgeBaseTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User"
        )
        self.admin_user = User.objects.create_user(
            username="adminuser",
            email="admin@example.com",
            first_name="Admin",
            last_name="User",
            is_staff=True
        )
        self.client.force_authenticate(user=self.admin_user)

        # Create test KB articles
        self.kb_article1 = KnowledgeBaseArticle.objects.create(
            title="VPN Connection Issue",
            content="To resolve VPN connection issues:\n1. Check your internet connection\n2. Restart the VPN client\n3. Clear VPN cache",
            tags=["vpn", "network", "connection"]
        )
        self.kb_article2 = KnowledgeBaseArticle.objects.create(
            title="Printer Not Working",
            content="Common printer troubleshooting steps:\n1. Check if printer is powered on\n2. Verify network connection\n3. Clear print queue",
            tags=["printer", "hardware"]
        )

    def test_kb_article_creation(self):
        """Test creating a new KB article"""
        url = reverse('knowledgebasearticle-list')
        data = {
            'title': 'New KB Article',
            'content': 'Test content',
            'tags': ['test', 'new']
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(KnowledgeBaseArticle.objects.count(), 3)

    def test_kb_article_search(self):
        """Test searching KB articles"""
        url = reverse('knowledgebasearticle-search')
        data = {'query': 'VPN'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data['results']) > 0)
        self.assertTrue('VPN Connection Issue' in [r['title'] for r in response.data['results']])

    def test_kb_article_update(self):
        """Test updating a KB article"""
        url = reverse('knowledgebasearticle-detail', args=[self.kb_article1.kb_id])
        data = {
            'title': 'Updated VPN Issue',
            'content': self.kb_article1.content,
            'tags': self.kb_article1.tags
        }
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.kb_article1.refresh_from_db()
        self.assertEqual(self.kb_article1.title, 'Updated VPN Issue')

    def test_kb_article_delete(self):
        """Test deleting a KB article"""
        url = reverse('knowledgebasearticle-detail', args=[self.kb_article1.kb_id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(KnowledgeBaseArticle.objects.count(), 1)

    def test_kb_article_retrieval(self):
        """Test retrieving a specific KB article"""
        url = reverse('knowledgebasearticle-detail', args=[self.kb_article1.kb_id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'VPN Connection Issue')

    def test_unauthorized_access(self):
        """Test KB articles are accessible (AllowAny for FastAPI agent)"""
        self.client.force_authenticate(user=self.user)  # Non-admin user
        url = reverse('knowledgebasearticle-list')
        response = self.client.get(url)
        # Knowledge base is publicly accessible for the FastAPI agent
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_kb_article_tag_filtering(self):
        """Test filtering KB articles by tags"""
        url = reverse('knowledgebasearticle-list')
        response = self.client.get(url, {'tags': 'vpn'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'VPN Connection Issue')

    def test_kb_article_content_search(self):
        """Test searching KB articles by content"""
        url = reverse('knowledgebasearticle-search')
        data = {'query': 'printer troubleshooting'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data['results']) > 0)
        self.assertTrue('Printer Not Working' in [r['title'] for r in response.data['results']])
