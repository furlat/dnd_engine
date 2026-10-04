# Summoning and first creature roster — unified implementation plan

Date: 2026-10-03. Status: implementation authorized by the human after the
[plan review](audits/SUMMONING_PLAN_REVIEW_RECEIPT_2026-10-03.md). The accepted
pre-implementation SHA256 was `d2c83849488ebe40a2fe01ca36cc09fdd9fcede13724207e82d22739545f375b`.
During implementation the human reassigned the vendor T-Rex artwork to a Raptor
and approved bounded enlargement of other large beasts using existing passive
appearance scale, subject to visual inspection. Those amendments are included
below; implementation receipts live in
[the current checkpoint](SUMMONING_IMPLEMENTATION_2026-10-03.md).

**Current final-phase amendment:** after reviewing the initial gallery, the human
requested [these bounded corrections and Fly/summoning visual integrations](SUMMONING_FLY_FINAL_PHASE_PLAN_2026-10-03.md).
The summoning artwork is explicitly accepted; Fly is the only added spell visual.
The subsequent [17-sheet Goblin amendment](GOBLIN_ROSTER_FINAL_PHASE_PLAN_2026-10-03.md)
adds ordinary Goblin content and its source bindings, with no new summon choices.
The original24-creature scope below describes the completed earlier packet;
these explicitly linked amendments own the current additional work.
That linked amendment is part of this unified delivery and supplies the current
remaining implementation/acceptance work. It is at a planning checkpoint, not an
assertion that the new integrations are already complete.
The [final-phase anti-slop and anti-OOP/ECS review receipts](audits/SUMMONING_FLY_FINAL_PHASE_PLAN_REVIEWS_2026-10-03.md)
approve the exact revised design; implementation acceptance remains pending.

This is the sole implementation plan for this batch. It owns the gameplay
choices, all 24 creature/art assignments, native lifecycle, ordinary attack
prerequisite, events, existing-art integration, module boundaries, delivery order
and acceptance. Source studies below supply evidence and numerical baselines;
they are not additional work queues or independent implementation plans.

## 1. Scope and rules

Implement temporary animals, fey spirits and fiends using ordinary creature
composition, conditions, concentration, native AI, Encounter and recorded events.
Finish creation, normal turns, control loss, expiry, defeat and cleanup together.
Deliver **24 distinct canonical creatures: 18 beasts/dinosaurs and six fiends**,
all three spell adapters and their existing-sprite bindings together. Four current
recipes/bindings are reused; twenty are added. All 18 beasts also appear as Fey
spirits using the same bodies; manifestation variants do not inflate that count.
A wolf-only demo or lifecycle-only implementation does not complete this plan.
Undead/persistent creation, Familiar, elementals, the rest of the full roster, new
artwork/summoning VFX, server and general world-time simulation remain out of scope.

The human requires:

- Define each creature once, independently of summoning. Its recipe constructs
  without a summoner, spell or lifetime condition. Summoning changes only the
  incoming instance, never the recipe or other instances.
- Autonomous existing AI, initially allied to the caster; no master command
  stream, custom tactical policy or extra action-economy rules.
- Higher animal spell slots unlock stronger forms, not just more bodies.
- Concentration-dependent existence is simply Concentrating -> Summoned.
  Without concentration, apply Summoned directly, with shared lifecycle handlers.
- **Fey exception:** losing concentration leaves it alive and hostile, with its
  original expiry. Its former controller cannot subsequently dismiss it.
- Fey spirit appearance uses a shared blue/translucent manifestation binding
  over the selected existing rig, as specified in sections 2 and 10.
  Gameplay records manifestation semantics, never filenames or shader rules.

Reference: [SRD 5.1](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf).
Conjure Animals disappears when concentration ends. Conjure Fey becomes hostile
on concentration loss and remains until its original one-hour expiry. Familiar/
Steed do not require concentration; Animate Dead/Create Undead have persistent
existence and separate control. These examples explain the separation, without
adding deferred spells to this lane.

### Approved gameplay defaults

| Entry | Lifetime | Concentration sustains | Loss outcome |
| --- | --- | --- | --- |
| Conjure Animals | 600 creature intervals | Summoned | Despawn |
| Conjure Fey | 600 creature intervals | Untimed SummonControl only | Hostile, same remaining lifetime |
| Conjure Fiend, authored adaptation | 600 creature intervals | Summoned | Despawn |
| Native nonconcentration creation | Authored finite duration | Nothing | No concentration/source-death dependency |

600 combat intervals represents the SRD hour and replaces the earlier unapproved
ten-round proposal. Duration pauses outside encounters because Game has no world
clock; explicit departure causes still work. No desktop timer. Nonconcentration
creation is a native backend capability/test, not another authored spell.

Other approved defaults: one chosen creature per cast; action casting; 60-foot
visible legal placement; no recursive summoning by these summons. These are
stated game adaptations. Packs remain a pending alternative requiring revised
batch admission, not a silently approved choice. Multiple casters and existing
multiple-concentration slots remain supported.

An uncontrolled Fey receives a nonempty faction unique to its UUID, such as
uncontrolled_summon:<uuid>. Existing equality-based factions then make it
independent and hostile to other factions, including its former allies, without
joining the enemy team. This explicit approximation adds no diplomacy or preferred
targeting system. Avoid None, also used for missing/redacted observation data.

## 2. Canonical creature content and selection

One cold allowlist references ContentRecipe values: stable form ID, family,
minimum slot, recipe and manifestation. Body, stats, gear, attacks and appearance
remain exclusively in the canonical creature definition.

| Spell | Proposed choice count by slot |
| --- | --- |
| Conjure Animals | 3: 7; 4: 10; 5: 14; 6: 16; 7: 17; 8–9: 18 |
| Conjure Fey | 6: 16; 7: 17; 8–9: 18; same canonical beasts with spirit manifestation |
| Conjure Fiend | 3: 2; 4: 4; 5: 5; 6–9: 6 |

Ordinary placement and summoning use the same installed materializer. Fey's type
and manifestation apply before birth to that instance only. Blue art grants no
extra resistance, flight or damage. The selected batch has intrinsic default possessions only. Admission rejects
unsupported equipped forms rather than
stripping gear or restricting ordinary creature construction.

Discovery exposes form plus actual slot level. The typed selection is revalidated
at execution: registered family/recipe/level, native creature occupancy, supported
ground, visibility, range and ordinary physical/spell access. Preserve GridMap's
existing one-anchor-tile creature membership and size-dependent admission rules,
including for Large/Huge selected creatures. Multi-cell world-object footprints are not a
creature footprint implementation; adding multi-cell creature geometry/movement
is deferred. An ordinary and summoned instance use identical placement rules.
Reject illegal placement; no silent nearby placement or substitution.

Admission carries the existing subjective query mode. Discovery checks the
caster's known occupancy/support/access; an unseen creature must not remove a
candidate square from suggestions. Real execution checks objective placement and
returns ordinary placement failure without revealing the hidden occupant's
identity. This reuses native subjective placement, not a second visibility model.

### 2.1 Content and art authority

- [Animal/dinosaur source matching](audits/PACK_ROSTER_SRD_FIRST_ANIMAL_DINOSAUR_2026-09-30.md)
  supplies source profiles and edition/page references.
- [Animal/dinosaur inspected artwork](audits/PACK_ROSTER_ANIMAL_DINOSAUR_COMPLETION_2026-09-30.md)
  and its chosen-attack provenance supply literal variants and primary clips.
- [Authored Devil study](audits/PACK_ROSTER_AUTHORED_DEVILS_DRAFT_2026-10-01.md)
  supplies C04, C05 and C27 only. Other proposals in that document are not adopted.
- Current GreyWolf and DemonBeast01/02/03 bindings and native wolf/dretch/
  corrosive_demon/dread_demon recipes remain authoritative for those four entries.
  Do not replace them with the study's competing Thornback/Hookclaw/Ironhide
  proposals as a side effect of adding summons.

