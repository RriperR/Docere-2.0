from fastapi import FastAPI

from app.presentation.api.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title='Docere Service')
    app.include_router(health_router, prefix='/api')
    return app


app = create_app()
