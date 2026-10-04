# Native and AI feature trace — 4 October 2026

This is an inventory for human scope/slop review, **not a blanket approval or a claim that the whole spell plan is complete**. It records every changed native/AI file and groups its changes by observable behavior, including shared CORE changes and repairs exposed by integration. “Authority” identifies the requested plan packet or bounded correction; code existing in the checkout is not itself authority.

Comparison: commit `95a47cd5ca508838bce8a2e67d6fe1fc591ce4e6` → the current uncommitted working tree, captured `2026-10-04T11:11:33.784755+00:00`. HEAD still equals that baseline. Coverage is **59 files: 58 tracked modifications and 1 new passive module**, `dnd/types/class_features.py`. There are three changed files under `dnd/ai/` and none under a separate top-level `ai/`. The **50 feature entries** below overlap where one shared dependency supports several spells; do not sum them as independent systems.

Authority references: [agent_docs/SPELL_VFX_IMPLEMENTATION_PLAN_2026-10-04.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/SPELL_VFX_IMPLEMENTATION_PLAN_2026-10-04.md) (P1–P8; source SHA256 `605ced75825d5ba20c5664683a252d8af01223d8b880359b930b1334e8208a35`), [RECOVERY_PLAN.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/RECOVERY_PLAN.md), [agent_docs/SPELL_VFX_IMPLEMENTATION_2026-10-04.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/SPELL_VFX_IMPLEMENTATION_2026-10-04.md), and the linked bounded receipts. The plan's current adaptations are explicit: hostile Telekinesis **4d8 force + 2d6 bludgeoning + actual ledge fall**, quick/eat Heroes' Feast **all benefits ten recipient turns**, and Finger of Death **no zombie**. Generic Frightened keeps its earlier approved zero-speed behavior; Eyebite Panicked gets source-specific retreat. Tabletop falls are **1d6/full 10 feet, capped at 20d6**. These choices must not be presented as unmodified SRD/BG3 rules.

Scope of this document is `dnd/` and AI only. Client drawing/operators, artwork/imports, devtools, changed tests and strict historical fixtures are evidence or separate trace lanes, not silently counted as native implementation. No production code, test, artwork or feature was changed to write this inventory, and no new test run is claimed for this documentation task.

The machine-readable [agent_docs/audits/SPELL_NATIVE_FEATURE_TRACE_2026-10-04.json](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/SPELL_NATIVE_FEATURE_TRACE_2026-10-04.json) pins **baseline and current raw-byte SHA256 for every file**, categories and feature IDs. Its SHA256 is `fcc4d5e4993a1d95010724f9261432c4dda1c640608f70c5345e9173d422e158`. Baseline Git blobs use repository line endings; current hashes use literal workspace bytes, including CRLF where present. This makes the snapshot reproducible without concealing later deltas.

## Shared engine changes

### CORE-01 — Retained magical contributions can be suspended without reapplication

**Authority:** P6: explicit retained Antimagic ownership requirement.

**Before → after:** Antimagic removed magical conditions and stored them in AntimagicSuppression marker conditions. Removal cleared their existing modifier/handler/child ownership and restoration reapplied effects. → Each retained condition has additive provider UUID tokens. Existing StaticValue aggregation, contextual modifiers, granted actions and event/spatial handlers consult its live contribution gate. Missing or removed owners fail closed; independent suppressors must all release before an effect resumes. Native duration and final cleanup remain live.

**API, event and existing owner:** [ContributionOwner](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_object.py:11) is a structural interface in the existing BaseObject registry, widened to accept actual item owners; no new registry. Server-only contribution_owner_uuid/contribution_position link existing payloads. [BaseCondition.bind_owned_contributions](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_conditions.py:588) stamps existing ownership arrays; set_suppression/suppression_providers retain identity. BaseHandler.runs_while_suppressed marks actual duration/cleanup exceptions. Structural-source lookups use get_contribution_owner rather than assuming an item inherits BaseObject.

**Evidence:** [tests/engine/test_antimagic_retained_contributions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_antimagic_retained_contributions.py); [agent_docs/audits/SPELL_FINAL_ECS_EVENT_REVIEW_2026-10-04.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/SPELL_FINAL_ECS_EVENT_REVIEW_2026-10-04.md).

**Scope/tradeoff:** CORE-wide aggregation/dispatch change, including unrelated effects using the same modifiers. The gate does not toggle or overwrite the existing enabled flag. Keeping native class subclasses here uses the existing condition/handler composition; it is not a parallel condition manager.

### CORE-02 — Direct senses, invisibility, movement exemptions and immunities remain source owned

**Authority:** P6 direct-contribution suppression; P1 sensory ownership.

**Before → after:** Several effects wrote shared booleans, appended unowned sense modes or used display-name immunity keys. Those bypassed the retained modifier gate and could remove another source on cleanup. → Invisible/Invisibility/Greater Invisibility contribute through their active condition; intrinsic/manual invisibility remains separate. Freedom of Movement contributes its three capabilities through the same condition gate. Darkvision/See Invisibility/True Seeing use the existing sense_mode_sources array keyed by owner. Petrified, Protection from Poison, Freedom of Movement and Feast immunity entries use exact source UUIDs.

**API, event and existing owner:** [BaseBlock.condition_immunity_contributes](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_block.py:2032), [Senses.get_sense_modes](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/sensory.py:182) and Entity capability properties compose existing state. SenseMode.contribution_owner_uuid is server-only/excluded from the wire. Existing condition membership refresh publishes visibility changes; reveal-on-attack/cast still runs while an invisibility effect is suppressed.

**Evidence:** [tests/engine/test_antimagic_retained_contributions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_antimagic_retained_contributions.py), [tests/engine/test_spell_handoff_senses.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_spell_handoff_senses.py).

**Scope/tradeoff:** Broadens ownership correctness beyond the named VFX spells. Ordinary nonmagical Hidden and intrinsic capabilities are not converted into spell owners; removing one source does not clear another.

### CORE-03 — Granted budgets/actions and magical equipment obey the same suppression owner

**Authority:** P6 action, item and direct-contribution gates.

**Before → after:** Restricted-action grants, flying speed grants, weapon overrides, item property modifiers and usable magic items could contribute despite a suppressed source. Projectile bonuses did not account for crossing a field. → Existing grants remain registered but unavailable while their owner is inactive. Fly speed derives from live grants without resetting spent movement. Weapon overrides and magic bonuses/extra damage are gated on the real item/condition. A mundane weapon/projectile remains usable while its magical contribution is suppressed, including a field crossed by the actual attack path.

**API, event and existing owner:** [dnd/blocks/action_economy.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/action_economy.py), [dnd/blocks/equipment.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/equipment.py), [dnd/items/property_composition.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/items/property_composition.py); BaseAction.contributions_active checks both discovery and execution, UsableItem.use_admission_error checks magic use, and ActionEvent.item_magic_suppression_provider_uuids records the crossing suppression. Unseen Strike consumes that exact fact. ConcentrationActionMarker unregisters its exact repeat UUID in normal owned-state release.

**Evidence:** [tests/engine/test_antimagic_retained_contributions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_antimagic_retained_contributions.py), [tests/engine/test_nature_spell_delivery.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_nature_spell_delivery.py).

**Scope/tradeoff:** CORE action economy and equipment behavior changed, although no new action pool or ordinary Attack route was introduced. Suppression withholds a live grant; it does not refund actions, replay a heal or create a replacement weapon.

### CORE-04 — Partially suppressed areas and lights keep their existing lifetime and geometry

**Authority:** P6 active areas/items/created-presence coverage; P7 wall suppression.

**Before → after:** Area, terrain, light and physical-wall contributions did not all use the same local gate. Absence of an anchored actor/object could retire its area rather than retain it for restoration. → Area footprints remain retained; movement cost, optical obstruction, triggers and field crossings contribute only at unsuppressed cells. Suspended anchors stop contributing without teardown. Existing LightSourceData keeps identity and authored is_active while its exact contribution owner gates illumination. Moving a field refreshes tiles, senses and published state.

**API, event and existing owner:** [AreaCondition.refresh_antimagic_suppression](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spatial/area_conditions.py:1136), [GridMap.refresh_contribution_lights](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py:4688); SpellSuppression.antimagic distinguishes temporary local gating from existing excluded coverage. WallSection republishes ordinary ItemLocationState with construction_suppressions when its actual owner changes. The invisible Force area owner is not made visible by this native section payload.

**Evidence:** [tests/engine/test_antimagic_retained_contributions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_antimagic_retained_contributions.py); [tests/game/test_construction_suppression.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/game/test_construction_suppression.py).

**Scope/tradeoff:** CORE spatial cache/light behavior changed. Stone remains physically nonmagical; Wind, Ice and Force honor affected-cell suppression. Full item disappearance and partial wall suppression remain different existing ownership cases.

### CORE-05 — Creature-plus-destination and primary-dependent target choices reach both human and AI execution

**Authority:** P3 Chain Lightning; P6 Telekinesis/Dimension Door; explicit selection dependencies.

**Before → after:** The selection union supported a single position or a position path. Multi-target choices came from one global pool; it could not expose only the secondaries valid for a chosen Chain primary. → EntityDestinationSelection requires exactly one creature then exactly one destination. AvailableTarget.secondary_targets optionally carries the engine-admitted pool for that primary; None preserves ordinary global multi-target behavior. Human functional execution and immutable AI affordances validate those same choices and reject malformed/stale requests.

**API, event and existing owner:** [dnd/core/action_types.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/action_types.py), [dnd/actions_functional.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/actions_functional.py), [dnd/ai/contracts/control.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/ai/contracts/control.py), [dnd/ai/runtime/decision_epoch.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/ai/runtime/decision_epoch.py), [dnd/ai/runtime/execution.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/ai/runtime/execution.py); BaseAction.get_secondary_target_options/get_application_propagation and multi_target_objects are narrow extension points. Entity discovery projects those values from the installed action template; no frontend/AI radius search.

**Evidence:** [tests/engine/test_chain_lightning_selection.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_chain_lightning_selection.py), [tests/game/test_dimension_door_selection_replay.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/game/test_dimension_door_selection_replay.py); [agent_docs/audits/SPELL_CHAIN_LIGHTNING_ECS_REVIEW_2026-10-04.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/SPELL_CHAIN_LIGHTNING_ECS_REVIEW_2026-10-04.md).