Art source keys are (pack, literal variant), not guessed filesystem names. Animal
art comes from Animals mega Pack 1 V2; dinosaurs from Dinosaurs Pack 1; fiends from
Demons V1.1. The JSON provenance under
.runtime/pack-study-20260930/animal-dinosaur-completion/animals/chosen-attacks/ and
its dinosaurs/contacts/ counterpart records the archive members. Source artwork
exists; that alone does not establish a production binding or calibrated timing.

### 2.2 Complete creature / slot / artwork table

Keys below are canonical creature keys, never summon-only species. Existing keys
retain their current content namespace/version. New adapted recipes belong to
content.neurodragon with creature.<key> identities; proposed identifiers must be
checked for collisions during registration. Do not claim source-exact SRD content
for the bounded adaptations below.

An unlock is cumulative: casting above it retains the selection without secretly
inflating its stats. Numbers are authored progression, not official SRD limits.
Fey unlock for each beast is max(6, Animals unlock); the Fey cast changes only the
incoming instance's type/manifestation/lifecycle, not its base recipe.

| # | Canonical key / display | Animals slot | Fey slot | Fiend slot | Exact artwork assignment | Production status / combat identity |
| --- | --- | ---: | ---: | ---: | --- | --- |
| 1 | wolf / Wolf | 3 | 6 | — | Animals: Grey Wolf; primary Attack2 | Existing smallscale.greywolf binding; Pack Tactics, scent/hearing and bite knockdown |
| 2 | hound / Hound | 3 | 6 | — | Animals: Shepherd Dog; Attack2 | New binding; Mastiff-based scent/hearing and bite knockdown |
| 3 | boar / Boar | 3 | 6 | — | Animals: Boar; Attack2 | New binding; tusk knockdown, compact melee body |
| 4 | stag / Stag | 3 | 6 | — | Animals: Stag; Attack1 | New binding; fast antler/ram knockdown |
| 5 | jaguar / Jaguar | 3 | 6 | — | Animals: Jaguar; Attack2 | New binding; fast claw/bite hunter, claw knockdown |
| 6 | bison / Bison | 3 | 6 | — | Animals: Bison; Attack3 | New binding; Giant-Goat-based horn/ram frontliner |
| 7 | ostrich / Ostrich | 3 | 6 | — | Animals: Ostrich; Attack1 | New binding; Axe-Beak-based fast peck attacker |
| 8 | brown_bear / Brown Bear | 4 | 6 | — | Animals: Brown Bear; Attack2 | New binding; bite-and-claw Multiattack, durable close fighter |
| 9 | lion / Lion | 4 | 6 | — | Animals: Lion; Attack2 | New binding; Pack Tactics and claw knockdown |
| 10 | tiger / Tiger | 4 | 6 | — | Animals: Tiger; Attack2 | New binding; stronger individual claw/bite hunter |
| 11 | polar_bear / Polar Bear | 5 | 6 | — | Animals: Polar Bear; Attack2 | New binding; stronger bite-and-claw Multiattack |
| 12 | rhinoceros / Rhinoceros | 5 | 6 | — | Animals: Rhino; Attack2 | New binding; heavy gore knockdown |
| 13 | blue_raptor / Blue Raptor | 5 | 6 | — | Dinosaurs: Blue Raptor; Raptor Attack1 | New binding; Allosaurus-derived claw/bite predator, explicit adaptation |
| 14 | stegosaurus / Stegosaurus | 6 | 6 | — | Dinosaurs: Stegosaurus; Attack3 | New binding; Ankylosaurus-derived armored reach-tail fighter |
| 15 | elephant / Elephant | 6 | 6 | — | Animals: Elephant; Attack1 | New binding; heavy trunk sweep and knockdown |
| 16 | triceratops / Triceratops | 7 | 7 | — | Dinosaurs: Triceratops; Attack1 | New binding; very heavy horn attack and knockdown |
| 17 | mammoth / Mammoth | 8 | 8 | — | Animals: Mammoth; Attack2 | New binding; high-HP tusk frontliner and knockdown |
| 18 | raptor / Raptor | 5 | 6 | — | Dinosaurs: vendor T-Rex reassigned by human; Attack1 | Existing Allosaurus numerical baseline; Bite or Tail, reach5; original appearance scale1.55 |
| 19 | dretch / Dretch | — | — | 3 | Demons: Demon Beast 1 | Existing smallscale.demonbeast01; preserve native kit |
| 20 | claw_mote_devil / Claw Mote Devil | — | — | 3 | Demons: Imp 5 | New binding; C27 intrinsic claw, ordinary actions, no invented wings/gear |
| 21 | corrosive_demon / Corrosive Demon | — | — | 4 | Demons: Demon Beast 2 | Existing smallscale.demonbeast02; native corrosive blood |
| 22 | dread_demon / Dread Demon | — | — | 4 | Demons: Demon Beast 3 | Existing smallscale.demonbeast03; native fear-producing blood |
| 23 | huntsman_wing_devil / Huntsman Wing Devil | — | — | 5 | Demons: Demon Beast 5 | New binding; C05 two claws, Devil's Sight and grounded flight |
| 24 | fellwing_devil / Fellwing Devil | — | — | 6 | Demons: Demon Beast 4 | New binding; C04 two claws plus gore, Magic Resistance and grounded flight |

Conjure Animals offers 7 choices at level 3, then 10/14/16/17/18/18 at
levels 4/5/6/7/8/9. Conjure Fey offers 16 choices at level 6, then 17/18/18.
Conjure Fiend offers 2 choices at level 3, then 4/5/6 at levels 4/5/6. Slots
7–9 retain those six choices; this batch invents no extra boss, scale multiplier
or recursive summons to fill every cell. Corrosive/Dread share a Dretch chassis;
their extra blood effects are the unlock, not a claimed higher base stat block.
Dire Wolf is removed from this batch rather than pretending an elite palette is
already its approved art. No palette sibling counts as another creature.

### 2.3 Bounded gameplay definitions

This is an art-led adapted game batch. Use the linked source block's passive
stats, defenses, speed and listed attack dice as the starting specification;
all departures in this section are explicit authored rules. The implementation
records the final complete EntityConfig/possessions/traits per recipe, with source
attribution and reviewed adaptation metadata. Do not copy the old draft's claims
that every source ability must be implemented into this bounded lane.

- Wolf and the three existing demons keep their content identity, stats, traits,
  attack dice and configured Multiattack. Do not recreate/fork them inside
  summoning/forms.py. The selected anatomical weapon definitions also receive
  the explicit body-attack semantics below; this corrects their incidental
  hand-slot defaults, without changing their creature kits.
- Hound uses Mastiff's ordinary Bite, its DC11 Strength save to apply Prone and
  keen hearing/smell. Bison uses Giant Goat stats; Stag uses Elk stats; Ostrich
  uses Axe Beak stats. These are explicit analogues, not exact source species.
- Boar/Stag/Bison/Rhinoceros use their primary Tusk/Ram/Gore with a configured
  on-hit Strength save versus Prone: DC11/13/13/15 respectively. This replaces
  approach-distance Charge for this adapted batch; no movement-distance tracker,
  charge bonus dice, Relentless or free follow-up attack is introduced.
- Jaguar/Lion/Tiger/Blue Raptor keep ordinary Bite and Claw actions. Their Claw
  carries a Strength save versus Prone at DC12/13/13/14. This replaces Pounce's
  run-up/bonus Bite chain. Lion retains existing Pack Tactics. No Running Leap
  extension or new bonus-action accounting. Natural senses use current owners.
