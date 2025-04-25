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
from allauth.account.decorators import login_required, verified_email_required

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
    available_packages = SubscriptionPackage.objects.all().order_by('price')

    context = {
        'user': user,
        'active_subscription': active_subscription,
        'subscription_history': subscription_history,
        'available_packages': available_packages,
        'is_free_user': not active_subscription,
    }
    return render(request, 'subscription.html', context)


# ============================================================
# Checkout: Create Stripe Subscription
# ============================================================
@login_required
@verified_email_required
def CheckoutView(request):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid request method.")

    user = request.user
    selected_price_id = request.POST.get('selected_plan')
    quantity_str = request.POST.get('selected_quantity', '1')

    if not selected_price_id:
        return HttpResponseBadRequest("No subscription plan selected.")

    try:
        quantity = int(quantity_str)
    except ValueError:
        quantity = 1

    try:
        package = SubscriptionPackage.objects.get(stripe_price_id=selected_price_id)
    except SubscriptionPackage.DoesNotExist:
        return HttpResponseBadRequest("Invalid subscription plan.")

    if Subscription.objects.filter(user=user, status=Subscription.STATUS_ACTIVE).exists():
        return HttpResponse("You already have an active subscription.", status=403)

    try:
        session = stripe.checkout.Session.create(
            line_items=[{'price': selected_price_id, 'quantity': quantity}],
            mode='subscription',
            customer_email=user.email,
            success_url=f"{HOST_URL}/subscriptions?success=true",
            cancel_url=f"{HOST_URL}/subscriptions?cancel=true",
            metadata={
                'user_id': str(user.id),
                'package_id': str(package.id),
                'selected_quantity': quantity
            }
        )
        return redirect(session.url, code=303)

    except stripe.StripeError as e:
        print(f"[Stripe Checkout Error] {e}")
        return HttpResponse("An error occurred while processing your payment.", status=500)


# ============================================================
# Stripe Billing Portal
# ============================================================
@login_required
@verified_email_required
def CustomerView(request):
    user = request.user
    subscription = Subscription.objects.filter(user=user, stripe_customer_id__isnull=False).order_by('-created_at').first()

    if not subscription:
        return HttpResponse("You don't have a billing account yet. <a href='/subscriptions'>Subscribe here</a>.", status=403)

    try:
        session = stripe.billing_portal.Session.create(
            customer=subscription.stripe_customer_id,
            return_url=f"{HOST_URL}{reverse('subscriptions:subscription')}"
        )
        return redirect(session.url)
    except stripe.StripeError as e:
        print(f"[Stripe Portal Error] {e}")
        return HttpResponse("Unable to open billing portal right now. Please try again later.", status=500)


# ============================================================
# Stripe Webhook Endpoint
# ============================================================
@csrf_exempt
def WebhookView(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    event_type = event['type']
    data = event['data']['object']

    def get_expiry_date(subscription):
        return make_aware(datetime.datetime.fromtimestamp(subscription['current_period_end']))

    def update_subscription_status(sub, status, expiry_date=None, email_func=None):
        sub.status = status
        if expiry_date:
            sub.expiry_date = expiry_date
        sub.save()
        if email_func:
            email_func(sub)

    # 1. Checkout Completed
    if event_type == 'checkout.session.completed':
        try:
            user_id = data['metadata']['user_id']
            package_id = data['metadata']['package_id']
            subscription_id = data.get('subscription')
            customer_id = data.get('customer')

            user = User.objects.get(id=user_id)
            package = SubscriptionPackage.objects.get(id=package_id)
            stripe_sub = stripe.Subscription.retrieve(subscription_id)
            expiry_date = get_expiry_date(stripe_sub)

            # Expire old subscriptions
            Subscription.objects.filter(user=user, status=Subscription.STATUS_ACTIVE).update(status=Subscription.STATUS_EXPIRED)

            # Create new subscription
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

        except Exception as e:
            print(f"[Webhook Error - checkout.session.completed] {e}")

    # 2. Subscription Updated (including status like incomplete_expired or cancellation)
    elif event_type == 'customer.subscription.updated':
        try:
            subscription_id = data['id']
            status = data.get('status')
            cancel_reason = data.get('cancellation_details', {}).get('reason')
            expiry_date = get_expiry_date(data)

            sub = Subscription.objects.filter(stripe_subscription_id=subscription_id).first()
            if not sub:
                return HttpResponse(status=200)

            if status == 'incomplete_expired':
                update_subscription_status(sub, Subscription.STATUS_EXPIRED, expiry_date, SubscriptionEmail(sub.user).subscription_expired)
            elif cancel_reason:
                update_subscription_status(sub, Subscription.STATUS_CANCELLED, expiry_date, SubscriptionEmail(sub.user).subscription_cancellation)
            else:
                update_subscription_status(sub, Subscription.STATUS_ACTIVE, expiry_date, SubscriptionEmail(sub.user).subscription_update)

        except Exception as e:
            print(f"[Webhook Error - subscription.updated] {e}")

    # 3. Invoice Paid (Renewal Success)
    elif event_type == 'invoice.paid':
        try:
            subscription_id = data['subscription']
            sub = Subscription.objects.filter(stripe_subscription_id=subscription_id).first()
            if not sub:
                return HttpResponse(status=200)

            stripe_sub = stripe.Subscription.retrieve(subscription_id)
            expiry_date = get_expiry_date(stripe_sub)

            update_subscription_status(sub, Subscription.STATUS_ACTIVE, expiry_date, SubscriptionEmail(sub.user).subscription_renewal_paid)

        except Exception as e:
            print(f"[Webhook Error - invoice.paid] {e}")

    # 4. Invoice Payment Failed
    elif event_type == 'invoice.payment_failed':
        try:
            subscription_id = data['subscription']
            sub = Subscription.objects.filter(stripe_subscription_id=subscription_id).first()
            if sub:
                update_subscription_status(sub, Subscription.STATUS_CANCELLED, email_func=SubscriptionEmail(sub.user).subscription_payment_failed)

        except Exception as e:
            print(f"[Webhook Error - invoice.payment_failed] {e}")

    # 5. Subscription Deleted (Manually or automatically)
    elif event_type == 'customer.subscription.deleted':
        try:
            subscription_id = data['id']
            sub = Subscription.objects.filter(stripe_subscription_id=subscription_id).first()
            if sub:
                update_subscription_status(sub, Subscription.STATUS_CANCELLED, email_func=SubscriptionEmail(sub.user).subscription_delete)

        except Exception as e:
            print(f"[Webhook Error - subscription.deleted] {e}")

    return HttpResponse(status=200)
