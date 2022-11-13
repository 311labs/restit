
import os
import tempfile
import subprocess

tesseract_cmd = "/usr/bin/tesseract"

def hasTesseract():
    return os.path.exists(tesseract_cmd)

def ocrImage(img_path, **kwargs):
    # tessedit_char_whitelist=0123456789ABCDEF
    charset = kwargs.get("charset", None)
    pp_dpi = kwargs.get("pp_dpi", None)
    pp_noise = kwargs.get("pp_noise", None)
    pp_rotate = kwargs.get("pp_rotate", None)
    orig_path = img_path
    if pp_dpi:
        img_path = preprocessImage(img_path)
        # img_path = set_image_dpi(img_path, img_path)
    # if pp_noise:
    #     remove_noise_and_smooth(img_path, img_path)
    args = []
    if charset:
        args.append("-c")
        args.append("tessedit_char_whitelist={}".format(charset))
    return safe_cmd(tesseract_cmd, img_path, "stdout", *args)

from .cvutil import CVImage

def preprocessImage(image_path):
    img = CVImage(image_path)
    # shrink kernel to 2pixel w/h
    img.setKernel((2,2))
    # perform a series of commands to cleanup and bolden text
    # img.grayscale().adjust(50, 50).erode(4).save(image_path)
    img.reset().setKernel((2,2)).grayscale().adjust(50, 90).erode(2).bw().save(image_path)
    return image_path



