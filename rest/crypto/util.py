import base64
import re
import binascii
import string
import hmac
from hashlib import md5, sha512, sha256
from Crypto.Random import random as crypt_random
from hashids import Hashids


def generateKey(bit_size=128, allow_punctuation=False):
    byte_size = int(bit_size / 8)
    return randomString(byte_size, allow_punctuation)


def get_random_bits(bit_size=128):
    return crypt_random.getrandbits(bit_size)


def randomString(str_size=128, allow_punctuation=False, char_list=None):
    if char_list is None:
        char_list = string.ascii_letters + string.digits
    if allow_punctuation:
        char_list += string.punctuation
    return ''.join([crypt_random.choice(char_list) for n in range(str_size)])


def randomCode(str_size=6):
    return randomString(str_size, False, string.digits)


def hash(data):
    return hashMD5(data)


def hashit(data, salt=None):
    return hashSHA512(data, salt)


def obfuscateID(label, int_id):
    return Hashids(label).encode(int_id)


def unobfuscateID(label, obfuscated_id):
    res = Hashids(label).decode(obfuscated_id)
    if len(res):
        return res[0]
    return None


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


def toBase64(value, as_str=True):
    if isinstance(value, str):
        value = toBytes(value)
    if as_str:
        return toString(base64.b64encode(value))
    return base64.b64encode(value)


def fromBase64(value, as_str=True):
    if as_str:
        return toString(base64.b64decode(value))
    return base64.b64decode(value)


def hashSHA256(data, salt=None):
    bdat = toBytes(data)
    if salt is not None:
        bdat = toBytes(salt) + bdat
    return toString(sha256(bdat).hexdigest())


def hashSHA512(data, salt=None):
    bdat = toBytes(data)
    if salt is not None:
        bdat = toBytes(salt) + bdat
    return toString(sha512(toBytes(bdat)).hexdigest())


def hashMD5(data):
    return toString(md5(toBytes(data)).hexdigest())


def getSSHSignature(pub_key):
    data = pub_key.strip()
    # accept either base64 encoded data or full pub key file,
    # same as `fingerprint_from_ssh_pub_key
    if (re.search(r'^ssh-(?:rsa|dss|ed25519) ', data)):
        data = data.split(None, 2)[1]
    # Python 2/3 hack. May be a better solution but this works.
    data = toBytes(data)
    digest = sha256(binascii.a2b_base64(data)).digest()
    encoded = toString(base64.b64encode(digest).rstrip(b'='))  # ssh-keygen strips this
    return "SHA256:" + encoded


def pad(data, block_size=16):
    # PKCS7Padding
    # if isinstance(data, str):
    #     data = str(data)
    length = block_size - (len(data) % block_size)
    return data + (chr(length) * length).encode()


def unpad(data):
    # PKCS7Padding
    return data[:-(data[-1] if type(data[-1]) == int else ord(data[-1]))]

def generateHMAC(label, val, length, encoding="base32", secret=None):
    if secret is None:
        secret = hashSHA256(label)
    ret = hmac.new(toBytes(secret + label), toBytes(val), sha512)
    if encoding == "base32":
        retstr = toString(base64.b32encode(ret.digest()))
    else:
        retstr = toHex(ret.digest())
    return retstr[:length].lower()
