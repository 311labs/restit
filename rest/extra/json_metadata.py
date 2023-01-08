from django.db import models as dm
from rest import fields as rf
from objict import objict


class JSONMetaData(dm.Model):
    class Meta:
        abstract = True
        
    metadata = rf.JSONField()

    def getProperty(self, key, default):
        if self.metadata is None:
            return None
        # fix for when metadata is a string
        # if isinstance(self.metadata, str):
        #     self.metadata = objict.fromJSON(self.metadata)
        return self.metadata.get(key, default)

    def setProperty(self, key, value):
        if self.metadata is None:
            self.metadata = objict()
        # fix for when metadata is a string
        # if isinstance(self.metadata, str):
        #     self.metadata = objict.fromJSON(self.metadata)
        self.metadata.set(key, value)
