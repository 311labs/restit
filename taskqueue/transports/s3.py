from medialib.stores.s3store import getS3
from rest.helpers import toBytes
from django.conf import settings
from datetime import datetime
import boto3
from rest import helpers as rest_helpers

def UPLOAD(task):
    when = rest_helpers.parseDate(task.data.when)
    if not when:
        when = datetime.now()
    bucket = task.data.bucket
    filename = task.data.filename
    folder = task.data.folder
    key = task.data.aws
    secret = task.data.secret
    data = toBytes(task.data.data)
    if not key and not secret:
        key = settings.AWS_KEY
        secret = settings.AWS_SECRET
    if filename and '{date' in filename:
        filename = filename.format(date=when)
    if folder:
        filename = "{}/{}".format(folder.strip('/'), filename)
    try:
        s3 = boto3.resource('s3', aws_access_key_id=key, aws_secret_access_key=secret)
        s3_obj = s3.Object(bucket, filename)
        result = s3_obj.put(Body=data)
    except Exception as err:
        task.failed(err)
        return False
    task.log("data written to bucket {} at {}".format(bucket, filename))
    return True
