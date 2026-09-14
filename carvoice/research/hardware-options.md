# CarVoice Hardware Research: ELM327 OBD2 Adapters

**Scope:** per `carvoice/agents/hardware.md`, this is the "what adapter models
exist" research pass — no purchase has been made, no decision is final. The
`hardware` agent context makes the actual buy call using these facts.

**Research date:** 2026-09-14. OBD2 adapter pricing on Amazon/eBay/AliExpress
moves constantly (sales, counterfeit listings undercutting real ones, etc.) —
**re-check current price and read the most recent reviews on the exact listing
before buying**, don't trust the numbers below as final.

Target vehicle context: household is mid-shopping for a Subaru Forester per
`scripts/car_buy_math.py` / `car_finder.py` (candidate model years 2019–2026,
i.e. all CAN-bus OBD2 Foresters — see compatibility notes below). No vehicle
is registered in `data/carvoice/vehicles.yaml` yet.

---

## 1. Adapter models on the market

### Reliable / name-brand

| Model | Type | Approx. price (Sept 2026) | Chipset | Notes |
|---|---|---|---|---|
| **OBDLink MX+** | Bluetooth Classic + BLE | ~$140 | ScanTool's own **STN2120** silicon — *not* an ELM327 clone | Widely regarded as the reliability benchmark. Supports all 5 OBD2 protocols simultaneously, fast, proper low-power sleep (<2mA idle) so it won't drain a parked car's battery. One of the few adapters that connects to a laptop as cleanly as a phone. |
| **OBDLink CX** | BLE 5.1 | ~$80 | ScanTool STN-series | Purpose-built for BMW/Mini + BimmerCode. Excellent build quality but a specialty product — not the general pick for a generic-PID Subaru logger. |
| **BAFX Products 34t5** | Bluetooth Classic (SPP) | ~$20–30 (seen $20–40 depending on retailer/sale) | ELM327-compatible, well-regarded implementation | Basic, cheap, but consistently reported as reliable rather than flaky. One review explicitly lists **Subaru** among vehicles it was tested working on (alongside Honda, Toyota, Jeep). 2-year manufacturer warranty. |
| **Veepeak OBDCheck BLE / BLE+** | BLE 4.0 | ~$25–32 (BLE), ~$42 (BLE+) | Veepeak's BLE implementation | "Budget baseline" pick per multiple review sites — no random drops reported, supports all 5 OBD2 protocols. BLE-only (see §3 caveat on python-obd). |
| **Veepeak Mini (Bluetooth)** | Bluetooth Classic | ~$14–20 | ELM327-compatible | Cited as "best budget adapter under $20," no random disconnects reported. |
| **Vgate iCar Pro BLE 4.0** | BLE 4.0 | ~$25–32 | Newer "2.3" chip generation | 4.5–4.6★ across thousands of reviews, has a real sleep mode. BLE-only. Doesn't expose ABS/SRS systems (not relevant to CarVoice's generic-PID scope). |

### Flaky / known clone-complaint category

- **Sub-$10 no-name "ELM327" listings** on Amazon/eBay/AliExpress. This is the
  single biggest complaint category in every forum thread and review site
  checked: dropped connections mid-scan, incorrect readings, failure on
  modern CAN-bus vehicles, and — reported repeatedly — battery drain if left
  plugged in because they lack a real sleep mode.
