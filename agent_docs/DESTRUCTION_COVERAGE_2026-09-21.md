# Destruction coverage and missing-art ledger — 2026-09-21

Status: **baseline inventory plus validated core implementation (September 22)**.
The tables below describe the pre-implementation checkout. Current-family
migration, the three chest identities, seven ground bodies and bed/table proof
are now implemented. Selected accepted prop art is installed; new fixture art
from the user's asset task remains explicitly unapproved. Track current evidence and
uncompleted adoption in [the implementation record](DESTRUCTION_IMPLEMENTATION_2026-09-21.md).
Companion to [the destruction lifecycle plan](DESTRUCTION_LIFECYCLE_PLAN_2026-09-21.md)
and [the exhaustive interiors asset coverage](INTERIORS_ASSET_COVERAGE_2026-09-21.md),
under [RECOVERY_PLAN](../RECOVERY_PLAN.md). The requested result is an intact
world item becoming destroyed **with the same item UUID**. Actual removal,
consumption and spell-object retirement remain separate operations.

This ledger describes the studied baseline first, then the required work. Its
counts are content identities or delivered subjects, not instances or guarantees
that every spell can damage every object. Current direct Python definitions and
builders are native authority; detached art previews are not backend definitions.

## 1. Reconciled native and media inventory

| Inventory | Count | Meaning |
| --- | ---: | --- |
| Direct item builders | 179 | Current `DIRECT_ITEM_BUILDERS`; helper-only objects are listed separately below |
| Registered environment identities | 43 | 34 default health-bearing, targetable items plus 9 default nonbreakable identities |
| Other registered items | 136 | Gear, weapons, wearables, consumables and spell-granting equipment; do not make these all damageable |
| Default destructible species | 34 | 16 authored doors + 12 blade/crusher hardware + 2 spell-device bodies + 3 static blockers + 1 oil barrel |
| Those species with installed intact, finite break and settled wreck art | 30 | The 16 doors, 12 hardware and 2 device bodies |
| Those species missing installed art, including their intact binding | 4 | Crate, boulder, barricade and oil barrel |
| Installed door renderer entries | 17 | 16 authored doors plus the generic `environment.directional_door` alias; the alias is **not** a seventeenth default health-bearing door |
| Installed environment-art wreck mappings / animation banks | 40 / 146 | Door and trap media inventory; device media is separately registered. These are not additional gameplay species. |
| Delivered interiors matrix | 160 | Exact rows are already enumerated in the coverage companion |
| Accepted destruction subjects / selected banks | 129 / 135 | Current reviewed source authority, not the superseded 133 / 139 handoff |

The lifecycle plan's section 9 defines the required adoption set. Current-state
rows saying “no Health” or “no hardware item” identify work to do; they are not
reasons to omit ordinary doors, delivered props, containers, light/control
fixtures or the listed physical ground-trap counterparts. Explicitly excluded
abstract effects, temporary objects, terrain and unselected structural collapse
remain outside that set.

Source inspection: `dnd/content/items/authored_item_builders.py`,
`authored_item_definitions.py`, `environment_item_builders.py`,
`door_profiles.py`, `trap_hardware_builders.py`; presentation selection in
`game/data/environment_art.json`, `world_bindings.json`, `spell_devices.json`
and their existing loaders. Counts were checked against current cold tables,
without constructing a map, running the game, hashing assets or adding a runtime
audit.

## 2. Every default destructible native family

### Doors: all 16 profiles and the generic alias

Every authored door below has one native item, Health and `AttackObject`
eligibility. Its current destruction creates a **different** remnant UUID;
the new lifecycle must retain the original UUID while preserving these physical
outcomes and the already approved art.

| Exact native IDs / finite expansion | Count | Native intact properties | Supplied break / aftermath |
| --- | ---: | --- | --- |
| `environment.door.fantasy_a1`, `environment.door.desert_a1` | 2 | Wood, double hinged, 18 HP, closed movement/optical/propagation channels, extent 2 height steps | Closed/open inward/open outward; clear or jammed |
| `environment.door.{fantasy\|desert}_c{1\|3\|5}` | 6 | Metal lift gate, 27 HP, closed movement channel only, extent 2 | Same three recorded entry selections; clear or jammed |
| `environment.door.desert_c7`, `environment.door.desert_c9` | 2 | Wood, single hinged, 18 HP, all three closed channels, extent 2 | Closed/open inward/open outward; clear or jammed |
| `environment.door.indoor_door_{shabby\|shabby_plain\|shabby_battens\|shabby_patched\|elegant\|elegant_three_panel}` | 6 | Wood, single hinged, 18 HP, all three closed channels, extent 2 | Closed/open inward/open outward; **clear only** |
| `environment.directional_door` | Alias, outside 16 | Default generic constructor has no Health and is not targetable | Renderer alias has full door media; native durability/destruction policy is not thereby authored |

