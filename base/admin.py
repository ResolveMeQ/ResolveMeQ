import csv

from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django import forms
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone

from base.billing.staff_grant import apply_staff_subscription_grant

from base.models import (
    Profile, Team, UserPreferences, Plan, Subscription, Invoice,
    PlanGatewayProduct, BillingWebhookDelivery,
    InAppNotification, NewsletterSubscription, ContactRequest,
    SupportContactSubmission, AgentUsageMonthly, SubscriptionGrantLog,
)

User = get_user_model()


@admin.action(description='Export selected rows to CSV')
def export_agent_usage_csv(modeladmin, request, queryset):
    """Export selected AgentUsageMonthly rows for finance / support."""
    response = HttpResponse(content_type='text/csv')
    fname = f'agent_usage_{timezone.now().strftime("%Y%m%d_%H%M")}.csv'
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    writer = csv.writer(response)
    writer.writerow(
        ['user_email', 'user_id', 'period_start', 'period_end', 'operations_used', 'updated_at']
    )
    for row in queryset.select_related('user').order_by('-period_start', 'user__email'):
        writer.writerow(
            [
                row.user.email,
                str(row.user_id),
                row.period_start.isoformat(),
                row.period_end.isoformat(),
                row.operations_used,
                row.updated_at.isoformat() if row.updated_at else '',
            ]
        )
    return response


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

    list_display = ('email', 'username', 'is_active', 'is_staff', 'is_platform_agent')
    search_fields = ('email', 'username')
    ordering = ('email',)
    readonly_fields = ('secure_code',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name','username', 'last_name')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_verified', 'is_platform_agent', 'secure_code')}),
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


class PlanGatewayProductInline(admin.TabularInline):
    model = PlanGatewayProduct
    extra = 0
    readonly_fields = ['external_product_id', 'created_at', 'updated_at']


@admin.register(PlanGatewayProduct)
class PlanGatewayProductAdmin(admin.ModelAdmin):
    list_display = ['plan', 'gateway', 'interval', 'external_product_id', 'updated_at']
    list_filter = ['gateway', 'interval']
    search_fields = ['plan__slug', 'plan__name', 'external_product_id']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(BillingWebhookDelivery)
class BillingWebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ['delivery_id', 'provider', 'event_type', 'created_at']
    list_filter = ['provider', 'event_type']
    search_fields = ['delivery_id']
    readonly_fields = ['delivery_id', 'provider', 'event_type', 'created_at']


@admin.register(AgentUsageMonthly)
class AgentUsageMonthlyAdmin(admin.ModelAdmin):
    list_display = ['user', 'period_start', 'period_end', 'operations_used', 'updated_at']
    search_fields = ['user__email', 'user__username']
    date_hierarchy = 'period_start'
    ordering = ['-period_start', '-operations_used']
    list_per_page = 50
    readonly_fields = ['id', 'user', 'period_start', 'period_end', 'operations_used', 'created_at', 'updated_at']
    actions = [export_agent_usage_csv]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'slug', 'max_teams', 'max_members', 'max_agent_operations_per_month',
        'price_monthly', 'price_yearly', 'is_active',
    ]
    list_filter = ['is_active']
    search_fields = ['name', 'slug']
    inlines = [PlanGatewayProductInline]


