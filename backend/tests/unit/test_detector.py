from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt
import pytest
from vision.detector import PERSON_CLASS_ID, PersonDetector
from vision.inference_backend import ONNXBackend, RawDetection

MODEL_PATH = Path(__file__).resolve().parent.parent.parent / "models" / "yolo26n.onnx"
BUS_IMAGE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "bus.jpg"


def test_model_file_exists() -> None:
    assert MODEL_PATH.is_file(), f"Model file not found at {MODEL_PATH}"


def test_onnx_backend_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        ONNXBackend("models/non_existent_model.onnx")


def test_raw_detection_has_no_pii_or_pixels() -> None:
    det = RawDetection(class_id=0, confidence=0.9, bbox=(10, 20, 30, 40))
    assert hasattr(det, "class_id")
    assert hasattr(det, "confidence")
    assert hasattr(det, "bbox")
    assert not hasattr(det, "pixels")
    assert not hasattr(det, "image")
    assert not hasattr(det, "crop")
    assert not hasattr(det, "embedding")


@pytest.mark.skipif(not MODEL_PATH.is_file(), reason="ONNX model not present")
def test_onnx_backend_infer_bus_image() -> None:
    assert BUS_IMAGE_PATH.is_file(), f"Test fixture image missing at {BUS_IMAGE_PATH}"
    raw_img = cv2.imread(str(BUS_IMAGE_PATH))
    assert raw_img is not None
    img: npt.NDArray[np.uint8] = np.asarray(raw_img, dtype=np.uint8)

    backend = ONNXBackend(MODEL_PATH, conf_threshold=0.4)
    raw_detections = backend.infer(img)

    # bus.jpg has 4 people and 1 bus
    person_detections = [d for d in raw_detections if d.class_id == PERSON_CLASS_ID]
    non_person_detections = [d for d in raw_detections if d.class_id != PERSON_CLASS_ID]

    assert len(person_detections) == 4, f"Expected 4 persons, got {len(person_detections)}"
    assert len(non_person_detections) >= 1, "Expected at least 1 non-person detection (the bus)"

    # Verify bounding boxes are within image bounds
    h, w = img.shape[:2]
    for d in raw_detections:
        x, y, bw, bh = d.bbox
        assert 0 <= x < w
        assert 0 <= y < h
        assert bw > 0
        assert bh > 0
        assert x + bw <= w
        assert y + bh <= h
        assert 0.0 <= d.confidence <= 1.0


@pytest.mark.skipif(not MODEL_PATH.is_file(), reason="ONNX model not present")
def test_person_detector_filters_non_person_classes() -> None:
    raw_img = cv2.imread(str(BUS_IMAGE_PATH))
    assert raw_img is not None
    img: npt.NDArray[np.uint8] = np.asarray(raw_img, dtype=np.uint8)

    backend = ONNXBackend(MODEL_PATH, conf_threshold=0.4)
    detector = PersonDetector(backend)
    person_only_detections = detector.detect(img)

    assert len(person_only_detections) == 4
    for d in person_only_detections:
        assert d.class_id == PERSON_CLASS_ID


@pytest.mark.skipif(not MODEL_PATH.is_file(), reason="ONNX model not present")
def test_onnx_backend_mismatched_input_size_raises_value_error() -> None:
    with pytest.raises(ValueError, match="does not match model static"):
        ONNXBackend(MODEL_PATH, input_size=(512, 512))

