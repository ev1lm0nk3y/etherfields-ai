# 🌌 Etherfields AI Rule Master & Surgical Retrieval Engine

An intelligent, local knowledge-base, and surgical rule-retrieval engine designed for the campaign board game **Etherfields** (specifically utilizing the official **Rulebook v2.0**).

This project turns an AI agent into an expert **Rule Master**, allowing players to quickly resolve complex mechanical queries with zero-hallucination, page-accurate text extractions.

---

## 🚀 Key Features

1. **Surgical Page-Mapping Lookup (`src/rulebook_tool.py`)**
   Instead of bloating an AI's context window with the entire 20-page rulebook, the engine cross-references a dynamically compiled `index.json` mapping hundreds of game terms and Table of Contents tags. It retrieves and displays *only* the exact page text files (e.g., Page 15 for *Shopping*) required to answer a question.

2. **Self-Healing Cache Integrity**
   The Python 3.13 (`uv`) CLI tool tracks the cryptographic SHA-256 hash and modification timestamp of the original `Rulebook_20.pdf`. If the PDF is updated, the tool automatically invalidates the cache, extracts individual page texts to `rulebook_pages/`, and rebuilds the structured lookup index.

3. **Persistent Campaign Memory**
   Keeps track of discussed rules, campaign-specific errata, and active player configurations. When rules are verified and accepted, they are saved to a local `.md` file inside the `topics/` folder and registered inside `TOPICS.md` as long-term context cache.

---

## 📂 Directory Structure

```
.
├── Rulebook_20.pdf       # The official Etherfields 2.0 PDF rulebook (User-provided)
├── rulebook_pages/       # Extracted page-level text files (page_01.txt to page_20.txt)
├── topics/               # Cached campaign-specific rule discussions and explanations
├── index.json            # Generated TOC and alphabetical index mapping keywords to pages
├── install.py            # Primary installation and setup script
├── src/                  # Main Python source directory
│   ├── rulebook_tool.py  # Unified Python 3.13 tool to validate, regenerate, and query the cache
│   ├── secret_scripts_tool.py # Polite offline caching and lookups of Core Secret Scripts
│   ├── preprocess_scripts.py # Offline compilation tool for secret scripts
│   ├── extract_chat.py   # Chat history exporter tool
│   └── voice/            # Voice assistant & wake-word listening sub-system
│       ├── voice_assistant.py # Local TTS narration (Kokoro-ONNX / OpenAI / ElevenLabs)
│       ├── voice_listener.py  # Continuous wake-word listener (openWakeWord / mlx-whisper / faster-whisper)
│       └── wakeword_model_training.ipynb # Google Colab notebook for training custom models
├── GEMINI.md             # Automatic LLM instructions and workflow protocols
├── RULEMASTER.md         # Baseline rules role prompt and active player roster
├── TOPICS.md             # The central registry of cached topic files
└── README.md             # This file
```

---

## 🛠️ Setup & Usage

### Prerequisites
* **Python 3.12** or higher
* **`uv`** (fast Python package installer and runner)

### 🚀 Interactive Setup Wizard

The project includes an interactive installation script that validates your environment, creates directory structures, configures environment settings, and downloads necessary assets. 

To start the installer, simply run:
```bash
python install.py
```

The setup wizard will walk you through:
1. **Prerequisite Verification:** Ensuring Python 3.12+ and `uv` are available.
2. **Custom Files Directory:** Defining a local directory for logs, caches, and models (defaults to `~/.local/etherfields-ai`), keeping the repository directory clean.
3. **Environment Generation:** Creating a local `.env` file (copied from `.env.example` template) to specify your custom paths and configurations. This file is automatically ignored by git.
4. **Voice Assistance (Optional):** Setting up wake-word models (e.g. downloading `jarvis.onnx`) and verifying `ffmpeg` installation.
5. **Rulebook PDF Auto-Retrieval:** Checking for `Rulebook_20.pdf` and offering to automatically download it directly from Awaken Realms if missing, followed by rebuilding the page search index.
6. **Dependency Warming:** Pre-downloading any large libraries (like PyTorch/torch) so they're ready for instant, offline, hands-free gameplay sessions.

