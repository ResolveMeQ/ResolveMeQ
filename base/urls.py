from django.urls import path
from rest_framework_simplejwt.views import (

    TokenRefreshView,
)

from . import views

urlpatterns = [
    path('register/', views.RegisterAPIView.as_view(), name='register'),
    path('login/', views.LoginAPIView.as_view(),
         name='login'),
    path('verify-user/', views.VerifyUserAPIView.as_view(), name='verify-user'),
    path('reset-passwprd/', views.ResetPasswordAPIView.as_view(),
         name='rest-password'),
    path('change-password/', views.ChangePasswordAPIView.as_view(), name='change-password'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('profile/', views.CurrentUserProfileView.as_view(), name='profile'),
    path('preferences/', views.CurrentUserPreferencesView.as_view(), name='preferences'),
    path('notifications/', views.InAppNotificationListView.as_view(), name='notifications-list'),
    path('notifications/<uuid:notification_id>/read/', views.InAppNotificationMarkReadView.as_view(), name='notification-mark-read'),
    path('notifications/read-all/', views.InAppNotificationMarkAllReadView.as_view(), name='notifications-mark-all-read'),

    path('resend-verification-code/', views.ResendVerificationCodeAPIView.as_view(), name='resend-verification-code'),

]