**Scope/tradeoff:** CORE command/affordance schema changed and AI now accepts the new selection shape. It does not add new AI tactics, a planner, target registry or spell-specific controller.

### CORE-06 — Ordinary ledge falls and finite forced movement share supported landing resolution

**Authority:** P6 human request for actual Shove/Telekinesis ledge damage; tabletop fall choice.

**Before → after:** Push paths used ordinary walking admission and stopped at downward support edges. Jump and forced landing did not share the requested actual-support fall damage contract. → Shove, Thunderwave and Gust can finish on an admitted lower support; downward Jump settlement also resolves a fall. Damage is 1d6 per full 10 feet, capped at 20d6. Ordinary fall Prone requires positive committed damage, including temporary-HP absorption. Telekinesis supplies its own landing damage/Prone-save composition. Controlled allied movement/teleport does not gain cosmetic-lift damage.

**API, event and existing owner:** [commit_forced_movement](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/actions.py:370), [resolve_fall_damage](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/actions.py:344), GridMap.admit_forced_step/admit_airborne_transfer. Existing ForcedMovementEvent now records path, actual support heights, drop and LandingKind. Damage is a child of the actual landing; retained DamageApplied facts determine whether ordinary fall Prone occurs.

**Evidence:** [tests/engine/test_telekinesis_landing.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_telekinesis_landing.py); [agent_docs/audits/SPELL_PACKET6_TELEKINESIS_NATIVE_REVIEW_2026-10-04.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/SPELL_PACKET6_TELEKINESIS_NATIVE_REVIEW_2026-10-04.md).

**Scope/tradeoff:** CORE movement, Jump and ordinary Shove changed. Existing support/edge/occupancy queries are reused; finite transfer is conservative and cannot infer clearance over obstacles or search a different landing. No persistent airborne actor state, multi-Z world expansion, hover or new physics solver.

### CORE-07 — Absence, nearest-free return and paired teleport commit preserve real identities

**Authority:** P6 Banishment, Dimension Door and Antimagic presence.

**Before → after:** Banishment return could displace occupants near its original cell. There was no retained plane/disposition or pending nearest-free return obligation; teleport had no paired participant transaction. → Banishment reserves original/nearest valid free support for each returning actor, never evicts occupants, and retains a pending return if all supports are unavailable. Paired teleports commit every admitted position before any arrival reaction; failure before commit rolls positions back. Suspended entities retain identity but have no battlefield runtime agency. Antimagic creations restore only to their original anchor when legal.

**API, event and existing owner:** [Entity.commit_position_transfers](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entity.py:945), prepare_spatial_return/retain_pending_spatial_return and BaseBlock.prepared_return_reservations reuse the accepted removal/placement transactions. SpatialDisposition/PendingSpatialReturn and native_plane_id/current_plane_id are passive data. Existing actor snapshots and ENTITY_ENTERED folding carry committed presence.

**Evidence:** [tests/engine/test_banishment_dimension_door.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_banishment_dimension_door.py), [tests/engine/test_antimagic_retained_contributions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_antimagic_retained_contributions.py); [agent_docs/audits/SPELL_BANISHMENT_DIMENSION_DOOR_NATIVE_2026-10-04.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/SPELL_BANISHMENT_DIMENSION_DOOR_NATIVE_2026-10-04.md).

**Scope/tradeoff:** CORE placement/lifecycle API changed: prepare_spatial_return may return None; PreparedSpatialReturn no longer contains displaced occupants. Named plane identity is not a planar simulator. Publication failure does not undo an already committed return/teleport.

### CORE-08 — Normal HP caps, max-HP changes and actual disintegration death use the existing health transaction

**Authority:** P3 Harm/Disintegrate; P5 Feast.

**Before → after:** The public damage call did not expose the existing normal-HP cap. Changing maximum HP also changed apparent current HP through damage_taken. Death lacked a committed remains distinction and ordinary revive could restore any dead body. → Entity.receive_damage forwards normal_hit_point_damage_cap unchanged to the existing damage preview/apply path. Health.preserve_normal_hit_points reconciles a changed maximum without another damage/heal event. zero_hp_disposition requests disintegrated remains only when that damage actually leaves zero normal HP and death succeeds; ordinary revival rejects those remains.

**API, event and existing owner:** [dnd/blocks/health.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/health.py), [dnd/core/life_types.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/life_types.py); [Entity._fire_death_event](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entity.py:2664) still permits EXECUTION cancellation before death/gear teardown, then uses existing publish_committed_phase for committed DEATH EFFECT. Damage/save/prevention/life owners remain the same; magical gear is staged for preservation before irreversible teardown.

**Evidence:** [tests/engine/test_disintegrate_outcomes.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_disintegrate_outcomes.py), [tests/engine/test_spell_handoff_necromancy.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_spell_handoff_necromancy.py), [tests/engine/test_spell_handoff_holy.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_spell_handoff_holy.py); [agent_docs/audits/SPELL_DISINTEGRATE_NATIVE_IMPLEMENTATION_2026-10-04.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/SPELL_DISINTEGRATE_NATIVE_IMPLEMENTATION_2026-10-04.md).

**Scope/tradeoff:** CORE health, death publication and revive semantics changed. The committed-DEATH-EFFECT rule also applies to ordinary deaths; late EFFECT cancellation cannot erase committed state. Temporary HP and life state are not silently altered by max-HP reconciliation.

### CORE-09 — Disintegrated objects retain real apertures and actual item survivors

**Authority:** P3 Disintegrate object/gear rules; P7 remaining walls.

**Before → after:** Larger-object Disintegrate rejected partial cuts. Whole object retirement had no dust disposition or retained removed volume. Native wall crossing tested the intact shell. → Small eligible objects retire as dust through existing item retirement. Large objects lose an admitted 10-foot cube while retaining UUID, anchor, remaining placement and collision. Creature dust destroys nonmagical possessions, extracts magical survivors even inside consumed containers, and drops them once; targeting a container alone spills its contents. Ice breach leaves cold air only in the actual removed footprint; Force Disintegrate retires its full owner.

**API, event and existing owner:** [BaseItem.disintegrate_section](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/base_item.py:1035), GridMap.remove_object_section, WorldPlacementSpec.removed_local_bands/WorldObjectPlacement.removed_bands and wall geometry removed_sections. ObjectSectionVolume is a passive leaf value; existing spatial/item destruction events carry before/after placement and survivor UUIDs.

**Evidence:** [tests/engine/test_disintegrate_outcomes.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_disintegrate_outcomes.py), [tests/engine/test_remaining_walls.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_remaining_walls.py); [agent_docs/audits/SPELL_DISINTEGRATE_NATIVE_IMPLEMENTATION_2026-10-04.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/SPELL_DISINTEGRATE_NATIVE_IMPLEMENTATION_2026-10-04.md).

**Scope/tradeoff:** CORE item destruction, placement-band indexing, optical/physical crossings and saved schemas changed. Only full-height cuts remove the wall crossing at that height; no generic mesh-based native collision system or repairable dust remnant was introduced.

### CORE-10 — Healthless but targetable objects can be struck by ordinary Attack

**Authority:** P7 Force ordinary contact acceptance; root review correction.

**Before → after:** Attack required BaseItem.is_breakable, so a visible/targetable but damage-immune Force section was absent or rejected despite being a real physical contact. → Attack uses existing object_target_policy="active" and retains active, targetable, perception, reach and current contact checks. Health/breakability determines damage response, not whether the attack can be attempted. A legal attack spends its normal cost and leaves the immune barrier unchanged.

**API, event and existing owner:** [Attack](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/actions.py:1963) only changes its object policy/range/contact admission; the existing attack/damage pipeline and budget apply. Other action classes keep their default damageable-object policy.

**Evidence:** [tests/engine/test_remaining_walls.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_remaining_walls.py); [agent_docs/audits/SPELL_FORCE_ATTACK_TARGETABILITY_REVIEW_2026-10-04.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/SPELL_FORCE_ATTACK_TARGETABILITY_REVIEW_2026-10-04.md) records 67 checks plus five independent public-menu/stale-input probes..

**Scope/tradeoff:** A deliberately broader ordinary-Attack correction, not merely VFX. Invisible, nontargetable, inactive, out-of-reach or no-longer-seen contacts still reject before payment. No separate object attack command or fake HP was added.

### CORE-11 — Retained spell actions keep magical protections without recasting

**Authority:** P2 Produce Flame; P3 Eyebite; P4 Sunbeam; P6 Telekinesis.

**Before → after:** Some follow-ups were treated as fresh casts or as untyped ordinary actions. That could invoke Silence/metamagic incorrectly or bypass Sanctuary, Globe and Antimagic. → The existing SpellEvent data shape is used with BASE_ACTION for non-cast spell follow-ups, original effect origin/DC/slot and ordinary action costs. Globe, Sanctuary and Antimagic include that typed branch. Metamagic only changes SpellAction templates with is_spell=True. Consuming the held flame uses exact consumed removal, and marker teardown unregisters the exact action UUID.

**API, event and existing owner:** [dnd/actions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/actions.py), [dnd/core/base_actions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_actions.py), [dnd/spells/abjuration.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/abjuration.py), [dnd/classes/sorcerer.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/classes/sorcerer.py); SpellEvent.retained_effect_origin is data, not another executor. Position-target declarations record self.end_position without changing area-origin semantics.

**Evidence:** [tests/engine/test_nature_spell_delivery.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_nature_spell_delivery.py), [tests/engine/test_spell_handoff_necromancy.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_spell_handoff_necromancy.py), [tests/engine/test_weather_solar_spells.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_weather_solar_spells.py).

**Scope/tradeoff:** CORE event classification, protection handlers and metamagic template filtering changed. A follow-up remains a magical effect for defenses but does not spend another slot or trigger another verbal cast/Counterspell opportunity.

### CORE-12 — Checks and independent fear sources use exact contributions

**Authority:** P3 Eyebite; final plan clarification preserving generic Frightened.

