from django.urls import path
from .views import (
    UserListView,
    TeamMembersListView,
    UserDetailView,
    UserCreateView,
    UserUpdateView,
    UserDeleteView,
)

urlpatterns = [
    path('', UserListView.as_view(), name='user-list'),
    path('team-members/', TeamMembersListView.as_view(), name='user-team-members'),
    path('create/', UserCreateView.as_view(), name='user-create'),
    path('<uuid:pk>/', UserDetailView.as_view(), name='user-detail'),
    path('<uuid:pk>/update/', UserUpdateView.as_view(), name='user-update'),
    path('<uuid:pk>/delete/', UserDeleteView.as_view(), name='user-delete'),
]
