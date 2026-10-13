"""Celery application (PDF section 8).

Start a worker with:   celery -A config worker -l info
"""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("erp")
# All Celery settings live in settings.py, prefixed with CELERY_.
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
