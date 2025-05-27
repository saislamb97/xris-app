from django.contrib import admin
from django.utils.html import format_html
from .models import SubscriptionPackage, Subscription


@admin.register(SubscriptionPackage)
class SubscriptionPackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'duration_days', 'stripe_price_id')
    list_editable = ('price', 'duration_days')
    search_fields = ('name',)
    ordering = ('price',)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'user_email', 'package', 'status_colored', 'is_current_bool', 'pending_cancellation_bool',
        'created_at', 'expiry_date', 'days_remaining'
    )
    list_filter = ('status', 'package__name', 'created_at', 'expiry_date', 'pending_cancellation')
    search_fields = ('user__email', 'stripe_subscription_id', 'stripe_customer_id')
    ordering = ('-created_at',)
    readonly_fields = (
        'created_at', 'renewed_at', 'user_email', 'status_colored',
        'days_remaining', 'stripe_subscription_id', 'stripe_customer_id', 'pending_cancellation_bool'
    )

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = "User Email"
    user_email.admin_order_field = "user__email"

    def status_colored(self, obj):
        color = {
            'ACTIVE': 'green',
            'EXPIRED': 'orange',
            'CANCELLED': 'red',
        }.get(obj.status, 'gray')
        return format_html('<span style="color:{}; font-weight:600;">{}</span>', color, obj.get_status_display())
    status_colored.short_description = "Status"

    def is_current_bool(self, obj):
        return obj.is_current
    is_current_bool.boolean = True
    is_current_bool.short_description = "Currently Active"

    def pending_cancellation_bool(self, obj):
        return obj.pending_cancellation
    pending_cancellation_bool.boolean = True
    pending_cancellation_bool.short_description = "Pending Cancellation"

    def days_remaining(self, obj):
        return obj.days_remaining
    days_remaining.short_description = "Days Left"