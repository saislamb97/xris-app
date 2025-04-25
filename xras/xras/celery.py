from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# Set the broker URL directly
BROKER_URL = 'amqp://guest@localhost:5672/'

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xras.settings')

app = Celery('xras')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.conf.broker_url = BROKER_URL  # Assign the broker URL here

# Set broker_connection_retry_on_startup to True
app.conf.broker_connection_retry_on_startup = True

app.autodiscover_tasks()

# Run commands: 
# celery -A xras worker --loglevel=info
# celery -A xras beat --loglevel=info
# python3 manage.py migrate django_celery_beat
