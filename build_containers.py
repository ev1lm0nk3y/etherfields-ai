#!/usr/bin/env python
"""Build program to compile both the MCP Server and Voice Subsystem Docker containers.

Natively integrates with Docker Buildx to utilize advanced cache mounts and speed up rebuilds.
"""

import subprocess
import sys
import shutil

def run_command(command, description):
    print(f"\n🚀 {description}...")
    print(f"Command: {' '.join(command)}")
    try:
        subprocess.run(command, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during: {description}")
        print(e)
        return False

def main():
    # 1. Verify Docker CLI is installed
    if not shutil.which("docker"):
        print("❌ Error: 'docker' command-line tool not found. Please install Docker first.", file=sys.stderr)
        sys.exit(1)
        
    print("🐳 Docker command-line tool detected.")
    
    # 2. Check for BuildKit / Buildx support
    buildx_check = subprocess.run(["docker", "buildx", "version"], capture_output=True, text=True)
    if buildx_check.returncode != 0:
        print("⚠️ Warning: Docker Buildx is not available. Building with standard docker engine.", file=sys.stderr)
        print("   (Advanced cache mounts will be skipped.)", file=sys.stderr)
        mcp_cmd = ["docker", "build", "-t", "etherfields-ai-mcp-server", "-f", "Dockerfile", "."]
        voice_cmd = ["docker", "build", "-t", "etherfields-ai-voice-subsystem", "-f", "Dockerfile.voice", "."]
    else:
        print("✨ Docker Buildx detected! Using advanced layer and mount caching.")
        # Enable BuildKit explicitly
        import os
        os.environ["DOCKER_BUILDKIT"] = "1"
        # Buildx build commands require '--load' to make them visible in local docker images list
        mcp_cmd = ["docker", "buildx", "build", "--load", "-t", "etherfields-ai-mcp-server", "-f", "Dockerfile", "."]
        voice_cmd = ["docker", "buildx", "build", "--load", "-t", "etherfields-ai-voice-subsystem", "-f", "Dockerfile.voice", "."]

    # 3. Build Core MCP Server Container
    if not run_command(mcp_cmd, "Building Core MCP Server Container (mcp-server)"):
        print("❌ Build failed for core mcp-server container.", file=sys.stderr)
        sys.exit(1)

    # 4. Build Voice Subsystem Container
    if not run_command(voice_cmd, "Building Voice Subsystem Container (voice-subsystem)"):
        print("❌ Build failed for voice-subsystem container.", file=sys.stderr)
        sys.exit(1)

    print("\n" + "="*60)
    print("🎉 BOTH CONTAINERS SUCCESSFULLY COMPILED!")
    print("="*60)
    print("  • Core Engine image : 'etherfields-ai-mcp-server'")
    print("  • Voice Subsystem   : 'etherfields-ai-voice-subsystem'")
    print("\nTo start both containers in the background using Docker Compose, run:")
    print("  docker compose up -d")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
