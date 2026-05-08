# setup_and_run.ps1 - One click setup for Z-Image Turbo (GGUF) with minimal UI
# Place this file in ZImage-Windows and double-click start_zimage.bat to run.

Write-Host '=== Z-Image Turbo: One-Click (4/6/10GB) — Minimal UI ==='
Write-Host ''

# 0. Basic checks
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Python not found. Install Python 3.10+ from https://python.org and re-run."
    exit 1
}

function Download-FileWithProgress {
    param(
        [Parameter(Mandatory=$true)][string]$Url,
        [Parameter(Mandatory=$true)][string]$Destination,
        [Parameter(Mandatory=$true)][string]$Label
    )

    try {
        # Hugging Face downloads can fail on older TLS defaults
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    } catch {
        # ignore
    }

    $dir = Split-Path -Parent $Destination
    if (!(Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }

    try {
        $curlCmd = Get-Command curl.exe -ErrorAction SilentlyContinue
        if ($curlCmd -and $curlCmd.Source) {
            $curl = $curlCmd.Source
            Write-Host ("{0} - downloading via curl (with resume/retry)..." -f $Label)

            $args = @(
                '--location',
                '--fail',
                '--retry', '10',
                '--retry-delay', '5',
                '--retry-all-errors',
                '--connect-timeout', '30',
                '--speed-time', '30',
                '--speed-limit', '10240',
                '--progress-bar',
                '--header', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                '--header', 'Accept: */*'
            )

            if (Test-Path $Destination) {
                $args += @('--continue-at', '-')
            }

            $args += @('--output', $Destination, $Url)

            & $curl @args
            if ($LASTEXITCODE -ne 0) {
                throw "curl failed with exit code $LASTEXITCODE"
            }
            return
        }
    } catch {
        Write-Host "`nPrimary download method (curl) failed. Falling back..."
        Write-Host ("Reason: {0}" -f $_.Exception.Message)
    }

    try {
        Write-Host ("{0} - downloading via Invoke-WebRequest (fallback)..." -f $Label)
        $headers = @{
            'User-Agent' = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            'Accept' = '*/*'
        }
        Invoke-WebRequest -Uri $Url -OutFile $Destination -Headers $headers -MaximumRedirection 10 -ProxyUseDefaultCredentials
        return
    } catch {
        $msg = $_.Exception.Message
        try {
            if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
                $msg = "HTTP {0} - {1}" -f [int]$_.Exception.Response.StatusCode, $_.Exception.Response.StatusDescription
            }
        } catch {
            # ignore
        }
        throw $msg
    }
}

# 1. Create folders
$root = $PSScriptRoot
$sdBin = Join-Path $root "sd_bin"
$modelsDir = Join-Path $root "models"
$zimageDir = Join-Path $modelsDir "zimage"
$vaeDir = Join-Path $modelsDir "vae"
$llmDir = Join-Path $modelsDir "llm"
$loraDir = Join-Path $modelsDir "loras"
if (!(Test-Path $sdBin)) { New-Item -ItemType Directory -Path $sdBin | Out-Null }
if (!(Test-Path $modelsDir)) { New-Item -ItemType Directory -Path $modelsDir | Out-Null }
if (!(Test-Path $zimageDir)) { New-Item -ItemType Directory -Path $zimageDir | Out-Null }
if (!(Test-Path $vaeDir)) { New-Item -ItemType Directory -Path $vaeDir | Out-Null }
if (!(Test-Path $llmDir)) { New-Item -ItemType Directory -Path $llmDir | Out-Null }
if (!(Test-Path $loraDir)) { New-Item -ItemType Directory -Path $loraDir | Out-Null }

Write-Host 'Folders prepared:'
Write-Host (" - sd_bin  : {0}" -f $sdBin)
Write-Host (" - models/zimage  : {0}" -f $zimageDir)
Write-Host (" - models/vae  : {0}" -f $vaeDir)
Write-Host (" - models/llm  : {0}" -f $llmDir)
Write-Host ''

# 2. Ask user about VRAM tier
Write-Host 'Choose your GPU VRAM tier (pick the number):'
Write-Host ' 1) 4 GB  (Fastest, smallest model, recommended for RTX 3050 4GB)'
Write-Host ' 2) 6-8 GB  (Better quality)'
Write-Host ' 3) 10+ GB  (Highest quality - not recommended for 4GB)'
$choice = Read-Host 'Enter 1, 2 or 3'

