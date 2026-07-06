# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "nanowakeword",
#     "sounddevice",
#     "soundfile",
#     "numpy==1.26.4",
#     "pyyaml",
#     "mlx-whisper>=0.4.0",
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

try:
    import nanowakeword
except ImportError:
    print("Error: The 'nanowakeword' library is not installed.", file=sys.stderr)
    print("Please run voice installation or install it manually with: pip install nanowakeword", file=sys.stderr)
    sys.exit(1)


class NanoInterpreter:
    """
    Compatibility wrapper to bridge the old NanoInterpreter API 
    with the modern nanowakeword.Model class. Automatically converts
    float32 microphone audio inputs [-1.0, 1.0] to 16-bit signed PCM integers.
    """
    def __init__(self, model_path):
        self.model = nanowakeword.Model(
            wakeword_models=[os.path.abspath(model_path)],
            inference_framework="onnx"
        )
        self.model_key = os.path.splitext(os.path.basename(model_path))[0]

    def process(self, chunk):
        # Convert float32 microphone chunk [-1.0, 1.0] to np.int16 signed PCM
        int_chunk = (chunk * 32767.0).astype(np.int16)
        predictions = self.model.predict(int_chunk)
        return predictions.get(self.model_key, 0.0)

    def reset(self):
        self.model.reset()

# Repo root is parent of the directory of this file
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def to_float(val):
    """
    Safely converts a value (which could be a numpy array, a list, a numpy float,
    or a standard float/int) into a standard Python float.
    """
    if val is None:
        return 0.0
    if isinstance(val, np.ndarray):
        if val.size == 0:
            return 0.0
        return float(val.item() if val.size == 1 else val.flat[0])
    if isinstance(val, (list, tuple)):
        if len(val) == 0:
            return 0.0
        return float(val[0])
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def load_env_vars():
    env_vars = {}
    local_path = os.environ.get("ETHERFIELDS_LOCAL_PATH")
    paths_to_try = []
    if local_path:
        paths_to_try.append(os.path.join(os.path.abspath(os.path.expanduser(os.path.expandvars(local_path))), ".env"))
    paths_to_try.append(os.path.join(REPO_ROOT, ".env"))

    for env_path in paths_to_try:
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        env_vars[key.strip()] = val.strip()
            break
    return env_vars


_env = load_env_vars()
CUSTOM_DIR_STR = _env.get("ETHERFIELDS_LOCAL_PATH", REPO_ROOT)
CUSTOM_DIR = os.path.abspath(os.path.expanduser(os.path.expandvars(CUSTOM_DIR_STR)))
DEFAULT_MODELS_DIR = os.path.join(CUSTOM_DIR, "models")
DEFAULT_AUDIO_CACHE_DIR = os.path.join(CUSTOM_DIR, "audio_cache")

# Global Audio Parameters
SAMPLE_RATE = 16000  # nanowakeword and Whisper expect 16kHz
CHANNELS = 1
CHUNK_SIZE = 1280  # Chunks fed into nanowakeword


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
    temp_wav_dir = (
        DEFAULT_AUDIO_CACHE_DIR if os.path.exists(DEFAULT_AUDIO_CACHE_DIR) else os.getcwd()
    )
    temp_wav = os.path.join(temp_wav_dir, "question_temp.wav")
    sf.write(temp_wav, audio_data, SAMPLE_RATE)
    return temp_wav


# Global variable for lazy model loading
_stt_model = None


def transcribe_audio(wav_path):
    """
    Transcribes audio using the configured local STT engine (mlx-whisper or faster-whisper).
    Loads the model into memory upon first use.
    """
    global _stt_model
    stt_program = _env.get("STT_PROGRAM", "faster-whisper").lower()

    print(f"[{stt_program.upper()}] Transcribing audio file...", flush=True)
    start_t = time.time()
    transcription = None

    try:
        if stt_program == "mlx-whisper":
            import mlx_whisper

            # mlx_whisper takes a path_or_hf_repo and returns a dict with 'text'
            result = mlx_whisper.transcribe(
                wav_path, path_or_hf_repo="mlx-community/whisper-large-v3-turbo"
            )
            transcription = result["text"].strip()

        elif stt_program == "faster-whisper":
            from faster_whisper import WhisperModel

            if _stt_model is None:
                print("[FASTER-WHISPER] Loading model (first time only)...", flush=True)
                _stt_model = WhisperModel(
                    "Systran/faster-whisper-medium.en",
                    device="cpu",
                    compute_type="int8",
                    download_root=DEFAULT_MODELS_DIR,
                )

            segments, _ = _stt_model.transcribe(wav_path, beam_size=5)
            transcription = " ".join([segment.text for segment in segments]).strip()

        else:
            print(f"[STT] Error: Unknown STT program configured '{stt_program}'", file=sys.stderr)
            return None

        elapsed = time.time() - start_t
        print(f"[{stt_program.upper()}] Transcription completed in {elapsed:.2f}s", flush=True)

        # Cleanup wav
        if os.path.exists(wav_path):
            os.remove(wav_path)

        return transcription

    except Exception as e:
        print(f"[{stt_program.upper()}] Error during transcription process: {e}", file=sys.stderr)
        if os.path.exists(wav_path):
            os.remove(wav_path)
    return None


