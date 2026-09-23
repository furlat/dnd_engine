# Destruction: persistent item state, existing content and complete asset coverage

Date: 2026-09-21. **Reviewed design; implementation authorized and in progress.**
Implementation evidence is recorded in [the result log](DESTRUCTION_IMPLEMENTATION_2026-09-21.md).
Subordinate to [RECOVERY_PLAN](../RECOVERY_PLAN.md). This is the destruction
subplan of the [interiors integration plan](INTERIORS_INTEGRATION_PLAN_2026-09-21.md).
It supersedes that plan's replacement-object recommendation. The user selected
one object becoming destroyed and requested coverage of both existing and new
items, required methods/tests, and actionable missing-art identification.

## 1. Required result

A persistent world item retains its UUID and content identity when broken.
Its native state becomes destroyed; its active behavior ends; its authored
physical aftermath remains in the world. Presentation plays the witnessed
transition and subsequently shows that same object's destroyed appearance.

This applies consistently to current destructible doors, trap hardware, devices
and props, and to the new delivered breakable content. It is not a special
furniture implementation alongside unchanged replacement-based doors.

Actual removal is a separate lifecycle operation. Consuming the last potion,
despawning a temporary spell object or disposing of failed construction must
still retire the object. They must not leave persistent debris merely because
their implementation currently calls destroy(). Ordinary pickup/unplacement
also remains distinct from permanent retirement.

The [destruction coverage and asset requests](DESTRUCTION_COVERAGE_2026-09-21.md)
are the detailed content ledger. Existing visuals that the user approved are
the visual baseline: changing identity/state ownership must preserve their
placement, contact timing, swing, mechanism pose and final appearance.

## 2. What already exists, and what changes

| Existing owner | Reuse | Necessary change |
| --- | --- | --- |
| AttackObject and item receive_damage | Actual attack cost/damage, TakeDamageEvent interception and Health resolution | Multi-cell manual reach; intact/destroyed eligibility at discovery and invocation |
| BaseItem.destroy and _on_destroy(parent_event) | Shared destruction entry and current item-specific effects | Separate physical destruction from terminal retirement; stop unregistering persistent scenery |
| Torch/chest/door/oil-barrel hooks | Extinguish, spill contents, clear pending close and spill oil | Retain exact causal parent, run once on the actual physical transition, not from passive replay |
| ItemDestructionRemnant / ItemRemnantState | Authored aftermath placement and the remembered open/swing/trap configuration | Move aftermath data onto the original item's destroyed-state profile; no new wreck UUID or gameplay item species |
| GridMap placement and spatial publication | One native authority for bands, boundaries, invalidation and committed facts | Replace effective physical properties/footprint coherently for the same UUID |
| Existing condition/light/concentration ownership | Real cleanup of the item's active effects | Cleanup can no longer depend on removing the physical object from the map |
| Existing spatial difficult-terrain owner | Owned walking-cost modifiers and their removal | Optional debris-area behavior driven by an authored destroyed profile |
| Native/public world facts and item state | Complete, passive received after-state | Preserve destroyed floor objects; distinguish state change from removal |
| ObjectDestroyedFact and finite world transitions | Witnessed contact and existing authored destruction sampling | Transition targets the same persistent UUID; record entry configuration and persistent aftermath |

There is no need for a damage system per material, a class per destroyed item,
an independent debris registry, or a new simulation clock. Existing methods are
implementation evidence, not an obligation to keep their current replacement
semantics.

## 3. Native data contract

Keep three independent facts:

1. **Integrity:** intact or destroyed. Partial damage remains in existing HP;
   no speculative damaged/repaired/burning lifecycle enum is added.
2. **Location:** placed, carried/equipped, unplaced or terminally retired under
   existing location ownership. Destroyed does not imply absent.
3. **Content behavior:** the authored physical/action properties of the current
   integrity state, plus current native conditions.

The proposed integrity field belongs on the shared item state and its retained
item snapshot. It is a small cold value, not a renderer flag. Do not maintain
parallel booleans for dead, broken, inactive and wreck. HP alone cannot describe
every non-damage removal or authored initially broken prop.

