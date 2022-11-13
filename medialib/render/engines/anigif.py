import PIL
from PIL import Image, ImageChops
from PIL.GifImagePlugin import getheader, getdata
try:
    from PIL.GifImagePlugin import _write_multiple_frames
except:
    _write_multiple_frames = None

def intToBin(i):
    """ Integer to two bytes """
    i1 = i % 256
    i2 = int( i/256)
    return chr(i1) + chr(i2)


def getheaderAnim(im):
    """ Animation header. To replace the getheader()[0] """
    bb = "GIF89a"
    bb += intToBin(im.size[0])
    bb += intToBin(im.size[1])
    bb += "\x87\x00\x00"
    return bb


def getAppExt(loops=0):
    """ Application extention. Part that secifies amount of loops. 
    if loops is 0, if goes on infinitely.
    """
    bb = "\x21\xFF\x0B"  # application extension
    bb += "NETSCAPE2.0"
    bb += "\x03\x01"
    if loops == 0:
        loops = 2**16-1
    bb += intToBin(loops)
    bb += '\x00'  # end
    return bb


def getGraphicsControlExt(duration=0.1):
    """ Graphics Control Extension. A sort of header at the start of
    each image. Specifies transparancy and duration. """
    bb = '\x21\xF9\x04'
    bb += '\x08'  # no transparancy
    bb += intToBin( int(duration*100) ) # in 100th of seconds
    bb += '\x00'  # no transparant color
    bb += '\x00'  # end
    return bb

# def run(fp, images, durations, loops):
# 	pass

def getPalette(images):
    # check which colors are used
    used_palette_colors = []
    for im in images:
        for i, count in enumerate(im.histogram()):
            if count and i not in used_palette_colors:
                used_palette_colors.append(i)
    used_palette_colors.sort()
    return used_palette_colors

def run(fp, images, durations, loops):
    """
    Given a set of images writes the bytes to the specified stream.
    """

    if hasattr(durations, '__len__'):
        if len(durations) != len(images):
            raise ValueError("number of durations mismatch with infiles")
    else:
        durations = [durations] * len(images)

    img = images[0]
    img.save(fp, save_all=True, append_images=images[1:], duration=durations, loop=0)
    return len(images)

def writeGif(fp, images, durations, loops):
    _write_multiple_frames(im, fp, images)

def writeLegacyGif(fp, images, durations, loops):
    frames = 0
    previous = None
    cimages = []
    for img in images:
        cimg = img.convert('P', palette=Image.ADAPTIVE, dither=1)
        cimages.append(cimg)

    palette = getPalette(cimages)
    print(("pallette size is: {}".format(len(palette))))
    for img in cimages:
        if not previous:
            # first image
            # gather data
            data = getdata(img)
            imdes, data = data[0], data[1:]
            header = getheaderAnim(img)
            appext = getAppExt(loops)
            graphext = getGraphicsControlExt(durations[0])

            # write global header
            fp.write(header)
            fp.write(palette)
            fp.write(appext)

            # write image
            fp.write(graphext)
            fp.write(imdes)
            for d in data:
                fp.write(d)
        else:
            # gather info (compress difference)
            data = getdata(img) 
            imdes, data = data[0], data[1:]
            graphext = getGraphicsControlExt(durations[frames])

            # write image
            fp.write(graphext)
            fp.write(imdes)
            for d in data:
                fp.write(d)
        # previous = img.copy()
        previous = True
        frames = frames + 1
    fp.write(";")  # end gif
    return frames

