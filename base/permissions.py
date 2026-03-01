from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.owner == request.user


class IsAuthenticatedOrAgent(permissions.BasePermission):
    """
    Custom permission to allow authenticated users OR AI Agent with valid API key.
    """

    def has_permission(self, request, view):
        # Check if authenticated via JWT
        if request.user and request.user.is_authenticated:
            return True
        
        # Check if authenticated via Agent API Key
        # The AgentAPIKeyAuthentication sets request.user to None but request.auth to the API key
        if request.auth and request.user is None:
            # This means agent API key authentication succeeded
            return True
        
        return False
