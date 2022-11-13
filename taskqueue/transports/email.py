
from datetime import datetime
from rest import mail

def SEND(task, attempts=3):
    now = datetime.now()
    filename = task.data.filename
    if filename and '{date' in filename:
        filename = filename.format(date=now)
    subject = task.data.subject
    if subject and '{date' in subject:
        subject = subject.format(date=now)
    atch1 = mail.makeAttachment(filename, task.data.data)
    try:
        mail.send(task.data.address, subject, attachments=[atch1], body=task.data.body, template=task.data.template)
    except Exception as err:
        task.log_exception(err)
        return False
    return True
