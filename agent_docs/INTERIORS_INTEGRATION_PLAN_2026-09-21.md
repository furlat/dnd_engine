# Complete interiors and environment asset integration plan

Date: 2026-09-21. **Planning only; no implementation in this unit.**
Authority: [RECOVERY_PLAN](../RECOVERY_PLAN.md), the user's consolidated asset
handoff and subsequent instruction to cover all assets, backend first.
This replaces this document's earlier small-lodge-only delivery framing.

**Destruction refinement:** the user selected same-object destroyed state and
requested complete existing/new content coverage. The reviewed
[dedicated destruction plan](DESTRUCTION_LIFECYCLE_PLAN_2026-09-21.md) owns that
contract and migration; its [coverage ledger](DESTRUCTION_COVERAGE_2026-09-21.md)
records native, media, material/condition and test gaps. Original-to-replacement
wreck identity is existing code being migrated, not the desired native model.

**Multi-Z is outside this plan at the user's explicit request.** Its separate
task owns the stacked-floor discussion. Existing ground elevation, object
height, wall apertures and mounting still need correct content data here.
This plan neither chooses nor implements a new XYZ representation. Overlapping
storeys are retained as authored source assemblies awaiting that separate work;
they are never flattened into the same live Tile or counted as playable here.

## 1. Intended result and meaning of complete

Every in-scope delivered asset has an explicit role in the game: a native
item/fixture, structural boundary, support surface, attached object or cosmetic
dressing. Its physical placement and interaction rules are authored, its state
changes use the existing engine owners, and its received state selects the
matching presentation. Art variants do not become new gameplay systems.

Completion covers the whole catalog, including content not used by the eight
example houses. A small interaction room is the first proof, not the definition
of the finished integration. Explicitly stopped/held assets remain excluded;
missing mounted art is reported as missing rather than silently substituted.
No crafting, economy, rest, imprisonment or structural-collapse feature is
implied by an image of a workbench, shop, bed, cage or wall.

There are three independently observable results:

1. **Content:** exact in-scope identities and state/style mappings exist through
   the current content and presentation registries, with physical profiles.
2. **Mechanics:** placing, navigating, observing, using and destroying those
   objects changes native state correctly and emits complete causal lineages.
3. **Presentation:** saved subjective events replay the correct intact state,
   interaction, destruction and persistent aftermath without live engine access.

A copied sprite is not completion of 2; a passing gameplay test is not visual
approval of 3. The completion table records those separately in this document
and its coverage companion, not in a new runtime certification service.

### Active first unit: placement, windows and existing destruction

The user now prioritizes **multi-cell furniture, windows, attacking and
destroying objects** before broad content intake. This is the first execution
unit; the remaining catalog stays in the plan. Supported-child lifecycle is
also real backend work, but follows this core rather than entering it implicitly.

Destruction is already shared native behavior. Trap hardware is an ordinary
BaseItem composed with Health and ItemDestructionRemnant. AttackObject invokes
BaseItem.receive_damage, which runs TakeDamageEvent/Health and BaseItem.destroy.
Today that path cleans up owned light/conditions/location, places a separate
declared wreck and publishes destruction under its cause. The dedicated plan
migrates that shared owner to persistent destroyed state on the original UUID,
with terminal retirement kept separate. All existing doors, trap hardware and
devices adopt it along with furniture. Ordinary prop bank selection and current
replacement-dependent replay also need that migration; a furniture-only path
would leave the core inconsistency in place.

Use a two-cell bed/table, a one-cell reference item, a solid boundary beside a
fixed barred window, and two observers for the geometric proof. Those are the
initial new geometry profiles; they do not limit the destruction plan's required
adoption of current doors/traps/devices and missing physical counterparts.
Container behavior is proved in that destruction plan. Mounts, movable furniture
player actions, operable shutters, glass, structural collapse and full houses
are not required for this first geometric proof.
Rotation/move checks exercise the existing world-placement API; they do not
introduce a player push/rotate action. Four-camera saved replay proves the
resulting mechanics; large-scale asset copying waits until the core works.

| Core part | Contract and connected owners | Finish evidence |
| --- | --- | --- |
| One multi-cell object | Local footprint offsets in existing placement capability; resolved covered cells in committed placement; one anchor/UUID/HP owner | Both cells block consistently; valid rotations reindex; rejected placement/rotation leaves the prior placement intact |
| Complete spatial consequence | Existing GridMap band indices, tile-detachment checks and barriers; spatial-event affected positions, sensory candidates, light invalidation, world/public reduction use the old/new footprint union | Seeing only the nonanchor end still establishes the proper contact; changes there update paths/light/senses; a covered Tile cannot be detached under a still-placed object |
| Stable identity versus contact | Canonical placement anchor remains fixed; deterministic actually observed/access cell is separate evidence | Changing observer/camera does not move the furniture sprite or choose an arbitrary last-cell contact |
| Manual object access | One eligible reachable footprint point in discovery and execution, with physical obstruction and current state checked | Attack either accessible end; no through-wall access; intentional remote lever controls remain valid |
| Native destruction and wreck | Shared item damage/hooks and same-UUID integrity transition; effective footprint/bands update coherently | Nonlethal hit keeps both cells; lethal hit leaves the original object destroyed with authored physical aftermath and unchanged Tile IDs/conditions; late observer sees settled state |
| Fixed-window aperture | Authored sill/header/clear span at the current boundary query owner; movement bars separate from optical/shot passage | Actual native sight, light and ranged attack pass through the opening; intersecting solid portions block; ordinary walking through bars fails |
| Passive presentation | Existing complete-lineage reduction, generic prop destruction selector and received footprint/anchor facts | Both subjective streams save/replay independently; existing door/trap clips retain their behavior |

