# Gameplay presentation bridge audit

This report excludes sprite/art quality. `BROKEN` means a concrete current bridge defect; `NOT_SCANNED` means only that this tool needs updating. Current `projectile`/`touch`/`direct`/`missile_volley` labels below name the renderer-shaped contract being audited; they are not endorsed as the neutral target contract. The action hard-cut plan deletes backend spell route and morphology authority.

## Run

```bash
.venv/bin/python -B tools/audit_presentation_bridge.py \
  --markdown tools/PRESENTATION_BRIDGE_AUDIT.md \
  --json tools/PRESENTATION_BRIDGE_AUDIT.json
```

The strict command writes both reports and exits non-zero for any `BROKEN`, `NOT_SCANNED`, or scanner-error result. Add `--allow-broken` only when deliberately refreshing the known-defect snapshot.

## Facts

- `public_content_rows`: 671
- `public_dependency_closure_rows`: 699
- `public_action_and_reaction_rows`: 91
- `public_spell_rows`: 116
- `public_runtime_condition_rows`: 141
- `public_reachable_presentation_runtime_identities`: 340
- `reachable_runtime_identities_without_frontend_binding`: 2
- `server_cue_kinds`: 18
- `runtime_intent_kinds`: 25
- `deterministic_identity_frame_blocking_entry_points`: 13
- `deterministic_zero_application_spell_entry_points`: 4
- `known_deterministic_frame_blocking_entry_points`: 17
- `privacy_variant_frame_blocking_spells`: 67
- `public_spells_with_known_frame_blocking_variant`: 71

## Static definition-binding closure by category

`CONNECTED` here means the exact public definition has a compiled client binding. It is not a runtime verdict; transport variants, identity loss, and continuity are reported separately below.

| Category | Total | Status counts |
|---|---:|---|
| `class_and_subclass_actions` | 19 | CONNECTED=19 |
| `conditions` | 141 | CONNECTED=109, INTENTIONAL_STATE_ONLY=32 |
| `environment_actions` | 12 | CONNECTED=12 |
| `item_actions` | 7 | CONNECTED=7 |
| `monster_trait_and_configured_actions` | 15 | CONNECTED=15 |
| `movement` | 4 | CONNECTED=4 |
| `origin_actions` | 1 | CONNECTED=1 |
| `reactions` | 8 | CONNECTED=8 |
| `spell_followup_actions` | 12 | CONNECTED=12 |
| `spells` | 116 | CONNECTED=116 |
| `universal_and_base_actions` | 13 | CONNECTED=13 |

## Runtime bridge defects by category

Counts in parentheses are affected identities/variants for that check; they are not added together because checks can overlap.

| Category | Broken checks | Audit gaps |
|---|---|---|
| `audit_authority` | `authoring.missing_definition_gate` (not independently enumerated) | — |
| `class_and_monster_passive_procs` | — | `passive_proc.identity` |
| `environment_and_equipment` | `equipment.transition_coverage` (1) | — |
| `item_actions` | `items.item_action_contract_authority` (3) | — |
| `item_owned_spell_routes` | `item.acid_flask_spell_surface` (1) | — |
| `monster_trait_and_configured_actions` | `monster.multiattack_identity` (10), `direct_apply_site.multiattackaction.apply` (10) | — |
| `movement` | `direct_apply_site.commandfleeeffect.activate.commanded.turn` (1), `direct_apply_site.eyebitepanickedeffect.create.flee.handler.processor` (1), `movement.connector_identity` (1), `movement.anchor_elevation` (1), `movement.cross_head_body_continuity` (1) | — |
| `reactions` | `direct_apply_site.retaliation.processor` (1) | — |
| `spell_followup_actions` | `direct_apply_site.sunbeam.apply` (1), `direct_apply_site.eyebite.apply` (1), `direct_apply_site.telekinesis.apply` (1) | — |
| `spells` | `direct_apply_site.truestrike.apply` (1), `spells.redacted_target_cardinality.projectile` (17), `spells.redacted_target_cardinality.touch` (24), `spells.redacted_target_cardinality.direct` (26), `spells.position_application_routes` (3), `spells.successful_zero_application` (4), `spells.aoe_geometry_fidelity.cone` (5), `spells.aoe_geometry_fidelity.line` (3), `spells.aoe_geometry_fidelity.cylinder` (3), `spells.true_strike_wire_id` (2) | — |
| `systemic` | `definitions.reachable_runtime_identity_gap` (2), `state_only.position_settlement` (not independently enumerated) | — |
| `universal_and_base_actions` | `direct_apply_site.execute.drop` (1), `actions.shove_contract_authority` (1) | — |

