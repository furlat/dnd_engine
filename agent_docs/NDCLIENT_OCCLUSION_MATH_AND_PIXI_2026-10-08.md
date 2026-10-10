# NDClient: occlusion mathematics, shared wall geometry and minimal render data

Date: 8 October 2026. Required technical chapter of the
[master plan](NDCLIENT_IMPLEMENTATION_PLAN_2026-10-08.md), refining
[N−1](NDCLIENT_EFFECT_REPRESENTATION_PREFLIGHT_2026-10-08.md).

**Destination: PixiJS 8.22.0 / WebGL2. Godot is an offline asset producer only.**
This chapter first specifies the mathematics and Pixi implementation. Whether and
how an exporter supplies the selected inputs is subsequent work. No Godot runtime,
second renderer, new native lighting simulation or production asset conversion is
introduced here. The subsequent [standalone proof](audits/ndclient-plan-20261008/FIREBALL_PROOF.md)
now measures a subset of this design: Fireball depth, real wall registration and
shared receiving/emitted light. Other cases retain their explicit proof obligations.
Independent anti-slop and ECS/DAG/history/privacy review approved the revised
chapter; findings and exact approval limits are in the
[review receipt](audits/ndclient-plan-20261008/PLAN_REVIEWS.md#october-8--occlusion-mathematics-walllight-reuse-and-compact-data).

**Subsequent concrete selection:** the human has requested the
[single-view Fireball export and Pixi proof](FIREBALL_SINGLE_VIEW_PIXI_HANDOFF_2026-10-08.md).
Its baseline uses two true depth bands, eight byte channels per layer texel and
local depth peeling for crossing transparent contributions. It is explicitly
24 FPS; selected v4 now has 46 frames and a 1.916667-second manifest duration.
All other media retain their rates. The
alternative compositor discussion below is research context, not an instruction
to implement several algorithms. The first export and standalone measurements are
delivered. The media chapter's selected contracts and §1.1 below govern production
integration; combined production performance and visual correctness remain unproven.

## 1. The actual problem, separated into independent operations

XYZ is a representation of a point, not an occlusion algorithm. We need the
following results; these do not all need the same data or execution frequency.

| Operation | Question | Required information | Execution owner |
|---|---|---|---|
| Admission | May this audience see this entity/effect/part? | Received historical disclosure and authored reveal | Existing presentation compiler; never inferred from a GPU depth buffer |
| Native occupancy/propagation | Where does this spell exist or affect gameplay? | Received field/shape/causal facts | Native engine; client does not recompute reachability around wall corners |
| Camera occlusion | Is this fragment behind a wall, actor or raised floor? | Screen coordinate and comparable depth, actual visual coverage | GPU depth comparison |
| Physical intersection | Is this sample below its support, inside a solid or excluded sphere? | Reconstructed point, or a ray interval, and compact disclosed geometry | GPU geometry tests |
| Transparent composition | How much foreground smoke/fire lies in front of this body or another effect? | Ordered colour/transmittance samples along the viewing ray | GPU composition; a nearest-depth buffer alone is insufficient |
| Material coordinates | Where is the bark, frost or noise sampled? | Authored UV/rest-space mapping | Material shader; not interchangeable with camera depth |
| Lighting response | How brightly does this receiving face appear? | Effective received illumination, receiving support/face; optional normal and admitted light direction | Material shader, independent of native visibility |
| Picking/cutaway | Which admitted physical object is under the pointer? | Same placement, apertures, presented silhouette and cutaway policy | Existing point picker and shader highlight |

The old hot path does more than unpack XYZ. `game/volume_media.py` reconstructs
arrays of points, tests wall segments, finds corner visibility origins, samples
supports, tests sphere exclusions and masks copied images. `game/fixture_depth.py`
then partitions images around overlapping painter contacts. **None of those CPU
image arrays or image partitions are a target implementation requirement.**

An admitted Fireball silhouette is not multiplied by a floor visibility grid.
Ground deposits and genuinely tile-owned fields retain their separate receiving
surface/admission rules. Physical walls may hide an explosion; an unseen floor
cell must not cut triangular teeth into it. A camera depth buffer answers only
camera visibility: it cannot prevent an effect spreading through a wall behind it.

### Hard boundary: gameplay cells are not artwork stencils

The user reports repeated Pygame regressions from enforcing cell boundaries on
artwork. Preserve this distinction throughout shader and schema design:

* **Gameplay footprint:** targets, affected cells, blocked traversal and native
  condition occupancy. It does not define the outer alpha silhouette of a picture.
* **Visual footprint:** flame tongues, smoke rise, glow, antialias fringes, wall
  caps, sprite shoulders and source-authored overhang. It has registered continuous
  bounds and may extend past the gameplay cells or their projected floor diamonds.
* **Physical obstruction:** a real finite wall/support or an applicable native
  exclusion volume. Evaluate it in the fragment's reconstructed world space, with
  actual apertures/coverage; not by asking which floor diamond lies behind its UV.
* **Audience admission:** whether a draw or disclosed volume exists for this viewer.
  Admit that contribution before drawing. Never turn its affected-cell list into
  a screen-space alpha mask. This does not admit hidden entities underneath it.

For explicitly tile-owned ground deposits, use the receiving surface and authored
edge feather/overhang policy; do not reuse that policy for an airborne cloud.
For genuine partial/upper-only volume disclosure, preserve the existing disclosed
3D support/height restriction. Do not derive a new restriction from absent floor
visibility or make hidden floors/entities visible to fill an effect silhouette.

Do not solve geometry errors by adding an arbitrary whole-tile padding radius.
Fix registration/space errors first; numerical edge tolerance is tied to source
pixel scale. Decorative halo may need a continuous visibility weight from its
emitter/proxy, rather than the wall/floor test of a fictitious borrowed 3D point.
It cannot simply bypass every wall. Keep source alpha and intentional overhang;
no new crop based on mechanical range. Studio must expose the reason for an
actual rejection (physical solid, support, applicable exclusion, disclosure),
using those production predicates. A missing ground cell is not such a reason
for an otherwise admitted burst. This is a debug view, not a new rules registry.

This follows the existing types, rather than relaxing server privacy:
`SpellFact.resolved_area_positions` is explicitly a disclosed subset, never a
physical blast mask; `dnd/player/projection.py` filters it by observer permission.
`PerceivedSpatialEffect.positions`, `visible_volume_positions` and
`upper_volume_surfaces` distinguish retained footprint from separately disclosed
upper volume. Their absence cannot establish a physical blocker. Do not flood-fill
or raycast a new native propagation solution from that incomplete set. Reuse actual
received suppression/removal facts for interior exclusions and displayed physical
geometry for solid intersections. Any genuinely missing propagation presentation
fact is a producer/projection issue to identify, not a licence for tile masking.

### 1.1 Native reach to continuous render regions

**Accepted bounded example:** the demo's solid-wall/open-doorway scenes use native
objective footprints baked by `export-reach-cases.py`; there is no browser rules
engine. Each straight-wall layout has two otherwise empty rooms. A verified room
permission reduces to a continuous X interval: the actual stone faces are x=0
and x=.25. Both room permissions allow the open-door spread; a blocked room is
excluded. Point tests inside the finite wall/jamb/header solids keep the opening
separate from stone. The mechanical circle is not used to crop decorative fringes.
These dimensions describe this proof's D1 registration, not a global wall rule.

Per represented band, the existing effect shader evaluates:

```
P = sourceToWorld(pixelRayOrigin + decodedDepth * pixelRayDirection)
if P belongs to an explicitly excluded reach region: reject contribution
if P lies inside a displayed physical solid: reject contribution
if sceneDepth at the projected pixel is nearer than depth(P): reject contribution
otherwise: shade and composite the original appearance/opacity
```

The first test uses native reach. The second is local physical intersection.
The third is camera occlusion. Incoming-light shadow rays are a fourth, separate
operation. Two scalar region bounds and an enable flag suffice for this demo;
no tile stencil, extra image bank or propagation-ray wedge is involved. GPU point
tests cannot deform a prerecorded explosion or recover translucent surfaces lost
within a representative depth band. The accepted proof extrudes 2D reach vertically;
it does not demonstrate fluid pressure, smoke advection or over-wall mechanics.

**Native source findings that govern generalization:**

* `dnd/spells/evocation.py:Fireball` uses a 20-foot sphere footprint with connected
  propagation. `dnd/core/gridmap.py:connected_propagation_positions` visits four
  cardinal neighbours within the original geometric envelope, through native
  propagation edges. Solid terminal cells can receive the effect but cannot pass
  it onward. Paths through openings/around ends can reach behind the barrier;
  straight radial visibility is not equivalent to this rule.
* Fireball contacts damageable objects and repeats reach after an actual topology
  change. `AreaReachEvent` carries new cells, previous stage and prerequisite
  destruction lineages; recipients are not hit twice and the radius never restarts.
  Existing presentation scheduling waits for the relevant visible destruction
  clearance. Preserve that causality and one explosion clock when porting.
* Current Pygame `cast_surface_volume` leaves `admitted` unset for this burst;
  `compose_volume` instead recomputes a continuous corner-visibility approximation
  on a horizontal slice at the cast elevation. Its reach approximation and CPU
  arrays are not the production algorithm. The new depth reconstructs points,
  but does not make that separate approximation authoritative.

**Selected production contract; implementation remains stopped.** Positive
results alone remain insufficient. `SpellFact.resolved_area_positions` and
`AreaReachFact.newly_reached_positions` keep their present meanings; neither is an
artwork mask. The following addition records physical classification and its
native boundary witnesses at the existing event/fact owners. It selects one
continuous compilation policy, including its unknown/overhang behavior. Production
implementation and acceptance cases exercise this selection; another standalone
algorithm-selection proof is not a prerequisite.

#### Native evidence fields and ownership

Add these strict frozen passive values at `dnd/types/event_facts.py`, the existing
shared event/world after-value owner. Position components are strict integers;
UUIDs retain their existing encounter identity. The notation below is the field
contract, not a new class hierarchy or runtime service:

```python
Position = tuple[StrictInt, StrictInt]

ReachProviderRef:
    kind: Literal["object", "tile", "spatial_effect"]
    provider_uuid: UUID

ReachBoundary:
    edge: AdjacentEdgeKey
    reached_from: Position
    blockers: tuple[ReachProviderRef, ...]

AreaReachEvidence:
    reached_positions: tuple[Position, ...]
    blocked_positions: tuple[Position, ...]
    boundaries: tuple[ReachBoundary, ...]
    occluders: tuple[ReachProviderRef, ...] = ()
```

`AdjacentEdgeKey` is reused from `dnd/core/world_edges.py`; its two endpoints are
already cardinally adjacent and canonically ordered. `event_facts.py` already
imports that module's `ElevationSurfaceKind` and `SlopeAxis`. `world_edges.py`
imports only cold world/physical-access values and does not import event facts,
events, the grid, actions or player projection. This addition preserves the import
DAG: live producers and player facts import the passive owner, never the reverse.

Positions are sorted and unique, and positive/negative sets are disjoint. Every
boundary has nonempty unique blockers in canonical `(kind, UUID)` order;
`reached_from` is its positive endpoint and the other endpoint is negative.
Boundary rows sort by `(edge.first, edge.second, reached_from)` and are unique.
`occluders` is a sorted unique set of provider witnesses for line-of-effect queries;
connected evidence uses `boundaries` and leaves `occluders` empty. Line-of-effect
evidence uses `occluders` and leaves `boundaries` empty. The existing parent
`area_propagation` identifies the mode; do not add a second mode enum.
An object reference resolves through existing `WorldObjectPlacement` and item
state, a tile reference through `WorldTileState`, and a spatial-effect reference
through existing perceived spatial facts. Do not embed copied placements, pixel
dimensions, material meshes or a new world-geometry registry.

| Existing owner | Exact addition | Meaning |
|---|---|---|
| `SpellEvent` in `dnd/actions.py`, `SpellFact` in `dnd/player/facts.py` | `reach_evidence: AreaReachEvidence \| None = None` | Snapshot for an **unstaged** area only; `None` for staged areas and old/unrecorded results |
| `AreaReachEvent` in `dnd/core/events.py`, `AreaReachFact` in `dnd/player/facts.py` | `reach_evidence: AreaReachEvidence \| None = None` | Full physical snapshot for this stage, before its applications can alter topology |
| Same area-reach event/fact owners | `suppressions: tuple[SpellSuppression, ...] = ()` | This stage's native suppression snapshot, reusing the existing suppression type and the separate attribution contract below |

For staged casts, evidence belongs only to the stages. The root retains its
existing final `resolved_area_positions` and causal children; do not duplicate
the last stage's evidence onto it. Every stage carries a full snapshot because
an audience may not have received earlier positive deltas. Existing public
projection can remove/renumber stages, so accumulating only new cells cannot
reconstruct a later disclosed stage. No second effect state, stage clock or wire
envelope is introduced.

`None` means no recorded physical evidence. Empty negative/boundary tuples mean
**no disclosed exclusion**, which includes both an unobstructed result and withheld
evidence. They never authorize treating an absent cell as blocked. `reached_positions`
means physical reach before magical suppression. `blocked_positions` contains only
existing native cells inside the original envelope that physical propagation did
not reach. Protection is retained in `SpellSuppression`, not recast as a wall.

#### Capture the existing traversal, not another reach solution

For the existing connected traversal, let `E` be its original geometric envelope
intersected with existing map tiles and `R` its returned reached set. Record `R`
and `E − R`. Missing map cells supply no negative evidence. Keep the current
four-neighbor traversal, origin exception, terminal-cell rule and topology revision
invalidation (`dnd/core/gridmap.py:connected_propagation_positions`).

Alongside each cached rejected edge decision, retain the sufficient blocking
providers found by the same boundary/spatial predicate. When a reached terminal
cell stops expansion, retain its blocking tile/center-object providers. After the
existing traversal, extract cardinal frontier edges with one endpoint in `R` and
the other in `E − R`; this is a linear boundary extraction, not another flood fill.
A rejected edge whose other side was eventually reached through an opening is not
an exclusion frontier. A terminal cell remains positive; its outgoing frontier
references the provider that stopped transmission. The origin's special permission
to emit remains intact. Retain all sufficient blockers returned by that decision;
projection below does not expose an undisclosed colocated blocker.

The provider decisions remain in `is_blocking_propagation`,
`_world_edge_channel_allows` and `spatial_crossing_allows`, including their existing
cache invalidation. Keep their ordinary boolean callers compatible; the captured
explanation is cold outcome data. Do not derive providers by raycasting artwork,
retest changed topology after execution, or enlarge `get_affected_positions()`
with negative cells and thereby change event dispatch/gameplay.

Fireball records evidence after each `shape.compute_objective()` and before target
applications, at `dnd/spells/evocation.py:Fireball._apply_target_applications`.
Its existing topology-change loop supplies subsequent snapshots and destruction
lineages. All current propagated area producers must attach evidence from their
actual resolution; `None` is only for old records, genuinely nonpropagating effects
or undisclosed evidence, not a permitted omission for a current supported spell.
Existing capture deep-copies events at `dnd/player/capture.py`; extend the same
strict export and regenerate the SDK once with the other finalized owner changes.

#### Line-of-effect areas use their own existing native result

`AoEShape.compute_objective()` in `dnd/core/aoe.py` has two native propagation
modes. They must not be rendered as though both were connected Fireball spread.
For `line_of_effect`, the existing path calls `compute_propagation_fov`, choosing
symmetric shadowcasting or `_compute_directional_fov` with supercover transitions.
Keep those exact results and the current no-barrier fast path; no second traversal
or different geometric rules decide damage.

* Extend the existing propagation-cache entry to retain the blocking provider
  witnesses beside its boolean result. The grid's `compute_fov` callback records
  provider identities whenever its existing blocking predicate is true; directional
  FOV records the provider witness for a rejected transition/terminal blocking
  cell. Reuse the same cold `ReachProviderRef` and existing topology invalidation.
  Do not run another FOV to identify causes after the spell has changed the world.
* `AoEShape` retains optional cold `reach_evidence` alongside its existing
  `affected_positions`: `R=geometric ∩ actualFov`, `E−R` physical negatives, and the
  sorted unique queried blocking providers in `occluders`. No-barrier fast path
  records R=E and empty negatives/occluders exactly as the engine resolved it.
  Map absence outside E is not an occluder to disclose. Evidence caches share the
  existing origin/radius/topology lifetime; ordinary set/boolean callers remain
  compatible and consume the same result, not a competing computation.
* `dnd/core/base_actions.py` publishes that snapshot beside its existing
  `resolved_area_positions` assignment, before protection subtraction. This covers
  standard cones/lines/radial areas including Burning Hands and Sunburst. The
  existing manual resolution publishers in `spells/ice_knife.py`, `conjuration.py`
  and `illusion.py` attach their resolved shape's snapshot at that same boundary;
  retained zone presentation uses its existing shape computation. Fireball keeps
  snapshots on its stages only. Generated wall assemblies use explicit construction
  geometry, not a fabricated area-propagation record.
* The geometry origin is the existing admitted `AoEPresentationGeometry` origin/
  center captured from `computed_origin`; no client inference from the caster's
  latest position is allowed. Missing permitted origin makes reach clipping unknown.
* For this mode, release negatives/occluders only when **every queried blocker**
  and its relevant placement/position is admitted at event time, together with
  the origin. After that check, filter every negative sample by its own event-time
  position admission, just as in connected mode. Otherwise both negatives and
  occluders are empty, with no withheld-count/completeness flag or provider-count
  side channel. Independently authorized positive samples remain. This conservative rule may omit cosmetic
  exclusion under partial disclosure but never exposes an undisclosed occluder.

The one continuous compiler below adds an origin-to-vertex supporting line for
each registered end/jamb/silhouette vertex **only for `line_of_effect`**. These lines
partition possible physical line-of-effect shadow boundaries; native positive and
negative samples still label the faces. There is no client visibility/reach query.
For a short wall in a fully disclosed cone, the region behind it can consequently
carry negative samples separately from reached samples around its ends. Connected
Fireball never receives these radial partitions: its frontiers/face geometry permit
spread around ends and doors without the rejected explosion-origin wedge.

The engine's discrete shadowcasting and a registered art silhouette are not an
identical continuous model. A contradictory or unseeded face remains unknown;
never move a boundary to a tile edge or delete positive artwork to force agreement.
This explicitly prioritizes native admitted outcomes and preserved art over an
invented exact fluid/shadow reconstruction. Acceptance includes a fully disclosed
finite wall with both blocked and reached cone cells, an open aperture, all camera
rotations, a hidden blocker, cached repeat and interruption/destruction. Missing
current producer evidence is a contract failure, not a successful unknown fallback.

#### Persistent areas, cold discovery and retained revisions

Transient cast/stage facts do not suffice for a cloud first observed after its
cast. Add the same optional `reach_evidence: AreaReachEvidence | None` to existing
`dnd/spatial/area_conditions.py::AreaCondition` and
`dnd/types/senses.py::PerceivedSpatialEffect`. No new area state or observation
stream is introduced. Capture the native value in the existing owner:

1. `_compute_affected_positions()` copies its resolved `AoEShape.reach_evidence`
   before `_apply_spell_protection()`. `resolve_condition_footprint()` retains
   physical evidence independently from the protected subset. When a creator
   supplies precomputed `affected_positions`, it must also supply evidence from
   that same shape/query, not rerun reach during observation. Manual propagated
   producers in conjuration/illusion/ice/evocation use this one contract. Deliberate
   shapes without native propagation retain None; they do not pretend to be a
   wall-clipped cloud. Missing evidence for a propagated selected area is an error
   at its existing producer, not permission for a render fallback.
2. `move_zone()` computes the replacement alongside its new native footprint and
   restores the previous evidence with position/suppressions if the move rolls
   back. Existing `observation_revision` publishes the changed value. Ordinary
   topology change only changes evidence when the native owner actually recomputes
   the footprint; the renderer must not expand an old cloud because a door opened.
   Suppression/resume alters protection separately without rewriting physical reach.
3. `get_spatial_observation()` includes **filtered** evidence only after its existing
   visibility/discovery gate admits the effect. Cold acquisition, initial snapshot,
   reconnect and an unobserved cast therefore retain the same current native
   classification. Pure filtering is shared with transient/stage projection through
   `project_area_reach_evidence` next to the cold evidence values in
   `dnd/types/event_facts.py`. It receives passive allowed-position/provider sets,
   propagation mode and origin-admission boolean; it imports no entities, senses,
   grid, handler, player or renderer. Native observation and player projection
   collect their permissions at their existing owners and call this same function.
   It filters samples and enforces the full-frontier/full-occluder rules above.
4. `PerceivedSpatialEffect` never stores objective unfiltered evidence. Party
   reduction uses the existing observation/revision mechanism; it may union admitted
   positives at the same admitted revision. It must not merge partial hidden cuts
   from different observations into an allegedly complete negative cut. A complete
   admitted evidence snapshot can be reused at that revision; otherwise exclusion
   remains unknown. This intentionally conservative policy adds no party/world model.
5. `dnd/player/projection.py::_observe_spatial_revisions` already compares admitted
   values and remaps native revisions. The new filtered value participates in that
   comparison; hidden-only changes cannot increment the public revision. Observed
   loss of boundary authorization clears stale negatives and triggers an admitted
   revision, even when the cloud's positive positions have not changed. Retained
   historical observations keep their historical evidence; latest observations
   cannot rewrite a previous clip. Removing the effect removes its active region
   lease; backward seek restores it from the retained observation.

The same presentation lifetime reads stage evidence while a witnessed cast is
active, then retained spatial evidence for its maintained field. It does not render
both as independent clouds. Cold discovery begins the existing settled/maintained
phase rather than replaying an unwitnessed creation. No publication of a private
native topology revision, hidden cut counts, later geometry or hidden provider
identity is allowed. The new cold import in `senses.py` points to `event_facts.py`;
the latter must remain independent of senses/player/live spatial modules.

Mandatory lifecycle cases: Fog/Cloudkill/Darkness observed without their cast;
move/suppress/resume/expire; newly disclosed or lost boundary; already-authorized
party observers in separate rooms; native unchanged footprint after unrelated
wall change; replay before/after relocation and reconnect with no root cast record.

**Non-query footprint mutations have an explicit invalidation rule.** The common
`SpatialCondition._change_footprint()` / `AreaCondition` mutation boundary must
publish positions and evidence coherently. A fresh native shape computation passes
its fresh evidence into that change. A translation, trim, replacement or activation
arbitration that does **not** recompute propagation clears `AreaCondition.reach_evidence`
to None before publishing the new observation revision. It must not translate
stationary wall/provider witnesses with an attached cloud or retain old positive
samples as though a trimmed cloud still occupied them. This applies to
`relocate_anchor()`, `spatial/transitions.py`'s REMOVE_AFFECTED/replacement paths,
and incumbent displacement during exclusive activation. The same native rollback
restores the previous evidence alongside its previous position/footprint/suppressions.

Use an optional cold evidence argument at the existing mutation boundary (default
None = explicitly invalidated for that mutation), not a second cache, dirty-world
watcher or query performed by the observer. Fresh `move_zone()` / initial shape
resolution supplies its value explicitly. A no-op footprint change preserves the
old snapshot unless the actual native shape/evidence changed, in which case publish
the changed admitted revision. Provider destruction elsewhere alone cannot invent
a footprint recomputation. The initial propagated-producer completeness requirement
above does not forbid this intentional invalidation on a later non-query mutation.

Explicit native removal remains an existing footprint/lifetime after-value and
`SpatialEffectInteraction` cause. It is **not physical blocked-space evidence**:
never put trimmed cells in `blocked_positions`, invent a wall there, or replay the
creation. Ground receivers remove the actual changed membership; maintained-volume
operators update their existing footprint/retirement contribution at the authored
commit. Their admitted decorative fringes keep the normal source-registration
policy; missing propagation evidence cannot become a new cell-alpha wall mask.
Replacements use the replacement owner's admitted footprint and normal lifecycle.
Add attached-anchor translation, partial cloud removal, exclusive displacement and
failed relocation rollback to the same retained-area case; these are mandatory
consistency cases for the single owner, not another representation subsystem.

#### Conservative audience projection is fixed

For connected evidence apply the full-frontier rule below; line-of-effect uses
the complete-occluder rule above. Both share the same cold value and no-completeness-
flag policy. Negative evidence never creates permission to disclose a cast. The cast/area must
already be admitted through its existing spell, positive reach or application
facts. Use the audience's historical senses at this stage and the existing
`_position_allowed` grants, not latest state or the union of later observations.
Keep every independently authorized positive sample.

Release negative/boundary evidence **only if the complete native exclusion
frontier is disclosed**: both endpoints of every native frontier edge pass that
stage's position authorization, and every provider reference in every boundary
passes its existing current observation rule. Objects use the existing observation
rule, including the rule that a seen supporting wall does not disclose a hidden
insert; tiles and spatial effects use their existing admission owners. Remembered
but currently unobserved provider state does not satisfy this predicate.

If any frontier endpoint/provider fails, set both public `blocked_positions` and
`boundaries` to `()`, while retaining independently admitted positives. Do not
partially publish the cut, replace hidden UUIDs with anonymous planes, or add a
completeness flag, hidden count or withholding reason to the protocol. If the
complete frontier passes, retain its rows and filter negative samples by their
own stage-time position authorization. The empty-frontier case adds no inferred
exclusion: a subdivision face still needs an explicit negative sample.

This all-or-nothing cut rule deliberately gives up some physical reach clipping
in partially disclosed scenes. Unknown does not reject an admitted effect sample;
ordinary disclosed solids, audience volume admission and camera depth still apply.
The public empty negative/boundary tuples do not distinguish no exclusion from
withheld evidence. Studio can report insufficient **received** evidence or missing
registration, never the existence/count of hidden world facts.

`_project_fact` currently drops an area stage when its new positive list is empty.
Retain such a stage when its already-admitted public evidence/suppression snapshot
changes, including clearing a previous exclusion to unknown. Do not introduce an
otherwise undisclosed first stage merely to carry an all-empty snapshot. Continue
to strip hidden previous/prerequisite lineage UUIDs and renumber public stages at
the existing final projection pass (`dnd/player/projection.py`).

#### Continuous geometry compiler and shader

Use one local planar arrangement, labelled by the received native samples:

1. Resolve the stage's disclosed boundary witnesses and nearby displayed geometry
   against their `WorldObjectPlacement`, authored finite front/back/end faces,
   apertures, jambs and displayed leaf pose. A required missing registration makes
   physical exclusion compilation unknown; it is not a guessed rectangular wall.
2. Intersect the supporting lines of those footprint edges with the media's
   registered world-space XY bounds, deduplicating coincident lines. Include end
   and jamb faces: a long wall-face line alone would incorrectly extend a finite
   wall's side classification past its tip. For line-of-effect evidence, also add
   the admitted origin-to-registered-vertex lines described above; connected mode
   never adds them. The media bounds come from the existing
   client registration; the server neither knows nor exports artwork bounds.
3. Split those bounds by the lines into convex faces. Assign admitted native
   cell-center samples to faces. A free-space face with positive samples only is
   reached; one with negative samples only is blocked; a face with neither or with
   conflicting samples is unknown. A sample on a subdivision line labels every
   incident free-space face; solid-interior samples do not label free space.
   Missing required geometry makes exclusion unknown rather than strengthening it.
4. Dissolve adjacent equal-state faces, preserve holes, and triangulate the resulting
   blocked polygons. Internal cell seams never enter the geometry. Unknown/reached
   faces do not reject artwork. Conflicting labels identify an actual evidence/
   registration gap for Studio, not permission to guess a blocked face.
5. Upload the compact continuous polygons/convex pieces under the existing scene
   resource owner. At each represented sample, classify `P.xy` against that data,
   then independently perform solid, support, camera-depth and material tests.

For a convex piece with outward unit normals and inequalities `n_i · p <= b_i`,
membership requires every inequality at `p = P.xy`. Use one calibrated world-unit epsilon
derived from source registration for edge/solid agreement; do not snap to the
camera or expand by a tile. On shared edges, physical-solid membership wins and
blocked-region membership is inclusive. Dissolved nonconvex polygons retain their
triangles/convex pieces; no per-pixel native path search is needed.

This subdivision is geometric registration and labelling, not propagation. It
never decides a target or reachable native cell. No visible-cell bitmap, staircase
of cell squares, client propagation raycast or flood fill is produced. Origin-ray
partitions are specific to native line-of-effect evidence; they are forbidden for
connected spread, including Fireball.
The finite faces are the same geometry used for camera composition, material
receivers and picking. Source alpha/overhang remain the original artwork.

#### Outer fringe, low walls and stages: selected limits

A native four-neighbor result does not specify a unique continuous blast volume.
The selected visual continuation extends a known classification through its
geometry-defined face, including decorative overhang beyond the mechanical
envelope. A face with no admitted samples stays unknown and retains admitted
artwork. The mechanical radius is never an image crop or extra clipping plane.

If a finite wall ends just outside the radius, native reach cannot go around it:
negative samples exclude the behind-wall strip. The region beyond the registered
end plane has no in-envelope samples and is unknown, so a decorative flame tongue
can survive around that distant end. This cosmetic continuation is an explicit
limit; it creates no targets, damage, reach, light entitlement or revealed entities.
Closing it would invent another propagation/continuation rule. If the end or open
doorway is within native reach, positive samples on both sides remove that reach
cut; the registered solid itself still rejects its interior. An open door outside
the original envelope does not grant native reach into the other room.

**Low-wall policy is vertical extrusion of the native 2D reach classification.**
An explicitly blocked XY region rejects represented samples at every height.
Registered base/top heights still govern finite solid intersections, support,
camera occlusion and lighting; they do not reopen reach above a low cap. This can
produce a visibly artificial vertical cutoff above a low wall. The current engine
has no over-wall reach rule, and this plan does not claim natural smoke/fluid flow
there (`dnd/core/world_edges.py:world_edge_contribution_allows`). Raised supports
retain their own reconstructed heights without changing that native policy.

Each stage replaces the active evidence snapshot after the maximum of its causal
start and its disclosed prerequisites' destruction-clearance times, as in
`game/choreography.py`'s `AreaReachFact` handling. Keep one original explosion
clock. Backward seeking selects the earlier evidence and displayed geometry;
never compile historical stages against the latest world. Canceled stages do not
replace an admitted snapshot. No visible destruction prerequisite means no invented
clearance animation or undisclosed dependency.

Native storage and frontier extraction are `O(|E| + frontier)` beyond the existing
traversal. A 20-foot sphere has a 9×9 bounding square: at most 648 bytes of int32 XY
sample coordinates before protocol serialization, plus boundary/provider rows.
For `n` distinct nearby registered supporting lines, arrangement output is worst
case `O(n²)`; cardinal geometry is the corresponding sorted X/Y subdivision.
Label placement, seam dissolution and triangulation happen on stage or relevant
displayed geometry/registration change, not every frame. GPU bytes scale with
merged polygon complexity, not map cells or artwork resolution. Reuse the existing
instance/resource cache and historical ownership; camera panning does not rebuild
the world-space region. Measure complex local arrangements in the combined workload;
never silently truncate their polygons to make a frame budget pass.

Production acceptance covers open overhang, finite/L/multiple walls, both sides,
reachable/out-of-radius openings, surviving and serially destroyed barriers,
terminal solids, low walls/raised support, partial/upper-only disclosure, four
cameras and backward clearance seeking. These verify the selected rules and their
named limitations; they are not a request to reopen algorithm selection.

See [master §0.2](NDCLIENT_IMPLEMENTATION_PLAN_2026-10-08.md#02-accepted-v4-and-native-reach-shader-findings)
and the [versioned proof receipt](audits/ndclient-plan-20261008/FIREBALL_PROOF.md#october-8--v4-and-the-two-room-reach-example).

## 2. One depth value can replace three coordinates for a surface sample

Use a common world-to-view transform and explicit source registration. In an
orthographic projection a pixel determines a ray:

```
P(u,v,t) = O(u,v) + t D
```

`O` is the point on a reference plane, `D` the fixed viewing direction, and `t`
one scalar. Hence a genuine surface sample needs **one depth scalar**, not X, Y
and Z independently. The fragment's UV/screen position already supplies the other
two degrees of freedom. This also holds for perspective after proper unprojection.

For the current host projection, in camera-local cell/height units:

```
u = 64 (X − Z)
v = 32 (X + Z) − 64 H
d = X + Z

X = (d + u/64) / 2
Z = (d − u/64) / 2
H = (32 d − v) / 64
```

These are local, unzoomed, pivot-relative coordinates. Apply origin/elevation and
inverse camera rotation once through matrices. Increasing `d` is nearer in this
convention; map it monotonically to decreasing WebGL depth, with explicit near/far
bounds. Store a linear depth parameter, not an undocumented Godot hardware-Z value.
The same calibrated ray/depth definition is used for floors, walls, actors and VFX.
Per-object independently normalized depths cannot be compared without decoding.

The existing Fireball has source Y projected with 78.383671769 px/unit, followed
by a 1.224744871391589 height conversion to the host's 64 px/unit. That distinction
belongs in the source-to-world matrix, not a Fireball conditional in a shader.

### Source check, not an assumption

The current Fireball packer already derives Y from source pixel V and captured
X/Z. It rejects native samples whose projected U differs by at least one pixel.
This confirms the redundancy for its native samples. Four installed SE frames
(0, 29, 49, 63) were decoded for this study, without changing pixels:

* Native-owner projection error: worst p99 across sampled components **0.310 px**;
  maximum **0.9992 px**, at original scale. Most p99 values are below 0.04 px.
* Fringe/glow samples inherit a neighbour's XYZ. Sampled glow error reaches
  **13.035 px**: those points do not lie on the colour pixel's ray.
* A single depth is therefore a sound surface representation, but a conversion
  must specify how borrowed glow is treated. It is not a bit-exact XYZ compressor.

Evidence: `fireball-surface-export/{HANDOFF.md,pack.py}` in the supplied artwork
workspace, `game/{projectile_media,registered_media,volume_media}.py`, and
[numerical receipt](audits/ndclient-plan-20261008/volume-projection-samples.json).
The four-frame result is not an all-frame/asset certification.

The scalar precision calculation is independent of texture transport. The selected
transport is the media owner's **`rg16be_oct8_rgba8`** geometry plane: raw RGBA8,
RG holding big-endian uint16 camera-ray depth and BA holding the octahedral normal.
Decode `code = 256*R + G`; zero is invalid, and valid codes decode as
`low + (code−1)*(high−low)/65534`. Across a 64-cell range the scalar quantization
half-error is under 0.000489 cell, before its registered transform. This arithmetic
does not bound a coarse texture/proxy's error. Use the exact calibration and error
limits in [media §2.3](NDCLIENT_EFFECT_REPRESENTATION_PREFLIGHT_2026-10-08.md#23-scalar-depth-conversion-precision-and-paired-validity).
The earlier R16UI suggestion is not a second runtime format. Use nearest sampling,
no mipmaps, and no gamma conversion, lossy colour codec or premultiplication for
geometry data; categorical ownership is also never bilinear-filtered.

## 3. A hierarchy of the minimum geometry, selected by visual need

| Representation | Additional asset data | Suitable use | Limitation |
|---|---|---|---|
| Plane or small mesh | Shared vertices/indices, calibrated transform | Floors, wall faces, door leaves, ground effects, ordinary body billboards | Cannot describe depth detail absent from the geometry |
| Analytic envelope, optionally keyed over time | Centre/axes or radii, phase times, optional shell thickness | Radial bursts, clouds, globes; approved one-camera appearance | Coarse envelope does not encode internal smoke/flame distribution |
| Surface depth map | One scalar per geometry texel, validity, registration | Irregular forms whose silhouette/occlusion needs more detail | One represented surface per pixel, not a volume |
| A few independently compositable depth layers | Colour/transmittance and depth for each layer | Hollow shells and clouds with visible front/back structure | Costs extra appearance data; cannot be recovered exactly from already flattened colour |

These are the mathematical representations consumed by the selected owner-local
contracts in [media §2](NDCLIENT_EFFECT_REPRESENTATION_PREFLIGHT_2026-10-08.md).
That chapter fixes each family's fields and calibration; this table does not reopen
selection. A flat wall derives its plane normal from registered geometry. Globe
uses its existing front/back appearance and analytic sphere. Fireball retains the
accepted v4 two genuine depth bands and original animated appearance; do not replace
those bands with a constant or newly fitted sphere.

The common shader input is a reconstructed representative point on the registered
ray. Ellipsoid intersections locate the selected surface/quarter-chord samples.
These passive representations share one compositor and resource owner. Full XYZ
remains an offline source reference. Stone-fracture rest-space material coordinates
are reconstructed from the current ray/depth point, its source-piece ownership and
the per-frame current-to-rest piece transform specified in
[media §2.4](NDCLIENT_EFFECT_REPRESENTATION_PREFLIGHT_2026-10-08.md). This preserves
material attachment without delivering runtime current/rest XYZ image banks.

### Analytic intersections used by the shader

For a plane `N·P + b = 0`, intersect the ray at
`t = −(N·O+b)/(N·D)`, then test its finite face bounds and aperture. Parallel rays
need an explicit epsilon case. Actual source alpha determines visual coverage.

For an ellipsoid with centre C and axes R, set `q=(O−C)/R`, `w=D/R` and solve:
`(w·w)t² + 2(q·w)t + (q·q−1)=0`. The roots give near/far intersections.
The selected shell samples its distinct front/back appearances at the corresponding
surfaces; it does not fill the chord with colour or treat a dome as a solid blob. Floors and slopes use their actual support planes. Complex
profiles use their small mesh or depth map; no universal raymarcher is required.

Sphere exclusion tests use `(P−C)` in the exclusion's own calibrated basis, and
test squared normalized distance. Distinct nonuniform art scales must not turn a
world sphere into the wrong exclusion shape. Every selected contribution uses
point membership, including both fog samples; runtime interval-density subtraction
is not selected. Ground-only receivers keep their own registered support geometry.

### Globe of Invulnerability and Antimagic Field are mandatory distinct cases

The shader receives an **applicable** exclusion/suppression selected from native
historical facts. It never decides spell level, origin, immunity or magic status.
`cast_surface_volume` currently derives exclusions from retained `protections`;
persistent fields also retain explicit suppression facts. Reuse those existing
causes and presentation commits, not a client-side "all domes suppress all magic"
rule. If a required predicate is missing from the projected facts, document that
specific gap at the existing source owner before implementation.

* Globe: distinguish an intercepted incoming application, excluded portion of
  an area, an unaffected application and a cast originating within the protection,
  according to the recorded outcome. Shell impact belongs at the actual path/
  sphere contact, not the target's feet or the nearest owning tile.
* Antimagic: distinguish interruption of an incoming effect from suppression of a
  maintained field, creature effect or item presentation. Enter/exit, resume and
  expiry are separate causal states. Removal/suppression is not a decorative hole
  unconditionally applied to every draw; expiry while suppressed must not revive it.
* Both: near/far/edge/fully-inside/disjoint overlap; lower/raised origins; projectile,
  beam and continuous volume; concurrent protections; four camera quadrants. No
  damage/body hit for a natively suppressed application. Preserve its authored shell
  response and timing. The selected compiler handles the same facts in play/Studio.

Segment/sphere entry for a straight path comes from `P(s)=A+s(B−A)` and the same
quadratic, restricted to `0≤s≤1`; choose the first applicable crossing in causal
order. Curved trajectories use the existing path sampler plus a bounded root
bracket/refinement, not a per-pixel test or a new projectile simulator. This is
visual contact placement for an already decided native outcome. If the event or
authored path already supplies that contact, reuse it. For the selected representative-point media, sphere subtraction is point membership
for each reconstructed contribution, independent of projectile contact timing.
Do not attenuate colour by surviving chord length as a second volume model.

**Selected typed attribution repair:** master [§5.5](NDCLIENT_IMPLEMENTATION_PLAN_2026-10-08.md#55-typed-protection-cancellations-and-exact-native-amendment)
owns the exact fields and native/projector edits. Retain `SpellSuppression` and its
event-time admitted provider geometry. Area suppression stays on the existing
spell/reach fact; terminal cancellation uses the existing `PlayerNode.cancellation`
with that same passive value. Portal/forced movement are covered as well as casts.
No status-message parsing, latest-provider lookup or hidden-provider inference is
permitted. Unknown provenance produces generic cancellation, never a guessed shell
contact. This correction changes no spell rules or server architecture.

Globe already has authored directional response media; Antimagic's inspected
binding has its maintained layers. Do not fabricate an Antimagic shell-hit animation
by assuming its art contract matches Globe. Show its actual received cancellation/
suppression with existing applicable media and record any additional response art
as a later authoring requirement.

Single-view radial appearance remains camera-facing. Its proxy is instantiated
consistently in the current camera/world basis. Nearby walls and characters still
rotate normally. Do not screen-rotate the flame plume, borrow depth from another
camera bank, or claim that reusing random lobes preserves exact world-locked
particle positions. Directional walls/beams/cones keep meaningful headings.

## 4. The transparent part: what can and cannot be recovered

Premultiplied compositing of a near sample over a far sample is:

```
C = Cnear + Tnear Cfar
T = Tnear Tfar                 (T = 1 − alpha)
```

Pure additive emission is a sample with nonzero C and T=1. If it lies behind
smoke, the smoke still attenuates it; drawing all additive fire last is not a
general physical solution. Preserve deliberate authored normal/add sibling order
where they are a flattened artistic composite rather than independent geometry.

**RGBA plus one XYZ/depth cannot reveal how much of that RGBA was behind an
actor inserted halfway into the cloud.** The source Fireball handoff explicitly
acknowledges this approximation. Normal-alpha smoke and additive fire are two
blend components, not automatically the back and front of the volume.

The selected family contracts in
[media §2](NDCLIENT_EFFECT_REPRESENTATION_PREFLIGHT_2026-10-08.md) distinguish a
representative surface, which preserves its original component wherever its
sample survives, from independently compositable depth contributions. Fireball
uses its two accepted genuine contributions. Original front/back layers stay
independent where they exist; copying full colour/opacity to several proxy shells
is forbidden. Account for every appearance layer's colour bytes, not just depth.

For clarity, the earlier uniform-density interval calculation below is research
context, not a second selected representation or another comparison task. It does
not recover original particles. With full transmittance T and visible path fraction f,
`Tvisible=T^f`; for constant source colour,
`Cvisible=C*(1−Tvisible)/(1−T)`. Handle T≈1 separately; emission-only scales with
visible length. This preserves the full original composite at f=1, but can fail
for an opaque core plus wispy edges. Do not promote it by mathematics alone or
use it for a shell. Exporting density alone also does not recover depth-varying
colour/emission; those are separate requirements.

Subtracting an exclusion can leave several disjoint ray intervals. Retain their
ordered endpoints when another shell/effect lies between them. Summing their
lengths into one f before interleaving loses that order. Empty visibility gives
C=0,T=1 explicitly, including T=0,f=0; handle T near zero/one without undefined
powers/division. These limits do not make the uniform-density model exact.

For intersecting transparent *draws*, ordinary object-centre sorting is not exact.
Use direct back-to-front composition where depth intervals establish an order.
The remaining crossing case uses local depth peeling. The alternatives studied
below explain that selection; weighted OIT is not another implementation task:

* **Depth peeling** is the correctness reference for represented samples: find the
  nearest remaining sample at each pixel on successive GPU passes and accumulate
  C/T. It requires no CPU image cutting. Restrict work to overlap regions; cost
  grows with represented depth complexity. A fixed small pass cap would lose
  contributions and is forbidden as a silent production shortcut. Exact ties
  retain stable authored sibling order. This is not a mandate to peel every
  particle in the whole scene.
* **Weighted blended OIT** has bounded targets and no sorting pops, but approximates
  colour order. It may fit soft similar-colour smoke and fail dense contrasting
  shells/fire. It is not the default for all artwork, and a depth-only improvement
  must not quietly introduce its appearance changes.

For the peeling reference, use the same normalized near-first quantized depth code in current and
previous-pass comparisons, plus a stable per-contribution draw key. Reject samples
whose `(depthCode,key)` is not lexicographically after the previous selected pair.
Store the selected key alongside depth; submit equal-depth candidates in ascending
key order so the ordinary LESS depth test selects the first remaining one. That
preserves deliberately coincident contributions instead of deleting all but one.
Stable keys are renderer draw identities, not new public entity IDs or depth hacks.
Before drawing, derive a conservative maximum ray-contribution count from the
candidate primitives/layers in the overlap group (a quad contributes at most one;
a multilayer/closed mesh can contribute more). That gives the finite pass bound.
Do not wait synchronously for GPU queries or silently stop after four layers. This
selected path may be too expensive for high complexity; report that measured
failure and optimize its overlap grouping/resource work while preserving every
represented contribution. Do not silently switch compositors or truncate layers.

The selected Fireball proof uses **local depth peeling**, with direct ordered
composition wherever the intervals establish an order. Weighted OIT is not a
second required implementation. Measure the chosen path against the named cases;
if cost or two-band appearance fails, record that concrete failure and correct
the shared implementation within N1/N3 acceptance. Do not claim arbitrary
transparent intersections are solved by `zIndex` or hide contributions with a cap.

## 5. Concrete Pixi/WebGL execution

The verified API is pinned source, not a guess that Pixi's 2D sprites have depth.
`State.for2d()` disables depth tests and writes. A `RenderTarget` can request an
explicit `depthStencilTexture` or depth attachment; `depth: true` alone can create
a renderbuffer and is not a promise of a shader-sampleable texture. `Mesh` with
custom `Shader` and `State` provides the required draw primitive. Custom shader
meshes do not automatically join Pixi's ordinary Sprite batching.

Ordinary Sprite batching remains useful for depth-free UI/overlays and already
resolved composites. World bodies whose per-fragment depth must participate in
the solid/transparent passes use batched custom quads/geometry with that explicit
depth state. Reuse their texture views/rig sampling, not default Sprite depth
behaviour. This distinction applies to environment parts too.

1. Compile admitted **displayed** world data into shared support/boundary meshes
   and actor/VFX draw records. Rebuild geometric buffers only when that geometry
   or authored pose changes. Pan and rotation update matrices/culling.
2. Draw opaque/cutout receiving geometry and bodies to world colour plus depth.
   Shader reconstructs P, applies the material/light response and writes comparable
   `gl_FragDepth` where a flat quad carries variable depth. Discard uncovered source
   pixels; transparent padding cannot occlude. Floors, raised floors and walls
   participate in the same physical depth space.
3. Evaluate transparent VFX over that scene, with scene-depth **writes disabled**. A
   represented contribution compares its own reconstructed depth to the solid
   depth, then applies pointwise physical exclusions and the selected C/T
   composition. Analytic ellipsoid roots place the representative contributions;
   they are not a density-integration/clipped-length renderer.
   Isolate the few crossing groups needing the selected additional compositor.
   Depth-peeling selection writes its own current nearest-depth attachment;
   final colour/transmittance accumulation does not write scene depth. The previous
   selected depth/key textures and current attachments are distinct resources.
4. Apply bounded shared emissive treatment/bloom, then render UI. Grid/path feedback
   is attached to its receiving floor before bodies/walls, not a final overlay.

Separate opaque cores from fractional-alpha edge coverage in the material policy;
do not force antialiased edges or a faded wall to write fully opaque depth. That
edge/cutaway coverage participates in the same transparent composition as VFX.
An opened doorway has no invisible rectangle left in depth. Faded foreground walls
stop visually hiding admitted ground but remain physical/native light blockers.

Never sample a texture while it is attached to the framebuffer being written.
After the solid pass, use a different colour target with no sampled depth attached,
and manual shader comparison, or a separately owned depth attachment when hardware
testing is required. Depth peeling similarly ping-pongs distinct previous/current
attachments. Do not rely on setting depth writes false to make feedback legal.
Use nearest data sampling and single-sample geometry/depth first; multi-sample
resolve/filtering is not allowed to blend unrelated depths at an edge.

WebGL2 supports the integer data textures and fragment depth used here. Pixi's
pinned format maps include `r16uint`, `rg8unorm` and depth formats. Float *render*
targets require a capability check; texture upload support is a different question.
Weighted OIT's separate accumulation/revealage blends require either independent
attachment blend support (`OES_draw_buffers_indexed`) or two passes. Do not assume
Pixi's `State` exposes per-attachment blending. Its core depth state also does not
expose an arbitrary depth comparison enum: use the established near→0/LESS convention
and explicit shader comparisons instead of mutating raw GL state behind Pixi.

`EXT_color_buffer_float` concerns float renderability; `EXT_float_blend` specifically
removes the restriction on blending 32-bit float targets. It must not be described
as a blanket requirement for all half-float accumulation. Check the actual selected
target/blend combination. Do not grow WebGPU or a second rendering backend here.

No synchronous readback, per-fragment JavaScript, fullscreen filter per entity,
per-wall image copies or per-camera decoded colour duplication. Scissor/cull to
real bounds. Shader fragment cost and upload/decode cost are measured separately;
moving arithmetic to GLSL cannot fix an unbounded texture working set.

## 6. Walls: reuse geometry for occlusion, receiving surfaces and lighting

We already have native boundary direction, base/top heights, occupied/removed
bands, covered supports and structure channels in `dnd/types/world_placement.py`.
The renderer must consume their existing audience-projected forms, not serialize
the objective map again. Source registration has actual frame/leaf art and pivots.
`environment_art.json` has **136 of 368 banks with `actor_depth`**. These are
calibrated painter/contact depth maps, not automatically camera-Z or normal maps.
The world bindings have **3 residue face profiles / 24 asset assignments**. These
help identify receiving faces, but are not a complete high-detail wall mesh bank.
There is no general per-wall normal map in these inspected binding types.

One derived boundary geometry record should serve all consumers:

| Shared input | Camera composition | Lighting/material use |
|---|---|---|
| Finite front/back/top/end faces, base/top, thickness | Depth and volume intersections | Face position and coarse normal |
| Aperture/door leaf state and displayed pose | Visible/pickable holes and animated leaf depth | Open/closed continuity and directional shadow blockers |
| Source UV, pivot and face assignment | Exact silhouette and face registration | Surface material, stain UV and optional normal detail |
| Incident receiving support on each face | Correct floor/raised-floor association | Sample illumination from the correct side of the wall |
| Separate visual cutaway and physical state | Fade upper coverage to expose admitted ground | Fading does not allow light through a physically closed wall |

Prefer a few calibrated faces for a regular wall and a hinge/pose transform for a
door. Match sculpted caps/irregular props with existing registered depth where
necessary. A wall's colour alpha supplies visual silhouette; native rectangular
blocking geometry supplies the physical boundary. Neither should silently replace
the other. Missing detail does not justify assuming solid pixels in an open doorway.

### Normals: useful, but not a visibility map

For simple faces, calculate N from the mesh; no texture. Scalar-depth media use the
selected geometry plane's two octahedral BA bytes for a unit normal, with the
media contract's measured angular-error limit. This chapter does not select another
RG16 normal format. Interpolate decoded normals and renormalize,
not packed depth/IDs. Define object/tangent/view space, handedness and mirror rules.
Nonuniform transforms require the inverse-transpose normal transform. A mirrored
sprite cannot retain an unmirrored normal basis. Existing shaded colour is not
clean albedo; relighting it aggressively would double its baked highlights/shadows.

N tells us how a face catches light. It does **not** say whether a wall blocks the
light, nor what geometry exists behind the visible surface. Camera depth is also
insufficient for light-space occlusion. Use the same compact disclosed geometry
for the requested proof's separate light-to-receiver test and the bounded cosmetic
light policy in the depth/material/light chapter.
That reuse does not mean reusing the camera depth image as a universal shadow map.

### Lighting we can support with the data actually delivered

The present stream has effective categorical illumination on admitted supports;
it does not contain a full list of directional/RGB point lights. Required baseline:
map those categories to the existing authored treatment colours, interpolate only
across compatible disclosed boundaries, and evaluate the same response on the
floor, appropriate wall face, matching door and non-emissive body/equipment.
Never average enum IDs. Never let smoothing brighten an undisclosed room or replace
the audience's senses. This part needs geometry/face ownership, not normal textures.

For an **already disclosed** visual emitter, the requested proof and production
policy use a bounded local enhancement:

```
L = normalize(lightPosition − P)
diffuse = max(dot(N,L), 0)
direct = sum(admittedVisibility * attenuation * diffuse * lightColour)
illumination = admittedBase + min(direct, max(0, authoredCeiling - admittedBase))
colour = base * illumination + authoredEmission
```

Here admittedVisibility includes both the audience boundary and, if required,
light-ray occlusion against known geometry. It must not synthesize undisclosed
light sources or change native light/vision. A visual Fireball flash can reuse its
disclosed position; reconstructing a hidden torch from cell brightness is forbidden.
Warm/cool lights and a Fireball flash are now explicitly requested proof work.
The single production policy in §5.2 of the depth/material/light chapter bounds
their cosmetic enhancement; native effective light remains the baseline. No new
server light facts, hidden emitters or client propagation are implied. Fireball's
combined appearance remains self-emitting and now also receives light through
the same normal/position functions, with an authored neutral reflectance across
the whole effect. The formula and existing-owner mapping are in
[lighting §4.1](NDCLIENT_DEPTH_MATERIAL_LIGHTING_2026-10-08.md#41-proven-emitting-and-receiving-material).
This needs no isolated smoke/emission channel or legacy export recovery. Its
independent fitted light curve illuminates other receivers using their own normals.
The original proof did not establish natural wall contact: an origin-to-fragment
shadow mask was rejected because it removed broad angular wedges of artwork.
Keep camera occlusion, incoming-light shadowing and effect contact distinct.
The later accepted two-room example in §1.1 adds native-region clipping. That
section now fixes general topology, conservative private disclosure and low-wall
policy; their combined production validation remains part of N−1.

## 7. Lighting libraries requested by the user

Both repositories were cloned read-only into
`.runtime/ndclient-lighting-references-20261008/`; no packages installed or scripts
executed. Pinned revisions and relevant file hashes are in
[lighting-reference receipt](audits/ndclient-plan-20261008/lighting-references.json).
These are source findings, not measured compatibility/performance results.

### `haiyoucuv/pixijs-light2d`

Inspected HEAD `5a76653520d0d2ef56ddb6802d301d03cadf822d`, dated 20 September 2026;
package 1.0.3, Pixi peer `^8.0.0`, development dependency `^8.16.0`. It implements
forward diffuse/normal lighting and a shared 2D occlusion texture feeding a 1D
angular shadow-distance map. It packs the first four shadowed lights into RGBA.
Useful ideas: preallocated geometry buffers, shared light uniform data, spatially
stable/snapped shadow bounds, and generating a small reusable shadow lookup.

Do not adopt it unchanged:

* `LightingShader.ts` uses 2D positions and a hardcoded light-direction Z=100. It
  does not reconstruct our elevated receiver position or finite-height walls.
* `Light2DSystem` truncates at 32 lights; shadows cover only the first four. These
  are library limits, not proposed game rules.
* `ShadowSystem` has a 2048² occlusion target and a 1024×1 angular target, with up
  to 256 occupancy samples per direction/light. Its update clears/rebuilds caster
  Graphics and renders the map again. Nominal worst-case taps are 1024×4×256,
  before early exits—not a measured frame cost or a reason to call it free.
* The sprite pipe does useful manual batching but flushes by **Texture view UID**,
  not shared atlas-source identity. Our many frame views would need adaptation.
  Its diffuse/normal UV sharing also requires matching registration.
* The inspected lighting shader has a GL program, not WGSL; registering a WebGPU
  pipe is not evidence that the advertised WebGPU readiness is implemented.
* It brings singleton light/shadow state and a Spine peer dependency. Neither
  belongs in our passive scene records merely to reuse a small lighting formula.

Read source: [lighting shader](https://github.com/haiyoucuv/pixijs-light2d/blob/5a76653520d0d2ef56ddb6802d301d03cadf822d/src/shader/LightingShader.ts),
[shadow system](https://github.com/haiyoucuv/pixijs-light2d/blob/5a76653520d0d2ef56ddb6802d301d03cadf822d/src/location/shadow/ShadowSystem.ts),
[sprite pipe](https://github.com/haiyoucuv/pixijs-light2d/blob/5a76653520d0d2ef56ddb6802d301d03cadf822d/src/scene/sprite/LightSpritePipe.ts).

### `pixijs-userland/lights`

Inspected HEAD `1e6a3e8263afbe36c6d2f6e48ef0d58f586f6a68`, dated 19 December 2024;
package 4.1.0. The package description says v6, but actual peers are Pixi v7 and
`@pixi/layers` v2. It renders diffuse and normal images into separate targets and
accumulates lights over them. Useful reference for separating surface properties
from illumination and bounding a point light's draw area. Its point shader uses
screen UV plus a light-height parameter, not our physical support/world depth.
It is not a v8 drop-in or a complete wall-shadow/volume compositor.

Read source: [package](https://github.com/pixijs-userland/lights/blob/1e6a3e8263afbe36c6d2f6e48ef0d58f586f6a68/package.json),
[shared shaders](https://github.com/pixijs-userland/lights/blob/1e6a3e8263afbe36c6d2f6e48ef0d58f586f6a68/src/lights/shared.ts),
[point shader](https://github.com/pixijs-userland/lights/blob/1e6a3e8263afbe36c6d2f6e48ef0d58f586f6a68/src/lights/pointLight/point.frag.ts).

### What the 1D shadow idea means mathematically for this game

For a planar light at L, `distance(theta)` is the distance to the first blocking
intersection along `L + r*(cos(theta),sin(theta))`. A receiver samples its angle
and compares its radius. That is compact and useful **when blockers and receivers
can actually be treated as one plane/extrusion**.

At different heights the ray height at an obstacle is
`H(s)=Hlight+(Hreceiver−Hlight)*s/r`. A low first obstacle may not block it, while
a later tall wall does. One first-hit 2D distance cannot answer that question.
Nor does it encode windows, stacked floors or the correct side of a door. Therefore
do not use a screen-space occupancy texture as the universal shadow geometry.

For our small finite walls, evaluate light-to-receiver intersections against the
same nearby 3D face geometry, or generate a light-space depth lookup from those
faces if selected light counts make it cheaper. The 1D lookup remains a candidate
only for genuinely planar light domains. Generate/update on relevant geometry or
light revision, not because the camera panned. Categorical-light smoothing alone
needs no shadow test; the additional requested cosmetic light uses the shared
finite geometry test above, without replacing native illumination.

**Integration decision:** incorporate the shared-buffer, bounded-light-area and
stable-lookup ideas into this existing renderer plan. Do not add either library as
a production dependency, copy their singleton scene ownership or assume their
normal mapping solves elevated occlusion. No new lighting feature is silently
authorized by citing their demos.

## 8. Required information before asking any exporter to produce it

Keep these at existing media/environment authoring owners. Do not introduce an
independent collider registry, a parallel world protocol or one descriptor per spell.

| Information | Required? | Smallest useful form |
|---|---|---|
| Original appearance, frame time, crop, pivot, blend/premultiplication | Yes | Existing media/frame registration; one view for accepted radial families |
| Projection/basis/units and source→world transform | Yes | Shared calibration plus per-instance transform |
| Geometric point/interval reconstruction | Yes for intersecting media | Selected plane/mesh/envelope registration or scalar depth in the common RG16BE+oct8 RGBA8 geometry plane |
| More than one compositable depth contribution | Only when interior/overlap proof requires it | Independently composited layers, each with its own C/T and registered depth |
| Valid geometry versus borrowed glow | Yes if retained representation has invalid samples | Reserved invalid depth + explicit material/halo policy; sparse mask only if required |
| Receiving support/face and aperture identity | Yes | Existing native references plus compact authored face mapping |
| Surface normal | Optional detail | Mesh constant/vertex normal; compact map only for relief |
| Albedo, emission, roughness | Only selected material operations | Reuse appearance/emission; no mandatory PBR texture stack |
| Rest-space material mapping | Only materials using it | Existing UV or compact rest mapping; camera depth cannot replace it |
| Collision, damage, propagation, light legality | Not art data | Existing native facts, never inferred from pictures |

Geometry bytes for a 64-frame candidate, excluding appearance:

| Candidate | Decoded size |
|---|---:|
| One analytic envelope per frame, 12 float32 parameters | 3,072 B |
| One 128×128 R16 depth plane/frame | 2 MiB |
| One 256×256 R16 depth plane/frame | 8 MiB |
| Two such 256×256 depth planes/frame | 16 MiB |
| Current SE XYZ + owner, both blend components | 575,915,536 B (about 549 MiB) |

These are historical arithmetic budgets for the isolated scalar component, not
alternative runtime formats or a claim that 128/256 geometry is sufficient. The
selected scalar-depth geometry plane also includes two normal bytes per texel.
One coarse texel can cover several source pixels. Check contact/doorway contours
at scale 1; use face discontinuities and valid coverage to avoid smoothing depth
across empty space. Additional independent appearance layers may cost more than
all their depth maps. Current one-view RGBA alone is 329,094,592 B: colour packing
and bounded frame residency remain necessary separate work. Do not claim 8 MiB
as the whole Fireball's footprint. These figures describe the existing 64-frame,
32 FPS archive, not the new export. The selected v4 proof uses 46 frames at
24 FPS over 1.916667 seconds; other assets retain their authored rates.

## 9. Implementation boundaries and combined acceptance

Within the existing planned `src/render/` owner:

* Projection/registration functions reconstruct rays, points and normal bases.
* World-geometry functions derive compact faces/supports from displayed facts and
  authored registration; picking/materials/occlusion share those values.
* Media shaders evaluate the finite plane/envelope/depth choice, palette/material
  and receiving-light operations. Instance parameters are passive data.
* The compositor owns Pixi targets, passes and transparent order. It cannot resolve
  gameplay, inspect spell names, mutate native occupancy or read latest state.
* Existing asset-resource ownership manages pages/upload/residency; no second cache
  per effect or camera. Normal/depth companions share that same lifetime.

No new renderer-class hierarchy or event types are needed for numeric depth storage.
Implement the selected fields at the existing media-registration owner and §1.1's
passive reach additions at their existing event/fact owners. A missing subjective
physical fact is repaired at its existing projection owner; it is not permission
to add client pathfinding or send the global map.

N1/N3/N5 verify the selected family representations from
[media §2](NDCLIENT_EFFECT_REPRESENTATION_PREFLIGHT_2026-10-08.md), the reach contract
in §1.1 and the shared compositor together in the production Pixi/Studio path on
recorded native data. It is integration acceptance, not another standalone demo or
an open choice among algorithms. Required cases:

1. Fireball/Sleep/Sunburst in open space and at a wall, open/closed doorway, low
   wall and raised floor; four cameras at scale 1. No tile-mask teeth or bottom cut.
2. Actor behind, inside and in front of the effect; small/large/prone actor and
   faded wall. No full-opacity billboard padding or double colour/opacity.
3. Globe of Invulnerability and Antimagic Field cases from §3, including native
   applicability, incoming impacts and maintained suppression/resume/expiry; two
   crossing coloured clouds and a translucent shell. Compare all represented
   contributions, not one poster. Include purely decorative overhang across cells.
4. Wall and door illuminated from each admitted side, with top/end face; split-party
   audience, closed/just-opening/historical door and remembered room.
5. Pan/rotation/seek while effects are active. Record GPU passes, fragments, CPU
   submission, decode/upload, resident bytes and frame-time distributions.

Record errors and performance against these selected contracts and their explicit
approximation limits. The Fireball handoff fixes its offline export; reuse existing
Globe art/registration and the other owner-authored media formats. The current
production stop still applies; this chapter authorizes no runtime edits, broad
Godot export or copying. Once production resumes, the master's production
measurement requirements and independent anti-slop/ECS review govern combined
acceptance in N1/N3/N5. No repeated SDK-generation or algorithm-selection gate
is added.

## 10. Primary research and API evidence

These references inform the choices; their historical benchmark numbers are not
performance promises for our game. Their algorithms are not all implementation scope.

| Primary source | Relevant result and decision |
|---|---|
| [Shade et al., Layered Depth Images, SIGGRAPH 1998](https://www.microsoft.com/en-us/research/publication/layered-depth-images/) | An image can store multiple depth samples along a ray. Separating contributions is information that a flattened image lacks. Use that insight only where required. |
| [Everitt, Interactive Order-Independent Transparency](https://developer.download.nvidia.com/assets/gamedev/docs/order_independent_transparency.pdf) | Depth peeling supplies ordered per-pixel layers through repeated raster passes. Useful correctness reference; pass cost prevents adopting it blindly for everything. |
| [McGuire and Bavoil, Weighted Blended OIT, JCGT 2013](https://jcgt.org/published/0002/02/09/) | Bounded-memory approximate composition avoids explicit fragment sorting. Its changed colour operator must be judged against dense, differently coloured effects. |
| [Cantlay, GPU Gems 3 ch.23: off-screen particles](https://developer.nvidia.com/gpugems/gpugems3/part-iv-image-effects/chapter-23-high-speed-screen-particles) | Scene depth supports particle intersections; fill-rate and texture bandwidth still matter. Reduced resolution can damage sharp detail, so no blanket colour downscale is selected. |
| [Risser, GPU Gems 3 ch.21: True Impostors](https://developer.nvidia.com/gpugems/gpugems3/part-iv-image-effects/chapter-21-true-impostors) | Small depth representations on billboards can support geometric intersection. Full raymarching/refraction is unnecessary for our finite primitives. |
| [Cigolle et al., unit-vector representation survey, JCGT 2014](https://jcgt.org/published/0003/02/01/paper-lowres.pdf) | Compare compact normal encodings and their errors; do not spend three floating-point channels on every wall normal. |
| [GPU Gems 3 ch.19: deferred shading](https://developer.nvidia.com/gpugems/gpugems3/part-iii-rendering/chapter-19-deferred-shading-tabula-rasa) | Position/depth, normal and material are distinct lighting inputs. This does not justify copying a full multi-buffer deferred renderer into Pixi. |
| [Khronos WebGL2 specification](https://registry.khronos.org/webgl/specs/latest/2.0/), [float renderability](https://registry.khronos.org/webgl/extensions/EXT_color_buffer_float/), [32-bit float blending](https://registry.khronos.org/webgl/extensions/EXT_float_blend/), [indexed blending](https://registry.khronos.org/webgl/extensions/OES_draw_buffers_indexed/) | Texture formats, framebuffer feedback and blend capabilities constrain the concrete pass design. |
| [Pixi v8.22.0 RenderTarget](https://github.com/pixijs/pixijs/blob/v8.22.0/src/rendering/renderers/shared/renderTarget/RenderTarget.ts), [GL adaptor](https://github.com/pixijs/pixijs/blob/v8.22.0/src/rendering/renderers/gl/renderTarget/GlRenderTargetAdaptor.ts), [State](https://github.com/pixijs/pixijs/blob/v8.22.0/src/rendering/renderers/shared/state/State.ts) | Verified explicit depth attachments and depth-state defaults. Local copies and hashes are in `references/pixijs-8.22.0-20261008/depth_api_sources.json`. |

Godot documentation was consulted during source reconnaissance, but its capture
features do not determine this design. Export feasibility follows the selected
mathematical inputs; no dependency on Godot's runtime or built-in depth/normal pass
has been assumed.
