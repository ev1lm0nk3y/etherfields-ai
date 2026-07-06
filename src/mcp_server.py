# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "mcp[cli]>=1.0.0",
#     "pypdf>=5.0.0",
#     "python-dotenv>=1.0.0",
# ]
# ///

import contextlib
import io
import json
import os
import sys

# Ensure we can import sibling files and subdirectories
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(CURRENT_DIR)
sys.path.append(os.path.join(CURRENT_DIR, "voice"))

from mcp.server.fastmcp import FastMCP  # noqa: E402

import rulebook_tool  # noqa: E402
import secret_scripts_tool  # noqa: E402

# Initialize FastMCP Server
mcp = FastMCP("Etherfields AI Assistant")

# ==============================================================================
# TOOLS
# ==============================================================================


@mcp.tool()
def search_rulebook(query: str) -> str:
    """Search the official Etherfields 2.0 PDF rulebook page cache and TOC index.

    Returns page matches and their full text.

    Args:
        query: The term or gameplay concept to search for (e.g. 'Slumber', 'Awakening').
    """
    f = io.StringIO()
    with contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
        rulebook_tool.search_rulebook(query)
    return f.getvalue()


@mcp.tool()
def get_secret_script(script_num: str) -> str:
    """Look up a specific core campaign secret script by its number/id.

    Returns its narrative story text, game actions, and branching links.

    Args:
        script_num: The script number or ID to look up (e.g., '100' or 's. 100').
    """
    script_clean = script_num.lower().replace("s.", "").strip()

    # Ensure structured scripts cache is populated
    cache_path = secret_scripts_tool.STRUCTURED_CACHE_PATH
    if not os.path.exists(cache_path):
        f = io.StringIO()
        with contextlib.redirect_stderr(f):
            secret_scripts_tool.build_cache()

    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                scripts = json.load(f)
            script_data = scripts.get(script_clean)
            if script_data:
                tone = script_data.get("tone", "neutral")
                narrative = script_data.get("narrative", "")
                instructions = script_data.get("instructions", "")
                branches = script_data.get("branches", [])

                lines = []
                lines.append(f"### Secret Script {script_clean} (Tone: {tone.upper()})")
                if narrative:
                    lines.append(f"\n**Story Narrative:**\n> {narrative}")
                if instructions:
                    lines.append(f"\n**Actions & Instructions:**\n{instructions}")
                if branches:
                    lines.append("\n**Branching Choices:**")
                    for b in branches:
                        dest = b["link"].split("/")[-1]
                        lines.append(f"- {b['label']} -> Go to script {dest}")
                return "\n".join(lines)
        except Exception as e:
            return f"Error reading structured scripts cache: {e}"

    # Fallback to stdout capture if JSON not read/parsed successfully
    f = io.StringIO()
    with contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
        secret_scripts_tool.lookup_script(script_clean)
    return f.getvalue()


@mcp.tool()
def validate_rulebook_cache() -> str:
    """Validate that the rulebook page split cache and index match the latest PDF.

    Regenerates page cache if necessary.
    """
    f = io.StringIO()
    with contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
        rulebook_tool.check_and_validate_index()
    output = f.getvalue()
    if not output.strip():
        output = "Rulebook cache and index successfully validated/initialized."
    return output


@mcp.tool()
def narrate_text(text: str) -> str:
    """Narrate gameplay text or rules out loud using the local voice/TTS assistant.

    Only functional if ENABLE_VOICE is configured.

    Args:
        text: The story text, instruction, or rule to narrate.
    """
    try:
        import time
        import uuid

        from voice import voice_assistant

        _env = voice_assistant.load_env_vars()
        if _env.get("ENABLE_VOICE", "False").lower() in ["true", "1"]:
            # Check if queue mode is active (for multi-container audio IPC)
            via_queue = os.environ.get("NARRATE_VIA_QUEUE", "False").lower() in ["true", "1"]
            if via_queue:
                queue_dir = os.path.join(rulebook_tool.CUSTOM_DIR, "narration_queue")
                os.makedirs(queue_dir, exist_ok=True)
                req_id = str(uuid.uuid4())
                req_file = os.path.join(queue_dir, f"req_{req_id}.json")
                with open(req_file, "w", encoding="utf-8") as f:
                    json.dump({"text": text, "timestamp": time.time()}, f)
                return f"Narration request successfully queued: '{text}'"
            else:
                voice_assistant.speak_text(text)
                return f"Narration completed successfully: '{text}'"
        else:
            return "Narration skipped: ENABLE_VOICE is not set to True in '.env' configuration."
    except Exception as e:
        return f"Could not perform narration: {e}"


