# Fixed windows: implementation plan and delivery

Scope: the ten Fantasy window families confirmed by the environment artist on
October 1. The user requested planning against existing code and starting all
their content now. Window opening/closing is canceled. Desert, multi-Z, cloud
rendering and the separate NPC roster are outside this work.

## Implementation status — October 1

Implemented ten registered Fantasy families, nineteen ordinary item definitions,
shared physical reach queries, parent attachment destruction/removal, and cleared
aperture traversal through the existing PASSAGE connector. Ordinary native events
own the changes; rendering uses retained facts and independently authored media.

Traversal costs twice normal destination movement, including difficult terrain.
A4/A5 admit Small or smaller; the other eight admit Medium or smaller. A4/A5 bars
use metal material; the other inserts use wooden lattice/shutter. No window
opening/closing, Desert, multi-Z or cloud changes were introduced.

Approved media now includes parent-wall collapse after prior insert destruction.
The retained destruction fact captures intact attached items before cascading;
this selects the right bank and prevents a second insert animation. Uneven source
sample times are retained. The authored clearance frame delays the visual spatial
update. Separate masks pick the two independently actionable components, using
received object state. Crossing records a typed connector movement and samples
an authored Rolling vault with a small arc; geometry comes from admitted steps.

Validation: 96 focused native tests pass. Anti-slop and anti-OOP reviewers caught
and prompted fixes for subjective admission, vetoed removal/placement, post-roll
barrier changes, early duplicate insert drawing, and mixed-target mask fallback.
Final presentation, recording and UI checks and review-gallery link follow below.

| Artist asset | Native family ID | Independent insert |
| --- | --- | --- |
| `fantasy.wall.a4` | `environment.window.fantasy_a4` | Fixed grille |
| `fantasy.wall.a5` | `environment.window.fantasy_a5` | Fixed grille |
| `fantasy.wall.c4` | `environment.window.fantasy_c4` | Fixed grille |
| `fantasy.wall.d16` | `environment.window.fantasy_d16` | Fixed grille |
| `fantasy.wall.d7` | `environment.window.fantasy_d7` | Fixed grille |
| `fantasy.wall.f16` | `environment.window.fantasy_f16` | Fixed grille |
| `fantasy.wall.f7` | `environment.window.fantasy_f7` | Fixed grille |
| `fantasy.wall.g7` | `environment.window.fantasy_g7` | None: empty opening |
| `fantasy.wall.g8` | `environment.window.fantasy_g8` | Fixed grille |
| `fantasy.wall.g9` | `environment.window.fantasy_g9` | Fixed wooden shutter |

Each family has a `.wall` item ID; all except G7 have an `.insert` item ID.
The family itself is not another runtime item. G7 can eventually expose an
inspection/traversal region, but never a nonexistent insert damage target.

## What already exists, and what is actually missing

| Requirement | Reuse | Required work |
| --- | --- | --- |
| Item content and HP | `AuthoredItemDefinition`, `WorldItem`, item Health, direct builder registry | Complete per-component physical profiles, then one shared builder |
| Independent attacks | `AttackObject`, UUID targeting, `manual_object_contact` from either incident cell | Separate wall/insert identities and presented selection regions; current action is adjacent melee only |
| Destruction | Same-UUID integrity, `ItemDestructionProfile`, `ItemDestructionEvent`, spatial and sensory refresh | Link parent destruction to insert destruction; preserve parent on insert-only break |
| Boundary physics | Multiple boundary contributions and existing movement/optical/propagation channels | Author a frame aperture, not an opaque ordinary wall; inset must not collide with parent bands |
| Light and sight | Native optical admission, source light propagation and caches | Verify changed channels invalidate existing queries; no new light emitter or automatic one-level dimming |
| Melee versus shots | Existing range, visibility and propagation queries | Shared physical reach admission: current weapon/natural attacks and contact actions do not consistently test barriers |
| Crawl/climb | Same-level `PASSAGE` connectors and `TraverseConnector` transaction | Bind admission to actual aperture/insert state, body eligibility and other blockers |
| Rendering and picking | Intact/breaking/remnant banks, retained item facts and destruction lineages | Family wall bindings, separate registered masks, correct parent/insert composition and reveal timing |

`WorldItem` already accepts both a boundary structure and an explicit placement
specification, and respects destroyed profiles. Use it. Merely giving
`DirectionalWall` HP is incorrect: its current overrides always return the intact
placement and channels. No new window class hierarchy or change to unrelated
walls is necessary for this composition.

