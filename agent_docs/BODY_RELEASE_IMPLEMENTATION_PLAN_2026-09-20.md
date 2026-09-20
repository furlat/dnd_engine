# Material releases and deposited floor geometry

Status: **implemented, independently code-reviewed and validated in 40 paired
four-camera clips**. See the [implementation result](BODY_RELEASE_IMPLEMENTATION_RESULT_2026-09-20.md)
for shipped behavior, evidence and explicit limits.
The user requested finalization, review and artwork handoffs before implementation.
This is the implementation successor to
[the source study](BODY_RELEASE_GEOMETRY_STUDY_2026-09-20.md), which remains the
record of inspected code and numerical checks. The earlier approved blood
integration checkpoint remains the record of already implemented work.

## 1. Outcome and scope

A real physical injury selects a compact release pattern and the creature's
material. Native geometry resolves receiving floor regions. Existing conditions
retain their current material/amount/geometry. Subjective events are sufficient
to animate particles toward those regions and reconstruct their persistent marks,
including for an observer who did not witness the injury.

Extend the existing creature response, residue conditions, observation deltas,
Studio action-media track and absolute particle sampler. No parallel event queue,
new renderer clock, particle entities, fluid simulation or injury-history store.
Work remains pure Python/Pygame with portable data, independently of Godot spell
color work. No live TypeScript implementation is part of this unit.

Initial content: piercing, slashing and blunt patterns; normal/critical variants;
ordinary blood, bone and existing corrosive/dread materials. Request poison art
as a counterpart now, but do not introduce a new poison gameplay profile merely
because the artwork exists. Grounded injuries are the first production boundary.
Retain current AIR release/no-floor-deposit behavior and existing jump mechanics.

## 2. V1 behavior selected for the implementation proposal

These are explicit implementation defaults for review, not claims that the old
code already contains them or that they are official D&D injury rules.

- Keep current injury admission: positive effective normal-HP loss and at least
  one positive post-affinity physical component. No new periodic bleeding or
  elemental release behaviors.
- Select the physical pattern from the largest positive post-affinity physical
  component; source order breaks ties. This is a pattern rule, not attribution
  of packet-level flat reductions/temporary HP to individual damage types.
- The creature's existing profile selects material independently of the weapon.
- Preserve one accumulation unit per receiving tile per qualifying injury,
  regardless of how many regions overlap that tile. This is a local counter,
  not conserved liters of fluid. Do not count decorative droplets as units.
- Criticals get distinct airborne fullness/shape detail, with the same receiving
  region layout and one native accumulation unit. No extra reach, entry damage,
  save DC or quantity multiplier. Critical damage dice already scale separately.
- Preserve material caps: ordinary blood five; existing bone/corrosive/dread
  profiles one. No new hazard threshold: a tile receiving actual native residue
  gets its existing profile's behavior. Particle count and alpha never decide it.
- A newly deposited hazardous pool keeps current entry-only behavior. Deposition
  under an existing occupant is not a new entry and does not add a damage tick.

### Initial compact region layouts

Author these in gameplay data/code alongside the existing response profiles,
not in a renderer. All distances below are tiles. Local +X is incoming impact
direction and +Y its perpendicular; values are conservative first-review content.
Each tuple is `(centerX, centerY, radiusX, radiusY, angleDegrees)`.

| Pattern | Local receiving ellipses |
| --- | --- |
| Piercing | `(0, 0, .20, .20, 0)`, `(.55, 0, .42, .15, 0)` |
| Slashing | `(0, 0, .20, .20, 0)`, `(.45, .30, .38, .20, 30)`, `(.45, -.30, .38, .20, -30)` |
| Blunt / cause without a directional impact | `(0, 0, .36, .36, 0)` |

Ordinary/critical share these extents. They deliberately replace treating the
art preview's wide emission or canvas dimensions as mechanical reach. First
paired clips must show their footprints plainly; visual tuning that changes
these numbers is also a gameplay coverage change and must be called out.

## 3. Native causality and receiving surfaces

Keep `BodyResponseHandler` as the single configured owner. Retain the exact
critical flag already supplied by the weapon damage application; pass it into
the factual applied-damage result. Obtain direction from the actual weapon-hit
application context while that context exists. A narrow optional neutral impact
direction is sufficient; do not search an unrelated ancestor for an attack or
query renderer sockets from the backend. Directionless trap/environment damage
uses the local pattern. Do not infer direction from an arbitrary source entity
whose position might not be the impact source.

Transform the selected regions around the injury's native origin. Enumerate only
tiles intersecting those compact ellipses; retain positive-area intersections
with actual floor supports. Keep each original ellipse intersected with its
owning tile bounds: a clipped ellipse is not a newly fitted ellipse or a filled
tile polygon. Reuse native propagation to reject destinations across blocking
walls/closed doors; open doors admit them. Treat the native region as the
containing area for the artist's smaller lobes.