- **Counterfeit PIC18F25K80-branded clones**: a well-documented fake variant
  uses a relabeled "QBD327" chip pretending to be the genuine Microchip
  PIC18F25K80. Tells: blurred/wrong Microchip logo, a 16MHz crystal instead
  of the correct 4MHz, bogus third-line date-code strings, and failure to
  respond to the `ATPPS` command (genuine chips support it, fakes don't).
  Source: FORScan forum's "Known problems with china clones of ELM327"
  thread, and the CVTz50 buying guide.
- **Panlong ELM327** (Bluetooth and WiFi variants): repeatedly described as
  "hit-or-miss on pairing reliability," Android-oriented, and — for the WiFi
  version — lower throughput and no enhanced/manufacturer-code support
  compared to name-brand options. Cheap but not a confidence-inspiring first
  buy.

**Bottom line on chipsets:** favor adapters that either (a) use ScanTool's
own STN11xx/STN22xx silicon (OBDLink line — a faster reimplementation, not a
clone) or (b) explicitly and verifiably use a genuine ELM327-compatible
PIC18F25K80 with the correct crystal/firmware. Avoid anything under ~$10 with
no brand accountability.

---

## 2. Subaru-specific compatibility notes

- **Generic OBD2 (what CarVoice Session 1 needs) is not a problem.** Every
  US-market Subaru 1996+ is legally required to expose standard Mode 01 PIDs
  (RPM, coolant temp, vehicle speed, calculated engine load, fuel level,
  active DTCs — exactly CarVoice's target PID set) over a standard protocol.
  A 2014+ Forester communicates over **ISO 15765-4 CAN, 500kbps, 11-bit
  ID** — a protocol every modern ELM327-class adapter auto-detects. Older
  (pre-CAN-era, roughly pre-2008) Subarus use ISO 9141-2 or KWP2000 instead,
  which is also standard and also auto-detected — not a special case, but
  worth knowing if the household ends up with an older used Forester than
  the 2019+ candidates currently in `car_buy_math.py`.
- **Do not confuse this with Subaru's SSM protocol.** Subaru Select Monitor
  (SSM1/SSM2) is a completely separate, proprietary, non-OBD2 diagnostic
  protocol Subaru dealers/tuners use for enhanced data — individual sensor
  voltages, fine fuel-trim correction, boost, etc. — running at a nonstandard
  1953 baud with its own framing. **Plain ELM327 AT-command adapters cannot
  speak SSM at all** (see LegacyGT.com "stn1110 vs elm327 vs clone" thread
  and the Torque forum's "Subaru SSM protocol" thread) — that requires a
  purpose-built SSM cable/tool (e.g. FreeSSM, RomRaider) which is a different
  product category entirely. **This is irrelevant to CarVoice Phase 1**,
  since the plan only targets generic Mode 01 PIDs — but if a future session
  wants Subaru-specific enhanced data, that's a separate hardware/software
  problem, not "buy a better ELM327."
- **The anecdotal "ELM327 useless on my Forester" complaints found (e.g. the
  FT86CLUB "no protocol found" thread) trace back to clone-quality issues,
  not a Subaru-specific gap** — the same forums and review sites report
  name-brand adapters (BAFX 34t5 explicitly, OBDLink implicitly via its
  "all vehicles" positioning) working fine on Subarus. Read as: Subaru
  doesn't need special handling, but a bad clone will fail on a Subaru the
  same way it fails on anything else.
- No Subaru-specific "missing standard PID" quirks turned up beyond the
  universal caveat that every manufacturer only guarantees the PIDs Mode 01
  requires — enhanced/optional PIDs vary by ECU regardless of make.

---

## 3. Connection-type reality check for `python-obd` (important finding)

The Session 1 plan frames this as "WiFi or BLE, whichever is easiest with
python-obd on a laptop." Research says: **neither is the easy path — classic
Bluetooth (SPP) is.**

- `python-obd` talks over a serial connection under the hood (pyserial).
- **Bluetooth Classic (SPP profile)** — the "Bluetooth 2.x/3.0/4.0 Classic"
  mode that BAFX 34t5, Veepeak Mini, and OBDLink MX+ all support — pairs at
  the OS level as an ordinary virtual COM port (Windows) or `/dev/rfcomm*`
  / `/dev/tty.*` device (Linux/macOS). `python-obd` auto-detects or accepts
  that port string directly, with **no extra code**. This is the turnkey
  path.
- **BLE (Bluetooth Low Energy)** — the mode Veepeak OBDCheck BLE/BLE+ and
  Vgate iCar Pro BLE 4.0 use — does **not** expose a serial port over GATT.
  Talking to a BLE-only adapter from Python means writing (or adopting) a
  BLE-to-serial bridge, e.g. via the `bleak` library — `python-obd` doesn't
  do this natively. Home Assistant's ELM327-BLE integration is built exactly
  this way, as a separate `bleak`-based layer, not stock `python-obd`.
- **WiFi** adapters expose a raw TCP socket (commonly port 35000). Mainline
  `python-obd`'s WiFi support is murkier than expected: GitHub issue
  [`brendan-w/python-OBD#107`](https://github.com/brendan-w/python-OBD/issues/107)
  shows a user's `socket://192.168.0.10:35000` connection string failing
  because pyserial's socket URL handler wasn't being invoked as documented —
  the issue closed with no confirmed fix landed in mainline. Community forks
  (`dailab/python-OBD-wifi` and further forks by `pgreenland` and
  `nvladimirovi`) exist specifically to patch in working WiFi support, which
  means the WiFi path likely means installing a fork instead of `pip install
  obd`, not zero extra effort.

**Implication for the coder/hardware agents:** an adapter that does
**Bluetooth Classic (SPP)** is the actual path of least resistance for
`python-obd` on a laptop today, not WiFi or BLE.

---

## 4. Recommendation

**Buy: OBDLink MX+ (~$140).**

Reasoning:
- It supports **Bluetooth Classic**, so it plugs into `python-obd` the
  turnkey way described in §3 — no BLE bridge, no WiFi fork — while also
  keeping BLE as a fallback if a future session wants a phone-app path
  instead.
- Its STN2120 chipset sidesteps the entire "is this clone flaky" question
  that dominates the cheap end of this market — it's not an ELM327 clone at
  all, it's ScanTool's own faster, more complete reimplementation.
- Real sleep mode (<2mA idle) matters here specifically because Session 1's
  plan is to leave hardware plugged into a real car during dev/test — a
  flaky or sleep-less clone risking a dead battery on the household's likely
  first (recently purchased or about-to-be-purchased) Forester is a real
  cost, not a hypothetical.
- Per `carvoice/agents/hardware.md`'s hard rule ("reliability > price for a
  first prototype"), removing the adapter itself as a variable is worth the
  premium: if the logger fails against real hardware, the failure will be in
  the script or the PID set, not "was it the $12 clone."

**Budget fallback if $140 feels like too much to spend before Session 1 has
proven anything: BAFX Products 34t5 (~$25–30).** It's genuine Bluetooth
Classic SPP hardware (same turnkey `python-obd` path as the MX+, unlike the
BLE-only budget options), has multiple independent reports of working
specifically on Subarus, and is cheap enough to treat as disposable — if it
turns out flaky, the MX+ purchase isn't a second sunk cost, it's the planned
upgrade.

**Explicitly avoid for this prototype:**
- Any sub-$10 no-name ELM327 listing (flaky-clone category, §1).
- BLE-only adapters (Veepeak OBDCheck BLE/BLE+, Vgate iCar Pro BLE 4.0)
  *unless* the hardware/coder agents are prepared to add a `bleak`-based BLE
  bridge on top of `python-obd` — that's extra scope Session 1 doesn't need.
- WiFi-only adapters *unless* committing to a community fork of `python-obd`
  instead of the stock `pip install obd` package.

**Not blocked on the car purchase.** All Forester model years currently in
`scripts/car_buy_math.py`'s scenarios (2019–2026) are CAN-bus OBD2 vehicles
with no SSM-related gap in the generic PID set CarVoice targets (§2), so this
adapter recommendation holds regardless of which specific used/new Forester
the household ends up buying — the adapter can be bought before the car is.

---

## Sources

- [OBDLink MX+ product/pricing page](https://www.obdlink.com/lp/mxp-1a/) and [Amazon listing](https://www.amazon.com/OBDLink-Bluetooth-Professional-Grade-Diagnostic-Performance/dp/B07JFRFJG6)
- [Iamcarhacker: OBDLink MX+ Review](https://iamcarhacker.com/obdlink-mx-review/)
- [OBDLink CX product page](https://www.obdlink.com/products/obdlink-cx/)
- [Veepeak OBDCheck BLE Amazon listing](https://www.amazon.com/Veepeak-OBDCheck-Bluetooth-Diagnostic-Supports/dp/B073XKQQQW) and [BLE+ listing](https://www.amazon.com/Veepeak-Bluetooth-Diagnostic-Supports-Vehicles/dp/B076XVQMVS)
- [Iamcarhacker: Veepeak Review](https://iamcarhacker.com/veepeak/)
- [Iamcarhacker: Vgate iCar Pro BLE 4.0 Review](https://iamcarhacker.com/vgate-icar-pro-ble4-0-owners-review/)
- [Vgate iCar Pro Amazon listing](https://www.amazon.com/Vgate-iCar-Bluetooth4-0-OBD2-Splitter/dp/B09MHY5P1R)
- BAFX Products 34t5 reviews: [ScannerAnswers](https://scanneranswers.com/bafx-products-34t5-review/), [BestOBD2Scanners](https://bestobd2scanners.com/bafx-34t5-review-bluetooth-obdii-scan-tool/), [NAXJA Forums thread](https://naxja.org/threads/obdii-bluetooth-adapter.1133389/)
- [FORScan forum: "Known problems with china clones of ELM327"](https://forscan.org/forum/viewtopic.php?t=1575&start=30)
- [CVTz50: How to buy proper ELM327 v1.5](http://cvtz50.info/en/elm327/)
- Subaru SSM protocol: [LegacyGT.com "stn1110 vs elm327 vs clone vs etc"](https://www.legacygt.com/topic/107640-stn1110-vs-elm327-vs-clone-vs-etc/), [Torque-BHP "Subaru SSM protocol" thread](https://torque-bhp.com/community/main-forum/subaru-ssm-protocol/paged/5/), [FreeSSM discussion, subaruoutback.org](https://www.subaruoutback.org/threads/freessm-complete-access-to-your-ecm-and-tcu.39426/)
- [FT86CLUB: "ELM327 OBD2 adapter + Torque = no protocol found"](https://www.ft86club.com/forums/showthread.php?t=77516) (Subaru BRZ platform)
- Forester OBD2 protocol confirmation: [subaruforester.org "2017 - OBD2 protocol?"](https://www.subaruforester.org/threads/2017-obd2-protocol.831986/), [subaruforester.org generic PID list](https://www.subaruforester.org/attachments/subaru-pid-list-pdf.569001/)
- [`brendan-w/python-OBD` GitHub repo](https://github.com/brendan-w/python-OBD) and [issue #107 (WiFi socket connection)](https://github.com/brendan-w/python-OBD/issues/107)
- [`dailab/python-OBD-wifi` fork](https://github.com/dailab/python-OBD-wifi)
- Clone-detection background: [general ELM327 buyer guides](https://www.carscanner.info/choosing-obdii-adapter/), [OBDadvisor ELM327 roundup](https://obdadvisor.com/elm327/)

*Prices and specific product listings above were current as of this
research session (Sept 2026) and are known to drift — Amazon/eBay/AliExpress
listings for this category churn constantly, including counterfeit listings
undercutting genuine ones. Re-verify price and read the current top reviews
on the exact SKU before purchasing.*