**Before → after:** Sickened put disadvantage on ability scores rather than all actual skill/raw checks. Shared Frightened membership conflated the source-specific movement/attack/check rules of overlapping fears. → Ability.check_bonus contributes only to raw ability checks; skill modifiers remain on existing skill bonuses. Frightened shared membership retains live parent links across replacement/expiry. Eyebite Panicked owns each frightener's retreat restriction and check/attack penalties independently; ordinary/residue fear keeps its established movement behavior.

**API, event and existing owner:** [dnd/blocks/abilities.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/abilities.py), [dnd/entity.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entity.py), [dnd/conditions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/conditions.py); apply_frightened_disadvantage installs modifiers into the ordinary ownership list. Frightened source_rules_owned_by_parent/allow_retreat and parent bookkeeping isolate membership from source rules. STEP_MOVEMENT rejects approach toward the currently visible source using support distance.

**Evidence:** [tests/engine/test_spell_handoff_necromancy.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_spell_handoff_necromancy.py), [tests/engine/test_antimagic_retained_contributions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_antimagic_retained_contributions.py).

**Scope/tradeoff:** CORE ability-check aggregation and Frightened lifecycle changed. The new raw-check lane must not change saves or attacks; generic Frightened still imposes the previously approved zero-speed behavior. No general fear manager.

### CORE-13 — Native round-end rules now receive normal event phases

**Authority:** P4 exact source-turn expiry with departed-caster fallback; P5 world lifetimes.

**Before → after:** Encounter._fire_round_end constructed ROUND_END directly at COMPLETION; EFFECT-phase round-end handlers could not observe it. → One RoundEndEvent now advances DECLARATION → EXECUTION → EFFECT → COMPLETION. The shared solar/ice source-turn expiry handler can use the next world round when a dead/departed caster will not take a next turn.

**API, event and existing owner:** [Encounter._fire_round_end](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/encounter.py:669) and [_source_turn_expiry_handler](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/evocation.py:2039); existing turn_execution_id prevents the casting turn itself from satisfying the next-turn deadline.

**Evidence:** [tests/engine/test_weather_solar_spells.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_weather_solar_spells.py), [tests/engine/test_spell_handoff_holy.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_spell_handoff_holy.py).

**Scope/tradeoff:** CORE event lifecycle change visible to every ROUND_END subscriber, not just these spells. The absent-caster next-round fallback is a bounded game lifetime policy, not a new scheduler or an assertion that SRD defines an absent creature's next turn.

### CORE-14 — Published facts retain outcomes and source ownership for replay

**Authority:** All packets: existing retained event → projection → shared presentation contract.

**Before → after:** Several results omitted their real condition/item owner, branch endpoints, suppression, remains, selected class mode or spatial disposition. A consumer otherwise had to infer from names, query mutable engine state or treat a requested effect as successful. → Existing native event/snapshot records carry those optional typed after-values. Native actor projection retains committed remains/presence and sets PRESENT on ENTITY_ENTERED. Perceived spatial observations include an anchor identity only through existing observer visibility rules, with energy/presence mode where selected.

**API, event and existing owner:** [dnd/core/events.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py), [dnd/types/actor.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/types/actor.py), [dnd/types/actor_facts.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/types/actor_facts.py), [dnd/actor_projection.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/actor_projection.py), [dnd/types/senses.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/types/senses.py), [dnd/core/item_types.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/item_types.py). The complete field inventory below names the schemas. No new EventType gameplay family is added; LandingKind is a closed passive enum.

**Evidence:** [tests/engine/test_class_presentation_facts.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_class_presentation_facts.py), [tests/game/test_transport_spell_delivery.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/game/test_transport_spell_delivery.py); [agent_docs/audits/SPELL_FINAL_ECS_EVENT_REVIEW_2026-10-04.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/SPELL_FINAL_ECS_EVENT_REVIEW_2026-10-04.md).

**Scope/tradeoff:** CORE wire/schema changes require strict historical fixture migration. Optional/default values denote absence of evidence, not success. Client privacy/sanitization is reviewed separately; this document inventories the native additions rather than asserting every observer may read every native field.

## Spell and wall behavior

### S01 — Darkvision, See Invisibility and True Seeing durations and exact sense sources

**Authority:** P1.

**Before → after:** Darkvision incorrectly required concentration; See Invisibility/True Seeing lasted 10 rounds. Granted modes were appended to the basic sense list. → Darkvision lasts 4,800 rounds (8 hours), without concentration; See Invisibility and True Seeing last 600 rounds (1 hour). Their 60-foot darkvision, existing see-invisible channel and 120-foot truesight use exact sense owners and preserve innate/other modes on removal.

**API, event and existing owner:** [dnd/spells/transmutation.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/transmutation.py), [dnd/spells/divination.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/divination.py); existing effect conditions and Senses.add_sense_mode_source/remove_sense_mode_source, plus CORE-02.

**Evidence:** [tests/engine/test_spell_handoff_senses.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_spell_handoff_senses.py).

**Scope/tradeoff:** No new ethereal map, wall penetration, automatic hit permission or revised blindness rules; existing sense channels are reused.

### S02 — Hold Monster validates the complete selected group and shares paralysis

**Authority:** P1.

**Before → after:** Validation checked only the primary; replacing a Paralyzed child could disturb an independent source. The effect lacked the explicit one-minute condition duration. → Every chosen creature must be visible, in 90-foot range, non-undead and within 30 feet of the others before cost. The ten-round owner shares an existing Paralyzed child and rejects false parent application when paralysis was immune/canceled.

**API, event and existing owner:** [HoldMonster](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/enchantment.py:530) / HoldMonsterEffect; existing multi-target allocation, WIS saves, concentration and shared-child links.

**Evidence:** [tests/engine/test_spell_handoff_control.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_spell_handoff_control.py).

**Scope/tradeoff:** Upcast count, WIS repeat and ordinary paralysis mechanics already existed; this is group admission/lifetime/ownership repair, not a new paralysis system.

### S03 — Power Word thresholds and source-independent Stun repeat

**Authority:** P1.

**Before → after:** Power Word Kill/Stun compared get_hp, which includes temporary HP. Stun replaced an independent Stunned child and dropped its effect when the caster disappeared. → Thresholds use normal HP: Kill 100, Stun 150. Stun shares the existing child and retries CON against the recorded DC even without a live caster. Kill still attempts native instant death; it does not fabricate damage.

**API, event and existing owner:** [PowerWordStunEffect](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/enchantment.py:1066); Entity.saving_throw_bonus permits recorded-source saves when that source no longer exists. Existing death prevention and condition owners remain authoritative.

**Evidence:** [tests/engine/test_spell_handoff_control.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_spell_handoff_control.py).

**Scope/tradeoff:** The ordinary instant-death route and absence of an initial Stun save were already implemented. New presentation facts must distinguish their actual outcome from the utterance.

### S04 — Longstrider and Barkskin use actual touch admission

**Authority:** P1 Longstrider; P2 Barkskin; scoped regression fix for SELF touch.

**Before → after:** These actions could rely on visual/global target discovery rather than explicit physical touch; Longstrider had no local excessive-recipient guard. The shared touch validator only accepted one ENTITY target. → Both declare TOUCH_CONTACT. Longstrider rejects too many recipients for the slot. Shared BaseAction touch validation now checks each MULTI_ENTITY target and permits legitimate SELF touch, preserving existing touch-origin restrictions.

**API, event and existing owner:** [dnd/spells/transmutation.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/transmutation.py), [dnd/core/base_actions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_actions.py); ordinary action admission, existing speed modifier and Barkskin AC minimum owner.

**Evidence:** [tests/engine/test_roster_support_spells.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_roster_support_spells.py), [tests/engine/test_nature_spell_delivery.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_nature_spell_delivery.py).

**Scope/tradeoff:** Longstrider +10-foot speed/hour and Barkskin concentration/hour/minimum AC16 were already present and are not newly invented here. The SELF correction also preserves existing self-touch actions such as Wayfarer.

### S05 — Shillelagh selects and releases the actual held wooden weapon

**Authority:** P2.

**Before → after:** An override already supplied d8/casting ability/magical attacks, but qualifying inactive loadout items and hand selection/release could diverge from the actually held weapon; condition snapshots did not identify the affected item. → Discovery offers qualifying main/off-hand wooden clubs or quarterstaves only in the active melee set. Execution rechecks the exact selected item. Releasing it or switching out of that set removes only its effect. ConditionState.affected_item_uuid names the true material/attack owner.

**API, event and existing owner:** [Shillelagh](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/transmutation.py:2123) / ShillelaghEffect; existing WeaponAttackOverride and equipment events; release handler stays live while suppressed.

**Evidence:** [tests/engine/test_roster_support_spells.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_roster_support_spells.py), [tests/engine/test_antimagic_retained_contributions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_antimagic_retained_contributions.py).

**Scope/tradeoff:** Bonus action, minute duration and override mechanics were already native. Unlike a persistent coating, this effect intentionally ends when the caster lets go; no other weapon inherits it.

### S06 — Produce Flame retained hurl pays once and consumes the correct flame

**Authority:** P2.

**Before → after:** Held light/hurl and cantrip scaling existed, but later throws could be treated as casts, skip range admission, lose original effect provenance or omit critical damage semantics. → Initial/later hurl validates the recipient before cost or consumption. Later hurl is a nonverbal ability carrying its original magical origin; Silence/metamagic cannot recast it. Exact consumed removal releases the held flame, and damage retains critical_hit/origin. Owner gates suppress both light and granted action.

**API, event and existing owner:** [HurlProduceFlame](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/conjuration.py:5162), _hurl_flame/ProduceFlameEffect; existing ranged spell attack, action costs, itemless hand-flame condition and light owner.

**Evidence:** [tests/engine/test_nature_spell_delivery.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_nature_spell_delivery.py); [agent_docs/audits/SPELL_PACKET2_NATIVE_REVIEW_2026-10-04.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/SPELL_PACKET2_NATIVE_REVIEW_2026-10-04.md).

**Scope/tradeoff:** d8 scaling, ten-minute held duration and 10/10 light remain existing rules. This corrects cost/classification/protection/outcome facts; no second projectile damage event.

### S07 — Fire Shield retaliation names its true owner and uses support-height range

