# Clouds, area propagation and usable windows — action plan

The current fixed-window scope and content scaffold are owned by
[WINDOWS_IMPLEMENTATION_PLAN_2026-10-01.md](WINDOWS_IMPLEMENTATION_PLAN_2026-10-01.md).
The older window proposals below are historical context, not implementation authority.

**October 1 scope update:** the user moved on from cloud iteration and requested
coordination with environment thread `01a0b501-8a27-7413-ba24-4a36e5b140d2` for
windows. Opening/closing windows is canceled: targetability, destruction and
crawling/climbing through selected apertures are the current requirements.
The artist is preparing separate insert/wall highlights and destruction for
Fantasy windows; Desert is deferred. Per-family traversal/transmission decisions
and the current production handoff have been requested. The opening/closing
sections below are superseded, not pending implementation. Other sections remain
historical reviewed reference; this scope update does not authorize the entire
broader AoE migration below.

Updated September 30. **Planning only.** This revision follows the user's request
for shared AoE propagation and a simple first window implementation. It replaces
this document's earlier six-cloud-only scope and numerical aperture/eye-height
proposal. Multi-Z, mounted furniture and the paused storehouse experiment are
outside this unit. Read [RECOVERY_PLAN](../RECOVERY_PLAN.md) for project scope.

## 1. Intended result and fixed decisions

The engine determines where an area reaches; subjective events carry the resolved
result; the renderer presents it using the accepted geometry and XYZ artwork.
The implementation must agree across casting, discovery, retained conditions,
recording and playback. It must not establish a different rule for each spell.

The agreed simplification is connected spread inside the declared area for
laterally propagating AoEs. It can fill reachable parts around an opening, but
cannot leave the shape's envelope, pass through a sealed barrier, or enlarge the
spell. A cone remains a cone and a line remains a line. The travelling projectile
and selection of its destination are separate from spread after arrival. The
existing vertical delivery of Ice Storm/Flame Strike remains explicit.

**Closing a door does not remove or redistribute a cloud already on either side.**
Native creation and actual zone movement resolve the footprint. Subsequent door
opening, closure or destruction changes sight, light, movement and physical
occlusion; it does not itself change established area occupancy or trigger damage.
Existing duration, turn, wind, movement, concentration and Globe mechanics retain
their owners and timing. This is not a fluid simulation.

Windows use the existing boundary placement on the current map. For the first
release, admission is a whole-edge rule per physical channel. A sill or bars can
block ordinary walking and melee while permitting sight, light and ranged shots.
We do not need a new map representation or numerical sill/jamb/ray-height solver
to implement this selected simplification.

**Recommended first lighting rule: no additional attenuation.** Existing optical
admission and distance bands already determine light propagation. A window does
not become a light emitter; actual light sources pass through it. Ambient outdoor
brightness is not automatically a directional sunlight source. A later request
for tinted glass or sunlight would be an explicit lighting feature.

The user is reviewing the actual window families with the environment artist.
There is no blanket assumption that every closed window is opaque, glazed or
openable. Closed and destroyed profiles must match the chosen artwork.

## 2. What exists, and the concrete gaps

| Owner | Existing behavior | Work in this unit |
| --- | --- | --- |
| `dnd/core/aoe.py` | One geometric shape model and connected traversal; only Fireball explicitly selects connected spread | Make the shared rule usable for other shapes, then apply it to the intended lateral AoE families |
| `dnd/entity.py` | Discovery has its own footprint dispatch and existing revision-aware caches | Use the same propagation resolution as execution; retain subjective filtering and caches |
| `dnd/spatial/area_conditions.py` | Area owners resolve at activation/movement, but shape construction defaults to line of effect | Author policy on the owner and retain resolved cells without a door-topology subscription |
| `dnd/types/senses.py` | `PerceivedSpatialEffect` contains cells, geometry and native suppressions | Carry the native propagation policy through the same observation/serialization path |
| Maintained media | Sphere media defaults to connected, Line media forces line of effect, volume compositing rechecks reach through current boundaries | Consume explicit policy and authoritative recorded occupancy; keep current wall occlusion independent |
| Older area layers | Some layers still apply source-radial wall shadows | Check active users and align admission with recorded footprint rather than leave a conflicting legacy path |
| Boundaries | `MOVEMENT`, `OPTICAL`, `PROPAGATION`, placed height intervals, revisions and event publication already exist | Author simple window state profiles with these channels |
| Attacks and threats | Many direct attacks test range/visibility; melee threats use propagation | Share physical reach admission so seeing through a barred window does not permit striking through it |
| Door use/destruction | Existing open/close and same-object destruction update native structure and sensory state | Reuse the transition path; open windows must retain their selected blocked channels |

