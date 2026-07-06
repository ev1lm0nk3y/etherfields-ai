#!/usr/bin/env python3
"""
run_adversarial_review.py - Multi-Agent Adversarial Code Review Pipeline for GitHub Actions.
Executes service-specific and specialist reviewers, runs developer validation challenges,
synthesizes findings via the Review Orchestrator, and posts inline PR review comments and labels.
"""

import os
import sys
import json
import urllib.request
import urllib.error

# Load environment variables
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
REPO = os.environ.get("GITHUB_REPOSITORY")
PR_NUMBER = os.environ.get("GITHUB_PR_NUMBER")
COMMIT_SHA = os.environ.get("GITHUB_SHA")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# Setup base directory paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AGENTS_DIR = os.path.join(BASE_DIR, ".github", "agents")


def load_agent(agent_name):
    """Loads an agent's markdown file and extracts its system instruction body."""
    path = os.path.join(AGENTS_DIR, f"{agent_name}.md")
    if not os.path.exists(path):
        print(f"Warning: Agent file not found at {path}", file=sys.stderr)
        return ""
    
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Parse YAML frontmatter
    parts = content.split("---")
    if len(parts) >= 3:
        body = "---".join(parts[2:])
    else:
        body = content
        
    return body.strip()


def call_gemini(system_instruction, user_prompt, response_json=False):
    """Calls the Gemini API using native urllib with zero external dependencies."""
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    headers = {
        "Content-Type": "application/json"
    }
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": user_prompt}
                ]
            }
        ]
    }
    
    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [
                {"text": system_instruction}
            ]
        }
        
    if response_json:
        payload["generationConfig"] = {
            "responseMimeType": "application/json"
        }
        
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            candidates = res_data.get("candidates", [])
            if candidates:
                text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                return text
            return ""
    except urllib.error.HTTPError as e:
        print(f"Gemini API HTTP Error {e.code}: {e.reason}", file=sys.stderr)
        try:
            err_body = e.read().decode("utf-8")
            print(f"Error body: {err_body}", file=sys.stderr)
        except Exception:
            pass
        raise e
    except Exception as e:
        print(f"Error calling Gemini: {e}", file=sys.stderr)
        raise e


