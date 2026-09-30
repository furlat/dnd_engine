# Fixed windows: content scaffold and implementation plan

Scope: the ten Fantasy window families confirmed by the environment artist on
October 1. The user requested planning against existing code and starting all
their content now. Window opening/closing is canceled. Desert, multi-Z, cloud
rendering and the separate NPC roster are outside this work.

## Current deliverable

`dnd/content/items/window_definitions.py` supplies ten passive family records,
containing nineteen ordinary `AuthoredItemDefinition` values: ten parent walls
and nine inserts. This is an authoring scaffold, not playable registration.
It adds no entity subclasses, execution hooks, asset paths, speculative numeric
geometry or live factory entries. Tags describe content; they do not execute rules.

The artist confirms eight fixed grilles, one empty opening and one wooden shutter.
Their earlier Small-only/Medium clearance and transmission recommendations are
proposals, not human-approved physical measurements. Those decisions remain here
instead of becoming nullable gameplay placeholders or invented defaults in code.

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
| Frame with insert broken, or G7 empty | Blocked by retained sill/frame | Restricted by the selected attack; proposed Light weapons | Pass | Pass |
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

The user's proposed weapon predicate is the existing `WeaponProperty.LIGHT`,
not absence of `HEAVY`. Current content therefore permits dagger, shortsword and
handaxe, and excludes spear, rapier and greataxe. This approximates maneuverability,
not a universal stabbing rule; the exact predicate remains under discussion.
Do not infer permission from a slash animation, damage type or sprite size.

Touch spells, unarmed/natural attacks and body-displacing actions need their own
actual contact context. In particular `NaturalAttack`'s `MELEE_MAIN` slot is a
plumbing proxy: the held weapon must not decide whether a bite or claw fits.
Proposed hand contact through an empty aperture must not silently grant passage
through intact bars, a bite, a grapple across the frame or bodily traversal.
Those action policies remain explicit before implementing their admission.

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

## Decisions to settle during the next backend step

The main gameplay choice is traversal. The artist suggests Small-or-smaller for
A4/A5 and Medium-or-smaller for the other eight openings. These are candidate
gameplay categories, not measured dimensions; these size candidates remain to be
chosen. **Confirmed by the user: double normal movement cost for crossing a
window.** Express this relative to normal movement, not as a fixed 10-foot fee.
No additional traversal subsystem is needed.

The other proposed default is the coarse transmission table above, including
the fixed G9 shutter. Material durability can reuse existing content values when
authoring each confirmed material; it is routine balancing, not a new subsystem.
Native bands and available traversal presentation still need explicit authoring.

Parent linkage, structural attack admission and support/occupancy validation are
implementation obligations, not choices to hand back to the human. Ranged/spell
object targeting is an existing capability gap to resolve deliberately if needed
for release, not a new rule where windows are arbitrarily immune to projectiles.

The scaffold is useful without guessing these decisions. It does not register
half-working windows in maps or expose a misleading playable action.

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
separate. Light/nonweapon policy choices remain discussion, not implemented rules.
Both also approved the detailed attack/action companion after auditing reaction
timing, every identified attack wrapper, shared spell preflight, direct native
object use and retained spatial data. The existing reaction/pressure/cost baseline
passes sixteen selected tests; this is not proof of the unimplemented window rule.