These are source findings, not claims that windows are implemented. The earlier
42-test baseline for Globe, world geometry and multi-cell objects is historical;
new acceptance runs are required after implementation.

## 3. Shared AoE implementation

### 3.1 Repair the existing traversal before migrating spell data

Two actual shape assumptions make a blind default change incorrect:

- The connected solver requires the origin to be in the affected geometric set.
  Cones deliberately exclude their apex. Permit the origin to seed traversal
  without turning it into an affected cone cell.
- Narrow diagonal lines contain diagonally adjacent cells, while the existing
  flood only visits cardinal neighbors. Respect existing map edge/corner
  transition semantics so all facings work and a closed corner cannot be bypassed.
  Crossing support used to evaluate an edge does not become extra affected cells.

Keep one bounded traversal and one footprint entry point. Reuse native map
transition checks. Do not introduce a propagation service, per-spell flood
implementations or a second cache. Clear-floor tests for all shape orientations
must pass before migrating the spell declarations.

### 3.2 Make policy truthful in every consumer

Use one dependency-neutral typed propagation vocabulary. Retain `line_of_effect`
for explicitly authored/historical behavior and `connected` for the shared
lateral rule. Add `vertical` to describe the existing Cylinder behavior: its
area arrives from above/below and currently ignores intervening lateral walls.
This records an existing rule rather than creating one.

Move the Cylinder compute-method bypass into the same policy resolution used
by shape execution and discovery. Do not infer delivery from the shape class in
each consumer. Geometry records remain dimensions, not a second policy owner.
Vertical presentation skips lateral source-reachability masking, while retaining
native admitted cells, actual wall/support occlusion and Globe exclusions.

Apply the rule by native area definition, including these representative families:

| Geometry/use | Examples to verify against their native declarations | Intended treatment |
| --- | --- | --- |
| Lateral sphere/burst | Fireball, Shatter, Sleep, Circle of Death | Connected inside the existing radius |
| Cone | Burning Hands, Cone of Cold, Fear, Color Spray, Prismatic Spray | Connected inside the existing directional envelope; apex remains excluded |
| Line | Lightning Bolt, Sunbeam, Gust of Wind | Connected within the declared width/length; no curve outside the line |
| Cube | Thunderwave, Slow, Hypnotic Pattern | Connected within the existing cube and origin convention |
| Vertical cylinder | Ice Storm, Flame Strike | Preserve existing vertical delivery; discovery must agree |
| Maintained airborne/volumetric areas | Fog Cloud, Cloudkill, Stinking Cloud, Incendiary Cloud, Darkness, Insect Plague | Connected at native activation or real movement |

During implementation, enumerate the actual constructors/callers, including
nested bursts such as Ice Knife and area templates used by discovery. Record
migration coverage in this document. Geometry alone must not accidentally change
ground-liquid spill rules, teleport destinations, a wall's placement, or a
sight-only spell's target admission. Those are distinct existing mechanics.

### 3.3 Carry facts, not a second world

Use the same policy meaning in immediate spell events, spatial observations,
subjective lineages and retained presentation state. The existing resolved cell
set remains the footprint; preserve attributed suppressions, identity, origin and
geometry. No objective wall snapshot is added to the player stream.

Discovery uses the common footprint resolver, then applies existing subjective
visibility/contact rules. Execution remains objective. They must agree for the
same known geometry without discovery exposing unseen entities or terrain.
Existing revision/shape cache keys can include the authored policy where needed;
there is no new cache/invalidation architecture.

New recordings contain the explicit policy. At the existing input boundary,
define compatibility for recordings predating the field and check them against
their current approved replay. Missing metadata must not recalculate historical
native cells or silently relabel old input as a new cast.

## 4. Keep propagation separate from presentation occlusion

Audit the active paths in `spatial_media_draw.py`, `spatial_field_media.py`,
`volume_media.py`, `area_media.py` and finite combat media as one consumer change:

1. Use the recorded geometry, occupied cells, subjective admission and native
   suppressions. A maintained field must not run a fresh source flood through
   today's door state to decide whether a previously occupied cell still exists.
2. Preserve physical clipping/occlusion against the currently presented wall,
   door, solid and floor geometry. Removing a source-reachability check is not
   permission to paint through the foreground wall.
3. Preserve the accepted cell-ownership rules for decorative fringe beyond an
   open map edge, including while the actor/observer moves. An absent map tile
   is not a wall and gives no new gameplay occupancy.
4. Preserve genuine XYZ, height, packing/registration and frame clocks. Do not
   flatten Y, alter the approved cloud scale, or replace the Globe cut with
   tile-column holes. Globe visibility continues to use the existing subjective
   volume evidence rather than requiring sight of its center floor tile.
5. Inspect active non-XYZ area-layer users before removing or changing their
   radial mask. Every changed path must distinguish affected-cell admission from
   camera occlusion; no spell-name exception restores the old rule.
