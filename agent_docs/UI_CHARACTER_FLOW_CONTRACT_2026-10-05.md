# Local character, progression and inventory UI contract

2026-10-05. Source study only; no production changes. This closes the discovery prerequisite in PLAYER_UI_PLAN_2026-10-05.md. The paused server is not a supported execution route. Native creation/hydration working in memory must not be advertised as a working disk save/load pipeline.

## 1. Supported character inputs and exact owners

| Input | Current source / contract | UI behavior |
|---|---|---|
| Complete build | `dnd/content/characters/builds.py`: CharacterBuild, CharacterAppearance, resolve_character_build | Edit an immutable candidate; validate through the existing resolver. Do not construct a live Entity for every widget change. |
| Creation | prepare_character, create_character | prepare installs origin, class grants, initial items and standard actions; create commits the sole birth. Failed uncommitted creation discards its entity. Composition entry owns content bootstrap. |
| Classes | `class_definitions.py`: FIGHTER_DEFINITION, BARBARIAN_DEFINITION, SORCERER_DEFINITION and corresponding resolve_*_level | Fighter/Champion, Barbarian/Berserker, Sorcerer/Draconic Bloodline only. Each has authored levels through 20; do not offer retired registry classes. |
| Species | `origin_definitions.py` and `types/character_progression.py` | Dragonborn, Dwarf, Elf, Gnome, Half-Elf, Half-Orc, Halfling, Human, Tiefling. Variants: Hill Dwarf, High Elf, Rock Gnome, Lightfoot. Present only each species' permitted variants and declared choice rows. |
| Background | Background enum / origin definitions | Acolyte and Adventurer. Do not copy additional legacy-server backgrounds into the selector. |
| Ability scores | resolve_character_build + core.progression.point_buy_cost + resolve_origin | Exactly 27 points; six named ability inputs. One +2 and one +1 flexible bonus, with ordered/unique selections enforced by resolver. Show native validation errors, not a second rules implementation. |
| Class choices | ClassChoiceDefinition(choice_id, selections, allowed_values), class/subclass level tables | Fighting style, class skills, starting package, subclass, ASI/feat, Sorcerer cantrips/known spells/replacement, ancestry and metamagic as declared. Selection cardinality is native data. ASI combination and prerequisites remain resolver checks. |
| Multiclass | resolve_character_build / progression._validate_multiclass_prerequisites | Total cap20; Barbarian STR13, Fighter STR13 or DEX13, Sorcerer CHA13. Requirements apply to entering and existing classes. No UI bypass. |
| Equipment package | `content/items/item_loadouts.py`: CLASS_STARTING_LOADOUTS, BACKGROUND_ITEM_LOADOUTS, ItemLoadoutEntry | Use selected package IDs and existing ordered plans to assemble build.item_loadout once. Class choice resolution validates the package ID but current class grant functions do not install its items; prepare_character installs only the explicit item_loadout. Premades supply that list explicitly. Do not assume choosing a package alone grants gear. |
| Appearance | CharacterAppearance.config → AppearanceConfig | Existing body/head category, skin/hair/beard color, beard flag and scale fields. Expose supported modular choices from actual art metadata; no species-to-art promise absent a mapping. Preserve natural scale by default. Portrait is a separate UI preference, not a mechanical appearance trait. |
| Prepared spells / toggles | PreparedSpellSelection, FeatureToggleSelection; resolve_character_build | Only supported known spells/source IDs and owned toggles. Current toggle allowlist: great-weapon fighting, protection, indomitable, retaliation, lucky. Do not expose arbitrary handler switches. |

Existing premade shortcuts are normal builds: hero.fighter_l5_shield_torch, hero.barbarian_l5_berserker_torch, hero.sorcerer_l5_standard_torch, hero.fighter_2_sorcerer_3_spellblade (`premades.py`). They are not an alternate creator domain.

For a current-level preview, pure resolved definitions supply choices and validation. A full derived sheet/visual preview may use one isolated scratch preparation outside an active encounter and discard it; do not reset global runtime while a live encounter exists. The safer initial UI preview uses the authored appearance input and pure build summaries until final composition.

