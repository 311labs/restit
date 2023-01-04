import os
from .settings_helper import settings
from rest.crypto.privpub import PrivatePublicEncryption


DECRYPTER_KEY_FILE = os.path.join(settings.PROJECT_ROOT, "config", "decrypt_key.pem")
DECRYPTER = None
if not os.path.exists(DECRYPTER_KEY_FILE):
    print(("WARNING, failed to load decrypter!!! {}".format(DECRYPTER_KEY_FILE)))
    DECRYPTER_KEY_FILE = os.path.join(os.path.dirname(os.path.dirname(settings.ROOT)), "config", "decrypt_key.pem")

if os.path.exists(DECRYPTER_KEY_FILE):
    DECRYPTER = PrivatePublicEncryption(private_key_file=DECRYPTER_KEY_FILE)


ENCRYPTER_KEY_FILE = os.path.join(settings.PROJECT_ROOT, "config", "encrypt_key.pem")
ENCRYPTER = None
if os.path.exists(ENCRYPTER_KEY_FILE):
    ENCRYPTER = PrivatePublicEncryption(private_key_file=ENCRYPTER_KEY_FILE)
