"""Контракт сервиса хеширования паролей."""


class PasswordHasherPort:
    """Порт хеширования и проверки паролей."""

    def hash_password(self, plain_password: str) -> str:
        """Сформировать хеш пароля.

        Args:
            plain_password: Пароль в открытом виде.

        Returns:
            Строка с хешем пароля.
        """
        raise NotImplementedError

    def verify_password(self, plain_password: str, password_hash: str) -> bool:
        """Проверить соответствие пароля хешу.

        Args:
            plain_password: Пароль в открытом виде.
            password_hash: Хеш пароля.

        Returns:
            `True`, если пароль корректен, иначе `False`.
        """
        raise NotImplementedError