`owner_uuid`/`stored_in_uuid` describe inventory ownership; engine child blocks
describe internal composition. Neither is a physical wall attachment. There is
currently no implemented native parent-wall relationship to reuse by renaming it.

## Implementation order

### 1. Finish physical authoring for all families

Add physical profile data beside the identity definitions after settling the
few actual choices below. Keep artwork registration in `game/data`, keyed by the
native item IDs. Do not read the private artist manifest at game startup.

Proposed coarse physical model to confirm:

| State | Ordinary walking | Weapon melee through opening | Sight and source light | Direct projectile / laterally spreading spell |
| --- | --- | --- | --- | --- |
| Frame plus intact grille | Blocked | Blocked | Pass | Pass |
| Frame plus intact G9 shutter | Blocked | Blocked | Blocked | Blocked |
| Frame with insert broken, or G7 empty | Blocked by retained sill/frame | Restricted by the selected attack; Light melee weapons | Pass | Pass |
| Parent and insert destroyed | Clear from these providers | Clear from these providers | Clear from these providers | Clear from these providers |

Other map blockers, source/target visibility, support and occupancy still apply.
These are whole-boundary simplifications, not exact rays through individual bars.
No glazing is inferred. Existing clouds keep their established occupancy when a
window breaks; a new cast uses the new boundary state.

Before live registration, choose parent material/HP, insert material/HP,
intact height bands and nonblocking destroyed remnants. Values are authored game
data, never inferred feet or durability from PNG size. Retained debris does not
become a second object or difficult terrain unless explicitly chosen.

Implement one shared builder composing `WorldItem` with Health, boundary
placement, intact structure and destroyed profile. Parent owns the structural
bands; the inset contributes channels with `occupies_bands=False`, allowing both
to share the boundary. The inset must still be independently observable and
targetable. A fixed window gets no DoorAction or open/close state.

### 2. Add the small structural attachment lifecycle

Add an explicit native supported-by relationship for an insert's parent UUID at
the existing item/placement boundary. Validate parent existence, co-location on
the same side/support and absence of cyclic/self attachment. Reject relocating
one half independently; this task does not add a building editor or scene graph.
The authoritative composition operation must not leave a half-placed assembly
if the second component cannot be admitted.

Use existing destruction causality: damage → parent's destruction → inset's
destruction → corresponding channel/sensory changes. Insert-only destruction
preserves the original wall, its HP, sill and placement. Repeated destruction is
idempotent. Destroying an already broken insert's parent must not replay its break
or duplicate debris. Terminal parent disposal must not leave an orphan blocker.

Carry the relationship through the existing world initialization/retained facts,
so cold loaded and already-destroyed assemblies settle correctly without invented
damage events. Do not add a second destruction event vocabulary. Publish enough
data for the client to compose both identities without consulting the live map.

### 3. Wire physical admission into the actual consumers

The [detailed attack/action audit](WINDOW_ATTACK_ACCESS_AUDIT_2026-10-01.md)
records exact integration points, opportunity timing, threat consumers, costs,
spell wrappers, discovery and the behavioral acceptance matrix. Use it alongside
this contract; changing only ordinary `Attack._validate` is insufficient.

