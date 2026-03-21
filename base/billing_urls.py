from django.urls import path

from base.billing.dodo_webhook_view import DodoWebhookView

from .billing_views import (
    PlanListView,
    CurrentSubscriptionView,
    BillingUsageView,
    InvoiceListView,
    BillingCheckoutSessionView,
    BillingChangePlanView,
    BillingCustomerPortalView,
)

urlpatterns = [
    path('plans/', PlanListView.as_view(), name='billing-plans'),
    path('subscription/', CurrentSubscriptionView.as_view(), name='billing-subscription'),
    path('usage/', BillingUsageView.as_view(), name='billing-usage'),
    path('invoices/', InvoiceListView.as_view(), name='billing-invoices'),
    path('checkout/', BillingCheckoutSessionView.as_view(), name='billing-checkout'),
    path('change-plan/', BillingChangePlanView.as_view(), name='billing-change-plan'),
    path('customer-portal/', BillingCustomerPortalView.as_view(), name='billing-customer-portal'),
    path('webhooks/dodo/', DodoWebhookView.as_view(), name='billing-webhook-dodo'),
]
