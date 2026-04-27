#!/usr/bin/env python3
"""
Goddard organ manifest conformance validator.

Walks data/robots/organs/*.yaml (or --organs-dir) and validates each manifest
against the rules stated in docs/goddard/SCHEMA.md. Exits 0 on a clean
library, non-zero with one error per line on violations.

Error format:  <file>:<rule_id>: <message>
Warning format: <file>:<rule_id>[warn]: <message>

Use --strict to treat warnings as errors.

Rules enforced (SCHEMA.md section anchor in brackets):

  R001  error  Required fields present: id, name, region, group, description,
               hardware-or-composes, preconditions, owned_by
               [§ Required fields]
  R002  error  region is one of the 8 valid values
               [§ Two axes]
  R003  error  group is one of the 9 valid functional groups
               [§ Two axes]
  R004  error  Every id in composes_with: resolves to an existing organ id
               [§ Registration protocol]
  R005  error  Every skill: id in composes: resolves to an existing organ id
               [§ Composed skills]
  R006  error  Every utterance_ref: <key> resolves to a key in the same
               manifest's voice_lines: block
               [§ Voice lines]
  R007  error  Every [token] in voice_lines: strings resolves to a
               token-backed key in MEMORY.md
               [§ Voice lines — Substitution tokens]
  R008  error  Every brain_memory query/update key resolves to a config or
               log key in MEMORY.md
               [§ Memory-key conventions]
  R009  error  Every recovery list ends in a terminal action (abort: true,
               hold:+until:, or a skill invocation)
               [§ Fallback and recovery]
  R010  error  Every hold: action carries a paired until: condition
               [§ Fallback and recovery — hold:/until:]
  R011  error  Every resident-facing hold: state (per MORALITY.md registry)
               carries requires_consent: on the same action
               [§ Morality module — Action-level pointer]
  R012  error  Every requires_consent: value resolves to a consent key in
               MORALITY.md
               [§ Morality module]
  R013  error  Every morality.requires: key resolves to a consent key in
               MORALITY.md
               [§ Morality module]
  R014  error  Same clause_id must have identical statement and overridable
               across all manifests in the library
               [§ Morality module — Module-clause layer]
  R015  error  Every morality.clauses: clause_id is registered in
               MORALITY.md § Module clauses
               [§ Morality module]
  R016  error  fallback: clauses use trigger:/recovery: envelope; no
               deprecated when:/action: keys
               [§ Fallback and recovery]
  R017  warn   storage_volume_cm3 > 0 requires hardware.slot for bucket
               routing
               [§ Registration protocol]
  R018  warn   only_if: expressions in composes: use valid boolean grammar
               (AND/OR not and/or/not)
               [§ Composed skills — only_if:]
  R019  error  Every composes: entry using a hand_* skill on a manifest that
               is a registered contact-primitive asserter (MORALITY.md
               § Resident-facing contact primitives) carries
               requires_consent: <key> matching the registry entry
               [§ Morality module — Action-level pointer]
"""

import argparse
import glob
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

# ── repo-relative defaults ────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).parent.parent
DEFAULT_ORGANS_DIR = str(_REPO_ROOT / "data" / "robots" / "organs")
DEFAULT_REGISTRIES_DIR = str(_REPO_ROOT / "docs" / "goddard")

# ── schema constants ──────────────────────────────────────────────────────────

VALID_REGIONS = frozenset({
    "brain", "core", "guts", "arm", "hands", "legs", "thighs", "skin"
})
VALID_GROUPS = frozenset({
    "movement", "manipulation", "fabrication", "sensing",
    "sequence_reading", "power", "communication", "gadgets", "infrastructure",
})

_TOKEN_RE = re.compile(r'\[[a-z][a-z0-9_]*\]')
_INVALID_BOOL_RE = re.compile(r'\b(and|or|not)\b')
_ASSERTER_SUFFIX_RE = re.compile(r'\s*\(\d+\)\s*$')

# ── registry parsing ──────────────────────────────────────────────────────────

def _section_text(text: str, header: str) -> str:
    """Extract body of a ## section, up to the next ## or EOF."""
    pattern = re.escape(header) + r'\s*\n(.*?)(?=\n##\s|\Z)'
    m = re.search(pattern, text, re.DOTALL)
    if m is None:
        raise ValueError(
            f"Registry section not found: {header!r} — "
            "table shape may have changed; fix the registry or the parser."
        )
    return m.group(1)


