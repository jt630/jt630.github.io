#!/usr/bin/env python3
"""
diagnose.py — CarVoice diagnosis pipeline

Reads a drive log (from obd2_logger.py) plus a vehicle's maintenance history
and asks Claude for a structured diagnosis: severity, likely causes, repair
steps, estimated cost, and urgency.

The system prompt, JSON output schema, and disclaimer-injection pattern are
adapted from speed785/open-mechanic (MIT License) — see
carvoice/THIRD_PARTY_NOTICES.md and carvoice/research/open-mechanic-review.md
§4/§6 for what was adapted and why. The disclaimer is injected here, in code,
on every result — never left to the caller or to the model's own copy of it.

Usage:
  python scripts/carvoice/diagnose.py --drive-log data/carvoice/drives/2019_subaru_forester_20260915.jsonl
  python scripts/carvoice/diagnose.py --drive-log ... --save

Dependencies (pip install -r requirements-carvoice.txt):
  anthropic
  pyyaml
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent.parent
MAINTENANCE_LOG_PATH = ROOT / "data" / "carvoice" / "maintenance_log.yaml"
VEHICLES_PATH = ROOT / "data" / "carvoice" / "vehicles.yaml"
REPORTS_DIR = ROOT / "data" / "carvoice" / "reports"

DISCLAIMER = (
    "This diagnosis is informational only and does not constitute professional "
    "mechanical advice. Consult a qualified mechanic before making safety-critical repairs."
)

# Adapted from open-mechanic's DIAGNOSTIC_SYSTEM_PROMPT (ai/prompts.py), with
# the maintenance-history-weighting rule (#3) added — that cross-reference is
# CarVoice's own differentiator, not present in the original.
DIAGNOSTIC_SYSTEM_PROMPT = """\
You are an expert automotive technician with deep knowledge of OBD-II diagnostics, \
vehicle fault codes, and mechanical repair across all major makes and models.

You will be given vehicle information, active fault codes (DTCs), recent sensor \
readings from an OBD-II scan, and the vehicle's maintenance history. Analyze this \
data and return a diagnosis.

RESPONSE FORMAT:
You MUST respond with ONLY valid JSON — no markdown, no prose, no code fences. \
The JSON must conform exactly to this schema:

{
  "severity": "<info|warning|critical|do_not_drive>",
  "summary": "<one sentence plain-English summary of the diagnosis>",
  "likely_causes": ["<cause 1>", "<cause 2>"],
  "repair_steps": ["<step 1>", "<step 2>"],
  "estimated_cost_usd": {"low": <integer>, "high": <integer>},
  "diy_feasible": <true|false>,
  "diy_difficulty": "<easy|moderate|hard|professional_only>",
  "urgency": "<immediate|soon|next_service|monitor>"
}

SEVERITY DEFINITIONS:
- info: No fault codes, all sensors nominal — routine check.
- warning: Issue present but vehicle is drivable; address within days to weeks.
- critical: Significant fault; continued driving risks further damage. Address soon.
- do_not_drive: Safety-critical fault; vehicle should not be driven until repaired.

URGENCY DEFINITIONS:
- immediate: Stop driving now; safety risk.
- soon: Address within 1-3 days.
- next_service: Address at next scheduled service.
- monitor: Keep an eye on it; no immediate action required.

RULES:
1. Be conservative: when in doubt, escalate severity rather than downplay it.
2. Sensor values marked unsupported/null mean the vehicle doesn't expose that PID —
   don't treat missing data as a fault; work with what's available.
3. Weigh maintenance history: a code following recent related service reads
   differently than the same code on a component with no service history.
