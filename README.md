# 🌌 Etherfields AI Rule Master & Surgical Retrieval Engine

An intelligent, local knowledge-base, and surgical rule-retrieval engine designed for the campaign board game **Etherfields** (specifically utilizing the official **Rulebook v2.0**).

This project turns an AI agent into an expert **Rule Master**, allowing players to quickly resolve complex mechanical queries with zero-hallucination, page-accurate text extractions.

---

## 🚀 Key Features

1. **Surgical Page-Mapping Lookup (`src/rulebook_tool.py`)**
   Instead of bloating an AI's context window with the entire 20-page rulebook, the engine cross-references a dynamically compiled `index.json` mapping hundreds of game terms and Table of Contents tags. It retrieves and displays *only* the exact page text files (e.g., Page 15 for *Shopping*) required to answer a question.

2. **Self-Healing Cache Integrity**
   The Python 3.11 (`uv`) CLI tool tracks the cryptographic SHA-256 hash and modification timestamp of the original `Rulebook_20.pdf`. If the PDF is updated, the tool automatically invalidates the cache, extracts individual page texts to `rulebook_pages/`, and rebuilds the structured lookup index.

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
│   ├── rulebook_tool.py  # Unified Python 3.11 tool to validate, regenerate, and query the cache
│   ├── secret_scripts_tool.py # Polite offline caching and lookups of Core Secret Scripts
│   ├── preprocess_scripts.py # Offline compilation tool for secret scripts
│   ├── extract_chat.py   # Chat history exporter tool
│   └── voice/            # Voice assistant & wake-word listening sub-system
│       ├── create_voice.py  # Synthesizes offline neural voices
│       ├── test_assistant.py # Tests TTS playback and config settings
│       ├── test_stt.py       # Tests Whisper Speech-to-Text transcribing
│       ├── voice_assistant.py # Local TTS narration (Kokoro-ONNX / OpenAI / ElevenLabs)
│       ├── voice_install.py   # Interactive nanowakeword/openWakeWord installation wizard
│       ├── voice_listener.py  # Continuous wake-word listener (nanowakeword / openWakeWord / mlx-whisper / faster-whisper)
│       ├── voice_training_wizard.py # Interactive voice clip recorder and training config generator
│       ├── wakeword_model_training.ipynb # Google Colab notebook for training custom models
│       ├── VOICE_TOOLS.md     # Detailed documentation on voice options and settings
│       └── templates/         # Configuration templates
│           └── nanowakeword_config.yaml.j2 # Jinja2 configuration template for nanowakeword
├── RULEMASTER.md         # Baseline rules role prompt and active player roster
├── TOPICS.md             # The central registry of cached topic files
└── README.md             # This file
```

---

## 🛠️ Setup & Usage

### Prerequisites
* **Python 3.11** (specifically 3.11.10)
* **`uv`** (fast Python package installer and runner)

### 🚀 Interactive Setup Wizard

The project includes an interactive installation script that validates your environment, creates directory structures, configures environment settings, and downloads necessary assets. 

To start the installer, simply run:
```bash
python install.py
```

The setup wizard will walk you through:
1. **Prerequisite Verification:** Ensuring Python 3.11 (specifically 3.11.10) and `uv` are available.
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

This repository supports two state-of-the-art offline wake-word engines: **nanowakeword** (highly recommended for personalized single-voice models) and **openWakeWord** (ideal for general-use models). You can configure your engine and set up your system interactively, or build custom models tailored specifically to your voice and room acoustics.

### 🛠️ Interactive Voice Setup Wizard (`src/voice/voice_install.py`)

The repository includes a dedicated interactive configuration script for the voice subsystem. It handles library installation, environment generation, configuration templating using modular Jinja2 configurations (`src/voice/templates/nanowakeword_config.yaml.j2`), and voice-source selection (microphone vs. synthetic text-to-speech clones).

To launch the setup wizard, run:
```bash
uv run python src/voice/voice_install.py
```

---

### 🎨 Method 1: Nanowakeword Training Wizard (`src/voice/voice_training_wizard.py`) [Personalized & Offline]

**nanowakeword** is a modern, lightweight, transformer-based wake-word detector optimized for running on laptops and micro-controllers. The project provides an interactive command-line utility, `src/voice/voice_training_wizard.py`, to guide you through recording your own real-voice clips and preparing the training configuration.

#### 1. Record Your Voice and Generate Config
Run the training wizard from your terminal:
```bash
uv run python src/voice/voice_training_wizard.py
```
The wizard will:
* Prompt you to name your custom wake word (e.g. `ee_thir_fields`, `jarvis`).
* Create a dedicated training workspace under your configured dynamic directory (e.g., `~/.local/etherfields-ai/voice/training_data/[your_wake_word]`).
* Guide you through recording 30 to 50 real-voice samples (each 1.6 seconds long) from your physical microphone using the `sounddevice` library.
* Automatically write a tailored `config.yaml` file with transformer architectures, targeting the output to your local models directory.

#### 2. Choose Your Training Pipeline:

##### Option A: Local Training (Directly on your MacBook / Laptop)
This option keeps your voice and data completely offline and secure.
1. Install nanowakeword with its optional training dependencies:
   ```bash
   pip install "nanowakeword[train] @ git+https://github.com/arcosoph/nanowakeword.git"
   ```
2. Execute the training command using nanowakeword's Auto-Config feature:
   ```bash
   nanowakeword-train -c ~/.local/etherfields-ai/voice/training_data/[your_wake_word]/config.yaml --auto-config -G -t -T
   ```
   *This command will automatically synthesize look-alike negative datasets (adversarial training), configure hyperparameters, train a robust transformer model, and export a lightweight `.onnx` model file in about 45 minutes.*
3. Place your output `.onnx` file into your local models directory:
   ```bash
   cp ~/.local/etherfields-ai/voice/training_data/[your_wake_word]/models/[your_wake_word].onnx ~/.local/etherfields-ai/models/
   ```

##### Option B: Cloud Training (Google Colab) [Free GPU Acceleration]
Google Colab provides high-speed, free GPU acceleration, cutting training times down to under 15 minutes!
1. Zip up your recorded training directory:
   ```bash
   cd ~/.local/etherfields-ai/voice/training_data/[your_wake_word] && zip -r targets.zip data/
   ```
2. Open the official Nanowakeword notebook or upload `src/voice/wakeword_model_training.ipynb` directly to [Google Colab](https://colab.research.google.com/).
3. Upload `targets.zip` to Colab's file explorer and unzip it:
   ```bash
   !unzip targets.zip -d ./
   ```
4. Combine your real voice recordings with Colab's synthetic voice clones (Piper TTS) for the absolute highest model accuracy, and run the training cells.
5. Download your finished `.onnx` model and place it in your local models folder:
   ```bash
   mv ~/Downloads/[your_wake_word].onnx ~/.local/etherfields-ai/models/
   ```

---

### 📡 Method 2: OpenWakeWord Custom Model Training (`src/voice/wakeword_model_training.ipynb`)

**openWakeWord** is a deep-learning-based wake-word detector with pre-trained models that can also be trained on your custom words. It performs best on general-purpose terms and features robust noise filtering.

You can train openWakeWord models either in the cloud or locally:

#### Option A: Cloud Training (Google Colab) [Recommended]
1. **Upload the Notebook:** Upload `src/voice/wakeword_model_training.ipynb` to your [Google Drive](https://drive.google.com/) or open it directly in [Google Colab](https://colab.research.google.com/).
2. **Choose a Runtime:** 
   * Go to **Runtime** > **Change runtime type** and select a **GPU** (e.g., T4).
   * The notebook features **automatic multi-accelerator hardware detection**. It dynamically configures and installs the correct PyTorch build (CUDA 12.1 for GPU, stable CPU build otherwise).
3. **Configure Your Wake Word:** 
   * In Step 2, set the `target_word` variable to your custom phrase (e.g., `'ee_thir_fields'`).
   * Spell it phonetically with underscores if the TTS pronunciation needs adjustments (e.g., `'hey_seer_e'`).
4. **Run All Cells:** Go to **Runtime** > **Run all**. 
   * The notebook will verify the pronunciation using Piper TTS, download reverb impulse responses (MIT RIR) and background noise (AudioSet & Free Music Archive), generate and augment synthetic training clips, and train the model.
5. **Download and Deploy:** Once complete, the notebook automatically exports and downloads your custom model files:
   * `[your_wake_word].onnx`
   * `[your_wake_word].tflite`
   * Simply place your custom `.onnx` model files in your local `models/` directory. The continuous listener `src/voice/voice_listener.py` will automatically discover and load them in parallel!

#### Option B: Local Training (Your Machine)
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

## 🔌 Model Context Protocol (MCP) Server

The project includes an **AI-Agent Agnostic Model Context Protocol (MCP) Server** (`src/mcp_server.py`) that implements the official Model Context Protocol. This allows any MCP-enabled AI client (such as Claude Desktop, Gemini CLI, Cursor, or any other agent) to connect to this repository, read the campaign state, and execute rule searches, voice narration, or script retrieval.

### Exposed Capabilities

#### 1. Tools
* **`search_rulebook(query: str)`**: Searches the official Etherfields 2.0 PDF rulebook page cache and TOC index. Returns page matches and their full page text.
* **`get_secret_script(script_num: str)`**: Looks up a specific core campaign secret script. Returns story narrative, action instructions, and branching choices in a beautiful markdown format without spoilers.
* **`validate_rulebook_cache()`**: Checks and validates that the rulebook page split cache and index match the latest PDF, rebuilding them if necessary.
* **`narrate_text(text: str)`**: Narrates gameplay text or rules out loud using the local voice/TTS assistant (if voice/TTS is enabled).

#### 2. Resources
* **`campaign://state`**: Exposes the current campaign state and player details directly from `RULEMASTER.md`.
* **`topics://index`**: Exposes the central registry of discussed rules/mechanics from `TOPICS.md`.
* **`logs://index`**: Exposes the campaign session log history from `LOGS.md`.

