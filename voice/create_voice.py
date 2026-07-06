# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "sounddevice",
#     "soundfile",
#     "numpy",
# ]
# ///

import os
import shutil
import sys
import time
from pathlib import Path

# Repo root is parent of the directory of this file
REPO_ROOT = Path(__file__).resolve().parent.parent

def load_env_vars():
    env_vars = {}
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    env_vars[key.strip()] = val.strip()
    return env_vars

def save_env_vars(env_vars):
    env_path = REPO_ROOT / ".env"
    # Read existing lines to preserve comments
    lines = []
    if env_path.exists():
        with open(env_path, "r") as f:
            lines = f.readlines()

    updated_keys = set()
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, val = stripped.split("=", 1)
            key_clean = key.strip()
            if key_clean in env_vars:
                new_lines.append(f"{key_clean}={env_vars[key_clean]}\n")
                updated_keys.add(key_clean)
                continue
        new_lines.append(line)

    # Append any keys that weren't already in .env
    for key, val in env_vars.items():
        if key not in updated_keys:
            # Add a newline if file doesn't end with one
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines[-1] = new_lines[-1] + "\n"
            new_lines.append(f"{key}={val}\n")

    with open(env_path, "w") as f:
        f.writelines(new_lines)

def print_info(text):
    print(f"\033[94mℹ️  [Info] {text}\033[0m")

def print_success(text):
    print(f"\033[92m✅  [Success] {text}\033[0m")

def print_error(text):
    print(f"\033[91m❌  [Error] {text}\033[0m", file=sys.stderr)

def ask_input(prompt, default=None):
    if default is not None:
        val = input(f"{prompt} [{default}]: ").strip()
        return val if val else default
    return input(f"{prompt}: ").strip()

def ask_choice(prompt, options):
    print(prompt)
    for k, v in options.items():
        print(f"  {k}) {v}")
    while True:
        choice = input("Enter choice: ").strip().lower()
        if choice in options:
            return choice
        print("Invalid choice. Please try again.")

def main():
    print("=" * 60)
    print("🌌  Etherfields Voice Profile Creator & Cloner Wizard  🌌")
    print("=" * 60)

    _env = load_env_vars()
    custom_dir_str = _env.get("ETHERFIELDS_LOCAL_DIR", str(REPO_ROOT))
    custom_dir = Path(custom_dir_str).expanduser().resolve()
    models_dir = custom_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    # 1. Select Role
    role_choice = ask_choice(
        "Select the voice role you would like to create/clonify:",
        {
            "1": "Narrative (For emotional narrative, dreamworld descriptions, secret scripts)",
            "2": "Instruction (For neutral rulebooks, game steps, card setup guidelines)"
        }
    )
    role_name = "NARRATIVE" if role_choice == "1" else "INSTRUCTION"
    role_filename = f"voice_ref_{role_name.lower()}.wav"
    target_path = models_dir / role_filename

    # 2. Select Source
    source_choice = ask_choice(
        "\nHow would you like to provide the voice reference?",
        {
            "1": "Record a fresh 6-second sample right now using your microphone",
            "2": "Provide an existing local .wav audio file"
        }
    )

    if source_choice == "1":
        # Recording with sounddevice
        try:
            import numpy as np
            import sounddevice as sd
            import soundfile as sf
        except ImportError:
            print_error("Failed to load audio recording dependencies (sounddevice, soundfile, numpy).")
            sys.exit(1)

        print("\n" + "-" * 50)
        print("🎤 [Voice Recording Setup]")
        print("Chatterbox works best with clean, clear vocals.")
        print("Prepare to speak a sample phrase. Recommended phrases:")
        if role_name == "NARRATIVE":
            print("  >>> 'In the middle of the deep slumber, a strange shadow rises. Discard one turn card and suffer one damage.'")
        else:
            print("  >>> 'Flip the rulebook to page fifteen. Place the active token onto the map space and prepare for setup.'")
        print("-" * 50 + "\n")

        ready = input("Press [Enter] when ready to record for 6 seconds...")

        # Audio parameters
        sample_rate = 16000
        channels = 1
        duration = 6.0  # seconds (Chatterbox recommends > 5.1s to avoid padding)

        print("\n🔴 Recording starting in...")
        for i in range(3, 0, -1):
            print(f"   {i}...")
            time.sleep(1.0)

        print("\n🎤 RECORDING NOW... (Speak clearly!)")
        try:
            # Trigger OS beep if on macOS
            if sys.platform == "darwin":
                os.system('printf "\a"')

            audio_data = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=channels, dtype='float32')

            # Show a simple progress bar
            for s in range(int(duration)):
                time.sleep(1.0)
                progress = "#" * (s + 1) + " " * (int(duration) - s - 1)
                print(f"\r   [{progress}] {s+1}/6s", end="", flush=True)
            sd.wait()

            print("\n⏹️ Recording completed!\n")

            # Save the WAV file
            sf.write(str(target_path), audio_data, sample_rate)
            print_success(f"Successfully recorded and saved voice profile to: {target_path}")

        except Exception as e:
            print_error(f"Failed to record audio from microphone: {e}")
            sys.exit(1)

    else:
        # Existing file path
        while True:
            file_path_str = ask_input("\nEnter the absolute or relative path to your local .wav file")
            file_path = Path(file_path_str).expanduser().resolve()
            if file_path.exists() and file_path.suffix.lower() == '.wav':
                break
            print_error("Specified file does not exist or is not a .wav file. Please try again.")

        try:
            print_info("Copying reference file to custom directory...")
            shutil.copy2(file_path, target_path)
            print_success(f"Successfully registered custom voice profile: {target_path}")
        except Exception as e:
            print_error(f"Failed to copy file: {e}")
            sys.exit(1)

    # 3. Save to .env
    print_info("Updating your local environment configuration...")
    env_vars = {
        f"VOICE_REF_{role_name}": str(target_path)
    }
    save_env_vars(env_vars)
    print_success(f"Added VOICE_REF_{role_name} override path in '.env'!")

    print("\n" + "=" * 60)
    print("\033[92m🎉  Voice Profile Successfully Setup!  🎉\033[0m")
    print("-" * 60)
    print(f" Role: {role_name}")
    print(f" Profile WAV: {target_path}")
    print(" This voice will now be automatically cloned offline during active gameplay!")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
