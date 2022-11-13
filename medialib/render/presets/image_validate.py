from ..render_utils import *
from ..exceptions import *

import os
from PIL import Image

PresetConfig = {
    'name':		'Validate Image',
    'description':	'Basic image validation',
    'stage':	1,
    'default_use':	'validate',
    'applicable_kinds': 'I',
    'parameters': {
    },
}

def image_is_animated_gif(image):
    # verify image format
    if image.format.lower() != 'gif':
        return False

    # verify GIF is animated by attempting to seek beyond the initial frame
    try:
        image.seek(1)
    except EOFError:
        return False
    else:
        return True

def render(item, renditiondef, params):
    original = get_rendition(item, 'original')

    try:
        im = Image.open(original.filename)
        if image_is_animated_gif(im):
            original.kind = "N"
        original.width = im.size[0]
        original.height = im.size[1]
        original.save()
    except (IOError, SyntaxError, ValueError, EOFError, AttributeError, IndexError, CmdError) as err:
        raise RenderError('%s: %s' % (renditiondef.name, str(err)), stack=err, show_stack=True)
