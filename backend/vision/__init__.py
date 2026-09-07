"""Computer vision module: cameras, inference, detection, and tracking."""

from vision.camera_base import CameraSource
from vision.detector import PersonDetector
from vision.inference_backend import InferenceBackend, ONNXBackend, RawDetection
from vision.rtsp_source import RTSPSource, format_authenticated_rtsp_url, mask_rtsp_credentials
from vision.tracker import TrackedDetection, Tracker
from vision.usb_source import USBSource

__all__ = [
    "CameraSource",
    "InferenceBackend",
    "ONNXBackend",
    "PersonDetector",
    "RTSPSource",
    "RawDetection",
    "TrackedDetection",
    "Tracker",
    "USBSource",
    "format_authenticated_rtsp_url",
    "mask_rtsp_credentials",
]
