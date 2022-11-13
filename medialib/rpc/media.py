from rest import decorators as rd
from medialib import models as medialib


@rd.url(r'media/item/$')
@rd.url(r'media/item/(?P<pk>\d+)$')
@rd.login_required
def rest_on_media_item(request, pk=None):
    return medialib.MediaItem.on_rest_request(request, pk)


@rd.url(r'media/ref/$')
@rd.url(r'media/ref/(?P<pk>\d+)$')
@rd.login_required
def rest_on_media_ref(request, pk=None):
    return medialib.MediaItemRef.on_rest_request(request, pk)


@rd.url(r'library/$')
@rd.url(r'library/(?P<pk>\d+)$')
@rd.login_required
def rest_on_library(request, pk=None):
    return medialib.MediaLibrary.on_rest_request(request, pk)
