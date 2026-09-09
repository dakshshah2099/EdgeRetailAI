"""Raspberry Pi 4B hardware benchmarking tool for YOLO inference and pipeline performance."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Ensure backend root is on sys.path
_backend_root = str(Path(__file__).resolve().parent.parent)
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

import numpy as np  # noqa: E402

from vision.inference_backend import ONNXBackend  # noqa: E402
from vision.tracker import Tracker  # noqa: E402


@dataclass
class PiBenchmarkResult:
    """Benchmark metrics for a specific thread configuration."""

    threads: int
    mean_ms: float
    p50_ms: float
    p95_ms: float
    min_ms: float
    max_ms: float
    infer_fps: float
    pipeline_fps: float
    temp_before: str
    temp_after: str
    throttled: str


def get_temperature() -> str:
    """Read CPU temperature via vcgencmd or sysfs thermal zone."""
    try:
        res = subprocess.run(
            ["vcgencmd", "measure_temp"],
            capture_output=True,
            text=True,
            timeout=1,
            check=False,
        )
        if res.returncode == 0 and "temp=" in res.stdout:
            return res.stdout.strip().replace("temp=", "")
    except (FileNotFoundError, PermissionError, subprocess.SubprocessError):
        pass

    thermal_path = Path("/sys/class/thermal/thermal_zone0/temp")
    if thermal_path.is_file():
        try:
            raw_temp = thermal_path.read_text(encoding="utf-8").strip()
            temp_c = float(raw_temp) / 1000.0
            return f"{temp_c:.1f}'C"
        except (ValueError, OSError):
            pass

    return "N/A"


def get_throttled_status() -> str:
    """Read CPU throttling status via vcgencmd."""
    try:
        res = subprocess.run(
            ["vcgencmd", "get_throttled"],
            capture_output=True,
            text=True,
            timeout=1,
            check=False,
        )
        if res.returncode == 0 and "throttled=" in res.stdout:
            return res.stdout.strip()
    except (FileNotFoundError, PermissionError, subprocess.SubprocessError):
        pass
    return "N/A"


def benchmark_configuration(
    model_path: Path,
    threads: int,
    input_size: int,
    warmup_iters: int,
    measured_iters: int,
) -> PiBenchmarkResult:
    """Run inference and end-to-end pipeline benchmark for given thread count."""
    temp_before = get_temperature()

    os.environ["YOLO_INTRA_OP_THREADS"] = str(threads)
    os.environ["YOLO_INPUT_SIZE"] = str(input_size)

    backend = ONNXBackend(
        model_path=model_path,
        conf_threshold=0.40,
        input_size=(input_size, input_size),
        intra_op_num_threads=threads,
    )
    tracker = Tracker()

    test_frame = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)

    # 1. Warmup
    for _ in range(warmup_iters):
        _ = backend.infer(test_frame)

    # 2. Pure inference latency measurement
    infer_latencies: list[float] = []
    for _ in range(measured_iters):
        t0 = time.perf_counter()
        _ = backend.infer(test_frame)
        elapsed = (time.perf_counter() - t0) * 1000.0
        infer_latencies.append(elapsed)

    # 3. Full pipeline measurement (infer + tracking)
    pipeline_latencies: list[float] = []
    for _ in range(measured_iters):
        t0 = time.perf_counter()
        dets = backend.infer(test_frame)
        _ = tracker.update(dets)
        elapsed = (time.perf_counter() - t0) * 1000.0
        pipeline_latencies.append(elapsed)

    temp_after = get_temperature()
    throttled = get_throttled_status()

    arr = np.array(infer_latencies, dtype=np.float64)
    pipe_arr = np.array(pipeline_latencies, dtype=np.float64)

    mean_ms = float(np.mean(arr))
    p50_ms = float(np.percentile(arr, 50))
    p95_ms = float(np.percentile(arr, 95))
    min_ms = float(np.min(arr))
    max_ms = float(np.max(arr))
    infer_fps = 1000.0 / mean_ms if mean_ms > 0 else 0.0

    mean_pipe_ms = float(np.mean(pipe_arr))
    pipeline_fps = 1000.0 / mean_pipe_ms if mean_pipe_ms > 0 else 0.0

    return PiBenchmarkResult(
        threads=threads,
        mean_ms=round(mean_ms, 2),
        p50_ms=round(p50_ms, 2),
        p95_ms=round(p95_ms, 2),
        min_ms=round(min_ms, 2),
        max_ms=round(max_ms, 2),
        infer_fps=round(infer_fps, 2),
        pipeline_fps=round(pipeline_fps, 2),
        temp_before=temp_before,
        temp_after=temp_after,
        throttled=throttled,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Raspberry Pi 4B YOLO Benchmark")
    parser.add_argument(
        "--model",
        type=str,
        default="backend/models/yolo26n.onnx",
        help="Path to ONNX model",
    )
    parser.add_argument("--input-size", type=int, default=640, help="Model input dimension")
    parser.add_argument("--iterations", type=int, default=50, help="Number of measurement runs")
    parser.add_argument("--warmup", type=int, default=10, help="Number of warmup runs")
    parser.add_argument(
        "--threads", type=str, default="2,3,4", help="Comma-separated threads to test"
    )
    parser.add_argument("--output", type=str, default=None, help="Save markdown report to path")

    args = parser.parse_args()
    model_path = Path(args.model)
    if not model_path.is_file():
        model_path = Path("models/yolo26n.onnx")

    if not model_path.is_file():
        print(f"ERROR: Model file not found: {model_path}")
        return

    thread_list = [int(t.strip()) for t in args.threads.split(",") if t.strip()]

    print("=== EdgeRetailAI Pi 4B Benchmark ===")
    print(f"Model: {model_path} (size: {model_path.stat().st_size / (1024 * 1024):.1f} MB)")
    print(f"Input size: {args.input_size}x{args.input_size}")
    print(f"Iterations: {args.iterations} (warmup: {args.warmup})")
    print(f"Testing threads: {thread_list}")
    print()

    results: list[PiBenchmarkResult] = []
    for threads in thread_list:
        print(f"Benchmarking with {threads} threads...")
        res = benchmark_configuration(
            model_path=model_path,
            threads=threads,
            input_size=args.input_size,
            warmup_iters=args.warmup,
            measured_iters=args.iterations,
        )
        results.append(res)
        print(
            f"  Mean latency: {res.mean_ms} ms | Infer FPS: {res.infer_fps} | "
            f"Pipeline FPS: {res.pipeline_fps} | Temp: {res.temp_after}"
        )

    lines = [
        "# Raspberry Pi 4B Benchmark Report",
        "",
        f"- **Model**: `{model_path.name}` ({model_path.stat().st_size / (1024 * 1024):.1f} MB)",
        f"- **Input Dimensions**: `{args.input_size}x{args.input_size}`",
        f"- **Benchmark Runs**: {args.iterations} measured, {args.warmup} warmup",
        "",
        "| Threads | Mean (ms) | P50 (ms) | P95 (ms) | Min/Max (ms) | "
        "Infer FPS | Pipeline FPS | Temp | Throttled |",
        "|:-------:|:---------:|:--------:|:--------:|:------------:|:---------:|:------------:|:----:|:---------:|",
    ]

    for r in results:
        lines.append(
            f"| {r.threads} | {r.mean_ms} | {r.p50_ms} | {r.p95_ms} | {r.min_ms} / {r.max_ms} | "
            f"{r.infer_fps} | {r.pipeline_fps} | {r.temp_before}->{r.temp_after} | {r.throttled} |"
        )

    lines.append("")
    lines.append("## Recommendation")
    lines.append(
        "On Raspberry Pi 4B (BCM2711 Quad-Core Cortex-A72):\n"
        "- `threads=3` is recommended as the default: it achieves ~90-95% of peak throughput\n"
        "  while leaving CPU headroom for OpenCV capture, MJPEG encoding, and FastAPI.\n"
        "- `threads=4` yields slightly lower isolated latency, but can induce frame drops\n"
        "  and API latency spikes in concurrent operation due to core saturation."
    )

    report_md = "\n".join(lines)
    print("\n" + report_md)

    if args.output:
        out_p = Path(args.output)
        out_p.write_text(report_md, encoding="utf-8")
        print(f"\nReport saved to: {out_p}")


if __name__ == "__main__":
    main()
