# Z-Image Turbo - One-Click Windows Installer (Low VRAM)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Platform: Windows](https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows)](https://www.microsoft.com/windows)
[![Built with Gradio](https://img.shields.io/badge/Built%20with-Gradio-FFD21F?logo=gradio)](https://gradio.app)
[![Low VRAM Support](https://img.shields.io/badge/VRAM-4GB+-green)](https://github.com/leejet/stable-diffusion.cpp)

A beginner-friendly Windows package to run **Z-Image Turbo (GGUF)** locally with a simple **Gradio Web UI**.

Target users:

- Low-VRAM NVIDIA GPUs (including 4GB)
- Anyone who wants free local image generation without complex tools

## Table of Contents
- [Features](#features)
- [Quickstart](#quickstart)
- [Requirements](#requirements)
- [Running the Setup](#running-the-setup)
- [Setup Wizard and Saved Configuration](#setup-wizard-and-saved-configuration)
- [Why Backend Setup Is Hybrid](#why-backend-setup-is-hybrid)
- [Where to Get the Executable (Windows)](#where-to-get-the-executable-windows)
- [NVIDIA GPU / CUDA Notes](#nvidia-gpu--cuda-notes)
- [Low VRAM Workflow](#low-vram-workflow)
- [Generation Queue](#generation-queue)
- [LoRA Support](#lora-support)
- [Experimental Img2Img](#experimental-img2img)
- [Experimental Inpainting](#experimental-inpainting)
- [Downloads](#what-the-installer-downloads-and-what-is-manual)
- [Manual Download Sources](#manual-download-sources)
- [Troubleshooting](#troubleshooting)
- [Credits](#credits--upstream)

## Features

- One-click installer: `start_zimage.bat`
- First-run setup wizard that saves configuration and does not ask repeated questions
- Automatic hardware detection and profile recommendation
- Creates an isolated Python `venv` automatically
- Downloads required model weights, VAE, and text encoder automatically
- Gradio Web UI with prompt, resolution, seed tools, CFG, timer, stop button, and recent output gallery
- Background generation queue: add new prompts while another image is still generating
- Queue status table with running, queued, done, failed, stopped, and stopping states
- Low VRAM presets for 4GB, 6-8GB, and 10GB+ NVIDIA workflows
- LoRA support through `models\loras\`
- Experimental img2img using stable-diffusion.cpp `--init-img` and `--strength`, with dedicated output-size controls
- Experimental inpainting using stable-diffusion.cpp `--init-img` and `--mask`
- Example prompt presets for text-to-image, img2img, and inpainting
- Ready-link launcher: the URL is shown only after the local Gradio server responds
- Hybrid backend setup: automatic for beginners, manual override for advanced users

## Quickstart

1. Download / clone this repo.
2. Double-click `start_zimage.bat`.
3. The first-run wizard installs missing files and saves configuration.
4. Wait until the terminal says **Ready. Open this link:**.
5. Open the UI:
   - http://127.0.0.1:9000

## Requirements

- Windows 10/11 (64-bit)
- Python 3.10+
- Microsoft Visual C++ Redistributable 2015-2022 (x64)
- NVIDIA GPU users (optional)
  - Latest NVIDIA driver recommended

## Running the setup

Double-click:

- `start_zimage.bat`

The installer will:

- Create a Python virtual environment (`venv\`)
- Detect your hardware
- Recommend a profile automatically
- Download required files
- Save setup state in `config\setup_config.json`
- Start the Gradio UI and print http://127.0.0.1:9000 only after the page is reachable

After setup is complete, future launches start the app directly.

## Setup Wizard and Saved Configuration

The setup now uses a two-stage flow:

- First launch: runs the setup wizard, detects hardware, installs missing files, and saves configuration.
- Normal launch: loads saved configuration and starts the app without asking setup questions again.

Useful commands:

```powershell
.\setup_and_run.ps1
.\setup_and_run.ps1 -AdvancedSetup
.\setup_and_run.ps1 -ResetSetup
.\setup_and_run.ps1 -SetupOnly
```

Most users do not need these commands. They are mainly for reset, setup verification, and advanced setup. The normal beginner flow is still double-clicking `start_zimage.bat`.

Saved configuration:

- `config\setup_config.json`

Model registry:

- `config\model_registry.json`

The registry keeps model URLs and profile defaults outside the setup script so future models can be added more easily.

Keep the terminal window open while it downloads models.

## Why backend setup is hybrid

This project can now download stable-diffusion.cpp backend files automatically during beginner setup. Advanced users can still manage binaries manually.

The app uses **stable-diffusion.cpp** as the inference backend. Older releases used one main executable named `sd.exe`. Newer releases split this into files such as `sd-cli.exe`, `sd-server.exe`, and `stable-diffusion.dll`.

If you followed an older tutorial for this project that says to copy `sd.exe`, that was correct for the old stable-diffusion.cpp release. For current releases, use `sd-cli.exe` instead. The installer and UI will automatically detect either `sd-cli.exe` or legacy `sd.exe`.

Beginner mode:

- Automatically downloads the recommended stable-diffusion.cpp backend when missing.

Advanced mode:

- Allows manual backend placement in `sd_bin\`.

## Where to get the executable (Windows)

Download a Windows build from the **stable-diffusion.cpp Releases** page.

Recommended assets (names include a commit/hash):

- NVIDIA executable package: `sd-...-bin-win-cuda12-x64.zip`
- NVIDIA CUDA runtime/DLL package: `cudart-sd-bin-win-cu12-x64.zip`
- CPU only: `sd-...-bin-win-x64.zip`

For NVIDIA GPUs, use the CUDA 12 Windows x64 build. Recent builds may look like:

- `sd-master-90e87bc-bin-win-cuda12-x64.zip`
- `cudart-sd-bin-win-cu12-x64.zip`

The `sd-...-bin-win-cuda12-x64.zip` file usually contains the stable-diffusion.cpp program files, such as:

- `sd-cli.exe`
- `sd-server.exe`
- `stable-diffusion.dll`

The larger `cudart-sd-bin-win-cu12-x64.zip` file contains the CUDA runtime DLLs required by the CUDA build. It commonly includes files such as CUDA/cuBLAS DLLs. Copy those DLL files into `sd_bin\` too.

Install steps:

1. Download the latest `sd-...-bin-win-cuda12-x64.zip`.
2. Extract it and copy these files into `sd_bin\`:
   - `sd-cli.exe`
   - `sd-server.exe`
   - `stable-diffusion.dll`
3. Download the matching `cudart-sd-bin-win-cu12-x64.zip`.
4. Extract it and copy its `*.dll` files into `sd_bin\`.
5. If you are using an older stable-diffusion.cpp build that only has `sd.exe`, copy it to `sd_bin\sd.exe`.

Important:

- New users should copy both the executable package files and the CUDA runtime DLL package files.
- Existing users who already have the older CUDA DLLs may only need to replace `sd-cli.exe`, `sd-server.exe`, and `stable-diffusion.dll` from the newer executable package.
- If CUDA fails, crashes, or your dedicated GPU is not used, refresh the CUDA runtime DLLs from the matching `cudart-sd-bin-win-cu12-x64.zip`.
- Do not mix `stable-diffusion.dll` from one release with `sd-cli.exe` from another release.

## NVIDIA GPU / CUDA notes

If generation works but your dedicated NVIDIA GPU is not being used, your stable-diffusion.cpp files are probably too old or you copied a CPU-only build.

Use the latest Windows CUDA 12 x64 build from stable-diffusion.cpp. For example, recent working assets are:

- `sd-master-90e87bc-bin-win-cuda12-x64.zip`
- `cudart-sd-bin-win-cu12-x64.zip`

After downloading it:

1. Stop the Gradio app.
2. Replace `sd-cli.exe`, `sd-server.exe`, and `stable-diffusion.dll` in `sd_bin\` from the `sd-...-bin-win-cuda12-x64.zip` file.
3. If you are setting up fresh, or if CUDA still does not work, also copy the DLLs from `cudart-sd-bin-win-cu12-x64.zip` into `sd_bin\`.
4. Start the app again with `start_zimage.bat`.

The important migration point for old users is this: the old tutorial used `sd.exe` because stable-diffusion.cpp used to ship that way. New stable-diffusion.cpp releases use `sd-cli.exe` plus `stable-diffusion.dll`, so updating those files is what fixes many NVIDIA GPU detection/utilization problems.

## Low VRAM workflow

The UI includes a **Low VRAM Mode** section:

- `4GB (safest)` enables CPU offload, diffusion flash attention, VAE tiling, and direct VAE convolution. There is also an optional checkbox to keep the text encoder on CPU.
- `6-8GB (balanced)` enables CPU offload and diffusion flash attention. You can optionally enable VAE tiling for larger resolutions.
- `10GB+ (fastest)` keeps the command lighter and focuses on faster GPU usage.

The app also saves a metadata `.txt` file next to each generated image, including the prompt, seed, command, selected LoRAs, and timing. The UI shows the last command and a recent output gallery for easier testing.

## Generation queue

The app now uses a background generation queue. This means you can:

1. Start a generation.
2. Change the prompt, seed, LoRA, size, or other settings.
3. Click **Generate** again while the first image is still running.
4. The new request is added to the queue and starts automatically when the current job finishes.

The **Generation Queue** table shows each job status:

- `queued` means waiting for its turn.
- `running` means stable-diffusion.cpp is currently generating it.
- `done` means the image finished successfully.
- `failed` means the job hit an error.
- `stopping` / `stopped` means the stop button was used.

The queue runs one job at a time to protect low-VRAM GPUs. It is managed by the local Python app, not by the browser tab, so refreshing the page should not stop the backend queue. The UI polls the backend state and restores the queue table after a reload.

Use **Clear Finished Queue Items** to remove completed, failed, or stopped rows from the table. It does not delete generated images.

## LoRA support

The setup now automatically creates this folder:

- `models\loras\`

To use a LoRA:

1. Download a Z-Image-compatible LoRA from Civitai or use your own trained LoRA.
2. Put the `.safetensors` file in:
   - `models\loras\`
3. Start or refresh the UI.
4. In the LoRA section, click **Refresh** if needed.
5. Check the LoRA you want to use and set the LoRA strength.
6. Generate as usual.

The UI passes selected LoRAs to stable-diffusion.cpp using prompt tags and the configured LoRA model directory.

## Experimental Img2Img

The UI includes an **Experimental Img2Img** tab. This uses stable-diffusion.cpp options:

- `--init-img`
- `--strength`

To try it:

1. Enable img2img in the tab.
2. Write the img2img prompt in that tab.
3. Upload an input image.
4. Choose the img2img output size:
   - Keep **Auto match uploaded image aspect ratio** enabled for the easiest workflow.
   - A 16:9 upload will automatically select a 16:9 output preset, a portrait upload will select a portrait preset, and a square upload will stay square.
   - You can turn auto mode off and manually choose the img2img resolution preset, width, and height.
5. Set img2img steps, guidance, and strength:
   - `0.30-0.45` preserves strongly and may show little change.
   - `0.50-0.60` is a better practical range for visible Z-Image Turbo edits.
   - `0.65+` can drift heavily or become a new image.
6. Generate as usual.

For small edits such as color changes, use the negative prompt to block unwanted scene changes such as `tree`, `branch`, or `outdoor`. The app copies and resizes the uploaded image into a local temp folder before generation so the backend can read it reliably. Img2img support depends on the installed stable-diffusion.cpp build and Z-Image Turbo GGUF behavior, so it is labeled experimental.

## Experimental Inpainting

The UI includes an **Inpaint / Selective Edit** tab. This uses stable-diffusion.cpp options:

- `--init-img`
- `--mask`
- `--strength`

To try it:

1. Enable inpainting.
2. Upload a source image in the editor.
3. Paint over the area you want to edit.
4. Write the inpaint prompt and optional negative prompt.
5. Set steps, guidance, strength, and seed.
6. Generate as usual.

This is experimental with Z-Image Turbo. The backend accepts the mask path, but Z-Image Turbo is not a dedicated Photoshop-style inpainting model, so results may behave like masked img2img rather than perfect local edits.

## What the installer downloads (and what is manual)

Automatic during beginner setup:

- Z-Image Turbo GGUF (diffusion model)
- VAE: `models\vae\ae.safetensors`
- Qwen GGUF (LLM/text encoder)
- Recommended stable-diffusion.cpp backend files when missing:
  - Current NVIDIA build: `sd-cli.exe`, `sd-server.exe`, `stable-diffusion.dll`
  - CUDA runtime DLLs from `cudart-sd-bin-win-cu12-x64.zip`
  - CPU build files when using the CPU profile

Manual / advanced override:

- stable-diffusion.cpp backend files:
  - Current NVIDIA build: `sd-cli.exe`, `sd-server.exe`, `stable-diffusion.dll`
  - CUDA runtime DLLs from `cudart-sd-bin-win-cu12-x64.zip`
  - Legacy builds: `sd.exe`
- Any model file you want to replace or pin manually

Manual download sources:

- Z-Image Turbo GGUF:
  - https://huggingface.co/leejet/Z-Image-Turbo-GGUF/tree/main
- VAE (`ae.safetensors`):
  - https://huggingface.co/airesearch-official/z-image-turbo-vae/tree/main
- Qwen GGUF:
  - https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/tree/main

## Troubleshooting

If the browser says "This site can't be reached":

- Wait for the terminal to print **Ready. Open this link:** before opening the URL.
- The launcher starts Gradio first, checks the local page, and only then prints the ready URL.
- If the ready message never appears, close the terminal and run `start_zimage.bat` again.

If the queue table looks outdated:

- The UI refreshes queue status from the local backend every second.
- Reloading the browser tab should restore the queue table without stopping the backend queue.
- If a job fails, check the **Status / Logs** box and the `.txt` metadata file next to the output image.
- Use **Clear Finished Queue Items** only to clean completed/failed/stopped rows.

If generation fails or the executable crashes:

- For current CUDA builds, make sure `sd-cli.exe`, `sd-server.exe`, and `stable-diffusion.dll` came from the same `sd-...-bin-win-cuda12-x64.zip` package.
- For fresh installs, also copy the CUDA runtime DLLs from `cudart-sd-bin-win-cu12-x64.zip`.
- If you upgraded from an older working setup and only GPU usage was broken, replacing `sd-cli.exe`, `sd-server.exe`, and `stable-diffusion.dll` may be enough.
- If CUDA still fails, crashes, or your NVIDIA GPU is not used, refresh the CUDA runtime DLLs from `cudart-sd-bin-win-cu12-x64.zip`.
- Install Microsoft Visual C++ Redistributable 2015-2022 (x64).
- If the CUDA build fails, try the CPU build to confirm everything else works.
- Common crash code:
  - `3221225781` (`0xC0000135`) typically means a missing DLL/runtime dependency.

If model downloads fail in the installer but the same URL works in your browser:

- Your network (proxy/firewall/antivirus) may block programmatic downloads from Hugging Face/CDN.
- The installer prefers `curl.exe` (resume + retries + progress bar). If that is unavailable, it falls back to `Invoke-WebRequest`.
- If it still fails, use the manual download links above and place the files into the indicated `models\...` folders.

## Credits / Upstream

This project is a Windows-friendly wrapper around the excellent **stable-diffusion.cpp** backend:

- https://github.com/leejet/stable-diffusion.cpp

Z-Image weights and related resources are hosted on Hugging Face by their respective authors.

