
import base64
import binascii
import json
from io import BytesIO

try:
    from Crypto import Random
    from Crypto.PublicKey import RSA
    from Crypto.Cipher import AES, PKCS1_OAEP
except Exception:
    print("missing Crypto module.... pip install pycrypto")

from . import util


class PrivatePublicEncryption(object):
    def __init__(self, private_key=None, public_key=None, private_key_file=None, public_key_file=None):
        if private_key_file:
            with open(private_key_file, 'r') as f:
                private_key = f.read()
        if public_key_file:
            with open(public_key_file, 'r') as f:
                public_key = f.read()
        if private_key:
            if isinstance(private_key, str):
                private_key = RSA.importKey(private_key)
        self.private_key = private_key
        if public_key:
            if isinstance(public_key, str):
                public_key = RSA.importKey(public_key)
        self.public_key = public_key

    def generatePublicKey(self, make_new=False):
        if self.public_key is None or make_new:
            self.public_key = generatePublicKey(self.private_key)
        return self.public_key

    def encrypt(self, data):
        self.generatePublicKey()
        return self.encryptToB64(data)

    def decrypt(self, data, as_string=True):
        return self.decryptFromB64(data, as_string)

    def encryptToB64(self, data):
        # this function exports encrypted data as base64
        ebytes = encryptWithPublicKey(data, self.public_key)
        return util.toString(base64.b64encode(ebytes))

    def decryptFromB64(self, data, as_string=True):
        data = base64.b64decode(data)
        return decryptWithPrivateKey(data, self.private_key, as_string)

    def encryptToHex(self, data):
        # this function exports encrypted data as hex
        ebytes = encryptWithPublicKey(data, self.public_key)
        return util.toString(binascii.hexlify(ebytes))

    def decryptFromHex(self, data, as_string=True):
        data = binascii.unhexlify(data)
        return decryptWithPrivateKey(data, self.private_key, as_string)


def generatePrivateKey(size=2048):
    """
        key = RSA.generate(size)
        private_key = key.export_key()
        file_out = open("private.pem", "wb")
        file_out.write(private_key)
    """
    return RSA.generate(size)


def generatePublicKey(private_key):
    """
    public_key = private_key.publickey().export_key()
    file_out = open("receiver.pem", "wb")
    file_out.write(public_key)
    """
    if isinstance(private_key, str):
        private_key = RSA.import_key(private_key)
    return private_key.publickey()


def encryptWithPublicKey(data, public_key):
    if isinstance(public_key, str):
        public_key = RSA.import_key(public_key)

    if isinstance(data, dict) or isinstance(data, list):
        data = json.dumps(data)

    session_key = Random.get_random_bytes(16)

    # Encrypt the session key with the public RSA key
    cipher_rsa = PKCS1_OAEP.new(public_key)
    enc_session_key = cipher_rsa.encrypt(session_key)

    # Encrypt the data with the AES session key
    cipher_aes = AES.new(session_key, AES.MODE_EAX)
    ciphertext, tag = cipher_aes.encrypt_and_digest(util.toBytes(data))
    output = BytesIO()
    [output.write(x) for x in (enc_session_key, cipher_aes.nonce, tag, ciphertext)]
    raw = output.getvalue()
    output.close()
    return raw


def decryptWithPrivateKey(data, private_key, as_string=True):
    if isinstance(private_key, str):
        private_key = RSA.import_key(private_key)
    if isinstance(data, (str, bytes)):
        data = BytesIO(data)
    enc_session_key, nonce, tag, ciphertext = \
        [data.read(x) for x in (private_key.size_in_bytes(), 16, 16, -1)]

    cipher_rsa = PKCS1_OAEP.new(private_key)
    session_key = cipher_rsa.decrypt(enc_session_key)

    cipher_aes = AES.new(session_key, AES.MODE_EAX, nonce)
    decrypted_data = cipher_aes.decrypt_and_verify(ciphertext, tag)
    if as_string:
        return util.toString(decrypted_data)
    return decrypted_data
