"""
Blacklist Agent — applies the hand-edited "do not draft" list to the board.

Two inputs feed the same mechanism:

  1. Manual entries in data/beer_sheet/blacklist.yaml — the owner types a
     name in by hand, any time, in seconds.
  2. Auto-flagging — players whose injury_status is severe (OUT,
     INJURY_RESERVE, SUSPENSION by default) get flagged without anyone
     having to remember them.

Each entry carries a severity:

  EXCLUDE  Player is dropped from the board entirely, before truncation to
           board_size, so a real player is promoted into the sheet instead
           of leaving a hole.
  FADE     Player stays on the board with blacklisted=True and a
           blacklist_reason, and is excluded from the bargains/reaches
           summaries — a faded player is never presented as a "value."

File format
-----------
blacklist.yaml is YAML-flavored, but Python's stdlib has no YAML parser and
this pipeline is deliberately pip-free (see main.py's docstring — nothing
should require an install on draft morning). Rather than pull in a
dependency, `_parse_blacklist_yaml` below hand-parses the ONE small subset
of YAML this file is defined to use:

  - full-line comments (`# ...`) and blank lines, ignored
  - a top-level `players:` key holding a list of `- name: ... / severity:
    ... / reason: ...` records (dash-prefixed, 2-space-indented block)
  - a top-level `auto_flag:` key holding flat `key: value` pairs, including
    a `statuses: [A, B, C]` flow-style list
  - quoted or bare scalar values, `true`/`false` booleans

This keeps the file itself real YAML (so Hugo, or a future `yaml.safe_load`,
can still read it directly out of data/) while keeping the *parser* pure
stdlib. If the file's structure ever needs to grow beyond this subset,
extend the parser deliberately — don't silently start ignoring lines.

Name matching
-------------
Matching is case-insensitive, punctuation- and accent-insensitive, and
suffix-tolerant (Jr/Sr/II/III/IV/V), via `normalize_name`. "ja'marr chase",
"Jamarr Chase", and "Ja'Marr Chase" all normalize to the same key.

Any blacklist entry that matches no player on the board is reported via a
loud `logger.warning` (never silently dropped) — a typo'd name that does
nothing is worse than no blacklist at all, because the owner will believe
a player is suppressed when they aren't.
"""

import logging
import re
import unicodedata
from pathlib import Path

from config import BLACKLIST_FILE, BLACKLIST_AUTO_FLAG_STATUSES, BLACKLIST_AUTO_FLAG_SEVERITY

logger = logging.getLogger("blacklist_agent")

_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def normalize_name(name: str) -> str:
    """
    Case/punctuation/accent/suffix-insensitive key for matching player names.
    "Ja'Marr Chase" -> "jamarr chase"; "James Cook III" -> "james cook".
    """
    if not name:
        return ""
    # Strip accents: decompose, drop combining marks (e.g. "é" -> "e").
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    lowered = stripped.lower()
    # Apostrophes disappear entirely (no gap) so "Ja'Marr" == "Jamarr", not
    # "Ja Marr". Every other non-alnum char (hyphens, periods, spaces)
    # collapses to a single space so multi-word names still tokenize right.
    no_apostrophes = re.sub(r"['’`]", "", lowered)
    cleaned = re.sub(r"[^a-z0-9]+", " ", no_apostrophes)
    tokens = [t for t in cleaned.split() if t not in _SUFFIXES]
    return " ".join(tokens)


# ── Minimal YAML subset parser ─────────────────────────────────────────────

def _parse_scalar(raw: str):
    s = raw.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        s = s[1:-1]
    if s.lower() == "true":
        return True
    if s.lower() == "false":
        return False
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part) for part in inner.split(",")]
    return s


def _parse_blacklist_yaml(text: str) -> dict:
    data = {"players": [], "auto_flag": {}}
    current_key = None
    current_record = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))

        if indent == 0:
            if ":" not in stripped:
                continue
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            current_key = key
            current_record = None
            if key == "players":
                data.setdefault("players", [])
            elif key == "auto_flag":
                data.setdefault("auto_flag", {})
            elif val:
                data[key] = _parse_scalar(val)
            continue

        if current_key == "players":
            item = stripped
            if item.startswith("- "):
                current_record = {}
                data["players"].append(current_record)
                item = item[2:].strip()
            if current_record is None:
                continue
            if ":" in item:
                k, _, v = item.partition(":")
                current_record[k.strip()] = _parse_scalar(v)
        elif current_key == "auto_flag":
            if ":" in stripped:
                k, _, v = stripped.partition(":")
                data["auto_flag"][k.strip()] = _parse_scalar(v)

    return data


