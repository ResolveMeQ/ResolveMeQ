import logging
from datetime import timedelta
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.conf import settings as django_settings
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, permissions, generics
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from base.models import Profile
from base.google_auth import username_from_email, verify_google_id_token
from base.serializers import RegisterSerializer, LoginSerializer, GoogleAuthSerializer, UserProfileSerializer, VerifyUserSerializer, \
    ChangePasswordSerializer, ResetPasswordSerializer, ForgotPasswordRequestSerializer, ResendVerificationCodeSerializer, UserManagementSerializer, \
    TeamSerializer, UserPreferencesSerializer, InAppNotificationSerializer
from base.tasks import dispatch_send_email_with_template
from base.utils import generate_secure_code

User = get_user_model()
logger = logging.getLogger(__name__)


def _send_team_invitation_email(invitation, team, invited_by):
    """Email the invitee with link to Teams (sign in with invited email to accept)."""
    frontend = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173').rstrip('/')
    inviter_name = invited_by.get_full_name() or invited_by.email
    context = {
        'app_name': getattr(settings, 'APP_NAME', 'ResolveMeQ'),
        'team_name': team.name,
        'inviter_name': inviter_name,
        'inviter_email': invited_by.email,
        'invitee_email': invitation.email,
        'teams_url': f'{frontend}/teams',
        'signup_url': f'{frontend}/signup',
    }
    data = {
        'subject': f'{inviter_name} invited you to join {team.name} on {context["app_name"]}',
    }
    try:
        dispatch_send_email_with_template(data, 'team_invitation.html', context, [invitation.email])
    except Exception as exc:
        logger.exception('Team invitation email failed: %s', exc)


def _notify_existing_user_team_invitation(invitation, team, invited_by):
    """Bell notification when the invitee already has an account."""
    from base.models import InAppNotification

    invitee = User.objects.filter(email__iexact=invitation.email).first()
    if not invitee:
        return
    inviter_name = invited_by.get_full_name() or invited_by.email
    try:
        InAppNotification.objects.create(
            user=invitee,
            type=InAppNotification.Type.INFO,
            title=f'Team invitation: {team.name}',
            message=f'{inviter_name} invited you to join this team. Open Teams to accept or decline.',
            link='/teams',
        )
    except Exception as exc:
        logger.warning('Team invitation in-app notification failed: %s', exc)