#### 3. Prompts
* **`rule_master_session()`**: Initializes a full, interactive Rule Master gameplay session, setting strict rules of conduct (forbidding tactical gameplay advice, configuring speech verbosity, and setting up the Action-State-Wait protocol for secret scripts).
* **`explain_rule(concept: str)`**: Generates a prompt guiding the agent to explain a gameplay concept based on the rulebook.
* **`resolve_script(script_num: str)`**: Generates a prompt guiding the agent to resolve a secret script sequentially while avoiding spoilers and following the action-state-wait protocol.

### How to Run

You can run the MCP server using `uv`:

```bash
uv run python src/mcp_server.py
```

### Client Configurations

#### 1. Claude Desktop
Add the following to your `claude_desktop_config.json` (usually located at `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS or `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "etherfields-ai": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/Users/ryan/Documents/mcp-transition",
        "python",
        "src/mcp_server.py"
      ]
    }
  }
}
```

Replace the path above with the absolute path to your cloned repository.

#### 2. Gemini CLI
Gemini CLI supports MCP servers natively. You can configure it globally in `~/.gemini/settings.json` or locally in `.gemini/settings.json` under your project root directory:

```json
{
  "mcpServers": {
    "etherfields-ai": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/Users/ryan/Documents/mcp-transition",
        "python",
        "src/mcp_server.py"
      ]
    }
  }
}
```

Replace the path above with the absolute path to your cloned repository. Once configured, restart your Gemini CLI and use `/mcp` to list and verify all discovered tools!

#### 3. OpenAI Assistants & Agents
Since OpenAI does not have a native "desktop app" config for MCP, you can connect OpenAI models to this server using standard middleware or custom client wrappers:

* **Python Bridge Integration:**
  You can build a small Python wrapper using the `mcp` client and `openai` libraries to translate OpenAI tool calls into MCP actions:
  
  ```python
  from mcp import ClientSession, StdioServerParameters
  from mcp.client.stdio import stdio_client
  from openai import OpenAI

  # 1. Define server parameters
  server_params = StdioServerParameters(
      command="uv",
      args=["run", "--project", "/Users/ryan/Documents/mcp-transition", "python", "src/mcp_server.py"]
  )

  # 2. Start MCP and OpenAI clients
  async def run_agent():
      async with stdio_client(server_params) as (read_stream, write_stream):
          async with ClientSession(read_stream, write_stream) as session:
              # Initialize MCP
              await session.initialize()
              
              # Retrieve available tools to register as OpenAI tools
              tools = await session.list_tools()
              
              # Map tools to OpenAI schema, and execute chat completions!
  ```

* **OpenAI Secure MCP Tunnel:**
  For cloud-based assistants (like OpenAI GPTs or custom Assistants), you can use OpenAI's official secure tunnel client (`@openai/tunnel-client`) to expose this local server securely to the OpenAI cloud:
  ```bash
  npx @openai/tunnel-client --port 8000
  ```

* **OpenAI MCP Bridge Middleware:**
  You can run [mcp-bridge](https://github.com/SecretiveShell/MCP-Bridge) to host an OpenAI-compatible API gateway (`localhost:3000/v1/chat/completions`) that translates OpenAI's standard function calling format to the local MCP tools natively.

---

## 🐳 Containerization & Docker Orchestration

The project is fully containerized into a multi-container architecture using **Docker** and **Docker Compose**. This isolates heavy system dependencies, ensures highly portable runtimes, and provides a seamless local interface for both the AI engine and the voice assistant.

### 🏗️ Dual-Service Architecture

1. **`mcp-server` (Core AI Engine)**
   * Built from `Dockerfile` using the official `astral-sh/uv` pre-packaged image.
   * **Pure Docker Baking:** During image build, it downloads the official 2.0 PDF, slices individual page text caches, and politely downloads and pre-compiles all 1093 campaign secret scripts directly into `/app`.
   * **Masking Avoided:** By baking these assets into the static image folder `/app`, they are never masked or overwritten by runtime volume mounts. When the container starts and detects an empty data volume, it flawlessly falls back to reading these baked-in files.
   * **Dynamic volume mount:** Mounts `${HOME}/.local/etherfields-ai` to `/app/data` to dynamically persist session logs, custom topics, campaign state, and `.env` settings.
   * Exposes standard stdio for any MCP-enabled client (e.g. Claude Desktop or Gemini CLI).

2. **`voice-subsystem` (Continuous Listener & Narration Assistant)**
   * Built from `Dockerfile.voice` using the official `astral-sh/uv` base.
   * Includes complete system dependencies (`libasound2`, `libportaudio2`, `ffmpeg`, `gcc`) pre-installed.
   * Shares the same `${HOME}/.local/etherfields-ai` volume mount to access custom wake-word models (such as `jarvis.onnx`), local voice audio caches, and `.env` settings.
   * Interfaces directly with host sound cards and microphone inputs.

---

### 🔨 Compilation via Build Program (`build_containers.py`)

A smart, dedicated build script is included to orchestrate compilation using Docker Buildx and advanced caches. It automatically verifies your Docker daemon status, checks for BuildKit support, and handles caching targets to accelerate subsequent rebuilds.

To compile both containers, simply run:
```bash
python build_containers.py
```

#### Why this Build System is Lightning-Fast:
* **Dependency Caching:** The script utilizes Buildx cache mounts (`--mount=type=cache,target=/root/.cache/uv`) for package synchronization. Rebuilding a container after code changes is nearly instantaneous as pip/uv packages are never re-downloaded.
* **Network & Processing Caching:** We mount a custom Buildx directory (`--mount=type=cache,target=/app/build_cache`) during core engine compilation. It persists downloaded rulebooks and script databases. On subsequent rebuilds, it skips downstream network fetches and the 30-second polite throttling delay entirely, reducing build generation time from **45 seconds to under 2 seconds!**

#### ⚙️ Continuous Integration via GitHub Actions

The repository includes a fully configured GitHub Actions workflow (`.github/workflows/publish_containers.yml`) to automatically compile and publish both images to the **GitHub Container Registry (GHCR)**:

1. **Triggering:** The workflow executes on any push to the `main` or `mcp-transition` branches, or when a release tag (e.g., `v*`) is pushed. It can also be triggered manually using `workflow_dispatch`.
2. **GHCR Publishing:** It compiles and publishes the following images:
   * **Core Engine:** `ghcr.io/<owner>/etherfields-mcp-server`
   * **Voice Subsystem:** `ghcr.io/<owner>/etherfields-voice-subsystem`
3. **Advanced Cloud Caching:** The pipeline integrates natively with the GitHub Actions Cache (`type=gha`), enabling the cloud runner to reuse the `uv` virtual environment caches and downloaded databases across workflow runs. This keeps cloud build times under 30 seconds!

---

### 🎙️ Configuring the Voice Subsystem Container

To use the hands-free voice assistant container, ensure you configure the persistent shared host directory `${HOME}/.local/etherfields-ai/`:

1. **Configure the Environment:**
   Ensure your `.env` configuration file (located at `${HOME}/.local/etherfields-ai/.env`) includes your active voice settings:
   ```env
   ETHERFIELDS_LOCAL_DIR=/app/data
   ENABLE_VOICE=True
   STT_PROGRAM=faster-whisper
   TTS_ENGINE=kokoro
   ```
2. **Add Your Wake Word Models:**
   Create a `models` folder inside your dynamic directory and place your `.onnx` wake-word model files there (e.g. `jarvis.onnx` or any custom trained models):
   ```bash
   mkdir -p ~/.local/etherfields-ai/models
   cp src/voice/models/jarvis.onnx ~/.local/etherfields-ai/models/
   ```
3. **Download Audio Synthesis Models (Optional):**
   If you configure Kokoro, you can place model files (e.g., `kokoro-v0_19.onnx` and `voices.bin`) inside the same custom directory or let the container pull them automatically on first narration.

---

### 🔀 The Multi-Container Audio IPC Bridge (No Port Conflicts!)

To play audio out loud, we must overcome a common multi-container limitation: the lightweight `mcp-server` container does not have audio hardware access or voice libraries, while the `voice-subsystem` container has full hardware mapping but does not receive the LLM's tool calls.

We solved this natively using a **Multi-Threaded Filesystem IPC Queue** in the shared volume mount:
* When the AI Agent calls the `narrate_text(text)` tool, the MCP server detects `NARRATE_VIA_QUEUE=true` and writes a small, structured JSON request file inside the shared volume mount (`/app/data/narration_queue/req_<uuid>.json`).
* Inside the `voice-subsystem`, `voice_listener.py` starts a concurrent, background daemon thread (`load_narration_worker()`) that constantly polls this shared folder.
* When a request is detected, the worker instantly reads it, synthesizes and plays the audio natively through the host's speakers, and cleans up the request file.
* This operates with **zero port conflicts, zero firewall headaches, and sub-millisecond lag**.

---

### 🐳 Starting the Services with Docker Compose

Modern Docker installations natively support standard compose actions. 

#### 1. Start the services in the background:
```bash
docker compose up -d
```

#### 2. Check live container logs (to see wake word detections and audio outputs):
```bash
docker compose logs -f voice-subsystem
```

#### 3. Native Hardware Audio Device Mapping:
The `voice-subsystem` is configured inside `docker-compose.yml` to support native host soundcards:
```yaml
    devices:
      - /dev/snd:/dev/snd
    network_mode: host
    ipc: host
    group_add:
      - audio
