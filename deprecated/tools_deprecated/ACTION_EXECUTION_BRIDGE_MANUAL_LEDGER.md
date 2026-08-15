# Action execution bridge — manual WP0 ledger

**Status:** hand-audited and second-pass-verified action-only baseline

**Date:** 2026-08-13

**Repositories:** `dnd_engine` and `/home/tommaso/Dev/NeuroClient`

**Production changes made by WP0:** none

This is the human-owned migration ledger for the existing action-execution bridge. It was assembled by reading the engine, projection contract/mapper, generated SDK boundary, NeuroClient mapper/intents/clips, the current presentation audit, and the renderer-neutral bridge study. Repository searches were used to find evidence; there is no parser framework, generated ownership graph, hashing protocol, or executable ledger system.

## Boundary used for every decision

The engine owns what happened: exact identity, selected subject/target, applications, results, geometry, state transition, and causal order. The SDK transports and reduces those facts. NeuroClient owns animation, timing, media, colors, body clips, local phase scheduling, camera, sound, and textual/visual style.

This first cut includes:

- ordinary, configured, class, item, monster, origin, and spell-follow-up actions;
- attacks;
- voluntary and forced movement, action-caused relocation, and presence transitions;
- checks and direct action results;
- the eight installed reactions;
- spell execution identity, applications, results, relationships, and area geometry;
- only the identity/causal handoff from an action to a condition or dynamic spatial effect.

This first cut excludes:

- static world, terrain, tile, and ground representation;
- condition appearance authoring or redesign;
- actor rigs, ancestry/body appearance, portraits, general icons, and equipment art;
- general persistence, deployment, or content-rollout architecture;
- changes to rules or spell mechanics merely to improve presentation.

## Dispositions

| Disposition | Meaning |
|---|---|
| `KEEP_NEUTRAL` | Existing engine fact and transport shape are renderer-independent; preserve them. |
| `KEEP_STATE_ONLY` | The resulting state patch is the complete presentation for this cut. |
| `FIX_IDENTITY` | Preserve an existing exact identity that is currently lost, substituted, or display-derived. |
| `FIX_CAUSALITY` | Preserve an existing parent/application/trigger/result relationship currently flattened or guessed. |
| `REPLACE_NEUTRAL` | Replace a lossy or renderer-shaped field with the engine fact already owned by execution. |
| `MOVE_CLIENT` | Remove a renderer choice from engine/wire and keep it only in the existing client recipe. |
| `DELETE` | Remove a redundant/dead bridge field with no replacement. |
| `CLOSE_GATE` | Turn an existing diagnostic/coverage calculation into a pre-stream admission failure. |
| `OUTSIDE_CUT` | Explicitly leave the surface unchanged in this migration. |

## Current structural baseline

| Surface | Manual result | Disposition | Evidence |
|---|---|---|---|
| Canonical cue dispatch | All 18 current cue kinds have an explicit NeuroClient mapper branch. Do not create another cue dispatcher. | `KEEP_NEUTRAL` | `server/player_replication_contract.py`; `app/src/render/subjectivePresentationMapper.ts::mapCueUnchecked` |
| Intent execution | All 25 current `ClipIntent` discriminants have dispatcher handling. Enrich this union in place; do not create a parallel semantic graph. | `KEEP_NEUTRAL` | `app/src/render/types.ts::ClipIntent`; `app/src/render/dispatcher.ts` |
| Public action recipes | All 91 public action/reaction definitions have an exact recipe or explicit movement disposition. Static recipe presence is not the runtime identity proof. | `KEEP_NEUTRAL` | `contentActionPresentationRecipes.json`; `actionPresentationDispositions.json`; `presentationBundle.ts` |
| Public spell recipes | All 116 current spell catalog rows compile to a client recipe (114 generated, 2 authored). Generated geometry is a valid client route; sprites are not mandatory. | `KEEP_NEUTRAL` | `spellAuthoring/generatedBaseline.ts`; `spellAuthoring/runtimeResolver.ts` |
| Journal pacing | The SDK already has authoritative and presentation replicas and an opaque head token. Server order is independent of local animation time. | `KEEP_NEUTRAL` | `sdk/typescript/src/subjectiveJournal.ts`; `app/src/engine/eventIngestion.ts` |
| Exact-definition admission | The bundle calculates missing exact definition refs but bootstrap treats them as diagnostics. A missing exact action binding can reach runtime. | `CLOSE_GATE` | `presentationBundle.ts`; `presentationBundleBootstrap.ts` |

## Cross-cutting identity, privacy, and contract rows

| ID | Current owner and bridge | Manual finding | Final disposition | Evidence / focused check |
|---|---|---|---|---|
| X01 | `BehaviorBinding` → `ActionEvent.behavior_binding` → content attribution | The correct exact semantic identity exists for normally admitted actions. Preserve it as the primary binding key. | `KEEP_NEUTRAL` | `dnd/core/base_actions.py`; `server/player_replication/mapper.py::_action_node` |
| X02 | Direct constructors that call `apply()` | Drop, Retaliation, configured Multiattack children, Command flee, Sunbeam Strike, True Strike, Eyebite flee/strike, and Telekinesis Grab bypass or lose the active authored binding. | `FIX_IDENTITY` | Existing direct-apply evidence in `PRESENTATION_BRIDGE_AUDIT.md`; focused execution per named site |
| X03 | Handler dispatch evidence | Passive class/monster handlers can cause action results, but dispatch evidence does not consistently retain the handler's existing `BehaviorBinding`. | `FIX_IDENTITY` | `dnd/core/events.py` handler evidence; mapper handler-evidence projection |
| X04 | `configured_action_ref` | The ten public configured Multiattack definitions are selected, but the root/children expose the internal generic implementation instead. | `FIX_IDENTITY` | `dnd/monsters/traits.py::MultiattackAction`; mapper `_action_node`; all ten configured rows |
| X05 | `ActionEvent.source_item_uuid` and `source_item_presentation` | Source-item identity is useful; the presentation snapshot also contains renderer/UI classification. Carry exact source item identity and neutral resource/location facts only. | `REPLACE_NEUTRAL` | `dnd/core/base_actions.py::ActionEvent`; item/spell projection |
| X06 | `ActionEvent.presentation_kind` / item presentation classifications | These fields exist only to select specialized client presentation. Exact action/source-item refs and results already identify the behavior. | `DELETE` | `dnd/core/action_types.py`; potion action producer; item cue mapper |
| X07 | `BaseObject.context` and reachable action-event context dictionaries | Open dictionaries currently carry semantic facts for some actions/reactions and cannot form a closed SDK contract. Replace each live semantic use with a typed fact; delete unused duplicates. | `REPLACE_NEUTRAL` | `dnd/core/base_object.py`; `DiceRollResultEvent`; action/reaction context reads |
| X08 | `SpellEvent.spell_id`, `EffectOrigin.source_id`, display-name normalization | Display-derived IDs are not stable action identity and already drift for True Strike variants. Exact selected `ContentRef` is the existing authority. | `FIX_IDENTITY` | `dnd/actions.py::SpellEvent`; `dnd/core/effect_types.py`; True Strike producers |
| X09 | Content visibility and subjective projection | Exact OBSERVED/INTERNAL implementation refs cannot join the public catalog. Emit an independently lawful public definition/provider/configured/source-item attribution or a closed systemic fact; never relabel one role as another. | `FIX_IDENTITY` | Acid Flask hidden spell implementation; configured Multiattack; `server/content_catalog.py` |
| X10 | Parent/child/application IDs | Projection IDs and ordered children are neutral, but the mapper reparents some nodes to a nearest delivered ancestor and synthesizes spell application IDs instead of using the engine-owned `ActionEvent.application_id`. Preserve execution-owned application IDs and only exact authorized direct edges; hiding a parent severs the edge. | `KEEP_NEUTRAL` + `FIX_CAUSALITY` | `PresentationCueBase`; `server/player_replication/presentation.py`; mapper graph construction; `BaseAction.apply()` |
| X11 | Engine/content/server bridge fields containing frames, clips, speeds, delivery/VFX, or art keys | Renderer policy is split across the engine model, content descriptors, and server cue payloads. None of these choices is a gameplay observation. | `MOVE_CLIENT` | action/item/spell models and descriptors; ItemAction, Shove, ForcedMovement, Attack, and Spell cue fields |
| X12 | Existing client mapper evidence | The mapper already retains per-cue bundle/binding/ownership/disposition evidence outside the SDK, but `VisualTransaction` has no immutable provenance and field-level semantic use is absent. Keep the existing evidence seam and enrich it only where required; do not add a graph or SDK fields. | `KEEP_NEUTRAL` + `REPLACE_NEUTRAL` | `subjectivePresentationMapper.ts`; `NormalSubjectiveFramePresentationPlan`; `VisualTransaction` |

