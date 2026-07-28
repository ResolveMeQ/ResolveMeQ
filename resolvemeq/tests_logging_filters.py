from django.test import SimpleTestCase

from resolvemeq.logging_filters import SuppressTransientDbAdminEmailFilter
import logging


class SuppressTransientDbAdminEmailFilterTests(SimpleTestCase):
    def test_suppresses_dns_resolution_errors(self):
        filt = SuppressTransientDbAdminEmailFilter()
        record = logging.LogRecord(
            name="django.request",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="Internal Server Error: /api/tickets/reply-needed-count/",
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
