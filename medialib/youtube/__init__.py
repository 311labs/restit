import http.client
from . import httplib2
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json


from medialib.youtube.apiclient import discovery
from medialib.youtube.oauth2client.client import AccessTokenCredentials

import logging

from medialib.render import render_utils

# in module
from . import upload


httplib2.RETRIES = 1

VALID_PRIVACY_STATUSES = ("public", "private", "unlisted")


def getService(access_token):
    """
    Retrieves a usable YouTubeService via just an access_token
    """
    if hasattr(access_token, "logger"):
        return access_token

    credentials = AccessTokenCredentials(access_token, 'medialib-311/1.0')
    http = httplib2.Http()
    http = credentials.authorize(http)
    # Construct the service object for the interacting with the YouTube Data API.
    service = discovery.build('youtube', 'v3', http=http)
    service.logger = logging.getLogger("youtube")
    return service

def testToken(access_token):
    data = getUserDetails(access_token)
    return data and "email" in data

def refreshToken(refresh_token, client_id, client_secret):
    data = urlencode({
        'refresh_token': refresh_token,
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'refresh_token'
        })

    request = Request('https://accounts.google.com/o/oauth2/token', data)
    try:
        data = json.loads(urlopen(request).read())
        return data
    except (ValueError, IOError):
        pass
    return None

def hasChannel(access_token):
    try:
        channels = listChannels(access_token)
    except:
        return False
    for ch in channels:
        if "snippet" in ch and "title" in ch["snippet"] and len(ch["snippet"]["title"]):
            return True
    return False

def getUserDetails(access_token):
    data = urlencode({'oauth_token': access_token, 'alt': 'json'})
    request = Request('https://www.googleapis.com/userinfo/v2/me?' + data, headers={'Authorization': data})
    try:
        data = json.loads(urlopen(request).read())
        return data
    except (ValueError, IOError):
        pass
    return None

def getVideos(access_token, video_ids=""):
    service = getService(access_token)
    # Retrieve the contentDetails part of the channel resource for the
    # authenticated user's channel.
    videos_response = service.videos().list(
        id=video_ids,
        part="id, status, statistics"
    ).execute()

    if not videos_response["items"]:
        service.logger.warning("no video results returned")
        return None

    return videos_response

def listChannels(access_token):
    service = getService(access_token)
    channels_response = service.channels().list(
      mine=True,
      part="id, snippet"
    ).execute()
    return channels_response["items"]

def listVideos(access_token, video_ids=""):
    service = getService(access_token)
    # Retrieve the contentDetails part of the channel resource for the
    # authenticated user's channel.
    channels_response = service.channels().list(
        mine=True,
        part="contentDetails"
    ).execute()

def uploadVideoFile(access_token, videofile, title, description, category="22", keywords="", privacy="public"):
    """
    Upload a video file with just an access_token
    """
    service = getService(access_token)
    return upload.resumable_upload(service, videofile, title, description, category, keywords, privacy)


def uploadMediaItem(access_token, media_item, renditiondef, params=None):
    """
    Upload a media item
    """
    from medialib.models import MediaItemRendition
    # get the original video file to transfer
    # TODO get straight from S3 bucket???
    original = render_utils.get_rendition(media_item, 'original')
    title = media_item.name
    description = media_item.description
    if params and "description" in params:
        description = params["description"]

    # upload the actual file
    response = uploadVideoFile(access_token, original.filename, title, description)

    # now update the rendition
    rendition = MediaItemRendition(mediaitem=media_item, name=renditiondef.name, use=renditiondef.use, rendition_definition=renditiondef, bytes=0, url='{0}'.format(response["id"]))
    rendition.save()

    return rendition
