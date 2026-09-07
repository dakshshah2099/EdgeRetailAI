"""Edge benchmarking, quantization, and edge hardware comparison suite."""

from benchmarks.jetson_specs import (
    ALL_HARDWARE_SPECS,
    ALL_JETSON_SPECS,
    ESP32_S3_CAM,
    JETSON_AGX_ORIN_64GB,
    JETSON_ORIN_NANO_4GB,
    JETSON_ORIN_NANO_8GB,
    JETSON_ORIN_NX_16GB,
    RASPBERRY_PI_4B_8GB,
    RASPBERRY_PI_5_HAILO,
    JetsonSpec,
)
from benchmarks.quantize import quantize_model
from benchmarks.report import generate_report
from benchmarks.run_benchmark import (
    BenchmarkResult,
    calculate_statistics,
    run_fps_benchmark,
)

__all__ = [
    "JetsonSpec",
    "JETSON_ORIN_NANO_4GB",
    "JETSON_ORIN_NANO_8GB",
    "JETSON_ORIN_NX_16GB",
    "JETSON_AGX_ORIN_64GB",
    "RASPBERRY_PI_4B_8GB",
    "RASPBERRY_PI_5_HAILO",
    "ESP32_S3_CAM",
    "ALL_JETSON_SPECS",
    "ALL_HARDWARE_SPECS",
    "quantize_model",
    "generate_report",
    "BenchmarkResult",
    "calculate_statistics",
    "run_fps_benchmark",
]