class RegisterAPIView(GenericAPIView):
    """
    API view for user registration.
    """
    serializer_class = RegisterSerializer

    @swagger_auto_schema(
        operation_description="Register a new user",
        responses={
            200: openapi.Response("Account created successfully"),
            400: openapi.Response("Invalid token or email"),
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                password = serializer.validated_data['password']
                user = serializer.save()
                user.set_password(password)

                if not user.secure_code:
                    user.generate_new_secure_code()

                user.save()

                # All database operations completed successfully

            # Email sending outside transaction since it's an external operation
            data = {
                "subject": "Verify your email",
            }
            context = {
                "email": user.email,
                "token": user.secure_code,
                "username": user.username,
                "expiration": user.secure_code_expiry,
                "app_name": "ResolveMeQ",
                "verification_link": f"{settings.FRONTEND_URL}/verify?token={quote(str(user.secure_code))}&email={quote(user.email)}",
            }
            dispatch_send_email_with_template(data, 'welcome.html', context, [user.email])
            print("Email sent to:", user.email)
            print("With token:", user.secure_code)

            return Response({
                "Message": "Successfully registered"
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({
                "error": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class VerifyUserAPIView(GenericAPIView):
    """
    API view for verifying user email using a verification token.
    """
    serializer_class = VerifyUserSerializer

    @swagger_auto_schema(
        operation_description="Verify user email using verification token",
        responses={
            200: openapi.Response("User verified successfully"),
            400: openapi.Response("Invalid token or email"),
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({
            "message": "User verified successfully"
        }, status=status.HTTP_200_OK)


class LoginAPIView(GenericAPIView):
    """
    API view for user login.
    """
    serializer_class = LoginSerializer

    @swagger_auto_schema(
        operation_description="Login a user",
        responses={
            200: openapi.Response("User login successfully"),
            400: openapi.Response("Invalid credentials or user not verified"),
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        user = User.objects.get(email=email)

        if not user.is_verified:
            return Response({
                "message": "User is not verified. Please verify your email first.",
            }, status=status.HTTP_403_FORBIDDEN)

        token = RefreshToken.for_user(user)
        access_token = token.access_token
        return Response({
            "message": "Successfully logged in",
            "email": email,
            "access_token": str(access_token),
            "refresh_token": str(token),
        }, status=status.HTTP_200_OK)


class GoogleAuthAPIView(GenericAPIView):
    """Exchange a Google ID token (credential JWT) for ResolveMeQ JWTs."""

    permission_classes = [permissions.AllowAny]
    serializer_class = GoogleAuthSerializer

    @swagger_auto_schema(
        operation_description="Sign in or register with a Google ID token",
        responses={
            200: openapi.Response("JWTs issued"),
            400: openapi.Response("Invalid token or email"),
            409: openapi.Response("Email linked to another Google account"),
            503: openapi.Response("Google OAuth not configured"),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        credential = serializer.validated_data["credential"]

        try:
            idinfo = verify_google_id_token(credential)
        except RuntimeError:
            return Response(
                {
                    "error": (
                        "Google sign-in is not configured on the server. "
                        "Set environment variable GOOGLE_OAUTH_CLIENT_ID to your OAuth Web client ID "
                        "(same value as VITE_GOOGLE_CLIENT_ID on the frontend)."
                    ),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except ValueError:
            return Response(
                {"error": "Invalid or expired Google sign-in token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not idinfo.get("email_verified", False):
            return Response(
                {"error": "Google email is not verified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = User.objects.normalize_email((idinfo.get("email") or "").strip())
        if not email:
            return Response(
                {"error": "Google did not return an email address."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sub = idinfo.get("sub")
        if not sub:
            return Response(
                {"error": "Invalid Google token payload."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        first = (idinfo.get("given_name") or "")[:150]
        last = (idinfo.get("family_name") or "")[:150]

        with transaction.atomic():
            user = User.objects.filter(google_sub=sub).first()
            if user is None:
                user = User.objects.filter(email__iexact=email).first()
                if user:
                    if user.google_sub and user.google_sub != sub:
                        return Response(
                            {
                                "error": "This email is already linked to another Google account.",
                            },
                            status=status.HTTP_409_CONFLICT,
                        )
                    user.google_sub = sub
                    user.is_verified = True
                    user.is_active = True
                    update_fields = ["google_sub", "is_verified", "is_active"]
                    if first and not user.first_name:
                        user.first_name = first
                        update_fields.append("first_name")
                    if last and not user.last_name:
                        user.last_name = last
                        update_fields.append("last_name")
                    user.save(update_fields=update_fields)
                else:
                    user = User.objects.create_user(
                        email=email,
                        password=None,
                        username=username_from_email(User, email),
                        first_name=first,
                        last_name=last,
                    )
                    User.objects.filter(pk=user.pk).update(
                        google_sub=sub,
                        is_verified=True,
                        is_active=True,
                        secure_code=None,
                        secure_code_expiry=None,
                    )
                    user.refresh_from_db()

        token = RefreshToken.for_user(user)
        access_token = token.access_token
        return Response(
            {
                "message": "Successfully signed in with Google",
                "email": user.email,
                "access_token": str(access_token),
                "refresh_token": str(token),
            },
            status=status.HTTP_200_OK,
        )


class ChangePasswordAPIView(GenericAPIView):
    """
    API view for requesting a password reset.
    """
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Forgot password request",
        responses={
            200: openapi.Response("New code or token send successfully"),
            400: openapi.Response("Invalid  email"),
        }
    )
    def post(self, request, *args, **kwargs):
        """
          Handle password change request  and the user must be login to carry out this request.
        :param request:
        :param args:
        :param kwargs:
        :return: updated user password in the system
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        new_password = serializer.validated_data['new_password']
        user.set_password(new_password)
        user.save()
        return Response({
            "message": "Password changed successfully",
            "email": user.email
        }, status=status.HTTP_200_OK)


class ResetPasswordAPIView(GenericAPIView):
    """
    API view for resetting the user's password using a reset token.
    """
    serializer_class = ResetPasswordSerializer
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        operation_description="Reset user password with token",
        responses={
            200: openapi.Response("Password reset successfully"),
            400: openapi.Response("Invalid token or password validation failed"),
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        serializer.save()

        return Response({
            "message": "Password reset successfully"
        }, status=status.HTTP_200_OK)


class ForgotPasswordRequestAPIView(GenericAPIView):
    """
    Request a password reset email. Sends reset link to verified users only.
    Always returns success to prevent email enumeration.
    """
    serializer_class = ForgotPasswordRequestSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        ip_address = request.META.get('REMOTE_ADDR')
        cache_key = f"forgot_password_{ip_address}"
        if cache.get(cache_key):
            return Response({"message": "If this email is registered, you will receive reset instructions."}, status=status.HTTP_200_OK)
        cache.set(cache_key, True, timeout=60)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        try:
            user = User.objects.get(email=email)
            if not user.is_verified:
                # Don't send; return success anyway for security
                return Response({"message": "If this email is registered, you will receive reset instructions."}, status=status.HTTP_200_OK)
            user.secure_code = generate_secure_code()
            user.secure_code_expiry = timezone.now() + timedelta(minutes=60)
            user.save(update_fields=['secure_code', 'secure_code_expiry'])
            reset_url = f"{settings.FRONTEND_URL}/reset-password?token={quote(str(user.secure_code))}&email={quote(user.email)}"
            app_name = getattr(settings, 'APP_NAME', 'ResolveMeQ')
            support = getattr(settings, 'SUPPORT_EMAIL', '') or ''
            data = {'subject': f'Reset your {app_name} password'}
            context = {
                'user': user,
                'reset_url': reset_url,
                'token': user.secure_code,
                'app_name': app_name,
                'support_email': support,
                'frontend_url': getattr(settings, 'FRONTEND_URL', '').rstrip('/'),
                'validity_minutes': 60,
            }
            dispatch_send_email_with_template(data, 'reset_password.html', context, [user.email])
        except User.DoesNotExist:
            pass  # Don't reveal; return success anyway
        return Response({"message": "If this email is registered, you will receive reset instructions."}, status=status.HTTP_200_OK)


class ResendVerificationCodeAPIView(GenericAPIView):
    """
    API view for resending the verification code to the user's email.
    """
    serializer_class = ResendVerificationCodeSerializer

    @swagger_auto_schema(
        operation_description="Resend verification code to user's email",
        responses={
            200: openapi.Response("Verification code resent successfully"),
            400: openapi.Response("Invalid email or user not found"),
        }
    )
    def post(self, request, *args, **kwargs):
        """
        Resend verification code to the user's email.
        :param request: The HTTP request containing the email.
        :return: A response indicating the success or failure of the operation.
        200: openapi.Response("Verification code resent successfully"),
        400: openapi.Response("Invalid email or user not found"),
        """
        ip_address = request.META.get('REMOTE_ADDR')
        cache_key = f"resend_verification_{ip_address}"

        if cache.get(cache_key):
            return Response({
                "error": "Too many requests. Please try again later."
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        cache.set(cache_key, True, timeout=60)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        user = User.objects.get(email=email)
        user.secure_code = generate_secure_code()
        user.secure_code_expiry = timezone.now() + timedelta(minutes=10)
        user.save(update_fields=['secure_code', 'secure_code_expiry'])
        data = {
            "subject": "Resend verification code",

        }
        context = {
            "email": user.email,
            "token": user.secure_code,
            "username": user.username,
            "expiration": user.secure_code_expiry,
            "app_name": "ResolveMeQ",
            "verification_link": settings.FRONTEND_URL + '/verify?token=' + str(user.secure_code) + '&email=' + quote(user.email),
        }
        dispatch_send_email_with_template(data, 'welcome.html', context, [user.email])
        return Response({
            "message": "Verification code resent successfully."
        }, status=status.HTTP_200_OK)


class CurrentUserProfileView(GenericAPIView):
    """
    Manage the current user's profile at a fixed endpoint.
    Accepts JSON (for bio, location, city) or multipart/form-data (for profile image).
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    serializer_class = UserProfileSerializer

    def get_object(self):
        return get_object_or_404(Profile, user=self.request.user)

    def get(self, request):
        profile = self.get_object()
        serializer = self.get_serializer(profile)
        return Response(serializer.data)

    def patch(self, request):
        profile = self.get_object()
        serializer = self.get_serializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        profile = self.get_object()
        profile.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserPreferencesView(GenericAPIView):
    """
    Manage the current user's preferences.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserPreferencesSerializer

    def get_object(self):
        from base.models import UserPreferences
        # Get or create preferences for the current user
        preferences, created = UserPreferences.objects.get_or_create(user=self.request.user)
        return preferences

    def get(self, request):
        preferences = self.get_object()
        serializer = self.get_serializer(preferences)
        return Response(serializer.data)

    def patch(self, request):
        preferences = self.get_object()
        serializer = self.get_serializer(preferences, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        preferences = self.get_object()
        serializer = self.get_serializer(preferences, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# In-app notifications (header bell)
class InAppNotificationListView(GenericAPIView):
    """List in-app notifications for the current user."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = InAppNotificationSerializer

    def get_queryset(self):
        from base.models import InAppNotification
        return InAppNotification.objects.filter(user=self.request.user)

    def get(self, request):
        from base.models import InAppNotification
        notifications = InAppNotification.objects.filter(user=request.user).order_by('-created_at')[:50]
        serializer = InAppNotificationSerializer(notifications, many=True)
        return Response(serializer.data)


class InAppNotificationMarkReadView(GenericAPIView):
    """Mark a single notification as read."""
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, notification_id):
        from base.models import InAppNotification
        notification = get_object_or_404(
            InAppNotification,
            id=notification_id,
            user=request.user
        )
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response({'status': 'ok'})


class InAppNotificationMarkAllReadView(GenericAPIView):
    """Mark all notifications as read for the current user."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from base.models import InAppNotification
        updated = InAppNotification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'marked_read': updated})


# User Management Views
class UserListView(generics.ListAPIView):
    """List all users (e.g. for admin)."""
    queryset = User.objects.all()
    serializer_class = UserManagementSerializer
    permission_classes = [permissions.IsAuthenticated]


class TeamMembersListView(generics.ListAPIView):
    """List users who are in at least one team with the current user (team colleagues)."""
    serializer_class = UserManagementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        from base.models import Team
        user = self.request.user
        my_teams = Team.objects.filter(Q(owner=user) | Q(members=user)).values_list('pk', flat=True)
        return User.objects.filter(
            Q(owned_teams__pk__in=my_teams) | Q(teams__pk__in=my_teams)
        ).distinct().order_by('email')


class UserDetailView(generics.RetrieveAPIView):
    """Get user details"""
    queryset = User.objects.all()
    serializer_class = UserManagementSerializer
    permission_classes = [permissions.IsAuthenticated]


class UserCreateView(generics.CreateAPIView):
    """Create new user (admin only)"""
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.IsAuthenticated]


class UserUpdateView(generics.UpdateAPIView):
    """Update user"""
    queryset = User.objects.all()
    serializer_class = UserManagementSerializer
    permission_classes = [permissions.IsAuthenticated]


class UserDeleteView(generics.DestroyAPIView):
    """Delete user"""
    queryset = User.objects.all()
    permission_classes = [permissions.IsAuthenticated]


# ============= Team Management Views =============

class TeamListView(generics.ListAPIView):
    """List teams the current user owns or is a member of."""
    from base.models import Team
    serializer_class = TeamSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        from base.models import Team
        user = self.request.user
        return Team.objects.filter(
            Q(owner=user) | Q(members=user)
        ).distinct()


class TeamDetailView(generics.RetrieveAPIView):
    """Get team details (only if user is owner or member)."""
    from base.models import Team
    serializer_class = TeamSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        from base.models import Team
        user = self.request.user
        return Team.objects.filter(
            Q(owner=user) | Q(members=user)
        ).distinct()


class TeamLimitsView(GenericAPIView):
    """Return team creation limits for the current plan (teams owned by user)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from base.models import Team
        from base.billing_views import get_max_teams_for_user
        max_teams = get_max_teams_for_user(request.user)
        current_count = Team.objects.filter(owner=request.user).count()
        return Response({
            'max_teams': max_teams,
            'current_count': current_count,
            'can_create': current_count < max_teams,
        })


class TeamCreateView(generics.CreateAPIView):
    """Create new team (respects plan limit). Caller becomes owner and is added as member."""
    from base.models import Team
    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        from base.models import Team
        from base.billing_views import get_max_teams_for_user
        max_teams = get_max_teams_for_user(self.request.user)
        current_count = Team.objects.filter(owner=self.request.user).count()
        if current_count >= max_teams:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(
                detail=f'Team limit reached ({max_teams} teams). Upgrade your plan to create more teams.'
            )
        team = serializer.save(owner=self.request.user)
        team.members.add(self.request.user)


class TeamUpdateView(generics.UpdateAPIView):
    """Update team (owner only)."""
    from base.models import Team
    serializer_class = TeamSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        from base.models import Team
        return Team.objects.filter(owner=self.request.user)


class TeamDeleteView(generics.DestroyAPIView):
    """Delete team (owner only)."""
    from base.models import Team
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        from base.models import Team
        return Team.objects.filter(owner=self.request.user)


# ---------- Team invitations (owner invites by email; invitee accepts/declines) ----------

class TeamInviteView(GenericAPIView):
    """Invite a user to the team by email (owner only). Respects plan max_members."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        from base.models import Team, TeamInvitation
        from base.billing_views import get_plan_for_user
        team = get_object_or_404(Team, pk=pk)
        if team.owner_id != request.user.id:
            return Response({'error': 'Only the team owner can invite members.'}, status=status.HTTP_403_FORBIDDEN)
        email = (request.data.get('email') or '').strip().lower()
        if not email:
            return Response({'error': 'email is required.'}, status=status.HTTP_400_BAD_REQUEST)
        plan = get_plan_for_user(request.user)
        max_members = plan.max_members if plan else 50
        current = team.members.count()
        pending = TeamInvitation.objects.filter(team=team, status=TeamInvitation.Status.PENDING).count()
        if current + pending >= max_members:
            return Response(
                {'error': f'Team member limit reached ({max_members} per team). Upgrade your plan for more.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if team.members.filter(email__iexact=email).exists():
            return Response({'error': 'This user is already a member.'}, status=status.HTTP_400_BAD_REQUEST)
        inv, created = TeamInvitation.objects.get_or_create(
            team=team,
            email=email,
            defaults={'invited_by': request.user, 'status': TeamInvitation.Status.PENDING}
        )
        if not created:
            if inv.status != TeamInvitation.Status.PENDING:
                return Response({'error': 'An invitation was already sent and processed.'}, status=status.HTTP_400_BAD_REQUEST)
        if created:
            _send_team_invitation_email(inv, team, request.user)
            _notify_existing_user_team_invitation(inv, team, request.user)
        return Response({
            'id': str(inv.id),
            'team_id': str(team.id),
            'email': inv.email,
            'status': inv.status,
        }, status=status.HTTP_201_CREATED)


class TeamSentInvitationsListView(GenericAPIView):
    """List pending invitations the owner sent for this team."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, team_id):
        from base.models import Team, TeamInvitation
        team = get_object_or_404(Team, pk=team_id)
        if team.owner_id != request.user.id:
            return Response({'error': 'Only the team owner can view sent invitations.'}, status=status.HTTP_403_FORBIDDEN)
        qs = TeamInvitation.objects.filter(
            team=team,
            status=TeamInvitation.Status.PENDING,
        ).select_related('invited_by').order_by('-created_at')
        out = [
            {
                'id': str(inv.id),
                'email': inv.email,
                'created_at': inv.created_at.isoformat(),
                'invited_by_email': inv.invited_by.email,
            }
            for inv in qs
        ]
        return Response(out)


class TeamInvitationResendView(GenericAPIView):
    """Resend invitation email (owner only). Does not duplicate in-app notifications."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, invitation_id):
        from base.models import TeamInvitation
        inv = get_object_or_404(TeamInvitation, id=invitation_id)
        if inv.team.owner_id != request.user.id:
            return Response({'error': 'Only the team owner can resend invitations.'}, status=status.HTTP_403_FORBIDDEN)
        if inv.status != TeamInvitation.Status.PENDING:
            return Response({'error': 'This invitation is no longer pending.'}, status=status.HTTP_400_BAD_REQUEST)
        _send_team_invitation_email(inv, inv.team, inv.invited_by)
        return Response({'message': 'Invitation email sent again.'})


class TeamInvitationOwnerCancelView(GenericAPIView):
    """Revoke a pending invitation (owner only)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, invitation_id):
        from base.models import TeamInvitation
        inv = get_object_or_404(TeamInvitation, id=invitation_id)
        if inv.team.owner_id != request.user.id:
            return Response({'error': 'Only the team owner can cancel invitations.'}, status=status.HTTP_403_FORBIDDEN)
        if inv.status != TeamInvitation.Status.PENDING:
            return Response({'error': 'This invitation is no longer pending.'}, status=status.HTTP_400_BAD_REQUEST)
        inv.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TeamInvitationListView(GenericAPIView):
    """List pending invitations for the current user (where invitee email matches)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from base.models import TeamInvitation
        email = request.user.email.lower()
        invitations = TeamInvitation.objects.filter(
            email=email,
            status=TeamInvitation.Status.PENDING
        ).select_related('team', 'invited_by').order_by('-created_at')
        out = [
            {
                'id': str(inv.id),
                'team_id': str(inv.team_id),
                'team_name': inv.team.name,
                'invited_by_email': inv.invited_by.email,
                'invited_by_name': inv.invited_by.get_full_name() or inv.invited_by.email,
                'created_at': inv.created_at.isoformat(),
            }
            for inv in invitations
        ]
        return Response(out)


class TeamInvitationAcceptView(GenericAPIView):
    """Accept an invitation (invitee only)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, invitation_id):
        from base.models import TeamInvitation
        from base.billing_views import get_plan_for_user
        inv = get_object_or_404(TeamInvitation, id=invitation_id)
        if inv.status != TeamInvitation.Status.PENDING:
            return Response({'error': 'This invitation is no longer valid.'}, status=status.HTTP_400_BAD_REQUEST)
        if inv.email.lower() != request.user.email.lower():
            return Response({'error': 'This invitation was sent to another email.'}, status=status.HTTP_403_FORBIDDEN)
        plan = get_plan_for_user(inv.team.owner)
        max_members = plan.max_members if plan else 50
        if inv.team.members.count() >= max_members:
            return Response({'error': 'Team is full.'}, status=status.HTTP_400_BAD_REQUEST)
        inv.team.members.add(request.user)
        inv.status = TeamInvitation.Status.ACCEPTED
        inv.save(update_fields=['status'])
        return Response({'message': f'You joined {inv.team.name}.'})


class TeamInvitationDeclineView(GenericAPIView):
    """Decline an invitation (invitee only)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, invitation_id):
        from base.models import TeamInvitation
        inv = get_object_or_404(TeamInvitation, id=invitation_id)
        if inv.status != TeamInvitation.Status.PENDING:
            return Response({'error': 'This invitation is no longer valid.'}, status=status.HTTP_400_BAD_REQUEST)
        if inv.email.lower() != request.user.email.lower():
            return Response({'error': 'This invitation was sent to another email.'}, status=status.HTTP_403_FORBIDDEN)
        inv.status = TeamInvitation.Status.DECLINED
        inv.save(update_fields=['status'])
        return Response({'message': 'Invitation declined.'})


class TeamLeaveView(GenericAPIView):
    """Leave a team (member only; owner cannot leave)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        from base.models import Team
        team = get_object_or_404(Team, pk=pk)
        if team.owner_id == request.user.id:
            return Response({'error': 'Owner cannot leave. Transfer ownership or delete the team.'}, status=status.HTTP_400_BAD_REQUEST)
        if not team.members.filter(pk=request.user.id).exists():
            return Response({'error': 'You are not a member of this team.'}, status=status.HTTP_400_BAD_REQUEST)
        team.members.remove(request.user)
        return Response({'message': 'You left the team.'})


class TeamRemoveMemberView(GenericAPIView):
    """Remove a member from the team (owner only)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        from base.models import Team
        team = get_object_or_404(Team, pk=pk)
        if team.owner_id != request.user.id:
            return Response({'error': 'Only the team owner can remove members.'}, status=status.HTTP_403_FORBIDDEN)
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'error': 'user_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if str(team.owner_id) == str(user_id):
            return Response({'error': 'Cannot remove the owner.'}, status=status.HTTP_400_BAD_REQUEST)
        member = team.members.filter(pk=user_id).first()
        if not member:
            return Response({'error': 'User is not a member of this team.'}, status=status.HTTP_400_BAD_REQUEST)
        team.members.remove(member)
        return Response({'message': 'Member removed.'})


class NewsletterSubscribeView(GenericAPIView):
    """
    Public endpoint for newsletter subscription from marketing site.
    No authentication required.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = None  # Will import dynamically

    def get_client_ip(self, request):
        """Extract client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    @swagger_auto_schema(
        operation_description="Subscribe to newsletter",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['email'],
            properties={
                'email': openapi.Schema(type=openapi.TYPE_STRING, format='email', description='Email address'),
            },
        ),
        responses={
            201: openapi.Response(
                description="Subscribed successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'ok': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: openapi.Response(description="Invalid email or already subscribed"),
        }
    )
    def post(self, request):
        from base.serializers import NewsletterSubscribeSerializer
        from base.models import NewsletterSubscription
        
        serializer = NewsletterSubscribeSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'ok': False,
                'error': serializer.errors.get('email', ['Invalid email'])[0]
            }, status=status.HTTP_400_BAD_REQUEST)
        
        email = serializer.validated_data['email']
        
        # Check if already exists and is active
        existing = NewsletterSubscription.objects.filter(email=email).first()
        if existing and existing.is_active:
            return Response({
                'ok': False,
                'error': 'Already subscribed'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create or reactivate subscription
        validated_data = serializer.validated_data.copy()
        validated_data['ip_address'] = self.get_client_ip(request)
        serializer.create(validated_data)
        
        return Response({
            'ok': True,
            'message': 'Subscribed successfully'
        }, status=status.HTTP_201_CREATED)


class ContactRequestView(GenericAPIView):
    """
    Public endpoint for demo/contact requests from marketing site.
    No authentication required.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = None  # Will import dynamically

    def get_client_ip(self, request):
        """Extract client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    @swagger_auto_schema(
        operation_description="Submit contact/demo request",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['email', 'company_size'],
            properties={
                'email': openapi.Schema(type=openapi.TYPE_STRING, format='email', description='Work email'),
                'company_size': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=['1-50', '51-200', '201-500', '501+'],
                    description='Company size range'
                ),
            },
        ),
        responses={
            201: openapi.Response(
                description="Request received",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'ok': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: openapi.Response(description="Invalid data"),
        }
    )
    def post(self, request):
        from base.serializers import ContactRequestSerializer
        
        serializer = ContactRequestSerializer(data=request.data)
        
        if not serializer.is_valid():
            # Extract first error message
            errors = serializer.errors
            if 'email' in errors:
                error_msg = errors['email'][0]
            elif 'company_size' in errors:
                error_msg = errors['company_size'][0]
            else:
                error_msg = 'Invalid data'
            
            return Response({
                'ok': False,
                'error': error_msg
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create contact request
        validated_data = serializer.validated_data.copy()
        validated_data['ip_address'] = self.get_client_ip(request)
        serializer.create(validated_data)
        
        return Response({
            'ok': True,
            'message': 'Request received'
        }, status=status.HTTP_201_CREATED)
