# Complete feature change trace — spell backlog, 4 October 2026

This is the human-facing inventory of the work since committed baseline
`95a47cd5ca508838bce8a2e67d6fe1fc591ce4e6`. The authority is the approved
[eight-packet implementation plan](../SPELL_VFX_IMPLEMENTATION_PLAN_2026-10-04.md),
plus the human's final Telekinesis damage choice. The scope comprises 34 named
spell entries, the available Thorns/Wind and surface deliveries, and 21 class
presentation sets. Most spells already existed: the work connects accepted art
and closes the specific rules, ownership, targeting and replay gaps in that plan.

**Final validation:** 3,009 native and 120 architecture cases passed; all 3,522
client cases accounted for by the full run and passing complete affected-file
reruns of its five failures. Active typing is clean. The [final report](SPELL_VFX_FINAL_ACCEPTANCE_2026-10-04.md)
gives exact receipts and corrections. Source descriptions below are an audit
inventory, not a blanket assertion that every line is elegant.

## How to inspect the changes

- [Native feature trace](SPELL_NATIVE_FEATURE_TRACE_2026-10-04.md): all 59 changed
  backend/AI files across 50 trace entries, including 14 explicit core changes,
  before/after rules, fields, evidence and choices. The linked JSON pins both revisions.
- [Presentation and class trace](SPELL_PRESENTATION_FEATURE_TRACE_2026-10-04.md):
  all 21 class sets, source measurements, item attachments, holy/Finger integration,
  class provenance and the precise limits of those consumers.
- [New rendering modules](SPELL_NEW_GAME_MODULE_TRACE_2026-10-04.md): purpose,
  concrete consumers and ownership boundary for every newly introduced module.
- [Complete client/tool file inventory](SPELL_CLIENT_FILE_INVENTORY_2026-10-04.json):
  all 209 changed files, including 74 client Python modules and 42 authoring/review
  tools, mapped to their responsibility and pinned by hash. Data entries are
  listed too; a large registration manifest is not hidden behind the Python count.
- [Spell coverage matrix](SPELL_VFX_VISUAL_COVERAGE_2026-10-04.md): all 34 named
  entries mapped to native tests and selected engine recordings.
- [Implementation ledger](../SPELL_VFX_IMPLEMENTATION_2026-10-04.md): chronology
  and retained failed attempts. Its older checkpoints are historical.
- [ECS/event review](SPELL_FINAL_ECS_EVENT_REVIEW_2026-10-04.md) and
  [anti-slop review](SPELL_FINAL_ANTISLOP_REVIEW_2026-10-04.md): independent findings,
  exact reviewed source boundaries and corrections.

## Feature inventory

| Plan packet | Named entries | Observable delivery/change |
| --- | --- | --- |
|1: senses/control | Darkvision, See Invisibility, True Seeing, Longstrider, Hold Monster, Power Word Stun, Power Word Kill | Correct source-owned duration/target admission and committed outcome cues; independent Hold recipients and saved/HP-threshold outcomes. Shared Restrained, Petrified, Stunned, Sickened and Incapacitated media use existing condition ownership. |
|2: item/body effects | Shillelagh, Barkskin, Produce Flame, Fire Shield, Continual Flame | Exact affected-item material; source body treatment; held flame consumed on release with its granted hurl; warm/chill actual retaliation; real item-owned persistent flame through drop/equip/loot/cover/suppression/destruction. |
|3: directed/necrotic | Lightning Bolt, Chain Lightning, Blight, Circle of Death, Harm, Eyebite, Finger of Death, Disintegrate | Native line and primary-to-secondary lightning branches; saved/failed and actual recipient outcomes; all three Eyebite modes/repeats; original directed source art; current-pose terminal effects; actual Disintegrate remains/gear and object-section consequences. |
|4: weather/solar | Ice Storm, Sleet Storm, Sunbeam, Sunburst | Original weather/solar materials follow actual area and recipients; native terrain/lifetime/concentration interactions; Sunbeam repeat and recorded blindness timing. |
|5: holy | Spirit Guardians, Guardian of Faith, Heroes' Feast | Following radiant/necrotic field; admitted Guardian strike/retirement; actual Feast Eat interaction and its complete benefits for the chosen ten turns. |
|6: transport/suppression | Banishment, Dimension Door, Telekinesis, Antimagic Field | Real absence and lawful return; linked companion selection/mishap; entity-plus-destination finite movement/landing; suppression/restoration preserving real owners instead of deleting/re-creating them. |
|7: constructions | Wall of Force, Wall of Ice, Wall of Stone | Actual panel/dome forms and owners; distinct intact retirement/destruction; Force contact/collapse; Ice shared-dome destruction and native frigid air; partial Stone cut retained through subsequent fracture. |
|7: available extra media | Wind Wall, Wall of Thorns; existing ignition/dousing | Joined current paths, original source components and admitted contacts; Oil/Fire and Web/Burning Web transition art follows existing native operations. |
|8: existing class actions |21 sets, enumerated in the presentation trace | Actual action/handler/condition outcomes receive accepted art. Source facts are added where existing results lacked enough provenance. Existing attack/resource rules remain authoritative. |