Start with an explicitly nonblocking destroyed furniture profile, reusing and
adapting existing remnant data on the same object. Blocking aftermath needs
explicit center-channel data:
occupies_bands is not the same as movement/optical blocking, and current remnant
data does not carry all center blocking flags. Do not claim intact-to-wreck
collision policy is solved merely because a PNG of debris is present.

Window geometry is the main additional query work. Current optical/propagation
edge permission ignores height, and directional FOV caches a boolean by adjacent
edge. An aperture result depends on the original segment's crossing position
and height. Keep reusable geometry cached; do not reuse a context-free aperture
permission across different rays. Diagonal walking may accept either bridge
route, but a straight sight/shot segment cannot bend around a window jamb.

For the first fixed-window proof, explicitly author one representative native
standing-Medium sample for sight and direct shot admission. Use the same sample
policy in that proof rather than implying independently measured eyes/muzzle
positions. No renderer sockets become rules. A distinct shot-origin policy
later requires its actual targeting consumer. Light has its own authored source
height; current LightSourceData is XY-only, so a mounted lamp cannot borrow the
observer's sample by accident. Record the required physical facts and preserve
existing spell-family propagation/recipient policies. No anatomy, cover-per-bar
or stacked-floor system is introduced by these window cases.

Carry aperture geometry as native boundary/item facts through recording and
passive AI/player reduction. Boundary-route evidence and directional summaries
must describe the relevant query sample, not a universal blocked/unblocked edge.
Existing identification, darkness and special-sense rules keep their meaning;
this is geometry work, not a new subjectivity policy. The first C4 window stays
fixed and intact; attacks/destruction are proven on the selected furniture and
existing doors/traps, without inventing broken bars or glass artwork.

Current attacks and spell LOS admission rely on visual contact. Trace and connect
the selected physical segment check at those real admission/query seams; FOV
alone cannot prove an independently chosen shot origin clears a sill. Before
implementing the window, author its concrete aperture/sample values and verify
them against the selected source geometry in a small native case. Unknown values
remain authoring work, not claims that current data already implements windows.

Core execution order: **existing destruction baseline → shared same-UUID
lifecycle and current-family migration → footprint/manual access and multi-cell
destruction → fixed-window geometry and consumers → native narratives and
representative clips**. The dedicated destruction plan specifies its coordinated
native/projection/presentation steps. Then resume supported objects/lights,
full catalog mappings and house assemblies. This reorders section 11's broader
sequence; it does not drop its remaining work or restart the multi-Z discussion.

Baseline rerun on 2026-09-21: uv with the WSL environment, current recovery source,
tests/engine/test_environment_destruction.py: **48 passed in 4.76 seconds**.
Those tests establish existing door/trap behavior only. No multi-cell furniture
or window implementation is claimed by that result.

The narrowed core section was re-reviewed independently by backend_ecs_review
and presentation_antislop_review. Both approved it with no remaining concrete
design blocker after the explicit affected-cell updates, preserved destruction
owner, native window sampling/cache contract and passive-consumer obligations
were recorded. Their approval does not certify unimplemented behavior.

## 2. Source authority and exhaustive coverage

Source root:
/home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/house-prefabs/.

The [consolidated handoff](/home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/house-prefabs/INTERIORS-CONSOLIDATED-HANDOFF.md)
and its current reviewed manifest supersede older art readiness notes. The
source worktree's backend is stale; inspect this recovery checkout for mechanics.
No source hashing, repeated validation sweep or whole-catalog startup audit is
part of intake. Author explicit mappings once and load ordinary selected data.

The [complete coverage companion](INTERIORS_ASSET_COVERAGE_2026-09-21.md)
enumerates exact source IDs, current status and integration categories. Original
dimensions, pivots, filenames and state banks stay in their existing manifests;
do not copy a second media database into Markdown.

