import re

filepath = "/Users/ryan/.gemini/tmp/etherfields-ai/tool-outputs/session-a4446215-1566-4806-bcb6-c62aa1596929/run_shell_command__xkj9bhng.txt"

with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
    html = f.read()

print(f"HTML length: {len(html)}")

# Look for share data pattern or words like "Dreamer" or "Mask"
keywords = ["Dreamer", "Mask", "combat", "intent", "turn", "slumber", "board game"]
for kw in keywords:
    matches = list(re.finditer(kw, html, re.IGNORECASE))
    print(f"Keyword '{kw}': {len(matches)} matches")

# Print out any large JS data blocks that might contain the conversation
# Usually Gemini shares serialize conversation inside a JS array block of window.WIZ_global_data
# or AF_initDataChunkQueue
for match in re.finditer(r"AF_initDataChunkQueue\.push\((.*?)\);", html, re.DOTALL):
    chunk = match.group(1)
    if "ds:" in chunk:
        print(f"\n--- Found AF_initDataChunkQueue chunk of len {len(chunk)} ---")
        # print first 500 characters
        print(chunk[:500] + "...")
