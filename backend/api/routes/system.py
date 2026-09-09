import os
from typing import Any

import yaml
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from api.dependencies import get_app_config
from api.env_manager import is_debug_mode, read_env_file, write_env_file
from core.schemas import ZoneConfig

router = APIRouter(prefix="/system", tags=["system"])


class SystemEnvResponse(BaseModel):
    debug_mode: bool
    variables: dict[str, str] = Field(default_factory=dict)


class UpdateEnvRequest(BaseModel):
    variables: dict[str, str]


class UpdateZonesRequest(BaseModel):
    zones: list[ZoneConfig]


@router.get("/env", response_model=SystemEnvResponse)
def get_system_environment() -> SystemEnvResponse:
    """Return all system environment variables and active debug mode status."""
    env_vars = read_env_file()
    debug = is_debug_mode()
    return SystemEnvResponse(debug_mode=debug, variables=env_vars)


@router.put("/env", response_model=SystemEnvResponse)
def update_system_environment(req: UpdateEnvRequest) -> SystemEnvResponse:
    """Update system .env variables when in debug mode."""
    if not is_debug_mode():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debug mode is disabled. Cannot modify environment variables.",
        )

    updated_vars = write_env_file(req.variables)
    return SystemEnvResponse(
        debug_mode=is_debug_mode(),
        variables=updated_vars,
    )


@router.post("/toggle-debug", response_model=SystemEnvResponse)
def toggle_debug_mode(
    x_debug_token: str | None = Header(None, alias="X-Debug-Token"),
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


@router.get("/zones", response_model=list[ZoneConfig])
def get_system_zones() -> list[ZoneConfig]:
    """Return currently configured spatial ROI and detection zones."""
    cfg = get_app_config()
    if cfg and cfg.zones:
        return cfg.zones
    return []


@router.put("/zones", response_model=list[ZoneConfig])
def update_system_zones(req: UpdateZonesRequest) -> list[ZoneConfig]:
    """Save modified zone polygons directly into config.yaml."""
    if not is_debug_mode():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debug mode is disabled. Cannot modify zone layout.",
        )

    from api.dependencies import get_config_path

    cfg_path = get_config_path()
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

    with cfg_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(raw_cfg, f, default_flow_style=False, sort_keys=False)

    return req.zones
