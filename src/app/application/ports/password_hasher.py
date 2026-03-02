class PasswordHasherPort:
    def hash_password(self, plain_password: str) -> str:
        raise NotImplementedError

    def verify_password(self, plain_password: str, password_hash: str) -> bool:
        raise NotImplementedError