| Delivered scope | Treatment in this plan |
| --- | --- |
| 160 item rows: 106 recovered non-foliage, 27 foliage, 21 generated household sets, 6 indoor doors | Account for every row, including unused selections; map many art rows to one item when they represent states |
| 129 accepted destruction subjects / 135 banks | Shared prop destruction plus already installed doors; six extra banks are alternatives, not additional objects |
| 4 held subjects: misc-b22, misc-b48, misc-b49, misc-b50 | Excluded; stopped boat/crane work and ambiguous labels are not revived |
| 6 chest source rows | Three real containers with closed/open pairs A1/A2, A3/A4, B1/B2 |
| 16 installed native door profiles / 17 renderer identities including generic alias | Reuse and reconcile; six indoor designs are already in the 160-row inventory |
| 12 installed doorway trap variants | Reuse their native hardware, controls, damage and remnants; no duplicate trap system |
| 49 furniture choices / 73 families used by saved houses | Cross-reference the asset rows and architecture; these are overlapping views, not additional item counts |
| Architecture register with 225 wall configurations | Filter to the delivered Fantasy A/C/D/E/F/G styles and actual roles; Desert/palisade house expansion is excluded |
| 79 entries excluded from the wall-only study | The companion accounts for all 17 Fantasy and 62 Desert entries; reusable Fantasy stairs/pillars/gables remain, while Desert/palisade house intake stays excluded |
| 12 dressing cutouts, 5 banners, 7 trade signs | Receiver-bound dressing or mounted native objects as appropriate; signs/banners overlap the item inventory |
| 27 foliage groups | Intact authored placement/blocking/dressing; no delivered fracture or thermal media |
| 8 saved prefabs / 14 floors | Preserve all source assemblies; fully integrate the four non-overlapping examples here, retain the others for the separate spatial task |
| 12 thematic building briefs | Reuse asset and room vocabulary; design references, not twelve new service systems or completed maps |

The current code studies remain evidence, not competing execution plans:
[native owners](INTERIORS_MAP_ECS_STUDY_2026-09-21.md),
[content](INTERIORS_CONTENT_STUDY_2026-09-21.md), and
[presentation](INTERIORS_PRESENTATION_STUDY_2026-09-21.md).
Their earlier recommended first-unit restrictions are superseded here.

## 3. One ownership split, using the existing architecture

| Layer | Owns | Does not own |
| --- | --- | --- |
| Native content definition | Stable item ID, name/description, capabilities, physical material, footprint/extent, blocking, health, aftermath, action parameters | Sheet paths, pixel pivots, camera-specific offsets, animation timing |
| Committed native placement and state | Object UUID, actual supporting Tile, world orientation, covered cells, boundary/mount relation, HP, lid/light/mechanism state | A second independent copy of the content profile or renderer pose |
| Presentation binding | Authored visual identity, state-to-bank mapping, image registration, sockets, depth masks, finite playback | Collision, private inventory, light radius, whether an object was destroyed |
| Prefab assembly | Concrete instances, surfaces, boundaries, attachments, entrances and authored local references | A separate runtime world, callbacks, simulation clocks or preview-server logic |

Use current item IDs, visual_item_name and visual_variant_id. Data is passive
and JSON-expressible, so a future TypeScript consumer can read the same authored
presentation facts. No Python callable or Pygame object appears in a content
record. Stable local assembly IDs resolve to normal UUIDs during construction;
the lookup is a build operation, not another runtime entity registry.

Extend existing definitions/builders and WorldPlacementSpec where required.
Compose WorldItem, optional Health, Inventory, existing light owners, handlers and native
actions. StaticBlockerDefinition is health-bearing: use it where that contract
fits, not for harmless dressing by inventing 1 HP. Do not create Table, Chair, Banner or PlasterWall subclasses per art
family. Keep imports directed from cold data into composers/systems; no late
imports, runtime reflection or type checks to escape that ownership.

## 4. Physical authoring contract

These are required meanings, not a demand to create a universal new component
for every column. Reuse existing fields; add only a fact with a real consumer.

| Fact | Representation / owner | Acceptance |
| --- | --- | --- |
| Identity and state variants | Existing native and visual IDs; state in its current owner | Open/closed chest is one UUID; appearance cannot silently change mechanics |
| Anchor and placement kind | Existing supporting Tile and center/boundary placement | No floating item or replaced floor to simulate furniture |
| Horizontal footprint | Small authored local cell offsets on placement capability; one committed resolved footprint | Rotation reindexes old/new cells and invalidates affected senses; movement, removal and reach agree for a two-cell bed |
| Vertical extent | Existing physical height units relative to support; explicitly authored interval | Low furniture and tall cupboard are not both arbitrary sprite-height blockers |
| Blocking channels | Movement, optics and propagation independently, at current native query owners | Walk, light/sight and legal effect paths agree with each object's intended role |
| Physical orientation | Native cardinal direction transformed once from source facing | Camera rotation changes neither occupancy nor access |
| Approach/access | Authored access side/socket where needed; shared manual interaction admission over eligible footprint cells | Discovery and execution agree on reach and obstruction; no use through an adjacent solid wall |
| Exposed support/mount | Optional parent UUID plus named physical mount/socket and floor support; owned by location/placement | A cup is visible on its table without being private inventory |
| Material and durability | Native material/responses plus authored targetability, HP and remnant profile | Painting trim gold does not produce a new physical material or immunity |
| Available actions | Existing container, light, door or other explicitly selected capability | Static furniture has no fabricated use action |
| Aftermath | Same native item UUID, destroyed integrity/profile and effective placement/blocking, plus supported-child policy | Destroying furniture releases the intended cells and leaves persistent facts |
| Surface/dressing receiver | Existing support/boundary identity and authored variant/placement | Grime follows its receiver and never becomes a hazard by accident |

