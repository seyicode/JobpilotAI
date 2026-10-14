from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from jobpilot.api.routes.applications import router as applications_router
from jobpilot.api.routes.health import router as health_router
from jobpilot.api.routes.jobs import router as jobs_router
from jobpilot.api.routes.library import router as library_router
from jobpilot.api.routes.preferences import router as preferences_router
from jobpilot.api.routes.profile import router as profile_router
from jobpilot.api.routes.resumes import router as resumes_router
from jobpilot.api.routes.sources import router as sources_router
from jobpilot.api.routes.tailored import router as tailored_router
from jobpilot.core.config import get_settings
from jobpilot.services.matching import validate_weights


def create_app() -> FastAPI:
    validate_weights(get_settings().match_weights)  # Fail at startup on a bad MATCH_WEIGHTS
    app = FastAPI(title="JobPilot AI API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )
    app.include_router(health_router)
    app.include_router(resumes_router)
    app.include_router(library_router)
    app.include_router(preferences_router)
    app.include_router(jobs_router)
    app.include_router(profile_router)
    app.include_router(tailored_router)
    app.include_router(sources_router)
    app.include_router(applications_router)
    return app


app = create_app()