def _parse_table(text: str, section_header: str) -> list[list[str]]:
    """
    Extract data rows from the first markdown table in the named ## section.
    Skips the header row and separator rows. Strips backticks from each cell.
    Raises ValueError loudly if the section or any table row is malformed —
    per the wave brief: "if a table shape changes, fail loudly."
    """
    section = _section_text(text, section_header)
    rows: list[list[str]] = []
    header_seen = False

    for raw_line in section.split('\n'):
        line = raw_line.strip()
        if not line.startswith('|'):
            continue
        if re.match(r'^\|[-\s|]+\|$', line):  # separator row
            continue
        cells = [c.strip().strip('`') for c in line.split('|') if c.strip()]
        if not cells:
            continue
        if not header_seen:
            header_seen = True
            continue  # skip header row
        rows.append(cells)

    if not header_seen:
        raise ValueError(
            f"No markdown table found in section {section_header!r}. "
            "Registry file may have changed shape."
        )
    return rows


@dataclass
class Registries:
    consent_keys: frozenset       # str
    hold_states: frozenset        # str — resident-facing only
    clause_ids: frozenset         # str
    config_keys: frozenset        # str
    log_keys: frozenset           # str
    token_strings: frozenset      # str — e.g. "[name]", "[drug_name]"
    contact_asserter_map: dict    # manifest_id -> required_consent_key


def _parse_asserters(cell: str) -> list[str]:
    """
    Split an asserter cell into individual manifest ids.
    Handles both single ids ('leg_fall_response') and multi-asserter cells
    like '`arm_print_on_demand` (1), `arm_print_and_clean` (2)'.
    """
    parts = cell.split(',')
    result = []
    for part in parts:
        p = _ASSERTER_SUFFIX_RE.sub('', part.strip().strip('`')).strip()
        if p:
            result.append(p)
    return result


def load_registries(registries_dir: str) -> Registries:
    morality_path = os.path.join(registries_dir, "MORALITY.md")
    memory_path = os.path.join(registries_dir, "MEMORY.md")

    for p in (morality_path, memory_path):
        if not os.path.exists(p):
            sys.exit(f"ERROR: Registry file not found: {p}")

    morality = Path(morality_path).read_text()
    memory = Path(memory_path).read_text()

    consent_rows = _parse_table(morality, "## Consent keys")
    consent_keys = frozenset(r[0] for r in consent_rows if r)

    hold_rows = _parse_table(morality, "## Resident-facing hold states")
    hold_states = frozenset(r[0] for r in hold_rows if r)

    clause_rows = _parse_table(morality, "## Module clauses")
    clause_ids = frozenset(r[0] for r in clause_rows if r)

    config_rows = _parse_table(memory, "## Config keys")
    config_keys = frozenset(r[0] for r in config_rows if r)

    log_rows = _parse_table(memory, "## Log keys")
    log_keys = frozenset(r[0] for r in log_rows if r)

    token_rows = _parse_table(memory, "## Token-backed keys")
    # Column 1 holds the token string, e.g. "[name]"
    token_strings = frozenset(r[1] for r in token_rows if len(r) > 1)

    primitive_rows = _parse_table(morality, "## Resident-facing contact primitives")
    # Columns: Primitive | Consent key | Asserted by
    contact_asserter_map: dict[str, str] = {}
    for row in primitive_rows:
        if len(row) >= 3:
            consent_key = row[1]
            for asserter_id in _parse_asserters(row[2]):
                contact_asserter_map[asserter_id] = consent_key

    return Registries(
        consent_keys=consent_keys,
        hold_states=hold_states,
        clause_ids=clause_ids,
        config_keys=config_keys,
        log_keys=log_keys,
        token_strings=token_strings,
        contact_asserter_map=contact_asserter_map,
    )

# ── manifest loading ──────────────────────────────────────────────────────────

def load_manifests(organs_dir: str) -> dict[str, dict]:
    """Load all *.yaml files from organs_dir. Exits on parse error."""
    pattern = os.path.join(organs_dir, "*.yaml")
    manifests: dict[str, dict] = {}
    for filepath in sorted(glob.glob(pattern)):
        try:
            with open(filepath) as fh:
                data = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            sys.exit(f"ERROR: YAML parse failure in {filepath}: {exc}")
        if not isinstance(data, dict):
            print(f"WARNING: {filepath}: not a YAML mapping, skipped", file=sys.stderr)
            continue
        manifests[filepath] = data
    return manifests