## 2. Progression: working API, not an XP policy

`dnd/content/characters/progression.py:add_class_level(entity, AppliedClassLevel)` validates the cap/prerequisites, preflights the native level event, applies the class family, reconciles origin/proficiency, and publishes EntityLevelAddedEvent. Its exception path removes the applied family and reverses reconciliation. `remove_last_class_level` exists, but its safety/active-child checks do not authorize a new free-respec UI.

`hydrate_class_progression(entity)` rebuilds origin/class owners and receipts from already-loaded semantic rows. It is silent and requires an entity without installed receipts. It is not a file decoder, runtime-state restore, or function to call on a freshly created character whose classes are already installed. Tests in `tests/progression/test_direct_character_progression.py` explicitly create a blank entity, assign semantic fields, then hydrate and verify no extra events.

Level-up screen: choose one next class; derive that resulting class level and total level from current rows; expose the exact new definition rows; build candidate AppliedClassLevel; validate a complete candidate build before committing; on Confirm call add_class_level once and capture its native operation. Cancel changes no live state. Eligibility must come from an existing earned-level source, not a new XP algorithm in UI. There is no local Pygame earned-level/promotion policy currently wired. Proposed initial flow is an explicit pre-encounter build level selection (1–20), with in-session automatic XP/level awards outside this lane; if the product wants earned campaign levels now, that policy needs a human decision.

## 3. Persistence scope: full-world save deferred

The user prefers whole-map plus character save/load only if an existing easy integration exists. The inspected native owners provide no complete round-trip restore route. Therefore this UI delivery does not implement disk Save/Load or evolve a character-only durable format. Section 7 records the exact feasibility evidence. Creation, party deployment and current-encounter inventory remain in scope; passive recording remains recording, never a resumable game save.

`hydrate_class_progression` is in-memory grant reconstruction, not a disk loader. Legacy `core/content/durable_characters.py` definitions use older ContentRef-backed recipes, whereas current creation uses direct Species/CharacterClass enums and AppliedClassLevel. The old `server/character_build_preview_worker.py` imports absent character_materialization code. Do not revive this paused server path or start a replacement persistence architecture inside the UI.

## 4. Session and human party

`game/session.py:create_session` currently creates two premades at fixed player positions, or uses `_create_authored_session` which expects exactly one human and one AI roster slot. Session already stores a tuple player_uuids; multiple human-controlled entities are real native combatants, each with HumanController. There is no need for a new party entity/system.

Minimal change: allow an explicitly selected list of validated character deployment inputs and positions at the existing session composition boundary, replacing only the hardcoded two premades. Preserve authored encounter enemy composition and one shared NativeAIController. Capture birth events after equipment/grants are ready. The pre-deployment roster is an ordered tuple of selected build drafts/premade references with local UI identities, separate from runtime UUIDs; it is not a durable character save.

`_current_player` requires active encounter, in-progress turn, actor in player_uuids, matching current entity and HumanController. Portrait selection inspects/focuses only; it does not change turn ownership or observer permission. `discover_player_actions` and `execute_player_action` use this gate. Every mutating inventory command needs the same gate during combat. Pre-deployment edits modify the selected build draft instead, never forge a combat turn.

## 5. Inventory, equipment and loot commands

