
from ..engines import websnap
from ..render_utils import *
from ..exceptions import *

from PIL import Image

from django.conf import settings

PresetConfig = {
    'name':		'WebSnap',
    'description':	'Snapshot a URL',
    'stage':	101,
    'default_use':	'websnap',
    'applicable_kinds': 'E',
}



def render(item, renditiondef, params):
    fp = tempfile.NamedTemporaryFile(suffix=('.' + params.get('image_container', 'png')), prefix="t_websnap_")
    dstfile = fp.name
    tmpdir = tempfile.mkdtemp()
    prevdir = os.getcwd()
    os.chdir(tmpdir)

    original = get_rendition(item, 'original')

    websnap.run(dstfile, original.url)
    im = Image.open(dstfile)
    params["width"] = im.size[0]
    params["height"] = im.size[1]

    new_rendition(item, renditiondef, fp, kind='I', width=params.get('width', None), height=params.get('height', None))