**Authority:** P2.

**Before → after:** Warm/chill shields, opposite resistance/light and 2d8 close melee retaliation already existed. Range used only planar distance and retaliation damage did not record the shield condition UUID. → The five-foot contact check includes support elevations. The shield snapshot carries its selected energy; retaliation DamageApplied carries source_condition_uuid and effect_id spell.fire_shield.retaliation for the admitted attacker.

**API, event and existing owner:** [FireShieldEffect](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/evocation.py:5293); existing successful melee-hit handler and ordinary damage resolution, no reaction cost.

**Evidence:** [tests/engine/test_roster_support_spells.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_roster_support_spells.py), [tests/engine/test_nature_spell_delivery.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_nature_spell_delivery.py).

**Scope/tradeoff:** This is bounded range/provenance repair, not newly implemented warm/chill rules or an extra attack/reaction.

### S08 — Continual Flame attaches to an actual item through ownership changes

**Authority:** P2.

**Before → after:** Casting chose a position and created a fake ContinualFlameObject plus spatial light condition. → Casting touches a real intact item, including the caster's inventory/equipment via the existing item selection. One item condition owns its permanent heatless 20/20 light and item-effect snapshot. Equip, carry, storage/cover, drop, transfer and destruction use actual placement/ownership; suppressed light restores without reapplying the spell.

**API, event and existing owner:** [ContinualFlameCondition](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/evocation.py:4434); BaseAction.include_owned_item_targets, BaseItem.on_world_placement_committed and existing ItemEffectPresentationState. contribution_uuid/damage_type are optional because a light is not a damage contribution.

**Evidence:** [tests/engine/test_continual_flame_items.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_continual_flame_items.py); [agent_docs/audits/SPELL_CONTINUAL_FLAME_NATIVE_IMPLEMENTATION_2026-10-04.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/SPELL_CONTINUAL_FLAME_NATIVE_IMPLEMENTATION_2026-10-04.md).

**Scope/tradeoff:** Removes the fake object path; no new inventory, heat, ignition, oxygen or ground-item executor. Object selection is intentionally expanded only by actions opting into owned items.

### S09 — Lightning Bolt resolves empty-area coverage and native ignition

**Authority:** P3.

**Before → after:** Its line/dice/save existed, but area execution/finalization did not ignite eligible surface contacts and could require a creature target. → The action resolves the native line through the existing area path even with no creature. Finalization calls existing ignite_surface_contacts once on admitted cells after spell-protection exclusions.

**API, event and existing owner:** [LightningBolt](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/evocation.py:1285); existing AoE resolution and surface ignition owner.

**Evidence:** [tests/engine/test_chain_lightning_selection.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_chain_lightning_selection.py); [tests/game/test_electric_spell_delivery.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/game/test_electric_spell_delivery.py).

**Scope/tradeoff:** 100×5 feet, 8d6/DEX half/+1d6 per slot are retained. No electrified-water rule, neighboring-pixel ignition spread or persistent lightning zone.

### S10 — Chain Lightning uses chosen branches from one primary

**Authority:** P3.

**Before → after:** The spell selected nearest visible enemies from any previous recipient and increased damage dice on upcast; it did not expose the actual secondary choices or object recipients. → A visible, reachable creature/object primary lies within 150 feet; every selected distinct secondary must be visibly reachable within 30 feet of that primary. Slot6 allows up to three secondaries; higher slots add recipients, while each remains10d8/DEX half. Each existing application carries frozen source/target endpoints and its own application ID.

**API, event and existing owner:** [ChainLightning](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/evocation.py:3715); CORE-05 pools and EffectPropagationLink. Antimagic checks the real primary→secondary leg. Actor-cast wands retain the actor endpoint rather than substituting the held item.

**Evidence:** [tests/engine/test_chain_lightning_selection.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_chain_lightning_selection.py); [agent_docs/audits/SPELL_CHAIN_LIGHTNING_ECS_REVIEW_2026-10-04.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/SPELL_CHAIN_LIGHTNING_ECS_REVIEW_2026-10-04.md).

**Scope/tradeoff:** This is a real target-selection and upcast rule correction. Current Chain object admission retains its breakable-object requirement; the broader immune-object Attack change is separate. No automatic client branching or recursive bounce search.

### S11 — Blight plant saves and canceled outcomes resolve correctly

**Authority:** P3.

**Before → after:** Undead/construct immunity, plant disadvantage and maximum damage were already present; a plant that saved still took full maximum damage. Temporary disadvantage cleanup was not guaranteed on exceptional resolution. → A successful plant save halves maximum damage. The temporary save modifier is removed in finally, canceled effects stop damage, and accepted damage carries the exact spell origin/components/rolls.

**API, event and existing owner:** [Blight](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/necromancy.py:405); ordinary CON save and Damage owner.

**Evidence:** [tests/engine/test_spell_handoff_necromancy.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_spell_handoff_necromancy.py).

**Scope/tradeoff:** No persistent disease or new world-vegetation model. Existing type immunity is preserved rather than claimed as newly added.

### S12 — Circle of Death records its existing damage and respects effect cancellation

**Authority:** P3.

**Before → after:** 60-foot area,8d6/+2d6 and CON half were present; the damage call omitted component/roll/origin evidence and could continue after a canceled EFFECT. → Canceled effects stop; the ordinary damage call retains its actual roll, component and spell source for the existing application/replay path.

**API, event and existing owner:** [CircleOfDeath](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/evocation.py:1786); existing area/save/damage pipeline.

**Evidence:** [tests/engine/test_spell_handoff_necromancy.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_spell_handoff_necromancy.py).

**Scope/tradeoff:** Provenance/cancellation repair only for native rules; no persistent damaging smoke and no new dice/scaling rule.

### S13 — Harm cannot kill through normal HP and owns its timed max-HP disease

**Authority:** P3 explicit Harm overlap paragraph.

**Before → after:** Harm capped a pre-resolution combined-HP number and omitted its one-hour maximum-HP reduction. → The existing health cap preserves at least one normal HP after defenses/temp HP. On failed CON save, accepted damage including absorbed temporary HP becomes a one-hour reduction. Per-cast HarmSource owners retain independent clocks and one shared HarmEffect modifier; strongest/latest wins, weaker live sources can resume. Disease/max-reduction cleanup removes the real sources.

**API, event and existing owner:** [HarmSource](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/necromancy.py:1935) / HarmEffect/Harm; CORE-08 HP reconciliation and existing add_shared_subcondition links. State changes publish existing ConditionStateChangedEvent after-value stats.

**Evidence:** [tests/engine/test_spell_handoff_necromancy.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_spell_handoff_necromancy.py), [tests/engine/test_antimagic_retained_contributions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_antimagic_retained_contributions.py).

**Scope/tradeoff:** No upcast bonus, double damage on lowering maximum, healing on expiry, or generic stacking manager. Source conditions intentionally have internal UUID-qualified identities so same-name replacement cannot erase another cast.

### S14 — Eyebite pays its initial gaze once and retains all three exact modes

**Authority:** P3; Frightened clarification.

**Before → after:** A self cast optionally launched a separate free first action; repeat protection/source facts and exact ownership were incomplete. Panicked used custom forced movement instead of spending ordinary movement, while Sickened missed actual check modifiers. → The paid cast requires an initial visible creature and resolves that gaze on its own event. A ten-round casting marker owns the exact paid repeat action, successful-saver memory and linked results. Asleep wakes via actual damage/assistance mechanics; Panicked owns its own Frightened source penalties, paid Dash and ordinary Move; Sickened disadvantages attacks/skills/raw checks and retries WIS at turn end against recorded magical context.

**API, event and existing owner:** [Eyebite](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/necromancy.py:1523), EyebiteStrike/EyebiteCastingState and the three existing effect compositions. No free move/restrain follow-up, no new movement executor. Shared Frightened membership survives independent fear cleanup (CORE-12).

**Evidence:** [tests/engine/test_spell_handoff_necromancy.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_spell_handoff_necromancy.py); [agent_docs/audits/SPELL_PACKET3_NECROMANCY_NATIVE_REVIEW_2026-10-04.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/SPELL_PACKET3_NECROMANCY_NATIVE_REVIEW_2026-10-04.md).

**Scope/tradeoff:** Changes action selection/cost sequencing and mode ownership. The ordinary fear zero-speed rule is deliberately preserved outside the source-specific Panicked path; successful repeat saves are remembered by this cast only.

### S15 — Finger of Death stays fixed damage and creates no zombie

**Authority:** P3 explicit human damage-only adaptation.

**Before → after:** 7d8+30/CON half existed, but code added a d8 per higher slot. No working zombie creation was present at this baseline. → All eligible slots retain seven d8 plus30. Canceled EFFECT stops damage; normal damage facts retain components/rolls/origin and use ordinary prevention/death/corpse/items.

**API, event and existing owner:** [FingerOfDeath](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/necromancy.py:1619); existing Damage and life pipeline.

**Evidence:** [tests/engine/test_spell_handoff_necromancy.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_spell_handoff_necromancy.py).

**Scope/tradeoff:** No-zombie is an explicit human deviation from the full SRD spell, not an unimplemented creation feature hidden by the art. No roster/materialization/AI extension was added; the baseline missing zombie remains intentionally absent.

### S16 — Disintegrate requests dust only from its actual lethal result

**Authority:** P3 plus accepted outcome supplement.

**Before → after:** The spell had the DEX-negates dice formula but only dealt force damage; it lacked authoritative creature dust/remains and complete partial-object outcomes. The flat40 sat outside the recorded damage roll. → The flat40 is part of the ordinary damage component;10d6+40/+3d6 per slot remains. The call requests DISINTEGRATED only on its actual lethal result. The death/item transaction destroys nonmagical gear, preserves magical gear, carries retained disposition, and blocks ordinary revival; object rules use CORE-09.

**API, event and existing owner:** [Disintegrate](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/transmutation.py:936); CORE-08/09 existing health/death/retirement owners.