## Generic actions and direct results

| ID | Producer / current bridge | Manual finding | Final disposition | Evidence / focused check |
|---|---|---|---|---|
| A01 | `BaseAction.apply()` target convolution → `ActionPresentationCue.target_uuids` | The cue deduplicates targets and has no durable application record. Repeated targets, selected position, object targets, and per-application result ownership are lost. | `REPLACE_NEUTRAL` | `dnd/core/base_actions.py`; `ActionPresentationCue`; `mapAction` |
| A02 | Generic action target types | Execution supports SELF, ENTITY, POSITION, POSITION_PATH, POSITION_LOS, POSITION_AOE, MULTI_ENTITY, and OBJECT. Every value needs an explicit closed disposition; current SELF identifies the source, while durable application IDs exist only on convolution children. Movement-specific path/LOS actions remain on their specialized movement bridge rather than being forced into generic applications. | `REPLACE_NEUTRAL` | `TargetType`; `BaseAction._declared_target_uuids`; `BaseAction.apply`; PickUp; AttackObject |
| A03 | Weapon Coat | Validation and application currently resolve the equipped weapon separately. Freeze one post-handler equipment endpoint `{owner, WeaponSlot, weapon UUID}` and make the mutation consume it. | `REPLACE_NEUTRAL` | `dnd/items/consumables.py::_ApplyWeaponCoatAction` |
| A04 | Generic action area fields | Breath Weapon and spell follow-up actions already own cone/line/other geometry, but the generic cue drops it. | `REPLACE_NEUTRAL` | Dragonborn Breath Weapon; Sunbeam Strike; generic Action mapper |
| A05 | `selection_parameter` | The typed choice exists on `BaseAction`/`ActionInfo` and is used by Sorcerer conversions, but it is not frozen onto `ActionEvent` or the cue. Copy the selected typed value into the execution observation rather than claiming it already crosses the bridge. | `REPLACE_NEUTRAL` | `BaseAction.selection_parameter`; `ActionInfo`; Sorcerer conversion actions |
| A06 | Checks and contests | Roll, bonus, DC where present, total, and existing optional result exist; a completed no-DC check is total-only. Do not invent a tie result. | `REPLACE_NEUTRAL` | D20/check events; Hide; Shove contest |
| A07 | Damage execution | Damage declaration/effect can cancel before mutation; current bridge can lack one replay-safe terminal snapshot. Freeze exactly one terminal result on every return path. | `REPLACE_NEUTRAL` | `dnd/blocks/health.py`; `Entity.receive_damage`; TakeDamage events |
| A08 | Damage affinity | `DamageResolution.components` already freezes canonical `DamageType` and `ResistanceStatus`, but projection drops the status. Extend the neutral damage result to transport authorized component affinity; never infer it from zero applied damage. | `REPLACE_NEUTRAL` | `dnd/core/damage.py`; `dnd/blocks/health.py::_preview_damage_components`; mapper `_damage_node` |
| A09 | Object damage | AttackObject damages a `BaseItem`; creature HP/temp-HP/life-state fields do not apply. Preserve an Object endpoint, structural HP, and destruction/location children. | `REPLACE_NEUTRAL` | `dnd/actions.py::AttackObject`; `dnd/blocks/base_item.py` |
| A10 | Healing | Requested/applied/resulting facts exist, but `hp_before` is only a local and cancellation can return before a terminal completion. Freeze before/resulting pools and an explicit applied/no-change/blocked/canceled terminal disposition on every return path; project without live reads. | `REPLACE_NEUTRAL` | `HealEvent`; `Entity.receive_healing`; heal mapper/client intent |
| A11 | Temporary HP | Previous/requested/resulting temporary HP exists but has no first-class presentation semantic node. | `REPLACE_NEUTRAL` | `TemporaryHitPointsEvent`; campfire/item/spell effects |
| A12 | Item charges and quantities | Item charge lineage/cost and inventory mutations are engine facts; the current item-action cue instead emphasizes animation constants. | `REPLACE_NEUTRAL` | `ActionEvent.item_charge_*`; consumable actions; inventory mutation events |
| A13 | Item location/transfer | Existing item events freeze resulting location/owner/container/tile/position/slot/merge and quantity facts, but not the prior location, and presentation mostly ignores them. Add the exact before state and preserve application/root ownership for Drop, PickUp, Loot All, consumption, destruction, and merges. | `REPLACE_NEUTRAL` | `ItemLocationStateEvent`; `dnd/blocks/base_item.py`; inventory/equipment actions |
| A14 | Equipment transition | SwitchWeapon already has a typed client route, but bundle coverage reports the wrong context and can miss the exact transition policy. | `FIX_CAUSALITY` | `actionContextPresentation.ts`; `presentationBundle.ts`; `mapEquipment` |
| A15 | Life-state transition | The cue already preserves previous/current state, reason, and cause, but `DieIntent`/`ReviveIntent` drop those facts and dying/stable becomes local feedback. Enrich the existing lifecycle intents/evidence with the immutable transition and cause; keep appearance unchanged. | `REPLACE_NEUTRAL` | life-state cue; `DieIntent`/`ReviveIntent`; `mapLifeState` |
| A16 | Action-caused condition application/removal | Condition events/cues retain identity, operation, and subject but drop `application_disposition`, while generic convolution ownership is flattened. Preserve disposition and exact root/application ancestry. Condition appearance remains unchanged. | `REPLACE_NEUTRAL` + `FIX_CAUSALITY` | `ConditionEvent`; condition cue/mapper; generic action convolution |
| A17 | Action-caused dynamic spatial effect | Existing lifecycle events already carry neutral operation/ref/layer/anchor/affected/previous facts and lawful cells are privacy-filtered. Keep that payload unchanged; only repair exact application ownership where suppressed generic parents break it. Spatial-effect state and visual representation remain outside this cut. | `KEEP_NEUTRAL` + `FIX_CAUSALITY` + `OUTSIDE_CUT` | `SpatialEffectChangeEvent`; `dnd/spatial_effects.py`; spatial-effect cue/mapper |
| A18 | Door/light/world transition cues | The current client deliberately state-settles these. Preserve the typed action parent and reducer-owned disposition; do not migrate static representation. | `KEEP_STATE_ONLY` | mapper door/light branches; state patches |
| A19 | Encounter-end feedback caused by an action | The terminal encounter payload is typed and rendered, but `_check_encounter_end()` emits it without parent/action lineage. Preserve the current payload and add exact cause linkage only when action-caused; turn-start/general encounter authoring remains outside this cut. | `KEEP_NEUTRAL` + `FIX_CAUSALITY` | `EncounterEndEvent`; `Encounter.end_encounter`; `mapEncounter` |
| A20 | `ItemActionPresentationCue` | `actor_clip`, `effect_frame`, `playback_speed`, `hidden_slots`, item presentation kind, and drink modality are renderer policy. | `MOVE_CLIENT` / `DELETE` | contract cue; `mapItemAction`; exact item recipe |
| A21 | `ShovePresentationCue` | Outcome and child ownership are gameplay; `Kick`, contact frame, and playback speed are not. | `KEEP_NEUTRAL` + `MOVE_CLIENT` | Shove cue; `mapShove`; action recipe |

