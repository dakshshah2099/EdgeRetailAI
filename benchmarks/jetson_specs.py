"""Published hardware specifications and benchmark figures for edge devices."""

from dataclasses import dataclass


@dataclass(frozen=True)
class JetsonSpec:
    """Published hardware specification and benchmark baseline for edge devices."""

    device_name: str
    architecture: str
    ai_tops_int8: float
    memory_gb: float
    memory_bandwidth_gbps: float
    power_watts: str
    precision: str
    comparable_model: str
    published_fps: float | None
    source_url: str
    notes: str


JETSON_ORIN_NANO_4GB = JetsonSpec(
    device_name="NVIDIA Jetson Orin Nano (4GB)",
    architecture="NVIDIA Ampere (512 CUDA cores + 16 Tensor cores)",
    ai_tops_int8=20.0,
    memory_gb=4.0,
    memory_bandwidth_gbps=34.0,
    power_watts="5W - 10W",
    precision="TensorRT INT8",
    comparable_model="YOLOv8n / YOLO26n (640x640)",
    published_fps=48.0,
    source_url="https://developer.nvidia.com/embedded/jetson-benchmarks",
    notes="Official NVIDIA benchmark for Orin Nano 4GB at 10W power mode",
)

JETSON_ORIN_NANO_8GB = JetsonSpec(
    device_name="NVIDIA Jetson Orin Nano (8GB)",
    architecture="NVIDIA Ampere (1024 CUDA cores + 32 Tensor cores)",
    ai_tops_int8=40.0,
    memory_gb=8.0,
    memory_bandwidth_gbps=68.0,
    power_watts="7W - 15W",
    precision="TensorRT INT8",
    comparable_model="YOLOv8n / YOLO26n (640x640)",
    published_fps=95.0,
    source_url="https://developer.nvidia.com/embedded/jetson-benchmarks",
    notes="Official NVIDIA benchmark for Orin Nano 8GB at 15W power mode",
)

JETSON_ORIN_NX_16GB = JetsonSpec(
    device_name="NVIDIA Jetson Orin NX (16GB)",
    architecture="NVIDIA Ampere (1024 CUDA cores + 32 Tensor cores)",
    ai_tops_int8=100.0,
    memory_gb=16.0,
    memory_bandwidth_gbps=102.4,
    power_watts="10W - 25W",
    precision="TensorRT INT8",
    comparable_model="YOLOv8n / YOLO26n (640x640)",
    published_fps=210.0,
    source_url="https://developer.nvidia.com/embedded/jetson-benchmarks",
    notes="Official NVIDIA benchmark for Orin NX 16GB at 25W power mode",
)

JETSON_AGX_ORIN_64GB = JetsonSpec(
    device_name="NVIDIA Jetson AGX Orin (64GB)",
    architecture="NVIDIA Ampere (2048 CUDA cores + 64 Tensor cores)",
    ai_tops_int8=275.0,
    memory_gb=64.0,
    memory_bandwidth_gbps=204.8,
    power_watts="15W - 60W",
    precision="TensorRT INT8",
    comparable_model="YOLOv8n / YOLO26n (640x640)",
    published_fps=580.0,
    source_url="https://developer.nvidia.com/embedded/jetson-benchmarks",
    notes="Official NVIDIA benchmark for AGX Orin 64GB at 60W MAX-N mode",
)

RASPBERRY_PI_4B_8GB = JetsonSpec(
    device_name="Raspberry Pi 4B (8GB)",
    architecture="Broadcom BCM2711 (4x ARM Cortex-A72 @ 1.5GHz, NEON SIMD)",
    ai_tops_int8=0.1,
    memory_gb=8.0,
    memory_bandwidth_gbps=4.4,
    power_watts="5W - 7.5W",
    precision="ONNX Runtime / NCNN INT8",
    comparable_model="YOLOv8n / YOLO26n (640x640)",
    published_fps=8.5,
    source_url="https://docs.ultralytics.com/guides/yolo-performance-benchmarking/",
    notes="Ultralytics embedded benchmark; 8.5 FPS at 640x640 INT8 (~16 FPS at 320x320)",
)

RASPBERRY_PI_5_HAILO = JetsonSpec(
    device_name="Raspberry Pi 5 + Hailo-8L M.2 AI Kit",
    architecture="Broadcom BCM2712 (4x Cortex-A76 @ 2.4GHz) + Hailo-8L NPU",
    ai_tops_int8=13.0,
    memory_gb=8.0,
    memory_bandwidth_gbps=17.0,
    power_watts="5W - 12W",
    precision="HailoRT INT8",
    comparable_model="YOLOv8n / YOLO26n (640x640)",
    published_fps=150.0,
    source_url="https://www.raspberrypi.com/products/ai-kit/",
    notes="Official Raspberry Pi AI Kit benchmark with Hailo-8L NPU (13 TOPS)",
)

ESP32_S3_CAM = JetsonSpec(
    device_name="Espressif ESP32-S3 (8MB PSRAM) / ESP32-CAM",
    architecture="Dual-Core Xtensa LX7 @ 240MHz + Vector Extensions (PIE)",
    ai_tops_int8=0.01,
    memory_gb=0.008,
    memory_bandwidth_gbps=0.3,
    power_watts="0.5W - 1.5W",
    precision="ESP-DL INT8 (Micro CV)",
    comparable_model="MobileNet / FOMO (96x96)",
    published_fps=4.0,
    source_url="https://github.com/espressif/esp-dl",
    notes=(
        "Microcontroller tier. Unsuitable for full 640x640 YOLO26n; "
        "ideal as low-cost RTSP camera feed provider to RPi 4B host"
    ),
)

ALL_JETSON_SPECS: list[JetsonSpec] = [
    JETSON_ORIN_NANO_4GB,
    JETSON_ORIN_NANO_8GB,
    JETSON_ORIN_NX_16GB,
    JETSON_AGX_ORIN_64GB,
]

ALL_HARDWARE_SPECS: list[JetsonSpec] = [
    JETSON_ORIN_NANO_4GB,
    JETSON_ORIN_NANO_8GB,
    JETSON_ORIN_NX_16GB,
    JETSON_AGX_ORIN_64GB,
    RASPBERRY_PI_4B_8GB,
    RASPBERRY_PI_5_HAILO,
    ESP32_S3_CAM,
]