The concrete current coverage is **34 default health-bearing, targetable item
definitions: 16 doors, 12 blade/crusher hardware profiles, two device bodies,
three static blockers and one oil barrel**. Thirty have installed destruction
media. The registry has nine other environment definitions without default
damageability; helper-only and condition-only content is listed separately in
the coverage companion. Do not confuse a cannon body with every spell it can
be configured to cast.

A passive destruction profile on the original content definition supplies:

| Fact | Meaning |
| --- | --- |
| Destroyed description | Native text such as broken table, collapsed frame or jammed doorway |
| Physical aftermath | Existing placement kind, footprint/extent, center blocking channels or boundary contribution |
| Remaining capabilities | Which existing actions still make sense; normal use/fire/open/rearm ceases by default |
| Optional ground effect | Authored debris footprint using existing difficult-terrain ownership |
| Material and damage response | Existing physical material/durability configuration; explicit response data where the family needs it |
| Destruction outcome | Existing meaningful outcomes such as clear versus jammed; not an animation-bank ID |

Rendering separately maps (original item/visual identity, integrity, native
destruction context/outcome) to the accepted animation and stable final frame.
Existing .wreck art keys can remain resource aliases; they no longer require
new runtime entities or duplicated gameplay content definitions.

The entry configuration must remain available after the object breaks: a door's
open/closed state and swing, a trap's ready/activated state, and original facing
select different authored sequences. Reuse/generalize the existing cold
ItemRemnantState value for that physical context. Do not query a deactivated
mechanism later to reconstruct how it looked at impact.

State-dependent properties must have one shared resolution point. Systems ask
the normal item/placement capability for effective properties; they do not
scatter tests for destroyed item IDs throughout movement, actions and drawing.
Existing classes/composers may supply real capability hooks; new content families
should be passive definitions using them.

## 4. Lifecycle and hook semantics

Use the existing receive_damage/Health event path. Once accepted damage causes
the intact item to break, the shared destruction operation:

**User clarification during implementation:** physical destruction has its own
typed native ItemDestructionEvent. Its open effect owns the transition and
cascades the ordinary spatial change, mechanism shutdown, light/condition cleanup
and hook consequences as children. It completes with the resulting item state.
Do not infer destruction from an ordinary geometry update or reduce away this
causal owner. Prevention still belongs before the accepted damaging effect.

1. Captures actual pre-destruction configuration and current placement.
2. Commits integrity and the authored effective physical profile coherently for
   that UUID through the existing placement/index update owner. Before any
   resulting snapshot or sensory publication, integrity, effective channels,
   placement and covered-cell indices must agree. The committed transition
   prevents repeated hooks; a transient reentry guard is not public game state.
3. Runs the existing _on_destroy hook and retires the item's intact behavior
   through the relevant condition/light/control owners, under the real cause.
   These owners already publish child after-values, so they must never see
   new integrity paired with old physical indices. Captured pre-break context
   remains available to the hook and witnessed presentation.
4. Installs any authored destroyed-state terrain behavior after retiring intact
   behavior, without erasing independent consequences such as spilled oil.
5. Publishes the completed native state change, preserving the accepted damage
   lineage and all child consequences. The complete lineage remains the unit of
   reduction; rendering has its independent historical clock.

These are responsibilities of one transition, not five new event frameworks.
Keep existing interception phases before the damage effect. Do not invent a
late veto after damage has already applied, or a rollback system for presentation.
Hook ordering must preserve real source context: the chest still knows its
contents and position while spilling; the oil barrel still knows its damage
cause. Existing tests and focused new narratives establish those contracts.

The method boundary should distinguish physical break from permanent retirement.
Retain destroy() as the physical operation if that makes current damage call
sites clear, and introduce one shared explicit retirement operation for terminal
callers. Exact naming is ordinary implementation work; these semantics are not.
Do not use reflection or one method per item family to choose the path.

Audit every current destroy() caller:

- Damage resolution: physical destruction for every selected persistent item.
  Existing absence of destruction_remnant is not evidence for terminal
  removal: crate, boulder, barricade and oil barrel need explicit persistent
  aftermath profiles too.
- Consumable charge exhaustion: consume/retire after the final stack member;
  preserve inventory/equipment membership, charges and the existing actor facts.
- Temporary spell objects and expired summons represented as items: retire on
  their existing expiry/dismissal path; an effect expiring is not a smashed prop.
