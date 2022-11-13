from .models import *
from . import stores

from django.shortcuts import render, get_object_or_404, Http404
from django.http import HttpResponse

def smil(request, item_id, token=None):
    item = get_object_or_404(MediaItem, pk=item_id)
    #if not item.check_token(token):
    #   item.assertAcl("R", request.user)
    renditions = item.renditions.filter(use='video').order_by('-created')
    rseen = []
    ret = []
    base = ""
    for r in renditions:
        if r.rendition_definition_id in rseen:
            continue
        rseen.append(r.rendition_definition_id)
        urls = r.view_url().split("/")
        url = urls.pop()
        base = "/".join(urls)
        ret.append({
            'url': url,
            'bitrate': r.bitrate(),
        })

    return render(request, 'medialib/smil',
        RequestContext(request, {
            'base': base,
            'item': item,
            'renditions': ret,
        }),
        mimetype="application/smil",
    )


def hlsIndex(request, rendition_id, token=None):
    rendition = get_object_or_404(MediaItemRendition, pk=rendition_id)
    if not rendition.mediaitem.check_token(token):
        rendition.mediaitem.assertAcl("R", request.user)

    try:
        bufsize = int(request.DATA.get('buffer', 30))
    except ValueError:
        bufsize = 30

    segment_duration = rendition.get_meta('segment_duration', 1, int)
    final = rendition.get_meta('final')

    if final and not request.DATA.get('live', False):
        segments = rendition.segments.order_by('segment').values_list('segment', 'url', 'duration')
        if not segments:
            raise Http404
    else:
        segments = list(rendition.segments.order_by('-segment')[:int(bufsize/segment_duration)].values_list('segment', 'url', 'duration'))
        segments.reverse()

    try:
        outbuf = """#EXTM3U
#EXT-X-TARGETDURATION:%d
#EXT-X-MEDIA-SEQUENCE:%d
#EXT-X-SLIDINGWINDOW
""" % (segment_duration, segments[0][0]+3)
        for s in segments:
            outbuf += "#EXTINF:%d,\n" % s[2]
            outbuf += stores.view_url(s[1], is_secure=request.is_secure(), request=request) + "\n"
        if final:
            outbuf += "#EXT-X-ENDLIST\n"
    except IndexError:
        outbuf = """#EXTM3U
#EXT-X-TARGETDURATION:3
#EXT-X-MEDIA-SEQUENCE:0
#EXT-X-SLIDINGWINDOW
#EXTINF:3,
/static/video/wait.ts
"""
    return HttpResponse(outbuf, mimetype="application/vnd.apple.mpegurl")

def instances(request):
    if not request.user.is_superuser:
        raise NotAuthorized

    start = request.DATA.get('start', 0)
    count = request.DATA.get('count', 25)

    instances = RenderInstance.objects.all().order_by('-priority', '-shutdown', '-priority', 'started')[start:start+count]
    return render(request, 'medialib/instances.html', {
        'title': 'Rendering Instances',
        'instances': instances,
        'more': (len(instances) == count) and (start+count+1) or None
    })

def renderErrors(request):
    if not request.user.is_superuser:
        raise NotAuthorized

    start = request.DATA.get('start', 0)
    count = request.DATA.get('count', 25)

    items = MediaItem.objects.filter(state=110).order_by('-id')[start:start+count]
    return render(request, 'medialib/items.html', {
        'title': 'Rendering Errors',
        'items': items,
        'more': (len(items) == count) and (start+count+1) or None
    })

def renderPending(request):
    if not request.user.is_superuser:
        raise NotAuthorized

    items = MediaItem.objects.filter(state__gte=100, state__lt=110).order_by('id')
    return render(request, 'medialib/items.html', {
        'title': 'Pending Renders',
        'items': items,
    })

def showLibrary(request, library_id):
    if not request.user.is_superuser:
        raise NotAuthorized

    library = MediaLibrary.objects.get(pk=library_id)
    libraries = MediaLibrary.objects.all()
    return render(request, 'medialib/library.html', {
        'title': 'Pending Renders',
        'library': library,
        'libraries': libraries
    })

def showLibraryOld(request, library_id):
    if not request.user.is_superuser:
        raise NotAuthorized

    library = MediaLibrary.objects.get(pk=library_id)
    return render(request, 'medialib/testpicker.html', {
        'title': 'Pending Renders',
        'library': library,
    })
