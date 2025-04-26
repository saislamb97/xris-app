import logging
import stripe
import datetime
from decimal import Decimal
from django.conf import settings
from django.utils.timezone import make_aware
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import HttpResponse, HttpResponseBadRequest
from django.contrib.auth import get_user_model
from subscriptions.models import Subscription, SubscriptionPackage
from subscriptions.emails import SubscriptionEmail
from django.contrib import messages 
from allauth.account.decorators import login_required, verified_email_required

logger = logging.getLogger(__name__)

# --- Setup ---
User = get_user_model()
stripe.api_key = settings.STRIPE_SECRET_KEY
HOST_URL = settings.HOST_URL
STRIPE_WEBHOOK_SECRET = settings.STRIPE_WEBHOOK_SECRET

# ============================================================
# Subscription Overview
# ============================================================
@login_required
@verified_email_required
def SubscriptionView(request):
    user = request.user
    subscription_history = Subscription.objects.filter(user=user).order_by('-created_at')
    active_subscription = subscription_history.filter(status=Subscription.STATUS_ACTIVE).first()
    available_packages = SubscriptionPackage.objects.all().order_by('price')  # still show all packages

    # ✅ Optional: Show a success message if redirected here after success
    if request.GET.get('success') == 'true':
        messages.success(request, "Subscription completed successfully! 🎉 Welcome aboard.")
    elif request.GET.get('cancel') == 'true':
        messages.error(request, "Subscription process was canceled. Feel free to try again anytime!")

    context = {
        'user': user,
        'active_subscription': active_subscription,
        'subscription_history': subscription_history,
        'available_packages': available_packages,
        'is_free_user': not active_subscription,
        'is_pending_cancellation': active_subscription.pending_cancellation if active_subscription else False,
        'PACKAGE_FREE': SubscriptionPackage.PACKAGE_FREE,
    }
    return render(request, 'subscription.html', context)

# ============================================================
# Checkout: Create Stripe Subscription
# ============================================================
@login_required
@verified_email_required
def CheckoutView(request):
    logger.info("CheckoutView hit: Request received.")

    user = request.user
    logger.info(f"Authenticated user: {user.email} (ID: {user.id})")

    if request.method != "POST":
        logger.warning("Checkout attempt with invalid method.")
        messages.error(request, "Invalid request method.")
        return redirect('subscriptions:subscription')

    selected_price_id = request.POST.get('selected_plan')

    if not selected_price_id:
        logger.warning("Checkout failed: No subscription plan selected.")
        messages.error(request, "Please select a subscription plan.")
        return redirect('subscriptions:subscription')

    try:
        package = SubscriptionPackage.objects.get(stripe_price_id=selected_price_id)
        logger.info(f"Selected package: {package.name} (Stripe Price ID: {selected_price_id})")
    except SubscriptionPackage.DoesNotExist:
        logger.error(f"Checkout failed: No package found for price ID {selected_price_id}.")
        messages.error(request, "Selected subscription plan does not exist.")
        return redirect('subscriptions:subscription')

    # 🚨 Block trying to subscribe to Free Plan
    if package.name == SubscriptionPackage.PACKAGE_FREE:
        logger.warning(f"Checkout prevented: User {user.email} attempted to subscribe to Free plan.")
        messages.error(request, "You cannot subscribe to the Free plan.")
        return redirect('subscriptions:subscription')

    # 🚨 Block subscribing again if already active subscription
    if Subscription.objects.filter(user=user, status=Subscription.STATUS_ACTIVE).exists():
        logger.warning(f"Checkout prevented: User {user.email} already has an active subscription.")
        messages.warning(request, "You already have an active subscription.")
        return redirect('subscriptions:subscription')

    try:
        session = stripe.checkout.Session.create(
            line_items=[{'price': selected_price_id, 'quantity': 1}],
            mode='subscription',
            customer_email=user.email,
            success_url=f"{HOST_URL}/subscriptions/?success=true",
            cancel_url=f"{HOST_URL}/subscriptions/?cancel=true",
            metadata={
                'user_id': str(user.id),
                'package_id': str(package.id),
                'selected_quantity': 1
            }
        )
        logger.info(f"Stripe Checkout Session created successfully. Session ID: {session.id}")
        return redirect(session.url, code=303)

    except stripe.StripeError as e:
        logger.exception(f"Stripe error occurred during checkout: {str(e)}")
        messages.error(request, "There was a problem creating your subscription. Please try again.")
        return redirect('subscriptions:subscription')

