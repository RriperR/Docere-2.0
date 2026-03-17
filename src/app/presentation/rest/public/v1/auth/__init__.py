"""Публичные auth-endpoint-ы версии v1."""

from app.presentation.rest.public.v1.auth.router import router as auth_router

__all__ = ['auth_router']
