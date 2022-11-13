from . import s3store
from . import httpstore
from . import youtubestore
from . import filestore
from . import rtmpstore
from . import nullstore

from django.conf import settings

try:
    import boto.cloudfront
except:
    pass

from urllib.parse import urlparse
import time
from django.core.cache import cache

def _pick_store(url):
    if url[:3] == "s3:":
        return s3store
    elif url[:5] == "http:" or url[:6] == "https:":
        return httpstore
    elif url[:5] == "file:":
        return filestore
    elif url[:8] == "youtube:":
        return youtubestore
    elif url[:5] == "rtmp:":
        return rtmpstore
    elif url[:1] == "/":
        return nullstore
    elif url == "":
        return nullstore
    else:
        raise Exception("Unknown URL format: %s" % url)

def type(url):
    store = _pick_store(url)
    return store.__name__.split(".")[-1]

def upload(url, fp, background=False):
    store = _pick_store(url)
    return store.upload(url, fp, background)

def view_url(url, expires=600, is_secure=False, request=None):
    mirrors = getattr(settings, 'CLOUDFRONT_MIRRORS', {})
    for k in mirrors:
        if url[:len(k)] == k:
            if is_secure and "url_secure" in mirrors[k]:
                murl = mirrors[k]["url_secure"]
            else:
                murl = mirrors[k]["url"]
            mpath = url[len(k):]
            try:
                ext = mpath.rsplit('.', 1)[1]
            except ValueError:
                ext = None
            srcip = getattr(request, 'META', {}).get('REMOTE_ADDR', None)
            try:
                ips = list(int(a) for a in srcip.split('.'))
                if len(ips) == 4 and (
                    (ips[0] == 127) or
                    (ips[0] == 10) or
                    (ips[0] == 192 and ips[1] == 168) or
                    (ips[0] == 172 and ips[1] >= 16 and ips[1] <= 31) or
                    (ips[0] == 204 and ips[1] == 97 and ips[2] == 176)):
                    srcip = None
            except (ValueError, AttributeError,):
                srcip = None

            if not 'key' in mirrors[k] or ext in mirrors[k].get('no_sign', []):
                return murl + mpath
            ckey = "cfsign/" + (srcip or '') + "/" + murl
            sign = cache.get(ckey)
            if sign and expires != None:
                if '?' in mpath:
                    sep = '&'
                else:
                    sep = '?'
                return murl + mpath + sep + sign

            dist = boto.cloudfront.Distribution()
            purl = murl + mpath

            try:
                if expires == None:
                    surl = dist.create_signed_url(purl, mirrors[k]["key"], private_key_string=mirrors[k]["secret"], expire_time=2147483647)
                    return surl
                else:
                    surl = dist.create_signed_url(purl, mirrors[k]["key"], private_key_string=mirrors[k]["secret"],
                        expire_time=int(time.time())+expires+1800, ip_address=srcip, policy_url=murl + "*")
            except (AttributeError, NotImplementedError,):
                #print "Your installation of boto does not support cloudfront"
                break
            cache.set(ckey, surl[len(purl)+1:], 1800)
            return surl

    store = _pick_store(url)
    return store.view_url(url, expires=expires, is_secure=is_secure)

def rtmp_url(url, expires=600, is_secure=False, request=None):
    mirrors = getattr(settings, 'CLOUDFRONT_MIRRORS', {})
    for k in mirrors:
        if url[:len(k)] == k:
            if "url_rtmp" in mirrors[k]:
                murl = mirrors[k]["url_rtmp"]
            else:
                break

            mpath = url[len(k):]
            try:
                (mpath, ext) = mpath.rsplit('.', 1)
            except ValueError:
                break
            if ext in mirrors[k].get("rtmp_exts", ()):
                mpath = ext + ":" + mpath
            else:
                break

            srcip = getattr(request, 'META', {}).get('REMOTE_ADDR', None)
            try:
                ips = list(int(a) for a in srcip.split('.'))
                if len(ips) == 4 and (
                    (ips[0] == 127) or
                    (ips[0] == 10) or
                    (ips[0] == 192 and ips[1] == 168) or
                    (ips[0] == 172 and ips[1] >= 16 and ips[1] <= 31) or
                    (ips[0] == 204 and ips[1] == 97 and ips[2] == 176)):
                    srcip = None
            except (ValueError, AttributeError,):
                srcip = None

            ckey = "cfsign/" + (srcip or '') + "/"
            sign = cache.get(ckey)
            if sign:
                if '?' in mpath:
                    sep = '&'
                else:
                    sep = '?'
                return murl + mpath + sep + sign

            dist = boto.cloudfront.Distribution()
            purl = murl + mpath
            try:
                surl = dist.create_signed_url(purl, mirrors[k]["key"], private_key_string=mirrors[k]["secret"],
                    expire_time=int(time.time())+expires+1800, ip_address=srcip, policy_url="*")
            except (AttributeError, NotImplementedError,):
                #print "Your installation of boto does not support cloudfront"
                break
            cache.set(ckey, surl[len(purl)+1:], 1800)
            return surl
    return None

def exists(url):
    store = _pick_store(url)
    return store.exists(url)

def get_file(url, fp):
    store = _pick_store(url)
    return store.get_file(url, fp)

def delete(url):
    store = _pick_store(url)
    return store.delete(url)

def netloc(url):
    store = _pick_store(url)
    if hasattr(store, "netloc"):
        return store.netloc(url)
    return None

def path(url):
    store = _pick_store(url)
    if hasattr(store, "path"):
        return store.path(url)
    return None
