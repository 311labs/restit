from rest import decorators as rd
from rest import views as rv
from . import models as restlytics

"""
Capture simple analytics counters.

uuid: a uuid for your analytics object
    cannot have any special character like ".:!&*
    an example could be "mm_website_page_home"
event: the event that you are capturing
    "view"

that then happens is a auuid is created with "mm_website_page_home.view" and the count is increased

every hour the records are stored into a summary and reset


1. new uuids and event pairs must be registered before being used


Simple examples

count web views and count locations
{"uuid":"mm_website_page_home", "event": "view", "geolocate":true}


{"uuid":"mm_website_page_home", "event": "view"}

"""


@rd.urlPOST(r'^event$')
def rest_on_event(request, pk=None):
    return rv.restStatus(request, True)


@rd.urlPOST(r'^register$')
def rest_on_register(request, pk=None):
    return rv.restStatus(request, True)