switch ($choice) {
    "1" {
        $moshort = "4GB"
        $model_name = "z_image_turbo_Q4_0.gguf"
        # Example public URL placeholder - replace if you prefer another source.
        $model_url = "https://huggingface.co/leejet/Z-Image-Turbo-GGUF/resolve/main/z_image_turbo-Q4_0.gguf"
    }
    "2" {
        $moshort = "6-8GB"
        $model_name = "z_image_turbo_Q6_K.gguf"
        $model_url = "https://huggingface.co/leejet/Z-Image-Turbo-GGUF/resolve/main/z_image_turbo-Q6_K.gguf"
    }
    "3" {
        $moshort = "10+GB"
        $model_name = "z_image_turbo_Q8_0.gguf"
        $model_url = "https://huggingface.co/leejet/Z-Image-Turbo-GGUF/resolve/main/z_image_turbo-Q8_0.gguf"
    }
    default {
        Write-Host "Invalid choice. Exiting."
        exit 1
    }
}

Write-Host ''
Write-Host ("You picked: {0}" -f $moshort)
Write-Host ("Model will be saved as: {0}" -f $model_name)
Write-Host ''

# 3. Create venv (if missing)
$venv = Join-Path $root "venv"
if (!(Test-Path $venv)) {
    Write-Host "Creating Python virtual environment..."
    python -m venv venv
} else {
    Write-Host "Virtual environment already exists (venv/)."
}

# 4. Use venv python directly (avoids PowerShell execution policy issues with Activate.ps1)
$venvPython = Join-Path $venv "Scripts\python.exe"
if (!(Test-Path $venvPython)) {
    Write-Host "ERROR: venv python not found at: $venvPython"
    exit 1
}

# 5. Upgrade pip safely
Write-Host "Upgrading pip..."
& $venvPython -m pip install --upgrade pip

# 6. Install Python deps for minimal UI
Write-Host 'Installing Python requirements (gradio, requests)...'
& $venvPython -m pip install gradio requests tqdm

# 7. Check for sd binary (sd-cli.exe or sd.exe)
$sdCliExe = Join-Path $sdBin "sd-cli.exe"
$sdOldExe = Join-Path $sdBin "sd.exe"

if ((Test-Path $sdCliExe)) {
    Write-Host "Found sd-cli.exe (recommended)"
    $sdexe = $sdCliExe
} elseif ((Test-Path $sdOldExe)) {
    Write-Host "Found sd.exe (legacy)"
    $sdexe = $sdOldExe
} else {
    Write-Host ""
    Write-Host "IMPORTANT: A stable-diffusion.cpp Windows binary is REQUIRED to run the model."
    Write-Host "Please download from the official stable-diffusion.cpp releases:"
    Write-Host "    https://github.com/leejet/stable-diffusion.cpp/releases"
    Write-Host ""
    Write-Host "Recommended: Extract 'sd-cli.exe' (or 'sd.exe' from older releases) to:"
    Write-Host "    $sdBin"
    Write-Host ""
    Write-Host "Note: Recent releases use 'sd-cli.exe'. Older releases use 'sd.exe'. Either will work."
    Write-Host ""
    Write-Host "Press Enter after you have placed the executable, or Ctrl+C to exit."
    Read-Host
}

if (!(Test-Path $sdexe)) {
    Write-Host "Executable still not found in $sdBin. Exiting."
    exit 1
}

# 7b. Sanity-check executable (common crash is missing DLL / wrong build)
Write-Host "`nChecking executable..."
try {
    & $sdexe --help | Out-Null
} catch {
    # swallow - we will check exit code below
}
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Executable failed to start (exit code: $LASTEXITCODE)."
    Write-Host "This usually means a missing dependency or wrong build." 
    Write-Host "" 
    Write-Host "Please check:" 
    Write-Host " 1) You extracted the release ZIP and copied the executable AND any .dll files into:"
    Write-Host "    $sdBin"
    Write-Host " 2) Microsoft Visual C++ Redistributable 2015-2022 (x64) is installed"
    Write-Host " 3) If you downloaded a CUDA build, your NVIDIA driver supports that CUDA version"
    Write-Host " 4) Try the CPU-only ZIP (sd-...-bin-win-x64.zip) to confirm it works on your PC"
    Write-Host ""
    Write-Host "Press Enter to exit."
    Read-Host
    exit 1
}

