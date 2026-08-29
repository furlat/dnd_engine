# Native event causality full-cleanup implementation ledger

Date: 2026-08-28
Repository: /mnt/c/users/tommaso/documents/dev/dnd_engine
Scope: Cut 0 read-only preflight only

## Checkpoint status

CUT_0_PREFLIGHT_COMPLETE — READY_FOR_COORDINATOR_REVIEW

No production or test file was edited. This ledger is the only file created by
this checkpoint. The accepted native-causality plan is the sole implementation
authority; the earlier tree-commit plan is retained only as superseded design
history.

## 1. Authority and instruction verification

Raw bytes were verified with sha256sum before this ledger was written.

| Artifact | SHA-256 | Status |
| --- | --- | --- |
| DND_EVENT_NATIVE_CAUSAL_RESOLUTION_CLEANUP_PLAN_2026-08-28.md | cda9dfce80ce36e5d3a1fbeb0b06c351086c4d34535fe99ebb55e937a2e0b9e6 | exact accepted Cut 0 authority |
| DND_EVENT_TREE_COMMIT_FULL_DESLOP_PLAN_2026-08-28.md | 25352211b8ec2187e6ae3cba54d6a7d57d6b7a23a6c5b43d6e6e04ab87a427c6 | superseded history only; not followed |
| DND_EVENT_KNOWLEDGE_CONTEXT_E3_E6_IMPLEMENTATION_PLAN_2026-08-27.md | aaf75e26e3b1e13419caf3d0b7e8346ad8a86531bc155b90f6d37767a8328c98 | preserved prior authority |
| DND_EVENT_KNOWLEDGE_CONTEXT_REDUCTION_PLAN_2026-08-27.md | 7856a537f0b75063fe5bcb012fd7d020b2f92a1e018c17d1ccf6b5e830605c21 | preserved E1/E2 reduction authority |
| DND_EVENT_KNOWLEDGE_CONTEXT_IMPLEMENTATION_PLAN_2026-08-27.md | 3f98f0b926fce8e9662c5718c01aa863734a563897bebe0b403173d8eba0a9ad | preserved E1/E2 implementation authority |
| DND_PYGAME_SCRIPTED_ENCOUNTER_MVP_IMPLEMENTATION_PLAN_2026-08-27.md | 8e83dde4916ca3a6a4691bd9b25f720d3e381fe49e6458d4c0800007f9b390b9 | preserved broader authority; no pygame work |
| DND_EVENT_KNOWLEDGE_CONTEXT_E3_E6_IMPLEMENTATION_MANIFEST_2026-08-27.json | fd9bd2055f67b48b2861ff1fe94d665e98a3d78341990d0e257af4ebbba13772 | preserved prior active-only artifact; not changed |
| agents.md | fcc5dd1e15bae2ff86a7203f42b0c55de4d51dd0d93bc3a3ae059b7e58ee39b1 | read completely |
| HOW_TO_TEST.MD | 96ba573eb50504f9e2c9c8676acc2f352ae198466d79f46e75c57d3f29995013 | read completely; 517 lines |

The native plan contains no additional literal E1/E2 hash table. The companion
E1/E2/E3 authority hashes above were reverified for the preserved prior track.
No plan, rejected-plan, production, or test bytes were altered.

## 2. Dirty checkout frozen before this ledger

Exact git status --short --untracked-files=all before this ledger:

 M dnd/blocks/sensory.py
?? DND_EVENT_KNOWLEDGE_CONTEXT_E3_E6_DESLOP_REPAIR_PLAN_2026-08-28.md
?? DND_EVENT_KNOWLEDGE_CONTEXT_E3_E6_IMPLEMENTATION_LEDGER_2026-08-27.md
?? DND_EVENT_KNOWLEDGE_CONTEXT_E3_E6_IMPLEMENTATION_MANIFEST_2026-08-27.json
?? DND_EVENT_KNOWLEDGE_CONTEXT_E3_E6_IMPLEMENTATION_PLAN_2026-08-27.md
?? DND_EVENT_KNOWLEDGE_CONTEXT_IMPLEMENTATION_PLAN_2026-08-27.md
?? DND_EVENT_KNOWLEDGE_CONTEXT_REDUCTION_PLAN_2026-08-27.md
?? DND_EVENT_NATIVE_CAUSAL_RESOLUTION_CLEANUP_PLAN_2026-08-28.md
?? DND_EVENT_REDUCTION_FIRST_PRINCIPLES_STUDY_2026-08-27.md
?? DND_EVENT_TREE_COMMIT_FULL_DESLOP_PLAN_2026-08-28.md
?? DND_PYGAME_FIRST_PRINCIPLES_CLIENT_STUDY_2026-08-27.md
?? DND_PYGAME_SCRIPTED_ENCOUNTER_MVP_IMPLEMENTATION_PLAN_2026-08-27.md
?? dnd/core/events/knowledge.py
?? dnd/event_reduction.py
?? tests/architecture/test_event_knowledge_context_architecture.py
?? tests/engine/test_event_knowledge_async_boundary.py
?? tests/engine/test_event_knowledge_context.py
?? tests/engine/test_event_knowledge_scripted_encounter.py

Pre-existing active dirty production/test raw hashes:

75d508f52156bd6d1ce73b0d5eafe25eee804cd4b3e1056b943c365435bec8ee dnd/blocks/sensory.py
f9347cdeb21591b051014b06a90d4d5604904abdfe1c0d40d4d55d2c7d433026 dnd/core/events/knowledge.py
44450644478c90141789f53e31ecac70c78f84f2396cf2c5d3c842614f5859c7 dnd/event_reduction.py
d4a3e8d1feec813c5497ff025377986c99997799efddd2101dbf51c87012d273 tests/engine/test_event_knowledge_context.py
a33e6b831f9388d669a748707d8a087a6c8bfb9601e42593f5193b184fcf0644 tests/engine/test_event_knowledge_scripted_encounter.py
1d014da295dc4a812725a903cef996207e595439b37d892c9b9c3ffaa73d0f4e tests/engine/test_event_knowledge_async_boundary.py
5ffbe13efbf6d02c7cd98a953891b0f31cc676f5e766d7ceb06848f9e120308f tests/architecture/test_event_knowledge_context_architecture.py

## 3. Current baseline and collection identity

The exact current governed baseline command was:

.venv/bin/python -m pytest -q -p no:cacheprovider tests/engine/test_event_knowledge_async_boundary.py tests/engine/test_event_knowledge_context.py tests/engine/test_event_knowledge_scripted_encounter.py tests/engine/test_objective_state.py tests/engine/test_direct_scenario_deployment.py tests/engine/test_event_wire_visibility_contract.py tests/engine/test_move_settlement.py tests/engine/test_senses_light_stealth.py tests/engine/test_combat_actions.py tests/engine/test_action_cost_and_position_commit.py tests/architecture

Collection used pytest --collect-only -q -p no:cacheprovider, retained only
lines matching ^tests/.*::, C-bytewise sorted and deduplicated, with one terminal
LF before hashing. It produced 309 unique node IDs with normalized SHA-256
f9a548aac09faf728ba330c1f7a12c2b4142eae851c5919a48aae54347409d80.

The command was executed unchanged on current bytes: 308 passed, 1 failed in
177.97s. The first failing selector was:

tests/engine/test_event_knowledge_scripted_encounter.py::test_full_public_encounter_replays_and_consumes_detached_batches_deterministically

