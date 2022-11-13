
from urllib.parse import urlparse

def upload(url, fp, background=False):
    raise Exception("Cannot upload to youtube using store")

def view_url(url, expires=600, is_secure=False):
    u = urlparse(url)
    return 'http://www.youtube.com/watch?v=' + u.path

def exists(url):
    return None

def get_file(url, fp):
    raise Exception("Cannot download from youtube")

def delete(url):
    pass # no-op
