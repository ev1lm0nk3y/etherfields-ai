# 🌌 Etherfields AI Rule Master & Surgical Retrieval Engine

An intelligent, local knowledge-base, and surgical rule-retrieval engine designed for the campaign board game **Etherfields** (specifically utilizing the official **Rulebook v2.0**).

This project turns an AI agent into an expert **Rule Master**, allowing players to quickly resolve complex mechanical queries with zero-hallucination, page-accurate text extractions.

---

## 🚀 Key Features

1. **Surgical Page-Mapping Lookup (`rulebook_tool.py`)**
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
├── rulebook_tool.py      # Unified Python 3.13 tool to validate, regenerate, and query the cache
├── GEMINI.md             # Automatic LLM instructions and workflow protocols
├── RULEMASTER.md         # Baseline rules role prompt and active player roster
├── TOPICS.md             # The central registry of cached topic files
└── README.md             # This file
```

---

## 🛠️ Setup & Usage

### Prerequisites
* **Python 3.13** or higher
* **`uv`** (fast Python package installer and runner)
* Place `Rulebook_20.pdf` in the project root.

### Usage Commands

#### 1. Validate the Cache (Checks hash/time metadata)
```bash
uv run rulebook_tool.py --validate
```
*Note: If the PDF is updated, the tool will automatically self-heal and regenerate the page cache and `index.json`.*

#### 2. Search for a Topic or Term
```bash
uv run rulebook_tool.py --search "Slumber"
```
This searches the index, lists matching chapters/index terms, maps them to their respective pages, and prints the raw extracted page contents for immediate, zero-guesswork rule verification.

#### 3. Force Cache Rebuild
```bash
uv run rulebook_tool.py --force
```

---

## 👥 Players & Campaign State
Tracked inside `RULEMASTER.md` to customize rule context (such as character-specific abilities):
* **Player Count:** 2 Players
* **Characters:**
  * **The Specialist** (Expert engineer, builds Progress engine)
  * **The Free Spirit** (Bends basic game laws, generates Spirit Tokens)
