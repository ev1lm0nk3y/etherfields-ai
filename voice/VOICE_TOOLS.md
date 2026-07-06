# Etherfields AI Rule Master - Voice Tools & Capabilities

This document provides detailed setup and usage instructions for the offline, local, and remote voice features of the Etherfields Board Game Assistant workspace.

---

## 1. Local Dual-Voice TTS Voice Assistant
Use `uv run voice/voice_assistant.py` to voice rule answers or secret scripts locally.
* **Default Local Engine:** Runs 100% offline via local PyTorch & Apple Silicon GPU acceleration (`mps`). Automatically performs zero-shot voice cloning of reference prompts! Rule instructions use clear narrative and instruction voices. If no custom `.wav` reference clips are set in `.env`, it falls back gracefully to high-quality default pretrained models.
* **WebSocket Remote Engine:** Interfaces with an external, high-fidelity WebSocket-based TTS server. Supports automated emotion-detection keyword scanning to dynamically adjust voices and tones matching the narrative.
* **To create custom voice reference models:** Run `uv run voice/create_voice.py` to record a fresh clip or load a local `.wav` file!
* **To speak custom text:**
  ```bash
  uv run voice/voice_assistant.py --text "My text response here"
  ```
* **To speak a secret script:**
  ```bash
  uv run voice/voice_assistant.py --script 234
  ```

---

## 2. Continuous Voice Listener (Hands-Free Integration)
Use `uv run voice/voice_listener.py` to run the continuous wake-word detector locally. It dynamically supports both **nanowakeword** (for highest accuracy and low laptop footprint) and **openWakeWord** engines in parallel!
* **Auto-discovery:** By default, the script automatically scans the `models/` directory for any custom `.onnx` wake-word models (like `hey_rule_book.onnx`, `hey_rule_book_1.onnx`, etc.) and loads all of them in parallel!
* **Multi-Engine Auto-Detection:** If `nanowakeword` is installed, it will automatically load compatible models using the advanced `NanoInterpreter` for ultra-low latency; otherwise, it falls back to the openWakeWord backend.
* **Engine Selection:** Force a specific engine with `--engine nanowakeword` or `--engine openwakeword`.
* **Listing models:** Run:
  ```bash
  uv run voice/voice_listener.py --list-models
  ```
* **Running specific models:** Use `--model-name <name>` to load only matching custom models (e.g., `uv run voice/voice_listener.py --model-name hey_rule_book_3`), or `--model-path <path>` for direct loading.
* **How it works:** It continuously listens for an active wake word. Upon detection, it triggers a macOS beep, records your question until you stop speaking, transcribes it locally using the `whisper` uv tool, and automatically copies the transcription text to your clipboard.
* **Action:** Simply paste (Cmd+V) the transcribed question directly into this terminal agent session!

---

## 3. Custom Voice Training Wizard
Use the interactive training wizard to record your own voice and prepare a personalized, high-accuracy nanowakeword model:
```bash
uv run voice/voice_training_wizard.py
```
The wizard will guide you through recording 30–50 samples of your voice using your laptop microphone, and generate a customized `config.yaml` for nanowakeword's automated `--auto-config` training pipeline.
