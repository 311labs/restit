from telephony.models import SMS
from datetime import datetime

def SEND(task):
    SMS.send(task.data.phone, task.data.data)
    return True