**Evidence:** [tests/engine/test_disintegrate_outcomes.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_disintegrate_outcomes.py); [agent_docs/audits/SPELL_DISINTEGRATE_NATIVE_IMPLEMENTATION_2026-10-04.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/SPELL_DISINTEGRATE_NATIVE_IMPLEMENTATION_2026-10-04.md), [agent_docs/audits/SPELL_PACKET_IMPLEMENTATION_ROOT_REVIEW_2026-10-04.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/SPELL_PACKET_IMPLEMENTATION_ROOT_REVIEW_2026-10-04.md).

**Scope/tradeoff:** A real native outcome addition, not a visual disappearance. EXECUTION prevention leaves no dust/gear teardown; a save/survivor keeps ordinary state. No resurrection spell or private HP engine.

### S17 — Ice Storm range, empty-area terrain and exact expiry

**Authority:** P4.

**Before → after:** Range was60 feet; terrain used a generic one-round duration. Existing mixed dice/upcast/save behavior was present. → Range is300 feet. Native admitted 20-foot-radius/40-foot-height coverage may be empty of creatures and still owns terrain. Canceled damage stops and carries source provenance. Difficult terrain uses the actual resolved footprint and ends at the end of the caster's next turn, with the explicit departed-source fallback in CORE-13.

**API, event and existing owner:** [IceStorm](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/evocation.py:3346) / IceStormTerrain; existing area/damage/terrain owners and native turn IDs.

**Evidence:** [tests/engine/test_weather_solar_spells.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_weather_solar_spells.py).

**Scope/tradeoff:** 2d8 bludgeoning+4d6 cold and +1d8 bludgeoning/slot are retained, not new rules. This adds no damaging ice surface after the initial storm.

### S18 — Sleet Storm affects all occupants with independently admitted entry/turn checks

**Authority:** P4.

**Before → after:** Enemy-only filtering, spherical inherited footprint, shared entry/turn allowance and skipping DEX while already Prone could suppress required saves. Saves used the recipient as source. → The area is a40-foot-radius/20-foot-height cylinder for ten rounds; allies are affected too. First entry and turn-start admission are separate. Every required DEX save occurs; concentration CON saves use recorded spell DC/source/magical context. Existing obscure/difficult-terrain/extinguish effects remain.

**API, event and existing owner:** [SleetStormZone](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/conjuration.py:3946); existing AreaCondition trigger gates and Prone/concentration removal.

**Evidence:** [tests/engine/test_weather_solar_spells.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_weather_solar_spells.py).

**Scope/tradeoff:** No damage, enemy safety exemption, additional weather simulator or private turn counter. Existing douse/terrain rules are reused.

### S19 — Sunbeam has an initial line, paid repeats, brief shared blindness and actual sunlight

**Authority:** P4.

**Before → after:** Casting was SELF/grant-only and the repeat had its own ad hoc action resolution. Native maintained sunlight and correct next-caster-turn blindness were missing/incomplete. → Cast selects a60×5 line and resolves the initial6d8/CON-half strike. A ten-round owner grants the exact action-cost non-cast repeat and owns30/30 sunlight. Failed-save blindness shares Blinded and expires at the caster's next turn; undead/oozes retain the required disadvantage. Empty lines are legal.

**API, event and existing owner:** [SunbeamEffect](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/evocation.py:3519), Sunbeam/SunbeamStrike/_apply_sunbeam; existing SpellAction allocation, concentration marker, light and save conditions.

**Evidence:** [tests/engine/test_weather_solar_spells.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_weather_solar_spells.py).

**Scope/tradeoff:** CORE light extension: LightSourceData.sunlight and GridMap.is_sunlit feed existing SunlightSensitivity attack/sight-Perception rules through occluded light footprints. Ordinary bright light does not become sunlight; no second vision permission.

### S20 — Sunburst keeps timed blindness and removes actual spell darkness

**Authority:** P4.

**Before → after:** Damage/type disadvantage existed; blindness depended on a live caster and could replace another Blinded source. Darkness cleanup and creature-free area finalization were missing. → A ten-round blindness owner shares Blinded and repeats CON against recorded DC after caster absence. Temporary disadvantage cleans up in finally; canceled/dead outcomes do not gain false blindness. Finalization removes intersecting spell-created magical-darkness owners, even with no creature recipients.

**API, event and existing owner:** [Sunburst](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/evocation.py:2179) / SunburstBlindedEffect; existing area/save/damage/condition owners.

**Evidence:** [tests/engine/test_weather_solar_spells.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_weather_solar_spells.py).

**Scope/tradeoff:** 12d6/radius60/range150 remain existing values. Ordinary night, fog and unlit terrain are not dispelled; darkness owner retirement remains whole-owner cleanup.

### S21 — Spirit Guardians uses declared exclusions and correct entry semantics

**Authority:** P5.

**Before → after:** A permanent enemy-only filter selected recipients; aura movement could count as damage entry, and trigger budgeting mixed entry and turn-start. Duration/source evidence were incomplete. → Visible cast-time excluded UUIDs stay excluded regardless of later faction. Nonexcluded occupants are slowed immediately; forming/moving the aura over them does not deal entry damage. Their own first entry and start turn are separately admitted.100-round concentration retains15-foot aura,3d8/+1d8 slot/WIS half; discovery exposes radiant/necrotic variants.

**API, event and existing owner:** [SpiritGuardiansZone](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/conjuration.py:2214); existing MembershipAreaCondition slow ownership and direct committed damage with source_condition_uuid. PerceivedSpatialEffect.energy_type reflects the native choice.

**Evidence:** [tests/engine/test_spell_handoff_holy.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_spell_handoff_holy.py); [agent_docs/audits/SPELL_PACKET5_NATIVE_REVIEW_2026-10-04.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/SPELL_PACKET5_NATIVE_REVIEW_2026-10-04.md).

**Scope/tradeoff:** Explicit radiant/necrotic choice is the plan's declared game adaptation, not an added alignment subsystem. Exclusions are native action data; no visual spirit chooses a victim.

### S22 — Guardian of Faith occupies Large space and spends its actual damage budget

**Authority:** P5.

**Before → after:** The object blocked one anchor with an authored square hazard, depended on a live caster, and estimated budget from normal HP differences. → The ordinary object occupies an admitted2×2 Large footprint. Its10-foot native distance area reacts to a hostile creature's first actual movement within it each turn, not creation/standing. Stored faction/DC survive caster absence.20/10 radiant counts direct committed damage including temporary HP; reaching/exceeding60 retires it. Eight-hour world lifetime is independent of caster presence.

**API, event and existing owner:** [GuardianOfFaithObject](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/conjuration.py:4444) / GuardianOfFaithZone; existing placement, AreaCondition, DamageAppliedEvent and item retirement. No per-hit cap is added to force a total of exactly 60.

**Evidence:** [tests/engine/test_spell_handoff_holy.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_spell_handoff_holy.py); [agent_docs/audits/SPELL_PACKET5_NATIVE_REVIEW_2026-10-04.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/SPELL_PACKET5_NATIVE_REVIEW_2026-10-04.md).

**Scope/tradeoff:** Occupancy, trigger admission and budget accounting are genuine native changes. The source facts are retained; no actor/AI/initiative participant is invented for the prop.

### S23 — Heroes’ Feast is paid once per eater with all benefits for ten turns

**Authority:** P5 explicit human quick-cast/eat and10-turn adaptation; separate full-plan prop lifetime choice.

**Before → after:** A quick prop/buff existed, but eating did not declare the required action cost; buffs were incomplete, duration/overlap/current-HP bookkeeping was incomplete, and finite guest/prop ownership was missing. → Adjacent ordinary item use spends one action, accepts each eater once, rolls2d10 through native Dice, cures disease/poison/fear, grants poison-damage and Poisoned/Frightened immunity, WIS-save advantage and matching max/current HP gain. Per-cast sources last ten recipient native turn-start ticks, strongest/latest wins without rehealing on expiry. Capacity is caster plus 12 guests (13 charges); prop expires after 10 world rounds or exhaustion.

**API, event and existing owner:** [EatFromFeast](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/conjuration.py:4871), HeroesFeastSource/Buff/Object/Lifetime; existing UsableItem cost/charges, condition shared parents, modifiers, immunity and spatial duration owners.

**Evidence:** [tests/engine/test_spell_handoff_holy.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_spell_handoff_holy.py), [tests/engine/test_antimagic_retained_contributions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_antimagic_retained_contributions.py); [agent_docs/audits/SPELL_PACKET5_NATIVE_REVIEW_2026-10-04.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/SPELL_PACKET5_NATIVE_REVIEW_2026-10-04.md).

**Scope/tradeoff:** Quick cast/eat and ten-turn benefits deliberately differ from SRD ritual/eating/day duration. The plan text still calls the separate10-round prop limit proposed; it is implemented under the full-plan assignment and must not be conflated with the explicit human benefit-duration answer. Prop destruction does not erase accepted buffs.

### S24 — Banishment chooses temporary return versus completed home-plane departure

**Authority:** P6.

**Before → after:** One enemy target was always suspended/incapacitated and returned via occupant displacement. No plane-dependent terminal branch or higher-slot target allocation. → Visible distinct creatures (including self/allies) use CHA resistance and one+slot-above4 allocation. A current-plane native becomes temporarily absent/incapacitated and loses concentration. A foreign creature goes home without automatically applying that incapacitation; early release returns it, a full ten native ticks leaves HOME_PLANE. Return/pending reservation follows CORE-07.

**API, event and existing owner:** [BanishedCondition](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/abjuration.py:1374) / Banishment; exact apply_owned_condition concentration ownership before publication. Later allocations stop if self-banishment already ended the original concentration.

**Evidence:** [tests/engine/test_banishment_dimension_door.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_banishment_dimension_door.py); [agent_docs/audits/SPELL_BANISHMENT_DIMENSION_DOOR_NATIVE_2026-10-04.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/SPELL_BANISHMENT_DIMENSION_DOOR_NATIVE_2026-10-04.md).

**Scope/tradeoff:** Actual native rule/selection change. Plane IDs are authored metadata only; no additional map, world simulation, copied inventory or displaced occupant.

### S25 — Dimension Door permits unseen destinations, companion travel and real mishaps

**Authority:** P6.

