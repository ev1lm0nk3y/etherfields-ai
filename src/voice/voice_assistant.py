# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "kokoro-onnx>=0.3.0",
#     "onnxruntime>=1.16.0",
#     "soundfile>=0.12.1",
#     "numpy>=1.26.0",
# ]
# ///

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

BASE_DIR = "/Users/ryan/Documents/etherfields-ai"


def load_env_vars():
    env_vars = {}
    env_path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    env_vars[key.strip()] = val.strip()
    return env_vars


_env = load_env_vars()
CUSTOM_DIR_STR = _env.get("ETHERFIELDS_LOCAL_DIR", BASE_DIR)
CUSTOM_DIR = os.path.abspath(os.path.expanduser(os.path.expandvars(CUSTOM_DIR_STR)))

SCRIPTS_CACHE_PATH = os.path.join(BASE_DIR, "secret_scripts_cache.json")
AUDIO_CACHE_DIR = os.path.abspath(os.path.join(CUSTOM_DIR, "voice", "cache"))
DEFAULT_MODELS_DIR = os.path.abspath(os.path.join(CUSTOM_DIR, "voice", "models"))

# Ensure directories exist
os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)
os.makedirs(DEFAULT_MODELS_DIR, exist_ok=True)

# Custom Audio Player Setup (Defaulting per-platform)
import platform

_default_player = "afplay"
if platform.system() == "Linux":
    _default_player = "aplay"
elif platform.system() == "Windows":
    _default_player = "start"

AUDIO_PLAYER = _env.get("AUDIO_PLAYER", _default_player)


def play_audio_file(file_path):
    import shlex

    cmd = shlex.split(AUDIO_PLAYER) + [file_path]
    try:
        subprocess.run(cmd, check=True)
    except Exception as e:
        print(
            f"[Playback Error] Failed to play audio file using player command '{AUDIO_PLAYER}': {e}",
            file=sys.stderr,
        )


# Global variable for local Kokoro TTS instance
_kokoro_instance = None


def get_kokoro():
    global _local_chatterbox_instance, _stt_model, _kokoro_instance
    # Re-using a module level caching pattern
    global _stt_model
    try:
        import kokoro_onnx
    except ImportError:
        print("[Local TTS] Error: kokoro-onnx package is not installed.", file=sys.stderr)
        return None

    # Resolve paths
    model_path = os.path.join(DEFAULT_MODELS_DIR, "kokoro-v1.0.onnx")
    voices_path = os.path.join(DEFAULT_MODELS_DIR, "voices-v1.0.bin")

    # Auto-heal/download models if missing
    if not os.path.exists(model_path) or not os.path.exists(voices_path):
        os.makedirs(DEFAULT_MODELS_DIR, exist_ok=True)
        print("[Local TTS] downloading missing Kokoro model files...", flush=True)
        try:
            if not os.path.exists(model_path):
                url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
                print(f"[Download] Downloading model from {url}...")
                urllib.request.urlretrieve(url, model_path)
            if not os.path.exists(voices_path):
                url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"
                print(f"[Download] Downloading voices binary from {url}...")
                urllib.request.urlretrieve(url, voices_path)
            print("[Local TTS] Kokoro model files synchronized successfully.")
        except Exception as e:
            print(f"[Local TTS Error] Failed to download Kokoro files: {e}", file=sys.stderr)
            return None

    global _kokoro_instance
    if _kokoro_instance is None:
        print("[Local TTS] Initializing local kokoro-onnx engine...", flush=True)
        try:
            from kokoro_onnx import Kokoro

            _kokoro_instance = Kokoro(model_path, voices_path)
        except Exception as e:
            print(f"[Local TTS Error] Failed to load Kokoro engine: {e}", file=sys.stderr)
            return None
    return _kokoro_instance


def speak_text_kokoro(text, voice="bm_george", speed=1.0, output_path=None, play_audio=True):
    if output_path and os.path.exists(output_path):
        if play_audio:
            print("[Local TTS] Playing cached audio...", flush=True)
            play_audio_file(output_path)
        return True

    kokoro = get_kokoro()
    if kokoro is None:
        return False

    try:
        import soundfile as sf

        print(
            f"[Local TTS] Generating local speech (Voice: {voice}, Speed: {speed})...", flush=True
        )
        samples, sample_rate = kokoro.create(text, voice=voice, speed=speed, lang="en-us")

        save_path = output_path
        if not save_path:
            temp_f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            save_path = temp_f.name
            temp_f.close()

        sf.write(save_path, samples, sample_rate)

        if play_audio:
            try:
                play_audio_file(save_path)
            finally:
                if not output_path and os.path.exists(save_path):
                    os.remove(save_path)
        return True
    except Exception as e:
        print(f"[Local TTS Error] Generation failed: {e}", file=sys.stderr)
        return False


