
from urllib.parse import urlparse

import urllib.request, urllib.parse, urllib.error

def upload(url, fp, background=False):
    raise Exception("Cannot upload to http store")

def view_url(url, expires=600, is_secure=False):
    return url

def exists(url):
    try:
        ifp = urllib.request.urlopen(url)
    except IOError:
        return False
    ifp.close()
    return True

def get_file(url, fp):
    ifp = urllib.request.urlopen(url)
    buf = ifp.read(10240)
    while buf:
        fp.write(buf)
        buf = ifp.read(10240)
    ifp.close()

def delete(url):
    pass # no-op

def netloc(url):
    u = urlparse(url)
    return u.netloc

def path(url):
    u = urlparse(url)
    return u.path