- Failed scenario grant or trap-hardware setup: dispose construction state;
  do not spill gameplay loot, create rubble or run an attack animation.
- Explicit removal/pickup: retain existing placement/container transition
  semantics; ordinary map unplacement is not permanent registry deletion.

Do not globally turn all items into persistent breakables. Health/targetability
and an authored destruction capability remain the admission criteria. Existing
mundane equipment and consumables are not given durability as a side effect.

Resolve owned items explicitly rather than leaving retained objects with no
location:

| Content/location | Physical breakage outcome in this plan |
| --- | --- |
| Selected persistent scenery on the map | Same UUID and content identity; authored destroyed placement, including mounted/support aftermath when that later unit is implemented |
| Selected persistent pickable prop inside an inventory/container | Same UUID in the same container with destroyed state; no fabricated floor placement or disclosure of private contents |
| Existing equipment/consumable content with no authored persistent broken form | Preserve current terminal physical-breakage behavior, including equipped slot/modifier cleanup; no new equipment durability or broken-gear content is introduced |
| Explicit consumption, expiry or failed setup | Terminal retirement independent of physical-breakage policy |

The existing equipped shield/armor damage test is a required regression for
the third row. Newly selected scenery cannot silently use that legacy terminal
policy because its profile was forgotten: catalog coverage must require its
persistent profile. No selected new persistent prop is equippable; author a
concrete broken-gear location policy before expanding into that separate content.
Direct destruction and lethal damage use the same authored physical policy.

## 5. Stop active behavior without deleting the body

This is essential for the same-identity model. Today several behaviors end as
a consequence of SPATIAL_OBJECT_REMOVED. That event will no longer occur when
a wreck stays placed. The owning capability must react to physical destruction,
while actual removal retains its existing cleanup semantics.

| Family | Required native consequence and regression |
| --- | --- |
| Every door profile and generic door | Disable normal Open/Close/Use on destroyed state; clear pending close requests; preserve boundary placement, clear/jammed outcome and authored swing context |
| Linked/held doors and controls | Destroying a provider ends only its own active contribution; preserve the existing occupied-door and surviving controller rules |
| Blade/crusher physical trap hardware | Deactivate its exact anchored mechanism, including in-progress activation; linked pressure plate and other outputs survive |
| Other physically represented traps/triggers | Compose an actual damageable hardware item where selected; anchor existing trap behavior to it; destruction disables that behavior, not unrelated map hazards |
| All current cannon/device identities | Stop firing/use, release all owned concentration slots and their linked effects; body remains destroyed; the operator's independent effects survive |
| Chest | Spill the selected contents causally, then end lid/normal container-use behavior; observe spilled contents through existing rules |
| Torch/new lit fixture | Extinguish/remove its light source through current ownership; keep observable destroyed physical state |
| Oil barrel | Its authored spill/ignition remains a consequence of destruction; the resulting independent oil area must not vanish merely because intact barrel behavior ends |
| Simple blockers/furniture | Resolve destroyed placement, blocking and optional terrain; no machinery-specific hook needed |

Distinguish effects that require an intact object (trap mechanism, device
concentration, lamp light) from effects created by breaking it (oil spill,
debris). Do not deactivate every effect referencing the UUID after creating its
aftermath. Reuse explicit condition ownership/links; add only the lifecycle fact
required at the existing anchor handler, not a universal dependency graph.

The current hidden-trap body delegates observation to its mechanism. Retaining
the body after deactivating that mechanism must not make a witnessed wreck
disappear. Preserve existing discovery rules and record the correctly observed
destroyed state; do not globally reveal hidden traps on an unseen destruction.

Discovery and direct execution both honor integrity. A saved stale Open Door,
Fire Cannon or trigger request cannot reactivate destroyed hardware. Keep
intentional remote lever invocation valid for intact targets; manual proximity
checks must not prohibit that existing behavior.

Check intactness at action admission and at the actual relevant mutation owner.
Do not add a blanket source-exists check to every later action phase: a valid
potion or scroll can consume its final charge and retire its source before the
accepted spell effect finishes. Preserve that accepted cast from its committed
source context while rejecting later requests, including unlimited-charge
cannon actions captured before the cannon broke.

## 6. Physical aftermath, multi-cell objects and difficult terrain

