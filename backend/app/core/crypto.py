"""Secret encryption (S10 rule 8): Fernet with `ENCRYPTION_KEY`. Worker-only.

Plaintext secrets are never logged, never returned by the API, never passed to agent code.
"""

from cryptography.fernet import Fernet, InvalidToken

from app.core.settings import Settings, get_settings


class CryptoError(RuntimeError):
    """Missing/invalid key, or ciphertext that this key can't decrypt."""


def get_fernet(settings: Settings | None = None) -> Fernet:
    settings = settings or get_settings()
    key = settings.encryption_key.get_secret_value() if settings.encryption_key else ""
    if not key:
        raise CryptoError("ENCRYPTION_KEY is not set; the sync worker refuses to start without it.")
    try:
        return Fernet(key.encode())
    except ValueError as exc:
        raise CryptoError("ENCRYPTION_KEY is not a valid Fernet key.") from exc


def encrypt(plaintext: str, fernet: Fernet | None = None) -> bytes:
    return (fernet or get_fernet()).encrypt(plaintext.encode("utf-8"))


def decrypt(ciphertext: bytes, fernet: Fernet | None = None) -> str:
    try:
        return (fernet or get_fernet()).decrypt(bytes(ciphertext)).decode("utf-8")
    except InvalidToken as exc:
        raise CryptoError("Secret can't be decrypted with the current ENCRYPTION_KEY.") from exc