6. Include finite Cone/Line/Cube XYZ admission. Currently `combat.py` supplies a
   radius only for Sphere, and a zero radius prevents the compositor from finding
   corner origins for connected spread. Changing the policy field alone would
   leave those shapes visibly clipped by a center ray. Use recorded native
   geometry/admission consistently; do not invent a circular radius for a cone
   or line. Preserve the actual directional envelope.

Check finite effects against their recorded event facts and historical boundary
state too. The renderer must not query the live engine. Old clips and new casts
answer different questions: replay proves presentation preservation; new native
histories prove changed rules.

## 5. Windows using the existing structural model

### 5.1 State data and the artist decision

These are candidate profiles for review, not assumptions about every asset:

| Selected physical state | Sight/light | Area transmission and physical shot path | Walking/melee across the edge |
| --- | --- | --- | --- |
| Open or fixed barred opening | Pass | Pass under the simple opening rule | Block |
| Closed clear pane, if selected | Pass | Block | Block |
| Closed opaque shutter, if selected | Block | Block | Block |
| Destroyed | Authored remnant profile | Authored remnant profile | Depends on whether the blocking frame/bars/sill remain |

The first fixed-window proof can use the existing C4 barred opening and the
same `MOVEMENT`-only channel pattern already present on iron lift gates. Source
catalog labels do not establish a working opening/closing animation.

For an approved openable window, extend the existing passive state profile with
open-state blocked channels. Ordinary doors retain an empty open profile;
windows retain `MOVEMENT` where required. Reuse the existing boundary provider,
use actions, open/closed fact publication and item destruction profile. No
subclass or action executor per artwork, and no general building framework.

Keep the doorway-occupancy veto/deferred-close behavior for transitions that
close a previously passable body route. `DirectionalDoor.get_use_actions` and
`_request_open` currently reject closing when an entity occupies the owner tile;
applying that unchanged to a window blocking movement in both states would stop
its adjacent user closing it. Fixed-frame window closure must remain usable from
either legal side, while ordinary occupied-door behavior stays unchanged.

### 5.2 One physical reach query, distinct from walking

Implement one shared GridMap structural-reach query using existing world-edge
contributions and their height-interval predicate. For this selected rule,
`MOVEMENT` structural blockers also obstruct physical melee reach. A new MELEE
channel is unnecessary unless a later chosen mechanic requires that distinction.

The query must not call pathfinding or ordinary walking admission: occupied
endpoints, walking costs and stair/ramp requirements do not define weapon reach.
Use a straight segment, both boundary-side contributions and existing corner
semantics. Respect native weapon reach and support heights; do not invent eye or
hand heights from renderer sockets. Do not turn central solid obstacles into
empty space along longer reach segments: reuse intermediate Tile/center-object
physical blockers (`is_blocking_propagation`), independently of actors occupying
the target and without applying walkability or hazard rules to reaching.

Route actual consumers through the shared result:

- Weapon `Attack` and monster `NaturalAttack`, using their resolved native range.
- Touch/REACH spell targets through `SpellAction`'s shared targeting preflight.
- Physical contact actions such as `Shove` and `ShakeAwake`.
- Threatened positions and opportunity attacks, so threat display, ranged
  disadvantage and reaction eligibility agree with the actual attack.

Discovery already calls native validation; it needs no duplicated window rule.
Keep existing validation/cost/event ordering. `AttackObject`, pickup and manual
item use already use `manual_object_contact`; preserve its exception for the
target provider so opening or attacking the window itself does not require
reaching through that window. Verify interactions from both accessible sides.

Ranged weapons use the existing straight `PROPAGATION` check in addition to
range/visibility. Airborne AoE spread uses the shared connected rule, not a shot
ray. For a physical projectile spell, require an authored native path policy at
the existing targeting hook; do not infer it from `projectile_type`, VFX anchors,
damage type or every spell with RANGE. Verify a real bolt and a sight-only spell
as distinct cases. This small targeting requirement belongs to game data and
must also work for a device-origin cast, not originate at its operator by mistake.
It is not a new projectile simulation or a change to existing cannon trajectory.

### 5.3 State change and destruction

A use action changes the same object's native state and publishes the existing
causal transition. `update_object_boundary_structure` owns the physical revision,
light/sight refresh and observations. Destruction retains the existing object
identity and uses its authored remnant structure. Neither path mutates cloud
occupancy merely because geometry changed.

Presentation consumes the recorded transition and plays the chosen opening,
closing or breaking animation. The structural visual change and newly revealed
content occur at its authored contact/release point, following the established
door/destruction timeline, not at animation frame zero. No visual cue is added
to the backend as a substitute for an actual state event.

## 6. Window art brief and decisions