The same object may retain, shrink or clear its blocking footprint. Its anchor,
orientation and stable identity stay explicit. Its drawn debris is not a new
source of geometry. Update existing placement/band indices and all affected
movement/optical/propagation/light/sensory consumers over old and new footprints.
No fake remove/reinsert sequence solely to force existing destruction observers
to react. Floors and their existing conditions remain the same Tiles.

Reuse the interiors core's finite footprint extension. One multi-cell object
has one HP owner, one destruction transition and one observed identity. Query
results deduplicate UUIDs without making creature-only spells affect items.
Rotations, far-end interaction and partial visibility stay in the existing
core acceptance; destruction must work from an observer who sees only the
nonanchor end. Observation contact does not become the renderer's new anchor.

Author representative aftermath outcomes:

- Small rubble: visible, passable and non-occluding.
- Large furniture debris: passable, usually non-occluding, with an explicitly
  authored difficult-terrain footprint.
- Existing jammed doorway: movement-blocking native boundary result retained.

Do not infer these from object size, pixel padding or a name. A large object
may collapse neatly; a small sharp hazard is a different authored behavior.
Use existing terrain-cost modifiers. Clearing/removing the debris removes only
its own modifier. Preserve other terrain effects and the existing overlap rules;
do not reset the Tile's walking cost to one. State this behavior in native text.

Salvage, repair and a new player debris-clearing action are not required now.
The lifecycle must support real native removal for tests and future content.
Chest contents are actual items; a destroyed object does not automatically
become a new loot container or generate one item per animated fragment.

## 7. Conditions and physical materials

Keep three authoring concerns separate:

1. Material/durability affects native damage response where current rules use it.
2. Conditions such as ash, blood and burning describe actual persistent facts.
3. Fracture fragments, hit flashes and sparks are authored presentation.

Existing Material values and item Health response profiles are reused. Source
labels mixed, gold trim or plaster appearance are not valid rules merely because
they appear in a manifest. Do not infer resistances from a sprite or silently
change every spell's object eligibility.

For each family the coverage ledger records whether physical material/response,
object-condition handling, hit feedback, destruction sequence and final state
exist. Unknown is explicit; it is not filled by universal wood/blood fallback.
The user asked for these gaps to be visible, not for a speculative complete
combustion/chemistry simulation.

The same-UUID transition should retain compatible surface conditions on the
remaining body, or resolve them through an explicitly authored removal policy.
Inspect current object blood/ash handlers: deleting all conditions indiscriminately
would erase the new state's surface history as well as its intact behavior.
Save before/after conditions and prove any selected visual overlay from those
facts. A new debris effect starts after intact-effect cleanup, under the same
causal lineage. No duplicate body-release or terrain-residue system is added.

## 8. Events, subjective state and saved replay

Integrity and location must be separately represented in retained item state.
A floor object becoming destroyed remains in world.objects with the same UUID.
ItemDestructionEvent carries the actual transition entry and completion.
Existing ItemLocationStateEvent can publish a FLOOR after-value containing its
destroyed integrity and physical state, and spatial children retain their
ordinary geometry/sensory meaning.
Do not encode physical destruction as inventory movement or depend on live
objects while decoding.

The existing terminal ItemLocation.DESTROYED value continues to mean
removed/unregistered for consumption, expiry and deliberately terminal breakage.
Document that legacy name; do not rename the whole location protocol just for
this feature, or reinterpret old packets as persistent wrecks. New persistent
destruction uses integrity plus its actual location. ItemChargeConsumptionEvent's
item_destroyed flag likewise continues to mean terminal source retirement.

Existing native WorldFacts, actor inventory projection, player projection,
PlayerObject state and destruction facts all need coordinated updates:

- Native snapshots and world mutations retain the same item, effective geometry,
  state, context/outcome and relevant conditions.
- Subjective projection grants only facts the existing observer rules disclose.
  An unseen break must not update the player's remembered room from hidden
  objective data. A late observer receives destroyed state without a past hit.
- Capture witnessed prior contact at the actual integrity transition's entry.
  The current OBJECT_REMOVED-entry capture cannot be reused unchanged: physical
  breakage no longer removes the body. Final visibility alone also cannot
  establish whether an observer saw the transition. Keep the existing
  subjectivity rules and attach this evidence at the existing projection seam.
