# Area spells: native propagation and rendering data

Read-only investigation, 2026-09-23. No gameplay or production rendering change
is included. The user's immediate concern is whether the other area spells need
the spatial data being explored for Fireball, and how their backend works.
This is a findings record, not an approved implementation plan.

## What needs 3D data

For a large image that overlaps walls or a spherical ward, a single sprite
position does not tell us which visible parts lie in front, behind, above, or
inside the obstacle. A list of affected ground cells does not answer that either.
Those effects benefit from spatial ownership attached to the artwork samples.

This does not require a new 3D gameplay simulation. The current map already
records boundary positions, orientation, base height and top height through
`WorldObjectPlacement`. Its current door/wall state owns the blocked channels.
The renderer can use those observed placements with registered effect geometry.
It must not acquire hidden objective map data to improve clipping.

| Presentation family | Smallest useful spatial representation |
| --- | --- |
| Floor residue, Grease and other flat ground layers | Actual receiving cells, their support heights, registered floor coordinates. Explicit XYZ per pixel is usually unnecessary. |
| Small projectile | Existing 3D trajectory/anchor and a compact sprite are often sufficient. Per-pixel geometry is justified only by observable partial-intersection requirements. |
| Large blast, fog, smoke, tall flame | Sample positions/depth registered to the source image, to split one image against finite walls, actors and protection surfaces. |
| Ground vegetation/Web | Existing floor/clump registration may suffice. Tall overlapping parts can use spatial metadata if their actual occlusion requires it. |
| Analytic shell/ring | Its authored sphere/plane geometry can provide spatial placement without a new position-map export. Transparency remains a separate composition concern. |

The requirement is useful spatial information, not necessarily three stored
coordinates everywhere. In an orthographic source render, X/Z plus the original
pixel coordinate and known camera projection can reconstruct Y. That calculation
belongs to the source registration/export; inferring height from an already
cropped, scaled or rotated destination pixel is unreliable.

Current installed volume media already has two-channel world footpoints:
`game/registered_media.py` decodes X/Z; `game/spatial_field_media.py` uses them
for native cell ownership, support heights and per-pixel ground depth.
`game/fixture_depth.py` partitions those draws against other scene depths.
This is an existing foundation, but it is not yet a general XYZ intersection
path for finite walls and spherical protection.

Current Fireball composition in `game/area_media.py` uses ground propagation
shadows, actual boundary sprite silhouettes and reachable wall-face slices.
It does not have individual flame/smoke sample heights. Changing more screen
offsets cannot supply that missing information.

The Godot Fireball delivery already supplies matched smoke/fire color and XYZ:
`/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/fireball-surface-export/HANDOFF.md`.
It is a prototype export, not installed production behavior. Camera registration,
source scale and support height must agree between color and geometry.

Its limitation is explicit: one position per pixel per material layer represents
one surface, while multiple transparent particles may already contribute to that
pixel. Splitting smoke and fire improves that approximation; it cannot recover
all hidden particle layers. Glow has associated emitter ownership rather than
a unique physical surface. This is a reasonable compromise to evaluate before
considering a much larger runtime particle/volume renderer.

The native 144 Hz, eight-facing delivery is source material, not an instruction
to decode every frame and direction into memory during startup. Production
cost has not been measured for this integration. Preserve the existing playback
schedule and assess the actual shared compositor before choosing a runtime
packing strategy. No new source audits, hashes or startup validation are needed.

## Three separate questions

1. **Gameplay reach:** which cells and entities the native spell can affect,
   respecting its propagation, immunity and protection rules.
2. **Effect shape:** where the visible material is placed within that allowed
   world region, using the authored asset's spatial registration.
3. **Camera occlusion:** which visible samples lie behind scene structures or
   actors from the current view.

A wall can block gameplay propagation and also hide artwork; those are distinct
tests. A tall effect may be visible above a wall without damaging a protected
creature behind it. Conversely, overhead native spells deliberately have
different propagation from ground-origin blasts.

The rejected Godot experiment used whole-cell membership as a hard image stencil
and introduced visible facets. Retain cell facts as authoritative gameplay data;
they are not, by themselves, a continuous surface model for flame/smoke edges.
Any continuous visual compromise must still respect which side of a gameplay
barrier can receive the effect. Do not silently change native reach to repair an
image.

## Shared backend owners

- `dnd/core/aoe.py`: geometric Sphere/Cone/Line/Cube/Cylinder shapes, physical
  footprint resolution and occupants. Ordinary shapes use propagation FOV when
  blockers are present. `Cylinder.compute_objective` deliberately skips it.