## Exact findings

| Status | Category | Impact | Finding | Affected |
|---|---|---|---|---:|
| **CONNECTED** | `systemic` | `structural` | `structure.cue_to_mapper` — 18 canonical cue kinds; registry missing/extra=[]/[]; mapper missing/extra=[]/[]; extraction_ready=True | — |
| **CONNECTED** | `systemic` | `structural` | `structure.intent_to_executor` — 25 ClipIntent discriminants; executor missing/extra=[]/[]; extraction_ready=True | — |
| **CONNECTED** | `systemic` | `structural` | `definitions.action_recipe_closure` — The real bundle compiler validated all 91 exact public action/reaction definitions with one recipe or explicit movement disposition. Runtime identity propagation is audited separately. | — |
| **CONNECTED** | `spells` | `structural` | `spells.generated_geometry_route` — NeuroClient's real compiler materialized structurally valid data-driven recipes for all 116 backend spell rows without warnings (statuses={'authored': 2, 'generated': 114}); generated Pixi geometry is a first-class route and a spritesheet is not required. Global spell cue and CastIntent dispatcher closure is audited separately. | — |
| **BROKEN** | `systemic` | `frame_blocking` | `definitions.reachable_runtime_identity_gap` — Dependency traversal from all 671 public declarations reaches 340 action/reaction/spell/condition runtime identities. Exact frontend bindings are missing for 2: ['content.neurodragon:spell:spell.acid_flask@1#e4d439f0a982', 'content.srd_5_1_cc:action:action.monster.multiattack@1#b348fe0a75aa']. | 2 |
| **BROKEN** | `monster_trait_and_configured_actions` | `frame_blocking` | `monster.multiattack_identity` — All configured Multiattacks lose their public configured_action_ref; the root exposes an internal implementation ref with no frontend binding, and nested Attacks are unattributed. | 10 |
| **CONNECTED** | `systemic` | `audit_authority` | `actions.direct_apply_site_discovery` — AST discovery found 192 BaseAction descendants and 10 direct constructor-to-apply sites; the checked disposition ledger has exact set equality=True. | — |
| **BROKEN** | `universal_and_base_actions` | `semantic_omission` | `direct_apply_site.execute.drop` — The direct Drop instance is not admitted through the binding gateway. | 1 |
| **BROKEN** | `reactions` | `frame_blocking` | `direct_apply_site.retaliation.processor` — The emitted nested Attack has no exact authored reaction attribution. | 1 |
| **BROKEN** | `monster_trait_and_configured_actions` | `frame_blocking` | `direct_apply_site.multiattackaction.apply` — The emitted child Attack loses the selected configured Multiattack identity. | 10 |
| **CONNECTED** | `reactions` | `connected` | `direct_apply_site.opportunity.attack.processor` — The processor explicitly copies the active reaction binding before apply. | 1 |
| **BROKEN** | `movement` | `semantic_omission` | `direct_apply_site.commandfleeeffect.activate.commanded.turn` — Movement still renders through its context-owned route, but the authored Command cause identity is omitted. | 1 |
| **BROKEN** | `spell_followup_actions` | `semantic_omission` | `direct_apply_site.sunbeam.apply` — The initial follow-up action is directly applied without its action binding. | 1 |
| **BROKEN** | `spells` | `frame_blocking` | `direct_apply_site.truestrike.apply` — The nested Attack emits without the enclosing True Strike attribution. | 1 |
| **BROKEN** | `movement` | `semantic_omission` | `direct_apply_site.eyebitepanickedeffect.create.flee.handler.processor` — Dash state survives, but the authored Eyebite cause identity is omitted. | 1 |
| **BROKEN** | `spell_followup_actions` | `semantic_omission` | `direct_apply_site.eyebite.apply` — The initial follow-up action is directly applied without its action binding. | 1 |
| **BROKEN** | `spell_followup_actions` | `semantic_omission` | `direct_apply_site.telekinesis.apply` — The initial follow-up action is directly applied without its action binding. | 1 |
| **BROKEN** | `item_owned_spell_routes` | `frame_blocking` | `item.acid_flask_spell_surface` — Acid Flask emits a private/OBSERVED spell behavior absent from the frontend spell definitions, so no draft can be resolved. | 1 |
| **BROKEN** | `spells` | `conditional_frame_blocking` | `spells.redacted_target_cardinality.projectile` — The server contract/projector permit 17 projectile spell definitions to reach an observer with caster identity but targets=[] after per-target privacy filtering; this is a source-derived conditional variant set, not 17 replayed executions. The real client mapper probe returned {'accepted': False, 'error': '[subjectivePresentationMapper] probe:projectile:fire_bolt has no entity target supported by CastIntent'}. | 17 |
| **BROKEN** | `spells` | `conditional_frame_blocking` | `spells.redacted_target_cardinality.touch` — The server contract/projector permit 24 touch spell definitions to reach an observer with caster identity but targets=[] after per-target privacy filtering; this is a source-derived conditional variant set, not 24 replayed executions. The real client mapper probe returned {'accepted': False, 'error': '[subjectivePresentationMapper] probe:touch:cure_wounds touch delivery has no entity target'}. | 24 |
| **BROKEN** | `spells` | `conditional_frame_blocking` | `spells.redacted_target_cardinality.direct` — The server contract/projector permit 26 direct spell definitions to reach an observer with caster identity but targets=[] after per-target privacy filtering; this is a source-derived conditional variant set, not 26 replayed executions. The real client mapper probe returned {'accepted': False, 'error': '[subjectivePresentationMapper] probe:direct:healing_word direct delivery has no application'}. | 26 |
| **BROKEN** | `spells` | `contract_variant_frame_blocking` | `spells.position_application_routes` — SpellTargetPresentation permits entity-or-position applications and the server can synthesize a position application from an owned spatial effect. Real client mapper probes={'touch': {'accepted': False, 'error': '[subjectivePresentationMapper] probe:touch:cure_wounds touch delivery has no entity target'}, 'projectile': {'accepted': False, 'error': '[subjectivePresentationMapper] probe:projectile:fire_bolt has no entity target supported by CastIntent'}, 'missile_volley': {'accepted': False, 'error': '[subjectivePresentationMapper] probe:missile_volley:magic_missile has a position-only missile application unsupported by CastIntent'}, 'direct': {'accepted': True, 'intentTypes': ['cast'], 'deliveries': ['position']}}; rejected routes=['missile_volley', 'projectile', 'touch']. | 3 |
| **BROKEN** | `spells` | `frame_blocking` | `spells.successful_zero_application` — The source-derived non-entity/non-self route set is executed through canonical projection. catalog_routes=['spell.continual_flame', 'spell.dimension_door', 'spell.heroes_feast', 'spell.thaumaturgy']; probe={'spell.thaumaturgy': [('direct', 0)], 'spell.continual_flame': [('touch', 0)], 'spell.dimension_door': [('direct', 0)], 'spell.heroes_feast': [('direct', 0)]}; route_set_drift=[]; client_mapper_probes={'spell.thaumaturgy': [{'accepted': False, 'error': '[subjectivePresentationMapper] probe:direct:healing_word direct delivery has no application'}], 'spell.continual_flame': [{'accepted': False, 'error': '[subjectivePresentationMapper] probe:touch:cure_wounds touch delivery has no entity target'}], 'spell.dimension_door': [{'accepted': False, 'error': '[subjectivePresentationMapper] probe:direct:healing_word direct delivery has no application'}], 'spell.heroes_feast': [{'accepted': False, 'error': '[subjectivePresentationMapper] probe:direct:healing_word direct delivery has no application'}]}; client_probe_drift=[]. The client rejects these ordinary successful zero-application frames. | 4 |
| **BROKEN** | `spells` | `authoritative_data_dropped` | `spells.aoe_geometry_fidelity.cone` — cone AoE executes, but authoritative angle_degrees is not closed contract -> mapper -> CastIntent -> AoeFx; missing=['mapper', 'CastIntent', 'AoeFx options', 'AoeFx consumption']. | 5 |
| **BROKEN** | `spells` | `authoritative_data_dropped` | `spells.aoe_geometry_fidelity.line` — line AoE executes, but authoritative width_feet is not closed contract -> mapper -> CastIntent -> AoeFx; missing=['mapper', 'CastIntent', 'AoeFx options', 'AoeFx consumption']. | 3 |
| **BROKEN** | `spells` | `authoritative_data_dropped` | `spells.aoe_geometry_fidelity.cylinder` — cylinder AoE executes, but authoritative height_feet is not closed contract -> mapper -> CastIntent -> AoeFx; missing=['mapper', 'CastIntent', 'AoeFx options', 'AoeFx consumption']. | 3 |
| **BROKEN** | `spells` | `transport_identity_drift` | `spells.true_strike_wire_id` — True Strike variants emit spell_id=true_strike_melee/true_strike_ranged instead of catalog ID true_strike. Current client mapping survives only because it selects by behavior ContentRef. | 2 |
| **BROKEN** | `universal_and_base_actions` | `contract_authority_drift` | `actions.shove_contract_authority` — Shove transports actor/timing fields that the client ignores in favor of the exact ContentRef recipe; ignored fields=['actor_clip', 'contact_frame', 'playback_speed']. | 1 |
| **BROKEN** | `item_actions` | `contract_authority_drift` | `items.item_action_contract_authority` — Item Action transports actor/timing/visibility fields that the client ignores in favor of the exact ContentRef recipe; ignored fields=['actor_clip', 'effect_frame', 'hidden_slots', 'playback_speed']. | 3 |
| **BROKEN** | `movement` | `authoritative_data_dropped` | `movement.connector_identity` — Connector identity reaches MoveIntent but the locomotion executor consumes no connector presentation key/kind/revision; it executes as ordinary planar movement. | 1 |
| **BROKEN** | `movement` | `authoritative_data_dropped` | `movement.anchor_elevation` — Elevation reaches locomotion anchors but neither path movement nor JumpClip consumes it; vertical motion is not bridged from the backend anchor data. | 1 |
| **BROKEN** | `movement` | `runtime_continuity` | `movement.cross_head_body_continuity` — One server move can arrive as independent observation heads; each head ends Walking and deletes the locomotion session, so the client restarts the body cycle. | 1 |
| **BROKEN** | `environment_and_equipment` | `coverage_gate` | `equipment.transition_coverage` — SwitchWeapon executes from the authored equipment_transition context, but bundle coverage omits that context and reports equipment.structural instead. | 1 |
| **NOT_SCANNED** | `class_and_monster_passive_procs` | `audit_boundary` | `passive_proc.identity` — The catalog does not identify which class-feature/trait handlers produce gameplay activations, and HandlerDispatchEvidence omits the handler's existing BehaviorBinding. A static list would be a handwritten guess, so this tool refuses to claim exhaustive passive-proc bridge coverage. Add the existing binding snapshot to dispatch evidence, then this audit can join effected handlers to projected attribution without a new subsystem. | — |
| **CONNECTED** | `conditions` | `structural` | `conditions.explicit_dispositions` — All 141 public runtime condition identities have exact client dispositions; 32 are explicitly state-only. | — |
| **INTENTIONAL_STATE_ONLY** | `environment_and_encounter` | `structural` | `world.reducer_owned_cues` — The real shared semantic classifier marks door, light, spatial-effect lifecycle, equipment-none, and non-visual encounter transitions as reducer/replica-owned; probes={'door': 'door_reducer_state', 'light': 'light_reducer_state', 'spatial_effect': 'spatial_effect_reducer_state', 'equipment_none': 'unequipped_loadout_replacement', 'encounter_start': 'encounter_reducer_transition', 'encounter_turn_start': None}. | 5 |
| **BROKEN** | `systemic` | `render_state_divergence` | `state_only.position_settlement` — Entity-position settlement is limited to cue-empty state-only frames; a nonempty state-only cue plus position patch can leave the scene stale. | — |
| **BROKEN** | `audit_authority` | `coverage_gate` | `authoring.missing_definition_gate` — The bundle computes missingDefinitionRefs and bootstrap reports a control-plane diagnostic, but the bundle is still published when every cue kind has some binding. Missing exact definition ownership is diagnosed without being enforced as an authoring/install gate. | — |

