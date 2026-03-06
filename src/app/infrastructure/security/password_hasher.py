"""PBKDF2-реализация хеширования паролей."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

from app.application.ports.password_hasher import PasswordHasherPort

_HASH_ALGORITHM = 'sha256'
_PBKDF2_ITERATIONS = 600_000


class Pbkdf2PasswordHasher(PasswordHasherPort):
    """Сервис хеширования и верификации паролей через PBKDF2."""

    def hash_password(self, plain_password: str) -> str:
        """Сформировать хеш пароля.

        Args:
            plain_password: Пароль в открытом виде.

        Returns:
            Строка с параметрами алгоритма и хешем.
        """
        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac(
            _HASH_ALGORITHM,
            plain_password.encode('utf-8'),
            salt,
            _PBKDF2_ITERATIONS,
        )
        salt_b64 = base64.urlsafe_b64encode(salt).decode('ascii')
        digest_b64 = base64.urlsafe_b64encode(digest).decode('ascii')
        return f'pbkdf2_{_HASH_ALGORITHM}${_PBKDF2_ITERATIONS}${salt_b64}${digest_b64}'

    def verify_password(self, plain_password: str, password_hash: str) -> bool:
        """Проверить пароль по сохраненному хешу.

        Args:
            plain_password: Пароль в открытом виде.
            password_hash: Строка сохраненного хеша.

        Returns:
            `True`, если пароль валиден, иначе `False`.
        """
        try:
            algorithm, iterations_raw, salt_b64, digest_b64 = password_hash.split('$', maxsplit=3)
            if algorithm != f'pbkdf2_{_HASH_ALGORITHM}':
                return False

            iterations = int(iterations_raw)
            salt = base64.urlsafe_b64decode(salt_b64.encode('ascii'))
            expected_digest = base64.urlsafe_b64decode(digest_b64.encode('ascii'))
            actual_digest = hashlib.pbkdf2_hmac(
                _HASH_ALGORITHM,
                plain_password.encode('utf-8'),
                salt,
                iterations,
            )
            return hmac.compare_digest(actual_digest, expected_digest)
        except (TypeError, ValueError):
            return False