Longstrider is one entry despite appearing in both sense/support and nature
verification. Shared surface/condition/class rows are additional capabilities,
not extra spells silently added to the34-entry count.

## Core changes that deserve explicit scrutiny

| Change | Why this scope needed it | Boundary and design cost |
| --- | --- | --- |
| Dependent target choices | Chain Lightning secondary choices depend on its primary; Dimension Door companion and Telekinesis destination depend on the first selection. | Existing action discovery, public selection, AI intent and UI consume typed secondary targets. This is a real API expansion, covered by selection/revalidation tests. |
| Actual ground-to-ground forced movement and landing | Telekinesis and the approved ledge-fall addition must retain the movement before damage. | Existing movement/grid/support owners decide legal landing. Recorded trajectory/elevation/drop fields let presentation animate it. It adds falling consequences, not continuous physics or hovering. |
| Retained Antimagic suppression | Existing deletion/re-application lost ownership and source state; native and rendered restoration must agree. | Condition/item/construction contributions retain provider identities. Shared lookup and state publication changed. This is broader than an art binding and is listed file-by-file in the native trace. |
| Disintegrate remains and partial objects | Dead body dust, preserved magical possessions and a cut piece of wall cannot be inferred reliably from HP or sprite alpha. | Existing native death/destruction events carry explicit remains/volume/placement results. The renderer cannot destroy an object or choose loot. |
| Real item-owned Continual Flame | Dropping, covering or transferring an item must move/suppress its light and effect without creating a fake world object. | Existing item-effect owner and snapshot; client retains its source clock and binds actual item pixels. |
| Weather expiry and sunlight | Solar spells need actual sunlight semantics and source-owned temporary effects must expire after source removal. | Existing sunlight query/sensitivity consumers are connected; RoundEnd receives its proper declaration/execution/effect/completion phases and existing durations gain a round-boundary fallback when their source is absent. These are native lifecycle changes, detailed in the native trace. |
| Direct class results | Indomitable, Relentless Rage and Font lacked sufficient retained outcome/resource data for correct visuals. | Passive closed values on existing events; effective-handler provenance and ordinary progression remain authoritative. Owner-only resource numbers stay private. |
| Shared condition/material consumers | The accepted art includes current-body materials, damage responses and frozen poses. | Existing condition recipes/lifetimes gain closed data fields; no condition per spell or parallel rules executor. |
| Shared source rendering operators | Accepted effects include procedural meshes, source textures and particles, not only pre-rendered sheets. | New small material/sampling modules feed existing DrawCommands, world clipping and choreography. This is substantial renderer code; the module trace names every added file and actual consumer. |
| Projection timing/privacy | Self-blinding, transport, item teardown and invisible constructions exposed missing/mis-timed retained facts. | Existing subjective projection/reduction changes. Witnessed physical footprint is distinct from hidden outcome/recipient knowledge; hidden return/reacquisition cannot fabricate an animation. |

## Explicit game choices

- **Telekinesis:** finite creature movement; hostile landing adds 4d8 force and 2d6
  bludgeoning. An actual lower support adds ordinary falling damage. Safe ally
  placement has no impact/fall damage. It does not hold an enemy hovering/stunned.