Brace notation denotes the exact Cartesian expansion, not arbitrary family
matching. Clear remnants contribute no blocked channels; jammed remnants retain
movement blocking. Existing remnants preserve door material, boundary placement,
elevation, open state and swing. The six indoor profiles explicitly reject a
jammed outcome; do not request another bank or enable that outcome by accident.

The installed media covers settled entry states, **not** a matching fracture
from every possible intermediate opening frame. Native break/disable must happen
at its actual event boundary, without waiting for a cosmetic opening to finish.
Retain this limit until a real interruption case needs a visual policy.

### Physical trap hardware: all 12

Exact IDs are the complete product
`environment.trap.{swinging_blade|crusher}.{stone|wood}.{workshop|brassbound|fortress}`.
Stone profiles have 27 HP; wood profiles have 18 HP. All are nonpickable,
targetable physical items with an independently owned `FiniteTrap` attached by
`WORLD_OBJECT` anchor to that item's UUID. Their default payload is 1d6 slashing
for a blade and 1d6 bludgeoning for a crusher. Damage payload, save, visibility,
direction and rearming are existing mechanism data, not animation behavior.

All 12 have installed intact/activation, break and stable wreck media. Entry
states are ready, activated and deactivated; ready/deactivated share a bank.
They support the four native cardinal placements and camera-specific rendering.
The current `{item_id}.wreck` remnant is not another trap; it does not retain
the old mechanism's damage capability.

Migration obligation: physical destruction must deactivate **that mechanism**,
including pending activation/rearm, while retaining the destroyed body UUID.
The linked pressure plate and other outputs remain independent. Presently the
anchor handler in `dnd/spatial/area_conditions.py` deactivates on
`SPATIAL_OBJECT_REMOVED`; `SPATIAL_OBJECT_CHANGED` only relocates it. A retained
destroyed body therefore needs the real lifecycle change to reach this existing
owner. Fake removal/reinsertion is not the solution. The item's delegated trap
perception also needs to retain legitimately observed wreck state after the
mechanism stops, without revealing an unseen hidden trap.

### Spell devices: two body identities, independently authored spells

| Native body | Current default grant | Native durability / ownership | Supplied media |
| --- | --- | --- | --- |
| `environment.fireball_cannon` | Fireball; default 3 charges | 32 HP, nonpickable, targetable, concentration capacity 2 | Intact/aiming, 8-frame break at 12 FPS, matching stable wreck; pitches 0/15/30/45 and four cameras |
| `environment.arcane_machine_gun` | Sleep; default unlimited charges | Same default Health and concentration capacity | Matching body-specific intact/break/wreck coverage |

`build_spell_device` accepts separate spell templates. Existing Sleep-on-cannon,
Fireball-on-cannon and Web-on-device scenarios reuse these body identities;
they are **not** additional cannon species or new destruction art requests.
Scenario HP overrides such as 8 or 12 HP are fixture choices, not catalog values.
A custom third `item_id` accepted by the helper does not automatically acquire
an authored remnant or media mapping.

Preserve all owned maintained-effect cleanup, independent operator effects,
actual hit flash, selected aim/pitch and destruction contact. Destroyed devices
must stop granting fire/use actions while remaining present. Spell effects end
according to their existing ownership; an instant payload does not become a
maintained spell merely because a cannon fired it.

### Four native destructibles without installed presentation

