# Region: arm

The arm spans from the shoulder joint through the elbow to the wrist. It is
Goddard's primary positioning mechanism — the segment that moves a tool or
end-effector from the stowed pose to wherever the task requires it. The arm
itself does not grasp or press anything; it provides the reach, the angle,
and the controlled force envelope that lets hands and tools do their work
safely inside a home.

## Interfaces with other regions

- **core / thighs — shoulder handshake.** Power and bus connectivity arrive at
  the shoulder mount bay. The shoulder joint is the boundary where the arm
  region begins. A formal mount-bay spec for the shoulder (power pin-out,
  bus connector, alignment key) is needed from the core or thighs lane before
  the arm can be treated as hot-swappable.
- **hands — wrist interface.** The wrist exposes an active-tool mount bay.
  Any hand_* end-effector and any arm_* tool (e.g. arm_3d_printer) plugs in
  here. The wrist interface is currently defined implicitly by the
  `slot: wrist-interface` field; a formal wrist-handshake spec (locking
  mechanism, signal protocol, weight limit) would benefit both the arm and
  hands lanes.
- **brain — intent queue.** The arm receives manipulation intents from the
  planner via the core bus. It does not call the brain directly.
- **skin — no direct interface.** Skin-mounted gadgets are parallel organs;
  the arm does not route through or depend on the skin region.

## Key design decisions

- **One active-tool slot at the wrist.** The arm carries exactly one mounted
  tool or hand at a time. Multi-tool capability (a quick-change magazine) is
  explicitly left for a future iteration. For now, swapping the active hand
  or tool is a deliberate planner action, not an automatic behavior.
- **Skill-directory tier 2.** Whatever is loaded at the wrist is the
  session's tier-2 skill — immediately available, no setup cost. Swapping it
  introduces setup_time_ms and bumps to tier 3 for the incoming tool.
- **Soft speed cap near people.** 15 cm/s is the enforced ceiling when any
  human is within 80 cm of the arm's swept volume. This is non-negotiable —
  elderly residents may move unpredictably, and a fast arm is a fall risk.
- **Payload ceiling is 2 kg continuous, 3 kg peak.** The arm does not lift
  people and does not attempt to support a person's full weight.

## Open questions

- Does the shoulder bay support a second arm in a future revision, or is
  Goddard always single-arm? (Affects core mount-bay spec.)
- Should the wrist interface carry a torque sensor for tactile feedback, or
  is back-drive compliance on joint current sufficient for elderly-safe force
  limiting?
- Can the arm carry two tools simultaneously in a dual-slot wrist (e.g.,
  hand_paw_grip + a small light), or is the single active-tool slot firm?
