"""
This is where you can put handlers for running async background tasks

Task.Publish("app name", "function name")

Task.Publish("taskqueue", "on_tq_test")
"""
import time
from rest.log import getLogger
from datetime import datetime, timedelta
import random
from rest import helpers as rest_helpers
from taskqueue.models import Task


def on_tq_test(task):
    # a background task has been pushed to this call
    logger = getLogger("debug", "debug.log")
    logger.info("on_tq_test: task {}".format(task.id))
    logger.info("published at: {}".format(task.data.published_at))
    sleep_time = 20.0
    if task.data.sleep_time:
        sleep_time = task.data.sleep_time
    end_at = time.time() + sleep_time
    x = 1
    while end_at > time.time():
        if x > (9*1000000):
            x = 1
        else:
            x += x*2
            if random.randint(1,100) > 80:
                time.sleep(0.2)
    logger.info("task completed")