## Attacks

| ID | Producer / current bridge | Manual finding | Final disposition | Evidence / focused check |
|---|---|---|---|---|
| AT01 | `AttackEvent` → `_attack_node` → `AttackPresentationCue` | Attacker, target, outcome, damage types, and ordered impact children are valid neutral facts. | `KEEP_NEUTRAL` | `dnd/actions.py::AttackEvent`; mapper `_attack_node`; `mapAttack` |
| AT02 | `AttackEvent.range` | The engine resolves canonical `Range`, but projection drops it and derives renderer delivery from equipment slot. Carry the canonical range and long-range result instead. | `REPLACE_NEUTRAL` | `AttackEvent.range`; attack validation; mapper `_attack_node` |
| AT03 | Ranged equipment slot → `PresentationProjectile.BOLT` | Every ranged-slot attack is labeled Bolt even when no bolt was selected by gameplay. Delete the carrier inference. | `DELETE` / `MOVE_CLIENT` | `server/player_replication/mapper.py`; attack cue; `AttackIntent` |
| AT04 | Attack source | Preserve exact item ref and selected `WeaponSlot` when disclosed; permit absent/coarse source when privacy does not authorize classification. | `KEEP_NEUTRAL` | attack source snapshot; item/equipment projection |
| AT05 | Natural/intrinsic attacks | Bite, Slam, and Claws are currently differentiated by names/rider matching, not a stable selected intrinsic form. Move that existing mechanical distinction to a canonical engine fact. | `REPLACE_NEUTRAL` | `NaturalAttack`; wolf/dire-wolf/ghoul rider matching |
| AT06 | Thrown/ammunition | The engine models capability but does not consistently select a distinct throw mode or ammunition item for an executed attack. There is no bridge field to migrate: do not add speculative wire vocabulary. | `OUTSIDE_CUT` | weapon capabilities and current Attack selection |
| AT07 | Client `AttackIntent` | Current melee/projectile intent split contains renderer delivery and local media. Keep neutral attack payload separate from the local recipe while retaining the existing runner. | `REPLACE_NEUTRAL` / `MOVE_CLIENT` | `app/src/render/types.ts::AttackIntent`; `AttackClip` |
| AT08 | Multiattack child attacks | Child attacks lose the selected public configured Multiattack attribution. | `FIX_IDENTITY` | ten configured Multiattack rows; `MultiattackAction.apply` |
| AT09 | Retaliation and True Strike nested attacks | Nested Attack exists, but enclosing authored identity is absent. Opportunity Attack demonstrates the working binding-copy pattern. | `FIX_IDENTITY` | Retaliation, True Strike, Opportunity Attack processors |

## Voluntary movement, forced movement, relocation, and presence

