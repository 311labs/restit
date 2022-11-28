from rest import decorators as rd
from account.models.settings import Settings


@rd.url(r'^settings$')
@rd.url(r'^settings/$')
@rd.url(r'^settings/(?P<pk>\d+)$')
@rd.staff_required
def on_rest_settings(request, pk=None):
    return Settings.on_rest_request(request, pk)