# ── YAML structure helpers ────────────────────────────────────────────────────

def _find_values(data: Any, key: str) -> list[Any]:
    """Return all values for key anywhere in the nested structure."""
    results: list[Any] = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k == key:
                results.append(v)
            else:
                results.extend(_find_values(v, key))
    elif isinstance(data, list):
        for item in data:
            results.extend(_find_values(item, key))
    return results


def _find_dicts_with(data: Any, key: str) -> list[dict]:
    """Return all dicts that contain key anywhere in the nested structure."""
    results: list[dict] = []
    if isinstance(data, dict):
        if key in data:
            results.append(data)
        for v in data.values():
            results.extend(_find_dicts_with(v, key))
    elif isinstance(data, list):
        for item in data:
            results.extend(_find_dicts_with(item, key))
    return results


def _fallback_clauses(manifest: dict) -> list[dict]:
    fb = manifest.get('fallback', [])
    if not isinstance(fb, list):
        return []
    return [c for c in fb if isinstance(c, dict)]


def _is_terminal(action: Any) -> bool:
    """True if action is a terminal recovery action per SCHEMA.md § Fallback."""
    if not isinstance(action, dict):
        return False
    # abort: true
    if 'abort' in action:
        return True
    # hold: <state> until: <cond> — both fields required (R010 enforces that separately)
    if 'hold' in action and 'until' in action:
        return True
    # skill invocation — a completed skill call terminates the recovery
    if 'skill' in action:
        return True
    return False


def _voice_lines(manifest: dict) -> dict:
    vl = manifest.get('voice_lines', {})
    return vl if isinstance(vl, dict) else {}


def _morality_clauses(manifest: dict) -> list[dict]:
    m = manifest.get('morality', {})
    if not isinstance(m, dict):
        return []
    clauses = m.get('clauses', [])
    return [c for c in (clauses or []) if isinstance(c, dict)]

# ── rule implementations ──────────────────────────────────────────────────────

def check_r001(manifest, filepath, reg, organ_ids, _all_clauses):
    """Required fields present."""
    errors = []
    required = ['id', 'name', 'region', 'group', 'description', 'preconditions', 'owned_by']
    for f in required:
        if f not in manifest:
            errors.append(f"missing required field '{f}'")
    # hardware OR composes required
    if 'hardware' not in manifest and 'composes' not in manifest:
        errors.append("missing required field 'hardware' (or 'composes' for kind: composed)")
    return errors


def check_r002(manifest, filepath, reg, organ_ids, _all_clauses):
    """region is one of the 8 valid values."""
    region = manifest.get('region')
    if region is not None and region not in VALID_REGIONS:
        return [f"region '{region}' is not one of the 8 valid values: "
                f"{sorted(VALID_REGIONS)}"]
    return []


def check_r003(manifest, filepath, reg, organ_ids, _all_clauses):
    """group is one of the 9 valid functional groups."""
    group = manifest.get('group')
    if group is not None and group not in VALID_GROUPS:
        return [f"group '{group}' is not one of the 9 valid values: "
                f"{sorted(VALID_GROUPS)}"]
    return []


def check_r004(manifest, filepath, reg, organ_ids, _all_clauses):
    """Every id in composes_with: resolves to an existing organ id."""
    errors = []
    cw = manifest.get('composes_with', [])
    if not isinstance(cw, list):
        return []
    for ref in cw:
        if isinstance(ref, str) and ref not in organ_ids:
            errors.append(f"composes_with: '{ref}' does not resolve to a known organ id")
    return errors


def check_r005(manifest, filepath, reg, organ_ids, _all_clauses):
    """Every skill: id in composes: resolves to an existing organ id."""
    errors = []
    composes = manifest.get('composes', [])
    if not isinstance(composes, list):
        return []
    for entry in composes:
        if not isinstance(entry, dict):
            continue
        skill = entry.get('skill')
        if skill is not None and skill not in organ_ids:
            errors.append(f"composes: skill '{skill}' does not resolve to a known organ id")
    return errors


def check_r006(manifest, filepath, reg, organ_ids, _all_clauses):
    """Every utterance_ref: <key> resolves to a key in the manifest's voice_lines: block."""
    errors = []
    vl_keys = set(_voice_lines(manifest).keys())
    for ref in _find_values(manifest, 'utterance_ref'):
        if isinstance(ref, str) and ref not in vl_keys:
            errors.append(f"utterance_ref '{ref}' not found in this manifest's voice_lines: block")
    return errors