def clean_and_parse_json(text):
    """Cleans markdown formatting and parses JSON response from Gemini robustly."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"JSON Parse Error: {e}\nRaw Response was:\n{text}", file=sys.stderr)
        # Attempt minimal self-healing or return empty dict
        return {"findings": [], "validations": [], "verdict": "APPROVE", "summary": "Failed to parse reviewer JSON."}


def call_github_api(endpoint, method="GET", payload=None, accept="application/vnd.github.v3+json"):
    """Performs an authenticated GitHub API request using native urllib."""
    if not GITHUB_TOKEN:
        print("Error: GITHUB_TOKEN environment variable is not set.", file=sys.stderr)
        sys.exit(1)
        
    url = f"https://api.github.com{endpoint}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": accept,
        "User-Agent": "Etherfields-Adversarial-Review"
    }
    
    data = json.dumps(payload).encode("utf-8") if payload else None
    if payload:
        headers["Content-Type"] = "application/json"
        
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 204:  # No Content
                return None
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404 and method == "DELETE":
            # Gracefully handle 404 when trying to delete non-existent labels
            return None
        print(f"GitHub API HTTP Error {e.code} on {method} {endpoint}: {e.reason}", file=sys.stderr)
        try:
            print(f"Response body: {e.read().decode('utf-8')}", file=sys.stderr)
        except Exception:
            pass
        raise e
    except Exception as e:
        print(f"Error calling GitHub API: {e}", file=sys.stderr)
        raise e


def get_pr_files():
    """Fetches list of changed files and their patches in the current Pull Request."""
    print(f"Fetching modified files for PR #{PR_NUMBER}...")
    endpoint = f"/repos/{REPO}/pulls/{PR_NUMBER}/files?per_page=100"
    return call_github_api(endpoint)


def get_file_content(filepath):
    """Safely reads the contents of a file from the workspace if it exists."""
    full_path = os.path.join(BASE_DIR, filepath)
    if os.path.exists(full_path) and os.path.isfile(full_path):
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"Error reading {filepath}: {e}", file=sys.stderr)
    return ""


def check_line_validity(filepath, line_num):
    """Defensively checks if a line number is valid for the given file."""
    if line_num <= 0:
        return False
    full_path = os.path.join(BASE_DIR, filepath)
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        return False
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return line_num <= len(lines)
    except Exception:
        return False


def main():
    if not all([GITHUB_TOKEN, GEMINI_API_KEY, REPO, PR_NUMBER]):
        print("Error: Missing mandatory environment variables: GITHUB_TOKEN, GEMINI_API_KEY, GITHUB_REPOSITORY, GITHUB_PR_NUMBER", file=sys.stderr)
        sys.exit(1)

    print("=" * 80)
    print(f"Starting Adversarial Code Review for Pull Request #{PR_NUMBER}")
    print(f"Repository: {REPO} | Model: {GEMINI_MODEL}")
    print("=" * 80)

    # 1. Fetch changed files
    files = get_pr_files()
    if not files:
        print("No files modified in this pull request. Exiting successfully.")
        sys.exit(0)

    # 2. Analyze which service domains are touched and compile diff data
    rulebook_touched = False
    scripts_touched = False
    voice_touched = False
    
    all_files_context = []
    
    for f in files:
        filepath = f["filename"]
        patch = f.get("patch", "")
        status = f["status"]
        
        # Classify domains
        if "rulebook" in filepath or filepath == "src/rulebook_tool.py":
            rulebook_touched = True
        if "secret_scripts" in filepath or filepath == "src/secret_scripts_tool.py" or filepath == "secret_scripts_cache.json":
            scripts_touched = True
        if "voice/" in filepath or "voice" in filepath:
            voice_touched = True
            
        file_content = get_file_content(filepath) if status != "removed" else ""
        
        all_files_context.append({
            "filepath": filepath,
            "status": status,
            "patch": patch,
            "content": file_content
        })

    print(f"Domain touch status: Rulebook={rulebook_touched}, Scripts={scripts_touched}, Voice={voice_touched}")

    # Load DNA preamble and specialists
    preamble = load_agent("adversarial-preamble")
    
    # 3. Execution Phase: Run Specialist and Service Reviewers + Dev Validators
    all_service_findings = []
    all_specialist_findings = []
    
    # Prepare full diff package context for specialists
    full_diff_context_str = ""
    for fc in all_files_context:
        full_diff_context_str += f"\nFile: {fc['filepath']} ({fc['status'].upper()})\n"
        if fc['content']:
            full_diff_context_str += f"--- START OF FILE CONTENT ---\n{fc['content']}\n--- END OF FILE CONTENT ---\n"
        if fc['patch']:
            full_diff_context_str += f"--- START OF DIFF PATCH ---\n{fc['patch']}\n--- END OF DIFF PATCH ---\n"
        full_diff_context_str += "=" * 40 + "\n"

    # A. Run Specialists (Security, Architecture, Observability)
    specialists = [
        {"name": "review-security", "title": "Security Specialist Reviewer"},
        {"name": "review-architecture", "title": "Architecture Specialist Reviewer"},
        {"name": "review-observability", "title": "Observability Specialist Reviewer"}
    ]
    
    for spec in specialists:
        print(f"Running cross-cutting specialist: {spec['title']}...")
        sys_inst = preamble + "\n" + load_agent(spec["name"])
        
        prompt = f"""You are reviewing a Pull Request. Below is the file contents and the git diff patches of all modified files.
        
{full_diff_context_str}

Analyze the changes according to your system instructions, checklists, and red flags.
You MUST return your findings in the following JSON format:
{{
  "findings": [
    {{
      "file": "relative/path/to/file.py",
      "line": 42,
      "severity": "BLOCKER", // Can be: BLOCKER, MAJOR, MINOR, NEEDS_REVIEW
      "description": "Describe the specific failure scenario and why it is a problem.",
      "remediation": "Clear, executable remediation guidelines."
    }}
  ]
}}

