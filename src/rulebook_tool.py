# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "pypdf",
# ]
# ///

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

from pypdf import PdfReader

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_env_vars():
    env_vars = {}
    local_path = os.environ.get("ETHERFIELDS_LOCAL_PATH")
    paths_to_try = []
    if local_path:
        paths_to_try.append(os.path.join(os.path.abspath(os.path.expanduser(os.path.expandvars(local_path))), ".env"))
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

# Resolve custom directory from env if available (falls back to workspace root)
_env = load_env_vars()
CUSTOM_DIR_STR = _env.get("ETHERFIELDS_LOCAL_PATH", BASE_DIR)
CUSTOM_DIR = os.path.abspath(os.path.expanduser(os.path.expandvars(CUSTOM_DIR_STR)))

PDF_PATH = os.path.join(CUSTOM_DIR, "Rulebook_20.pdf")
if not os.path.exists(PDF_PATH):
    PDF_PATH = os.path.join(BASE_DIR, "Rulebook_20.pdf")

PAGES_DIR = os.path.join(CUSTOM_DIR, "rulebook_pages")
if not os.path.exists(PAGES_DIR) or not os.listdir(PAGES_DIR):
    PAGES_DIR = os.path.join(BASE_DIR, "rulebook_pages")

INDEX_PATH = os.path.join(CUSTOM_DIR, "index.json")
if not os.path.exists(INDEX_PATH):
    INDEX_PATH = os.path.join(BASE_DIR, "index.json")