| ID | Producer / current bridge | Manual finding | Final disposition | Evidence / focused check |
|---|---|---|---|---|
| M01 | `MovementEvent` / movement cue | Family, trajectory, committed anchors/elevation, connector identity, and endpoint outcome already reach the cue. Movement cost, provocation policy, and termination facts exist on engine events but are not all transported; preserve them only in the neutral result/causal roles that consume them. | `KEEP_NEUTRAL` + `REPLACE_NEUTRAL` | `MovementEvent`; `StepMovementEvent`; `MovementPresentationCue`; movement mapper |
| M02 | Movement action identity | Move, Aggressive movement, Dragon Wings/Fly, Command-driven movement, and similar routes lose exact causing behavior attribution. | `FIX_IDENTITY` | movement producers; movement mapper |
| M03 | Termination reason | Collision, budget exhaustion, interruption, and other engine reasons are frozen by `MovementTerminationReason` but dropped by projection. Carry the selected canonical reason. | `REPLACE_NEUTRAL` | movement execution; `MovementTerminationReason`; movement cue |
| M04 | Jump arc | The engine validates an interior arc, while projection/client primarily preserve endpoints. | `KEEP_NEUTRAL` | Jump producer; movement projection; `JumpClip` |
| M05 | Elevation | Elevation reaches client movement anchors but current Move/Jump execution treats motion as planar. | `KEEP_NEUTRAL` | movement cue; `types.ts`; `MoveClip`/`JumpClip` |
| M06 | Connector transfer | Connector UUID, authored identity, endpoints, and revision are game facts. `presentation_key` is renderer authority. `TraversalConnectorKind` is currently documented as a presentation family; either reauthor it as a genuine physical connector form or keep it client-local rather than silently calling it mechanical. | `KEEP_NEUTRAL` + `REPLACE_NEUTRAL` + `MOVE_CLIENT` | `TraversalConnectorDefinition`; movement cue; connector projection; `MoveClip` |
| M07 | Cross-head locomotion | One engine move may be split across subjective heads; the client retires/restarts the body cycle per head. Preserve an explicit disclosed session continuity/sever/terminal fact. | `FIX_CAUSALITY` | replication runtime test; `LocomotionSessionExecutor.ts` |
| M08 | Opportunity Attack during movement | Provisional edge → reaction/attack → committed or rejected edge is already the correct causal model. | `KEEP_NEUTRAL` | movement event lineage; OA processor; movement reaction mapping |
| M09 | `ForcedMovementEvent` common distance | Push displacement, Eyebite movement cost, and Telekinesis endpoint delta are different quantities currently conflated as `actual_distance`. | `REPLACE_NEUTRAL` | `dnd/core/events.py::ForcedMovementEvent`; spell producers |
| M10 | Forced movement anchors | Preserve actual ordered committed anchors, elevations, blocked state, and final state-patch equality. Client timing derives from anchors plus recipe. | `REPLACE_NEUTRAL` | forced movement producers/mapper; entity position patch |
| M11 | Forced movement intent fields | Push direction/intended distance, compelled planned path/cost, and reposition requested endpoint belong only to their producing kind and may be privacy-filtered. | `REPLACE_NEUTRAL` | Shove/Thunderwave/Gust; Eyebite; Telekinesis |
| M12 | Forced movement blocker | Current blocker identity is a display string. Preserve `blocked: bool`; delete `blocked_by` until a real typed gameplay resolver exists. | `DELETE` | `GridMap.identify_blocker_at`; forced movement event |
| M13 | Forced movement renderer fields | `duration_ms`, `target_clip`, `brace_frame`, and `playback_speed` are hard-coded backend/client recipe values. | `MOVE_CLIENT` | forced movement cue; mapper payload construction; `ForcedMoveClip` |
| M14 | Immediate blocked push | Shove, Thunderwave, and Gust currently emit no `ForcedMovementEvent` when the first transition is blocked, and the mapper rejects zero displacement. Adding a completed zero-displacement event could affect handlers/logs, so WP0 does not authorize it. Preserve the current root result/state; treat any new attempted-movement event as a separate reviewed contract decision. | `OUTSIDE_CUT` | Shove/Thunderwave/Gust immediate-block branches; mapper `_forced_node` |
| M15 | Teleporting actions | Misty Step and Dimension Door commit direct position changes without a dedicated neutral transition. Emit a committed teleport observation only when the position mutation occurs. | `FIX_CAUSALITY` | `dnd/spells/conjuration.py`; subjective world diff |
| M16 | Banishment presence | Banishment directly mutates grid presence/indexes. This cut may preserve an action-owned exit/return result around that existing behavior, and any displaced occupant remains a separate forced reposition, but it must not redesign grid/world/ground state or change Banishment's return mechanics. | `FIX_CAUSALITY` + `OUTSIDE_CUT` | `dnd/spells/abjuration.py`; existing action/event lineage only |
| M17 | Mixed rendered/state-only position patches | Current settlement can snap only cue-empty state-only frames, so a mixed head can leave scene position stale. Each changed entity patch needs its exact movement/state-only owner. | `REPLACE_NEUTRAL` | `eventIngestion.ts`; `sceneRenderer.ts`; mapper plan |

## Installed reactions

| Reaction | Current engine boundary | Current bridge result | Final disposition | Focused verification |
|---|---|---|---|---|
| Opportunity Attack | Before movement-edge commit; emits an Attack | Correct causal placement and binding-copy pattern. | `KEEP_NEUTRAL` | provisional step, nested Attack, edge commit/reject |
| Retaliation | After positive post-mitigation damage; emits counterattack | Nested Attack loses exact reaction attribution. | `FIX_IDENTITY` | damage trigger → exact reaction → nested Attack |
| Protection | Before attack roll; changes roll distribution | Exact reaction may survive, but phase and disadvantage mutation/relationship are dropped. | `FIX_CAUSALITY` | advantage before/after plus trigger attack |
| Divine Smite | After hit/base roll and before damage application; appends damage packet | Client schedules a generic preamble too early; selected level and append relation are missing. Exact controlled detail stays private where required. | `FIX_CAUSALITY` | trigger impact, selected parameter, coarse/controlled append, resulting damage |
| Parry | After attack roll and before effects; rewrites hit to miss | Final miss survives, but post-roll prevention boundary and outcome mutation do not. | `FIX_CAUSALITY` | outcome before/after and exact attack stage |
| Counterspell | Before spell resolution; success interrupts | Strong result facts exist, but the verified trigger cue/application relationship is not fully transported. Client must not fabricate touch delivery. | `FIX_CAUSALITY` / `MOVE_CLIENT` | success/failure against exact cast trigger |
| Hellish Rebuke | During incoming damage; emits remote fire countereffect | Generic handler action and emitted action can duplicate actor presentation; trigger collapses to nearest Attack/Spell. | `FIX_CAUSALITY` | one reaction root, exact damage trigger, one emitted countereffect |
| Shield | Post-roll prevention or cancellation of Magic Missile-linked damage | Spell application remains automatic; the missing fact is the linked terminal Damage result being canceled, not a canceled spell application. | `FIX_CAUSALITY` | ordinary attack prevention and Magic Missile DamageResult cancellation |

Reaction transport should reuse exact reaction `ContentRef`, trigger presentation/application identity, existing `EventType`, `EventPhase`, `HandlerDispatchOutcome`, ordered emitted result IDs, and typed result mutations. Only a genuine missing attack-stage discriminator should be added. A generic renderer scheduling label is not causal truth.

## Spells