- ObjectDestroyedFact describes an actual witnessed integrity transition on
  one object. It no longer requires a replacement_uuid for newly recorded data.
- DestructionContact, choreography, playback facing and app drawing use that
  same UUID for transition and settled body. Draw exactly one body at a time.
- Damage feedback still belongs at contact; finite collapse continues on the
  independent historical clock. Backend progress does not wait for the clip.

Preserve saved approved sequences. Old records with original/replacement UUIDs
keep their recorded identities and terminal semantics through the existing
passive compatibility boundary; do not re-execute the engine, regenerate inputs
or invent an unseen replacement. Normalize the presentation reference to the
actual recorded surviving body once. Keep compatibility out of gameplay code
and avoid permanent per-spell/per-door branches in the renderer.

Initially destroyed content is also valid: initialization carries the destroyed
state and final appearance, with no destruction animation and no intact behavior
being installed then immediately removed. This is useful for native rubble/ruin
scenes and exercises the same contract as a late observer.

## 9. Adoption and asset-gap policy

The required adoption set is concrete. References below to selected content
mean this set, not permission to finish after demonstrating a single item:

| Adoption unit | Required content and completion |
| --- | --- |
| Current breakables | All 34 default definitions, with every authored door, trap hardware and device profile using the same lifecycle |
| Other ordinary door paths | Give the generic directional door an explicit breakable profile consistent with its existing art alias; migrate actual legacy DoorObject callers through the shared owner, without creating another door system |
| Containers, lights and controls | Three styled chest pairs; wall/standing fixtures and trap/control levers with authored durability and same-item aftermath. Generic helpers may still construct deliberately nonbreakable fixtures when explicitly authored; ordinary production counterparts must be covered |
| Existing physical ground mechanisms | Add ordinary hardware counterparts for spikes, dart emitter, jaw, gas vent, pressure plate, tripwire and portal hatch; attach current mechanism/trigger owners, preserving hidden/discovery and lifetime rules. A bare portal or a gas/fire field is not hardware |
| Accepted ordinary interiors props | Account for all 117 remaining accepted source subjects through the existing exact ledger; author breakable item counterparts for actual props and fixtures. Structural/support subjects follow their explicit support restrictions, rather than enabling whole-building collapse |

The separate generic arcane healing device needs its own profile and appearance
disposition in the ledger; it cannot borrow cannon durability or art by name.
Terrain cliffs, cosmetic decals, abstract areas, temporary spell objects, held
source subjects and general roof/floor/wall collapse are outside this adoption
set. Foliage remains static content pending its separately selected behavior.
The fixed-window proof stays intact as already planned. These exclusions do not
exclude current Desert doors or any of the 34 existing breakable definitions.

The coverage companion must account for these overlapping sets:

- Every currently damageable native item, including helper-only builders and
  native fixtures outside the direct registry.
- Every installed destruction media family: all 16 authored door profiles,
  generic door behavior, all 12 blade/crusher variants, and device identities.
- All delivered interiors subjects: 129 accepted subjects/135 banks within the
  160-row source matrix; chest pairs are states, not six separate mechanics.
- Delivered physical trap/control/fixture art that currently exists only as a
  spatial condition or nondamageable object.
- Existing items with missing destruction animation, intact/wreck registration,
  damage feedback, material/condition rules or tests.

Do not declare a source asset native merely because a similar generic item
exists. Conversely, do not commission a new render because the delivered bank
has not been bound yet. The ledger distinguishes:

| Status | Next action |
| --- | --- |
| Native behavior and accepted media already present | Migrate same-identity lifecycle; preserve visual result and run family tests |
| Approved media present, native capability absent | Author native counterpart/profile and binding through the shared lifecycle |
| Native destructible, media absent | Keep mechanics explicit; prepare the exact art brief and report the visible gap |
| Intact physical asset only | Decide physical capability from intended item role; add selected breakability and request required aftermath art |
| Delivered bank incompatible with actual mount | Request correct mounted entry/grounded aftermath; do not raise floor debris into the air |
| Intentionally held or nonphysical effect | Preserve that disposition; no automatic destructibility or art request |

Every art-request row names the exact affected item/source family, required
states and poses, mounted/floor/boundary registration, material/outcome, reusable
existing source and missing deliverable. Requests distinguish contact hit media,
finite destruction, final state, masks and condition variants. Do not request
every material × damage-type combination by default; ask for what the selected
native behavior needs. No artwork is generated or dispatched in this plan turn.