| Exact native ID | Current mechanics | Current presentation / delivered counterpart | Work needed |
| --- | --- | --- | --- |
| `environment.blocker.crate` | 20 HP; center, height 1; all blocking flags false, does not occupy bands | No installed item binding, break or wreck. Delivered `misc-b1` / `fantasy.misc.b1` has approved intact/collapse/settled art | Reconcile exact art/profile; retain this nonblocking identity or author a separate deliberate blocking variant. Add destroyed state/media. |
| `environment.blocker.boulder` | 30 HP; center, height 1; occupies bands; movement and propagation block, optical does not | No installed item binding/break/wreck; exact delivered counterpart not identified in the 160-row matrix | Identify source art first. Then explicitly author intact registration and persistent physical aftermath; request missing art only if no suitable delivered source exists. |
| `environment.blocker.barricade` | 20 HP; center, height 1; occupies bands; movement, optical and propagation all block | No installed item binding/break/wreck; exact delivered counterpart not identified | Same identification step. House palisades and arbitrary rubble are not an automatic identity match. |
| `environment.blocker.oil_barrel` | 12 HP; blocks movement, not optics/propagation; real destruction hook creates OilSurface; fire damage can ignite it | No installed barrel binding/break/wreck. Delivered `misc-a8` / `fantasy.misc.a8` supplies barrel art; current oil/burning surface also lacks an explicit game spatial binding | Bind selected barrel art without losing the native spill/ignition. Track floor-effect presentation separately from barrel collapse. An ordinary barrel is not automatically an oil barrel. |

These four currently disappear on destruction without an authored remnant.
Preserving their existing intact physical defaults is distinct from authoring a
new destroyed aftermath. Do not infer rubble blocking from the picture.

## 3. Existing native content outside the default breakable count

These objects must be considered by the lifecycle work without pretending they
already have damageable hardware. Health is optional content, not a requirement
for an item to exist.

| Native identity / composer | Current behavior and art | Destruction disposition |
| --- | --- | --- |
| `environment.storage_chest` / `StorageChest` | Open/close/loot/inventory; default no Health or targetability; installed static original A1/A2 | Explicitly author damageable container variants. Existing `_on_destroy` spills contents, but new same-UUID state and causal spill coverage are required. Replace intact and broken art together using the approved reconstructed pair. |
| `environment.wall_torch` | Registered light/use fixture; default no Health; installed lit/unlit/use art | Add the breakable counterpart with Health/profile, preserve light-owner cleanup, supply a matching broken body. No break/wreck currently selected. |
| `environment.trap_lever` | Registered trap control; no default Health; installed use animation | Add durability, control-contribution cleanup and matching wreck. A use/toggled frame is not a broken frame. |
| `environment.directional_wall` | Generic boundary, default stone; no default Health | New structural/window profiles need explicit selected durability and aftermath. Generic wall capability is not complete destructive wall content. |
| `environment.cliff_face` | Movement-only boundary, no default Health | Terrain-like boundary, not automatically a destructible loose boulder. No new damageability implied. |
| `environment.directional_door` | Generic door noted above; no default Health | Give the ordinary production door an explicit native durability/destruction profile consistent with its current art alias. Deliberately nonbreakable helper fixtures require explicit authoring; media alias alone is insufficient. |
| `environment.arcane_device` | Arcana-gated healing/use device; no default Health | Separate from the two spell cannon bodies. Do not claim its health, concentration slots or cannon art by name similarity. |
| `environment.campfire` | Existing Rest/Cook/use behavior; no default Health | Do not equate extinguishing with breaking a solid body. Any fixture durability/light behavior must be authored separately. |
| `environment.spell_object.heroes_feast` | Temporary spell-owned usable object; no default Health | Preserve eating/expiry/removal semantics. Not automatically persistent smashed furniture. |

These are all **nine** default nonbreakable registered environment identities.
The following helper-only paths also need explicit disposition:

| Helper / identity | Current role | Boundary to preserve |
| --- | --- | --- |
| `build_standing_torch` → `environment.standing_torch` | Same light/use owner as WallTorch, no default Health; installed static/lit art | Add authored Health/aftermath and missing broken art; retain extinguishing semantics. |
| `build_control_lever` → `environment.control_lever` | Linked door/light control, no default Health; installed use art | Preserve typed links and held-output ownership. Do not disable unrelated surviving providers when its body breaks. |
| `build_guardian_of_faith_object` → `environment.spell_object.guardian_of_faith` | Private helper creates BaseItem without Health and its WORLD_OBJECT-owned spell effect | Existing expiry/damage-budget retirement is disposal, not a physical wreck transition. |
| `ContinualFlameObject` | BaseBlock, not BaseItem; explicit flame position/light/spell lifetime | Not an attackable item simply because it has a destroy method. |
| Legacy `DoorObject` | Older/test use/blocker composition, no default Health; not a separate direct species | Preserve or migrate its actual call sites deliberately; do not count it as another authored door family. |
| Test-created breakable chest, shield or armor | Tests explicitly add Health and targetability to otherwise nonbreakable content | Keep their cleanup contract. These fixtures do not establish catalog-wide durability. |