# ============================================================
# Stripe Billing Portal
# ============================================================
@login_required
@verified_email_required
def CustomerView(request):
    user = request.user

    if request.method == "POST":
        subscription_id = request.POST.get('subscription_id')

        if not subscription_id:
            messages.error(request, "Missing subscription ID.")
            return redirect('subscriptions:subscription')

        subscription = Subscription.objects.filter(
            user=user, stripe_subscription_id=subscription_id
        ).first()

        if not subscription or not subscription.stripe_customer_id:
            messages.error(request, "Subscription not found. Please subscribe first.")
            return redirect('subscriptions:subscription')

        try:
            session = stripe.billing_portal.Session.create(
                customer=subscription.stripe_customer_id,
                return_url=f"{HOST_URL}{reverse('subscriptions:subscription')}"
            )
            logger.info(f"[Stripe] Billing portal session created for {user.email}")
            return redirect(session.url)

        except stripe.StripeError as e:
            logger.exception(f"[Stripe Portal Error] {e}")
            messages.error(request, "Unable to open billing portal at the moment. Please try again later.")
            return redirect('subscriptions:subscription')

    messages.error(request, "Invalid request method.")
    return redirect('subscriptions:subscription')

# ============================================================
# Stripe Webhook Endpoint
# ============================================================
@csrf_exempt
def WebhookView(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        logger.warning(f"[Webhook] Invalid payload or signature: {str(e)}")
        return HttpResponse(status=400)

    event_type = event.get('type')
    data = event.get('data', {}).get('object', {})

    logger.info(f"[Webhook] Received event: {event_type}")

    def get_expiry_date(subscription):
        current_period_end = subscription.get('current_period_end')
        if not current_period_end:
            logger.warning("[Webhook] Subscription missing current_period_end.")
            return None
        return make_aware(datetime.datetime.fromtimestamp(current_period_end))

    def update_subscription_status(sub, status, expiry_date=None, pending_cancellation=False, email_func=None):
        sub.status = status
        if expiry_date:
            sub.expiry_date = expiry_date
        sub.pending_cancellation = pending_cancellation
        sub.save()
        if email_func:
            email_func(sub)

    try:
        if event_type == 'checkout.session.completed':
            user_id = data.get('metadata', {}).get('user_id')
            package_id = data.get('metadata', {}).get('package_id')
            subscription_id = data.get('subscription')
            customer_id = data.get('customer')

            if not (user_id and package_id and subscription_id and customer_id):
                logger.error("[Webhook] Missing data in checkout.session.completed.")
                return HttpResponse(status=400)

            user = User.objects.get(id=user_id)
            package = SubscriptionPackage.objects.get(id=package_id)
            stripe_sub = stripe.Subscription.retrieve(subscription_id)
            expiry_date = get_expiry_date(stripe_sub)

            Subscription.objects.filter(user=user, status=Subscription.STATUS_ACTIVE).update(status=Subscription.STATUS_EXPIRED)

            new_sub = Subscription.objects.create(
                user=user,
                package=package,
                price=package.price,
                stripe_subscription_id=subscription_id,
                stripe_customer_id=customer_id,
                status=Subscription.STATUS_ACTIVE,
                expiry_date=expiry_date
            )
            SubscriptionEmail(user).subscription_confirmation(new_sub)
            logger.info(f"[Webhook] Subscription created for user {user.email}")

        elif event_type == 'customer.subscription.updated':
            subscription_id = data.get('id')
            if not subscription_id:
                logger.error("[Webhook] Missing subscription_id in subscription.updated.")
                return HttpResponse(status=400)

            status = data.get('status')
            cancel_at_period_end = data.get('cancel_at_period_end', False)
            expiry_date = get_expiry_date(data)

            sub = Subscription.objects.filter(stripe_subscription_id=subscription_id).first()
            if not sub:
                logger.warning(f"[Webhook] Subscription not found for ID {subscription_id}")
                return HttpResponse(status=200)

            if status == 'incomplete_expired':
                update_subscription_status(
                    sub,
                    Subscription.STATUS_EXPIRED,
                    expiry_date,
                    pending_cancellation=False,
                    email_func=SubscriptionEmail(sub.user).subscription_expired
                )
                logger.info(f"[Webhook] Subscription expired for {sub.user.email}")

            elif cancel_at_period_end:
                # Subscription is still ACTIVE but will cancel at period end
                update_subscription_status(
                    sub,
                    Subscription.STATUS_ACTIVE,
                    expiry_date,
                    pending_cancellation=True,
                    email_func=SubscriptionEmail(sub.user).subscription_update
                )
                logger.info(f"[Webhook] Subscription set to cancel at period end for {sub.user.email}")

            else:
                # Normal subscription update
                update_subscription_status(
                    sub,
                    Subscription.STATUS_ACTIVE,
                    expiry_date,
                    pending_cancellation=False,
                    email_func=SubscriptionEmail(sub.user).subscription_update
                )
                logger.info(f"[Webhook] Subscription updated for {sub.user.email}")

        elif event_type == 'invoice.paid':
            subscription_id = data.get('subscription')
            if not subscription_id:
                logger.error("[Webhook] Missing subscription_id in invoice.paid.")
                return HttpResponse(status=200)

            sub = Subscription.objects.filter(stripe_subscription_id=subscription_id).first()
            if not sub:
                logger.warning(f"[Webhook] Subscription not found for ID {subscription_id}")
                return HttpResponse(status=200)

            stripe_sub = stripe.Subscription.retrieve(subscription_id)
            expiry_date = get_expiry_date(stripe_sub)

            update_subscription_status(sub, Subscription.STATUS_ACTIVE, expiry_date, SubscriptionEmail(sub.user).subscription_renewal_paid)
            logger.info(f"[Webhook] Invoice paid and subscription renewed for {sub.user.email}")

        elif event_type == 'invoice.payment_failed':
            subscription_id = data.get('subscription')
            if not subscription_id:
                logger.error("[Webhook] Missing subscription_id in invoice.payment_failed.")
                return HttpResponse(status=400)

            sub = Subscription.objects.filter(stripe_subscription_id=subscription_id).first()
            if sub:
                update_subscription_status(sub, Subscription.STATUS_CANCELLED, email_func=SubscriptionEmail(sub.user).subscription_payment_failed)
                logger.info(f"[Webhook] Invoice payment failed. Subscription cancelled for {sub.user.email}")

        elif event_type == 'customer.subscription.deleted':
            subscription_id = data.get('id')
            if not subscription_id:
                logger.error("[Webhook] Missing subscription_id in subscription.deleted.")
                return HttpResponse(status=400)

            sub = Subscription.objects.filter(stripe_subscription_id=subscription_id).first()
            if sub:
                update_subscription_status(sub, Subscription.STATUS_CANCELLED, email_func=SubscriptionEmail(sub.user).subscription_delete)
                logger.info(f"[Webhook] Subscription deleted for {sub.user.email}")

        else:
            logger.info(f"[Webhook] Unhandled event type: {event_type}")

    except Exception as e:
        logger.exception(f"[Webhook Error] {str(e)}")
        return HttpResponse(status=500)

    return HttpResponse(status=200)