Art labels such as mixed and source-authored components are not Material enum
values. Select existing physical profiles and author exceptions only for real
mechanical differences. No numerical HP, light radius or aperture size is
claimed measured by this plan. The first authoring pass supplies those values
from current content conventions and source geometry; a field with unknown
meaning is not filled with a magic zero to make an importer pass.

Source floor elevation, native five-foot height steps, physical mount height
and image pivot are different quantities. A cup's local lift must not raise
its floor. Preserve current physical quantization where sufficient; if a selected
aperture or mount needs finer physical bounds, extend that existing geometry
value and consumer narrowly. Do not use rounded image pixels as collision.
Exact pixel attachment offsets remain presentation data. No new floor-address
scheme is designed here.

Source facing and source sprite pose may differ. Convert both deliberately;
the source compass uses E=+X/S=+Y while native NORTH=+Y. Derive footprints,
boundary sides, access directions and visual row registration from that single
conversion. One asymmetric four-rotation test must prove the whole transform.

## 5. Content families and their gameplay meaning

The companion lists each row; this table specifies the shared capabilities
those rows must use. Each category is an authoring pass, not a new hierarchy.

| Family | Native behavior to author | Limits / resulting state |
| --- | --- | --- |
| Tables, benches, beds, counters, desks, chairs and stools | Passive WorldItem; explicit footprint/height/blocking/HP/remnant; support sockets where actually used | No seating, rest or crafting required; a table may support exposed children |
| Wardrobes, shelves, racks, stands and display furniture | Same physical owner; distinguish free-standing from wall-mounted | A closed storage capability is added only to selected actual containers; do not hide every shelf's objects in Inventory |
| Three chest styles | Existing StorageChest lid/loot/inventory and native breakable lifecycle | Exact paired state art, causal released contents, matching stable wreck |
| Crates, ordinary barrels, pottery, sacks and small floor props | Passive content by default; explicit durability and physical aftermath | Existing oil barrel remains specialized; no oil or loot inferred from shape |
| Ovens, stove/fireplace bodies and workshop tools | Physical furniture; active light/fire only if explicitly composed | No automatic campfire Cook/Rest action; heat/damage is not inferred from glowing art |
| Candles, holders, lamps and wall fixtures | Existing fixed/portable light owner as appropriate; authored lit state/radii and mount | Distinguish a holder from a light; native extinguish/destruction removes the source |
| Tableware, papers, ink and other exposed small items | Passive item or grouped dressing where the source is a single inseparable set; parent/socket placement | No invisible private inventory; supported aftermath must be native |
| Banners, trade signs, wall shelves, utensils, tools and ivy | Wall-facing mount with height and real native identity if independently selectable/destroyable | No floor blocker from a hanging image; no invented sign-reading/quest system |
| Statues, gravestones, cages, specialist props and unused decor | Explicit physical profiles and approved destruction where delivered | A cage may block but does not gain jail/restraint rules; ambiguous held IDs stay held |
| Rugs and cosmetic floor/wall marks | Receiver-bound visual dressing, normally nonblocking | No arbitrary HP/hazard object per stain; existing blood/ash remains condition-driven |
| Bushes, plants and other foliage | Explicit intact physical or dressing category; wall ivy stays mounted | Do not promise thermal response/fracture; missing response art remains documented |
| Doors and doorway traps | Existing profile IDs and composers, including state, controls and health | Preserve their installed opening/depth/destruction and current gameplay |
| Walls, corners, windows, frames, partitions, rails and pillars | Structural physical profiles plus authored visual family | A frame cannot seal an otherwise open door; decorative trim shares its structural owner |
| Floors, stairs, roofs, roof edges and rubble | Real support, terrain/boundary or dressing according to explicit role | Roof art is not automatically a walkable floor; stairs retain current traversal rules |

Current environment.blocker.crate is **nonblocking**. Preserve that content;
if a house requires a blocking crate, author an explicit distinct profile.
Do not silently reinterpret an existing item ID to match a preview.

The exact delivered banks are approved images, not a universal destruction
simulation. An asset appearing in two source inventories is integrated once.
Appearance aliases may share one physical profile; states of one object share
one identity; genuinely different capabilities need different native profiles.

## 6. Placement, reach, navigation and observation

Extend GridMap's existing placement ownership to index one object's UUID in
every cell of its finite footprint. Do not create invisible child blockers or
duplicate HP owners. Preserve the supporting floor under every occupied cell,
its conditions and its identity. Destruction updates placement and sensory
invalidation once through the current transaction/event route.

Consumers must use that same footprint: walking/corner passage, legal action
reach, attack targeting, nearby item listing, geometric object enumeration and
observation. A query covering both bed cells enumerates that object once.
This does not add objects to creature-only spell recipients: current AoEShape
collects entities, and Fireball's damage resolves Entity recipients. Preserve
each action's recipient policy. Object-damage acceptance uses the actual native
AttackObject path; any future object-affecting area operation must deduplicate
its eligible object UUIDs without silently expanding every spell here. A player
who sees the end of a bed can discover that object under existing rules even
if its anchor is out of view; that does not reveal hidden floor cells, contents
or the rest of the room. Preserve object discovery versus cell disclosure as
separate facts at the current projection owner. Current sensory object-contact
collection assigns by UUID once per candidate cell; multi-cell indexing alone
would leave an arbitrary last-cell contact. Resolve a deterministic actually
observed contact/access cell, distinct from the object's physical anchor, and
preserve the needed received facts. Discovery must not depend on index traversal
order. Existing orient_object also updates single-cell placement metadata;
footprint rotation must update occupied-cell membership, not merely orientation.

