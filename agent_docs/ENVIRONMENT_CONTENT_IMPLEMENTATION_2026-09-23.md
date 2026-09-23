# Freestanding environment content implementation

User authorization: implement the 21-object batch agreed in
[the intake record](ENVIRONMENT_CONTENT_INTAKE_2026-09-23.md). The three optional
objects are not included. Existing bed/table/chests/doors/traps remain intact.

## Observable contract

- Requested behavior: 21 real, registered, freestanding objects with their
  reviewed art, appropriate physical profiles and persistent native destruction.
- Boundary: authored item creation/placement, actual attacks, movement and sight;
  recorded subjective events consumed by the ordinary Pygame renderer.
- Input: place an intact object; nonlethal and lethal attacks; walk through its
  aftermath; initialize a late observer and replay saved events after reset.
- Output: correct footprint/height/blocking/HP; one same-UUID destruction with
  native physical consequences; authored finite break then stable wreck in all
  four camera views. Baked shelf/desk contents remain part of that one object.

## Bounded implementation

1. Extend the existing `WorldPropProfile` with passive native height and channel
   fields, preserving bed/table defaults. Author the 21 profiles in that ledger;
   the existing direct item table already consumes it. Reuse Health,
   `ItemDestructionProfile`, placement and `DestructionDebris`. No new behavior
   subclasses, event types, registries or generic support framework.
2. Author each object's footprint, HP, material tag, intact channel policy and
   optional difficult debris. Inspect the actual source registration and known
   footprint hints. Tall solid shelves/wardrobe need optical/propagation blocking;
   low objects must not inherit it indiscriminately. Native height is the existing
   coarse step envelope, not inferred from sprite padding. Destruction retains
   the footprint with nonblocking remnants; larger authored debris can retain
   the existing difficult-terrain cost. No new damage resistances or hazards.
3. Select one reviewed bank per subject from the exact September 23 handoff.
   Add declarations to `environment_prop_sources.json` and passive prop bindings
   to `environment_art.json`; package with the existing offline importer. Preserve
   pivots, four views, frame count/fps, source scale and stable final frame. Source
   hashes and preview systems do not enter the game. Keep existing media unchanged.
4. Extend the existing native prop scenario/clip catalog with data rows. Use real
   attacks and walking, both subjective observers, four camera views, saved event
   inputs and ordinary replay. Adjust the shared scenario only where actual new
   heights/footprints/HP require it, without scripting expected damage or state.
5. Verify native content and physical aftermath for all profiles; inspect tall
   sight blocking and multi-cell contact/rotation through existing queries. Verify
   representative public replay, finite animation/seek/late state plus all new
   bindings; run affected tests and typing. Generate and inspect the 21-case
   paired gallery, then document completion and any actual remaining limitation.

Explicitly outside this unit: fixtures awaiting visual approval, new containers
or loot children, liquid spills, lights, mounting, windows, buildings, multi-Z,
crafting, sitting and the concurrent Fireball spatial-rendering experiment.

## Review

Before implementation: independent **anti-slop reviewer** and **anti-OOP/ECS
reviewer** inspect this scope and the actual owners. Incorporate concrete findings
without reopening unrelated systems. Review the final changed implementation
against the same boundaries before reporting completion.

Both reviews approved before implementation. Anti-slop review required real
extra attacks for objects over 20 HP and full playback of the long stone banks.
ECS review required native sight/propagation checks and cold/late wreck coverage;
it explicitly rejected unnecessary unification of the existing content families.
Both subsequently approved the bounded changed implementation. Visual inspection
remains the root task's responsibility, not implied by those code reviews.

## Authored content choices

All 21 new objects use a one-cell coarse physical footprint at the existing art
scale. This is authored gameplay occupancy, not a claim of exact recovered mesh
geometry. The artist confirmed that the old stone-bench two-cell preview hint
was not a measured native contract, then supplied explicit authored placement
profiles in `house-prefabs/placement-profiles/profiles.json` under the art source.
Stone bench: centered 1.00 by 0.34 cells, coarse height one step. Large crate
stack: centered 0.96 by 0.96 cells, coarse height two steps. Both select the same
one-cell footprint used here; the obsolete preview hint is corrected. Source
pivots remain unchanged. Fine proxy geometry is source registration evidence,
not a new runtime collider. The existing bed continues exercising true multi-cell
behavior.

