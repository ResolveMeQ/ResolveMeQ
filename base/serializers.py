from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from rest_framework import serializers

from .models import User, Profile
from .tasks import send_email_with_template
from .utils import ImageProcessor, generate_secure_code


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'username', 'password', 'confirm_password']

    def validate(self, data):
        password = data['password']
        confirm_password = data.pop('confirm_password')
        if password != confirm_password:
            raise serializers.ValidationError('Passwords do not match')

        if User.objects.filter(username=data['username']).exists():
            raise serializers.ValidationError('Username already exists')

        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError('Email already registered')
        return data


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data['email']
        password = data['password']
        user = User.objects.filter(email=email).first()

        if not user:
            raise serializers.ValidationError('No user found with this email')

        if not user.is_verified:
            raise serializers.ValidationError('User is not verified')

        if not user.check_password(password):
            raise serializers.ValidationError('Invalid password')

        return data


class VerifyUserSerializer(serializers.Serializer):
    token = serializers.CharField(write_only=True, required=True)
    email = serializers.EmailField(write_only=True, required=True)

    def validate(self, data):
        token = data['token']
        email = data['email']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError('Invalid email or token')

        try:
            user.verify_user(token)
        except ValueError as e:
            error_message = str(e)

            if "expired" in error_message.lower() and not user.is_verified:
                user.secure_code = generate_secure_code()
                user.secure_code_expiry = timezone.now() + timedelta(minutes=15)
                user.save(update_fields=['secure_code', 'secure_code_expiry'])
                data = {
                    "subject": "New verification code",

                }
                context = {
                    "email": user.email,
                    "token": user.secure_code,
                    "username": user.username,
                    "expiration": user.secure_code_expiry,
                    "app_name": "ResolveMeQ",
                    "verification_link": settings.FRONTEND_URL + reverse('verify-user'),
                }
                send_email_with_template.delay(data, 'welcome.html', context, [user.email])
                error_message += " A new verification code has been sent."

            raise serializers.ValidationError(error_message)

        return data


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, required=True)

    def validate_new_password(self, value):
        """
        Validate that the new password meets the requirements.
        :param value: new_password
        :return: new_password
        """
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long")
        return value

    def validate(self, data):
        """
        Validate that the old password is correct and new passwords match.
        :param data:
        :return: validated data
        """
        user = self.context['request'].user
        old_password = data['old_password']
        new_password = data['new_password']
        confirm_password = data['confirm_password']

        if not user.check_password(old_password):
            raise serializers.ValidationError("Old password is incorrect")

        if not constant_time_compare(new_password, confirm_password):
            raise serializers.ValidationError("New passwords do not match")

        if constant_time_compare(old_password, new_password):
            raise serializers.ValidationError("Old password cannot be the same as new password")

        return data


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(write_only=True, required=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, required=True)

    def validate_new_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long")
        return value

    def validate(self, data):
        if not constant_time_compare(str(data['new_password']), str(data['confirm_password'])):
            raise serializers.ValidationError("Passwords do not match")

        email = data['email']
        token = data['token']

        try:
            user = User.objects.get(email=email)

            if not user.secure_code or not constant_time_compare(str(user.secure_code), str(token)):
                raise serializers.ValidationError("Invalid or expired reset token")

            if user.secure_code_expiry and user.secure_code_expiry < timezone.now():
                raise serializers.ValidationError("Reset token has expired")

        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid reset token")

        return data

    def save(self, **kwargs):
        email = self.validated_data['email']
        new_password = self.validated_data['new_password']
        token = self.validated_data['token']

        try:
            user = User.objects.get(email=email)

            if (user.secure_code and
                    constant_time_compare(str(user.secure_code), str(token)) and
                    user.secure_code_expiry and
                    user.secure_code_expiry >= timezone.now()):

                user.set_password(new_password)

                user.secure_code = None
                user.secure_code_expiry = None

                user.save(update_fields=['password', 'secure_code', 'secure_code_expiry'])

            else:
                raise serializers.ValidationError("Invalid or expired reset token")

        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid reset token")