- **Ordinary ledge falls:** 1d6 bludgeoning per complete 10 feet, capped at 20d6,
  with existing landing/Prone rules. Normal safe flight arrival stays safe.
- **Heroes' Feast:** existing quick Eat interaction; completed benefits last 10
  turns, as selected by the human, rather than tabletop meal pacing.
- **Finger of Death:** no zombie creation, as explicitly requested.
- **Ice dome:** existing accepted 120 HP shared owner; the whole dome breaks.
  Transparent ice and quiet residual air remain the accepted optical policies.
- Existing game limitations such as supported terrain/grounded endpoints and
  prior Frightened behavior remain. Eyebite's Panicked child expressly permits
  retreat through the existing movement rules; its distinction is documented.

## Rendering and event changes in plain terms

The renderer now has data for an actual linked lightning branch, actual item
effect, native forced landing, remembered absence, disintegrated remains,
partial object cut, witnessed construction removal, surface dousing and class
intervention result. These travel through existing retained events/player facts.
The native and presentation traces list exact fields and publication points.

The existing client loader admits the new authored variants. Existing
choreography chooses contact/response dates and extends the same presentation
head through finite tails. Body, item, condition, spatial and construction
consumers draw only their admitted source data. New source-specific math is kept
in explicitly named material modules; JSON selects a closed material rather than
importing callbacks or executing gameplay. A TypeScript port would need to port
these operators and schemas; merely copying the art would not be enough.

Fixed-sheet creatures retain their existing rigs. Some exact hand/face/weapon
attachments are unavailable without measured sockets or separable equipment.
Those omissions are explicit rather than replaced with guessed body offsets.

## Corrections discovered during implementation

These are included so the trace does not hide regression work behind feature
names:

- Shared touch validation briefly rejected a SELF item-granted Longstrider;
  validation now resolves SELF to the actual caster first.
- A generic class-handler consumer duplicated Shield's existing gesture; only
  the four intended class handlers now opt in through default-false authored data.
- Hypnotic's existing transform did not create a generic Incapacitated child;
  its original persistent cue is retained, with the existing exclusivity group.
  Web's specific wraps likewise take priority over the generic Restrained mark.
- Banishment return could animate on later reacquisition; it now needs the
  witnessed, committed entry edge.
- Item teardown observations could restore stale pre-death state; reduction
  retains the already received committed life/damage facts.
- Partial wall cut coordinates incorrectly depended on camera zoom; the sampler
  now receives the actual zoom. Separately, retained material-rest coordinates
  keep an old cut out of moving fracture fragments without corrupting world depth.
- Native Force cells could miss the continuous drawn dome surface; the final
  geometric registration handles that disclosed approximation without changing
  native targeting or damage.
- Mindless cleanse used a terminal child as event parent; it now uses the live
  action. Retaliation's normal Attack now carries its canonical binding and
  existing handler-emitted lineage. Neither creates a second attack budget.
- Decorative Grease splashes briefly joined blocking effect duration and paused
  walking. They retain their own clocks without extending the movement join;
  damage, quench and summon lifecycle tails keep their intended joins.
- Dependent-target picking briefly bypassed a disallowed window's solid mask.
  Existing object-action mask admission is restored alongside dependent options.

Fixture updates and invalid first-run validation are separately accounted for
in the acceptance report. Expected output was not changed to conceal a changed
game rule: the reviewed fixture corrections name the approved new contract or neutral
schema default; their individual receipts identify the independent checks.

## Limits and excluded work

The delivered source is preserved, but a CPU/Pygame port does not promise
byte-identical whole-scene Godot lighting/transparency. Quantizing individual
world-depth primitives can differ from isolated Godot postprocessing. Ordinary
Force weapon contacts use admitted actor-to-band geometry; exact weapon XYZ was
not supplied. The rounded-shell fallback is explicitly a visual registration
approximation. Source timing/constants and measured/null sockets are documented.

The previously agreed later-art list remains: general-heading Cone of Cold,
Call LightningV5, isolated Wind interception gust, and correctly dimensioned
20-foot Thorns ring. Ogre's unimported rig remains character-port work. No
additional monster roster, ammunition system, grappling system, new cloud rules,
continuous flight physics, new UI project or server restart was authorized here.
No external chat was read or contacted, and no commit is made by this task.