Sent to environment chat `01a0b501-8a27-7413-ba24-4a36e5b140d2` on September 30.
The user will review families directly there. The brief requests:

- A visual inventory of all actual windows: C4 and other barred-window variants,
  window g4/g7 and miscellaneous window/shutter frames, with exact source IDs.
- Separation of empty frames, bars, glass and shutters; available static states
  and transitions versus missing work. Do not assume closures from a name.
- Per-family choices: fixed/openable, transmission when closed, appearance and
  physical remnant after destruction. Do not generate new art before selection.
- For approved missing transitions: existing pixel scale/palette, four views,
  stable registration and shadows, opening/closing/breaking timing, and the
  current packed private asset contract. Preserve sources under [ASSETS](../ASSETS.md).

This decision does not block shared AoE work or the fixed barred-window proof.
It does gate production choices for openable families. No invented temporary
shutter rule is needed while the user reviews the inventory.

## 7. Execution order and acceptance

1. **Review this revision** independently for anti-slop/correctness and ECS/
   anti-OOP. Resolve concrete findings before code changes.
2. **Shared area solver and native facts.** Repair cone/diagonal assumptions,
   express vertical delivery, make discovery/execution agree, migrate intended
   declarations, retain policy in recorded observations.
3. **Presentation consumption.** Remove conflicting current-door re-propagation
   without weakening subjective admission, actual wall occlusion or accepted
   XYZ/fringe/Globe behavior. Replay saved reference inputs and record new causal
   door/cloud examples.
4. **Fixed window and shared reach.** Author C4's simple channels, connect all
   physical-reach consumers, and verify existing iron gates/ordinary walls and
   doors alongside it. No new window animation is required for this proof.
5. **Selected openable windows.** Apply the user's art/state decisions to the
   shared data, use/destruction and authored media. Verify sight/light/targeting
   refresh and state-change timing through real native events.
6. **Focused combined review.** Save event inputs once; replay both observers in
   all four cameras. Update this plan with actual completion and remaining art
   decisions. Do not let more content or asset experimentation expand this unit.

Required checks are behavioral, following [HOW_TO_TEST](../HOW_TO_TEST.MD):

| Contract | Proof |
| --- | --- |
| Area geometry | Nonempty clear-floor cones/all-facing lines; correct apex exclusion and diagonal corner blocking; no cells outside the authored envelope |
| Connected spread | Target beyond an opening is reached inside the shape; sealed wall/door blocks; native damage/conditions match the resolved cells |
| Non-spherical presentation | A real cone/line/cube reaching around an opening renders in its permitted native cells, without retaining a center-ray shadow or painting outside its directional envelope |
| Vertical delivery | Ice Storm/Flame Strike retain their existing geometry and discovery/execution agree with walls present |
| Established cloud | Cast with a door open → close/open/break it: same condition and occupied cells, no geometry-triggered damage or reflow; existing turn damage/lifetime still operate |
| Actual cloud movement | Existing movement event resolves the destination footprint and retains its own causal triggers; no topology-only movement |
| Subjectivity | Independent observer streams retain only permitted facts; replay works after engine reset and preserves complete lineages |
| Window channels | Opposite-side sight and a real light source pass through the selected opening; wall blocks; brightness follows existing source distances |
| Physical contact | Melee/natural/touch/shove/wake and threats/OA block across the barred edge; long reach, diagonal corner, existing height and target occupancy cases remain coherent |
| Physical shots | Bow and selected physical bolt pass open and fail across a selected closed blocking pane/shutter; sight-only targeting remains independent; device-origin check uses the device |
| Own fixture contact | Open/close/attack window from either legal side, including closing a fixed-frame window from its owner tile; an occupied ordinary doorway still blocks or defers closure as before; destruction changes its native structure once and reveals only through ordinary sensory events |
| Presentation | Static/moving open-map edge, real wall, closed door, Globe overlap, raised support, and clearing the effect preserve accepted playback in four cameras |

Use the existing engine/replay tests and clip extractor. A focused gallery should
show no-wall edge separately from real-wall edge; cloud around an opening; cloud
retained after door closure from both sides; Globe overlap; fixed barred-window
sight/light/failed melee/successful ranged; selected window use/destruction.
Include both caster/perceiver streams; no synthetic render-only gameplay and no
new visual-test framework, asset audit, source hashing or per-frame validation.

**Independent reviews completed September 30:** `cloud_backend_review` approves
the revised plan for anti-slop/correctness; `interiors_backend_review` approves
for ECS/anti-OOP. Their concrete findings are incorporated: finite non-spherical
XYZ admission, ordinary-door occupancy versus fixed-frame closure, and
intermediate physical blockers for reach. Both re-read the additions and report
no remaining plan blockers. These are design approvals, not runtime test results
or authorization to invent the still-pending openable-window asset states.
