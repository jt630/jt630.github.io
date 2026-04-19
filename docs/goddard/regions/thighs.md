# Region: thighs

The thighs region connects the legs to the body. Physically, it is the
hip-level assembly that holds everything together — four high-torque joints
(`thigh_joint`) and the power rail that feeds them (`thigh_power_route`).
Without the thighs, the legs have nowhere to attach and nothing to drive them.

That makes the thighs region load-bearing in two senses: mechanically, it
carries the chassis weight down into the leg assemblies, and electrically,
it routes power from the core bus out to every leg actuator. Both paths run
through here, and both operate at all times whenever the robot is upright.

The most important safety commitment this region makes is the **balance
authority reserve**. Under normal operation, power is plentiful and
everything runs freely. Under a battery low-warning, `thigh_power_route`
begins shedding non-essential load — and the last thing it ever surrenders
is the wattage needed to hold balance and a safe standing pose. A robot that
falls over during a power sag is a hazard to anyone nearby. This region
ensures that never happens.

Interfaces with:

- **legs** — `thigh_joint` receives balance corrections from the 100 Hz
  sub-loop owned by `leg_walk`, and holds a locked hip angle during wheel
  transit. The hip is the physical handoff point between the two regions.
- **core (power bus)** — `thigh_power_route` draws directly from
  `core_power_bus` and monitors `core_battery` state each tick.
- **core (reflex loop)** — both organs report state each 10 Hz tick; the
  reflex loop can inspect joint temperature and power allocation without
  polling.
- **core (safety monitor)** — thermal and torque flags from `thigh_joint`
  are evaluated by the safety monitor; a joint that exceeds thermal limits
  halts and reports before hardware damage can occur.

Key decisions:

- Balance authority always has power priority. The `brown_out_priority`
  order in `thigh_power_route` is: balance hold → safe pose →
  non-motion sensors → locomotion. Locomotion yields first; balance never
  yields.
- The hip joint uses jerk-limiting on all corrections. Smooth motion at the
  hip prevents the robot from making sudden movements near a resident even
  when absorbing a balance correction at 100 Hz.
- `thigh_joint` refuses commands that would exceed `max_torque_nm` rather
  than straining through them. The joint halts in place and reports; it does
  not damage itself silently.

Open questions:

- Hip load spec: what is the maximum chassis-plus-payload weight the joints
  must plan for? The legs region should provide an expected load estimate so
  `thigh_joint` can calibrate torque scaling accurately.
- Cross-region interface with the chassis/skin lane: the joint housings sit
  inside the physical chassis frame. Does the skin region own the panels that
  enclose the hip assemblies, and if so, where is the boundary?
- Thermal dissipation path: at full load (32 W across four joints), heat
  needs somewhere to go. A future skin or chassis lane should define the
  thermal interface at the hip housing.
