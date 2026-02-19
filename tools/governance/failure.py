"""PostToolUseFailure hook: investigation reminder on unexpected tool errors.

When a tool fails unexpectedly, injects an additionalContext advisory
reminding the agent to consider whether the failure indicates a defect
requiring root cause analysis (5-whys), rather than silently working
around it. Always exits 0 — PostToolUseFailure hooks cannot block.

The reminder fires for ANY unexpected failure (not just governance-
related ones) because the 5-whys discipline applies universally:
framework dev sessions might hit governance bugs, product builds might
hit hook configuration issues or integration problems. The point is to
interrupt the "work around and move on" reflex.

Routine/expected failures are filtered out to avoid noise.
"""

from __future__ import annotations

import json

# Error patterns that are routine/expected — these should NOT trigger
# an investigation reminder because they represent normal workflow.
_ROUTINE_PATTERNS = [
    # Edit tool: normal usage patterns
    "not unique in the file",
    "old_string",
    "new_string must be different",
    # Read tool: normal misses
    "file not found",
    "no such file",
    "is a directory",
    # General
    "permission denied",
    # Governance blocks are intentional, not defects
    "blocked:",
    "governance debt",
    "requires activation",
    "requires root cause",
    "edit requires",
    # User interrupts
    "interrupt",
    "cancelled",
    "timed out",
]


def check(hook_input: dict) -> str | None:
    """Return JSON additionalContext if failure warrants investigation, else None."""
    error = hook_input.get("error", "")
    error_lower = error.lower()

    # Skip if the user interrupted
    if hook_input.get("is_interrupt"):
        return None

    # Skip empty errors
    if not error.strip():
        return None

    # Skip routine/expected errors
    for pattern in _ROUTINE_PATTERNS:
        if pattern in error_lower:
            return None

    msg = (
        "UNEXPECTED TOOL FAILURE. Before working around this error, "
        "pause and apply root cause analysis: What failed? Why? "
        "Is this a systemic issue or a one-off? If it indicates a "
        "defect (in the framework, hooks, or integration), capture it "
        "as an observation rather than silently working around it."
    )
    return json.dumps({"additionalContext": msg})