| ID | Producer / current bridge | Manual finding | Final disposition | Evidence / focused check |
|---|---|---|---|---|
| S01 | Spell catalog → client recipe compiler | All 116 current rows compile. Preserve exact-ref recipe ownership and generated client geometry. | `KEEP_NEUTRAL` | generated spell baseline/runtime resolver |
| S02 | `SpellEvent` exact behavior | Exact behavior is the binding authority; display-derived `spell_id` and names are not. | `FIX_IDENTITY` | `SpellEvent`; spell mapper; True Strike variants |
| S03 | Source item/provider | Spell execution can know its source item/provider, but spell projection normally carries only behavior attribution. Preserve lawful source attribution. | `FIX_IDENTITY` | `SpellEvent` source item; `_spell_node` |
| S04 | Execution applications | Current application IDs/indexes exist mainly on convolution children; root/single/selected-position/object paths rely on fallback or synthesis. The root action lifecycle must own ordered terminal Entity/Position/Object applications and result IDs. | `REPLACE_NEUTRAL` | `BaseAction.apply`; `SpellEvent`; `_spell_node`; `_attach_semantic_nodes` |
| S05 | Successful zero applications | Thaumaturgy, Continual Flame, Dimension Door, and Heroes' Feast can complete with zero applications; privacy may also disclose zero. Current client routes reject these frames. | `REPLACE_NEUTRAL` | canonical mapper test and client mapper probes |
| S06 | Position applications | Some route-shaped client variants reject position endpoints. Preserve the tagged endpoint instead of forcing an entity. | `REPLACE_NEUTRAL` | spell target contract; client `mapSpell` probes |
| S07 | Object applications | Continual Flame executes `TargetType.OBJECT`, but the root bridge has no reliable application record. Preserve the selected visible object identity and frozen execution position. | `REPLACE_NEUTRAL` | Continual Flame; object senses/world projection |
| S08 | Repeated and multi applications | Client mapping picks a first endpoint, flattens effects, or reclassifies route from visible application count. Preserve every disclosed application identity/order/children independently. | `REPLACE_NEUTRAL` | `mapSpell`; `CastIntent`; Magic Missile/Scorching Ray/repeated targets |
| S09 | Application resolution | The engine already owns attack outcome/save success, but the mapper currently invents a lossy parallel `SpellApplicationOutcome` (including collapsing critical miss, with dead resisted/immune members). Replace it with AUTOMATIC, ATTACK carrying canonical `AttackOutcome`, or SAVE carrying succeeded bool. Keep resistance/immunity on Damage results. | `REPLACE_NEUTRAL` | attack/save child events; mapper `_spell_application_outcome`; damage resolution |
| S10 | Per-application cancellation | The action loop supports a target event canceled at an existing phase. Represent that terminal lifecycle separately; do not overload AUTOMATIC or damage cancellation. | `REPLACE_NEUTRAL` | `BaseAction.apply` per-target event loop |
| S11 | Area geometry | Sphere/cone/line/cube/cylinder parameters are already authoritative. Client mapping drops cone angle, line width, cylinder height, immutable origin/direction, and other shape fields. | `KEEP_NEUTRAL` | geometry contract; `mapSpell`; `CastIntent`; `AoeFx` |
| S12 | Chain Lightning | Runtime can select each later target from any earlier selected target but currently discards the winning predecessor. Freeze that direct parent when selection occurs; privacy can sever it but never invent a bypass. | `FIX_CAUSALITY` | `dnd/spells/evocation.py::ChainLightning`; branch/hidden-parent cases |
| S13 | Fireball and similar visual travel | Current execution has no interruptible/collidable/observable in-flight game state. Do not add a server arrival phase; client recipe may stage manifestation then explosion locally. | `MOVE_CLIENT` | current synchronous spell event lineage |
| S14 | Legacy projectile/delivery/VFX fields | Current catalog/runtime fields mix morphology, range, cardinality, route, and assets. Delete them from runtime Event/cue/SDK authority. | `DELETE` / `MOVE_CLIENT` | spell catalog/API; `SpellPresentationCue`; client route selection |
| S15 | Optional spell physical description | No clean descriptor exists today: the legacy projectile/delivery fields are mixed renderer authority. A separately reauthored exact-ref catalog description may suggest bolt/ray/orb/beam/dart/spray/rain to humans or Studio draft generation, but it must be noncausal, optional, ignorable, and absent from Event/cue/SDK/binding identity. | `REPLACE_NEUTRAL` | legacy spell catalog metadata; content catalog target only; no runtime observation consumer |
| S16 | Spell follow-up generic actions | Sunbeam Strike, Eyebite Strike, Telekinesis Grab, Breath Weapon, and similar action roots lose exact identity and/or geometry when routed through generic Action. | `FIX_IDENTITY` / `REPLACE_NEUTRAL` | named producers; generic Action mapper |
| S17 | Acid Flask | The item route emits a hidden/OBSERVED spell implementation absent from public client definitions. Project the truthful public item/provider/action identity, not the private spell ref. | `FIX_IDENTITY` | `dnd/items/spell_items.py`; spell runtime resolver |
| S18 | Client `CastIntent` | Current delivery union (`aoe`, projectile, volley, touch, direct, etc.) is a renderer-shaped flattening. Keep one Cast intent with exact range/geometry/applications/results plus separate local phase graph. | `REPLACE_NEUTRAL` / `MOVE_CLIENT` | `types.ts::CastIntent`; `mapSpell`; `CastClip` |

Known geometry fidelity rows from the current audit:

- cone angle: Burning Hands, Color Spray, Cone of Cold, Fear, Prismatic Spray;
- line width: Gust of Wind, Lightning Bolt, Sunbeam;
- cylinder height: Flame Strike, Ice Storm, Sleet Storm.

## NeuroClient and Studio boundary

