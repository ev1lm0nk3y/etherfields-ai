# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "nanowakeword",
#     "openwakeword",
#     "sounddevice",
#     "soundfile",
#     "numpy==1.26.4",
#     "pyyaml",
# ]
# ///

import argparse
import os
import subprocess
import sys
import time

import numpy as np
import sounddevice as sd
import soundfile as sf

# Try importing nanowakeword
try:
    from nanowakeword import NanoInterpreter
    HAS_NANOWAKEWORD = True
except ImportError:
    HAS_NANOWAKEWORD = False

# Try importing openwakeword
try:
    import openwakeword
    from openwakeword.model import Model as OWWModel
    HAS_OPENWAKEWORD = True
except ImportError:
    HAS_OPENWAKEWORD = False

# Repo root is parent of the directory of this file
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_env_vars():
    env_vars = {}
    env_path = os.path.join(REPO_ROOT, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    env_vars[key.strip()] = val.strip()
    return env_vars

_env = load_env_vars()
CUSTOM_DIR_STR = _env.get("ETHERFIELDS_LOCAL_DIR", REPO_ROOT)
CUSTOM_DIR = os.path.abspath(os.path.expanduser(os.path.expandvars(CUSTOM_DIR_STR)))
DEFAULT_MODELS_DIR = os.path.join(CUSTOM_DIR, "models")
DEFAULT_AUDIO_CACHE_DIR = os.path.join(CUSTOM_DIR, "audio_cache")

# Global Audio Parameters
SAMPLE_RATE = 16000  # openWakeWord and Whisper expect 16kHz
CHANNELS = 1
CHUNK_SIZE = 1280  # Chunks fed into openWakeWord


def record_question(silence_threshold=0.03, silence_duration=1.5, max_duration=15.0):
    """
    Records audio from the microphone until silence is detected or max duration is reached.
    """
    print("\n🎤 [Listening] Speak your question now...", flush=True)
    # macOS system beep to signal start
    os.system('printf "\a"')

    recording = []
    silence_start = None
    start_time = time.time()

    # Callback to append audio frames
    def callback(indata, frames, time_info, status):
        recording.append(indata.copy())

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=callback):
        while True:
            sd.sleep(100)
            elapsed = time.time() - start_time
            if elapsed > max_duration:
                print("[Record] Reached maximum recording duration.", flush=True)
                break

            if len(recording) > 0:
                # Check volume of the last 1 second of audio
                recent_data = (
                    np.concatenate(recording[-10:])
                    if len(recording) >= 10
                    else np.concatenate(recording)
                )
                volume = np.linalg.norm(recent_data) / np.sqrt(len(recent_data))

                # Silence detection
                if volume < silence_threshold:
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start > silence_duration:
                        print("[Record] Silence detected. Stopping...", flush=True)
                        break
                else:
                    silence_start = None

    print("[Record] Processing audio...", flush=True)
    audio_data = np.concatenate(recording)
    temp_wav_dir = DEFAULT_AUDIO_CACHE_DIR if os.path.exists(DEFAULT_AUDIO_CACHE_DIR) else os.getcwd()
    temp_wav = os.path.join(temp_wav_dir, "question_temp.wav")
    sf.write(temp_wav, audio_data, SAMPLE_RATE)
    return temp_wav


