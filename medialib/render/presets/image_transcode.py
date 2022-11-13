from ..render_utils import *
from ..exceptions import *
from .. import render_utils

import os
import tempfile
import copy
from PIL import Image


from rest.log import getLogger
logger = getLogger("medialib", filename="medialib.log")


PresetConfig = [{
    'name':		'Image Transcode',
    'description':	'Transcode image to alternate size/quality/container',
    'stage':	50,
    'short_name':	'image_transcode',
    'default_use':	'image',
    'applicable_kinds': 'I',
    'parameters': {
        'image_container': {
            'description':	'Output image container extension',
            'required':	True,
            'kind':		'C',
            'configurable':	True,
            'choices':	'gif,jpg,png',
            'value':	'jpg',
        },
        'detect_black': {
            'description':	'detect black bounding areas',
            'required':	False,
            'kind':		'B',
            'configurable':	True,
            'value':	1,
        },
        'quality': {
            'description':	'Image quality, 1-100',
            'required':	False,
            'kind':		'I',
            'configurable':	True,
            'value':	75,
        },
    },
}]
PresetConfig[0]['parameters'].update(copy.deepcopy(render_utils.PresetParameters))

PresetConfig.append(copy.deepcopy(PresetConfig[0]))
PresetConfig[1].update({
    'name':		'Image Thumbnail',
    'description':	'transcode image to thumbnail',
    'stage':	20,
    'short_name':	'thumbnail',
})
render_utils.update_params(PresetConfig[1],
    maxwidth = 128,
    maxaspect = 1,
    quality = 95,
    minheight = 32,
    minwidth = 32,
)

PresetConfig.append(copy.deepcopy(PresetConfig[0]))
PresetConfig[2].update({
    'name':		'Image Thumbnail (zoomed)',
    'description':	'transcode image to zoomed-in thumbnail of specific size',
    'stage':	20,
    'short_name':	'thumbnail_zoomed',
})
render_utils.update_params(PresetConfig[2],
    quality = 95,
)


container_settings = {
    'jpg': {
        'mode': 'RGBA',
        'kind': 'JPEG',
    },
    'gif': {
        'mode': 'RGBA',
        'kind': 'GIF',
    },
    'png': {
        'mode': 'RGBA',
        'kind': 'GIF',
    },
}
        

def render(item, renditiondef, params):
    logger.info("image_transacoding...")
    if params.get('image_container', '') in container_settings:
        container = container_settings[params['image_container']]
    else:
        raise RenderError('%s: Unknown image container: %s' % (renditiondef.name, params.get('image_container', 'Undefined')))

    original = get_rendition(item, 'still')
    params['no_threads'] = True
    fp = None
    logger.info("image_transacoding 2...")
    try:
        im = Image.open(original.filename)
        orig_kind = im.format
        if orig_kind:
            orig_kind = orig_kind.lower()

        im.draft(container['mode'], im.size)
        
        im = adjust_exif(im)
        
        size = im.size
        if 'detect_black' in params and params['detect_black']:
            bound = Image.eval(im, lambda p: p>5 and p or 0).getbbox()
            
            if bound:
                bound_size = (bound[2]-bound[0], bound[3]-bound[1])
                
                if bound_size == size:
                    # original size and bound are the same - ignore boundary
                    bound = None
                else:
                    size = bound_size
        else:
            bound = None
        # print "presize: ",
        # print params
        logger.info("image params..", params)
        params = calc_size(params, size[0], size[1], even=False, rotate=original.get_meta('rotate'))
        logger.info("image post params..", params)
        # print "rendering image: ",
        # print params

        if not bound:
            pass
        elif 'crop' in params:
            params['crop'] = (params['crop'][0]+bound[0], params['crop'][1]+bound[1], params['crop'][2]+bound[0], params['crop'][3]+bound[1], )
        else:
            params['crop'] = bound

        if 'crop' in params:
            im = im.crop(params['crop'])
        if 'width' in params and 'height' in params:
            if size[0] > params['width']*3 and size[1] > params['height']*3:
                # do 2-pass resize - fast low quality resize
                im.thumbnail((params['width']*3, params['height']*3))
            logger.info("image resizing..")
            # do slow high quality resize
            im = im.resize((params['width'], params['height']), Image.ANTIALIAS)
        
        if im.mode != container['mode']:
            im = im.convert(container['mode'])

        saveopts = {}
        if 'quality' in params:
            saveopts['quality'] = params['quality']

        # ians keep the original format if GIF or PNG to keep transparency
        kind = container["kind"].lower()

        if orig_kind != kind and orig_kind in ["gif", "png"]:
            kind = orig_kind 
        # print container
        # print "original format: {0}... new format: {1}".format(orig_kind, kind)
        # fp = tempfile.NamedTemporaryFile(suffix=('.' + params.get('image_container', 'jpg')), prefix="t_transcode_")
        fp = tempfile.NamedTemporaryFile(suffix=('.' + kind), prefix="t_transcode_")
        dstfile = fp.name
        if im.mode == "RGBA" and kind not in ["gif", "png"]:
            # im = im.convert("RGB")
            kind = "png"

        im.save(dstfile, kind, **saveopts)
        logger.info("image saved: {}".format(dstfile))
        new_rendition(item, renditiondef, fp, kind='I', width=im.size[0], height=im.size[1])
        if hasattr(im, "close"):
            im.close()
        fp.close()

    except (IOError, SyntaxError, ValueError, EOFError, AttributeError, IndexError, CmdError) as err:
        logger.error("image_transcode")
        try:
            if fp:
                fp.close()
        except:
            pass
        raise RenderError('%s: %s' % (renditiondef.name, str(err)), stack=err, show_stack=True)

def adjust_exif(im):
    # fix any camera rotations
    try:
        info = im._getexif()
    except (AttributeError, KeyError):
        return im
    if info and 0x0112 in info and info[0x0112]:
        orient = info[0x0112]
        if orient == 1: # A-OK
            pass
        if orient == 2: # mirror horz
            im = im.transpose(FLIP_LEFT_RIGHT)
        elif orient == 3: # rotated 180
            im = im.transpose(Image.ROTATE_180)
        elif orient == 4: # mirror vert
            im = im.transpose(Image.FLIP_TOP_BOTTOM)
        elif orient == 5: # mirror horz rotated 90 ccw
            im = im.transpose(Image.ROTATE_90).transpose(FLIP_LEFT_RIGHT)
        elif orient == 6: # rotated 90 cw
            im = im.transpose(Image.ROTATE_270)
        elif orient == 7: # mirror horz rotated 90 cw
            im = im.transpose(Image.ROTATE_270).transpose(FLIP_LEFT_RIGHT)
        elif orient == 8: # rotated 90 ccw
            im = im.transpose(Image.ROTATE_90)
    
    return im