- `dnd/core/gridmap.py`: propagation through the existing map and boundary
  channels. Current physical propagation is predominantly XY, not a 3D ray
  simulation through ceilings and over wall tops.
- `dnd/core/base_actions.py`: `_resolve_area_targets` resolves native cells and
  occupants together. Some spells retain both through `_resolve_execution_targets`;
  the generic implementation currently returns selected entities and no cells.
- `dnd/spatial/area_conditions.py`: exact persistent-zone footprint, occupancy
  handlers, movement/turn triggers, terrain/light changes, movement and removal.
  Spell protection exclusions are applied when its footprint is resolved.
- `game/player_projection.py`: observed event facts and observer-filtered area
  positions. A missing cell in a subjective record is not proof of a wall or a
  Globe exclusion; it may simply not be disclosed to that observer.
- `game/spatial_media_draw.py` / `game/spatial_field_media.py`: registered
  floor/clump/volume presentation from those observations. No new damage or
  target selection belongs here.

## Installed presentations and their native behavior

| Family and spells | Current native behavior | Relevance to the Fireball treatment |
| --- | --- | --- |
| Fireball, Shatter | Target-origin sphere, physical propagation, per-target effects; Fireball additionally deposits Ashen. | Shared wall/protection/occlusion handling. XYZ is useful for substantial visible volume, not mandated merely because the rule says sphere. |
| Ice Knife | Targeted primary attack followed by a 5 ft cold burst on hit or miss, with separate saves. | Burst needs the same area protection contract; flight remains ordinary projectile presentation. |
| Sleep, Color Spray | Native sphere/cone candidates, followed by HP-pool ordering and eligibility restrictions. | Visible area and selected affected creatures are different facts. Do not trim the entire graphic to the sleeping/blinded targets. |
| Burning Hands, Thunderwave, Gust of Wind | Cone, directional cube, and line respectively. Thunderwave emits forced movement; Gust maintains an anchored zone with push/movement/environmental behavior. | Share registered directional placement and clipping. Each retains its own shape, origin and effect behavior. |
| Grease, Web, Spike Growth | Native ground/zone footprint, difficult terrain and existing save/restraint/damage handlers. | Floor coverage, boundary edges and contact timing first. No automatic requirement for volumetric reexports. |
| Fog Cloud, Cloudkill, Stinking Cloud, Incendiary Cloud, Insect Plague | Persistent spheres with their own occupancy/turn handlers. Fog changes sight; the damaging/nauseating zones have distinct triggers and immunities. Cloudkill and Incendiary Cloud can move their zone anchors. | Strong candidates for shared spatial volume composition against walls and actors; several already have X/Z footpoints. |
| Darkness | Magical darkness/light state in a native area. | Its image must follow the light/observation contract, not invent ordinary smoke mechanics. Spatial composition may be shared. |
| Silence, Globe | Native membership and spell interception/protection, respectively. Silence currently has a rear/front shell presentation. | Analytic shell placement can remain lean. The renderer needs actual observed protection facts before drawing suppression as a gameplay result. |

Examples of exact sizes: Fireball 20 ft radius; Shatter 10 ft radius; Sleep
20 ft radius; Burning Hands and Color Spray 15 ft cone; Thunderwave 15 ft cube;
Gust 60 by 10 ft line; Grease 10 ft square; Web 20 ft square; Spike Growth
20 ft radius. The generic zone field named `zone_radius_feet` represents a side
length for cube zones; do not interpret every value as a radius.

Poison Spray and Sacred Flame are single-target. Acid Splash selects up to two
targets. Their broad artwork is not authorization to introduce new area rules.

## Existing native spells to account for when their presentations arrive

The inspected active presentation bundles do not contain bindings for these
native candidates:

- Directional: Lightning Bolt, Sunbeam's repeated strike, Cone of Cold, Fear,
  Prismatic Spray. Sunbeam's strike is a separate action; do not assume every
  application follows exactly the ordinary SpellAction path.
- Ordinary areas: Circle of Death, Sunburst, Hypnotic Pattern, Slow, Mass Cure
  Wounds (area candidates but capped recipient count).
- Persistent areas: Entangle, Black Tentacles, Spirit Guardians, Daylight,
  Antimagic Field, Sleet Storm.
- Overhead damage: Ice Storm and Flame Strike.