```
*Note on Linux:* This provides incredibly low-latency and robust native audio recording and playback using ALSA/PulseAudio/PipeWire.

*Note on macOS & Windows:* Since Docker Desktop runs inside a Virtual Machine on macOS and Windows, direct audio hardware device passthrough (`/dev/snd`) is not supported natively. For Mac and Windows environments, **it is highly recommended to run the `voice-subsystem` natively** on your host machine to access the physical microphone and speakers, while running the core `mcp-server` inside Docker:
```bash
# Run voice listener natively on Mac/Windows:
uv run src/voice/voice_listener.py
```

### Direct MCP Execution in Docker

For standard AI Clients (like Claude Desktop or Gemini CLI), you can point your configuration directly to execute the docker container in stdio mode:

```json
{
  "mcpServers": {
    "etherfields-ai-docker": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-v",
        "/Users/ryan/.local/etherfields-ai:/app/data",
        "etherfields-ai-mcp-server"
      ]
    }
  }
}
```

---

## 👥 Players & Campaign State
Tracked inside `RULEMASTER.md` to customize rule context (such as character-specific abilities):
* **Player Count:** 2 Players
* **Characters:**
  * **The Specialist** (Expert engineer, builds Progress engine)
  * **The Free Spirit** (Bends basic game laws, generates Spirit Tokens)
