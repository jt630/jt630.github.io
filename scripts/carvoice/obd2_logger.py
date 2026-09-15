#!/usr/bin/env python3
"""
obd2_logger.py — CarVoice OBD2 drive logger

Polls a fixed PID set + active DTCs from a car's OBD2 port and writes one
JSON line per sample to data/carvoice/drives/{vehicle_id}_{YYYYMMDD}.jsonl.

Connection handling, sensor polling, and DTC reading are adapted from
speed785/open-mechanic (MIT License) — see carvoice/THIRD_PARTY_NOTICES.md
and carvoice/research/open-mechanic-review.md for what was adapted and why.
Trimmed for CarVoice's flat-file logger: no SQLite/ORM, that's a Session 3
(dashboard) concern, not needed here.

Hardware: a USB OBD2 adapter, not Bluetooth/WiFi (OBDLink SX recommended for
a non-Ford vehicle; OBDLink EX only if the target vehicle is a Ford — it's
Ford-optimized and costs more for features that go unused otherwise. See
carvoice/research/open-mechanic-review.md §1 for the full reasoning).

Usage:
  python scripts/carvoice/obd2_logger.py --vehicle-id 2019_subaru_forester --duration 300
  python scripts/carvoice/obd2_logger.py --vehicle-id 2019_subaru_forester --dry-run --duration 10

Dependencies (pip install -r requirements-carvoice.txt):
  obd
  pyserial
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import platform
import random
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent.parent
DRIVES_DIR = ROOT / "data" / "carvoice" / "drives"
DTC_DB_PATH = ROOT / "data" / "carvoice" / "dtc_codes.json"
VEHICLES_PATH = ROOT / "data" / "carvoice" / "vehicles.yaml"

# Session 1's target PID set (RPM, coolant temp, speed, engine load, fuel
# level) plus a few extras from open-mechanic's own sensor list that are
# cheap to also log and useful for later trend analysis (see analyst.md).
SENSOR_COMMANDS: list[str] = [
    "RPM",
    "SPEED",
    "COOLANT_TEMP",
    "ENGINE_LOAD",
    "FUEL_LEVEL",
    "INTAKE_TEMP",
    "SHORT_FUEL_TRIM_1",
    "LONG_FUEL_TRIM_1",
    "CONTROL_MODULE_VOLTAGE",
]


def get_default_port() -> str:
    system_name = platform.system()
    if system_name == "Linux":
        return "/dev/ttyUSB0"
    if system_name == "Darwin":
        matches = glob.glob("/dev/cu.usbserial-*") or glob.glob("/dev/tty.usbserial-*")
        return matches[0] if matches else "/dev/cu.usbserial-0"
    if system_name == "Windows":
        return "COM3"
    return "/dev/ttyUSB0"


class OBDConnection:
    """Adapted from open-mechanic's connection.py (MIT). Retry/backoff over
    a USB-serial adapter. No Bluetooth/WiFi path — see the hardware pivot
    note in CARVOICE.md Session 1 for why."""

    def __init__(
        self,
        port: str | None = None,
        protocol: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        self.port = port or get_default_port()
        self.protocol = protocol
        self.timeout = timeout
        self.max_retries = max_retries
        self._connection = None

    def connect(self) -> bool:
        import obd  # local import so --dry-run works without the package installed

        for attempt in range(1, self.max_retries + 1):
            logger.info(
                "Connecting to OBD adapter on %s (attempt %s/%s)",
                self.port,
                attempt,
                self.max_retries,
            )
            try:
                connection = obd.OBD(
                    portstr=self.port,
                    protocol=self.protocol,
                    timeout=self.timeout,
                    check_voltage=False,
                )
                if connection.is_connected():
                    self._connection = connection
                    logger.info(
                        "Connected on %s using protocol %s",
                        self.port,
                        connection.protocol_name(),
                    )
                    return True
                logger.warning("Connection attempt %s failed: adapter not connected", attempt)
            except Exception as exc:
                logger.warning("Connection attempt %s failed with error: %s", attempt, exc)

            if attempt < self.max_retries:
                time.sleep([0.5, 1.0, 2.0][min(attempt - 1, 2)])

        logger.error(
            "Failed to connect to OBD adapter on %s after %s attempts", self.port, self.max_retries
        )
        return False

    def disconnect(self) -> None:
        if self._connection is not None:
            self._connection.close()
        self._connection = None

    def is_connected(self) -> bool:
        return self._connection is not None and self._connection.is_connected()

    def get_connection(self):
        return self._connection


@dataclass
class SensorValue:
    name: str
    value: str | None
    unit: str | None
    supported: bool


def read_snapshot(conn) -> dict[str, dict]:
    """Adapted from open-mechanic's reader.py SensorPoller.get_snapshot().
    Unsupported PIDs are marked N/A rather than raising — some cars don't
    expose every command, and that's not a fault condition."""
    import obd

    snapshot: dict[str, dict] = {}
    for name in SENSOR_COMMANDS:
        cmd = getattr(obd.commands, name, None)
        if cmd is None:
            continue
        try:
            if cmd not in conn.supported_commands:
                snapshot[name] = asdict(SensorValue(name, None, None, False))
                continue

            response = conn.query(cmd)
            if response is None or response.is_null():
                snapshot[name] = asdict(SensorValue(name, None, None, False))
                continue

            raw_value = response.value
            magnitude = getattr(raw_value, "magnitude", raw_value)
            unit = getattr(raw_value, "units", None)
            value = f"{magnitude:.2f}" if isinstance(magnitude, float) else str(magnitude)
            snapshot[name] = asdict(SensorValue(name, value, str(unit) if unit else None, True))
        except Exception:
            snapshot[name] = asdict(SensorValue(name, None, None, False))

    return snapshot