Do not import the preview's reachable graph as native pathfinding. In layout 1,
96 physical floor cells become 75 preview walkable cells after furniture; in
layout 6, 64 become 53. Native floors come from level cells and actual openings,
then native placement/blocking determines paths. Destroying the bed must expose
existing floor, not create a new Tile or leave a permanent hole.

Preview approach cells are useful assembly/access evidence. They are not a new
exclusive interaction coordinate unless an authored action really requires a
particular side. Current PickUp and AttackObject validation checks anchor XY
distance; chest action validation checks chest state, and discovery filters
object contact distance. These do not already establish the required footprint
reach or through-wall protection. Extend shared manual world-interaction
admission at both action discovery and execution: select an eligible reachable
footprint cell/side and apply the relevant native boundary obstruction rule.
Recheck actual position/state on invocation rather than trusting an old menu.
Keep existing range/cost semantics. Do not add universal source-item proximity
to BaseAction: ToggleLeverAction intentionally invokes linked object actions
remotely under the lever's causal effect. Preserve that authorized remote path.
A chair's
approach_via_seat marker does not implement a sit action or permit walking
through a table. Keep the intended two-cell circulation and doorway access.

## 7. Attachments, mounting, lights and destruction

Use one passive exposed-support relation at the existing location/placement
boundary for selected tabletop and wall fixtures. Store parent UUID, authored
mount/socket and resolved physical placement/floor relation. Keep one authority
for location; do not create independently mutable parent and floor positions.
The relation is part of native and observed state, not just renderer sorting.

Author a finite child aftermath per selected capability: release intact to the
floor, become destroyed under its own authored profile, or remain attached to
the same destroyed parent
when that is explicitly supported. Initial useful examples are tableware
breaking onto the floor and a surviving item being released intact. No physics
simulation, arbitrary recursive scene manager or silent child deletion is
needed. Use current item/location/damage events in the parent's full lineage.
Removing or relocating a parent must update children coherently; prohibit an
unsupported live move instead of leaving them behind at stale coordinates.

The same relation must be cleared when the child is picked up, independently
destroyed, transferred or merged through existing item/location owners. A cup
removed from its table cannot be released or damaged a second time when the
table later breaks. Exercise a real pickable child, pick it up, then destroy
the parent and replay that lineage; do not infer cleanup from parent-only tests.

Exposed children are not Inventory. A closed chest's unseen contents stay
private; a cup on a table is independently observable. If the parent is not
known to a receiver, the projection must still supply a usable disclosed child
location without exposing a private parent/object graph. Use existing subjectivity
rules; do not rewrite them to make the gallery convenient.

StorageChest._on_destroy currently ignores the supplied parent_event when
placing contents. Before changing it, record a real spill and check causal
ancestry; then thread the existing parent through the hook if the reproduction
shows missing ancestry. This is an acceptance obligation, not a claim that a
projection bug has already been reproduced.

Wall/candle lights reuse current lit state, brightness and source cleanup. The
standing-torch helper exists but was not in the inspected direct registry;
registration and a factory's existence are separate. A new fixture needs both
native placement and native illumination, plus authored on/off appearance.
Light motion/extinguishing/destruction updates senses through existing owners.

Mounted destruction needs matching entry and final receiver registration.
A floor-baked fracture bank raised onto a wall leaves hovering debris. Verify
the source mount for every mounted bank. If absent, keep correct native aftermath
and record the exact media request; do not relabel that asset visually complete.
Static placement and gameplay can proceed while a matching transition is authored.

## 8. Architecture and usable windows, on existing maps

Preserve all in-scope family identities A/C/D/E/F/G. The source register mixes
wall families with frames, windows, open timber and decorative pieces. Classify
those roles explicitly; do not register all 225 configurations as solid walls.
Existing Material alone cannot select the correct wall style. Consume the
existing visual identity and group only compatible geometry/style in drawing.

Build structural boundaries and their visual parts together. A doorway has its
frame plus existing door leaf/state; it does not get a second permanent wall
blocker. Open timber bays, full masonry, rails and windows have distinct channel
and height profiles. Roof/floor/trim roles also remain distinct. Layout 6's 130
terrain-tagged images include 64 floors, 64 roof decks and two rugs: the tag
alone cannot decide where a character can stand.

For floors, compare delivered surface variants against current floor bindings;
if identity is missing, extend current surface facts with a small authored
variant carried through initialization/deltas. Do not create a new material
per image or query the live prefab to choose the surface in replay.