4. Provide at least two likely causes and at least two repair steps.
5. Cost estimates should reflect realistic US market labor + parts ranges.
"""


@dataclass
class DiagnosisResult:
    severity: str
    summary: str
    likely_causes: list[str]
    repair_steps: list[str]
    estimated_cost_usd: dict[str, int]
    diy_feasible: bool
    diy_difficulty: str
    urgency: str
    disclaimer: str = field(default=DISCLAIMER)


def _strip_code_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```json"):
        text = text[7:].lstrip()
    elif text.startswith("```"):
        text = text[3:].lstrip()
    if text.endswith("```"):
        text = text[:-3].rstrip()
    return text


def load_drive_log(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def load_vehicle(vehicle_id: str) -> dict[str, Any]:
    if not VEHICLES_PATH.exists():
        return {}
    with open(VEHICLES_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    for entry in data.get("vehicles", []) or []:
        if entry.get("vehicle_id") == vehicle_id:
            return entry
    return {}


def load_maintenance_history(vehicle_id: str) -> list[dict[str, Any]]:
    if not MAINTENANCE_LOG_PATH.exists():
        return []
    with open(MAINTENANCE_LOG_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    events = [e for e in (data.get("maintenance_events") or []) if e.get("vehicle_id") == vehicle_id]
    return sorted(events, key=lambda e: e.get("date", ""))


def summarize_drive(records: list[dict[str, Any]]) -> str:
    """Collapse a drive log into a compact text summary rather than pasting
    hundreds of raw JSON lines into the prompt."""
    if not records:
        return "(no sensor data in this drive log)"

    dtc_codes: dict[str, dict] = {}
    for record in records:
        for dtc in record.get("dtcs", []):
            dtc_codes[dtc["code"]] = dtc

    latest_sensors = records[-1].get("sensors", {})
    lines = [f"Drive log: {len(records)} samples.", "Most recent sensor snapshot:"]
    for name, sensor in latest_sensors.items():
        if not sensor.get("supported"):
            lines.append(f"  {name}: N/A (unsupported)")
        else:
            unit = f" {sensor['unit']}" if sensor.get("unit") else ""
            lines.append(f"  {name}: {sensor['value']}{unit}")

    if dtc_codes:
        lines.append(f"Fault Codes ({len(dtc_codes)}):")
        for dtc in sorted(dtc_codes.values(), key=lambda d: d["code"]):
            lines.append(
                f"  - {dtc['code']}: {dtc.get('description', 'Unknown code')} "
                f"[{dtc.get('severity', 'unknown')}, {dtc.get('status', 'unknown')}]"
            )
    else:
        lines.append("Fault Codes: None")

    return "\n".join(lines)


def summarize_maintenance(events: list[dict[str, Any]]) -> str:
    if not events:
        return "(no maintenance history on record)"
    lines = [
        f"  - {e.get('date', '?')} @ {e.get('mileage', '?')} mi: "
        f"{e.get('type', 'other')} — {e.get('description', '')}"
        for e in events[-10:]
    ]
    return "Maintenance history (most recent last):\n" + "\n".join(lines)


def format_prompt(vehicle: dict[str, Any], drive_summary: str, maintenance_summary: str) -> str:
    vehicle_line = f"Vehicle: {vehicle.get('year', '?')} {vehicle.get('make', '?')} {vehicle.get('model', '?')}"
    if vehicle.get("vin"):
        vehicle_line += f" | VIN: {vehicle['vin']}"

    return (
        f"{vehicle_line}\n\n{drive_summary}\n\n{maintenance_summary}\n\n"
        "Please analyze this data and provide your diagnosis as JSON."
    )


def diagnose(vehicle_id: str, drive_log_path: Path, model: str | None = None) -> DiagnosisResult:
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY is not set — export it before running diagnose.py")

    vehicle = load_vehicle(vehicle_id)
    if not vehicle:
        logger.warning(
            "No entry for %s in data/carvoice/vehicles.yaml — diagnosing with minimal context",
            vehicle_id,
        )

    records = load_drive_log(drive_log_path)
    drive_summary = summarize_drive(records)
    maintenance_summary = summarize_maintenance(load_maintenance_history(vehicle_id))
    user_message = format_prompt(vehicle, drive_summary, maintenance_summary)

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model or os.getenv("ANTHROPIC_MODEL") or "claude-sonnet-4-5",
        max_tokens=1024,
        system=DIAGNOSTIC_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = "\n".join(
        block.text for block in response.content if isinstance(getattr(block, "text", None), str)
    )
    cleaned = _strip_code_fences(raw_text)
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("AI response JSON must be an object")

    cost = data.get("estimated_cost_usd") or {}
    result = DiagnosisResult(
        severity=str(data.get("severity", "warning")),
        summary=str(data.get("summary", "Diagnosis unavailable")),
        likely_causes=[c for c in data.get("likely_causes", []) if isinstance(c, str)],
        repair_steps=[s for s in data.get("repair_steps", []) if isinstance(s, str)],
        estimated_cost_usd={
            "low": int(cost.get("low", 0) or 0),
            "high": int(cost.get("high", 0) or 0),
        },
        diy_feasible=bool(data.get("diy_feasible", False)),
        diy_difficulty=str(data.get("diy_difficulty", "moderate")),
        urgency=str(data.get("urgency", "soon")),
    )
    # Always the fixed constant, never the model's own copy of it.
    result.disclaimer = DISCLAIMER
    return result


def format_report(vehicle_id: str, result: DiagnosisResult) -> str:
    lines = [
        f"# CarVoice Diagnosis — {vehicle_id}",
        "",
        f"**Severity:** {result.severity}  ·  **Urgency:** {result.urgency}",
        "",
        result.summary,
        "",
        "## Likely Causes",
        *[f"- {c}" for c in result.likely_causes],
        "",
        "## Repair Steps",
        *[f"{i}. {s}" for i, s in enumerate(result.repair_steps, start=1)],
        "",
        f"**Estimated cost:** ${result.estimated_cost_usd['low']}-${result.estimated_cost_usd['high']}",
        f"**DIY feasible:** {result.diy_feasible} ({result.diy_difficulty})",
        "",
        f"> {result.disclaimer}",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="CarVoice diagnosis pipeline")
    parser.add_argument(
        "--drive-log", required=True, type=Path, help="Path to a .jsonl drive log from obd2_logger.py"
    )
    parser.add_argument(
        "--vehicle-id", default=None, help="Defaults to the drive log's own vehicle_id field"
    )
    parser.add_argument("--save", action="store_true", help="Also write the report to data/carvoice/reports/")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if not args.drive_log.exists():
        raise SystemExit(f"Drive log not found: {args.drive_log}")

    if args.vehicle_id:
        vehicle_id = args.vehicle_id
    else:
        with open(args.drive_log, encoding="utf-8") as f:
            first_line = json.loads(f.readline())
        vehicle_id = first_line.get("vehicle_id", "unknown_vehicle")

    result = diagnose(vehicle_id, args.drive_log, model=args.model)
    report = format_report(vehicle_id, result)
    print(report)

    if args.save:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = REPORTS_DIR / f"{vehicle_id}_{date.today():%Y%m%d}.md"
        out_path.write_text(report, encoding="utf-8")
        print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