## 10. Tests and review clips

Follow [HOW_TO_TEST](../HOW_TO_TEST.md). Parameterize actual content definitions
and public native actions; do not test a guessed private call sequence. The
shared method implementation serves every family; tests prove the family-specific
outcomes and that all applicable registered profiles adopt it.

| Test group | Required observable contract |
| --- | --- |
| Shared damage transition | Nonlethal hit preserves identity/placement; lethal hit leaves same UUID destroyed with exact after-properties; later hit/use cannot rerun destruction effects |
| Every door profile | Both sides and legal open/closed/swing states; supported clear/jammed outcomes; same identity after damage; no normal use/pending close/reactivation; correct geometry and late state |
| Every hardware profile | Ready and activated destruction, direction, mechanism cleanup, hidden/witnessed discovery, surviving linked plate and peer outputs; destruction during real activation/interception preserves existing phase semantics |
| Every current device identity | Nonlethal hit feedback, lethal body state, no further shots; all device-owned concentration slots retire with linked fields/conditions, unrelated operator effects remain |
| Simple blockers and new furniture | Different material/footprint profiles, reachable far end, old/new occupancy and observer/light changes; passable and difficult-terrain aftermath |
| Chest styles | Open/closed destruction, same body identity, real contents released once with causal parent; no hidden inventory disclosure and no duplicate loot |
| Light/fire/oil fixture | Lit and unlit destruction, source cleanup, intended oil spill/ignition remains independent; no ghost light or repeated spill |
| Physical controls and newly attached hardware | Destroy controller/hardware under actual active linkage; only owned behavior ends; no retained handler silently fires from a destroyed object |
| Ground-mechanism cleanup | Broken jaw releases its captured source-owned restraint; broken held plate withdraws only its output; dart/spike/vent/tripwire cannot retrigger; hatch destruction retires its owned transport while unrelated portals/areas survive |
| Removal/consumption and owned items | Last charge/stack member retires its source but completes the accepted effect; existing equipped-item terminal breakage clears slot/modifiers; new persistent carried props retain valid container membership; temporary expiry/setup disposal leaves no debris |
| Coherent publication and stale actions | Every published item after-value agrees with committed placement/indexes during condition/concentration cleanup; stale direct/remote/retained actions cannot revive destroyed hardware, including unlimited devices |
| Terrain/conditions | Selected debris applies current owned cost behavior; removal cleans only that contribution; selected compatible surface state retained |
| Serialization/subjectivity | Record once; same-ID destroyed state, hidden destruction, late discovery and initial wreck replay without live registries; two observers remain independent |
| Legacy playback | Existing approved replacement-based inputs retain their recorded visible behavior; no forced rerecording |
| Content/media coverage | Explicit applicable native IDs and accepted data maps have lifecycle profiles and correct state bindings; missing art reported separately from absent mechanics |

Test the required public behavior for every applicable native profile; reuse a
small common scenario helper, with extra narrative cases only for distinct
capabilities. A data coverage check does not replace gameplay tests, and passing
one door does not establish all door mechanism/swing/outcome combinations.

Use the existing clip extractor for representative combinations and the current
four-camera/two-subjective-perspective approach. Include destruction near a
door/wall, nonanchor-end visibility, a destroyed device with its effect ending,
a chest spilling contents, difficult-terrain movement and late wreck discovery.
The finite animation should land on exactly the native aftermath. Static
variant review can cover art-only differences without rendering the entire
catalog after each edit. No new pixel-test framework or runtime media audit.

Preserve actual visual assertions while migrating identity assertions: one body
at contact, lethal flash on that body, unchanged pivots/facing/depth and finite
timing, matching reconstructed intact/collapse/final art for props and chests,
identical settled appearance on cold initialization, and correct backward seek.
Reuse tests/game/test_environment_presentation.py's door-pose, destruction,
seek and cold-wreck cases rather than replacing them with UUID-only checks.

Existing door/trap banks cover settled closed/open and legal swing poses, or
ready/deployed mechanisms. They do not cover arbitrary mid-opening/mid-sweep
entry poses. Preserve and document that media limit; request precise additional
exports only for selected missing transitions. Native destruction and cleanup
never wait for art or an animation to finish.

