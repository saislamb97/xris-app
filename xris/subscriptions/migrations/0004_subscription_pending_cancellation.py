# Generated by Django 5.2 on 2025-04-26 13:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0003_alter_subscription_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='pending_cancellation',
            field=models.BooleanField(default=False),
        ),
    ]
