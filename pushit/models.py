
from django.db import models
from django.conf import settings


from account.models import User, Member, Group, MemberFeed
from medialib.models import MediaItem, MediaLibrary
from location.models import GeoIP, Address

from rest import helpers as rest_helpers
from rest.middleware import get_request
from rest import RemoteEvents
from rest.models import RestModel, MetaDataModel, MetaDataBase, UberDict

class Product(models.Model, RestModel, MetaDataModel):
    class RestMeta:
        GRAPHS = {
            "base": {
                "graphs": {
                    "current":"default",
                    "beta":"default",
                },
                "exclude":["library"]
            },
            "default": {
                "graphs": {
                    "current":"default",
                    "beta":"default",
                },
                "recurse_into":[("getReleases", "versions")],
                "exclude":["library"]
            }
        }
    oid = models.CharField(max_length=250, db_index=True, blank=True, default="")
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True)

    owner = models.ForeignKey(Member, related_name="+", on_delete=models.CASCADE)
    group = models.ForeignKey(Group, related_name="+", blank=True, null=True, default=None, on_delete=models.CASCADE)

    archived = models.BooleanField(default=False, blank=True)

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True, default=None)
    kind = models.CharField(max_length=64, blank=True, null=True, default=None)
    is_public = models.BooleanField(default=False, blank=True)

    current = models.ForeignKey("Release", related_name="+", blank=True, null=True, default=None, on_delete=models.CASCADE)
    beta = models.ForeignKey("Release", related_name="+", blank=True, null=True, default=None, on_delete=models.CASCADE)

    library = models.ForeignKey(MediaLibrary, blank=True, null=True, default=None, on_delete=models.CASCADE)

    def getReleases(self):
        return self.releases.all().order_by("-created")[:10]

    def getLibrary(self, commit=True):
        if not self.library:  # object is being created, thus no primary key field yet
            library = MediaLibrary(owner=self.owner, name="Releases")
            library.save()
            self.library = library
            if commit:
                self.save()
        return self.library

    def save(self, *args, **kwargs):
        self.getLibrary(False)
        super(Product, self).save(*args, **kwargs)

    def __unicode__(self):
        return "{0} - {1}".format(self.name, self.kind)


class ProductMetaData(MetaDataBase):
    parent = models.ForeignKey(Product, related_name="properties", on_delete=models.CASCADE)

class Release(models.Model, RestModel, MetaDataModel):
    class RestMeta:
        GRAPHS = {
            "default": {
                "exclude":["media"],
                "extra":["download_url"]
            }
        }

        POST_SAVE_FIELDS = ["media"]


    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True)
    owner = models.ForeignKey(Member, related_name="+", on_delete=models.CASCADE)

    product = models.ForeignKey(Product, related_name="releases", on_delete=models.CASCADE)

    notes = models.TextField(blank=True, null=True, default=None)
    version_num = models.IntegerField(db_index=True, default=1)
    version_str = models.CharField(max_length=32, blank=True, null=True)

    media = models.ForeignKey(MediaItem, on_delete=models.PROTECT, blank=True, null=True, default=None)

    def makeCurrent(self):
        self.product.current = self
        self.product.save()

    def makeBeta(self):
        self.product.beta = self
        self.product.save()

    def download_url(self):
        if self.media:
            return self.media.url()
        return None

    def set_media(self, value, commit=False):
        if value is None:
            return

        if value.startswith("http"):
            media = MediaItem.CreateFromURL(value, self.owner, library=self.product.getLibrary(), kind=None)
            self.media = media
            if commit:
                self.save()
            return media

        request = get_request()
        name = request.DATA.get("media_name", "test.txt")
        kind = MediaItem.guessMediaKind(value)
        media = MediaItem(library=self.product.getLibrary(), name=name, owner=self.product.owner, kind=kind, base64_data=value)
        media.save()
        self.media = media

    # upload__ called for files
    def upload__media(self, value, name):
        if value is None:
            return

        kind = MediaItem.guessMediaKind(value)
        media = MediaItem(library=self.product.getLibrary(), name=name, owner=self.product.owner, kind=kind, newfile=value)
        media.save()
        self.media = media

    def __unicode__(self):
        return "{0} - {1}".format(self.product.name, self.version_str)



