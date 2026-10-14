from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from jobpilot.api.routes.health import router as health_router
from jobpilot.api.routes.library import router as library_router
from jobpilot.api.routes.resumes import router as resumes_router
from jobpilot.core.config import get_settings


def create_app() -> FastAPI:
    app = FastAPI(title="JobPilot AI API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )
    app.include_router(health_router)
    app.include_router(resumes_router)
    app.include_router(library_router)
    return app


app = create_app()