The other **136 direct builders** are 5 ordinary gear + 1 field kit + 46 authored
weapons + 1 assassin dagger + 64 wearables + 9 consumables + 9 scroll/wand items
+ 1 portable torch. Consumable charge/stack exhaustion must still retire the
consumed item. Equipment destruction must still remove its contributions from
its owner. Portable torch cleanup must still extinguish its light. None requires
floor wreck art or automatic HP on all mundane equipment.

## 4. Animated ground mechanisms are not automatically physical breakables

| Existing native owner | Current coverage | Required distinction |
| --- | --- | --- |
| SpikeTrap and poisoned/sickening spike variants | Spatial condition, real payload/discovery/raised state and installed floor media | No separate default attackable hardware item or destroyed counterpart. Lowered/deactivated is not broken. |
| Dart launcher / standalone FiniteTrap | Spatial mechanism and projectile/payload; not necessarily an item | The 12 blade/crusher compositions are the currently supplied physical subset. Other selected damageable devices need an explicit body/anchor, then matching destruction media. |
| JawTrap | Spatial condition, capture/save/retreat rules and media | A jaw opening or releasing is not a broken jaw. |
| GasVent | Spatial mechanism/field delivery and media | Stopping an active field and breaking its physical emitter are separate facts. |
| PressurePlate / Tripwire | Spatial trigger with held/press behavior | No current ordinary Health owner. A broken trigger must stop its own contribution without fabricating another press/release behavior. |
| Portal and portal hatch | Spatial transport owner and animated entry/hatch | Closing/deactivation is not destruction. Physical hatch durability, if selected, needs an item counterpart; bare magical area lifetime remains separate. |
| Oil, fire, wet, ice, electrified water, steam, burning web and other area conditions | Native material/condition behavior | Do not add item HP to area conditions merely to cover missing fixture artwork. |

The physical spikes, dart emitter, jaw, vent, plate, tripwire and hatch are
required counterpart work under the parent plan, using ordinary items plus
their existing anchored owners. The native profiles must specify actual body
durability, physical aftermath and owned behavior cleanup. Bare portals and
independent area effects keep their own lifetimes; they do not gain item HP.
This is not a reason for one new trap class per spritesheet or a duplicate body
drawn over its existing mechanism art.

## 5. Every delivered interiors subject and counterpart

Source root:
`/home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/house-prefabs/`.
Use `INTERIORS-CONSOLIDATED-HANDOFF.md`,
`handoff-interiors-2026-09-21/item-matrix.json`,
`decor-study/reviewed-manifest.json` and
`decor-study/object-destruction-bindings.json` v3 together. Older aggregate counts
and unreviewed preview selections do not override these explicit selections.

The companion's **Every item-matrix row** table is the exhaustive exact-ID ledger;
its 160 rows are not duplicated here. The following partition assigns destruction
work to all of them:

| Partition of all 160 subjects | Count | Destruction disposition |
| --- | ---: | --- |
| Six `generated-indoor-door-*` subjects | 6 | Already represented by the six native indoor profiles and installed art. Migrate their lifecycle; do not re-import as new doors. |
| `chest-a1/a2`, `chest-a3/a4`, `chest-b1/b2` | 6 | Three styled containers, each with closed/open state. Both states have approved reconstructed intact/collapse/settled art. No smooth lid animation is supplied. |
| Other accepted exact families | 117 | Delivered intact/collapse/settled banks; exact native profiles/bindings not yet integrated. Shared passive item, mount, light, structural or dressing composition as assigned in the companion. Generic crate/barrel analogues do not establish exact per-family coverage. |
| Held `misc-b22`, `misc-b48`, `misc-b49`, `misc-b50` | 4 | Explicitly excluded; no approved collapse intake. B22/B48 have conflicting historical labels, so do not infer body/material from those labels. |
| Foliage: 7 ground cover, 6 bush, 14 wall-ivy families | 27 | Supplied static content only. No fracture **or thermal** art; `thermal_response_only` is not evidence of a delivered effect. |