**Before → after:** A single position teleport required a visible destination and did not implement the companion/mishap/atomic endpoint contract. → Select self or one perceived nearby ally of caster size or smaller, then an in-map destination within 500 feet without LOS. An admitted obstructed/occupied/unsupported arrival spends cast and deals the same rolled4d6 force to both participants without movement. Legal endpoints commit together; arrival reactions see the completed pair.

**API, event and existing owner:** [DimensionDoor](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/conjuration.py:4289); CORE-05/07, existing PortalTransferEvent per participant with common spell parent and optional portal_uuid=None.

**Evidence:** [tests/engine/test_banishment_dimension_door.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_banishment_dimension_door.py), [tests/game/test_dimension_door_selection_replay.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/game/test_dimension_door_selection_replay.py).

**Scope/tradeoff:** Current implementation uses the existing ally relation as willing-companion admission; there is no new consent system. Destination coordinates stay within the authored map, and discovery does not reveal hidden occupancy by prefiltering it. No persistent portal object.

### S26 — Telekinesis is finite supported movement with the selected hostile impact

**Authority:** P6 explicit human final damage/landing decision, superseding earlier recommendations.

**Before → after:** Maintained Grab exposed free Move/Restrain follow-ups and held-victim semantics. → Cast requires one supported Huge-or-smaller creature and visible legal destination; both are within 60 feet of caster, displacement at most30 feet. Initial paid cast resolves once; a100-round concentration marker grants action-cost finite repeats. Hostile STR save negates movement; a committed hostile landing deals4d8 force+2d6 bludgeoning plus actual lower-support fall dice, then DEX solely against Prone. Allies take no impact/fall/forced-Prone damage from controlled placement.

**API, event and existing owner:** [Telekinesis](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/transmutation.py:1754) / TelekinesisMove/_resolve_telekinetic_transfer; existing marker UUID, SpellEvent BASE_ACTION, CORE-06 landing transaction. Obsolete Grab/Restrain definitions/registrations are removed.

**Evidence:** [tests/engine/test_telekinesis_landing.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_telekinesis_landing.py); [agent_docs/audits/SPELL_PACKET6_TELEKINESIS_NATIVE_REVIEW_2026-10-04.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/SPELL_PACKET6_TELEKINESIS_NATIVE_REVIEW_2026-10-04.md).

**Scope/tradeoff:** An explicit game adaptation, not SRD-held-creature Telekinesis. Earlier proposed3d6 or larger-of-impact/fall choices are not the implementation. No held-air/Stunned/Restrained owner, free repeat, object manipulation expansion or hover.

### S27 — Antimagic covers moving fields, items, retained creations and transport

**Authority:** P6 exact approved suppression scope.

**Before → after:** The field mainly blocked casts and removed/readded top-level magical conditions; caster exclusion, overlap, areas/items/created presence and transport were incomplete. → A caster-following10-foot field lasts600 rounds and applies exact tokens to retained owners (CORE-01–04). Native direct/area effects use actual propagation endpoints/cells; magical forced paths and teleport endpoints can be rejected. Magical item properties suppress while physical items remain; summoned actors/created props become spatially absent and restore at their exact free anchor. Lifetimes continue, expired owners never resurrect, and overlapping fields release independently.

**API, event and existing owner:** [AntimagicFieldZone](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/abjuration.py:3237); existing SpellProtectionRegistry, BaseCondition owners, area/item snapshots and placement transactions. EffectOrigin/condition/item AntimagicException distinguishes ARTIFACT, DEITY and FIELD; fields do not suppress each other.

**Evidence:** [tests/engine/test_antimagic_retained_contributions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_antimagic_retained_contributions.py); [agent_docs/audits/SPELL_ELECTRIC_ANTIMAGIC_MOVEMENT_REVIEW_2026-10-04.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/SPELL_ELECTRIC_ANTIMAGIC_MOVEMENT_REVIEW_2026-10-04.md).

**Scope/tradeoff:** This is the largest native dependency expansion in the trace. Exemptions require authored metadata; no string-name exemption. Original anchor occupancy can delay restoration. It is not a general summon rewrite or second absence queue.

### S28 — Existing Force/Ice/Stone walls retain suppression and local disintegration geometry

**Authority:** P7 preservation plus P3/P6 dependencies.

**Before → after:** Construction rules/forms mostly existed at the baseline. Large-section Disintegrate rejected cuts; destroyed-Ice residual footprint could expand; retained area suppression was not exposed on received section items. → Local removed volumes update remaining bands/shell; Ice residual air is bounded to its actual breached section. Force still retires the entire owner on Disintegrate. Stone material stays physically nonmagical from creation. Moving Antimagic changes received section construction_suppressions and actual crossing contributions without replacing the section UUID.

**API, event and existing owner:** [dnd/spells/wall_constructions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/wall_constructions.py), [dnd/core/wall_geometry.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/wall_geometry.py), [dnd/core/item_types.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/item_types.py); existing SolidWallZone/WallSection/FrigidAirZone and spatial/item events.

**Evidence:** [tests/engine/test_remaining_walls.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_remaining_walls.py), [tests/engine/test_disintegrate_outcomes.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_disintegrate_outcomes.py), [tests/game/test_construction_suppression.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/game/test_construction_suppression.py).

**Scope/tradeoff:** Baseline formation displacement, section/dome HP, damage immunity, Stone permanence and supported forms are preserved, not newly claimed features. No full sphere or new native curved collision model; received suppression geometry privacy remains a projection obligation.

### S29 — Wind and shared restraint contributions honor current native owners

**Authority:** P6 partial suppression; P7 preserve Wind and existing surface ownership.

**Before → after:** Wind crossing/ordinary-missile deflection/dispersal did not exclude suppressed cells. A renewed generic Restrained child could lose surviving spatial-restraint parent links. → Wind's same crossing/deflection/disperse queries use only active contribution cells. Existing SpatialRestraintSource escape actions are owner-gated; a newly applied Restrained membership is reattached to still-live spatial sources so exact cleanup does not discard them.

**API, event and existing owner:** [dnd/spells/wall_fields.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/wall_fields.py), [dnd/spatial/restraints.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spatial/restraints.py); existing wall contact and shared-child mechanisms.

**Evidence:** [tests/engine/test_remaining_walls.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_remaining_walls.py), [tests/engine/test_antimagic_retained_contributions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_antimagic_retained_contributions.py).

**Scope/tradeoff:** Wind joined-path rendering adds no native repeated damage or separate missile event. Existing Oil/Water/Web/Thorns rules are not rewritten; spatial/ignition.py is unchanged from the baseline.

## Class mechanics and result attribution

### K01 — Indomitable, Relentless Rage and Survivor expose their actual intervention

**Authority:** P8 C1/C4 missing typed outcomes; ordinary progression must stay canonical.

**Before → after:** These features executed, but successful/failed intervention and exact legacy condition owner were absent from retained result fields; direct progression has no synthetic condition to identify. → SavingThrowEvent.indomitable_reroll and TakeDamageEvent.relentless_rage retain success and optional real condition UUID. Survivor healing carries the actual optional source condition. EventQueue records effective CLASS_FEATURE handler evidence alongside the existing REACTION evidence. Canonical direct Barbarian grants tag the handler correctly.

**API, event and existing owner:** [dnd/classes/fighter.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/classes/fighter.py), [dnd/classes/barbarian.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/classes/barbarian.py), [dnd/content/characters/barbarian_grants.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/barbarian_grants.py), [dnd/types/class_features.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/types/class_features.py), [dnd/core/events.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py); existing reroll, health cap, heal, resource and handler paths.

**Evidence:** [tests/engine/test_class_presentation_facts.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_class_presentation_facts.py); [agent_docs/audits/SPELL_CLASS_ECS_REVIEW_2026-10-04.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/SPELL_CLASS_ECS_REVIEW_2026-10-04.md).

**Scope/tradeoff:** No extra action, condition, roll or resource debit. Optional owner=None is necessary for real direct progression, not permission to invent a condition. Effective emitted-handler evidence is causality data, not a second class event.

### K02 — Font of Magic publishes actual conversion direction and deltas

**Authority:** P8 C3.

**Before → after:** Conversion status text described nominal ranks/gains; capped actual sorcery-point gains and the resource debit were not a structured result. → ActionEvent.font_conversion records direction, slot level and actual point/slot deltas measured around the existing cost applier and resource change. Values may be redacted by subjective projection without losing the visible direction.

**API, event and existing owner:** [_font_conversion_costs](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/classes/sorcerer.py:1368), ConvertSlotToSP/ConvertSPToSlot; frozen FontConversion in the new passive class_features leaf.

**Evidence:** [tests/engine/test_class_presentation_facts.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_class_presentation_facts.py); [agent_docs/audits/SPELL_CLASS_ECS_REVIEW_2026-10-04.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/SPELL_CLASS_ECS_REVIEW_2026-10-04.md).

**Scope/tradeoff:** No new conversion exchange rate, free resource grant or duplicate cost. Raw native facts contain owner-private amounts; the separately reviewed client projection exposes only direction to foreign observers.

### K03 — Selected metamagic, affinity and Draconic Presence modes are passive facts

**Authority:** P8 C4/C5.

**Before → after:** Metamagic used a free string and snapshots omitted selected mode/energy; Draconic Presence lacked its visible spatial presence/mode evidence. → Closed MetamagicMode/DraconicPresenceMode values live in a passive leaf. Conditions expose metamagic_mode or energy_type; DraconicPresenceAura declares visible presence and observed presence_mode. Original aura saves, immunity and source ownership remain.

**API, event and existing owner:** [dnd/types/class_features.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/types/class_features.py), [dnd/classes/sorcerer.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/classes/sorcerer.py), [dnd/types/actor.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/types/actor.py), [dnd/types/senses.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/types/senses.py); existing ConditionState/PerceivedSpatialEffect only.

**Evidence:** [tests/engine/test_class_presentation_facts.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_class_presentation_facts.py).

**Scope/tradeoff:** The aura's visual disclosure is observable behavior, not merely typing. No change to spell slots, Draconic DC/targets, a new class action or string-parsed outcome. Metamagic filtering of retained spell actions is separately CORE-11.

### K04 — Mindless Rage cleanse has a still-live causal parent

**Authority:** P8 C2 required actual cleanse; defect found during native class acceptance.

