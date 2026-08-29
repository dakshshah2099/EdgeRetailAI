from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from camera.base import CameraSource
from camera.rtsp_source import RTSPSource
from camera.usb_source import USBSource
from schemas import Frame


@pytest.fixture(scope="session")
def sample_video_path(tmp_path_factory: pytest.TempPathFactory) -> str:
    fixtures_dir = Path("tests/fixtures")
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    video_path = fixtures_dir / "sample_video.mp4"

    if not video_path.exists():
        fourcc = cv2.VideoWriter.fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(video_path), fourcc, 10.0, (320, 240))
        for i in range(5):
            # Create a 320x240 synthetic frame with varying intensity
            frame = np.full((240, 320, 3), fill_value=(i * 40) % 255, dtype=np.uint8)
            writer.write(frame)
        writer.release()

    return str(video_path)


def test_usb_source_with_sample_video(sample_video_path: str) -> None:
    source = USBSource(device_index=sample_video_path, source_id="test_video_source")
    frames_read = 0

    while True:
        result = source.get_frame()
        if result is None:
            break

        meta, raw_frame = result
        assert isinstance(meta, Frame)
        assert meta.source_id == "test_video_source"
        assert meta.width == 320
        assert meta.height == 240
        assert isinstance(meta.timestamp, datetime)
        assert meta.timestamp.tzinfo == UTC

        assert isinstance(raw_frame, np.ndarray)
        assert raw_frame.shape == (240, 320, 3)
        assert raw_frame.dtype == np.uint8

        frames_read += 1

    assert frames_read == 5
    source.close()


def test_usb_source_failed_open() -> None:
    with patch("cv2.VideoCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_cap_cls.return_value = mock_cap

        source = USBSource(device_index=999, source_id="bad_usb")
        result = source.get_frame()
        assert result is None
        source.close()
        mock_cap.release.assert_called_once()


def test_usb_source_failed_read() -> None:
    with patch("cv2.VideoCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (False, None)
        mock_cap_cls.return_value = mock_cap

        source = USBSource(device_index=0, source_id="usb_read_fail")
        result = source.get_frame()
        assert result is None
        source.close()
        mock_cap.release.assert_called_once()


def test_rtsp_source_unreachable_returns_none_and_reconnects() -> None:
    with (
        patch("cv2.VideoCapture") as mock_cap_cls,
        patch("time.sleep") as mock_sleep,
    ):
        mock_cap_fail = MagicMock()
        mock_cap_fail.isOpened.return_value = False
        mock_cap_cls.return_value = mock_cap_fail

        source = RTSPSource(
            source_url="rtsp://192.168.1.999:8080/nonexistent",
            source_id="unreachable_rtsp",
            initial_backoff_sec=1.0,
            max_backoff_sec=10.0,
        )

        result = source.get_frame()
        assert result is None
        assert mock_cap_cls.call_count >= 1
        mock_cap_cls.assert_called_with("rtsp://192.168.1.999:8080/nonexistent", cv2.CAP_FFMPEG)
        mock_cap_fail.set.assert_any_call(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
        mock_cap_fail.set.assert_any_call(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)

        result_2 = source.get_frame()
        assert result_2 is None
        assert mock_cap_cls.call_count >= 2
        mock_sleep.assert_called()

        source.close()


def test_rtsp_source_backoff_is_capped() -> None:
    sleep_calls: list[float] = []

    def mock_sleep_record(duration: float) -> None:
        sleep_calls.append(duration)

    with (
        patch("cv2.VideoCapture") as mock_cap_cls,
        patch("time.sleep", side_effect=mock_sleep_record),
    ):
        mock_cap_fail = MagicMock()
        mock_cap_fail.isOpened.return_value = True
        mock_cap_fail.read.return_value = (False, None)
        mock_cap_cls.return_value = mock_cap_fail

        source = RTSPSource(
            source_url="rtsp://192.168.1.100:8080/live",
            source_id="rtsp_cam",
            initial_backoff_sec=1.0,
            max_backoff_sec=10.0,
            backoff_factor=2.0,
        )

        # Trigger 6 consecutive failed reads
        for _ in range(6):
            res = source.get_frame()
            assert res is None

        # Verify backoff sequence: 1.0, 2.0, 4.0, 8.0, 10.0 (capped), 10.0 (capped)
        assert len(sleep_calls) >= 6
        expected_backoffs = [1.0, 2.0, 4.0, 8.0, 10.0, 10.0]
        for actual, expected in zip(sleep_calls[:6], expected_backoffs, strict=False):
            assert actual == pytest.approx(expected)

        # All sleep calls must be <= max_backoff_sec (10.0)
        assert all(call <= 10.0 for call in sleep_calls)
        source.close()


def test_rtsp_source_successful_read_resets_backoff() -> None:
    sleep_calls: list[float] = []

    def mock_sleep_record(duration: float) -> None:
        sleep_calls.append(duration)

    with (
        patch("cv2.VideoCapture") as mock_cap_cls,
        patch("time.sleep", side_effect=mock_sleep_record),
    ):
        mock_cap_1 = MagicMock()
        mock_cap_1.isOpened.return_value = True
        mock_cap_1.read.return_value = (False, None)  # Fail read

        mock_cap_2 = MagicMock()
        mock_cap_2.isOpened.return_value = True
        mock_cap_2.read.return_value = (False, None)  # Fail read

        mock_cap_3 = MagicMock()
        mock_cap_3.isOpened.return_value = True
        sample_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap_3.read.side_effect = [(True, sample_frame), (False, None)]

        mock_cap_4 = MagicMock()
        mock_cap_4.isOpened.return_value = True
        mock_cap_4.read.return_value = (False, None)

        mock_cap_cls.side_effect = [mock_cap_1, mock_cap_2, mock_cap_3, mock_cap_4]

        source = RTSPSource(
            source_url="rtsp://192.168.1.100:8080/live",
            source_id="rtsp_cam",
            initial_backoff_sec=1.0,
            max_backoff_sec=10.0,
            backoff_factor=2.0,
        )

        # 1st read -> fail (sleeps 1.0)
        res1 = source.get_frame()
        assert res1 is None

        # 2nd read -> fail (sleeps 2.0)
        res2 = source.get_frame()
        assert res2 is None

        # 3rd read -> succeed (should reset backoff to 1.0)
        res3 = source.get_frame()
        assert res3 is not None
        meta, raw = res3
        assert meta.width == 640
        assert meta.height == 480

        # 4th read -> fail (should start at 1.0 again)
        res4 = source.get_frame()
        assert res4 is None

        assert sleep_calls[0] == 1.0
        assert sleep_calls[1] == 2.0
        assert sleep_calls[2] == 1.0
        source.close()


def test_camera_source_context_manager() -> None:
    with patch("cv2.VideoCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap_cls.return_value = mock_cap

        with USBSource(device_index=0, source_id="ctx_usb") as src:
            assert isinstance(src, CameraSource)

        mock_cap.release.assert_called_once()


def test_no_pixel_persistence() -> None:
    """Verify camera classes do not hold persistent image buffers as attributes."""
    for cls in (USBSource, RTSPSource):
        forbidden_attrs = {"image", "frame", "frame_data", "pixels", "raw_frame", "crop"}
        for attr in forbidden_attrs:
            assert attr not in cls.__dict__, (
                f"Camera class '{cls.__name__}' defines forbidden attribute '{attr}'"
            )