**Windows are gameplay openings.** The source C4 window is barred, C6 is an
arch. Fixed bars are not an operable shutter. Author the selected sill/header
and clear span; sight/light and legal shot paths can pass through that aperture,
while the frame and sill still obstruct paths that intersect them. Movement
passage is separate from optics/propagation; bars can stop a body without making
the whole opening opaque. No per-bar projectile simulation is required.

Current world_edge_contribution_allows treats listed nonmovement channels as
blocked regardless of vertical span. Therefore adding profile numbers alone
does not implement apertures. Extend the shared local boundary query only as
needed for the selected windows and route native sight/light/shot consumers
through the same authored geometry. Keep the current distance, cover and
shape-propagation owners; an aperture does not justify changing spell rules.
Mechanical sight/shot samples are not renderer hand sockets. Any unresolved
height policy must be stated before claiming a below-sill shot is tested.

Unbarred, physically passable openings may use an explicit paid native traversal
between existing supported spaces, preserving movement costs, reactions and
arrival contact. Existing PASSAGE/connector machinery is a candidate, not proof
that a window-crossing action and animation already work. Fixed barred windows
need no fake open action. Operation or breakage of a separate closure is added
only where that closure and its chosen behavior exist; no speculative glass,
shutter or structural-collapse system is required for these delivered frames.

Stair and roof assets receive explicit roles, registration and physical extent.
Current gradual terrain steps can exercise stair art between existing supported
spaces without designing stacked floors. The generated timber stair is unused
by the saved examples and needs its own content placement example. Roofs are
visual/collision structure as currently supported, never fictitious traversable
Tiles just to render their images. Absent guardrails or unsupported structural
behavior stays explicit; do not fabricate mechanics from an incomplete image.

## 9. Media integration through the existing presentation route

Add one shared plain-prop entry and state selection to environment_art and its
existing world transitions, migrated to same-object destroyed state. Current selection admits doors/traps and
remnant_bank requires door/mechanism state; ordinary furniture has neither.
An ordinary prop must work without pretending it is a door, trap or device.
Use observed damage/destruction/state facts, the existing contact schedule and
independent historical playback. No per-item if/else executor or new event queue.

Each binding preserves sheet cell, pivot, direction rows, FPS, frame count,
intact/wreck registration and any supplied depth data. Current accepted banks
happen to use 384-pixel cells; that is not a universal scale or footprint.
Do not allow importers to copy another item's behavior then patch it later.
One authored binding owns final state-to-media choice.

For chests, integrate A3/A4 first (used by the prefabs), then A1/A2 and B1/B2
as explicit styled pairs. Use each reconstruction's matching intact/open entry
images with its destruction. Preserve the generic original A1/A2 baseline until
that exact reconciliation is reviewed. No smooth chest-opening bank was
delivered: current lid state changes at interaction contact remain valid.
Do not reverse destruction as opening. Show the full roughly 5.7–6.1-second
authored collapse initially; do not invent timing surgery before seeing it.

Persist final wreck state for late observers without replaying the destruction.
The selected collapse and its later wreck must agree even on a fresh replay;
late discovery cannot reroll a bank or select it from the wall clock.
Select any accepted alternative bank through an explicit deterministic binding;
impact-a/b names do not by themselves mean left/right hit direction. Native
mechanical aftermath comes from the original item's destroyed profile, never
the selected pixels. Preserve actual old replacement-based saved histories at
the passive compatibility boundary, as specified by the destruction plan.

Dressing uses twelve existing receiver-bound cutouts: floor marks may rotate;
wall streaks remain upright. Five banners, seven signs and foliage reuse their
source directional art. A stain need not become a damageable entity; a separately
attackable banner must have a real item. Keep blood/ash in their existing
condition/residue route rather than assigning all cosmetic dirt a condition.

Depth/cutaway remains presentation of already disclosed facts. Current production
has no roof/cutaway control; that feature exists only in the art preview. Begin
with a deliberately roofless presentation of the assembly. To include roof
pieces in the final content review, add a minimal explicit local roof visibility
selection over received assembly parts; no automatic cutaway system is required.
Roof visibility changes no native state. A camera hiding a wall cannot grant sight
or change collision. Use actual actor/furniture/door intersections in all four
cameras; do not port the preview's whole-house painter order, forced-open doors,
parent-child deletion or HTTP-driven animation state.

## 10. Concrete assemblies and source conversion

Convert the saved source records offline to passive native assembly data.
No runtime dependency on the preview server, Blender code or another worktree.
Preserve explicit component roles, physical floor coverage, orientations,
door boundaries, selected item identities, mounts, approaches and entrances.
Old embedded furniture animation paths are stale; resolve family IDs through
the current reviewed mappings instead of retaining those paths.

| Saved layout | Role in this integration |
| --- | --- |
| 6 L-shaped lodge, style C, 64 physical floor cells, 12 furniture placements | First complete furnished layout after shared mechanics; includes a two-cell bed, tableware, wall fixtures and five doors |
| 1 Long merchant house, style C, 96 physical floor cells | Containers and more room/door circulation, with actual native floors beneath furniture |
| 5 Courtyard residence, style D | Interior/exterior transitions, courtyard routes, views and lighting |
| 7 Garden wings, style G | Concave footprint, garden foliage, open structure and mounted dressing |
| 0, 2, 3, 4: artisan, townhouse, great hall, apothecary | Preserve their complete source records and all reusable content; full overlapping-floor assembly belongs to the separate task |