- Brown/Polar Bear retain Bite + Claws Multiattack through the existing configured
  Multiattack path. Stegosaurus uses the selected Ankylosaurus-derived AC15/HP68,
  speed30 and two reach10 Tail attacks, 1d10+4 each; damage is piercing to match
  its tail spikes. This is an authored adaptation, not an exact Ankylosaurus.
- Elephant uses the depicted Trunk Sweep as its ordinary attack: source Gore's
  3d8+6 dice, changed to bludgeoning; DC12 Strength save versus Prone. Mammoth
  Gore uses source 4d8+7 piercing and DC18 Prone. Triceratops Gore uses source
  4d8+6 piercing and DC13 Prone. No automatic charge/stomp chain in this batch.
- Raptor replaces the initially proposed Tyrannosaurus at the human's request.
  Use the already selected Allosaurus numerical baseline: Large,51HP,AC13,
  speed60,STR19/DEX13/CON17/INT2/WIS12/CHA5, proficiency2, Perception expertise.
  Ordinary Bite (2d10+4 piercing) OR depicted Tail (1d8+4 bludgeoning), both reach5;
  no grapple, holding, bonus action or new rider. Animals unlock5; Fey unlock6.
  Preserve the original1.55 appearance scale and vendor asset paths.
- Blue Raptor, Raptor and Stegosaurus borrow the named 5.2 numerical baselines only,
  using the exact 5.1-style action/save semantics specified here. Retain edition
  attribution; never silently mix in unlisted 5.2 rules.
- C04/C05/C27 use the explicit authored stats/attacks in the Devil study. C04/C05
  fly speeds use existing InnateFlight: ground-to-ground traversal, no hovering.
  Do not add Flyby, innate spells, holding attacks or a command system.
- No source skill adds unsupported world exploration, swimming/climbing gameplay
  or multi-Z work. Keep current engine movement capability limits explicit.
  All selected ground positions use normal creature admission and current size
  semantics; large artwork does not authorize a multi-cell movement rewrite.

The on-hit save riders reuse HitSaveRiderFeature/ordinary Prone and target
outcome facts, with authored parameters. They must match the actual selected
attack identity in the native pipeline, never event name/time guesses. If current
rider identity matching needs tightening, change that shared existing owner and
its callers once; do not create a parallel attack executor or per-species handler.
These concrete adaptations are proposed alongside the slot tiers for human
approval; they are not already accepted balance or implemented rules.

### 2.4 Anatomical attacks use the existing Attack route

Source inspection found a real prerequisite: equipment currently admits a second
weapon only through LIGHT/off-hand eligibility, defaults its standalone attack to
a bonus action, and changes its ability damage modifier. Using those defaults for
a second jaw/claw/tail would silently change these creatures' rules. The current
Dretch-derived recipes also expose that off-hand default; their existing behavior
is not proof of correct body-attack semantics.

Add one explicit held-versus-body usage value to the existing WeaponDefinition
and Weapon data owners. Default held preserves ordinary weapons. Body usage is
valid only for an explicitly owned intrinsic natural weapon; never infer it from
name, renderer, creature species or summoning state. Opt in the selected batch's
anatomical definitions, including its existing wolf/dretch weapons; leave unrelated
weapon definitions untouched. No new attack class/resolver, anatomy inventory or
equipment slot family. This batch uses at most two distinct anatomical attacks.

Use one shared usage query in the existing owners:

- Weapon/Equipment admission and revalidation allow the secondary body weapon
  in the existing secondary melee position without manufacturing LIGHT or
  two-weapon eligibility. The positions select attacks; they do not mean this
  creature is holding its tail in its left hand.
- update_weapon_template authors a normal one-action Attack for either body
  choice. Explicit Multiattack child costs=[] stay untouched. Ordinary held
  off-hand attacks retain their current bonus-action contract.
- Weapon base damage and Equipment.get_weapon_damage_profiles use the normal
  authored ability modifier for body attacks in either position. Keep runtime,
  AI/outcome profiles and recorded attack results consistent; changing only the
  actual damage roll is insufficient. Held off-hand modifiers are unchanged.
- Entity.get_weapon_physical_access resolves body usage to NATURAL while keeping
  the exact intrinsic item/attack identity. The existing ordinary attack route
  still owns range, cover/access, target type, costs, rolls, damage and events.
- Main position remains the existing opportunity-attack/threat choice. Primary
  attacks: Wolf/Hound/Raptor=Bite; Boar=Tusk; Stag/Bison=Ram;
  Jaguar/Lion/Tiger/Blue Raptor/Brown Bear/Polar Bear=Claws; Ostrich=Beak;
  Rhinoceros/Triceratops/Mammoth=Gore; Elephant=Trunk Sweep;
  Stegosaurus=Tail; C04/C05/C27=Claws. Existing Dretch variants retain their
  currently authored primary. Secondary choices remain ordinary selectable
  attacks, not another reaction entitlement.

Configured Multiattack continues to select ordinary Attack children by position
and count (bear Bite+Claws; Fellwing two Claws+Gore; Stegosaurus two Tail attacks).
Standalone body attacks keep Attack's existing Haste/Extra Attack eligibility;
Multiattack remains its own one-action sequence and is not enabled through Haste.
Slow and reaction limits use the existing owners, with no new budget implementation.
Acceptance checks these boundaries, full body damage modifiers in both positions,
no accidental standalone bonus-action body attack, native/AI profile agreement,
and unchanged held-weapon/off-hand behavior. This bounded prerequisite belongs
to the reviewed batch scope, not an unannounced later refactor.

## 3. Components and condition graph

```text
ordinary creature: canonical recipe, no summoning conditions
nonconcentration:  creature.Summoned(Duration)
animal/fiend:      exact Concentrating slot -> creature.Summoned(Duration)
Fey:              creature.Summoned(Duration) owns child SummonControl(untimed)
                  exact Concentrating slot ------------> SummonControl
```

Only Fey needs the extra control condition. Use existing same-owner child links
and cross-owner concentration links. Control loss must not remove its existence
parent (child_removal_policy='none'). Full existence removal removes its child
without briefly turning it hostile.

| Owner | State it owns |
| --- | --- |
| Canonical creature | Body, stats, gear, abilities, ordinary actions/appearance |
| Summoned condition on creature | Immutable origin/form/manifestation; ONE Duration; last processed interval; optional exact Fey control UUID |
| SummonControl, Fey only | Original controller and exact concentration parent link; no finite timer |
| Existing Concentrating/slot | Sustain link to exact effect UUID, not another lifetime |
| Summoning system | Explicit Game/Encounter, native AI handles, indexes to owned UUIDs and temporary prepared operations |
| Encounter | Initiative, active execution ID and pending membership removals |

There is no caster-side summon lease. No copied HP, inventory,
faction, duration or control boolean lives in the system's runtime record.
Fey dismissal authority requires the exact original applied control condition;
other admitted summons use original source plus live Summoned membership. Starting
another concentration does not recapture a released Fey.

## 4. Module structure and import DAG

| New file | Concrete contents |
| --- | --- |
| dnd/types/summoning.py | Frozen passive selection/origin/rule/release values and enums; no Entity/Game/AI imports |
| dnd/summoning/__init__.py | Minimal package marker; no binding/bootstrap side effects |
| dnd/summoning/forms.py | Cold canonical allowlist and three spell specifications; no duplicate statblocks |
| dnd/summoning/conditions.py | Summoned and Fey-only SummonControl, ordinary lifecycle hooks and interval progression |
| dnd/summoning/actions.py | One ordinary DismissSummon action and native authority/target validation |
| dnd/summoning/system.py | Binding, preparation/commit orchestration, indexed lifecycle handling and AI ownership |
| dnd/spells/summoning.py | Three thin SpellAction declarations and shared typed selection/discovery |
| dnd/monsters/beasts.py | Seventeen new canonical beast recipes composed through existing creature_factory/content registry; existing Wolf is reused |
| dnd/monsters/fiends.py | Three new C04/C05/C27 recipes; existing Dretch and demon_variants.py identities are reused |