---

### Usage Commands

#### 1. Validate the Cache (Checks hash/time metadata)
```bash
uv run src/rulebook_tool.py --validate
```
*Note: If the PDF is updated, the tool will automatically self-heal and regenerate the page cache and `index.json`.*

#### 2. Search for a Topic or Term
```bash
uv run src/rulebook_tool.py --search "Slumber"
```
This searches the index, lists matching chapters/index terms, maps them to their respective pages, and prints the raw extracted page contents for immediate, zero-guesswork rule verification.

#### 3. Force Cache Rebuild
```bash
uv run src/rulebook_tool.py --force
```

---

## 🎙️ Custom Wake Word Model Training

The project includes a Jupyter Notebook at `src/voice/wakeword_model_training.ipynb` that allows you to train your own custom **openWakeWord** models (such as `"ee_thir_fields"`, `"hey_rule_book"`, etc.). You can run this pipeline either in the cloud using Google Colab or completely offline on your local machine.

### Option A: Cloud Training (Google Colab) [Recommended]
1. **Upload the Notebook:** Upload `src/voice/wakeword_model_training.ipynb` to your [Google Drive](https://drive.google.com/) or open it directly in [Google Colab](https://colab.research.google.com/).
2. **Choose a Runtime:** 
   * For the fastest training, go to **Runtime** > **Change runtime type** and select a **GPU** (e.g., T4).
   * The notebook features **automatic multi-accelerator hardware detection**. It dynamically configures and installs the correct PyTorch build:
     * **GPU:** Installs PyTorch with CUDA 12.1 support for fast GPU-accelerated training.
     * **TPU / CPU:** Gracefully falls back to installing a stable CPU PyTorch build.
3. **Configure Your Wake Word:** 
   * In Step 2, set the `target_word` variable to your custom phrase (e.g., `'ee_thir_fields'`).
   * Spell it phonetically with underscores if the TTS pronunciation needs adjustments (e.g., `'hey_seer_e'`).
4. **Run All Cells:** Go to **Runtime** > **Run all**. 
   * The notebook will verify the pronunciation using Piper TTS, download reverb impulse responses (MIT RIR) and background noise (AudioSet & Free Music Archive), generate and augment synthetic training clips, and train the model.
5. **Download and Deploy:** Once complete, the notebook automatically exports and downloads your custom model files:
   * `[your_wake_word].onnx`
   * `[your_wake_word].tflite`
   * Simply place your custom `.onnx` model files in your local `models/` directory. The continuous listener `src/voice/voice_listener.py` will automatically auto-discover and load them in parallel!

### Option B: Local Training (Your Machine)
If you prefer to train your models offline, you can run the notebook locally using `uv` to automatically manage your Jupyter environment:

1. **Start the Jupyter Server:**
   Spin up a local Jupyter Notebook server using `uv`:
   ```bash
   uv run --with jupyter jupyter notebook src/voice/wakeword_model_training.ipynb
   ```
2. **Open the Notebook:** 
   Open the printed URL in your browser, or open the folder in **VS Code** and use the Jupyter extension.
3. **Configure and Run:**
   * Set your custom wake word in Step 1 (e.g., `target_word = 'ee_thir_fields'`).
   * Run the cells sequentially. The script automatically detects your hardware and installs the appropriate dependencies in your local environment.
   * *Note:* Downloading background noise and training features (~2.5 GB total) can take about 10-15 minutes depending on your internet connection. Once the `.onnx` and `.tflite` files are generated, simply move them to your local `models/` directory!

---

## 👥 Players & Campaign State
Tracked inside `RULEMASTER.md` to customize rule context (such as character-specific abilities):
* **Player Count:** 2 Players
* **Characters:**
  * **The Specialist** (Expert engineer, builds Progress engine)
  * **The Free Spirit** (Bends basic game laws, generates Spirit Tokens)