def transcribe_audio(wav_path):
    """
    Invokes the globally-installed Whisper tool to transcribe the WAV file.
    """
    print("[Whisper STT] Transcribing audio file...", flush=True)
    try:
        # Run Whisper CLI (installed globally via uv tool install)
        result = subprocess.run(
            [
                "whisper",
                wav_path,
                "--model",
                "base",
                "--language",
                "en",
                "--output_format",
                "txt",
            ],
            capture_output=True,
            text=True,
        )

        txt_path = wav_path.replace(".wav", ".txt")
        if os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8") as f:
                transcription = f.read().strip()

            # Clean up generated whisper artifact files
            os.remove(wav_path)
            os.remove(txt_path)
            for ext in [".vtt", ".srt", ".tsv", ".json"]:
                p = wav_path.replace(".wav", ext)
                if os.path.exists(p):
                    os.remove(p)

            return transcription
        else:
            print(
                "[Whisper STT] Error: Transcription output file not found.",
                file=sys.stderr,
            )
            if os.path.exists(wav_path):
                os.remove(wav_path)
    except Exception as e:
        print(f"[Whisper STT] Error during transcription process: {e}", file=sys.stderr)
        if os.path.exists(wav_path):
            os.remove(wav_path)
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Etherfields Rule Master Wake-Word Listener"
    )
    parser.add_argument(
        "--model-path",
        type=str,
        help="Path to a custom .onnx wake word model (or a comma-separated list of paths)",
    )
    parser.add_argument(
        "--models-dir",
        type=str,
        default=DEFAULT_MODELS_DIR,
        help=f"Directory containing custom .onnx models (default: {DEFAULT_MODELS_DIR})",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        help="Specify a custom model name/substring to load from --models-dir (default: load all found models)",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List all available custom models in --models-dir and exit",
    )
    parser.add_argument(
        "--inference-framework",
        type=str,
        default="onnx",
        choices=["onnx", "tflite"],
        help="Inference framework to use (default: onnx)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.3,
        help="Wake word activation threshold (0.0 to 1.0, default: 0.3)",
    )
    parser.add_argument(
        "--silence-threshold",
        type=float,
        default=0.03,
        help="Silence volume threshold for stopping recording (default: 0.03)",
    )
    parser.add_argument(
        "--preamble",
        type=str,
        default="Please give a highly concise, direct, and conversational 1-3 sentence answer suitable for text-to-speech reading. Question: ",
        help="Preamble to prepend to transcribed text on the clipboard (default: concise spoken instructions)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print real-time audio volume and model scores for debugging",
    )
    parser.add_argument(
        "--engine",
        type=str,
        default="auto",
        choices=["auto", "nanowakeword", "openwakeword"],
        help="The wake-word detection engine to use (default: auto)",
    )

    args = parser.parse_args()

    # Resolve models directory path
    models_dir = args.models_dir
    if not os.path.isabs(models_dir):
        models_dir = os.path.join(os.getcwd(), models_dir)

    # Discover custom .onnx files
    custom_onnx_files = []
    if os.path.exists(models_dir) and os.path.isdir(models_dir):
        custom_onnx_files = [
            os.path.join(models_dir, f)
            for f in os.listdir(models_dir)
            if f.endswith(".onnx")
        ]
        custom_onnx_files.sort()

    # Handle list models request
    if args.list_models:
        print(f"\n📁 Scanning models directory: {models_dir}")
        if not os.path.exists(models_dir):
            print("  ❌ Directory does not exist.")
        elif not custom_onnx_files:
            print("  ⚠️ No custom .onnx models found.")
        else:
            print("  ✨ Found the following custom .onnx wake word models:")
            for f in custom_onnx_files:
                filename = os.path.basename(f)
                size_kb = os.path.getsize(f) / 1024
                print(f"    - {filename} ({size_kb:.1f} KB)")
        print()
        sys.exit(0)

    print(f"[Voice Listener] Loading wake-word engine (Engine: {args.engine})...", flush=True)

    # Build the list of models to load
    model_paths = []
    if args.model_path:
        # User specified explicit path(s) (allow comma-separated list)
        explicit_paths = [p.strip() for p in args.model_path.split(",")]
        for p in explicit_paths:
            if not os.path.exists(p):
                print(
                    f"Error: Specified model path does not exist: {p}", file=sys.stderr
                )
                sys.exit(1)
            model_paths.append(p)
    elif args.model_name:
        # Filter files in models_dir by given model name
        matched = []
        for f in custom_onnx_files:
            filename = os.path.basename(f)
            # Match substring (case-insensitive) or match exact name without extension
            if (
                args.model_name.lower() in filename.lower()
                or args.model_name.lower() == os.path.splitext(filename)[0].lower()
            ):
                matched.append(f)
        if not matched:
            print(
                f"Error: No custom model in '{models_dir}' matches name: '{args.model_name}'",
                file=sys.stderr,
            )
            if custom_onnx_files:
                print("Available models in directory:", file=sys.stderr)
                for f in custom_onnx_files:
                    print(f"  - {os.path.basename(f)}", file=sys.stderr)
            sys.exit(1)
        model_paths.extend(matched)
    else:
        # Default: if custom ONNX models exist in the directory, load all of them
        if custom_onnx_files:
            print(
                f"[Voice Listener] Auto-discovered {len(custom_onnx_files)} custom models in '{args.models_dir}':",
                flush=True,
            )
            for f in custom_onnx_files:
                print(f"  - {os.path.basename(f)}", flush=True)
            model_paths.extend(custom_onnx_files)
        else:
            print(
                "[Voice Listener] No custom models found. Falling back to built-in models.",
                flush=True,
            )

    # Initialize nanowakeword and openWakeWord models
    nano_models = {}
    oww_paths = []

    for path in model_paths:
        model_name = os.path.basename(path)
        loaded_nano = False

        if HAS_NANOWAKEWORD and args.engine in ["auto", "nanowakeword"]:
            try:
                print(f"[Voice Listener] Attempting to load '{model_name}' using nanowakeword...", flush=True)
                nano_models[model_name] = NanoInterpreter(path)
                loaded_nano = True
                print(f"  ✨ Successfully loaded '{model_name}' with nanowakeword!", flush=True)
            except Exception as e:
                if args.engine == "nanowakeword":
                    print(f"  ❌ Error loading '{model_name}' with nanowakeword: {e}", file=sys.stderr)
                    sys.exit(1)
                else:
                    print(f"  ⚠️ Could not load '{model_name}' with nanowakeword: {e}. Falling back to openWakeWord...", flush=True)

        if not loaded_nano:
            if HAS_OPENWAKEWORD and args.engine in ["auto", "openwakeword"]:
                oww_paths.append(path)
            else:
                print(f"  ❌ Error: Model '{model_name}' requires openwakeword, but it is disabled or unavailable.", file=sys.stderr)
                sys.exit(1)

    oww_model = None
    if oww_paths:
        try:
            print(f"[Voice Listener] Loading {len(oww_paths)} custom model(s) using openWakeWord: {oww_paths}", flush=True)
            oww_model = OWWModel(
                wakeword_models=oww_paths,
                inference_framework=args.inference_framework,
            )
        except TypeError:
            print(
                "[Voice Listener] Warning: 'inference_framework' parameter not supported by this openWakeWord version. Retrying without it...",
                flush=True,
            )
            oww_model = OWWModel(wakeword_models=oww_paths)
        except Exception as e:
            print(f"[Voice Listener] Error initializing openWakeWord: {e}", file=sys.stderr)
            print(
                "[Voice Listener] Attempting to automatically download missing base/required models...",
                flush=True,
            )
            try:
                import openwakeword.utils
                openwakeword.utils.download_models()
                print(
                    "[Voice Listener] Base models downloaded successfully. Retrying initialization...",
                    flush=True,
                )
                try:
                    oww_model = OWWModel(
                        wakeword_models=oww_paths,
                        inference_framework=args.inference_framework,
                    )
                except TypeError:
                    oww_model = OWWModel(wakeword_models=oww_paths)
            except Exception as retry_err:
                print(f"Error after downloading and retrying initialization: {retry_err}", file=sys.stderr)
                sys.exit(1)

    # Handle built-in model fallback if no models were loaded
    if not nano_models and oww_model is None:
        if HAS_OPENWAKEWORD and args.engine in ["auto", "openwakeword"]:
            print("[Voice Listener] Loading built-in openWakeWord models (e.g. 'alexa', 'hey_mycroft')...", flush=True)
            try:
                oww_model = OWWModel(inference_framework=args.inference_framework)
            except TypeError:
                oww_model = OWWModel()
        else:
            print("❌ Error: No models specified and no wake-word engine was available to load built-ins.", file=sys.stderr)
            sys.exit(1)

    active_models = list(nano_models.keys())
    if oww_model is not None:
        active_models.extend(list(oww_model.models.keys()))

    print(f"[Voice Listener] Active wake word models: {active_models}", flush=True)
    print(
        f"[Voice Listener] Continuous listening started. Say an active wake word to trigger..."
        f"{' (Debug Mode enabled)' if args.debug else ' (Run with --debug to show live audio levels and scores)'}",
        flush=True,
    )

    audio_buffer = []

    # Stream mic input and queue chunks
    def audio_callback(indata, frames, time_info, status):
        audio_buffer.append(indata.copy())

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        blocksize=CHUNK_SIZE,
        callback=audio_callback,
    ):
        while True:
            if len(audio_buffer) > 0:
                chunk = audio_buffer.pop(0).squeeze()

                # Check for prediction
                prediction = {}

                # 1. Process with nanowakeword
                for model_name, interpreter in nano_models.items():
                    prediction[model_name] = interpreter.process(chunk)

                # 2. Process with openwakeword
                if oww_model is not None:
                    oww_preds = oww_model.predict(chunk)
                    for model_name, score in oww_preds.items():
                        prediction[model_name] = score

                # If debugging is active, print volume and model scores
                if args.debug:
                    volume = np.linalg.norm(chunk) / np.sqrt(len(chunk)) if len(chunk) > 0 else 0.0
                    scores_str = ", ".join([f"{name}: {score:.3f}" for name, score in prediction.items()])
                    print(f"\r[Debug] Vol: {volume:.4f} | Predictions: {scores_str}     ", end="", flush=True)

                # Process predictions
                for model_name, score in prediction.items():
                    if score > args.threshold:
                        print(
                            f"\n✨ Wake word detected! Model: '{model_name}' (Score: {score:.2f})",
                            flush=True,
                        )

                        # Stop audio buffer temporarily, record question, and process
                        wav_file = record_question(
                            silence_threshold=args.silence_threshold
                        )
                        text = transcribe_audio(wav_file)

                        if text:
                            print(
                                f"\n📝 [Transcribed Question]:\n  >>> {text}\n",
                                flush=True,
                            )

                            # Combine with preamble if configured
                            clipboard_text = (
                                f"{args.preamble}{text}" if args.preamble else text
                            )

                            # Copy to clipboard for easy copy-pasting to terminal CLI
                            try:
                                subprocess.run(
                                    ["pbcopy"], input=clipboard_text, text=True
                                )
                                if args.preamble:
                                    print(
                                        "[Clipboard] Copied to clipboard with voice preamble! Ready to paste into your session.",
                                        flush=True,
                                    )
                                else:
                                    print(
                                        "[Clipboard] Copied to clipboard! Ready to paste into your session.",
                                        flush=True,
                                    )
                            except Exception:
                                pass
                        else:
                            print(
                                "[Voice Listener] Transcription returned empty or failed.",
                                file=sys.stderr,
                            )

                        # Clear any accumulated audio buffer chunks and resume
                        audio_buffer.clear()
            else:
                # Sleep briefly to avoid 100% CPU usage
                time.sleep(0.01)


if __name__ == "__main__":
    main()
