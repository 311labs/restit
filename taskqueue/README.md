# Task Queue

This is a very very simple redis driven async task engine.  It uses a database as a backup to insure the task doesn't get lost and keeps a record of it.



## Overview

The mechanism is extremely simple.  You can push tasks to the task queue and it will first save the task to the dango's default database and then publish it to redis.   The worker engines run and subscribe to different channels to handle different types of task.   They will update the task instance in the database once completed.

This engine was built with more of a send and forget mentality.   The sender does not care about being updated on the status of the task.



## Handlers

A handler is a callback function that will be called by the task engine to actually execute the task.  This will happen in the engines own process and not in calling tasks process.

Currently for ease of implementation we only support class or static method attached to a django Model.

## Usage

```python
from taskqueue.models import Task

# send an async web POST (no handler required)
Task.WebRequest("https://dummy.com/uri/endpoint", {"test1":"hello world", "test2":"halo 2"})

# send a model handler task
# first implement a task handler
class MyModel(models.Model):
  @staticmethod
  def on_tq_run_summary(task):
    # an instance of a task model
    # task.data is a UberDict of the data sent
    # do stuff here
    # now mark the task completed or failed
    if success:
      task.completed()
    else:
      task.failed("could not find transactions")
    return True

# finally schedule some tasks to run
Task.Publish("myapp.MyModel", "on_tq_run_summary", {"id":22, "kind":"HOURLY"})

```



### Rest End Point

**/rpc/taskqueue/task**

This can be used to check the status of tasks.



## Task Engine

The task engine is designed to run as a background service.   It will need to be started manually or if configured it will automatically startup when the periodic runs every 5 minutes.

```bash
./bin/tq_worker.py start
```

### Logs

Logs are written to ./var/tq_worker.log

### Refresh with new code

The engine monitors for when a git pull happens and will automatically reload itself with the current code.

