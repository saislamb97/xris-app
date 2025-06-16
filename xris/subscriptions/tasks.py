from celery import shared_task
from django.utils import timezone
from subscriptions.models import Subscription
from django.core.cache import cache
from datetime import timedelta
from django.utils.timezone import now
import logging

logger = logging.getLogger(__name__)

@shared_task
def update_subscription_statuses():
    now = timezone.now()

    expired = Subscription.objects.filter(
        status=Subscription.STATUS_ACTIVE,
        expiry_date__lt=now
    ).update(status=Subscription.STATUS_EXPIRED)

    cancelled = Subscription.objects.filter(
        status=Subscription.STATUS_ACTIVE,
        pending_cancellation=True,
        expiry_date__lte=now
    ).update(status=Subscription.STATUS_CANCELLED)

    logger.info(f"Subscription update complete: {expired} expired, {cancelled} cancelled")

    return {"expired": expired, "cancelled": cancelled}


def trigger_subscription_update(force=False):
    lock_key = "subscription_status_update_lock"
    recent_run_key = "subscription_check_last_run"
    lock_expire = 60  # seconds
    cooldown_expire = 86400  # 24 hours

    if not force and cache.get(recent_run_key):
        logger.info(f"[{now()}] Skipped subscription status update: already triggered recently.")
        return False

    if cache.get(lock_key):
        logger.info(f"[{now()}] Subscription status update already in progress.")
        return False

    cache.set(lock_key, True, timeout=lock_expire)

    try:
        update_subscription_statuses.delay()
        cache.set(recent_run_key, True, timeout=cooldown_expire)
        logger.info("Triggered update_subscription_statuses task.")
        return True
    except Exception as e:
        logger.exception(f"Failed to dispatch subscription update task: {e}")
        return False
