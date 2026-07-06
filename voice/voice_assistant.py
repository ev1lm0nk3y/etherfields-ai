# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "websockets",
#     "chatterbox-tts",
#     "torchaudio",
#     "torch",
#     "setuptools",
# ]
# ///

import asyncio
import websockets
import json
import base64
import struct
import tempfile
import subprocess
import os
import argparse
import random
import sys
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
CUSTOM_DIR_STR = _env.get("ETHERFIELDS_CUSTOM_DIR", BASE_DIR)
CUSTOM_DIR = os.path.abspath(os.path.expanduser(os.path.expandvars(CUSTOM_DIR_STR)))

SCRIPTS_CACHE_PATH = os.path.join(BASE_DIR, "structured_scripts_cache.json")
AUDIO_CACHE_DIR = os.path.join(CUSTOM_DIR, "audio_cache")

# Custom WS Endpoint Configuration (Generalized TTS)
TTS_WS_URL = _env.get("TTS_WS_URL", _env.get("BANTR_WS_URL", "ws://127.0.0.1:46290/generate"))

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
        print(f"[Playback Error] Failed to play audio file using player command '{AUDIO_PLAYER}': {e}", file=sys.stderr)

# Check for local pip-installed Chatterbox TTS packages
HAS_LOCAL_CHATTERBOX = False
try:
    from chatterbox.tts_turbo import ChatterboxTurboTTS
    import torchaudio as ta
    import torch
    HAS_LOCAL_CHATTERBOX = True
except ImportError:
    pass

_local_chatterbox_instance = None

def get_chatterbox():
    global _local_chatterbox_instance
    if _local_chatterbox_instance is None:
        if not HAS_LOCAL_CHATTERBOX:
            return None
        print("[Local TTS] Initializing local GPU-accelerated Chatterbox Turbo model...", flush=True)
        try:
            device = "mps" if torch.backends.mps.is_available() else "cpu"
            print(f"[Local TTS] Loading model on device: {device}...", flush=True)
            _local_chatterbox_instance = ChatterboxTurboTTS.from_pretrained(device=device)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[Chatterbox TTS Error] Failed to initialize model: {e}", file=sys.stderr)
            return None
    return _local_chatterbox_instance

