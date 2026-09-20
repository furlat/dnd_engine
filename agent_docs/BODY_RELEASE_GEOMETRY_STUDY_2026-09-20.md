# Body release geometry — gameplay study

**Finalized follow-up:** the user subsequently requested a reviewed implementation
plan and early asset handoffs. See
[the final plan](BODY_RELEASE_IMPLEMENTATION_PLAN_2026-09-20.md) and
[the dispatched artwork request](BODY_RELEASE_ASSET_HANDOFF_2026-09-20.md).
Both received fresh anti-slop/ECS review. The proposals below remain study history;
the final plan selects the next implementation contract.

September 20. **Discussion, not implementation authorization.** The user asked
to pause, reason about blood as part of a dark fantasy game, consider physical
hit patterns and critical variants, and reuse the approach for other materials.
This replaces treating the remaining decision as merely “mark neighboring tiles?”
The earlier approved appearance remains the art reference; its demo settings do
not decide gameplay reach, quantity or hazardous area.

## What exists

- `dnd/body_responses.py`: one configured response per creature, subscribed to
  `DAMAGE_APPLIED` at EFFECT. It requires actual normal-HP loss and a positive
  post-affinity piercing, slashing or bludgeoning component. It records one
  material release and, when grounded, deposits on the creature's current tile.
- `dnd/residues.py`: persistent tile conditions for blood, bone, corrosive blood
  and dread blood. Blood accumulates through five amounts while retaining its
  condition identity. Corrosive/dread membership already has entry consequences.
- `dnd/types/residues.py`: the release currently retains material identity,
  origin cell, occupancy layer and one optional destination. A tile retains
  residue identity and amount. Neither records a directional floor pattern.
- `game/particle_media.py`: the imported blood preset samples 96 independent
  ballistic trajectories at absolute playback time. Production still selects
  the older strip. Other materials also still use strips.
- Current presentation derives direction from permitted historical source and
  victim contacts, using a canonical fallback when the source is unavailable.
  That is insufficient to own a mechanical footprint.

The approved preset has a 9-by-9-tile export canvas, **not a nine-tile splash
radius**. Computing its flat-ground E-facing droplet endpoints gives X roughly
-0.85 to +1.86 tiles and Y -0.96 to +0.66. Endpoint centers occupy nine cells;
45 of 96 land on the origin cell, 31 on the next forward cell. Deposit lobes
can extend beyond their centers. This is measurement of one artwork preset,
not a proposed combat rule or a full wall/height collision result.

## Recommended gameplay vocabulary

Separate three decisions: **what the body releases**, **how the hit disperses
it**, and **how much is released**. Use existing configured handler composition.

| Physical injury | Initial pattern proposal | Same pattern, different material |
| --- | --- | --- |
| Piercing | Narrow forward spray with a local deposit | Blood droplets, bone chips, demonic fluid |
| Slashing | Wider directional fan with a local deposit | Same material choices |
| Bludgeoning | Shorter, broader local burst | Same material choices |

Damage type is the initial default. No weapon-by-weapon table is needed; a
dagger and arrow can share piercing until an actual gameplay distinction earns
another authored choice. Direction is the incoming hit direction, not a guessed
exact sword swing or inferred projectile exit wound.

A critical is a modifier within that family, not another executor. First
candidate: a fuller release without automatically extending reach. More reach
would enlarge demonic hazards; more quantity and more reach should be separate
choices. The existing five-step accumulation does not settle a critical's amount.
Do not silently change it to two units, double range, or damage-proportional liters.
Criticals already affect rolled damage. If quantity later depends on that damage,
an additional critical quantity multiplier would be a second explicit policy,
not a necessary correction.

Do not create blood behavior for every elemental damage type just to fill a
matrix. Existing physical-injury qualification is the baseline. Fire/psychic/etc.
need a deliberate body response before they produce another material. For mixed
damage, a candidate is selecting the strongest positive post-affinity physical
component, using source order for ties; this is not implemented or approved.
Flat reduction, temporary HP and effective normal-HP loss are packet-level, so
that choice would be a pattern-selection rule, not precise per-type attribution
of wounded flesh.

## Geometry owned by gameplay

The handler should resolve a **small directed material release**. Its geometry
has ordinary world meaning: origin, direction, spread, reach and quantity. The
body selects material and the hit selects the pattern. Backend code should not
read PNGs, particle counts, palettes, visual RNG seeds or animation lifetimes.

The native calculation resolves actual receiving floor supports and deposits,
then uses the existing tile-condition mutation/publication path. A plain compact
result and geometry function fit the current architecture; no new object hierarchy,
particle entity registry, frame simulation, queue or handler per droplet is needed.

Use existing boundary propagation and support data. `GridMap.raycast_clear`
already respects directional walls/doors through the propagation channel, and
`get_support_elevation_feet` gives native support height. The line check is
cell-based; it is not already a complete ballistic wall/raised-floor solver.
Its PROPAGATION channel blocks in XY regardless of a boundary's height; actual
support heights do not by themselves supply airborne trajectory collision.
Do not claim importing it alone solves airborne splatter. Wall staining and
airborne wounds can remain separate from the first grounded floor implementation.