class ResendVerificationCodeSerializer(serializers.Serializer):
    """
    Serializer for resending verification code to the user.
    """
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        """
        Validate that the email exists and is not verified.
        """
        try:
            user = User.objects.get(email=value)
            if user.is_verified:
                raise serializers.ValidationError("User is already verified")
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist")
        return value


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile with image handling.
    """
    profile_image = serializers.ImageField(
        required=False,
        allow_null=True,
        validators=[ImageProcessor.validate_image]
    )

    thumbnail_url = serializers.SerializerMethodField()
    profile_image_url = serializers.SerializerMethodField()
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_full_name = serializers.CharField(source='user.full_name', read_only=True)

    class Meta:
        model = Profile
        fields = [
            'id',
            'user_email',
            'user_full_name',
            'profile_image',
            'profile_image_url',
            'thumbnail_url',
            'bio',
            'location',
            'city'
        ]

    def get_profile_image_url(self, obj):
        """Get full URL for profile image."""
        if obj.profile_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_image.url)
            return obj.profile_image.url
        return obj.get_default_image_url()

    def get_thumbnail_url(self, obj):
        """Get full URL for thumbnail."""
        if obj.thumbnail:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)
            return obj.thumbnail.url
        return obj.get_default_image_url()

    def validate_profile_image(self, value):
        """Additional validation for profile image."""
        if value:
            ImageProcessor.validate_image(value)
        return value



    def update(self, instance, validated_data):
        """Handle image updates properly."""
        profile_image = validated_data.get('profile_image')

        if profile_image:
            optimized_image = ImageProcessor.optimize_image(profile_image)
            validated_data['profile_image'] = optimized_image

        return super().update(instance, validated_data)


class UserManagementSerializer(serializers.ModelSerializer):
    """
    Serializer for user management with profile information.
    """
    profile_location = serializers.CharField(source='profile.location', required=False, allow_blank=True)
    profile_city = serializers.CharField(source='profile.city', required=False, allow_blank=True)
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 
            'email', 
            'username', 
            'first_name', 
            'last_name',
            'full_name',
            'is_active', 
            'is_staff',
            'is_verified',
            'date_joined',
            'last_login',
            'profile_location',
            'profile_city'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']
    
    def get_full_name(self, obj):
        """Get user's full name."""
        return obj.get_full_name() if hasattr(obj, 'get_full_name') else f"{obj.first_name} {obj.last_name}".strip()
    
    def update(self, instance, validated_data):
        """Handle updates including nested profile data."""
        profile_data = {}
        if 'profile' in validated_data:
            profile_data = validated_data.pop('profile')
        
        # Update user fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update or create profile
        if profile_data:
            Profile.objects.update_or_create(
                user=instance,
                defaults=profile_data
            )
        
        return instance


