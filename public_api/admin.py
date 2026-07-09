from django.contrib import admin

from .models import PartnerApiKey


@admin.register(PartnerApiKey)
class PartnerApiKeyAdmin(admin.ModelAdmin):
    list_display = ["name", "key_prefix", "team", "is_active", "last_used_at", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "key_prefix", "team__name"]
    readonly_fields = ["key_prefix", "key_hash", "created_at", "last_used_at"]
