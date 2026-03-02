class AuthError(Exception):
    """Base auth error."""


class EmailAlreadyExistsError(AuthError):
    """Email already exists."""


class InvalidCredentialsError(AuthError):
    """Invalid email or password."""


class InvalidTokenError(AuthError):
    """Invalid or expired token."""


class UserNotFoundError(AuthError):
    """User not found."""