Cover styles A/E/F and unused items in compact content rooms rather than
inventing replacement saved houses. Rooms demonstrating a selected upper-course
wall or unused timber stair are content fixtures, not claims that an omitted
storey has become playable. The twelve themed briefs remain recipes for future
content composition, not automatic new mechanics.

One builder composes these assemblies through current battlefield/map/item
owners. Cold initialization emits the existing WorldInitializedEvent then
settles native lights/conditions in the existing order. Live changes use existing
causal world/item mutations. Do not publish fake animation events from the
importer or serialize the entire house again on each damaged chair.

## 11. Implementation sequence with concrete finish conditions

These are consecutive units of the same complete plan. After authorization,
proceed through them without asking the user to supervise each data row.
Resolve ordinary profile choices from current conventions; return only actual
new gameplay decisions or demonstrated missing source material.

| Step | Work and current owners | Evidence that the step is complete |
| --- | --- | --- |
| A. Author the content mappings | Begin with core proving profiles; expand authored_item_definitions/builders, environment_item_builders and current presentation registries after core acceptance | Eventually every in-scope source has a role, selected native profile and media state mapping; exact values authored before registration; held rows excluded |
| B. Shared furniture placement | WorldPlacementSpec/WorldObjectPlacement, GridMap, targeting/listing and projection consumers | Two-cell rotation/reindexing, observed contact, manual reach/admission, collision and unique object enumeration; recipient rules unchanged; removal exposes existing floor |
| C. Damage, containers and aftermath | Dedicated same-UUID destruction plan; BaseItem/Health/hooks and existing state/projection owners | All current breakable families migrate; real attacks, coherent destroyed properties, terminal consumption intact, causal chest spill and observed late state |
| D. Supported and mounted objects | Existing location/placement, light ownership and public facts | Tableware release/break, surviving item release, wall light extinguish/destruction, no leaked inventory or floating child |
| E. Structure and apertures | Existing boundary queries, wall/surface definitions, native visibility/targeting | Solid neighbor blocks; window permits legal sight/light/shot; sill/frame and bars block appropriate paths; style identity retained |
| F. Full accepted media/content intake | Current EnvironmentArt, world bindings, world transitions and remnant selection | All accepted relevant state/alternative banks bound or explicitly held for a documented mount gap; all intact foliage/dressing/categories placed |
| G. Saved house assembly | Offline source adapter plus existing battlefield construction | Four actual single-storey layouts playable and recorded; all remaining reusable content exercised in compact rooms; no silently omitted parts |
| H. Final integration review | Existing native/replay tests, type checks and clip extractor | Catalog coverage reconciled, affected regressions green, subjective saved replay and representative four-camera clips inspectable |

B/C/E form the first core unit with a small fixed set of assets. D and the bulk
of A/F follow that core; see the active first-unit contract in section 1.
Do not make one art asset block unrelated backend capabilities. Do not stop at
the first room and call the 160-row integration complete. The separate task's
spatial work is not a prerequisite for A–H as defined here.

## 12. Acceptance narratives and efficient tests

Follow [HOW_TO_TEST](../HOW_TO_TEST.md). Public native commands and resulting
state/events are primary. Data coverage checks are ordinary development tests
at initialization/registry boundaries, not a startup audit or checksum system.
Parameterize actual capability variants; do not run a full movie per table row.

| Narrative | Required observable result |
| --- | --- |
| Move around and destroy a two-cell bed/table | Path and corner access obey rotated footprint; HP/damage owned once; released cells retain Tile identity/conditions |
| See only the far end of furniture | Correct object discovery without revealing hidden cells or private objects; live and recorded projection agree |
| Interact across a wall / from a valid far-end approach | Manual action discovery and execution reject blocked or stale access and permit the reachable end; linked lever actions retain intentional remote use |
| Enumerate and attack a multi-cell object | One UUID per geometric query and one HP/destruction owner via real AttackObject; creature-only area spells retain their recipient policy |
| Open, close, loot and destroy each chest style | Correct availability, both lid states, contents released causally, unseen inventory private until legitimately observed |
| Break table with exposed children | Real child release/break events and grounded aftermath; a surviving child remains selectable; no renderer-only deletion |
| Pick up child, then break parent | Mount relation ends during the native transfer; inventory item is not dropped/destroyed again; saved causal replay agrees |
| Two items share XY | Existing target list/Tab distinguishes relevant targets; no new pixel-picking framework required |
| Turn off, relight and break a mounted light | Native illumination and observer knowledge change; destroyed source leaves no ghost light |
| Opposite sides of window and adjacent solid wall | Intended sight/light/shot through aperture; blocked sill/frame path; barred body passage rejected; chosen passable traversal obeys costs/contact |
| Walk/use/break doors near furniture | Current opening contact, occupied-door behavior, inward leaves, trap controls and destruction still work |
| Damage unseen prop; later enter room | No hidden animation/state leak; newly discovered final remnant appears without past collapse replay |
| Visit lodge, merchant, courtyard and garden | Native circulation, actual doors/fixtures, exposed and private items, indoor/outdoor sight and persistent aftermath |
| Rotate one asymmetric content room | Same physical world across cameras; correct footprint/facing/mount/decal and source sprite rows |
| Save once, replay repeatedly | Full causal records reduce independently; no native constructors, private registry or source-preview access during replay |

