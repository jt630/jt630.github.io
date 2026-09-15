# CarVoice — Hardware Context

Point a session here for anything touching the physical OBD2 adapter, the
target vehicle, or hardware-in-the-loop testing. This context can't act on
hardware directly — it reasons about it, decides what to buy/try, and writes
down what happened.

## Read first
`CARVOICE.md` (architecture + Session 1 requirements) and
`data/carvoice/vehicles.yaml` (current registered vehicle, if any).

> **Updated 2026-09-15:** current recommendation is USB, not Bluetooth — see
> `carvoice/research/open-mechanic-review.md` §1. Prior art (`open-mechanic`)
> field-tested a USB adapter (plain serial port, no pairing) on a real
> vehicle; that supersedes the earlier Bluetooth Classic recommendation in
> `carvoice/research/hardware-options.md` for a first prototype.
>
> **Corrected same day, twice:** first corrected to OBDLink SX (~$40, cheaper,
> assumed the household only had a non-Ford Subaru). Then corrected back to
> **OBDLink EX** (~$60) once it came out that the household also has an
> existing **1999 Ford F-150** — SX and EX both support the F-150's protocol
> (SAE J1850 PWM, since it predates CAN entirely) equally well for CarVoice's
> own generic-OBD2 purposes, but EX's FORScan-compatible proprietary Ford
> access is a genuine bonus for the truck if FORScan itself is ever wanted
> for real Ford-specific work — not wasted spend once a Ford is actually in
> the picture. This also surfaced a real bug: `obd2_logger.py` had
> `OBD_PROTOCOL=6` (CAN) hardcoded, copied from open-mechanic's own newer
> CAN-based Ford — that would have failed against the '99 truck's J1850 PWM.
> Fixed to auto-detect with a per-vehicle cached value in `vehicles.yaml`.
> Lesson: always check what vehicle(s) are actually in play before picking
> hardware or a protocol default — don't assume "a Subaru" without asking.
> Corrected a third time: SX turned out to be **discontinued** anyway, with
> EX as its direct manufacturer replacement — EX is simply the current
> adapter to buy, independent of which vehicle is involved.

## Owns

- Adapter selection: ELM327 Bluetooth vs. WiFi vs. USB, brand/model tradeoffs, price
- Compatibility checks against the target vehicle (year/make/model in
  `data/carvoice/vehicles.yaml` — CarVoice targets OBD2, i.e. 1996+ only)
- Connection troubleshooting: pairing, port/IP config, `python-obd` connection
  string quirks per adapter
- Updating `data/carvoice/vehicles.yaml` with `obd2_adapter`, `vin`, and
  `added_date` once real hardware and a real car are in the loop
- Physical test log notes — what was plugged in, what worked, what didn't
  (append to `CARVOICE.md` Session Log, not a separate file)

## Hands off

- Writing the actual logger/diagnose code → **coder**
- General "what adapter models exist" research (no decision needed yet) →
  **research**; hardware makes the call once research has facts
- Verifying the logger's output format is correct → **qa**

## Hard rules

- Don't report a hardware integration as working without an actual device
  connected and a real drive log produced. "Should work per the datasheet" is
  a research finding, not a hardware result.
- Any cost figures (adapter price, shipping) should be real, current prices —
  not the $15/$30 manufacturing-cost placeholders from the original pitch doc,
  which describe unit economics at scale, not what a single hobbyist adapter costs.

## Out of scope

This context is not for the general car-buying research already happening in
`scripts/car_finder.py` / `car_buy_math.py` — those are about which car to buy;
this is about instrumenting a car once it's owned.
