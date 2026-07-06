# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "numpy==1.26.4",
#     "sounddevice",
#     "soundfile",
#     "pyyaml",
# ]
# ---
# Note: To run this script, use: uv run voice/reformat_notebook.py or similar.
# ///

import os
import sys
import time
import uuid

import sounddevice as sd
import soundfile as sf
import yaml

# Repo root is parent of the directory containing this file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WIZARD_DATA_DIR = os.path.join(BASE_DIR, "src", "voice", "training_data")

SAMPLE_RATE = 16000  # standard for nanowakeword
CHANNELS = 1
RECORD_DURATION = 1.6  # seconds


def beep():
    """Plays system alert sound."""
    sys.stdout.write("\a")
    sys.stdout.flush()


def record_sample(sample_idx, target_dir):
    """Records a single positive voice sample from the microphone."""
    print(f"\n🎙️  [Clip #{sample_idx}] Get ready...")
    time.sleep(0.5)

    beep()
    print("🔴 RECORDING... Speak your wake word now!")

    # Record audio data in-memory
    recording = sd.rec(
        int(RECORD_DURATION * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16"
    )
    sd.wait()  # Wait until the recording is finished

    print("✅ Stopped.")

    # Save recording
    filename = f"target_{sample_idx}_{uuid.uuid4().hex[:8]}.wav"
    filepath = os.path.join(target_dir, filename)
    sf.write(filepath, recording, SAMPLE_RATE)
    return filepath


def main():
    print("=" * 60)
    print("        🎨 NANOWAKEWORD CUSTOM VOICE TRAINING WIZARD 🎨")
    print("=" * 60)
    print("This wizard helps you record your own voice to train a highly accurate,")
    print("personalized wake word model using nanowakeword.")
    print("-" * 60)

    # 1. Get Wake Word name
    default_wakeword = "jarvis"
    wakeword = (
        input(f"Enter your desired wake word (default: '{default_wakeword}'): ").strip().lower()
    )
    if not wakeword:
        wakeword = default_wakeword

    # Clean wake word name for folder structure
    wakeword_slug = wakeword.replace(" ", "_")
    project_dir = os.path.join(WIZARD_DATA_DIR, wakeword_slug)
    targets_dir = os.path.join(project_dir, "data", "targets")
    negatives_dir = os.path.join(project_dir, "data", "negatives")
    false_positives_dir = os.path.join(project_dir, "data", "false_positives")
    output_models_dir = os.path.join(project_dir, "models")

    # Create directories
    os.makedirs(targets_dir, exist_ok=True)
    os.makedirs(negatives_dir, exist_ok=True)
    os.makedirs(false_positives_dir, exist_ok=True)
    os.makedirs(output_models_dir, exist_ok=True)

    print("\n📂 Created training workspace:")
    print(f"   -> Workspace: {project_dir}")
    print(f"   -> Positive Samples: {targets_dir}")

    # 2. Configure sample count
    default_count = 40
    count_str = input(
        f"\nHow many voice samples would you like to record? (Recommended: 30-50, default: {default_count}): "
    ).strip()
    try:
        count = int(count_str) if count_str else default_count
    except ValueError:
        count = default_count

    print(f"\n🎬 Preparing to record {count} clips.")
    print("For best results, vary your distance, tone, speed, and background noise slightly.")
    input("Press Enter when you are ready to begin the recording sequence...")

    recorded_count = 0
    for i in range(1, count + 1):
        try:
            record_sample(i, targets_dir)
            recorded_count += 1
        except Exception as e:
            print(f"❌ Error recording sample #{i}: {e}")
            choice = input("Do you want to retry this sample? (y/n, default: y): ").strip().lower()
            if choice != "n":
                # Retry sample
                try:
                    record_sample(i, targets_dir)
                    recorded_count += 1
                except Exception as retry_err:
                    print(f"❌ Failed to retry: {retry_err}")

    print(f"\n🎉 Successfully recorded {recorded_count} positive voice samples!")

    # 3. Create Config YAML for training
    config = {
        "target_phrase": wakeword,
        "model_name": wakeword_slug,
        "output_dir": output_models_dir,
        "feature_manifest": {
            "targets": {"t": "features/targets.npy"},
            "negatives": {"n": "features/negatives.npy"},
        },
        "model_architecture": {
            "model_type": "transformer"  # Use Transformer for high-end SOTA laptop performance
        },
    }

    config_path = os.path.join(project_dir, "config.yaml")
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    print("\n📝 Created Nanowakeword configuration file:")
    print(f"   -> Path: {config_path}")
    print("-" * 75)
    print("💡 NEXT STEPS: CHOOSE YOUR TRAINING METHOD")
    print("-" * 75)
    print("You can train your model either completely locally or in the cloud using Google Colab.")
    print("\n---------------------------------------------------------------------------")
    print("🔥 METHOD A: Local Training (Directly on your MacBook / Laptop)")
    print("---------------------------------------------------------------------------")
    print("This is the most straightforward option and keeps all voice data offline.")
    print("\n1. Install Nanowakeword with training dependencies:")
    print('   pip install "nanowakeword[train] @ git+https://github.com/arcosoph/nanowakeword.git"')
    print("\n2. Execute the training command with Auto-Config:")
    print(f"   nanowakeword-train -c {config_path} --auto-config -G -t -T")
    print("\nThis single command will:")
    print(
        "   * Auto-synthesize LOOK-ALIKE speech to prevent false triggers (Adversarial generation)"
    )
    print("   * Generate negative datasets automatically")
    print(
        "   * Train a robust, state-of-the-art Transformer model tailored to your voice and room acoustics"
    )
    print("   * Export a lightweight `.onnx` model inside the output directory!")
    print("\n3. Copy the output `.onnx` file to your models folder:")
    print(f"   cp {output_models_dir}/{wakeword_slug}.onnx {os.path.join(BASE_DIR, 'models/')}")

    print("\n---------------------------------------------------------------------------")
    print("🌤️  METHOD B: Cloud Training (Google Colab - Highly Recommended for Free GPUs)")
    print("---------------------------------------------------------------------------")
    print("Google Colab provides high-speed, free GPU acceleration which can cut training time")
    print("from 1 hour down to less than 15 minutes!")
    print("\n1. Zip up your recorded raw target samples:")
    print(f"   cd {project_dir} && zip -r targets.zip data/")
    print("\n2. Open your web browser and load the training notebook:")
    print("   * Upload 'src/voice/wakeword_model_training.ipynb' directly to Google Colab")
    print("   * Or open the official Nanowakeword Colab Notebook")
    print("\n3. Upload your 'targets.zip' file to Colab's file browser and run:")
    print("   !unzip targets.zip -d ./")
    print("\n4. Combine your real voice with synthetic data (Best-Practice Hybrid Model!):")
    print("   * Setting 'target_word' in the notebook will generate synthetic positive samples.")
    print("   * The notebook will automatically combine these synthetic voice clones with the")
    print("     real targets you recorded on your MacBook's microphone.")
    print("   * This dual-source approach yields the absolute highest accuracy: synthetic clips")
    print("     give broad phonetic coverage, while your recordings calibrate the model perfectly")
    print("     to your physical room acoustics and laptop microphone arrays!")
    print("\n5. Run the training cells, and once complete, download your compiled '.onnx' model")
    print("   and place it inside your local models directory:")
    print(f"   mv ~/Downloads/{wakeword_slug}.onnx {os.path.join(BASE_DIR, 'models/')}")
    print("=" * 75)


if __name__ == "__main__":
    main()