## Affected IDs

- `definitions.reachable_runtime_identity_gap`: `content.neurodragon:spell:spell.acid_flask@1#e4d439f0a982`, `content.srd_5_1_cc:action:action.monster.multiattack@1#b348fe0a75aa`
- `monster.multiattack_identity`: `action.monster.multiattack.bandit_captain.melee`, `action.monster.multiattack.bandit_captain.ranged`, `action.monster.multiattack.cult_fanatic`, `action.monster.multiattack.knight`, `action.monster.multiattack.scout.longbow`, `action.monster.multiattack.scout.shortsword`, `action.monster.multiattack.spy`, `action.monster.multiattack.thug`, `action.monster.multiattack.veteran.melee`, `action.monster.multiattack.veteran.ranged`
- `direct_apply_site.execute.drop`: `action.core.drop`
- `direct_apply_site.retaliation.processor`: `reaction.class_feature.barbarian.retaliation`
- `direct_apply_site.multiattackaction.apply`: `action.monster.multiattack.bandit_captain.melee`, `action.monster.multiattack.bandit_captain.ranged`, `action.monster.multiattack.cult_fanatic`, `action.monster.multiattack.knight`, `action.monster.multiattack.scout.longbow`, `action.monster.multiattack.scout.shortsword`, `action.monster.multiattack.spy`, `action.monster.multiattack.thug`, `action.monster.multiattack.veteran.melee`, `action.monster.multiattack.veteran.ranged`
- `direct_apply_site.opportunity.attack.processor`: `reaction.opportunity_attack`
- `direct_apply_site.commandfleeeffect.activate.commanded.turn`: `spell.command`
- `direct_apply_site.sunbeam.apply`: `action.spell.sunbeam.strike`
- `direct_apply_site.truestrike.apply`: `spell.true_strike`
- `direct_apply_site.eyebitepanickedeffect.create.flee.handler.processor`: `spell.eyebite`
- `direct_apply_site.eyebite.apply`: `action.spell.eyebite.strike`
- `direct_apply_site.telekinesis.apply`: `action.spell.telekinesis.grab`
- `item.acid_flask_spell_surface`: `consumable.acid_flask`
- `spells.redacted_target_cardinality.projectile`: `spell.acid_splash`, `spell.blight`, `spell.call_lightning`, `spell.chain_lightning`, `spell.chill_touch`, `spell.disintegrate`, `spell.eldritch_blast`, `spell.finger_of_death`, `spell.fire_bolt`, `spell.guiding_bolt`, `spell.harm`, `spell.magic_missile`, `spell.poison_spray`, `spell.ray_of_frost`, `spell.sacred_flame`, `spell.scorching_ray`, `spell.telekinesis`
- `spells.redacted_target_cardinality.touch`: `spell.bestow_curse`, `spell.cure_wounds`, `spell.darkvision`, `spell.death_ward`, `spell.enhance_ability`, `spell.freedom_of_movement`, `spell.greater_invisibility`, `spell.greater_restoration`, `spell.guidance`, `spell.inflict_wounds`, `spell.invisibility`, `spell.jump`, `spell.lesser_restoration`, `spell.light`, `spell.mage_armor`, `spell.protection_from_energy`, `spell.protection_from_poison`, `spell.regenerate`, `spell.remove_curse`, `spell.resistance`, `spell.shocking_grasp`, `spell.stoneskin`, `spell.true_seeing`, `spell.true_strike`
- `spells.redacted_target_cardinality.direct`: `spell.aegis_spark`, `spell.aid`, `spell.bane`, `spell.banishment`, `spell.beacon_of_hope`, `spell.bless`, `spell.blindness_deafness`, `spell.charm_person`, `spell.command`, `spell.counterspell`, `spell.divine_word`, `spell.enlarge_reduce`, `spell.haste`, `spell.heal`, `spell.healing_word`, `spell.hellish_rebuke`, `spell.hold_monster`, `spell.hold_person`, `spell.mass_heal`, `spell.mass_healing_word`, `spell.necrotic_bless`, `spell.power_word_kill`, `spell.power_word_stun`, `spell.prayer_of_healing`, `spell.sanctuary`, `spell.shield_of_faith`
- `spells.position_application_routes`: `spell.delivery.missile_volley:position`, `spell.delivery.projectile:position`, `spell.delivery.touch:position`
- `spells.successful_zero_application`: `spell.continual_flame`, `spell.dimension_door`, `spell.heroes_feast`, `spell.thaumaturgy`
- `spells.aoe_geometry_fidelity.cone`: `spell.burning_hands`, `spell.color_spray`, `spell.cone_of_cold`, `spell.fear`, `spell.prismatic_spray`
- `spells.aoe_geometry_fidelity.line`: `spell.gust_of_wind`, `spell.lightning_bolt`, `spell.sunbeam`
- `spells.aoe_geometry_fidelity.cylinder`: `spell.flame_strike`, `spell.ice_storm`, `spell.sleet_storm`
- `spells.true_strike_wire_id`: `true_strike_melee`, `true_strike_ranged`
- `actions.shove_contract_authority`: `action.shove`
- `items.item_action_contract_authority`: `action.item.potion_greater_invisibility.drink`, `action.item.potion_haste.drink`, `action.item.potion_healing.drink`
- `movement.connector_identity`: `movement.connector.presentation_key`
- `movement.anchor_elevation`: `movement.anchor.elevation_feet`
- `movement.cross_head_body_continuity`: `movement.multi_step_across_observation_heads`
- `equipment.transition_coverage`: `equipment_transition`
- `world.reducer_owned_cues`: `door`, `light`, `spatial_effect`, `equipment:none`, `encounter:structural`