The particle projector uses the same resolved direction, extent and receiving
geometry to animate richer detail. Generate its paths toward the recorded
deposits, rather than launching unrestricted particles and hiding their final
frames when they fall outside legal cells. Their count, colors and timing remain
presentation choices. One material substitution should reuse this path: blood
can draw droplets, bone chips can use different shapes, and demonic fluids can
select their own palettes. No bone bounce simulation is implied.

This is one shared **spatial contract**, not a requirement for native code to
simulate the artist's 96 droplets. The approved visual character should survive
adaptation to the agreed game footprint; the demo's current range is not law.

## Persistent floor state and existing causality

The native injury lineage owns the release and its tile changes. Rendering
reveals the already-recorded changes at the existing injury/landing anchors.
It never calls the backend when a visual droplet lands. Event progression can
finish while presentation continues at its own speed.

Amount alone cannot reproduce a narrow east-facing streak versus a north-facing
fan when a new observer arrives. If that distinction must persist, the tile's
observable after-state needs compact **local deposited geometry**, as well as
material and amount. Local position/extent/orientation are candidate properties;
the exact record and accumulation rule are not chosen here. Existing permitted
tile observations must be sufficient without replaying hidden injuries or looking
up a hidden donor. Do not invent a global splash registry or unbounded list of
past hit events as a shortcut.

Repeat strikes from different directions expose a real limitation of the art
demo: its five-hit accumulation repeats the same seeded field. We should preserve
the requested small-splat-to-pool progression without assuming all future hits
share that field. Choosing the bounded deposited-state representation is part of
the next design step, before wiring the new floor artwork.

Any multi-cell demonic deposit changes combat: current entry handlers act on
every tile owning that residue. The distribution/quantity rule must explicitly
decide which cells receive actual residue. A tiny decorative fleck must not
silently expand hazard membership because a pixel happened to cross a boundary.
No new hazard thresholds or damage scaling are approved by this study.

## Inputs and modest next step

Damage resolution already supplies the surviving typed components and actual HP
loss. `receive_damage` already receives a `critical_hit` flag, but does not pass
it to `DamageAppliedEvent`. Retaining that existing factual flag is a smaller
candidate than searching an arbitrary ancestor and assuming its crit also
applies to a nested trap/rider injury. Impact direction needs a native causal
source appropriate to the hit; an entity position is not universally the origin
of trap or area damage. Non-directional causes can use a local burst explicitly.
Weapon attacks forward the critical flag; spell callers do not consistently do
so. The first weapon slice can retain it directly, without claiming a complete
all-damage cause contract or expanding this study into a spell audit.

Before implementation, settle the gameplay examples: normal/critical piercing,
slashing and blunt injury; material substitution; repeated differently directed
hits; which neighboring tiles actually acquire residue. Then choose the smallest
result/state data that expresses them and preserves existing observer rules.

An eventual first acceptance slice should use real attacks on flat ground,
reversed attacker/victim positions and four cameras, then a wall/open door and
different supports. Compare both observers and a later observer, include mixed
damage and a nested trap response, and verify critical behavior from the actual
injury context. Replay saved events without native work. These are proposed
acceptance boundaries, not tests implemented during this study.

## Follow-up: inspecting the actual particle and deposit anchors

The user proposed letting gameplay determine splat anchors, which then place the
renderer's particles. The approved source supports that refinement. This section
records an implementation study, not an implemented anchor API.

Exact source inspected:

- `output/environment-sprites/blood-fluid/approved/index.html.snapshot` in the
  artwork worktree `/home/tommaso/.codex/worktrees/23a9/dnd_engine`: lines 9–15.
- That directory's `fluid.js.snapshot`: lines 5–12.
- `approved/a-lot-v1/particles.json` and `hit-5-deposits.json`.
- Current Python `game/particle_media.py` and the particle drawing path in
  `game/animation_draw.py`.

### What the source actually computes

1. `setup()` selects the wound origin, strike direction and each droplet's
   velocity, vertical launch, gravity, delay and size. It computes flat-ground
   landing time analytically. This is currently velocity-first, not an authored
   destination-anchor system.
2. During drawing, world XY is `originXY + velocityXY * age`; Z follows a
   parabola. Camera rotation and isometric projection happen afterward.
3. On landing, the same trajectory gives the splat center:
   `centerXY = originXY + velocityXY * landingTime`.
4. `BloodFluid.deposit(centerX, centerY, radius, angle, seed)` creates a main
   ellipse plus five smaller lobes. Large droplets also get three satellites
   from the caller. The records already contain `x, y, rx, ry, angle, mass`.
5. `BloodFluid.render()` sums those rotated elliptical kernels into one field;
   noise alters its visible edge and the field drives color/opacity. Overlapping
   deposits merge visually because they contribute to the same field.