def build_wav(pcm_data, sample_rate):
    num_channels = 1
    bits_per_sample = 16
    byte_rate = sample_rate * num_channels * (bits_per_sample // 8)
    block_align = num_channels * (bits_per_sample // 8)
    data_size = len(pcm_data)
    
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',
        36 + data_size,
        b'WAVE',
        b'fmt ',
        16,
        1,  # PCM format
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b'data',
        data_size
    )
    return header + pcm_data

def get_script_cache_paths(script_num, script_obj, args):
    engine = getattr(args, "engine", "chatterbox") or "chatterbox"
    
    # 1. Narrative Cache Path
    narrative_path = None
    narrative_text = script_obj.get("narrative", "").strip() if isinstance(script_obj, dict) else ""
    if narrative_text:
        voice_ref = getattr(args, "voice", "cyrus") or "cyrus"
        # Since voice_ref could be a path or a voice name, we should clean it to a safe string for filename
        if voice_ref.endswith(".wav"):
            voice_name = os.path.splitext(os.path.basename(voice_ref))[0]
        else:
            voice_name = voice_ref
        
        emotion = getattr(args, "emotion", None) or (script_obj.get("tone", "neutral") if isinstance(script_obj, dict) else "neutral")
        narrative_path = os.path.join(
            AUDIO_CACHE_DIR, engine, 
            f"script_{script_num}_narrative_{voice_name}_{emotion}.wav"
        )
        
    # 2. Instructions Cache Path
    instructions_path = None
    instructions_text = script_obj.get("instructions", "").strip() if isinstance(script_obj, dict) else ""
    if instructions_text:
        voice_ref = "cora" if engine == "chatterbox" else "0099_cora_f_neutral"
        if voice_ref.endswith(".wav"):
            voice_name = os.path.splitext(os.path.basename(voice_ref))[0]
        else:
            voice_name = voice_ref
            
        instructions_path = os.path.join(
            AUDIO_CACHE_DIR, engine, 
            f"script_{script_num}_instructions_{voice_name}_neutral.wav"
        )
        
    return narrative_path, instructions_path

async def speak_text_bantr(text, voice, speed=1.0, stability=2.0, creativity=0.0, output_path=None, play_audio=True):
    if output_path and os.path.exists(output_path):
        if play_audio:
            print(f"[Web TTS] Playing cached audio...", flush=True)
            play_audio_file(output_path)
        return True

    url = f"{TTS_WS_URL}?speed={speed}&stability={stability}&creativity={creativity}"
    
    try:
        # We specify max_size=None to handle large files (e.g. secret scripts)
        async with websockets.connect(url, max_size=None) as websocket:
            payload = {
                "text": text,
                "voice": voice,
                "seed": random.randint(0, 2**31 - 1)
            }
            await websocket.send(json.dumps(payload))
            
            async for message in websocket:
                data = json.loads(message)
                t = data.get("type")
                if t == "progress":
                    step = data.get("step")
                    total = data.get("total_steps")
                    print(f"[Web TTS] Generating speech... ({step}/{total})", flush=True)
                elif t == "done":
                    audio_b64 = data["audio"]
                    sample_rate = data.get("sample_rate", 22050)
                    pcm_data = base64.b64decode(audio_b64)
                    
                    wav_data = build_wav(pcm_data, sample_rate)
                    if output_path:
                        save_path = output_path
                        os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    else:
                        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                            f.write(wav_data)
                            save_path = f.name
                            
                    if output_path:
                        with open(save_path, "wb") as f:
                            f.write(wav_data)
                    
                    if play_audio:
                        print(f"[Web TTS] Playing generated audio...", flush=True)
                        try:
                            play_audio_file(save_path)
                        finally:
                            if not output_path and os.path.exists(save_path):
                                os.remove(save_path)
                    return True
                elif t == "error":
                    print(f"Error from Bantr: {data.get('message')}", file=sys.stderr)
                    return False
    except ConnectionRefusedError:
        print("\n[Web TTS Error] Could not connect to TTS server. Is the server running?", file=sys.stderr)
        return False
    except Exception as e:
        print(f"\n[Web TTS Error] An error occurred during voice generation: {e}", file=sys.stderr)
        return False

def resolve_reference_wav(voice_name="cyrus", emotion="neutral"):
    """
    Returns the absolute path to the local reference .wav sample file to use
    as the reference voice cloning prompt for Chatterbox TTS.
    """
    # Map abstract role names
    role_name = voice_name
    if voice_name.lower() == "cyrus":
        role_name = "narrative"
    elif voice_name.lower() == "cora":
        role_name = "instruction"

    # 1. Allow the user to specify custom direct mappings in .env
    # e.g., VOICE_REF_NARRATIVE_FEARFUL=/path/to/narrator_fearful.wav
    env_key = f"VOICE_REF_{role_name.upper()}_{emotion.upper()}"
    if env_key in _env:
        custom_path = _env[env_key]
        if os.path.exists(custom_path):
            return custom_path

    # Fallback to general voice role override
    general_env_key = f"VOICE_REF_{role_name.upper()}"
    if general_env_key in _env:
        custom_path = _env[general_env_key]
        if os.path.exists(custom_path):
            return custom_path

    # 2. Look in the configured reference voices directory (generalized TTS)
    base_dir = _env.get("TTS_RESOURCES_DIR", _env.get("BANTR_RESOURCES_DIR", "/Applications/Bantr.app/Contents/Resources/renderer/voices_transformed"))
    if not os.path.exists(base_dir) and "voices_transformed" not in base_dir:
        # Check if voices_transformed subfolder exists inside standard TTS_RESOURCES_DIR
        alt_path = os.path.join(base_dir, "voices_transformed")
        if os.path.exists(alt_path):
            base_dir = alt_path
    
    # Standard voice mappings
    mappings = {
        "cora": {
            "neutral": "0099_cora_f_neutral_gen.wav"
        },
        "jonathan": {
            "neutral": "0277_jonathan_m_narrative_gen.wav",
            "narrative": "0277_jonathan_m_narrative_gen.wav"
        },
        "cyrus": {
            "neutral": "0306_cyrus_m_neutral_gen.wav",
            "narrative": "0306_cyrus_m_neutral_gen.wav",
            "fearful": "0305_cyrus_m_fearful_gen.wav",
            "angry": "0307_cyrus_m_angry_gen.wav",
            "sad": "0308_cyrus_m_sad_gen.wav",
            "disgusted": "0309_cyrus_m_disgusted_gen.wav",
            "surprised": "0310_cyrus_m_surprised_gen.wav",
            "happy": "0311_cyrus_m_happy_gen.wav"
        }
    }
    
    vn = str(voice_name).lower().strip()
    em = str(emotion).lower().strip()
    
    if vn in mappings:
        style_map = mappings[vn]
        filename = style_map.get(em) or style_map.get("neutral")
        if filename:
            full_path = os.path.join(base_dir, filename)
            if os.path.exists(full_path):
                return full_path
                
    # Fallback/wildcard check in the directory if we cannot match perfectly
    if os.path.exists(base_dir):
        # Look for any filename containing the voice name and emotion
        for file in os.listdir(base_dir):
            if file.endswith(".wav") and vn in file.lower() and em in file.lower():
                return os.path.join(base_dir, file)
        # Fallback to cyrus neutral
        fallback_path = os.path.join(base_dir, "0306_cyrus_m_neutral_gen.wav")
        if os.path.exists(fallback_path):
            return fallback_path
            
    return None

def get_safe_audio_prompt(path):
    """
    Reads the audio file, checks length, and if shorter than 5.1 seconds,
    tiles/repeats the audio data so it exceeds 5.1 seconds, saving it to a temp file.
    """
    if not path or not os.path.exists(path):
        return path
        
    try:
        import soundfile as sf
        import numpy as np
        data, samplerate = sf.read(path)
        duration = len(data) / samplerate
        if duration < 5.1:
            # We need to tile the audio to exceed 5.1 seconds
            repeats = int(np.ceil(5.1 / duration))
            padded_data = np.tile(data, repeats)
            
            # Save to temporary path
            temp_f = tempfile.NamedTemporaryFile(suffix="_padded.wav", delete=False)
            temp_path = temp_f.name
            temp_f.close()
            
            sf.write(temp_path, padded_data, samplerate)
            print(f"[Local TTS] Audio prompt '{os.path.basename(path)}' was only {duration:.2f}s. Automatically padded/tiled to {len(padded_data)/samplerate:.2f}s.", flush=True)
            return temp_path
    except Exception as e:
        print(f"[Warning] Failed to pad audio prompt: {e}", flush=True)
        
    return path

_voice_conditionals_cache = {}

def speak_text_chatterbox(text, audio_prompt_path=None, output_path=None, play_audio=True):
    if output_path and os.path.exists(output_path):
        if play_audio:
            print(f"[Local TTS] Playing cached audio...", flush=True)
            play_audio_file(output_path)
        return True

    model = get_chatterbox()
    if model is None:
        print("\n[Chatterbox TTS Error] Local Chatterbox model is not available.", file=sys.stderr)
        if not HAS_LOCAL_CHATTERBOX:
            print("\n>>> Offline Local Setup Option <<<\n"
                  "To run Chatterbox completely offline and locally, you can install the python packages:\n"
                  "  pip install chatterbox-tts torchaudio torch\n"
                  "The assistant will automatically detect and use it locally!\n", file=sys.stderr)
        return False
        
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name
            
        if audio_prompt_path and os.path.exists(audio_prompt_path):
            cache_key = audio_prompt_path
            if cache_key in _voice_conditionals_cache:
                print(f"[Local TTS] Reusing cached voice conditionals (prompt: {os.path.basename(audio_prompt_path)})...", flush=True)
                model.conds = _voice_conditionals_cache[cache_key]
                wav = model.generate(text, audio_prompt_path=None)
            else:
                safe_prompt_path = get_safe_audio_prompt(audio_prompt_path)
                print(f"[Local TTS] Compiling and caching voice conditionals (prompt: {os.path.basename(audio_prompt_path)})...", flush=True)
                wav = model.generate(text, audio_prompt_path=safe_prompt_path)
                _voice_conditionals_cache[cache_key] = model.conds
                if safe_prompt_path != audio_prompt_path and os.path.exists(safe_prompt_path):
                    try:
                        os.remove(safe_prompt_path)
                    except:
                        pass
        else:
            print("[Local TTS] Synthesizing speech with default pretrained voice...", flush=True)
            wav = model.generate(text)
            
        # Ensure 2D tensor for torchaudio saving: (1, frames)
        if hasattr(wav, "cpu"):
            wav = wav.cpu()
        if hasattr(wav, "ndim") and wav.ndim == 1:
            wav = wav.unsqueeze(0)
            
        import torchaudio as ta
        save_path = output_path or temp_path
        
        # Ensure parent directory exists for save_path
        if output_path:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
        ta.save(save_path, wav, model.sr)
        
        if play_audio:
            print("[Local TTS] Playing generated audio...", flush=True)
            try:
                play_audio_file(save_path)
            finally:
                if not output_path and os.path.exists(save_path):
                    os.remove(save_path)
        return True
    except Exception as e:
        print(f"\n[Chatterbox TTS Error] Generation failed: {e}", file=sys.stderr)
        return False

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

    script_num_str = str(script_num).strip().lstrip('0')
    if not script_num_str:
        script_num_str = '0'
    return scripts.get(script_num_str)

def detect_script_emotion(text):
    """
    Analyzes the script text for emotional keywords and returns the most
    appropriate emotion for the Cyrus model ('fearful', 'sad', 'angry', 'neutral').
    """
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
        return max_emotion
    return "neutral"

def resolve_cyrus_voice(emotion="neutral"):
    """
    Attempts to dynamically query the local Bantr server or read its local voices.json
    to find the correct Cyrus voice ID matching the requested emotion.
    """
    # 1. Try reading directly from Bantr app's voices.json on disk (fast & reliable)
    base_dir = _env.get("TTS_RESOURCES_DIR", _env.get("BANTR_RESOURCES_DIR", "/Applications/Bantr.app/Contents/Resources/renderer"))
    if "voices_transformed" in base_dir:
        base_dir = os.path.dirname(base_dir)
        
    local_voices_path = os.path.join(base_dir, "voices.json")
    if not os.path.exists(local_voices_path):
        local_voices_path = "/Applications/Bantr.app/Contents/Resources/renderer/voices.json"
        
    if os.path.exists(local_voices_path):
        try:
            with open(local_voices_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
                # Filter for cyrus voice items
                cyrus_voices = []
                for v in data:
                    vid = str(v.get("id", "")).lower()
                    vname = str(v.get("name", "")).lower()
                    if "cyrus" in vid or "cyrus" in vname:
                        cyrus_voices.append(v)
                        
                if cyrus_voices:
                    # Look for specific emotion in style/id
                    for cv in cyrus_voices:
                        style = str(cv.get("style", "")).lower()
                        vid = str(cv.get("id", "")).lower()
                        if emotion in style or emotion in vid:
                            voice_id = cv.get("id")
                            print(f"[Web TTS] Found Cyrus voice '{voice_id}' for style '{emotion}' in voices.json")
                            return voice_id
                            
                    # Fallback to neutral if style/emotion not explicitly found
                    for cv in cyrus_voices:
                        style = str(cv.get("style", "")).lower()
                        if "neutral" in style:
                            voice_id = cv.get("id")
                            print(f"[Web TTS] Style '{emotion}' not found. Defaulting to neutral Cyrus voice: '{voice_id}'")
                            return voice_id
                            
                    first_id = cyrus_voices[0].get("id")
                    print(f"[Web TTS] Style '{emotion}' not found. Defaulting to first Cyrus voice: '{first_id}'")
                    return first_id
        except Exception as e:
            print(f"[Web TTS Info] Tried reading local voices.json but failed: {e}")

    # 2. Hardcoded verified failsafe mapping
    failsafe = {
        "neutral": "0306_cyrus_m_neutral",
        "fearful": "0305_cyrus_m_fearful",
        "angry": "0307_cyrus_m_angry",
        "sad": "0308_cyrus_m_sad",
        "disgusted": "0309_cyrus_m_disgusted",
        "surprised": "0310_cyrus_m_surprised",
        "happy": "0311_cyrus_m_happy",
        "narrative": "0306_cyrus_m_neutral"
    }
    
    if emotion in failsafe:
        val = failsafe[emotion]
        print(f"[Web TTS] Resolved Cyrus voice '{val}' for emotion '{emotion}' via failsafe mapping")
        return val

    # 3. Try querying local Bantr HTTP endpoints
    endpoints = [
        "http://127.0.0.1:46290/voices",
        "http://127.0.0.1:46290/api/voices",
        "http://127.0.0.1:46290/"
    ]
    
    import urllib.request
    
    found_voice = None
    for url in endpoints:
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=1.0) as response:
                data = json.loads(response.read().decode("utf-8"))
                
                voices = []
                if isinstance(data, list):
                    voices = data
                elif isinstance(data, dict):
                    if "voices" in data:
                        voices = data["voices"]
                    else:
                        voices = list(data.keys())
                
                cyrus_voices = [v for v in voices if "cyrus" in str(v).lower()]
                if cyrus_voices:
                    # Look for specific emotion
                    for cv in cyrus_voices:
                        if emotion in str(cv).lower():
                            found_voice = str(cv)
                            break
                    # If specific emotion not found, try to find close match or default to first
                    if not found_voice:
                        found_voice = str(cyrus_voices[0])
                    break
        except Exception:
            continue
            
    if found_voice:
        print(f"[Web TTS] Dynamically resolved Cyrus voice: '{found_voice}' (emotion: '{emotion}')")
        return found_voice
        
    fallback = f"cyrus_m_{emotion}"
    print(f"[Web TTS] Could not dynamically resolve Cyrus voice. Falling back to: '{fallback}'")
    return fallback

def clean_script_text(text, engine="chatterbox"):
    # Basic cleanup: remove asterisks and backticks
    clean = text.replace("*", "").replace("`", "").replace("\n", " ").strip()
    
    # Strip out all timing instructions entirely for all engines (e.g., {1.5s} or {0.5s} -> space)
    # This prevents modern TTS engines from speaking pacing cues out loud as "one point five sss".
    clean = re.sub(r'\{\s*\d*(?:\.\d+)?s\s*\}', ' ', clean)
    
    # Standardize multiple whitespaces into a single space
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip()

async def pre_cache_scripts_async(script_nums, args):
    print("\n" + "="*60)
    print("ETHERFIELDS RULE MASTER - PRE-CACHING SCRIPTS (Bantr)")
    print(f"Processing {len(script_nums)} scripts...")
    print("="*60 + "\n")
    
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
        instructions = script_obj.get("instructions", "").strip() if isinstance(script_obj, dict) else ""
        
        narrative_path, instructions_path = get_script_cache_paths(num, script_obj, args)
        
        print(f"\n--- Script {num} ---")
        
        # 1. Process Narrative
        if narrative:
            if narrative_path and os.path.exists(narrative_path):
                print(f"  ✓ Narrative already cached at {os.path.basename(narrative_path)}")
                skipped_count += 1
            else:
                emotion = args.emotion or script_obj.get("tone", "neutral")
                voice_ref = args.voice or "cyrus"
                voice = await asyncio.to_thread(resolve_cyrus_voice, emotion) if voice_ref.lower() == "cyrus" else voice_ref
                
                clean_narrative = clean_script_text(narrative, "bantr")
                print(f"  🔊 Generating narrative via Bantr (Voice: {voice})...")
                ok = await speak_text_bantr(clean_narrative, voice, args.speed, args.stability, args.creativity, output_path=narrative_path, play_audio=False)
                if ok:
                    success_count += 1
                else:
                    fail_count += 1
                    
        # 2. Process Instructions
        if instructions:
            if instructions_path and os.path.exists(instructions_path):
                print(f"  ✓ Instructions already cached at {os.path.basename(instructions_path)}")
                skipped_count += 1
            else:
                instruction_voice = "0099_cora_f_neutral"
                clean_instructions = clean_script_text(instructions, "bantr")
                print(f"  🔊 Generating instructions via Bantr (Voice: {instruction_voice})...")
                ok = await speak_text_bantr(clean_instructions, instruction_voice, args.speed, args.stability, args.creativity, output_path=instructions_path, play_audio=False)
                if ok:
                    success_count += 1
                else:
                    fail_count += 1
                    
    print("\n" + "="*60)
    print("PRE-CACHING COMPLETED")
    print(f"Successfully cached: {success_count} files")
    print(f"Already cached: {skipped_count} files")
    print(f"Failed/Missing: {fail_count}")
    print("="*60 + "\n")

async def main_async(args):
    # This async runner handles Bantr's websocket protocol
    if args.pre_cache:
        raw_nums = [s.strip() for s in args.pre_cache.split(",") if s.strip()]
        script_nums = [n.lstrip('0') if n.lstrip('0') else '0' for n in raw_nums]
        await pre_cache_scripts_async(script_nums, args)
        return

    script_obj = None
    if args.script:
        script_obj = lookup_secret_script(args.script)
        if not script_obj:
            print(f"Script '{args.script}' not found in cache.", file=sys.stderr)
            sys.exit(1)
            
        print("\n" + "="*60)
        print(f"SECRET SCRIPT: {args.script}")
        print("="*60)
        if isinstance(script_obj, dict) and "narrative" in script_obj:
            print(f"TONE: {script_obj.get('tone', 'neutral')}")
            print(script_obj["narrative"])
            print("\n--- INSTRUCTIONS ---")
            print(script_obj["instructions"])
        else:
            print(script_obj)
        print("="*60 + "\n")
        
    if args.text:
        voice = args.voice or "0099_cora_f_neutral"
        text_to_speak = clean_script_text(args.text, "bantr")
        print(f"[Web TTS] Playing via voice: '{voice}'...")
        await speak_text_bantr(text_to_speak, voice, args.speed, args.stability, args.creativity)
    elif script_obj and isinstance(script_obj, dict):
        # Sequential Dual-Voice Playback
        narrative = script_obj.get("narrative", "").strip()
        instructions = script_obj.get("instructions", "").strip()
        
        narrative_path, instructions_path = get_script_cache_paths(args.script, script_obj, args)
        
        if narrative:
            emotion = args.emotion or script_obj.get("tone", "neutral")
            voice_ref = args.voice or "cyrus"
            voice = await asyncio.to_thread(resolve_cyrus_voice, emotion) if voice_ref.lower() == "cyrus" else voice_ref
            
            clean_narrative = clean_script_text(narrative, "bantr")
            if narrative_path and os.path.exists(narrative_path):
                print(f"[Web TTS] Found cached NARRATIVE audio: {os.path.basename(narrative_path)}. Playing instantly...")
            else:
                print(f"[Web TTS] Playing NARRATIVE via voice: '{voice}'...")
            await speak_text_bantr(clean_narrative, voice, args.speed, args.stability, args.creativity, output_path=narrative_path)
            
        if instructions:
            instruction_voice = "0099_cora_f_neutral" # Default clear instruction voice
            clean_instructions = clean_script_text(instructions, "bantr")
            if instructions_path and os.path.exists(instructions_path):
                print(f"[Web TTS] Found cached INSTRUCTIONS audio: {os.path.basename(instructions_path)}. Playing instantly...")
            else:
                print(f"[Web TTS] Playing INSTRUCTIONS via voice: '{instruction_voice}'...")
            await speak_text_bantr(clean_instructions, instruction_voice, args.speed, args.stability, args.creativity, output_path=instructions_path)
    elif script_obj:
        # Fallback for old cache format
        voice = args.voice or "0277_jonathan_m_narrative"
        text_to_speak = clean_script_text(script_obj, "bantr")
        await speak_text_bantr(text_to_speak, voice, args.speed, args.stability, args.creativity)

def pre_cache_scripts_sync(script_nums, args):
    print("\n" + "="*60)
    print("ETHERFIELDS RULE MASTER - PRE-CACHING SCRIPTS (Chatterbox)")
    print(f"Processing {len(script_nums)} scripts...")
    print("="*60 + "\n")
    
    # Pre-load Chatterbox model to GPU
    get_chatterbox()
    
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
        instructions = script_obj.get("instructions", "").strip() if isinstance(script_obj, dict) else ""
        
        narrative_path, instructions_path = get_script_cache_paths(num, script_obj, args)
        
        print(f"\n--- Script {num} ---")
        
        # 1. Process Narrative
        if narrative:
            if narrative_path and os.path.exists(narrative_path):
                print(f"  ✓ Narrative already cached at {os.path.basename(narrative_path)}")
                skipped_count += 1
            else:
                emotion = args.emotion or script_obj.get("tone", "neutral")
                voice_ref = args.voice or "cyrus"
                audio_prompt_path = None
                if voice_ref.lower().endswith(".wav") and os.path.exists(voice_ref):
                    audio_prompt_path = voice_ref
                else:
                    audio_prompt_path = resolve_reference_wav(voice_ref, emotion)
                    
                clean_narrative = clean_script_text(narrative, "chatterbox")
                print(f"  🔊 Generating narrative (Voice: {voice_ref}, Emotion: {emotion})...")
                ok = speak_text_chatterbox(clean_narrative, audio_prompt_path, output_path=narrative_path, play_audio=False)
                if ok:
                    success_count += 1
                else:
                    fail_count += 1
                    
        # 2. Process Instructions
        if instructions:
            if instructions_path and os.path.exists(instructions_path):
                print(f"  ✓ Instructions already cached at {os.path.basename(instructions_path)}")
                skipped_count += 1
            else:
                instruction_prompt_path = resolve_reference_wav("cora", "neutral")
                clean_instructions = clean_script_text(instructions, "chatterbox")
                print(f"  🔊 Generating instructions (Voice: cora)...")
                ok = speak_text_chatterbox(clean_instructions, instruction_prompt_path, output_path=instructions_path, play_audio=False)
                if ok:
                    success_count += 1
                else:
                    fail_count += 1
                    
    print("\n" + "="*60)
    print("PRE-CACHING COMPLETED")
    print(f"Successfully cached: {success_count} files")
    print(f"Already cached: {skipped_count} files")
    print(f"Failed/Missing: {fail_count}")
    print("="*60 + "\n")

def main():
    parser = argparse.ArgumentParser(description="Etherfields Rule Master Voice Assistant")
    parser.add_argument("--text", type=str, help="Convert custom text to speech and play it")
    parser.add_argument("--script", type=str, help="Look up a secret script and play it")
    parser.add_argument("--voice", type=str, help="Voice ID / prompt name (cyrus, cora, jonathan, or path to local reference .wav file)")
    parser.add_argument("--engine", type=str, choices=["chatterbox", "bantr"], default="chatterbox", help="TTS Engine to use (default: chatterbox)")
    parser.add_argument("--emotion", type=str, choices=["neutral", "fearful", "sad", "angry", "happy", "narrative"], help="Override emotion detection for Cyrus voice (Bantr/Chatterbox)")
    parser.add_argument("--speed", type=float, default=1.0, help="Speech speed (default: 1.0)")
    parser.add_argument("--stability", type=float, default=2.0, help="Speech stability (default: 2.0)")
    parser.add_argument("--creativity", type=float, default=0.0, help="Speech creativity (default: 0.0)")
    parser.add_argument("--interactive", action="store_true", help="Run in persistent interactive mode (keeps model loaded on GPU for ultra-fast generation)")
    parser.add_argument("--pre-cache", type=str, help="Pre-cache a comma-separated list of script numbers silently without playing them")
    
    args = parser.parse_args()
    
    if not args.text and not args.script and not args.interactive and not args.pre_cache:
        parser.print_help()
        sys.exit(0)
        
    if args.pre_cache and args.engine == "chatterbox":
        raw_nums = [s.strip() for s in args.pre_cache.split(",") if s.strip()]
        script_nums = [n.lstrip('0') if n.lstrip('0') else '0' for n in raw_nums]
        pre_cache_scripts_sync(script_nums, args)
        sys.exit(0)
        
    if args.interactive:
        if args.engine == "chatterbox":
            print("\n" + "="*60)
            print("ETHERFIELDS RULE MASTER - INTERACTIVE VOICE ASSISTANT")
            print("Engine: local GPU-accelerated Chatterbox Turbo")
            print("Type a script number (e.g. 777), type custom text directly,")
            print("or type 'exit' or 'quit' to close.")
            print("="*60 + "\n")
            
            # Pre-load the model to GPU to keep it warm
            get_chatterbox()
            
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
                        print("-"*60)
                        if isinstance(script_obj, dict) and "narrative" in script_obj:
                            print(f"TONE: {script_obj.get('tone', 'neutral').upper()}")
                            print(script_obj["narrative"])
                            print("\n--- INSTRUCTIONS ---")
                            print(script_obj["instructions"])
                        else:
                            print(script_obj)
                        print("-"*60)
                        
                        if isinstance(script_obj, dict) and "narrative" in script_obj:
                            narrative = script_obj.get("narrative", "").strip()
                            instructions = script_obj.get("instructions", "").strip()
                            
                            narrative_path, instructions_path = get_script_cache_paths(user_input, script_obj, args)
                            
                            if narrative:
                                emotion = script_obj.get("tone", "neutral")
                                audio_prompt_path = resolve_reference_wav("cyrus", emotion)
                                clean_narrative = clean_script_text(narrative, "chatterbox")
                                if narrative_path and os.path.exists(narrative_path):
                                    print(f"[Local TTS] Found cached NARRATIVE audio: {os.path.basename(narrative_path)}. Playing instantly...")
                                else:
                                    print(f"[Local TTS] Playing NARRATIVE with zero-shot cloning for emotion '{emotion}'...")
                                speak_text_chatterbox(clean_narrative, audio_prompt_path, output_path=narrative_path)
                                
                            if instructions:
                                instruction_prompt_path = resolve_reference_wav("cora", "neutral")
                                clean_instructions = clean_script_text(instructions, "chatterbox")
                                if instructions_path and os.path.exists(instructions_path):
                                    print(f"[Local TTS] Found cached INSTRUCTIONS audio: {os.path.basename(instructions_path)}. Playing instantly...")
                                else:
                                    print(f"[Local TTS] Playing INSTRUCTIONS with clear rule voice...")
                                speak_text_chatterbox(clean_instructions, instruction_prompt_path, output_path=instructions_path)
                        else:
                            clean_text = clean_script_text(str(script_obj), "chatterbox")
                            audio_prompt_path = resolve_reference_wav("cyrus", "neutral")
                            speak_text_chatterbox(clean_text, audio_prompt_path)
                    else:
                        clean_text = clean_script_text(user_input, "chatterbox")
                        audio_prompt_path = resolve_reference_wav("cyrus", "neutral")
                        print(f"[Local TTS] Playing custom text...")
                        speak_text_chatterbox(clean_text, audio_prompt_path)
                except KeyboardInterrupt:
                    print("\nExiting interactive mode. Goodbye!")
                    break
                except Exception as loop_e:
                    print(f"An error occurred in interactive loop: {loop_e}")
        else:
            print("[Bantr] Interactive mode is only supported with local Chatterbox engine.", file=sys.stderr)
            sys.exit(1)
            
    elif args.engine == "chatterbox":
        script_obj = None
        if args.script:
            script_obj = lookup_secret_script(args.script)
            if not script_obj:
                print(f"Script '{args.script}' not found in cache.", file=sys.stderr)
                sys.exit(1)
                
            print("\n" + "="*60)
            print(f"SECRET SCRIPT: {args.script}")
            print("="*60)
            if isinstance(script_obj, dict) and "narrative" in script_obj:
                print(f"TONE: {script_obj.get('tone', 'neutral')}")
                print(script_obj["narrative"])
                print("\n--- INSTRUCTIONS ---")
                print(script_obj["instructions"])
            else:
                print(script_obj)
            print("="*60 + "\n")
            
        if args.text:
            text_to_speak = clean_script_text(args.text, "chatterbox")
            audio_prompt_path = None
            if args.voice and args.voice.lower().endswith(".wav") and os.path.exists(args.voice):
                audio_prompt_path = args.voice
            elif args.voice:
                audio_prompt_path = resolve_reference_wav(args.voice, "neutral")
            speak_text_chatterbox(text_to_speak, audio_prompt_path)
            
        elif script_obj and isinstance(script_obj, dict):
            # Sequential Dual-Voice Playback
            narrative = script_obj.get("narrative", "").strip()
            instructions = script_obj.get("instructions", "").strip()
            
            narrative_path, instructions_path = get_script_cache_paths(args.script, script_obj, args)
            
            if narrative:
                emotion = args.emotion or script_obj.get("tone", "neutral")
                voice_ref = args.voice or "cyrus"
                
                audio_prompt_path = None
                if voice_ref.lower().endswith(".wav") and os.path.exists(voice_ref):
                    audio_prompt_path = voice_ref
                else:
                    audio_prompt_path = resolve_reference_wav(voice_ref, emotion)
                    
                clean_narrative = clean_script_text(narrative, "chatterbox")
                if narrative_path and os.path.exists(narrative_path):
                    print(f"[Local TTS] Found cached NARRATIVE audio: {os.path.basename(narrative_path)}. Playing instantly...")
                else:
                    print(f"[Local TTS] Playing NARRATIVE with zero-shot cloning for emotion '{emotion}'...")
                speak_text_chatterbox(clean_narrative, audio_prompt_path, output_path=narrative_path)
                
            if instructions:
                # Default clear female voice for instructions via Chatterbox
                instruction_prompt_path = resolve_reference_wav("cora", "neutral")
                clean_instructions = clean_script_text(instructions, "chatterbox")
                if instructions_path and os.path.exists(instructions_path):
                    print(f"[Local TTS] Found cached INSTRUCTIONS audio: {os.path.basename(instructions_path)}. Playing instantly...")
                else:
                    print(f"[Local TTS] Playing INSTRUCTIONS with clear rule voice...")
                speak_text_chatterbox(clean_instructions, instruction_prompt_path, output_path=instructions_path)
        elif script_obj:
            # Fallback for old cache format
            text_to_speak = clean_script_text(script_obj, "chatterbox")
            audio_prompt_path = resolve_reference_wav("cyrus", "neutral")
            speak_text_chatterbox(text_to_speak, audio_prompt_path)
    else:
        # Bantr uses async websockets
        asyncio.run(main_async(args))

if __name__ == "__main__":
    main()
