

from rest.decorators import periodic, PERIODIC_EVERY_5_MINUTES
from rest import helpers
from rest.log import getLogger
from taskqueue.models import Task, TASK_STATE_COMPLETED, TASK_STATE_RETRY, TASK_STATE_SCHEDULED
from django.db.models import Q
from account.models import Member
from datetime import datetime, timedelta

import os

from django.conf import settings

logger = getLogger()

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
VAR_FOLDER = os.path.join(ROOT, "var")
PID_FILE = os.path.join(VAR_FOLDER, "tq_worker.pid")
ENGINE_CMD = os.path.join(ROOT, "bin", "tq_worker.py")

TQ_THREADS = getattr(settings, "TQ_THREADS", 4)
TQ_SUBSCRIBE = getattr(settings, "TQ_SUBSCRIBE", [])
TQ_REPORT_BACKLOG = getattr(settings, "TQ_REPORT_BACKLOG", 200)


def isLocalEngineRunning():
    pid = helpers.getPidFromFile(PID_FILE)
    if not pid:
        return False
    return helpers.isPidRunning(pid)


def startLocalEngine():
    # needs to be added to sudoers
    helpers.sudoCMD([ENGINE_CMD, "start"], as_user="www")


@periodic()
def run_check_taskrunner(force=False, verbose=False, now=None):
    # check if pid is running
    # check if any backlog exists (ignore state=1)
    if not TQ_SUBSCRIBE:
        logger.warning("periodic taskrunner called but engine is disabled via empty TQ_SUBSCRIBE")
        return
    if not isLocalEngineRunning():
        # attempt to start local engine
        logger.info("pid is: {} @ {}".format(helpers.getPidFromFile(PID_FILE), PID_FILE))
        logger.info("taskrunner is not running? starting task runner...")
        startLocalEngine()


@periodic(minute=PERIODIC_EVERY_5_MINUTES)
def run_retry(force=False, verbose=False, now=None):
    # check for retry jobs
    if now is None:
        now = datetime.now()
    retry_jobs = Task.objects.filter(state=TASK_STATE_RETRY).filter(Q(scheduled_for__isnull=True)|Q(scheduled_for__lte=now))[:200]
    for retry in retry_jobs:
        if not retry.is_stale:
            retry.retry_now()
        else:
            retry.failed("stale")

    # check if we have back log
    qset = Task.objects.filter(state=TASK_STATE_SCHEDULED)
    backlog_count = qset.count()
    # btask = Task.objects.filter(state=TASK_STATE_SCHEDULED).last()
    if backlog_count > TQ_REPORT_BACKLOG:
        # if btask and btask.modified_age > (60*30):
        subject = "Task Worker Backlog"
        msg = "Backlog is: {}\n".format(backlog_count)
        for key, value in helpers.countOccurences(qset, "channel").items():
            msg += "{} = {}\n".format(key, value)
        sms_msg = "{}\n{}".format(subject, msg)
        Member.notifyWithPermission("rest_errors", subject, msg, sms_msg=sms_msg)


@periodic(minute=45, hour=10)
def run_cleanup(force=False, verbose=False, now=None):
    stale = datetime.now() - timedelta(days=90)
    count = Task.objects.filter(created__lte=stale).delete()
    if count:
        logger.info("deleted {} old tasks".format(count))
    stale = datetime.now() - timedelta(days=7)
    count = Task.objects.filter(created__lte=stale, state=TASK_STATE_COMPLETED).delete()
    if count:
        logger.info("deleted {} old completed tasks".format(count))