## Evidence

- `structure.cue_to_mapper`
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/server/player_replication_contract.py:1609` — canonical cue union
  - `/home/tommaso/Dev/NeuroClient/app/src/render/subjectivePresentationMapper.ts:914` — exhaustive client mapper
- `structure.intent_to_executor`
  - `/home/tommaso/Dev/NeuroClient/app/src/render/types.ts:774` — runtime intent union
  - `/home/tommaso/Dev/NeuroClient/app/src/render/dispatcher.ts:61` — intent executor switch
- `definitions.action_recipe_closure`
  - `/home/tommaso/Dev/NeuroClient/app/src/render/data/animation/contentActionPresentationRecipes.json:4` — exact action recipes
  - `/home/tommaso/Dev/NeuroClient/app/src/render/data/animation/actionPresentationDispositions.json:4` — explicit movement dispositions
- `spells.generated_geometry_route`
  - `/home/tommaso/Dev/NeuroClient/app/src/render/spellAuthoring/generatedBaseline.ts:31` — catalog row -> generated recipe
  - `/home/tommaso/Dev/NeuroClient/app/src/render/spellAuthoring/runtimeResolver.ts:16` — recipe -> runtime presentation
- `monster.multiattack_identity`
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/dnd/core/base_actions.py:795` — identity exists on action discovery model
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/dnd/monsters/traits.py:552` — composite runtime action
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/server/player_replication/mapper.py:2620` — projection reads behavior binding only
- `direct_apply_site.execute.drop`
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/dnd/actions_functional.py:571` — source-discovered dnd.actions.Drop constructor -> apply
- `direct_apply_site.retaliation.processor`
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/dnd/classes/barbarian.py:494` — source-discovered dnd.actions.Attack constructor -> apply
- `direct_apply_site.multiattackaction.apply`
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/dnd/monsters/traits.py:604` — source-discovered dnd.actions.Attack constructor -> apply
- `direct_apply_site.opportunity.attack.processor`
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/dnd/reactions.py:79` — source-discovered dnd.actions.Attack constructor -> apply
- `direct_apply_site.commandfleeeffect.activate.commanded.turn`
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/dnd/spells/enchantment.py:1708` — source-discovered dnd.actions.Move constructor -> apply
- `direct_apply_site.sunbeam.apply`
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/dnd/spells/evocation.py:3100` — source-discovered dnd.spells.evocation.SunbeamStrike constructor -> apply
- `direct_apply_site.truestrike.apply`
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/dnd/spells/evocation.py:3516` — source-discovered dnd.actions.Attack constructor -> apply
- `direct_apply_site.eyebitepanickedeffect.create.flee.handler.processor`
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/dnd/spells/necromancy.py:1272` — source-discovered dnd.actions.Dash constructor -> apply
- `direct_apply_site.eyebite.apply`
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/dnd/spells/necromancy.py:1544` — source-discovered dnd.spells.necromancy.EyebiteStrike constructor -> apply
- `direct_apply_site.telekinesis.apply`
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/dnd/spells/transmutation.py:1855` — source-discovered dnd.spells.transmutation.TelekinesisGrab constructor -> apply
- `item.acid_flask_spell_surface`
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/dnd/items/spell_items.py:204` — private item spell
  - `/home/tommaso/Dev/NeuroClient/app/src/render/spellAuthoring/runtimeResolver.ts:27` — exact frontend catalog join
- `spells.redacted_target_cardinality.projectile`
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/server/player_replication/mapper.py:2284` — target applications projected independently
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/server/player_replication/mapper.py:2290` — per-target privacy filter
  - `/home/tommaso/Dev/NeuroClient/app/src/render/subjectivePresentationMapper.ts:1692` — real zero-target projectile mapper probe
- `spells.redacted_target_cardinality.touch`
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/server/player_replication/mapper.py:2284` — target applications projected independently
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/server/player_replication/mapper.py:2290` — per-target privacy filter
  - `/home/tommaso/Dev/NeuroClient/app/src/render/subjectivePresentationMapper.ts:1692` — real zero-target touch mapper probe
- `spells.redacted_target_cardinality.direct`
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/server/player_replication/mapper.py:2284` — target applications projected independently
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/server/player_replication/mapper.py:2290` — per-target privacy filter
  - `/home/tommaso/Dev/NeuroClient/app/src/render/subjectivePresentationMapper.ts:1692` — real zero-target direct mapper probe
- `spells.position_application_routes`
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/server/player_replication_contract.py:1120` — entity-or-position application contract
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/server/player_replication/mapper.py:3293` — spatial-effect position application synthesis
  - `/home/tommaso/Dev/NeuroClient/app/src/render/subjectivePresentationMapper.ts:1692` — real position-application mapper probes
- `spells.successful_zero_application`
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/tests/manual/test_121_canonical_presentation_mapper.py:318` — real EventQueue -> canonical projection
  - `/home/tommaso/Dev/NeuroClient/app/src/render/subjectivePresentationMapper.ts:1692` — real client mapper probes
