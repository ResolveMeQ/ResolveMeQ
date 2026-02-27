from django.urls import path
from .billing_views import (
    PlanListView,
    CurrentSubscriptionView,
    BillingUsageView,
    InvoiceListView,
)

urlpatterns = [
    path('plans/', PlanListView.as_view(), name='billing-plans'),
    path('subscription/', CurrentSubscriptionView.as_view(), name='billing-subscription'),
    path('usage/', BillingUsageView.as_view(), name='billing-usage'),
    path('invoices/', InvoiceListView.as_view(), name='billing-invoices'),
]