def get_pdf_metadata():
    if not os.path.exists(PDF_PATH):
        return None
    mtime = os.path.getmtime(PDF_PATH)
    mtime_str = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

    sha256_hash = hashlib.sha256()
    with open(PDF_PATH, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return mtime_str, sha256_hash.hexdigest()

def regenerate_cache_and_index():
    print("[Rulebook Tool] Regenerating page cache and building index...", file=sys.stderr)

    # 1. Extract Pages
    os.makedirs(PAGES_DIR, exist_ok=True)
    reader = PdfReader(PDF_PATH)
    total_pages = len(reader.pages)

    for i, page in enumerate(reader.pages):
        page_num = i + 1
        text = page.extract_text() or ""
        output_file = os.path.join(PAGES_DIR, f"page_{page_num:02d}.txt")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(text.strip())

    # 2. Get Metadata
    mtime_str, sha256_hex = get_pdf_metadata()
    metadata = {
        "source_file": "Rulebook_20.pdf",
        "last_modified": mtime_str,
        "sha256": sha256_hex,
        "total_pages": total_pages
    }

    # 3. Parse Table of Contents
    chapters = {}
    toc_file = os.path.join(PAGES_DIR, "page_02.txt")
    if os.path.exists(toc_file):
        import re
        with open(toc_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        in_toc = False
        current_page = None
        for line in lines:
            line_clean = line.strip()
            if "TABLE OF CONTENTS" in line_clean:
                in_toc = True
                continue
            if in_toc:
                if "CREDITS" in line_clean or "All life is only a" in line_clean:
                    break
                toc_match = re.match(r"^(\d+)?\s*(.+)$", line_clean)
                if toc_match:
                    page_str, title = toc_match.groups()
                    title_clean = re.sub(r"\d+\s*", "", title).strip()
                    # Deduplicate duplicated words in PDF extraction artifacts
                    words = title_clean.split()
                    if len(words) > 1 and len(words) % 2 == 0:
                        half = len(words) // 2
                        if words[:half] == words[half:]:
                            title_clean = " ".join(words[:half])
                    if page_str:
                        current_page = int(page_str)
                    if title_clean and current_page:
                        if not title_clean.isdigit() and len(title_clean) > 2:
                            chapters[title_clean] = [current_page]

    # 4. Parse Alphabetical Index
    index_terms = {}
    index_file = os.path.join(PAGES_DIR, "page_19.txt")
    if os.path.exists(index_file):
        import re
        with open(index_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        in_index = False
        for line in lines:
            line_clean = line.strip()
            if line_clean == "INDEX":
                in_index = True
                continue
            if in_index:
                if "INDEX OF COMMON SYMBOLS" in line_clean:
                    break
                match = re.search(r"^(.*?)\s+((?:\d+[\s,]*)+)$", line_clean)
                if match:
                    term, pages_str = match.groups()
                    term = term.strip()
                    try:
                        pages = [int(p.strip()) for p in re.split(r"[\s,]+", pages_str) if p.strip()]
                        if term and pages:
                            index_terms[term] = pages
                    except ValueError:
                        continue

    # 5. Save index.json
    final_index = {
        "_metadata": metadata,
        "chapters": chapters,
        "index_terms": index_terms
    }
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(final_index, f, indent=2)
    print(f"[Rulebook Tool] Index successfully updated! Mapped {len(chapters)} chapters and {len(index_terms)} index terms.", file=sys.stderr)

def check_and_validate_index(force=False):
    if not os.path.exists(PDF_PATH):
        print(f"Error: PDF not found at {PDF_PATH}", file=sys.stderr)
        return False

    if force or not os.path.exists(INDEX_PATH) or not os.path.exists(PAGES_DIR) or len(os.listdir(PAGES_DIR)) == 0:
        regenerate_cache_and_index()
        return True

    # Read index metadata
    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            index_data = json.load(f)
        cached_meta = index_data.get("_metadata", {})
    except Exception:
        regenerate_cache_and_index()
        return True

    # Get current PDF metadata
    current_mtime, current_sha = get_pdf_metadata()

    if cached_meta.get("sha256") != current_sha:
        print("[Rulebook Tool] PDF hash mismatch! Rebuilding cache.", file=sys.stderr)
        regenerate_cache_and_index()
        return True

    return True

def search_rulebook(query):
    # Ensure valid index
    check_and_validate_index()

    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        index_data = json.load(f)

    query_lower = query.lower().strip()

    matched_chapters = []
    for chapter, pages in index_data.get("chapters", {}).items():
        if query_lower in chapter.lower():
            matched_chapters.append((chapter, pages))

    matched_terms = []
    for term, pages in index_data.get("index_terms", {}).items():
        if query_lower in term.lower():
            matched_terms.append((term, pages))

    print("\n" + "="*60)
    print(f"SEARCH RESULTS FOR: '{query}'")
    print("="*60)

    pages_to_display = set()

    if matched_chapters:
        print("\n--- MATCHING CHAPTERS/SECTIONS ---")
        for chap, pages in matched_chapters:
            print(f"  * {chap} -> Page(s) {', '.join(map(str, pages))}")
            pages_to_display.update(pages)

    if matched_terms:
        print("\n--- MATCHING INDEX TERMS ---")
        for term, pages in matched_terms:
            print(f"  * {term} -> Page(s) {', '.join(map(str, pages))}")
            pages_to_display.update(pages)

    if not matched_chapters and not matched_terms:
        print(f"\nNo exact index terms found containing '{query}'.")
        print("Falling back to full-text search across all page text files...")
        # Full text search fallback
        for filename in sorted(os.listdir(PAGES_DIR)):
            if filename.endswith(".txt"):
                page_num = int(filename.split("_")[1].split(".")[0])
                file_path = os.path.join(PAGES_DIR, filename)
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if query_lower in content.lower():
                    # Find count of matches
                    count = content.lower().count(query_lower)
                    print(f"  * Page {page_num:02d} (found {count} occurrences in text)")
                    pages_to_display.add(page_num)

    if pages_to_display:
        print("\n" + "="*60)
        print("RETRIEVED PAGE CONTENTS")
        print("="*60)
        for page_num in sorted(pages_to_display):
            page_file = os.path.join(PAGES_DIR, f"page_{page_num:02d}.txt")
            if os.path.exists(page_file):
                print(f"\n--- PAGE {page_num:02d} ---")
                with open(page_file, "r", encoding="utf-8") as f:
                    print(f.read())
            else:
                print(f"\n[Error: Page {page_num:02d} cache file missing]", file=sys.stderr)
    else:
        print("\nNo results found anywhere in the rulebook.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Etherfields Rulebook Surgical Retrieval and Index Tool")
    parser.add_argument("--validate", action="store_true", help="Validate index and rebuild if necessary")
    parser.add_argument("--search", type=str, help="Search for a topic or term in the index and display contents")
    parser.add_argument("--force", action="store_true", help="Force rebuild cache")

    args = parser.parse_args()

    if args.force:
        check_and_validate_index(force=True)
    elif args.validate:
        check_and_validate_index()
    elif args.search:
        search_rulebook(args.search)
    else:
        # Default behavior: run validation
        check_and_validate_index()
        print("[Rulebook Tool] Cache and index are up-to-date and valid!")
