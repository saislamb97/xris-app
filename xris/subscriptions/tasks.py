from celery import shared_task
from django.utils import timezone
from subscriptions.models import Subscription


@shared_task
def update_subscription_statuses():
    now = timezone.now()

    # Expire subscriptions that are past expiry date
    expired = Subscription.objects.filter(
        status=Subscription.STATUS_ACTIVE,
        expiry_date__lt=now
    ).update(status=Subscription.STATUS_EXPIRED)

    # Cancel subscriptions flagged as pending
    cancelled = Subscription.objects.filter(
        status=Subscription.STATUS_ACTIVE,
        pending_cancellation=True,
        expiry_date__lte=now
    ).update(status=Subscription.STATUS_CANCELLED)

    return {"expired": expired, "cancelled": cancelled}