| ID | Current owner | Manual finding | Final disposition | Evidence / focused check |
|---|---|---|---|---|
| C01 | `subjectivePresentationMapper.ts` | Keep this as the one production mapping boundary. It must clone/preserve neutral semantic payload before selecting a local recipe. | `KEEP_NEUTRAL` | normal live head mapping and replay mapping |
| C02 | Existing `VisualTransaction` / `ClipIntent` graph | Enrich existing intents with immutable semantic evidence and local-recipe fields. Do not add another graph, scheduler, reducer, or semantic model. | `KEEP_NEUTRAL` | `types.ts`; dispatcher; clip queue |
| C03 | Result intents | Damage/Heal/Death/Revive exist but are lossy; Check, temp-HP, item-resource/location, object damage, and some transitions lack an exact semantic owner. Add members only to the existing union when rendering is needed. | `REPLACE_NEUTRAL` | `types.ts`; result mapper branches/clips |
| C04 | Floating badges/numbers/flashes | These may be local children but cannot be the sole semantic owner of a typed engine result. | `MOVE_CLIENT` | damage/heal/reaction mapper branches |
| C05 | Application handling | `ActionIntent`, `UseItemIntent`, and `CastIntent` must preserve exact application IDs, endpoints, lifecycle, ordered result IDs, and child intents rather than a first target or flat `onEffect`. | `REPLACE_NEUTRAL` | `mapAction`; `mapItemAction`; `mapSpell`; current intent types |
| C06 | Action recipe/art generation | Current action generation/Studio paths read backend tint, VFX profile, visual variant, route hints, and asset tags. Action compilation must read exact gameplay identity/facts, while all art stays local. | `MOVE_CLIENT` | action recipe population script; scenario providers; spell authoring catalog path |
| C07 | Studio scenario builders | Current Action/Spell Studio builders manufacture target applications, outcomes, HP, routes, geometry, paths, and timing before the production mapper. Studio must start from an explicit valid SDK frame and invoke the same mapper. | `REPLACE_NEUTRAL` | `studioSubjectiveActionFrame.ts`; `studioSubjectiveSpellFrame.ts`; `StudioScenarioCompiler.ts` |
| C08 | Studio synthetic scenarios | Current family builders are not this authority. Replace them with explicit, labelled, SDK-valid synthetic frames whose neutral facts are immutable except opaque IDs and one declared rigid spatial transform. | `REPLACE_NEUTRAL` | current Action/Spell Studio frame builders; target fixture/corpus checks |
| C09 | Bundle admission | Before stream attachment, every wire-emittable action subject/role/variant must resolve to an exact recipe, explicit generic client policy, state-only disposition, or installation failure. | `CLOSE_GATE` | bundle compiler; bootstrap before `startEventStream` |
| C10 | Action-owned media readiness | Current bundle bootstrap synchronously validates actor/ancestry profiles and awaits icon diagnostics before install, so out-of-scope appearance data can block the action gate. Detach those prerequisites while keeping their diagnostics visible; gate only media selected by compiled action recipes. | `REPLACE_NEUTRAL` + `CLOSE_GATE` | `presentationBundleBootstrap.ts`; actor/ancestry validators; game-icon diagnostics; action resource preparation |
| C11 | Position settlement | One normal head may have rendered movement for one entity and state-only movement for another. Settlement must be owned per changed entity patch, not by a frame-wide cue-empty predicate. | `REPLACE_NEUTRAL` | `eventIngestion.ts`; `sceneRenderer.ts`; replay drain |
| C12 | Head failure | A pre-commit failure currently latches the drain and leaves the journal head uncommitted, so a later head cannot overtake it. That alone is not retry safety: staging/clip execution may already have changed the scene, and the exact client bundle identity is not yet an immutable field on every normal-head plan. Preserve the journal rule, then add explicit scene restoration/reload ownership and frozen client-plan provenance. | `KEEP_NEUTRAL` + `REPLACE_NEUTRAL` | `eventIngestion.ts::PresentationHeadDrain.fail`; SDK journal; normal-head plan evidence |
| C13 | Local time | Clips can run at any local speed but cannot reorder engine heads or parent/result constraints. Backend milliseconds never repair missing causality. | `KEEP_NEUTRAL` | journal dual-clock behavior; clip queue |

## Second-pass row-by-row verification

This pass re-opened every row against the current source in both repositories. `CONFIRMED` means the source supports the row's description of the current bridge and its disposition; it does **not** mean the later migration is implemented. `CORRECTED` means the first wording overstated, omitted, or misclassified a fact and the main row above was edited. No row was accepted merely because it appeared in the earlier study or audit.

### Structural baseline

| Check ID | Row | Verdict | Second-pass source check |
|---|---|---|---|
| B01 | Canonical cue dispatch | `CONFIRMED` | 18 contract cue variants; all 18 dispatched by `mapCueUnchecked`. |
| B02 | Intent execution | `CONFIRMED` | 25 `ClipIntent` discriminants; all 25 handled by the existing dispatcher. |
| B03 | Public action recipes | `CONFIRMED` | 88 exact recipe rows plus 3 explicit dispositions close the current 91 public action/reaction refs. |
| B04 | Public spell recipes | `CONFIRMED` | 116 catalog rows materialize: 114 generated plus 2 authored drafts. |
| B05 | Journal pacing | `CONFIRMED` | SDK authoritative/presentation replicas and one-use opaque head tokens are distinct; NeuroClient spends after its barrier. |
| B06 | Exact-definition admission | `CONFIRMED` | Compiler records missing refs, but bootstrap installs and reports them instead of rejecting activation. |

### Cross-cutting rows

| ID | Verdict | Second-pass source check |
|---|---|---|
| X01 | `CONFIRMED` | `BehaviorBinding` survives normal action admission into mapper behavior attribution. |
| X02 | `CONFIRMED` | Drop, Retaliation, Multiattack children, Command, Sunbeam, True Strike, Eyebite, and Telekinesis contain direct/unbound child construction sites. |
| X03 | `CONFIRMED` | Handler dispatch evidence is not a complete `BehaviorBinding`; passive handler identity can vanish. |
| X04 | `CONFIRMED` | Discovery retains `configured_action_ref`; declaration/projection drops it for Multiattack root and children. |
| X05 | `CONFIRMED` | Source-item snapshot combines exact identity with `ItemPresentationState` UI/renderer classifications. |
| X06 | `CONFIRMED` | `ActionPresentationKind.DRINK` exists to choose the item-presentation route. |
| X07 | `CONFIRMED` | Open `context` reaches generated contracts; Divine Smite stores live semantic facts in it. |
| X08 | `CONFIRMED` | `SpellAction` normalizes display name into `spell_id`; True Strike variants demonstrate drift. |
| X09 | `CONFIRMED` | Public catalog omits non-public descriptors while mapper can emit their refs; Acid Flask and Multiattack are concrete cases. |
| X10 | `CORRECTED` | Projection IDs are neutral, but mapper reparents hidden ancestry and synthesizes spell application IDs instead of preserving execution IDs. |
| X11 | `CORRECTED` | Renderer-policy ownership spans engine models, content descriptors, and server cue fields, not only the event contract. |
| X12 | `CORRECTED` | Per-cue evidence already exists; the missing pieces are immutable transaction/plan provenance and field-use evidence, not a new provenance system. |

### Generic action/result rows

