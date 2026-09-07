"""Inference latency and throughput benchmarking module."""

import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Ensure backend root is on sys.path
_backend_root = str(Path(__file__).resolve().parent.parent)
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import numpy.typing as npt  # noqa: E402
from vision.inference_backend import InferenceBackend  # noqa: E402

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BenchmarkResult:
    """Statistical summary of an inference benchmark run."""

    model_name: str
    total_iterations: int
    warmup_iterations: int
    measured_iterations: int
    min_latency_ms: float
    max_latency_ms: float
    mean_latency_ms: float
    p95_latency_ms: float
    fps: float
    model_size_mb: float = 0.0


def calculate_statistics(
    latencies_ms: list[float],
    model_name: str = "Model",
    warmup_iters: int = 0,
    model_size_mb: float = 0.0,
) -> BenchmarkResult:
    """Calculate min, max, mean, p95, and FPS from a list of measured latencies."""
    if not latencies_ms:
        return BenchmarkResult(
            model_name=model_name,
            total_iterations=warmup_iters,
            warmup_iterations=warmup_iters,
            measured_iterations=0,
            min_latency_ms=0.0,
            max_latency_ms=0.0,
            mean_latency_ms=0.0,
            p95_latency_ms=0.0,
            fps=0.0,
            model_size_mb=model_size_mb,
        )

    latencies_arr = np.array(latencies_ms, dtype=np.float64)
    min_lat = float(np.min(latencies_arr))
    max_lat = float(np.max(latencies_arr))
    mean_lat = float(np.mean(latencies_arr))
    p95_lat = float(np.percentile(latencies_arr, 95))
    fps = 1000.0 / mean_lat if mean_lat > 0.0 else 0.0

    return BenchmarkResult(
        model_name=model_name,
        total_iterations=len(latencies_ms) + warmup_iters,
        warmup_iterations=warmup_iters,
        measured_iterations=len(latencies_ms),
        min_latency_ms=round(min_lat, 2),
        max_latency_ms=round(max_lat, 2),
        mean_latency_ms=round(mean_lat, 2),
        p95_latency_ms=round(p95_lat, 2),
        fps=round(fps, 2),
        model_size_mb=round(model_size_mb, 2),
    )


def run_fps_benchmark(
    backend: InferenceBackend,
    frames: list[npt.NDArray[np.uint8]],
    warmup_iters: int = 5,
) -> BenchmarkResult:
    """Run inference repeatedly over the given frames, discard warmup_iters
    as JIT/cache warmup, measure wall-clock latency per frame and derive
    fps. Returns min/max/mean/p95 latency plus fps.
    """
    if not frames:
        raise ValueError("Frames list cannot be empty for benchmarking")

    total_iters = len(frames)
    if total_iters <= warmup_iters:
        raise ValueError(
            f"Total frames ({total_iters}) must exceed warmup iterations ({warmup_iters})"
        )

    # 1. Warmup phase (discarded from final statistics)
    for i in range(warmup_iters):
        frame = frames[i % len(frames)]
        _ = backend.infer(frame)

    # 2. Measurement phase
    measured_latencies_ms: list[float] = []
    for i in range(warmup_iters, total_iters):
        frame = frames[i % len(frames)]
        start_time = time.perf_counter()
        _ = backend.infer(frame)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        measured_latencies_ms.append(elapsed_ms)

    model_name = getattr(backend, "model_name", backend.__class__.__name__)
    model_size_mb = 0.0
    session = getattr(backend, "session", None)
    if session is not None:
        model_path = getattr(session, "_model_path", None)
        if model_path:
            p = Path(str(model_path))
            if p.is_file():
                model_size_mb = p.stat().st_size / (1024 * 1024)

    return calculate_statistics(
        latencies_ms=measured_latencies_ms,
        model_name=str(model_name),
        warmup_iters=warmup_iters,
        model_size_mb=model_size_mb,
    )


def main() -> None:
    """Run real FP32 and INT8 benchmarks and produce BENCHMARK_REPORT.md."""
    from vision.inference_backend import ONNXBackend

    from benchmarks.jetson_specs import ALL_HARDWARE_SPECS
    from benchmarks.quantize import quantize_model
    from benchmarks.report import generate_report

    fp32_model = Path("models/yolo26n.onnx")
    int8_model = Path("models/yolo26n_int8.onnx")
    report_path = Path("BENCHMARK_REPORT.md")

    if not fp32_model.is_file():
        logger.error("FP32 model not found at %s", fp32_model)
        return

    # 1. Quantize if INT8 model not present
    if not int8_model.is_file():
        logger.info("Quantizing %s to %s...", fp32_model, int8_model)
        quantize_model(str(fp32_model), str(int8_model))

    # 2. Prepare representative frames
    test_image_path = Path("tests/fixtures/bus.jpg")
    img: npt.NDArray[np.uint8] = np.zeros((640, 640, 3), dtype=np.uint8)
    if test_image_path.is_file():
        loaded = cv2.imread(str(test_image_path))
        if loaded is not None:
            img = loaded.astype(np.uint8)

    benchmark_frames: list[npt.NDArray[np.uint8]] = [img.copy() for _ in range(25)]

    # 3. Benchmark FP32
    logger.info("Running FP32 benchmark (5 warmup + 20 measured)...")
    fp32_backend = ONNXBackend(fp32_model)
    fp32_result = run_fps_benchmark(fp32_backend, benchmark_frames, warmup_iters=5)

    # 4. Benchmark INT8
    logger.info("Running INT8 benchmark (5 warmup + 20 measured)...")
    int8_backend = ONNXBackend(int8_model)
    int8_result = run_fps_benchmark(int8_backend, benchmark_frames, warmup_iters=5)

    # 5. Generate Report
    logger.info("Generating report at %s...", report_path)
    generate_report(fp32_result, int8_result, ALL_HARDWARE_SPECS, str(report_path))
    logger.info("Benchmark report generated successfully at %s", report_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    main()
