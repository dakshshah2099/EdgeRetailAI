"""Computer vision module: cameras, inference, detection, and tracking."""

from vision.camera_base import CameraSource
from vision.detector import (
    CART_CLASS_ID,
    DEFAULT_COCO_RETAIL_CLASS_MAP,
    OPEN_RETAIL_CLASS_MAP,
    PERSON_CLASS_ID,
    PRODUCT_CLASS_ID,
    DetectionDiagnostics,
    PersonDetector,
    YOLODetector,
)
from vision.inference_backend import InferenceBackend, ONNXBackend, RawDetection
from vision.rtsp_source import RTSPSource, format_authenticated_rtsp_url, mask_rtsp_credentials
from vision.tracker import TrackedDetection, Tracker
from vision.usb_source import USBSource

__all__ = [
    "CART_CLASS_ID",
    "CameraSource",
    "DEFAULT_COCO_RETAIL_CLASS_MAP",
    "DetectionDiagnostics",
    "InferenceBackend",
    "ONNXBackend",
    "OPEN_RETAIL_CLASS_MAP",
    "PERSON_CLASS_ID",
    "PRODUCT_CLASS_ID",
    "PersonDetector",
    "RTSPSource",
    "RawDetection",
    "TrackedDetection",
    "Tracker",
    "USBSource",
    "YOLODetector",
    "format_authenticated_rtsp_url",
    "mask_rtsp_credentials",
]
