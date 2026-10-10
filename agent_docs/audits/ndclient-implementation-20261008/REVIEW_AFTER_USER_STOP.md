# NDClient review after the user's implementation stop

8 October 2026. Implementation is stopped. This document records two independent
read-only reviews: anti-slop/source fidelity and geometry/ECS ownership. Neither
review ran tests or edited production code. The current client is not accepted.
This receipt supersedes any implication in `RENDER_ORDERING.md` or the client
`docs/FOUNDATION.md` that raised doors and stairs were geometrically validated.

## Confirmed findings

1. **P1 — Exposed raised-floor underside at the disclosure frontier.**
   `NDClient/src/presentation/terrain.ts:45–49` places a complete lower earth tile
   beneath every known raised tile, but selects cliff faces only against known
   lower neighbors. In the reported recording, disclosed raised tiles stop at x=5;
   x=6 is undisclosed. The native scenario's raised area actually continues through
   x=8 (`tests/game/door_destruction_scenarios.py:114`). The visible earth strip is
   therefore not evidence that a physical cliff belongs there. Repair disclosed
   support presentation without turning unknown space into invented geometry.

2. **P1 — Static-wall depth and lighting use substitute geometry.**
   `NDClient/src/render/environment.ts:63` and `render/world-depth.ts:57` use ideal
   boundary planes without calibrated artwork thickness and faces. Independently,
   `presentation/lighting.ts:19` reconstructs zero-thickness light barriers.
   This does not meet the existing depth/material plan. Source registration should
   supply the shared geometry; another wall-specific shader exception is not the
   solution. This finding alone does not establish the detached door's cause.

3. **P1 — Newly revealed world assets can be drawn without preparation.**
   `NDClient/src/render/scene.ts:32–49` prepares terrain/environment mainly from the
   operation's before state; readiness checks cover effects only. A presented
   state revealing a new material or object can request an unprepared texture.
   The existing preparation owner must account for the compiled presented states.

4. **P1 — Multiple clocks break deterministic playback.**
   `NDClient/src/app/main.ts:87–91` advances `visualTime` even when effect readiness
   holds operation playback. `render/scene.ts:44–45` passes operation-local time
   to terrain/environment and a different clock to actors. Loops can restart at
   operation boundaries; idle actors can advance during buffering; replay does not
   restore their phase. Use the existing presentation time consistently and remove
   the redundant clock.

5. **P1 — Changing audience leaves stale pixels and pending work.**
   `NDClient/src/app/main.ts:42–56` clears JavaScript state without clearing the
   displayed canvas or invalidating an earlier asynchronous preparation. A failed
   connection can leave the prior audience visible; old preparation can install
   its program after a connection change. Repair the existing connection/scene
   lifecycle rather than adding another session system.

6. **P2 — Terrain registration is only partially consumed.**
   Cliff selection always draws one registered two-step rise for any positive
   height difference (`presentation/terrain.ts:49–59`). The stair shader also
   assumes exactly three supports and does not consume the authored contact
   registration (`render/terrain.ts:46–56,108`). The arbitrary-height problem is
   separate from the reported fixture, whose known drops are two steps.

7. **P2 — Cast equipment hiding is broader than the authored contract.**
   `NDClient/src/render/actors.ts:37` hides both weapon and offhand for the cast
   equipment `hidden` policy, whose recovered contract concerns the main weapon.
   Preserve slot-specific semantics in the existing appearance composition.

8. **Verification claim withdrawn.**
   `tools/world-support-check.mjs` captures raised-floor and stair screenshots but
   does not assert their placement. Its failure condition checks browser errors
   and animated water. The separate flat-floor insertion-order comparison is a
   valid narrower check; it does not validate these malformed scenes. The visual
   inspection should have rejected them.

## Door and actor size: established versus unresolved

The door looks detached in the supplied screenshots. Its exact cause has not been
established. The installed release retains and the client consumes its per-pose
pivots, scale, packed cells and depth calibration. Its optional surface geometry
is empty at source; it was not populated and then dropped by this renderer.

The frontend has no additional creature-size-category multiplier. It consumes
retained appearance scale and the established source-to-world tile conversion
`128 / 64`, plus camera zoom. That observation does not validate all appearances.
Natural artwork proportions remain the policy except explicitly authored animal
enlargement, halfling sizing and gameplay Enlarge/Reduce effects.

Before the user's stop, the parent removed Sorcerer/Barbarian cosmetic scale and
width overrides, removed the legacy goblin shrink, and restricted the generic SRD
size-based appearance table to beasts. Those edits are not independent approval
of the resulting complete sizing policy. Saved recordings still contain their
original appearance values. No production edits followed the stop. The cosmetic
overrides were not a user sizing instruction; their location in an existing
module does not transfer responsibility to the user.

## Actual position in the master plan

| Work | Current extent |
|---|---|
| Repository, references, asset copying, SDK | Present; complete copy is not complete runtime support. Native reach/cancellation amendment remains outstanding. |
| Shared renderer and event playback | Partial, with the confirmed defects above; raised-world placement is not accepted. |
| All authored content families | Incomplete; conditions/materials, construction, blood/ground and other operators still require integration. |
| Studio | Recording playback, timeline and inspection exist; canonical editing, A/B and save do not. |
| Playable application | Movement-oriented diagnostic app; full action UI, inventory, combat log and playable encounter are not delivered. |
| Final acceptance | Outstanding; the bounded checks and reviews do not certify the full client. |

The reviews support retaining the ordinary shared reducer/compiler/render owners.
They do not recommend another architecture or extra systems. The failure is ignored
registration and lifecycle contracts, insufficient visual verification, and too
much work concentrated on one partial rendering slice. No new benchmark quotas,
validation programme or implementation work is authorized by this receipt.
