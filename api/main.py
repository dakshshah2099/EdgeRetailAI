from fastapi import FastAPI

from api.routes.alerts import router as alerts_router
from api.routes.heatmap import router as heatmap_router
from api.routes.kpi import router as kpi_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    desc = (
        "Edge-AI retail analytics API for footfall, queues, stock, alerts, "
        "and heatmap visualization."
    )
    application = FastAPI(
        title="Intelligent Retail Analytics API",
        description=desc,
        version="0.1.0",
    )

    application.include_router(kpi_router)
    application.include_router(alerts_router)
    application.include_router(heatmap_router)

    @application.get("/", tags=["system"])
    def root() -> dict[str, str]:
        return {
            "status": "ok",
            "name": "Intelligent Retail Analytics API",
            "docs": "/docs",
            "health": "/health",
        }

    @application.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