Thus **129 accepted = 6 doors + 6 chest states + 117 other subjects**;
**160 = 129 + 4 held + 27 foliage**. The 135 banks are those 129 subjects plus one
extra alternative each for `misc-a2`, `misc-c5`, `misc-c6`, `misc-c7`, `misc-c10`
and `misc-c11`. Alternative impact banks do not create six new native items.

The 21 generated household sets are within the 117, not an additional batch:
plain dining table, bed, wardrobe, bookshelf, writing desk, preparation counter,
washstand, ingredient shelves, bedside stand, sack bundles, candlesticks,
tableware, papers and ink, work stool, storage shelving, wall shelves, hanging
utensils, tool rack, wall candle holder, wash basin and timber stair flight.
The 49 furniture selection choices and 73 families used by 3,171 house parts
are overlapping views of this broader library, not extra destructible species.

**Chest selection:** A1/A2, A3/A4 and B1/B2 must migrate as complete visual pairs.
Closed A1/A3/B1 select the reviewed v3-contact bank; open A2/A4 use v9-contact;
open B2 uses v12-contact. The reconstructed intact artwork differs from the
original static atlas; using the original intact frame then the new collapse
would visibly pop. This is a binding decision, not a reason to generate another
collapse. Preserve the exact per-bank registration and sampling metadata.

**Mounted/tabletop families:** all accepted source banks remain accounted for,
but floor-baked collapse/wreck pixels are not valid at arbitrary wall or table
height. Candlesticks/tableware/papers, wall shelves/utensils/tool rack/candle
holder and the 12 recovered sign/banner families need the native detach/drop
policy to select a valid floor aftermath. Do not claim an in-place wall fracture
just because the same asset has a ground collapse. Source labels that call a
tool rack or candlestick simply `floor` do not override its explicit placements.

### Architecture, dressing and terrain outside the 160-row count

The companion exhaustively lists all 87 Fantasy wall/frame configurations plus
17 Fantasy configurations excluded only from the older wall-only study. It
explicitly holds the 11 total palisade-family configurations; the other 93 are
reusable source geometry/appearance, **not 93 approved destruction banks**.
All Desert house configurations (138 in the old wall register, 62 outside that
register) remain outside interiors intake; already working Desert doors remain
inside destruction migration.

The 12 Fantasy roof variants, 3 selected ground families, stair/pillar/gable/post
profiles, fixed windows and room-shell geometry need their authored native
placement/support/channel contracts. No general wall, roof or floor destruction
atlas was established by the interiors manifest. Existing damaged wall/rubble
art is static source content, not a guaranteed matching aftermath for every
intact wall. Floor removal/support collapse is not silently introduced by this
destruction-content plan. The separately supplied timber-flight bank is already
counted among the 117; it does not define arbitrary structural collapse rules.

All 12 room decals are receiver-bound cosmetic content with no supplied
damage/thermal behavior. Spell scorch and blood overlays remain condition or
material presentation, not destroyed-state counterparts. Reusable static
foliage/dressing need not become Health-bearing just to enter a destruction list.
Overlapping-floor design is outside this plan.

## 6. Native mechanics and presentation gaps the asset count does not solve

1. **State versus removal.** Current `BaseItem.destroy` runs hooks, removes
   placement, creates a new remnant when configured, publishes destroyed
   location/replacement and unregisters the old item. Existing source profiles
   are reusable, but all relevant live, native-recorded and subjective after-state
   consumers need the new same-UUID contract. Saved old replacement histories
   must not be reinterpreted as evidence that a new event occurred.
2. **Actual methods.** Current public `AttackObject` is a melee-main weapon
   action, 5-foot reach and action cost 1, with an automatic hit and actual rolled
   damage. `BaseItem.receive_damage` handles phased TakeDamage interception,
   Health and destruction. This does **not** establish general ranged-weapon or
   spell item targeting: many normal spell/AoE recipients are explicitly entities.
   Preserve their rules; enumerate deliberately supported methods in tests.
3. **Material rules.** Default item Health supplies poison/psychic immunity.
   Door/profile material labels do not automatically supply wood ignition,
   stone fracture, thermal states or vulnerability. Oil-barrel spill/ignition is
   a real implemented coupling. Author other needed responses explicitly through
   existing damage/condition owners rather than infer them from pixels.
4. **Owned effects.** Destruction must stop light, maintained spells, controls
   and anchored mechanisms that need an intact body, while allowing newly created
   independent oil/debris aftermath to survive. Condition IDs and ownership stay
   causal; a global cleanup of every UUID reference would be wrong.
