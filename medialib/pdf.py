from io import BytesIO
from django.template.loader import get_template
from django.template import Context
from django.http import HttpResponse
from html import escape
from django.conf import settings
from rest.helpers import toString
from rest import settings
import os

try:
    from xhtml2pdf import pisa
except:
    pass

def fetch_resources(uri, rel):
    if settings.get("CDN_DOMAIN", "cdn.") in uri:
        return uri
    path = os.path.join(settings.STATIC_ROOT, uri.replace("/static/", ""))
    return path

def render_to_pdf(context):
    template = get_template(context.template_src)
    html  = template.render(context)
    result = BytesIO()
    pdf = pisa.CreatePDF(html, result, link_callback=fetch_resources)
    return pdf, result.getvalue()

def render_to_pdf_response(context):
    template = get_template(context.template_src)
    html  = template.render(context)
    result = BytesIO()
    pdf = pisa.CreatePDF(html, result, link_callback=fetch_resources)
    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename={}.pdf'.format(context.filename)
        return response
    return HttpResponse('We had some errors<pre>%s</pre>' % escape(html))