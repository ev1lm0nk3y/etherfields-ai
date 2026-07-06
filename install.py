#!/usr/bin/env python3
"""
install.py - Interactive Installation Script for Etherfields AI Rule Master.
Validates system prerequisites, initializes directories, configures environment,
downloads assets, and handles tool installations.
"""

import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path


# Color helpers for rich CLI experience
def print_success(msg):
    print(f"\033[92m✔ {msg}\033[0m")

def print_info(msg):
    print(f"\033[94mℹ {msg}\033[0m")

def print_warning(msg):
    print(f"\033[93m⚠ {msg}\033[0m")

def print_error(msg):
    print(f"\033[91m✘ {msg}\033[0m")

def ask_yes_no(question, default=False):
    suffix = " [Y/n]: " if default else " [y/N]: "
    val = input(f"\033[95m? {question}\033[0m" + suffix).strip().lower()
    if not val:
        return default
    return val.startswith('y')

def ask_input(question, default_val=None):
    suffix = f" [{default_val}]: " if default_val else ": "
    val = input(f"\033[95m? {question}\033[0m" + suffix).strip()
    return val if val else default_val


def check_prerequisites():
    print_info("Checking system prerequisites...")

    # 1. Python version >= 3.12
    major, minor = sys.version_info.major, sys.version_info.minor
    if major < 3 or (major == 3 and minor < 12):
        print_error(f"Python 3.12 or higher is required. Detected Python {major}.{minor}")
        sys.exit(1)
    print_success(f"Python version: {major}.{minor}")

    # 2. Check for uv
    uv_path = shutil.which("uv")
    if not uv_path:
        print_error("`uv` was not found in the system PATH. Please install it first (https://github.com/astral-sh/uv).")
        sys.exit(1)
    print_success(f"Found uv at {uv_path}")

    # 3. Check for gemini CLI
    gemini_path = shutil.which("gemini")
    if not gemini_path:
        print_warning("`gemini` CLI was not found in the system PATH. (Ensure you have it installed or are running in its environment).")
    else:
        print_success(f"Found gemini CLI at {gemini_path}")


def setup_directories_and_env():
    # 1. Ask for custom directory
    default_dir = os.path.expanduser("~/.local/etherfields-ai")
    custom_dir_str = ask_input("Define the custom files directory to store logs, cache, and models", default_dir)
    custom_dir = Path(os.path.expandvars(os.path.expanduser(custom_dir_str))).resolve()

    print_info(f"Initializing directories in: {custom_dir}")

    # Create directories
    subdirs = ["logs", "audio_cache", "rulebook_pages", "topics", "models"]
    for subdir in subdirs:
        dir_path = custom_dir / subdir
        dir_path.mkdir(parents=True, exist_ok=True)
        print_success(f"Ensured directory: {dir_path}")

    # 2. Ask for Voice Assist enablement
    enable_voice = ask_yes_no("Would you like to enable the voice/TTS and wake-word listener capabilities?", default=False)

    if enable_voice:
        # Check ffmpeg
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            print_error("`ffmpeg` is required for voice capabilities but was not found.")
            print_warning("Please install ffmpeg on your system first (e.g. `brew install ffmpeg` on macOS) or proceed without voice.")
            sys.exit(1)
        print_success(f"Found ffmpeg at {ffmpeg_path}")

    # 3. Wake Word setup
    wake_word_model = "jarvis.onnx"
    if enable_voice:
        wake_word_choice = ask_input("Enter path to a custom .onnx or .tflite wake-word model, or press Enter to download 'jarvis'", "jarvis")
        if wake_word_choice.lower() == "jarvis":
            jarvis_url = "https://github.com/dscripka/openWakeWord/raw/main/openwakeword/resources/models/jarvis.onnx"
            target_path = custom_dir / "models" / "jarvis.onnx"
            if not target_path.exists():
                print_info("Downloading Jarvis wake-word model...")
                try:
                    urllib.request.urlretrieve(jarvis_url, target_path)
                    print_success(f"Downloaded Jarvis model to {target_path}")
                except Exception as e:
                    print_error(f"Failed to download wake-word model: {e}")
                    print_warning("You may need to manually place jarvis.onnx in your models directory.")
            else:
                print_success("Jarvis wake-word model already exists.")
        else:
            # Copy user custom model
            src_model_path = Path(wake_word_choice).expanduser().resolve()
            if src_model_path.exists() and src_model_path.suffix in ['.onnx', '.tflite']:
                target_path = custom_dir / "models" / src_model_path.name
                shutil.copy2(src_model_path, target_path)
                wake_word_model = src_model_path.name
                print_success(f"Copied custom wake word model {src_model_path.name} to {target_path}")
            else:
                print_error(f"File {wake_word_choice} does not exist or is not a valid model file.")
                print_warning("Falling back to default 'jarvis.onnx'. Please place your model inside custom directory manually.")
                wake_word_model = "jarvis.onnx"

    # 4. Generate .env file
    print_info("Generating .env configuration...")
    env_content = f"""# Generated by install.py - DO NOT COMMIT TO GIT
ETHERFIELDS_CUSTOM_DIR={custom_dir_str}
ENABLE_VOICE={str(enable_voice)}
WAKE_WORD_MODEL={wake_word_model}
"""
    with open(".env", "w") as f:
        f.write(env_content)
    print_success("Generated local '.env' successfully.")

    return enable_voice, custom_dir


