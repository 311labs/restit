from urllib.parse import urlparse

import urllib.request, urllib.parse, urllib.error

def upload(url, fp, background=False):
    raise Exception("Cannot upload to rtmp store")

def view_url(url, expires=600, is_secure=False):
    return url

def exists(url):
    return None

def get_file(url, fp):
    raise Exception("Cannot get from rtmp store")

def delete(url):
    pass # no-op

def netloc(url):
    u = urlparse(url)
    return u.netloc

def path(url):
    u = urlparse(url)
    return u.path
