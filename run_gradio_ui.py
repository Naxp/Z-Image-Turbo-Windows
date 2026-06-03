import os
import random
import subprocess
import time
import uuid
from datetime import datetime
from pathlib import Path

import gradio as gr
from gradio import Brush, Eraser
from PIL import Image, ImageOps


ROOT = Path(__file__).parent
SD_BIN_DIR = ROOT / "sd_bin"
MODEL_CONFIG_PATH = ROOT / "models" / "zimage" / "selected_model.txt"
MODEL_NAME = os.environ.get("ZIMAGE_MODEL_NAME")
if not MODEL_NAME and MODEL_CONFIG_PATH.exists():
    MODEL_NAME = MODEL_CONFIG_PATH.read_text(encoding="utf-8").strip()
if not MODEL_NAME:
    MODEL_NAME = "z_image_turbo_Q4_0.gguf"
MODEL_PATH = str(ROOT / "models" / "zimage" / MODEL_NAME)
LORA_DIR = ROOT / "models" / "loras"
OUTDIR = ROOT / "outputs"
TEMP_INPUT_DIR = OUTDIR / "_tmp_inputs"

DEFAULT_VAE_PATH = str(ROOT / "models" / "vae" / "ae.safetensors")
DEFAULT_LLM_PATH = str(ROOT / "models" / "llm" / "Qwen3-4B-Instruct-2507-Q4_K_M.gguf")

OUTDIR.mkdir(exist_ok=True)
LORA_DIR.mkdir(exist_ok=True)
TEMP_INPUT_DIR.mkdir(exist_ok=True)

current_proc = None
FIRST_RUN = True
LAST_SEED = None
LAST_IMG2IMG_SEED = None
LAST_INPAINT_SEED = None

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
VRAM_PRESETS = [
    "4GB (safest)",
    "6-8GB (balanced)",
    "10GB+ (fastest)",
]
LORA_APPLY_MODES = ["auto", "immediately", "at_runtime"]
TXT2IMG_PROMPTS = {
    "Portrait": "cinematic portrait of a woman in a red dress inside a cozy cafe, soft window light, natural skin texture, 35mm photo",
    "Product": "premium product photo of a matte black wireless speaker on a clean desk, softbox lighting, sharp details, commercial photography",
    "Landscape": "wide landscape photo of a misty mountain valley at sunrise, dramatic light, realistic atmosphere, high detail",
    "Fantasy": "fantasy castle above a glowing forest, epic scale, detailed architecture, cinematic lighting",
    "Anime": "anime character portrait, expressive eyes, detailed hair, clean line art, soft color palette",
    "Cinematic": "cinematic scene of a lone explorer standing in a neon-lit rainy street, film still, dramatic composition",
}
IMG2IMG_PROMPTS = {
    "Color edit": "Change only the main subject color while preserving the same shape, lighting, background, and composition",
    "Style shift": "Transform this image into a cinematic film still while preserving the subject and composition",
    "Product polish": "Make this look like a premium studio product photo, clean lighting, sharp details, same object",
    "Anime style": "Convert this image to a polished anime style while preserving the pose and composition",
}
INPAINT_PROMPTS = {
    "Replace object": "Replace the masked area with a realistic object that matches the original lighting and perspective",
    "Change clothing": "Change only the masked clothing color and fabric while preserving the person, pose, and background",
    "Remove object": "Fill the masked area naturally using the surrounding background",
    "Add detail": "Add realistic detail inside the masked area while matching the original image style",
}


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


def get_lora_list():
    """List available LoRA files in the loras directory."""
    if not LORA_DIR.exists():
        return []
    return [f.name for f in sorted(LORA_DIR.glob("*.safetensors"))]


def get_recent_outputs(limit=12):
    images = []
    for pattern in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        images.extend(OUTDIR.glob(pattern))
    return [str(p.absolute()) for p in sorted(images, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]]


def apply_preset(preset_label):
    for name, w, h in RES_PRESETS:
        if name == preset_label:
            return w, h
    return gr.update(), gr.update()


def random_seed():
    return random.randint(0, 2_147_483_647)