**User clarification:** attack passage must mimic the other spatial systems,
including their requester-dependent evaluation. “Subjective” here includes actor
capabilities (as visibility depends on the observer's senses), not merely which
obstacles the observer knows about. Add attack passage alongside existing spatial
properties. Do not implement a window exception inside `Attack` or introduce a
window-specific attack subclass.

Use existing Tile/provider contributions and map queries, passing the requesting
actor and actual selected attack. The boundary owns its authored passage policy;
the query evaluates that policy against the current attack context. A dagger and
a greataxe can produce different results at the same unchanged opening. Preserve
the separate knowledge/perception admission for available actions and replay;
execution evaluates current authoritative state and the actor's real capabilities.
Resolve selected-attack facts at the action boundary and pass dependency-neutral
context into spatial evaluation. Cold geometry types must not import `Attack`,
`Entity` or `Weapon`. Retain authored passage policy with existing boundary facts;
do not add a callback registry or numerical modifier for a categorical permission.

For ordinary structural blockers, default contact obstruction follows their
structural movement blocking. This does **not** mean calling path walkability:
target occupancy, lack of a walkable floor and navigation costs do not by
themselves obstruct a weapon. Direct projectiles retain their existing physical
propagation policy. The selected attack mode determines the query; an archer's
two-handed bow does not need to fit through a window for its arrow to pass.

The frame contributes restricted contact passage, the intact insert contributes
blocked contact passage, and every provider crossed on both sides must admit the
request. Destroying the insert removes only its restriction; destroying the parent
and insert removes both. An additional wall always retains its own restriction.
Do not cache one actor-independent `can_attack` boolean on the Tile. Reuse
geometry, evaluate context-dependent permission per request, and use existing
spatial events/invalidation when provider state changes. Equipment or relevant
actor-state changes must also refresh available targets/threats.

The selected weapon predicate is the existing `WeaponProperty.LIGHT`,
not absence of `HEAVY`. Current content therefore permits dagger, shortsword and
handaxe, and excludes spear, rapier and greataxe. This approximates maneuverability,
not a universal stabbing rule.
Do not infer permission from a slash animation, damage type or sprite size.

Touch spells, unarmed/natural attacks and body-displacing actions need their own
actual contact context. In particular `NaturalAttack`'s `MELEE_MAIN` slot is a
plumbing proxy: the held weapon must not decide whether a bite or claw fits.
Hand contact through an empty aperture does not grant passage
through intact bars, a bite, a grapple across the frame or bodily traversal.
The implementation carries these distinct physical access contexts.

Reuse the query in discovery and validation
for weapon/natural attacks, opportunity threats, touch/REACH spells through
`SpellAction`'s shared targeting preflight, and relevant adjacent contact actions
(including shove and waking another creature). Sight alone does not permit
reaching through a grille. Opportunity threats and their actual reaction must
agree on the effective attack. Projectile travel and weapon reach use a straight
segment with explicit corner handling; an L-shaped walking route cannot establish
reach. Existing diagonal either-bridge movement admission must not be reused as
proof that a weapon segment is clear. Do not change cloud spread or visibility
corner rules as a side effect of adding this contact query.

Preserve `manual_object_contact`'s ability to hit the contacted boundary object
itself from either side, while still rejecting intervening unrelated barriers.
A greataxe may smash an insert it cannot pass through: terminal contact with the
selected surface is different from crossing it to attack someone beyond it.
Check two providers on the same edge so a nearer shutter/frame cannot be bypassed
by excluding the wrong object. Blocked actions must follow the existing economy
and cancellation contract, not a renderer-only stop. Initial structural rejection
is validation before cost commitment; an interruption after execution commitment
keeps the existing cancellation/cost semantics. A rejected target does not
silently become damage to the intervening wall.

Current `AttackObject` is an adjacent automatic weapon-damage action. This first
native proof uses that actual supported action. Ranged creature attacks through
an aperture are a separate acceptance case. Ranged/spell attacks **against the
window object itself** remain an explicit targeting gap: do not claim they work
or silently convert them to automatic adjacent hits. Expanding object targeting
needs its own bounded resolution work after this core, if selected for release.

### 4. Enable selected crawl/climb routes

Author eligible families and permitted body sizes. The confirmed crossing cost is
twice normal movement cost, using the existing movement-cost calculation. Keep
ordinary traversal simple; do not add a separate action or roll for the crossing.
G7's empty appearance alone grants no traversal; breaking bars alone likewise
does not prove every creature fits. Default to no exposed route until the family
has an authored choice.

Reuse `PASSAGE` and `TraverseConnector` for the existing cost, reaction,
destination occupancy and event transaction. Add explicit aperture ownership and
state admission, rather than an unconditional connector through a wall. A route
may bypass only its own sill/frame when its own insert is absent/destroyed; it
cannot ignore another wall/provider on the opposite side. Revalidate at execution,
including a blocker or occupant appearing after discovery. Bind cleanup to parent
destruction/disposal; a full breach uses ordinary supported movement.

Presentation must distinguish the selected crawl/climb action using recorded
native movement facts and an available animation. No ordinary walk relabeled as
climb and no renderer-only teleport. Same-level endpoints do not require multi-Z.

### 5. Integrate the completed art and prove replay

Preserve originals privately per `ASSETS.md`. The artist has delivered the
completed batch and relayed the human's approval: “looking good hand those off
good job.” Approved source root:
`/mnt/c/Users/tommaso/Documents/assets/window-reconstruction`;
`destruction-showcase/manifest.json` and `mask-validation.json` cover all ten.
All ten parent breaks and nine insert breaks are supplied, with four-view masks
and highlights. `README.txt` records the rebuild pipeline and verification files.
Original idle is retained exactly; reconstructed Blender rest is not pixel-exact.
Human approval applies to this visual set, not native clearance or transmission.

The preview atlas contains source idle plus source frames 1, 4, 7, 10, 13, 19,
37 and 61 from 24 FPS motion. These are **unequally spaced source times**, although
the showcase cycles them uniformly. Production must preserve elapsed source time
through existing timed frame registration or pack the saved full renders at their
native rate; never play the nine atlas columns as uniform 24/32 FPS motion. G9's
last sample intentionally holds its settled frame 37. Preserve the source-to-320px
padded-canvas registration for both artwork and masks. No 144 FPS duplication.

Map family IDs to registered four-view media and independent wall/insert picking
regions. Current generic wall drawing selects material/corner art, so family art
requires an actual binding path. Render the shared original appearance only once;
separate target identities must not double-draw the intact source. Insert break
reveals the aperture while retaining frame/sill. Parent break consumes both
components without replaying the insert effect twice. Use authored transition
timing for visual exposure, while gameplay commits through its native event.

Selection obeys received state and occlusion. Damage goes to the selected UUID;
an empty aperture never silently redirects an insert attack to its parent. A late
observer sees the settled remnant, not a fresh break animation. Saved subjective
replay must work after engine reset, with no private live-state lookup.

## Acceptance and tests

Follow `HOW_TO_TEST.MD`: real commands/events in, externally observable facts out.
Do not add a visual regression framework or tests mirroring these table entries.

1. All nineteen item IDs build once their profiles are complete; every family can
   be placed from either owner side without parent/inset band collisions. Failed
   placement leaves no partial assembly or new spatial contribution.
2. From either incident side, hit the insert without damaging the wall. Lethal
   damage preserves identity and yields the authored aperture channels. Ordinary
   walking remains blocked by the frame. Parent destruction clears both bodies'
   blockers exactly once under the actual damage/destruction lineage.
3. Warm native LOS/light/propagation caches before breaking G9, then verify their
   changed result; prove a real existing light passes through a grille/empty
   opening with the normal distance falloff. No synthetic light source is added.
4. Real movement/melee/ranged actions and a real touch spell distinguish solid wall, grille, shutter,
   broken insert and full breach; include diagonals, long reach, discovery versus
   execution, and another obstruction on the same boundary.
   Exercise dagger and greataxe from the same actor/location, the literal Light
   cases handaxe versus spear/rapier, touch/natural contact independent of the
   equipped weapon, threatened cells and actual opportunity reactions, attacking
   the insert itself, and rejection before costs versus interruption afterward.
5. For each selected traversal policy, prove accepted body/state/cost, rejected
   larger body/intact insert, blocked or unsupported destination, another wall,
   stale discovery and parent cleanup. Use actual movement and reaction events.
6. Load intact, insert-broken and fully destroyed assemblies cold. No fake damage;
   no orphan insert, channel or route. Reset and replay both observers' events.
7. Four-camera clips: insert-only break, parent-only break, parent after insert,
   nonlethal flash, G7 inspection, selected traversal and full-breach walking.
   Include a viewer on each side and keep native inputs identical across views.
   Native checks and human visual approval are reported separately.

## Selected gameplay policies and remaining capability boundary

A4/A5 admit Small-or-smaller and the other eight admit Medium-or-smaller. These
are authored gameplay categories, not dimensions inferred from pixels. Crossing
costs twice normal destination movement, including difficult terrain. Ordinary
walks cannot bypass a retained sill/frame; parent destruction clears that frame.
Hand contact and Light melee weapons cross cleared apertures, while body,
bites/claws and ordinary weapons remain blocked. Native bars/shutters gate their
own channels independently of the supporting frame.

Ranged/spell targeting of objects remains the explicitly identified existing
capability gap. This delivery uses the existing adjacent AttackObject action;
it does not invent projectile immunity for windows or extend arbitrary spells
to object targets. Artwork and native object HP are ready for that later shared
capability work.

## Independent reviews

Anti-slop reviewer: `/root/windows_anti_slop`.
Anti-OOP/ECS reviewer: `/root/interiors_backend_review`.
Both reviewed the actual document and scaffold and approved the bounded content
and ECS design. Both requested explicit touch/REACH spell coverage in the shared
contact query; that clarification and its acceptance case are included above.
The validation script loaded ten families and nineteen unique, valid native IDs
and verified that none is prematurely registered with live item builders.
Both reviewers also approved the subsequent requester-relative attack-access
refinement in section 3. This follows existing sense-dependent contact resolution
and requester-dependent movement blockers while keeping knowledge admission
separate. The selected Light/HAND policies are now implemented.
Both also approved the detailed attack/action companion after auditing reaction
timing, every identified attack wrapper, shared spell preflight, direct native
object use and retained spatial data. The existing reaction/pressure/cost baseline
passed sixteen baseline tests; the implementation now passes 96 native acceptance tests.

## Final delivery and checks

- Native combat, cost, assembly and traversal suite: **96 passed**.
- Window replay, mixed-target UI, retained history and dependency-boundary suite:
  **84 passed**. The strengthened mixed-target regression also passes separately.
- Targeted runtime/importer/review typing: **zero errors**; window-patch whitespace check clean.
- Both independent reviewers approved after their concrete findings were fixed.
- [Gameplay review: ten families, both observers, four views](http://127.0.0.1:8767/runs/20261001T004700Z-263b93/index.html):
  **24/24 captures pass**. Final export reprojects and renders the same saved native
  inputs; it does not fabricate movement, damage or destruction. Parent-collapse
  and cleared-aperture cases are separate. Source positions start on opposite
  sides; the vault deliberately puts the attacker on the witness's side.
- Public packets retain only disclosed attached identities for composite media;
  a hidden insert is never revealed by its supporting wall's appearance or collapse.
- Private originals are preserved; production sheets/masks are installed and
  included in the private installer manifest. No licensed pixels are Git-tracked
  in this engine patch.

### Human visual correction — matching wall context

The review fixture now places each window between two existing solid siblings,
using the recovered architecture handoff: A4/A5→A1, C4→C1, D7→D1, D16→D8,
F7→F1, F16→F8, G7/G8/G9→G1. Seven intact banks preserve the original 256px
pixels padded to the same 320px canvas/pivot160240 as the windows; no new wall
geometry or destruction was generated. These adjoining walls use the existing
fixed directional-wall provider, not new breakable content or inferred break art.
The attacker now starts one cell further away and walks to the adjacent cell
through native movement before attacking. Four-view mounting diagrams verify
the base sits on the actual edge; no half-cell sprite shift was applied.
[Focused A4/G8 review](http://127.0.0.1:8767/runs/20261001T011251Z-708dac/index.html)
contains four event-driven clips, both observers, all cameras; all capture checks
and the six window presentation tests pass. The rolling vault remains a visual concern. The dense missing-frame delivery
was subsequently installed:61frames at24FPS,37 for G9 insert; preserved pivots,
unchanged physical clearance at416.7ms and unchanged source models/transforms.
The standalone shadow sorting experiment was withdrawn after an opaque-wall
regression. The human clarified that actors leak through transparent exterior
wall pixels, while the window opening must remain transparent. A finite boundary
clip now uses received wall placement and separately authored aperture masks;
solid siblings explicitly opt in as well. Bodies use billboard depth, shadows
use their support-plane depth only for clipping. Existing painter order, native
rules and cloud composition stay unchanged. Four-camera exterior/opening and
fractional-position shadow checks cover the clarified defect.

[Corrected four-view A4/G8 replay](http://127.0.0.1:8767/runs/20261001T014550Z-d9c5d6/index.html)
uses the same saved native events and dense art; all four capture checks pass.
The ECS and anti-slop reviews approved boundary/aperture ownership and the revised
ground-shadow clipping. Scoped typing and 21 import-boundary tests pass.
The final focused window, boundary, animation and fixture suite passes 90 tests.
The four-direction aperture tests explicitly check unpainted exterior margins;
raised and fractional-position shadow tests retain the existing draw order.

### Follow-up: crossing through the authored opening

Use the existing window aperture measurements to author one camera-independent
waypoint per family. Resolve the received boundary being crossed, shape the
connector movement through that point, and align the rolling body with the
opening. Preserve recorded endpoints, movement costs and ordinary jump behavior.
Check both directions, small/high apertures, all four cameras and interruption
continuity. Anti-slop and ECS/anti-OOP reviewers validate this bounded change.

Implemented as authored `passage_point` values beside each parent wall bank, in
local normal/tangent cells and height steps. The existing connector profile
authors the Rolling body center at 12 rig pixels. One quadratic curve passes
through that center, retaining recorded ground supports and exact endpoints;
its shadow stays on the ground. Only committed crossings use this alignment.
Reaction pauses and resumed frames retain the original trajectory/clip phase.

A5 has a deep stone reveal: each facing exposes a different interval of the
same crossing. Its reviewed visible masks are not a thin collision plane. Do
not shift sprites or add camera-specific curves to force one simultaneous
point into all four visible contours. The all-view test checks the complete
trajectory against each visible opening.

[Authored passage review](http://127.0.0.1:8767/runs/20261001T015833Z-dff84e/index.html)
replays unchanged native inputs for G8, higher D16 and narrow A5: both observers,
all four cameras, six successful capture checks.
Final follow-up validation: 76 movement, window, attack and architecture tests
pass; scoped typing reports zero errors. Independent ECS/data-ownership and
anti-slop reviews approve the implementation, including the rejected-step gate.

# October 1 corrective validation: insert-only destruction

The user found a standing wall remaining after the final destruction in the
015833 review. The native saved inputs contain one insert destruction and one
parent destruction. The imported dense insert animation was a standalone review
composite containing the parent wall, so its retained final frame incorrectly
redrew that wall. The artist repackaged the original raw fragment renders without
the parent beauty layer; no simulation, geometry, camera, timing or parent media
changed. All nine families/four directions now use explicit insert-only sheets.

The new final-frame pixel regression reproduces the old problem for all nine
families and passes after the media replacement. The whole window presentation
suite passes 24 checks. The exact original six saved inputs are replayed in
`20261001T092718Z-b0a6ce`; this supersedes the defective 015833 visual review.
Art originals and superseded installed sheets remain private and preserved.

# October 1 corrective implementation: wall clipping and CrawlThroughWindow

The attack leak came from testing a flat sprite's constant depth against each
pixel of a sloping wall, and stopping the mask at the wall base. Actor contact
now determines its side of the finite wall plane. Behind-wall sprite overhang
below the base is clipped on the same support; raised walls still permit lower
supports. Shadows retain their ground-depth test and cannot extend through the
boundary from a behind-wall owner. Window alpha remains an explicit opening.
The environment compositor also now consumes the existing occlusion flag for
matching solid wall props, instead of requiring a window aperture.

The user's clarification replaces the previous full roll with the independently
named `CrawlThroughWindow` connector animation. It has its own 450 ms clock,
selected source pose keys (0–3, brief hold, reverse to 0), 12% sill-height hold, and
temporary 0.6 × 0.8 squeeze. `Rolling` is only the source pose bank; neither its
ordinary playback nor Jump's trajectory/timing is changed. Native traversal
permission, paid movement, endpoints and reaction ordering remain authoritative.

Registration uses `body_center` in the existing typed pose-socket format. The
120 points are the centres of the alpha≥128 bounds of the unarmed `NakedBody`
Rolling source, all 15 frames/eight facings. Gear cannot bias that measurement;
existing head/face sockets remain unchanged. During the passage the sampled
centre blends onto the authored world-space aperture point. Body scaling and
registration do not transform the ground shadow, and attached pose effects use
the transformed sockets. This needs no new artwork or pixel probing at runtime.

Validation: 86 wall/window/attack tests and 42 Jump, visible-movement and rig-data
checks pass. Scoped typing reports zero errors. The actual-body pixel check
verifies the measured body centre reaches the opening in every camera; other
checks cover finite wall ends, preserved aperture alpha, source-surface safety,
ground shadows, rejected movement and intact/destructed fixtures.
The six unchanged recorded inputs are replayed in the
[crawl and clipping review](http://127.0.0.1:8767/runs/20261001T095928Z-aacdbd/index.html).
All six capture checks pass. This supersedes the earlier window presentation;
artistic acceptance of the new crawl remains for the user.

October 1 review correction: the user rejected the procedural grid. That entire
renderer option is removed. The recorder now selects the unmodified Fantasy
Ground H1 paving sprites through the existing terrain catalog (`--floor paving`,
default); `--floor scene` retains original scene bindings. Only artwork changes:
all six saved gameplay sequences compare equal to the earlier recordings. The
450 ms crawl has a 54 ms sill-height hold instead of 450 ms. All four floor
sprites match the original ZIP bytes; their private archive and production
copies are preserved. The six cases pass in the
[real-floor and faster-crawl review](http://127.0.0.1:8767/runs/20261001T101914Z-682806/index.html).
Validation for this correction: 53 window/boundary checks and 8 review-pipeline
checks pass; scoped typing reports zero errors. The actual floor and crawl
midpoint were inspected in the resulting four-camera video.
