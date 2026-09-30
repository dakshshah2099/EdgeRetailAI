import numpy as np
import numpy.typing as npt

from vision.inference_backend import InferenceBackend, RawDetection

# COCO class 0 is 'person'
PERSON_CLASS_ID = 0


class PersonDetector:
    """YOLO person detector wrapper producing person-only bounding boxes."""

    def __init__(
        self,
        backend: InferenceBackend,
        target_class_id: int = PERSON_CLASS_ID,
    ) -> None:
        self.backend = backend
        self.target_class_id = target_class_id

    def detect(self, frame: npt.NDArray[np.uint8]) -> list[RawDetection]:
        """Run inference and return only person-class detections."""
        raw_detections = self.backend.infer(frame)
        return [d for d in raw_detections if d.class_id == self.target_class_id]


class RetailDetector:
    """Multi-class YOLO detector supporting person, cart, and retail product classes."""

    def __init__(
        self,
        backend: InferenceBackend,
        allowed_class_ids: set[int] | None = None,
    ) -> None:
        self.backend = backend
        self.allowed_class_ids = allowed_class_ids

    def detect(self, frame: npt.NDArray[np.uint8]) -> list[RawDetection]:
        """Run inference and return detections matching allowed classes (or all)."""
        raw_detections = self.backend.infer(frame)
        if self.allowed_class_ids is None:
            return raw_detections
        return [d for d in raw_detections if d.class_id in self.allowed_class_ids]
