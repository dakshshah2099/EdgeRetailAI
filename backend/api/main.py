import contextlib
import os
import signal
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from api.routes.alerts import router as alerts_router
from api.routes.heatmap import router as heatmap_router
from api.routes.kpi import router as kpi_router
from api.routes.planogram import router as planogram_router
from api.routes.reports import router as reports_router
from api.routes.staff import router as staff_router
from api.routes.system import router as system_router
from api.routes.video import router as video_router
from api.routes.ws import router as ws_router


def _install_signal_handlers() -> None:
    """Install signal handlers to stop stream_manager immediately on SIGINT/SIGTERM."""
    from api.stream_manager import stream_manager

    def _on_signal(signum: int, frame: Any) -> None:
        stream_manager.stop()
        orig = _orig_handlers.get(signum)
        if callable(orig):
            orig(signum, frame)

    _orig_handlers: dict[int, Any] = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            prev = signal.getsignal(sig)
            _orig_handlers[sig] = prev
            signal.signal(sig, _on_signal)
        except (ValueError, OSError, AttributeError):
            pass


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from api.stream_manager import stream_manager

    _install_signal_handlers()

    from api.dependencies import get_app_config
    from vision.camera_mesh import camera_mesh

    with contextlib.suppress(Exception):
        cfg = get_app_config()
        if cfg and cfg.cameras:
            for c in cfg.cameras:
                camera_mesh.register_camera(
                    camera_id=c.camera_id,
                    source=c.source,
                    role=c.role,
                    label=c.label,
                )

    if "PYTEST_CURRENT_TEST" not in os.environ:
        with contextlib.suppress(Exception):
            stream_manager._ensure_workers_started()

    try:
        yield
    finally:
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
    application.include_router(planogram_router)
    application.include_router(staff_router)
    application.include_router(reports_router)
    application.include_router(alerts_router)
    application.include_router(heatmap_router)
    application.include_router(system_router)
    application.include_router(video_router)
    application.include_router(ws_router)

    @application.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    # Mount central multi-store monitoring dashboard at /central
    if os.environ.get("ENABLE_CENTRAL_DASHBOARD", "true").lower() == "true":
        from central.central_dashboard import HTML_TEMPLATE, create_central_app

        application.mount("/central", create_central_app())

        @application.get("/central", response_class=HTMLResponse, tags=["central"])
        @application.get("/central/", response_class=HTMLResponse, tags=["central"])
        async def central_dashboard_view() -> HTMLResponse:
            return HTMLResponse(HTML_TEMPLATE)

    # If static frontend build is present, serve it via app.frontend()
    frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
    dist_dir = frontend_dir / "dist"
    if not dist_dir.is_dir():
        dist_dir = Path(__file__).resolve().parent.parent.parent / "dashboard" / "dist"

    if dist_dir.is_dir():
        application.frontend("/app", directory=dist_dir)
        application.frontend("/frontend", directory=dist_dir)
        assets_dir = dist_dir / "assets"
        if assets_dir.is_dir():
            application.frontend("/assets", directory=assets_dir)

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
