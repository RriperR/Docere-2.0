from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuthToken:
    access_token: str
    token_type: str = 'bearer'  # noqa: S105