def reuse_last_seed():
    if LAST_SEED is None:
        return gr.update()
    return LAST_SEED


def reuse_last_img2img_seed():
    if LAST_IMG2IMG_SEED is None:
        return gr.update()
    return LAST_IMG2IMG_SEED


def reuse_last_inpaint_seed():
    if LAST_INPAINT_SEED is None:
        return gr.update()
    return LAST_INPAINT_SEED


def refresh_loras():
    return gr.update(choices=get_lora_list())


def refresh_gallery():
    return get_recent_outputs()


def apply_example(prompt_map, selected_label):
    if selected_label in prompt_map:
        return prompt_map[selected_label]
    return gr.update()


def apply_txt2img_example(selected_label):
    return apply_example(TXT2IMG_PROMPTS, selected_label)


def apply_img2img_example(selected_label):
    return apply_example(IMG2IMG_PROMPTS, selected_label)


def apply_inpaint_example(selected_label):
    return apply_example(INPAINT_PROMPTS, selected_label)


def set_unlocked(enabled):
    return gr.update(interactive=bool(enabled)), gr.update(interactive=bool(enabled))


def set_img2img_enabled(enabled):
    return gr.update(interactive=bool(enabled)), gr.update(interactive=bool(enabled))


def set_inpaint_enabled(enabled):
    return gr.update(interactive=bool(enabled)), gr.update(interactive=bool(enabled))


def stop_gen():
    global current_proc
    if current_proc and current_proc.poll() is None:
        print("Stopping generation...")
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(current_proc.pid)], capture_output=True)
        else:
            current_proc.terminate()
        return "Generation stopped by user."
    return "No active generation to stop."


def normalize_seed(seed_value):
    try:
        seed_int = int(seed_value)
    except (TypeError, ValueError):
        seed_int = -1
    if seed_int < 0:
        return random_seed()
    return seed_int


def append_lora_tags(prompt, selected_loras, lora_strength):
    final_prompt = prompt or ""
    if selected_loras:
        for lora in selected_loras:
            lora_name = Path(lora).stem
            final_prompt += f" <lora:{lora_name}:{lora_strength}>"
    return final_prompt


def low_vram_flags(vram_mode, clip_on_cpu, balanced_vae_tiling):
    flags = []
    if vram_mode == "4GB (safest)":
        flags.extend(["--offload-to-cpu", "--diffusion-fa", "--vae-tiling", "--vae-conv-direct"])
        if clip_on_cpu:
            flags.append("--clip-on-cpu")
    elif vram_mode == "6-8GB (balanced)":
        flags.extend(["--offload-to-cpu", "--diffusion-fa"])
        if balanced_vae_tiling:
            flags.append("--vae-tiling")
    elif vram_mode == "10GB+ (fastest)":
        flags.append("--diffusion-fa")
    return flags


def prepare_init_image(init_image_path, width, height):
    if not init_image_path:
        return None, None

    src = Path(init_image_path)
    if not src.exists():
        return None, f"Img2img input image was not found: {src}"

    try:
        image = Image.open(src)
        image = ImageOps.exif_transpose(image).convert("RGB")
        if image.size != (width, height):
            image = image.resize((width, height), Image.Resampling.LANCZOS)
        dest = TEMP_INPUT_DIR / f"init_{uuid.uuid4().hex[:8]}.png"
        image.save(dest)
        return str(dest.absolute()), None
    except Exception as exc:
        return None, f"Could not prepare img2img input image: {exc}"


def get_editor_background(editor_value):
    if not editor_value:
        return None
    if isinstance(editor_value, dict):
        return editor_value.get("background") or editor_value.get("composite")
    return editor_value