def handle_voice_tools(enable_voice):
    if not enable_voice:
        return

    print_info("Installing global transcription tool `openai-whisper` via uv...")
    try:
        # Run uv tool install openai-whisper
        subprocess.run(["uv", "tool", "install", "openai-whisper"], check=True)
        print_success("Successfully installed openai-whisper tool.")
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install openai-whisper: {e}")
        print_warning("Ensure you have network access and try running manually: `uv tool install openai-whisper`")


def handle_rulebook_pdf(custom_dir):
    # Rulebook PDF check
    local_pdf = Path("Rulebook_20.pdf")
    custom_pdf_path = custom_dir / "Rulebook_20.pdf"

    # If PDF is already in CWD, move/copy it to the custom directory
    if local_pdf.exists() and not custom_pdf_path.exists():
        print_info(f"Moving local Rulebook_20.pdf to custom directory: {custom_pdf_path}")
        shutil.move(local_pdf, custom_pdf_path)

    if not custom_pdf_path.exists():
        print_warning("Rulebook_20.pdf was not found in the custom directory.")
        default_url = "https://awakenrealms.com/images/download/etherfields/ENG/Etherfields_Rulebook_20_280x280mm-PAGES-20.pdf"
        pdf_input = ask_input("Enter local path to the Rulebook v2.0 PDF, or a URL to download it", default_url)

        if pdf_input.startswith("http://") or pdf_input.startswith("https://"):
            print_info("Downloading Rulebook_20.pdf from Awaken Realms...")
            try:
                urllib.request.urlretrieve(pdf_input, custom_pdf_path)
                print_success(f"Downloaded rulebook successfully to {custom_pdf_path}")
            except Exception as e:
                print_error(f"Failed to download rulebook: {e}")
                print_warning(f"Please manually download the rulebook v2.0 and save it as {custom_pdf_path}")
        else:
            user_pdf = Path(pdf_input).expanduser().resolve()
            if user_pdf.exists():
                shutil.copy2(user_pdf, custom_pdf_path)
                print_success(f"Copied rulebook from {user_pdf} to {custom_pdf_path}")
            else:
                print_error(f"Specified local path does not exist: {user_pdf}")
                print_warning(f"Please manually place Rulebook_20.pdf into {custom_dir}")

    # Now run the validation/regeneration script
    if custom_pdf_path.exists():
        print_info("Triggering Rulebook validation and cache building...")
        try:
            # We run rulebook_tool.py --validate via uv run
            # Note: we need to ensure the script itself loads the custom dir .env, which we will implement next.
            subprocess.run(["uv", "run", "rulebook_tool.py", "--validate"], check=True)
            print_success("Rulebook cache validated and initialized successfully.")
        except subprocess.CalledProcessError as e:
            print_error(f"Failed to validate rulebook cache: {e}")
    else:
        print_warning("Skipping rulebook validation because PDF is missing. Please add the PDF and run `uv run rulebook_tool.py --validate` later.")