- `spells.aoe_geometry_fidelity.cone`
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/server/player_replication_contract.py:1047` — authoritative cone field
  - `/home/tommaso/Dev/NeuroClient/app/src/render/subjectivePresentationMapper.ts:2649` — client projection
  - `/home/tommaso/Dev/NeuroClient/app/src/render/types.ts:556` — renderer intent
  - `/home/tommaso/Dev/NeuroClient/app/src/render/clips/AoeFx.ts:33` — renderer input
- `spells.aoe_geometry_fidelity.line`
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/server/player_replication_contract.py:1061` — authoritative line field
  - `/home/tommaso/Dev/NeuroClient/app/src/render/subjectivePresentationMapper.ts:2649` — client projection
  - `/home/tommaso/Dev/NeuroClient/app/src/render/types.ts:556` — renderer intent
  - `/home/tommaso/Dev/NeuroClient/app/src/render/clips/AoeFx.ts:33` — renderer input
- `spells.aoe_geometry_fidelity.cylinder`
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/server/player_replication_contract.py:1092` — authoritative cylinder field
  - `/home/tommaso/Dev/NeuroClient/app/src/render/subjectivePresentationMapper.ts:2649` — client projection
  - `/home/tommaso/Dev/NeuroClient/app/src/render/types.ts:556` — renderer intent
  - `/home/tommaso/Dev/NeuroClient/app/src/render/clips/AoeFx.ts:33` — renderer input
- `spells.true_strike_wire_id`
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/dnd/actions.py:6407` — wire ID derived from display name
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/dnd/spells/evocation.py:3543` — variant display names
- `actions.shove_contract_authority`
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/server/player_replication_contract.py:1260` — transported shove fields
  - `/home/tommaso/Dev/NeuroClient/app/src/render/subjectivePresentationMapper.ts:1379` — client recipe selection
