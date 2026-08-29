from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from detection.inference_backend import RawDetection


@dataclass(frozen=True)
class TrackedDetection:
    """Detection with an assigned anonymous track ID."""

    track_id: str
    bbox: tuple[int, int, int, int]  # (x, y, w, h)
    confidence: float
    class_id: int = 0


def _compute_iou(
    box1: tuple[int, int, int, int],
    box2: tuple[int, int, int, int],
) -> float:
    """Compute Intersection-over-Union (IoU) between two (x, y, w, h) boxes."""
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2

    if w1 <= 0 or h1 <= 0 or w2 <= 0 or h2 <= 0:
        return 0.0

    xa1, ya1, xa2, ya2 = x1, y1, x1 + w1, y1 + h1
    xb1, yb1, xb2, yb2 = x2, y2, x2 + w2, y2 + h2

    inter_x1 = max(xa1, xb1)
    inter_y1 = max(ya1, yb1)
    inter_x2 = min(xa2, xb2)
    inter_y2 = min(ya2, yb2)

    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area1 = w1 * h1
    area2 = w2 * h2
    union_area = area1 + area2 - inter_area

    if union_area <= 0:
        return 0.0

    return float(inter_area / union_area)


def _linear_assignment(
    cost_matrix: npt.NDArray[np.float32],
    threshold: float,
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """Greedy bipartite matching for bounding box association based on cost."""
    if cost_matrix.size == 0:
        return (
            [],
            list(range(cost_matrix.shape[0])),
            list(range(cost_matrix.shape[1])),
        )

    matched_indices: list[tuple[int, int]] = []
    unmatched_a = set(range(cost_matrix.shape[0]))
    unmatched_b = set(range(cost_matrix.shape[1]))

    # Flatten and sort pairs by lowest cost
    rows, cols = cost_matrix.shape
    pairs = []
    for r in range(rows):
        for c in range(cols):
            pairs.append((cost_matrix[r, c], r, c))
    pairs.sort(key=lambda x: x[0])

    for cost, r, c in pairs:
        if r in unmatched_a and c in unmatched_b and cost <= threshold:
            matched_indices.append((r, c))
            unmatched_a.remove(r)
            unmatched_b.remove(c)

    return matched_indices, sorted(unmatched_a), sorted(unmatched_b)


class _Track:
    """Internal track state representing an anonymous target."""

    def __init__(
        self,
        track_id: str,
        bbox: tuple[int, int, int, int],
        confidence: float,
        class_id: int = 0,
        min_hits: int = 1,
    ) -> None:
        self.track_id = track_id
        self.bbox = bbox
        self.confidence = confidence
        self.class_id = class_id
        self.hits = 1
        self.age = 1
        self.time_since_update = 0
        self.min_hits = min_hits
        self.is_activated = (min_hits <= 1)

    def predict(self) -> None:
        """Advance track state by one frame without detection."""
        self.age += 1
        self.time_since_update += 1

    def update(self, bbox: tuple[int, int, int, int], confidence: float) -> None:
        """Update track with newly matched detection."""
        self.bbox = bbox
        self.confidence = confidence
        self.hits += 1
        self.time_since_update = 0
        if self.hits >= self.min_hits:
            self.is_activated = True


class Tracker:
    """ByteTrack-style multi-object tracker assigning stable anonymous IDs.

    Uses two-stage association (high-confidence and low-confidence detections)
    with IoU distance to maintain stable tracks during occlusions and low-contrast
    conditions without heavy dependencies.
    """

    def __init__(
        self,
        max_age: int = 30,
        min_hits: int = 1,
        iou_threshold: float = 0.5,
        high_conf_threshold: float = 0.5,
        low_conf_threshold: float = 0.1,
    ) -> None:
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        self.high_conf_threshold = high_conf_threshold
        self.low_conf_threshold = low_conf_threshold

        self._next_id: int = 1
        self.tracks: list[_Track] = []

    def reset(self) -> None:
        """Reset all tracking states and ID counter."""
        self._next_id = 1
        self.tracks.clear()

    def update(self, detections: list[RawDetection]) -> list[TrackedDetection]:
        """Update tracks with detections from current frame."""
        for track in self.tracks:
            track.predict()

        # Split detections by confidence (ByteTrack principle)
        dets_high = [d for d in detections if d.confidence >= self.high_conf_threshold]
        dets_low = [
            d for d in detections
            if self.low_conf_threshold <= d.confidence < self.high_conf_threshold
        ]

        # Stage 1: Match active tracks with high-confidence detections
        cost_matrix_high = np.zeros((len(self.tracks), len(dets_high)), dtype=np.float32)
        for i, track in enumerate(self.tracks):
            for j, det in enumerate(dets_high):
                iou = _compute_iou(track.bbox, det.bbox)
                cost_matrix_high[i, j] = 1.0 - iou

        matches_1, unmatched_tracks_1, unmatched_dets_high = _linear_assignment(
            cost_matrix_high, threshold=1.0 - self.iou_threshold
        )

        for track_idx, det_idx in matches_1:
            det = dets_high[det_idx]
            self.tracks[track_idx].update(det.bbox, det.confidence)

        # Stage 2: Match remaining tracks with low-confidence detections
        remaining_track_indices = unmatched_tracks_1
        if remaining_track_indices and dets_low:
            cost_matrix_low = np.zeros(
                (len(remaining_track_indices), len(dets_low)), dtype=np.float32
            )
            for i, track_idx in enumerate(remaining_track_indices):
                track = self.tracks[track_idx]
                for j, det in enumerate(dets_low):
                    iou = _compute_iou(track.bbox, det.bbox)
                    cost_matrix_low[i, j] = 1.0 - iou

            matches_2, unmatched_tracks_2_rel, _ = _linear_assignment(
                cost_matrix_low, threshold=1.0 - self.iou_threshold
            )

            for rel_track_idx, det_idx in matches_2:
                track_idx = remaining_track_indices[rel_track_idx]
                det = dets_low[det_idx]
                self.tracks[track_idx].update(det.bbox, det.confidence)

        # Stage 3: Initialize new tracks from unmatched high-confidence detections
        for det_idx in unmatched_dets_high:
            det = dets_high[det_idx]
            track_id = str(self._next_id)
            self._next_id += 1
            new_track = _Track(
                track_id=track_id,
                bbox=det.bbox,
                confidence=det.confidence,
                class_id=det.class_id,
                min_hits=self.min_hits,
            )
            self.tracks.append(new_track)

        # Remove dead tracks
        self.tracks = [
            t for t in self.tracks
            if t.time_since_update <= self.max_age
        ]

        # Return currently active detections updated in this frame
        active_outputs: list[TrackedDetection] = []
        for track in self.tracks:
            if track.time_since_update == 0 and track.is_activated:
                active_outputs.append(
                    TrackedDetection(
                        track_id=track.track_id,
                        bbox=track.bbox,
                        confidence=track.confidence,
                        class_id=track.class_id,
                    )
                )

        return active_outputs
