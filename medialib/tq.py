"""
This is where you can put handlers for running async background tasks

Task.Publish("mymo", "on_background_job")
"""
import time
from rest.log import getLogger
from medialib.models import MediaItem

logger = getLogger("medialib", filename="medialib.log")

# this is a background job handler
def on_render(task):
    logger.info("media task called", task.data)
    try:
        item = MediaItem.objects.get(id=task.data.id)
        item.createRenditions()
        task.completed()
    except Exception as err:
        task.failed(str(err))