**Cylinder is an important existing exception.** Ice Storm, Flame Strike and
Sleet Storm use a geometric ground circle without lateral-wall propagation
filtering because their effects come from above/below. Height is stored, but
ceiling occlusion and full Z membership are not implemented by that class.
Applying Fireball's propagation mask to these spells would change gameplay.
Ice Storm also leaves a separate terrain condition; inspect that footprint
independently of the falling damage.

Guardian of Faith is another explicit exception: its current zone computes a
5 by 5 square directly and owns a world-object anchor, despite declaring a
spherical zone shape. Record that behavior before deciding whether to revise it.

No native Wall of Fire/Ice/Force/Stone/Thorns spell implementation was found in
the current `dnd/` Python scan. Existing wall artwork and explosion-wall tests
are not evidence that those spell mechanics exist.

## Concrete findings, with different levels of certainty

### Confirmed protection defect: Ice Knife's secondary burst

A real native Ice Knife cast can damage a Globe-protected creature when the
primary target is outside the Globe and adjacent to the protected creature.
The burst/application nodes start at EFFECT to avoid declaring a second cast.
Globe's spell blocker currently intercepts EXECUTION; the secondary application
bypasses it. The correct eventual fix must preserve the single admitted spell
lineage, rather than manufacture another cast or reopen Counterspell.

Probe: reused the native Globe test scene; protected neighbor at (12,7), primary
outside target at (13,7), outside caster at (2,7). A second-level Ice Knife with
fixed rolls of 1 missed its primary attack but dealt **3 cold damage** to the
protected neighbor through its real secondary burst. No renderer participated.

### Confirmed separation: Fireball damage protection and Ashen

An earlier real cast showed zero damage to a protected creature, while the same
cell remained in Fireball's root physical footprint and received Ashen. Therefore
the root footprint cannot be treated as a final protection mask for every child
effect. This needs an explicit protection/terrain contract before claiming that
one renderer mask accurately represents all native outcomes.

### Current propagation disagrees with some spell descriptions

Fog Cloud, Cloudkill and Darkness explicitly describe spreading around corners
in this repository. Their current shared Sphere computation uses direct physical
propagation; it does not flood around a doorway corner. This is a native rules
question independent of the amount of XYZ supplied by the artist.

Probe: a 21 by 21 native arena, source (-3,0), wall plane x=-1.5 with a one-cell
opening at y=0. Calling actual zone footprint resolution admitted the straight
doorway cell (-1,0) but excluded (-1,1) for those spheres. The same shared result
occurred for the inspected damaging cloud zones. These were native footprint
calls, not full casts of every spell.

### Static zones do not automatically expand when a door opens

A real Fog Cloud cast behind a closed door retained 36 cells after calling the
native door's open operation. A fresh Sphere computation after opening had
41 cells, including five newly reachable cells. The zone's existing footprint
did not change. Whether a persistent fog should spread into the new opening is
a lifecycle/gameplay decision to make explicitly; the renderer must not grow
the effect independently and imply nonexistent concealment.

### Some native actions do not retain their resolved root footprint

On a flat native arena, `_resolve_execution_targets` retained cells for Shatter
but returned no cells for Lightning Bolt, Cone of Cold and Flame Strike. Color
Spray also lacks an override of the generic discard path in the inspected code.
This does not prove their target selection is wrong. It identifies missing
area facts for future replay/presentation integration, particularly where the
renderer must not recompute objective geometry or infer it from hit targets.

## Evidence and validation

- Native Sphere versus Cylinder probe behind the same closed wall: 36 versus
  49 cells; the Cylinder included the far-side cell excluded by the Sphere.
- Selected existing tests passed: **10 passed, 43 deselected in 10.64 s**.
  Command: `python -m pytest -q
  tests/manual/test_133_new_spells_batch4_legacy_contract.py
  tests/game/test_spell14_native_facts.py
  -k 'globe or volume_geometry_excludes or cloud_surface_observation'` through
  the existing WSL uv environment. These passing tests do not cover or refute
  the new Ice Knife reproduction.
- Actual-cast Fireball fixtures are retained in
  `output/fireball-propagation/native-wall-fixtures.json`.
  `wall-policy-comparison.json` adds a hypothetical corner-flow comparison;
  it is not implemented mechanics. All four layouts use the same native data.
- The Godot task has been told that volumetric composition can be shared while
  native spell policies differ. No blanket reexport request was made.

The immediate technical opportunity is narrow: evaluate registered spatial
samples against existing observed world geometry for the large effects that
need it. Keep native reach/protection, subjective disclosure and camera clipping
separate. A failed image stencil is not evidence that the backend needs a new
3D physics system, nor that every spell needs bespoke rendering code.
