# Specs workflow

This folder contains small implementation specs for the coding agent.

Specs must be implemented in the active sequence order below. Work on **one spec at a time**.

Completed specs are stored in `archive/`. Active and future specs live in this folder and should be taken by number.

## Active sequence

Current active/future specs:

- `14-html-answer-matrix.md` — primary answer matrix report.
- `15-diagnostics-data-contract.md` — run-level `diagnostics.json`.
- `16-diagnostics-html-report.md` — human-readable `diagnostics.html`.
- `17-line-based-prompt-modernization.md` — switch active prompts to line-based tag output and prompt v2.
- `18-resumable-request-artifacts.md` — durable per-request artifacts and resume modes.
- `19-collect-merge-from-artifacts.md` — rebuild summary/diagnostics/reports from artifacts.
- `20-report-statistics-and-print.md` — top timing summary, final tag colors, print-friendly report.
- `21-accumulate-result-mode.md` — append-only repeated attempts for the same logical request.

Recommended implementation order from the current state:

1. `17-line-based-prompt-modernization.md`
2. `18-resumable-request-artifacts.md`
3. `19-collect-merge-from-artifacts.md`
4. `20-report-statistics-and-print.md`
5. `21-accumulate-result-mode.md`

## Workflow

For each spec:

1. Read the current spec and linked project documentation.
2. Implement only the tasks from this spec.
3. Update related documentation if behavior, config, CLI usage, output format, or project structure changes.
4. Add or update tests when testing is possible and reasonable for this stage.
5. Run the relevant checks.
6. Fill the `Agent report` section in the spec.
7. Commit code, tests, docs, and the updated spec report together.

## Rules

- Do not implement several specs in one pass.
- Do not skip documentation updates when the implementation changes documented behavior.
- Keep changes small and reviewable.
- Prefer simple Python modules over large frameworks.
- Avoid speculative features.
- Do not add GUI, SQLite, web server, async runner, Ollama support, plugin system, or heavy frontend tooling in v1.
- For smoke checks, run only the smallest configured model (minimum `params`) with one image to keep checks fast and stable.
- If something is ambiguous, choose the simplest working option and mention it in `Agent report`.
- If automated testing is not practical for a stage, add a short manual check instead.

## Spec format

Each spec uses this structure:

```md
# SPEC-XX — Short stage name

## Goal

What should be done in this stage.

## Files

Related files:

- [README](../README.md)
- [Architecture](../ARCHITECTURE.md)
- [Archived specs](./archive/)

Expected files:

- `path/to/file.py`
- `tests/test_something.py`

## Tasks

- Task 1.
- Task 2.
- Task 3.

## Check

Commands or manual checks that confirm the stage works.

## Agent report

Fill this after implementation:

- Done:
- Changed files:
- Checks run:
- Notes:
```