6. Three projected points named `o`, `a`, `b` establish the affine mapping from
   the top-down field to the camera. These are projection basis points, **not
   landing anchors or collision checks**. Moving them only moves/distorts the
   displayed texture. The separate blood painter places deposit centers directly
   and uses the same field painter, but is also art-only.

Thus landing centers and their surrounding extents control where the splat is;
the demo does not currently calculate which native tiles or objects it hits.
Moving a floor center alone also does not retarget the flight: both must consume
the same destination geometry.

### Smallest useful adaptation

Use **native receiving patches as the anchors**: position on an actual support,
extent/orientation and deposited quantity. These describe where material exists,
not an instruction to play a graphic. Pattern selection lays out those patches
around the real impact and respects game boundaries before they are published.

The existing artist data can supply organic detail within that layout. Translate,
rotate or stretch a template around a patch's local axes, transforming the
particle endpoints and floor deposits together. Alternatively select landing
points inside a resolved patch and derive the horizontal velocities toward them:
`vx = (landingX - originX) / T`, and likewise for Y. This keeps the current
absolute-time sampler; it does not require mutable particles in the engine or
a replacement animation clock. These are adaptation options, not two runtimes
to implement together.

For unchanged support height, the original vertical arc and T can be preserved.
For another support height h, they cannot all be kept independently: preserve
z0/vz/gravity and solve `T = (vz + sqrt(vz² + 2*g*(z0-h))) / g` when a descending
intersection exists, or choose T and adjust vertical launch. Actual boundary
admission still belongs to the native geometry decision. This is a limitation
of the current flat-ground art, not an excuse to introduce a physics engine.

An anchor is not just a point: a main ellipse and its satellites occupy space.
Define the receiving extent so visual detail cannot freely spread beyond a wall
or paint persistent material onto an unrecorded neighboring surface. Gameplay
membership follows the agreed deposit geometry/quantity rule, never a PNG alpha
test or decorative-noise threshold. Exact containment/coverage and accumulation
still need selection before implementation.

One native patch may drive many visual droplets. The selected art's 96 droplets
and 672 lobes need not become 672 native objects, events or tile conditions.
Keep tile-owned current patches independent of their generating release. Later
observers receive those patches; they need neither the hidden wound origin nor
an old animation to reconstruct the floor. Each destination follows the existing
location grants when projecting a witnessed release.

### Read-only numerical check

For all 96 exported droplets, the computed endpoint matches its exported main
deposit center (maximum discrepancy about 6.1e-16 world tiles). The resulting
672 lobes match the bundle count. The exported vertical trajectory reaches the
floor at its stored landing time within floating-point precision.

A read-only probe translated and rotated the whole template, stretched its
forward axis and narrowed its lateral axis. Deriving velocities from the
transformed endpoints reproduces the same transformed original paths at start,
quarter, half, three-quarter and landing samples (maximum discrepancy about
1.0e-15 tiles). This verifies the geometry reuse on a flat support, not collisions,
visual acceptance, subjective integration or a new implemented renderer feature.

The proposal can therefore become more concrete than a separate generic spray
system: **game-resolved landing patches feed the existing trajectory/deposit
machinery**, with the final current patches retained on the existing tiles.

### User follow-up: tighter artwork and material counterparts

The user explicitly suggests generating more tightly controlled splats and bone,
poison and demonic-blood counterparts. Treat this as part of the design discussion;
no new art generation was dispatched during this study.

That lets us author local templates with a known landing origin and containing
extent instead of forcing every future hit to reshape the current broad spray.
Use the same world-unit origin, destination-region and support conventions for
each material. Particle endpoints and persistent marks must agree inside those
extents, including their secondary lobes. A template's organic edge should remain
organic; precise placement does not mean opaque tile-shaped fills.

Materials share placement, not necessarily surface shading: blood/poison/demonic
fluid may use distinct liquid palettes and textures, while bones leave discrete
fragments. Existing native profiles determine any entry effect. Producing poison
artwork does not itself select or introduce a new mechanical poison rule.

First establish the normal physical-hit layouts and critical variation, then
request matching material sets with those same local geometric constraints.
Particle density and highlights can vary without changing gameplay coverage.
An art handoff should state origin, unit scale and containing extent, and show
the airborne endpoints against the persistent marks. It need not add a new
runtime schema, per-material interpreter or source-auditing machinery.

## Independent reviews

- Anti-slop: `spell_data`, read-only review of current code and this proposal.
- ECS/anti-OOP: `ashen_native`, read-only review of event data, state ownership
  and existing geometry helpers.

Both reviewers support the bounded ownership and three-family/material-orthogonal
proposal. Their corrections are incorporated above: post-affinity components
are not exact HP-loss attribution; critical damage is already scaled; existing
critical propagation covers the weapon slice rather than every cause; propagation
is XY rather than a ballistic solver; and per-tile amount caps do not settle
differently oriented deposit accumulation. Neither review chooses gameplay
reach, quantity or hazardous-cell membership on the user's behalf.

No game code or assets were changed, and no runtime tests were needed for this
read-only implementation study and documentation update.
