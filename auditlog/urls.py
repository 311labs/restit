from django.conf.urls import *

from .rpc import *
from rest.decorators import include_urlpatterns

urlpatterns = include_urlpatterns(r'^', __package__ + '.rpc')

