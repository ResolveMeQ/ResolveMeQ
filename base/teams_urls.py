from django.urls import path
from .views import (
    TeamListView,
    TeamDetailView,
    TeamCreateView,
    TeamUpdateView,
    TeamDeleteView,
    TeamLimitsView,
    TeamInviteView,
    TeamInvitationListView,
    TeamInvitationAcceptView,
    TeamInvitationDeclineView,
    TeamLeaveView,
    TeamRemoveMemberView,
)

urlpatterns = [
    path('', TeamListView.as_view(), name='team-list'),
    path('limits/', TeamLimitsView.as_view(), name='team-limits'),
    path('create/', TeamCreateView.as_view(), name='team-create'),
    path('invitations/', TeamInvitationListView.as_view(), name='team-invitations-list'),
    path('invitations/<uuid:invitation_id>/accept/', TeamInvitationAcceptView.as_view(), name='team-invitation-accept'),
    path('invitations/<uuid:invitation_id>/decline/', TeamInvitationDeclineView.as_view(), name='team-invitation-decline'),
    path('<uuid:pk>/', TeamDetailView.as_view(), name='team-detail'),
    path('<uuid:pk>/update/', TeamUpdateView.as_view(), name='team-update'),
    path('<uuid:pk>/delete/', TeamDeleteView.as_view(), name='team-delete'),
    path('<uuid:pk>/invite/', TeamInviteView.as_view(), name='team-invite'),
    path('<uuid:pk>/leave/', TeamLeaveView.as_view(), name='team-leave'),
    path('<uuid:pk>/members/remove/', TeamRemoveMemberView.as_view(), name='team-remove-member'),
]