def load_narration_worker():
    """Starts the background thread to poll and narrate queue items."""
    import json
    import threading

    def worker():
        topics_dir = os.path.join(CUSTOM_DIR, "narration_queue")
        os.makedirs(topics_dir, exist_ok=True)

        # Lazy import of speak_text to avoid circular dependencies
        from voice_assistant import speak_text

        print("[Voice Listener] Background narration queue worker started.", flush=True)
        while True:
            try:
                if os.path.exists(topics_dir):
                    files = [
                        f
                        for f in os.listdir(topics_dir)
                        if f.startswith("req_") and f.endswith(".json")
                    ]
                    if files:
                        files.sort(key=lambda x: os.path.getmtime(os.path.join(topics_dir, x)))
                        next_file = files[0]
                        file_path = os.path.join(topics_dir, next_file)

                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                data = json.load(f)
                            text_to_narrate = data.get("text")
                            if text_to_narrate:
                                print(f"\n📢 [Queue] Narrating: '{text_to_narrate}'\n", flush=True)
                                speak_text(text_to_narrate)
                        except Exception as fe:
                            print(f"Error processing queue file {next_file}: {fe}", file=sys.stderr)

                        if os.path.exists(file_path):
                            os.remove(file_path)
            except Exception as e:
                print(f"Error in queue worker loop: {e}", file=sys.stderr)

            time.sleep(0.5)

    worker_thread = threading.Thread(target=worker, daemon=True)
    worker_thread.start()


def main():
    parser = argparse.ArgumentParser(description="Etherfields Rule Master Wake-Word Listener")
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
        default="nanowakeword",
        choices=["nanowakeword"],
        help="The wake-word detection engine to use (default: nanowakeword)",
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
            os.path.join(models_dir, f) for f in os.listdir(models_dir) if f.endswith(".onnx")
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
                print(f"Error: Specified model path does not exist: {p}", file=sys.stderr)
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
                "[Voice Listener] No custom models found. Please place your .onnx wake word models in your models directory.",
                flush=True,
            )

    # Initialize nanowakeword models
    nano_models = {}

    for path in model_paths:
        model_name = os.path.basename(path)
        try:
            print(
                f"[Voice Listener] Attempting to load '{model_name}' using nanowakeword...",
                flush=True,
            )
            nano_models[model_name] = NanoInterpreter(path)
            print(f"  ✨ Successfully loaded '{model_name}' with nanowakeword!", flush=True)
        except Exception as e:
            print(
                f"  ❌ Error loading '{model_name}' with nanowakeword: {e}", file=sys.stderr
            )
            sys.exit(1)

    if not nano_models:
        print(
            "❌ Error: No models successfully loaded.",
            file=sys.stderr,
        )
        sys.exit(1)

    active_models = list(nano_models.keys())
    print(f"[Voice Listener] Active wake word models: {active_models}", flush=True)
    print(
        f"[Voice Listener] Continuous listening started. Say an active wake word to trigger..."
        f"{' (Debug Mode enabled)' if args.debug else ' (Run with --debug to show live audio levels and scores)'}",
        flush=True,
    )

    # Start background narration queue worker thread to process MCP narrate_text requests
    load_narration_worker()

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

                # Process with nanowakeword
                for model_name, interpreter in nano_models.items():
                    prediction[model_name] = to_float(interpreter.process(chunk))

                # If debugging is active, print volume and model scores
                if args.debug:
                    volume = np.linalg.norm(chunk) / np.sqrt(len(chunk)) if len(chunk) > 0 else 0.0
                    scores_str = ", ".join(
                        [f"{name}: {score:.3f}" for name, score in prediction.items()]
                    )
                    print(
                        f"\r[Debug] Vol: {volume:.4f} | Predictions: {scores_str}     ",
                        end="",
                        flush=True,
                    )

                # Process predictions
                for model_name, score in prediction.items():
                    if score > args.threshold:
                        print(
                            f"\n✨ Wake word detected! Model: '{model_name}' (Score: {score:.2f})",
                            flush=True,
                        )

                        # Stop audio buffer temporarily, record question, and process
                        wav_file = record_question(silence_threshold=args.silence_threshold)
                        text = transcribe_audio(wav_file)

                        if text:
                            print(
                                f"\n📝 [Transcribed Question]:\n  >>> {text}\n",
                                flush=True,
                            )

                            # Combine with preamble if configured
                            clipboard_text = f"{args.preamble}{text}" if args.preamble else text

                            # Copy to clipboard for easy copy-pasting to terminal CLI
                            try:
                                subprocess.run(["pbcopy"], input=clipboard_text, text=True)
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
                        for interpreter in nano_models.values():
                            interpreter.reset()
            else:
                # Sleep briefly to avoid 100% CPU usage
                time.sleep(0.01)


if __name__ == "__main__":
    main()
