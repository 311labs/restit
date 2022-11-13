import requests
from django.conf import settings
from rest import log

# SEND_URL = "POST https://fcm.googleapis.com/v1/{parent=projects/*}/messages:send"
SEND_URL = "https://fcm.googleapis.com/fcm/send"
CM_PROVIDERS = getattr(settings, "CM_PROVIDERS", None)

FCM_KEY = CM_PROVIDERS["fcm"]["key"]

logger = log.getLogger("fcm", filename="fcm.log")


def sendToDevice(device, data):
    return sendData(device.cm_token, data)


def sendNotification(to_token, title, body):
    return postMessage(dict(to=to_token, notification=dict(title=title, body=body)))


def sendData(to_token, data, priority="high"):
    return postMessage(dict(to=to_token, data=data, content_available=True, priority=priority))


def postMessage(payload):
    logger.info("sending FCM", payload)
    headers = dict(Authorization=F"key={FCM_KEY}")
    headers['Content-type'] = 'application/json'
    resp = requests.post(SEND_URL, json=payload, headers=headers)
    logger.info("response", resp.text)
    return resp

