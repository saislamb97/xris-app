from django.conf import settings
from django.core.mail import send_mail

class SubscriptionEmail:
    def __init__(self, user):
        self.user = user
        self.from_email = settings.EMAIL_FROM
        self.to_email = user.email

    def __str__(self):
        return f'Subject: {self.subject}\nMessage: {self.message}\nTo: {self.to_email}'

    def _send(self, subject, message):
        print(subject)
        send_mail(subject, message, self.from_email, [self.to_email])

    def _format_basic(self, action, subscription):
        return (
            f'Your subscription has been {action}.\n'
            f'Plan: {subscription.plan}\n'
            f'Price: {subscription.price}'
        )

    def subscription_confirmation(self, subscription):
        self._send('Subscription Created', self._format_basic('created', subscription))

    def subscription_update(self, subscription):
        self._send('Subscription Updated', self._format_basic('updated', subscription))

    def subscription_renewal(self, subscription):
        self._send('Subscription Renewed', self._format_basic('renewed', subscription))

    def subscription_cancellation(self, subscription):
        self._send('Subscription Cancellation', self._format_basic('cancelled', subscription))

    def subscription_delete(self, subscription):
        message = (
            f'Your subscription has been cancelled.\n'
            f'Thank you for using our service.\nPlan: {subscription.plan}'
        )
        self._send('Subscription Cancelled Successfully', message)

    def subscription_expired(self, subscription):
        message = (
            f'Your subscription has expired.\n'
            f'Plan: {subscription.plan}\n'
            f'Expired on: {subscription.expiry_date.strftime("%Y-%m-%d %H:%M")}\n\n'
            'Please renew your plan to continue enjoying premium features.'
        )
        self._send('Subscription Expired', message)

    def subscription_payment_failed(self, subscription):
        name = self.user.get_full_name() or self.user.username
        message = (
            f'Hi {name},\n\n'
            f'We were unable to process your subscription payment.\n'
            f'Plan: {subscription.plan}\n'
            f'Please update your payment information to avoid service interruption.'
        )
        self._send('Payment Failed', message)

    def subscription_renewal_paid(self, subscription):
        message = (
            f'Your subscription has been renewed successfully.\n'
            f'Plan: {subscription.plan}\n'
            f'Expires on: {subscription.expiry_date.strftime("%Y-%m-%d")}'
        )
        self._send('Subscription Renewed', message)