| UI operation | Current native command | Required application wiring |
|---|---|---|
| Inspect inventory | PlayerActor/observations controlled_items, exposed visual_loadout, projected known item data | Own-character inventory only. Do not read all live Entity inventories in the renderer. None means not disclosed, not empty. |
| Equip | Entity.equip_item(item_uuid, slot); Equipment.compatible_slots_for_actor / resolve_equipment_slot and equip_transaction | New thin Session wrapper with _current_player, cursor capture, native call, Operation return. UI asks native compatible slots; do not directly mutate equipment dicts. |
| Unequip | Entity.unequip_item(slot, allow_ground_fallback=...) | Same gate/capture. Existing default can drop if inventory full; show that outcome/confirmation rather than silently imply inventory transfer. No new action cost assumed. |
| Change melee/ranged use | Existing attack discovery/declared weapon slot and native weapon-set transitions | Both loadouts coexist. Render from native resulting visual loadout; no independent hotbar equipment truth. |
| Drop | Discovered Drop variant per nonintrinsic inventory item; execute_player_action. execute_drop also exists but bypasses Session gate unless wrapped | Select current/adjacent legal position from discovery. Item UUID is source identity. Do not invent a throw animation/range or drop intrinsic gear. |
| Pick up floor item | Discovered PickUp object target | Ordinary action route validates pickability, inventory capacity and manual_object_contact. Refresh discovery after transfer. |
| Open/close chest | OpenChestAction/CloseChestAction via item-provided action discovery | Preserve native access and chest state. No custom storage mechanics. |
| Loot chest | LootAllAction(source_item_uuid=chest UUID), native entity.loot_item transfer | Closed active chest rejects; empty chest rejects. Native loot loop may transfer only items capacity permits, so update from actual result, not assume chest emptied. |
| Use consumable/item power | Existing discovered item-sourced actions / execute_available_action | Preserve source item UUID, native charges/costs/targets and resulting event stream. No special arrows/ammunition system added by inventory UI. |

Equipment APIs are transactional native methods rather than AvailableActionInfo rows in the current Session interface. Calling them is a concrete missing adapter, not permission to implement client equipment rules. Existing source-owned item effects must survive equip/drop/loot in the current encounter; persistent save support is separately constrained above.

## 6. Implementation order and acceptance

1. Build passive creator widgets from current definition rows and resolve_character_build. Invalid/cancel flow demonstrates zero native entity/event mutation.
2. Add selected-character inputs at Session composition and gated equip/unequip wrappers. Keep drop/pickup/use on native discovery.
3. Integrate authorized sheet/resources/initiative projection described in section 8; distinguish present command admission from retained historical display.
4. Integrate inventory and pre-encounter level selection. No new XP, respec, character-save format or rest policy.
5. Record create→deploy→equip→drop→pickup/loot→use→end encounter; cancelled creation/level draft; two human members with noncurrent mutation rejected and observer histories kept separate. Follow HOW_TO_TEST.md and use native semantic outcomes/events, not snapshots of widget internals.

Anti-slop and ECS/import reviewers assess each implementation boundary. This source study is not independent implementation approval.

## 7. Whole-map save feasibility and revised scope

**Recommendation: keep full gameplay save/resume outside this UI implementation. There is no existing easy round-trip route in the inspected owners. No character-only durable-format changes are authorized.** The approved UI can compose and run a selected party, and existing recording can preserve a replay; neither is a resumable campaign save.

Concrete evidence:

- `game/replay.py:RecordedSequence`, `encode_sequence`, `decode_sequence` restore passive initialization and completed lineages under `PASSIVE_EVENT_REPLAY`. `decode_sequence` returns a `PresentationTarget` and recorded lineages, not a live Session/Encounter/Entity graph. This is suitable for watching previous play, not issuing the next combat command.
- `dnd/core/gridmap.py` has placement/spatial/light snapshot operations. `dnd/world_authoring.py` has explicit live edits (`place_world_item`, tile/connector updates) and cold projections. Neither exposes a complete world save/hydrate inverse restoring condition owners, callbacks, object contents, actors and encounter state.
- `dnd/encounter.py:Encounter` owns combatants, initiative order/index, round/turn lifecycle, controllers, private pending membership changes and event-log generation. Its Pydantic fields do not constitute a certified restore routine: runtime registries/controller bindings/callbacks and linked entities also need reconstruction.
- ConditionState and ItemEffectPresentationState omit executable condition/coating duration/handler reconstruction; adding map tiles alone does not solve those dependencies. Saving the current public observer projection would additionally omit hidden world state by design.
- Replaying all **events** cannot reconstruct executable mechanics: the recorded events are outcomes/passive observations, not a deterministic player/AI command journal with complete initial world, RNG state, identity allocation and version guarantees. `create_session` deliberately leaves seeding to callers; `game/replay.py` does not re-execute commands. A new deterministic gameplay replay loader would be another project, not a shortcut.

