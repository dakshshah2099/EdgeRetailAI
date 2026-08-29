from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt
import onnxruntime as ort  # type: ignore[import-untyped] # onnxruntime lacks official py.typed marker


@dataclass(frozen=True)
class RawDetection:
    """Raw detection output from an inference backend before tracking."""

    class_id: int
    confidence: float
    bbox: tuple[int, int, int, int]  # (x, y, w, h)


class InferenceBackend(ABC):
    """Swap point: ONNXBackend today, TensorRTBackend later — same model
    file, same call signature. This is the seam the Jetson-substitution
    pitch depends on; keep it thin and backend-agnostic."""

    @abstractmethod
    def infer(self, frame: npt.NDArray[np.uint8]) -> list[RawDetection]:
        """Run the detection model on one frame, return raw (unfiltered,
        untracked) detections."""
        ...


class ONNXBackend(InferenceBackend):
    """ONNX Runtime implementation of InferenceBackend for YOLO26 models."""

    def __init__(
        self,
        model_path: str | Path,
        conf_threshold: float = 0.4,
        input_size: tuple[int, int] = (640, 640),
    ) -> None:
        path_str = str(model_path)
        if not Path(path_str).is_file():
            raise FileNotFoundError(f"Model file not found: {path_str}")

        self.conf_threshold = conf_threshold
        self.input_size = input_size

        session_options = ort.SessionOptions()
        session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(
            path_str,
            sess_options=session_options,
            providers=["CPUExecutionProvider"],
        )
        self.input_name: str = str(self.session.get_inputs()[0].name)

    def _letterbox(
        self, frame: npt.NDArray[np.uint8]
    ) -> tuple[npt.NDArray[np.float32], float, tuple[float, float]]:
        """Resize and pad image while meeting stride-multiple constraints."""
        h_orig, w_orig = frame.shape[:2]
        target_w, target_h = self.input_size

        scale = min(target_w / w_orig, target_h / h_orig)
        new_unpad = (int(round(w_orig * scale)), int(round(h_orig * scale)))
        dw = (target_w - new_unpad[0]) / 2.0
        dh = (target_h - new_unpad[1]) / 2.0

        if (w_orig, h_orig) != new_unpad:
            resized: npt.NDArray[np.uint8] = np.asarray(
                cv2.resize(frame, new_unpad, interpolation=cv2.INTER_LINEAR),
                dtype=np.uint8,
            )
        else:
            resized = frame

        top = int(round(dh - 0.1))
        bottom = int(round(dh + 0.1))
        left = int(round(dw - 0.1))
        right = int(round(dw + 0.1))

        padded: npt.NDArray[np.uint8] = np.asarray(
            cv2.copyMakeBorder(
                resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114)
            ),
            dtype=np.uint8,
        )

        rgb: npt.NDArray[np.uint8] = np.asarray(
            cv2.cvtColor(padded, cv2.COLOR_BGR2RGB),
            dtype=np.uint8,
        )
        blob: npt.NDArray[np.float32] = (rgb.astype(np.float32) / 255.0).transpose(2, 0, 1)
        blob = np.expand_dims(blob, axis=0)

        return blob, scale, (float(left), float(top))

    def _parse_yolo26_output(
        self,
        output: npt.NDArray[np.float32],
        scale: float,
        pad: tuple[float, float],
        img_shape: tuple[int, int],
    ) -> list[RawDetection]:
        """Parse YOLO26 NMS-free end-to-end output shaped (1, N, 6)."""
        w_orig, h_orig = img_shape
        pad_x, pad_y = pad
        detections: list[RawDetection] = []

        raw_boxes = output[0]  # (N, 6): [x1, y1, x2, y2, score, class_id]
        if raw_boxes.ndim != 2 or raw_boxes.shape[1] < 6:
            return detections

        mask = raw_boxes[:, 4] >= self.conf_threshold
        filtered_boxes = raw_boxes[mask]

        for row in filtered_boxes:
            x1, y1, x2, y2, score, class_id = row[:6]

            # Unpad and scale back to original resolution
            orig_x1 = (float(x1) - pad_x) / scale
            orig_y1 = (float(y1) - pad_y) / scale
            orig_x2 = (float(x2) - pad_x) / scale
            orig_y2 = (float(y2) - pad_y) / scale

            # Clip to image boundaries
            orig_x1 = max(0.0, min(float(w_orig), orig_x1))
            orig_y1 = max(0.0, min(float(h_orig), orig_y1))
            orig_x2 = max(0.0, min(float(w_orig), orig_x2))
            orig_y2 = max(0.0, min(float(h_orig), orig_y2))

            bx = int(round(orig_x1))
            by = int(round(orig_y1))
            bw = max(0, int(round(orig_x2 - orig_x1)))
            bh = max(0, int(round(orig_y2 - orig_y1)))

            detections.append(
                RawDetection(
                    class_id=int(round(float(class_id))),
                    confidence=float(score),
                    bbox=(bx, by, bw, bh),
                )
            )

        return detections

    def infer(self, frame: npt.NDArray[np.uint8]) -> list[RawDetection]:
        """Run the ONNX detection model on one frame, return raw detections."""
        if frame is None or frame.size == 0:
            return []

        h_orig, w_orig = frame.shape[:2]
        blob, scale, pad = self._letterbox(frame)

        outputs: list[npt.NDArray[np.float32]] = self.session.run(
            None, {self.input_name: blob}
        )
        if not outputs:
            return []

        out = outputs[0]
        # YOLO26 output shape: (1, 300, 6) or (1, N, 6)
        if out.ndim == 3 and out.shape[2] == 6:
            return self._parse_yolo26_output(out, scale, pad, (w_orig, h_orig))

        return []