**Before → after:** Rage/Frenzy passed a completed condition-application event as parent for Charmed/Frightened purge; the existing event attachment contract could reject the cleanup after the parent had finished. → Both calls use the still-live execution_event. Existing purge rules, ordering, resources and condition-removal transaction are preserved.

**API, event and existing owner:** [dnd/classes/rage.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/classes/rage.py); only the two _purge_mindless_rage_conditions parent arguments change.

**Evidence:** [agent_docs/audits/SPELL_CLASS_ECS_REVIEW_2026-10-04.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/SPELL_CLASS_ECS_REVIEW_2026-10-04.md) and [agent_docs/audits/SPELL_PACKET_IMPLEMENTATION_ROOT_REVIEW_2026-10-04.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/SPELL_PACKET_IMPLEMENTATION_ROOT_REVIEW_2026-10-04.md) record full Barbarian28-case verification..

**Scope/tradeoff:** This is a genuine native bug fix discovered by presentation acceptance, not a new Mindless Rage immunity rule. No completed-event attachment workaround or duplicate cleanse event.

### K05 — Retaliation executes one canonically bound ordinary Attack and records provenance

**Authority:** P8 C5 required equipped Retaliation; defect found during actual progression acceptance.

**Before → after:** retaliation_processor created an unbound Attack and returned None after invoking it, which could reject normal action execution and omit effective-handler evidence. → The child Attack has the existing action.attack BehaviorBinding, provided_by class_feature.barbarian.retaliation and the actual runtime owner. The processor returns its original triggering event after that same attack, allowing existing effective-emitter attribution.

**API, event and existing owner:** [retaliation_processor](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/classes/barbarian.py:1072); canonical Attack action and its existing reaction Cost remain the sole attack/payment.

**Evidence:** [agent_docs/audits/SPELL_CLASS_ECS_REVIEW_2026-10-04.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/SPELL_CLASS_ECS_REVIEW_2026-10-04.md); [tests/game/test_class_feature_presentation.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/game/test_class_feature_presentation.py).

**Scope/tradeoff:** Actual native execution/provenance repair, not extra damage or another class action. Presentation can select the real weapon trail without fabricating an additional body/attack event.

## Catalog and review support

### D01 — Canonical metadata matches corrected action and condition identities

**Authority:** P1–P6 integration requirement; no parallel spell registry.

**Before → after:** Catalog metadata retained stale concentration/range/target descriptions and obsolete Telekinesis grants; new retained conditions lacked canonical identities. → Catalog declares Darkvision duration/no concentration, Continual Flame object target, Ice Storm300-foot range/deadline, Banish multi-target count, Dimension Door companion selection/mishap, finite Telekinesis damage/saves and Sunbeam directional area. Action registry removes Grab/Restrain and retains Move. Condition registry adds Sunbeam/short blindness, Eyebite casting and Harm identities.

**API, event and existing owner:** [dnd/spells/catalog_content.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/catalog_content.py), [dnd/spells/content_metadata.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/content_metadata.py), [dnd/content_system/action_definitions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content_system/action_definitions.py), [dnd/content_system/condition_definitions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content_system/condition_definitions.py); existing installed content catalog remains the single source.

**Evidence:** [tests/engine/test_roster_support_spells.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_roster_support_spells.py), [tests/engine/test_weather_solar_spells.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_weather_solar_spells.py); architecture evidence below..

**Scope/tradeoff:** Some metadata affects discovery, so this is not labeled documentation-only. The target-type literal adds object; no duplicate spell catalog or import-time bootstrap is added.

### D02 — A bounded open-field review battlefield is registered

**Authority:** P4 production-resolution weather/solar acceptance.

**Before → after:** Existing review fields did not provide the required open area for the large weather/solar recordings. → battlefield.weather_review registers a28×28 bright open field using the existing battlefield builder.

**API, event and existing owner:** [dnd/scenarios/battlefield_catalog.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/scenarios/battlefield_catalog.py); existing scenario registry and tile construction.

**Evidence:** [tests/engine/test_weather_solar_spells.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_weather_solar_spells.py); packet4 recordings cited in the implementation ledger..

**Scope/tradeoff:** Review-support content addition, not a gameplay rule, campaign, new terrain system or character roster expansion.

## Native field and API review index

This is an explicit schema checklist for the feature rows, not another event pipeline. Defaults describe existing intact/ground/unsuppressed behavior. The new `class_features.py` file contains only closed Literal modes and frozen strict result records; it imports no entity, spell, class implementation or runtime dispatcher.

| Existing record/API | Added or changed contract | Feature |
| --- | --- | --- |
| BaseObject existing registry | Structural ContributionOwner; server-only contribution_owner_uuid/contribution_position; get_contribution_owner/contributions_active/allows_contribution_at | CORE-01–03 |
| BaseCondition | Provider token set, inherited suppression_providers, bind_owned_contributions, exact presence-return handler UUID, semantic capability flags, optional antimagic_exception | CORE-01–04, S27 |
| BaseHandler | runs_while_suppressed; existing enabled remains independent | CORE-01 |
| BaseBlock.remove_condition_by_uuid | consumed argument uses existing semantic removal reason | CORE-11, S06 |
| BaseBlock/Entity condition immunity | Exact source keys and active-owner query, including structural item sources | CORE-02 |
| Ability / Entity raw-check aggregation | check_bonus; raw-check bonus tuple becomes three components; no save/attack consumer | CORE-12 |
| PositionSelection | New closed EntityDestinationSelection arm | CORE-05 |
| BaseAction / AvailableTarget | include_owned_item_targets, multi_target_objects, secondary_targets, get_secondary_target_options/get_application_propagation | CORE-05, S08, S10 |
| AI ActionTarget | Optional immutable secondary_targets sequence; exact selected-primary validation | CORE-05 |
| ActionEvent | Optional font_conversion, propagation; item_magic_suppression_provider_uuids | CORE-03/05/14, K02 |
| SpellEvent / SpellAction | retained_effect_origin; optional antimagic_exception; BASE_ACTION classification for is_spell=False; real POSITION target_position | CORE-11, S27 |
| EffectOrigin / EffectEndpoint / EffectPropagationLink | Optional ARTIFACT/DEITY/FIELD exception; actual endpoint kind/UUID/position/base-height and application ID | CORE-05/14, S10/S27 |
| SpellProtection / SpellSuppression | suppresses_magic / antimagic distinction | CORE-04, S27 |
| ConditionState | suppression_provider_uuids, affected_item_uuid, metamagic_mode; existing energy_type populated by actual owners | CORE-14, S05/S07, K03 |
| SenseMode / PerceivedSpatialEffect | Owner UUID excluded from SenseMode wire; observed anchor_entity_uuid, energy_type, presence_mode | CORE-02/14, S21, K03 |
| LightSourceData / GridMap.add_light_source | sunlight, contribution_owner_uuid; refresh_contribution_lights and is_sunlit | CORE-04, S19 |
| EntityConfig/Entity/EntityStatsState | native_plane_id/current_plane_id; spatial_disposition; retained pending return and exact suppressed-presence owner | CORE-07, S24/S27 |
| PreparedSpatialReturn / Entity movement | No displaced list; optional nearest-free preparation, existing removal reservations, commit_position_transfers | CORE-07 |
| PortalTransferEvent | portal_uuid optional; effect_origin | CORE-07/14, S25 |
| ForcedMovementEvent / LandingKind | disclosed_path, start/end elevation feet, drop_feet, ground/fall/controlled/impact kind, effect_origin; affected positions include path | CORE-06/14 |
| Entity.receive_damage | Forward existing normal_hit_point_damage_cap; source_condition_uuid; zero_hp_disposition | CORE-08/14, S07/S13/S16 |
| Health | remains_disposition; preserve_normal_hit_points(previous_normal_hp, maximum_hp=...) | CORE-08 |
| TakeDamageEvent / DamageAppliedEvent | source_condition_uuid; request additionally zero_hp_disposition and optional relentless_rage | CORE-08/14, K01 |
| SavingThrowEvent | Optional indomitable_reroll | K01 |
| EntityCreatedEvent / LifeStateChangeEvent / DeathEvent | Committed remains_disposition; DeathEvent additionally destroyed_item_uuids/preserved_item_uuids | CORE-08/14 |
| Native ActorState / actor projection | Retained remains_disposition and spatial_disposition after-values | CORE-07/14 |
| ItemDestructionEvent / SpatialChangeEvent | Dust disposition, destroyed/preserved UUIDs, affected_volume/resulting_placement; removed_object_volume | CORE-09/14 |
| BaseItem | Exact suppression tokens; magically_created/creation_condition_uuid; saved absent placement; removed_local_bands; disintegration methods use existing retirement | CORE-03/09, S27 |
| WorldPlacementSpec / WorldObjectPlacement | Validated removed_local_bands/removed_bands; positions/band_heights expose remaining occupied bands | CORE-09 |
| WallAssemblyPresentationGeometry | Retained removed_sections of ObjectSectionVolume | CORE-09, S28 |
| ItemPresentationState / ItemEffectPresentationState | Top-level/effect suppression tuples; construction_suppressions; optional contribution_uuid and damage_type for nondamaging light | CORE-04/14, S08/S28 |
| EventQueue / Encounter | CLASS_FEATURE effective handler evidence; committed DEATH EFFECT; ROUND_END now traverses normal phases | CORE-08/13, K01 |

## Evidence and limits

The linked test files are the current executable behavioral contracts. Prior receipts pin their own checkpoint hashes and clearly state which results were independently rerun versus read from an implementation log. Their totals are **overlapping scopes, not an additive total**. This trace makes no new pass claim merely because a test file exists.

