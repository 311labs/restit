from django.http import HttpResponse

from rest import decorators as rd
from medialib.qrcode import generateQRCode


@rd.url(r'^qrcode$')
def qrcode_image(request):
    params = dict(data=request.DATA.get("data", "missing data"))
    error = request.DATA.get("error", None)
    if error is not None:
        params["error"] = error
    version = request.DATA.get("version", None)
    if version is not None:
        params["version"] = int(version)
    img_format = request.DATA.get("format", "png")
    if img_format is not None:
        params["img_format"] = img_format
    scale = request.DATA.get("scale", 1)
    if scale is not None:
        params["scale"] = int(scale)

    code = generateQRCode(**params)
    if img_format == "base64":
        return HttpResponse(code, content_type="text/plain")
    elif img_format == "svg":
        return HttpResponse(code, content_type="image/svg+xml")
    return HttpResponse(code, content_type="image/png")
