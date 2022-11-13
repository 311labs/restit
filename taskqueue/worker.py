
import requests
import threading
from concurrent import futures

from redis import ConnectionPool, StrictRedis
from ws4redis import settings as ws4redis_settings

redis_connection_pool = ConnectionPool(**ws4redis_settings.WS4REDIS_CONNECTION)

def getRedisClient():
    return StrictRedis(connection_pool=redis_connection_pool)

from .models import *
from .transports import email, http, sftp, sms, s3
from rest import helpers
from rest.log import getLogger
from rest.uberdict import UberDict
from datetime import datetime, timedelta
import time
from django.conf import settings

TQ_WORKERS = getattr(settings, "TQ_WORKERS", 4)
TQ_SUBSCRIBE = getattr(settings, "TQ_SUBSCRIBE", [])

logger = None

# use threads or processes
# because tasks are general heavy IO bound threads are probably more efficient
USE_THREADS = True

import multiprocessing
CPU_COUNT = multiprocessing.cpu_count()

if not USE_THREADS:
    # only use the number of cpus we have if using process
    TQ_WORKERS = min(TQ_WORKERS, CPU_COUNT)

class WorkManager(object):
    def __init__(self, worker_count=TQ_WORKERS, subscribe_to=TQ_SUBSCRIBE, **kwargs):
        self.worker_count = worker_count
        self.subscribe_to = subscribe_to
        self.logger = kwargs.get("logger", None)
        self.service = kwargs.get("service", None)
        self._scheduled_tasks = {}
        self._running_count = 0
        self._pending_count = 0
        self.is_running = False
        self.lock = threading.RLock()
        if not self.logger:
            self.logger = getLogger("root", filename="tq_worker.log")
        self.logger.info("starting manager, workers: {}".format(self.worker_count))
        self.logger.info("handling: {}".format(self.subscribe_to))
        if USE_THREADS:
            self._pool = futures.ThreadPoolExecutor(max_workers=self.worker_count)
        else:
            self._pool = futures.ProcessPoolExecutor(max_workers=self.worker_count)

    def updateCounts(self):
        self.logger.info("running: {} --- pending: {}".format(self._running_count, self._pending_count))

    def addTask(self, task):
        if task.is_stale:
            self.logger.warning("task({}) is now stale".format(task.id))
            task.failed("stale")
            return
        if task.id in self._scheduled_tasks:
            self.logger.error("task({}) is alrleady scheduled".format(task.id))
            return
        task.manager = self
        with self.lock:
            task.worker_running = False
            self._scheduled_tasks[task.id] = task
            self._pending_count += 1
            task.future = self._pool.submit(self.on_run_task, task)
        self.updateCounts()

    def addEvent(self, event):
        # self.logger.info("processing event", event)
        if event.type == "subscribe":
            # confirmation we subscribed
            self.logger.info("succesfully subscribed to: {}".format(event.channel))
            return
        if event.channel == "tq_restart":
            self.restart()
            return
        elif event.data:
            event.data = UberDict.fromJSON(event.data)

        task = Task.FromEvent(event)
        if not task:
            self.logger.warning("event has no task", event)
            return
        if event.channel == "tq_cancel":
            self.logger.info("cancel request received")
            try:
                self.cancelTask(task, event.data.reason)
            except:
                self.logger.exception("during cancelTask")
            return
        self.addTask(task)

    def cancelTask(self, task, reason=None):
        cached_task = self._scheduled_tasks.get(task.id, None)
        if not cached_task:
            # task is not scheduled
            self.logger.warning("canceling non scheduled task({})".format(task.id))
            task.state = -2
            task.reason = reason
            task.save()
            return
        if not hasattr(cached_task, "future"):
            self.removeTask(cached_task)
            self.logger.error("task has no future!")
            return
        task = cached_task
        if task.future.running():
            # right now we don't support canceling a running task but we will try!
            self.logger.warning("attempting to stop running task({})".format(task.id))
            if self.killWorker(task._thread_id):
                time.sleep(2.0)
                if task.future.done():
                    self.logger.info("succesfully killed task({}@{})".format(task.id, task._thread_id))
                    task.state = -2
                    task.reason = reason
                    task.save()
                else:
                    self.logger.warning("failed to kill worker")
            else:
                self.logger.warning("failed to kill worker")
        else:
            if task.future.cancel():
                self.logger.info("succesfully canceled task({})".format(task.id))
                task.state = -2
                task.reason = reason
                task.save()
                self.removeTask(task)
                return
            else:
                self.logger.error("failed to cancel task({})".format(task.id))

    def killWorker(self, thread_id):
        import ctypes
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, ctypes.py_object(SystemExit))
        if res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
            return False
        return True

    def removeTask(self, task):
        try:
            with self.lock:
                del self._scheduled_tasks[task.id]
                self._pending_count -= 1
                self.updateCounts()
        except:
            pass


    def processBacklog(self):
        tasks = Task.objects.filter(state__in=[0,1,2])
        for task in tasks:
            if task.channel in self.subscribe_to:
                if task.cancel_requested:
                    self.logger.info("task has cancel request {}".format(task.id))
                    task.state = -2
                    if not task.reason:
                        task.reason = "task canceled"
                    task.save()
                    continue
                self.logger.debug("resubmitting job {}".format(task.id))
                self.addTask(task)
            else:
                self.logger.warning("ignore job {}:{}".format(task.id, task.channel))

    def _on_webrequest(self, task):
        self.logger.debug("starting webrequest to: {}".format(task.data.url))
        # we need to copy the data and remove the url
        if task.fname.upper() == "GET":
            resp = http.GET(task)
        elif task.fname.upper() == "FABI":
            resp = fabi.POST(task)
        else:
            resp = http.POST(task)
        if resp:
            task.completed()
        elif task.state == 1:
            # slowly backoff retries
            task.retry_later(from_now_secs=(task.attempts-1) * 120)

    def _on_hookrequest(self, task):
        self.logger.debug("starting webrequest to: {}".format(task.data.url))
        # we need to copy the data and remove the url
        if task.model == "tq_email_request":
            resp = email.SEND(task)
        elif task.model == "tq_sms_request":
            resp = sms.SEND(task)
        elif task.model == "tq_sftp_request":
            resp = sftp.SEND(task)
        elif task.model == "tq_s3_request":
            resp = s3.UPLOAD(task)
        if resp:
            task.completed()
        elif task.state == 1:
            task.retry_later(from_now_secs=task.attempts * 60)
        else:
            task.failed()

    def on_task_started(self, task):
        with self.lock:
            task.worker_running = True
            self._running_count += 1
            self._pending_count -= 1
            self.updateCounts()

    def on_task_ended(self, task):
        with self.lock:
            task.worker_running = False
            del self._scheduled_tasks[task.id]
            self._running_count -= 1
            self.updateCounts()

    def on_run_task(self, task):
        self.logger.info("running task({})".format(task.id))

        # check if its canceled
        try:
            self.on_task_started(task)
            task.refresh_from_db()
            task._thread_id = threading.current_thread().ident
            self.logger.debug("running on thread:{}".format(task._thread_id))
            if task.state not in [0,1,2] or task.cancel_requested:
                self.logger.info("task({}) was canceled?".format(task.id))
                self.on_task_ended(task)
                return

            if task.is_stale:
                self.logger.warning("task({}) is now stale".format(task.id))
                task.failed("stale")
                self.on_task_ended(task)
                return
        except Exception as err:
            self.logger.exception(err)
            return

        handler = None
        if task.model == "tq_web_request":
            handler = self._on_webrequest
        elif task.model in ["tq_sftp_request", "tq_email_request", "tq_sms_request", "tq_s3_request"]:
            handler = self._on_hookrequest
        else:
            try:
                handler = task.getHandler()
            except Exception as err:
                self.logger.exception(err)
                task.log_exception(err)
                task.failed(str(err))
                self.on_task_ended(task)
                return

        if handler is None:
            self.logger.error("failed to find handler: task({})".format(task.id))
            task.failed("failed to find handler")
            self.on_task_ended(task)
            return

        self.logger.debug("task.started()")
        task.started()
        try:
            self.logger.debug("task({}) calling handler".format(task.id))
            handler(task)
            if task.state == TASK_STATE_STARTED:
                task.completed()
            self.logger.debug("task({}) handler finished".format(task.id))
        except Exception as err:
            self.logger.exception(err, "task({}) had exception".format(task.id))
            task.log_exception(err)
            if "connection already closed" in str(err).lower():
                # this is a nasty little bug in django when forking django db connections
                # we will schedule the task to retry later
                task.retry_later()
                # let us try and close db connections?
                hack_closeDjangoDB()
                # or should we restart the task queue?
            else:
                task.failed(str(err))
        except SystemExit:
            self.logger.error("task({}) was killed".format(task.id))
        finally:
            self.on_task_ended(task)
        self.logger.info("task({}) finished with state {}".format(task.id, task.state))

    def run_forever(self):
        self.logger.info("starting work manager...")
        self.is_running = True
        client = getRedisClient()
        sub = client.pubsub()
        for key in self.subscribe_to:
            self.logger.info("subscribing to: {}".format(key))
            sub.subscribe(key)
        sub.subscribe("tq_cancel")
        sub.subscribe("tq_restart")
        self.logger.info("listening for incoming events...")
        while self.is_running:
            for event in sub.listen():
                if self.is_running:
                    self.logger.debug("new event", event)
                    try:
                        event = UberDict.fromdict(event)
                        event.channel = helpers.toString(event.channel)
                        self.addEvent(event)
                    except Exception as err:
                        self.logger.exception(err)

    def restart(self):
        if self.service:
            self.is_running = False
            self.stop(timeout=30.0)
            self.service.restart()

    def stop(self, timeout=30.0):
        self.updateCounts()
        self.logger.info("stopping, canceling pending tasks...")
        self.is_running = False
        # we need to cancel all futures not running:
        try:
            RemoteEvents.publish("tq_cancel", {"pk":1})
            with self.lock:
                self.updateCounts()
                for key, task in list(self._scheduled_tasks.items()):
                    if not hasattr(task, "future"):
                        continue
                    if not task.future.running():
                        task.future.cancel()
                self.updateCounts()
        except Exception as err:
            self.logger.exception(err)

        self.logger.info("waiting for {} running tasks, timeout: {}".format(self._running_count, timeout))
        timeout_at = time.time() + timeout
        while self._running_count > 0 and time.time() < timeout_at:
            # we are waiting for all jobs to finish
            time.sleep(1.0)

        self.updateCounts()
        if self._running_count:
            self.logger.error("timedout waiting for long running tasks, stopping anyway")
            # lets set all to failed that are running
            for pk, task in list(self._scheduled_tasks.items()):
                if task.worker_running:
                    if task.current_runtime >= 300:
                        task.failed("killed because task is taking to long to run")
                    else:
                        task.retry_later("worker engine restarting")
        else:
            self.logger.info("all tasks complete and workers stopped!")


def hack_closeDjangoDB():
    from django.db import connections
    for conn in connections.all():
        conn.close_if_unusable_or_obsolete()


