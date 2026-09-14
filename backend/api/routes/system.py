import os
from typing import Annotated, Any

import yaml
from fastapi import APIRouter, Header, HTTPException, Response, status

from api.dependencies import AppConfigDep, ConfigPathDep, RequireDebugModeDep
from api.env_manager import is_debug_mode, read_env_file, write_env_file
from api.schemas_api import SystemEnvResponse, UpdateEnvRequest, UpdateZonesRequest
from api.stream_manager import scale_zones_to_frame
from core.schemas import ZoneConfig

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/env")
def get_system_environment() -> SystemEnvResponse:
    """Return all system environment variables and active debug mode status."""
    env_vars = read_env_file()
    debug = is_debug_mode()
    return SystemEnvResponse(debug_mode=debug, variables=env_vars)


@router.put("/env")
def update_system_environment(
    req: UpdateEnvRequest,
) -> SystemEnvResponse:
    """Update system .env variables without requiring debug mode."""
    updated_vars = write_env_file(req.variables)
    return SystemEnvResponse(
        debug_mode=is_debug_mode(),
        variables=updated_vars,
    )


@router.post("/toggle-debug")
def toggle_debug_mode(
    x_debug_token: Annotated[str | None, Header(alias="X-Debug-Token")] = None,
) -> SystemEnvResponse:
    """Toggle DEBUG_MODE boolean flag in .env.

    Enabling debug mode requires authentication via the X-Debug-Token header
    matching DEBUG_TOKEN in the environment (or default local debug secret)
    to prevent unauthorized privilege escalation. Disabling debug mode is
    permitted if debug mode is already active.
    """
    current_debug = is_debug_mode()
    new_debug = not current_debug

    if new_debug:
        # SECURITY NOTE: The hardcoded fallback below ("retail-edge-debug-secret") is NOT a real
        # authentication mechanism. It is solely an edge-POC barrier to prevent accidental clicks
        # during local demo usage. Anyone with source access knows it. Production deployments
        # must set a cryptographically secure token in the DEBUG_TOKEN environment variable.
        expected_token = os.environ.get(
            "DEBUG_TOKEN", read_env_file().get("DEBUG_TOKEN", "retail-edge-debug-secret")
        )
        if not x_debug_token or x_debug_token != expected_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Debug mode is disabled. Valid X-Debug-Token header required to enable.",
            )

    updated_vars = write_env_file({"DEBUG_MODE": "true" if new_debug else "false"})
    return SystemEnvResponse(
        debug_mode=new_debug,
        variables=updated_vars,
    )


@router.get("/zones")
def get_system_zones(
    cfg: AppConfigDep,
    response: Response,
    frame_w: int | None = None,
    frame_h: int | None = None,
) -> list[ZoneConfig]:
    """Return currently configured spatial ROI and detection zones.

    If frame_w and frame_h are provided, coordinates are proportionally scaled
    from calibration reference resolution to the requested frame dimensions.
    """
    raw_zones = cfg.zones if cfg and cfg.zones else []
    base_w = cfg.calibration_width if cfg else 640
    base_h = cfg.calibration_height if cfg else 480

    if frame_w is not None and frame_h is not None and frame_w > 0 and frame_h > 0:
        scaled = scale_zones_to_frame(raw_zones, frame_w, frame_h, base_w=base_w, base_h=base_h)
        response.headers["X-Calibration-Width"] = str(frame_w)
        response.headers["X-Calibration-Height"] = str(frame_h)
        return scaled

    response.headers["X-Calibration-Width"] = str(base_w)
    response.headers["X-Calibration-Height"] = str(base_h)
    return raw_zones


@router.put("/zones")
def update_system_zones(
    req: UpdateZonesRequest,
    cfg_path: ConfigPathDep,
    response: Response,
    _: RequireDebugModeDep,
) -> list[ZoneConfig]:
    """Save modified zone polygons directly into config.yaml."""
    raw_cfg: dict[str, Any] = {}

    if cfg_path.is_file():
        with cfg_path.open("r", encoding="utf-8") as f:
            raw_cfg = yaml.safe_load(f) or {}

    raw_cfg["zones"] = [
        {
            "zone_id": z.zone_id,
            "zone_type": z.zone_type,
            "polygon": [list(pt) for pt in z.polygon],
            "label": z.label,
        }
        for z in req.zones
    ]

    cal_w = req.calibration_width or raw_cfg.get("calibration_width", 640)
    cal_h = req.calibration_height or raw_cfg.get("calibration_height", 480)
    raw_cfg["calibration_width"] = cal_w
    raw_cfg["calibration_height"] = cal_h

    with cfg_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(raw_cfg, f, default_flow_style=False, sort_keys=False)

    response.headers["X-Calibration-Width"] = str(cal_w)
    response.headers["X-Calibration-Height"] = str(cal_h)
    return req.zones
