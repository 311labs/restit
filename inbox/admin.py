from django.contrib import admin
from . import models as inbox

admin.site.register(inbox.Mailbox)
admin.site.register(inbox.Message)
admin.site.register(inbox.Attachment)
admin.site.register(inbox.Bounce)
admin.site.register(inbox.Complaint)
