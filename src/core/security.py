"""Security and Cryptography Module for JobSniper ET.

Implements AES-256-GCM authenticated encryption for candidate CV text and sensitive data.
"""

import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from src.config.settings import settings


class SecurityManager:
    """Manages encryption and decryption of sensitive user payloads."""

    def __init__(self, key_b64: str = None):
        key_str = key_b64 or settings.CV_ENCRYPTION_KEY
        try:
            self._key = base64.urlsafe_b64decode(key_str.encode())
            if len(self._key) != 32:
                # Fallback: pad or hash to 32 bytes if not exact
                import hashlib
                self._key = hashlib.sha256(self._key).digest()
        except Exception:
            import hashlib
            self._key = hashlib.sha256(key_str.encode()).digest()

        self._aesgcm = AESGCM(self._key)

    def encrypt_text(self, plaintext: str) -> str:
        """Encrypts a plaintext string and returns a base64 encoded string containing nonce + ciphertext."""
        if not plaintext:
            return ""
        # 12-byte standard nonce for AES-GCM
        nonce = os.urandom(12)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        # Combine nonce + ciphertext
        payload = nonce + ciphertext
        return base64.urlsafe_b64encode(payload).decode("utf-8")

    def decrypt_text(self, encrypted_b64: str) -> str:
        """Decrypts a base64 encoded payload produced by encrypt_text."""
        if not encrypted_b64:
            return ""
        try:
            raw = base64.urlsafe_b64decode(encrypted_b64.encode("utf-8"))
            nonce = raw[:12]
            ciphertext = raw[12:]
            plaintext_bytes = self._aesgcm.decrypt(nonce, ciphertext, None)
            return plaintext_bytes.decode("utf-8")
        except Exception as e:
            # If decryption fails or data was not encrypted
            return encrypted_b64


# Singleton security instance
security_manager = SecurityManager()