def check_r007(manifest, filepath, reg, organ_ids, _all_clauses):
    """Every [token] in voice_lines: strings resolves to a token in MEMORY.md."""
    errors = []
    for key, value in _voice_lines(manifest).items():
        if not isinstance(value, str):
            continue
        for token in _TOKEN_RE.findall(value):
            if token not in reg.token_strings:
                errors.append(
                    f"voice_lines.{key}: substitution token '{token}' is not "
                    f"registered in MEMORY.md § Token-backed keys "
                    f"(known: {sorted(reg.token_strings)})"
                )
    return errors


def check_r008(manifest, filepath, reg, organ_ids, _all_clauses):
    """Every brain_memory query/update key resolves to a config or log key in MEMORY.md."""
    errors = []
    valid_keys = reg.config_keys | reg.log_keys

    for call in _find_dicts_with(manifest, 'skill'):
        if not isinstance(call, dict) or call.get('skill') != 'brain_memory':
            continue
        with_block = call.get('with', {})
        if not isinstance(with_block, dict):
            continue

        for access_type in ('query', 'update'):
            access = with_block.get(access_type)
            if not isinstance(access, dict):
                continue
            key = access.get('key')
            if isinstance(key, str) and key not in valid_keys:
                errors.append(
                    f"brain_memory {access_type}.key '{key}' is not registered "
                    f"in MEMORY.md § Config keys or § Log keys"
                )
    return errors


def check_r009(manifest, filepath, reg, organ_ids, _all_clauses):
    """Every recovery list ends in a terminal action."""
    errors = []
    for clause in _fallback_clauses(manifest):
        trigger = clause.get('trigger', '<no trigger>')
        recovery = clause.get('recovery', [])
        if not isinstance(recovery, list) or not recovery:
            errors.append(
                f"fallback trigger '{trigger}': recovery list is empty or missing"
            )
            continue
        last = recovery[-1]
        if not _is_terminal(last):
            action_type = list(last.keys())[0] if isinstance(last, dict) and last else repr(last)
            errors.append(
                f"fallback trigger '{trigger}': recovery list ends with "
                f"non-terminal action '{action_type}' — "
                f"must end with abort:, hold:+until:, or a skill invocation"
            )
    return errors


def check_r010(manifest, filepath, reg, organ_ids, _all_clauses):
    """Every hold: action carries a paired until: condition."""
    errors = []
    for hold_dict in _find_dicts_with(manifest, 'hold'):
        if 'until' not in hold_dict:
            state = hold_dict.get('hold', '<unknown>')
            errors.append(
                f"hold: '{state}' has no paired until: condition "
                f"(forever-holds are invalid per SCHEMA.md)"
            )
    return errors


def check_r011(manifest, filepath, reg, organ_ids, _all_clauses):
    """Every resident-facing hold: carries requires_consent:."""
    errors = []
    for hold_dict in _find_dicts_with(manifest, 'hold'):
        state = hold_dict.get('hold', '')
        if state in reg.hold_states and 'requires_consent' not in hold_dict:
            errors.append(
                f"hold: '{state}' is a resident-facing hold state "
                f"(per MORALITY.md § Resident-facing hold states) "
                f"but carries no requires_consent: — registration will fail"
            )
    return errors


def check_r012(manifest, filepath, reg, organ_ids, _all_clauses):
    """Every requires_consent: value resolves to a consent key in MORALITY.md."""
    errors = []
    for key in _find_values(manifest, 'requires_consent'):
        if isinstance(key, str) and key not in reg.consent_keys:
            errors.append(
                f"requires_consent: '{key}' is not a registered consent key "
                f"in MORALITY.md § Consent keys (known: {sorted(reg.consent_keys)})"
            )
    return errors


def check_r013(manifest, filepath, reg, organ_ids, _all_clauses):
    """Every morality.requires: key resolves to a consent key in MORALITY.md."""
    errors = []
    morality = manifest.get('morality', {})
    if not isinstance(morality, dict):
        return []
    requires = morality.get('requires', [])
    if not isinstance(requires, list):
        return []
    for key in requires:
        if isinstance(key, str) and key not in reg.consent_keys:
            errors.append(
                f"morality.requires: '{key}' is not a registered consent key "
                f"in MORALITY.md § Consent keys (known: {sorted(reg.consent_keys)})"
            )
    return errors