def speak_text_openai(text, voice="onyx", speed=1.0, output_path=None, play_audio=True):
    if output_path and os.path.exists(output_path):
        if play_audio:
            print("[OpenAI TTS] Playing cached audio...", flush=True)
            play_audio_file(output_path)
        return True

    api_key = _env.get("OPENAI_API_KEY", "")
    if not api_key:
        print("[OpenAI TTS Error] OPENAI_API_KEY is missing from .env file.", file=sys.stderr)
        return False

    url = "https://api.openai.com/v1/audio/speech"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": "tts-1", "input": text, "voice": voice, "speed": speed}

    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
        )
        print("[OpenAI TTS] Connecting to cloud speech synthesizer...", flush=True)
        with urllib.request.urlopen(req) as response:
            audio_data = response.read()

        save_path = output_path
        if not save_path:
            temp_f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            save_path = temp_f.name
            temp_f.close()

        with open(save_path, "wb") as f:
            f.write(audio_data)

        if play_audio:
            try:
                play_audio_file(save_path)
            finally:
                if not output_path and os.path.exists(save_path):
                    os.remove(save_path)
        return True
    except Exception as e:
        print(f"[OpenAI TTS Error] Generation failed: {e}", file=sys.stderr)
        return False


def speak_text_elevenlabs(
    text, voice_id="pNInz6obpg7ANgFlW75D", speed=1.0, output_path=None, play_audio=True
):
    if output_path and os.path.exists(output_path):
        if play_audio:
            print("[ElevenLabs TTS] Playing cached audio...", flush=True)
            play_audio_file(output_path)
        return True

    api_key = _env.get("ELEVENLABS_API_KEY", "")
    if not api_key:
        print(
            "[ElevenLabs TTS Error] ELEVENLABS_API_KEY is missing from .env file.", file=sys.stderr
        )
        return False

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    payload = {
        "text": text,
        "model_id": "eleven_flash_v2_5",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "speed": speed},
    }

    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
        )
        print("[ElevenLabs TTS] Connecting to cloud speech synthesizer...", flush=True)
        with urllib.request.urlopen(req) as response:
            audio_data = response.read()

        save_path = output_path
        if not save_path:
            temp_f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            save_path = temp_f.name
            temp_f.close()

        with open(save_path, "wb") as f:
            f.write(audio_data)

        if play_audio:
            try:
                play_audio_file(save_path)
            finally:
                if not output_path and os.path.exists(save_path):
                    os.remove(save_path)
        return True
    except Exception as e:
        print(f"[ElevenLabs TTS Error] Generation failed: {e}", file=sys.stderr)
        return False


def speak_text(text, voice=None, speed=1.0, output_path=None, play_audio=True, engine=None):
    engine = (engine or _env.get("TTS_ENGINE", "kokoro")).lower()

    if engine == "kokoro":
        resolved_voice = voice or _env.get("VOICE_REF_NARRATIVE", "bm_george")
        return speak_text_kokoro(text, resolved_voice, speed, output_path, play_audio)
    elif engine == "openai":
        resolved_voice = voice or _env.get("VOICE_REF_NARRATIVE", "onyx")
        return speak_text_openai(text, resolved_voice, speed, output_path, play_audio)
    elif engine == "elevenlabs":
        resolved_voice = voice or _env.get("VOICE_REF_NARRATIVE", "pNInz6obpg7ANgFlW75D")
        return speak_text_elevenlabs(text, resolved_voice, speed, output_path, play_audio)
    else:
        # Fallback
        resolved_voice = voice or "bm_george"
        return speak_text_kokoro(text, resolved_voice, speed, output_path, play_audio)


def lookup_secret_script(script_num):
    if not os.path.exists(SCRIPTS_CACHE_PATH):
        print(f"Error: Secret scripts cache missing at {SCRIPTS_CACHE_PATH}.", file=sys.stderr)
        return None

    try:
        with open(SCRIPTS_CACHE_PATH, "r", encoding="utf-8") as f:
            scripts = json.load(f)
    except Exception as e:
        print(f"Error reading cache: {e}", file=sys.stderr)
        return None

    script_num_str = str(script_num).strip().lstrip("0")
    if not script_num_str:
        script_num_str = "0"
    return scripts.get(script_num_str)


def clean_script_text(text):
    clean = text.replace("*", "").replace("`", "").replace("\n", " ").strip()
    clean = re.sub(r"\{\s*\d*(?:\.\d+)?s\s*\}", " ", clean)
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip()