**V1 floor-admission rule:** the receiving tile and every tile on the finite
supercover route from the injury's tile must exist at the same support elevation
as the grounded injury. Require the existing XY propagation route as well.
This works on level floors and uniformly raised platforms, rejects holes and
changes of height, and requires no native launch arc or new interception solver.
PROPAGATION remains conservative about low walls. Cross-height deposition,
high-arc passage over boundaries, airborne wound deposits, wall stains and
continuous stair collision are deferred. Artwork can prepare height retargeting
independently; that does not claim native admission for those cases.

Apply all accepted pieces through the existing tile-condition path as children
of the actual injury. The release describes actual receiving regions/material,
not sprite IDs, palette values, particle counts or playback times.

## 4. Persistent state: capped current contributions

Extend the existing tile residue after-value with passive local deposited
geometry. A contribution contains its receiving footprint (at most the three
profile ellipses clipped to that tile) and its accumulated units. Coordinates
are relative to its owning tile/support. No attacker, event ID, time or individual
particle identity is needed to describe current deposited material.
Retain the original ellipse basis even when its center lies outside that tile;
intersect it with tile bounds when consuming it. Adjacent admitted pieces then
reconstruct one common shape without polygonization or per-tile rescaling.

For one injury on one tile:

1. If below the existing material cap, accept one unit.
2. Combine it with an identical local footprint if present; otherwise append
   that footprint with one unit.
3. The sum of contribution units equals the existing residue amount.
4. At the cap, leave amount and geometry unchanged, as current saturation does.

Therefore blood retains at most five contributions, each of at most three
clipped regions; current other profiles retain one. The bound follows the actual
accumulation rule rather than a new eviction registry. Different directions
remain exact until saturation, and gaps between deposits remain dry. Do not merge
them into a bounding ellipse that silently fills previously untouched space.

**Deliberate saturation limit:** later releases still animate, but no new
persistent footprint is accepted on a saturated tile. The animation must not
paint a new floor stamp and then erase it. It can show the transient release;
only accepted changes grow the floor. This does not preserve indefinitely many
new differently positioned marks after saturation. A later request for that
behavior needs a chosen merge policy, not silently unbounded state.

Identical repeated footprints use the existing small-splat-to-full progression,
with contribution units relative to the material cap. Recompute/replace the
resulting field; do not repeatedly alpha-blit a finished stain and darken it.
Existing recordings without geometric fields keep their old generic floor-art
path. New releases always carry the new values. Do not manufacture an old
injury's direction when decoding historical packets.

## 5. Observation and historical playback

Use existing location grants for every receiving tile. Seeing a victim does not
automatically grant unseen destination cells. Later observation carries only
current local material, contributions and amount; it neither identifies a hidden
donor nor replays the old burst. Complete lineages remain the reduction unit.

The engine commits without waiting for VFX. Existing injury and action-media
anchors own the visible release. Playback reveals accepted floor contributions
as their particles land; latest state may already be ahead. Existing marks stay
visible, and a seek must produce the same floor/air state without stepping a
mutable particle simulation. Use retained pre/post values to distinguish actual
floor growth from saturation; do not add fake damage or tile events for clips.

An interrupted-moving actor keeps its held historical wound attachment. Keep
that source fixed when retargeting particles to native receiving regions;
translating the entire template around a destination would incorrectly move the
wound origin too. Legal origins and historical rendering poses remain distinct.

## 6. Presentation and the artwork contract

[The artwork handoff](BODY_RELEASE_ASSET_HANDOFF_2026-09-20.md) is prepared before
implementation. It asks for compact normalized landing templates using the
existing procedural particle/deposit vocabulary and distinct material styles.

Transform destination detail once into the native region; keep its real wound
source fixed and derive horizontal velocities toward those destinations. Split
ownership and observation by admitted tile pieces, not by independently emitting
a whole template on each tile. Endpoints and persistent lobes must respect the
admitted pieces, retaining one common ellipse basis. Sampling/painting the same
region across two tiles must not duplicate particles or darken a seam.
Keep the absolute-time evaluator. Uniformly raised support translates source
and destination together in V1. The artwork's independent-height retargeting is
preparation only until native cross-height admission has its own selected rule.

Particles, tails, highlights and organic shoreline noise remain presentation.
Endpoint and persistent-lobe extents must fit the receiving region. Bone fragments
share placement but use fragment shapes, not a recolored liquid pool. Existing
source templates are references, not a mandate to generate a new engine schema.
Use one clear retarget path; do not ship both transformed-whole-burst and targeted
particle runtimes. New assets must not require per-material renderer branches
where existing data primitives can express the distinction.

