# Directed body releases and persistent floor material

Current qualification update: [spell body releases](SPELL_BODY_RELEASE_2026-09-20.md)
supersedes the physical-only filter described below. All positive normal-HP
injuries can release the configured creature material; a positive physical
component still selects its original pattern when present.

Implemented on `codex/recovery-design` against the independently reviewed
[plan](BODY_RELEASE_IMPLEMENTATION_PLAN_2026-09-20.md). Final [gameplay gallery](http://127.0.0.1:8767/runs/20260919T230628Z-0a2658/index.html): **40/40 clips passed**,
3,503 synchronized four-camera frames, replayed from saved public inputs.
Representative airborne, settled, material and raised-floor frames were inspected.
All automated clip checks passed. Four opportunity cards still report the missing
fixed-goblin decorative slash overlay `smallscale.goblin01/Attack2/slash/Slash2`;
this is a visible media gap, not a failed body-release/floor-state check. It is
retained in each exported trace and is not claimed fixed by this unit.

## What now owns the behavior

- The creature's existing `BodyResponseHandler` admits actual physical HP loss.
  Weapon damage supplies its own impact direction and actual critical result.
  The strongest positive post-affinity physical component selects piercing,
  slashing or blunt geometry; directionless causes remain local. A nested trap
  does not borrow an enclosing attack's critical or direction.
- Native receiving ellipses use existing propagation and same-height support
  along the finite supercover route. Each receiving tile gains one unit per
  injury even where ellipses overlap. Doors block/admit through their native
  state. Height discontinuities and absent supports reject deposition.
- Existing tile conditions own passive local contributions and capped amount.
  Identical footprints coalesce; changed directions remain separate until the
  cap. Saturation preserves condition identity, amount and geometry. Existing
  corrosive damage and dread entry/retreat mechanics stay on these actual tiles.
- Subjective recording retains permitted receiving regions and local current
  geometry. A later observer reconstructs floor material without donor history,
  airborne replay, access to a live entity, or a native engine rerun.
- Existing action-media tracks bind a normalized template to each native region.
  The source remains the historical wound contact, including during a paused
  opportunity attack. Absolute samples land at fixed world destinations.
  Criticals add a transient copy; final deposited geometry and amount are equal.
- The floor samples each original ellipse intersected with its owning tile.
  It does not refit a template per cell. Accepted contribution increments reveal
  at particle landing times on the same historical clock; earlier marks remain.
  Engine completion does not wait for presentation.

The new native values are `ResidueEllipse`, `ResidueContribution`,
`BodyReleaseRegion`, and additive fields on the existing release/tile result.
The presentation extension is passive `LandingTemplate`/`RegionParticleStyle`
data on `ParticleMediaAsset`, plus `ResidueReveal` values. There is no new
entity, handler registry, event queue, fluid simulation, or renderer clock.

## Imported artwork and compatibility

The asset task delivered four normalized templates of 28 particles, with liquid
kernels and bone polygons. Blood, bone, corrosive and dread are bound; poison is
available as artwork without a new gameplay profile. The checked-in portable
value document is `game/data/neuroclient/body-release-regions.json`. Its original
source was the asset task's `output/environment-sprites/body-release-regions/templates.json`
in worktree `23a9`. No Godot, TypeScript or source archive is needed at runtime.
This compact region artwork is an integrated visual review candidate; code review
and successful clip extraction do not claim human approval of its appearance.

The old approved 96-particle blood source remains available as a reference.
Old recordings without geometric release fields retain their original strip and
floor behavior. AIR injuries retain the existing transient strip and no deposit;
this unit adds neither flight mechanics nor airborne floor collision.

The mace clips revealed a missing resource import. Fourteen original `Melee9`
PNG sheets (1,704,995 bytes) were copied from NeuroClient and bound, with the
existing offline import selection updated. No replacement weapon was invented.

**Clipped-edge limit:** every observer uses the same canonical trajectory.
An airborne particle is culled if its endpoint is not an admitted disclosed
piece. Floor kernels still reconstruct locally and clip to the owning tile,
including portions whose center lies outside that piece. Such a small edge
portion can reveal at its authored arrival without a visible matching droplet.
Redirecting particles toward the observer's visible cells would give observers
different trajectories, so the implementation deliberately avoids that shortcut.

## Verification and measured costs

- Focused native, saved subjective replay, shared playback and floor geometry:
  **101 passed**. This includes normal/critical weapons, rotation/reversal,
  repeat accumulation, physical admission, raised supports, doors, later sight,
  held opportunity contact, absolute seek, cache reuse and unchanged saturated
  marks. The packaged skeleton also completed its actual paired clip capture.
- Affected native and presentation modules: **Pyright clean**.
- Broader architecture/recovery/boundary run: **163 passed, 14 failed**.
  These are not reported as a green whole-repository run. See the inventory below.
- Independent final ECS/anti-OOP and anti-slop reviews approved the implementation.
  Additional reviewer probes covered overlapping reveal deltas, future deltas,
  replacement condition IDs, and surviving/lethal opportunity reveal offsets.

The first floor timing test exposed a real binding mistake: anchor staging had
already supplied the final world tiles. Comparing against that staged value
produced no reveal. The fix compares historical `displayed_before` values, while
retaining existing anchor staging for animation. Tests assert that marks are
absent before landing and that previous marks persist during the next injury.

One WSL measurement, source on `/mnt/c`, Python environment on Linux, dependencies
already imported:

| Work | Elapsed |
| --- | ---: |
| Scenario construction, seven real attacks/turns and paired private capture | 583.15 ms |
| One observer's projection and public JSON encoding | 4.72 ms |
| Public decode and initialization reduction | 2.37 ms |
| Reduce all roots and bind the seven injuries | 3.68 ms |

That public packet was 298,201 bytes. These are distinct stages, not a claim
that native damage alone takes the entire scenario time or that rendering is
included in gameplay timing.

The reviewer's same five-distinct-slashing-deposit floor probe measured:

| Floor operation | Initial implementation | Final |
| --- | ---: | ---: |
| Cold construction of 15 ellipses on one tile | 36.54 ms | 32.31 ms |
| Active updates at selected landing masks | 29.88–36.76 ms | 1.62–8.31 ms |
| Settled recomposition | 36.83 ms | 0.88 ms |
| 1,000 repeated settled reads | — | 4.22 ms total, no rebuilds |

The final renderer retains per-ellipse numerical fields, so a new contribution
does not rebuild old deposits. Numerical fields have an 8 MiB bound; existing
rendered surfaces retain their 32 MiB bound. The probe retained 376,832 bytes of
fields. Cold construction of a densely marked newly encountered tile remains a
measurable cost. No source hashes, startup media scan or idle field regeneration
was added.

## Broader test failure inventory

The 14 failures lie in these existing test areas; this unit did not rewrite their
expectations to make the run pass:

- `test_content_recovery_cr0_evidence`: 3 frozen artifact/count expectations.
- `test_content_recovery_cri_direct_items`: 5 frozen artifact/registry/overlay
  count expectations against the expanded gameplay content.
- `test_dependency_boundaries`: 3 failures — the retired server imports removed
  `dnd.core.senses`, a historical canonical-name assertion also finds the
  presentation `EquipmentSlot`, and the same retired server import violates its
  old cold-leaf list. The import-cycle test passed.
- `test_spell_catalog_composition`: 1 retired server import failure through
  `server/world_contracts.py` and removed `dnd.core.senses`.
- `test_presentation_boundary`: 2 historical assumptions about exact copied-event
  equality and copying an immutable `PerceivedContact` instead of sharing it.

A separate fixture investigation also found that editing floor elevations after
world initialization was not reflected in these captures' starting public tile
values, even through the world-authoring API. Only a later injury's changed tiles
then revealed their current height. That is a concrete follow-up for world-edit
initialization/recording, not a blood geometry or cliff-rendering fix. The final
height cases use the existing cold-authored terrace and verify both observers'
initial heights. No snapshots or successful gameplay events were fabricated.

## Review and follow-up boundary

The final gallery uses the `body-release-regions` catalog tag. Cases exercise
piercing/slashing/blunt, all three critical counterparts, north/reverse direction,
open/closed doors, a raised terrace and its edge, seven-hit saturation, modular
and packaged skeletons, both demonic materials, later sight, and surviving/lethal
opportunity attacks. Each experiment is captured once for its two observers and
replayed from saved player JSON into four camera views. Replay includes compact
floor-reveal timing in debug traces.

Cross-height deposits, wall staining, wider skill-authored regions and blood
consumption/interactions remain future design work. The asset task's newer broad
splat/skill controls are an art proposal; they do not silently expand native
geometry, quantity or hazard rules here.


### Subsequent weapon-motion correction

The user found that the piercing critical video played a sweeping body attack.
The native release pattern was correct; a higher-precedence imported critical
recipe selected the wrong body motion. The
[weapon-motion correction](WEAPON_ANIMATION_AND_FACING_2026-09-20.md) records the
subsequent authored weapon overrides, damage-type defaults, dagger overhead
critical and deliberate frontal/rear review poses. Its gallery supersedes the
corresponding weapon-motion examples here; this original result remains history.


### Art-task comparison after gore feedback

The art task confirmed the four compact templates, palettes and timing still
match its current handoff. Direct comparison also verified the actual embedded
asset values in the latest gallery's accumulation trace. There is no newer,
larger replacement template awaiting import. What came later was a wider
art-only layout preview: seven patches / spread 2 / size 1.6, touching 12
alpha-covered tiles instead of the base's two at the first amount stage.

Current game coverage and quantities remain deliberately narrower: the dagger
sequence deposits on two tiles and reaches five blood units after five hits;
seven hits are recorded. Bone/corrosive/dread cap at one, and poison has artwork
only. The art preview's five stages for all materials do not establish native
counterpart accumulation. Wider gore needs explicit footprint/quantity authoring
and real repeated-hit examples, rather than reimporting identical art or
stretching visuals beyond their native receiving tiles.

References confirmed by the art task:
- [Real seven-hit gameplay clip](http://127.0.0.1:8767/runs/20260919T233559Z-0ebdbd/cases/release-regions-accumulation/clip.mp4)
- [Original heavier blood comparison](http://127.0.0.1:8778/blood-fluid/)
- [Compact materials and wider proposed layouts](http://127.0.0.1:8778/body-release-regions/)

The game and workshop also differ in source raster resolution/noise basis and
bone edge treatment. These affect fine appearance, not admitted tile coverage.
