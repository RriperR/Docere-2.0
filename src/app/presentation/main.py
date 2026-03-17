"""Точка входа FastAPI-приложения."""

from app.presentation.webserver.app_factory import app, create_app

__all__ = ['app', 'create_app']