def check_r015(manifest, filepath, reg, organ_ids, _all_clauses):
    """Every morality.clauses: clause_id is registered in MORALITY.md."""
    errors = []
    for clause in _morality_clauses(manifest):
        cid = clause.get('clause_id')
        if isinstance(cid, str) and cid not in reg.clause_ids:
            errors.append(
                f"morality.clauses: clause_id '{cid}' is not registered "
                f"in MORALITY.md § Module clauses — a clause asserted under "
                f"an unregistered name registers as inert"
            )
    return errors


def check_r016(manifest, filepath, reg, organ_ids, _all_clauses):
    """fallback: clauses use trigger:/recovery: not deprecated when:/action:."""
    errors = []
    for clause in _fallback_clauses(manifest):
        if 'when' in clause:
            errors.append(
                "fallback clause uses deprecated 'when:' key — "
                "migrate to 'trigger:' per SCHEMA.md § Fallback and recovery "
                "(Wave 12 canonical envelope)"
            )
        if 'action' in clause:
            errors.append(
                "fallback clause uses deprecated 'action:' key — "
                "migrate to 'recovery:' per SCHEMA.md § Fallback and recovery "
                "(Wave 12 canonical envelope)"
            )
    return errors


def check_r017(manifest, filepath, reg, organ_ids, _all_clauses):
    """storage_volume_cm3 > 0 requires hardware.slot for routing."""
    hardware = manifest.get('hardware', {})
    if not isinstance(hardware, dict):
        return []
    vol = hardware.get('storage_volume_cm3')
    try:
        vol_n = float(vol) if vol is not None else 0
    except (TypeError, ValueError):
        return []
    if vol_n > 0 and 'slot' not in hardware:
        return [
            f"hardware.storage_volume_cm3 = {vol} but hardware.slot is missing — "
            f"the registration protocol cannot route this organ to a chassis bucket"
        ]
    return []


def check_r018(manifest, filepath, reg, organ_ids, _all_clauses):
    """only_if: expressions in composes: use valid boolean grammar (AND/OR not and/or/not)."""
    errors = []
    composes = manifest.get('composes', [])
    if not isinstance(composes, list):
        return []
    for entry in composes:
        if not isinstance(entry, dict):
            continue
        expr = entry.get('only_if')
        if not isinstance(expr, str):
            continue
        bad = _INVALID_BOOL_RE.findall(expr)
        if bad:
            role = entry.get('role', '<no role>')
            errors.append(
                f"composes[role={role!r}] only_if: expression contains "
                f"lowercase boolean keyword(s) {bad!r} — "
                f"use AND/OR (uppercase) per SCHEMA.md § Composed skills"
            )
    return errors

def check_r019(manifest, filepath, reg, organ_ids, _all_clauses):
    """Every hand_* composes entry on a contact-primitive asserter carries requires_consent:."""
    manifest_id = manifest.get('id')
    if not isinstance(manifest_id, str) or manifest_id not in reg.contact_asserter_map:
        return []
    expected_key = reg.contact_asserter_map[manifest_id]
    errors = []
    composes = manifest.get('composes', [])
    if not isinstance(composes, list):
        return []
    for entry in composes:
        if not isinstance(entry, dict):
            continue
        skill = entry.get('skill', '')
        if not isinstance(skill, str) or not skill.startswith('hand_'):
            continue
        role = entry.get('role', '<no role>')
        rc = entry.get('requires_consent')
        if rc is None:
            errors.append(
                f"composes[role={role!r}, skill={skill!r}] is a registered "
                f"contact primitive (asserter: {manifest_id!r}) but carries no "
                f"requires_consent: — expected '{expected_key}' per "
                f"MORALITY.md § Resident-facing contact primitives"
            )
        elif rc != expected_key:
            errors.append(
                f"composes[role={role!r}, skill={skill!r}] requires_consent: "
                f"'{rc}' does not match the registered consent key "
                f"'{expected_key}' (MORALITY.md § Resident-facing contact primitives)"
            )
    return errors


# ── R014: cross-manifest clause consistency ───────────────────────────────────