@mcp.tool()
def update_campaign_state(content: str) -> str:
    """Update the campaign state, active characters, or player details inside RULEMASTER.md.

    Args:
        content: The full updated Markdown content for RULEMASTER.md.
    """
    path = os.path.join(rulebook_tool.BASE_DIR, "RULEMASTER.md")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return "RULEMASTER.md successfully updated."
    except Exception as e:
        return f"Error updating campaign state: {e}"


@mcp.tool()
def save_discussed_topic(topic_name: str, content: str) -> str:
    """Save/update discussed gameplay topic and register it in TOPICS.md.

    Writes the topic's details to a new Markdown file in the custom topics directory
    and appends a summary registration link inside TOPICS.md if not already registered.

    Args:
        topic_name: The name/title of the rule or mechanic discussed (e.g., 'Stunned State').
        content: The detailed explanation of the topic to write to the topic Markdown file.
    """
    import re

    # 1. Standardize filename
    safe_name = re.sub(r"[^\w\s-]", "", topic_name).strip().lower()
    safe_name = re.sub(r"[-\s]+", "_", safe_name)
    filename = f"{safe_name}.md"

    # 2. Paths
    topics_dir = os.path.join(rulebook_tool.CUSTOM_DIR, "topics")
    os.makedirs(topics_dir, exist_ok=True)
    topic_file_path = os.path.join(topics_dir, filename)

    # Path to TOPICS.md (check custom dir first, then base dir)
    topics_md_path = os.path.join(rulebook_tool.CUSTOM_DIR, "TOPICS.md")
    if not os.path.exists(topics_md_path):
        topics_md_path = os.path.join(rulebook_tool.BASE_DIR, "TOPICS.md")

    try:
        # 3. Write topic file
        with open(topic_file_path, "w", encoding="utf-8") as f:
            f.write(content)

        # 4. Extract a one-sentence summary from the content for the TOPICS.md registry
        summary = "Clarified gameplay rules and mechanics."
        first_line = content.strip().split("\n")[0] if content.strip() else ""
        if first_line.startswith("#"):
            lines = [
                line.strip()
                for line in content.strip().split("\n")[1:]
                if line.strip()
            ]
            if lines:
                summary = lines[0]
        elif first_line:
            summary = first_line

        if len(summary) > 100:
            summary = summary[:97] + "..."

        # 5. Register in TOPICS.md
        topic_entry = f"- [{topic_name}](topics/{filename}): {summary}"

        existing_content = ""
        if os.path.exists(topics_md_path):
            with open(topics_md_path, "r", encoding="utf-8") as f:
                existing_content = f.read()

        if f"topics/{filename}" in existing_content:
            status = f"Topic '{topic_name}' file updated, but already registered in TOPICS.md."
        else:
            separator = "\n" if existing_content and not existing_content.endswith("\n") else ""
            with open(topics_md_path, "a", encoding="utf-8") as f:
                f.write(f"{separator}{topic_entry}\n")
            status = f"Topic '{topic_name}' successfully created and registered in TOPICS.md."

        return f"Success: Written topic file to {topic_file_path}. {status}"
    except Exception as e:
        return f"Error saving discussed topic: {e}"