Existing baseline: tests/engine/test_environment_destruction.py passed 48 tests
in 4.76 seconds during the preceding core study. That validates the old current
behavior, not this same-identity design. New assertions legitimately replace
old replacement-UUID expectations while retaining all gameplay/visual outcomes.
No new implementation tests have run for this plan.

## 11. Implementation order and definition of done

1. Complete the native/media counterpart ledger and capture current approved
   behavior from saved histories. Decide explicit physical/terminal call sites.
2. Implement shared integrity plus physical/terminal lifecycle semantics and
   retained facts. Prove one ordinary item, consumption and passive replay;
   no content expansion yet.
3. Migrate existing doors, all trap hardware and all device profiles in the same
   coherent change, including active-effect cleanup and old-history decoding.
   Do not call the feature complete with existing content on the old path.
4. Migrate existing blockers, oil/container/light/control capabilities and add
   the selected missing physical counterparts. Connect generic prop media to
   the same authored state route; reuse supplied destruction banks.
5. Complete the multi-cell destruction and owned difficult-terrain proof in the
   interiors core. Native footprint state, observation and replay agree.
6. Expand approved new assets through data with the same methods/tests. Resolve
   the media gaps from the ledger with exact handoffs; keep missing artwork
   explicitly unreviewed rather than a generic visual fallback.
7. Run affected native, replay/presentation, architecture and typing checks;
   then appropriate broader suites and representative saved-input galleries.
   Record actual results and remaining per-content art gaps.

Backend completion means every selected native destructible uses the shared
state lifecycle, full cleanup/public facts work, terminal removal remains correct,
and its behavioral tests pass. Visual completion additionally needs the mapped
accepted state/transition art and review. Outstanding art does not excuse a
missing native test, and implemented mechanics do not imply approved visuals.

Performance: no hashing, source scans, recursive validation, per-frame content
rebuild or whole-world serialization. Load authored profiles once; update the
changed item/footprint through existing deltas. Keep engine timings separate
from rendering/encoding. No multi-Z, repair/salvage economy, general physics,
new spell-recipient rules or unrelated window-query implementation here.

## 12. Independent review record

Reviewed on 2026-09-21 against this written plan and its coverage companion,
separately from the earlier interiors review:

| Reviewer / finding | Amendment or result |
| --- | --- |
| backend_ecs_review — anti-OOP/ECS, P1: broken owned items lacked a valid location policy | Section 4 now distinguishes persistent placed/carried props, deliberately terminal existing gear breakage, and consumption/expiry; the equipped-item regression stays required |
| backend_ecs_review — P1: cleanup can publish new integrity with old placement/index state | Section 4 requires a coherent native physical commit before those child after-values; captured entry context remains separate |
| backend_ecs_review — P2: broad stale-source checks can cancel a valid last-charge potion/scroll | Sections 5/10 explicitly preserve the accepted consumed-source effect while rejecting future/stale requests, including unlimited devices |
| presentation_antislop_review — absent remnant profile must not imply terminal scenery | Crate/boulder/barricade/oil barrel explicitly require persistent authored aftermath |
| presentation_antislop_review — witnessed transition previously relied on removal entry | Capture actual integrity-transition entry observation; preserve hidden/late-observer behavior and old recorded identities |
| presentation_antislop_review — exact visual preservation and honest entry-pose limits | Preserve actual contact, lethal flash, pivots/depth, matching reconstructed banks, settled/cold appearance and seek assertions; no claim of arbitrary interruption banks |
| spell_orientation_antislop — content inventory study | Reconciled all 34 current breakables, helpers/nonbreakables, 160 source rows and 129/135 accepted subjects/banks; distinguished native, binding, art, material/condition and test gaps |

Both independent reviewers **approved the amended plan and coverage** and
reaffirmed approval after section 9 made adoption of current and new physical
counterparts mandatory. No remaining architectural/presentation design blocker
was reported. Physical ground mechanisms reuse their existing WORLD_OBJECT
anchor and cleanup owners; they do not gain separate per-sprite systems.

Approval covers design only. No production behavior, new art, or implementation
test result is claimed by this document. The 48-test baseline above predates
this plan and still exercises the existing replacement-based implementation.