def load(path: Path = None) -> dict:
    """Read and parse blacklist.yaml. Missing file = empty blacklist (not an error)."""
    path = path or BLACKLIST_FILE
    if not path.exists():
        logger.info("No blacklist file at %s — nothing to apply", path)
        return {"players": [], "auto_flag": {}}
    text = path.read_text(encoding="utf-8")
    return _parse_blacklist_yaml(text)


# ── Application ─────────────────────────────────────────────────────────────

def apply(players: list, path: Path = None) -> tuple:
    """
    Apply the blacklist to a list of merged player dicts (pre-truncation).

    Mutates nothing in place beyond adding `blacklisted` / `blacklist_reason`
    keys to every player dict (so every player on the board has both fields,
    even when False/"" ). Returns (kept_players, summary):

      kept_players — same list minus EXCLUDE matches, in original order.
      summary      — counts + names, for board.json's blacklist_summary.
    """
    raw = load(path)
    manual_entries = raw.get("players") or []
    auto_cfg = raw.get("auto_flag") or {}
    auto_enabled = auto_cfg.get("enabled", True)
    auto_statuses = set(
        (auto_cfg.get("statuses") or BLACKLIST_AUTO_FLAG_STATUSES)
    )
    auto_statuses = {s.upper() for s in auto_statuses}
    auto_severity = str(auto_cfg.get("severity") or BLACKLIST_AUTO_FLAG_SEVERITY).upper()

    # Default fields on every player, so board.json's schema is uniform
    # whether or not the blacklist touched them.
    for p in players:
        p["blacklisted"] = False
        p["blacklist_reason"] = ""

    index = {}
    for p in players:
        index.setdefault(normalize_name(p["name"]), []).append(p)

    excluded_names, faded_names, unmatched = [], [], []
    manually_touched_ids = set()

    for entry in manual_entries:
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        severity = str(entry.get("severity") or "FADE").strip().upper()
        reason = str(entry.get("reason") or "").strip()

        matches = index.get(normalize_name(name), [])
        if not matches:
            unmatched.append(name)
            logger.warning(
                "blacklist entry matched NO player: %r — check the spelling "
                "in blacklist.yaml (this entry is doing NOTHING)", name
            )
            continue

        for p in matches:
            p["_bl_severity"] = severity
            p["blacklist_reason"] = reason or f"blacklisted ({severity.lower()})"
            manually_touched_ids.add(p["player_id"])
            if severity == "EXCLUDE":
                excluded_names.append(p["name"])
            else:
                faded_names.append(p["name"])

    auto_flagged_names = []
    if auto_enabled:
        for p in players:
            if p["player_id"] in manually_touched_ids:
                continue  # manual entry always wins over auto-flag
            status = str(p.get("injury_status") or "").upper()
            if status in auto_statuses:
                p["_bl_severity"] = auto_severity
                p["blacklist_reason"] = f"auto-flagged: {status}"
                auto_flagged_names.append(p["name"])
                if auto_severity == "EXCLUDE":
                    excluded_names.append(p["name"])
                else:
                    faded_names.append(p["name"])

    kept = []
    for p in players:
        severity = p.pop("_bl_severity", None)
        if severity == "EXCLUDE":
            continue  # dropped entirely, before board_size truncation
        if severity == "FADE":
            p["blacklisted"] = True
        kept.append(p)

    summary = {
        "excluded_count": len(excluded_names),
        "faded_count": len(faded_names),
        "auto_flagged_count": len(auto_flagged_names),
        "excluded_names": sorted(set(excluded_names)),
        "faded_names": sorted(set(faded_names)),
        "unmatched_entries": unmatched,
    }

    logger.info(
        "Blacklist: %d excluded, %d faded (%d auto-flagged), %d unmatched entr%s",
        summary["excluded_count"], summary["faded_count"],
        summary["auto_flagged_count"], len(unmatched),
        "y" if len(unmatched) == 1 else "ies",
    )
    if unmatched:
        logger.warning("Unmatched blacklist entries: %s", ", ".join(unmatched))

    return kept, summary