def prepare_inpaint_images(editor_value, width, height):
    if not editor_value:
        return None, None, "Upload an image and paint a mask before using inpainting."

    background = get_editor_background(editor_value)
    if background is None:
        return None, None, "Inpaint source image is missing."

    try:
        image = ImageOps.exif_transpose(background).convert("RGB")
        layers = editor_value.get("layers", []) if isinstance(editor_value, dict) else []
        mask = Image.new("L", image.size, 0)
        for layer in layers:
            layer_img = ImageOps.exif_transpose(layer).convert("RGBA")
            alpha = layer_img.getchannel("A")
            mask = Image.composite(Image.new("L", image.size, 255), mask, alpha)

        if not mask.getbbox():
            return None, None, "Paint over the area you want to edit before generating."

        if image.size != (width, height):
            image = image.resize((width, height), Image.Resampling.LANCZOS)
            mask = mask.resize((width, height), Image.Resampling.NEAREST)

        uid = uuid.uuid4().hex[:8]
        init_dest = TEMP_INPUT_DIR / f"inpaint_init_{uid}.png"
        mask_dest = TEMP_INPUT_DIR / f"inpaint_mask_{uid}.png"
        image.save(init_dest)
        mask.save(mask_dest)
        return str(init_dest.absolute()), str(mask_dest.absolute()), None
    except Exception as exc:
        return None, None, f"Could not prepare inpaint image/mask: {exc}"


def format_command(cmd):
    return subprocess.list2cmdline([str(part) for part in cmd])


def write_metadata(out_file, metadata):
    meta_path = Path(out_file).with_suffix(Path(out_file).suffix + ".txt")
    lines = [
        "Z-Image Turbo generation metadata",
        f"Created: {datetime.now().isoformat(timespec='seconds')}",
        "",
    ]
    for key, value in metadata.items():
        if value is None or value == "":
            continue
        lines.append(f"{key}: {value}")
    try:
        meta_path.write_text("\n".join(lines), encoding="utf-8")
    except OSError as exc:
        print(f"Could not write metadata file: {exc}")


