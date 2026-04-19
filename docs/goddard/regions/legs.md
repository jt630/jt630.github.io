# Region: legs

The legs region is responsible for all locomotion — getting Goddard from one
place to another safely and smoothly. It owns the walking gait (`leg_walk`) and
the wheeled transit mode (`leg_wheel`), and it runs the **100 Hz balance
sub-loop** that keeps the robot stable every moment it is standing or moving.

That balance sub-loop is worth naming clearly. The main reflex loop runs at
10 Hz — plenty fast for most decisions. But balance corrections need to happen
faster than the eye can see, because a small wobble at 10 Hz becomes a stumble
on the next step. The legs region runs its own 100 Hz inner loop, feeds the
resulting state back into the core reflex loop each tick, and never lets the
core tell it to slow down. Stability is always the first obligation.

Interfaces with:

- **thighs** — the hip joint (`thigh_joint`) connects leg to chassis. The legs
  region drives joint angles; the thighs region provides the actuated hardware
  and absorbs balance corrections.
- **core (reflex loop)** — `leg_walk` and `leg_wheel` are `owned_by: goddard`
  and run under the reflex tick. The 100 Hz balance sub-loop reports state
  to `core_reflex_loop` each main-loop tick.
- **core (safety monitor)** — all preconditions are evaluated before and
  during locomotion. The safety monitor can abort a gait mid-stride.
- **core (power bus)** — power flows via `thigh_power_route`; balance authority
  is protected even under brown-out.

Key decisions:

- Two locomotion modes coexist (walk and wheel) rather than one. Walk handles
  terrain variation; wheel handles smooth open floors quietly and efficiently.
  The robot chooses based on floor-type sensing, never the other way around.
- Elderly-care gait caps are hard-coded, not advisory. Speed near a resident
  drops to 15 cm/s or below. Near a detected fall event it drops further, to
  8 cm/s — a cautious approach, never an urgent rush.
- No stair descent without `handrail_assist_active`. The precondition is a
  guard, not a preference.

Open questions:

- What is the handrail-assist organ? This is a stair-assist path not yet
  scaffolded. The legs region needs a cross-region interface to whatever arm
  or gadget provides this capability.
- What is the floor-type sensing organ? `leg_wheel` depends on a `floor_type`
  precondition. The sensing region should own this; legs needs to consume it.
- Hip load spec: thighs needs to know the maximum load (in grams) the hip joint
  should plan for. Legs should provide an expected chassis-weight estimate.
