from django.forms import ValidationError
import mimetypes
from io import StringIO
import base64
import binascii
import hashlib

EXT_MAP = {
    "V":['mpg', 'mpeg', 'mpe', 'mp4', 'm4v', 'mov', 'qt', '3gp', 'ogv', 'webm', 'flv', 'asf', 'asx', 'wmv', 'mpv', 'mkv', 'avi', 'dat', 'swf'],
    "I":['jpg', 'jpg', 'jpeg', 'gif', 'png', 'bmp', 'tif', 'tiff'],
    "T":['txt', 'html'],
}

KIND_MAP = {
    "video": "V",
    "image": "I",
    "http": "E"
}

def getFileExt(file):
    if hasattr(file, 'name'):
        return file.name.split(".")[-1].lower()
    return file.split(".")[-1].lower()

def guessBase64Kind(data):
    # look at first 16 bytes for ext
    sample = fromBase64ToBytes(data[:16]).lower() # data[:16]
    # sample = self.base64_data[:16].decode('base64').lower()
    for ext in ["png", "jpg", "jpeg", "jfif", "bmp", "gif", "tif"]:
        if toBytes(ext) in sample:
            if ext == "jfif":
                ext = "jpg"
            return ext
    return None

def getFileNameFromURL(url):
    return url.split("#")[0].split("?")[0].split("/")[-1]

def guessMediaKindByFile(file):
    if not hasattr(file, "name"):
        return guessMediaKindByName(file)
    if hasattr(file, 'content_type'):
        kind = guessMediaKindByContentType(file.content_type)
        if kind:
            return kind
    return guessMediaKindByFile(file.name)

def guessMediaKindByName(filename):
    kind = guessMediaKindByContentType(mimetypes.guess_type(filename))
    if kind:
        return kind
    # now lets look at our internal map
    ext = getFileExt(filename)
    for key in EXT_MAP:
        if ext in EXT_MAP[key]:
            return key
    return None

def guessMediaKindByContentType(content_type):
    # print content_type
    if type(content_type) is tuple:
        content_type = content_type[0]
    if not content_type:
        return None
    kind = content_type.split('/')[0]
    if kind == "video":
        return "V"
    elif kind == "image":
        return "I"
    elif kind == "text":
        return "T"
    return None

def guessMediaKind(file):
    kind = guessMediaKindByFile(file)
    if not kind:
        return '*'
    return kind

def validate_upload(file):
    kind = None
    kind = guessMediaKindByFile(file)
    if not kind:
        ext = getFileExt(file)
        return "*"
        # raise ValidationError("Invalid file type: .{0}".format(ext))
    return kind

# UTILS

def toString(value):
    if isinstance(value, bytes):
        value = value.decode()
    elif isinstance(value, bytearray):
        value = value.decode("utf-8")
    elif isinstance(value, (int, float)):
        value = str(value)
    return value

def toBytes(value):
    if isinstance(value, str):
        value = value.encode("utf-8")
    elif isinstance(value, bytearray):
        value = bytes(value)
    elif isinstance(value, (int, float)):
        value = str(value).encode('utf-8')
    return value

def toByteArray(value):
    if isinstance(value, bytearray):
        return value
    elif isinstance(value, str):
        return bytearray(value, 'utf-8')
    elif isinstance(value, bytes):
        return bytearray(value)
    return value

def toHex(value):
    return toBytes(value).hex().upper()

def hexToByteArray(value):
    return bytearray.fromhex(value)

def hexToString(value):
    return bytes.fromhex(value).decode('utf-8')

def toBase64(value):
    return base64.b64encode(value)

def fromBase64(value):
    return fromBase64ToString(value)

def fromBase64ToString(value):
    return toString(base64.b64decode(value))

def fromBase64ToBytes(value):
    return base64.b64decode(value)

def toMD5(*args):
    output = []
    for arg in args:
        output.append(hashlib.md5(toBytes(arg)).hexdigest())
    return "".join(output)