Surface construction is driven by changed retained geometry and camera needs,
with the existing finite surface cache; no field rebuild on every idle frame.
No startup export scans, hashes, source verification or eager atlas loads.

## 7. Implementation sequence after review

1. Finalize both independent reviews; dispatch artwork handoff and obtain receipt.
2. Introduce passive release/deposit values and real weapon cause propagation.
   Keep existing field defaults for old recordings. Establish native normal/crit,
   mixed packet and trap examples through actual actions.
3. Resolve receiving geometry with existing floor/boundary owners. Implement
   capped contributions and one spatial after-value publication per changed tile.
   Inert changes must not invalidate pathfinding; hazardous membership retains
   its existing invalidation behavior.
4. Preserve permitted multi-location facts and current floor geometry through
   player recording, fresh-process decoding and later observation. Close this
   contract before polishing particles.
5. Connect accepted artwork through existing action media, historical contacts,
   absolute sampling and floor painter. Keep production binding off until the
   integrated current/new-floor representation agrees on position and lifetime.
6. Generate and inspect the paired four-camera review below, update the recovery
   checkpoint, and record limitations. Obtain final anti-slop and ECS code review.

The original planning unit changed no game code. Implementation was then authorized
and completed in the successor result linked above.

## 8. Observable acceptance

Follow `HOW_TO_TEST.md`: native action in, recorded outcome/current tile state
out; saved packets in, reproducible historical frame/final floor out. Use small
shared scenario tables, not tests mirroring private call order.

- Real piercing/slashing/blunt normal and critical hits; swap participants and
  reverse/rotate attack direction. Verify actual native receiving cells and local
  geometry, same critical footprint/counter, different selected presentation.
- Mixed physical/poison damage, physical immunity, temporary-HP-only loss and a
  trap nested under another action. Do not inherit its enclosing attack's crit.
- Repeated same-location injuries through seven hits; east then north hits before
  saturation; a changed direction after saturation. Check condition identity,
  capped geometry/amount and no transient new floor stamp at no-op saturation.
- Same placement with blood, modular/fixed skeleton and existing demon bodies.
  Walk out/in across actual corrosive/dread deposits; confirm existing entry and
  paid-retreat behavior. Deposition itself does not invent a new entry.
- Wall, open/closed doorway, equal raised support and neighboring height changes.
  Admit level routes, including translated raised platforms; reject missing or
  different-height supports along the finite route. Preserve jump over/landing
  controls and explicit AIR no-floor behavior. No cross-height landing claim.
- One ellipse across two same-height tiles; reject or hide one receiving piece.
  Keep the common pattern without duplicate particles, rescaled per-tile stamps,
  dark seams or satellite marks on an unrecorded support.
- Wound during interrupted movement uses held body attachment without recentering;
  landing geometry follows native support. Preserve nearby bodies' painter order.
- Witness, hidden injury/later discovery, partially visible receiving area and
  observers on both sides. Record once; decode after native teardown; replay from
  both participants at four camera corners without native events.
- Inspect airborne-to-floor handover, seek forward/backward, saturated aftermath
  and art endpoint containment. No wall/stair/airborne feature is accepted merely
  because a flat-ground numerical test passed.

Measure the bounded footprint calculation and cold/warm floor rendering
separately using ordinary elapsed timings. Compare against existing small
injury/replay scenarios; inspect a demonstrated regression before adding work.

## 9. Reviews and handoff status

- Anti-slop reviewer: `spell_data` — **approved** after rereading both corrected
  documents; no outstanding required changes.
- ECS/anti-OOP reviewer: `ashen_native` — **approved** after rereading both
  corrected documents; no outstanding blocking findings.
- Artwork producer: existing task `01a0b501-8a27-7413-ba24-4a36e5b140d2`.
  Dispatched September 20 before implementation; producer acknowledged both
  documents and started a separate `body-release-regions` art bundle/preview.
  Approved `blood-fluid` baseline and the main game checkout remain untouched.

These are fresh reviews of the written implementation plan and artwork handoff,
not the earlier conceptual approvals. Both reviewers identified the same two
material gaps: unspecified support interception implied a new collision solver,
and the artist's full ellipse needed an explicit contract for clipped tile pieces.
The final documents instead select the equal-elevation supercover admission rule
and the original ellipse intersected with admitted tile bounds. The handoff also
clarifies presentation-owned timing and identical normal/critical floor quantity.

Both reviewers verified those changes. The artwork task received the corrections
after its initial acknowledgement. Production code, assets and runtime tests were
not changed/run in this planning unit. Final implementation/code review remains
part of the later acceptance sequence, not implied by this plan approval.