```text
spell declarations -> forms / summon conditions / ordinary actions / passive types
summon conditions/actions -> ordinary condition/action/entity owners / passive types
summoning system -> Game / Encounter / AI / installed materializer /
                    summon conditions / forms / passive types
Game / Entity / Encounter / core events -> passive types and existing lower owners
creature recipes -> EntityConfig / existing item grants / native trait/action grants
forms -> canonical recipe references; never copied creature definitions
record codec / shared reduction -> passive facts
rig/material ingestion -> content references / existing BodyRig and BodyClip data
presentation -> retained actor facts / loaded rig and material data
```

Spell/condition code and Game never import the high summoning system. Creature
recipes import no summoning runtime. Use installed_creature_materialization.py,
not the bootstrap-importing creature_materialization.py inside spell closure.
No entity subclasses, late imports, reflection/class-name dispatch, current-game
service lookup, new bus or parallel registry.

| Existing owner | Required bounded implementation |
| --- | --- |
| dnd/entity.py | Initial-condition prepare/commit, prepared birth/state commitment/publication, exact aggregate retirement, faction change, duration interval forwarding |
| dnd/core/base_block.py; base_conditions.py; condition_types.py | Lower-owned condition admission/commit records and hooks; removal-graph settled boundary; typed involuntary sustain-loss and terminal release contexts |
| dnd/actions.py; dnd/conditions.py | Share optional concentration preparation; exact cast/slot links; preserve current action-cost timing |
| dnd/game.py; core/gridmap.py | Prepared causal deployment/retirement and existing real-item placement; close callbacks |
| dnd/encounter.py; controller.py | Live join/leave, safe unwinding, current_turn_execution_id in TurnContext |
| dnd/ai/contracts/control.py; runtime/decision_epoch.py; assignment_lifecycle.py; policies/basic.py | Existing stable turn ID in epoch/budget/memory, not mutable list index |
| dnd/ai/runtime/movement_revalidation.py | Faction in existing state guard, stopping a path planned under obsolete allegiance |
| dnd/core/events.py; dnd/actor_projection.py; types/actor_facts.py | Typed origin/departure and ordinary faction-after-value fact/reduction |
| game/event_record.py; game/player_projection.py; dnd/ai/runtime/knowledge_reduction.py | Finite codec/subjective fact consumption only, no drawings or VFX |
| dnd/blocks/base_item.py; equipment.py; inventory.py | Explicit prepared release results, causal real-item drops and exact intrinsic retirement |
| Existing item definitions/Weapon data, actions_functional.py and Entity attack access | Section 2.4's explicit anatomical-use policy through ordinary Attack; shared equipment/runtime/AI damage semantics, no new attack executor |
| dnd/actions_functional.py; content_system/builtin.py; spells/catalog_content.py | Standard DismissSummon template and canonical spell/condition registration |

The creature modules share ordinary composition from existing EntityConfig,
intrinsic item grants and explicit native trait/action grants. Reuse current
composition helpers where sufficient; no opaque trait-name dispatcher or second
content registry. Natural attacks/defenses are actual intrinsic possessions,
never droppable anatomy or an empty-hand fallback for claws. Low weapon/equipment
owners consume passive usage data; they import neither creature catalogs,
summoning nor rendering.

Existing presentation owners remain game/data/rigs/<rig>.json, BodyRig/BodyClip
and game/animation_data.py ingestion, plus the shared material binding. They
resolve explicit content references; native recipes/forms contain no sprite
filenames. The finite codec/shared reduction owns retained manifestation facts,
not a per-creature renderer. Section 10 specifies the complete binding contract.
Check the precise existing registration owners while implementing; do not solve
an import problem by creating another content registry.

## 5. Data and native API contracts

Passive values:

- SummonSelection: family, form_id, cast_at_level, target_position.
- SummonRules: duration_rounds and concentration requirement/target (none,
  existence, Fey control), with only supported combinations authored.
- SummonOrigin: immutable summoner UUID, cast lineage, canonical recipe/form,
  manifestation, existence-condition UUID and optional Fey control UUID.
- TerminalOwnerRelease: exact actor/existence-condition UUID, committed typed
  cause and parent event reference. Not a universal force flag.

Prepared operations are private runtime records, storing admitted objects/owner
references and consumed state. They are never serialized as event payloads.
Proposed public seams extend existing owners and share their existing helpers:

```python
bind_summoning(game, encounter) -> SummoningSystem
system.rebind_encounter(encounter) -> None
system.close(parent_event=None) -> None
system.reset() -> None  # silent engine reset

entity.prepare_initial_conditions(conditions, *, parent_event) -> PreparedInitialConditions
entity.commit_initial_conditions(prepared) -> None
entity.prepare_birth(*, initial_conditions, parent_event=None,
                     summon_origin=None) -> PreparedBirth
entity.commit_birth(prepared) -> None
entity.publish_birth(prepared) -> EntityCreatedEvent
entity.compose_entity(*, parent_event=None, summon_origin=None) -> EntityCreatedEvent
entity.set_faction(faction, *, parent_event) -> EntityFactionChangedEvent | None

game.prepare_deployment(entity, position, *, parent_event) -> PreparedDeployment
game.commit_deployment(prepared) -> None
game.prepare_entity_retirement(entity_uuid, *, cause, parent_event) -> PreparedRetirement | None
game.commit_entity_retirement(prepared) -> None

encounter.prepare_combatant_join(entity, controller, *, after_uuid) -> PreparedJoin
encounter.commit_combatant_join(prepared) -> None
encounter.request_combatant_leave(entity_uuid, *, parent_event) -> None
```

Ordinary Game deploy/remove wrappers preserve behavior; remove_entity remains
reversible. Prepared condition/concentration logic belongs to existing native
condition/action owners, never a second implementation in system.py.

PreparedInitialConditions and the ordinary PreparedConditionApplication record
belong to BaseBlock, referencing only BaseCondition and admitted lower-owned
application/link data. Extract the existing condition application commit hook in
BaseCondition; Concentrating implements its own prepared slot-transfer commit in
dnd/conditions.py. SpellAction prepares its optional sustain requirement through
those shared APIs. The high summoning owner orchestrates already admitted lower
tokens; Entity commits only its own initial conditions. Entity never imports
Concentrating, SpellAction or their concrete prepared implementation. These are
bounded extractions of current admission/commit work, not a new transaction model.

PreparedBirth belongs to Entity and holds one unregistered EntityCreatedEvent
captured from its complete admitted initial composition, including incoming
condition after-values. prepare_birth validates while the actor is uncommitted
and undeployed; commit_birth sets creation_committed without publishing; then
prepared deployment/join can commit. publish_birth publishes that exact staged
fact once, without rerunning undeployed-state validation. Ordinary compose_entity
becomes the prepare/commit/publish wrapper, preserving its existing caller path.

## 6. Binding, discovery and creation

Bind explicitly after native Game/Encounter/content composition and before
discovery. Install exact world/encounter-filtered handlers once and an indexed
PreCompletionSystem for actual phase-transition condition/damage/death facts.
Duplicate binding is an error. This registration performs actual lifecycle work,
not a dummy registration to receive reset.

Pure admission uses a dedicated typed SummonAdmissionEvent proposal with
use_register=False. Both discovery and actual pre-cost validation explicitly
invoke existing EventQueue.preflight. Only its narrow validation_only handler
answers with a passive binding identity or rejection. Discovery currently bypasses
normal declaration dispatch; do not depend on that dispatch. No actor/condition
construction, resource reservations or event publication during discovery.
The proposal explicitly carries discovery's subjective mode; actual pre-cost
validation and final placement admission use objective mode. A hidden occupancy
failure supplies no new identity or visibility fact.

