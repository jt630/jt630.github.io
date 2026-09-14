# OBD2 Engineering Reference

Research notes for CarVoice Session 1 (`scripts/carvoice/obd2_logger.py`) and Session 2
(`scripts/carvoice/diagnose.py`). Compiled 2026-09-14. No hardware has been tested against
this repo yet — everything below is desk research, not verified against a real ELM327.
Where a claim rests on a single low-quality source or couldn't be cross-checked, it's
flagged **[unconfirmed]**.

---

## 1. Standard OBD2 PIDs (Mode 01 — current data)

All Mode 01 requests are sent as a 2-hex-digit PID after the mode byte `01`. Responses come
back as `41 <PID> <data bytes...>`. Formulas below are standard SAE J1979 scaling; the exact
PID hex codes and decoder logic are cross-checked against the `python-obd` library source
(`obd/commands.py`, `obd/decoders.py` in [brendan-w/python-OBD](https://github.com/brendan-w/python-OBD)),
which is itself an implementation of J1979, and against general PID references
([CSS Electronics PID table](https://www.csselectronics.com/pages/obd2-pid-table-on-board-diagnostics-j1979),
[python-OBD Command Tables docs](https://python-obd.readthedocs.io/en/latest/Command%20Tables/)).

### The Session 1 target set (RPM, coolant temp, speed, engine load, fuel level) + DTCs

| PID (hex) | Name | Bytes | Formula | Units | Notes |
|---|---|---|---|---|---|
| `01 0C` | Engine RPM | 2 (A,B) | `((A*256)+B)/4` | rpm | Most commonly polled PID; supported on essentially every OBD2 vehicle. |
| `01 05` | Engine coolant temperature | 1 (A) | `A - 40` | °C | Range -40 to 215 °C. Cold-start diagnostics (thermostat stuck open = P0128) depend on watching this over time, not just a single reading. |
| `01 0D` | Vehicle speed | 1 (A) | `A` | km/h | Direct byte value, 0–255 km/h. No scaling factor. |
| `01 04` | Calculated engine load | 1 (A) | `A * 100 / 255` | % | "Load" here is a computed value (percent of peak available torque at current RPM), not raw MAF/MAP. |
| `01 2F` | Fuel level input | 1 (A) | `A * 100 / 255` | % | Support for this PID is inconsistent across manufacturers — some vehicles simply don't expose it (return "NO DATA"). Worth a fallback in the logger. |
| Mode `03` | Get stored DTCs | variable | see §2 | — | Returns confirmed/stored trouble codes. Different from Mode `07` (pending codes) and Mode `0A` (permanent codes). |
| Mode `04` | Clear DTCs / turn off MIL | — | — | — | Destructive — clears freeze frame data and resets readiness monitors too. Don't wire this into the logger without an explicit flag; clearing codes right before a diagnose run would erase the evidence you're trying to explain. |

### Additional PIDs worth adding to the poll set

These round out a "general vehicle health" snapshot and are cheap to add since they're all
Mode 01, single or double-byte reads:

| PID (hex) | Name | Bytes | Formula | Units | Why it's useful |
|---|---|---|---|---|---|
| `01 0F` | Intake air temperature (IAT) | 1 (A) | `A - 40` | °C | Same decoder as coolant temp. Cross-referencing IAT vs. coolant temp helps distinguish a real overheating condition from a bad sensor. |
| `01 10` | MAF air flow rate | 2 (A,B) | `((A*256)+B)/100` | g/s | Mass air flow sensor reading. Comparing MAF to expected load/RPM is a classic way to catch a dirty/failing MAF sensor (root cause behind many P0171/P0174 lean codes). |
| `01 06` | Short term fuel trim — Bank 1 | 1 (A) | `(A - 128) * 100/128` | % | Signed, centered on 0%. Positive = ECU adding fuel (compensating for lean condition); negative = removing fuel (compensating for rich). Directly relevant to P0171/P0174/P0172/P0175. |
| `01 07` | Long term fuel trim — Bank 1 | 1 (A) | `(A - 128) * 100/128` | % | Same scaling as short-term; long-term trim is the "learned" adaptive correction and is more diagnostically meaningful than the short-term instantaneous value. |
| `01 08` / `01 09` | Short/long term fuel trim — Bank 2 | 1 each | same as above | % | Only meaningful on V-engines with two exhaust banks; single-bank engines will return "NO DATA" or not support these PIDs. |
| `01 11` | Throttle position | 1 (A) | `A * 100 / 255` | % | Useful to correlate load/RPM spikes with driver input vs. an unexplained idle issue. |
| `01 0B` | Intake manifold absolute pressure (MAP) | 1 (A) | `A` (direct) | kPa | On MAP-based (speed-density) engines this is the primary load sensor; on MAF-based engines it's a useful cross-check. |
| `01 0A` | Fuel pressure | 1 (A) | `A * 3` | kPa | Not supported on all vehicles (many modern ones report fuel rail pressure via a different PID, `01 23`, in kPa*10 for high-pressure direct-injection systems). |
| `01 14`–`01 1B` | O2 sensor voltage + short-term trim (Bank1 Sensor1 … Bank2 Sensor4) | 2 each | voltage = `A/200` V, trim = `(B-128)*100/128` % | V, % | Legacy narrowband O2 sensor PIDs. Many 2008+ vehicles use wideband sensors and report via `01 24`–`01 2B` (air-fuel equivalence ratio) instead — expect "NO DATA" on newer cars for the legacy PIDs and vice versa. |
| `01 1F` | Run time since engine start | 2 (A,B) | `(A*256)+B` | seconds | Cheap way to timestamp how far into a drive a given reading occurred without relying on wall-clock only. |
| `01 42` | Control module voltage | 2 (A,B) | `((A*256)+B)/1000` | V | Battery/charging system health — a slowly dropping value across a drive log could flag an alternator or battery issue, which is outside the emissions system but a real "is this car okay" question. |
| `01 1C` | OBD standards this vehicle conforms to | 1 (A) | lookup table | — | Worth reading once per vehicle (not every sample) — tells you if you're talking to OBD-II (US), EOBD (Europe), JOBD, etc., which can affect which PIDs are supported. |

**Recommendation for Session 1:** poll the six items already in the build plan (RPM, coolant
temp, speed, load, fuel level, DTCs) plus IAT, MAF, short+long fuel trim (bank 1 at minimum),
throttle position, and control module voltage. All of those are single or double-byte Mode 01
reads and give `diagnose.py` in Session 2 real signal (fuel trim drift, MAF/load mismatch,
voltage sag) beyond just parroting back DTC lookup-table text.

**Source note:** the RPM/temp/speed/load formulas above and the PID→command mapping are
corroborated directly against `python-obd`'s command table (fetched from
`obd/commands.py` and `obd/decoders.py` in the GitHub repo) — see full mapping:

```
0100 PIDS_A            0104 ENGINE_LOAD (percent)     0105 COOLANT_TEMP (temp)
0106 SHORT_FUEL_TRIM_1  0107 LONG_FUEL_TRIM_1          0108/0109 (bank 2 equivalents)
010A FUEL_PRESSURE      010B INTAKE_PRESSURE           010C RPM (uas 0x07)
010D SPEED (uas 0x09)   010E TIMING_ADVANCE            010F INTAKE_TEMP (temp)
0110 MAF (uas 0x27)     0111 THROTTLE_POS (percent)    0114-011B O2_B1S1..O2_B2S4
012F FUEL_LEVEL (percent)
Mode 3 (03) = GET_DTC, Mode 4 (04) = CLEAR_DTC, Mode 7 (07) = GET_CURRENT_DTC (pending)
```

`temp()` decoder: `bytes_to_int(data) - 40` → °C. `percent()` decoder: `byte * 100.0 / 255.0`.
These match the general J1979 references, so treat the formulas above as reliable.

---

## 2. DTC (Diagnostic Trouble Code) structure

### Format

A DTC is a 5-character code: **one letter + four digits**, e.g. `P0301`.

| Position | Meaning |
|---|---|
| 1st char (letter) | System: `P` = Powertrain (engine/transmission), `C` = Chassis (brakes, steering, suspension), `B` = Body (airbags, climate control, comfort systems), `U` = Network/communication (module-to-module bus faults) |
| 2nd char (digit) | Code origin: `0` = SAE-defined generic code (standardized across all manufacturers), `1` = manufacturer-specific/enhanced code, `2` = generic for P-codes is split (see below), `3` = manufacturer-specific for some categories |
| 3rd char (digit) | Subsystem affected (for P-codes specifically): `1` = fuel/air metering, `2` = fuel/air metering — injector circuit, `3` = ignition system or misfire, `4` = auxiliary emission controls, `5` = vehicle speed/idle control, `6` = computer/output circuit, `7`/`8` = transmission, `9`/`0` = SAE reserved / turbocharger (varies by year of spec) |
| 4th–5th chars | Specific fault number within that subsystem — manufacturer/SAE assigned, no universal formula |

### Generic vs. manufacturer-specific ranges (P-codes, the ones you'll see most in a
consumer OBD2 project)

- `P0000`–`P0999`: **generic/SAE-standard** — same meaning across all OBD2-compliant vehicles.
- `P1000`–`P1999`: **manufacturer-specific** — meaning varies by make; requires a
  manufacturer-specific lookup table, not just the generic J2012 spec.
- `P2000`–`P2999`: **generic (extended)** — SAE added this second generic block once the
  original `P0xxx` block filled up; still standardized.
- `P3000`–`P3399`: **manufacturer-specific** (also used for some SAE-defined hybrid/direct
  injection codes in newer specs) — treat as vendor-specific unless confirmed otherwise.

The same generic/manufacturer split pattern (second digit 0 vs. 1) applies to B, C, and U
codes, though the third-digit subsystem table differs per letter and is less standardized
than the P-code table. **[unconfirmed]** — I could not find as authoritative a breakdown for
B/C/U third-digit subsystem meanings as for P-codes; treat any B/C/U third-digit table you
see elsewhere with caution.

For CarVoice's purposes: a `python-obd`-style DTC decoder reads the raw 2-byte DTC from the
ECU as follows — top 2 bits of the first byte select the letter (`00`=P, `01`=C, `10`=B,
`11`=U), the next 2 bits are the first digit, and the rest of the bits map to the remaining
4 hex digits. This matches the decoder logic in `python-obd`'s `obd/decoders.py`
(`parse_dtc`), which is a reasonable reference for the raw wire format even before
`diagnose.py` gets involved.

### Common DTCs a home OBD2 project will actually encounter

These are the codes most likely to show up on an actual daily-driver over time — general
consumer-vehicle faults, not exotic ones:

| Code | Plain English |
|---|---|
| `P0300` | Random/multiple cylinder misfire detected — engine misfiring without the ECU pinning it to one specific cylinder. Often ignition (plugs/coils), fuel delivery, or a vacuum leak. |
| `P0301`–`P0308` | Cylinder-specific misfire (P0301 = cylinder 1, P0302 = cylinder 2, etc.) — same causes as P0300 but isolated to one cylinder, which usually points more specifically at that cylinder's plug, coil, or injector. |
| `P0171` | Fuel trim system too lean — Bank 1. Engine computer is adding more fuel than normal to compensate for excess air; common causes: vacuum leak, dirty/failing MAF sensor, weak fuel pump, clogged fuel filter. |
| `P0174` | Same as P0171 but Bank 2 (the other cylinder bank on a V-engine). |
| `P0172` / `P0175` | Fuel trim system too rich — Bank 1 / Bank 2 respectively (opposite of the lean codes above: too much fuel or too little air). |
| `P0420` | Catalyst system efficiency below threshold — Bank 1. The catalytic converter isn't cleaning exhaust as well as the ECU expects. Often the converter itself, but can also be triggered by an upstream engine problem (misfire, rich/lean condition) prematurely wearing the cat, or a failing downstream O2 sensor giving a false reading. |
| `P0430` | Same as P0420 but Bank 2. |
| `P0128` | Coolant thermostat — engine not reaching expected operating temperature within the expected time. Usually a stuck-open thermostat; not urgent but affects fuel economy and heater performance. |
| `P0113` | Intake air temperature (IAT) sensor circuit — high input (voltage reading implausibly high, ECU may think intake air is much colder than reality). |
| `P0134` | O2 sensor circuit — no activity detected, Bank 1 Sensor 1. The upstream oxygen sensor isn't switching/responding — could be a dead sensor, wiring fault, or exhaust leak near the sensor. |
| `P0442` | EVAP system — small leak detected. Very frequently just a loose or bad gas cap; worth checking that before assuming a real leak. |
| `P0455` | EVAP system — large leak detected. Same system as P0442 but a bigger leak (e.g., disconnected hose, cracked purge valve) — same starting point of checking the gas cap first, but more likely a real component issue if it persists. |
| `P0230` | Fuel pump primary circuit malfunction — electrical fault in the circuit that powers the fuel pump (relay, wiring, or pump itself), not a fuel-quality/pressure code per se. |

This list intentionally leans toward "codes that show up on an aging but reasonably healthy
daily driver" rather than a full J2012 dump — `diagnose.py` should probably ship with this
subset as a fallback plain-English table for when there's no network access to ask Claude,
and let the model handle anything outside this set.

---

## 3. `python-obd` (PyPI: `obd`) — current state

- **Latest release: 0.7.3, published April 7, 2025** (per PyPI). As of this research
  (September 2026) that's roughly a year and a half old — not abandoned, but not fast-moving
  either.
- **Repo:** [brendan-w/python-OBD](https://github.com/brendan-w/python-OBD) — 1.3k stars,
  427 forks, 86 open issues at time of research. Appears to be maintained by essentially one
  person (Brendan Whitfield); the README notes it's itself a fork of two older projects
  (`pyobd` and `pyobd-pi`).
- **Development status:** PyPI classifies it as "3 - Alpha" despite the project being many
  years old — treat the API as not fully stable across versions (their own classifier says
  as much).
- **Python support:** 3.9–3.13 per the current PyPI metadata.
- **License:** GPL v2.
- **Known limitations / gotchas surfaced in issues and docs:**
  - Bluetooth connections are flaky on some hardware, Raspberry Pi being called out
    specifically in the README; the documented workaround is passing
    `fast=False, timeout=30` to the `OBD()` constructor.
  - **WiFi support is not first-class.** The library connects via PySerial's
    `serial_for_url()`, which in principle supports a `socket://host:port` URL scheme for
    network sockets (confirmed by reading `obd/elm327.py` — it calls
    `serial.serial_for_url(portname, ...)`), but a long-standing GitHub issue
    ([#107](https://github.com/brendan-w/python-OBD/issues/107), opened 2018, closed without
    a documented resolution) shows at least one user hitting trouble getting this to work
    cleanly. Several separate small forks/scripts exist specifically to paper over this
    (e.g. `dailab/python-OBD-wifi`, which wraps a plain `connection = obd.OBD("192.168.0.10", 35000)`
    call). **Practical takeaway for CarVoice:** if the adapter is WiFi-based, don't assume
    `obd.OBD()` auto-detection will find it — expect to pass an explicit `socket://<ip>:<port>`
    portstr, and budget time in Session 1 to debug this specifically, or fall back to one of
    the wifi-specific forks if the mainline library gives trouble. **[unconfirmed]** whether
    this is fully solved in the current 0.7.3 release — the closed issue doesn't confirm a fix
    was merged, it may simply have gone stale.
  - PID support varies significantly by vehicle — the library's own docs state this
    explicitly. `obd.OBD()` runs a supported-PID query on connect and will report which of
    your requested commands actually work on the connected vehicle; the logger should handle
    "NO DATA" / unsupported responses gracefully rather than assuming every PID above returns
    a value.
  - Older pyserial compatibility issue noted in community discussion: pyserial 3.0 changed
    `in_waiting` from a function to a property, which broke some things downstream historically
    — likely long resolved in the current release but worth knowing if a `serial` version pin
    causes odd errors. **[unconfirmed / likely stale]**.

### Alternatives worth knowing about

- **[`py-obdii`](https://pypi.org/project/py-obdii/)** — actively developed as of this
  research (latest pre-release `0.10.5b0`, published July 2026), MIT licensed, supports
  Python 3.8–3.14, and explicitly advertises USB, Bluetooth, WiFi, and Ethernet adapter
  support in its own description. Still pre-1.0/beta, so expect API churn, but it looks like
  the more actively maintained option today if `python-obd`'s WiFi handling turns out to be
  painful in practice. No confirmed async support found in the material reviewed.
- **`openOBD`** — appeared in search results as a "production-stable" library (MIT license,
  Python ≥3.11) with a version roadmap mentioning "Terminal 15 support" and "session
  transfer" for 2025. **[unconfirmed]** — I could not verify claims about it beyond the PyPI
  listing; treat as a lead to evaluate hands-on rather than a vetted recommendation.
- **`pyOBD` / `pyOBDA`** (`AtesComp/pyOBDA` on GitHub) — GUI-oriented diagnostic apps
  descended from the original `pyobd`, not really a library to import into a script the way
  `obd`/`py-obdii` are. Useful as a manual scan-tool reference/sanity-check tool rather than
  as `obd2_logger.py`'s dependency.

**Recommendation:** start Session 1 with `python-obd` (`pip install obd`) since it's what
CARVOICE.md's plan already names and it's the most documented/battle-tested option, but treat
`py-obdii` as the fallback if the WiFi connection path (if the adapter turns out to be WiFi
rather than Bluetooth) proves troublesome — don't sink more than an hour into fighting
`python-obd`'s WiFi handling before trying the alternative.

---

## 4. ELM327 Bluetooth vs. WiFi adapters — practical differences for a Python script

| Aspect | Bluetooth (SPP/RFCOMM) | WiFi |
|---|---|---|
| Connection method from Python | Appears as a serial device once paired — `/dev/rfcomm0` on Linux (may need a manual `rfcomm bind`/`rfcomm connect` step first), a COM port on Windows, `/dev/tty.*` on macOS. `python-obd` then opens it like any serial port. | Adapter runs a small WiFi access point (or joins your network) and exposes a raw TCP socket, typically on a fixed IP/port (commonly `192.168.0.10:35000` for many cheap ELM327 WiFi clones — **[unconfirmed]** this exact IP/port is the actual default for the specific hardware CarVoice ends up buying; it's a commonly cited default across several cheap clone adapters in search results, not a universal standard). Python needs to open that as a TCP socket rather than a conventional serial port. |
| Setup friction | OS-level Bluetooth pairing first (and on Linux, sometimes a manual `rfcomm` bind), then it behaves like a normal serial device — historically the more finicky first-connection step, especially on Raspberry Pi per `python-obd`'s own README. | Usually simpler to get *a* connection (join the adapter's WiFi network or have it join yours), but then requires the extra step of pointing the library at a `socket://ip:port` string rather than relying on auto-detection, since `python-obd`'s port auto-scan is built around serial device enumeration, not network discovery. |
| Range/stability while driving | Bluetooth Classic (SPP) range is short (a few meters) but that's rarely an issue since the adapter and laptop are both in the car; more relevant is that cheap Bluetooth OBD2 chipsets can be flaky near the car's metal chassis/electrical noise. | If the adapter creates its own WiFi hotspot, most laptops can only join one WiFi network at a time — meaning your laptop loses its normal internet connection while connected to the adapter's hotspot. This matters for CarVoice specifically since Session 2's `diagnose.py` needs to reach the Claude API over the internet — with a WiFi-hotspot-style adapter you likely can't be connected to the OBD2 adapter and have internet access simultaneously unless the adapter supports joining your existing WiFi network (some do, some only run as their own AP) or your laptop has a second network path (e.g. cellular hotspot on a phone, or Ethernet). **This is a real architecture consideration for Session 1** — worth checking before buying hardware. |
| Latency | Some sources claim Bluetooth adapters see periodic 80–200ms latency spikes vs. sub-15ms for WiFi on the same query. **[unconfirmed — low-confidence source]**; this specific figure came from a marketing-adjacent comparison page, not a benchmark I could independently verify. Directionally plausible (Bluetooth Classic SPP does carry more protocol overhead than a raw TCP socket) but don't treat the numbers as precise. For a logger sampling once every second or so (typical drive-logging cadence), neither adapter type's latency should matter in practice. | See above. |
| Multi-client | Typically one Bluetooth client (your laptop) at a time. | Some WiFi ELM327 adapters allow multiple simultaneous TCP clients — not a CarVoice concern for Phase 1 (single logger script) but could matter later if a dashboard (Session 3) wants to read live data alongside the logger. |
| Library support (this project specifically) | `python-obd` treats it as a normal serial connection — best-supported path, most examples and community troubleshooting assume Bluetooth-as-serial. | `python-obd`'s auto-connect logic doesn't scan for network adapters; requires explicitly constructing the connection with a `socket://` portstr (see §3) and has at least one documented rough edge in GitHub issues. If the adapter purchased for CarVoice turns out to be WiFi-only, budget explicit debugging time for the connection step in Session 1, or fall back to `py-obdii`, which advertises WiFi support directly. |

### Bottom line for CarVoice hardware choice

Given `python-obd` is the library CARVOICE.md already commits to, **a Bluetooth ELM327
adapter is the lower-friction choice for Session 1** — better-trodden path in the library's
own docs and community troubleshooting, and it avoids the "laptop can only be on one WiFi
network at a time" problem that a WiFi adapter creates for reaching the Claude API in Session 2.
If a WiFi adapter is what's already on hand, it's workable, but plan for: (a) an explicit
`socket://ip:port` connection string rather than relying on auto-detect, and (b) a second
network path for internet access while the adapter's hotspot is connected (phone hotspot,
Ethernet, or an adapter model that joins your existing WiFi instead of creating its own AP).

---

## Sources

- [python-OBD Command Tables (docs)](https://python-obd.readthedocs.io/en/latest/Command%20Tables/)
- [python-OBD GitHub repo](https://github.com/brendan-w/python-OBD) — README, `obd/commands.py`, `obd/decoders.py`, `obd/elm327.py`, commit history, issue #107
- [`obd` package on PyPI](https://pypi.org/project/obd/)
- [`py-obdii` package on PyPI](https://pypi.org/project/py-obdii/)
- [CSS Electronics OBD2 PID table](https://www.csselectronics.com/pages/obd2-pid-table-on-board-diagnostics-j1979)
- [Anatomy of the DTC: OBD2 Codes Explained — The Group Training Academy](https://thegrouptrainingacademy.com/anatomy-of-the-dtc-obd2-codes-explained/)
- [Generic vs Manufacturer-Specific DTCs Explained — Wrenchlane](https://wrenchlane.com/en/article/understanding-generic-vs-manufacturer-specific-dtcs-key-differences-explained)
- [OBD2 Codes List: P, B, C and U Trouble Codes Explained — A-Premium](https://a-premium.com/blogs/obd2-codes-categories)
- [P0171/P0174 — O'Reilly Auto Parts](https://www.oreillyauto.com/check-engine-light-code-p0171-and-p0174-fuel-trim-system-lean)
- [P0420 — Mechanic Base](https://mechanicbase.com/trouble-code/)
- [P0300 — Auto Barn](https://www.autobarn.net/specs/obd-codes/p0300)
- [P0113 — obd-codes.com](https://www.obd-codes.com/p0113)
- [P0134 — FIXD](https://www.fixdapp.com/blog/p0134-code/)
- [P0230 — Auto Barn](https://www.autobarn.net/specs/obd-codes/p0230)
- [ELM327 WiFi vs Bluetooth comparison — AliExpress wiki article](https://www.aliexpress.com/s/wiki-ssr/article/elm327-wifi-vs-bluetooth) *(low-confidence source, latency figures only)*
- [How to choose an OBD II adapter: Wi-Fi or Bluetooth — InCarDoc](https://incardoc.com/en-us/article/how-to-choose-an-obd-ii-adapter-wi-fi-or-bluetooth/)
- [`dailab/python-OBD-wifi` on GitHub](https://github.com/dailab/python-OBD-wifi)
- [`elm327 over wifi` — python-OBD issue #107](https://github.com/brendan-w/python-OBD/issues/107)

*Note: `en.wikipedia.org`, `python-obd.readthedocs.io`, and `www.csselectronics.com` were
blocked by this session's network egress proxy for direct fetching; those sources are cited
above based on search-result snippets and cross-checked against the `python-obd` source code
directly (a primary source for the PID/decoder mappings) rather than fetched in full.*