# 8. Download the chosen quantized GGUF model if it does not exist
$dest = Join-Path $zimageDir $model_name
if (Test-Path $dest) {
    Write-Host "Model already exists: $dest"
} else {
    Write-Host "`nDownloading quantized model (this can be several GB)."
    Write-Host "Source URL (if it fails, open link in browser and download manually):"
    Write-Host "  $model_url`n"
    try {
        Download-FileWithProgress -Url $model_url -Destination $dest -Label ("Downloading Z-Image model: {0}" -f $model_name)
        Write-Host "Downloaded model to: $dest"
    } catch {
        Write-Host "Automatic download failed. Please download the file manually and place it into:"
        Write-Host "   $dest"
        Write-Host "Then press Enter to continue."
        Read-Host
        if (!(Test-Path $dest)) {
            Write-Host "Model not found. Exiting."
            exit 1
        }
    }
}

# 9. Download VAE + LLM (required by Z-Image pipeline)
$vaeName = "ae.safetensors"
$vaeUrl = "https://huggingface.co/black-forest-labs/FLUX.1-schnell/resolve/main/ae.safetensors"
$vaePath = Join-Path $vaeDir $vaeName

$llmName = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
$llmUrl = "https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
$llmPath = Join-Path $llmDir $llmName

if (Test-Path $vaePath) {
    Write-Host "VAE already exists: $vaePath"
} else {
    Write-Host "`nVAE is required but may be restricted for non-logged-in downloads on Hugging Face."
    Write-Host "Please download it manually (login may be required):"
    Write-Host "  $vaeUrl"
    Write-Host "Save it to:"
    Write-Host "  $vaePath"
    Write-Host "`nPress Enter after you have placed ae.safetensors, or Ctrl+C to exit."
    Read-Host
    if (!(Test-Path $vaePath)) {
        Write-Host "VAE not found. Exiting."
        exit 1
    }
}

if (Test-Path $llmPath) {
    Write-Host "LLM already exists: $llmPath"
} else {
    Write-Host "`nDownloading LLM (Qwen): $llmName"
    Write-Host "Source URL (if it fails, open link in browser and download manually):"
    Write-Host "  $llmUrl`n"
    try {
        Download-FileWithProgress -Url $llmUrl -Destination $llmPath -Label ("Downloading Qwen LLM: {0}" -f $llmName)
        Write-Host "Downloaded LLM to: $llmPath"
    } catch {
        Write-Host "Automatic download failed. Please download the file manually and place it into:"
        Write-Host "   $llmPath"
        Write-Host "Then press Enter to continue."
        Read-Host
        if (!(Test-Path $llmPath)) {
            Write-Host "LLM not found. Exiting."
            exit 1
        }
    }
}

# 10. (Re)create minimal Gradio UI script
$uiScript = Join-Path $root "run_gradio_ui.py"
Write-Host "Writing run_gradio_ui.py..."
$py = @'
import os, subprocess, shlex, uuid, time
import re
from pathlib import Path
import gradio as gr

ROOT = Path(__file__).parent
SD_BIN_DIR = ROOT / "sd_bin"
SD_EXE = str(SD_BIN_DIR / "sd-cli.exe")
MODEL_PATH = str(ROOT / "models" / "zimage" / "__MODEL_NAME__")
LORA_DIR = ROOT / "models" / "loras"
OUTDIR = str(ROOT / "outputs")
os.makedirs(OUTDIR, exist_ok=True)
os.makedirs(LORA_DIR, exist_ok=True)


def find_sd_executable():
    """Auto-detect available stable-diffusion executable."""
    candidates = [
        ("sd-cli.exe", "sd-cli.exe (recommended)"),
        ("sd.exe", "sd.exe (legacy)"),
    ]
    for exe_name, label in candidates:
        exe_path = SD_BIN_DIR / exe_name
        if exe_path.exists():
            return str(exe_path), label
    return None, None


SD_EXE, SD_EXE_LABEL = find_sd_executable()

DEFAULT_VAE_PATH = str(ROOT / "models" / "vae" / "ae.safetensors")
DEFAULT_LLM_PATH = str(ROOT / "models" / "llm" / "Qwen3-4B-Instruct-2507-Q4_K_M.gguf")

FIRST_RUN = True

