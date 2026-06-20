# Agents.md

Last updated: 2026-06-21

This file is the permanent repository rulebook and must be read before any AI/dev pass.

## Project context and non-negotiable constraints

- This repository targets **Windows 10/11 (64-bit)** users.
- The user-facing application is a Gradio launcher for **Z-Image Turbo (GGUF)** using **stable-diffusion.cpp** as the generation backend.
- The authoritative implementation flow is:
  - `start_zimage.bat` (entrypoint)
  - `setup_and_run.ps1` (setup + launch flow)
  - `run_gradio_ui.py` (app runtime)
- Core data and model config files are:
  - `config/setup_config.json` (generated setup state)
  - `config/model_registry.json` (model source-of-truth metadata)
  - `models\zimage\`
  - `models\vae\`
  - `models\llm\`
  - `models\loras\`
- Backend assets and installation rules remain:
  - Preferred executable: `sd_bin\sd-cli.exe`
  - Legacy support: `sd_bin\sd.exe` remains valid
  - `sd_server`/`stable-diffusion.dll` handling is tied to current stable-diffusion.cpp packages
  - New users are expected to use the automatic backend path where possible; manual placement in `sd_bin\` is still supported
- Hardware and profile behavior currently implemented:
  - NVIDIA uses `cuda12` detection and auto-recommendation
  - AMD/Intel fallback strategy is CPU unless a Windows Vulkan/SYCL path is explicitly made stable for that hardware
  - `cpu_only` profile remains supported

## 1) Mandatory pre-read

- Every AI/dev pass must start by reading `Agents.md`.
- If a task touches a known system, the pass must also read:
  - relevant task file(s)
  - relevant audit file(s)
  - `Repo_map.md`
  - relevant source files (for example: `setup_and_run.ps1`, `run_gradio_ui.py`, `README.md`, `docs\setup_architecture.md`) before editing.

## 2) Pass type policy

- Default pass type is **combined audit + implementation**.
- Allowed exceptions:
  - audit-only
  - question-only
  - mapping-only
- In a combined pass, both governance artifacts and implementation changes are required together.
- Audit-only and question-only passes do not modify files.
- Mapping-only passes must update architecture mapping but not implement product/feature changes.

## 3) Task tracking requirements

- Every pass must create or update `tasks/TASK_INDEX.md` before implementation.
- `tasks/TASK_INDEX.md` is the repo-level task index and must contain one row for every task.
- Every task requires its own file in `tasks/`.
- Minimum fields in each task file:
  - task name
  - date
  - goal
  - scope
  - checklist
  - files reviewed
  - files changed
  - audit reference
  - changelog reference
  - completion status
- Completed passes must mark all required checklist items complete before finishing.

## 4) Audit tracking requirements

- All audits live under `audits/` and must be indexed in `Audits_index.md`.
- Every combined pass must create/update an audit entry and include:
  - date
  - task reference
  - files reviewed
  - findings
  - risks
  - decisions
  - implementation notes (when applicable)
  - freshness status
- An audit is considered stale after 3 days for implementation proof.
- If an older audit is referenced, all files it covers must be re-checked before implementation.

## 5) Repo mapping requirements

- Repository architecture and source-of-truth relationships are recorded in `Repo_map.md`.
- If implementation changes alter ownership, architecture, or source-of-truth boundaries, update `Repo_map.md` in the same pass.
- Existing architecture notes in docs should be preserved unless directly conflicting.

## 6) Changelog requirements

- Any documentation, governance, config, code, or structure change requires a `changelog.md` entry.
- Required changelog entry content:
  - date
  - task reference
  - summary
  - files changed
  - reason for change

## 7) Preservation rule

- Preserve existing project constraints and architecture notes found in this repo, unless they conflict with mandatory governance standards.
- If a conflict exists, preserve the stricter rule and log the decision in the audit.
- If uncertain, keep both instructions and add a clarification.
- Do not remove operational knowledge from docs without replacement.

## 8) Git requirements

- For a completed implementation pass in a Git repo:
  - stage only files changed by the pass
  - commit locally
  - do not push
- If unrelated local changes exist, do not overwrite them; document them and avoid staging unrelated files.

## 9) End-of-pass report format

Every completed pass must use this structure in the handoff:

Before:
- ...

After:
- ...

What changed:
- ...

Why:
- ...

Files reviewed:
- ...

Files changed:
- ...

Audit:
- ...

Task:
- ...

Changelog:
- ...

Git:
- Commit: <hash or "not committed because ...">
- Push: not pushed

