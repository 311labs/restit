"""
This is where you can put handlers for running async background tasks

Task.Publish("myapp", "on_tq_test")
"""
# from datetime import datetime, timedelta
# from auditlog.models import PersistentLog
# from django.conf import settings
from incident.models import Event


def new_event(task):
    Event.createFromDict(None, task.data)
    task.completed()
