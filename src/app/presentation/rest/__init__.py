"""REST-endpoint-ы presentation-слоя."""

from app.presentation.rest.public.v1.router import router as public_v1_router
from app.presentation.rest.system.router import router as system_router

__all__ = ['public_v1_router', 'system_router']
