"""Unit tests for Slice 9 benchmark calculations, quantization, and report generation."""

import time
from pathlib import Path

import numpy as np
import numpy.typing as npt
import pytest

from benchmarks.jetson_specs import ALL_JETSON_SPECS
from benchmarks.quantize import quantize_model
from benchmarks.report import generate_report
from benchmarks.run_benchmark import (
    BenchmarkResult,
    calculate_statistics,
    run_fps_benchmark,
)
from vision.inference_backend import InferenceBackend, ONNXBackend, RawDetection


class MockTimingBackend(InferenceBackend):
    """Mock backend that sleeps for a configurable latency on each call."""

    def __init__(self, latencies_sec: list[float]) -> None:
        self.latencies_sec = latencies_sec
        self.call_count = 0

    def infer(self, frame: npt.NDArray[np.uint8]) -> list[RawDetection]:
        idx = min(self.call_count, len(self.latencies_sec) - 1)
        sleep_time = self.latencies_sec[idx]
        self.call_count += 1
        time.sleep(sleep_time)
        return []


class MockWarmupFlagBackend(InferenceBackend):
    """Mock backend that records call counts."""

    def __init__(self) -> None:
        self.call_count = 0
        self.recorded_calls: list[int] = []

    def infer(self, frame: npt.NDArray[np.uint8]) -> list[RawDetection]:
        self.call_count += 1
        self.recorded_calls.append(self.call_count)
        return []


def test_run_fps_benchmark_warmup_exclusion() -> None:
    """Warmup iterations must be discarded and excluded from measured iterations."""
    backend = MockWarmupFlagBackend()
    frames = [np.zeros((64, 64, 3), dtype=np.uint8) for _ in range(12)]
    warmup_iters = 4

    result = run_fps_benchmark(backend, frames, warmup_iters=warmup_iters)

    assert backend.call_count == 12
    assert result.warmup_iterations == 4
    assert result.measured_iterations == 8
    assert result.total_iterations == 12


def test_run_fps_benchmark_empty_or_invalid_frames() -> None:
    """Benchmark raises ValueError when frames are empty or warmup exceeds frame count."""
    backend = MockWarmupFlagBackend()
    with pytest.raises(ValueError, match="cannot be empty"):
        run_fps_benchmark(backend, [], warmup_iters=1)

    frames = [np.zeros((64, 64, 3), dtype=np.uint8) for _ in range(3)]
    with pytest.raises(ValueError, match="must exceed warmup"):
        run_fps_benchmark(backend, frames, warmup_iters=3)


def test_calculate_statistics_known_sequence() -> None:
    """Verify mean, min, max, p95, and fps calculations on a deterministic synthetic sequence."""
    latencies = [float(i) for i in range(1, 101)]
    result = calculate_statistics(
        latencies, model_name="TestModel", warmup_iters=5, model_size_mb=10.0
    )

    assert result.model_name == "TestModel"
    assert result.total_iterations == 105
    assert result.warmup_iterations == 5
    assert result.measured_iterations == 100
    assert result.min_latency_ms == 1.0
    assert result.max_latency_ms == 100.0
    assert result.mean_latency_ms == 50.5
    assert abs(result.p95_latency_ms - 95.05) < 0.2
    assert abs(result.fps - (1000.0 / 50.5)) < 0.05
    assert result.model_size_mb == 10.0


def test_calculate_statistics_empty_sequence() -> None:
    """Empty latency list returns safe zeroed BenchmarkResult."""
    result = calculate_statistics([], model_name="EmptyModel")
    assert result.measured_iterations == 0
    assert result.mean_latency_ms == 0.0
    assert result.fps == 0.0


def test_run_fps_benchmark_timing_accuracy() -> None:
    """Verify wall-clock measurement matches mocked sleep times."""
    sleeps = [0.001, 0.001, 0.010, 0.010, 0.010]
    backend = MockTimingBackend(sleeps)
    frames = [np.zeros((64, 64, 3), dtype=np.uint8) for _ in range(5)]

    result = run_fps_benchmark(backend, frames, warmup_iters=2)
    assert result.measured_iterations == 3
    assert 5.0 <= result.mean_latency_ms <= 35.0
    assert 25.0 <= result.fps <= 200.0


