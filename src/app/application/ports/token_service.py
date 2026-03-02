from __future__ import annotations

from uuid import UUID


class TokenServicePort:
    def create_access_token(self, user_id: UUID) -> str:
        raise NotImplementedError

    def decode_access_token(self, token: str) -> UUID:
        raise NotImplementedError
