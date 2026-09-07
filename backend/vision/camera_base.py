from abc import ABC, abstractmethod
from typing import Self

import numpy as np
import numpy.typing as npt
from core.schemas import Frame


class CameraSource(ABC):
    """Abstract camera input. Any implementation must yield (Frame, ndarray)
    pairs. The ndarray is the raw BGR pixel buffer — it is NEVER wrapped in
    or attached to a Pydantic model, and must never be passed to anything
    in storage/ (Slice 7) or logged."""

    @abstractmethod
    def get_frame(self) -> tuple[Frame, npt.NDArray[np.uint8]] | None:
        """Return the next available frame, or None if the stream is
        temporarily unavailable (caller decides retry policy)."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Release the underlying capture resource."""
        ...

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()
