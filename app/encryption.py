import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .unlock_acc import get_account_password


class Encryption:
    key = None

    @classmethod
    def _check_status(cls):
        password = get_account_password()
        if not password:
            raise Exception("Cannot get password from shkeeper, quit")
        elif password and (cls.key is None):
            cls.key  = cls._get_key_from_password(password)
        else:
            pass

    @classmethod
    def encrypt(cls, cleartext):
        cls._check_status()
        return cls._encrypt(cleartext)

    @classmethod
    def decrypt(cls, ciphertext):
        cls._check_status()
        return cls._decrypt(ciphertext)

    @classmethod
    def _get_key_from_password(cls, password: str):
        salt = b'Shkeeper4TheWin!'
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=500_000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    @classmethod
    def _encrypt(cls, cleartext: str):
        return base64.urlsafe_b64encode(Fernet(cls.key).encrypt(cleartext.encode())).decode()

    @classmethod
    def _decrypt(cls, ciphertext: str):
        return Fernet(cls.key).decrypt(base64.urlsafe_b64decode(ciphertext)).decode()