def warmup_dependencies(enable_voice):
    if not enable_voice:
        return

    print_info("Warming up Python voice dependency caches...")
    try:
        # We perform a dry-run / help output to warm up uv script-level virtual environment
        subprocess.run(["uv", "run", "voice/voice_listener.py", "--list-models"], check=True)
        print_success("Voice assistant dependency cache warmed up.")
    except subprocess.CalledProcessError as e:
        print_warning(f"Dry-run dependency warm-up exited with an error (this might be normal if audio devices aren't ready): {e}")


def detect_hardware():
    # 1. Check for Apple Silicon Mac
    if sys.platform == "darwin":
        try:
            # check CPU brand
            brand = subprocess.getoutput("sysctl -n machdep.cpu.brand_string")
            if "apple" in brand.lower() or "m1" in brand.lower() or "m2" in brand.lower() or "m3" in brand.lower():
                return "mps"
        except Exception:
            pass

    # 2. Check for NVIDIA CUDA
    if shutil.which("nvidia-smi"):
        return "cuda"

    return "cpu"


def select_hardware_acceleration():
    detected = detect_hardware()
    print_info(f"Hardware Detection: Detected {detected.upper()} acceleration capability.")
    print("Select your desired installation target:")
    print("  1) GPU (MPS - Apple Silicon Mac)")
    print("  2) GPU (CUDA - NVIDIA Graphics Cards)")
    print("  3) CPU Only (Lightweight, default on most systems)")

    # Set default choice based on detection
    if detected == "mps":
        default_choice = "1"
    elif detected == "cuda":
        default_choice = "2"
    else:
        default_choice = "3"

    choice = ask_input("Select target (1-3)", default_choice)
    if choice == "1":
        return "mps"
    elif choice == "2":
        return "cuda"
    else:
        return "cpu"


def sync_environment(target):
    print_info(f"Synchronizing environment and installing developer tools via `uv sync` ({target.upper()} optimized)...")
    try:
        if target == "cuda":
            cmd = ["uv", "sync", "--index-url", "https://download.pytorch.org/whl/cu121", "--extra-index-url", "https://pypi.org/simple"]
            subprocess.run(cmd, check=True)
            print_info("Installing onnxruntime-gpu for CUDA-accelerated wake word detection...")
            subprocess.run(["uv", "pip", "install", "onnxruntime-gpu"], check=True)
        elif target == "cpu":
            cmd = ["uv", "sync", "--index-url", "https://download.pytorch.org/whl/cpu", "--extra-index-url", "https://pypi.org/simple"]
            subprocess.run(cmd, check=True)
        else: # mps / default
            subprocess.run(["uv", "sync"], check=True)

        print_success("Project environment synced successfully (dependencies and dev tools installed).")
    except subprocess.CalledProcessError as e:
        print_warning(f"Failed to synchronize environment: {e}")


def main():
    print("=" * 60)
    print("🌌  Etherfields AI Rule Master & Retriever Setup Wizard  🌌")
    print("=" * 60)

    check_prerequisites()
    print("-" * 60)

    target = select_hardware_acceleration()
    print("-" * 60)

    sync_environment(target)
    print("-" * 60)

    enable_voice, custom_dir = setup_directories_and_env()
    print("-" * 60)

    handle_voice_tools(enable_voice)
    print("-" * 60)

    handle_rulebook_pdf(custom_dir)
    print("-" * 60)

    warmup_dependencies(enable_voice)

    print("=" * 60)
    print("\033[92m🎉  Installation and configuration completed successfully!  🎉\033[0m")
    print("-" * 60)
    print("Next Steps:")
    print(f" 1. Custom Directory: {custom_dir}")
    print(" 2. To run the rule master lookup directly:")
    print("    `uv run rulebook_tool.py --search \"<term>\"`")
    if enable_voice:
        print(" 3. To run the continuous hands-free voice listener:")
        print("    `uv run voice/voice_listener.py`")
        print(" 4. Remember that you can drop additional custom .onnx wake-word models")
        print(f"    directly into {custom_dir}/models/ for parallel wake-word support!")
    print("=" * 60)

if __name__ == "__main__":
    main()