def load_vehicle_protocol(vehicle_id: str) -> str | None:
    """Look up a cached OBD protocol number for this vehicle from
    vehicles.yaml (an optional `obd_protocol` field), so a vehicle whose
    protocol has already been confirmed doesn't pay the ~30s auto-detect
    cost on every run. Different vehicles can need different protocols —
    e.g. a pre-2003ish Ford uses SAE J1850 PWM (protocol "1"), while a
    2008+ car typically uses ISO 15765-4 CAN (protocol "6"). Don't assume
    one protocol number is right for every vehicle."""
    if not VEHICLES_PATH.exists():
        return None
    with open(VEHICLES_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    for entry in data.get("vehicles", []) or []:
        if entry.get("vehicle_id") == vehicle_id:
            protocol = entry.get("obd_protocol")
            return str(protocol) if protocol is not None else None
    return None


def _load_dtc_db() -> dict[str, dict]:
    if not DTC_DB_PATH.exists():
        logger.warning("DTC database not found at %s; codes will be unlabeled", DTC_DB_PATH)
        return {}
    with open(DTC_DB_PATH, encoding="utf-8") as f:
        entries = json.load(f)
    return {entry["code"].upper(): entry for entry in entries if "code" in entry}


def read_dtcs(conn, dtc_db: dict[str, dict]) -> list[dict]:
    """Adapted from open-mechanic's dtc.py DTCReader.get_dtcs() — reads both
    pending and confirmed codes and decodes them against the local DTC
    database vendored at data/carvoice/dtc_codes.json."""
    import obd

    codes: dict[str, dict] = {}
    for command_name, status in (("GET_CURRENT_DTC", "pending"), ("GET_DTC", "confirmed")):
        command = getattr(obd.commands, command_name, None)
        if command is None:
            continue
        try:
            response = conn.query(command)
        except Exception as exc:
            logger.warning("Failed querying %s: %s", command_name, exc)
            continue
        if response is None or response.is_null() or not isinstance(response.value, list):
            continue
        for item in response.value:
            if not isinstance(item, tuple) or not item:
                continue
            code = str(item[0]).strip().upper()
            if not code:
                continue
            details = dtc_db.get(code, {})
            codes[code] = {
                "code": code,
                "status": status,
                "description": details.get("description", "Unknown code"),
                "severity": details.get("severity", "unknown"),
                "category": details.get("category", "unknown"),
            }

    return sorted(codes.values(), key=lambda d: d["code"])


def fake_snapshot() -> dict[str, dict]:
    """--dry-run readings: plausible but fake, for testing without hardware.
    NOT validated against a real car — see CARVOICE.md Session 1's rule
    against claiming the real-hardware path works untested."""
    fake_ranges = {
        "RPM": (800, 3000, "rpm"),
        "SPEED": (0, 70, "kph"),
        "COOLANT_TEMP": (85, 105, "celsius"),
        "ENGINE_LOAD": (10, 60, "percent"),
        "FUEL_LEVEL": (20, 90, "percent"),
        "INTAKE_TEMP": (15, 40, "celsius"),
        "SHORT_FUEL_TRIM_1": (-5, 5, "percent"),
        "LONG_FUEL_TRIM_1": (-5, 5, "percent"),
        "CONTROL_MODULE_VOLTAGE": (13.5, 14.5, "volt"),
    }
    snapshot: dict[str, dict] = {}
    for name, (low, high, unit) in fake_ranges.items():
        value = round(random.uniform(low, high), 2)
        snapshot[name] = asdict(SensorValue(name, str(value), unit, True))
    return snapshot


def run(
    vehicle_id: str,
    duration: float | None,
    interval: float,
    dry_run: bool,
    port: str | None,
    protocol: str | None,
) -> Path:
    DRIVES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DRIVES_DIR / f"{vehicle_id}_{date.today():%Y%m%d}.jsonl"
    dtc_db = _load_dtc_db()

    conn: OBDConnection | None = None
    if not dry_run:
        conn = OBDConnection(port=port, protocol=protocol)
        if not conn.connect():
            raise SystemExit(
                "Could not connect to an OBD2 adapter. Use --dry-run to test "
                "the logger without hardware, or check the adapter/port/protocol."
            )

    logger.info("Logging to %s (dry_run=%s)", out_path, dry_run)
    start = time.monotonic()
    sample_count = 0
    try:
        with open(out_path, "a", encoding="utf-8") as f:
            while duration is None or (time.monotonic() - start) < duration:
                if dry_run:
                    snapshot = fake_snapshot()
                    dtcs: list[dict] = []
                else:
                    raw_conn = conn.get_connection()
                    snapshot = read_snapshot(raw_conn)
                    dtcs = read_dtcs(raw_conn, dtc_db)

                record = {
                    "timestamp": datetime.now().isoformat(),
                    "vehicle_id": vehicle_id,
                    "dry_run": dry_run,
                    "sensors": snapshot,
                    "dtcs": dtcs,
                }
                f.write(json.dumps(record) + "\n")
                f.flush()
                sample_count += 1
                time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Stopped by user")
    finally:
        if conn is not None:
            conn.disconnect()

    logger.info("Wrote %s samples to %s", sample_count, out_path)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="CarVoice OBD2 drive logger")
    parser.add_argument(
        "--vehicle-id",
        required=True,
        help="Matches an entry in data/carvoice/vehicles.yaml, e.g. 2019_subaru_forester",
    )
    parser.add_argument(
        "--duration", type=float, default=None, help="Seconds to log for (default: run until Ctrl+C)"
    )
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between samples")
    parser.add_argument("--port", default=None, help="Override serial port (e.g. /dev/ttyUSB0, COM3)")
    parser.add_argument(
        "--protocol",
        default=None,
        help=(
            "OBD protocol number (e.g. 1 = SAE J1850 PWM, most pre-2003ish Fords; "
            "6 = ISO 15765-4 CAN 11/500, most 2008+ cars). Different vehicles need "
            "different values — there is no safe universal default. If omitted, "
            "checks data/carvoice/vehicles.yaml for a cached obd_protocol on this "
            "vehicle_id; if that's also unset, falls back to slow (~30s) auto-detect."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate fake but plausible readings instead of connecting to real hardware",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    protocol = args.protocol or load_vehicle_protocol(args.vehicle_id)
    if protocol is None and not args.dry_run:
        logger.info(
            "No protocol specified or cached for %s — auto-detecting (can take ~30s). "
            "Once connected, note the protocol and add it as obd_protocol in "
            "vehicles.yaml to skip this next time.",
            args.vehicle_id,
        )
    run(args.vehicle_id, args.duration, args.interval, args.dry_run, args.port, protocol)


if __name__ == "__main__":
    main()
