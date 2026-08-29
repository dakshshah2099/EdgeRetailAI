# AGENTS.md — Operating Rules for Coding Agents

This file governs how any AI coding agent (Antigravity, Claude Code, Cursor, etc...)
works in this repository. Read this before touching any code. If a slice prompt
conflicts with this file, this file wins on process; the slice prompt wins on
scope/interface details.

## Project

Intelligent Retail Analytics System (SIH26179) — edge-AI shopper analytics,
inventory monitoring, and queue intelligence. POC runs on a laptop (Jetson
substitute) using a phone camera (CCTV substitute) via RTSP, with an explicit
model-portability story (ONNX now → TensorRT on Jetson later).

## Ground truth documents

- `CONTEXT.md` — problem statement, functional requirements, architecture, stack.
- `slices/SLICE_<n>_<name>.md` — one file per vertical slice, the actual work order.

Agents must read `CONTEXT.md` and the specific slice file before writing code.
Do not infer requirements from filenames or prior slices alone.

## Golden rules

1. **One slice, one branch, one PR.** Never touch files outside the slice's
   declared interface boundaries (see slice file's "Files owned" section).
   If a slice needs to change a file owned by another slice, stop and flag it
   instead of editing silently.
2. **Contracts first.** All data crossing a slice boundary is a typed Pydantic
   model defined in `schemas.py`. No raw dicts, no untyped tuples, no `Any`
   at a public interface.
3. **Tests are the spec.** Write or update tests for the slice's acceptance
   criteria before or alongside implementation. A slice is not done until its
   listed acceptance tests pass. Do not mark a slice complete by inspection alone.
4. **No PII persistence, ever.** No raw frames, face crops, or identity data
   may be written to disk, DB, or logs. This is enforced structurally in
   `schemas.py` (no `image`/`face`/`embedding` fields on any persisted model) —
   do not add one to satisfy a slice's convenience. If a slice seems to require
   it, stop and flag it instead of implementing.
5. **Type and lint discipline.** `mypy --strict` and `ruff` must pass with zero
   errors before a slice is considered complete. No bare `except:`. No
   `# type: ignore` without a one-line reason comment.
6. **Small, reviewable diffs.** Prefer several small commits over one large
   commit. Commit messages: `slice(N): <what>`, e.g. `slice(2): add ByteTrack
   person counter`.
7. **Don't invent scope.** Each slice file has a "Non-goals" section. Do not
   implement anything listed there, even if it seems easy or related. Flag it
   as a future slice instead.
8. **Ask via comments, not assumptions.** If a slice prompt is ambiguous on an
   implementation detail not covered by "Interface in/out," leave a `# AGENT-QUESTION:`
   comment and pick the simplest reasonable default rather than blocking.

## Repo layout

```
retail-poc/
  schemas.py              # Slice 0 — all cross-slice contracts live here
  config.yaml              # runtime config (camera source, zones, thresholds)
  camera/                  # Slice 1
  detection/                # Slice 2, 3
  inventory/                 # Slice 4
  queue_intel/                # Slice 5
  alerts/                      # Slice 6
  storage/                      # Slice 7
  api/                            # Slice 8
  benchmarks/                      # Slice 9
  tests/
    unit/
    fixtures/               # test videos, sample frames, labeled shelf images
  slices/                    # slice prompt files (source of truth for scope)
  CONTEXT.md
  AGENTS.md
```

## Definition of done (applies to every slice)

- [ ] Acceptance tests in the slice file pass (`pytest -k slice_N`)
- [ ] `mypy --strict` clean on changed files
- [ ] `ruff check` clean
- [ ] No new field/type introduced that stores PII or raw imagery
- [ ] Public interface matches the slice's "Interface in/out" exactly (or the
      deviation is called out explicitly in the PR description)
- [ ] No files outside the slice's owned paths were modified

## Stack (fixed for this POC — do not swap without discussion)

- Python 3.11+, FastAPI, Pydantic v2, SQLite, OpenCV, ONNX Runtime
- YOLOv8n (person/object detection) exported to ONNX
- pytest, mypy --strict, ruff, pre-commit

## Non-negotiables

- Model inference path must stay swappable: ONNX Runtime session wrapped
  behind a single `InferenceBackend` interface (Slice 0/2), so swapping to
  TensorRT later touches one file, not the whole pipeline.
- Camera input must stay swappable: `CameraSource` interface (Slice 1), so
  swapping phone-RTSP for CSI/USB camera later touches one file.