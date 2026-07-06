# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///

import argparse
import json
import os
import sys
import time
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_env_vars():
    env_vars = {}
    local_dir = os.environ.get("ETHERFIELDS_LOCAL_DIR")
    paths_to_try = []
    if local_dir:
        paths_to_try.append(os.path.join(os.path.abspath(os.path.expanduser(os.path.expandvars(local_dir))), ".env"))
    paths_to_try.append(os.path.join(BASE_DIR, ".env"))

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
CUSTOM_DIR_STR = _env.get("ETHERFIELDS_LOCAL_DIR", BASE_DIR)
CUSTOM_DIR = os.path.abspath(os.path.expanduser(os.path.expandvars(CUSTOM_DIR_STR)))

RAW_CACHE_PATH = os.path.join(CUSTOM_DIR, "scripts", "secret_scripts_cache.json")
if not os.path.exists(RAW_CACHE_PATH):
    RAW_CACHE_PATH = os.path.join(CUSTOM_DIR, "secret_scripts_cache.json")
if not os.path.exists(RAW_CACHE_PATH):
    RAW_CACHE_PATH = os.path.join(BASE_DIR, "secret_scripts_cache.json")

STRUCTURED_CACHE_PATH = os.path.join(CUSTOM_DIR, "scripts", "structured_scripts_cache.json")
if not os.path.exists(STRUCTURED_CACHE_PATH):
    STRUCTURED_CACHE_PATH = os.path.join(CUSTOM_DIR, "structured_scripts_cache.json")
if not os.path.exists(STRUCTURED_CACHE_PATH):
    STRUCTURED_CACHE_PATH = os.path.join(BASE_DIR, "structured_scripts_cache.json")
URL_PREFIX = "https://dev.etherfieldsapp.awakenrealms.com/assets/secrets/en/"

def build_cache(force=False):
    if os.path.exists(RAW_CACHE_PATH) and not force:
        print("[Secret Scripts] Cache file already exists. Use --update-cache to rebuild.", file=sys.stderr)
        return True

    print("[Secret Scripts] Starting cache build for core campaign...", file=sys.stderr)
    stats_url = f"{URL_PREFIX}stats.json"

    try:
        print(f"[Secret Scripts] Fetching stats from {stats_url}...", file=sys.stderr)
        req = urllib.request.Request(stats_url, headers={"User-Agent": "Etherfields Rule Master Cache Builder (Polite User)"})
        with urllib.request.urlopen(req) as response:
            stats = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"Error fetching stats: {e}", file=sys.stderr)
        return False

    core_count = stats.get("core", 0)
    if core_count == 0:
        print("Error: Could not find 'core' bundle count in stats.json", file=sys.stderr)
        return False

    print(f"[Secret Scripts] Core campaign consists of {core_count} shards.", file=sys.stderr)

    combined_scripts = {}

    for i in range(core_count):
        shard_url = f"{URL_PREFIX}core/{i}.json"
        print(f"[Secret Scripts] Downloading core shard {i+1}/{core_count}... ({shard_url})", file=sys.stderr)

        try:
            req = urllib.request.Request(shard_url, headers={"User-Agent": "Etherfields Rule Master Cache Builder (Polite User)"})
            with urllib.request.urlopen(req) as response:
                shard_data = json.loads(response.read().decode("utf-8"))
                combined_scripts.update(shard_data)
        except Exception as e:
            print(f"Error downloading shard {i}: {e}", file=sys.stderr)
            return False

        # Polite throttling as requested (1.5 seconds)
        if i < core_count - 1:
            print("[Secret Scripts] Sleeping 1.5s to be polite...", file=sys.stderr)
            time.sleep(1.5)

    try:
        # Save raw cache
        with open(RAW_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(combined_scripts, f, indent=2, ensure_ascii=False)
        print(f"[Secret Scripts] Cached {len(combined_scripts)} raw scripts to {RAW_CACHE_PATH}!", file=sys.stderr)

        # Automatically run preprocessor to sync the structured database
        print("[Secret Scripts] Triggering preprocessor to build structured cache...", file=sys.stderr)
        import preprocess_scripts
        preprocess_scripts.preprocess(RAW_CACHE_PATH, STRUCTURED_CACHE_PATH)
        return True
    except Exception as e:
        print(f"Error saving cache to file: {e}", file=sys.stderr)
        return False

def lookup_script(script_num):
    if not os.path.exists(STRUCTURED_CACHE_PATH):
        print("[Secret Scripts] Structured cache not found. Rebuilding both raw and structured caches...", file=sys.stderr)
        if not build_cache():
            print("[Secret Scripts] Failed to build cache. Cannot perform lookup.", file=sys.stderr)
            return

    try:
        with open(STRUCTURED_CACHE_PATH, "r", encoding="utf-8") as f:
            scripts = json.load(f)
    except Exception as e:
        print(f"Error reading structured cache: {e}", file=sys.stderr)
        return

    script_num_str = str(script_num).strip()
    script_data = scripts.get(script_num_str)

    if script_data:
        tone = script_data.get("tone", "neutral")
        narrative = script_data.get("narrative", "")
        instructions = script_data.get("instructions", "")
        branches = script_data.get("branches", [])

        print("\n" + "="*60)
        print(f"SECRET SCRIPT: {script_num_str} (Tone: {tone.upper()})")
        print("="*60)

        if narrative:
            # Yellow text / italic simulation for narrative
            print("\033[93m" + "--- STORY NARRATIVE ---" + "\033[0m")
            print(f"\033[3m{narrative}\033[0m")
            print()

        if instructions:
            # Green text for gameplay instructions
            print("\033[92m" + "--- ACTIONS & INSTRUCTIONS ---" + "\033[0m")
            print(instructions)
            print()

        if branches:
            # Cyan text for branching choices
            print("\033[96m" + "--- BRANCHING CHOICES ---" + "\033[0m")
            for b in branches:
                dest = b['link'].split('/')[-1]
                print(f"  • {b['label']} -> go to script {dest}")
            print()

        print("="*60 + "\n")
    else:
        print(f"\n[Secret Scripts] Script '{script_num_str}' not found in structured cache.\n", file=sys.stderr)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Etherfields Secret Scripts Cache & Retrieval Tool")
    parser.add_argument("--update-cache", action="store_true", help="Politely rebuild the local secret scripts cache")
    parser.add_argument("--script", type=str, help="Look up a secret script by number/id")

    args = parser.parse_args()

    if args.update_cache:
        build_cache(force=True)
    elif args.script:
        lookup_script(args.script)
    else:
        # Default behavior: build cache if missing
        if not os.path.exists(RAW_CACHE_PATH) or not os.path.exists(STRUCTURED_CACHE_PATH):
            build_cache()
        else:
            print("[Secret Scripts] Local caches exist. Use --script <num> to look up, or --update-cache to refresh.", file=sys.stderr)
