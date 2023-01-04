from Crypto.Cipher import AES
from Crypto import Random
from hashlib import md5

import json
from . import util


DEFAULT_SALT = b"Salted__"
MD5V_SALT = b"__MD5V__"
SDKV_SALT = b"__SDKV__"
SDKV16_SALT = b"__SDKV16"

KNOWN_SALTS = [DEFAULT_SALT, SDKV_SALT, MD5V_SALT, SDKV16_SALT]

DEFAULT_IV_GENERATOR = "md5"

# THIS USES AES/CBC/PKCS7Padding

def encrypt(key, data, random_size=128, ivgen=DEFAULT_IV_GENERATOR):
    """
    encrypts @data with @key using AES
    will pad data with random string of @random_size
        this will keep it so the same data is never producing the same encryption
    returns bytes as base64 string
    """
    if random_size > 0:
        rdata = util.toBytes(data) + util.toBytes(util.randomString(random_size))
    else:
        rdata = data
    return util.toString(cbc_encrypt(key, rdata, ivgen))


def decrypt(key, edata, random_size=128, as_string=True):
    encrypted = util.fromBase64(edata, False)
    data = cbc_decrypt(key, encrypted)
    if random_size > 0:
        data = data[:-1 * random_size]
    if as_string:
        return util.toString(data)
    return data


def cbc_encrypt(key, data, ivgen=DEFAULT_IV_GENERATOR):
    if isinstance(data, dict) or isinstance(data, list):
        data = json.dumps(data)
    salt_prefix = getSaltPrefix(ivgen)
    data = util.toBytes(data)
    key = util.toBytes(key)
    salt = Random.new().read(8)
    if ivgen == "simple": 
        key_iv = deterministric_key_iv(ivgen, key, salt, 32)
        key = key_iv[:16]
        iv = key_iv[16:]
    else:
        key_iv = deterministric_key_iv(ivgen, key, salt, 32 + 16)
        key = key_iv[:32]
        iv = key_iv[32:]
    aes = AES.new(key, AES.MODE_CBC, iv)
    return util.toBase64(salt_prefix + salt + aes.encrypt(util.pad(data)))


def cbc_decrypt(key, encrypted):
    salt_prefix = encrypted[0:8]
    if salt_prefix not in KNOWN_SALTS:
        print("unknown salt: {}".format(str(salt_prefix)))
    key = util.toBytes(key)
    salt = encrypted[8:16]
    if salt_prefix == SDKV16_SALT:  
        key_iv = deterministric_key_iv(salt_prefix, key, salt, 32)
        key = key_iv[:16]
        iv = key_iv[16:]
    else:
        key_iv = deterministric_key_iv(salt_prefix, key, salt, 32 + 16)
        key = key_iv[:32]
        iv = key_iv[32:]
    aes = AES.new(key, AES.MODE_CBC, iv)
    decrypted = aes.decrypt(encrypted[16:])
    return util.unpad(decrypted)


def deterministric_key_iv(generator, data, salt, length=48):
    if generator in [DEFAULT_SALT, MD5V_SALT, "md5"]:
        return md5_deterministic_key_iv(data, salt, length)
    return simple_deterministic_key_iv(data, salt, length)


def getSaltPrefix(generator):
    if generator == "md5":
        return DEFAULT_SALT
    elif generator == "simple":
        return SDKV16_SALT
    return SDKV_SALT


def md5_deterministic_key_iv(data, salt, length=48):
    # extended from https://gist.github.com/gsakkis/4546068
    assert len(salt) == 8, len(salt)
    data += salt
    key = md5(data).digest()
    final_key = key
    while len(final_key) < length:
        key = md5(key + data).digest()
        final_key += key
    return final_key[:length]


def simple_deterministic_key_iv(data, salt, length=48):
    src = data + salt
    src_len = len(src)
    dst = bytearray(length)
    p = salt[2] >> 4
    while p >= src_len:
        p = int(p / 2)
    x = len(data)
    for i in range(0, length):
        h = (src[p] - src[x]) * (src[p])
        dst[i] = h & 255
        p -= 1
        if p <= 0:
            p = src_len - 1
        x += 1
        if x >= src_len:
            x = 0
    return bytes(dst)