def pre_cache_scripts(script_nums, args):
    print("\n" + "=" * 60)
    print(f"ETHERFIELDS RULE MASTER - PRE-CACHING SCRIPTS (Engine: {args.engine})")
    print(f"Processing {len(script_nums)} scripts...")
    print("=" * 60 + "\n")

    success_count = 0
    fail_count = 0
    skipped_count = 0

    for num in script_nums:
        script_obj = lookup_secret_script(num)
        if not script_obj:
            print(f"❌ Script '{num}' not found in cache.")
            fail_count += 1
            continue

        narrative = script_obj.get("narrative", "").strip() if isinstance(script_obj, dict) else ""
        instructions = (
            script_obj.get("instructions", "").strip() if isinstance(script_obj, dict) else ""
        )

        print(f"\n--- Script {num} ---")

        # 1. Narrative
        if narrative:
            narrative_path = os.path.join(AUDIO_CACHE_DIR, f"script_{num}_narrative.wav")
            if os.path.exists(narrative_path):
                print(f"  ✓ Narrative already cached at {os.path.basename(narrative_path)}")
                skipped_count += 1
            else:
                clean_narr = clean_script_text(narrative)
                voice = args.voice or _env.get("VOICE_REF_NARRATIVE")
                ok = speak_text(
                    clean_narr,
                    voice,
                    args.speed,
                    output_path=narrative_path,
                    play_audio=False,
                    engine=args.engine,
                )
                if ok:
                    success_count += 1
                else:
                    fail_count += 1

        # 2. Instructions
        if instructions:
            instructions_path = os.path.join(AUDIO_CACHE_DIR, f"script_{num}_instructions.wav")
            if os.path.exists(instructions_path):
                print(f"  ✓ Instructions already cached at {os.path.basename(instructions_path)}")
                skipped_count += 1
            else:
                clean_inst = clean_script_text(instructions)
                voice = _env.get("VOICE_REF_INSTRUCTION")
                ok = speak_text(
                    clean_inst,
                    voice,
                    args.speed,
                    output_path=instructions_path,
                    play_audio=False,
                    engine=args.engine,
                )
                if ok:
                    success_count += 1
                else:
                    fail_count += 1

    print("\n" + "=" * 60)
    print("PRE-CACHING COMPLETED")
    print(f"Successfully cached: {success_count} files")
    print(f"Already cached: {skipped_count} files")
    print(f"Failed/Missing: {fail_count}")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Etherfields Rule Master Voice Assistant")
    parser.add_argument("--text", type=str, help="Convert custom text to speech and play it")
    parser.add_argument("--script", type=str, help="Look up a secret script and play it")
    parser.add_argument(
        "--voice", type=str, help="Voice ID / name override (for Kokoro, OpenAI, or ElevenLabs)"
    )
    parser.add_argument(
        "--engine",
        type=str,
        choices=["kokoro", "openai", "elevenlabs"],
        help="TTS Engine to use (default loaded from .env)",
    )
    parser.add_argument("--speed", type=float, default=1.0, help="Speech speed (default: 1.0)")
    parser.add_argument(
        "--interactive", action="store_true", help="Run in persistent interactive mode"
    )
    parser.add_argument(
        "--pre-cache", type=str, help="Pre-cache a comma-separated list of script numbers silently"
    )
    parser.add_argument(
        "--filename",
        type=str,
        help="Specify a custom filename to save/read the cached audio (e.g. 'topic_stun')",
    )

    args = parser.parse_args()

    # Load default engine if not specified
    if not args.engine:
        args.engine = _env.get("TTS_ENGINE", "kokoro").lower()

    if not args.text and not args.script and not args.interactive and not args.pre_cache:
        parser.print_help()
        sys.exit(0)

    # 1. Pre-caching Option
    if args.pre_cache:
        raw_nums = [s.strip() for s in args.pre_cache.split(",") if s.strip()]
        script_nums = [n.lstrip("0") if n.lstrip("0") else "0" for n in raw_nums]
        pre_cache_scripts(script_nums, args)
        sys.exit(0)

    # 2. Interactive Loop Option
    if args.interactive:
        print("\n" + "=" * 60)
        print("ETHERFIELDS RULE MASTER - INTERACTIVE VOICE ASSISTANT")
        print(f"Engine: {args.engine.upper()}")
        print("Type a script number (e.g. 777), type custom text directly,")
        print("or type 'exit' or 'quit' to close.")
        print("=" * 60 + "\n")

        # Warm up Kokoro
        if args.engine == "kokoro":
            get_kokoro()

        while True:
            try:
                user_input = input("\nEnter script number or custom text > ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ["exit", "quit"]:
                    print("Exiting interactive mode. Goodbye!")
                    break

                if user_input.isdigit():
                    script_obj = lookup_secret_script(user_input)
                    if not script_obj:
                        print(f"Script '{user_input}' not found in cache.")
                        continue

                    print(f"\nSECRET SCRIPT: {user_input}")
                    print("-" * 60)
                    if isinstance(script_obj, dict) and "narrative" in script_obj:
                        print(script_obj["narrative"])
                        print("\n--- INSTRUCTIONS ---")
                        print(script_obj["instructions"])
                    else:
                        print(script_obj)
                    print("-" * 60)

                    if isinstance(script_obj, dict) and "narrative" in script_obj:
                        narrative = script_obj.get("narrative", "").strip()
                        instructions = script_obj.get("instructions", "").strip()

                        narr_path = os.path.join(
                            AUDIO_CACHE_DIR, f"script_{user_input}_narrative.wav"
                        )
                        inst_path = os.path.join(
                            AUDIO_CACHE_DIR, f"script_{user_input}_instructions.wav"
                        )

                        if narrative:
                            clean_narrative = clean_script_text(narrative)
                            if os.path.exists(narrative_path := narr_path):
                                print(
                                    f"[TTS] Playing cached NARRATIVE audio: {os.path.basename(narrative_path)}..."
                                )
                            else:
                                print(f"[TTS] Synthesizing narrative...")
                            speak_text(
                                clean_narrative,
                                args.voice,
                                args.speed,
                                output_path=narr_path,
                                engine=args.engine,
                            )

                        if instructions:
                            clean_instructions = clean_script_text(instructions)
                            inst_voice = _env.get("VOICE_REF_INSTRUCTION")
                            if os.path.exists(instructions_path := inst_path):
                                print(
                                    f"[TTS] Playing cached INSTRUCTIONS audio: {os.path.basename(instructions_path)}..."
                                )
                            else:
                                print(f"[TTS] Synthesizing instructions...")
                            speak_text(
                                clean_instructions,
                                inst_voice,
                                args.speed,
                                output_path=inst_path,
                                engine=args.engine,
                            )
                    else:
                        clean_text = clean_script_text(str(script_obj))
                        speak_text(clean_text, args.voice, args.speed, engine=args.engine)
                else:
                    clean_text = clean_script_text(user_input)
                    speak_text(clean_text, args.voice, args.speed, engine=args.engine)
            except KeyboardInterrupt:
                print("\nExiting interactive mode. Goodbye!")
                break
            except Exception as e:
                print(f"An error occurred in interactive loop: {e}")
        sys.exit(0)

    # 3. Direct convert Text Option
    if args.text:
        clean_text = clean_script_text(args.text)
        output_path = None
        if args.filename:
            output_path = os.path.join(AUDIO_CACHE_DIR, f"{args.filename}.wav")
        else:
            # Hash text for stable default cache filename if no name was specified
            txt_hash = hashlib.md5(clean_text.encode("utf-8")).hexdigest()[:12]
            output_path = os.path.join(AUDIO_CACHE_DIR, f"text_{txt_hash}.wav")

        speak_text(clean_text, args.voice, args.speed, output_path=output_path, engine=args.engine)

    # 4. Direct play Script Option
    elif args.script:
        script_obj = lookup_secret_script(args.script)
        if not script_obj:
            print(f"Script '{args.script}' not found in cache.", file=sys.stderr)
            sys.exit(1)

        if isinstance(script_obj, dict) and "narrative" in script_obj:
            narrative = script_obj.get("narrative", "").strip()
            instructions = script_obj.get("instructions", "").strip()

            narr_path = os.path.join(AUDIO_CACHE_DIR, f"script_{args.script}_narrative.wav")
            inst_path = os.path.join(AUDIO_CACHE_DIR, f"script_{args.script}_instructions.wav")

            if narrative:
                clean_narrative = clean_script_text(narrative)
                if os.path.exists(narr_path):
                    print(f"[TTS] Playing cached NARRATIVE audio: {os.path.basename(narr_path)}...")
                speak_text(
                    clean_narrative,
                    args.voice,
                    args.speed,
                    output_path=narr_path,
                    engine=args.engine,
                )

            if instructions:
                clean_instructions = clean_script_text(instructions)
                inst_voice = _env.get("VOICE_REF_INSTRUCTION")
                if os.path.exists(inst_path):
                    print(
                        f"[TTS] Playing cached INSTRUCTIONS audio: {os.path.basename(inst_path)}..."
                    )
                speak_text(
                    clean_instructions,
                    inst_voice,
                    args.speed,
                    output_path=inst_path,
                    engine=args.engine,
                )
        else:
            clean_text = clean_script_text(str(script_obj))
            output_path = os.path.join(AUDIO_CACHE_DIR, f"script_{args.script}.wav")
            speak_text(
                clean_text, args.voice, args.speed, output_path=output_path, engine=args.engine
            )


if __name__ == "__main__":
    main()
