# CarVoice — Hardware Context

Point a session here for anything touching the physical OBD2 adapter, the
target vehicle, or hardware-in-the-loop testing. This context can't act on
hardware directly — it reasons about it, decides what to buy/try, and writes
down what happened.

## Read first
`CARVOICE.md` (architecture + Session 1 requirements) and
`data/carvoice/vehicles.yaml` (current registered vehicle, if any).

## Owns

- Adapter selection: ELM327 Bluetooth vs. WiFi, brand/model tradeoffs, price
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