class TeamSerializer(serializers.ModelSerializer):
    """
    Serializer for Team model with member and lead information.
    """
    lead_name = serializers.SerializerMethodField()
    lead_email = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    active_member_count = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()
    member_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        allow_empty=True
    )
    members_details = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        from base.models import Team
        model = Team
        fields = [
            'id',
            'name',
            'description',
            'department',
            'location',
            'owner',
            'is_owner',
            'lead',
            'lead_name',
            'lead_email',
            'members_details',
            'member_ids',
            'member_count',
            'active_member_count',
            'is_active',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at', 'member_count', 'active_member_count']
    
    def get_is_owner(self, obj):
        request = self.context.get('request')
        if not request or not request.user:
            return False
        return obj.owner_id == request.user.id
    
    def get_lead_name(self, obj):
        """Get the team lead's full name."""
        if obj.lead:
            return obj.lead.get_full_name() if hasattr(obj.lead, 'get_full_name') else f"{obj.lead.first_name} {obj.lead.last_name}".strip()
        return None
    
    def get_lead_email(self, obj):
        """Get the team lead's email."""
        return obj.lead.email if obj.lead else None
    
    def get_member_count(self, obj):
        """Get the total number of members in the team."""
        return obj.member_count
    
    def get_active_member_count(self, obj):
        """Get the number of active members in the team."""
        return obj.active_member_count
    
    def get_members_details(self, obj):
        """Get detailed information about team members."""
        return [
            {
                'id': str(member.id),
                'name': member.get_full_name() if hasattr(member, 'get_full_name') else f"{member.first_name} {member.last_name}".strip(),
                'email': member.email,
                'is_active': member.is_active
            }
            for member in obj.members.all()
        ]
    
    def create(self, validated_data):
        """Handle team creation with members."""
        member_ids = validated_data.pop('member_ids', [])
        team = super().create(validated_data)
        
        if member_ids:
            from base.models import User
            members = User.objects.filter(id__in=member_ids)
            team.members.set(members)
        
        return team
    
    def update(self, instance, validated_data):
        """Handle team updates including members."""
        member_ids = validated_data.pop('member_ids', None)
        
        # Update basic fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update members if provided
        if member_ids is not None:
            from base.models import User
            members = User.objects.filter(id__in=member_ids)
            instance.members.set(members)
        
        return instance


class UserPreferencesSerializer(serializers.ModelSerializer):
    """
    Serializer for UserPreferences model.
    """
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    active_team_name = serializers.SerializerMethodField()

    class Meta:
        from base.models import UserPreferences
        model = UserPreferences
        fields = [
            'id',
            'user',
            'user_email',
            'user_name',
            'email_notifications',
            'push_notifications',
            'ticket_updates',
            'system_alerts',
            'daily_digest',
            'timezone',
            'language',
            'theme',
            'active_team',
            'active_team_name',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at', 'active_team_name']

    def get_user_name(self, obj):
        """Get user's full name."""
        return obj.user.get_full_name() if hasattr(obj.user, 'get_full_name') else obj.user.username

    def get_active_team_name(self, obj):
        """Get active team name for display."""
        return obj.active_team.name if obj.active_team_id else None

    def validate_active_team(self, value):
        """User can only set active_team to a team they belong to (member or owner)."""
        if value is None:
            return value
        request = self.context.get('request')
        if not request or not request.user:
            return value
        from base.models import Team
        if not Team.objects.filter(pk=value.pk).filter(
            Q(owner=request.user) | Q(members=request.user)
        ).exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError('You can only set your active team to a team you belong to.')
        return value


class InAppNotificationSerializer(serializers.ModelSerializer):
    """Serializer for in-app notifications (bell dropdown)."""
    time = serializers.SerializerMethodField()

    class Meta:
        from base.models import InAppNotification
        model = InAppNotification
        fields = ['id', 'type', 'title', 'message', 'link', 'is_read', 'created_at', 'time']
        read_only_fields = ['id', 'type', 'title', 'message', 'link', 'created_at']

    def get_time(self, obj):
        from django.utils.timesince import timesince
        return timesince(obj.created_at) + ' ago'


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        from base.models import Plan
        model = Plan
        fields = [
            'id', 'name', 'slug', 'max_teams', 'max_members',
            'price_monthly', 'price_yearly', 'is_active',
        ]


class SubscriptionSerializer(serializers.ModelSerializer):
    plan_detail = PlanSerializer(source='plan', read_only=True)

    class Meta:
        from base.models import Subscription
        model = Subscription
        fields = [
            'id', 'plan', 'plan_detail', 'status',
            'current_period_start', 'current_period_end',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        from base.models import Invoice
        model = Invoice
        fields = [
            'id', 'subscription', 'amount', 'currency', 'status',
            'period_start', 'period_end', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
