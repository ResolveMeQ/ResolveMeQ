from rest_framework.permissions import BasePermission


class PartnerScopePermission(BasePermission):
    """Require an authenticated partner principal with a given scope."""

    required_scope = ""

    def has_permission(self, request, view):
        key = getattr(request.user, "api_key", None)
        if not key:
            return False
        scope = self.required_scope or getattr(view, "partner_scope", None) or ""
        if not scope:
            return True
        return key.has_scope(scope)


class PartnerTicketsRead(PartnerScopePermission):
    required_scope = "tickets:read"


class PartnerTicketsWrite(PartnerScopePermission):
    required_scope = "tickets:write"


class PartnerWorkflowsRead(PartnerScopePermission):
    required_scope = "workflows:read"


class PartnerRulesRead(PartnerScopePermission):
    required_scope = "rules:read"


class PartnerAuthenticated(PartnerScopePermission):
    required_scope = ""
