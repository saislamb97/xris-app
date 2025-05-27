from django.conf import settings
from django.core.mail import send_mail

class SubscriptionEmail:
    def __init__(self, user):
        self.user = user
        self.from_email = settings.DEFAULT_FROM_EMAIL
        self.to_email = user.email

    def __str__(self):
        return f'Subscription email to {self.to_email}'

    def _send(self, subject, message):
        print(f"Sending email: {subject}")
        send_mail(subject, message, self.from_email, [self.to_email])

    def _format_basic(self, action, subscription):
        return (
            f"Hello {self.user.get_full_name() or self.user.username},\n\n"
            f"Your subscription has been {action}.\n\n"
            f"Plan: {subscription.package.get_name_display()}\n"
            f"Price: ${subscription.price:.2f}\n"
            f"Expiry Date: {subscription.expiry_date.strftime('%Y-%m-%d')}\n\n"
            f"Thank you for using our service!"
        )

    def subscription_confirmation(self, subscription):
        subject = 'Subscription Created Successfully'
        message = self._format_basic('created', subscription)
        self._send(subject, message)

    def subscription_update(self, subscription):
        subject = 'Subscription Updated'
        message = self._format_basic('updated', subscription)
        self._send(subject, message)

    def subscription_renewal(self, subscription):
        subject = 'Subscription Renewed'
        message = self._format_basic('renewed', subscription)
        self._send(subject, message)

    def subscription_renewal_paid(self, subscription):
        subject = 'Subscription Renewal Successful'
        message = (
            f"Hello {self.user.get_full_name() or self.user.username},\n\n"
            f"Your subscription has been renewed successfully.\n\n"
            f"Plan: {subscription.package.get_name_display()}\n"
            f"Price: ${subscription.price:.2f}\n"
            f"New Expiry Date: {subscription.expiry_date.strftime('%Y-%m-%d')}\n\n"
            "Thank you for continuing to use our service!"
        )
        self._send(subject, message)

    def subscription_cancellation(self, subscription):
        subject = 'Subscription Cancelled'
        message = (
            f"Hello {self.user.get_full_name() or self.user.username},\n\n"
            f"Your subscription has been cancelled.\n\n"
            f"Plan: {subscription.package.get_name_display()}\n"
            f"Cancellation Date: {subscription.expiry_date.strftime('%Y-%m-%d')}\n\n"
            "We hope to see you again!"
        )
        self._send(subject, message)

    def subscription_delete(self, subscription):
        subject = 'Subscription Deleted Successfully'
        message = (
            f"Hello {self.user.get_full_name() or self.user.username},\n\n"
            f"Your subscription has been permanently deleted.\n\n"
            f"Plan: {subscription.package.get_name_display()}\n\n"
            "If you have any questions, feel free to reach out."
        )
        self._send(subject, message)

    def subscription_expired(self, subscription):
        subject = 'Subscription Expired'
        message = (
            f"Hello {self.user.get_full_name() or self.user.username},\n\n"
            f"Your subscription has expired.\n\n"
            f"Plan: {subscription.package.get_name_display()}\n"
            f"Expired on: {subscription.expiry_date.strftime('%Y-%m-%d %H:%M')}\n\n"
            "Please renew your plan to continue enjoying premium features.\n"
        )
        self._send(subject, message)

    def subscription_payment_failed(self, subscription):
        subject = 'Subscription Payment Failed'
        message = (
            f"Hello {self.user.get_full_name() or self.user.username},\n\n"
            "We were unable to process your subscription payment.\n\n"
            f"Plan: {subscription.package.get_name_display()}\n\n"
            "Please update your payment information to avoid service interruption.\n"
        )
        self._send(subject, message)