| ID | Verdict | Second-pass source check |
|---|---|---|
| A01 | `CONFIRMED` | Convolution alone allocates applications; action cue deduplicates UUIDs and client intent has no application records. |
| A02 | `CORRECTED` | `TargetType` has eight values, including POSITION_PATH and POSITION_LOS; SELF currently identifies the source. |
| A03 | `CONFIRMED` | Weapon Coat resolves slot/weapon once in validation and again in apply. |
| A04 | `CONFIRMED` | Breath Weapon/Sunbeam own shape dimensions that the generic action cue drops. |
| A05 | `CORRECTED` | `selection_parameter` exists on action discovery objects, not on `ActionEvent`/cue; transport is missing. |
| A06 | `CONFIRMED` | D20/check events support DC-result and total-only completion; Shove owns contest facts. |
| A07 | `CONFIRMED` | Damage cancellation/zero paths can return without the positive-only projected `DamageAppliedEvent`. |
| A08 | `CORRECTED` | `ResistanceStatus` is frozen in damage resolution but dropped by `_damage_node`; it is not already transported. |
| A09 | `CONFIRMED` | AttackObject mutates `BaseItem` structural HP and may emit location/destruction children; current damage cue is creature-shaped. |
| A10 | `CORRECTED` | Heal has requested/actual/resulting facts, but before HP is local and cancellation lacks a terminal completion. |
| A11 | `CONFIRMED` | Temporary-HP event owns previous/requested/resulting values; no presentation semantic branch consumes it. |
| A12 | `CONFIRMED` | Charge lineage/mutation exists; presentation instead carries animation constants. |
| A13 | `CORRECTED` | Item events freeze resulting location but not before location; most exact transfer facts are not presented. |
| A14 | `CONFIRMED` | Client consumes equipment transition context while bundle coverage reports structural state-only ownership. |
| A15 | `CORRECTED` | Cue has lifecycle reason/cause; Die/Revive intents drop it and dying/stable becomes feedback. |
| A16 | `CORRECTED` | Condition cue drops `application_disposition` and generic application ancestry is flattened. |
| A17 | `CORRECTED` | Existing spatial lifecycle payload is already neutral; only application ownership is in this cut, with state/visual redesign excluded. |
| A18 | `CONFIRMED` | Door/light mapper branches intentionally emit no intent and rely on state patches. |
| A19 | `CORRECTED` | Encounter-end payload is typed, but automatic encounter-end emission lacks action parent lineage. |
| A20 | `CONFIRMED` | ItemAction cue and mapper contain actor clip/frame/speed/slot policy already owned by recipes. |
| A21 | `CONFIRMED` | Shove outcome is mechanical; Kick/contact frame/speed are presentation policy. |

### Attack rows

| ID | Verdict | Second-pass source check |
|---|---|---|
| AT01 | `CONFIRMED` | Attack cue preserves actor, target, canonical outcome, damage types, and ordered impact child IDs. |
| AT02 | `CORRECTED` | `AttackEvent.range`/`is_long_range` are engine facts but projection drops both; `KEEP_NEUTRAL` alone was inaccurate. |
| AT03 | `CONFIRMED` | `_attack_node` maps every ranged equipment slot to `PresentationProjectile.BOLT`. |
| AT04 | `CONFIRMED` | Selected `WeaponSlot` and source-item attribution exist, subject to current identity visibility. |
| AT05 | `CONFIRMED` | Natural attack effect/rider matching depends on display names such as Bite/Claws. |
| AT06 | `CORRECTED` | No executed throw/ammunition selection field exists to delete; the correct decision is to add nothing in this cut. |
| AT07 | `CONFIRMED` | Client intent is a melee/projectile presentation union with local media/timing and no complete neutral payload. |
| AT08 | `CONFIRMED` | Configured Multiattack child attacks are direct/unbound. |
| AT09 | `CONFIRMED` | Retaliation/True Strike nested attacks omit outer authored identity; Opportunity Attack copies the active binding. |

### Movement, relocation, and presence rows

| ID | Verdict | Second-pass source check |
|---|---|---|
| M01 | `CORRECTED` | Cue retains family/trajectory/anchors/elevation/endpoint; costs, provocation, and termination live on engine events and are not all transported. |
| M02 | `CONFIRMED` | Multiple movement producers create roots/children without preserving the selected causing behavior attribution. |
| M03 | `CORRECTED` | Canonical `MovementTerminationReason` exists but is absent from the movement cue. |
| M04 | `CONFIRMED` | Jump root freezes a disclosed arc; cue/client direct-arc route uses only takeoff/landing anchors. |
| M05 | `CONFIRMED` | Elevation reaches client anchor evidence while Move/Jump playback remains planar. |
| M06 | `CORRECTED` | Connector identity/revision are neutral, but `presentation_key` and the currently presentation-described `kind` cannot both be called mechanical unchanged. |
| M07 | `CONFIRMED` | Session owner keys stream/generation/entity and retires after each intent; there is no cross-head engine session identity. |
| M08 | `CONFIRMED` | Step movement owns the provisional pre-edge reaction boundary and projection attaches surviving reaction children to that segment. |
| M09 | `CONFIRMED` | Shove/push, Eyebite, and Telekinesis store incompatible quantities in common distance fields. |
| M10 | `CONFIRMED` | Current forced cue has only start/end and renderer duration; it lacks ordered committed anchors and explicit patch equality. |
| M11 | `CONFIRMED` | Push, compelled path, and reposition producers own different optional intent facts. |
| M12 | `CONFIRMED` | Blocker is an untyped display string from `identify_blocker_at`; boolean blocked state is the only closed fact. |
| M13 | `CONFIRMED` | Mapper computes milliseconds and hard-codes TakeDamage/brace/speed into the forced cue. |
| M14 | `CORRECTED` | Immediate-block producers emit no forced event and mapper rejects zero displacement; WP0 now explicitly does not change that behavior. |
| M15 | `CONFIRMED` | Misty Step and Dimension Door commit positions without a dedicated action transition observation. |
| M16 | `CORRECTED` | Banishment mutates grid indexes directly; ledger now limits itself to action causality and explicitly forbids world/presence redesign or mechanic changes. |
| M17 | `CONFIRMED` | State-only position settlement runs only for a cue-empty state-only frame and then snaps every upserted entity. |

### Reaction rows

| ID | Reaction | Verdict | Second-pass source check |
|---|---|---|---|
| R01 | Opportunity Attack | `CONFIRMED` | Trigger is one step boundary; nested attack copies active reaction binding before apply. |
| R02 | Retaliation | `CONFIRMED` | Positive damage handler constructs a nested attack and returns no durable reaction result identity. |
| R03 | Protection | `CONFIRMED` | ATTACK/EXECUTION handler adds disadvantage before the roll; final cue does not preserve mutation relationship. |
| R04 | Divine Smite | `CONFIRMED` | Damage-roll handler appends a packet and stores selected level/dice details in open context. |
| R05 | Parry | `CONFIRMED` | Post-roll ATTACK/EXECUTION handler changes a HIT to MISS after checking the rolled total. |
| R06 | Counterspell | `CONFIRMED` | Dedicated event/cue has resolution facts, but client maps a fabricated touch cast route and exact trigger scheduling is incomplete. |
| R07 | Hellish Rebuke | `CONFIRMED` | Damage handler creates its own ActionEvent/effect path; current handler/action projection can duplicate or misplace the reaction root. |
| R08 | Shield | `CONFIRMED` | Attack branch rewrites HIT to MISS; Magic Missile branch cancels linked TakeDamage while the spell application itself remains automatic. |

### Spell rows

