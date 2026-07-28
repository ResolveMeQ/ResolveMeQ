from django.db.utils import OperationalError
from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase

from resolvemeq.db_errors import is_dns_resolution_error, is_transient_db_error
from resolvemeq.middleware import TransientDatabaseErrorMiddleware
from resolvemeq.logging_filters import SuppressTransientDbAdminEmailFilter
import logging


class DbErrorHelperTests(SimpleTestCase):
    def test_detects_supabase_dns_error(self):
        exc = OperationalError(
            'could not translate host name "aws-1-eu-west-3.pooler.supabase.com" '
            "to address: Name or service not known"
        )
        self.assertTrue(is_dns_resolution_error(exc))
        self.assertTrue(is_transient_db_error(exc))


class TransientDatabaseErrorMiddlewareTests(SimpleTestCase):
    def test_process_exception_returns_503_for_any_api_path(self):
        factory = RequestFactory()
        for path in (
            "/api/tickets/reply-needed-count/",
            "/api/auth/notifications/",
            "/api/billing/webhooks/dodo/",
            "/api/tickets/escalated/",
        ):
            request = factory.get(path)
            middleware = TransientDatabaseErrorMiddleware(lambda r: None)
            response = middleware.process_exception(
                request,
                OperationalError(
                    'could not translate host name "aws-1-eu-west-3.pooler.supabase.com" '
                    "to address: Name or service not known"
                ),
            )
            self.assertIsInstance(response, JsonResponse)
            self.assertEqual(response.status_code, 503)
            self.assertTrue(response.json().get("degraded"))

    def test_process_exception_ignores_non_transient(self):
        factory = RequestFactory()
        request = factory.get("/api/tickets/")
        middleware = TransientDatabaseErrorMiddleware(lambda r: None)
        self.assertIsNone(
            middleware.process_exception(
                request, OperationalError("permission denied for table tickets")
            )
        )


class SuppressTransientDbAdminEmailFilterTests(SimpleTestCase):
    def test_suppresses_dns_resolution_errors(self):
        filt = SuppressTransientDbAdminEmailFilter()
        record = logging.LogRecord(
            name="django.request",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="Internal Server Error: /api/auth/notifications/",
            args=(),
            exc_info=(
                Exception,
                Exception(
                    'could not translate host name "aws-1-eu-west-3.pooler.supabase.com" '
                    "to address: Name or service not known"
                ),
                None,
            ),
        )
        self.assertFalse(filt.filter(record))

    def test_allows_unrelated_errors(self):
        filt = SuppressTransientDbAdminEmailFilter()
        record = logging.LogRecord(
            name="django.request",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="Internal Server Error: /api/tickets/",
            args=(),
            exc_info=(Exception, Exception("ValueError: bad payload"), None),
        )
        self.assertTrue(filt.filter(record))
