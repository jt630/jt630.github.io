# Region: hands

The hands region owns all end-effectors that attach at the arm's wrist
interface. A hand does the actual touching — gripping, cradling, pressing,
threading — while the arm provides the reach and positioning. Three
end-effectors currently live here: the soft paw, the precision pincer, and
the fine tip. Each addresses a different slice of what elderly-care contact
looks like.

## Interfaces with other regions

- **arm — wrist handshake.** Every hand_* organ declares
  `slot: wrist-interface`. The arm_manipulator exposes this slot at its
  distal end. Currently the handshake is defined by the shared slot name;
  a formal wrist spec (connector type, locking mechanism, weight budget,
  signal lines for force feedback) is an open cross-lane request to the arm
  or core regions.
- **skin — indirect via composes_with.** The skin_vacuum organ references
  hand_paw_grip in its own `composes_with` list. The collaboration is
  one-way: the vacuum stabilizes the chassis while the paw manipulates. No
  direct region-to-region data link is needed.
- **brain — intent queue via arm.** Hands do not receive intents directly.
  The planner fires a manipulation intent at the arm, which carries the
  active hand to the target pose. Hand selection is part of the planner's
  organ-choice step.

## Key design decisions

- **Paw first, always.** When in doubt, use hand_paw_grip. It is the safest
  choice for any task involving elderly residents or fragile objects. Pincer
  and fine tip are escalations, not defaults.
- **When to escalate to pincer.** Object is smaller than 3 cm and needs
  a positive hold rather than a cradle, and there is no skin contact risk.
  Dropped keys, hearing-aid batteries, small cards.
- **When to escalate to fine tip.** The action is a press, nudge, thread,
  or plug — not a grasp at all. Buttons, ports, needles, touchscreens.
- **One hand at a time.** The wrist interface carries one end-effector per
  session. Swapping is a deliberate planner action with a brief setup cost.
  There is no automatic hand-change.
- **Force caps are hard.** Paw: 15 N. Pincer: 35 N. Fine tip: 8 N. These
  are not soft advisory limits — the safety monitor enforces them at the
  joint level and refuses override. Elderly skin and bones require this.

## Open questions

- Should the wrist interface carry a force/torque sensor shared across all
  hands, or does each hand manage its own contact sensing? A shared sensor
  would let the arm monitor contact regardless of which hand is loaded.
- Is a fourth end-effector warranted — something between paw and pincer for
  medium objects like a pill bottle or glasses case?
- Tool-change time (hand swap) is currently implicit in `deploy_time_ms`.
  Should there be an explicit `swap_time_ms` field to help the planner
  decide whether swapping is worth it mid-task?