5. **Container contents and mounts.** Existing chest hook spills items; current
   tests establish their new placement, not the whole new causal/subjective
   contract. New parent/child scenery must release through the actual native
   relation. Do not clone contents or treat exposed tabletop objects as private
   inventory.
6. **Aftermath geometry.** No current per-decor debris footprint or difficult
   terrain is inferred by the art import. Authored intact/destroyed footprint,
   height and blocked channels must update the existing map owners coherently.
   One multi-cell item still has one Health/UUID and one break transition.
7. **Existing hit feedback.** Devices already consume the shared hit flash;
   ordinary props in `game/app.py` do not yet consume that sampled value despite
   generic ObjectDamageFact binding. Share the existing feedback contract; no
   new hit atlas is required. Current object-attack body recipe is Attack1 with
   a longsword presentation; do not claim weapon-specific object strikes are
   already authored.

## 7. Asset-request ledger — inspect/reuse before asking for production

These are proposed dispositions, **not requests already sent to an artist**.
Do not regenerate approved banks because their backend binding is incomplete.

| Family | Exact missing piece / decision | Next action |
| --- | --- | --- |
| 16 authored doors, 12 blade/crusher hardware, 2 device bodies | No missing baseline intact/break/wreck art | Preserve installed banks; migrate native state and replay selection. Intermediate-state fracture remains a disclosed limit, not a new blanket request. |
| Crate / oil barrel | Missing selected local bindings and native aftermath profile | Reuse reviewed `misc-b1` / `misc-a8` after exact identity/registration inspection. Do not request new crates/barrels. |
| Boulder / barricade | Exact matching intact source and fracture/wreck not identified | Search available supplied banks for the precise native appearance; if absent, request matching intact, finite break, stable wreck and camera registration. Do not borrow excluded palisades or arbitrary rubble. |
| Three styled chests | Native styled profiles/state binding missing; no smooth lid transition | Reuse all six reconstructed banks together. A smooth lid transition is a separate optional request, not missing destruction art. |
| 117 accepted decor families | Native profiles/bindings/placement policy absent, approved ground break artwork present | Integrate reviewed art; no repeat generation. Do not label all these assets missing because the renderer does not select them yet. |
| Mounted and tabletop subset | Matching elevated break/detach entry only where the approved ground bank cannot represent the selected native release | First settle physical release and inspect the exact bank. Request only missing mounted entry/detach or aligned aftermath; use supplied floor wreck where it fits the real landing. |
| Wall/standing torch, trap/control lever | No selected matching finite break and wreck for the existing intact bodies | Author required breakable profiles and request these exact counterparts. Existing use/lit/off art and shared hit flash are reusable. |
| Physical spikes, dart emitter, jaw, vent, plate, tripwire, hatch | No ordinary hardware-integrity/wreck binding currently demonstrated | Author each required physical native item/anchor and intact appearance; ask for matching break/settled state only where that delivered package lacks it. Do not ask for a broken abstract area condition. |
| Oil spill / burning surface | Native effects exist; no explicit current world spatial binding | Check retained effect media/registration first, then request missing floor effect only if necessary. Keep it independent of barrel collapse. |
| Walls/windows/roofs/stairs or other structural pieces selected as destructible | General matching fracture/aftermath is not established by this handoff | Author physical aftermath and exact selected subset first; request only uncovered counterpart banks. Do not silently claim whole-building collapse. |
| 27 foliage | No fracture or thermal art | Record explicit gap; static intake can proceed. Generate only when actual destructible/burning foliage behavior is selected. |
| 4 held subjects; decals; ordinary gear/potions; temporary spell objects | No accepted requirement for a persistent physical wreck | No automatic art request. Preserve hold, dressing, consumption and expiry contracts. |

## 8. Existing tests and the required coverage expansion

This study read test ownership; it did **not** rerun gameplay tests or claim new
implementation validation. The recovery plan's recent 48-test environment
baseline belongs to that earlier run.