The normal SpellEvent receives an optional typed summon selection/application
field. Its EFFECT reaches the bound mechanical handler, which runs shared native
creation. No executable callbacks in events, second summon command/result journal,
duplicate resource facts or spell-name switch. Native creation also admits an
explicitly authored nonconcentration specification; player spell input cannot
override canonical sustain rules.

### Actual creation sequence

1. Validate canonical form/level, live binding, active encounter, nonempty caster
   faction and placement before costs. Invalid input spends nothing.
2. Preserve BaseAction's existing action/slot commitment before EXECUTION and
   _apply. Counterspell or later rejection retains those spent resources.
3. Revalidate access; materialize fresh canonical creature/default possessions,
   validate intrinsic admission and set any instance-only FEY manifestation.
   No birth/presence has been published.
4. Build one Summoned(Duration); add untimed control only for Fey. Prepare initial
   condition applications, native one-tile creature placement, encounter join and
   idle AI. Prepare the single complete birth fact while still undeployed.
5. Share SpellAction's get_concentration_owner/_new_concentration preparation.
   Preserve item sustainers and multiple slots. The exact child is Summoned for
   Animals/Fiend, control for Fey, absent for nonconcentration.
6. Admit cancellable phases and revalidate placement/turn membership after their
   callbacks. Commit admitted concentration replacement, incoming condition
   memberships and exact links through their native lower hooks. Commit the
   prepared birth's creation flag, then prepared world/encounter memberships.
   No further veto/callback/publication may split this authority commit.
7. Publish the single staged EntityCreatedEvent, initial condition COMPLETION facts,
   presence/initiative facts and concentration after-state. Start normal AI only
   after committed membership/facts; no decision inside the casting call.

This needs a real narrow extension: add_condition currently publishes immediately,
condition._apply precedes required concentration admission, and apply_owned_condition
links the child only after add_condition returns. Sequential calls would publish
orphan completed conditions or a birth before a later veto. Extract existing
prepare/commit parts. Preparation may publish DECLARATION/EXECUTION/EFFECT attempts,
but no committed condition COMPLETION, birth or world presence. Incoming lifecycle
condition _apply hooks activate no external mechanics before commit.

Prepared concentration records admitted old removals, retained/incoming slots and
exact child link; defer old-slot removal until all incoming admissions pass. Its
commit uses the existing child-first transfer. Keep apply_owned_condition as the
ordinary wrapper with its existing public cost/cancellation contract. No early
ensure_concentration call or new generic buffering/transaction framework. Prepared
deployment/join revalidate before the non-reentrant commit; resulting observation
cannot retroactively veto committed state.

Condition, concentration, deployment and join owners likewise separate their
state commit from publication for these prepared operations; ordinary wrappers
continue to do both. Prepared records retain their specific accepted events and
after-values, not an arbitrary buffer of gameplay events. Existing child removal
and linked-parent publications from concentration replacement occur after this
authority commit and before draining its settled removal consequences.

Precommit failure cancels attempts, closes provisional AI, discards materialization
binding and unpublished actor state; previous summon/concentration survive. Paid
spell costs stay paid. After commitment, publication failure is a committed error,
not cancellation/rollback. Fix compose_entity's current catch-all reset/discard
path after publication has begun; archived birth must never be silently undone.
Duplicate delivery of one committed operation is a no-op; a newly issued cast is
a new paid action. No network retry/cache system.

## 7. Shared handlers, Fey control and dismissal

Conditions use ordinary data/hooks and do not import the high owner. Its runtime
indexes match exact condition/entity UUIDs; do not scan historical events or
branch on spell/creature display names.

| Trigger | Shared handler result |
| --- | --- |
| Summoned removal admission | Prepare exact actor/item/encounter retirement before voluntary removal can commit |
| Summoned committed removal | Commit prepared retirement once; suppress subordinate control-loss hostility |
| Fey control committed removal while Summoned remains | Set hostile faction, preserve actor/HP/gear/AI/Duration; end former dismissal authority |
| Summoned actor zero HP / death | Mandatory terminal release; no lootable corpse, death saves or resurrection target |
| Exact sustain ends | Existing graph removes linked child; no universal source-death handler |
| Game close | Causal retirement before world/identity release |
| EventQueue reset | Silent runtime teardown, no events in a cleared generation |

Terminal context identifies the ending existence owner through child-first
cleanup. A control child removed during expiry/dismissal produces no intermediate
hostility. Independent control removal does. Per-child condition completion is
still inside BaseBlock's removal loop, so it cannot be the retirement boundary.
Those indexed handlers only record the exact prepared consequence and revoke
departing agency immediately; they do not recursively retire the actor.

BaseBlock exposes a dependency-neutral condition-graph-settled callback, registered
and removed by the explicit summoning binding. A bounded removal scope records
the actual committed condition UUIDs and causal removal facts, then invokes this
hook once after the outer graph's children, parent links and resulting-state
publications finish. Concentration replacement and prepared birth share that
outer scope. The callback matches the high owner's exact prepared consequences,
consumes each before executing it, and finishes retirement/control loss there.
No generic deferred-work queue, new gameplay fact or passive observer performs
mechanics. Cancelled preparation has no settled removal consequence; reset removes
the hook silently. Keep this scope in the existing condition-removal owner.

The scope wraps complete outer operations: _remove_condition_tree;
_apply_declared_condition through incoming membership publication;
Concentrating.drop_slot through slot deletion/sync/owner publication; and prepared
summon creation through its final parent publications. It cannot end merely when
_commit_prepared_condition_removals returns. Nested calls reuse that same scope.
Receipts contain only owner/condition UUIDs, causal removal fact and typed release
context. Reset the active scope before callback dispatch, so body cleanup starts
a fresh graph. Publication errors still settle committed receipts before reporting
the error; one callback failure cannot skip other committed cleanup receipts.

Damage break, caster death, DropConcentration and replacement remove the exact
linked effect. For Fey these release control. Item sustainers follow their existing
rules; summoner death alone does not end independently sustained/nonconcentration
existence. No automatic control restoration on a later cast.

Involuntary loss must enter before a removal veto can preserve authority.
Concentrating's failed-save, zero-HP and death handlers call the lower removal
owner with a typed InvoluntarySustainLoss (cause, exact sustaining condition/slot,
parent fact). BaseCondition exposes a passive sustain-loss policy, ordinary by
default; Summoned and SummonControl require release of their exact sustain link.
No concrete summoning import is added to Concentrating. The native owner prepares
and commits these mandatory linked branches independently of vetoes on voluntary
or unrelated branches: an old concentration root retained by an unrelated veto
cannot retain/recreate the removed summon/control link or its slot authority.
Then existing removal semantics handle any other links/root cleanup. Required
Summoned loss uses TerminalOwnerRelease; required Fey control loss leaves Summoned
and its Duration intact and schedules hostility at the settled boundary.
DropConcentration and replacement remain voluntary and retain admission vetoes.
This does not grant arbitrary callers a force-remove API or change the default
loss policy of unrelated effects.

DismissSummon is one native action, proposed cost one action. Its standard template
only exposes truly dismissible targets; execution revalidates source/target and
exact live membership. Fey requires its original applied control condition, so a
hostile Fey rejects old action indices, guessed UUIDs and source-only authority.
Use ordinary action/event handling plus prepared voluntary terminal removal.
DropConcentration remains separate and turns Fey hostile. No tactical commands
or new UI are included.

Entity.set_faction validates live identity, commits once, and publishes ordinary
EntityFactionChangedEvent(entity_uuid, previous_faction, faction_after, parent).
Equal value is a no-op. Shared actor/AI reduction updates recorded allegiance.
Keep the same one-entity controller, turn ID and resources. Revalidate stale
choices and remaining movement at normal boundaries; never grant a fresh turn
or action budget when control is lost.

## 8. One duration clock and live initiative