@mcp.tool()
def append_session_log(session_num: int, content: str) -> str:
    """Append session log to persistent logs registry in LOGS.md and the rotating log files.

    Args:
        session_num: The session number (e.g. 1, 2, 3, 5, etc.)
        content: The detailed session log content in Markdown format.
    """
    # 1. Determine which 4-session file to write to (Sessions 1-4, 5-8, etc.)
    start_session = ((session_num - 1) // 4) * 4 + 1
    end_session = start_session + 3
    filename = f"sessions_{start_session:02d}_{end_session:02d}.md"

    # 2. Paths
    logs_dir = os.path.join(rulebook_tool.CUSTOM_DIR, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_file_path = os.path.join(logs_dir, filename)

    # Path to LOGS.md
    logs_md_path = os.path.join(rulebook_tool.CUSTOM_DIR, "LOGS.md")
    if not os.path.exists(logs_md_path):
        logs_md_path = os.path.join(rulebook_tool.BASE_DIR, "LOGS.md")

    try:
        # 3. Write or append to the rotating session file
        is_new_file = not os.path.exists(log_file_path)
        with open(log_file_path, "a", encoding="utf-8") as f:
            if is_new_file:
                header = (
                    f"# Campaign Session Logs (Sessions "
                    f"{start_session:02d} to {end_session:02d})\n\n"
                )
                f.write(header)
            f.write(content)
            f.write("\n\n---\n\n")

        # 4. Update the LOGS.md registry if not already registered
        logs_entry = (
            f"- [Sessions {start_session}-{end_session}]"
            f"(logs/{filename}): Campaign session history."
        )

        existing_content = ""
        if os.path.exists(logs_md_path):
            with open(logs_md_path, "r", encoding="utf-8") as f:
                existing_content = f.read()

        if f"logs/{filename}" not in existing_content:
            separator = "\n" if existing_content and not existing_content.endswith("\n") else ""
            if not existing_content:
                existing_content = "# Campaign Session Registry\n\n"
            with open(logs_md_path, "w", encoding="utf-8") as f:
                f.write(existing_content + separator + logs_entry + "\n")

        msg = (
            f"Success: Appended Session {session_num} details to "
            f"{log_file_path} and registered in LOGS.md."
        )
        return msg
    except Exception as e:
        return f"Error appending session log: {e}"


# ==============================================================================
# RESOURCES
# ==============================================================================


@mcp.resource("campaign://state")
def get_campaign_state() -> str:
    """Returns the current campaign state and player details from RULEMASTER.md."""
    path = os.path.join(rulebook_tool.BASE_DIR, "RULEMASTER.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "RULEMASTER.md not found in workspace."


@mcp.resource("topics://index")
def get_topics_index() -> str:
    """Returns the central registry of discussed rules/mechanics from TOPICS.md."""
    path = os.path.join(rulebook_tool.CUSTOM_DIR, "TOPICS.md")
    if not os.path.exists(path):
        path = os.path.join(rulebook_tool.BASE_DIR, "TOPICS.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "TOPICS.md not found."


@mcp.resource("logs://index")
def get_logs_index() -> str:
    """Returns the campaign session log registry from LOGS.md."""
    path = os.path.join(rulebook_tool.CUSTOM_DIR, "LOGS.md")
    if not os.path.exists(path):
        path = os.path.join(rulebook_tool.BASE_DIR, "LOGS.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "LOGS.md not found."


# ==============================================================================
# PROMPTS
# ==============================================================================


@mcp.prompt()
def explain_rule(concept: str) -> str:
    """Create a prompt to explain an Etherfields rule concept to the team."""
    return (
        f"You are the Etherfields Rule Master. The players have asked about: '{concept}'. "
        "Please retrieve any relevant rulebook pages using the `search_rulebook` tool "
        "and provide a clear, concise explanation suitable for text-to-speech (2-3 sentences), "
        "focusing strictly on mechanical rules and without giving tactical or strategic advice."
    )


@mcp.prompt()
def resolve_script(script_num: str) -> str:
    """Create a prompt to guide players through a secret script resolution."""
    return (
        f"You are the Etherfields Rule Master. We need to resolve Secret Script {script_num}. "
        "Please use the `get_secret_script` tool to look it up. "
        "Guide us through any instructions sequentially. Remember the action-state-wait "
        "protocol: if the script instructs players to perform game actions, list them clearly, "
        "and stop and wait for confirmation before providing further text, options, "
        "or subsequent scripts. Avoid spoilers!"
    )


@mcp.prompt()
def rule_master_session() -> str:
    """Initialize a full Rule Master gameplay session with strict behavioral instructions."""
    return (
        "You are the Etherfields Rule Master—an expert in the Etherfields board game. "
        "Your mission is to help the players play correctly, smoothly, and strictly "
        "according to the rules, using the tools and resources available on your connected "
        "MCP server. You must strictly adhere to the following rules of conduct:\n\n"
        "1. NO GAMEPLAY OR STRATEGIC ADVICE:\n"
        "   - NEVER give advice on what players should do strategically or tactically.\n"
        "   - Clarify HOW mechanics work, but do not suggest moves, choices, or paths.\n\n"
        "2. SECRET SCRIPTS PROTOCOL:\n"
        "   - Only look up and display the IMMEDIATE script requested using `get_secret_script`.\n"
        "   - Do NOT pre-emptively look up or reveal branching links "
        "(e.g., [Resolve](/core/xx)).\n\n"
        "3. ACTION-STATE-WAIT PROTOCOL:\n"
        "   - If a secret script commands a physical board action (e.g., 'Suffer 1 damage', "
        "'Discard turn card'), state the actions in a clear bulleted list.\n"
        "   - STOP and wait for the players to confirm they have performed the physical board "
        "actions before providing any further instructions, narrative, or options.\n\n"
        "4. TTS VERBOSITY OPTIMIZATION:\n"
        "   - If a voice preamble is present, limit answers to 2-3 concise, fluid sentences "
        "suitable for TTS reading. Avoid bullet points, markdown tables, or parentheses.\n\n"
        "Always read the current campaign state from `campaign://state` on startup to tailor "
        "your rule application."
    )


if __name__ == "__main__":
    mcp.run()