| Evidence already recorded | Scope and result available at trace time |
| --- | --- |
| Packet2 native review | Independently reran13 retained-flame/protection/range/metamagic/critical cases; current full nature file also appears in root's later acceptance. |
| Packet3 necromancy + packet6 landing review | Independent combined90 native cases after the temporary-HP fall-Prone correction; necromancy protection/source corrective rerun62 is separately recorded. |
| Packet5 native review | Read-only independent implementation review; inspected35 combined native cases, two variant checks and clean typing. Its original suppression dependency was subsequently handled by CORE-01–04/S27, not retroactively included in that initial verdict. |
| Banishment/DD native receipt | Author records94 native/selection/lifecycle/DAG cases and46 existing portal/legacy cases; root and final ECS receipts separately review return/privacy corrections. |
| Chain Lightning ECS review | Independently ran9 native and42 selection/control/Continual/DAG cases; actual branch Antimagic bug was reproduced and fixed before the bounded verdict. |
| Disintegrate native receipt | Author records42 native/DAG,133 death/lifecycle and52 wall cases; root independently reviews the implementation. Original partial-Ice failure is retained with the bounded remnant correction. |
| Force Attack review | Independent67 existing native checks plus five actual selection/stale-command probes cover lawful cost and rejection behavior. |
| Class ECS/final ECS receipts | Direct progression, optional owner facts, actual Retaliation, Mindless parent correction and foreign Font privacy reviewed. Independent78 class/privacy/Barbarian/construction checks and38 architecture/schema checks are recorded, with later54 handler-opt-in and52 Sleep/weather/equipment checks in their stated scopes. |
| Latest wider evidence cited by final ECS receipt | Root reports3,009 active native cases,46 final native class checks and120 architecture checks passing. Full-client acceptance/failure reconciliation is tracked separately; it is not asserted complete by this native trace. |

The largest scrutiny points are the broad owner gate (CORE-01–04), actual ordinary fall/Jump change (CORE-06), nearest-free versus exact-anchor return policy (CORE-07), committed death/gear teardown (CORE-08–09), ordinary Attack's invulnerable-object admission (CORE-10), shared raw-check/Frightened lifecycle (CORE-12), and ROUND_END phase expansion (CORE-13). They are disclosed as engine changes because presentation alone would not justify hiding them.

Native rules deliberately unchanged by this slice include the established wall formation/HP/permanence rules, normal attack budgets outside the named repairs, existing Oil/Water/Web ignition/quench mechanics, roster content and global support/ground topology. Existing `dnd/spatial/ignition.py`, the event type set and the core damage resolver are not edited. Schema/default migrations and presentation fixes outside `dnd/` belong in their companion traces.

## Complete native/AI file coverage

Every file in the baseline diff or untracked native/AI inventory maps below. A file can support more than one feature. “Passive schema” still changes the serialized/API contract; it does not mean no observable effect. Full before/after hashes live in the JSON appendix linked above.

| File | Change/category | Feature IDs |
| --- | --- | --- |
| [dnd/actions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/actions.py) | modified; native_behavior_or_projection | CORE-03, CORE-06, CORE-10, CORE-11 |
| [dnd/actions_functional.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/actions_functional.py) | modified; native_behavior_or_projection | CORE-05 |
| [dnd/actor_projection.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/actor_projection.py) | modified; native_behavior_or_projection | CORE-07, CORE-14 |
| [dnd/ai/contracts/control.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/ai/contracts/control.py) | modified; native_behavior_or_projection | CORE-05 |
| [dnd/ai/runtime/decision_epoch.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/ai/runtime/decision_epoch.py) | modified; native_behavior_or_projection | CORE-05 |
| [dnd/ai/runtime/execution.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/ai/runtime/execution.py) | modified; native_behavior_or_projection | CORE-05 |
| [dnd/blocks/abilities.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/abilities.py) | modified; native_behavior_or_projection | CORE-12 |
| [dnd/blocks/action_economy.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/action_economy.py) | modified; native_behavior_or_projection | CORE-03 |
| [dnd/blocks/base_item.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/base_item.py) | modified; native_behavior_or_projection | CORE-03, CORE-09, S08, S16, S27 |
| [dnd/blocks/equipment.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/equipment.py) | modified; native_behavior_or_projection | CORE-03, S05 |
| [dnd/blocks/health.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/health.py) | modified; native_behavior_or_projection | CORE-08, S13, S23 |
| [dnd/blocks/sensory.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/sensory.py) | modified; native_behavior_or_projection | CORE-02 |
| [dnd/classes/barbarian.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/classes/barbarian.py) | modified; native_behavior_or_projection | K01, K05 |
| [dnd/classes/fighter.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/classes/fighter.py) | modified; native_behavior_or_projection | K01 |
| [dnd/classes/rage.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/classes/rage.py) | modified; native_behavior_or_projection | K04 |
| [dnd/classes/sorcerer.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/classes/sorcerer.py) | modified; native_behavior_or_projection | CORE-11, K02, K03 |
| [dnd/conditions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/conditions.py) | modified; native_behavior_or_projection | CORE-02, CORE-03, CORE-11, CORE-12, S14 |
| [dnd/content/characters/barbarian_grants.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/barbarian_grants.py) | modified; native_behavior_or_projection | K01 |
| [dnd/content_system/action_definitions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content_system/action_definitions.py) | modified; catalog_composition | S26, D01 |
| [dnd/content_system/condition_definitions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content_system/condition_definitions.py) | modified; catalog_composition | S13, S14, S19, D01 |
| [dnd/core/action_types.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/action_types.py) | modified; passive_schema | CORE-05 |
| [dnd/core/base_actions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_actions.py) | modified; native_behavior_or_projection | CORE-03, CORE-05, CORE-11, CORE-14, S04, S08, S10, K02 |
| [dnd/core/base_block.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_block.py) | modified; native_behavior_or_projection | CORE-01, CORE-02, CORE-07, CORE-11 |
| [dnd/core/base_conditions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_conditions.py) | modified; native_behavior_or_projection | CORE-01, CORE-04, S27 |
| [dnd/core/base_object.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_object.py) | modified; native_behavior_or_projection | CORE-01 |
| [dnd/core/effect_types.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/effect_types.py) | modified; passive_schema | CORE-05, CORE-09, CORE-14, S10, S27 |
| [dnd/core/events.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py) | modified; native_behavior_or_projection | CORE-01, CORE-06, CORE-07, CORE-08, CORE-09, CORE-14, S07, S16, S25, K01 |
| [dnd/core/gridmap.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py) | modified; native_behavior_or_projection | CORE-04, CORE-06, CORE-09, S19 |
| [dnd/core/item_types.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/item_types.py) | modified; passive_schema | CORE-04, CORE-14, S08, S28 |
| [dnd/core/life_types.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/life_types.py) | modified; passive_schema | CORE-08 |
| [dnd/core/modifiers.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/modifiers.py) | modified; native_behavior_or_projection | CORE-01 |
| [dnd/core/presentation_geometry.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/presentation_geometry.py) | modified; passive_schema | CORE-09, S28 |
| [dnd/core/values.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/values.py) | modified; native_behavior_or_projection | CORE-01 |
| [dnd/core/wall_geometry.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/wall_geometry.py) | modified; native_behavior_or_projection | CORE-09, S28 |
| [dnd/encounter.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/encounter.py) | modified; native_behavior_or_projection | CORE-13 |
| [dnd/entity.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entity.py) | modified; native_behavior_or_projection | CORE-02, CORE-05, CORE-07, CORE-08, CORE-09, CORE-12, S03, S07, S08, S13, S16, S27 |
| [dnd/items/property_composition.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/items/property_composition.py) | modified; native_behavior_or_projection | CORE-03 |
| [dnd/monsters/traits.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/monsters/traits.py) | modified; native_behavior_or_projection | S19 |
| [dnd/scenarios/battlefield_catalog.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/scenarios/battlefield_catalog.py) | modified; review_support | D02 |
| [dnd/spatial/area_conditions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spatial/area_conditions.py) | modified; native_behavior_or_projection | CORE-04 |
| [dnd/spatial/restraints.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spatial/restraints.py) | modified; native_behavior_or_projection | S29 |
| [dnd/spells/abjuration.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/abjuration.py) | modified; native_behavior_or_projection | CORE-02, CORE-11, S10, S24, S27 |
| [dnd/spells/catalog_content.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/catalog_content.py) | modified; catalog_composition | S01, S08, S17, S19, S24, S25, S26, D01 |
| [dnd/spells/conjuration.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/conjuration.py) | modified; native_behavior_or_projection | S06, S18, S21, S22, S23, S25 |
| [dnd/spells/content_metadata.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/content_metadata.py) | modified; passive_schema | S08, D01 |
| [dnd/spells/divination.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/divination.py) | modified; native_behavior_or_projection | CORE-02, S01 |
| [dnd/spells/enchantment.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/enchantment.py) | modified; native_behavior_or_projection | S02, S03 |
| [dnd/spells/evocation.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/evocation.py) | modified; native_behavior_or_projection | CORE-06, CORE-13, S07, S08, S09, S10, S12, S17, S19, S20 |
| [dnd/spells/necromancy.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/necromancy.py) | modified; native_behavior_or_projection | CORE-12, S11, S13, S14, S15 |
| [dnd/spells/transmutation.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/transmutation.py) | modified; native_behavior_or_projection | CORE-02, CORE-06, S01, S04, S05, S16, S26 |
| [dnd/spells/wall_constructions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/wall_constructions.py) | modified; native_behavior_or_projection | CORE-04, CORE-09, S28 |
| [dnd/spells/wall_fields.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/wall_fields.py) | modified; native_behavior_or_projection | CORE-04, S29 |
| [dnd/types/actor.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/types/actor.py) | modified; passive_schema | CORE-07, CORE-14, S05, K03 |
| [dnd/types/actor_facts.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/types/actor_facts.py) | modified; passive_schema | CORE-07, CORE-14 |
| [dnd/types/class_features.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/types/class_features.py) | new; passive_schema | K01, K02, K03 |
| [dnd/types/event_facts.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/types/event_facts.py) | modified; passive_schema | CORE-06, CORE-14 |
| [dnd/types/senses.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/types/senses.py) | modified; passive_schema | CORE-02, CORE-14, S21, K03 |
| [dnd/types/spell_suppression.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/types/spell_suppression.py) | modified; passive_schema | CORE-04, S27 |
| [dnd/types/world_placement.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/types/world_placement.py) | modified; passive_schema | CORE-09 |

Coverage check: `59/59` native/AI files mapped; missing `0`; extra `0`. The only new native file is the passive class result/mode leaf. This inventory is frozen to the current hashes; later production changes require an explicit trace delta.
