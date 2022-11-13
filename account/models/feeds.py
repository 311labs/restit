from django.db import models


class FeedBase(models.Model):
    class Meta:
        abstract = True

    class RestMeta:
        GRAPHS = {
            "default": {
                "recurse_into": ["generic__component"]
            }
        }

    created = models.DateTimeField(auto_now_add=True, editable=True, db_index=True)
    component = models.SlugField(max_length=124, null=True, blank=True, default=None, db_index=True)
    component_id = models.IntegerField(null=True, blank=True, default=None, db_index=True)

    kind = models.SlugField(max_length=32, db_index=True)
    note = models.TextField(null=True, blank=True, default=None)

    @classmethod
    def log(cls, member, group, kind, component=None, component_id=None, note=None):
        obj = cls(member=member, group=group, kind=kind, component=component, component_id=component_id, note=note)
        obj.save()
        return obj


class MemberFeed(FeedBase):
    member = models.ForeignKey("account.Member", default=None, null=True, related_name="feed", on_delete=models.CASCADE)
    group = models.ForeignKey("account.Group", default=None, null=True, related_name="+", on_delete=models.CASCADE)


class GroupFeed(FeedBase):
    member = models.ForeignKey("account.Member", default=None, null=True, related_name="+", on_delete=models.CASCADE)
    group = models.ForeignKey("account.Group", default=None, null=True, related_name="feed", on_delete=models.CASCADE)