Bounded route available now: retain the existing passive replay export/import as an explicitly labelled recording. If the UI plan already includes replay viewing, wire that existing route; do not add a misleading Save Game/Continue button. Live in-process play can continue normally while Session remains alive. Creation drafts/build presets are a separate preference/product choice, not an authorized replacement for world persistence.

Future full-save scope needs one explicit coherent world/encounter snapshot contract and native restoration transaction; its conditions, items, clocks, controllers, RNG and identities must be designed together. Do not begin that work here. Any claim that the older paused-server durable format provides full native world resume is unsupported by this source study.

## 8. Exact sheet, resources and initiative disclosure gaps

Current UI cannot build these panels from PlayerActor alone:

| Panel | Existing source/type | Concrete minimal projection work |
|---|---|---|
| Character origin/class sheet | `EntityCreatedEvent` already carries species, variant, background, `AppliedOriginState`, tuple `AppliedClassLevel`; progression events carry updated applied rows | Reuse these existing semantic value types in an optional controlled-character sheet snapshot. Carry through the native capture → observer-authorized projection → player reduction path. Do not expose full origin/build choices for every visible enemy. |
| Ability/proficiency sheet | `EntityCreatedEvent.ability_scores`, skill_proficiencies, skill_expertise, saving_throw_proficiencies, proficiency_bonus, initiative | Reuse AbilityName/skill/save enums and tuple values. Initial creation fields are not sufficient after ability-modifying effects: provide a native evaluated sheet snapshot at relevant committed updates, rather than UI reevaluation from build rows. No such complete current PlayerActor field exists. |
| HP/AC/conditions/equipment | Existing `PlayerActor` normal_hp, maximum_hp, temporary_hp, armor_class, conditions, visual_loadout and controlled_items | Reuse directly. controlled_items is `None` for actors other than observer in `_public_actor`; `None` is undisclosed, not empty. No duplicate inventory query in widgets. |
| Turn/action/resource pools | `AvailableActionsResult` has remaining_movement and handler_details; private `_item_charge_pools` is not a public sheet snapshot. Native `ActionEconomy` has actual action/bonus/reaction/spell slots and named Resource values | Add a small immutable authorized resource snapshot, using stable native names and evaluated current/capacity values. Compute it in the application/native snapshot boundary, not inside widget paint. Keep item charges from existing ItemPresentationState. It must refresh after each committed operation and turn boundary. |
| Initiative strip | Native `Encounter.initiative_order`, CombatantState initiative totals; `_build_turn_context` already fills order/totals. `PlayerState` currently holds only current_actor_uuid and round_number | Add a projected initiative tuple at encounter membership/start/turn transitions. Reuse native ordering; do not reroll/sort in UI. The objective TurnContext includes all combatants and must not be handed blindly to observer widgets. |

`EntityStatsState` remains the existing evaluated HP/AC/affinity value type. It is not an ability/resource/class sheet and should not be stretched into a generic entity dump. The additional controlled-sheet data can be one bounded optional passive payload; it does not need a new domain system, per-widget live queries or separate registries.

Disclosure/control contract:

1. The session may authorize inspection of its human-controlled roster, but observer histories remain separate. Selecting a portrait must not silently merge that creature's visibility/memory into the current map observer.
2. Keep current strict observer policy until an explicit party inspection adapter validates membership and returns only controlled sheet facts. Do not weaken `_public_actor` to reveal every entity's inventory/class/resources.
3. Initiative strip includes only identities already disclosed to that observer, preserving their native relative order. Do not leak undisclosed combatant names, UUIDs, counts or order gaps. Reconcile newly observed/departed actors from committed projection; no objective list used by drawing code.
4. Portrait selection changes inspection/focus. Only the native active HumanController member can submit combat mutations through `_current_player`; selection does not transfer agency.
5. The same passive payload must be serializable in accepted replay/observer packets if shown historically. A separate current-native query must not overwrite historical displayed sheet values while presentation is behind the live head.

Acceptance: controlled actor with changed abilities and spent resources, two human members with distinct fog histories, hidden enemy in initiative, summon joining/departing, turn advancing, inventory not disclosed to another observer, and replay of the same projected panel data. These are concrete missing consumers/projection fields to implement in the UI lane; they are independent of full-world save support.
