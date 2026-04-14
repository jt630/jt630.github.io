"""
Claude API integration for receipt analysis.

Uses the official Anthropic Python SDK. Reads ANTHROPIC_API_KEY from env.
Model: claude-haiku-4-5-20251001
"""
from __future__ import annotations

import json

try:
    import anthropic
except ImportError as e:
    raise ImportError(
        "anthropic package not installed. Run: pip install anthropic"
    ) from e

from schemas import AnalysisResult, Receipt

# ── System prompts by mode ───────────────────────────────────────────────────

_SYSTEM_PROMPTS: dict[str, str] = {
    "expense": (
        "You are an expense categorization assistant. Given a receipt, categorize each line item "
        "into standard expense categories (Meals & Entertainment, Office Supplies, Travel, etc.), "
        "identify if the receipt is reimbursable, and suggest a memo line. Return a JSON object "
        "with keys: categories (list), reimbursable (bool), memo (str), "
        "total_by_category (dict)."
    ),
    "split": (
        "You are a bill-splitting assistant. Given a receipt, suggest fair split options "
        "(equal split, split by item). Return JSON with: equal_share (float), "
        "items_with_shareable_flag (list), suggested_splits (list of scenarios)."
    ),
    "warranty": (
        "You are a warranty tracking assistant. Identify items on this receipt that typically "
        "come with warranties or return windows. Return JSON with: warranty_items (list with "
        "name, typical_warranty_period, return_window), total_covered_value (float)."
    ),
    "returns": (
        "You are a returns helper. Identify items most likely to be returned, typical return "
        "policies for this type of store, and flag high-value items. Return JSON with: "
        "returnable_items (list), store_policy_note (str), high_value_threshold (float)."
    ),
}

_MODEL = "claude-haiku-4-5-20251001"


# ── Public API ───────────────────────────────────────────────────────────────

def analyze_receipt(receipt: Receipt, mode: str = "expense") -> AnalysisResult:
    """
    Send *receipt* to Claude for analysis using the given *mode*.

    Parameters
    ----------
    receipt : Receipt
        The parsed receipt data to analyse.
    mode : str
        One of "expense", "split", "warranty", "returns".

    Returns
    -------
    AnalysisResult
        Parsed analysis with mode, summary, details dict, and raw_response text.
    """
    system_prompt = _SYSTEM_PROMPTS.get(mode)
    if system_prompt is None:
        raise ValueError(
            f"Unknown analysis mode '{mode}'. "
            f"Valid modes: {', '.join(_SYSTEM_PROMPTS)}"
        )

    # Serialize receipt to a compact JSON string for the user message
    receipt_json = receipt.model_dump_json(exclude_none=True, indent=2)
    user_message = f"Please analyse this receipt:\n\n```json\n{receipt_json}\n```"

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    response = client.messages.create(
        model=_MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text: str = next(
        (block.text for block in response.content if block.type == "text"),
        "",
    )

    # Parse JSON from the assistant response
    details: dict = {}
    try:
        # Strip markdown code fences if Claude wrapped the JSON
        stripped = raw_text.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            # Remove opening fence (```json or ```) and closing fence (```)
            inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            stripped = "\n".join(inner)
        details = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        # Fall back to storing the raw text under a generic key
        details = {"raw_text": raw_text}

    # Build a human-readable summary from the top-level details
    summary = _build_summary(mode, details)

    return AnalysisResult(
        mode=mode,
        summary=summary,
        details=details,
        raw_response=raw_text,
    )


# ── Internal helpers ─────────────────────────────────────────────────────────

def _build_summary(mode: str, details: dict) -> str:
    """Generate a one-line summary from parsed details."""
    try:
        if mode == "expense":
            cats = details.get("categories", [])
            reimbursable = details.get("reimbursable", False)
            memo = details.get("memo", "")
            return (
                f"{'Reimbursable' if reimbursable else 'Non-reimbursable'} — "
                f"{len(cats)} categorie(s). Memo: {memo}"
            )
        if mode == "split":
            share = details.get("equal_share", 0.0)
            return f"Equal share per person: ${share:.2f}"
        if mode == "warranty":
            items = details.get("warranty_items", [])
            total = details.get("total_covered_value", 0.0)
            return (
                f"{len(items)} item(s) with warranty coverage; "
                f"total covered value: ${total:.2f}"
            )
        if mode == "returns":
            items = details.get("returnable_items", [])
            note = details.get("store_policy_note", "")
            return f"{len(items)} returnable item(s). {note}"
    except Exception:
        pass
    return f"Analysis complete (mode={mode})"
