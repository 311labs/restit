
from django.conf import settings

import os
import errno
import urllib.request, urllib.parse, urllib.error
import shutil
from urllib.parse import urlparse


def toString(value):
    if isinstance(value, bytes):
        value = value.decode()
    elif isinstance(value, bytearray):
        value = value.decode("utf-8")
    elif isinstance(value, (int, float)):
        value = str(value)
    return value


def upload(url, fp, background=False):
    u = urlparse(url)
    fn = os.path.join(settings.MEDIA_ROOT, u.path.lstrip("/"))
    dir = os.path.dirname(fn)
    try:
        os.makedirs(dir)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            pass
        else:
            raise
    ofp = open(fn, "wb")
    buf = fp.read(10240)
    while buf:
        ofp.write(buf)
        buf = fp.read(10240)
    ofp.close()

def view_url(url, expires=600, is_secure=False):
    u = urlparse(url)
    return settings.MEDIA_URL + u.path.lstrip("/")

def exists(url):
    u = urlparse(url)
    fn = os.path.join(settings.MEDIA_ROOT, u.path.lstrip("/"))
    return os.access(fn, os.R_OK)

def get_file(url, fp):
    u = urlparse(url)
    fn = os.path.join(settings.MEDIA_ROOT, u.path.lstrip("/"))
    ifp = open(fn, "rb")
    buf = ifp.read(10240)
    while buf:
        fp.write(buf)
        buf = ifp.read(10240)
    ifp.close()

def delete(url):
    u = urlparse(url)
    fn = os.path.join(settings.MEDIA_ROOT, u.path.lstrip("/"))
    try:
        if fn[-1] == "/":
            shutil.rmtree(fn[:-1])
        else:
            os.unlink(fn)
    except OSError:
        pass
