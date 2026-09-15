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
> **Corrected same day:** open-mechanic's specific pick (OBDLink EX, ~$60)
> is Ford-*optimized* (FORScan/MS-CAN support) — their own test vehicle was
> a Ford. For this household's Subaru, use **OBDLink SX** instead (~$40) —
> same standard OBD2/CAN coverage, same USB-serial connection to
> `python-obd`, without paying for Ford-only features. Use EX only if the
> target vehicle is ever a Ford/Lincoln/Mercury.

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
