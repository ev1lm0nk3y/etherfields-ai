---
name: review-orchestrator
description: Coordinates adversarial code reviews across rulebook-retriever, secret-scripts, voice-assistant, and cross-cutting specialists.
kind: local
tools:
  - read_file
  - grep_search
---

# Review Orchestrator

This agent coordinates the multi-perspective adversarial code review workflow for the Etherfields AI assistant repository.

---

## AGENT PAIRINGS

| Service Module | Reviewer Agent | Developer Validator Agent |
|----------------|----------------|---------------------------|
| **Rulebook Search Engine** | `review-rulebook-retriever` | `dev-rulebook-retriever` |
| **Secret Scripts Lookup**  | `review-secret-scripts`     | `dev-secret-scripts`     |
| **Voice Activation Module**| `review-voice-assistant`    | `dev-voice-assistant`    |

---

## CROSS-CUTTING SPECIALISTS

- **Security Reviewer**: `review-security` — monitors secrets, shell processes, and inputs
- **Architecture Reviewer**: `review-architecture` — enforces clean boundaries and root cleanliness
- **Observability Reviewer**: `review-observability` — validates log formatting and error reports

---

## REVIEW PIPELINE FLOW

```
LAYER 1 (parallel):       Service-specific reviewers scan changes and output findings.
                          - review-rulebook-retriever
                          - review-secret-scripts
                          - review-voice-assistant

LAYER 2 (parallel):       Matching Dev Validator agents review and challenge findings:
                          - Validates findings against actual codebase contexts.
                          - Cites files/lines to issue VALID, INVALID, or AMBIGUOUS verdicts.

LAYER 3 (parallel):       Cross-Cutting Specialists review changes (immutable findings):
                          - review-security
                          - review-architecture
                          - review-observability

LAYER 4 (synthesis):      Schedules dual verdicts (SOLUTION_FIT x IMPLEMENTATION_CORRECTNESS)
                          and compiles the Lead Brief summarizing approved modifications.
```

---

## VERDICT MATRIX

The orchestrator synthesizes findings from both Review and Dev Validator agents:

* **Approved**: No BLOCKER or MAJOR issues identified by active specialists or validated reviewers.
* **Request Changes**: Any validated MAJOR findings from reviewer/dev pairs or ANY findings from specialists.
* **Block**: Any validated BLOCKER findings from reviewer/dev pairs or security violations.
