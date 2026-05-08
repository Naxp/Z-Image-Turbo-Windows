import os, subprocess, shlex, uuid, time
import re
from pathlib import Path
import gradio as gr

ROOT = Path(__file__).parent
SD_BIN_DIR = ROOT / "sd_bin"
SD_EXE = str(SD_BIN_DIR / "sd-cli.exe")
MODEL_PATH = str(ROOT / "models" / "zimage" / "z_image_turbo_Q4_0.gguf")
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
                    refresh_btn = gr.Button("ðŸ”„ Refresh", variant="secondary", size="sm")
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
