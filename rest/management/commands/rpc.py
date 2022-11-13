from django.core.management.base import BaseCommand
import urls

from rest import url_docs

class Command(BaseCommand):
    help = "Inspect urlpatterns and their views looking for mismatched arguments"

    def handle(self, *labels, **options):
        apis = url_docs.getRestApis(urls.urlpatterns)

        for api in apis:
            print((api["url"]))
            print((api["doc"]))