| ID | Verdict | Second-pass source check |
|---|---|---|
| S01 | `CONFIRMED` | Current catalog/compiler report closes all 116 exact spell refs. |
| S02 | `CONFIRMED` | Exact behavior binding exists; mapper dispatches display-derived `spell_id`. |
| S03 | `CONFIRMED` | Spell declaration inherits source-item snapshot, but `_spell_node` emits only behavior attribution. |
| S04 | `CONFIRMED` | Application IDs exist only on convolution children; root/single/position/object cases fall back or disappear. |
| S05 | `CONFIRMED` | Current probes identify valid zero-application completions and client routes that reject them. |
| S06 | `CONFIRMED` | Current cue can carry position, but projectile/touch/volley client routes require an entity. |
| S07 | `CONFIRMED` | Continual Flame executes OBJECT; current spell application bridge has only entity/position and no root object record. |
| S08 | `CONFIRMED` | Client routes choose first target, flatten effects, or use visible count to choose volley. |
| S09 | `CORRECTED` | Existing mapper enum is derived/lossy, collapses critical miss, and has dead resisted/immune members; canonical engine facts must replace it. |
| S10 | `CONFIRMED` | Per-target loop observes canceled target events but skips them instead of terminalizing a delivered application record. |
| S11 | `CONFIRMED` | Typed area contract owns full shape data; client projection reduces several shapes to radius/center/planar live-state inputs. |
| S12 | `CONFIRMED` | Chain Lightning chooses against any earlier target but records only the new target, not the winning predecessor. |
| S13 | `CONFIRMED` | Fireball executes synchronously with no rule-visible in-flight phase. |
| S14 | `CONFIRMED` | Legacy runtime/catalog/cue route fields mix projectile morphology, target count, range, and VFX. |
| S15 | `CORRECTED` | The clean optional description is a new reauthored catalog-only target; legacy projectile fields are not that neutral descriptor. |
| S16 | `CONFIRMED` | Named follow-up actions use the generic action route and lose identity/geometry. |
| S17 | `CONFIRMED` | Acid Flask executes through an OBSERVED spell implementation absent from the public catalog. |
| S18 | `CONFIRMED` | Current CastIntent is a renderer-route union and loses exact application identity/outcome/geometry. |

### NeuroClient and Studio rows

| ID | Verdict | Second-pass source check |
|---|---|---|
| C01 | `CONFIRMED` | Live and replay use the same `subjectivePresentationMapper` boundary. |
| C02 | `CONFIRMED` | One existing `VisualTransaction`/`ClipIntent` graph and dispatcher own playback. |
| C03 | `CONFIRMED` | Existing result intents are lossy and several included result families have no exact intent member. |
| C04 | `CONFIRMED` | Badges/numbers are local feedback children and currently substitute for some missing semantic payloads. |
| C05 | `CONFIRMED` | Action/UseItem/Cast intents flatten applications into targets/`onEffect`/first route. |
| C06 | `CONFIRMED` | Action generation reads tint/VFX; scenario selection reads visual variant; spell authoring reads route hints/assets. |
| C07 | `CONFIRMED` | Action/Spell Studio builders manufacture gameplay outcomes, HP, paths, applications, routes, and geometry before the production mapper. |
| C08 | `CORRECTED` | Explicit SDK-valid synthetic frames are the replacement contract, not the behavior of current family builders. |
| C09 | `CONFIRMED` | Bundle compilation occurs before stream start, but missing exact definitions remain diagnostic rather than admission failure. |
| C10 | `CORRECTED` | Current bundle load gates on actor/ancestry validators and awaited icon diagnostics; these must be detached without deleting diagnostics. |
| C11 | `CONFIRMED` | Mixed rendered/state-only heads lack per-patch settlement ownership. |
| C12 | `CORRECTED` | Drain latch keeps the token/head pending, but mutated staging/scene and bundle provenance make simple retry unsafe. |
| C13 | `CONFIRMED` | SDK token/order is independent of local animation duration; clip timing cannot add missing causality. |

### Second-pass totals

- 104 rows checked individually: 6 structural, 12 cross-cutting, 21 generic/results, 9 attacks, 17 movement/relocation/presence, 8 reactions, 18 spells, and 13 NeuroClient/Studio rows.
- 80 rows were confirmed as written.
- 24 rows were corrected in place: X10–X12; A02, A05, A08, A10, A13, A15–A17, A19; AT02, AT06; M01, M03, M06, M14, M16; S09, S15; C08, C10, C12.
- No production behavior was changed. The only edited artifact is this manual Markdown ledger.

## Exact known runtime identity exceptions

These are not new categories; they are the current concrete instances that must be accounted for while applying `FIX_IDENTITY`:

- Drop: direct action instance bypasses the binding gateway.
- Retaliation: nested Attack lacks exact reaction attribution.
- Opportunity Attack: existing good pattern; copies the active reaction binding.
- Configured Multiattack: all ten public variants lose the configured root identity and child attribution.
- Command flee: movement loses the Command cause identity.
- Sunbeam Strike: direct follow-up Action loses its binding and line facts.
- True Strike: nested Attack loses enclosing identity; display-derived wire IDs drift.
- Eyebite flee/strike: Dash and follow-up action lose Eyebite attribution.
- Telekinesis Grab: direct follow-up action loses its binding.
- Acid Flask: private spell implementation cannot be the public renderer identity.

The ten affected configured Multiattack identities are:

- `action.monster.multiattack.bandit_captain.melee`
- `action.monster.multiattack.bandit_captain.ranged`
- `action.monster.multiattack.cult_fanatic`
- `action.monster.multiattack.knight`
- `action.monster.multiattack.scout.longbow`
- `action.monster.multiattack.scout.shortsword`
- `action.monster.multiattack.spy`
- `action.monster.multiattack.thug`
- `action.monster.multiattack.veteran.melee`
- `action.monster.multiattack.veteran.ranged`

## Migration order implied by the ledger

This ledger does not authorize production edits. It establishes the following smallest dependency order for later implementation:

1. Preserve exact runtime identity and close the action event/application/result vocabulary.
2. Project those facts with existing privacy authority and regenerate the SDK hard cut.
3. Preserve the complete facts in the existing NeuroClient intent/transaction graph.
4. Move all animation/timing/media decisions into existing client recipes and delete the old renderer-shaped wire fields.
5. Make complete action binding/disposition/media closure a pre-stream admission gate.
6. Verify live, replay, privacy-filtered, zero-application, repeated-application, state-only, and failure/pending-head cases.

## WP0 completion statement

This Markdown file is the WP0 result: a manually curated, action-only baseline of the existing bridge and the intended disposition of each known semantic seam. The existing audit JSON/Markdown and study remain supporting evidence, not migration authorities. Later work updates this ledger by human review when a concrete source owner is discovered; it does not introduce an automated ledger system.

No production engine, server, SDK, NeuroClient, Studio, world, or rendering behavior was changed while producing this ledger.
