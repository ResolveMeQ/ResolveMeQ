from django.test import TestCase
from unittest.mock import patch, MagicMock
from .metrics import AgentMetrics


class AgentMetricsTest(TestCase):
    """Test suite for AgentMetrics monitoring functionality."""

    @patch('monitoring.metrics.capture_message')
    @patch('monitoring.metrics.set_tag')
    @patch('monitoring.metrics.set_context')
    def test_track_autonomous_action_success(self, mock_set_context, mock_set_tag, mock_capture):
        """Test tracking successful autonomous actions."""
        AgentMetrics.track_autonomous_action(
            action_type='AUTO_RESOLVE',
            ticket_id='TKT-001',
            confidence=0.95,
            success=True
        )
        
        # Verify tags were set
        mock_set_tag.assert_any_call('action_type', 'AUTO_RESOLVE')
        mock_set_tag.assert_any_call('success', True)
        
        # Verify context was set
        mock_set_context.assert_called_once()
        
        # No capture_message for successful actions
        mock_capture.assert_not_called()

    @patch('monitoring.metrics.capture_message')
    @patch('monitoring.metrics.set_tag')
    @patch('monitoring.metrics.set_context')
    def test_track_autonomous_action_failure(self, mock_set_context, mock_set_tag, mock_capture):
        """Test tracking failed autonomous actions."""
        AgentMetrics.track_autonomous_action(
            action_type='ESCALATE',
            ticket_id='TKT-002',
            confidence=0.75,
            success=False
        )
        
        # Verify failure was tracked
        mock_set_tag.assert_any_call('success', False)
        
        # Failure should trigger capture_message
        mock_capture.assert_called_once()
        call_args = mock_capture.call_args
        self.assertIn('failed', call_args[0][0].lower())

    @patch('monitoring.metrics.capture_exception')
    @patch('monitoring.metrics.set_context')
    @patch('monitoring.metrics.set_tag')
    def test_track_agent_error(self, mock_set_tag, mock_set_context, mock_capture_exception):
        """Test error tracking."""
        test_error = ValueError("Test error")
        
        AgentMetrics.track_agent_error(
            error=test_error,
            ticket_id='TKT-003',
            context={'action': 'AUTO_ASSIGN'}
        )
        
        # Verify exception capture
        mock_capture_exception.assert_called_once_with(test_error)
        mock_set_context.assert_called_once()
        mock_set_tag.assert_any_call('component', 'autonomous_agent')
        mock_set_tag.assert_any_call('ticket_id', 'TKT-003')

    @patch('monitoring.metrics.capture_message')
    @patch('monitoring.metrics.set_context')
    @patch('monitoring.metrics.set_tag')
    def test_track_confidence_score_high(self, mock_set_tag, mock_set_context, mock_capture):
        """Test confidence score tracking for high confidence."""
        AgentMetrics.track_confidence_score(
            ticket_id='TKT-004',
            confidence=0.88,
            category='network'
        )
        
        # Verify context was set
        mock_set_context.assert_called_once()
        mock_set_tag.assert_any_call('ticket_category', 'network')
        
        # No alert for high confidence
        mock_capture.assert_not_called()

    @patch('monitoring.metrics.capture_message')
    @patch('monitoring.metrics.set_context')
    @patch('monitoring.metrics.set_tag')
    def test_track_confidence_score_low(self, mock_set_tag, mock_set_context, mock_capture):
        """Test confidence score tracking for very low confidence."""
        AgentMetrics.track_confidence_score(
            ticket_id='TKT-005',
            confidence=0.25,
            category='printer'
        )
        
        # Verify context was set
        mock_set_context.assert_called_once()
        
        # Alert should be triggered for very low confidence
        mock_capture.assert_called_once()
        call_args = mock_capture.call_args
        self.assertIn('low confidence', call_args[0][0].lower())