The unchanged callback candidate reported RuntimeError('sensory disclosure did
not resolve exactly one causative terminal') and non-contiguous callback
batches such as [9, 10) after cursor 5. This is baseline evidence and was not
repaired in Cut 0. The historical accepted E1/E2 baseline remains 264 nodes,
normalized SHA 13043bdba75fae26de00295ea681e809be2524b83252c683217ba972839269b0,
with 264 passed in 136.74s from its prior exact command.

git diff --check before this write: exit 0, with only the pre-existing LF/CRLF
normalization warning for dnd/blocks/sensory.py.

## 4. Active production callback and observer inventory

AST scope: all 205 Python files under dnd, excluding __pycache__ and inactive
stop-only dnd/items/environment_content.py. No excluded server/deprecated
server/SDK/transport/generated/renderer/editor/cross-language/pygame scope was
entered.

### 4.1 Passive event, sequence, batch, handler-dispatch, and pre-completion APIs

| API | Definition | Active production users |
| --- | --- | --- |
| add_on_event_callback | dnd/core/events/events_registry.py:1316 | dnd/core/gridmap.py:184 GridMap.__init__; dnd/core/gridmap.py:4555 GridMap._ensure_blocking_callback |
| remove_on_event_callback | dnd/core/events/events_registry.py:1583 | none |
| add_on_event_sequence_callback | dnd/core/events/events_registry.py:1590 | none |
| remove_on_event_sequence_callback | dnd/core/events/events_registry.py:1612 | none |
| add_on_event_batch_callback | dnd/core/events/events_registry.py:1648 | none in production; current tests use the existing boundary |
| remove_on_event_batch_callback | dnd/core/events/events_registry.py:1666 | none |
| batch_on_event_callbacks | dnd/core/events/events_registry.py:1685 | dnd/core/base_actions.py:1518 BaseAction.apply; dnd/encounters/encounter.py:991 Encounter.advance_one_controller_action_boundary |
| add_on_handler_dispatch_callback | dnd/core/events/events_registry.py:1342 | none |
| remove_on_handler_dispatch_callback | dnd/core/events/events_registry.py:1358 | none |
| add_pre_completion_callback | dnd/core/events/events_registry.py:1755 | dnd/actions/operations.py:720 execute_use_action; dnd/core/gridmap.py:4503 GridMap._ensure_light_pre_completion_callback |
| add_pre_completion_system | dnd/core/events/events_registry.py:1766 | dnd/blocks/sensory.py:780 SpatialSensesSystem.attach |
| remove_pre_completion_system | dnd/core/events/events_registry.py:1785 | dnd/core/events/events_registry.py:1779 as part of add_pre_completion_system |
| run_pre_completion_callbacks | dnd/core/events/events_registry.py:1796 | dnd/core/events/events_registry.py:430 Event._completion_updates |
| register_completion_sequence | dnd/core/events/events_registry.py:2090 | dnd/blocks/sensory.py:1339 SpatialSensesSystem.__call__ |

There are 120 EventHandler constructor call sites across 21 active production
files. These are gameplay handler creation/ownership, not passive event
observers. The separate passive handler-dispatch observer API has zero active
production users.

### 4.2 Combat-log listeners and callbacks

- _combat_log_listeners: dnd/encounters/encounter.py:171.
- Encounter.add_combat_log_listener definition: dnd/encounters/encounter.py:235;
  no active production caller.
- Encounter.remove_combat_log_listener definition: dnd/encounters/encounter.py:244;
  no active production caller.
- EventQueue.set_combat_log_callback definition: dnd/core/events/events_registry.py:1247;
  users dnd/encounters/encounter.py:384, :424 and dnd/runtime_reset.py:46.
- EventQueue.push_combat_log definition: dnd/core/events/events_registry.py:1294;
  user dnd/entities/entity.py:1161 Entity.add_condition.
- Encounter combat-log fan-out: dnd/encounters/encounter.py:751.

### 4.3 Terminal-phase handler inventory

One active terminal-phase handler construction was found:
dnd/classes/sorcerer.py:721 MetamagicActive._apply EventPhase.CANCEL.
No active EventHandler construction with EventPhase.COMPLETION was found. The
same handler also has an EFFECT trigger.

## 5. Completed-fact and root-producer inventory

### 5.1 Explicit completed-fact producers

Five EventQueue.publish_completed_fact call sites:

- dnd/content/scenarios/battlefield_builders.py:892 build_battlefield
- dnd/entities/entity_creation.py:443 compose_entity
- dnd/entities/entity_progression.py:341 apply_level
- dnd/entities/entity_progression.py:369 remove_last_level
- dnd/spatial/area_conditions.py:1046 SpatialCondition._publish_change

### 5.2 Root/lifecycle publication call sites

The current publication definitions are Event.phase_to at
dnd/core/events/events_registry.py:379, Event.cancel at :522, Event.post at
:632, EventQueue.register at :1825, EventQueue.publish_declaration at :1916,
EventQueue.publish_lifecycle at :1943, EventQueue.publish_preflighted at
:2045, and EventQueue.publish_completed_fact at :2070. The source call sites
below are the complete active production callers found by the same AST scan.

29 EventQueue.publish_declaration calls:

- dnd/actions/standard.py:3494 TraverseConnector._apply
- dnd/actions/standard.py:4137 Jump._apply
- dnd/actions/standard.py:4629 Shove._apply
- dnd/blocks/base_item.py:432 BaseItem.receive_damage
- dnd/content/spike_trap_materialization.py:33 _begin_environment_effect_event
- dnd/core/base_actions.py:1543 BaseAction._apply_action
- dnd/core/base_block.py:891 BaseBlock._promote_most_potent_lease
- dnd/core/base_block.py:994 BaseBlock._apply_condition_with_policy
- dnd/core/base_conditions.py:861 BaseCondition.apply
- dnd/core/base_conditions.py:1092 BaseCondition.cleanup_own_state
- dnd/core/gridmap.py:666 GridMap.set_tile_elevation
- dnd/core/gridmap.py:961 GridMap._publish_connector_change
- dnd/entities/entity.py:1133 Entity.add_condition
- dnd/entities/entity.py:1569 Entity._fire_death_event
- dnd/entities/entity.py:1666 Entity.make_death_save
- dnd/entities/entity.py:1759 Entity.revive
- dnd/entities/entity.py:1806 Entity.on_turn_start
- dnd/entities/entity.py:1894 Entity.on_turn_end
- dnd/entities/entity.py:2758 Entity.receive_damage
- dnd/entities/entity.py:2878 Entity.receive_instant_death
- dnd/entities/entity.py:2939 Entity.receive_healing
- dnd/entities/entity.py:2999 Entity.grant_temporary_hit_points
- dnd/spatial/area_conditions.py:1071 SpatialCondition.publish_revealed
- dnd/spells/abjuration.py:906 _begin_counterspell_reaction
- dnd/spells/evocation.py:1347 Thunderwave._apply
- dnd/spells/evocation.py:2658 _apply_gust_push
- dnd/spells/infernal.py:191 _rebuke_processor
- dnd/spells/necromancy.py:1236 EyebitePanickedEffect._move_along_flee_path
- dnd/spells/transmutation.py:1678 TelekinesisMove._apply

Six EventQueue.publish_lifecycle calls:

- dnd/core/base_block.py:378 BaseBlock._notify_perceivability_changed
- dnd/core/gridmap.py:214 GridMap._fire_spatial_event
- dnd/items/torches.py:357 Torch.ignite
- dnd/items/torches.py:706 WallTorch.light
- dnd/spells/conjuration.py:3510 SleetStormZone._emit_dousing_interaction
- dnd/spells/evocation.py:2572 GustOfWindZone._emit_wind_exposure

Four EventQueue.publish_preflighted calls:

- dnd/actions/standard.py:3971 Jump._publish_jump_effect_stop
- dnd/blocks/equipment.py:1543 and :1544 Equipment._publish_prepared_transition
- dnd/core/gridmap.py:224 GridMap._fire_committed_spatial_event

Four direct EventQueue.register sites:

- dnd/blocks/sensory.py:734 emit_sensory_update_delta
- dnd/core/base_actions.py:1590 BaseAction._apply_action
- dnd/core/events/events_registry.py:369 Event.model_post_init
- dnd/core/events/events_registry.py:657 Event.post

These are current source publication sites, not a claim that every publication
is a valid independent root. Root ownership is measured below.

## 6. Action-cost and concentration inventory

### 6.1 Action-cost overrides

The base implementation and four active overrides are:

- dnd/core/base_actions.py:1436 BaseAction._apply_costs
- dnd/actions/standard.py:1759 Move._apply_costs
- dnd/actions/standard.py:3596 TraverseConnector._apply_costs
- dnd/actions/standard.py:4293 Jump._apply_costs
- dnd/spells/abjuration.py:2229 FreedomOfMovementEscape._apply_costs

### 6.2 All 43 active concentration call sites

The AST count is 43 across exactly eight spell files:

| File | Count | Lines |
| --- | ---: | --- |
| dnd/spells/abjuration.py | 8 | 711, 831, 1354, 1577, 2516, 2621, 3065, 3509 |
| dnd/spells/conjuration.py | 12 | 357, 1241, 1406, 1669, 1968, 2323, 2453, 2585, 2961, 3198, 3389, 3710 |
| dnd/spells/divination.py | 1 | 354 |
| dnd/spells/enchantment.py | 4 | 397, 612, 1342, 1439 |
| dnd/spells/evocation.py | 2 | 2770, 3065 |
| dnd/spells/illusion.py | 6 | 169, 399, 616, 878, 951, 1426 |
| dnd/spells/necromancy.py | 3 | 853, 1551, 2336 |
| dnd/spells/transmutation.py | 7 | 262, 685, 904, 1251, 1343, 1491, 1858 |

Five named multi-entity cases:

- BeaconOfHope dnd/spells/abjuration.py:3025; ensure at :3065
- HoldMonster dnd/spells/enchantment.py:528; ensure at :612
- Bane dnd/spells/enchantment.py:1280; ensure at :1342
- Bless dnd/spells/enchantment.py:1382; ensure at :1439
- NecroticBless dnd/spells/necromancy.py:768; ensure at :853

## 7. Active _validate inventory for detached-validation split

The AST inventory found 159 active _validate definitions:

- dnd/actions/standard.py (13): Move@1052, Attack@2594, DropConcentration@2805, ShakeAwake@2877, Hide@2944, StandUp@3052, DropProne@3088, TraverseConnector@3335, Jump@3812, Shove@4505, PickUp@5886, AttackObject@5953, Drop@6041
- dnd/classes/barbarian.py (3): RecklessAttack@230, IntimidatingPresence@703, ExtendIntimidatingPresence@824
- dnd/classes/fighter.py (3): SecondWind@428, ActionSurge@570, ExtraAttack@839
- dnd/classes/rage.py (4): Rage@449, EndRage@522, FrenziedStrike@685, Frenzy@773
- dnd/classes/sorcerer.py (8): ElementalAffinityResistanceAction@195, DragonWings@330, DraconicPresence@577, QuickenedSpell@800, TwinnedSpell@848, DistantSpell@896, ConvertSlotToSP@970, ConvertSPToSlot@1034
- dnd/core/base_actions.py (1): BaseAction@1329
- dnd/extensions/aegis_spark.py (1): AegisSpark@92
- dnd/extensions/field_focus.py (1): DeployFieldFocus@173
- dnd/items/consumables.py (4): _DrinkHealingPotionAction@335, _ApplyWeaponCoatAction@688, _DrinkGreaterInvisibilityPotionAction@1065, _DrinkHastePotionAction@1221
- dnd/items/environment.py (2): OpenDirectionalDoorAction@160, CloseDirectionalDoorAction@211
- dnd/items/environment_interactables.py (5): PullLeverAction@56, LootAllAction@118, RestAction@190, CookAction@220, ActivateDeviceAction@262
- dnd/items/spell_items.py (1): _AcidFlaskSpell@269
- dnd/items/torches.py (4): IgniteTorchAction@146, ExtinguishTorchAction@220, IgniteWallTorchAction@505, ExtinguishWallTorchAction@567
- dnd/monsters/skeleton_abilities.py (1): MarkTargetAction@211
- dnd/monsters/traits.py (2): MultiattackAction@600, NaturalAttack@690
- dnd/origins/dragonborn.py (1): DragonbornBreathWeapon@155
- dnd/spatial/restraints.py (1): EscapeSpatialRestraintAction@93
- dnd/spells/abjuration.py (13): MageArmor@566, ProtectionFromEnergy@690, Stoneskin@816, GlobeOfInvulnerability@1322, Banishment@1534, LesserRestoration@1650, GreaterRestoration@1707, RemoveCurse@1782, ProtectionFromPoison@1929, DeathWard@2070, FreedomOfMovementEscape@2179, FreedomOfMovement@2356, AntimagicField@3483
- dnd/spells/conjuration.py (22): CallLightningStrike@179, CallLightning@289, PoisonSpray@397, AcidSplash@497, MistyStep@628, Grease@864, Web@1199, Entangle@1368, EvardsBlackTentacles@1629, Cloudkill@1925, SpiritGuardians@2284, FogCloud@2416, Darkness@2551, Daylight@2718, InsectPlague@2922, IncendiaryCloud@3160, StinkingCloud@3352, SleetStorm@3675, DimensionDoor@3748, GuardianOfFaith@3904, EatFromFeast@4079, HeroesFeast@4183
- dnd/spells/divination.py (1): TrueSeeing@181
- dnd/spells/enchantment.py (8): CharmPerson@112, HoldPerson@375, HoldMonster@589, PowerWordKill@664, TestBless@740, Sleep@961, PowerWordStun@1100, Command@1787
- dnd/spells/evocation.py (31): FireBolt@145, RayOfFrost@300, SacredFlame@402, MagicMissile@548, ScorchingRay@657, Fireball@795, BurningHands@930, LightningBolt@1055, Thunderwave@1248, Shatter@1429, CircleOfDeath@1540, ConeOfCold@1649, Sunburst@1852, ShockingGrasp@2014, GuidingBolt@2279, EldritchBlast@2391, GustOfWind@2703, IceStorm@2821, SunbeamStrike@2960, ChainLightning@3111, PrismaticSpray@3303, TrueStrike@3454, FlameStrike@3569, ContinualFlame@3909, CureWounds@4021, HealingWord@4079, PrayerOfHealing@4135, MassHealingWord@4202, MassCureWounds@4278, HealSpell@4333, MassHeal@4396
- dnd/spells/illusion.py (8): Blur@147, Fear@350, HypnoticPattern@569, ColorSpray@770, Invisibility@852, GreaterInvisibility@925, MirrorImage@1122, Silence@1370
- dnd/spells/necromancy.py (8): FalseLife@103, ChillTouch@306, Blight@440, BlindnessDeafness@706, EyebiteStrike@1411, FingerOfDeath@1627, InflictWounds@1725, BestowCurse@2320
- dnd/spells/transmutation.py (13): SpikeGrowth@223, Slow@635, Haste@878, DarkvisionSpell@967, Disintegrate@1029, JumpSpell@1142, EnhanceAbility@1332, EnlargeReduce@1466, TelekinesisRestrain@1540, TelekinesisMove@1628, TelekinesisGrab@1746, Telekinesis@1837, Regenerate@1965

For all 159 rows, direct self-attribute assignment was 0, EventQueue
publish/register/post calls were 0, and domain-state mutation calls were 0.
The observed phase_to/cancel calls only construct returned event proposals;
they do not emit events. One local append only builds a local validation result.
No active validator currently violates the proposed validation-only split.

## 8. Read-only proving-encounter graph measurement

The measurement used the existing public fixture and public operations:
build_battlefield("battlefield.open_floor_bright"), Game.deploy_entity,
Encounter.add_combatant, Encounter.roll_initiative, Encounter.start_encounter,
Encounter.advance_one_controller_action_boundary, Encounter.execute_action,
Encounter.complete_current_turn, and Encounter.end_encounter. Roles were
hero_frontline, hero_caster, enemy_guard, and enemy_raider. The read-only
driver captured EventQueue.get_events_chronological() after the public
encounter and checked parent UUIDs, parent lineages, roots, and terminals. It
did not monkeypatch a production file or alter mechanics.

Measured results:

source_events = 244
natural_root_identities = 30
root_terminal_identities = 30
parentless_event_versions = 96
missing_parent = 0
parent_cycle = 0
completion-child parent-lineage mismatches = 0
second_root_interleavings = 2
late_child = 0
terminal_order_violations = 0

The two second-root interleavings begin at source indices 121 and 193. The
defect consists of three parentless ConditionRemovalEvent lineages, exactly 12
phase versions:

- 121..125: declaration, execution, effect, completion
- 125..129: declaration, execution, effect, completion
- 193..197: declaration, execution, effect, completion

The first two occur during the TurnStart boundary 119..131; the third occurs
during TurnStart boundary 191..199. Carrying the active TurnStart event through
duration/removal ownership is the exact later repair evidence. The current
natural count is 30; nesting these three removal roots yields the plan target
of 27 causal roots.

The current schema leaves parent_lineage absent on 92 non-completion child
versions. The completion-only parent-lineage check is zero-mismatch and is the
existing public contract; this observation is recorded separately, not
misclassified as a missing-parent defect.

Known ownership defects required by the plan:

- WorldInitializedEvent: source [0,1), one parentless COMPLETION only; no
  declaration/execution/effect lifecycle or authored child ownership.
- RoundEndEvent: source [241,242), one parentless COMPLETION only; no
  declaration/execution/effect lifecycle or environment child ownership.

No missing-parent, late-child, or terminal-order violation was found in this
current stream. The baseline callback proof failure remains in Section 3.

## 9. Frozen scope and proposed Cut 1 envelope

### 9.1 Full future causal-cleanup production envelope from the accepted plan

The complete plan envelope is:

dnd/core/events/events_registry.py
dnd/core/events/ concrete event modules gaining native resolution/inert-fact behavior
dnd/core/base_actions.py
dnd/actions/operations.py
dnd/blocks/base_item.py
dnd/actions/standard.py
dnd/spells/{abjuration,conjuration,divination,enchantment,evocation,illusion,necromancy,transmutation}.py
dnd/classes/sorcerer.py
dnd/core/gridmap.py
dnd/blocks/sensory.py
dnd/spatial/area_conditions.py
dnd/entities/entity.py plus exact block/item duration owners reached by TurnStart
dnd/encounters/encounter.py
dnd/content/scenarios/battlefield_builders.py solely for WorldInitialized parentage
dnd/runtime_reset.py
dnd/event_reduction.py
focused active tests and architecture gates

This is a future-cut envelope, not authorization to edit all paths in Cut 0.

### 9.2 Proposed bounded Cut 1 envelope

Cut 1 is the queue/tree kernel and pull boundary only. Proposed production:
dnd/core/events/events_registry.py for root/descendant/terminal admission,
journal-derived extraction, and removal of deleted observer/batch state;
dnd/event_reduction.py for the pull entry only if required by the planned
reducer boundary; and dnd/runtime_reset.py for reset/generation cleanup only if
the deleted queue state requires it.

Proposed tests are the existing tests/engine/test_event_lifecycle.py for queue
laws, the existing event-knowledge/reducer test surface only for the pull cursor
contract, and tests/architecture/test_dependency_boundaries.py plus one
narrow existing architecture gate for hard-cut ownership. Exact selectors must
be declared and coordinator-approved before Cut 1 edits. No new test helper
framework or production module is proposed.

The direct fixture roles/public commands frozen for later end-to-end proof are
the four roles and public operation sequence in Section 8. No action controller,
event callback, listener, receipt, transaction, or synthetic batch is proposed.

### 9.3 Exclusions and stop conditions

Excluded and not to be ported for compatibility:

server/, deprecated server/, SDK, transport, generated code, renderer, pygame,
editor, save/persistence/networking, cross-language code, game/, map authoring,
general content recovery, inactive dnd/items/environment_content.py, and Phase 7.

If Cut 1 exposes a required active owner outside the approved envelope, a rule
that must outlive its root, or a need for a new callback/contributor/listener/
registry/manager/service/transaction/wrapper/receipt/async path, stop for
coordinator guidance. Do not weaken a gate or add compatibility.

## 10. File-change confirmation

Post-measurement status remains the Section 2 status plus this ledger. No dnd/
production byte and no tests/ byte changed during Cut 0. The only authorized
write was this append-only implementation ledger. Its SHA is reported
externally after the final newline and is intentionally not embedded in itself.

READY_FOR_COORDINATOR_REVIEW

### Superseding Cut 2 causal-correctness repair checkpoint — 2026-08-28

This checkpoint supersedes the rejected Cut 2 candidate recorded at ledger SHA
6a869c820dcc27d80689bc291b29a7864c5ade0d30f3d02baebe93f49291d5a4. The
governing amended plan remains
DND_EVENT_NATIVE_CAUSAL_RESOLUTION_CLEANUP_PLAN_2026-08-28.md, SHA-256
a739521673ecdfed95c237f28f8c5fbcf5d6e8aede4a5f56a926225b265fdc81.

The bounded repair preserves Cut 1 causal/publication invariants. Every active
root path checks cancellation immediately after EFFECT entry; metamagic removal
is direct SpellAction execution-commit work; Counterspell is parented to the
interrupted spell; finite item charge payment fails closed before execution
effects; concentration close is direct and ordered before root completion; and
the five named multi-target concentration cases have public journal-order
proofs. The stale tests/manual/test_legacy_reactive_reaction_coverage.py Cut 1
callback test was restored to its pre-Cut 2 bytes and is excluded from the
active Cut 2 path set.

#### Exact validation

The first reconstructed command stopped before collection because it named the
nonexistent tests/engine/test_spatial_effect_idempotency.py. This was a
command-list error, not a test failure. The corrected complete affected lane
used the existing tests/engine/test_spatial_effect_reveal_idempotency.py path
and returned 606 passed in 205.67s (0:03:25).

Focused causal proofs returned 12 passed in 6.59s, covering Guidance EFFECT
cancellation, multi/AOE cancellation, parented Counterspell, the two
concentration-order proofs, the five named concentration cases, and finite-item
declaration-removal failure. The complete test_spell_families.py lane returned
64 passed in 62.54s.

The runnable Counterspell contract selection returned 10 passed, 11 deselected
in 6.55s. The exact test_counterspell_evidence.py attempt stopped at collection
with ModuleNotFoundError: No module named dnd.core.content.runtime; this is the
known excluded missing-content dependency and no excluded file was changed.

The complete tests/architecture lane returned 59 passed in 28.66s. Compileall
over every retained Cut 2 active Python path exited 0. git diff --check exited
0 with only the repository's existing LF-to-CRLF normalization warnings. The
production hard-cut scan found no retired pre-completion, late-cost,
metamagic-auto-remove, or concentration-cleanup references, no production
register_completion_sequence or generic pre-completion registration, and no
terminal-phase Trigger declarations. The eight governed spell files contain
exactly 8 + 12 + 1 + 4 + 2 + 6 + 3 + 7 = 43 ensure_concentration( call sites.
The restored excluded legacy test has no diff.

#### Retained Cut 2 path hashes

These are the current raw-byte SHA-256 values for the retained Cut 2 path set.
Other dirty paths in the checkout are accepted prior-cut or unrelated work and
were not modified by this Cut 2 repair.

dnd/actions/operations.py 168296bd8e653c895ddf7580a9ecc9a6333d6aff658891fe48be362795d03d0d
dnd/actions/standard.py a1418416e25174909b62cf5f8f5a38e86a0f0b40e5eac0c68bc5aa1df8918080
dnd/blocks/base_item.py 617c9e19d50624a1ecac15777e00a0dbc924fe67b787f387fa35e4afe9a708d8
dnd/classes/sorcerer.py 8794c6f03b275db4f2bab9df7b45d27f389ea35b8d8236fe91e62f5652a471e9
dnd/core/base_actions.py 03098e0ce18eacf0c76c8bc881c15c055e1a71c90dbcaf4aa1f51ab8610f3d94
dnd/core/events/events_registry.py c30c44dc1ecb5c5606ea8892348f508a1afec27ec0151a9e7383869fe6fa6e6b
dnd/spells/abjuration.py 3636b5e5630b3d174e048cf2d43c6e97eee9ab183492b5c7967eb94052cf66cf
dnd/spells/conjuration.py 861a793cae6e4f7e8f1becc98e89cef99cb58878687d87ada7fbaf8bbc3149b9
dnd/spells/divination.py eff1536194d01a63b49038df5d255b8353c1ba750ebcec4f62b10461965dcfaa
dnd/spells/enchantment.py b1f6aba773c1082e6e196f57d34d960515b993260f17eedb60da49e8e127201f
dnd/spells/evocation.py 958c3a2a53ec15420bcff6674b5753f562a08690a820bb7a44052ccf65f362d6
dnd/spells/illusion.py ec9a29d0a5ab6a09a1b842e9e10a400cfaa71e4f54d6ec7cbc9da432cacd66c2
dnd/spells/necromancy.py e054caf1d7b2bd82fcac67b523c42422156caf01ebd4feda285647c1dcf11618
dnd/spells/transmutation.py ad0fa7833f8112ef10e5ffc6cea8c3ee20763fe57b42411cd8b1e95695400672
tests/architecture/test_dependency_boundaries.py 4386ff6090afc8b0c5f36a0ef98db96a274402b572147527a415aab6a89f001c
tests/engine/test_event_lifecycle.py 3552a33d7a6f2aa7daad6292ad060672a03dbac82881f771646503500bd662e8
tests/engine/test_items_inventory_equipment.py cc0da76bffb44e1dfc1fa9bd10873460176db49aadedf83f22fa488fd5bd9055
tests/engine/test_spell_families.py 3666d8a78b4d50a26eb3be432efc7d17dde10911e81d64c5736c4ee96e357c6f
tests/manual/test_50_counterspell_engine_contract.py 57c403f5f5d69d4df72bd575fd859faecf50c70a9e078495772fc792839541cb

The excluded restored tests/manual/test_legacy_reactive_reaction_coverage.py has
current SHA cbe94db49b2b3a6dc034b87af1e098698eaa311b2c4d76a9a4b339b65a197569,
and its scoped diff is empty. No manifest was created or modified. Cut 3+
remains unauthorized.

READY_FOR_COORDINATOR_REVIEW

## Coordinator review and dependency-order amendment

Cut 0 is accepted. The 309-node collection identity was independently
reproduced at normalized SHA-256
`f9a548aac09faf728ba330c1f7a12c2b4142eae851c5919a48aae54347409d80`,
and the checkpoint changed no production or test bytes.

The inventory exposed a sequencing contradiction in the original accepted
cut order: active GridMap, item-charge, indexed sensory, terminal-metamagic,
and known TurnStart root owners could not be hard-cut before their assigned
mechanic migrations. The plan's final architecture was not changed. Cuts 1-4
were dependency-reordered so each legacy mechanism is deleted in the same cut
as its final owner migration and strict root admission lands only after the
known roots are causally correct.

Exact amended plan SHA-256:
`a739521673ecdfed95c237f28f8c5fbcf5d6e8aede4a5f56a926225b265fdc81`.

Independent exact-byte reviews:

- correctness/causality: ACCEPT;
- anti-slop/dependency: ACCEPT.

Cut 1 is authorized only under the amended exact plan bytes. Cut 2+ remains
unauthorized pending coordinator review of the Cut 1 checkpoint.

CUT_0_ACCEPTED — CUT_1_AUTHORIZED
## Cut 1 — native resolution and spatial callback removal checkpoint

### Authority and change boundary

Cut 1 was executed under the amended plan SHA-256
a739521673ecdfed95c237f28f8c5fbcf5d6e8aede4a5f56a926225b265fdc81.
The pre-edit implementation-ledger SHA-256 was
2d691588b5c2b89c3ad3dc83333966c01e0a00641b4f62b7ec97198b4e7e7e87.
The governing instruction reads were verified before editing:

- agents.md: fcc5dd1e15bae2ff86a7203f42b0c55de4d51dd0d93bc3a3ae059b7e58ee39b1;
- HOW_TO_TEST.MD: 96ba573eb50504f9e2c9c8676acc2f352ae198466d79f46e75c57d3f29995013;
- amended plan: a739521673ecdfed95c237f28f8c5fbcf5d6e8aede4a5f56a926225b265fdc81;
- ledger before this append: 2d691588b5c2b89c3ad3dc83333966c01e0a00641b4f62b7ec97198b4e7e7e87.

No excluded server, deprecated-server, SDK, transport, generated, renderer,
editor, cross-language, pygame, content-recovery, or Phase 7 path was edited.
The existing accepted E3--E6 dirty files were preserved; their current hashes
are included below so the complete governed dirty scope remains auditable.

### Implemented Cut 1 mechanics

The following bounded changes were made:

- Event.resolve_sub_events() is the base no-op template. Completion and
  cancellation use the shared terminal finalizer, which derives parent and
  child metadata from the existing journal; the existing combat-log callback
  remains intact for this pre-Cut-2 boundary.
- GridMap physical spatial settlement, path invalidation, attached-light
  settlement, and light recomputation now run from the concrete
  SpatialChangeEvent.resolve_sub_events() path. The old per-event GridMap
  callback registration and its vision/blocking callback helpers are removed.
- Spatial and nonspatial sensory reduction now runs from concrete event
  resolution. Sensory children are registered as ordinary explicitly parented
  writes in stable observer order; the old indexed pre-completion sensory
  system registration and reset path are removed.
- SpatialEffectChangeEvent, WorldInitializedEvent, condition application /
  removal, TurnStart, life-state, and death concrete events now resolve their
  approved child mechanics through their subclass resolver. World initialization
  and authored trap/torch settlement use the non-vetoable concrete lifecycle.
- Entity-created and entity-level inert terminal facts use the reviewed
  publish_inert_terminal_fact() path. Only the existing item-charge generic
  pre-completion registration remains in production; the new architecture gate
  proves the exact production registration and callback name.
- SpatialEffectChangeEvent keeps the approved non-vetoable complete lifecycle.
  No action cost, item-charge ownership, concentration, metamagic,
  TurnStart/RoundEnd ownership, encounter log ownership, batch / reducer entry,
  or strict root-admission work was entered.

### Exact changed-path inventory and current hashes

The Cut 1-edited tracked path set is the following 27 files. Hashes are raw
current-byte SHA-256 values taken after the last code/test edit and before this
ledger append:

dnd/blocks/sensory.py a5a40c947824797359e341f428f3ce76e98e0564aa23d4d606c7c29ac137d2e1
dnd/content/scenarios/battlefield_builders.py 8196fe014f345ef6b7857226007c9999d986aacb9366d77c11c0678a48375bef
dnd/core/base_conditions.py 1f21487e9fc2e9ed147b437771d1957d1917d3ebcb15177e3b088885aec8b580
dnd/core/events/encounter_events.py 25ec5392a477992b581a9c4cdfc1324b3d9bbcabad798223e200e97cfc872640
dnd/core/events/entity_events.py 4ddb599809a92da412c0f49134e2fb9fda4700375291d38aa8a2faa33cf191af
dnd/core/events/events_registry.py 8f90aed8f55d74d6af89bcf1dc0fd9d4b426a5ef256200cc0d70193c46176980
dnd/core/events/world_events.py 41e646fbe4acfd3dc1e944e710361d322dcedc175cead48e88a5811b811e4c02
dnd/core/gridmap.py 6e3155ea8d0c32916aa36922e3ebf8dcc4446707ff751cf378d9031c29cabedb
dnd/entities/entity.py b9379e63b739d41f071d0395a41ea427cb6a8a1cb07abcc88307cbc371e6609b
dnd/entities/entity_creation.py 985c1b8f8ba1320e6795200e66d27ce6fa437dfbb633f799e61c27d93360648f
dnd/entities/entity_progression.py 94e6fd7cd9b2bcb2a198525e8230892f773d2c0cf6571e8bc8cb582a9764df29
dnd/runtime_reset.py 9ba073121929d5479ef2d9c0872089ad12324b48bdd73d2ce2239e97675c71af
dnd/spatial/area_conditions.py 92fd906429d13242be13c4bb69a4d6a4a50fbf30c1d140e90a10daee9c3dfaa9
tests/architecture/test_dependency_boundaries.py 64c15699f0024f6def7b0b948a492b664c8edf579d52fda3b17928d331ae6aea
tests/architecture/test_phase_6_completion_gates.py 9f1457c600ed6b2ef1a098b36904597cd1c3785662c23ec2408d610e990d9013
tests/engine/test_condition_content_evidence.py 6c6e6472af3c066370bde54189553f393a2503ba03f95aace58978198f6de60e
tests/engine/test_direct_scenario_deployment.py f56f0ed39315b1d75e4dcf507bc6207f14863eb60f8b8e7b49c2eb39a6b17519
tests/engine/test_elevation_proving_battlefield.py bd550aa94e2360a002de6584b705a64abf383a700fc8e42e8cb938a3b2398139
tests/engine/test_entity_creation_progression_core.py 4a36975d0ecde9edd0b82a25836ecec9a65c497142bb423441828160605cd3d9
tests/engine/test_equipment_domain_ownership.py 32d85587a7dd1387b1e342c22469e28900882ee293796e0ac909d7a5ebd50e9d
tests/engine/test_event_lifecycle.py 803401c18ed23a11a05d13c089776a021342a2843a5f2d1aa90ef747d89273d7
tests/engine/test_manual_05_events_before_handlers.py 2408f27d0061a8b9153c8c00a55a2b907f817def18bb89a35abd00fb37fad843
tests/engine/test_move_settlement.py d053cfe233fb6392f4338544f3f82664b1263f58e0680f2fb085df693b94f8cc
tests/engine/test_spatial_effects.py 9841021135b53269570e433f4d64798a6453a75e90e45a1c7c612c462522359f
tests/engine/test_tile_surface_contract.py 94d5fe2220a697fb23a43caa8090d92ceeed6c17216b4955964b1cca87c0330c
tests/engine/test_traversal_connectors.py f828e235b441925995e373ee220d7b8be0a8fbf9d36c4c86834bd1dc8e9212b9
tests/engine/test_world_edge_identity_and_elevation.py 078de4ed8d898edbf3bf91c7482eccf689aa052ca11bd35c918fe2c81e7f6396

The additional Cut 1-edited untracked test path is:

tests/engine/test_event_knowledge_scripted_encounter.py 24a5903b1d49295fbb28778afe2ae7593a92561b21d2d7ca58f5aeb62090c864

The five accepted E3--E6 files carried without Cut 1 edits are also present
in the shared dirty checkout and were hash-checked:

dnd/core/events/knowledge.py f9347cdeb21591b051014b06a90d4d5604904abdfe1c0d40d4d55d2c7d433026
tests/architecture/test_event_knowledge_context_architecture.py 5ffbe13efbf6d02c7cd98a953891b0f31cc676f5e766d7ceb06848f9e120308f
tests/engine/test_event_knowledge_async_boundary.py d1a014da295dc4a812725a903cef996207e595439b37d892c9b9c3ffaa73d0f4e
tests/engine/test_event_knowledge_context.py d4a3e8d1feec813c5497ff025377986c99997799efddd2101dbf51c87012d273
dnd/event_reduction.py 44450644478c90141789f53e31ecac70c78f84f2396cf2c5d3c842614f5859c7

tests/engine/test_event_knowledge_scripted_encounter.py is listed in the
Cut 1-edited set because only its expected native WorldInitialized phase count
and resulting source cursor were updated to exercise the now-four-phase
concrete lifecycle. Its E3 assertions below remain unmodified in meaning and
are not claimed green.

### Tests and commands

The accepted Cut 0 collection identity remains 309 nodes with normalized
SHA-256 f9a548aac09faf728ba330c1f7a12c2b4142eae851c5919a48aae54347409d80.
No Cut 1 node-union rewrite was requested; this checkpoint records the exact
runnable selectors and outcomes below.

Green focused/proportional results after the final architecture-gate edit:

- .venv/bin/python -m pytest -q -p no:cacheprovider tests/architecture ->
  58 passed in 36.25s;
- .venv/bin/python -m pytest -q -p no:cacheprovider
  tests/architecture/test_dependency_boundaries.py::test_only_item_charge_registers_generic_pre_completion_callback
  -> 1 passed in 2.06s (included in the 58-node architecture run);
- .venv/bin/python -m pytest -q -p no:cacheprovider
  tests/engine/test_event_knowledge_context.py -> 51 passed in 3.77s;
- .venv/bin/python -m pytest -q -p no:cacheprovider
  tests/engine/test_event_knowledge_async_boundary.py -> 1 passed in 4.86s;
- runnable sensory/terrain/entity/action group:
  test_senses_light_stealth.py, test_entity_creation_progression_core.py,
  test_elevation_distance_and_threat.py,
  test_elevation_performance_contract.py,
  test_elevation_proving_battlefield.py, test_progressive_elevation_movement.py,
  test_spatial_condition_performance_contract.py, test_spatial_effect_reveal_idempotency.py,
  test_spatial_restraints.py, test_direct_spatial_effect_materialization.py,
  test_condition_lifecycle.py, test_standard_conditions.py,
  test_items_inventory_equipment.py, and test_manual_05_events_before_handlers.py
  -> 178 passed in 76.72s;
- previously isolated runnable core lifecycle groups after the native-phase
  expectation repair: event lifecycle 13 passed in 1.37s, movement settlement
  50 passed in 34.08s, world/elevation 26 passed in 7.76s, and traversal
  connectors 38 passed in 7.47s; the combined core lifecycle run was
  165 passed in 37.65s;
- spatial/scenario run: test_spatial_effects.py 69 passed in 15.39s and
  test_direct_scenario_deployment.py 49 passed in 42.52s, combined
  118 passed in 47.17s;
- additional isolated results included test_senses_light_stealth.py 43
  passed in 27.38s, entity creation/progression 11 passed in 2.12s,
  elevation distance 9 passed in 6.36s, elevation performance 4 passed in
  12.07s, proving battlefield 7 passed in 7.95s, progressive movement 8 passed
  in 8.66s, spatial-condition performance 4 passed in 7.75s, reveal idempotency
  6 passed in 3.29s, restraints 5 passed in 12.25s, direct materialization 2
  passed in 3.13s, condition lifecycle 17 passed in 7.22s, standard conditions
  20 passed in 19.92s, items/inventory/equipment 37 passed in 7.03s, and
  manual engine event file 5 passed in 1.01s.

The following known collection blockers were preserved and not masked:

- The broad affected command collected with 2 errors and ran no body in
  tests/engine/test_condition_content_evidence.py, which imports missing
  dnd.core.content.runtime, and tests/engine/test_equipment_domain_ownership.py,
  which imports dnd.content_system. These are the known excluded dependency
  families from the shared checkout; no package restoration or excluded-file
  edit was made.

The accepted E3 scripted module currently has two failures and is explicitly
not claimed green:

1. test_direct_public_proving_encounter_freezes_the_real_event_inventory fails
   at its existing public combat-log identity assertion. The current encounter
   has 87 public combat-log entries, while only 13 parentless journal events
   carry matching stored combat-log objects; 74 entries are standalone log
   pushes, so the identity assertion fails. No encounter log ownership change
   was made in Cut 1.
2. test_full_public_encounter_replays_and_consumes_detached_batches_deterministically
   reaches source cursor 247 with 45 observed real batch callbacks, but the
   first callback error is:
   RuntimeError('sensory disclosure did not resolve exactly one causative terminal');
   subsequent callbacks report:
   RuntimeError('non-contiguous event batch [9, 10) after cursor 8') and later
   ranges. The child sensory event is stored during concrete parent resolution
   before the parent completion is stored, while the accepted E3 reducer expects
   its causative terminal to be available at callback reduction time. Fixing this
   would require a reducer/batch-boundary or root-storage change, which Cut 1
   explicitly does not authorize. This is the concrete Cut 1 stop condition for
   coordinator guidance.

### Callback hard-cut and retained inventory

The exact active production and tests/engine retired callback scan returned zero
matches for:

add_on_event_callback
remove_on_event_callback
add_pre_completion_system
remove_pre_completion_system
publish_completed_fact
_ensure_light_pre_completion_callback
_ensure_blocking_callback
_on_perceivability_changed
_on_vision_blocking_changed

The one retained production generic pre-completion registration is:

dnd/actions/operations.py:720
EventQueue.add_pre_completion_callback(consume_item_charge_before_action_completion)

The new architecture gate enforcing that exact production registration passed.
Existing retained sequence/batch infrastructure remains intentionally present
for later cuts: add_on_event_sequence_callback,
add_on_event_batch_callback, batch_on_event_callbacks, and
register_completion_sequence. Their production callers remain the existing
dnd/encounters/encounter.py and dnd/core/base_actions.py batch wrappers; this
is not a Cut 1 reducer-boundary change. Excluded manual callback residue was
not ported: tests/manual/test_05_event_lifecycle.py:351 and the
tests/manual/test_50_counterspell_engine_contract.py callback rows remain
outside the active Cut 1 migration. No publish_completed_fact reference
remains in active production or engine tests.

### Static validation and scope checks

- compileall -q over every current changed/untracked governed Python path:
  exit 0;
- git diff --check: exit 0 apart from the repository's existing LF-to-CRLF
  normalization warnings;
- exact active callback hard-cut scan: zero retired per-event and indexed
  pre-completion API matches;
- full architecture: green, 58 passed in 36.25s;
- current governed active dirty inventory: 33 paths total (27 tracked Cut 1
  paths, one additional untracked Cut 1-edited scripted-encounter path, and
  five carried accepted E3 untracked paths); no excluded path was added to
  scope.

No Cut 2+ work landed. Specifically, the generic item-charge pre-completion
API remains for Cut 2, terminal metamagic handling remains, action costs,
concentration, item-charge ownership, strict root admission, batch/reducer
entry, TurnStart/RoundEnd ownership, and encounter combat-log ownership were
not migrated. No new callback/contributor/listener/provider/manager/service/
controller/transaction/receipt/range-ledger or alternate event path was added.

This ledger append is the only remaining write for this checkpoint. Its raw
SHA-256 is to be computed externally after the final newline; it is not embedded
in itself.

READY_FOR_COORDINATOR_REVIEW

### Cut 1 bounded repair checkpoint — supersedes the rejected candidate

This checkpoint repairs the Cut 1 candidate rejected at ledger SHA
`d40b6d51902aae4a308c3fdd66d403fcb8edca8c05f818fad9edfa5ae3699997`.
The amended governing plan remains
`DND_EVENT_NATIVE_CAUSAL_RESOLUTION_CLEANUP_PLAN_2026-08-28.md`, raw SHA-256
`a739521673ecdfed95c237f28f8c5fbcf5d6e8aede4a5f56a926225b265fdc81`.
Only the bounded Cut 1 repair was continued; no Cut 2 or later-cut work was
started.

#### Native terminal resolution and inert facts

- `Event.finalize_terminal()` is mechanic-free. It derives terminal child
  lineages and combat-log descendants only from the stored `EventQueue`
  journal (`_all_events` and the existing UUID index), walking stored
  `parent_event` links with cycle protection. It does not read copied
  `children_events` or `lineage_children_events` arrays as authority and does
  not emit mechanics.
- A detached copied effect proposal retains the real stored child lineage/log
  tree, and a canceled effect retains completed reaction children; these are
  covered by the public journal/log tests
  `test_terminal_metadata_uses_stored_parentage_for_detached_completion` and
  `test_canceled_terminal_aggregates_completed_reaction_children`.
- Completion uses the existing stored-lineage terminal lookup before calling
  `resolve_sub_events()`, so a second completion attempt returns the stored
  terminal without rerunning mechanics or storing a second terminal. The
  direct proof is `test_terminal_resolution_is_idempotent_for_one_event_lineage`.
- `run_pre_completion_callbacks()` is invoked only by the normal COMPLETION
  path. CANCEL and inert terminal facts do not invoke it. The item-backed proof
  `test_canceled_item_action_does_not_consume_a_charge` leaves the consumable
  charge and inventory unchanged.
- Exactly `EncounterStartEvent`, `EncounterEndEvent`, and `RoundStartEvent`
  are classified as inert terminal facts. Their three encounter publishers
  construct unregistered COMPLETION events and call
  `publish_inert_terminal_fact`; `RoundEndEvent` remains non-inert.
- Handler-returned cancellation proposals are finalized through the same
  terminal metadata path before `_record_handler_result` stores them.

#### Callback retirement and retained Cut 1 boundary

The active production plus `tests/engine` hard-cut scan returned zero matches
for `add_on_event_callback`, `remove_on_event_callback`,
`register_completion_sequence`, `add_pre_completion_system`,
`remove_pre_completion_system`, `_pre_completion_systems`,
`publish_completed_fact`, `_ensure_light_pre_completion_callback`,
`_ensure_blocking_callback`, `_on_perceivability_changed`, and
`_on_vision_blocking_changed`. The one retained generic pre-completion
registration remains `dnd/actions/operations.py:720`:
`EventQueue.add_pre_completion_callback(consume_item_charge_before_action_completion)`.

`register_completion_sequence` has been removed. The existing sequence/batch
callback definitions and the batch callback boundary remain untouched for the
later reducer cut; no replacement callback/contributor/listener/provider,
second queue, manager, service, controller, transaction, receipt, or alternate
event path was introduced. Excluded manual callback residue remains governed
excluded residue and was not ported.

#### Spatial settlement proof and dependency-gate correction

`test_entity_anchor_presence_leave_and_restore_reconciles_footprint` now
uses the stored movement journal and its actual parent chain to prove that the
relevant `SPATIAL_LIGHT_CHANGED` and `SENSORY_UPDATE` descendants are stored
before the entered spatial root COMPLETION terminal, while retaining the final
observer-contact assertion. No event callback is used by this proof. The
boundary lifecycle test likewise uses journal phase rows rather than the
retired per-event observer.

The Cut 1 local-import allowlist is semantic rather than line-number based:
the only permitted local imports are the exact `(importer, function, target)`
triples for `resolve_sub_events` in the existing condition/encounter/world
event owners. The historical Phase 6 dependency-arrow gate now checks only
module-level imports for this rule, so it does not duplicate local-import
filename exemptions. The full architecture lane passed with this gate.

#### Exact validation results

- The complete runnable affected command covering event lifecycle, item
  cancellation, entity creation, movement, manual event, spatial effects,
  scenario deployment, Tile surface, connectors, and world/elevation was
  `335 passed in 59.81s`.
- The focused core lifecycle subset was `76 passed in 23.08s`, the item
  cancellation/lifecycle subset was `16 passed in 4.35s`, the direct repaired
  anchor journal proof was `1 passed in 7.04s`, and the journal-based boundary
  proof was `1 passed in 4.80s`.
- Full `tests/architecture` was `58 passed in 32.95s`.
- The broader command including
  `tests/engine/test_condition_content_evidence.py` and
  `tests/engine/test_equipment_domain_ownership.py` preserved the known two
  collection blockers and ran no body in those files: missing
  `dnd.core.content.runtime` and missing `dnd.content_system`. These are the
  previously governed excluded dependency families; no package restoration or
  excluded-scope edit was made.
- `.venv/bin/python -m compileall -q dnd tests/engine tests/architecture` —
  exit 0.
- `git diff --check` — exit 0; only the repository's existing LF-to-CRLF
  normalization warnings were reported.
- The active retired callback/API scan was empty except for the single
  retained item-charge registration. No Cut 2+ production/test migration was
  detected.

#### Current tracked Cut 1 candidate path hashes

The current tracked dirty candidate contains these 29 active paths. The raw
current-byte SHA-256 values for this checkpoint are recorded below.

```text
dnd/blocks/sensory.py                              b003ca9a549720ab6b63fbbf65d00ac117875157b55507d1b88b2886de92832e
dnd/content/scenarios/battlefield_builders.py      8196fe014f345ef6b7857226007c9999d986aacb9366d77c11c0678a48375bef
dnd/core/base_conditions.py                        1f21487e9fc2e9ed147b437771d1957d1917d3ebcb15177e3b088885aec8b580
dnd/core/events/encounter_events.py                3a9337fc1b08cbd679f81d044c5343dcc4f52d5a6d9652dd2d9bddce3714f0e3
dnd/core/events/entity_events.py                   4ddb599809a92da412c0f49134e2fb9fda4700375291d38aa8a2faa33cf191af
dnd/core/events/events_registry.py                 22e429b01f178328d499ce8cdd7bf71bf74950b183139d1bed448eed764414ae
dnd/core/events/world_events.py                    41e646fbe4acfd3dc1e944e710361d322dcedc175cead48e88a5811b811e4c02
dnd/core/gridmap.py                                6e3155ea8d0c32916aa36922e3ebf8dcc4446707ff751cf378d9031c29cabedb
dnd/encounters/encounter.py                        dec9eb5e6fd8c8eb4e89e96f7623564d43eafe832e98f778fcacabe249db66b5
dnd/entities/entity.py                             b9379e63b739d41f071d0395a41ea427cb6a8a1cb07abcc88307cbc371e6609b
dnd/entities/entity_creation.py                    985c1b8f8ba1320e6795200e66d27ce6fa437dfbb633f799e61c27d93360648f
dnd/entities/entity_progression.py                 94e6fd7cd9b2bcb2a198525e8230892f773d2c0cf6571e8bc8cb582a9764df29
dnd/runtime_reset.py                               9ba073121929d5479ef2d9c0872089ad12324b48bdd73d2ce2239e97675c71af
dnd/spatial/area_conditions.py                     92fd906429d13242be13c4bb69a4d6a4a50fbf30c1d140e90a10daee9c3dfaa9
tests/architecture/test_dependency_boundaries.py   857c89f03c87d8e2194073fcf818e53ba9835dd5fd4e1b0697e9dcb6a7b68ef5
tests/architecture/test_phase_6_completion_gates.py 718091a3585799e00021a5f19648fd5b219e8112f4f02225102b357eac7bd4b0
tests/engine/test_condition_content_evidence.py    3dfbdd8f02159c2cb7d37a54f945a4e6c7affb214c0a5cb9ff83c68383e59d32
tests/engine/test_direct_scenario_deployment.py    f56f0ed39315b1d75e4dcf507bc6207f14863eb60f8b8e7b49c2eb39a6b17519
tests/engine/test_elevation_proving_battlefield.py bd550aa94e2360a002de6584b705a64abf383a700fc8e42e8cb938a3b2398139
tests/engine/test_entity_creation_progression_core.py bc81b3115355e1db330e50ce7a4a5f9a3abd4f3a3dcdf7122cfb2281ec31cd8f
tests/engine/test_equipment_domain_ownership.py    6f1f8d6c648bbba4960438fd3251fe5d375c1975c52314cce0268bbc51d612cc
tests/engine/test_event_lifecycle.py               f478399ae8acb1299ef31294509c59745e3d6d418d83c1a78e47e950cb40ed1f
tests/engine/test_items_inventory_equipment.py     62a067ff1d3de548061cf13dffc1c008f3b8ba185d7316418517f34a873e2b76
tests/engine/test_manual_05_events_before_handlers.py 5f51b419736750b83ee46d40b13e1ae9aa72923444c0c2663907ac448a283172
tests/engine/test_move_settlement.py               be3ddd135f53ebaf303d433204038ff20b09920a7042e6dcaf403d41ed3c804f
tests/engine/test_spatial_effects.py               53df44796ebdfd6dc191c3d01c169b851b6399f3672a7316a4c10b5b8bea9305
tests/engine/test_tile_surface_contract.py         06bc07dd229e78baab64d6b6f4ac131f92b99f4c8d1e42cce190a5b6986dab3d
tests/engine/test_traversal_connectors.py          960c99bf43eba47873e782685cd1560dd9e3f42a5c55db05c310fe6d90354c21
tests/engine/test_world_edge_identity_and_elevation.py 3ae6de5dbdefc9f59c420db6e6c45fa8e274ceb4b889f74e461c2e57c92a66a5
```

The untracked E3/E4 governance artifacts and their missing-dependency test
surfaces remain carried accepted/unrelated work, not new Cut 1 scope. The
ledger itself is not a candidate member and its self-hash is not embedded.

No Cut 2+ work landed. The checkpoint is complete and stops here:

READY_FOR_COORDINATOR_REVIEW

### Cut 1 final bounded repair checkpoint — supersedes the rejected repair

This checkpoint supersedes the rejected Cut 1 candidate at ledger SHA
`d43246872b38111be28f6ae509dd0f3ba0ca95152f39ec92890712a50d0be38f` and
applies only the three coordinator-authorized repairs. The amended governing
plan remains `DND_EVENT_NATIVE_CAUSAL_RESOLUTION_CLEANUP_PLAN_2026-08-28.md`
with raw SHA-256
`a739521673ecdfed95c237f28f8c5fbcf5d6e8aede4a5f56a926225b265fdc81`.

#### Journal-derived terminal metadata

`Event.finalize_terminal()` now obtains the terminal lineage members from the
existing `_events_by_lineage` index, locates their earliest existing journal
position, and scans only that current tree suffix. Stored `parent_event` links
are walked with cycle protection to identify each direct child lineage. The
terminal metadata retains every stored phase UUID in each direct child lineage
in exact journal order in both `children_events` and
`lineage_children_events`; only `children_lineages` is deduplicated. No copied
child arrays are used as authority and no range ledger, cache, or new state was
added. The detached-completion and canceled-reaction-child proofs remain
green.

#### Idempotent cancellation

`Event.cancel()` returns the existing stored COMPLETION/CANCEL terminal for its
lineage before finalization or storage. A canceled handler result likewise
returns an already stored terminal before finalizing; an unposted cancellation
is finalized and recorded exactly once. The direct repeated-cancellation and
handler-cancellation proofs assert one CANCEL journal row, the expected single
cursor append, one combat-log projection, and stable returned-terminal identity.

#### Exact repair writes and validation

Only these two files were edited by this final bounded repair:

```text
dnd/core/events/events_registry.py
tests/engine/test_event_lifecycle.py
```

The focused repair command was:

```text
.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/engine/test_event_lifecycle.py::test_canceled_terminal_aggregates_completed_reaction_children \
  tests/engine/test_event_lifecycle.py::test_eb_04_006_cancel_posts_cancel_phase_and_stops_handler_chain \
  tests/engine/test_event_lifecycle.py::test_terminal_resolution_is_idempotent_for_one_event_lineage \
  tests/engine/test_senses_light_stealth.py::test_attached_light_moves_and_reduces_observers_once_per_step \
  tests/engine/test_senses_light_stealth.py::test_boundary_optical_light_settlement_is_a_child_before_object_completion
```

Result: `5 passed in 4.06s`.

The complete runnable affected engine lane was the lifecycle, item,
entity-creation, movement, manual-event, spatial, light/senses, scenario,
Tile, connector, and world/elevation modules; result: `378 passed in
80.98s`. Complete `tests/architecture`: `58 passed in 33.29s`.

Compileall over the governed changed Python paths exited 0. Full and scoped
`git diff --check` exited 0; only the repository's existing LF-to-CRLF
normalization warnings were emitted. The exact retired Cut 1 API scan returned
no matches for deleted per-event callbacks, `register_completion_sequence`,
deleted indexed pre-completion systems, `publish_completed_fact`, or the
retired callback names. The retained generic item-charge registration remains
the sole expected pre-completion registration.

Known excluded collection blockers remain unchanged: the broader optional
content/equipment surfaces require missing `dnd.core.content.runtime` and
`dnd.content_system`; no excluded package or file was changed. All prior
accepted/unrelated dirty files were preserved.

Current raw-byte hashes for the two repair files are:

```text
dnd/core/events/events_registry.py  c1f3e01ab0c98e6ea0eb5790adc66c2b1abafd6067e7c067115ff368600d8ccb
tests/engine/test_event_lifecycle.py  3c29cc4166a499a92cf4d237338e4ab192c447aae25323f10329ba1812629f07
```

No Cut 2+ work landed: batch/reducer entry, strict root admission, action
costs, concentration, metamagic, TurnStart/RoundEnd/log ownership, and all
other later-cut work remain untouched. The current ledger SHA is intentionally
not embedded in itself and must be computed from the final bytes.

READY_FOR_COORDINATOR_REVIEW

### Cut 1 publication-boundary repair checkpoint — supersedes rejected candidate

This checkpoint supersedes the rejected Cut 1 candidate at ledger SHA
`796e14824554b71848bb44389475d1f183cfd0344404cd9c52733f86b226f42b`.
Only the bounded detached-cancellation repair was applied; all other accepted
Cut 1 bytes and unrelated dirty work remain preserved. The amended plan is
`DND_EVENT_NATIVE_CAUSAL_RESOLUTION_CLEANUP_PLAN_2026-08-28.md`, SHA-256
`a739521673ecdfed95c237f28f8c5fbcf5d6e8aede4a5f56a926225b265fdc81`.

#### Repair

`Event.cancel()` now finalizes terminal metadata only for a registered
publication (`use_register=True`). A detached/unregistered cancellation
proposal therefore remains an unregistered CANCEL result and cannot invoke the
public combat-log callback or append to `EventQueue`. Registered direct
cancellation and handler-returned cancellation still use the shared finalizer;
the handler branch still returns an already stored terminal before any second
finalization or journal append.

#### Public validation

The new validation-boundary proof
`test_unregistered_validation_cancellation_is_detached_and_silent` uses a
public validation-only handler and asserts CANCEL phase, `use_register=False`,
no queue identity, unchanged cursor, and zero combat-log callbacks.

The prior direct/handler cancellation and journal-repair proofs were rerun:

```text
.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/engine/test_event_lifecycle.py::test_unregistered_validation_cancellation_is_detached_and_silent \
  tests/engine/test_event_lifecycle.py::test_canceled_terminal_aggregates_completed_reaction_children \
  tests/engine/test_event_lifecycle.py::test_eb_04_006_cancel_posts_cancel_phase_and_stops_handler_chain \
  tests/engine/test_event_lifecycle.py::test_terminal_resolution_is_idempotent_for_one_event_lineage \
  tests/engine/test_senses_light_stealth.py::test_attached_light_moves_and_reduces_observers_once_per_step \
  tests/engine/test_senses_light_stealth.py::test_boundary_optical_light_settlement_is_a_child_before_object_completion
```

Result: `6 passed in 4.14s`. The complete affected engine lane result was
`379 passed in 79.26s`; complete `tests/architecture` result was
`58 passed in 32.67s`. Compileall over the two repair Python paths exited 0.

Full `git diff --check` exited 0 with only the existing LF-to-CRLF
normalization warnings. The exact retired Cut 1 API scan returned zero matches
for deleted per-event callbacks, `register_completion_sequence`, deleted
indexed pre-completion systems, `publish_completed_fact`, and retired callback
names. The retained item-charge pre-completion registration remains the sole
expected generic registration. No Cut 2+ work landed.

#### Repair path hashes

```text
dnd/core/events/events_registry.py  3ae12c6fcd02a09553e8834adf573f41fdcc442ab7f8e636dd44a014b51bcfca
tests/engine/test_event_lifecycle.py  a69f90490aa2c8e3666c15e7115c5bd93768ee4aae1624cc1695dc037f72043d
```

Known excluded collection blockers remain unchanged (`dnd.core.content.runtime`
and `dnd.content_system` are unavailable); no excluded files or packages were
modified. The ledger SHA is intentionally not embedded in itself.

READY_FOR_COORDINATOR_REVIEW

### Coordinator acceptance — Cut 1 complete

The superseding Cut 1 publication-boundary candidate was independently
validated by the coordinator at `386 passed` across the runnable affected
engine lane and `58 passed` across the complete architecture lane. Full
`git diff --check`, compileall, and the retired-API hard-cut scan were clean;
the sole retained generic pre-completion registration is the explicitly
temporary item-charge seam assigned to Cut 2.

Two independent exact-byte reviews accepted the candidate with no material
findings:

- correctness/causality: ACCEPT;
- anti-slop/dependency/locality: ACCEPT.

The reviewed candidate hashes were:

```text
DND_EVENT_NATIVE_CAUSAL_RESOLUTION_CLEANUP_PLAN_2026-08-28.md  a739521673ecdfed95c237f28f8c5fbcf5d6e8aede4a5f56a926225b265fdc81
dnd/core/events/events_registry.py                              3ae12c6fcd02a09553e8834adf573f41fdcc442ab7f8e636dd44a014b51bcfca
tests/engine/test_event_lifecycle.py                            a69f90490aa2c8e3666c15e7115c5bd93768ee4aae1624cc1695dc037f72043d
```

Accepted Cut 1 laws include complete journal-ordered direct-child phase
membership, lineage-only deduplication, suffix-bounded ancestry through the
existing journal indexes, idempotent completion/cancellation, exactly one
stored terminal and log projection for public cancellation, and zero journal
or log publication for detached validation cancellation.

`CUT_1_ACCEPTED — CUT_2_AUTHORIZED_ONLY`

## Cut 2 action-terminal correctness checkpoint

This checkpoint implements Cut 2 only from the amended governing plan
`DND_EVENT_NATIVE_CAUSAL_RESOLUTION_CLEANUP_PLAN_2026-08-28.md`, SHA-256
`a739521673ecdfed95c237f28f8c5fbcf5d6e8aede4a5f56a926225b265fdc81`.
The accepted Cut 1 candidate and all unrelated dirty work remain preserved.
No Cut 3 or later work is included.

### Bounded implementation

`BaseAction._apply_action` now publishes the ordinary declaration, validates a
detached exact-class/exact-lineage proposal, publishes validation cancellation
without cost, commits accepted action/resource costs and the existing item
charge at the execution boundary, then registers execution for reactions. A
cost failure publishes the root cancellation after the failed commitment; an
execution reaction therefore observes already committed costs. Item charges
are emitted once as the existing `ItemChargeConsumptionEvent` child of the
stored action declaration. The obsolete late cost hooks and the generic
item-charge pre-completion registration are deleted.

The four owner-specific cost surfaces are execution-stage methods: Move,
TraverseConnector, and Jump retain explicit transaction-settled no-ops, while
FreedomOfMovementEscape commits its movement cost before effect resolution.
The spell-only late cancellation-cost override is deleted.

All 43 active `ensure_concentration()` call sites across the eight governed
spell files were inventoried. Single-target spell paths close their cast-local
slot from the final effect phase; the five multi-entity cases and the other
convolution/AOE concentration paths use the one BaseAction post-convolution
close. No `_cleanup_concentration` hook remains and no concentration cleanup is
performed after a root terminal.

MetamagicAutoRemove now consumes the pending metamagic condition at accepted
spell execution. Its terminal CANCEL trigger is deleted. EventQueue does not
dispatch handlers for COMPLETION or CANCEL, and the architecture gate rejects
any production Trigger declaration on either terminal phase.

### Validation commands and results

The consolidated runnable Cut 2 affected lane was executed exactly as:

```text
.venv/bin/python -m pytest -q -p no:cacheprovider \
 tests/engine/test_action_cost_and_position_commit.py \
 tests/engine/test_action_discovery.py \
 tests/engine/test_combat_actions.py \
 tests/engine/test_condition_lifecycle.py \
 tests/engine/test_condition_transform_ownership.py \
 tests/engine/test_direct_scenario_deployment.py \
 tests/engine/test_direct_spatial_effect_materialization.py \
 tests/engine/test_elevated_jump_transaction.py \
 tests/engine/test_elevation_distance_and_threat.py \
 tests/engine/test_elevation_proving_battlefield.py \
 tests/engine/test_entity_creation_progression_core.py \
 tests/engine/test_event_lifecycle.py \
 tests/engine/test_items_inventory_equipment.py \
 tests/engine/test_manual_05_events_before_handlers.py \
 tests/engine/test_manual_06_dice_and_roll_result_events.py \
 tests/engine/test_move_settlement.py \
 tests/engine/test_progressive_elevation_movement.py \
 tests/engine/test_senses_light_stealth.py \
 tests/engine/test_spatial_effect_reveal_idempotency.py \
 tests/engine/test_spatial_effects.py \
 tests/engine/test_spatial_restraints.py \
 tests/engine/test_standard_conditions.py \
 tests/engine/test_spell_families.py \
 tests/engine/test_traversal_connectors.py \
 tests/engine/test_world_edge_identity_and_elevation.py \
 tests/engine/test_direct_item_content.py
```

Result: `597 passed in 206.34s`.

The focused supplementary results were:

```text
test_direct_scenario_deployment.py + test_action_discovery.py
  + test_combat_actions.py + test_manual_05_events_before_handlers.py
  + test_event_wire_visibility_contract.py: 118 passed in 55.59s
test_spell_families.py + test_action_cost_and_position_commit.py
  + test_move_settlement.py + test_traversal_connectors.py: 157 passed in 84.79s
test_direct_scenario_deployment.py + test_senses_light_stealth.py
  + test_spatial_effects.py + test_manual_05_events_before_handlers.py:
  166 passed in 53.67s
test_elevated_jump_transaction.py + test_progressive_elevation_movement.py
  + test_elevation_distance_and_threat.py + test_elevation_proving_battlefield.py:
  34 passed in 15.64s
test_manual_06_dice_and_roll_result_events.py
  + test_entity_creation_progression_core.py + test_standard_conditions.py:
  36 passed in 17.45s
test_direct_spatial_effect_materialization.py
  + test_spatial_effect_reveal_idempotency.py + test_elevation_distance_and_threat.py:
  17 passed in 5.00s
```

`tests/engine/test_items_inventory_equipment.py` completed with `38 passed in
5.07s`; `tests/engine/test_event_lifecycle.py` plus the new item proof
completed with `16 passed in 4.08s`; and the action-cost selector completed
with `11 passed in 6.18s`.

The complete architecture lane returned `59 passed in 28.87s`. The two Cut 2
hard-cut selectors for generic pre-completion registration and terminal-phase
handler declarations returned `2 passed in 1.80s`.

Compileall over every Cut 2 changed active Python path exited 0. Full
`git diff --check` exited 0; only the repository's existing LF-to-CRLF
normalization warnings were emitted. The production AST hard-cut scan found:

```text
retired production references: []
terminal production Trigger declarations: []
commit-cost definitions: dnd/core/base_actions.py plus Move, TraverseConnector,
Jump, and FreedomOfMovementEscape
concentration close definitions: dnd/actions/standard.py only
ensure_concentration totals: 8 + 12 + 1 + 4 + 2 + 6 + 3 + 7 = 43
```

The first focused run exposed the old test expectation that a canceled
one-charge consumable remained in inventory. The authorized test was repaired
to assert execution-time charge consumption, item destruction, one charge
completion child, and declaration parentage; the final affected lane is green.
Two optional collection attempts remain excluded and unchanged because the
checkout lacks `dnd.core.content.runtime`, `dnd.content_system`, and the
optional `dnd.monsters.bestiary_content` package. No excluded package or file
was changed.

### Cut 2 changed active paths and raw-byte hashes

These are the exact active paths changed by this Cut 2 checkpoint. Other dirty
paths in the checkout are accepted prior-cut or unrelated work and were not
modified by Cut 2.

```text
dnd/actions/operations.py                                  168296bd8e653c895ddf7580a9ecc9a6333d6aff658891fe48be362795d03d0d
dnd/actions/standard.py                                    e88206c6e4dcd9e188c16cb70991c25a3b302a1aad94bd9400d79cd005e280d2
dnd/blocks/base_item.py                                    617c9e19d50624a1ecac15777e00a0dbc924fe67b787f387fa35e4afe9a708d8
dnd/classes/sorcerer.py                                    bcfdbd7a0c79f87c5426e8f0ea5b33b9316fd2031d9be9e67d8c6cb0410767fb
dnd/core/base_actions.py                                   c1493e36f6a6b87133c4f9854bbe6c62a5e6bed437241a7ee6e3bc3003533fd6
dnd/core/events/events_registry.py                         c30c44dc1ecb5c5606ea8892348f508a1afec27ec0151a9e7383869fe6fa6e6b
dnd/spells/abjuration.py                                   be56401db790a6973beb9c173f37cbcff924816c49e47ad696c5503d476b987a
dnd/spells/conjuration.py                                  15a2609ac1999a135b3dcdf629b61f5f99ee6c5898eb2453d3e9b7081fa6eec0
dnd/spells/divination.py                                   5b4d68555a69326c31f9894a7d6f70eb2152ca246e4e49786f64cb406fb21d63
dnd/spells/enchantment.py                                  f8b40054ca6e21f83844fc9cd611ffe4972affa83e6b9f9c29350dcfecbf6bd0
dnd/spells/evocation.py                                    d3fc458d426ec89b3a58e4b1d94013a2ca91a463d20b1300a8480244a9881f42
dnd/spells/illusion.py                                      c529b5b4e1441d629649b612681d08e3044355ec1926adc966b04925b7703679
dnd/spells/necromancy.py                                   0dc50c26d510521d659726a90e5aa4be2aca8beb1d25dbab6143fc028de4945e
dnd/spells/transmutation.py                                971cab53e2437ded326c36e70a96dc2347521451469479a0e7932dd447d62090
tests/architecture/test_dependency_boundaries.py           4386ff6090afc8b0c5f36a0ef98db96a274402b572147527a415aab6a89f001c
tests/engine/test_event_lifecycle.py                       3552a33d7a6f2aa7daad6292ad060672a03dbac82881f771646503500bd662e8
tests/engine/test_items_inventory_equipment.py             da3e4bb696f9a09368294b5d2a065d10baf70c1027a026f035612cd1d8a69572
tests/manual/test_legacy_reactive_reaction_coverage.py     eea1d378d68716c4b896b6118c1180c2cebd030de5192e9d66cd4f7406e84a0e
```

The ledger had raw SHA-256
`ea5a643f27638c3a548a37e122e665edc73c896ac5b756b884a2c115fa18ba46`
immediately before this append; its final hash is intentionally not embedded
in itself. No manifest was created or modified. Cut 3+ work remains
unauthorized.

READY_FOR_COORDINATOR_REVIEW

## Coordinator Cut 2 exact-candidate repair — 2026-08-28

This section supersedes every earlier Cut 2 checkpoint. The governing plan is
unchanged at SHA-256
`a739521673ecdfed95c237f28f8c5fbcf5d6e8aede4a5f56a926225b265fdc81`.
Cuts 3+ remain unauthorized.

The coordinator's independent run rejected the prior selection-only
Counterspell proof because the complete active module still referenced the
deleted per-event callback API. Those tests now observe ordinary stored journal
facts. That migration exposed and repaired one real projection defect:
evidence-invalidated Counterspell children no longer contribute a false spell
interruption log. Valid successful and failed Counterspell resolutions retain
their typed logs.

The same audit made the existing execution-commit contracts fully explicit.
Metamagic removal is parented to the stored spell declaration and completes
before the first Counterspell reaction fact. The existing `_commit_costs` seam
now receives that stored declaration; no hook or registry was added. Finite
item charges use the small dependency-neutral `FiniteChargeProvider` protocol,
one direct method call, and fail closed. The former attribute-probing and broad
exception masking are gone.

### Independent coordinator validation

- Complete affected lane, including the whole active Counterspell module:
  `627 passed in 219.69s`.
- Complete `tests/manual/test_50_counterspell_engine_contract.py`:
  `21 passed in 9.41s` after the final parenting repair.
- Counterspell plus event lifecycle: `36 passed in 9.43s`.
- Spell, item, and action-cost proofs: `120 passed in 68.92s`.
- Complete architecture lane: `59 passed in 30.28s`.
- Compileall over all 21 Cut 2 active paths: exit 0.
- `git diff --check`: exit 0 with only existing LF/CRLF notices.
- Retired callback/pre-completion/metamagic-auto-remove/reflective-seam scan:
  zero matches.
- `tests/engine/test_counterspell_evidence.py` remains an unchanged excluded
  collector because `dnd.core.content.runtime` is absent. No content-recovery
  file or compatibility stub was added.

### Exact Cut 2 candidate bytes

```text
dnd/actions/operations.py                              168296bd8e653c895ddf7580a9ecc9a6333d6aff658891fe48be362795d03d0d
dnd/actions/standard.py                                1820ebbd0ac6354c09ddf36bcd9086564d22c39d81da9849a61b09abb239fe4a
dnd/blocks/base_item.py                                617c9e19d50624a1ecac15777e00a0dbc924fe67b787f387fa35e4afe9a708d8
dnd/classes/sorcerer.py                                8794c6f03b275db4f2bab9df7b45d27f389ea35b8d8236fe91e62f5652a471e9
dnd/core/base_actions.py                               c484ad4af08fea13eb779b55e799765c73dd770f942c9661d58a0d9f8b9e85d4
dnd/core/events/action_events.py                       acb3c72134bc75d23e4e37659ab9978ed068a2dc2f6783522ec8184bed9c7d63
dnd/core/events/events_registry.py                     c30c44dc1ecb5c5606ea8892348f508a1afec27ec0151a9e7383869fe6fa6e6b
dnd/core/events/item_events.py                         07484281ac4df1e7c32ec40dc542ce583b04ebc2c04aa253016b3454ab4872f3
dnd/spells/abjuration.py                               1078d32120859f64bd2d8cd21524e06209159af5e5ab9200442a70f7719fc872
dnd/spells/conjuration.py                              861a793cae6e4f7e8f1becc98e89cef99cb58878687d87ada7fbaf8bbc3149b9
dnd/spells/divination.py                               eff1536194d01a63b49038df5d255b8353c1ba750ebcec4f62b10461965dcfaa
dnd/spells/enchantment.py                              b1f6aba773c1082e6e196f57d34d960515b993260f17eedb60da49e8e127201f
dnd/spells/evocation.py                                958c3a2a53ec15420bcff6674b5753f562a08690a820bb7a44052ccf65f362d6
dnd/spells/illusion.py                                 ec9a29d0a5ab6a09a1b842e9e10a400cfaa71e4f54d6ec7cbc9da432cacd66c2
dnd/spells/necromancy.py                               e054caf1d7b2bd82fcac67b523c42422156caf01ebd4feda285647c1dcf11618
dnd/spells/transmutation.py                            ad0fa7833f8112ef10e5ffc6cea8c3ee20763fe57b42411cd8b1e95695400672
tests/architecture/test_dependency_boundaries.py       4386ff6090afc8b0c5f36a0ef98db96a274402b572147527a415aab6a89f001c
tests/engine/test_event_lifecycle.py                   3552a33d7a6f2aa7daad6292ad060672a03dbac82881f771646503500bd662e8
tests/engine/test_items_inventory_equipment.py         cc0da76bffb44e1dfc1fa9bd10873460176db49aadedf83f22fa488fd5bd9055
tests/engine/test_spell_families.py                    3666d8a78b4d50a26eb3be432efc7d17dde10911e81d64c5736c4ee96e357c6f
tests/manual/test_50_counterspell_engine_contract.py   7724dacaac3d2a4d9b54ad43bc2d20c3e6816b645d4554029b641b7c20b50e84
```

The ledger SHA immediately before this append was
`8912aa2e1bc2113f31b09b6ad8f0e5a1a9c578a18921c462f3516a638336445a`.
The candidate is frozen for independent correctness and anti-slop review.

`CUT_2_READY_FOR_EXACT_CANDIDATE_REVIEW`

## Superseding Cut 2 concentration-admission repair — 2026-08-28

The first exact-candidate correctness review rejected ledger SHA
`9aa9c2ba73526cb4e441e61d5db0565e81516b11fd8759349ae27bc3242f7b24`.
Five single-target spells created an empty concentration slot before EFFECT
admission, while Bless and the undead Necrotic Bless branch installed target
state before their per-target EFFECT admission. No queue special case was
added. Each mechanic now follows the same direct law: admit EFFECT, return its
cancellation unchanged when vetoed, and only then create or mutate spell-owned
state.

Seven public-boundary regression cases were added: all five single-target
branches plus the Bless and undead Necrotic Bless per-target branches. They
assert the real spell result, target/caster state, canceled child evidence, and
journal terminal order.

Validation after the repair:

- Focused concentration admission/order selection: `13 passed in 9.09s`.
- Complete affected lane including the full Counterspell module:
  `634 passed in 310.02s`.
- Complete architecture lane: `59 passed in 38.89s`.
- Compileall: exit 0.
- `git diff --check`: exit 0 with only existing LF/CRLF notices.
- Retired callback/pre-completion/reflection scan: zero matches.

The 16 unlisted member hashes remain byte-identical to the preceding exact
candidate section. The five changed candidate members are:

```text
dnd/spells/abjuration.py                9fdb7f51b0523e0106384db6b0e78b47dfc9064e9ef2e4958c8d34f19b1de701
dnd/spells/enchantment.py               c768ac272f30ef88cd482af3b838aa306d620e6d4e48bbeae85b70a1b96037d3
dnd/spells/necromancy.py                d2e75de5f0d05f7610736c2151c4beeca0fc43788dc3f4e4aa3257d7db28e6ae
dnd/spells/transmutation.py             a426361e13dd78e302bbdbda8f187906842b4722dca73194220b8a9fbca6b8a1
tests/engine/test_spell_families.py     a73bcf1b0dd533ff4356630858772ed490852280e516c5df516b0f3c3cf2e46a
```

The ledger SHA immediately before this append was
`9aa9c2ba73526cb4e441e61d5db0565e81516b11fd8759349ae27bc3242f7b24`.
Both prior reviews are invalidated. The candidate is frozen for two fresh
exact-byte reviews; Cut 3+ remains unauthorized.

`CUT_2_REPAIRED_READY_FOR_FRESH_REVIEWS`

## Coordinator Cut 2 acceptance — 2026-08-28

Both independent reviewers accepted the exact candidate at ledger SHA
`6c588a700b92bb7c66a2b669f9fba100155708df50fcec7708c26feedf198b09`.

- Correctness/causality: ACCEPT. It independently checked all 21 member
  hashes, reran a focused repaired selection, and additionally probed the
  living Necrotic Bless branch. No state leakage, terminal-order violation,
  missing branch, or scope expansion remained.
- Anti-slop/dependency: ACCEPT. It independently checked the changed hashes
  and focused cases. The repair is operation reordering at existing owners;
  it adds no helper, hook, callback, registry, pending state, reflective
  dispatch, compatibility path, or catch-all exception.

No production or test byte changed after these approvals. Cut 2 is accepted.
Cut 3 alone is authorized next; Cuts 4+ remain unauthorized.

`CUT_2_ACCEPTED — CUT_3_AUTHORIZED_ONLY`

## Cut 3 candidate — turn, round, and combat-log ownership

Cut 3 is implemented and frozen for independent review. The ledger SHA before
this append was
`a39577da36207578dc030b25ff45403fe4aa1e67c592bb8d91ee7f896e6ba3af`.

Implemented ownership changes:

- `TurnStartEvent` execution now parents entity, equipped-item, and inventory
  duration advancement, fresh removal-saving-throw lineages, condition
  expiration, and linked cleanup. All children precede the turn terminal.
- `RoundEndEvent` now runs declaration, execution, effect, environment
  progression, and completion. Tile, placed-object, spatial-condition, and
  linked removals inherit the round effect; the next inert `RoundStartEvent`
  follows the terminal.
- Encounter combat logs are a read-only projection of real root terminal facts
  inside encounter-owned source cursors. Mutable log storage, queue log push,
  encounter callback/listener fan-out, and reset residue are deleted.
- Condition immunity cancels the real `ConditionApplicationEvent` with
  `IMMUNE` disposition; that terminal generates the typed log itself. No fake
  event or standalone log remains.
- The public scripted encounter now proves raw append-order parentage, one
  terminal per root, root-terminal finality, turn/round lifecycle ordering,
  and terminal/log identity.

Coordinator repairs after the implementer checkpoint were limited to tests:
the scripted proof now compares raw journal order with journal indexes; the
governed Counterspell contract reads the real canceled terminal instead of the
deleted callback; and the tile-duration contract proves RoundEnd owns linked
environment removal through its terminal.

Validation on the frozen candidate:

- focused Cut 3 causal contracts: `59 passed in 14.66s`;
- proportional event/condition/spell/scripted lane, excluding only the test
  explicitly owned by Cut 4's callback-to-pull migration:
  `190 passed, 1 deselected in 88.77s`;
- complete architecture lane: `59 passed in 31.20s`;
- compileall: exit 0;
- diff check: clean apart from existing line-ending notices;
- Cut 3 retired log API scan: zero matches in active production, engine tests,
  architecture tests, and the governed Counterspell contract;
- Cut 4 pull APIs remain absent, and existing batch/reducer production code is
  unchanged in this cut.

The deselected
`test_full_public_encounter_replays_and_consumes_detached_batches_deterministically`
is the accepted plan's explicit Cut 4 async-boundary migration target. Its
callback observes a sensory child before its future causal terminal and fails
without changing production behavior; no shim, re-batching, or cross-archive
repair was added in Cut 3.

Exact Cut 3 candidate members:

```text
dnd/core/base_block.py 1db46a74c225afefc92175bab76f4a7717838287483300944550570a802729eb
dnd/blocks/base_item.py fb0fe23c8aebde7e1ca624833a3682f43769cb0d6cb379858c2c01c2bce2fa78
dnd/runtime_reset.py fb815a009708975e2be41288e64d461356c29f039f0183686f69390980f02f29
dnd/entities/entity.py 84fa41159c229a85a159965c406192656bfa17d7408569b0498d58d8dad93bc2
dnd/core/events/events_registry.py 6701bccd2dda30e6bca2cc51f474ec843b9be72ecb1e7f334f6badab12e7bd21
dnd/encounters/encounter.py f921dc61e0f913c5cb1930971a82657b29d2fe08b01e848d56387dbd4c05bc8c
tests/engine/test_action_discovery.py 24f68ec3f9f3fcd710cc4b4d72ae9560a8c038c97344c9e50ae5a85c39cc7a6b
tests/engine/test_block_context.py 6aa7f5c5fd5ca30875aac416998ce7cf6c7e47e0b1c564066ba3fcd12c5af6e3
tests/engine/test_combat_actions.py cd2a611123fb998b9788a1a8b2894e6a9ba1e543000561a58b37a621a5945c9e
tests/engine/test_entity_composition.py 429c2186162425a6cada4c15660809f3ee8de0a43a85dd6ceabb2ef422aef2a6
tests/engine/test_grid_pathfinding.py 96b4add81501dbdbc3a120fee7e30ac27c89027ffbd87ad71ebe57bb06e37779
tests/engine/test_items_inventory_equipment.py 1bb97b34656c61d242e69961853c11f6e8a68798da6d4a6962be32e1d229308e
tests/engine/test_manual_05_events_before_handlers.py 6434aebd4b8511639ba2fdee965adefe3039f7af137a3bee8c717e2e76bfa099
tests/engine/test_manual_08_blocks_ownership_context_cleanup.py 17e37f6bd7bb3cb429e02b5442b2405ddae1266d8428dbbca131b0963c0c26ea
tests/engine/test_manual_09_conditions.py d74c4d231082977b4e79b978ffbfe9bde2c6ddd58055eee826486974418af0ac
tests/engine/test_manual_10_standard_conditions.py 9c28254e3233417cba3549aad0a41390697af0326d5848cc253536e496438c50
tests/engine/test_manual_11_grid_tiles_terrain_movement.py b64c305d4e86c5d7f23f6df558295ecb5fbf89abfcd20f17ded40719ba117730
tests/engine/test_manual_14_core_combat_flow.py a0597749a2ced6879b7b0f9562840e2fec938d1f920ea1eb4342607a5bf99f88
tests/engine/test_monster_presets.py 7cb1845ae4acfb257efb78182c447e4ef8d3b7cd652bc40453f9491fe187708d
tests/engine/test_spellcasting.py 6d189d1a67a50713d9c4cc6ddad58cdd270492ae7da558ec751ccee5f3ce284b
tests/engine/test_standard_conditions.py 5e68b584d4fdb9304066df2b2799c791a80b6b7b632d29216701edd535caf3d5
tests/engine/test_encounter_apis.py 90823374fff0f3bcc4bca3e951fbbbe484cd398f0c3d86d2a9fa981d1baba953
tests/engine/test_condition_content_evidence.py e56b4544286201d1009d6bb260b1c09866af07ba094909d6fdcc5ad574ed64c1
tests/engine/test_spell_families.py 5442871e03d221ba0cf6eea666426bd312df6c9f43507277dffb52d7f43f6883
tests/engine/test_runtime_reset.py bb879ab0237c6894315b35f5d3597eb1d6801c5934bcc8563f9f2d5bce4e713f
tests/engine/test_condition_lifecycle.py 234e315207eb771a188f51963e92e048486833eb42d1f0d04ca82a414efed974
tests/engine/test_event_knowledge_context.py 42516da23e17e3cf2f773ac18f28476c14f091e39106457fca03dd91463f8a37
tests/engine/test_manual_20_encounters_turns_controllers_apis.py 9750e6b31bf36f8ed060348156d65afc4698e447236013cb1f9adbe5ada0cc72
tests/engine/test_event_lifecycle.py 8c92ed576913686d80cc69dfeb4eef05ebaeb7fa6ae39da7892a873f071bdf31
tests/engine/test_spatial_restraints.py f38bcc0355041fb58354c1f845f03e5032688a1da8100af3afa7e45288379e32
tests/engine/test_event_knowledge_scripted_encounter.py 16c9e349f673f6d9ba0f5bbd8d0dac2d0798df20b35b1b332049d480965e9f69
tests/manual/test_50_counterspell_engine_contract.py c94b17cfc4f365f1e410b9742f77b2b01774e6e5c73a563b7777b06fd63c3f37
tests/manual/test_tile_condition_duration_legacy_contract.py 041b3fdc9eac4d67842479213891f1f34a8d82f93faca23559a337a3fee7fc7c
```

`CUT_3_READY_FOR_EXACT_REVIEWS — CUT_4_NOT_AUTHORIZED`

## Superseding Cut 3 terminal-finality and ownership-proof repair — 2026-08-29

The first exact-candidate correctness review rejected ledger SHA
`4b8554c39c4e32d18b91e95fc8675f989812606bee4d2867c95f8be81742cbf1`.
`Entity.on_turn_start()` did not return after its execution phase was canceled,
so it could publish duration-removal children, reset action economy, set turn
state, and attempt a later EFFECT after the root terminal. The production
repair is one immediate cancellation return at the existing phase boundary.
No helper, hook, callback, pending state, or queue exception was added.

The same review found a proof gap, not another observed production defect:
the frozen candidate did not directly exercise every duration owner named by
Cut 3. Public regressions now prove both sides of the contract:

- a canceled TurnStart leaves entity, equipped-item, and inventory-item
  durations and ownership unchanged and publishes nothing after its terminal;
- a successful TurnStart expires all three owners beneath its EXECUTION and
  before its completion;
- the actual encounter round boundary expires Tile, linked Entity,
  placed-object, and independent spatial-condition state beneath the RoundEnd
  EFFECT, before both the RoundEnd terminal and the following RoundStart.

Validation after the bounded repair:

- repaired TurnStart/RoundEnd cases: `3 passed in 5.21s`;
- complete affected item, tile-duration, event-lifecycle, and scripted files,
  excluding only Cut 4's already accepted callback-to-pull migration target:
  `61 passed, 1 deselected in 8.10s`;
- complete architecture lane: `59 passed in 30.23s`;
- compileall over all three changed members: exit 0;
- `git diff --check` over all three changed members: clean apart from existing
  line-ending notices.

The other 30 members in the preceding exact Cut 3 section remain
byte-identical. The three repaired member hashes are:

```text
dnd/entities/entity.py                                  388dcd0504036108e359f3f012259ebe0d9d299b15bc4980f3bbc2b5a51a4df2
tests/engine/test_items_inventory_equipment.py          8cb0125ac2b495b2bbc645bffc369fe839106ee230689458815e36d6bdf7c4b3
tests/manual/test_tile_condition_duration_legacy_contract.py 4ef38c5910b20d8df4a613fe72514f9883c16ab0181eb80a5eb8e12a93a48841
```

Both prior reviews are invalidated. The exact repaired candidate is frozen for
fresh correctness and anti-slop reviews; Cut 4 remains unauthorized.

`CUT_3_REPAIRED_READY_FOR_FRESH_REVIEWS — CUT_4_NOT_AUTHORIZED`

## Coordinator Cut 3 acceptance — 2026-08-29

Both independent reviewers accepted the exact repaired candidate at ledger SHA
`3827acc900dd07608c5655cbfb57106c7f500b7bce6be260802c14504422c129`.

- Correctness/causality: ACCEPT. It verified all 33 effective member hashes,
  reran the three repaired cases and the complete four-file lane, and directly
  probed a spent-action cancellation. TurnStart cancellation is terminal and
  mutation-free; all enumerated TurnStart and RoundEnd owners are proven
  beneath their causal phase and before the root terminal.
- Anti-slop/dependency: ACCEPT. It verified all 33 effective member hashes and
  reran the repaired selection. The repair is one immediate return at the
  existing boundary plus public journal/state proofs. It adds no helper,
  abstraction, callback, pending state, registry, reflection, compatibility
  path, queue exception, or premature Cut 4 API.

No production or test byte changed after these approvals. Cut 3 is accepted.
Cut 4 alone is authorized next; Cuts 5+ remain unauthorized.

`CUT_3_ACCEPTED — CUT_4_AUTHORIZED_ONLY`

## Cut 4 candidate — strict queue kernel and pull-only reduction

Cut 4 is implemented and frozen for exact independent review. The ledger SHA
before this append was
`7c84ae52b88b57d033895af07613af32f7a07ccfeb09e7bd9bf4333e0e66d5f3`.

Implemented boundary changes:

- `EventQueue` admits one parentless root at a time and rejects mismatched
  root class/lineage, missing or closed parents, parent cycles, phase
  regression, class changes within a lineage, late children, and non-final
  terminals. A root terminal clears the two-field open-root identity; child
  terminals do not.
- `next_committed_tree()` derives the next exact contiguous tree solely from
  the append-only journal and the consumer cursor. There is no range ledger,
  transaction identity, batch registry, or caller-authored range.
- Passive event/sequence/batch/handler observer APIs and storage are deleted,
  as are action/encounter batch wrappers and the completion-sequence writer.
- `EventReducer` now exposes only explicit next-tree pull/drain entry points.
  Reducer state advances only after a whole detached batch is built. Sensory
  causality resolves inside the current closed tree; older archives remain
  reference-only provenance and cannot repair a missing current cause.
- The async boundary is an explicit test-local reducer pump. No production
  asyncio pump, receipt, acknowledgement, presentation scheduler, or new
  manager/controller/framework was added.
- Direct kernel tests cover exact root identity, descendants and
  grandchildren, child-terminal non-closure, missing/closed parents, parent
  cycles, incomplete-root interleaving, cancellation closure, generation
  reset, and exact pull boundaries. An architecture gate freezes the deleted
  observer APIs and the one pull boundary.

An implementer briefly began five governed-caller repairs after a broad
diagnostic. Those Cut 5 edits were removed before this freeze. In particular,
`dnd/blocks/base_item.py`, `dnd/entities/entity.py`, and
`tests/engine/test_entity_composition.py` are byte-identical to their accepted
Cut 3 hashes. Cut 5's diagnostic failures remain visible and were not hidden by
weakening admission or adding exceptions.

Validation on the frozen candidate:

- complete Cut 4 queue/reducer/scripted/async/architecture file lane:
  `83 passed in 10.84s`;
- migrated direct-journal observer replacements plus complete architecture:
  `71 passed in 36.98s` (five focused engine proofs and 66 architecture
  tests);
- compileall over all 13 candidate members: exit 0;
- repository diff check: clean apart from existing line-ending notices;
- retired observer/batch/reducer APIs: absent from active production and
  current engine tests; the architecture gate contains their names only as
  forbidden literals;
- the separately collected dice module remains blocked by the accepted
  pre-existing missing `dnd.content_system` package; its changed file compiles
  and its callback removal is covered by the same handler-evidence API used by
  the green focused contracts.

Exact Cut 4 candidate members:

```text
dnd/core/events/events_registry.py 50b2a757867d5532ef93b2cbed1fd83b9897209b3eca860aed14e5dbe2f1abf5
dnd/core/base_actions.py 99c6f39d307d4114df926a5dee4e7e5462f61c8718845353ee1bc645504cedc6
dnd/encounters/encounter.py e5b957f298c0c255f4dc351e529d4d93f2dc455305dc7ce323e0e02e99c5fc4e
dnd/event_reduction.py afc60cd7594944ee9628dae77aa85607421080fd21f00a035a0dfe971c629c7b
tests/engine/test_event_lifecycle.py e38879b5dbff4f856b53c472adf447c729a269c9db793c9f94bc3496e70e2a3e
tests/engine/test_event_knowledge_context.py e77013b40451f4f0db86b4564c00ad49e587571a56ff366104c1b5d2bff210af
tests/engine/test_event_knowledge_scripted_encounter.py 6c15fb10392ec93af39497a9107852a141872035ec679566326ea547c2624f3e
tests/engine/test_event_knowledge_async_boundary.py f0998f66765c6571428af01cf1b5f12462c32db66e517cc220374eb28062bca6
tests/engine/test_move_settlement.py be3ddd135f53ebaf303d433204038ff20b09920a7042e6dcaf403d41ed3c804f
tests/engine/test_traversal_connectors.py 718008d9b41d20608a92d4f5f5971f09b62cb94a13f9db1c44eecb1d5853ffab
tests/engine/test_world_edge_identity_and_elevation.py fc3eafe1d5c7e6a60d7161926914d7d3ef4cfcd687ebacac3d6f971e988d0c60
tests/engine/test_dice_event_semantics.py ca8a37087d684c5f4fa730ff4ed4bb9f7a64310dcbde14197f9c04c90a32d855
tests/architecture/test_event_knowledge_context_architecture.py c69150a2d83a3f5c6e560548b71b879c25635af3c716acbfa76aa85e6a84afba
```

`CUT_4_READY_FOR_EXACT_REVIEWS — CUT_5_NOT_AUTHORIZED`

## Superseding Cut 4 strict-kernel repair — 2026-08-29

The first correctness review rejected ledger SHA
`5afcacdeca04b7a6c54f9b26ec252592dd448897222238e9c4361bd0bc0483bd`.
The anti-slop review accepted those bytes, but both reviews are invalidated by
this repair.

Three bounded kernel defects were corrected at their existing owners:

- root identity is assigned only after every admission check succeeds, so a
  rejected late version cannot poison the next valid root;
- every root-lineage version must remain parentless, both at admission and
  during journal-derived pull validation; and
- `phase_to(CANCEL)` delegates to the one `cancel()` path, which always builds
  shared terminal evidence outside an active handler proposal. Cancel facts
  must carry `canceled` and `canceled_from_phase`, and reviewed inert fact
  classes may form only a one-slot `COMPLETION` root.

The pull validator additionally verifies exact concrete class per lineage and
rejects a parented root lineage or malformed cancellation even if stored
journal objects were externally corrupted. No state, compatibility path, or
new abstraction was added.

Direct regressions prove rejection-state purity, root-lineage parentage,
`phase_to(CANCEL)` evidence, fresh-root admission after rejected late facts,
and completion-only inert roots.

Validation after the repair:

- complete Cut 4 queue/reducer/scripted/async/architecture file lane:
  `84 passed in 11.39s`;
- migrated direct-journal observer replacements plus complete architecture:
  `71 passed in 38.53s`;
- repaired member compileall: exit 0;
- repaired member diff check: clean apart from existing line-ending notices.

The other 11 Cut 4 candidate members remain byte-identical. Repaired hashes:

```text
dnd/core/events/events_registry.py fef02d1cf55ab7a5d0d4f78fc86e2bd7f511c423045955fc85244dbf6454eea3
tests/engine/test_event_lifecycle.py 1e8c8bbe2048a5a695beae8fa2ffd25a5c86df7afb04c0aa5b6d2431683c3ed2
```

`CUT_4_REPAIRED_READY_FOR_FRESH_REVIEWS — CUT_5_NOT_AUTHORIZED`

## Superseding Cut 4 inert-child lifecycle repair — 2026-08-29

The fresh correctness review of ledger SHA
`96777a31b15c6f5767645fbc897f69980b180de568466877eee182d766661431`
rejected one remaining lifecycle gap: completion-only inert facts were
enforced for roots but not for parented children. The corresponding anti-slop
acceptance is also invalidated because the candidate bytes changed.

The existing admission and pull validators now apply the same rule to every
inert event, independent of parentage: an inert terminal fact may exist only
at `COMPLETION`. No event kind, state, exception, compatibility path, callback,
or new abstraction was added.

The lifecycle regression now proves all three parented cases explicitly:
`DECLARATION` and `CANCEL` are rejected without poisoning the open tree, while
`COMPLETION` is accepted as a one-slot child and is returned inside the exact
committed root tree.

Validation after this repair:

- complete Cut 4 queue/reducer/scripted/async/architecture file lane:
  `84 passed in 11.33s`;
- repaired member compileall: exit 0;
- repaired member diff check: clean apart from existing line-ending notices.

The other 11 Cut 4 candidate members remain byte-identical. Repaired hashes:

```text
dnd/core/events/events_registry.py 5f9b9710c458602b3924373e2e6065b7109c9259af65860e45240941fd1055ac
tests/engine/test_event_lifecycle.py e541c7db42db1af5c88e8b392bc66c67e206dcda7722e0f914d9bf079b11a993
```

`CUT_4_REPAIRED_READY_FOR_FRESH_REVIEWS — CUT_5_NOT_AUTHORIZED`

## Cut 4 exact-candidate acceptance — 2026-08-29

Both independent reviewers accepted ledger SHA
`ccece8fbf3a87e6207d9fd4615dafae6c1f2ca01b2cdd09a1589d10e94c6235a`
and all 13 exact member hashes without edits:

- correctness/causal-boundary review: **ACCEPT**; it independently reran the
  exact 84-test lane, confirmed global completion-only inert validation at
  admission and pull, and found the previous poisoning, root-parentage, and
  cancellation defects closed;
- anti-slop/dependency/locality review: **ACCEPT**; it independently reran the
  exact 84-test lane and found no callback/observer residue, compatibility
  path, duplicate authority, hidden exception, weakened gate, queue/receipt
  layer, manager/controller/framework, or Cut 5 spillover.

Both reviewers reconfirmed the reviewed hashes after validation. Cut 4 is
accepted. Only the plan-governed caller closure in Cut 5 is authorized next.

`CUT_4_ACCEPTED — CUT_5_AUTHORIZED_ONLY`

## Cut 5 governed active closure candidate — 2026-08-29

The unchanged governed command from Section 3 first ran under strict root
admission as a read-only diagnostic. Its current 304-node union produced
`248 passed, 56 failed`. Every failure was classified at a concrete owner:

- 45 direct-scenario failures exposed post-commit item-location facts using a
  fake terminal-only lifecycle, plus authored wall-torch location parentage to
  an already-completed IGNITE child;
- two combat failures exposed a life-state lifecycle whose declaration,
  execution, and effect were never stored before sensory children referenced
  it;
- five senses failures used completed test roots as condition parents;
- two position tests used arbitrary unregistered parent UUIDs; and
- two movement tests emitted parentless damage while a movement root was
  open.

The repairs were made only at those owners:

- `ItemLocationStateEvent` now explicitly declares the existing inert-fact
  subclass contract. `BaseItem.publish_location_state()` constructs the
  already-committed `COMPLETION` fact directly and publishes it through
  `publish_inert_terminal_fact()`; the fake declaration/execution/effect chain
  is gone.
- Authored wall-torch settlement retains its IGNITE ordering proof but parents
  the later item-location fact directly to the still-open
  `WorldInitializedEvent` effect. The test proves IGNITE completion precedes
  the item fact and the world completion remains last.
- `Entity._transition_life_state()` stores its non-vetoable declaration,
  execution, and effect through existing publication paths, commits state and
  derived consequences under the stored effect UUID, and publishes completion
  only after sensory children.
- Tests now use stored open root effects, explicit root completion, detached
  JSON round-trips for completed non-inert events, and real parented damage
  lifecycles. One local `open_root_action()` helper removes mechanical setup
  repetition while every terminal remains explicit.

No queue/reducer rule, callback, exception, allowlist, compatibility path,
manager/controller, receipt, context manager, or new production abstraction
was added.

Frozen validation:

- governed active collection: 304 sorted unique nodes, normalized SHA-256
  `c56abccdeb3a8bcd4302cb00bda19bc0b96ad931fbebe062578f4751096c0eac`;
- independent exact governed run: `304 passed in 138.91s`;
- standalone architecture run by the implementer: `60 passed in 30.20s`;
- complete architecture is also part of the independent 304-node run;
- compileall over all eight Cut 5 members: exit 0;
- scoped diff check: clean apart from existing line-ending notices;
- retired callback/observer/batch names remain only as forbidden literals in
  architecture gates.

Exact Cut 5 candidate members:

```text
dnd/core/events/item_events.py 8d95be6dc2e5944f96c9848cba73ce477bc616a5a4bdd87c1c6cc18efbb57d29
dnd/blocks/base_item.py 4c64112749d28b7aecbeb30fec6ae35df3c717cdd794e2843ffd381a613ae877
dnd/content/scenarios/battlefield_builders.py e849bee67874db0a0a5602b03912bd59b4b1fcdaef64f8b14afaac372a61c4b8
dnd/entities/entity.py b03a7189b2542fc6f29613e50d28b472d15117bbda2db06e4ca6fc1b5fead53e
tests/engine/test_direct_scenario_deployment.py bd572cb6af90e593ef8ecd6a98c939c8af3b1aa10a4907ba02a08a2c46073163
tests/engine/test_senses_light_stealth.py 84bf5d1775b35e098d685640a88fb295051b24dbc41bdc06b35519590360ddd9
tests/engine/test_action_cost_and_position_commit.py c0c457e7d17dd2f236155af0fec5b7aa87b0ef6706b10959673f59821b505693
tests/engine/test_move_settlement.py e4ca714149c7a9ea71a12d749edd88dcb0604e3f911bc23a0ad5fdb4303fb1c2
```

`CUT_5_READY_FOR_EXACT_REVIEWS — CUT_6_NOT_AUTHORIZED`

## Superseding Cut 5 non-vetoability repair — 2026-08-29

The first Cut 5 correctness review rejected ledger SHA
`5fb91836ab6937833cbe37d92b3f8c889b9b69ea02a07a4d03ea7d2e7c6f69ca`.
The anti-slop review accepted those bytes, but both reviews are invalidated by
this repair.

Two concrete committed-state lifecycles still constructed execution/effect
through ordinary dispatching publication. A handler could therefore cancel or
rewrite `WorldInitializedEvent` or `LifeStateChangeEvent` after their owning
state was already committed.

Both owners now use only the existing `publish_preflighted()` storage
boundary. Each next execution/effect version is constructed unregistered with
the ordinary `phase_to()` value transformation, then stored directly without
handler dispatch:

- world initialization stores declaration, execution, and effect
  non-vetoably, resolves authored children under the stored effect, and stores
  completion last;
- life-state transition stores declaration, execution, and effect
  non-vetoably, commits authoritative state and derived children beneath the
  stored effect, finalizes its terminal evidence unregistered, and stores
  completion last.

No mode, flag, helper API, callback, exception, or new publication path was
added. The life-state docstring now states the actual full non-vetoable
lifecycle.

Two public phase-by-attempt matrices cover execution/effect crossed with
cancel/rewrite for both families. All eight cases prove that the attempted
handlers are not invoked, every stored phase retains authoritative payload,
state agrees with the journal, and completion exists.

Repaired validation:

- governed active collection: 312 sorted unique nodes, normalized SHA-256
  `33d553d576e40eda58ff0dc010753ff68b621fb635e9be81653ff7fbf37069c7`;
- implementer governed run: `312 passed in 121.04s`;
- independent exact governed run after the doc correction:
  `312 passed in 122.07s`;
- standalone architecture: `60 passed in 28.95s`;
- compileall over all nine Cut 5 members: exit 0;
- scoped diff check: clean apart from existing line-ending notices;
- strict queue kernel remains byte-identical at
  `5f9b9710c458602b3924373e2e6065b7109c9259af65860e45240941fd1055ac`.

Exact repaired Cut 5 candidate members:

```text
dnd/core/events/item_events.py 8d95be6dc2e5944f96c9848cba73ce477bc616a5a4bdd87c1c6cc18efbb57d29
dnd/blocks/base_item.py 4c64112749d28b7aecbeb30fec6ae35df3c717cdd794e2843ffd381a613ae877
dnd/content/scenarios/battlefield_builders.py d24505147288b9dfd8afcfa93b9674a60af6988d1e430c4f062a5d39a87e1b7a
dnd/entities/entity.py 022d22f8c42198b13968125771994587b5920af6b86afa65222b2c62929ef70b
tests/engine/test_direct_scenario_deployment.py 7ddf9778ee914fb9b614b29aac12e6585ccbfac2966c586ffdf6df138e3c877f
tests/engine/test_senses_light_stealth.py 84bf5d1775b35e098d685640a88fb295051b24dbc41bdc06b35519590360ddd9
tests/engine/test_action_cost_and_position_commit.py c0c457e7d17dd2f236155af0fec5b7aa87b0ef6706b10959673f59821b505693
tests/engine/test_move_settlement.py e4ca714149c7a9ea71a12d749edd88dcb0604e3f911bc23a0ad5fdb4303fb1c2
tests/engine/test_combat_actions.py aa5126d575b03f88df56483da7315edef5268193f375202cab2f8ce01ab4c18e
```

`CUT_5_REPAIRED_READY_FOR_FRESH_REVIEWS — CUT_6_NOT_AUTHORIZED`
