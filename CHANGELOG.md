# Changelog

## v0.1.0 - 2026-05-01

Initial public release of `lmstudio-vlm-tag-benchmark`.

### Added

- Local CLI workflow for benchmarking LM Studio vision-language models on image tagging tasks.
- User-facing `config.yaml` generation from LM Studio model inventory.
- REST Chat inference path through LM Studio.
- Russian and English tagging modes:
  - free tags;
  - plain pool tags;
  - ID-based explained pool tags.
- Raw, normalized, request-level, CSV, and HTML run artifacts.
- Rebuild flow with `collect --write-reports`.
- Static `report.html` answer matrix and `diagnostics.html` technical report.
- Reasoning-aware parsing diagnostics, including detection of models that write reasoning into final answers.
- Smoke and full-shape example configs.

### Scope

- Local-only benchmark runner.
- LM Studio backend only.
- CLI and static files only.

### Not Included

- GUI.
- Web server.
- Database storage.
- Async or distributed runner.
- Automatic judge model.
- Cloud backend.
- Plugin system.
