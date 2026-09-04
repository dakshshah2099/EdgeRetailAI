# Slice 9 — Benchmark & Quantization Report

Read `AGENTS.md` and `CONTEXT.md` before starting. This slice is the direct
evidence backing the "laptop = Jetson substitute, phone = CCTV substitute"
pitch claim. It doesn't add product functionality — it produces a
reproducible report comparing this pipeline's actual measured performance
against published Jetson Orin specs.

## FR satisfied

Not a functional requirement from the SIH problem statement directly — this
slice supports the POC's credibility argument (see CONTEXT.md's "POC
hardware substitution" section) and partially demonstrates FR12 (edge
inference feasibility) with real numbers instead of assertions.

## Depends on

- Slice 2: `InferenceBackend`/`ONNXBackend`, YOLO26n model — this slice
  benchmarks the existing detection pipeline, does not build a new one.
- Nothing else — this is a standalone measurement/reporting slice.

## Files owned by this slice

```
benchmarks/__init__.py
benchmarks/run_benchmark.py       # script: measures fps/latency on this machine
benchmarks/quantize.py             # INT8 quantization via ONNX Runtime quantization tools
benchmarks/report.py                # generates the comparison report (markdown or similar)
benchmarks/jetson_specs.py           # published Jetson Orin Nano/NX specs, with sources cited
tests/unit/test_benchmark_report.py    # tests the report generation logic, not the actual
                                          # hardware benchmark numbers (those aren't unit-testable)
```

Do not touch `detection/`, `schemas.py`, or any other slice. This slice
reads the existing `ONNXBackend` and model file as-is.

## Interface in

`InferenceBackend` (Slice 2), the existing `models/yolo26n.onnx` file, and
a representative set of test frames (reuse Slice 2's test fixtures if
suitable, or a short benchmark-specific clip/image set).

## Interface out

```python
def run_fps_benchmark(
    backend: InferenceBackend,
    frames: list[npt.NDArray[np.uint8]],
    warmup_iters: int = 5,
) -> BenchmarkResult:
    """Run inference repeatedly over the given frames, discard warmup_iters
    as JIT/cache warmup, measure wall-clock latency per frame and derive
    fps. Returns min/max/mean/p95 latency plus fps."""
    ...

def quantize_model(fp32_model_path: str, output_path: str) -> None:
    """Produce an INT8-quantized ONNX model via onnxruntime.quantization
    (dynamic or static quantization — state which and why). This is a
    real quantization step, not a simulated one — the output file must
    actually be usable by ONNXBackend."""
    ...

def generate_report(
    fp32_result: BenchmarkResult,
    int8_result: BenchmarkResult,
    jetson_specs: list[JetsonSpec],
    output_path: str,
) -> None:
    """Write a markdown report comparing this machine's measured fp32/int8
    performance against published Jetson Orin figures, with explicit
    citation of where the Jetson numbers came from (not fabricated)."""
    ...
```

`JetsonSpec` (local dataclass, not `schemas.py`) should hold: device name
(e.g. "Jetson Orin Nano 8GB"), published TOPS, published fps for a
comparable YOLO model size if available from Ultralytics'/NVIDIA's own
published benchmarks, and a source URL/citation. **Do not fabricate these
numbers** — pull from Ultralytics' YOLO26 release benchmarks (which
explicitly include Jetson Orin figures per earlier research in this
conversation) or NVIDIA's own Jetson benchmark pages. If a directly
comparable number isn't available, say so in the report rather than
interpolating silently.

## Acceptance tests

- [ ] `run_fps_benchmark()` correctly excludes warmup iterations from the
      final statistics (test with a mock backend where warmup calls behave
      differently from steady-state calls, assert warmup is excluded).
- [ ] `run_fps_benchmark()`'s p95/mean latency calculations are correct
      against a known synthetic sequence of latencies (mock the backend's
      timing, assert the math).
- [ ] `quantize_model()` produces a file that loads successfully in
      `ONNXBackend` (i.e. actually run it through the real quantization
      tool against the real model, not mocked — this is one of the few
      slices where hitting the real dependency is the point).
- [ ] `generate_report()` produces a markdown file containing both the
      fp32 and int8 measured numbers and the cited Jetson figures, and
      does NOT claim a number that wasn't actually measured or cited (test
      that every numeric claim in the generated report ties back to either
      `fp32_result`/`int8_result` or a `JetsonSpec` entry — this is really
      about disciplined report-generation code, not natural-language
      validation, so structure the report template so this is naturally
      true rather than trying to parse-and-verify the output text).
- [ ] `mypy --strict` and `ruff check` clean.

## Non-goals for this slice

- No TensorRT benchmarking (no real Jetson hardware available per the
  original constraint that motivated this whole POC substitution approach)
  — the report explicitly extrapolates from published Jetson figures, and
  says so, rather than pretending to have run on real Jetson hardware.
- No automated CI benchmark regression tracking — this is a one-off
  (or manually-rerun) report generator for the pitch deck, not a
  continuous benchmark suite.
- No changes to the detection pipeline itself to make it faster — this
  slice measures what exists, it doesn't optimize it (though the numbers
  it produces might motivate a future optimization pass).

## Agent prompt seed

> Implement `run_fps_benchmark`, `quantize_model`, and `generate_report`
> exactly per `slices/SLICE_9_benchmark_report.md`. Use real ONNX Runtime
> quantization (not a mock) against the actual `models/yolo26n.onnx` file
> — this is one of the rare slices where exercising the real dependency is
> the point, not something to mock out. For Jetson comparison figures, use
> only real published numbers from Ultralytics' YOLO26 release benchmarks
> or NVIDIA's own Jetson Orin benchmark pages — cite the source explicitly
> in `jetson_specs.py`, and if a directly comparable figure isn't
> available, say so in the generated report rather than estimating
> silently. Write unit tests for the statistics/report-generation logic
> (mockable), and separately confirm the real quantization step actually
> works end-to-end (not unit-testable in the strict sense, but show me the
> output in your report). Do not modify detection/, schemas.py, or any
> other slice.