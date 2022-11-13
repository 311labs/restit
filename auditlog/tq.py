"""
This is where you can put handlers for running async background tasks

Task.Publish("payauth", "on_tq_test")
"""
from datetime import datetime, timedelta
from auditlog.models import PersistentLog
from django.conf import settings

AUDITLOG_PRUNE_DAYS = getattr(settings, "AUDITLOG_PRUNE_DAYS", False)


def on_cleanup(task):
    # cleanup log files in the var directory
    # exclude_components = ["payauth.ATMTransaction", "payauth.QCTransaction", "payauth.CCTransaction", "account.Member"]
    if AUDITLOG_PRUNE_DAYS:
        before = datetime.now() - timedelta(days=AUDITLOG_PRUNE_DAYS)
        # remove all rest logs older then 6 months
        task.log("purging old persistent rest logs")
        PersistentLog.objects.filter(when__lte=before, component__in=["rest", "action"]).delete()
        before = datetime.now() - timedelta(days=AUDITLOG_PRUNE_DAYS * 2)
        task.log("purging old persistent logs")
        PersistentLog.objects.filter(when__lte=before).exclude(component="account.Member").delete()