class StaffGrantSubscriptionAdminForm(forms.Form):
    """Form for the admin-only complimentary subscription grant tool."""

    recipient_email = forms.EmailField(label='Recipient email', required=True)
    plan = forms.ModelChoiceField(
        queryset=Plan.objects.filter(is_active=True).order_by('name'),
        empty_label=None,
    )
    months_valid = forms.IntegerField(min_value=1, max_value=60, initial=12)
    clear_gateway = forms.BooleanField(
        required=False,
        initial=True,
        help_text='Clear Dodo gateway IDs so this row is not confused with an active checkout subscription.',
    )
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
    )

    def clean(self):
        cleaned = super().clean()
        if 'recipient_email' not in cleaned:
            return cleaned
        email = (cleaned.get('recipient_email') or '').strip()
        if not email:
            return cleaned
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if not user:
            self.add_error('recipient_email', 'No active user with this email address.')
            return cleaned
        self.grant_recipient = user
        return cleaned


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    change_list_template = 'admin/base/subscription/change_list.html'
    list_display = [
        'user', 'plan', 'status', 'gateway', 'gateway_subscription_id',
        'current_period_start', 'current_period_end',
        'subscription_expired_notified_at',
        'subscription_welcome_notified_at',
        'subscription_renewed_notified_period_end',
        'subscription_expiring_notified_for_end',
    ]
    list_filter = ['status', 'gateway']
    search_fields = ['user__email', 'gateway_subscription_id', 'gateway_customer_id']
    readonly_fields = ['id', 'created_at', 'updated_at']
    fieldsets = (
        (None, {'fields': ('user', 'plan', 'status')}),
        (
            'Billing period (local)',
            {
                'fields': ('current_period_start', 'current_period_end', 'trial_ends_at'),
                'description': (
                    'Entitlements use these dates. For paid plans via Dodo, webhooks usually set '
                    'periods; manual grants often set them here without a gateway id.'
                ),
            },
        ),
        (
            'Payment gateway (Dodo)',
            {
                'fields': ('gateway', 'gateway_customer_id', 'gateway_subscription_id'),
                'description': 'Leave blank for complimentary / manual access not tied to Dodo.',
            },
        ),
        (
            'Notifications',
            {
                'fields': (
                    'subscription_welcome_notified_at',
                    'subscription_trial_started_notified_at',
                    'subscription_renewed_notified_period_end',
                    'subscription_expiring_notified_for_end',
                    'subscription_past_due_notified_for_period_end',
                    'subscription_expired_notified_at',
                ),
                'description': 'Timestamps for billing lifecycle emails and in-app notices.',
            },
        ),
        ('Meta', {'fields': ('id', 'created_at', 'updated_at')}),
    )

    def get_urls(self):
        urls = super().get_urls()
        info = self.model._meta.app_label, self.model._meta.model_name
        custom = [
            path(
                'grant-subscription/',
                self.admin_site.admin_view(self.grant_subscription_view),
                name='%s_%s_grant_subscription' % info,
            ),
        ]
        return custom + urls

    def grant_subscription_view(self, request):
        if not self.has_change_permission(request):
            raise PermissionDenied

        opts = self.model._meta
        if request.method == 'POST':
            form = StaffGrantSubscriptionAdminForm(request.POST)
            if form.is_valid():
                sub = apply_staff_subscription_grant(
                    recipient=form.grant_recipient,
                    plan=form.cleaned_data['plan'],
                    months_valid=form.cleaned_data['months_valid'],
                    clear_gateway=form.cleaned_data['clear_gateway'],
                    note=form.cleaned_data.get('note') or '',
                    granted_by=request.user,
                )
                messages.success(
                    request,
                    f'Subscription updated for {form.grant_recipient.email} (plan "{sub.plan.name}").',
                )
                return redirect('admin:%s_%s_changelist' % (opts.app_label, opts.model_name))
        else:
            form = StaffGrantSubscriptionAdminForm()

        context = {
            **self.admin_site.each_context(request),
            'title': 'Grant subscription',
            'form': form,
            'opts': opts,
            'app_label': opts.app_label,
        }
        return TemplateResponse(
            request,
            'admin/base/subscription/grant_subscription.html',
            context,
        )


@admin.register(SubscriptionGrantLog)
class SubscriptionGrantLogAdmin(admin.ModelAdmin):
    list_display = [
        'created_at', 'recipient', 'plan', 'status_after', 'months_applied',
        'cleared_gateway', 'granted_by',
    ]
    list_filter = ['cleared_gateway', 'status_after']
    search_fields = ['recipient__email', 'note', 'granted_by__email']
    readonly_fields = [
        'id', 'recipient', 'granted_by', 'subscription', 'plan', 'status_after',
        'period_start', 'period_end', 'trial_ends_at', 'cleared_gateway',
        'months_applied', 'note', 'created_at',
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['id', 'subscription', 'amount', 'currency', 'status', 'created_at']
    list_filter = ['status']
    readonly_fields = ['id', 'created_at']


@admin.register(NewsletterSubscription)
class NewsletterSubscriptionAdmin(admin.ModelAdmin):
    """Admin interface for Newsletter Subscriptions from marketing site."""
    list_display = ['email', 'is_active', 'subscribed_at', 'ip_address']
    list_filter = ['is_active', 'subscribed_at']
    search_fields = ['email']
    readonly_fields = ['id', 'subscribed_at', 'ip_address']
    ordering = ['-subscribed_at']
    
    fieldsets = (
        ('Subscription Info', {
            'fields': ('email', 'is_active')
        }),
        ('System Information', {
            'fields': ('id', 'subscribed_at', 'ip_address'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ContactRequest)
class ContactRequestAdmin(admin.ModelAdmin):
    """Admin interface for Contact/Demo Requests from marketing site."""
    list_display = ['email', 'company_size', 'is_contacted', 'requested_at']
    list_filter = ['company_size', 'is_contacted', 'requested_at']
    search_fields = ['email', 'notes']
    readonly_fields = ['id', 'requested_at', 'ip_address']
    ordering = ['-requested_at']
    
    fieldsets = (
        ('Request Info', {
            'fields': ('email', 'company_size', 'is_contacted')
        }),
        ('Follow-up', {
            'fields': ('notes',)
        }),
        ('System Information', {
            'fields': ('id', 'requested_at', 'ip_address'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SupportContactSubmission)
class SupportContactSubmissionAdmin(admin.ModelAdmin):
    list_display = ['email', 'subject', 'page_context', 'created_at']
    list_filter = ['page_context', 'created_at']
    search_fields = ['email', 'message', 'subject']
    readonly_fields = ['id', 'created_at', 'ip_address']
    ordering = ['-created_at']
    raw_id_fields = ['user']
