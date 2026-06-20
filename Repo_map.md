# Repository Map

## Top-level structure

- `README.md` — user-facing documentation, requirements, setup workflow, download guidance, and troubleshooting.
- `setup_and_run.ps1` — authoritative setup-and-launch script; two-stage behavior (setup wizard + normal launch), hardware detection, model/backend discovery, and dependency install.
- `start_zimage.bat` — Windows entrypoint used by standard users.
- `run_gradio_ui.py` — Gradio app runtime.
- `config\` — generated and source-of-truth config files (`setup_config.json`, `model_registry.json`).
- `models\` — installed model artifacts (`zimage`, `vae`, `llm`, `loras`).
- `sd_bin\` — stable-diffusion backend files (`sd-cli.exe`, optional `sd.exe`, dll payloads).
- `docs\` — architecture notes and roadmap (`setup_architecture.md`).
- `downloads\` — temporary download artifacts.
- `outputs\` — generated media/output products.
- `venv\` — local Python environment.
- `tasks\` — task index and per-task files.
- `audits\` — governance and implementation audits.

## Ownership and source-of-truth notes

- Setup and launch behavior: source-of-truth is `setup_and_run.ps1`.
- Model registry: source-of-truth is `config/model_registry.json`.
- UI/API behavior and generation controls: source-of-truth is `run_gradio_ui.py`.
- New installer behavior and user flow: source-of-truth is `README.md`, `setup_and_run.ps1`, and `start_zimage.bat`.
- Future governance artifacts and process updates live at:
  - `Agents.md`
  - `tasks/TASK_INDEX.md`
  - `Audits_index.md`

## Current architecture highlights

- Two-stage setup:
  - Setup wizard executes when config is missing/incomplete or reset.
  - Normal launches use existing config and start UI directly.
- Hardware-aware profile behavior currently implemented:
  - NVIDIA path prefers CUDA assets.
  - Non-NVIDIA currently defaults to CPU-safe behavior unless manual override.
- Backend compatibility rules:
  - Prefer `sd-cli.exe` when auto-installed.
  - Accept legacy `sd.exe` for fallback compatibility.
  - Do not mix backend DLL and executable versions.