def test_generate_report_contents(tmp_path: Path) -> None:
    """Generated markdown report strictly contains measured numbers and cited specs."""
    fp32_res = BenchmarkResult(
        model_name="YOLO26n FP32",
        total_iterations=20,
        warmup_iterations=5,
        measured_iterations=15,
        min_latency_ms=18.5,
        max_latency_ms=25.2,
        mean_latency_ms=20.0,
        p95_latency_ms=24.1,
        fps=50.0,
        model_size_mb=9.5,
    )
    int8_res = BenchmarkResult(
        model_name="YOLO26n INT8",
        total_iterations=20,
        warmup_iterations=5,
        measured_iterations=15,
        min_latency_ms=9.1,
        max_latency_ms=14.5,
        mean_latency_ms=10.0,
        p95_latency_ms=13.8,
        fps=100.0,
        model_size_mb=2.8,
    )

    out_file = tmp_path / "report.md"
    generate_report(fp32_res, int8_res, ALL_JETSON_SPECS, str(out_file))

    assert out_file.is_file()
    content = out_file.read_text(encoding="utf-8")

    # Assert measured numbers are present in report
    assert "20.00 ms" in content
    assert "10.00 ms" in content
    assert "50.00 FPS" in content
    assert "100.00 FPS" in content
    assert "9.50 MB" in content
    assert "2.80 MB" in content
    assert "2.00x throughput (speedup)" in content
    assert "StreamManager" not in content

    # Assert cited Jetson devices and official links are present
    assert "NVIDIA Jetson Orin Nano (8GB)" in content
    assert "40.0 TOPS" in content
    assert "95.0 FPS" in content
    assert "https://developer.nvidia.com/embedded/jetson-benchmarks" in content


def test_generate_report_negative_delta_regression(tmp_path: Path) -> None:
    """When INT8 is slower than FP32, report honestly labels it as regression and slowdown."""
    fp32_res = BenchmarkResult(
        model_name="YOLO26n FP32",
        total_iterations=20,
        warmup_iterations=5,
        measured_iterations=15,
        min_latency_ms=40.0,
        max_latency_ms=50.0,
        mean_latency_ms=44.0,
        p95_latency_ms=48.0,
        fps=22.5,
        model_size_mb=9.5,
    )
    int8_res = BenchmarkResult(
        model_name="YOLO26n INT8",
        total_iterations=20,
        warmup_iterations=5,
        measured_iterations=15,
        min_latency_ms=80.0,
        max_latency_ms=110.0,
        mean_latency_ms=94.0,
        p95_latency_ms=105.0,
        fps=10.6,
        model_size_mb=2.8,
    )

    out_file = tmp_path / "regression_report.md"
    generate_report(fp32_res, int8_res, ALL_JETSON_SPECS, str(out_file))

    assert out_file.is_file()
    content = out_file.read_text(encoding="utf-8")

    # Honest labels must be present
    assert "latency increase (regression on CPU)" in content
    assert "slowdown on generic CPU" in content
    assert "StreamManager" not in content
    assert "published headroom of **95+ FPS**" in content


def test_quantize_model_missing_source(tmp_path: Path) -> None:
    """quantize_model raises FileNotFoundError when source model is missing."""
    missing_path = tmp_path / "non_existent.onnx"
    out_path = tmp_path / "out.onnx"
    with pytest.raises(FileNotFoundError):
        quantize_model(str(missing_path), str(out_path))


def test_quantize_and_load_real_model(tmp_path: Path) -> None:
    """Verify real ONNX dynamic quantization on the repository's YOLO26n model."""
    real_model = Path(__file__).resolve().parent.parent.parent / "models" / "yolo26n.onnx"
    if not real_model.is_file():
        pytest.skip("models/yolo26n.onnx not present in workspace")

    out_quant_model = tmp_path / "yolo26n_int8_test.onnx"
    quantize_model(str(real_model), str(out_quant_model))

    assert out_quant_model.is_file()
    assert out_quant_model.stat().st_size > 100_000
    assert out_quant_model.stat().st_size < real_model.stat().st_size * 0.5

    # Verify that the quantized model actually loads and runs in ONNXBackend
    backend = ONNXBackend(out_quant_model)
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    detections = backend.infer(dummy_frame)
    assert isinstance(detections, list)