Rules:
1. The 'file' field MUST match the file path of the reviewed file exactly.
2. The 'line' field MUST be a valid line number in the modified file where the issue occurs.
3. If there are no findings, return an empty array for "findings".
4. Be thorough, strict, and do not report false positives.
"""
        response_text = call_gemini(sys_inst, prompt, response_json=True)
        res_json = clean_and_parse_json(response_text)
        
        findings = res_json.get("findings", [])
        print(f"-> Found {len(findings)} issues from {spec['title']}.")
        for f in findings:
            f["reviewer"] = spec["title"]
            f["validated"] = True  # Specialist findings are immutable/auto-validated
            all_specialist_findings.append(f)

    # B. Run Service Reviewers & Dev Validators (Rulebook, Scripts, Voice)
    service_pairs = []
    if rulebook_touched:
        service_pairs.append({
            "reviewer": "review-rulebook-retriever",
            "validator": "dev-rulebook-retriever",
            "title": "Rulebook Retrieval Engine"
        })
    if scripts_touched:
        service_pairs.append({
            "reviewer": "review-secret-scripts",
            "validator": "dev-secret-scripts",
            "title": "Secret Scripts Lookup"
        })
    if voice_touched:
        service_pairs.append({
            "reviewer": "review-voice-assistant",
            "validator": "dev-voice-assistant",
            "title": "Voice Activation Module"
        })

    for pair in service_pairs:
        print(f"Running service reviewer: {pair['reviewer']}...")
        sys_inst = preamble + "\n" + load_agent(pair["reviewer"])
        
        # Filter files for this specific service domain
        domain_files_str = ""
        for fc in all_files_context:
            is_domain = False
            if pair["reviewer"] == "review-rulebook-retriever" and ("rulebook" in fc["filepath"] or fc["filepath"] == "src/rulebook_tool.py"):
                is_domain = True
            elif pair["reviewer"] == "review-secret-scripts" and ("secret_scripts" in fc["filepath"] or fc["filepath"] == "src/secret_scripts_tool.py" or fc["filepath"] == "secret_scripts_cache.json"):
                is_domain = True
            elif pair["reviewer"] == "review-voice-assistant" and ("voice/" in fc["filepath"] or "voice" in fc["filepath"]):
                is_domain = True
                
            if is_domain:
                domain_files_str += f"\nFile: {fc['filepath']} ({fc['status'].upper()})\n"
                if fc['content']:
                    domain_files_str += f"--- START OF FILE CONTENT ---\n{fc['content']}\n--- END OF FILE CONTENT ---\n"
                if fc['patch']:
                    domain_files_str += f"--- START OF DIFF PATCH ---\n{fc['patch']}\n--- END OF DIFF PATCH ---\n"
                domain_files_str += "=" * 40 + "\n"

        if not domain_files_str:
            print(f"Skipping {pair['title']} reviewer due to no matching file data.")
            continue

        reviewer_prompt = f"""You are reviewing a Pull Request. Below is the file contents and the git diff patch of the modified files belonging to your service domain.

{domain_files_str}

Analyze the changes according to your system instructions, domain context, red flags, and verification tasks.
You MUST return your findings in the following JSON format:
{{
  "findings": [
    {{
      "file": "relative/path/to/file.py",
      "line": 42,
      "severity": "BLOCKER", // Can be: BLOCKER, MAJOR, MINOR, NEEDS_REVIEW
      "description": "Describe the specific failure scenario and why it is a problem.",
      "remediation": "Clear, executable remediation guidelines."
    }}
  ],
  "chokepoint_answer": "Answer the chokepoint question: Is there a single file or function where this entire change could be made?"
}}

Rules:
1. The 'file' field MUST match the file path of the reviewed file exactly.
2. The 'line' field MUST be a valid line number in the modified file.
3. If there are no findings, return an empty array for "findings".
"""
        response_text = call_gemini(sys_inst, reviewer_prompt, response_json=True)
        res_json = clean_and_parse_json(response_text)
        
        findings = res_json.get("findings", [])
        chokepoint = res_json.get("chokepoint_answer", "NO SIMPLER ALTERNATIVE FOUND")
        print(f"-> Found {len(findings)} issues from {pair['reviewer']}. Chokepoint verdict: {chokepoint}")
        
        if findings:
            # Run Dev Validator to challenge findings
            print(f"Running matching dev validator: {pair['validator']}...")
            dev_sys_inst = load_agent(pair["validator"])
            
            validator_prompt = f"""You are the developer agent validating findings from the reviewer agent. Below are the findings reported by the reviewer, along with the actual file contents and git diff patch.