Summoned lives on the creature. Forward Entity.advance_duration_condition to
condition.progress_for_interval(self.turn_duration_interval), matching the existing
BaseBlock interval seam. Default BaseCondition behavior is unchanged; Summoned
alone deduplicates its existing encounter/round token and skips its birth interval.

Birth in round N stores that interval as already processed, without decrement.
Its first inserted turn in N keeps L. Turn N+1 decrements L to L-1. After L later
distinct intervals it expires before actions: L=10 permits N through N+9, L=600
permits N through N+599. Duplicate processing cannot decrement twice. Control
loss never resets the duration/token. New-encounter rebind preserves remaining
count; the first actual turn there consumes the next tick. No caster/control/AI
or client timer.

New summons join after caster and already anchored summons in creation order.
Do not reroll/reorder existing actors. Birth is not TurnStart; the ordinary
reaction becomes available on commitment without an extra refresh. A released
Fey keeps its place. On a later encounter, controlled survivors join after their
present source; uncontrolled Fey uses ordinary hostile admission/initiative and
does not require its former summoner. No new birth on rejoin.

Carry Encounter.current_turn_execution_id through TurnContext, DecisionEpoch,
assignment budget keys and basic-policy memory. Index is only position. Membership
shifts and allegiance changes cannot reset existing turn budgets.

Encounter defers list surgery until active calls unwind. At committed departure,
revoke action/reaction permission immediately so stale movement cannot commit a
further step. Finish leave at start/end/run-turn, indexed execution and move/
reaction return boundaries. Removal before current preserves actor/turn ID;
current removal ends its turn once; future removal does not skip the successor.
Use membership snapshots for death iteration. Re-evaluate encounter end after
last hostile departure or allegiance change.

Each summon has one existing one-entity NativeAIController assignment. No resizing
party assignments or resetting their memories/senses. Preserve the same assignment
across hostility. Encounter.end invokes controller.on_encounter_end; the directly
constructed COMPLETION event does not run pre-completion systems. Explicit rebind
releases old references and creates fresh assignments around surviving actors.
Outside combat, duration pauses; no new follow AI/world clock.

## 9. Exact terminal retirement and items

Game.prepare_entity_retirement delegates to Entity, existing BaseBlock child-graph
preparation and GridMap real-item placement preparation. It records exact owners/
IDs and admitted world/turn changes. commit applies this plan once. Preserve
ordinary reversible remove_entity.

- Voluntary dismissal/replacement retains normal veto admission. Rejection leaves
  previous actor, possessions and links intact; replacement's paid costs remain.
- Mandatory expiry, zero HP, required loss of an existence-sustaining effect or
  close uses exact TerminalOwnerRelease. Child veto cannot retain expired authority.
  No global force flag or changed unrelated cancellation policy. Fey control loss
  is explicitly not terminal.

Preserve real possessions with normal unequip hooks; retire intrinsic anatomy;
release owned conditions/modifiers/actions/reactions; detach occupancy/senses/light;
finish encounter/controller removal and exact live registrations/content binding.
Publish terminal membership while event-time position/witness identity remains
available. Retain historical facts. Repeated/simultaneous causes cannot duplicate
terminal departure.

BaseItem.retire must return an explicit accepted/rejected result and join prepared
release instead of silently ignoring veto. Never use destroy/remnants for magical
expiry. Extend normal contained-item release with parent_event and typed reason:
current equipment release emits unparented destruction-labelled facts even when
real gear survives. Run unequip hooks; do not clear slot dictionaries directly.

Intrinsic teeth/hide/claws cannot loot and retire with their exact owner. Real
acquired items drop intact on the last supported nonblocking ground tile, keeping
UUID, coatings, charges and bag contents. Missing/corrupt supporting tile is a hard
invariant failure preserving real item identity, never deletion fallback. New
terrain-deletion recovery/storage remains outside scope.

Only intrinsic-default recipes are supported here. Future conjured transferable
gear requires an explicit lifetime/merge policy before admission; no speculative
item registry or stack refactor now. Ordinary equipped creatures are unaffected.
Independent damage, recipient effects and demon residues keep existing lifetimes;
remove only real dependencies. Never erase everything with a matching mutable
source_entity_uuid. Ordinary creatures keep normal death/corpse/loot behavior.

## 10. Recorded events, presentation and session lifecycle

### 10.1 Facts and passive replay

| Fact | Producer/consumer | Concrete change |
| --- | --- | --- |
| Existing EntityCreatedEvent | Entity / shared actor birth reducer | Optional passive origin and causal parent; one complete birth |
| Existing condition facts | Initial-condition commit / shared reducer | Completions after birth, ordinary removals later; no duplicate entity snapshot |
| Existing SpatialChangeEvent ENTITY_LEFT | Game/GridMap / presence projection | Optional typed terminal reason/existence reference, distinct from reversible detach/contact loss |
| New EntityFactionChangedEvent | Entity.set_faction / actor and AI reducer | entity_uuid, previous_faction, faction_after, parent; ordinary engine fact |
| Existing concentration after-state | Concentrating / normal reducer | Exact slot/child links, no copied duration |

Extend game/event_record.py's finite codec explicitly; old recordings omit new
optional fields legally. No dynamic import/class-name codec. actor_fact_owner /
apply_actor_fact, AI knowledge and subjective projection consume the same facts.
Passive replay never creates native actors or spends resources.

No duplicate SummonCreated/Despawned state events alongside birth/actual departure.
Admission queries are not gameplay facts. Parent links connect concentration ->
control removal -> faction change, or expiry -> removal -> departure, without
matching by timestamp or target name.

Contact/visibility loss never despawns native actors. True departure cannot leave
a currently visible ghost. Capture normal event-time identity/coordinate permissions
before release; never reveal hidden caster/form/loot facts. Faction change also
follows current observation; later reacquisition receives current state, not unseen
history. The actor's own AI receives its new allegiance.

### 10.2 All 24 existing-art bindings and Fey manifestation

Four current rigs are reused; author the twenty missing bindings against the
exact pack variants in section 2. Read ASSETS.md before importing existing sheets.
Use existing game/data/rigs/<rig>.json, BodyRig/BodyClip, direction/shadow/action
data and game/animation_data.py ingestion. No runtime archive lookup, new artwork
production, per-creature renderer or unrelated animation refactor.

Each binding must supply actual Idle/Move/Attack/TakeDamage/Death mappings,
frame timing, contact/release markers, ground pivot, facing rows and separate
shadow policy. The inspected primary clip in section 2 is evidence, not proof
that it also represents every secondary attack. Resolve each required secondary
motion against the existing sheets before accepting that creature; record any
justified motion reuse. A missing mapping remains an incomplete row, never a
silent generic-human attack or missing animation presented as completion.

Fey uses the same rig plus a shared spirit material assignment: blue palette
replacement and authored alpha through existing material primitives, not
multiplicative tint or duplicated blue exports. Its typed manifestation is
captured before birth and retained by the finite codec, shared actor reducer and
subjective facts. Live and historical presentation read that same retained value;
they never inspect a live condition/controller/caster or infer rules from pixels.
Control loss changes faction, not body identity or spirit appearance. Supported
reacquisition carries current manifestation without revealing unseen history.
Any necessary shared body-material binding is bounded to these existing owners;
no summoning-only drawing executor.

Ordinary typed birth/departure inserts/removes the actor through the existing
presence path, including during historical playback. New special summon/despawn
VFX production is deferred and is not needed for functional lifecycle completion.
The review uses the established in-engine gallery, real floor tiles and actual
native fights; no substitute art-only preview is an acceptance artifact.

### 10.2.1 Explicit alternate-rig presentation component

Existing production already owns a single content-ref -> BodyRig registry in
AnimationData.creature_rigs/rigs, populated by _additional_rigs in
 game/animation_data.py. Keep it. Alternate sprites are registered data in this
