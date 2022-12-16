from rest.decorators import periodic
from incident.models import Event, ServerOssecAlert, Incident
from datetime import datetime, timedelta
from rest import log

logger = log.getLogger("incident", filename="incident.log")


@periodic(minute=50, hour=8)
def run_cleanup(force=False, verbose=False, now=None):
    stale = datetime.now() - timedelta(days=90)
    # delete all ossect alerts older then 90 days
    count = ServerOssecAlert.objects.filter(created__lte=stale).delete()
    if count:
        logger.info(f"deleted {count} old ServerOssecAlert")
    count = Event.objects.filter(created__lte=stale).delete()
    if count:
        logger.info(f"deleted {count} old Events")