Reviewer findings:
{json.dumps(findings, indent=2)}

Actual File context:
{domain_files_str}

For each finding, you must issue a verdict: VALID, INVALID, or AMBIGUOUS, and cite specific lines or codebase patterns.
You MUST return your response in the following JSON format:
{{
  "validations": [
    {{
      "file": "relative/path/to/file.py",
      "line": 42,
      "verdict": "VALID", // Can be: VALID, INVALID, AMBIGUOUS
      "reasoning": "Explain your choice using codebase context as evidence.",
      "remediation_adjustment": "Any adjustments to the proposed remediation if needed."
    }}
  ]
}}
"""
            val_response_text = call_gemini(dev_sys_inst, validator_prompt, response_json=True)
            val_json = clean_and_parse_json(val_response_text)
            validations_map = { (v["file"], v["line"]): v for v in val_json.get("validations", []) }
            
            for f in findings:
                f["reviewer"] = pair["title"]
                f["chokepoint_answer"] = chokepoint
                
                # Match validation verdict
                val = validations_map.get((f["file"], f["line"]))
                if val:
                    f["validated"] = val["verdict"] in ["VALID", "AMBIGUOUS"]
                    f["verdict"] = val["verdict"]
                    f["reasoning"] = val["reasoning"]
                    if val.get("remediation_adjustment"):
                        f["remediation"] += f"\n\n**Dev Validation Adjustment:** {val['remediation_adjustment']}"
                else:
                    # Default if validator failed to report
                    f["validated"] = True
                    f["verdict"] = "VALID (uncontested)"
                    f["reasoning"] = "No matching validator counter-argument was provided."
                
                all_service_findings.append(f)

    # 4. Synthesize everything via the Orchestrator
    print("Running Lead Review Orchestrator synthesis...")
    orchestrator_sys_inst = load_agent("review-orchestrator")
    
    service_reviews_summary = json.dumps(all_service_findings, indent=2)
    specialist_reviews_summary = json.dumps(all_specialist_findings, indent=2)
    
    orchestrator_prompt = f"""You are the Lead Review Orchestrator. You synthesize findings from active service reviewers (and their validator verdicts) and cross-cutting specialists to produce a final verdict and a lead brief.

Below are the findings and validations collected:

--- SERVICE REVIEWS & VALIDATION ---
{service_reviews_summary}

--- SPECIALIST REVIEWS ---
{specialist_reviews_summary}

Synthesize these results.
According to your system instructions, the final verdict matrix is:
- APPROVED: No BLOCKER or MAJOR issues identified by active specialists or validated reviewers.
- REQUEST_CHANGES: Any validated MAJOR findings from reviewer/dev pairs or ANY findings from specialists (MAJOR or MINOR).
- BLOCK: Any validated BLOCKER findings from reviewer/dev pairs or security violations.

You MUST return your response in the following JSON format:
{{
  "verdict": "APPROVE", // Can be: APPROVE, REQUEST_CHANGES, BLOCK
  "summary": "The Lead Brief summarizing approved modifications, outstanding issues, and clear next steps.",
  "solution_fit": "Analysis of how well the changes fulfill the user requirements.",
  "implementation_correctness": "Analysis of implementation correctness, edge cases, and code quality."
}}
"""
    orch_response_text = call_gemini(orchestrator_sys_inst, orchestrator_prompt, response_json=True)
    orch_json = clean_and_parse_json(orch_response_text)
    
    final_verdict = orch_json.get("verdict", "APPROVE")
    lead_summary = orch_json.get("summary", "No summary provided.")
    solution_fit = orch_json.get("solution_fit", "No assessment provided.")
    impl_correctness = orch_json.get("implementation_correctness", "No assessment provided.")
    
    print(f"\nFinal Orchestrator Verdict: {final_verdict}")
    print(f"Summary: {lead_summary[:200]}...")

    # 5. Compile and publish review comments to GitHub
    github_comments = []
    hallucinated_comments = []
    
    # Process specialist findings
    for f in all_specialist_findings:
        filepath = f["file"]
        line = int(f["line"])
        severity = f["severity"]
        reviewer = f["reviewer"]
        
        body = f"""### 🛡️ Adversarial Code Review - Specialist Finding
