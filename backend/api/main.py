from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from api.routes.alerts import router as alerts_router
from api.routes.heatmap import router as heatmap_router
from api.routes.kpi import router as kpi_router
from api.routes.system import router as system_router
from api.routes.video import router as video_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    from api.stream_manager import stream_manager

    stream_manager.stop()


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
        lifespan=lifespan,
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
    dist_dir = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if not dist_dir.is_dir():
        dist_dir = Path(__file__).resolve().parent.parent.parent / "dashboard" / "dist"

    if dist_dir.is_dir():
        application.mount(
            "/app", StaticFiles(directory=str(dist_dir), html=True), name="static_dashboard"
        )
        assets_dir = dist_dir / "assets"
        if assets_dir.is_dir():
            application.mount(
                "/assets", StaticFiles(directory=str(assets_dir)), name="static_assets"
            )

    @application.get("/", tags=["system"])
    def root() -> Response:
        index_file = dist_dir / "index.html"
        if index_file.is_file():
            return RedirectResponse(url="/app/")
        return JSONResponse(
            content={
                "status": "ok",
                "name": "Intelligent Retail Analytics API",
                "docs": "/docs",
                "health": "/health",
            }
        )

    return application


app = create_app()

if __name__ == "__main__":
    import os

    import uvicorn

    from api.env_manager import read_env_file

    env = read_env_file()
    srv_host = env.get("HOST") or env.get("API_HOST") or os.environ.get("HOST", "0.0.0.0")
    srv_port = int(env.get("PORT") or env.get("API_PORT") or os.environ.get("PORT", "8000"))
    uvicorn.run("api.main:app", host=srv_host, port=srv_port, reload=True)

