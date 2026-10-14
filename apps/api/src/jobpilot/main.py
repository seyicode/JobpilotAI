from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from jobpilot.api.routes.health import router as health_router
from jobpilot.core.config import get_settings


def create_app() -> FastAPI:
    app = FastAPI(title="JobPilot AI API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["GET"],
        allow_headers=["Content-Type"],
    )
    app.include_router(health_router)
    return app


app = create_app()