registry, not a second sprite system. Backend recipes stay independent of media.
The current BodyClip maps semantic clip IDs to source sheets/FPS/frames, but that
alone does not finish action selection or contact timing.

Source inspection found two concrete gaps to close within packet 5:

- AttackProfileMatch currently selects from attack source, item, slot, damage and
  outcome; it has no rig constraint. The default human off-hand profile chooses
  Attack5 and human contact frame 8. Copying that onto every secondary natural
  attack is not the required mapping. A selected source strip also does not
  establish correct miss/critical or secondary-action bindings.
- Shared movement/condition/body-action contexts supply body clips globally.
  They can request Rolling, Taunt or a death pose on a body lacking that motion.
  Flying movement facts already carry movement_mode; selecting a winged body
  cannot be inferred from the spell name or a creature-name branch.

Design the bounded extension in existing presentation owners:

1. Extend existing AttackProfileMatch with optional authored rig IDs. Resolve the
   actor's rig from retained actor state before select_attack_profile; pass that
   rig identity into the existing pure selector. Match natural attacks by exact
   recorded intrinsic item identity and its actual attack_source_kind, not by name
   or damage type alone. In the ordinary item-backed Attack route those body
   weapons currently record source kind equipped; preserve that fact and exact
   item UUID/ID. The natural discriminator belongs to the separate NaturalAttack
   representation and must not be required for this batch's intrinsic weapons.
   Physical access NATURAL and recorded attack-source kind are distinct concepts;
   do not rewrite events to make a presentation selector match. Author rig-scoped variants in the existing attack-profile data,
   reusing a row across rigs where clip, clock and markers are truly identical.
   Each row uses existing ActionActor, ActionFrameAnchor and AttackVfx types for
   its actual clip, contact/recovery timing and optional separated effects.
   No additional attack registry or per-creature Attack executor.
2. Add an optional passive body-context binding table to BodyRig, loaded with its
   existing JSON record. Define its small typed records in animation_types.py.
   Each RigBodyContextBinding has a finite context role and ONE discriminated
   qualifier: an exact existing action/condition content reference; the complete
   recorded movement signature (movement_mode, trajectory,
   connector_presentation_key, including explicit None values); or role-default.
   MovementFact has no action behavior reference: use its actual recorded fields.
   In particular DIRECT_ARC identifies jump travel, and connector keys distinguish
   window traversal; walking and flying modes alone are insufficient. Context
   roles distinguish primary/recovery movement, Shove, forced movement, ordinary
   body actions, equipment gesture, condition entry/hold/exit, healing and optional
   save-avoidance body motion. They are presentation contexts, not new actions.

   The payload is body-only: the existing ActionActor and ActionFrameAnchor data,
   plus the existing finite playback choices (loop/once/final-rest, reverse and
   any explicit frame keys used by that body context). Reuse lower authored types;
   do not create another rig or timeline type hierarchy. Actor media/hidden-slot
   mutation is not added through this table. Each override supplies the complete
   required body marker set for its consuming context; e.g. effect for a gesture,
   commit for equipment, and an explicit rest pose/frame for a condition hold.
   Keep source FPS/frame counts in BodyClip. Empty/disabled gesture data is valid
   only in contexts that already allow it; attack and required pose coverage
   cannot be disabled to conceal missing media. Validate frame keys/markers
   against the selected clip and validate playback choices for that context.

   These records never overwrite native trajectory, outcomes, resources,
   feedback, condition state or the shared event join semantics. This table does
   not select attacks; step 1 remains their sole profile/anchor owner.
3. Resolve body-context bindings through one pure helper beside body_clip in
   game/animation.py. Its query is retained rig identity + context role + the
   exact qualifier available from the recorded fact. Lookup order is one exact
   binding, then at most one authored role-default, then the existing compatible
   shared body recipe. There are no independent wildcard combinations, numeric
   precedence rules or ordering-dependent matches. Duplicate exact/default keys
   fail data validation; unknown references/modes/roles fail rather than being
   guessed. Missing fact fields from older records are not invented from a name.

   Feed the resolved body data to the existing owners, including both their
   timing and sampling: choreography movement primary/recovery; forced_movement;
   condition_animation entry/hold/exit; body_action primary/recovery; equipment,
   healing and optional save-avoidance body contexts. In forced_movement.py both
   bind_shove (ShoveFact does not enter body_action) and bind_forced_movement /
   sample_forced_body consume the binding. Resolve and retain primary/recovery
   data together on the existing cue, once; join/sampling may not reread the old
   global recovery clip after timing a rig-specific one. Damage/death/life-state
   owners in animation.py/choreography keep validated compatible shared defaults
   or consume the same body override where needed. Their actual clips and frame
   markers remain in coverage. A clip-only pixel remap
   while timing, reverse playback or held poses still use the human defaults is
   incomplete. Native motion still supplies its recorded path/arc/reactions;
   clip frame keys adjust body sampling only. No new runner, event subscriber,
   custom callbacks or actor-specific branches.
4. Existing modular and fixed-rig data with no overrides retains the original
   shared recipe. For the selected 24, validate every reachable ordinary action
   and applicable condition context against an explicit binding or a verified
   compatible shared default. Do not turn absent art into gameplay restrictions.
   A neutral no-gesture action is permitted only as an explicitly authored
   existing body-disabled disposition; it cannot replace attack/travel/Prone
   coverage or silently hide a required effect. Current bind_body_action reads
   body_clip even when disabled: author a valid neutral Idle binding, or make that
   existing owner skip unused gesture lookup/marker validation while preserving
   the ordinary effect/child join timing. Do not return None and lose the action.
   Missing required coverage fails
   the acceptance ledger, with the exact rig/context/clip reported.
5. Movement-mode selection can choose a flying clip or reviewed winged pose for
   the two flying fiends while existing recorded movement owns ground endpoints,
   route, reaction timing and height. Ordinary jump, flight and window traversal
   remain distinct native contexts; do not grant actions because a clip exists.
   Prone entry/rest/stand-up must use an adequate existing fall/rest sequence;
   an exploding or disappearing death strip cannot stand in for a living pose.
6. Each body binding still resolves through BodyRig.clips -> BodyClip -> existing
   resource records, pivots and eight facing rows. Separated body/shadow/effect
   layers retain their existing slot policy. Fixed attacks with baked effects do
   not acquire a duplicate modular sword slash. Use explicit empty AttackVfx
   tracks where no separate effect is required; unmet mandatory effect tracks
   stay a reported gap. Keep all mappings as portable typed JSON data.

The body-context table is a missing part of the current design, not a claim that
it already exists. Its implementation must keep the dependency DAG:
 passive authored records -> ingestion/validation -> pure binding -> existing
 samplers/drawers. Neither binding nor drawing imports canonical creature modules
or looks up native Entity/Equipment/conditions. Tests must check ordinary and
summoned copies select the same body/action data; Fey changes material only.
No hand-coded wolf/bear/demon dispatch is an accepted shortcut.

### 10.2.2 Visual gaps and later user-delivered handoff

[Visual gaps and action-mapping addendum](SUMMONING_VISUALS_ADDENDUM_2026-10-03.md)
is the linked evidence/acceptance ledger for this section. It distinguishes
existing bindings, source clips requiring calibration, new renderer data work
and deferred VFX production. It adds no new gameplay scope or second implementation
sequence. The user alone decides when to send its VFX portion to the artist;
**do not message or hand off to the VFX thread on the user's behalf.**

Dedicated arrival/despawn effects, optional spirit halo and control-break accent
remain later visual delivery. Their absence does not relax current ordinary
rig/action/Fey material requirements or the recorded birth/departure contracts.
Independent reviewers must review the linked addendum together with any change
to these mapping requirements; receipts identify the exact current document bytes.

### 10.3 Session close, reset and supported restoration

