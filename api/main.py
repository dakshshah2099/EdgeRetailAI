from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes.alerts import router as alerts_router
from api.routes.heatmap import router as heatmap_router
from api.routes.kpi import router as kpi_router
from api.routes.system import router as system_router
from api.routes.video import router as video_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    desc = (
        "Edge-AI retail analytics API for footfall, queues, stock, alerts, "
        "heatmap visualization, and live video streaming."
    )
    application = FastAPI(
        title="Intelligent Retail Analytics API",
        description=desc,
        version="0.1.0",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(kpi_router)
    application.include_router(alerts_router)
    application.include_router(heatmap_router)
    application.include_router(system_router)
    application.include_router(video_router)

    @application.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    # If static frontend build is present, mount it
    dist_dir = Path(__file__).resolve().parent.parent / "dashboard" / "dist"
    if dist_dir.is_dir():
        application.mount(
            "/app", StaticFiles(directory=str(dist_dir), html=True), name="static_dashboard"
        )

    @application.get("/", tags=["system"])
    def root() -> dict[str, str]:
        return {
            "status": "ok",
            "name": "Intelligent Retail Analytics API",
            "docs": "/docs",
            "health": "/health",
        }

    return application


app = create_app()
