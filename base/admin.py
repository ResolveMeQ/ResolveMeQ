from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django import forms

from base.models import Profile, Team, UserPreferences, Plan, Subscription, Invoice, InAppNotification

User = get_user_model()


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    pass


class UserCreationForm(forms.ModelForm):
    """Custom form for creating new users in the admin panel."""
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm Password", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ('email', 'username', 'first_name', 'last_name')

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords do not match")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserChangeForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ('email', 'username', 'first_name', 'last_name', 'is_active', 'is_staff')

    def clean_password(self):
        return self.initial.get("password")

class UserAdmin(BaseUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm

    list_display = ('email', 'username', 'is_active', 'is_staff')
    search_fields = ('email', 'username')
    ordering = ('email',)
    readonly_fields = ('secure_code',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name','username', 'last_name')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_verified', 'secure_code')}),
        ('Active Bar', {'fields': ('status',)})
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'first_name', 'last_name', 'password1', 'password2')}
        ),
    )

    def save_model(self, request, obj, form, change):
        if "password1" in form.cleaned_data and form.cleaned_data["password1"]:
            obj.set_password(form.cleaned_data["password1"])
        obj.save()


admin.site.register(User, UserAdmin)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    """Admin interface for Team model."""
    list_display = ['name', 'department', 'location', 'lead', 'is_active', 'created_at']
    list_filter = ['is_active', 'department', 'created_at']
    search_fields = ['name', 'description', 'department', 'location']
    filter_horizontal = ['members']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'department', 'location')
        }),
        ('Team Structure', {
            'fields': ('lead', 'members')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('System Information', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(UserPreferences)
class UserPreferencesAdmin(admin.ModelAdmin):
    """Admin interface for UserPreferences model."""
    list_display = ['user', 'email_notifications', 'push_notifications', 'timezone', 'language', 'theme']
    list_filter = ['email_notifications', 'push_notifications', 'language', 'theme']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Notification Preferences', {
            'fields': ('email_notifications', 'push_notifications', 'ticket_updates', 'system_alerts', 'daily_digest')
        }),
        ('General Preferences', {
            'fields': ('timezone', 'language', 'theme')
        }),
        ('System Information', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(InAppNotification)
class InAppNotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'type', 'is_read', 'created_at']
    list_filter = ['type', 'is_read', 'created_at']
    search_fields = ['title', 'message', 'user__email']
    readonly_fields = ['id', 'created_at']
    ordering = ['-created_at']


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'max_teams', 'max_members', 'price_monthly', 'price_yearly', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'slug']


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'plan', 'status', 'current_period_start', 'current_period_end']
    list_filter = ['status']
    search_fields = ['user__email']


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['id', 'subscription', 'amount', 'currency', 'status', 'created_at']
    list_filter = ['status']
    readonly_fields = ['id', 'created_at']