Game has dependency-neutral add_close_callback/remove_close_callback, with no
reverse import of the high system. Normal close retires summons causally before
other entities. EventQueue.reset clears generation first, so system.reset only
closes AI/releases references; normal full reset clears world registries.

General durable encounter save/load is not included. Passive archives round-trip
origin/control/departure. Any supported native restore must retain condition/
Duration/link data or explicitly reject unsupported restoration. No controllers
or closures in serialized data.

## 11. Single delivery sequence and acceptance

Finish the entire batch in this order; packets are implementation checkpoints,ok
not separate releases or permission requests. Each packet consumes the preceding
owners rather than introducing a parallel path.

| Packet | Concrete work and dependencies | Exit evidence |
| --- | --- | --- |
| 1. Ordinary body attacks and canonical content | Implement section 2.4 in existing weapon/equipment/Attack owners, then register the 20 new recipes and opt in the selected four existing recipes. Use the exact section 2 stats/adaptations, intrinsic possessions and primary/secondary attacks. No summoning dependency. | All 24 construct as ordinary creatures; every authored attack and existing Multiattack works through native indexed actions/AI; held-weapon/action-budget regressions pass. |
| 2. Passive contracts and native owner seams | Define passive selection/origin/release values and the two conditions. Extract native condition/concentration prepare/commit, birth/deployment, faction mutation and exact retirement, including the graph-settled and involuntary sustain-loss boundaries in sections 5–9. | Ordinary wrappers preserve public contracts; unpublished failure and committed publication-error cases pass; real possessions survive retirement and intrinsic ownership ends exactly once. |
| 3. Autonomous lifetime and live encounter membership | Bind the high system explicitly to Game/Encounter. Wire the direct existence dependency and Fey control exception, stable turn ID, interval progression, safe departure and ordinary AI assignment/rebinding. Uses packet 2, no spell-specific AI. | Native nonconcentration creation and both concentration patterns complete their lifecycle; insertion, hostility, expiry, defeat, dismissal and teardown preserve resources/initiative. |
| 4. Three spell adapters and selection | Register Animals/Fey/Fiend and DismissSummon. Connect cold canonical form/slot rows, pure subjective discovery, objective admission, optional typed SpellEvent data, exact sustain links and native creation. Uses packets 1–3. | Every allowed creature/spell/slot boundary works; forged choices fail; costs, cancellation, concentration replacement and former Fey controller rejection follow this plan. |
| 5. Recorded presentation and existing art | Implement the bounded alternate-rig binding design in section 10.2.1, then finish finite codec/shared reduction, all 24 rig bindings and retained Fey material. Add backend fact fields/reducers alongside their producing packets when needed; this packet completes end-to-end archive/client parity. No new summon VFX. | All base rigs and secondary attacks validate; live/history/reacquisition show the same actor state; true departure removes the actor; no renderer queries native mechanics. |
| 6. Complete fighting and independent acceptance | Run the full matrix below, representative native fights, all required suites and independent final implementation reviews. Resolve scoped findings and re-review final code. | All 24 ordinary/summoned units, all three spells, lifecycle/events/items/AI and binding coverage accounted for with recorded evidence; no unresolved scoped blockers. |

Read HOW_TO_TEST.MD. Use native composition/casts/indexed actions and observable
state/events, with small reusable checks rather than fake mechanics or private
call-order tests. Architecture evidence is separate from gameplay. Native lifecycle tests remain
independent of rendering. One acceptance ledger covers all 24 rows: canonical
construction, allowed forms/slot boundaries, real attacks/AI, complete rig/action
bindings and lifecycle coverage. Shared lifecycle permutations can use representative
bodies; this must not silently omit constructing, attacking with or validating
another row. No new summoning-effect artwork is required. Explicit presentation-only scale
values for large beast artwork may be calibrated through the existing Appearance
component; native size and one-anchor placement stay unchanged. Check the enlarged
original pixels in native movement/attack recordings, reducing scale if quality suffers.

| Area | Required public cases |
| --- | --- |
| Independent content | Same recipe ordinary/summoned; ordinary death/items unchanged; instance-only Fey adaptation |
| Selection | Every admitted form, low/high slot, wrong family/forged ID, same native placement for ordinary/summoned Large creature, wall/edge/ground and changed execution geometry |
| Admission | Pure subjective discovery including unseen occupant, objective attempt failure without identity leak, missing/duplicate binding, free pre-cost rejection vs paid interruption, incoming veto preserves old effect, exactly one prepared birth after valid commit, no orphan completed condition, committed publication error |
| Dependencies | Concentrating -> Summoned; direct Summoned without concentration; Fey concentration -> control with independent existence |
| Fey loss | Damage break, voluntary drop, source death, replacement; same UUID/HP/gear/AI/remaining duration; former allies legal targets; unchanged budget; failed-save/death veto cannot retain required control or an animal/fiend body, while voluntary rejection preserves authority |
| Dismissal | Controlled Fey accepted, released Fey rejected including forged/stale requests; terminal child removal produces no hostility blip |
| Clock | Birth skip, next tick, exact expiry, duplicate interval, encounter pause/rebind, caster death does not freeze surviving Fey |
| AI/turns | Player/enemy caster, own senses, insertion/removal before/current/after, reaction departure, faction change during movement, uncontrolled rejoin without former source |
| Resources | Haste/Slow/Extra Attack/Action Surge and ordinary action/bonus/reaction unchanged; list shifts/control change do not reset epochs; section 2.4 body-attack choices cost ordinary actions with full modifiers, no accidental off-hand bonus entitlement, held-weapon behavior preserved |
| Items | Unlootable anatomy, intact real coated gear/bag drop, no duplicate floor item, unsupported equipped summon rejected, mandatory veto vs voluntary no-op |
| Facts | One birth/departure, causal faction change, passive archive, hidden observer/reacquisition, retained spirit material before/after hostility, no mechanics during replay |
| Bindings | All 24 exact variants; primary/secondary/miss/critical/OA/Multiattack profiles; every reachable body-action/movement/condition context; unique selectors, reachable anchors, eight facings, pivots, shadows, Fey material and modular regressions; unresolved source mapping is an incomplete row |
| Native combat presentation | Recorded encounters cover distinct body families, large creatures and Fey appearance/shadows using native movement/attacks; all 24 rigs and primary/secondary action mappings are validated |
| Cleanup | Simultaneous causes, nested concentration replacement/removal, settled-boundary retirement without per-child reentry, publication failure, close twice/reset/rebind; no retained live actor/item/controller/handler authority |

### 11.1 Suites and final implementation review

After implementation run focused native cases, full engine/AI suite, architecture/
import-DAG checks, active dnd/game typing and full game suite for shared event
compatibility. Record commands/environment/revision and all failures. Do not
weaken tests or expand unrelated production fixes without user discussion.
No tests run for this planning revision.

## 12. Independent review and implementation gate

Three independent reviews of the same exact SHA256 of this single plan:

1. Anti-slop: reuse, no duplicate state/lifecycle, bounded rules and creature independence.
2. ECS/anti-OOP/import-DAG/AI: actual components, imports, owner APIs, admission,
   initiative, duration/control transitions and teardown.
3. Events/items: spending/publication boundaries, passive/subjective state and
   exact real-item/actor cleanup without duplicate event ownership.

Preserve findings/re-reviews in agent_docs/audits/SUMMONING_PLAN_*_REVIEW_2026-10-03.md
and update the separate receipt. Resolve blockers, then re-review new bytes.
The previous two-document receipt is historical. The creature-batch document is
now a superseded pointer, not a second set of implementation requirements.
Reviewers must check this single document for end-to-end completeness, dependency
order and consistency of content, lifecycle, events and presentation scope.
Plan review is not implementation acceptance. Human approval of concrete scope/
defaults precedes code changes, followed by independent implementation review.
Only plan/review documents change in this task.