def gen_image(
    prompt,
    width,
    height,
    steps,
    seed,
    cfg_scale,
    vae_path,
    llm_path,
    selected_loras,
    lora_strength,
    lora_apply_mode,
    vram_mode,
    clip_on_cpu,
    balanced_vae_tiling,
    negative_prompt,
    guidance,
    img2img_enabled,
    init_image_path,
    img2img_strength,
    mask_path=None,
    generation_mode="txt2img",
):
    global current_proc

    if SD_EXE is None:
        yield None, "Error: No stable-diffusion executable found.", "", ""
        return

    uses_input_image = img2img_enabled or generation_mode == "inpaint"
    if uses_input_image and not init_image_path:
        yield None, f"{generation_mode} is enabled, but no input image was provided.", "0s", ""
        return

    init_file = None
    init_error = None
    if generation_mode == "inpaint":
        init_file = init_image_path
    elif img2img_enabled:
        init_file, init_error = prepare_init_image(init_image_path, width, height)
    if init_error:
        yield None, init_error, "0s", ""
        return

    uid = uuid.uuid4().hex[:8]
    out_file = str((OUTDIR / f"out_{uid}.png").absolute())
    final_prompt = append_lora_tags(prompt, selected_loras, lora_strength)

    cmd = [
        SD_EXE,
        "--diffusion-model",
        MODEL_PATH,
        "--vae",
        vae_path,
        "--llm",
        llm_path,
        "--lora-model-dir",
        str(LORA_DIR),
        "--lora-apply-mode",
        lora_apply_mode,
        "-p",
        final_prompt,
        "--guidance",
        str(guidance),
        "--cfg-scale",
        str(cfg_scale),
        "--steps",
        str(steps),
        "-H",
        str(height),
        "-W",
        str(width),
        "-o",
        out_file,
        "--seed",
        str(seed),
        "--rng",
        "cuda",
    ]
    if negative_prompt:
        cmd.extend(["--negative-prompt", negative_prompt])
    cmd.extend(low_vram_flags(vram_mode, clip_on_cpu, balanced_vae_tiling))

    if uses_input_image:
        cmd.extend(["--init-img", init_file, "--strength", str(img2img_strength)])
    if generation_mode == "inpaint":
        cmd.extend(["--mask", mask_path])

    cmd_str = format_command(cmd)
    yield None, f"Starting generation...\nCommand: {cmd_str}", "0s", cmd_str

    t_start = time.perf_counter()
    current_proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )

    full_log = ""
    try:
        for line in current_proc.stdout:
            print(line, end="")
            full_log += line
            elapsed = int(time.perf_counter() - t_start)
            yield None, full_log.strip(), f"{elapsed}s", cmd_str
    except Exception as exc:
        yield None, f"Error during logging: {exc}", "0s", cmd_str

    current_proc.wait()
    total_time = f"{time.perf_counter() - t_start:.1f}s"

    if current_proc.returncode != 0:
        if current_proc.returncode in [-1, 1, 3221225786, 15]:
            yield None, f"Generation stopped.\n\n{full_log.strip()}", total_time, cmd_str
        else:
            yield (
                None,
                f"sd.exe exited with code {current_proc.returncode}\n\n{full_log.strip()}",
                total_time,
                cmd_str,
            )
        return

    if not os.path.exists(out_file):
        imgs = sorted(OUTDIR.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not imgs:
            yield None, f"No image was produced.\n\n{full_log.strip()}", total_time, cmd_str
            return
        out_file = str(imgs[0].absolute())

    write_metadata(
        out_file,
        {
            "mode": generation_mode,
            "prompt": prompt,
            "final_prompt": final_prompt,
            "seed": seed,
            "width": width,
            "height": height,
            "steps": steps,
            "cfg_scale": cfg_scale,
            "guidance": guidance,
            "negative_prompt": negative_prompt,
            "vram_mode": vram_mode,
            "lora_files": ", ".join(selected_loras or []),
            "lora_strength": lora_strength,
            "lora_apply_mode": lora_apply_mode,
            "init_image": init_file,
            "mask": mask_path,
            "strength": img2img_strength if uses_input_image else None,
            "command": cmd_str,
            "generation_time": total_time,
            "log": full_log.strip(),
        },
    )
    yield out_file, full_log.strip(), total_time, cmd_str


with gr.Blocks() as demo:
    gr.Markdown("# Z-Image Turbo - Low VRAM UI")

    with gr.Row():
        with gr.Column(scale=3):
            with gr.Tabs():
                with gr.Tab("Basic"):
                    txt2img_prompt = gr.Textbox(
                        label="Text-to-image prompt",
                        value="A large orange octopus on an ocean floor, cinematic, 8k",
                        lines=3,
                    )
                    with gr.Row():
                        txt2img_example = gr.Dropdown(
                            list(TXT2IMG_PROMPTS.keys()),
                            value="Portrait",
                            label="Example Prompt",
                        )
                        txt2img_example_btn = gr.Button("Use Example", variant="secondary")

                    with gr.Row():
                        preset = gr.Dropdown(
                            [n for n, _, _ in RES_PRESETS],
                            value="1:1 (512x512)",
                            label="Resolution Preset",
                        )
                        steps = gr.Slider(1, 50, value=8, step=1, label="Steps")

                    with gr.Row():
                        width = gr.Dropdown(SIZE_OPTIONS, value=512, label="Width")
                        height = gr.Dropdown(SIZE_OPTIONS, value=512, label="Height")

                    with gr.Row():
                        cfg_scale = gr.Slider(0.0, 10.0, value=1.0, step=0.1, label="CFG Scale")
                        seed = gr.Number(value=-1, precision=0, label="Seed (-1 = random)")

                    with gr.Row():
                        random_seed_btn = gr.Button("Random Seed", variant="secondary")
                        reuse_seed_btn = gr.Button("Reuse Last Seed", variant="secondary")

                    with gr.Group():
                        gr.Markdown("### Low VRAM Mode")
                        vram_mode = gr.Radio(
                            VRAM_PRESETS,
                            value="4GB (safest)",
                            label="VRAM Preset",
                        )
                        with gr.Row():
                            clip_on_cpu = gr.Checkbox(
                                value=False,
                                label="4GB extra: keep text encoder on CPU",
                            )
                            balanced_vae_tiling = gr.Checkbox(
                                value=False,
                                label="6-8GB extra: VAE tiling",
                            )

                    with gr.Group():
                        gr.Markdown("### LoRA Support")
                        with gr.Row():
                            lora_list = gr.CheckboxGroup(choices=get_lora_list(), label="Select LoRAs")
                            refresh_btn = gr.Button("Refresh", variant="secondary", size="sm")
                        with gr.Row():
                            lora_strength = gr.Slider(0.0, 2.0, value=1.0, step=0.1, label="LoRA Strength")
                            lora_apply_mode = gr.Dropdown(
                                LORA_APPLY_MODES,
                                value="auto",
                                label="LoRA Apply Mode",
                            )

                with gr.Tab("Experimental Img2Img"):
                    gr.Markdown(
                        "Creates a variation of the uploaded image. Higher strength values produce larger changes."
                    )
                    gr.Markdown(
                        "Experimental for Z-Image Turbo GGUF; results depend on backend support."
                    )
                    img2img_prompt = gr.Textbox(
                        label="Img2Img prompt",
                        value="Transform this image while preserving the main composition",
                        lines=3,
                    )
                    with gr.Row():
                        img2img_example = gr.Dropdown(
                            list(IMG2IMG_PROMPTS.keys()),
                            value="Color edit",
                            label="Example Prompt",
                        )
                        img2img_example_btn = gr.Button("Use Example", variant="secondary")
                    img2img_negative_prompt = gr.Textbox(
                        label="Img2Img negative prompt",
                        value="",
                        lines=2,
                    )
                    img2img_enabled = gr.Checkbox(value=False, label="Enable img2img")
                    init_image = gr.Image(
                        label="Input image",
                        type="filepath",
                        interactive=False,
                    )
                    with gr.Row():
                        img2img_seed = gr.Number(value=-1, precision=0, label="Img2Img Seed (-1 = random)")
                    with gr.Row():
                        img2img_random_seed_btn = gr.Button("Random Img2Img Seed", variant="secondary")
                        img2img_reuse_seed_btn = gr.Button("Reuse Last Img2Img Seed", variant="secondary")
                    with gr.Row():
                        img2img_steps = gr.Slider(
                            4,
                            30,
                            value=12,
                            step=1,
                            label="Img2Img Steps",
                            info="More steps give the prompt more chances to affect the uploaded image.",
                        )
                        img2img_guidance = gr.Slider(
                            1.0,
                            8.0,
                            value=3.5,
                            step=0.1,
                            label="Img2Img Guidance",
                            info="Higher values follow the prompt more strongly, but can create more drift.",
                        )
                    img2img_strength = gr.Slider(
                        0.1,
                        1.0,
                        value=0.55,
                        step=0.05,
                        label="Img2Img Strength",
                        info="Lower preserves more. Higher changes more. Z-Image usually needs about 0.50-0.60 for visible edits.",
                        interactive=False,
                    )

                with gr.Tab("Inpaint / Selective Edit"):
                    gr.Markdown(
                        "Edit only selected regions while preserving the rest of the image. Experimental with Z-Image Turbo."
                    )
                    inpaint_enabled = gr.Checkbox(value=False, label="Enable inpainting")
                    inpaint_editor = gr.ImageEditor(
                        label="Source image and mask",
                        type="pil",
                        image_mode="RGBA",
                        brush=Brush(default_size=32, colors=["#ffffff"], default_color="#ffffff", color_mode="fixed"),
                        eraser=Eraser(default_size=32),
                        layers=True,
                        interactive=False,
                        height=420,
                    )
                    inpaint_prompt = gr.Textbox(
                        label="Inpaint prompt",
                        value="Replace the masked area while matching the original lighting and style",
                        lines=3,
                    )
                    with gr.Row():
                        inpaint_example = gr.Dropdown(
                            list(INPAINT_PROMPTS.keys()),
                            value="Replace object",
                            label="Example Prompt",
                        )
                        inpaint_example_btn = gr.Button("Use Example", variant="secondary")
                    inpaint_negative_prompt = gr.Textbox(
                        label="Inpaint negative prompt",
                        value="",
                        lines=2,
                    )
                    with gr.Row():
                        inpaint_seed = gr.Number(value=-1, precision=0, label="Inpaint Seed (-1 = random)")
                    with gr.Row():
                        inpaint_random_seed_btn = gr.Button("Random Inpaint Seed", variant="secondary")
                        inpaint_reuse_seed_btn = gr.Button("Reuse Last Inpaint Seed", variant="secondary")
                    with gr.Row():
                        inpaint_steps = gr.Slider(4, 30, value=12, step=1, label="Inpaint Steps")
                        inpaint_guidance = gr.Slider(1.0, 8.0, value=4.0, step=0.1, label="Inpaint Guidance")
                    inpaint_strength = gr.Slider(
                        0.1,
                        1.0,
                        value=0.75,
                        step=0.05,
                        label="Inpaint Strength",
                        info="Higher values make the masked area change more.",
                        interactive=False,
                    )

                with gr.Tab("Advanced"):
                    unlock = gr.Checkbox(value=False, label="Allow editing advanced paths")
                    with gr.Row():
                        vae_path = gr.Textbox(label="VAE path", value=DEFAULT_VAE_PATH, interactive=False)
                        llm_path = gr.Textbox(label="LLM (Qwen) path", value=DEFAULT_LLM_PATH, interactive=False)

            with gr.Row():
                btn = gr.Button("Generate", variant="primary", scale=2)
                stop_btn = gr.Button("Stop", variant="stop", scale=1)

        with gr.Column(scale=2):
            img = gr.Image(label="Result", interactive=False, type="filepath")
            timer_display = gr.Markdown("Generation Time: **0s**")
            gallery = gr.Gallery(label="Recent Outputs", value=get_recent_outputs(), columns=3, height=260)
            refresh_gallery_btn = gr.Button("Refresh Gallery", variant="secondary")
            command_box = gr.Textbox(label="Last Command", interactive=False, lines=3)
            status = gr.Textbox(label="Status / Logs", interactive=False, lines=14)

    preset.change(apply_preset, inputs=[preset], outputs=[width, height])
    refresh_btn.click(refresh_loras, outputs=[lora_list])
    txt2img_example_btn.click(apply_txt2img_example, inputs=[txt2img_example], outputs=[txt2img_prompt])
    img2img_example_btn.click(apply_img2img_example, inputs=[img2img_example], outputs=[img2img_prompt])
    inpaint_example_btn.click(apply_inpaint_example, inputs=[inpaint_example], outputs=[inpaint_prompt])
    random_seed_btn.click(random_seed, outputs=[seed])
    reuse_seed_btn.click(reuse_last_seed, outputs=[seed])
    img2img_random_seed_btn.click(random_seed, outputs=[img2img_seed])
    img2img_reuse_seed_btn.click(reuse_last_img2img_seed, outputs=[img2img_seed])
    inpaint_random_seed_btn.click(random_seed, outputs=[inpaint_seed])
    inpaint_reuse_seed_btn.click(reuse_last_inpaint_seed, outputs=[inpaint_seed])
    refresh_gallery_btn.click(refresh_gallery, outputs=[gallery])
    unlock.change(set_unlocked, inputs=[unlock], outputs=[vae_path, llm_path])
    img2img_enabled.change(set_img2img_enabled, inputs=[img2img_enabled], outputs=[init_image, img2img_strength])
    inpaint_enabled.change(set_inpaint_enabled, inputs=[inpaint_enabled], outputs=[inpaint_editor, inpaint_strength])

    def run_and_return(
        txt_prompt,
        image_prompt,
        selective_prompt,
        w,
        h,
        st,
        txt_seed,
        cfg,
        vae,
        llm,
        l_list,
        l_str,
        l_apply_mode,
        low_vram_mode,
        keep_clip_cpu,
        use_balanced_vae_tiling,
        use_img2img,
        input_image,
        image_negative_prompt,
        image_seed,
        image_steps,
        image_guidance,
        image_strength,
        use_inpaint,
        inpaint_image,
        selective_negative_prompt,
        selective_seed,
        selective_steps,
        selective_guidance,
        selective_strength,
    ):
        global FIRST_RUN, LAST_SEED, LAST_IMG2IMG_SEED, LAST_INPAINT_SEED

        generation_mode = "inpaint" if use_inpaint else "img2img" if use_img2img else "txt2img"
        if generation_mode == "inpaint":
            run_seed = normalize_seed(selective_seed)
            LAST_INPAINT_SEED = run_seed
            seed_outputs = (gr.update(), gr.update(), run_seed)
        elif generation_mode == "img2img":
            run_seed = normalize_seed(image_seed)
            LAST_IMG2IMG_SEED = run_seed
            seed_outputs = (gr.update(), run_seed, gr.update())
        else:
            run_seed = normalize_seed(txt_seed)
            LAST_SEED = run_seed
            seed_outputs = (run_seed, gr.update(), gr.update())

        status_msg = "Generating... (first run can take longer)" if FIRST_RUN else "Generating..."
        FIRST_RUN = False
        active_prompt = selective_prompt if generation_mode == "inpaint" else image_prompt if generation_mode == "img2img" else txt_prompt
        active_steps = int(selective_steps) if generation_mode == "inpaint" else int(image_steps) if generation_mode == "img2img" else int(st)
        active_negative_prompt = selective_negative_prompt if generation_mode == "inpaint" else image_negative_prompt if generation_mode == "img2img" else ""
        active_guidance = float(selective_guidance) if generation_mode == "inpaint" else float(image_guidance) if generation_mode == "img2img" else 3.5
        active_strength = float(selective_strength) if generation_mode == "inpaint" else float(image_strength)
        active_init_image = input_image
        active_mask = None
        prep_error = None
        if generation_mode == "inpaint":
            active_init_image, active_mask, prep_error = prepare_inpaint_images(inpaint_image, int(w), int(h))
            if prep_error:
                yield (
                    None,
                    prep_error,
                    gr.update(interactive=True),
                    gr.update(interactive=False),
                    "Generation Time: **0s**",
                    "",
                    get_recent_outputs(),
                    *seed_outputs,
                )
                return

        yield (
            None,
            status_msg,
            gr.update(interactive=False),
            gr.update(interactive=True),
            "Generation Time: **0s**",
            "",
            get_recent_outputs(),
            *seed_outputs,
        )

        last_img = None
        last_log = ""
        last_time = "0s"
        last_command = ""
        for out_img, log, time_str, cmd_str in gen_image(
            active_prompt,
            int(w),
            int(h),
            active_steps,
            run_seed,
            float(cfg),
            vae,
            llm,
            l_list,
            l_str,
            l_apply_mode,
            low_vram_mode,
            keep_clip_cpu,
            use_balanced_vae_tiling,
            active_negative_prompt,
            active_guidance,
            generation_mode != "txt2img",
            active_init_image,
            active_strength,
            active_mask,
            generation_mode,
        ):
            if out_img is not None:
                last_img = out_img
            last_log = log
            last_time = time_str
            last_command = cmd_str
            image_update = out_img if out_img is not None else gr.update()
            yield (
                image_update,
                log,
                gr.update(interactive=False),
                gr.update(interactive=True),
                f"Generation Time: **{time_str}**",
                cmd_str,
                get_recent_outputs(),
                *seed_outputs,
            )

        final_image = last_img if last_img is not None else gr.update()
        yield (
            final_image,
            last_log,
            gr.update(interactive=True),
            gr.update(interactive=False),
            f"Generation Time: **{last_time}**",
            last_command,
            get_recent_outputs(),
            *seed_outputs,
        )

    btn.click(
        run_and_return,
        inputs=[
            txt2img_prompt,
            img2img_prompt,
            inpaint_prompt,
            width,
            height,
            steps,
            seed,
            cfg_scale,
            vae_path,
            llm_path,
            lora_list,
            lora_strength,
            lora_apply_mode,
            vram_mode,
            clip_on_cpu,
            balanced_vae_tiling,
            img2img_enabled,
            init_image,
            img2img_negative_prompt,
            img2img_seed,
            img2img_steps,
            img2img_guidance,
            img2img_strength,
            inpaint_enabled,
            inpaint_editor,
            inpaint_negative_prompt,
            inpaint_seed,
            inpaint_steps,
            inpaint_guidance,
            inpaint_strength,
        ],
        outputs=[
            img,
            status,
            btn,
            stop_btn,
            timer_display,
            command_box,
            gallery,
            seed,
            img2img_seed,
            inpaint_seed,
        ],
    )
    stop_btn.click(stop_gen, outputs=[status])

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=9000, share=False)
