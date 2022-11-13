
def upload(url, fp, background=False):
    raise Exception("Cannot upload to null store")

def exists(url):
    return None

def view_url(url, expires=600, is_secure=False):
    return url

def get_file(url, fp):
    raise Exception("Cannot download from null store")

def delete(url):
    pass # no-op
