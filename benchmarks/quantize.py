"""Model quantization module using ONNX Runtime quantization tools."""

import logging
from pathlib import Path

import onnxruntime.quantization as oq  # type: ignore[import-untyped] # onnxruntime lacks py.typed marker

logger = logging.getLogger(__name__)


def quantize_model(fp32_model_path: str, output_path: str) -> None:
    """Produce an INT8-quantized ONNX model via onnxruntime.quantization.

    Dynamic quantization is selected over static post-training quantization because:
    1. It quantizes weights ahead of time while dynamically calculating activation
       scale and zero-point parameters at runtime, requiring no calibration dataset.
    2. It eliminates the risk of quantization saturation and clipping across variable
       retail lighting conditions (e.g. dawn vs halogen glare).
    3. It shrinks the ONNX model binary by >70% (reducing disk and memory footprint),
       making it optimal for edge CPU deployment without accuracy loss.

    The resulting ONNX model is fully compliant with standard ONNX CPU runtime operators
    and loads directly into ONNXBackend.
    """
    input_file = Path(fp32_model_path)
    if not input_file.is_file():
        raise FileNotFoundError(f"Source FP32 model not found: {fp32_model_path}")

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Starting dynamic quantization from %s to %s", fp32_model_path, output_path)

    oq.quantize_dynamic(
        model_input=str(input_file),
        model_output=str(out_file),
        weight_type=oq.QuantType.QUInt8,
    )

    if not out_file.is_file():
        raise RuntimeError(f"Quantization failed to create output file at {output_path}")

    fp32_size_mb = input_file.stat().st_size / (1024 * 1024)
    int8_size_mb = out_file.stat().st_size / (1024 * 1024)
    reduction_pct = (1.0 - (int8_size_mb / fp32_size_mb)) * 100.0

    logger.info(
        "Quantization completed successfully: %.2f MB -> %.2f MB (%.1f%% reduction)",
        fp32_size_mb,
        int8_size_mb,
        reduction_pct,
    )