RES_PRESETS = [
    ("1:1 (256x256)", 256, 256),
    ("1:1 (512x512)", 512, 512),
    ("1:1 (768x768)", 768, 768),
    ("1:1 (1024x1024)", 1024, 1024),
    ("16:9 (640x384)", 640, 384),
    ("16:9 (896x512)", 896, 512),
    ("16:9 (1024x576)", 1024, 576),
    ("9:16 (384x640)", 384, 640),
    ("9:16 (512x896)", 512, 896),
    ("9:16 (576x1024)", 576, 1024),
    ("4:3 (640x480)", 640, 480),
    ("4:3 (768x576)", 768, 576),
    ("3:2 (768x512)", 768, 512),
    ("2:3 (512x768)", 512, 768),
]

SIZE_OPTIONS = sorted({s for _, w, h in RES_PRESETS for s in (w, h)})

def get_lora_list():
    """List available LoRA files in the loras directory."""
    if not LORA_DIR.exists():
        return []
    return [f.name for f in LORA_DIR.glob("*.safetensors")]

def apply_preset(preset_label):
    for name, w, h in RES_PRESETS:
        if name == preset_label:
            return w, h
    return gr.update(), gr.update()

def gen_image(prompt, width, height, steps, seed, cfg_scale, vae_path, llm_path, selected_loras, lora_strength):
    if SD_EXE is None:
        available = list(SD_BIN_DIR.glob("*.exe")) if SD_BIN_DIR.exists() else []
        if available:
            exe_list = ", ".join([f.name for f in available])
            yield None, f"No supported executable found in sd_bin/. Found: {exe_list}\n\nExpected: sd-cli.exe or sd.exe\n\nDownload from: https://github.com/leejet/stable-diffusion.cpp/releases"
        else:
            yield None, f"sd_bin folder not found. Create folder: {SD_BIN_DIR}"
        return

    uid = uuid.uuid4().hex[:8]
    out_file = os.path.join(OUTDIR, f"out_{uid}.png")
    if not os.path.isfile(SD_EXE):
        yield None, f"Executable not found: {SD_EXE}"
        return
    if not os.path.isfile(MODEL_PATH):
        yield None, f"Model not found: {MODEL_PATH}"
        return
    vae_path = (vae_path or "").strip() or DEFAULT_VAE_PATH
    llm_path = (llm_path or "").strip() or DEFAULT_LLM_PATH
    if not os.path.isfile(vae_path):
        yield None, f"VAE not found: {vae_path}"
        return
    if not os.path.isfile(llm_path):
        yield None, f"LLM (text encoder) not found: {llm_path}"
        return

    # Append LoRA tags to prompt
    final_prompt = prompt
    if selected_loras:
        for lora in selected_loras:
            lora_name = Path(lora).stem
            final_prompt += f" <lora:{lora_name}:{lora_strength}>"

    # RNG cuda to force GPU usage if possible
    cmd = [
        SD_EXE,
        "--diffusion-model", MODEL_PATH,
        "--vae", vae_path,
        "--llm", llm_path,
        "--lora-model-dir", str(LORA_DIR),
        "-p", final_prompt,
        "--cfg-scale", str(cfg_scale),
        "--steps", str(steps),
        "-H", str(height), "-W", str(width),
        "-o", out_file,
        "--seed", str(seed),
        "--rng", "cuda"
    ]
    
    cmd_str = " ".join([f'"{c}"' if " " in str(c) else str(c) for c in cmd])
    print("Running:", cmd_str)
    
    yield None, f"Starting generation...\nCommand: {cmd_str}"

    t0 = time.perf_counter()
    # Using Popen for real-time output
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )

    full_log = ""
    for line in proc.stdout:
        print(line, end="")
        full_log += line
        yield None, full_log.strip()

    proc.wait()
    t1 = time.perf_counter()
    elapsed = t1 - t0

    reported = []
    m = re.search(r"generate_image completed in\s+([0-9.]+)s", full_log)
    if m: reported.append(f"sd.exe generate_image: {m.group(1)}s")
    m = re.search(r"sampling completed, taking\s+([0-9.]+)s", full_log)
    if m: reported.append(f"sd.exe sampling: {m.group(1)}s")
    m = re.search(r"loading tensors completed, taking\s+([0-9.]+)s", full_log)
    if m: reported.append(f"sd.exe model load: {m.group(1)}s")

    timing_line = f"Wall-clock time: {elapsed:.2f}s"
    if reported:
        timing_line += "\n" + "\n".join(reported)

    final_log = (timing_line + "\n\n" + full_log.strip()).strip()
    
    if proc.returncode != 0:
        yield None, f"sd.exe exited with code {proc.returncode}\n\n{final_log}"
        return

    if os.path.exists(out_file):
        yield out_file, final_log
    else:
        imgs = sorted(Path(OUTDIR).glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
        if imgs:
            yield str(imgs[0]), final_log
        else:
            yield None, f"No image was produced.\n\n{final_log}"

with gr.Blocks() as demo:
    gr.Markdown("# Z-Image Turbo - Minimal UI")
    
    with gr.Tabs():
        with gr.Tab("Basic"):
            with gr.Row():
                preset = gr.Dropdown([n for n, _, _ in RES_PRESETS], value="1:1 (512x512)", label="Resolution / Aspect ratio")
            with gr.Row():
                width = gr.Dropdown(SIZE_OPTIONS, value=512, label="Width")
                height = gr.Dropdown(SIZE_OPTIONS, value=512, label="Height")
                steps = gr.Slider(1, 50, value=8, step=1, label="Steps")
            with gr.Row():
                cfg_scale = gr.Slider(0.0, 10.0, value=1.0, step=0.1, label="CFG Scale")
                seed = gr.Number(value=0, label="Seed (0 = random)")
            
            with gr.Group():
                gr.Markdown("### LoRA Support")
                with gr.Row():
                    lora_list = gr.CheckboxGroup(choices=get_lora_list(), label="Select LoRAs")
                    refresh_btn = gr.Button("🔄 Refresh", variant="secondary", size="sm")
                with gr.Row():
                    lora_strength = gr.Slider(0.0, 2.0, value=1.0, step=0.1, label="LoRA Strength")
                
                def refresh_loras():
                    return gr.update(choices=get_lora_list())
                refresh_btn.click(refresh_loras, outputs=[lora_list])

            gr.Markdown("High resolutions (like 1024x1024) use more VRAM.")

        with gr.Tab("Advanced"):
            unlock = gr.Checkbox(value=False, label="Allow editing advanced paths")
            with gr.Row():
                vae_path = gr.Textbox(label="VAE path", value=DEFAULT_VAE_PATH, interactive=False)
                llm_path = gr.Textbox(label="LLM (Qwen) path", value=DEFAULT_LLM_PATH, interactive=False)

            def set_unlocked(enabled):
                return gr.update(interactive=bool(enabled)), gr.update(interactive=bool(enabled))

            unlock.change(set_unlocked, inputs=[unlock], outputs=[vae_path, llm_path])

    with gr.Row():
        prompt = gr.Textbox(label="Prompt", value="A large orange octopus on an ocean floor, cinematic, 8k", lines=3)
    
    preset.change(apply_preset, inputs=[preset], outputs=[width, height])

    with gr.Row():
        btn = gr.Button("Generate", variant="primary")
    img = gr.Image(label="Result")
    status = gr.Textbox(label="Status", interactive=False, lines=12)

    def run_and_return(p, w, h, st, sd, cfg, vae, llm, l_list, l_str):
        global FIRST_RUN
        status_msg = "Generating... (first run can take longer)" if FIRST_RUN else "Generating..."
        FIRST_RUN = False
        
        yield None, status_msg, gr.update(interactive=False)
        
        last_log = ""
        for out_img, log in gen_image(p, int(w), int(h), int(st), int(sd), float(cfg), vae, llm, l_list, l_str):
            last_log = log
            yield out_img, log, gr.update(interactive=False)
        
        yield None, last_log, gr.update(interactive=True)

    btn.click(run_and_return, inputs=[prompt, width, height, steps, seed, cfg_scale, vae_path, llm_path, lora_list, lora_strength], outputs=[img, status, btn])

demo.launch(server_name="127.0.0.1", server_port=9000, share=False)
'@
$py = $py -replace '__MODEL_NAME__', $model_name
$py | Out-File -Encoding utf8 $uiScript
Write-Host "Wrote run_gradio_ui.py"

# 11. Run the UI
Write-Host "`nStarting the minimal UI (Gradio) at http://127.0.0.1:9000"
Write-Host "Press Ctrl+C in this window to stop."
& $venvPython (Join-Path $root "run_gradio_ui.py")
