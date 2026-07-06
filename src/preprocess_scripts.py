# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

import json
import os
import re

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

INPUT_CACHE = os.path.join(CUSTOM_DIR, "scripts", "secret_scripts_cache.json")
if not os.path.exists(INPUT_CACHE):
    INPUT_CACHE = os.path.join(CUSTOM_DIR, "secret_scripts_cache.json")
if not os.path.exists(INPUT_CACHE):
    INPUT_CACHE = os.path.join(BASE_DIR, "secret_scripts_cache.json")

OUTPUT_CACHE = os.path.join(CUSTOM_DIR, "scripts", "structured_scripts_cache.json")
if not os.path.exists(OUTPUT_CACHE):
    OUTPUT_CACHE = os.path.join(CUSTOM_DIR, "structured_scripts_cache.json")
if not os.path.exists(OUTPUT_CACHE):
    OUTPUT_CACHE = os.path.join(BASE_DIR, "structured_scripts_cache.json")

def detect_script_emotion(text):
    text_lower = text.lower()

    # Etherfields surreal nightmare / tension keywords
    fear_words = {"fear", "scared", "afraid", "horror", "terrified", "terror", "creepy", "darkness",
                  "monster", "beast", "trap", "danger", "claws", "teeth", "sinister", "threat",
                  "hide", "creeping", "flee", "escape", "warn", "warning", "deadly", "nightmare",
                  "paralyzed", "shiver", "shivering", "shadows", "ghostly"}

    sad_words = {"sad", "sadness", "grief", "loss", "lonely", "alone", "cry", "crying", "weep",
                 "weeping", "sobbing", "sob", "forlorn", "memories", "gone", "dead", "death",
                 "tomb", "grave", "ruin", "ruins", "shattered", "forgotten", "melancholy", "weary",
                 "tired", "absence", "sigh", "sighs", "old"}

    angry_words = {"angry", "anger", "hate", "hatred", "rage", "fury", "furious", "attack",
                   "weapon", "revolver", "shot", "shoot", "bang", "fight", "blast", "clash",
                   "destroy", "vengeance", "blood", "bloody", "strike"}

    fear_score = sum(1 for w in fear_words if w in text_lower)
    sad_score = sum(1 for w in sad_words if w in text_lower)
    angry_score = sum(1 for w in angry_words if w in text_lower)

    scores = {"fearful": fear_score, "sad": sad_score, "angry": angry_score}
    max_emotion, max_score = max(scores.items(), key=lambda x: x[1])

    # We remove 'happy' from auto-detection since Etherfields is a surreal, melancholic game.
    # Cozy dreaming with words like 'home' or 'warmth' combined with 'forlorn' or 'forgotten'
    # represents melancholic nostalgia (sad).
    if max_score > 0:
        return max_emotion, False
    return "neutral", True

def preprocess(input_path=INPUT_CACHE, output_path=OUTPUT_CACHE):
    with open(input_path, "r", encoding="utf-8") as f:
        raw_scripts = json.load(f)

    structured_scripts = {}

    # We want to match text that is wrapped in *...* (italics)
    # BUT we need to ensure we don't accidentally match **bold** text which are instructions.
    # A negative lookahead/lookbehind ensures we only match single asterisks.
    narrative_pattern = re.compile(r'(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)', re.DOTALL)
    branch_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')

    for script_id, full_text in raw_scripts.items():
        # 1. Extract Narrative
        narrative_blocks = narrative_pattern.findall(full_text)
        narrative = "\n\n".join(narrative_blocks).strip()

        # 2. Extract Instructions
        # Remove the narrative blocks and any stray timing cues that might be left outside them
        instructions = narrative_pattern.sub('', full_text)
        instructions = re.sub(r'\{\s*\d*(?:\.\d+)?s\s*\}', '', instructions)

        # Clean up excessive newlines left over from substitution
        instructions = re.sub(r'\n{3,}', '\n\n', instructions).strip()

        # 3. Extract Branches
        branches = []
        for match in branch_pattern.finditer(full_text):
            branches.append({"label": match.group(1), "link": match.group(2)})

        tone, needs_review = detect_script_emotion(narrative)

        structured_scripts[script_id] = {
            "narrative": narrative,
            "instructions": instructions,
            "branches": branches,
            "tone": tone,
            "needs_llm_review": needs_review
        }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(structured_scripts, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    preprocess()