def check_r014_cross_manifest(
    manifests: dict[str, dict]
) -> list[tuple[str, str]]:
    """
    R014 — Same clause_id must have identical statement and overridable
    across all manifests. Returns list of (filepath, message) pairs.
    """
    # clause_id -> (statement, overridable, first_filepath)
    seen: dict[str, tuple[str, Any, str]] = {}
    errors: list[tuple[str, str]] = []

    for filepath, manifest in sorted(manifests.items()):
        for clause in _morality_clauses(manifest):
            cid = clause.get('clause_id')
            if not isinstance(cid, str):
                continue
            stmt = clause.get('statement', '')
            ovr = clause.get('overridable')

            if cid not in seen:
                seen[cid] = (stmt, ovr, filepath)
            else:
                first_stmt, first_ovr, first_file = seen[cid]
                if stmt != first_stmt or ovr != first_ovr:
                    errors.append((filepath,
                        f"clause_id '{cid}' definition conflicts with "
                        f"{first_file}: "
                        f"statement {stmt!r} vs {first_stmt!r}, "
                        f"overridable {ovr!r} vs {first_ovr!r}"
                    ))
    return errors

# ── rule registry ─────────────────────────────────────────────────────────────

@dataclass
class Rule:
    rule_id: str
    severity: str   # "error" | "warn"
    schema_section: str
    check: Callable


_RULES: list[Rule] = [
    Rule("R001", "error",  "#required-fields",         check_r001),
    Rule("R002", "error",  "#two-axes",                check_r002),
    Rule("R003", "error",  "#two-axes",                check_r003),
    Rule("R004", "error",  "#registration-protocol",   check_r004),
    Rule("R005", "error",  "#composed-skills",         check_r005),
    Rule("R006", "error",  "#voice-lines",             check_r006),
    Rule("R007", "error",  "#voice-lines",             check_r007),
    Rule("R008", "error",  "#memory-key-conventions",  check_r008),
    Rule("R009", "error",  "#fallback-and-recovery",   check_r009),
    Rule("R010", "error",  "#fallback-and-recovery",   check_r010),
    Rule("R011", "error",  "#morality-module",         check_r011),
    Rule("R012", "error",  "#morality-module",         check_r012),
    Rule("R013", "error",  "#morality-module",         check_r013),
    # R014 is run separately (cross-manifest)
    Rule("R015", "error",  "#morality-module",         check_r015),
    Rule("R016", "error",  "#fallback-and-recovery",   check_r016),
    Rule("R017", "warn",   "#registration-protocol",   check_r017),
    Rule("R018", "warn",   "#composed-skills",         check_r018),
    Rule("R019", "error",  "#morality-module",         check_r019),
]

# ── main ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Goddard organ manifest conformance validator.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--organs-dir",
        default=DEFAULT_ORGANS_DIR,
        metavar="DIR",
        help=f"Directory of organ *.yaml files (default: {DEFAULT_ORGANS_DIR})",
    )
    p.add_argument(
        "--registries-dir",
        default=DEFAULT_REGISTRIES_DIR,
        metavar="DIR",
        help=f"Directory containing MORALITY.md and MEMORY.md "
             f"(default: {DEFAULT_REGISTRIES_DIR})",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings (R017, R018) as errors (R019 is always an error).",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    # ── load registries ────────────────────────────────────────────────────────
    try:
        reg = load_registries(args.registries_dir)
    except ValueError as exc:
        sys.exit(f"ERROR loading registries: {exc}")

    # ── load manifests ─────────────────────────────────────────────────────────
    manifests = load_manifests(args.organs_dir)
    if not manifests:
        sys.exit(f"ERROR: No *.yaml files found in {args.organs_dir}")

    all_organ_ids: set[str] = set()
    for m in manifests.values():
        if isinstance(m.get('id'), str):
            all_organ_ids.add(m['id'])

    # ── per-manifest rules ─────────────────────────────────────────────────────
    output_lines: list[tuple[str, str]] = []  # (severity, line)

    for filepath, manifest in sorted(manifests.items()):
        for rule in _RULES:
            msgs = rule.check(manifest, filepath, reg, all_organ_ids, None)
            for msg in msgs:
                tag = f"[{rule.severity}] " if rule.severity != "error" else ""
                output_lines.append(
                    (rule.severity, f"{filepath}:{rule.rule_id}: {tag}{msg}")
                )

    # ── R014: cross-manifest clause consistency ────────────────────────────────
    for fp, msg in check_r014_cross_manifest(manifests):
        output_lines.append(("error", f"{fp}:R014: {msg}"))

    # ── output and exit ────────────────────────────────────────────────────────
    has_error = False
    for severity, line in output_lines:
        print(line)
        if severity == "error" or args.strict:
            has_error = True

    if not output_lines:
        print(f"validate_organs: OK — {len(manifests)} manifest(s) passed all rules.")

    sys.exit(1 if has_error else 0)


if __name__ == "__main__":
    main()
