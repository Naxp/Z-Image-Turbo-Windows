# Setup Architecture Audit and Redesign

## Current Friction Points

- Users previously had to manually download stable-diffusion.cpp, extract the archive, and copy binaries into `sd_bin`.
- NVIDIA users also had to discover and download the separate CUDA runtime archive, then copy DLLs manually.
- The VAE used to require manual placement. The installer now uses the public Z-Image Turbo VAE mirror instead.
- The old setup asked for a VRAM tier every time the launcher ran, even when the user had already completed setup.
- Model URLs were hardcoded inside `setup_and_run.ps1`, which made future model additions harder to maintain.
- Setup and launch were mixed together. A normal launch could still stop on setup prompts.
- Advanced users had no persistent config for custom choices.

## New Two-Stage Flow

Stage 1: setup wizard

- Runs only when `config/setup_config.json` is missing, reset, or incomplete.
- Creates folders, detects hardware, recommends a profile, installs Python dependencies, downloads required assets, and saves config.
- Beginner mode uses the recommended profile automatically.
- Advanced mode is available through `.\setup_and_run.ps1 -AdvancedSetup`.
- Reset is available through `.\setup_and_run.ps1 -ResetSetup`.

Stage 2: normal launch

- Loads `config/setup_config.json`.
- Verifies required backend, model, VAE, and LLM files exist.
- Writes the selected model to `models/zimage/selected_model.txt`.
- Starts the Gradio app without asking repeated questions.

## Hardware Detection Strategy

- NVIDIA: use `nvidia-smi` to detect GPU name, VRAM, CUDA availability, and compute capability.
- AMD: detect Radeon adapters through Windows display adapters. Current Windows beginner fallback is CPU backend unless a future stable-diffusion.cpp Vulkan Windows build is promoted as reliable for this app.
- Intel: detect Intel/Arc adapters through Windows display adapters. Current beginner fallback is CPU backend; future support can add Vulkan/SYCL once a stable Windows binary path is reliable.
- CPU-only: use the AVX2 Windows backend by default.

Current stable-diffusion.cpp releases provide Windows CUDA and CPU/AVX builds, plus Linux ROCm and Vulkan builds. The project also supports multiple build backends upstream, but this app should only auto-install backends that are beginner-safe on Windows.

References:

- stable-diffusion.cpp README: https://github.com/leejet/stable-diffusion.cpp
- stable-diffusion.cpp releases: https://github.com/leejet/stable-diffusion.cpp/releases

## Profile Recommendation

- `ultra_low_vram`: NVIDIA GPUs below 6GB, default Q4 model.
- `balanced`: NVIDIA GPUs from 6GB to below 10GB, default Q6 model.
- `high_end`: NVIDIA GPUs 10GB+, default Q8 model.
- `cpu_only`: non-NVIDIA or no supported dedicated GPU, default Q4 model.

Users can override the recommendation in advanced setup.

## Download Manager

- Uses `curl.exe` first with resume, retry, retry-all-errors, timeouts, and progress.
- Falls back to `Invoke-WebRequest`.
- Supports optional SHA256 validation when a registry entry or release notes provide a checksum.
- Downloads backend archives to `downloads/backend`.
- Downloads model assets from `config/model_registry.json`.
- Detects corrupted files through SHA256 when hashes are present.
- Recovers from interrupted downloads through curl resume support.

## Backend Strategy

Beginner mode:

- If no backend exists, the setup wizard downloads stable-diffusion.cpp automatically.
- NVIDIA uses the latest Windows CUDA 12 asset plus the matching `cudart` runtime asset.
- CPU fallback uses the latest Windows AVX2 asset.

Advanced mode:

- Users can choose manual backend management.
- The launcher accepts existing `sd-cli.exe` or legacy `sd.exe` in `sd_bin`.
- Future custom backend paths can be added to `setup_config.json` without changing the UI app.

AMD and Intel note:

- Upstream stable-diffusion.cpp has multi-backend support, including Vulkan/SYCL/ROCm build paths.
- Current beginner automation chooses CPU fallback on Windows AMD/Intel because the official release path is less straightforward for beginner Windows users than NVIDIA CUDA.
- Future Windows Vulkan support should be added only after testing a stable release asset on AMD and Intel hardware.

## Model Registry

The registry lives at `config/model_registry.json`.

It defines:

- model id
- display name
- type
- filename
- download URL
- optional SHA256
- recommended profile
- approximate size

Future additions should be added to the registry instead of hardcoded in the setup script.

## Migration Plan

- Existing users with files already in place will be detected as complete after the first config is saved.
- The old selected model file is still supported through `models/zimage/selected_model.txt`.
- Existing manually installed backends remain valid.
- Users who want the new wizard can run `.\setup_and_run.ps1 -ResetSetup`.

## Setup UI Mockups

Console setup wizard:

```text
Z-Image Turbo Windows

Detected hardware
  GPU: NVIDIA GeForce RTX 3050 Laptop GPU
  VRAM: 4.0 GB
  CUDA: available

Recommended profile
  Ultra Low VRAM
  Model: Z-Image Turbo Q4_0

Installing
  [ok] Python environment
  [ok] stable-diffusion.cpp backend
  [ok] Z-Image Turbo model
  [ok] VAE
  [ok] Qwen text encoder

Setup complete. Future launches will start immediately.
```

Advanced setup:

```text
Advanced Setup

Profile
  1. Ultra Low VRAM
  2. Balanced
  3. High-End
  4. CPU Only

Backend
  1. Automatic download/install
  2. Manual binaries in sd_bin
```

Future settings page:

```text
Settings

Hardware
  Detected GPU: ...
  Profile: [Ultra Low VRAM v]

Models
  Diffusion model: [Z-Image Turbo Q4_0 v]
  VAE: installed
  Text encoder: installed

Backend
  Mode: [Automatic v]
  Path: sd_bin/sd-cli.exe

[Save] [Reset Setup] [Check for Updates]
```

## Ranked Roadmap

1. High impact / low difficulty: add a settings panel that shows current profile, selected model, backend path, and setup status.
2. High impact / medium difficulty: add a model manager page that reads `config/model_registry.json`.
3. Medium impact / medium difficulty: add backend update detection using the latest stable-diffusion.cpp release tag.
4. Medium impact / high difficulty: add tested Windows Vulkan support for AMD/Intel once backend assets are beginner-safe.
5. Medium impact / low difficulty: add model SHA256 values to the registry when maintained hashes are available.
6. Lower impact / medium difficulty: add optional mirror URLs for large model downloads.
