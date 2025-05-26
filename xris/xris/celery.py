from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# Set the broker URL directly
BROKER_URL = 'amqp://guest@localhost:5672/'

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xris.settings')

app = Celery('xris')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.conf.broker_url = BROKER_URL  # Assign the broker URL here

# Set broker_connection_retry_on_startup to True
app.conf.broker_connection_retry_on_startup = True

app.autodiscover_tasks()

# Run commands: 
# celery -A xris worker --loglevel=info

# For windows
# celery -A xris worker --loglevel=info --pool=solo --concurrency=1

# celery -A xris beat --scheduler django --loglevel=info
# celery -A xris flower --port=5555 --address=0.0.0.0
