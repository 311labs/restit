
import http.client
from . import httplib2
import mimetypes

from medialib.youtube.apiclient.errors import HttpError
from medialib.youtube.apiclient.http import MediaFileUpload

import random
import time

# Maximum number of times to retry before giving up.
MAX_RETRIES = 10

# Always retry when these exceptions are raised.
RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError, http.client.NotConnected,
  http.client.IncompleteRead, http.client.ImproperConnectionState,
  http.client.CannotSendRequest, http.client.CannotSendHeader,
  http.client.ResponseNotReady, http.client.BadStatusLine)

# Always retry when an apiclient.errors.HttpError with one of these status
# codes is raised.
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]

def resumable_upload(service, videofile, title, description, category="22", keywords="", privacy="public"):
    """
    Resumable upload for video files.

    returns

    """
    tags = None
    if keywords:
        tags = keywords.split(",")

    body=dict(
        snippet=dict(
            title=title,
            description=description,
            tags=tags,
            categoryId=category
        ),
        status=dict(
            privacyStatus=privacy
        )
    )

    (mimetype, encoding) = mimetypes.guess_type(videofile)
    if mimetype is None and (".uploadedMovie" in videofile or ".m4v" in videofile):
        mimetype = "video/quicktime"

    if mimetype is None:
        raise Exception("unable to determine mimetype of file")
    # Call the API's videos.insert method to create and upload the video.
    insert_request = service.videos().insert(
        part=",".join(list(body.keys())),
        body=body,
        media_body=MediaFileUpload(videofile, mimetype=mimetype, chunksize=-1, resumable=True)
    )

    response = None
    error = None
    retry = 0
    while response is None:
        try:
            status, response = insert_request.next_chunk()
            if 'id' in response:
                service.logger.debug("Video id '%s' was successfully uploaded." % response['id'])
                return response
            else:
                raise Exception("The upload failed with an unexpected response: %s" % response)
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                error = "A retriable HTTP error %d occurred:\n%s" % (e.resp.status, e.content)
            else:
                raise
        except RETRIABLE_EXCEPTIONS as e:
            error = "A retriable error occurred: %s" % e

        if error is not None:
            service.logger.error(error)
            retry += 1
            if retry > MAX_RETRIES:
                raise Exception("No longer attempting to retry.")

            max_sleep = 2 ** retry
            sleep_seconds = random.random() * max_sleep
            time.sleep(sleep_seconds)
