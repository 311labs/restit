from objict import objict


def event(category, description, level=10, **kwargs):
    from taskqueue.models import Task
    data = objict(category=category, description=description, level=level)
    data.update(kwargs)
    Task.Publish("incident", "new_event", channel="tq_app_handler", data=data)


def event_now(category, description, level=10, **kwargs):
    from .models.event import Event
    data = objict(category=category, description=description, level=level)
    data.update(kwargs)
    Event.createFromDict(None, data)
