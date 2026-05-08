import os, subprocess, shlex, uuid, time, signal
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

# Global variable to track the current process
current_proc = None

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

def stop_gen():
    global current_proc
    if current_proc and current_proc.poll() is None:
        print("Stopping generation...")
        if os.name == 'nt':
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(current_proc.pid)], capture_output=True)
        else:
            current_proc.terminate()
        return "Generation stopped by user."
    return "No active generation to stop."

def gen_image(prompt, width, height, steps, seed, cfg_scale, vae_path, llm_path, selected_loras, lora_strength):
    global current_proc
    if SD_EXE is None:
        yield None, "Error: No stable-diffusion executable found.", ""
        return

    uid = uuid.uuid4().hex[:8]
    out_file = str(Path(OUTDIR).absolute() / f"out_{uid}.png")
    
    # Append LoRA tags to prompt
    final_prompt = prompt
    if selected_loras:
        for lora in selected_loras:
            lora_name = Path(lora).stem
            final_prompt += f" <lora:{lora_name}:{lora_strength}>"

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
    yield None, f"Starting generation...\nCommand: {cmd_str}", "0s"

    t_start = time.perf_counter()
    current_proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
    )

    full_log = ""
    try:
        for line in current_proc.stdout:
            print(line, end="")
            full_log += line
            elapsed = int(time.perf_counter() - t_start)
            yield None, full_log.strip(), f"{elapsed}s"
    except Exception as e:
        yield None, f"Error during logging: {str(e)}", "0s"

    current_proc.wait()
    t_end = time.perf_counter()
    total_time = f"{t_end - t_start:.1f}s"
    
    if current_proc.returncode != 0:
        if current_proc.returncode in [-1, 1, 3221225786, 15]: 
            yield None, f"Generation stopped.\n\n{full_log.strip()}", total_time
        else:
            yield None, f"sd.exe exited with code {current_proc.returncode}\n\n{full_log.strip()}", total_time
        return

    if os.path.exists(out_file):
        yield out_file, full_log.strip(), total_time
    else:
        # Fallback search
        imgs = sorted(Path(OUTDIR).glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
        if imgs:
            yield str(imgs[0].absolute()), full_log.strip(), total_time
        else:
            yield None, f"No image was produced.\n\n{full_log.strip()}", total_time

with gr.Blocks() as demo:
    gr.Markdown("# Z-Image Turbo - Minimal UI")
    
    with gr.Row():
        with gr.Column(scale=3):
            with gr.Tabs():
                with gr.Tab("Basic"):
                    prompt = gr.Textbox(label="Prompt", value="A large orange octopus on an ocean floor, cinematic, 8k", lines=3)
                    
                    with gr.Row():
                        preset = gr.Dropdown([n for n, _, _ in RES_PRESETS], value="1:1 (512x512)", label="Resolution Preset")
                        steps = gr.Slider(1, 50, value=8, step=1, label="Steps")
                    
                    with gr.Row():
                        width = gr.Dropdown(SIZE_OPTIONS, value=512, label="Width")
                        height = gr.Dropdown(SIZE_OPTIONS, value=512, label="Height")
                    
                    with gr.Row():
                        cfg_scale = gr.Slider(0.0, 10.0, value=1.0, step=0.1, label="CFG Scale")
                        seed = gr.Number(value=0, label="Seed (0 = random)")
                    
                    with gr.Group():
                        gr.Markdown("### LoRA Support")
                        with gr.Row():
                            lora_list = gr.CheckboxGroup(choices=get_lora_list(), label="Select LoRAs")
                            refresh_btn = gr.Button("Refresh", variant="secondary", size="sm")
                        with gr.Row():
                            lora_strength = gr.Slider(0.0, 2.0, value=1.0, step=0.1, label="LoRA Strength")
                        
                        def refresh_loras():
                            return gr.update(choices=get_lora_list())
                        refresh_btn.click(refresh_loras, outputs=[lora_list])

                with gr.Tab("Advanced"):
                    unlock = gr.Checkbox(value=False, label="Allow editing advanced paths")
                    with gr.Row():
                        vae_path = gr.Textbox(label="VAE path", value=DEFAULT_VAE_PATH, interactive=False)
                        llm_path = gr.Textbox(label="LLM (Qwen) path", value=DEFAULT_LLM_PATH, interactive=False)

                    def set_unlocked(enabled):
                        return gr.update(interactive=bool(enabled)), gr.update(interactive=bool(enabled))
                    unlock.change(set_unlocked, inputs=[unlock], outputs=[vae_path, llm_path])

            with gr.Row():
                btn = gr.Button("Generate", variant="primary", scale=2)
                stop_btn = gr.Button("Stop", variant="stop", scale=1)

        with gr.Column(scale=2):
            with gr.Group():
                img = gr.Image(label="Result", interactive=False, type="filepath")
                with gr.Row():
                    timer_display = gr.Markdown("Generation Time: **0s**")
            
            status = gr.Textbox(label="Status / Logs", interactive=False, lines=15)

    preset.change(apply_preset, inputs=[preset], outputs=[width, height])

    def run_and_return(p, w, h, st, sd, cfg, vae, llm, l_list, l_str):
        global FIRST_RUN
        status_msg = "Generating... (first run can take longer)" if FIRST_RUN else "Generating..."
        FIRST_RUN = False
        
        yield None, status_msg, gr.update(interactive=False), gr.update(interactive=True), "Generation Time: **0s**"
        
        last_img = None
        last_log = ""
        last_time = "0s"
        for out_img, log, time_str in gen_image(p, int(w), int(h), int(st), int(sd), float(cfg), vae, llm, l_list, l_str):
            if out_img is not None:
                last_img = out_img
            last_log = log
            last_time = time_str
            image_update = out_img if out_img is not None else gr.update()
            yield image_update, log, gr.update(interactive=False), gr.update(interactive=True), f"Generation Time: **{time_str}**"
        
        final_image = last_img if last_img is not None else gr.update()
        yield final_image, last_log, gr.update(interactive=True), gr.update(interactive=False), f"Generation Time: **{last_time}**"

    btn.click(
        run_and_return, 
        inputs=[prompt, width, height, steps, seed, cfg_scale, vae_path, llm_path, lora_list, lora_strength], 
        outputs=[img, status, btn, stop_btn, timer_display]
    )
    stop_btn.click(stop_gen, outputs=[status])

demo.launch(server_name="127.0.0.1", server_port=9000, share=False)
