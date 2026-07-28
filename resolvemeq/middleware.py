"""
Catch transient DB/DNS failures for the whole request stack.

Auth/session middleware and every API view can hit Postgres. Endpoint-level
try/except misses failures during auth, and Django turns view exceptions into
500s (admin emails) unless process_exception returns a response.
"""
from __future__ import annotations

import logging

from django.db import close_old_connections
from django.db.utils import InterfaceError, OperationalError
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from resolvemeq.db_errors import is_dns_resolution_error, is_transient_db_error

logger = logging.getLogger(__name__)


class TransientDatabaseErrorMiddleware(MiddlewareMixin):
    def __call__(self, request):
        # Wrap middleware/session DB hits that raise outside the view handler.
        try:
            return super().__call__(request)
        except (OperationalError, InterfaceError) as exc:
            response = self._handle(request, exc, where="middleware")
            if response is not None:
                return response
            raise

    def process_exception(self, request, exception):
        # View-layer OperationalError (notifications, escalated, webhooks, …).
        if not isinstance(exception, (OperationalError, InterfaceError)):
            return None
        return self._handle(request, exception, where="view")

    def _handle(self, request, exc, *, where: str):
        if not is_transient_db_error(exc):
            return None

        logger.warning(
            "Transient DB error on %s %s (%s): %s",
            request.method,
            request.path,
            where,
            exc,
        )
        close_old_connections()

        # DNS never opened a connection — one retry is safe for all methods.
        if is_dns_resolution_error(exc) or request.method in ("GET", "HEAD", "OPTIONS"):
            try:
                # Only re-enter the full stack for middleware-raised errors.
                if where == "middleware":
                    return super().__call__(request)
            except (OperationalError, InterfaceError) as retry_exc:
                if not is_transient_db_error(retry_exc):
                    raise
                logger.warning(
                    "Transient DB error on %s %s (retry failed): %s",
                    request.method,
                    request.path,
                    retry_exc,
                )

        return self._unavailable(request)

    @staticmethod
    def _unavailable(request):
        # Returning a response here prevents Django's 500 → AdminEmailHandler path.
        return JsonResponse(
            {
                "detail": "Database temporarily unavailable. Please retry shortly.",
                "degraded": True,
            },
            status=503,
        )
