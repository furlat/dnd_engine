# V0 doorway presentation follow-up

## Scope and evidence

The user reported a dark diamond outside the closed door and an awkward
door/masonry join. These are presentation diagnostics, not permission to
change engine optics, placement, or door state.

The real closed/open/reclosed event sequence makes support `(32,31)` authored,
then visible/dim, then remembered. The renderer multiplies remembered terrain
by `(0.38,0.40,0.46)` but never-seen authored terrain by `(0.62,0.62,0.62)`.
The resulting isolated dark diamond resembles a cast shadow in this explicitly
full-structural debug view. No shadow caster produced it.

The D6 arch contains the brown underside visible above the leaf. The imported
D6 and A1/A2 occurrences have their actual different pivots: `(128,207.36)`
and `(128,209.92)`, respectively, both at scale `128/127`. The example scene
uses the same contact and a later door layer. Adjacent D7 window walls have the
same structural outline as our D1 wall. Thus source identity/pivots alone do
not demonstrate a placement error. The four-camera diagnostic comparing leaf
last versus all masonry last shows that the latter hides exposed open leaves.
It is not an accepted correction. The user-visible join remains a visual
acceptance concern; do not report it fixed on the strength of source metadata.

## Bounded correction

For this full-structural V0 view only, give the existing `memory` treatment the
same neutral RGB as `authored`: `(0.62,0.62,0.62)`. Retain its `memory.seen`
identity, reduced `seen`/`visible` data, missing current light value, frozen
remembered Water, and subjective door/torch disclosure. Current terrain keeps
its engine-supplied light treatment. No events, reducer, map, projection,
surface cache, layering, pivots, assets, or backend code change.

This explicitly supersedes only the darker memory RGB required by the earlier
full-map/neutral-boundary plans. It is not a claim that remembered space has
become visible or illuminated. Diagnostics still identify memory separately.
No new display mode, switch, shadow model, mask, sprite split, offset, or
occlusion framework is authorized.

## Implementation and validation

- Production: one RGB row in `game/data/world_bindings.json`.
- Regression: extend the existing real-frame test in
  `tests/game/test_app_smoke.py`. Through the real event sequence and published
  frames, assert a fixed unobstructed patch inside `(32,31)` is identical at
  startup and after reclosing, while the published provenance changes from
  authored to memory and open-door current light remains dim. Verify the
  selected patch actually contains rendered terrain pixels.
- Run that test red before the data correction, then green, complete pygame
  tests, and diff-check. No engine tests are rewritten.
- Capture and inspect all four camera views for closed/open/reclosed states,
  at the same map focus. Do not reuse a mutable target across saved states.
- Keep the doorway join concern explicit if removing the contrast does not
  resolve its appearance. A different local ordering or leaf placement needs
  its own demonstrated geometry rule, not an arbitrary patch here.

## Reviews and next work

Before implementation: correctness, anti-slop, and anti-OOP/ECS reviewers must
check this bounded change. Re-review the actual correction afterward.

After this bounded correction, the next work is the user's requested height
and stair asset investigation/plan, not height implementation. That plan must
carry any unresolved doorway overlap/visual-acceptance issue as a prerequisite
and must not claim the present global layer order already handles elevation.

## Result

Implemented only the RGB row and the existing real-frame test extension.
The regression failed on the old darker pixels, then passed with neutral
memory RGB. Complete `tests/game`: **201 passed in 92.81s**. Repository
diff-check passed with existing line-ending notices only.

Correctness, anti-slop, and anti-OOP/ECS reviewers approved the plan and actual
limited correction. The anti-slop reviewer independently compared the test's
5-by-5 framebuffer patch to isolated terrain pixels for each of the three
states, confirming it is not a door, HUD, or grid-line artifact.

Fresh closed/open/reclosed four-camera captures were inspected. The isolated
dark diamond is gone. The door still uses the original imported assembly:
the doorway join has **not** received a new geometry fix or final human visual
acceptance. Keep that distinction when handing off the height plan.