- `items.item_action_contract_authority`
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/server/player_replication_contract.py:1197` — transported item fields
  - `/home/tommaso/Dev/NeuroClient/app/src/render/subjectivePresentationMapper.ts:1426` — client recipe selection
- `movement.connector_identity`
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/server/player_replication_contract.py:794` — server identity
  - `/home/tommaso/Dev/NeuroClient/app/src/render/clips/MoveClip.ts:11` — movement executor
- `movement.anchor_elevation`
  - `/home/tommaso/Dev/NeuroClient/app/src/render/types.ts:288` — client carries elevation
  - `/home/tommaso/Dev/NeuroClient/app/src/render/clips/JumpClip.ts:20` — jump executor
- `movement.cross_head_body_continuity`
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/tests/manual/test_122_canonical_replication_runtime.py:494` — one move is delivered as three observation heads
  - `/home/tommaso/Dev/NeuroClient/app/src/render/clips/MoveClip.ts:70` — per-head walking settlement
  - `/home/tommaso/Dev/NeuroClient/app/src/render/LocomotionSessionExecutor.ts:62` — per-head session retirement
- `equipment.transition_coverage`
  - `/home/tommaso/Dev/NeuroClient/app/src/render/actionContextPresentation.ts:25` — authored runtime context
  - `/home/tommaso/Dev/NeuroClient/app/src/render/presentationBundle.ts:202` — compiled context coverage
  - `/home/tommaso/Dev/NeuroClient/app/src/render/subjectivePresentationMapper.ts:2809` — reported provenance
- `passive_proc.identity`
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/dnd/core/events.py:1545` — effective presentation retained only for reactions
  - `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/server/player_replication/mapper.py:2927` — handler evidence projection
- `conditions.explicit_dispositions`
  - `/home/tommaso/Dev/NeuroClient/app/src/render/data/animation/conditionPresentation.json:4` — condition disposition registry
- `world.reducer_owned_cues`
  - `/home/tommaso/Dev/NeuroClient/app/src/render/subjectivePresentationMapper.ts:947` — state-only mapper branch
  - `/home/tommaso/Dev/NeuroClient/app/src/render/subjectivePresentationMapper.ts:956` — state-only mapper branch
- `state_only.position_settlement`
  - `/home/tommaso/Dev/NeuroClient/app/src/engine/eventIngestion.ts:417` — over-narrow settlement predicate
- `authoring.missing_definition_gate`
  - `/home/tommaso/Dev/NeuroClient/app/src/render/presentationBundle.ts:465` — exact missing rows computed
  - `/home/tommaso/Dev/NeuroClient/app/src/render/presentationBundle.ts:473` — aggregate-only compile gate
  - `/home/tommaso/Dev/NeuroClient/app/src/render/presentationBundleBootstrap.ts:247` — diagnostic-only bootstrap handling

## Audit gaps

- At least one audit surface is NOT_SCANNED; the default command fails rather than pretending the report is exhaustive.
