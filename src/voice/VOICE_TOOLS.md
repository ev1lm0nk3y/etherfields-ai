# Etherfields AI Rule Master - Voice Tools & Capabilities

This document provides detailed setup, execution, and architectural information for the offline and online voice features of the Etherfields Board Game Assistant.

---

## 1. Local Voice Assistant (`src/voice/voice_assistant.py`)
Use `uv run src/voice/voice_assistant.py` to play voice narration for secret scripts or rule master answers. The sub-system supports three selectable Text-to-Speech (TTS) engines configured via `.env` or overridden at runtime:

### A. Kokoro ONNX Engine (Local Offline - Recommended)
* **How it works:** A state-of-the-art, lightweight neural TTS (82M parameters) running via the **ONNX Runtime**. It runs completely offline with near-ElevenLabs quality.
* **Speed:** Blazing-fast (**10x–30x real-time** on standard CPU, near-instantaneous on Apple Silicon GPU). Zero PyTorch startup/compilation latency.
* **Voices Included:** Includes 54 pre-packaged premium voices (American/British accents, Male/Female genders) embedded inside the single local `voices-v1.0.bin` file.

### B. OpenAI TTS (Online)
* **How it works:** Native REST integration using Python's built-in `urllib.request` to connect directly to the OpenAI Speech API.
* **Speed:** Extremely fast with excellent premium audio quality.
* **Requirements:** Requires setting your `OPENAI_API_KEY` in `.env`.

### C. ElevenLabs TTS (Online - Premium)
* **How it works:** Connects directly to ElevenLabs utilizing the ultra-low-latency **ElevenLabs Flash v2.5** model (~75ms latency).
* **Speed & Realism:** Unparalleled emotional prosody, narrative pacing, and natural breathing.
* **Requirements:** Requires setting your `ELEVENLABS_API_KEY` in `.env`.

---

## 2. Directory Architecture & Caching
To maintain zero-overhead gameplay, all synthesized speech is intelligently cached to prevent redundant generations.

* **Models Folder:** Neural network models (e.g. `kokoro-v1.0.onnx` and `voices-v1.0.bin`) are stored in `${ETHERFIELDS_LOCAL_DIR}/voice/models/`.
* **Cache Folder:** Synthesized audio clips are saved as `.wav` files inside `${ETHERFIELDS_LOCAL_DIR}/voice/cache/`.
* **Standardized Filename Mapping:**
  * **Secret Scripts:** Saved cleanly as `script_<num>_narrative.wav` and `script_<num>_instructions.wav`.
  * **Rule Discussions:** Unique text inputs are cached using a stable 12-character MD5 hash (e.g., `text_ae98d25d19c3.wav`), or with custom customizable slugs (e.g., `topic_stun.wav`) by passing the `--filename topic_stun` flag.

---

## 3. Basic Voice CLI Usage

### Speak Custom Text
```bash
# Speak custom text using your default .env engine
uv run src/voice/voice_assistant.py --text "Draw a Turn card and resolve Slumber."

# Override engine on-the-fly and specify a custom cache filename
uv run src/voice/voice_assistant.py --text "You enter a dark corridor." --engine elevenlabs --filename corridors_sound

# Override voice on-the-fly (e.g. British Male on Kokoro)
uv run src/voice/voice_assistant.py --text "Let me explain the rule." --voice bm_george
```

### Speak a Secret Script
Secret scripts often contain two parts: **story narrative** and **rules instructions**. The assistant reads these sequentially using two distinct voices (e.g. a rich male narrator voice and a clear female instruction voice).
```bash
uv run src/voice/voice_assistant.py --script 100
```

### Pre-Cache Multiple Scripts
You can pre-cache a comma-separated list of scripts silently before your game session starts to guarantee zero-latency play:
```bash
uv run src/voice/voice_assistant.py --pre-cache 100,101,102,105
```

### Persistent Interactive Mode
To run a persistent shell that keeps the local Kokoro ONNX model warmed up in memory for instant responses:
```bash
uv run src/voice/voice_assistant.py --interactive
```

---

## 4. Continuous Voice Listener (`src/voice/voice_listener.py`)
Use `uv run src/voice/voice_listener.py` to run the continuous wake-word detector locally. 

* **Dual Wake-Word Backends:** Dynamically supports both **nanowakeword** (for highest accuracy and exceptionally low CPU footprint) and **openWakeWord** engines in parallel!
* **Speech-to-Text (STT) Processing:** Upon hearing the wake word (e.g., *Jarvis* or a custom trained phrase), the listener records your voice question until you stop speaking, and transcribes it completely locally using:
  - **`mlx-whisper`**: High-performance Metal-accelerated translation using the `whisper-large-v3-turbo` model (Automatic on Apple Silicon Macs).
  - **`faster-whisper`**: Cross-platform CPU/GPU accelerated transcription using `faster-whisper-medium.en` (Automatic on Linux, Windows, and Intel Macs).
* **Instant Clipboard Mapping:** The transcribed question is automatically copied directly to your clipboard. Simply paste (Cmd+V / Ctrl+V) the query into your active Rule Master prompt for immediate answer retrieval!

To run the listener:
```bash
uv run src/voice/voice_listener.py
```
---