**Reviewer:** `{reviewer}`
**Severity:** `{severity}`

**Failure Scenario:**
{f['description']}

**Remediation:**
{f['remediation']}
"""
        
        if check_line_validity(filepath, line):
            github_comments.append({
                "path": filepath,
                "line": line,
                "body": body,
                "side": "RIGHT"
            })
        else:
            hallucinated_comments.append(f"**[{reviewer} - {severity}]** `{filepath}:{line}`: {f['description']} *(remediation: {f['remediation']})*")

    # Process service findings (only if validated as VALID or AMBIGUOUS)
    for f in all_service_findings:
        if not f["validated"]:
            print(f"Skipping invalidated finding: {f['file']}:{f['line']} ({f['reviewer']})")
            continue
            
        filepath = f["file"]
        line = int(f["line"])
        severity = f["severity"]
        reviewer = f["reviewer"]
        verdict = f["verdict"]
        reasoning = f["reasoning"]
        chokepoint = f.get("chokepoint_answer", "NO SIMPLER ALTERNATIVE FOUND")
        
        body = f"""### 🛡️ Adversarial Code Review - Service Finding
**Reviewer:** `{reviewer}`
**Severity:** `{severity}`
**Dev Validation Verdict:** `{verdict}`

**Validation Reasoning:**
> {reasoning}

**Failure Scenario:**
{f['description']}

**Remediation:**
{f['remediation']}

**Chokepoint Analysis:**
`{chokepoint}`
"""
        
        if check_line_validity(filepath, line):
            github_comments.append({
                "path": filepath,
                "line": line,
                "body": body,
                "side": "RIGHT"
            })
        else:
            hallucinated_comments.append(f"**[{reviewer} - {severity}]** `{filepath}:{line}`: {f['description']} *(remediation: {f['remediation']})*")

    # Build the main review body
    main_body = f"""# 🛡️ Multi-Agent Adversarial Code Review Report

**Lead Orchestrator Verdict:** `{final_verdict}`

## 📝 Lead Brief
{lead_summary}

## 📊 Dual-Verdict Assessments
* **Solution Fit:**
  {solution_fit}
* **Implementation Correctness:**
  {impl_correctness}
"""

    if hallucinated_comments:
        main_body += "\n\n## ⚠️ Off-Line or General Findings\n"
        main_body += "The following findings could not be mapped to exact active line ranges in the pull request:\n\n"
        for hc in hallucinated_comments:
            main_body += f"- {hc}\n"

    print(f"Posting PR review with {len(github_comments)} inline comments...")
    
    # Map final verdict to GitHub Review event
    # APPROVE, REQUEST_CHANGES, or COMMENT
    if final_verdict == "APPROVE":
        gh_event = "APPROVE"
    elif final_verdict == "BLOCK" or final_verdict == "REQUEST_CHANGES":
        gh_event = "REQUEST_CHANGES"
    else:
        gh_event = "COMMENT"
        
    review_payload = {
        "commit_id": COMMIT_SHA,
        "body": main_body,
        "event": gh_event
    }
    
    if github_comments:
        review_payload["comments"] = github_comments

    # Post Review via GitHub API
    reviews_endpoint = f"/repos/{REPO}/pulls/{PR_NUMBER}/reviews"
    call_github_api(reviews_endpoint, method="POST", payload=review_payload)
    print("PR review posted successfully!")

    # 6. Apply review labels to the PR (Issue labels endpoint)
    labels_endpoint = f"/repos/{REPO}/issues/{PR_NUMBER}/labels"
    
    if final_verdict == "APPROVE":
        add_label = "review:ai-pass"
        remove_label = "review:ai-block"
    else:
        add_label = "review:ai-block"
        remove_label = "review:ai-pass"
        
    print(f"Applying label: {add_label}...")
    call_github_api(labels_endpoint, method="POST", payload={"labels": [add_label]})
    
    print(f"Removing label (if exists): {remove_label}...")
    # Clean label name for deletion path encoding
    call_github_api(f"{labels_endpoint}/{remove_label}", method="DELETE")

    print("=" * 80)
    print("Adversarial Code Review Pipeline Completed Successfully!")
    print("=" * 80)


if __name__ == "__main__":
    main()