| Content | HP | Height steps | Blocks sight/propagation | Difficult debris |
| --- | ---: | ---: | --- | --- |
| Wardrobe | 24 | 2 | yes | yes |
| Bookshelf | 22 | 2 | yes | yes |
| Writing desk | 18 | 1 | no | yes |
| Bedside stand | 12 | 1 | no | no |
| Work stool | 8 | 1 | no | no |
| Storage shelving | 22 | 2 | yes | yes |
| Ingredient shelves | 20 | 2 | yes | yes |
| Preparation counter | 20 | 1 | no | yes |
| Sack bundles | 8 | 1 | no | no |
| Wooden chair | 10 | 1 | no | no |
| Wooden bench | 18 | 1 | no | no |
| Pottery jar | 6 | 1 | no | no |
| Pottery group | 10 | 1 | no | no |
| Pottery stack | 18 | 2 | yes | yes |
| Barrel cluster | 24 | 1 | no | yes |
| Crate stack | 20 | 1 | no | yes |
| Large crate stack | 30 | 2 | yes | yes |
| Animal statue | 36 | 2 | no | yes |
| Winged statue | 36 | 2 | no | yes |
| Stone pedestal | 27 | 2 | no | yes |
| Stone bench | 27 | 1 | no | yes |

All intact props obstruct ordinary walking. The narrower statue/pedestal
silhouettes leave sight and area propagation open under the existing cell model;
solid cupboards/backed shelves and compact tall stacks block them. Every wreck
is passable, has one-step nonoccupying placement and clears optical/propagation
blocking. Chosen larger remains retain the ordinary owned difficult-terrain cost.
The material values are existing tags, not new automatic resistances/hazards.

## Results

Implemented all 21 profiles through the existing world-prop builder and direct
item registration. The only production Python extension is three passive profile
fields for height, optics and propagation. The existing destruction event,
same-object identity, physical cascade, debris owner and presentation execute
the content. No per-prop behavior class or renderer branch was added.

The existing offline importer packaged 42 PNGs (8,526,671 bytes) with explicit
source declarations and prop bindings. Full authored frame counts remain intact,
including the 104-frame winged statue, 99-frame pedestal and 68-frame stone bench
at 12 fps. Their final frames provide persistent wrecks.

Validation:

- 52 native tests passed across world-prop debris, cold initialization and
  multi-cell objects. Coverage includes all profiles, same identity/footprint,
  HP, intact/wreck height and walking, cached sight/propagation reopening and
  owned difficult terrain.
- 38 prop presentation tests passed: real subjective packets replay after runtime
  reset, first-frame/contact continuity, all four cameras, full finite playback,
  stable remains, seeking and late observation.
- 20 selected direct-item registration/runtime tests passed. Total: 110 selected
  tests; this is not a full repository-suite claim.
- Scoped Pyright: zero errors and warnings. Scoped whitespace checks passed.
- All 42 gallery captures passed, with zero reported presentation gaps. Each
  object has separate attacker and witness inputs and a four-camera mosaic.

The new opaque objects exposed an old test assumption: a witness behind a solid
cupboard cannot necessarily see its attacker. Tests now check the saved sensory
facts instead of requiring an invisible attack gesture. Contact timing remains
tested for visible attacks; hidden-attacker destruction can begin immediately.
No visibility rule was changed to accommodate the clips.

[Review the 42 clips](http://127.0.0.1:8767/runs/20260923T145511Z-6d4722/index.html).
Saved inputs, native recordings, per-frame traces and videos are retained under
`.runtime/animation-review/runs/20260923T145511Z-6d4722/`. The shared scenario
performs actual nonlethal/lethal attacks, using additional turns where HP requires
them, then walks through the aftermath. Playback consumes those saved events.

Visual inspection sampled the cupboard, ceramic jar and winged-statue breaks and
settled remains in all four views, plus stone-bench placement. The source overview
was inspected for all 21 subjects. This is representative inspection, not a claim
of watching every frame or of user approval. The B3 large-crate source still
repeats its intact painted view across the four directions; its authored square
physical proxy is coherent, and no new directional artwork was invented here.

Reproduce with `python -m devtools.animation_review.capture --tag interiors-content`.
Use `python -m devtools.animation_review --tag interiors-content` to render the
saved inputs again without rerunning the native game.

User review accepted the rest of the appearance but identified visibility opening
while a destroyed object's strip still showed its intact first frame. See the
[clearance-timing correction](DESTRUCTION_VISIBILITY_TIMING_2026-09-23.md) for the
shared authored timing field and updated six-object review.
