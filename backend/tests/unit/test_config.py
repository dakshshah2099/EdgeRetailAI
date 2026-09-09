from pathlib import Path

import pytest
from pydantic import ValidationError

from core.schemas import AppConfig, load_config


def test_load_valid_config(tmp_path: Path) -> None:
    config_content = """
camera:
  source: "rtsp://192.168.1.100:8080/h264_pcm.sdp"

zones:
  - zone_id: "zone_entrance"
    zone_type: "entry_exit"
    polygon:
      - [0, 0]
      - [200, 0]
      - [200, 300]
      - [0, 300]
    label: "Main Entrance"

low_stock_confidence_threshold: 0.6
queue_congestion_length: 4
"""
    config_file = tmp_path / "valid_config.yaml"
    config_file.write_text(config_content, encoding="utf-8")

    cfg = load_config(str(config_file))
    assert isinstance(cfg, AppConfig)
    assert cfg.camera.source == "rtsp://192.168.1.100:8080/h264_pcm.sdp"
    assert len(cfg.zones) == 1
    assert cfg.zones[0].zone_id == "zone_entrance"
    assert cfg.low_stock_confidence_threshold == 0.6
    assert cfg.queue_congestion_length == 4


def test_load_repo_default_config() -> None:
    repo_config_path = Path("config.yaml")
    if repo_config_path.exists():
        cfg = load_config(str(repo_config_path))
        assert isinstance(cfg, AppConfig)
        assert cfg.camera.source.startswith("rtsp://")
        assert cfg.low_stock_confidence_threshold >= 0.0
        assert cfg.queue_congestion_length >= 1


def test_load_config_missing_field(tmp_path: Path) -> None:
    # Missing required 'camera' field
    config_content = """
zones: []
low_stock_confidence_threshold: 0.6
queue_congestion_length: 4
"""
    config_file = tmp_path / "missing_camera.yaml"
    config_file.write_text(config_content, encoding="utf-8")

    with pytest.raises(ValidationError):
        load_config(str(config_file))


def test_load_config_invalid_threshold(tmp_path: Path) -> None:
    # low_stock_confidence_threshold > 1.0
    config_content = """
camera:
  source: "rtsp://192.168.1.100:8080/h264_pcm.sdp"
zones: []
low_stock_confidence_threshold: 1.5
queue_congestion_length: 4
"""
    config_file = tmp_path / "bad_threshold.yaml"
    config_file.write_text(config_content, encoding="utf-8")

    with pytest.raises(ValidationError):
        load_config(str(config_file))


def test_load_config_file_not_found(tmp_path: Path) -> None:
    non_existent = tmp_path / "does_not_exist.yaml"
    with pytest.raises(FileNotFoundError):
        load_config(str(non_existent))


def test_load_config_non_dict(tmp_path: Path) -> None:
    config_file = tmp_path / "not_a_dict.yaml"
    config_file.write_text("- item1\n- item2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must contain a YAML mapping"):
        load_config(str(config_file))