| Current evidence | What it actually covers | Required change / extension |
| --- | --- | --- |
| `tests/engine/test_environment_destruction.py` all-profile construction test | All 16 door profiles, independent Health/material/channels/placement | Add actual nonlethal→lethal attacks and same-UUID aftermath for every profile; construction-only enumeration is not complete break coverage. |
| Same file's real door-attack matrix | `desert_c7` × open/closed × inward/outward × clear/jammed, including elevation | Preserve meaningful pose/outcome permutations; use all families with only their supported outcomes. Replace old “original removed/new wreck” assertions with native retained identity and explicit later removal. |
| Generic `DirectionalDoor` and legacy `DoorObject` call sites | Existing opening, occupied-door and use behavior; no default Health on either | Retain explicit nonbreakable admission tests, and test any deliberately composed breakable variant through the same lifecycle. If the legacy helper is retired, migrate its actual callers instead of pretending it is covered by the 16-profile loop. |
| Same file's hardware attack matrix | Stone/workshop blade and crusher, ready/activated, four directions | Add all 12 material/style profiles through the shared scenario; preserve selected state/direction cases and exact mechanism/peer ownership. |
| Same file's activation interception/discovery tests | Destruction during activation/save, no late payload/rearm; hidden discovery threshold | Prove these through destroyed-but-still-placed hardware, including observed wreck after mechanism retirement. |
| `tests/game/test_environment_presentation.py` | Explicit table coverage, real door/trap break sampling, late wreck initialization, saved replay, four-camera depth | Keep actual contact, entry pose and final pixels while changing identity ownership; initial destroyed state must not replay break. |
| `tests/game/test_device_destruction.py`, device replay/Web scenarios | Both bodies' banks, aim/pitch/cameras, real nonlethal/lethal attacks, hidden history, hit flash, effect cleanup | Retain both subjective views and actual maintained-slot ownership; remove dependence on new remnant UUID, not visibility assertions. |
| `test_action_discovery.py` object attack case | Real attack discovery/cost and a test crate's destruction | Preserve discovery/execution; destroyed item no longer offers intact actions. Explicit removal remains separate. |
| `test_items_inventory_equipment.py` | Manually breakable chest spill, equipped shield/armor cleanup, charges/stacks, torch behavior | Assert causal contents/state and distinguish physical persistent destruction from consumable/equipment retirement. |
| `test_direct_item_runtime.py`, `test_spatial_conditions.py` | Registry build behavior and actual oil-barrel physical/fire consequences | Preserve one spill and appropriate ignition under the real damage lineage, then replay the new retained barrel state. |
| `test_world_modification.py` | Unplacement without unregistering; moved/removed lights; causal world facts | Keep actual removal semantics, nonlethal state publication, independent light and spatial ownership. |

Helper-only standing torches/control levers and temporary spell objects require
the same explicit admission boundary in tests: adding Health in one scenario
must not silently change their default constructors, while terminal expiry of a
Guardian/Feast/flame must still clean up its existing registrations and effects.

New common acceptance should include a multi-cell furniture item hit from its
nonanchor end, a closed/open chest with spill, an extinguished broken fixture,
a held control with another surviving provider, and explicitly authored debris
terrain. Save the real native sequences once; replay both subjective perspectives
and four cameras using the existing clip extractor. Hidden destruction, later
discovery, repeat damage, and genuine final removal need native/replay assertions.

Use lean explicit data enumeration for all families and a bounded visual matrix
for distinct geometry/state/material cases. No 135-case handwritten mechanics,
new asset registry, checksum gate, or universal screenshot framework is needed.
No prospective regression should demand behavior absent from the authored
profile simply because a field could someday support it.

## Review and completion boundary

The parent lifecycle plan owns the cross-system migration and implementation
sequence. Independent **anti-slop** and **anti-OOP/ECS** reviewers assessed and
approved the amended plan with this ledger: one authoritative item lifecycle, complete real cleanup,
passive family data, honest attack-method support and no duplicated condition or
renderer ownership. The media reviewer independently confirmed the 30/34
installed coverage, 40/146 environment-art counts, chest pair hazards, mounted
bank limits and ordinary-prop hit-flash gap recorded here.

Both reviewers reaffirmed approval after the required adoption table made new
physical counterparts explicit. Findings and amendments are recorded in the
parent plan's section 12. This is design approval, not runtime validation or
approval of missing artwork.

This document completes the requested coverage study, not the implementation.
Production code, native content, assets and test assertions were not changed by
this unit. Outstanding artwork is explicitly separated from delivered artwork
awaiting integration, and unknown exact counterparts remain unknown rather than
being assigned invented names, HP or geometry.
