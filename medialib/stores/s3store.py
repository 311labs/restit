from django.conf import settings
# import boto
# from boto.s3.connection import S3Connection
import boto3
import botocore

from urllib.parse import urlparse
from datetime import datetime
import io
import sys
from medialib import utils
import threading

MY_S3_CLIENT = None
MY_S3_RESOURCE = None


def _getS3(as_resource=True):
    key = settings.AWS_KEY
    secret = settings.AWS_SECRET
    if as_resource:
        return boto3.resource('s3', aws_access_key_id=key, aws_secret_access_key=secret)
    return boto3.client('s3', aws_access_key_id=key, aws_secret_access_key=secret)


def getS3(as_resource=True):
    global MY_S3_CLIENT, MY_S3_RESOURCE
    if as_resource:
        if MY_S3_RESOURCE is None:
            MY_S3_RESOURCE = _getS3(True)
        return MY_S3_RESOURCE
    if MY_S3_CLIENT is None:
        MY_S3_CLIENT = _getS3(False)
    return MY_S3_CLIENT


def getBucket(name):
    s3r = getS3()
    return s3r.Bucket(name)


def getObject(bucket_name, key):
    s3r = getS3()
    return s3r.Object(bucket_name, key)


def getObjectContent(bucket_name, key):
    s3r = getS3(False)
    obj = s3r.get_object(Bucket=bucket_name, Key=key)
    return obj['Body'].read().decode('utf-8')


class ProgressPercentage(object):
    def __init__(self, size):
        self._size = size
        self._seen_so_far = 0
        self._lock = threading.Lock()

    def __call__(self, bytes_amount):
        # To simplify we'll assume this is hooked up
        # to a single filename.
        with self._lock:
            self._seen_so_far += bytes_amount
            percentage = (self._seen_so_far / self._size) * 100
            sys.stdout.write(
                "\r%s  %s / %s  (%.2f%%)" % (
                    self._filename, self._seen_so_far, self._size,
                    percentage))
            sys.stdout.flush()


class S3Item(object):
    def __init__(self, url):
        self.url = url
        u = urlparse(url)
        self.bucket_name = u.netloc
        self.key = u.path.lstrip('/')
        self.s3 = getS3()
        self.host = "https://s3.amazonaws.com"
        self.object = getObject(self.bucket_name, self.key)
        self.exists = self.checkExists()

    def checkExists(self):
        try:
            self.object.load()
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "404":
                # The object does not exist.
                return False
            else:
                # Something else has gone wrong.
                raise
        return True

    def upload(self, fp, background=False):
        self.object.upload_fileobj(openFile(fp))

    @property
    def public_url(self):
        return "{}/{}/{}".format(self.host, self.bucket_name, self.key)

    def generateURL(self, expires=600):
        client = getS3(False)
        return client.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket_name, 'Key': self.key})

    def download(self, fp):
        return self.object.download_fileobj(fp)

    def delete(self):
        self.object.delete()


def upload(url, fp, background=False):
    obj = S3Item(url)
    obj.upload(fp)


def view_url_noexpire(url, is_secure=False):
    obj = S3Item(url)
    return obj.public_url


def view_url(url, expires=600, is_secure=False):
    if expires is None:
        return view_url_noexpire(url, is_secure)
    obj = S3Item(url)
    return obj.generateURL(expires)


def exists(url):
    obj = S3Item(url)
    return obj.exists


def get_file(url, fp):
    obj = S3Item(url)
    return obj.download(fp)


def delete(url):
    if url[-1] == "/":
        prefix = url.path.lstrip("/")
        bucket_name = url.netloc
        s3 = getS3()
        response = s3.list_objects_v2(
            Bucket=bucket_name,
            Prefix =prefix,
            MaxKeys=100)
        for obj in response['Contents']:
            s3.delete_object(Bucket=bucket_name, Key=object['Key'])
    else:
        obj = S3Item(url)
        obj.delete()
        # _getkey(url, key=settings.AWS_ADMIN_KEY, secret=settings.AWS_ADMIN_SECRET).delete()


def openFile(fp):
    # this should fail if already opened.. if not iwll open
    # even if wrapped file-like object exists. To avoid Django-specific
    # logic, pass a copy of internal file-like object if `content` is
    # `File` class instance.
    if hasattr(fp, "read"):
        return io.BytesIO(utils.toBytes(fp.read()))
    try:
        return open(fp.name, "r")
    except IOError:
        background = False
    return fp


def path(url):
    u = urlparse(url)
    return u.path