Inspect both subjective participants and all four cameras for representative
capabilities, including windows, attachments and destruction. Reuse the current
clip extractor and saved-input gallery; labels identify content IDs and states.
Static contact sheets can cover art-only variants. Long accepted destruction
tails need one complete state/registration review, not a new animation scheduler.

Keep approved door/trap, height/jump, wall clipping, blood/ash and subjective
replay checks at the seams actually touched. Run native feature tests first,
then affected replay/presentation and typing; complete relevant broader suites
at the integration boundary. Repair demonstrated failures rather than recording
them indefinitely as preexisting. No tests have run for this planning-only work.

## 13. Performance and scope guardrails

Measure native construction/initial senses separately from asset load, rendering
and video encoding. Use the documented WSL/uv environment. No eager decoding
of every sheet for an unrelated scene, deep copy of whole maps for an item hit,
repeated serialization, source scan, hash guard or new validation framework.
Reuse placement indices, sensory invalidation and world deltas. Measure actual
changed behavior; this is not a return to an open-ended optimization project.

No new VFX generation session, generic physics, flight/falling, procedural
runtime city generator, structural collapse, equipment rewrite or inventory
redesign is part of the plan. No one-off backend animation cue. Document an
actual missing mounted bank before requesting art; already accepted matching
assets are reused directly. Multi-Z remains entirely with its separate task.

## 14. Independent review and status

The earlier small-lodge plan had completed content, anti-slop and ECS reviews.
They do not automatically approve this expanded plan. This revision requires:

- **Anti-OOP/ECS correctness:** passive definitions, one owner per placement/state,
  native lifecycle, footprint consumers, disclosure and causal replay; no new
  object hierarchy or hidden second world.
- **Anti-slop:** all additions serve actual delivered content, sources reused,
  no speculative subsystems, no Z migration brought back through this plan,
  meaningful completion and bounded tests/cost.
- **Content completeness:** every source row/category accounted for once, state
  pairs correct, exclusions preserved and missing mounted media honestly named.

All three reviews completed for this expanded revision. Reviewers read the
coverage companion as well as the main plan; the ECS reviewer re-read the
amended sections and reported no remaining concrete plan blockers.

| Reviewer / severity | Concrete finding | Incorporated resolution |
| --- | --- | --- |
| backend_ecs_review, P1 | Current area spells collect Entity recipients; a bed-blast promise silently widened spell rules | Separate unique geometric object enumeration from each action's recipient policy; real damage acceptance uses AttackObject |
| backend_ecs_review, P1 | Anchor-only distance checks and chest state checks do not establish legal multi-cell use | Shared manual discovery/execution admission over reachable footprint contacts, obstruction/stale-state checks; retain intentional remote lever invocation |
| backend_ecs_review, P1 detail | Index expansion alone leaves arbitrary last-cell sensory contacts and stale rotation memberships | Deterministic observed contact distinct from anchor; rotation updates old/new occupied cells and invalidation |
| backend_ecs_review, P2 | Parent-only attachment cleanup misses child pickup, merge and independent destruction | Clear relation at existing item/location transitions; add pick-up-child then break-parent native/replay narrative |
| presentation_antislop_review, P2 | Production has no existing roof/cutaway UI; that was preview-only | Explicit roofless initial presentation; minimal local received-part roof visibility for final roof review, without claiming an existing control |
| presentation_antislop_review, P2 | Wording about selected architecture could hide omitted unused assets | Point to exhaustive 17 Fantasy / 62 Desert exclusion dispositions, all wall roles and 12 roof variants |
| presentation_antislop_review | Alternative collapse selection must match a late observer's wreck | Explicit deterministic selection across replay/admission; no fresh random or clock choice |
| spell_orientation_antislop, content | Check complete identity sets, paired states and scope | All 160 matrix rows, 49 choices, 73 used families / 3,171 parts and 135 approved bank paths reconciled; held/stopped assets preserved |

Final decisions: **anti-OOP/ECS approved; anti-slop approved with the documented
amendments applied; content coverage approved.** The anti-slop reviewer also
independently compared the 160 item IDs and 73 used-family table to source, with
no omissions, extras or duplicate IDs. Counts and path comparisons used ordinary
metadata, not source hashes. Local links in the plan and companion were checked.

These approvals concern the plan. No production code, asset registration or
new clips were changed for this planning unit. No new gameplay tests were
written; the subsequent core-first study reran the existing destruction module
with 48 passing tests, as recorded in section 1. Physical
values still need the declared authoring pass, and missing mounted transitions
remain visually incomplete until supplied and reviewed. The planned sequence
and acceptance cases must not be reported later as completed implementation.
