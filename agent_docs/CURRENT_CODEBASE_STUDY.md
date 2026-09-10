# Current codebase: ownership and lifecycle study

Studied 2026-09-08 on **codex/recovery-design**, based on `16a6bfe141204cc46f336047da70e0cc9a4ceaa6`, including the existing uncommitted Event registry correction and presentation work. The source coverage ledger pins reviewed working-tree content; HEAD alone does not identify it.

**Status: core-owner study documented and reviewed; the appended 2026-09-09 integration records describe subsequent implementation.** This document records current behavior, design constraints and evidence. It is not a new implementation plan. Forward work belongs in [RECOVERY_PLAN.md](../RECOVERY_PLAN.md); branch history remains in [HISTORY_BEFORE_ME.md](../HISTORY_BEFORE_ME.md). The original source study itself made no production, test or asset changes.

## Framing that must survive the next implementation

- Render complete existing lineages, preserving parent/child and explicit reaction relationships. A phase version, completed child, captured interval or callback batch is not a render job.
- Event intake and reduction can advance while rendering plays a completed historical lineage at its authored speed. The newest reduced state must not overwrite the historical scene used by the active animation.
- Reuse NeuroStudio JSON, its types and timeline semantics. Python/Pygame is the runtime; the original TypeScript materializer is an offline export/reference tool.
- Existing subjectivity rules are authoritative. Preserve permitted details, including numeric facts; do not introduce a new withholding policy or replace outcomes with vague text.
- Entities compose ECS data, components and systems. Conditions, modifiers, handlers, item grants and spatial effects have specific owners and exact cleanup identities. Preserve those owners and the import DAG.
- Packaged sprite groups are rigs mapped into the shared authored system. Modular humanoid identity and equipment layers remain first-class historical presentation data.
- Current branch code establishes current behavior. Historical branches explain intent; they do not authorize restoring their machinery.

## How to use this reference

| Question | Read |
| --- | --- |
| How does an action get selected, paid for, intercepted and resolved? | [Actions](#actions-execution-discovery-and-causal-ownership), [damage/spells](#cross-entity-resolution-damage-and-spells), [Event progression](#event-progression-interception-and-complete-lineages) |
| Which state belongs to which owner? | [Entity/birth](#entity-composition-and-birth), [conditions](#conditions-duration-and-dependent-ownership), [values/economy](#values-dice-health-and-action-economy), [content/items](#character-content-grants-and-item-ownership) |
| How do turns, spatial changes and perception interact? | [Game/encounter](#game-encounter-and-controller-boundaries), [spatial owners](#spatial-ownership-movement-and-subjectivity) |
| What does the existing subjective projector actually do? | [Discovery and subjectivity](#discovery-details-and-existing-subjectivity), spatial sensory sections |
| What remains between Events and authored animation? | [Pygame/NeuroClient comparison](#presentation-neurostudio-and-independent-time), [cross-owner conclusions](#cross-owner-conclusions-and-the-next-change-guard) |
| Which statements were checked, and what remains unread? | Each chapter's evidence section and the [merged coverage ledger](#source-coverage-and-evidence-ledger) |

Use this as durable knowledge after a context reset. Check the branch and changed source, then reread affected owners and their actual callers. Update a claim when its implementation changes; do not append an incompatible theory underneath it. An indexed file, a passing test elsewhere, or a frozen outer model does not prove its entire behavior was reviewed.

## Actions: execution, discovery and causal ownership

Detailed source: `dnd/core/base_actions.py` entire file; `dnd/action_dispatch.py` entire file. These are current observations, not a replacement framework.

- `BaseAction` is a live executable/template registered through `BaseObject`; `ActionEvent` is a fact/progression model owned by `EventQueue`. Separating Event registration does not make actions or conditions passive.
- A reusable template cannot apply. `instantiate` deep-copies it into an ephemeral unregistered execution, retaining the exact registered template UUID. Semantic family, authored `configured_action_ref`, behavior implementation/provider/root provenance, machine command token and display name are different identities. Do not choose authored animation by display name.
- `Cost` contains runtime affordability callbacks; `BaseCost` is the intended callback-free serialized cost shape. Target-independent discovery costs and selected-target dynamic costs are distinct. Restricted action grants substitute specific eligible costs with exact named-resource costs; they are not general extra turns/actions.
- Discovery legality and affordability are separate; `AvailableActionInfo` validates a closed availability reason and retains an exact private execution template. Dispatcher requires the exact target object from that row, not an equal reconstructed target, and reuses it without rediscovery. This is a live command capability, not passive replay data.
- Apply enters behavior-provider context and the existing passive Event callback batch. It checks costs; constructs a detached declaration; explicitly registers the declaration and honors its accepted cancellation; deep-copies the accepted declaration for detached validation; validates concrete type and lineage; commits costs and item charges while execution is detached; then registers execution and honors dispatch cancellation.
- Cost commitment precedes published EXECUTION. Item charges are authorized once by root action lineage and emit their own child event. Cancellation after these commits does not imply universal refund/rollback.
- Single-target `_apply` owns mechanics and must finish at EFFECT or cancel. BaseAction cleans concentration before root COMPLETION. It does not own the domain-specific effect commit or automatically undo it.
- MULTI_ENTITY/POSITION_AOE use existing convolution: root EFFECT, then ordered per-target execution child lineages, each with `application_index` and deterministic UUID5 `application_id` from root lineage + index. Duplicate target selections remain distinct applications. Root action object temporarily targets each recipient, restored in `finally`. Successful child effects complete; canceled children are skipped; totals aggregate; AoE finalization runs before root completion. Single-target action need not have an application ID.
- Descendant mechanics, reactions, spatial/sensory children and finalization belong to the causal history. A delivered batch, any child COMPLETION, or public action return is not a new independent presentation unit. Preserve complete lineage rendering.
- `StructuredAction` exists, but default revalidation has a source inconsistency: `_apply` passes EFFECT/EXECUTION to `_validate`, which accepts DECLARATION only (2054–2099). This was source-read, not behavior-probed here. Do not promote it into the universal architecture or fix it during documentation.
- Discovery outcome/self-setup/target-effect/world-effect profiles are engine declarations for planning/query use, not actual resolved outcomes or an animation language. Attack baselines explicitly exclude target-private context. Position contracts disclose candidate navigation while authoritative execution repeats hidden-obstruction checks.

## Entity: composition and birth

The complete `dnd/entity.py` was read across the action, condition and spatial studies. The merged coverage ledger records the individual ranges and reviewed file hash.

- Entity is the aggregate composer over specialized blocks: abilities, skills, saves, health, equipment, creature proficiencies, economy, senses, inventory, appearance, spellcasting and modifiable values. Entity owns the sole objective coordinate. Components resolve ownership by UUID; do not create a parallel presentation mechanics aggregate.
- Registration is not composition commitment or deployment. `model_post_init` registers Entity identity and suppresses world-presence light; it does not add Tile membership. `compose_entity` validates the finished absent aggregate and publishes one non-vetoable `EntityCreatedEvent`; `Game` owns later deployment.
- Character direct body identity and authored creature content identity are exclusive. Source-owned feature/origin/size contributions and exact character grant receipts are retained for independent retirement. Multiple providers are not a boolean to unset wholesale.
- Birth captures concrete values, life/HP, appearance, inventory/equipment item snapshots, action/handler/condition identities, resources, proficiencies, class/origin and spell-source selections from the finished composition. It is not merely a name/position notification. Initial items are installed before birth; they must not be replayed as later acquisitions.
- `discard_uncommitted` is a specific unpublished-composition cleanup path: conditions/indexes, handlers/actions, light, observers, Entity/BaseObject/BaseValue/BaseBlock registries. It is not a generic transaction rollback for gameplay.
- Position mutation stages Entity coordinate + GridMap membership, restores on commit failure, then publishes membership facts. Publication failure is distinguished from failed commit; do not assume position rolled back after observers already received facts. Suspend/restore preserve Entity identity while changing world presence.

## Cross-entity resolution, damage and spells

- Entity target context propagates into child values. Weapon Attack explicitly scopes both actors with `_temporary_target`, composes attack bonus and target AC, installs reciprocal `set_from_target`, attaches lineage/context for dynamic contributors, and later resets them. A ModifiableValue stored on an Event remains an executable/contextual engine object; serializing its current score is a separate boundary decision, not evidence the full nested model is passive.
- Attack snapshots weapon identity/damage types/item presentation at declaration, including misses. It validates range and visual contact, posts attack-roll results for handlers, proposes damage EFFECT, rolls a child DamageRollResultEvent, then calls target.receive_damage. Authored rule flags (`is_first`/`is_last`) distinguish repeated phases; they are not universal stream completeness flags.
- `roll_d20` emits the exact ATTACK/SAVE/CHECK result subclass and completes it after handlers. `roll_d20_event` intentionally leaves the result at EFFECT so the caller can add children before completion. Do not replace both APIs with immediate finalization.
- Saving throws have a causal request owner and a recipient roll owner. The request carries typed saving-throw context (cause/effect/magical/tags), rolls under a child event, then accepts final roll/result modifications. D20 result interception and parent saving-throw interception are distinct.
- `receive_damage` proposes TakeDamage through EFFECT before health mutation; computes a typed mitigation/temp-HP/cap preview from the accepted event; commits Health; emits positive DamageApplied as child; resolves dying/death and reactions; then closes TakeDamage with final facts. `receive_damage` returns normal HP damage, while DamageApplied.applied_damage and TakeDamage.final_damage include temporary HP consumed. A consumer must not treat every field named damage as interchangeable.
- Positive DamageApplied captures HP immediately after damage, before later life transitions; its subscribers can cause more children. `get_hp` includes temp HP, `get_normal_hp` does not. `has_hp`, life_state, is_active and is_encounter_alive answer different rules questions. Death, dying, stable and healing cannot be reduced to hp <= 0.
- Death-save resolution is another concrete producer: [make_death_save](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entity.py:2100) leaves its child roll at EFFECT while natural-face logic causes healing, stabilization or death; it then completes the roll and publishes DeathSave EFFECT/COMPLETION with counters and flags. [revive](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entity.py:2190) accepts only DEAD, honors its execution cancellation, then sets HP, resets counters and publishes the child life transition before Revive EFFECT/COMPLETION. These sequences were source-read, not newly executed in this pass; their named outcome flags are not universal lineage-completion evidence.
- `receive_healing` proposes EFFECT, respects dead/healing-blocked state, commits actual healing, clears dying via child life transitions, and carries resulting normal/temp/total HP. No animation should reread the current Entity to reconstruct those historical facts.
- SpellAction lives in actions.py (spells/base.py only re-exports). It supplies metadata, costs/slot variants, cast-local ContextVar, save/attack helpers and concentration ownership; authored spell classes still own their effects. A cast scope binds to the actual declaration lineage. Low-level damage-affinity claims are once per cast lineage and released in `finally` after BaseAction's batch returns.
- SpellAttackResolution is a helper result; Fire Bolt keeps the attack result on its SpellEvent and does not manufacture an AttackEvent child. Do not impose a weapon-specific event shape on every cast.
- Saved spell recipes and Event spell/provenance identities are different surfaces that must be mapped explicitly. Existing declaration `spell_id` derives from normalize_spell_id(name); this is present code, not authorization for new name-based animation dispatch.
- One concentrating condition is created/reused across convolution; its linked effects own persistent mechanics. BaseAction calls spell cleanup before root terminal to remove empty concentration. Child concentration removals and persistent zone setup remain in causal history.

## Game, encounter and controller boundaries

Full reads: `dnd/game.py`, `dnd/encounter.py`, `dnd/controller.py`, `dnd/actions_functional.py`.

- Game owns deployed entities only. It respects commit-vs-publication exceptions when retaining/removing ownership. It does not create isolated process registries, run turns, or supply presentation time.
- Encounter owns combatants, initiative, rounds, turns, controller assignment, log capture and fallback death checks. Entity owns actual turn hooks/economy/condition progression. Controllers select/execute decisions through existing actions; they do not own world state.
- Encounter opens one turn execution UUID in EventQueue before Entity.on_turn_start; action/condition/roll events inherit this active turn context. End-turn closes it in finally. It is broader than an action lineage and must not replace the rendering unit.
- Turn-start navigation is materialized from the already reduced sensory projection. Encounter clears prior collision memory at turn start. World-owned spatial, Tile and item condition durations advance at round boundary; they must not also be advanced by a new frame timer.
- External and deferred controllers expose existing wait/decision boundaries. `advance_one_controller_action_boundary` nests passive batches around one decision; `complete_current_turn` ends and advances the initiative slot without automatically executing the next turn. These are useful same-thread scheduling seams, not new authored animation timing rules.
- Encounter.execute_action uses the functional index path and performs check_deaths after it returns. That method only checks Entity existence itself: callers cannot assume it alone authenticates active-turn/controller ownership. Deferred controller completion explicitly checks current entity/controller/execution-mode fences.
- Encounter.start installs the existing perceiver/identified/revealed/log callbacks. Candidate recipients come from GridMap affected positions/subscribers and participants; actual identity requires the observer's contact facts. These callbacks supply existing subjectivity, not a new policy invitation.
- Logs are captured from root completion, including nested logs, plus the standalone carrier path. Generation-qualified log range projection preserves every source index, including hidden slots. Event source cursor, log index, turn UUID, lineage UUID and rendering time have different roles.
- Existing controller models/TurnContext use BaseObject and live Entity access. They are engine mechanisms, not detached subjective replay DTOs. Retaining these facts does not endorse the old server/controller architecture as the Pygame target.

## Discovery details and existing subjectivity

- Full Entity discovery reread includes AoE footprint vs preview caches, visible/seen path eligibility, hazard/safe-route exposure, source-cost versus selected-target-cost checks, registered variants, exact bindings, finite item use pools and adjacent environment use actions. Cache invalidation is already separated by propagation revision, movement/path revision and observer contact facts. This is derived live discovery state; it is not a durable historical scene.
- Geometry can be cached before observation only when it contains no target facts. AoE preview intersects the footprint with the observer's current visible cells before resolving contacts. Actual AoE application recomputes objective targets. A presentation adapter must not substitute preview targets for actual child application identities.
- The plain-position contract, path-target family, LOS/AoE family and item-use routes are not currently perfectly uniform: object actions only emit available rows; selected item execution regenerates its use action from the item; generic action execution prefers its retained exact template. Record the exact path a future UI uses instead of claiming every row behaves identically.
- `dnd/subjective_combat_log.py` was read completely. It is a pure same-CombatLogEntry projection using recorded event-time grants and explicit controlled/observer scopes, never current Entity/GridMap lookups. It recursively projects children, keeps an otherwise unobserved parent when a child is permitted, sanitizes undisclosed identity/location facts, rebuilds movement and multi-target aggregates from permitted children, and clears internal grant maps from output.
- It preserves known numeric facts; it does not contain a new blanket NPC-HP withholding rule. Identity and exact location grants are separate. Controlled movement, observed path segments, jumps and connector transfers have explicit existing projection rules, including trajectory/commit/support-elevation evidence. These are established policy, not open design questions in this task.
- This pure combat-log projector is not an ordinary Event projector or an authored animation reducer. Logs remain text/history consumers; rebuilding animations from their prose would bypass concrete Event and lineage facts.

## Reset and interpreting test evidence

- `reset_engine_runtime` resets Event systems before owner registries, explicitly clears the combat-log callback (which EventQueue.reset alone retains), resets spell protections/behavior context, clears Entity/Block/Value/Object/controller/encounter state and legacy creature runtime bindings, then resets the GridMap singleton. The import of retained creature bindings is current transitional coupling, not grounds to recreate the old content runtime.
- The helper `tests.engine.support.create_test_entity` calls Entity.create, compose_entity and Game.deploy_entity. A test using this helper proves the combined path, even if its test name says only "create". Do not infer that raw Entity construction publishes birth or Tile membership.
- Existing tests read (not rerun by root in this documentation pass): `test_combat_actions.py:218–327` distinguishes cost commitment, canceled execution and children-before-root; `test_cold_presentation_facts.py:182–303` covers frozen area/item facts and repeated application IDs. The geometry test manually advances a detached declaration; it does not prove live Fireball admission/replay. The repeated Magic Missile target test does run the real public spell action.
- Prior selected public Fire Bolt/Counterspell/exception traces remain recorded in [RECOVERY_PLAN appendix B](/mnt/c/users/tommaso/documents/dev/dnd_engine/RECOVERY_PLAN.md#appendix-b-prior-public-cast-traces-and-unresolved-evidence) with their exact outcomes. They were performed before this extended reread, not newly repeated or a whole-suite acceptance claim.

## Movement discovery and Jump: additional owner distinctions

The spatial chapter follows committed Move steps. Its declaration setup was also read: [Move path/cost/discovery](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/actions.py:415) derives paths from the actor's existing subjective navigation, prefers safe walking paths, and queries mode-specific subjective paths for swimming/flying. Walking validation accepts a cached path or checks membership in known reachable positions; non-walking validation checks start/end and each subjective transition. The actual Move loop still checks objective transitions and accepted step effects. Declaration eligibility is not a guarantee that the entire route will commit.

[Jump](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/actions.py:2913) already has its own trajectory and actual/requested landing facts, including support elevations. Its standard discovery contract declares subjective walkability, occupancy and remaining movement prerequisites; its concrete validation requires visible landing, range, actual walkability and a clear propagation ray. The range is the current simplified authored jump rule, and its distance helper is XY-based. The straight-line disclosed cell path is shared with execution. These current mechanics are not an invitation for the renderer to substitute a textbook jump rule or a 3D collision simulation.

Jump commits through StepMovementEvent children with DIRECT_ARC and ORDINARY_EXIT, so step interception and reactions still apply while intermediate walkability is deliberately skipped. A step veto or lost action capability can stop the jump. Position/membership changes occur before the step's `committed=True` completion. Movement is consumed **after** that completion and after another capability check; this differs from Move's ordering. If entry consequences remove capability, the current code exits before consuming that leg's movement. This is a source observation, not a newly executed failure. Bonus-action cost is committed by the action owner before the loop; root finalization reports actual end/path/distance and navigation refresh runs in `finally`.

The current source therefore does not support a universal assumption that Step COMPLETION already includes every cost mutation, or that one producer's ordering proves all movement producers. Preserve the complete movement lineage and its authored trajectory rather than rendering independently from each positional callback. Full Jump source was read here; its behavior was not separately rerun in this pass.

## Event progression, interception and complete lineages

Date: 2026-09-08. Working tree based on `16a6bfe141204cc46f336047da70e0cc9a4ceaa6` (`codex/recovery-design`), including the current uncommitted Event registry separation. This is a source study, not an implementation plan or permission to repair the limitations below. The complete 5,516-line `dnd/core/events.py` was read in this pass. Exact supplementary ranges and unstudied owners are in [the merged coverage ledger](#source-coverage-and-evidence-ledger).

The required rendering unit is the **complete existing lineage and its causal relationships**. Phase versions provide facts for reduction and assembly. A queue callback, completion sequence, capture interval, or action batch is not itself a render job. Nothing in these notes proposes a replacement completion protocol, event hierarchy, or subjectivity policy.

### 1. What an Event represents, and what it does not promise

[Event fields and lifecycle](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:284) distinguish a version UUID from a logical `lineage_uuid`. Source/target identity, phase, timestamp, cancellation facts, turn execution identity, parent references, and child bookkeeping live on that same Event model. Concrete subclasses add mechanical payload. Events now inherit BaseModel directly; EventQueue alone stores Event history. Handlers, Damage specifications, and other live owners still inherit BaseObject where declared. Removing Event's extra BaseObject registration did not make its payload or construction passive.

`Event.model_post_init` first inherits `turn_execution_id` from the exact referenced parent if found, otherwise from the active encounter-turn identity; it then calls EventQueue.register when `use_register=True` ([482–495](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:482)). The constructor does **not** return a replacement produced by that call. An ordinary constructor can therefore return its original submitted object while a later accepted replacement exists in the queue. Current BaseAction avoids this by constructing unregistered and explicitly accepting the return from `register`.

`use_register` controls automatic construction/post publication. It is not proof that an object is absent from the queue: explicit `register(event)` stores even an object whose flag remains false, and sensory completion sequences deliberately store such values. Conversely, `use_register=False` does not suppress parent/turn lookups, subclass initialization, pre-completion work, or log generation when those other operations are explicitly called.

The model is mutable; Pydantic assignment validation/frozen mode is not enabled on Event. Copies made by `post`/`with_updates` use `model_copy`, not normal schema validation. Shared nested values, handler-side in-place mutations, and later child registration matter. There is no EventQueue snapshot/restore service in this file. Some queries return the actual index list; every query returns the original Event objects, not detached historical copies. A returned Python object must not be mistaken for an immutable archive. Append/source order and timestamp order also differ: `iter_events_since` retains append order, while `get_event_history` sorts timestamps. A copied/reposted child or explicitly supplied timestamp must not silently change causal source order.

`is_first` and `is_last` are stored fields with defaults true. EventQueue does not rewrite prior versions' flags when a same-phase version appears. `phase_to` sets both true unless explicitly overridden. A separate helper, `is_first_at_phase`, scans the lineage for a different UUID at the same phase with a strictly earlier timestamp ([2878–2894](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:2878)); it does not derive this from append indices or the stored flags. Concrete rules use both mechanisms; their meanings must be traced at the producer/consumer, not unified into an invented terminal test.

### 2. Version-producing operations and their different effects

| Public operation | Actual current behavior |
| --- | --- |
| `post(**updates)` | Forces `modified=True`, a fresh timestamp and UUID. Preserves lineage unless caller explicitly supplies another. Makes a shallow model copy, then registers and redispatches if the copied flag is true. Checks returned value is an instance of the original concrete class **after** dispatch. |
| `with_updates(**updates)` | Makes a shallow unposted modified value. UUID, timestamp, lineage, and registration flag remain unless the caller changes them. It is the normal functional way for a handler to feed an accepted replacement into its current chain. |
| `phase_to(explicit_phase)` | Makes a new version through `post`, with phase-specific child/log bookkeeping. It is not a general strict finite-state validator: explicit phase values need not be the next ordered phase. If self is already COMPLETION it returns self immediately, ignoring requested changes. |
| `phase_to()` | Selects the next entry in declaration → execution → effect → completion. CANCEL is not in that ordered list. |
| `cancel(...)` | Sets canceled true, phase CANCEL, and the first `canceled_from_phase`, then calls `post`. It does not run the completion-specific metadata/log path or provide rollback. Caller-supplied updates are merged last. |

Source: [phase_to 505–624](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:505), [cancel 626–644](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:626), [post/with_updates 737–783](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:737).

An explicit `post` inside a live handler is reentrant: the new version discovers and invokes handlers again before the outer handler returns. The outer chain then resumes with its existing candidate list. A once-guarded repost probe produced calls `first(initial), first(reposted), later(reposted), later(reposted)`. This is different from `with_updates`, which records the replacement and moves to the next handler without redispatching the same phase.

The current queue permits same-phase histories. The functional replacement probe produced declaration, execution submitted, execution replacement one, execution replacement two: four distinct UUIDs in one lineage, with the later handler seeing replacement one's value. All four stored first/last flags remained true. Collapsing this history before understanding which value each interceptor accepted would discard real rule inputs.

### 3. Trigger matching, ordering, ownership, and handler results

A [Trigger](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:1170) matches exact EventType and exact EventPhase, optionally exact source and target UUID. Its name does not participate in equality/hash. Python inheritance does not broaden event categories: a D20 trigger does not automatically see AttackD20RollResultEvent's different category. Existing dice tests explicitly prove this.

[BaseHandler/EventHandler/SpatialHandler](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:1228) own a processor callable, owning source UUID, enabled/toggle flags, optional binding, and cleanup owner. EventHandler rechecks any matching trigger when invoked; an empty trigger list works for direct calls but is absent from ordinary queue discovery. SpatialHandler relies on the position/type/phase index and only checks enabled on invocation.

There is **no numeric priority field, handler template pipeline, or generic once/consume mechanism in current events.py**. Actual queue precedence is:

1. For events with nonempty `spatial_dispatch_positions`, each supplied cell contributes its position-indexed handlers, then simple exact triggers, then matching remaining global handlers. UUID de-duplication prevents a handler covering multiple affected cells from firing once per cell.
2. Otherwise, simple exact type/phase handlers run first, followed by matching filtered handlers in registration order.
3. `set_event_handler_order` reorders global membership and associated lists; it does not eliminate the simple-before-filtered partition or put global handlers ahead of positional handlers.

Sources: [discovery 2381–2470](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:2381), [order APIs 2492–2516](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:2492). [Dice test 654–786](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_dice_event_semantics.py:654) registers filtered handlers first but verifies actual execution `simple → source-filtered → target-filtered`, changing the effective roll 5 → 12 → 15 → 18.

Live `register` computes the candidate list once from the submitted event. Later replacements are passed along that list. EventHandler's own trigger call can decline a previously selected candidate if replacement fields changed, but newly matching handlers are not discovered unless an explicit repost happens. Removing a handler from indexes during dispatch does not itself remove its already selected object from the list; toggling `enabled` affects the object's subsequent invocation. Rule-specific frequency protection and resource spending are elsewhere.

The handler's second argument defaults to **the handler owner**, not the incoming event actor. Opportunity Attack uses it to find the reactor, then acts against the mover. Confusing these two identities would reverse rule ownership.

Live result handling ([1979–2023](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:1979), [2244–2257](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:2244)):

- `None`: continue. Side effects and already emitted children remain; None is not proof of no mechanical change.
- The same object: in-place changes already affect the stored reference. If it is not canceled, processing continues. No new UUID is required merely because the object was mutated.
- A modified replacement: `_record_handler_result` stores it without invoking handlers again. If it has the UUID of a different stored object, the recorder creates a new UUID/timestamp. If the exact returned object is already stored, it is reused.
- A canceled result: ends the current live handler chain after recording it. An explicit `cancel()` may have already dispatched CANCEL handlers through its nested `post`.
- A distinct noncanceled result with `modified=False` is not adopted by the live queue. The result contract is therefore more specific than “return any Event and the queue accepts it.”

CANCEL is not excluded from ordinary queue handler lookup. However, its event already has canceled=true; the first CANCEL handler returning a non-None canceled event ends that chain. There is no promise that every matching CANCEL handler runs. COMPLETION is explicitly excluded from mechanical handler invocation.

BaseBlock owns block-local handler dictionaries and adds/removes the same instances from EventQueue ([692–757](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_block.py:692)). Handler.remove can clean its owner dictionaries via the declared neutral structural protocol; direct queue removal only owns queue indexes. Spatial registration supports both native SpatialHandler and retained EventHandler objects. Positions and event keys have reverse indexes for movement/removal; this study does not equate an affected-position set with the exact dispatch cells.

### 4. Interception before mutation versus publication after mutation

These operations are distinct existing contracts; their names cannot be collapsed into one phase rule.

#### Live register and explicit declaration

`register` rejects a different object reusing a stored UUID, returns the exact already-stored object unchanged, otherwise stores first and then invokes matched handlers. It does not automatically roll back owner state. `publish_declaration` requires an unregistered DECLARATION, explicitly accepts register's result, and returns a copy with future auto-publication enabled ([2044–2064](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:2044)). BaseAction currently uses an equivalent explicit register/return pattern instead of this helper.

#### Preflight

`preflight` accepts only unregistered DECLARATION/EXECUTION inputs and only handlers marked `validation_only` ([2067–2127](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:2067)). It invokes them directly, not through `_invoke_handler`; there are no normal handler-dispatch evidence callbacks or a newly supplied handler behavior-provider context in this path. Returned values must preserve the input class family and remain unregistered. A canceled value stops validation; accepted values chain without requiring modified=true.

During each validator, a ContextVar guard prevents `_store_event` and standalone log publication. The owner also checks the event cursor did not change. It does **not** snapshot every component or detect arbitrary mutation of another registry; nonmutation is a real validator contract, not a universal transactional sandbox. `publish_preflighted` trusts that the caller used the contract, changes flag/timestamp on that accepted object, stores once, and does not run validators twice. It has no new preflight token or generic approval object.

Concrete equipment proof owners: [rejected conflicting equip 150–232](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_equipment_domain_ownership.py:150) and [impure/emitting validator rejection 315–384](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_equipment_domain_ownership.py:315). Read as existing tests, not rerun-pass claims in this study.

#### Already committed phases

`publish_committed_phase` requires an unregistered, noncanceled EXECUTION/EFFECT ([2152–2184](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:2152)). It stores the committed value, then gives each matching enabled handler its own deep unregistered copy. Handlers may emit ordinary reactions; their returned replacement/cancellation cannot rewrite the committed record and does not suppress later handlers. The probe confirms a canceling/mutating first handler leaves the record unchanged and the next handler receives the original committed value. This API does not undo independent side effects the processor performs.

`publish_completed_fact` accepts an unregistered COMPLETION, runs pre-completion callbacks, marks and stores its copied terminal fact ([2187–2201](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:2187)). It bypasses `phase_to`'s child-lineage/log-generation block. Thus it is an explicit direct-fact path whose caller supplies the finished payload; it is not evidence that every Event must first have DECLARATION, EXECUTION, and EFFECT versions.

`register_completion_sequence` stores each supplied completion, calls per-event observers for each, and only after all are indexed invokes sequence observers once ([2204–2241](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:2204)). It checks items during iteration rather than prevalidating the full sequence. A later invalid phase/duplicate can leave a valid prefix stored and already observed. “Atomic sequence” in its observer documentation means grouped sequence notification on its successful path, not all-or-nothing rollback. It does not perform ordinary handler dispatch, general pre-completion callbacks, or `phase_to` log construction.

#### Condition EFFECT cancellation

The one explicit deferred-cancellation key is CONDITION_APPLICATION/EFFECT ([1423–1427](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:1423)). Register gives those handlers an unregistered copy. If canceled, it returns the cancellation without queue publication so the condition owner can restore its state first. `publish_handler_cancellation` then publishes the owner-approved cancellation through the ordinary CANCEL path. This is a narrow existing owner seam; do not generalize it into a transaction service. Detailed condition installation/rollback belongs to the condition study.

### 5. Callback ordering and what each observer can actually see

For ordinary live registration the order is ([2265–2378](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:2265)):

1. Reject publication during preflight and UUID collision.
2. Copy/capture observer identity and current location grants; merge parent identity evidence.
3. Insert exact version in lineage, UUID, timestamp and other indexes; propagate child UUID bookkeeping to parent versions; append source order and pending batch.
4. Run matching per-event callbacks.
5. Run sequence callbacks for this one event.
6. If no active batch, run the one-event batch callback.
7. Return from storage, discover handlers, and perform mechanical interception through `register`.

The unbatched diagnostic confirms event → sequence → batch → handler for EXECUTION. A passive callback at a nonterminal phase sees the submitted version before later handler processing. Callback API documentation calls it passive, but passes the original mutable Event; the rule “must not mutate” is a contract, not an immutable wrapper enforcement.

Per-event filters select exact type and phase. Sequence filters choose whether to invoke the callback if any event matches the requested type and any event matches the requested phase; they then pass the **whole** sequence rather than a filtered subset. The checks are independent, not a same-element predicate.

Per-event, sequence, batch, and handler-dispatch observer exceptions are logged and swallowed per callback. Later passive observers still run. Mechanical handler exceptions propagate. Pre-completion callback exceptions also propagate, while their recursion guard is cleared in `finally`. Combat-log construction/callback exceptions inside `phase_to` are separately caught/logged; completion publication can still proceed without a successfully generated/delivered log.

Batching delays only batch observers. Nested scopes share a pending list and only the outermost scope flushes, in `finally`, even on exception. The resulting sequence contains all stored phases and children, not just terminal events. It is append-order accounting, not a proof that every lineage in it has reached a terminal. It cannot replace actual lineage interpretation.

Standalone `push_combat_log` publishes an unregistered informational carrier directly to Encounter's log callback ([1552–1571](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:1552)). That carrier is not a queued CONDITION_APPLICATION transition. Existing Encounter log ranges/listeners remain the text route; they have independent indices. Current `reset` clears Event indexes, observers, and registered pre-completion systems, but does not clear `_combat_log_callback`; existing tests explicitly clear it separately. The probe confirms that callback still receives a standalone log after reset.

### 6. Completion bookkeeping, parent/child resolution, and complete lineages

`phase_to(COMPLETION)` does the following before publishing its new UUID ([538–624](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:538)):

- Runs pre-completion callbacks against the current version. These are allowed to emit causal children. Sensory events skip this invocation to prevent recursive recomputation; a version UUID recursion guard also applies.
- Captures current completion location grants and asks the concrete family for any endpoint coordinate evidence.
- Deduplicates current and earlier child UUIDs in first-seen order; resolves an exact stored parent to `parent_lineage`; resolves unique child lineages from those UUIDs.
- Builds a temporary completion-shaped copy, generates its log, recursively collects already available child logs, and merges the existing perceiver/identity/reveal evidence.
- Calls the top-level log callback, if eligible, **before** new completion storage; the temporary event still has the earlier version's UUID.
- Calls `post`, which produces and stores the actual completion UUID. Mechanical completion handlers do not run.

The queue's child registration mutates the referenced parent version and propagates the child UUID to other stored versions of that parent's lineage ([2320–2326](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:2320)). It does not require the parent to be nonterminal, require the child to be terminal, or reject a missing parent. Each child phase/version may be listed by UUID; `children_lineages` is the deduplicated logical relationship resolved at completion, not the same collection.

`get_parent_event` prefers the latest stored version of parent_lineage; only without one does it return the exact `parent_event` UUID. `get_children_events` prefers the latest stored version of each `children_lineages` member, otherwise exact child UUID lookup ([646–684](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:646)). These are live navigation helpers. They do not mean “give me the exact historical parent/child state at this version's boundary.” Exact source references and logical linkage must both survive capture.

The queue does not recursively wait for every child before allowing a parent COMPLETION. It also does not refuse a new child after parent completion. Existing public test [538–580](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_event_lifecycle.py:538) and this pass's probe both show a late child's UUID entering the completed parent's mutable UUID lists while its already computed `children_lineages` remains unchanged. With an earlier child lineage present, `get_children_events` therefore continues returning only that earlier lineage. This is observed compatibility behavior, not a license to invent a new render unit or silently discard the late relationship.

A complete lineage must retain the versions which established and intercepted the action, its actual terminal outcome, and related child/reaction facts. The source contains multiple legitimate shapes: successful action terminal COMPLETION; canceled action terminal CANCEL; direct completed facts; per-target children starting from copied EXECUTION; reaction lineages linked by explicit trigger fields. Some owners explicitly finish mandatory children before their root terminal. [Real Attack's existing test 291–327](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_combat_actions.py:291) protects that ordering for damage-result and TakeDamage children. That owner contract does not magically become a universal queue-level enforcement.

These findings expose the exact source relationships and their limits. Selecting admissible complete families and deciding how to treat late or interrupted lineages remains an integration question to answer from owners; neither “each phase is a job” nor “batch return is new completion” follows from this code.

### 7. How actions, rolls, damage, and reactions use interception

The current [BaseAction pipeline](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_actions.py:1762) explicitly accepts register's returned declaration, deep-copies it for detached owner validation, validates same concrete type and lineage, commits action costs and item charges before publishing EXECUTION, accepts execution interception, and only then runs authored effects. Cancellation at EXECUTION can therefore preserve an already spent action. The existing [Dash tests 218–288](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_combat_actions.py:218) distinguish that outcome from rejected declaration and prove effects are absent while cost remains spent.

Multi-target convolution emits the root EFFECT, then creates one separate child lineage for each ordered application. Each child gets an `application_index` and deterministic UUID5 from root lineage plus that index, so A/B/A remains three applications ([1925–1974](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_actions.py:1925)). The child starts from an EXECUTION copy and does not re-run the whole cost pipeline. Accepted noncanceled effects complete before root cleanup and root completion. A single-target action does not need or receive that convolution identity.

[D20 and damage-result events](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:4613) are post-roll, pre-application interception points. They preserve original versus effective rolls and ordered typed `RollModification` audit facts. `replace_roll` and `append_damage_roll` make new values with `with_updates`, so later handlers consume earlier effective replacements without restarting all handlers. Damage packets pair one definition with original/effective roll; appending a packet is not equivalent to editing an aggregate total. The original DiceRoll object is a mutable registered BaseModel despite several field descriptions saying “immutable”; replacement methods preserve it by convention. Damage definitions can retain live ModifiableValue graphs. This matters for passive capture but does not authorize stripping them from synchronous mechanics.

TakeDamage is the interruptible incoming application packet; DamageApplied is the factual positive amount after defenses/temporary HP allocation; LifeStateChange and Death remain separate consequences ([5018–5182](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:5018), [5381–5516](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:5381)). No visual death inference from HP is introduced here. Detailed damage mutation/concentration ownership is in the root/condition studies, not reconstructed by this queue review.

Opportunity Attack is a real nested Attack with a reaction Cost and parent_event pointing to the triggering StepMovementEvent ([reactions.py 17–68](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/reactions.py:17)). Resource affordability and consumption limit repeated opportunities, not a queue-level universal consumption flag. ForcedMovement has a distinct category and its own spatial consequences. Exact trajectory/provocation/committed/elevation facts on StepMovement are not reducible to “move to final cell.”

Counterspell has a different causal shape. Its [reaction Event](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/abjuration.py:89) carries `triggered_event_uuid` and `triggered_lineage_uuid`. The concrete emitter ([862–902](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/abjuration.py:862)) creates declaration → effect → completion without parent_event; the processor then returns a cancellation of the incoming cast on success. It spends actual reaction/slot resources in the rule owner. Failed Counterspell can emit a completed reaction and return None. Parent links alone or None-result classification alone would miss meaningful reaction behavior.

### 8. Dispatch evidence is existing evidence, not a complete independent fact stream

`_invoke_handler` supplies the handler behavior binding through the existing provider context, then counts event versions appended during the call and compares the returned object with the input ([1625–1697](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:1625)). It emits immutable `HandlerDispatchEvidence` after the handler returns. Nested invocations therefore finish and receive their indices before the enclosing invocation. Counts include the whole nested interval, not only direct children.

Outcome precedence is changed canceled result, changed modified result, emitted versions, then no_effect. An in-place mutation returning the same object can be classified no_effect because comparison happens after mutation against that same object. The current public probe reproduces it. A handler exception produces no successful dispatch record from this function. The current functional roll transform test proves the supported replacement path is classified modified; it does not prove detection of arbitrary side effects.

For an effected REACTION with a binding and non-None result, the function appends internal `EffectiveHandlerPresentation` to that returned Event. It records triggering version/lineage and deduplicated emitted lineages. It is private state, excluded from normal Event serialization. A reaction returning None after emitting children does not attach that result-carried evidence, though dispatch evidence and child Events can still exist. A presentation consumer must not assume this tuple is a complete alternate reaction journal.

The evidence contracts themselves remain current core data ([runtime.py 405–520](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/content/runtime.py:405)); their docstring still describes a legacy projected DTO consumer. That historical consumer is not imported or revived by this study.

### 9. Verified limitations and unverified concerns, separated from implementation

Executed finite public Event/handler diagnostics; the operations and observed results are retained here:

| Case | Observed result |
| --- | --- |
| Two functional same-phase replacements | Each accepted replacement retained under a fresh UUID; later handler sees earlier value; all first/last flags remain true. |
| Once-guarded explicit repost | Redispatch is recursive; later handler executes in both inner and outer chains. |
| Constructor replacement | Constructor returns submitted value; latest queue version is accepted replacement. |
| Same-object mutation | Returned state changes; dispatch outcome reports no_effect. |
| Preflight then publication | No queue rows during validation; validator runs once; publication keeps proposal UUID. |
| Committed-phase cancellation attempt | Committed value remains unchanged; later handler still sees it; no cancellation row from the unregistered copy. |
| Completion sequence invalid tail | Valid prefix remains stored and per-event-observed; sequence callback does not fire. |
| Late child after completed parent | Child UUID appended, but completed parent's logical child list remains stale. |
| Unbatched callback ordering | Event callback, sequence callback, batch callback all precede mechanical handler dispatch. |
| Reset and standalone log | Reset leaves combat-log callback installed; standalone log is still delivered outside Event history. |

These diagnostics use real Event/queue/handler APIs, no replacement dispatcher or mocks. They run in a fresh process, retain no live game, and change only ignored study artifacts. The Event reviewer edited no tests and ran diagnostics only; the other chapters report their separate pytest selections.

Separate source-only concern: StructuredAction's default `revalidate_prerequisites=True` path accepts an effect/execution consequence and calls its own declaration-only `_validate` ([2054–2099](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_actions.py:2054)). This is a source inconsistency requiring an actual authored caller trace before assessing impact. It was reported to the action-study owner and was not fixed or probed here.

No universal complete-lineage admission implementation has been claimed. No new subjectivity rule, nullable-source schema, Event snapshot framework, priority engine, or generic rollback layer was introduced. Remaining owner-level gaps and read coverage are explicit in the merged coverage/evidence ledger.

## Conditions, duration and dependent ownership

Read-only source and in-memory behavior study, 2026-09-08. Repository: `/mnt/c/users/tommaso/documents/dev/dnd_engine`, branch `codex/recovery-design`, HEAD `16a6bfe141204cc46f336047da70e0cc9a4ceaa6`. These findings describe the **current working tree**, which includes changes after that commit. Exact read ranges and file hashes are in [the merged coverage ledger](#source-coverage-and-evidence-ledger). The condition reviewer changed no production code, tests or content.

The complete implementations of BaseCondition, Duration, BaseBlock, standard conditions, BaseObject and creature transforms were read. Selected Entity, spell, class, grant and spatial-owner paths were followed in detail. This is not an audit of every condition authored in every spell, monster, item, feat or extension. Search hits are not counted as full reads. The distinctions below separate source observations, executed evidence and unexecuted concerns.

### 1. The actual owners and identities

A live condition is a registered rules object, not a passive presentation record. BaseCondition inherits BaseObject; ordinary construction registers its UUID. Duration also inherits BaseObject, and ConcentrationSlot does likewise. The condition owns its Duration by exact UUID, while a BaseBlock normally owns the active condition through three indexes: name, condition UUID and source UUID. A SpatialCondition can instead have an independent map/runtime owner. [BaseObject registration](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_object.py:50), [condition fields](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_conditions.py:398), [block indexes](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_block.py:79), [spatial owner](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spatial/area_conditions.py:482).

| Identity or ownership edge | Actual meaning |
| --- | --- |
| `condition.uuid` | Exact live effect instance, used for removal and child links. |
| `source_entity_uuid` | Causal creature/effect source. It is not necessarily the block containing the condition. |
| `target_entity_uuid` | Block on which the condition operates; it can be an entity or item/tile, not necessarily a creature. |
| `behavior_binding` | Immutable semantic behavior/provider/root identity plus runtime owner UUID. It is excluded from ordinary serialization. |
| `effect_origin` | Effect/cause provenance inherited from a supplied parent when missing; distinct from structural source ownership. |
| `modifers_uuids` | Existing, misspelled field storing value UUID → exact modifier UUIDs. |
| `event_handlers_uuids`, `spatial_handler_uuids` | Exact installed dispatch owners requiring queue/index cleanup. |
| `sub_conditions`, `parent_condition` | Same-block parent/child graph. |
| `linked_conditions`, `parent_link` | Forward `(owner_block_uuid, condition_uuid)` edges and reverse parent edge, including cross-entity and spatial owners. |
| `owning_action_template_uuid` in selected class effects | Persistent granting action template, distinct from its one-shot execution and from the active condition. |

The BaseCondition implementation has **no generic `template` switch**. Authored Python condition classes/metadata are definitions; a constructed condition is a mutable runtime instance even before `applied=True`. Action templates have their own lifecycle. RecklessAttack creates a fresh RecklessAttacking condition and records its UUID on its registered template only after accepted application. MetamagicActive owns temporary modifications to other registered spell templates. Treating all three as one interchangeable “effect definition” would erase current ownership. [RecklessAttack](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/classes/barbarian.py:290), [MetamagicActive](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/classes/sorcerer.py:984).

The content inventory expressly says its condition declarations do not independently construct or persist live condition instances. Runtime binding either preserves an explicit binding with matching owner, uses installed/scoped admission, or remains unbound for ordinary behavior when no gateway exists. Root-owned and explicit child routes have stricter requirements. The active provider context scopes child creation; it is not automatic proof that every child has been migrated to provider-aware admission. [Inventory contract](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content_system/condition_definitions.py:1), [runtime binding](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/content/runtime.py:187), [explicit child route](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/content/runtime.py:247).

### 2. Application: one outer owner and authored intermediate mutations

Entity.add_condition adds creature-specific immunity and saving-throw gates around the shared condition machinery. The chain is:

1. Require a name; fill a missing target UUID; establish binding/context and source/target display names.
2. Declare and publish ConditionApplicationEvent. Its `condition` is the live instance. A declaration veto discards the incoming tree.
3. Check static/contextual immunity. An immune application is canceled and also publishes an observation-only combat log. If an application saving throw exists, a success cancels before `_apply`.
4. BaseCondition.apply rejects already-applied or expired instances; publishes EXECUTION and respects cancellation. It invokes the concrete `_apply` under the provider context.
5. Concrete `_apply` installs modifiers, handlers, children or direct state and returns owned UUID collections plus an EFFECT Event. Some owners emit several EFFECT versions while doing this. The common method adopts returned collections and marks applied only after `_apply` returns.
6. A missing or canceled effect discards provisional ownership. An exception from `_apply` propagates after the entity/block attempts tree discard.
7. For a same-name existing condition, remove the old owner. **The incoming mechanics have already been installed at this point.** A removal veto discards the incoming condition and cancels replacement.
8. Index the new condition, then publish COMPLETION. `applied_source_event_cursor` is assigned after that completion returns, not before completion callbacks run.

Sources: [Entity.add_condition](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entity.py:1592), [BaseCondition.apply](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_conditions.py:729), [BaseBlock.add_condition](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_block.py:1166).

BaseBlock.add_condition has the `allow_events_conditions` gate, but does not perform Entity's saving-throw/immunity procedure. Supplying `check_save_throw` there does not make the generic block execute a creature save. Neither add method validates an already supplied target UUID against `self.uuid`; callers must compose the correct owner/target pair. This latter observation is from source, not a cross-owner misuse test.

The shared rollback operation releases `_release_owned_runtime_state`, Duration, recorded modifiers and handlers; it does **not** invoke the authored normal `_remove` hook. That is intentional for owners whose normal removal has new gameplay consequences, such as Haste's lethargy. Consequently, successful cleanup depends on each concrete owner recording state promptly or providing the separate provisional-release hook. It is not a general transaction over arbitrary code. [Provisional release](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_conditions.py:673), [tree discard](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_block.py:841).

Raging records each modifier/handler immediately, before later operations can raise, and explicitly unregisters admitted objects during cleanup. MetamagicActive retains its changed template UUIDs and supplies a release hook; BanishedCondition explicitly removes newly installed transform rows if EFFECT dispatch throws and compensates spatial suspension. These are concrete existing stronger owners; their guarantees cannot be inferred for every other `_apply`. [Raging receipts](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/classes/rage.py:343), [metamagic release](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/classes/sorcerer.py:1112), [Banishment compensation](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/abjuration.py:1335).

### 3. Removal, dependent effects and replacement

Public removal by name or exact UUID converges on one finite graph traversal. It prepares DECLARATION → EXECUTION → EFFECT for the root, recursively visits applied same-block children and linked conditions, and follows reverse `child_removal_policy` edges. `none` leaves the parent; `any` removes it after one child; `last` removes it only after no other applied unvisited linked child remains. A visited UUID set prevents cycles. The graph can contain independently owned spatial conditions. [Preparation](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_block.py:1019).

Preparation runs all vetoable removal phases before the ordinary commit loop cleans the prepared owner state. If a child vetoes, the accepted prepared removals are canceled and the graph remains active. If accepted, the list is committed in reverse preparation order: an ordinary parent-to-child traversal therefore completes children before its parent. Do not infer a universal topological order for every reverse-link entry point merely from the “child-first” description. [Prepare/commit entry](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_block.py:914), [canceled graph](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_block.py:949), [commit loop](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_block.py:973).

Cleanup invokes `_remove`, the direct-runtime release hook, exact Duration release, modifiers and handlers, and detaches ownership edges. The block then removes exact indexes and unregisters the condition before publishing COMPLETION with `_post_removal_stats`. A removal EFFECT is therefore an accepted cleanup cause, not the final cleaned after-state. If `_remove` throws, the code does not provide graph-wide rollback of already committed siblings. If accepted cleanup unexpectedly returns None/canceled, the block raises rather than silently completing. Those failure semantics must remain visible.

Modifier cleanup follows exact value/UUID rows, removing the modifier from self/outgoing/imported channels without wholesale clearing other sources. Detaching a modifier from a value is distinct from unregistering its BaseObject: ordinary `StaticValue.remove_value_modifier` only pops a dictionary entry, while Raging adds explicit registry retirement. Likewise, event handlers have queue indexes, optional owner-local indexes and BaseObject registration. BaseCondition calls handler.remove and remove_from_register; EventHandler.remove itself returns early if no queue entry exists. [Common cleanup](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_conditions.py:830), [value removal](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/values.py:2134), [handler removal](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:1336).

Same-name stacking is replacement, not automatic independent stacking. Differently named effects can own equivalent transforms independently. Active UUID and source indexes distinguish those ownership cases. The source-index cleanup should not be mistaken for “remove everything this caster ever supplied.” Exact slot, action-root and grant receipts are used where narrower retirement is necessary.

The `_expire` method exists on BaseCondition, but the read cleanup implementation does not invoke it. A repository search found no authored `_expire` override or call. The cleanup docstring claiming preservation of `_expire` does not establish a working separate expiration callback. Current expiration uses the ordinary removal path with `expire=True` on its events.

### 4. Duration is owner-relative, not render time

| Duration type | Current behavior |
| --- | --- |
| ROUNDS | Integer decremented by `progress`; expired at `<=0`. No positivity constraint prevents construction of an already expired duration. |
| PERMANENT | Must hold None; `progress` returns False. |
| UNTIL_LONG_REST | Must hold None; `long_rest` marks a flag and `is_expired` then returns True. |
| ON_CONDITION | Callable queried by `is_expired`; None means not expired. `progress` does not query it and returns False. JSON serialization emits the marker `"conditional"`, not an executable round-trip callable. |

[Duration](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_conditions.py:61).

BaseCondition's after-validator stamps the duration's owner UUID; it does not synchronize duration source/target UUIDs. Its explicit setters synchronize those fields, but construction and Entity.add_condition's direct field assignment do not invoke the setters. Default Duration source/target values are generated UUIDs. This distinction matters to contextual expiration, unlike a round counter that never consults identities. See the executed diagnostic below.

Entity.on_turn_start publishes TURN_START/EXECUTION, runs a death save, advances its condition names, then condition names on equipped/carried items, resets action costs/recharges resources, sets `is_my_turn`, and publishes EFFECT/COMPLETION. Entity.advance_duration_condition tries the removal save before decrementing rounds. Turn end does not generally advance durations. Entity.long_rest visits entity/equipped/inventory conditions, invokes condition.long_rest and removes expired conditions, then health rest recovery. Exhaustion overrides long_rest to replace itself with a reduced level through the entity owner. [Turn start](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entity.py:2239), [duration/save](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entity.py:1705), [long rest](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entity.py:1764), [Exhaustion](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/conditions.py:655).

Rage maintenance is registered at TURN_START/EXECUTION so HasAttacked/HasTakenDamage still exist before their one-round counters expire. Its source docs quote a turn-end SRD rule, but the implementation deliberately uses this turn-start marker check. Prone Auto-Stand is a **standard-action handler**, at TURN_START/EFFECT after resource reset. It consumes half base movement and then asks the entity to remove Prone. A separate Prone application during its owner's turn may immediately spend half movement and return CANCEL without indexing Prone. These are current mechanics, not timing rules to move into animation. [Rage check](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/classes/rage.py:151), [auto-stand](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/actions_functional.py:126), [Prone](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/conditions.py:1367).

Chill Touch illustrates why “target's next turn” is not universal: its timed tracker is placed on the caster; it links a NoHealing condition on the victim, and may own a contextual attack modifier in the victim's equipment. Caster expiration cleans the linked victim effect. [Tracker](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/necromancy.py:157), [producer](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/necromancy.py:365).

Spatial durations are inherited Duration objects, but map-owned progress calls deactivate and returns the actual removal result. This differs from the generic block/entity APIs, which return the expiration/save predicate even when a veto prevents removal. The owning spatial lifecycle also publishes explicit footprint-change facts before enclosing application/removal completion. [Spatial duration/removal](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spatial/area_conditions.py:668).

### 5. Standard concrete conditions actually read

The entire current `dnd/conditions.py` was read, including processors and declaration tables. This table summarizes code behavior without claiming complete SRD fidelity.

| Family | Mechanics and owned consequences |
| --- | --- |
| Underwater | Contextual weapon attack disadvantage/automiss depending on reach/range, swimming capability and explicit weapon exceptions. |
| HasAttacked / HasTakenDamage | Internal one-round marker conditions. Trackers use ATTACK and positive DamageApplied, respectively; they do not install a second full action owner. |
| Blinded / Deafened | Blinded owns visual-access denial, attack and incoming-attack modifiers, and sight-based skill failures. Deafened installs hearing-based skill failures. |
| Charmed | Contextual automiss against the charmer and social-check advantage for the charmer. This class does not itself implement every possible harmful-spell prohibition. |
| Dashing / Dodging / Disengaging | Movement bonus; incoming attack disadvantage plus Dexterity-save advantage; explicit opportunity-provocation cap. Each owns exact modifier rows. |
| Exhaustion | Cumulative level effects on skills, movement, attack/saves, max HP and level-six instant death; long-rest reduction and a revival handler. Level reduction constructs a replacement condition. |
| Frightened | Attack/check penalties when its source is visually contacted; current movement constraint is zero while that source is seen, rather than a directional move-toward test. |
| Grappled / Restrained | Grappled caps movement. Restrained additionally owns attack/save/incoming-attack modifiers. Relationship and escape owners live outside these generic status classes. |
| Incapacitated / Stunned / Paralyzed / Unconscious | Composed neutral transforms, with no fabricated global Incapacitated or Prone child for each severe condition. Unconscious adds visual denial and prone geometry; Paralyzed adds close-range automatic criticals. |
| Petrified | Stunned-like capabilities, resistance to every damage type and a Poisoned immunity entry; normal removal releases its immunity. |
| Prone | Distance-sensitive incoming attack advantage/disadvantage, own attack disadvantage, plus the immediate-stand application path described above. |
| Invisible / InvisibilityEffect / GreaterInvisibilityEffect | Direct invisibility plus contextual unseen-attacker/target modifiers. Normal removal recomputes whether another invisibility source survives. Spell Invisibility reveals on selected actions; Greater Invisibility performs escalating Stealth checks and defaults to ten owner rounds. |
| Hidden | Direct stealth DC, contextual attack advantage and a reveal handler. Normal removal recomputes surviving Hidden DC. Collision, very bright light, movement and full-turn agency-denying condition application are concrete reveal inputs. |
| Concentrating | Registered slots, cross-owner links and damage/death handler; detailed below. |
| ConcentrationActionMarker / NoReactions | Marker removes its granted action on normal cleanup; NoReactions owns reaction cap and relies on caller-authored duration. |

Shared transforms operate on a structural CreatureTransformTarget without importing Entity. They return ordinary modifier ownership rows and compose direct capability changes. This matches the current ECS-style aggregate composition: it does not create a parallel object hierarchy for every combination of conditions. Source/target in contextual modifier channels is intentionally evaluation-oriented; e.g. the afflicted creature is the outgoing modifier's source, and the attacking creature becomes its current target. [Transforms](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/creature_transforms.py:1).

### 6. Concentration: slots, shared targets and nested events

`SpellAction.ensure_concentration` caches an exact concentration UUID on the current cast so repeated application to several targets reuses one root. New Concentrating application can drop the oldest slot at capacity or migrate surviving slots/links into the replacement condition. Slot names identify maintained spells; slots also have exact registered UUIDs. A slot contains linked owner/condition pairs, while the concentration root holds the aggregate list. Removing the last linked child can remove the root through `child_removal_policy="last"`. Empty concentration is cleaned before the action terminal by the action's `_cleanup_concentration` hook. [Ensure/cleanup](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/actions.py:4566), [slots and migration](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/conditions.py:1553).

Dropping one slot prepares its entire dependent graph before committing. It seeds visited with the concentration root UUID so removing that one slot's children does not recursively remove other slots. A veto keeps both slot membership and spatial children intact; this was executed in the existing public test. Normal full concentration removal unregisters slots, removes its damage/death handler, and traverses children through the ordinary removal owner. Selected origin/class retirement asks this same owner to drop exact active roots; it does not scan all entities by spell name. [Drop slot](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/conditions.py:1641), [Tiefling Darkness retirement](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/origin_grants.py:968), [Sorcerer root graph](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/sorcerer_grants.py:605).

The concentration handler subscribes to DAMAGE_APPLIED/EFFECT and DEATH/EFFECT. Positive post-mitigation damage, including absorbed temporary HP, is the damage trigger. If the captured resulting normal HP is nonpositive it removes concentration without a save. Otherwise it requests a Constitution save with DC `max(10, applied_damage // 2)` parented to that DamageApplied version. A failed save removes the dependent graph and returns an updated damage Event marking concentration broken. These consequences can complete **inside** dispatch of DamageApplied/EFFECT, before DamageApplied COMPLETION and before later life-state resolution. [Handler](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/conditions.py:1776), [positive damage publication](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entity.py:2865).

Executed public diagnostic: apply Concentrating to an 18-HP caster, apply Dashing to a second creature, link that exact child, then `caster.receive_damage` with the existing fixed-random context returning 1. With 4 damage, DAMAGE_APPLIED DECLARATION/EXECUTION/EFFECT all saw HP 14, ALIVE and both conditions active. Removal phases for both then ran; child removal completed with only the parent still active, followed by parent completion. A reposted damage EFFECT and damage COMPLETION saw both removed. The linked target's movement returned from 60 to 30. With 100 damage, the same condition cleanup completed while HP was -82 and life still ALIVE; DamageApplied completed, then Death DECLARATION/EXECUTION, LifeStateChange COMPLETION to DEAD, and Death EFFECT/COMPLETION. This substantiates the nested ordering; it does not redefine rendering granularity.

Unexecuted boundary concerns: `ensure_concentration` does not inspect the add result before indexing `active_conditions["Concentrating"]`; a canceled new application can therefore interact badly with replacement/no prior concentration. Failed-save handler text marks concentration broken without testing the boolean removal result. These are owner-specific source concerns, not permission to rewrite concentration in this study.

### 7. Health, life and other direct state

Life-state capabilities belong to Entity's separate `_life_state_modifier_ownership`; they are not named Dying/Dead conditions. DYING and STABLE apply the unconscious capability transform; DEAD applies action/movement and visual denial. Healing removes/replaces only the life-state-owned rows. Independently applied Sleep/Unconscious/Paralyzed rows survive. LifeStateChange is a completed derived fact after the accepted damage/death/healing cause, and crossing the dead boundary also updates light suppression, occupancy path caches and perceivability. [Life-state owner](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entity.py:1876), [derived transforms](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/creature_transforms.py:336).

DamageApplied is emitted after HP mutation but before the later dying/death branch. It retains normal/temporary HP and typed resolution, and its EFFECT handlers can remove conditions. Reading current Entity state later is not a substitute for the earlier factual boundary. Direct Entity.take_damage, unlike receive_damage, rolls/applies Health damage without the TakeDamage/DamageApplied wrapper; code paths must be named accurately. [Damage paths](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entity.py:2845).

NoHealing owns the direct `health.healing_blocked` boolean; Health's healing and long-rest recovery consult it. It clears that boolean in normal `_remove`, not through a source-combining modifier. Haste adds a restricted-action grant owned by the condition UUID; normal removal releases it and can apply a new one-round HasteLethargy condition. Banishment owns spatial suspension with explicit compensation and differentiates failure before a position commit from failure publishing a committed position. These examples demonstrate why condition cleanup is broader than numerical modifiers and why calling normal `_remove` during every failed application would itself change gameplay. [NoHealing](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/necromancy.py:124), [Health consumer](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/health.py:678), [Haste](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/transmutation.py:760), [Banishment](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/abjuration.py:1319).

### 8. Event facts, observer semantics and complete lineages

ConditionApplicationEvent and ConditionRemovalEvent carry the **live BaseCondition object**, whose applied flag, duration, ownership lists, slot graph and concrete fields continue to change. They may also carry a SavingThrowEvent and runtime callables/context through that object. JSON set ordering is not passivity; Duration's callable marker is not a runtime reconstruction contract. Frozen bindings and effect-origin values do not make the rest of this object graph immutable. This is a concrete omission from the integration study's short passive-payload table, which already warns against blanket copies. [Event fields](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_conditions.py:165), [serialization](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_conditions.py:476).

Several condition handlers intentionally consume producer flags: HasAttacked checks `is_first_at_phase` at conditions.py:341; Hidden reveal, Invisibility reveal and Greater Invisibility checks use `is_last` at :2066/:2217/:2327. The event reviewer independently confirmed queue reposting does not recompute those flags. They are not complete-lineage evidence and should not be reused to schedule individual phase versions or declare presentation completion. Creation-lineage guards prevent a condition from immediately reacting to the same action that installed it. Actual parent/child condition removals, nested saves, sensory changes and life facts remain part of their complete causal lineage.

This study does not introduce new observer restrictions. Conditions have existing category/tags/agency-denial/obscures-perceivability semantics; Condition logs omit INTERNAL markers, and hidden/invisible mechanics consult event-time sensory contacts. A live condition reference or a primitive UUID is not by itself an observer-authorized retained fact. The condition reviewer did not independently reread the entire subjective mapper; the root discovery/subjectivity chapter records that full read. Its existing information rules are unchanged. The complete lineage remains the rendering unit; per-fact capture and operation return are supporting integrity boundaries, not new animation jobs.

### 9. Executed checks and precise limits

Read HOW_TO_TEST.MD first. No tests were added or changed. Commands used `PYTHONDONTWRITEBYTECODE=1` and pytest `-p no:cacheprovider`; diagnostics were stdin-only Python with fresh process state and public condition/action-owner APIs.

- `tests/engine/test_condition_lifecycle.py`, `test_condition_transform_ownership.py`, `test_standard_conditions.py`: **50 passed in 26.48s**. These prove accepted application indexes at completion, cancellation cleanup for recorded modifiers/direct-state hook fixture, graph veto preservation, name replacement, child policies, owned handler removal, duration/removal-save behavior, item condition lifecycle, independently owned severe transforms, and actual spatial Banishment compensation. The standard-condition test file was executed in full, but only its selected detailed scenarios were reread; the merged coverage/evidence ledger distinguishes that.
- `tests/engine/test_spatial_conditions.py::test_multi_slot_concentration_veto_preserves_slot_and_spatial_children`: **1 passed in 0.57s**. Proves a real slot-removal veto keeps slots, zones and dependent conditions active.
- Attempted concentration selection from `test_spellcasting.py` alongside spatial conditions: **collection failed**, 23 deselected, 1 error in 2.83s. `test_spellcasting.py` imports server.spell_catalog → server contracts → removed `dnd.core.senses`. No spellcasting test from that command ran. No server repair was attempted. Its concentration test source is useful intended behavior, not passing evidence on this branch. The spatial test was then run separately as above.

Additional executed observations, each through existing public Entity operations and an ordinary EventHandler where stated:

| Probe | Observed result | Scope of conclusion |
| --- | --- | --- |
| Cancel Invisible application at CONDITION_APPLICATION/EFFECT | CANCEL; condition absent/unregistered, applied False; `is_invisible=True` remains. | Direct-state provisional cleanup gap in this owner. |
| Cancel Hidden at the same boundary | Same cancellation/index cleanup; `stealth_dc=0` remains instead of None. | Same gap; the zero is the default Hidden roll in this probe. |
| Cancel Petrified at the same boundary | Condition removed, action permission restored to 1; Poisoned immunity remains True. | Modifier cleanup works, direct immunity cleanup does not run on this path. |
| Dashing with ON_CONDITION callable, then predicate becomes True | `duration.is_expired=True`; `advance_duration_condition=False`; still active. | The normal owner tick does not evaluate callable expiration. |
| Explicit condition IDs with default Duration IDs | Duration source/target each differ from condition IDs. | Constructor ownership stamping is not source/target propagation. |
| One-round Dashing, veto CONDITION_REMOVAL/DECLARATION during tick | `advance_duration_condition=True`; remaining duration 0; still active; movement 60. | Return means expiration predicate here, not successful removal. |

These observations are **not** a claim that every condition cancellation is broken. Recorded modifier cleanup and the specific Banishment/Raging/metamagic compensation patterns differ. NoHealing, Haste direct grants, ConcentrationSlot provisional retirement, exception-before-return ownership loss in other authored `_apply` implementations, and same-name direct-state replacement are source-motivated concerns not separately executed here. They remain explicitly unverified, rather than being counted as failures.

### 10. What this changes in the previous study's understanding

No disagreement with the user's complete-lineage design, existing subjectivity rules, two historical/reduced states, or source-authored timeline ownership was found. The earlier narrow Fire Bolt study was incomplete as a basis for general integration:

1. Its passive-payload inventory must also account for concrete live Condition objects and duration/slot/handler state. Event registry separation did not change those payloads.
2. Neither `canceled=True` nor a successful generic cleanup test proves “nothing happened.” Prone intentionally spends movement before canceled application; the three direct-state veto probes show unintended residue; Haste normal removal intentionally creates another effect.
3. “Expiration” is an owner-relative sequence, with removal saves, potential vetoes, nested linked effects and different trigger phases. A duration reaching zero is not necessarily successful cleanup.
4. Condition name, source UUID, actual effect owner, action template owner and grant receipt identity must remain distinct. Severe conditions share capability functions but retain independent UUID ownership.
5. Complete lineage means preserving nested save/removal/sensory/life work as such. An intermediate damage or condition completion is not a new presentation unit; producer flags do not close lineages.

These are study corrections and invariants to preserve, not a new implementation sequence. The merged ledger records the completed owner review and its remaining coverage limits. The content/item chapter records the deeper grant and item ownership study; all authored condition catalogs, multi-caster overlap, arbitrary interception combinations and full save-request lifetime/registry behavior remain outside this file's proof.

### Reproducing the stdin diagnostics

The following are concise reproduction steps for the executed probes, not new tests or a proposed owner API. Run each case in its own `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -` process, starting with `reset_engine_runtime(grid_size=(8, 8))`. Use `Entity.create(uuid4(), ...)` for an unplaced owner; the condition mechanisms here do not need a server or rendering. Use the ordinary `EventHandler`/`Trigger` constructors and `entity.add_event_handler`, not private dispatch.

1. **Application veto residue:** construct each of `Invisible`, `Hidden`, and `Petrified` with source and target both equal to a fresh entity UUID. Install an ordinary handler whose Trigger is `CONDITION_APPLICATION` at `EFFECT` for that source and whose processor returns `event.cancel(status_message="probe veto")`. Call `entity.add_condition(condition)`. Record the returned phase/canceled flag, condition `applied`, membership in both active indexes and `BaseCondition.get(condition.uuid)`, then the owner's `is_invisible`, `stealth_dc`, Poisoned immunity and action permission. Start fresh for each condition. This is the three-row cancellation probe in §9; Hidden uses its default roll.
2. **Callable expiration:** put a mutable boolean initially False behind a three-argument duration callable `(source_uuid, target_uuid, context)`. Give Dashing `Duration(duration_type=DurationType.ON_CONDITION, duration=callable)`, apply it normally, then set the boolean True. Read `duration.is_expired`; call `entity.advance_duration_condition("Dashing")`; inspect duration and active membership. Compare the default Duration source/target UUIDs with the explicitly supplied condition UUIDs before any explicit setter propagation.
3. **Expiry veto:** normally apply Dashing with `Duration(duration_type=DurationType.ROUNDS, duration=1)`. Install an ordinary `CONDITION_REMOVAL`/`DECLARATION` cancellation handler for the owner. Call `entity.advance_duration_condition("Dashing")` and record its return, remaining rounds, active membership and `action_economy.movement.normalized_score`. The duration reaches zero and the method returns True even though the removal veto retains Dashing and movement budget 60.
4. **Nested concentration and life:** create a caster with an 18-HP maximum (three maximum-mode d6 HitDice, neutral Constitution), a separate target, and a Concentrating root on the caster. Apply Dashing to the target; link its exact owner/condition UUID with `concentrating.add_linked_condition(target.uuid, child.uuid)`. Subscribe an on-event callback via `EventQueue.add_on_event_callback` which immediately stores primitive phase, event type, both HP/life values and both active-condition memberships for DAMAGE_APPLIED, CONDITION_REMOVAL, DEATH and LIFE_STATE_CHANGE. Under `fixed_randint(1)` from `tests.engine.test_condition_lifecycle`, call `caster.receive_damage(amount, DamageType.FIRE, source_entity_uuid=target.uuid)` for amount 4; repeat from fresh state for 100. Remove the callback in `finally`. The stored callback-time values, not references inspected after return, produce §6's ordering. This probe used the caster's default immediate-death behavior, not a death-save-enabled player.

The three pytest commands and their exact outcomes are also retained in [the merged coverage ledger](#source-coverage-and-evidence-ledger); the successful commands can be copied unchanged. The failed legacy-import command is recorded only as a coverage limitation.

## Values, dice, health and action economy

Date: 2026-09-08. Current working tree based on `16a6bfe141204cc46f336047da70e0cc9a4ceaa6`, branch `codex/recovery-design`. This is a read-only mechanical-owner study. The values reviewer changed no production source or tests. The five requested owner files were read completely: values.py (2,328 lines), modifiers.py (732), dice.py (365), health.py (811), and action_economy.py (1,228). Supplementary ranges, exact hashes, and limits are recorded in [the merged coverage ledger](#source-coverage-and-evidence-ledger).

This study describes the existing rules and implementation. It does not replace them with textbook D&D behavior, infer presentation outcomes from live values, or propose a new scheduler. Complete existing Event lineages remain the rendering unit; individual phase versions are mechanical/capture inputs.

### 1. Values are live composed rule state, not already detached facts

[BaseValue and StaticValue](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/values.py:41) are UUID-addressable data structures with modifier buckets, source/target/context metadata, normalizers, and `generated_from` provenance. BaseValue has its own registry; ordinary modifiers use the BaseObject registry. Construction, combination, and evaluator-created modifiers can register objects. These operations are not pure value arithmetic merely because their output looks numeric.

`ModifiableValue.create` builds four locally owned channels with aligned source identities and one named base NumericalModifier. An optional `identity_uuid` derives exact stable child/channel/modifier UUIDs. The four channels are self-static, self-contextual, outgoing-static, and outgoing-contextual. Optional imported channels point at the current target's exported effects ([1395–1478](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/values.py:1395)). Ordinary score, advantage, critical and auto-hit aggregation uses self plus imported channels, leaving outgoing channels available for another owner's explicit import.

That is not a uniform rule for every property: `damage_types` and `resistance_sum` explicitly include this value's outgoing channels as well as self/imported channels ([1702–1780](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/values.py:1702)). A summary claiming all aggregates exclude outgoing modifiers would be false. Effective size ignores MEDIUM channel results and chooses largest/smallest using self-static's policy. Imported size channels are consulted twice in current code; this is source behavior, not a proposed alternate priority system.

`combine_values` validates source UUID compatibility, merges dictionaries by modifier UUID (later colliding entries win), preserves modifier objects, and records the source value UUIDs in `generated_from`. It creates new registered containers, not a detached immutable clone ([631–668](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/values.py:631), [1248–1292](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/values.py:1248), [1895–1954](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/values.py:1895)). Current Entity bonus assembly deliberately adds a deep model copy after composition and resets temporary imports in `finally`; that is an owner-specific measure, not a guarantee provided by `combine_values` itself ([2460–2548](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entity.py:2460)).

### 2. Aggregation laws actually implemented and protected by tests

Numerical channels sum contributions, apply their own constraints, and then the containing ModifiableValue sums the already constrained channel scores and applies aggregate constraints again. Normalized scores use each NumericalModifier's optional normalizer; they do not simply normalize the grand total once. Global normalizer propagation mutates the numerical modifiers or contextual callable attributes when invoked. Newly inserted modifiers are simply inserted into their bucket; add methods do not rerun model validators or provide a universal ownership gate.

Existing constraints intentionally select the **lowest minimum and highest maximum**, the widest bounds. With a base self-static score of 6 and contextual minimum 8, the contextual channel contributes 8 and the aggregate is 14. The maintained test explicitly pins this outcome, so it must not be silently rewritten as a single final `max(6,8)` clamp ([values 408–489](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/values.py:408), [1513–1604](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/values.py:1513), [test 458–520](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_modifiable_value_semantics.py:458)).

Other existing combination laws:

- Advantage is a signed sum: advantage +1, disadvantage −1. Two advantages and one disadvantage produce advantage. There is no generic “any of each cancels regardless of count” implementation here.
- NOCRIT takes precedence over AUTOCRIT; AUTOMISS takes precedence over AUTOHIT.
- Resistance contributes +1, immunity +2, vulnerability −1 per damage type. Sum >1 means immunity, 1 resistance, 0 neutral, negative vulnerability. Two independent resistance modifiers therefore produce immunity in the current maintained test.
- Damage-type selection counts occurrences, returns the most common ties, and `damage_type` uses `random.choice` on those ties. Repeated property reads need not select the same representative type.

Sources: [modifiers status values](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/modifiers.py:18), [static aggregation](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/values.py:493), [maintained enum precedence test](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_modifiable_value_semantics.py:86), [maintained resistance test](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_modifiable_value_semantics.py:246). These tests were read, not rerun in this study. Their explicit expectations establish current compatibility semantics, not a claim that all rules match a particular D&D edition.

### 3. Context and target propagation are explicit, mutable, and directional

A contextual callable receives `(source_uuid, target_uuid, context)`. Its modifier owner UUID and its invocation source are distinct concepts. In an imported target channel, source remains the defender/channel owner and target becomes the attacking value owner. `set_from_target_contextual` validates that relationship, requires an explicit reverse target, then makes a **shallow** channel copy. Static import validates the outgoing source and makes the same kind of shallow copy ([1840–1879](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/values.py:1840)). Modifier dictionaries remain shared. The maintained test mutates a defender modifier and adds a new defender modifier after import; both immediately change the attacker's score ([test 600–644](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_modifiable_value_semantics.py:600)).

`set_context` propagates to the two locally owned contextual channels; it does not overwrite the already imported target channel's context. `set_event_lineage` separately labels local and imported contextual channels; `clear_event_lineage` clears those labels. `clear_target_entity` removes imported channels. BaseBlock recursively forwards target/context operations to direct values and child blocks ([460–521](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_block.py:460)). Correct nested action behavior depends on the rule owner restoring what it temporarily changed; it is not an ambient universal context stack in these value files.

`ContextualModifier.evaluate` always invokes the callable. It catches exceptions, logs, and stores the result or None under `source|target|lineage`; it never uses that dictionary to skip evaluation ([318–361](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/modifiers.py:318)). The word “cache” means retained last evidence for breakdowns here, not memoized deterministic mechanics. Context contents are not included in the key. A second evaluation in the same lineage overwrites the prior entry; a new context before a fresh evaluation can leave a stale displayed breakdown. The existing failing-call test proves two reads make two calls ([test 364–457](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_modifiable_value_semantics.py:364)).

Strict `execute_callable` requires stored arguments, propagates exceptions, and requires the exact supported modifier family; None is rejected even though ordinary aggregation allows an inactive None. Its setup checks invocation source against the contextual modifier's target, an easy identity distinction to miss. Ordinary aggregation also ignores results of the wrong modifier family. Repeated property access inside min/max and final aggregate calculations can invoke contextual rules multiple times during one high-level read.

`get_breakdown` reads already combined static numerical entries; it deliberately does not recursively recount `generated_from`. Full breakdown methods consult the retained contextual results for the current key and do not call rules ([1956–2132](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/values.py:1956)). These are useful existing evidence owners, but they are not historical snapshot APIs. A passive consumer needs the result selected at the actual event boundary, not permission to rerun arbitrary rule callables later.

### 4. Dice construction, actual roll identity, and Event interception are different owners

[Dice](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/dice.py:180) describes one dice expression, holds its live ModifiableValue bonus, and caches one DiceRoll on first `.roll`. Dice and DiceRoll each have their own registry. DiceRoll records chosen/all faces, total and captured status values, but remains a mutable Pydantic model with a mutable results list; it is not frozen just because Event field prose calls it immutable.

The dice module owns randomness and raw selection. `fixed_dice_faces` temporarily replaces its random provider, validates faces only when consumed, restores it in `finally`, and rejects exhaustion. Unused supplied faces are not rejected. This provider does not cover every random operation elsewhere: Health's hit-die methods use their separately imported `randint`, and value damage-type tie selection uses `random.choice`.

A normal d20 rolls one face; advantage/disadvantage rolls two and selects max/min while retaining both. Damage criticals use twice the base dice count plus `crit_extra_dice`, then add the normalized bonus once. Healing does not require an attack outcome; non-damage expressions must not supply one. Non-damage/heal rolls reject counts greater than one. Actual source `_roll` consults advantage for any configured dice, including damage/heal; those cases record only selected values in `.results`, and damage/heal random-face accounting currently reports effective count rather than both alternatives. No damage-advantage use case was executed in this study.

Dice does not emit an Event or determine hit success. `Entity.roll_d20` rolls first, constructs the exact Attack/Save/Check result Event category, publishes EFFECT for interception, completes that result lineage, and returns its effective roll. `roll_d20_event` intentionally returns at EFFECT so its caller can add causal children before completing it ([3683–3831](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entity.py:3683)). Optional weapon/ability/skill metadata does not demote a specific result category into generic D20. The Event study covers ordered `replace_roll`, `append_damage_roll`, and original/effective packet audit semantics.

`determine_attack_outcome` compares total to DC for saves/checks. For attacks it handles AUTOMISS/AUTOHIT, natural 1, natural 20, critical immunity, threshold and automatic critical status in explicit precedence order ([141–185](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entity.py:141)). A lowered critical threshold alone does not turn a below-AC non-20 attack into a hit. The existing tests cover selected dice, cache identity, category matching and natural-face differences ([225–307](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_dice_event_semantics.py:225), [435–548](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_dice_event_semantics.py:435)).

One finite diagnostic exposed the limit of repeated live bonus reads: a contextual callable returning 1 on its first invocation and 2 on its second produced face 6, total 7, but stored `bonus=2`. Dice evaluates the normalized bonus once for total and again for the recorded bonus. The same `.roll` object is correctly cached afterward. This is an artificial source-owner probe showing the consistency assumption, not a claim that an existing authored feature currently exhibits this mismatch.

### 5. Health resolves a packet; Entity owns causal mutation and life transitions

Health contains authoritative life_state, hit-dice sources, max-HP bonus, temporary HP, normal `damage_taken`, flat/type defenses and healing-blocked state. Its primitive methods do not dispatch DamageApplied, Death, Heal, or action Events; those causal orchestration decisions live in Entity and the action owners. Direct Health mutation is therefore not equivalent to executing a damage action.

The existing neutral [DamageResolution](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/damage.py:10) is frozen and extra-forbid, unlike DiceRoll/Event. It records typed component results and validates selected conservation equations. Health uses it directly through the existing `DamageApplicationPreview` alias; no alternate result protocol is proposed.

[Packet resolution](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/health.py:510) performs these concrete steps:

1. Validate nonnegative components and actual DamageType; read resistance for each component.
2. Multiply and truncate each component independently. A pair of resisted odd amounts does not necessarily equal halving their sum once.
3. Sum post-affinity components, subtract bounded nonnegative flat damage reduction **once for the packet**.
4. Allocate temporary HP first, then remaining normal damage, then an optional survival cap on normal damage.
5. If current normal HP availability was supplied, split applied normal damage into effective loss and overkill. The overkill split does not cap the damage_taken mutation itself.
6. Record declared-versus-post-handler prevention/amplification separately from affinity, flat reduction, temporary HP and survival prevention.

`apply_damage_preview` removes the preview's temporary HP allocation and adds its normal damage, returning only normal damage. It does not validate that the health state still equals the previewed state, attach an ownership receipt, reject reuse, emit Events, or perform lifecycle changes ([609–676](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/health.py:609)). Public probe: applying the same 3-damage preview twice marks 6 damage. That is a primitive-call contract, not proof of a broken Entity action. A renderer cannot safely replay this method while replaying facts.

Temporary HP uses numerical modifiers: a positive grant replaces the current pool only if larger; smaller grants do not stack. Removal adds a negative contribution or clears all modifiers once exhausted. Health's total HP helper includes temporary HP and subtracts normal damage without clamping to zero ([728–780](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/health.py:728)). Normal HP, temporary HP, effective loss, overkill, and lifecycle must remain distinct when explaining recorded outcomes.

Healing has a source-level caveat: with temporary HP present, current `heal` treats part of normal damage_taken as absorbed by that pool before reducing the remaining amount. A direct probe with damage_taken=5, temporary HP=10, heal=5 leaves damage_taken=5. This is observed primitive behavior; its rule intent and higher-level impact require a concrete Entity healing case before any repair. Long rest first clears temporary HP and recovers hit dice, then resets damage_taken unless healing is blocked ([686–726](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/health.py:686)). Dead-entity rest eligibility is outside Health and protected in the current Entity test.

HitDice keeps modifiable die size/count, spent dice, source identity and cached maximum-HP calculation. Average/maximum modes treat the first level specially; current roll mode rolls all configured dice directly. Available dice clamp count minus spent at zero. Spending precedes rolling; long rest recovers up to half total hit dice, at least one when any exist. Add/remove validates exact source ownership and unregisters the removed hit-die's locally owned values/modifiers ([108–171](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/health.py:108), [404–479](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/health.py:404)). Cached hit_points is not automatically invalidated by later die-size/count mutation in this file.

### 6. Action economy distinguishes channel debits, named resources, and entitlements

Actions, bonus actions, reactions, movement and nine normal slot ranks are ModifiableValues. `action_permission` and `provokes_opportunity_attacks` are separate neutral gates. Conditions can constrain capability without erasing the underlying spent-resource bookkeeping. `can_afford` reads the full normalized value, including contextual terms and constraints; `current_speed` excludes named cost modifiers and Dashing additions while retaining actual speed modifiers ([864–959](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/action_economy.py:864)).

Channel spending installs negative NumericalModifiers. Current cost identification uses the substring `cost` in modifier.name, not negativity or a separate universal cost registry. Turn reset removes those modifiers from four channel buckets but leaves their registry objects; slot reset also unregisters its cost modifiers and releases eligible floor handles. The direct turn-reset probe confirms a restored action count, absent debit in its channel, and still-present BaseObject registry entry. That is a concrete cleanup asymmetry, not a permission to perform global cleanup.

Named Resource uses mutable current/maximum values, exact source-keyed capacity contributions, a SUM or MAXIMUM combination policy, and explicit recharge timing. New contributions must agree with an existing resource's policy and recharge type. Partial recovery contributions are separately keyed and capped; long rest fully restores both short- and long-rest resources before considering partial additions. `add_resource` is a retained convenience which replaces the named resource at full uses with one deterministic legacy source; it is not equivalent to idempotently adding one contribution ([89–215](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/action_economy.py:89), [496–645](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/action_economy.py:496)).

Capacity recomputation preserves `spent=max(0,maximum-current)` for that one transition. It does not retain expenditure beyond a shrunken maximum indefinitely. Probe: maximum5, spend4, shrink maximum2 → current0; restore maximum5 → current3, because only two spent uses remain representable after shrinking. Record this limit when describing rebuild behavior. Direct Resource.consume also lacks a nonnegative amount guard; normal typed fixed-resource costs require positive StrictInt amounts. No negative-resource probe or authored misuse trace was added.

Normal spell slots use one authoritative aggregate capacity receipt, not additive class-local pools. Capacity installation computes baseline availability excluding old owned capacity and spend modifiers, installs one exact delta per rank, retains spend modifiers, and adds a zero availability floor. Reusing one source with changed capacity is rejected; a new source replaces the previous aggregate by exact handles. Removing capacity leaves floors while spend remains; resetting slot costs can release them ([659–862](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/action_economy.py:659)). Receipt validation proves handle presence, not arbitrary future rule compatibility or immutable ownership of every nested object.

Restricted action grants are explicit, source-owned named turn budgets with allowed action families and replaced cost types. Haste's policy is retained as actual data. Grant removal checks owner identity; the ActionEconomy only owns the budget/grant, while BaseAction owns selecting eligible action options and substituted costs ([372–445](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/action_economy.py:372), [neutral contract](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/action_types.py:47)).

AttackMultiplicityGrant means **total attacks within one Attack action**, not extra actions and not a sum of class ranks. Resolution chooses highest attacks_per_attack_action, then acquisition ordinal and UUID for deterministic tie-breaking; default is one. This block stores grants but does not execute the attack sequence ([447–494](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/action_economy.py:447), [neutral grant](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/feature_grants.py:6)). Actual action consumption and ordered attacks belong to the parent action study.

### 7. Exact fixed-cost rollback exists; it does not extend across arbitrary Events

Current ActionEconomy contains narrow, concrete receipt operations ([988–1182](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/action_economy.py:988)):

- Aggregate repeated typed channels deterministically and omit zero totals.
- `consume_aggregate_with_receipt` checks aggregate affordability before installing any debit.
- `install_prevalidated_aggregate_with_receipt` installs previously admitted debits without another affordability read, recording exact modifier UUID/name/amount and economy owner UUID. Failed insertion removes both installed and pending owned modifiers.
- `undo_prevalidated_debit` validates every handle and the economy identity before removing any owned state. Changed/forged/already-consumed receipts fail; unrelated modifiers remain.
- `commit_fixed_costs_without_dispatch` checks typed channel and named-resource aggregates, installs channels, then spends resources; a resource failure restores captured resource current values and undoes the exact channel receipt.

These are synchronous, no-dispatch owner operations. They do not roll back arbitrary handler emissions, committed world mutations, reaction state, observers, or an entire action. `consume_prevalidated` expressly trusts its owner boundary because admitted action costs may need to remain payable after declaration handlers install capability constraints. The current public tests cover aggregated debit, unaffordability before mutation, injected insertion failure before/after insertion, resource failure unwind, exact once-only undo, and forged receipt rejection ([entire test](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_action_cost_atomicity.py:1)). Those tests were read, not rerun here.

### 8. Evidence, open limitations, and scope

Five finite public-API observations ran in a fresh subprocess; the preceding sections retain their inputs, operations and observed results. They cover repeated contextual bonus reads, healing with a larger temporary pool, repeated damage-preview application, capacity shrink/regrow, and turn-cost registry cleanup. The values reviewer ran diagnostics only and added no production diagnostic behavior.

Source concerns are separated from demonstrated authored-game defects. The artificial changing callable proves an evaluation consistency assumption, not that current authored dice are wrong. Reapplicable preview is a primitive boundary, not a replay instruction. Signed advantage/resistance and permissive constraints are explicitly maintained behaviors. Heal/temporary HP, resource shrink history and retained turn-cost registry handles are concrete observations to trace further only if the parent owner study finds them relevant.

The values reviewer did not independently reread Entity, BaseAction, Attack/Spell, rest orchestration or every condition/context callback. Other chapters record their own coverage; complete class/resource catalogs, test suites and serialization consumers remain outside this chapter's proof. This pass does not claim whole-codebase coverage or a new universal capture schema. It establishes why accepted numeric/roll/damage/resource evidence must be understood at the existing causal owner boundary rather than recomputed by presentation from a live graph.

## Spatial ownership, movement and subjectivity

Read-only study of the working tree on `codex/recovery-design`, HEAD
`16a6bfe141204cc46f336047da70e0cc9a4ceaa6`, including current uncommitted recovery
changes. These notes describe current code, not an endorsement that all its
exception paths are correct. No historical branch was needed. Exact read ranges,
indexed-only files and gaps are recorded in [the merged coverage ledger](#source-coverage-and-evidence-ledger) below. This chapter records the spatial review findings.

### 1. Owners and authority

| Owner | Authoritative data / work | Boundary to preserve |
| --- | --- | --- |
| `Entity` | Position, deployment and spatial suspension; composition of presence with observer registration | Its position writer commits the entity and Tile membership before publishing occupancy. |
| `GridMap` | Existing Tiles, exact object placements, spatial-condition indexes, connectors, spatial query revisions and light contributions | No renderer or art metadata determines traversal, contacts or topology. |
| `Tile` | Support height, surface/slope, four movement cost values, intrinsic optics/propagation, light contributions, immutable object-band snapshots and entity/spatial-condition references | Independent conditions are references to one owner, not copied conditions per Tile. |
| `SpatialCondition` / `AreaCondition` | Exact condition identity, footprint, anchor, lifespan, handler IDs, owned terrain/light mechanics and linked children | Existing condition lifecycle and EventQueue dispatch; no parallel zone engine. |
| `SpatialSensesSystem` | Per-observer visual cells, typed contacts, effective light and candidate indexes | It runs before causal completion and emits observer-local concrete sensory Events. |
| `Senses` navigation materialization | Derived known paths and collision memory | Perception and path refresh are separate operations. |
| `world_authoring` | Explicit composition of world edits with before/after cold values and audit identity | It calls existing GridMap/BaseItem owners; it is not a second spatial registry. |

Sources: [GridMap state](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py:81),
[Tile](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_tiles.py:54),
[SpatialCondition](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spatial/area_conditions.py:40),
[sensory owner](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/sensory.py:608),
[world authoring](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/world_authoring.py:1).

### 2. Voluntary movement: proposal, interception, commit, publication

`Move._apply` uses the selected path and mode. For each leg it validates objective
`GridMap.can_transition`. If the objective leg fails but the subjective leg was
allowed, it records positional or directional collision memory and emits a
movement-collision child. That reveals a blocked route through existing sensory
rules; it does not itself grant the hidden blocker's identity.

The accepted leg is posted as `StepMovementEvent` at EFFECT with source/destination,
path index, cost, trajectory, disclosed leg, support elevations and provocation
policy. This is the interception point: opportunity attacks and other step rules
can cancel or incapacitate the actor before its coordinates change. The code
checks canceled state, ability to act/life state and objective transition again
after handlers. A non-canceled intercepted leg can complete with
`committed=False`. A canceled leg stays canceled.

Only after those checks does movement spend the leg's movement cost and call
`Entity.update_entity_position`. That writer:

1. Validates deployment, old membership and exact positions.
2. Stages the entity position, replaces old/new Tile membership, invalidates
   occupancy-dependent path caches, and rolls back this stage if the commit fails.
3. Publishes a LEFT fact at the old cell and ENTERED fact at the new cell, in that
   order, under the processed Step UUID. These occupancy facts are already
   committed and their phase publication is non-vetoable.
4. Lets ordinary entry/exit rules, attached effects, lights and sensory work settle.

The outer movement then publishes Step COMPLETION with `committed=True`, records
the actual traversed leg, and invokes the optional existing scoped continuation
guard. Its `MovementStepBoundary` carries the step UUID, parent lineage, objective
position, costs, traversed path and exact source cursor interval. The default is
CONTINUE; this is a controller revalidation boundary, not animation completion.
The final movement Event reports actual traversed path/end/cost and termination
reason. Navigation is materialized in `finally` separately from perception.

Sources: [Move application](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/actions.py:689),
[final movement result](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/actions.py:889),
[entity position commit](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entity.py:768),
[Tile membership commit](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py:2043),
[membership publication](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py:2123),
[committed occupancy dispatch](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py:229),
[continuation data](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/action_execution.py:44).

Concrete existing case: a lethal opportunity attack leaves the mover at the source
and produces a Step completion with `committed=False`; it must never animate as a
successful move simply because an EFFECT contained a destination. The case is
source-read at [combat test](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_combat_actions.py:540).

### 3. Forced movement and connector transfer are distinct existing paths

Shove proposes its own action, resolves prone versus push, and for a push constructs
one `ForcedMovementEvent` with intended/actual distance, direction, start/end and
obstacle information. It precomputes reachable cells through objective
`can_transition`, dispatches the forced lifecycle, then commits each cell via the
same Entity writer. It emits LEFT/ENTERED and therefore triggers hazards and
membership, but emits no `StepMovementEvent` and does not spend the target's
movement budget. It stops if entry consequences prevent further action and
completes with actual resulting position/distance.

The public forced-through-spikes case has one forced lineage, two ENTERED children,
two damage completions parented to those entries, then the forced completion. A
renderer must preserve that whole lineage and its relationships, not interpret the
forced completion's destination as a teleport or turn each damage row into an
unrelated render job.

Sources: [Shove path/application](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/actions.py:3580),
[forced movement test](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_manual_11_grid_tiles_terrain_movement.py:190),
[forced trap lineage test](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_combat_actions.py:688).

`TraverseConnector` is one SELF action for all connector kinds. Discovery freezes
the connector UUID, authored ID, revision, digest, endpoint positions/elevations,
costs and provocation policy. Execution revalidates these exact current facts;
`kind` does not select a separate mechanics executor. It posts one
`CONNECTOR_TRANSFER` Step with the endpoint pair as its disclosed path. After that
Step survives, it rechecks the connector and destination, consumes an aggregate
cost receipt, commits position, and completes the Step. Thus a ladder can cross
an otherwise illegal ordinary height edge without weakening ordinary walking.

Sources: [connector action](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/actions.py:1088),
[transfer commit](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/actions.py:1332),
[connector public proof](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_traversal_connectors.py:152).

**Observed limitation, not fixed:** `TraverseConnector` catches every exception
from `update_entity_position` and undoes the cost receipt
([actions.py:1420](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/actions.py:1420)).
`PositionPublicationError` explicitly means position is already committed,
whereas `PositionCommitError` means it is not. This catch does not distinguish the
two. The selected tests prove success and precommit veto, not this publication
failure case. Other owners already distinguish the classes (e.g. banishment
return tests). Do not claim all movement exception paths are transactional.

**Unverified edge:** Shove's per-cell forced loop uses its precomputed reachable
cells; there is no fresh `can_transition` inside that loop. Entry effects that
alter a later cell need a specific public case before making a broader statement.
Spell-specific forced producers were indexed but not individually read here.

### 4. Spatial handlers and sensory subscriptions have different jobs

`EventQueue.add_spatial_handler` indexes a mechanical handler by event type,
phase and exact cells. `spatial_dispatch_positions()` controls this dispatch.
`SpatialChangeEvent` returns only its primary cell even when
`get_affected_positions()` contains old/new placements, neighbors or both movement
endpoints. The queue combines positional and applicable global trigger handlers,
deduplicating handler UUIDs. Area footprint edits reindex these existing handlers.

`GridMap.subscribe_to_cells` instead stores observer-to-cell and inverse
cell-to-observer memberships. `SpatialSensesSystem` uses them conservatively to
choose which observers may require recomputation. It also has known-path and
known-entity/object reverse indexes. No game rule is executed by this subscription
index. These are not interchangeable subscriptions and should not be merged into
one new dispatcher.

Sources: [queue selection](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:2381),
[spatial registration](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:2569),
[affected versus dispatch cells](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:4115),
[observer subscriptions](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py:292),
[candidate observers](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/sensory.py:1000).

### 5. One independent condition owns one footprint

`SpatialCondition` owns an exact `ContentRef`, layer, occupancy policy, anchor,
footprint, trigger declarations and linked descendants. GridMap indexes the owner
once by UUID and references it from every affected Tile. `Tile.get_conditions`
combines direct Tile conditions with these exact independently owned references.
Missing/inactive references are errors. `dnd/tile_conditions.py` still contains
explicit legacy marker records; those are not the active independent SpikeTrap
implementation and should not be revived as the area engine.

Activation preflights every footprint cell. OVERLAPPING conditions coexist.
EXCLUSIVE_TRANSFORMING conditions require an authored transformation between
different materials; matching identities arbitrate using potency and effective
spell level. An explicitly authorized replacement must cover cells owned by the
specified incumbent in the same layer. The incoming application prepares its
footprint, commits admitted membership, installs handlers and mechanics, and
settles displaced incumbents only after incoming application succeeds. Failure
restores displaced Tile memberships through the existing condition cleanup.

The CREATED spatial-change EFFECT is the parent of admitted terrain/light and
occupant consequences. Those descendants finish before the spatial change and
outer condition application finish. Footprint updates carry previous and new
positions, remove only lost-cell mechanics, reindex handlers, add new-cell
mechanics and apply only declared effect-enters/effect-leaves triggers. Merely
moving an area over a target is not automatically the same rule as target ENTER.

Removal preflights the finite linked/subcondition graph using the existing
BaseBlock lifecycle. A descendant removal veto preserves the whole active graph;
accepted removal commits child-first, releases handler/modifier/light/Tile
ownership, and closes spatial then condition-removal terminals. Round retirement
uses inherited Duration; there is no rendering clock in zone lifetime.

Sources: [condition admission](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spatial/area_conditions.py:219),
[activation](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spatial/area_conditions.py:482),
[removal graph](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spatial/area_conditions.py:742),
[footprint mechanics](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spatial/area_conditions.py:1263),
[GridMap index](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py:1225),
[legacy Tile records](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/tile_conditions.py:1).

### 6. Membership, aura movement and overlapping status sources

`MembershipAreaCondition` creates an internal lease carrying exact
`source_spatial_condition_uuid`, links it to the spatial owner, and applies its
public manifestation through the entity condition lifecycle. Lookup is by source
class and UUID, not display name. Repeated entry within the same footprint keeps
the lease; actual exit removes only that owner's membership. The unusual legacy
`SpatialChangeEvent.old_position` field is significant: on ENTERED it is the old
cell, but on LEFT it is the **destination**. The exit membership predicate checks
that destination to distinguish within-area movement from leaving the area.

Membership admission runs before the area first-per-turn effect fence. That fence
uses actual `turn_execution_id` and target UUID, shared across the declared gated
trigger kinds; without turn execution context it allows the trigger. Do not make
turn gating a renderer timer or accidentally suppress reacquiring continuous
membership when repeated damage is suppressed.

Entity-attached conditions use the existing global ENTERED/LEFT EFFECT handler:
translate footprint on committed ENTERED; deactivate on terminal LEFT with no
destination. The active code also has world-object anchor handlers. The explicit
world-authoring APIs conservatively reject position changes/removal of objects
with active attached conditions, while allowing orientation. Do not infer that
the current authoring surface already supports arbitrary moving object auras.

Wet demonstrates two exact spatial leases sustaining one public Wet manifestation
and one set of resistance modifiers; the final lease removal removes Wet.
Restraint leases similarly share Restrained, each install escape actions that
refer to that exact lease, and remove only those actions/lease on escape. General
condition stacking is owned by existing condition logic, not a visual identity.

Sources: [membership](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spatial/memberships.py:1),
[LEFT field contract](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:3723),
[turn fence](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spatial/area_conditions.py:1009),
[anchor handler](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spatial/area_conditions.py:387),
[Wet leases](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spatial/environmental_conditions.py:422),
[restraint ownership](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spatial/restraints.py:136).

### 7. Environmental content composes ordinary mechanics

The active SpikeTrap is one persistent network owner with one indexed ENTERED
handler across all its cells. First entry reveals the network once, then damage
is parented directly to that ENTERED Event; expanding the trap retains its UUID
and reindexes the same handler. PullLeverAction refers to this exact condition
UUID and invokes its removal lifecycle; it does not manipulate Tile marker names
or handler dictionaries.

FireSurface declares entry and turn-start damage and source-owned bright light.
Oil adds owned difficult terrain. Wet, Ice, ElectrifiedWater and Steam compose
membership, saves, damage, light/obscurement and declared triggers. Material
interactions use `SpatialEffectInteractionEvent`, exact recipe comparisons and
the existing spatial handler. Douse removes selected cells; freeze/electrify
replace selected water cells; vaporize creates a secondary SteamCloud and removes
the affected original cells. Unknown recipes raise. These are direct finite
content builders, not an expression language or generic reaction compiler.

OilBarrel destruction activates Oil at its committed object position under the
damage cause. Fire destruction additionally emits IGNITE interaction under that
same cause. Torch owners create/remove GridMap light sources and ExposedFlame
events; movement of attached light is settled by the existing spatial-presence
path. DirectionalDoor changes its BoundaryStructure in place; the older
DoorObject changes center-blocking flags. Their publication patterns are not all
identical and must be read before admitting those families as committed facts.

Sources: [SpikeTrap](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spatial/environmental_conditions.py:954),
[lever](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/items/environment_interactables.py:170),
[material transitions](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spatial/transitions.py:1),
[OilBarrel](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/items/environment_item_builders.py:42),
[torch](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/items/torches.py:301),
[wall torch](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/items/torches.py:583),
[directional door](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/items/environment.py:317).

### 8. Sensory reduction runs before causal completion records its metadata

`SpatialSensesSystem.attach` registers one named pre-completion system. On each
relevant Event it selects candidates, snapshots each observer's prior cache,
recomputes exact current perception from the committed world, marks navigation
dirty when perception or known topology changed, creates a delta, and publishes
the completed sensory sequence. The delta carries `parent_event`, `parent_lineage`
and `cause_event_uuid` of that causal Event. Event completion then computes child-lineage
and location evidence. Sensory Events do not recursively invoke the
pre-completion system.

Moving LEFT with a destination deliberately produces no standalone sensory
recompute; ENTERED includes both endpoints and recomputes once. Terminal LEFT is
different. Attached-light movement and optical topology consequences settle
before the parent completion, so sensory snapshots see the committed light field.
One ordinary move therefore preserves both objective occupancy facts while
producing one observer contact transition, not a transient disappearance followed
by rediscovery.

Sources: [sensory reduction](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/sensory.py:1060),
[skip paired LEFT](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/sensory.py:1026),
[delta producer](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/sensory.py:471),
[Event completion](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:538),
[light before spatial completion](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py:2384),
[presence/light settlement](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py:4030).

### 9. Exact contact is not visual-cell access, and identity is not current location

Visual cells come from optical topology filtered by objective light, visual
capability and source-owned special senses. Heavy obscurement and magical
darkness have distinct existing sense rules. Blindsight/tremorsense use physical
propagation, create typed nonvisual contacts and do not create visual cells or
effective-light entries. Hidden contact is excluded when stealth DC is at least
passive perception. Invisibility is separately checked and may be bypassed by
existing true/see-invisible senses.

A boundary wall may be a visual object contact from the near side even when its
owning far Tile and that Tile's entity are unseen. `get_boundary_route_layers`
first exposes the near exit layer; only if it transmits does the far entry layer
become evidence. Therefore contact UUID/location, `contact.visual`, cell
visibility, historical `seen`, and perceived light are not synonyms.

The passive sensory reducer removes current contacts explicitly, applies changed
typed contacts and light after-values, and unions historical seen cells. Event
identity grants are separate from per-version location grants. A Step completion
uses the source-position grant captured before the leg and the destination grant
after the leg independently. Presentation must retain those existing facts; it
must not poll the latest actor coordinates or infer that identity permission
implies visibility of every historical coordinate.

Sources: [sense recomputation](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/sensory.py:670),
[contact resolution](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/sensory.py:928),
[passive sensory reducer](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/sensory.py:348),
[event grants](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:404),
[Step coordinate evidence](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:4408),
[near-side public case](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_senses_light_stealth.py:1407).

### 10. Support height, boundaries and current 2.5D limits

Tile support is an exact integer number of 5-foot steps. Ordinary support has no
slope axis; stairs and ramps require one. Ordinary same-height walking is allowed
subject to blockers. Different-height walking requires a cardinal edge, exactly
one step difference, matching stairs/ramp kinds on both supports and a compatible
slope axis. Nonflying diagonal movement requires equal endpoint heights and an
allowed cardinal bridge route. Flying may cross height differences using its
mode's occupancy/edge rules and support-distance cost. Connector transfer is an
explicit separate authorized route.

Distance must be named accurately: `grid_distance_feet` floors Euclidean XY
distance in cells then multiplies by 5. `support_distance_feet` is the maximum of
that XY result and vertical difference rounded upward to 5 feet. It is neither
Chebyshev XY nor Euclidean 3D nor the presentation isometric projectile metric.
`Senses.get_feet_distance` currently remains XY only.

Object placement is owned by one exact Tile and either its center or one explicit
boundary side. Placement carries Tile UUID, position, base/top height, orientation
and occupancy policy. Bands use half-open `[base, top)` ranges; one band can hold
many object references but only one occupying object. Incident Tiles can each own
a separate object on their side of the same geometric edge. A `WorldEdgeView` is
derived from both incident supports and their ordered exit/entry contributions;
it is not another stored authoritative edge.

Walking tests vertical interval overlap with boundary structures. Current optical
and physical propagation boundary policies are XY channel blocking, not general
height-aware 3D rays; nonwalking movement blocking is also not a generic flying
body collision volume. Do not infer stacked floors, creature vertical bodies or
projectile collision from art or from object-band storage.

Sources: [Tile support](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_tiles.py:115),
[progressive edges](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/world_edges.py:1),
[transition](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py:1681),
[geometry distance](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/geometry.py:7),
[support distance](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/elevation.py:24),
[placement](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py:2201),
[boundary interval reduction](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py:1629),
[derived edge](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py:2893).

### 11. Structural authoring has explicit limited mutation boundaries

`world_authoring` validates known invalid requests before declaring a
WorldModified root, opens its ordinary vetoable lifecycle, invokes existing
owners, then completes with detached before/after state. Gameplay door, torch and
damage paths do not automatically become WorldModified commands. A semantic-only
Tile replacement may legitimately have a world root without fake mechanics work.
Unchanged requests return early. A source cursor interval may also include a
passive unrelated diagnostic after the root; that interval is delivery evidence,
not one indivisible animation lineage.

Full Tile replacement/removal rejects occupancy, direct conditions, independent
condition references, handlers, attached light sources, world objects, connector
supports and invalid/shared movement-value ownership. It authenticates and
releases only the removed Tile's finite movement-value graph. External GridMap
light contributions are carried onto replacement support and recomputed as
necessary. The narrow in-place elevation API is different: it retains Tile UUID
and rejects changed height with center objects or connector endpoints; it does
not apply the entire Tile-detachment guard. It verifies the Tile identity and
old support tuple are still current after interception before writing the tuple.

Object relocation proposes departure and arrival before replacing bands and the
placement record. If arrival is rejected, departure is explicitly canceled and
both location owners remain unchanged. World authoring then synchronizes the
BaseItem floor mirror. Removal unplaces the item without destroying its identity.
Known attached-condition position edits are blocked at the world-authoring
surface; orientation is permitted. Connector edits retain exact authored/runtime
identity, increment revision and validate their frozen support Tile UUIDs/heights
after interception. Old discovery commands then fail exact-current checks.

Base-light editing is a useful different lifecycle: DECLARATION and EXECUTION may
veto; the actual default-light commit precedes non-vetoable EFFECT and completion.
When another illumination/cap masks the change, the authored world root changes
but no fake resolved-light delta is emitted. Source-owned illumination and caps
are exact contributions; removal restores the other surviving sources.

Sources: [world root lifecycle](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/world_authoring.py:71),
[Tile replacement](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py:435),
[Tile detachment](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py:638),
[elevation mutation](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py:1109),
[object move](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py:2504),
[world item guards](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/world_authoring.py:165),
[base light commit](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py:3508),
[closed interval versus tree](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_world_modification.py:1844).

### 12. Consequences for later presentation integration

- Assemble complete existing lineages, keeping Step/entry/reaction/damage and
  zone/condition descendants intact. A capture interval or source cursor boundary
  is not a replacement render unit.
- Source reduction may advance independently of visual time. Preserve historical
  Step contacts, exact supports and sensory facts; no delayed live-world lookup.
- Do not move an actor on a proposed EFFECT alone. Canceled/uncommitted legs and
  successful legs with later entry damage are visibly different histories.
- Preserve identity, location, nonvisual contact and visible-cell distinctions.
  A hidden blocker can stop movement without authorizing its sprite.
- Reuse the existing condition/handler/lifetime owners. Rig names, frames, elapsed
  milliseconds and media readiness never enter those mechanics.
- Treat support height changes and exact object placement as current geometry
  facts. Camera projection and art pivots do not redefine engine distance or LOS.
- Check a concrete family's actual commit boundary before capturing it as a fact;
  the shared Event phase name alone is insufficient evidence.

### 13. Validation and explicit remaining gaps

A finite existing public contract selection passed: **22 passed, 114 deselected
in 2.05s** using `.venv/bin/python -m pytest -q` against the five files recorded in
coverage. It covers ordinary/forced movement, connector transfer and veto,
membership/anchor movement, failed replacement, removal veto, SpikeTrap, shared
Wet, OilBarrel, paired sensory movement, near-side/nonvisual contacts and selected
world mutation ordering. This is local behavioral evidence for those cases, not
a full engine regression run. One initial launch's session metadata was not
retained; only the second recorded run above is claimed.

Remaining source gaps: GridMap's complete pathfinding and optical/propagation ray
loops, all light-source bookkeeping variants, all Move discovery/validation and
Jump internals, each spell-specific forced movement producer, all environmental
item use actions, all public test fixtures/assertions and comprehensive failure
injection for nested relocation. The controller implementation behind the
existing movement continuation protocol is outside this spatial owner pass.
The spatial reviewer changed no gameplay code, tests or assets.

## Character content, grants and item ownership

Read-only study, 2026-09-08. Source is the **current working tree** of `codex/recovery-design`, whose HEAD is `16a6bfe141204cc46f336047da70e0cc9a4ceaa6`; HEAD alone does not represent the uncommitted Event registry and Pygame work. Exact reviewed ranges and current hashes are in [the merged coverage ledger](#source-coverage-and-evidence-ledger). The content reviewer changed no gameplay code or tests. This extends the [conditions chapter](#conditions-duration-and-dependent-ownership); source reading is not a claim to have reviewed every caller or every authored rule.

### 1. Actual ownership, rather than a new abstraction

Direct authoring is ordinary immutable definitions and semantic choices, followed by concrete functions that compose existing Entity components. Entity stores semantic origin/class state and private family receipts, while `origin_grants.py`, each class grant module and `progression.py` own installation/retirement orchestration. Numerical values remain in their real channels, resources in ActionEconomy, AC formula candidates and gear slots in Equipment, spell sources in Spellcasting, senses in Senses, and conditions in the existing BaseBlock graph. There is no reason to infer a generic contribution interpreter from the word “receipt.” [Semantic records](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/types/character_progression.py:79), [closed receipts](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/types/character_receipts.py:1), [Entity storage](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entity.py:547).

Each receipt is a frozen family-specific row of exact UUID handles, source keys and replacement information. Its matching cleanup function explicitly calls the corresponding component methods. Receipts are runtime installation bookkeeping; ordered `AppliedClassLevel` and `AppliedOriginState` are the saved semantic inputs. Stable UUID5 identities under an entity and family prefix allow selected owner reconstruction to preserve action/handler position and identity. This is not permission to serialize live conditions or handlers and replay their constructors. [Fighter sources](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/fighter_grants.py:36), [Fighter retirement](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/fighter_grants.py:634), [hydration](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/progression.py:477).

`feature_sources` combines independent sources as sets, so removing one provider does not erase a sibling provider. Other mechanisms have their own actual combination law: resource SUM/MAXIMUM, highest applicable AC formula with stable tie order, normal spell capacity replacement, shared learned-reaction sources, or source-keyed structural size requiring agreement. They are not interchangeable implementations of a newly invented universal rule.

### 2. Build validation and the first birth

`CharacterBuild` is the full direct input, including one body ID, ordered base scores and flexible bonuses, origin choices, ordered class levels, explicit item loadout, appearance, prepared spells and toggles. `resolve_character_build` performs pure validation before Entity creation: nonempty name, the currently supported humanoid body, levels 1–20, exact 27-point buy with scores 8–15, ordered +2/+1 bonuses, origin choices, multiclass prerequisites, class sequence/subclass/choice rules, ASI ceiling, known/prepared spell relationships, toggle support/ownership and known item IDs. These are **current authored rules**, not study-authored policies for all future D&D content. [Build and resolver](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/builds.py:79).

The class resolvers separate character level from resulting class level and distinguish first-class entry from later multiclass entry. They require exact semantic step IDs and authored choice order. Current implemented lines are Fighter/Champion, Barbarian/Berserker and Sorcerer/Draconic Bloodline. Sorcerer replacement validates an actually known old spell and a new supported spell not already known; learned cantrips, spells and Metamagic selections must not repeat. The resolvers return concrete values consumed by their family installers. This study read all three resolver bodies but not every static class catalog row. [Fighter resolver](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/class_definitions.py:791), [Barbarian](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/class_definitions.py:927), [Sorcerer](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/class_definitions.py:1068).

`create_character` then creates an unpublished Entity, sets its body and persistent choices, installs standard actions, applies origin at the final total level, applies initial class rows, builds the explicitly authored items, and uses `Entity.install_initial_items`. That owner validates the entire inventory/equipment arrangement before installation, requires registered same-owner unplaced items, and discards the unpublished aggregate on failure. It does not silently resolve authored slot collisions by displacing a starter item. Ordinary equip hooks still run, without gear Events. Portable torches in this explicit path are lit before `compose_entity` publishes one complete birth; deployment is separate. [Creator](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/builds.py:270), [initial items and birth](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entity.py:1191).

The first-class starting-equipment selection is a validated authored choice; the explicit `item_loadout` is what the creator installs. Reading the semantic package choice does not authorize a second automatic gear grant. Four premades call the same creator with ordinary builds; their entire presentation/loadout catalog was not individually reviewed here. The public selected tests executed all four creators and their single-birth/torch facts.

### 3. Origin composition and removal

The origin definitions are cold records of species, optional variant, background, exact ordered choices and resolved values. The current vocabulary is nine species, four variants and two backgrounds. `resolve_origin` validates variant parentage, ordered six scores, +2/+1 bonus shape, exact choice IDs/cardinality/allowed values, and rejects duplicate resolved languages/skills/tools. It resolves existing capabilities separately from numerical features. Its direct spell choice for the selected High Elf line is currently only Fire Bolt; that restriction is authored scope, not a generic spell-selection engine. [Definitions/resolution](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/origin_definitions.py:20), [resolver](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/origin_definitions.py:353).

`apply_origin` installs identity and semantic state, then records each actual source as it is added: ability modifiers, structural size, movement delta, languages/tools/weapons/skills, capabilities/features, darkvision, contextual saving-throw advantages, resistance, hit-point/critical modifiers, action templates, handlers and resource/spell sources. The saving-throw helper consumes typed cause context, including magical/effect-tag distinctions; it does not infer a spell from display text. On failure, its partial receipt removes recorded ownership before clearing semantic identity/state. This is compensation for recorded operations, not arbitrary exception atomicity for every callback in every imported owner. [Install](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/origin_grants.py:368), [cause-sensitive advantage](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/origin_grants.py:97).

Removal first validates ownership: referenced actions exist; special Darkness root binding matches; handlers are the same objects in both entity and queue indexes; source contributions and modifiers remain in their declared owners and registries. It drops only its exact active Darkness concentration slot, then retires its receipt rows and clears origin identity. Shared Hellish Rebuke ownership is removed by spell/source/handler triple; the actual handler is retired only when no learned source remains. Independent class Darkness concentration and sibling feature/capability sources survive. [Validation](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/origin_grants.py:780), [cleanup](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/origin_grants.py:886), [Darkness slot](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/origin_grants.py:968).

`reconcile_origin_total_level` updates only total-level-dependent origin owners: Dwarven Toughness amount, Dragonborn breath level, innate action caster levels and innate source metadata, plus Tiefling thresholds at 3 and 5. Crossing down below Darkness removes its owned slot before removing its template/use resource. The function mutates owners in sequence and updates the receipt at the end; it contains no universal internal rollback around all intermediate exceptions. Public progression supplies additional compensation for its own supported operation paths. [Reconciliation](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/origin_grants.py:1020).

### 4. Class grants, live child effects and replacement

Fighter installation records a stable hit-die row, proficiency sources, ASIs, feature sources, style modifiers/handlers, resources and attack multiplicity. An action such as Second Wind is a stored template whose level changes as later levels apply; each level does not blindly duplicate every action. Extra Attack has its own existing multiplicity grant and resource policy, separate from action-template identity. Cleanup validates all recorded owners before removing handlers/actions, resource and attack sources, modifiers from both channels and registries, proficiencies and hit dice. The partial receipt is also the installer’s exception cleanup. [Feature installation](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/fighter_grants.py:315), [ownership checks](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/fighter_grants.py:533), [apply/remove](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/fighter_grants.py:744).

Barbarian has actual replacement semantics: at Berserker level 3, Frenzy replaces the owned Rage template after removing its active Raging root. The receipt retains the displaced template UUID, list index and complete Rage configuration for restoration. Later level removal may first remove an active root if its currently applied configuration would no longer match the remaining features. Rage and Reckless roots are removed by exact UUID, and cleanup verifies the template’s owner field was released. Ordinary Raging removal may itself emit other rule consequences; its behavior is covered in the conditions study. The family remover validates ownership, but some handler retirement precedes per-action root removal; no all-family veto atomicity is inferred from Sorcerer’s different graph path. [Replacement](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/barbarian_grants.py:572), [receipt retirement](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/barbarian_grants.py:886), [configuration-sensitive removal](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/barbarian_grants.py:1185).

Sorcerer owns a class spellcasting source, learned ordinary spell templates, potentially shared reaction handlers, normal slot capacity, resource/recovery contributions, AC and affinity sources, plus exact action-owned Metamagic/affinity/wings/presence roots. Ordinary spell replacement preserves old semantic ID, UUID and ordering position. A removed reaction source can leave a disabled handler alive for later exact restoration; when another source still owns the reaction it remains shared. This distinction is intentional in the current implementation, not an unowned duplicate handler. [Spell/reaction install](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/sorcerer_grants.py:147), [replacement](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/sorcerer_grants.py:1110), [restoration](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/sorcerer_grants.py:652).

Sorcerer retirement gathers live condition roots from the exact stored actions. Draconic Presence explicitly records its remote immunity owner/condition UUID pairs; it does not scan all entities by effect name. It preflights the combined removal graph, cancels the prepared removals on a veto, then commits graph cleanup before retiring templates/capacity. Receipt cleanup refuses to proceed while those live roots remain. The existing full-lineage parent supplied by progression can own these nested removals. [Root inventory and graph removal](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/sorcerer_grants.py:565), [retirement](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/sorcerer_grants.py:1265).

### 5. Public progression completion and failure

`add_class_level` and `remove_last_class_level` are functions outside Entity; Entity remains the state/component composer. They use private DECLARATION/EXECUTION preflight through existing EventQueue validation, then call the actual family owners and publish concrete completed EntityLevelAdded/Removed facts. A plain successful add/remove need not publish intermediate public phases. Initial installation emits no level Events and hydration rebuilds runtime receipts from saved semantic state without Events. Direct player-body proficiency is reconciled from total character level; an ordinary creature carrying a class row retains its existing base proficiency behavior. [Public progression](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/progression.py:275).

The distinction between rollback and committed-child preservation is explicit. Without active child effects, a rejected remove completion can reinstall the family, restore resource amounts, toggle enabled states and local/global handler/action order, and check exact receipt/resource equality. If removal has already committed child facts, the owner retains a terminal removal fact on the accepted lineage even when observation fails; it does not pretend the removed conditions never happened. Existing tests prove both paths. Arbitrary exceptions earlier in family mutation are not thereby covered by the completion-publication `try` block. [Removal path](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/progression.py:365), [public failure/lineage tests](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/progression/test_direct_character_progression.py:336).

This is relevant to the integration study: fact publication/completion, an entire aggregate command returning, and complete causal presentation are distinct boundaries. The source already has owner-specific compensation and preservation rules. It does not support replacing them with a new universal finalizer or treating each level/condition subevent as an independent animation job.

### 6. Direct item identity and remaining migration seams

`BaseItem.item_id` is required and frozen; item instance UUID, semantic item ID, owner UUID, storage UUID, grid tile UUID and equipment slot have distinct meanings. `DIRECT_ITEM_BUILDERS` is an explicit immutable mapping from exact IDs to direct constructors; source contains an assertion of 147 entries. This study reviewed the construction code, not all 147 authored rule rows. Cold definitions and loadouts do not invoke a content materializer. The runtime builder module imports concrete item implementations, modifiers, spell implementations and Entity because it actually composes those owners. [Item identity](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/base_item.py:102), [direct table](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/items/authored_item_builders.py:580), [loadouts](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/items/item_loadouts.py:1).

Current cold item definitions **still contain** `visual_item_name`, `visual_variant_id` and `equipped_visual_policy`. Their docstrings saying “no renderer asset vocabulary” are stronger than their actual fields. They are independent of renderer imports, not free of historical presentation strings. The same strings are preserved in item presentation facts. This study neither removes them nor invents replacements. A fixed world object also owns real placement, blocking flags and optional health; sprites are not collision policy. The environment constructors distinguish edge walls/doors, movement-only cliffs, torches, and oil barrel spill/ignition via existing spatial owners. Their complete imported door/torch/container action implementations were not reread here. [Definition fields](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/items/authored_item_definitions.py:32), [world constructors](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/items/environment_item_builders.py:47).

Character direct identity and old creature `ContentRef` are mutually exclusive at `Entity.set_character_body_identity`. The generic character grant/materialization path is explicitly retired in the maintained architecture tests, while shared spell/condition behavior declarations and creature content machinery remain present. The migration is incomplete by family; do not describe every old catalog as active authority or every shared declaration as dead. `bind_runtime_behavior_child` still requires an installed/scoped gateway when an unbound child needs binding. A fresh public diagnostic built a campfire successfully but `campfire.get_use_actions(entity.uuid)` raised `Content system is not installed for provider-owned behavior`. Direct item construction therefore does not prove all of its runtime actions are usable without the remaining gateway. No gateway/server was restored. [Gateway boundary](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/content/runtime.py:248), [generic item discovery](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/base_item.py:814), [retirement checks](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/architecture/test_content_recovery_cr45_direct_characters.py:50).

### 7. Inventory movement and stack identity

Inventory owns membership/capacity/merge behavior. `can_add` validates total incoming weight and the number of new stacks after one compatible merge, before mutation. Compatibility here is the same `stack_id`, a different instance UUID, and available room; it is not a full comparison of every item property. An add detaches the old container/grid membership, merges into one existing stack, and stamps ownership/storage on the surviving inserted item. A fully merged incoming instance has cleared location and is removed from BaseBlock’s registry. `InventoryAddResult` is a frozen return record holding **live items**, not a passive event payload. [Inventory](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/inventory.py:20).

`remove_item` is only membership removal; its caller owns location cleanup. `transfer_item` removes from the source, attempts the target add, and reinserts on a normal capacity rejection. It does not publish aggregate item facts by itself or wrap every possible exception. Initial inventory validation rejects duplicate UUIDs/stack IDs, placed items, source mismatch, overlarge stacks and capacity failure; it deliberately does not merge authored starter rows. The full merge branch unregisters only the consumed BaseBlock, not a generic entire item-owned graph; whether unusual stackable items have additional handlers/conditions needing retirement was not executed here. [Initial/add/transfer](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/inventory.py:124).

Entity’s higher-level loot/drop/equip operations own aggregate movement and the subsequent ItemLocationState facts. A merge publishes the changed surviving stack first, then a MERGED fact with incoming count zero and exact survivor UUID. A drop requires an inventory item, removes membership, places it through GridMap and calls its drop hook before publishing FLOOR. A failed placement or later publication is not generally rolled back by this method. [Aggregate item operations](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entity.py:4091).

### 8. Equipment policy, hooks and the exact publication order

EquippableItem owns compatible/default/occupied slots and its concrete event family. Equipment owns overlap detection and displacement. Rings require an explicit side; melee two-handed weapons occupy a footprint containing both melee hands even though they are stored in the selected slot. Melee and ranged fields are parallel loadouts. Actor attack values are derived from the selected slot, item modifiers, equipment modifiers and ability components; the normalized discovery damage profiles are separate from live Damage objects used for rolling. Equipment also selects the highest applicable source-owned AC formula; its legacy singleton formula remains a compatibility candidate. [Slot contract](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/base_item.py:650), [conflicts/initial items](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/equipment.py:1392), [AC formulas](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/equipment.py:1224).

An equip operation preflights the proposed equip and every conflicting unequip before changing slots/hooks. Matching validators must be `validation_only`; attempted Event publication during preflight is rejected by the existing queue. Accepted declaration/execution versions are published without redispatch, displaced hooks run and fields clear, the new item reparents its values and equips, and then every transition emits EFFECT/COMPLETION. Current implementation uses finite slot-field mapping and some existing `getattr`/`setattr`/field traversal; that is an observed implementation detail, not a design endorsement or permission to add reflection to new code. [Preflight/commit](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/equipment.py:1537).

The whole **equipment loadout** is final when its EFFECT handlers run, so armor can correctly remove Mage Armor or Raging through their real handlers. The **Entity item membership** is not yet final: `Entity.equip_item` calls Equipment while the incoming item remains in inventory; only after Equipment returns does Entity remove that membership, publish the EQUIPMENT item fact, then store/drop displaced items and publish those facts. Low-level `unequip` deliberately leaves owner/storage fields for its caller. No action/bonus-action resource cost is charged by these owner methods. [Aggregate continuation](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entity.py:4268), [public final-loadout test](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_equipment_domain_ownership.py:387).

Cancellation before commit preserves slot and location state, as the public tests prove. Arbitrary exceptions after commit are different. A real stdin diagnostic installed an ordinary WEAPON_EQUIP/EFFECT handler that raises, then called `entity.equip_item` on a carried shortsword. The call raised; the shortsword remained in the equipment slot **and** inventory membership, `is_equipped=True`, storage pointed to Equipment, and only weapon-equip DECLARATION/EXECUTION/EFFECT were appended. No item-location fact or equip completion followed. This is a verified owner-level exception limit; the method name `equip_transaction` must not be read as a universal rollback guarantee.

Causality is also narrower than a whole aggregate transaction: each prepared equipment transition currently starts independently, and `Entity.equip_item`/`_store_or_drop_equipment_item` do not pass its equipment event into the subsequent item-location publications. Their source UUID records the actor but does not turn those facts into children of one shared equipment lineage. Destruction has an explicit cause for item-state publication, while the destruction entry through `Equipment.remove_contained_item(item_uuid)` does not receive that cause. Ordinary `Equipment.unequip(..., parent_event_uuid=...)` does accept a parent; the missing edge is specific to the destruction entry. These facts must be described accurately by a later integration contract; no event/subjectivity redesign was made here.

### 9. Item hooks, use costs, damage and destruction

Concrete item hooks install actual mechanics: the reviewed direct arcane staff changes spell attack bonus; the crown changes Charisma; heavy armor adds stealth disadvantage and a contextual movement penalty; the Assassin Dagger owns a damage-result handler. Unequip retires the recorded channel/handler handles. Some hooks guard against repeat installation, others assume equipment’s transition discipline. Direct item modifiers and handlers are runtime owners and not suitable for cold snapshots. [Concrete hooks](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/items/authored_item_builders.py:145).

`UsableItem.get_use_actions` copies stored live templates with new UUID/user/item identity and a cold item snapshot, filters finite charge affordability, and binds missing behavior. This is runtime action construction, not passive Event replay. A finite item cost has its own ItemChargeConsumptionEvent with before/after charges, stack counts and item-destroyed fact. It runs DECLARATION/EXECUTION/EFFECT interception, consumes through the item owner, and publishes completion. Unlimited charges are `-1`; a depleted consumable can move to the next stacked copy or destroy itself. The plain `consume_charge` method does not publish this child event. [Use and charge owner](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/base_item.py:758).

Item damage differs from Entity damage. `BaseItem.receive_damage` uses TakeDamage phases, honors cancellation, previews/applies Health damage, destroys at zero, then completes TakeDamage with final resolution/HP. It does not emit Entity’s DamageApplied family. Destruction calls the concrete `_on_destroy` before detachment, cleans lights and active conditions, removes container/grid membership, runs equipment unequip hooks through that container, publishes the aggregate DESTROYED item fact if a known owner handles it, and removes the item registry entry. An oil barrel may activate oil/ignite during its destruction hook; nested container behavior belongs to that concrete imported implementation. [Damage/destruction](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/base_item.py:462), [oil cause](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/items/environment_item_builders.py:47).

The generic destruction loop does not inspect each condition removal result, nor visibly retire every arbitrary object that any hypothetical item might own. This is a source limitation to investigate for a relevant concrete item, not an executed claim that all destruction leaks. Existing selected destruction tests prove shield slot/membership/AC removal and consumable destroyed-state ordering. For a final consumable, the DESTROYED snapshot count is zero even though the charge-event payload retains its separately defined stack count field; consumers must use each field’s actual contract.

### 10. Passive state and integration invariants

`ItemPresentationState` is frozen and contains values/tuples/enums plus the leaf boundary descriptor, rather than live Health/modifier/item objects. Concrete item subclasses extend its declared fields with weapon/armor/charge/light values. ItemLocationState wraps that item snapshot, exact membership/slot/merge identity, optional whole-world placement and aggregate AC after-value. FLOOR validates placement UUID and coordinate agreement; non-floor forbids a world placement. It does not validate every imaginable location-field combination. Publication builds private phases then registers only completion. [Cold item contract](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/item_types.py:44), [fact validation/publication](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/base_item.py:42).

Passive payloads are useful evidence but do not independently establish observer authorization. This study adds no subjectivity policy. It also does not turn equipment transitions, condition removals or item-charge facts into independent animation jobs: complete causal lineage remains the existing presentation unit. Exact owner after-values must be captured at their actual boundary, and a later Entity query is not equivalent to them. The current branch’s equipment stance is a live `active_weapon_set` assignment/reconciliation with no committed stance Event found in this owner; the archived overnight stance-fact implementation must not be assumed present. [Current stance](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/equipment.py:789).

### 11. Executed evidence and reproduction

HOW_TO_TEST.MD was read before checks. No tests were written. Exact commands are in the merged coverage/evidence ledger. Existing tests were run with bytecode and pytest cache disabled.

- Equipment domain ownership, equipment replication facts, and direct-character public progression: **25 passed in 1.91s**. Includes cancel-before-mutation, preflight publication guard, final-loadout reactive removal, membership/AC facts, merge/destruction, silent hydration, sibling ownership, completion-failure restoration and committed-child lineage preservation. The equipment-domain file was fully read; a passing test does not extend its proof to arbitrary hook failures.
- Selected direct builds and origins: **45 passed, 23 deselected in 2.94s**. Includes all ordinary premade construction, selected pure build validations, provisional collision/birth/light cleanup, all parameterized origin apply/remove cases, sibling preservation, level thresholds, exact Darkness cleanup versus sibling class concentration, and moved-modifier/foreign-root rejection. Excluded catalog-assertion and other behavior tests are not passing evidence for this study.
- Fresh-process campfire discovery: construction succeeds, public `get_use_actions` raises the absent provider gateway error described in §6. No installed content bootstrap or server closure was repaired.
- Fresh-process committed equipment handler failure: exception, dual inventory/equipment membership and three stored weapon-equip versions as described in §8.

Reproduce the last two probes using `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -`, importing `Entity`, `reset_engine_runtime`, `build_authored_item`, `build_campfire`, `WeaponSlot` and existing EventHandler/EventQueue/Trigger/phase/type types. Start `reset_engine_runtime(grid_size=(3, 3))`; create `e=Entity.create(uuid4())`; build `weapon.shortsword` for `e.uuid`, and `e.loot_item(item)`. Add an ordinary handler for WEAPON_EQUIP/EFFECT/source=e.uuid whose processor raises `RuntimeError("diagnostic committed equipment effect failure")`. Save the queue cursor, call `e.equip_item(item.uuid, WeaponSlot.MELEE_MAIN)` and catch only that RuntimeError to inspect slot identity, inventory membership, `item.is_equipped`, `stored_in_uuid` and `iter_events_since(cursor)`. Reset again; create a fresh Entity, build its campfire, call `get_use_actions(e.uuid)` and retain the raised error. These calls and immediate observations produced the recorded results; no private mutation or mock was used.

### 12. Limits and corrections to prior assumptions

The full inventory/base-item/equipment mechanisms, direct item builder module, build/progression, origin definitions/grants, Fighter grant module and semantic/receipt types were read. Sorcerer and Barbarian lifecycle/install/remove/active-root/replacement bodies were read deeply, with explicitly omitted import/constants/proficiency/helper ranges in coverage. This is not an exhaustive review of all authored class rules, spell behavior, item subclasses, monsters, persistent storage encoders, server consumers, every registry payload or every caller of an owner. Other chapters record Entity birth/cleanup/reception and the shared runtime/event/spatial mechanisms; only their relevant junctions were reread here.

The important corrections are descriptive: direct content is a partial migration; family receipts are concrete owner bookkeeping; equipment cancellation safety does not imply arbitrary exception rollback; item and Entity damage publish different families; gear completion can precede aggregate membership completion; completed facts can intentionally survive observation errors after child effects commit. None of these justifies a new manager, bus, contribution framework, universal transaction layer or gameplay/observer policy. They constrain any later proposal to respect existing owners and to name the actual failure and causal boundaries.

## Presentation, NeuroStudio and independent time

Source study, 2026-09-08. This chapter compares current presentation owners
with the pinned NeuroClient reference. No production, tests, authored JSON, or assets changed in this study.

### Scope and revision labels

- **Current D&D working tree:** `codex/recovery-design`, HEAD
  `16a6bfe141204cc46f336047da70e0cc9a4ceaa6`, including the current uncommitted
  recovery files and Event registry cut. HEAD alone does not describe these files.
- **NeuroClient reference:** `/home/tommaso/Dev/NeuroClient/app`, clean checkout
  `d274f2d62ca9c1c5ed62a77841cacf6cc0347491`. Source can explain preserved intent
  without making the old server/client stack the current architecture.
- **Historical matching SDK:** D&D commit
  `74cc1f9e3d2d5524e3758ae3b7e73f7b8fd7b89e`, read with
  `git show 74cc1f9:sdk/typescript/src/subjectiveJournal.ts`. It supplies the
  preview/token API imported by the above NeuroClient source.
- **Installed SDK mismatch:** NeuroClient's package.json:160 points at this
  repository's SDK. Its installed symlink resolves to
  `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/sdk/typescript`. Current
  subjectiveJournal.ts:163 accepts a numeric cursor at commit and has no
  previewPresentationFrame. Do not claim that the historical client and the
  current linked SDK execute together unchanged. The offline materializer and
  timing oracle deliberately avoid that runtime dependency.

The accompanying [the merged coverage ledger](#source-coverage-and-evidence-ledger) records actual source ranges,
hashes, historical revisions, and gaps. Function-name searches are not counted
as full source reads. The map draw body and its projection/asset implementations
were not fully reread in this pass; this note examines their
presentation input and the detached actor/effect drawer.

### 1. What is already present in the current Python code

#### A. The map demo's capture boundary is finite and honest about its scope

[game/presentation.py:40](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/presentation.py:40)
defines primitive ObjectiveRow identities for each stored version, including
exact Event UUID, lineage UUID, parent references, phase and turn execution ID.
These rows are diagnostics, not animation instructions. SubjectiveTextRow is
already projected text. IntervalEnvelope also contains selected detached Events,
a generation and contiguous source range, plus explicit battlefield/door/torch
fixture identities. A source interval is transport/capture grouping; it is not
the complete-lineage animation unit required by the recovery plan.

[capture_interval:197](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/presentation.py:197)
checks generation and contiguous indices, retains primitive objective rows,
deep-copies only admitted completed Events, and independently projects available
combat-log entries. Admission is exact-type and deliberately narrow:
WorldInitialized for the selected battlefield; floor ItemLocationState for the
standing torch; OBJECT_CHANGED SpatialChange for the selected door; and the
selected observer's SensoryUpdate after its seed cursor.

[_safe_to_detach:153](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/presentation.py:153)
only checks context, combat_log and effective handler presentations. Together
with the finite family whitelist, this is sufficient for the current demo's
specific copies. It is not proof that arbitrary ordinary Event payloads are
passive. A frozen envelope also does not recursively freeze nested copied data.
The current test proves those selected copies survive engine reset; it does not
authorize a generic deep-copy archive for every combat Event.

#### B. Current reduction has one mutable presentation target

[PresentationTarget:91](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/presentation.py:91)
owns map indexes, selected door/torch values, SensesSnapshot and a reducer cursor.
It has no general actor appearance/vitals/equipment store, committed historical
base, active candidate, or complete-lineage pending assembly.

[reduce_interval:304](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/presentation.py:304)
checks generation, observer and cursor continuity; updates the selected map
state; reuses the canonical passive sensory reducer; and advances its cursor.
It mutates the existing target progressively. Reusing the meaning for two time
positions therefore requires owned successors or commit-after-validation
candidate values, rather than allowing a later failure to leave half-applied
state or permitting both positions to alias one mutable object.

[settle_dispositions:381](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/presentation.py:381)
requires disjoint represented/not-disclosed sets exactly covering pending
display obligations. It does not reject every pre-existing UNSUPPORTED row.
The map demo intentionally retains unsupported diagnostic rows; its successful
interval terminal is not proof that an unsupported required combat consequence
may advance the future complete-lineage display cursor.

#### C. Same-thread asynchronous intake exists, but R still waits for display

[game/app.py:1135](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/app.py:1135)
creates the authored battlefield, observer, door and torch and captures the
fixed startup/open/close scenario. OpenDoorAction.apply and CloseDoorAction.apply
are real mechanics, but this is three scripted operations, not general action
discovery or playable combat.

[_produce_intervals:1231](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/app.py:1231)
puts each captured interval into an asyncio.Queue and yields with sleep(0).
Thus the engine can produce ahead while the display holds an earlier scene.
Queue size three works because there are exactly three scripted outputs. It is
not a general capacity guarantee before starting autonomous mechanics: the
producer currently uses put_nowait after the mechanics have already occurred.

[_run:1363](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/app.py:1363)
yields to intake, but it only dequeues and calls reduce_interval when
`current is None`. Drawing immediately consumes that same target. Therefore
E can advance ahead, while R remains gated by display and its demo hold. This
is the precise missing outer connection, not evidence that another inner
animation scheduler or thread is needed.

The loop publishes with pygame.display.flip before classifying display sources
and moving D to the interval end. It subsequently waits display_hold_seconds
and emits a terminal. FrameEvidence compares calculated and actual draw records
for the selected world/door/torch obligations. It does not yet prove complete
actor state convergence at an authored consequence anchor.

#### D. The existing inner timeline is already renderer-independent

[game/animation.py:23](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation.py:23)
has frozen ActorContact, CastInput, timeline/anchor/interval and sample data.
compile_cast binds a selected imported recipe to supplied historical values;
sample_cast samples at an absolute elapsed time; crossed_anchors reports
boundaries in `(previous, current]`. There are no Pygame calls, live Entity
lookups, sleeps, per-actor event loops or animation controller objects.

The current input is still a hand-built single-cast fixture: it requires string
root_event_uuid/application_id and one caster/target. It is not ordinary Event
capture or a complete-lineage/application binder. Do not fabricate engine
application IDs to satisfy this fixture, and do not bucket repeated A/B/A
applications by target when extending the existing input boundary.

[compile_cast:323](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation.py:323)
explicitly admits a bounded straight sprite projectile family. Missing complete
materialized fields, required resources and unsupported execution choices fail
before sampling. Imported area/condition/media data remains preserved in the
loader; preservation is not a claim of executable support.

The sample composes caster body, prepare/travel/impact, target hit or explicit
death, flash, number and optional recovery using authored anchors. Release does
not require the caster body to finish; caster completion and delivery/reaction
join before recovery. Damage presence is separate from numeric disclosure;
hidden number does not suppress the HP anchor. Life comes from the supplied
canonical LifeState fact, not HP arithmetic. DYING and STABLE deliberately lack
this death-only presentation. Normal HP here is not the complete actor vital
contract: retained temporary HP and other state still need the outer reducer.

Same elapsed produces the same sample; pause is a repeated time value; large
deltas cross existing anchors without shifting the authored schedule. The
explicit correction to original callback-hitch behavior is already documented
and tested. Do not replace absolute sampling with sleeps or enqueue-time delays.

#### E. Rig/resource ownership is already data, not a second executor

[game/animation_types.py:398](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation_types.py:398)
defines BodyClip (semantic source name, frames, fps, category-to-sheet bindings)
and BodyRig (cell dimensions, support-relative origin, facing rows, slot order,
slot capabilities and semantic clips). Loader derives the root binding from
the unchanged imported tables; explicit local rig_files add packaged bindings.
Both actors resolve their timing and drawing through the same metadata owner.

[game/animation_data.py:68](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation_data.py:68)
resolves original URLs as keys to contained existing local resources, never as
network instructions. Source absolute paths are provenance, not readiness
requirements. Bundle maps are read-only; selected models validate source field
names; unused context inventory remains exact source JSON. No Bun/NeuroClient
runtime is required to read the resulting game artifacts.

[game/animation_draw.py:66](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation_draw.py:66)
preloads selected actor slots/clips and exactly the four reachable quarter-turn
rows. It validates dimensions/category capabilities and keeps cropped rows,
not the entire source sheets. Required selected gear is checked before clock
start. draw_animation consumes supplied samples and performs no frame-time
image loading or clock advancement. Public tests remove source links after
preload and seek through phases to prove this boundary.

#### F. The preview proves authored animation, not game integration

[game/animation_preview.py:49](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation_preview.py:49)
constructs Fire Bolt contacts and fixed appearance tuples, with optional Goblin
target, explicit DEAD outcome, recovery, height and camera variations. Its
validated source JSON mutations are preview inputs, not persistent recipe edits.
Media/fonts load before the loop's clock. Whole playback rate scales the single
elapsed clock; cast speed changes the authored body field. Pause/seek does not
accumulate catch-up time. Camera rotation changes projection, never timing.

The current game.app imports no animation modules. The detached preview
explicitly says no live game runs. Its stage has transparent support markers;
it does not claim map terrain occlusion.

### 2. NeuroClient's preserved runtime design

#### Intake and presentation are separate progress processes

[eventIngestion.ts:210](/home/tommaso/Dev/NeuroClient/app/src/engine/eventIngestion.ts:210)
starts one async drain promise, returns the same running promise to additional
wake-ups, and re-wakes when pending heads remain. wake at 240 starts that work
without turning transport acceptance into an animation barrier.

[projectSubjectiveReplicationUpdate:804](/home/tommaso/Dev/NeuroClient/app/src/engine/eventIngestion.ts:804)
notes accepted reset safety synchronously, updates metadata, and wakes for frame
delivery. It does not await the visual transaction. The drain loop at 274
acquires exactly one head. Later intake can be accepted while this head awaits
its authored visual outcome.

In **historical SDK 74cc1f9**, subjectiveJournal.ts:440–486 validates/freeze-copies
the accepted frame, applies the common world reducer to authoritative state,
and retains the frozen frame in the pending queue. At 229–282,
previewPresentationFrame applies that same reducer to the committed
presentation base plus exactly the next frame. It freezes the candidate and
issues a token tied to the exact base/head/incarnation. Commit at 285–305
rechecks those identities, installs that candidate once and advances the queue.
At 534–546, independent eligible combat-log delivery is retained while a token
is active so it cannot replace that exact presentation base object underneath
the active head.

This is the useful two-state design. The Python ECS recovery needs the ownership
and invariants, not the SDK class, transport protocol, token object hierarchy,
or a replacement server.

#### Existing actors remain historical through their active visual work

[consumeNormalHead:309](/home/tommaso/Dev/NeuroClient/app/src/engine/eventIngestion.ts:309)
builds from the immutable candidate, maps/stages required entities, enqueues one
causal transaction, awaits its result, checks the rendered scene against that
candidate, rechecks the head, then commits. Failures have an explicit blocked
recovery path rather than falsely acknowledging success.

[stateSync.ts:47](/home/tommaso/Dev/NeuroClient/app/src/engine/stateSync.ts:47)
projects only committed presentation state. At 200–260 it stages newly admitted
actors/loadouts needed to render this frame, while existing actors retain
pre-frame position, vitals and appearance. New identity acquisition is a real
boundary, not permission to replace every existing actor from latest engine
state. Current Python actor acquisition still needs retained actor/item facts
from their existing owners; fixed APPEARANCE is only the reference fixture.

#### There is one causal head, with structured concurrent children

[clipQueue.ts:225](/home/tommaso/Dev/NeuroClient/app/src/render/clipQueue.ts:225)
rejects causal enqueue while a causal transaction is active. There is no second
pending causal backlog here: the journal owns pending heads. Its update method
does not dequeue another schedule; execution starts on accepted enqueue.
At 491–539, groups run sequentially, the intents inside one group run
concurrently, and dispatchChildren concurrently joins declared child intents.
Decorative work is separate and generation-scoped; it does not become a second
causal acknowledgement owner.

[subjectivePresentationMapper.ts:819](/home/tommaso/Dev/NeuroClient/app/src/render/subjectivePresentationMapper.ts:819)
maps graph roots to top-level groups and folds children into their parent's
contact/release/effect boundaries. This recovers why damage should be a cast's
child rather than a subsequent generic time slice.

**Do not conflate the old transport frame with the new engine lineage.** The old
mapper's transaction rootLineage is synthesized from subjective stream,
generation, perspective epoch and observation cursor (238–248), and one frame
can contain several cue roots (258–316). The current user/plan explicitly
requires complete existing Event lineages as rendering units. Recover the
causal graph and single-head/two-state behavior; do not transplant the old
frame-derived identity, cue taxonomy, or manufacture jobs for delivery chunks.

### 3. Reuse the authoring format and runtime timing evidence

[validation.ts:90](/home/tommaso/Dev/NeuroClient/app/src/render/spellAuthoring/validation.ts:90)
normalizes catalog/assets, validates saved Studio drafts, and materializes each
catalog entry by merging the generated baseline with its exact saved draft.
The Python importer already executes this original TypeScript owner offline.
There is no need to reimplement those defaults in Python.

[serialize.ts:12](/home/tommaso/Dev/NeuroClient/app/src/ui/spellStudio/serialize.ts:12)
persists exact definitionRef, cast/projectile/area/damage/condition data. Its
damage serializer rejects scenario-specific target rows that disagree: a saved
recipe is reusable presentation data, not captured backend scenario outcome.
The engine still owns target selection, damage, life and allowed disclosure.

[phaseGraph.ts:19](/home/tommaso/Dev/NeuroClient/app/src/render/spellAuthoring/phaseGraph.ts:19)
keeps disabled optional phases present. The graph explicitly relates prepare,
travel, impact, disclosed effects, optional area/explosion and recovery.
[CastClip.ts:70](/home/tommaso/Dev/NeuroClient/app/src/render/clips/CastClip.ts:70)
registers authored body-frame callbacks, joins preparation before delivery,
awaits both body completion and the release/delivery chain, restores equipment,
and then runs recovery. These are the selected Python sampler's source rules.

[StudioTransportController.ts:69](/home/tommaso/Dev/NeuroClient/app/src/ui/studio/StudioTransportController.ts:69)
returns one scaled delta, or zero while paused. SpellStudioPreview.ts:381–386
passes that same delta to host and actors. Its seek at 2246–2302 rebuilds the
seed and pumps forward. The pure Python sampler already supports direct seek;
copying the editor's mutable-scene replay machinery would add unnecessary work.

The original runtime also has distinct realtime and supplied-frame clock
adapters, [presentationRuntimeHost.ts:152](/home/tommaso/Dev/NeuroClient/app/src/render/presentationRuntimeHost.ts:152).
The supplied clock measures waits from its provided nowMs and delivered frame
callbacks, making the controlled oracle possible. Same-thread async Python can
preserve that independence with supplied elapsed values; it need not recover
Pixi, browser timers or old threading.

The editor overview is not the timing oracle. timelineBuild.ts:44/1314 uses
15/FPS for a body, whereas actual source execution ends at the last index14
boundary. Its recovery estimate also uses 15/FPS (311–313). Its impactByTargetUuid
summary at 1180–1188 chooses the earliest arrival for each target; damage rows
at 273–280 use that summary, losing later repeated-target application timing.
Keep the format and causal phase hierarchy; do not turn these display estimates
into execution rules.

[devtools/import_neuroclient_presentation.py:145](/mnt/c/users/tommaso/documents/dev/dnd_engine/devtools/import_neuroclient_presentation.py:145)
imports the original validation/materializer and rig constants from the pinned
checkout through native Bun only while exporting. It checks exact selected
catalog refs/source bytes and enumerated outputs. The current imported set has
three materialized drafts, original source inventory, root tables and 47 PNGs
for the reference media. [Data README](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/data/neuroclient/README.md)
explicitly distinguishes imported records from supported runtime execution.

The stored [timing oracle](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/game/fixtures/neuroclient_animation_timing.json)
records actual original clip execution using the frame-driven clock with a
1 ms pump. Its provenance lists substituted diagnostics, inert texture/font
rendering, supplied frame delivery and inert watchdogs. It is not an Event
mapper, old SDK, GPU pixel or deadline/reset proof. Current public tests bound
each ideal/recorded difference by counted serial 1 ms wakeups, rather than an
arbitrarily broad tolerance. Large initial callback-hitch behavior is a named
source correction, not silently changed expected data.

### 4. The minimum missing connection, expressed as ownership constraints

This is a description of the missing existing-design connection, not a new
implementation plan or authorization to edit files.

1. **Capture facts and retain complete causality.** The selected ordinary Event
   families need valid detached values under the existing observer rules, plus
   independent standalone log ranges. Capture at factual boundaries; assemble
   complete lineages using their existing lifecycle and exact identities.
   Source callback batches/operation ranges help delivery integrity but do not
   replace the lineage as the rendering unit. The spatial study explains why
   precompletion sensory children and later life facts must remain ordered facts.
2. **Maintain two reduction positions.** Latest target-at-R may ingest later
   complete facts while committed presentation base and its next candidate stay
   historical. One reduction meaning serves both. Keep one pending lineage queue
   plus incomplete assembly and one active candidate, rather than world snapshots
   for every pending cast or another backlog in the sampler.
3. **Bind the existing sampler from historical values.** Resolve authored content
   identity, actor/gear appearance, rig and contact/support from the retained head
   state; preserve explicit root/application/child identities. No entity-name
   inference, sprite paths in mechanics, or backend animation timing fields.
4. **Use one visual clock in the same thread.** Perform mechanics/capture without
   yielding inside a partially committed operation. Yield between admitted work,
   so intake/reduction and Pygame event/draw pumping both progress. Preload before
   starting the current head clock. Advance elapsed only by supplied frame delta
   and whole-playback speed; paused time contributes zero. Later queue depth or
   engine turn count never rescales authored playback.
5. **Publish and settle the correct state.** Apply permitted state consequences at
   their authored anchors, render the required terminal candidate, then advance
   D. Compare to that candidate, not latest R. Do not settle required unsupported
   consequences as decoration or mistake a sampled complete flag for a published
   frame. Failure must preserve honest mechanical outcomes and stop false visual
   acknowledgement; missing media cannot roll engine state back.
6. **Reuse the existing raised-map projection/painter.** The sampler freezes
   canonical contacts and elevations. project_projectile only changes the viewed
   point/facing/rotation; it retains phase/frame/progress and fixed duration.
   Drawing must contribute actors/effects to the existing map painter, rather
   than treating a separately sorted transparent diagnostic stage as terrain
   occlusion. Historical support must come from the current head, not live GridMap.

Capacity must cover incomplete plus pending retained work before an autonomous
operation starts. Async alone does not bound memory or guarantee fairness if one
operation blocks the event loop for too long. This study introduces no worker
threads or machinery for hypothetical long operations; a real bounded command
probe should establish the missing application's behavior.

### 5. Concrete self-validation and remaining gaps

Ran the existing finite public selection: **11 passed, 60 deselected in 7.06s**.
It covers all seven authored boundary cases (normal speeds, damage speed, lethal,
near, recovery and disabled number), pause/direct seek/large delta, recovery tail,
map replay after reset, and incremental same-thread demo production. Exact
command and runtime are in the merged coverage/evidence ledger. No tests changed; no arbitrary sleeps, browser,
source TS execution, GPU or extra generated assets were needed.

Already-read public draw tests cover preload failures, drawing after source-link
removal and repeated-seek pixel equality. They were not rerun in this study;
this note does not conflate earlier P2/G5 proof with a new test run.

Missing integration is not covered by those 11 passes: R advancing while a first
authored head remains active; active gear/contact/HP stability under a later
head; causal lineage assembly independent of delivery chunking; repeated-target
applications; ordinary hidden-source Event representation; temporary HP;
reaction/cancellation/operation-failure capture; required terminal map publication;
queue saturation; or joint raised-map occlusion. These are connecting-boundary
questions, not reasons to recreate the recipes, rig maps or pure sampler.

This pass did not re-read the whole legacy server mapper, all NeuroClient scene
controllers, all authoring condition/area fields, the full AnimatedEntity/FSM,
or all current map rendering helpers. Their existence is not a readiness claim.
Historical source was used only for the concrete preview/commit SDK mismatch.

## Cross-owner conclusions and the next-change guard

The design problem is the connection between established systems: the engine's causal, intercepted and observer-dependent mechanics, and NeuroStudio's authored historical playback. The detailed reread strengthens the user's original framing. It does not justify a replacement event system, rules implementation, timeline language or controller hierarchy.

### Preserve these distinctions

| Existing concept | What it establishes | What it does not establish |
| --- | --- | --- |
| Event UUID | One recorded version and its dispatch/capture position | A whole action, immutable payload or completed lineage |
| Lineage UUID and parent/child links | Existing logical causal structure across versions | Automatic recursive closure enforced by EventQueue |
| Explicit reaction trigger links | Causality for reactions that may have a separate root | Permission to drop that reaction because parent_event is None |
| Application UUID/index | Distinct ordered recipient application, including repeated recipients | A replacement cast identity or a second animation queue |
| EFFECT | A producer-specific interception/publication boundary | A universal commit point shared by every event family |
| COMPLETION | That producer's completed version and associated bookkeeping | Success of an enclosing action, universal cleanup, or an independent render job |
| Callback batch/source interval | Delivered source order and accounting | Atomic transaction, success, complete-lineage admission, or authored playback duration |
| Turn execution UUID | Existing turn-relative rule scope and frequency fences | Animation time or an action lineage |
| Condition/modifier/grant UUID | Exact live ownership and independent retirement | A display label or interchangeable status name |
| Recorded sensory/contact/log grants | Existing observer knowledge at its factual boundary | A new policy to infer from whichever entities are visible now |
| Deep copy / frozen outer record | The particular copy/validation behavior implemented there | Automatic passivity of nested conditions, values, dice, registries or callables |

### Worked causal implications

The condition study's real damage diagnostic is especially useful as a reference. HP changes first. DamageApplied/EFFECT then runs concentration's handler; that handler can complete linked child removal and root concentration removal. DamageApplied completes with those effects gone. A later Death/LifeStateChange sequence can then establish DEAD. The **complete enclosing lineage**, including its real children and reaction relationships, supplies the presentation history. Choosing one intermediate after-value as the whole outcome would omit existing work.

Movement has the same need for producer-specific understanding. Move can accept a Step, publish committed departure/arrival facts, run entry effects and sensory reduction, and only then complete the enclosing movement. Jump consumes a leg's movement at a different point from Move. Connector transfer has authored endpoint/cost/provocation authority. Shove has forced movement and entry effects. A general "position changed" callback cannot replace these distinctions.

Condition removal also has a broader owner than one Event. A root may prepare removal of linked effects across entities and spatial footprints; a dependent veto keeps that graph alive. Accepted cleanup retires exact modifiers/handlers/actions and can create further effects. A duration reaching zero, a CANCEL flag or an API's boolean result must be interpreted through that owner's actual contract.

### Where presentation work remains

The current Event registry correction answers where Event versions are registered. It does not detach nested runtime payloads or implement the ordinary subjective Event input needed by gameplay animation. Existing sensory and combat-log projection rules supply established knowledge semantics; they do not, by themselves, provide the still-missing ordinary Event-to-authored-animation connection. The passive representation gap recorded in RECOVERY_PLAN remains a specific unresolved integration question, not a reopened subjectivity decision.

The current authored Python sampler proves reuse of selected NeuroStudio data and rig mappings. The Pygame map demonstration separately proves world/light/door presentation. They are not yet one game action pipeline. In particular, current game.app defers its reduction while its interval is active. NeuroClient's inspected design maintains independently advancing intake/reduction and a historical presentation base; it previews a complete head, plays the authored timeline, converges, then commits that head. Its visual queue does not introduce a second backlog behind the Event/reduction owner.

The next implementation proposal must therefore connect **one existing public action and its complete lineage** to the reused authored sampler while preserving its observer facts, historical actor/gear/support data and independent playback time. It must account for interception, real child/reaction structure and any relevant late-child limitation before calling the example complete. This is a design conclusion from the study, not authorization to start that implementation during the requested reading pass.

### A small guard against repeating this mistake

For the next bounded change, add one short decision/evidence entry to RECOVERY_PLAN rather than creating another framework or document series. It must name:

1. The user requirement and current source owners being connected; identify existing reusable JSON/types/functions before proposing any new abstraction.
2. The complete causal trace: public caller, validation/cost/interception, actual mutation, children/reactions, cleanup and terminal behavior. Include the relevant cancellation/failure path and owner-specific exceptions to the common path.
3. The historical facts and existing observer rules consumed by presentation, and the separation between advancing reduction and active playback. State which nested data remains live and which admitted facts are detached.
4. The smallest proposed edit, its consumers and import direction, plus the public behavior that will validate it under HOW_TO_TEST.MD. A fixture-only animation cannot certify a real action integration.
5. **Anti-slop reviewer:** challenge unsupported generalization, duplicate systems, scope creep, live-state rereads and tests that merely mirror the new code. **Anti-OOP reviewer:** check data/system ownership, exact contribution cleanup, composition and the import DAG; reject new actor/effect/manager hierarchies that duplicate current owners.

When any of these facts is missing, return to the named source and extend the corresponding note before patching. Do not ask the user to restate already-established subjectivity or timeline design. Do not turn a newly found bug into an unsolicited repair campaign. Current implementation remains paused; confirmed defects and source concerns below are evidence for choosing a later bounded cut.

### Findings are not a repair backlog by default

The chapter evidence separates three kinds of result:

- **Executed owner diagnostics:** selected cancellation probes leave condition state behind; one expiration API can report true while its condition remains active. Interpret each against the actual owner contract and caller before calling it a gameplay defect. The injected Fire Bolt veto claim was withdrawn; see the later reassessment. These observations are not an automatic repair list.
- **Executed primitive contracts/limits:** mutable parent bookkeeping after a late child, callback timing, repeated preview application, changing contextual evaluation, resource capacity transitions and registry cleanup differences. These establish API assumptions; they do not prove an authored rule misuses that primitive.
- **Source-only concerns:** StructuredAction's default revalidation, connector refund after a committed publication exception, selected concentration cancellation paths, Jump's post-completion cost ordering, and other named ownership cases. These require a relevant public trace before being called demonstrated gameplay failures.

None was fixed in this pass. Current signed advantage/resistance/constraint semantics and the existing subjective disclosure rules were studied as compatibility behavior, not silently replaced with a preferred ruleset.

## Source coverage and evidence ledger

This is a **detailed core-owner study**, not a claim that every authored spell, monster, AI module, legacy server endpoint or rendering line has been audited. Whole-file source reading, selected-range reading, test execution, diagnostics and historical reference are separate evidence levels. The following table merges actual detailed reads by the root and three assigned reviewers; a module absent from it has no whole-file-read claim from this pass.

Ranges are inclusive. `Full` means the complete source file was read, potentially across reviewers; it does not certify all callers or arbitrary rule combinations. The 12-character SHA-256 prefix identifies the actual file bytes reviewed. Compare with `sha256sum PATH` before relying on unchanged-source claims. Documentation and JSON/asset provenance are recorded in their owner chapters rather than counted as Python implementation reads.

### Current production and import tools
| File | Detailed source read / total lines | SHA-256 prefix |
| --- | --- | --- |
| [devtools/import_neuroclient_presentation.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/devtools/import_neuroclient_presentation.py) | 1–112, 145–189, 236–284 / 324 | `fca342664950` |
| [dnd/action_dispatch.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/action_dispatch.py) | Full / 97 | `f48ed016fe67` |
| [dnd/actions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/actions.py) | 183–687, 689–998, 1088–1444, 1447–1480, 1670–2236, 2913–3360, 3580–3809, 3813–3910, 4228–4840 / 5090 | `7f925067a8e6` |
| [dnd/actions_functional.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/actions_functional.py) | Full / 768 | `6d708b24969d` |
| [dnd/blocks/action_economy.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/action_economy.py) | Full / 1228 | `4a0e31dcf626` |
| [dnd/blocks/base_item.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/base_item.py) | Full / 945 | `393047914681` |
| [dnd/blocks/equipment.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/equipment.py) | Full / 1768 | `a3e5a06243a2` |
| [dnd/blocks/health.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/health.py) | Full / 811 | `3c619b0563c5` |
| [dnd/blocks/inventory.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/inventory.py) | Full / 277 | `d8c7eb6a0aa7` |
| [dnd/blocks/sensory.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/blocks/sensory.py) | Full / 1206 | `3533eb23ae11` |
| [dnd/classes/barbarian.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/classes/barbarian.py) | 70–335 / 1598 | `2f1e24951e0e` |
| [dnd/classes/rage.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/classes/rage.py) | 77–508 / 1257 | `b1dbcde4f925` |
| [dnd/classes/sorcerer.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/classes/sorcerer.py) | 940–1215 / 1573 | `861485c22d17` |
| [dnd/conditions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/conditions.py) | Full / 2466 | `04ec246b5b15` |
| [dnd/content/characters/__init__.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/__init__.py) | Full / 2 | `e89211bb9c73` |
| [dnd/content/characters/barbarian_grants.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/barbarian_grants.py) | 61–188, 290–1235 / 1235 | `0578ef8aaa43` |
| [dnd/content/characters/builds.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/builds.py) | Full / 346 | `35e3c145337a` |
| [dnd/content/characters/class_definitions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/class_definitions.py) | 341–478, 750–1286 / 1286 | `ca07743dade5` |
| [dnd/content/characters/fighter_grants.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/fighter_grants.py) | Full / 912 | `6ca123f69fa3` |
| [dnd/content/characters/origin_definitions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/origin_definitions.py) | Full / 481 | `9503bc12754f` |
| [dnd/content/characters/origin_grants.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/origin_grants.py) | Full / 1153 | `52ac90551398` |
| [dnd/content/characters/premades.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/premades.py) | 1–120, 363–422 / 422 | `59f940e3c953` |
| [dnd/content/characters/progression.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/progression.py) | Full / 549 | `ef0457c735e9` |
| [dnd/content/characters/sorcerer_grants.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/characters/sorcerer_grants.py) | 74–287, 387–1324 / 1324 | `1ce4e3b5efa0` |
| [dnd/content/items/authored_item_builders.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/items/authored_item_builders.py) | Full / 741 | `b6543c09f34d` |
| [dnd/content/items/authored_item_definitions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/items/authored_item_definitions.py) | 1–185 / 1118 | `1b5f9b9639d9` |
| [dnd/content/items/environment_item_builders.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/items/environment_item_builders.py) | Full / 324 | `be0c276ea5c6` |
| [dnd/content/items/item_loadouts.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/items/item_loadouts.py) | Full / 87 | `88a2518535c2` |
| [dnd/content_system/condition_definitions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content_system/condition_definitions.py) | 1–185 / 564 | `196dad9f9547` |
| [dnd/controller.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/controller.py) | Full / 311 | `1f6f36aa1f49` |
| [dnd/core/action_execution.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/action_execution.py) | Full / 109 | `d80555c5e272` |
| [dnd/core/action_types.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/action_types.py) | Full / 97 | `ef29226eb9c8` |
| [dnd/core/base_actions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_actions.py) | Full / 2415 | `8ba48f73f8b5` |
| [dnd/core/base_block.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_block.py) | Full / 1406 | `368f006a2872` |
| [dnd/core/base_conditions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_conditions.py) | Full / 1060 | `d822880bb81b` |
| [dnd/core/base_object.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_object.py) | Full / 191 | `0065f201e5a0` |
| [dnd/core/base_tiles.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_tiles.py) | Full / 646 | `b0945ca9d2d8` |
| [dnd/core/condition_types.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/condition_types.py) | Full / 56 | `4d1df51e7c88` |
| [dnd/core/content/runtime.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/content/runtime.py) | Full / 520 | `9b8fb9e1ea9c` |
| [dnd/core/damage.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/damage.py) | Full / 135 | `9b6c8c368fdf` |
| [dnd/core/dice.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/dice.py) | Full / 365 | `e3498fa591c2` |
| [dnd/core/elevation.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/elevation.py) | Full / 39 | `53f25b74ccc8` |
| [dnd/core/events.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py) | Full / 5516 | `f524b65f205d` |
| [dnd/core/feature_grants.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/feature_grants.py) | Full / 32 | `9385706e456e` |
| [dnd/core/geometry.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/geometry.py) | Full / 354 | `b086ae80ce5a` |
| [dnd/core/gridmap.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/gridmap.py) | 81–428, 435–759, 770–1498, 1629–1858, 2026–2165, 2194–2600, 2645–2753, 2893–2983, 3508–3605, 3990–4100 / 4449 | `8573d5336ed2` |
| [dnd/core/item_types.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/item_types.py) | Full / 150 | `aa1c3fbdaf2c` |
| [dnd/core/modifiers.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/modifiers.py) | Full / 732 | `b88c481f2a1a` |
| [dnd/core/positioning.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/positioning.py) | Full / 24 | `3fb26fee8520` |
| [dnd/core/spell_execution.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/spell_execution.py) | Full / 95 | `dbb6e2cf06a7` |
| [dnd/core/traversal_connectors.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/traversal_connectors.py) | Full / 287 | `ba80356469ab` |
| [dnd/core/values.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/values.py) | Full / 2328 | `60a8c3d8d930` |
| [dnd/core/world_edges.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/world_edges.py) | Full / 194 | `fd862952092a` |
| [dnd/creature_transforms.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/creature_transforms.py) | Full / 362 | `a3f72dd442c0` |
| [dnd/encounter.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/encounter.py) | Full / 1448 | `2735b713facb` |
| [dnd/entity.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entity.py) | Full / 6952 | `de4307f72249` |
| [dnd/game.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/game.py) | Full / 54 | `f2f2dbad350e` |
| [dnd/items/environment.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/items/environment.py) | Full / 349 | `724a755b36dd` |
| [dnd/items/environment_interactables.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/items/environment_interactables.py) | 26–245 / 421 | `d1c01e632669` |
| [dnd/items/torches.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/items/torches.py) | 299–379, 582–661 / 680 | `cd34c0091230` |
| [dnd/reactions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/reactions.py) | Full / 107 | `f7b5781ff4f9` |
| [dnd/runtime_reset.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/runtime_reset.py) | Full / 64 | `caf0045fea4a` |
| [dnd/spatial/__init__.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spatial/__init__.py) | Full / 42 | `e39df88bd41e` |
| [dnd/spatial/area_conditions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spatial/area_conditions.py) | Full / 1353 | `e7c77d97d472` |
| [dnd/spatial/environmental_conditions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spatial/environmental_conditions.py) | Full / 1187 | `0c7510e9af07` |
| [dnd/spatial/memberships.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spatial/memberships.py) | Full / 281 | `9c1596c76890` |
| [dnd/spatial/restraints.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spatial/restraints.py) | Full / 296 | `f50e89c9de4e` |
| [dnd/spatial/transitions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spatial/transitions.py) | Full / 145 | `a494f630ff55` |
| [dnd/spells/abjuration.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/abjuration.py) | 89–111, 852–1032, 1319–1495 / 3515 | `78a6d5df064e` |
| [dnd/spells/base.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/base.py) | Full / 8 | `ede989d85c35` |
| [dnd/spells/evocation.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/evocation.py) | 1–227 / 5006 | `3944a9b6e89e` |
| [dnd/spells/necromancy.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/necromancy.py) | 82–286, 355–453 / 2476 | `7162d4d8a949` |
| [dnd/spells/transmutation.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/transmutation.py) | 724–960 / 2196 | `eea27d04be13` |
| [dnd/subjective_combat_log.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/subjective_combat_log.py) | Full / 913 | `450ba3f82231` |
| [dnd/tile_conditions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/tile_conditions.py) | Full / 66 | `4a1e275ead61` |
| [dnd/types/character_progression.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/types/character_progression.py) | Full / 190 | `23173f36aa5e` |
| [dnd/types/character_receipts.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/types/character_receipts.py) | Full / 221 | `0aacc0efcdac` |
| [dnd/world_authoring.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/world_authoring.py) | Full / 813 | `192c400359ab` |
| [game/animation.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation.py) | Full / 555 | `e3e5d99c3c63` |
| [game/animation_data.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation_data.py) | Full / 214 | `c78f0ab552b7` |
| [game/animation_draw.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation_draw.py) | Full / 277 | `eb9516f82c1d` |
| [game/animation_preview.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation_preview.py) | Full / 214 | `d2a23fc6f7bb` |
| [game/animation_types.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation_types.py) | 1–55, 294–321, 379–450, 489–501 / 501 | `3caacaf7c470` |
| [game/app.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/app.py) | 1–114, 1129–1493 / 1493 | `91b65b2b2fbe` |
| [game/presentation.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/presentation.py) | Full / 411 | `a4dab906ca3d` |

### Existing test source read
| File | Detailed source read / total lines | SHA-256 prefix |
| --- | --- | --- |
| [tests/architecture/test_content_recovery_cr45_direct_characters.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/architecture/test_content_recovery_cr45_direct_characters.py) | 1–105, 249–292, 490–555, 702–775 / 792 | `25f04aff4b57` |
| [tests/engine/support.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/support.py) | 1–205 / 385 | `7281c9bb9bc9` |
| [tests/engine/test_action_cost_atomicity.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_action_cost_atomicity.py) | Full / 156 | `2f3962125b6f` |
| [tests/engine/test_cold_presentation_facts.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_cold_presentation_facts.py) | 182–306 / 325 | `cdd664990ea1` |
| [tests/engine/test_combat_actions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_combat_actions.py) | 180–340, 540–588, 688–752, 755–772 / 1620 | `f014254230a8` |
| [tests/engine/test_condition_lifecycle.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_condition_lifecycle.py) | Full / 1034 | `152891598873` |
| [tests/engine/test_condition_transform_ownership.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_condition_transform_ownership.py) | Full / 510 | `e3ecfbe142e0` |
| [tests/engine/test_dice_event_semantics.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_dice_event_semantics.py) | 225–308, 435–549, 654–789, 1022–1097, 1612–1666 / 1800 | `2ef16dd52275` |
| [tests/engine/test_entity_composition.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_entity_composition.py) | 1–180, 645–721 / 779 | `3176035d08eb` |
| [tests/engine/test_equipment_domain_ownership.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_equipment_domain_ownership.py) | Full / 531 | `f482f61d951d` |
| [tests/engine/test_equipment_replication_facts.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_equipment_replication_facts.py) | Full / 245 | `e77356feed17` |
| [tests/engine/test_event_lifecycle.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_event_lifecycle.py) | Full / 663 | `bfd2fda00c7e` |
| [tests/engine/test_items_inventory_equipment.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_items_inventory_equipment.py) | 1–75 / 826 | `8dada4406449` |
| [tests/engine/test_manual_06_dice_and_roll_result_events.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_manual_06_dice_and_roll_result_events.py) | 160–322 / 322 | `7d1ac3757fbe` |
| [tests/engine/test_manual_11_grid_tiles_terrain_movement.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_manual_11_grid_tiles_terrain_movement.py) | 133–290 / 293 | `fe248b11333c` |
| [tests/engine/test_modifiable_value_semantics.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_modifiable_value_semantics.py) | Full / 700 | `7b936051c31b` |
| [tests/engine/test_senses_light_stealth.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_senses_light_stealth.py) | 1159–1234, 1407–1485 / 1943 | `a2756bde0034` |
| [tests/engine/test_spatial_conditions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_spatial_conditions.py) | 277–418, 494–569, 978–1314 / 1445 | `54821333489f` |
| [tests/engine/test_spellcasting.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_spellcasting.py) | 591–638, 757–922 / 1006 | `dc64943cec8b` |
| [tests/engine/test_standard_conditions.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_standard_conditions.py) | 363–609 / 804 | `ffe04890cfa3` |
| [tests/engine/test_traversal_connectors.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_traversal_connectors.py) | 1–245 / 251 | `4094546791fc` |
| [tests/engine/test_world_modification.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/engine/test_world_modification.py) | 741–865, 1391–1497, 1844–1944 / 2155 | `838bbdd8dda9` |
| [tests/game/test_animation.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/game/test_animation.py) | 1–86, 152–287, 365–434 / 434 | `464c739ec1c0` |
| [tests/game/test_animation_draw.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/game/test_animation_draw.py) | 66–116 / 233 | `7b732e53f381` |
| [tests/game/test_app_smoke.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/game/test_app_smoke.py) | 434–468 / 489 | `eb1a73544feb` |
| [tests/game/test_presentation_boundary.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/game/test_presentation_boundary.py) | Full / 230 | `e0526af3dedf` |
| [tests/progression/test_direct_character_builds.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/progression/test_direct_character_builds.py) | 1–159, 313–568 / 568 | `cc5014749450` |
| [tests/progression/test_direct_character_origins.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/progression/test_direct_character_origins.py) | 1–188, 510–650, 897–1020, 1115–1261 / 1261 | `bf8458af2dd7` |
| [tests/progression/test_direct_character_progression.py](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/progression/test_direct_character_progression.py) | Full / 529 | `12320ef81cee` |

### TypeScript and authoring reference source

NeuroClient (`NC` below) is pinned to `d274f2d62ca9c1c5ed62a77841cacf6cc0347491`. The matching journal implementation is **historical D&D SDK 74cc1f9**, not the current linked SDK. These are source-reference reads, not proof that the combined old application currently runs. Local fixture/SDK/oracle records have their own current working-tree hashes.

| Reference | Detailed ranges / total lines | SHA-256 prefix |
| --- | --- | --- |
| [devtools/trace_neuroclient_animation.ts](/mnt/c/users/tommaso/documents/dev/dnd_engine/devtools/trace_neuroclient_animation.ts) | 1–77 / 307 | `9a3247ec5f49` |
| [tests/game/fixtures/neuroclient_animation_timing.json](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/game/fixtures/neuroclient_animation_timing.json) | 1–64 / 5932 | `d7f8fac526b8` |
| [sdk/typescript/src/subjectiveJournal.ts](/mnt/c/users/tommaso/documents/dev/dnd_engine/sdk/typescript/src/subjectiveJournal.ts) | 133–192 / 595 | `f6521bf17468` |
| [NC/src/engine/eventIngestion.ts](/home/tommaso/Dev/NeuroClient/app/src/engine/eventIngestion.ts) | 1–105, 116–447, 780–860 / 947 | `594f0776f906` |
| [NC/src/engine/stateSync.ts](/home/tommaso/Dev/NeuroClient/app/src/engine/stateSync.ts) | 1–110, 180–260 / 618 | `d015d1c29e49` |
| [NC/src/render/clipQueue.ts](/home/tommaso/Dev/NeuroClient/app/src/render/clipQueue.ts) | 205–270, 455–555 / 690 | `dd891b5f9ee1` |
| [NC/src/render/clips/CastClip.ts](/home/tommaso/Dev/NeuroClient/app/src/render/clips/CastClip.ts) | 1–165 / 551 | `b24fc7e0535b` |
| [NC/src/render/subjectivePresentationMapper.ts](/home/tommaso/Dev/NeuroClient/app/src/render/subjectivePresentationMapper.ts) | 238–316, 408–461, 815–867 / 3259 | `11e7b5951696` |
| [NC/src/render/spellAuthoring/validation.ts](/home/tommaso/Dev/NeuroClient/app/src/render/spellAuthoring/validation.ts) | 85–130 / 1463 | `a3ce50d32960` |
| [NC/src/render/spellAuthoring/phaseGraph.ts](/home/tommaso/Dev/NeuroClient/app/src/render/spellAuthoring/phaseGraph.ts) | 1–155 / 233 | `44aed4396ba9` |
| [NC/src/ui/spellStudio/serialize.ts](/home/tommaso/Dev/NeuroClient/app/src/ui/spellStudio/serialize.ts) | 1–83 / 83 | `4e25fd1479b0` |
| [NC/src/ui/studio/StudioTransportController.ts](/home/tommaso/Dev/NeuroClient/app/src/ui/studio/StudioTransportController.ts) | 1–150 / 168 | `333cf0591c59` |
| [NC/src/ui/SpellStudioPreview.ts](/home/tommaso/Dev/NeuroClient/app/src/ui/SpellStudioPreview.ts) | 367–396, 2240–2310 / 4514 | `3b1655055298` |
| [NC/src/ui/spellStudio/timelineBuild.ts](/home/tommaso/Dev/NeuroClient/app/src/ui/spellStudio/timelineBuild.ts) | 28–45, 259–318, 1160–1200, 1304–1320 / 1334 | `925424ca4e0e` |
| [NC/src/render/presentationRuntimeHost.ts](/home/tommaso/Dev/NeuroClient/app/src/render/presentationRuntimeHost.ts) | 145–209 / 210 | `4bf3f0870461` |
| [NC/package.json](/home/tommaso/Dev/NeuroClient/app/package.json) | 141–167 / 167 | `8b4de2a3bae5` |
| `74cc1f9:sdk/typescript/src/subjectiveJournal.ts` (historical) | 218–312, 426–488, 527–552 / 842 | `3c7415e1091c` |

### Existing test commands executed in this documentation pass

These are the exact bounded pytest invocations reported by the reviewers. Read HOW_TO_TEST.MD before changing or extending them. Outcomes are retained individually; overlapping selections are not summed into a whole-suite coverage claim. Diagnostics are separately described in the Event, condition and values chapters.

**conditions:** 50 passed

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider tests/engine/test_condition_lifecycle.py tests/engine/test_condition_transform_ownership.py tests/engine/test_standard_conditions.py -q
```

**conditions:** Collection error; 23 deselected, one error. No selected spellcasting tests executed.

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider tests/engine/test_spellcasting.py -k concentration tests/engine/test_spatial_conditions.py -k concentration -q
```

**conditions:** 1 passed

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider tests/engine/test_spatial_conditions.py::test_multi_slot_concentration_veto_preserves_slot_and_spatial_children -q
```

**content-items:** 25 passed

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider tests/progression/test_direct_character_progression.py tests/engine/test_equipment_domain_ownership.py tests/engine/test_equipment_replication_facts.py -q
```

**content-items:** 45 passed, 23 deselected

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider tests/progression/test_direct_character_builds.py -k 'custom_build or point_buy or all_premades or unsupported_toggle or collision or birth_publication_failure or torch_premade_birth_failure' tests/progression/test_direct_character_origins.py -k 'every_origin_applies or natural_owner_failure or removal_preserves_sibling or total_level_reconciliation or removing_tiefling or moved_to_a_foreign or foreign_binding or custom_build or point_buy or all_premades or unsupported_toggle or collision or birth_publication_failure or torch_premade_birth_failure' -q
```

**presentation:** 11 passed; 60 deselected

```bash
.venv/bin/python -m pytest -q tests/game/test_animation.py tests/game/test_presentation_boundary.py tests/game/test_app_smoke.py -k 'authored_boundaries_match_original_runtime_pump or pause_seek_and_large_delta_share_one_time_domain or three_intervals_are_complete_passive_and_replay_after_reset or engine_producer_yields_each_scripted_mechanic_incrementally or authored_recovery_joins_delivery_while_number_finishes_its_own_lifetime'
```

**spatial:** 22 passed, 114 deselected in 2.05s

```bash
.venv/bin/python -m pytest -q tests/engine/test_manual_11_grid_tiles_terrain_movement.py tests/engine/test_traversal_connectors.py tests/engine/test_spatial_conditions.py tests/engine/test_senses_light_stealth.py tests/engine/test_world_modification.py -k 'entity_position_updates or voluntary_move_walks or forced_movement_uses or step_handlers_see or connector_variant_commits or connector_step_veto or area_membership_is_source or entity_anchored_area or failed_authorized_replacement or spatial_child_veto or spike_trap_uses or overlapping_wet or oil_barrel_destruction or paired_movement_emits or near_side_wall or nonvisual_senses_create or tile_removal_veto or world_tile_elevation_uses or rejected_move_arrival or attached_condition_blocks or world_root_completes_after'
```

### Inventory boundaries and remaining reading

Python inventory counts below include present tracked/untracked `.py` files under each named source tree. They are navigation scope, not acceptance totals or lines attributed to this task. The narrow read table above is authoritative for this pass.

| Source tree | Python files / lines | Scope remaining |
| --- | --- | --- |
| `dnd/` | 225 / 138,376 | Core owners and selected concrete consumers reviewed above; complete authored spell/monster/class/feat combinations, AI/planning, analytics and all content migration paths remain broader work. |
| `game/` | 12 / 4,805 | Capture/reduction, outer scheduling and authored actor/effect path reviewed; full map painter/projection internals and every asset adapter were not reread here. |
| `server/` | 88 / 53,219 | Retained legacy implementation; not re-audited wholesale or revived. One obsolete import surfaced during test collection and is recorded as a failure. |
| `sdk/` | 0 / 0 | Pinned historical journal API and current mismatch studied for intention only; no SDK runtime dependency is proposed for Pygame. |
| `devtools/` | 7 / 4,479 | Existing presentation import/oracle tools studied where recorded; unrelated development tools remain outside the detailed read. |


In particular, selected GridMap ray/path/light algorithms were followed through their relevant owners and public tests; that is not a full read of every internal geometry loop. Standard conditions were read completely, while conditions authored in all other catalogs were not. Full Entity/BaseAction reads do not imply every spell implementation satisfies those contracts. NeuroClient source coverage and the exact SDK revision distinction are recorded in the presentation chapter; its installed runtime mismatch remains explicit.

The root personally read the full Entity action/discovery/turn paths, BaseAction, action dispatcher, functional standard actions, Game, Encounter, Controller, runtime reset and subjective combat-log projector, and reviewed the other owner notes before consolidation. The Event reviewer read Events and values/economy; the condition reviewer read lifecycle/transforms and content/item ownership; the spatial reviewer followed world/perception and presentation. Their read ranges are merged above, not multiplied into inflated totals.

Existing checks and public diagnostics are recorded with outcomes in their chapters. Passing selections establish those behaviors only; source-only concerns remain unexecuted. Earlier P1/P2/G5/registry checks remain historical records in RECOVERY_PLAN, separate from tests run during this documentation pass. Ignored `.runtime/codebase-study` artifacts were working notes; the maintained chapters retain the findings, reproduction conditions and test evidence needed after those scratch files are removed.

## Review of this reference

Completed 2026-09-08. These reviews assess the study and its stated evidence; they are not acceptance of unimplemented gameplay integration.

| Review | Scope and result |
| --- | --- |
| Anti-slop: Event/values reviewer | Read the assembled owner chapters, synthesis and coverage; cross-checked critical equipment, destruction and progression junctions. No blocking overclaim or unnecessary system remained after corrections. |
| Anti-OOP: condition/content reviewer | Reviewed framing, Event/action ownership, values, conditions, content/items, presentation and synthesis. Specialized ECS owners, exact cleanup and the import boundaries were preserved. Relied on the spatial review for spatial implementation detail. |
| Spatial/presentation source reviewer | Checked its chapters against current owners and the pinned NeuroClient source. Complete engine lineages remain distinct from old frame-derived identity; existing observer semantics and independent historical playback remain intact. |
| Root consolidation | Read all six owner notes and the additional source recorded above, reconciled cross-owner claims, checked source hashes, local source links/line bounds, section links and Markdown whitespace. |

Corrections made during review included: replacing “completion freezes” with the actual mutable metadata contract; closing the Entity read-range gap; retaining the historical TypeScript/SDK coverage rather than claiming a runnable current pairing; distinguishing scheduler yields from arbitrary sleeps; using Dashing's movement budget rather than base speed in reproduction; and identifying the exact destruction entry missing a causal parent. The final record retains source-only concerns as unverified and does not hide the failed legacy test collection behind the passing selections.

The maintained changes for this study are this reference and navigation/continuation updates in RECOVERY_PLAN, README and CURRENT_BRANCH_DESIGN_GUIDE. Existing gameplay, test, asset and other branch changes were preserved. No skill or gameplay policy was introduced, and no implementation was resumed.

## Spell interception follow-up — 2026-09-09

**Current conclusion: the claimed Fire Bolt gameplay defect was not established.** The six-line patch and its new nine-case test file have been removed. They implemented an assumed CAST_SPELL/EFFECT veto/outcome-replacement contract that no maintained subscribing mechanic was found to use. They are not recovery prerequisites or current acceptance evidence.

The audit covered 112 explicit SpellAction `_apply` bodies across the school modules, plus Thaumaturgy's inherited implementation. Its reported 106 sibling patterns were conditional observations under an injected interceptor, not a count of broken gameplay spells. The earlier reviews verified the patch against the assumed contract and missed whether the requirement itself was justified.

The injected diagnostics did produce the reported values: canceled Ray of Frost damaged/slowed; canceled Cure Wounds healed; canceled False Life granted temporary HP; canceled or rewritten-to-MISS Inflict Wounds damaged; canceled Mage Armor installed its condition; canceled Misty Step moved. These observations establish what the generic API permits under those test handlers. They do not establish the intended interception contract. The removed nine-case suite had five failures before the candidate and nine passes afterward; that comparison likewise proved implementation of our assumption, not its legitimacy. Do not recreate those tests as shipped requirements.

The earlier broad run had 90 passing checks and two existing server dependency failures involving `server/world_contracts.py` importing removed `dnd.core.senses`; `test_spellcasting.py` also failed collection through that import. Those remain separate baseline limitations. No server repair was made. The withdrawn candidate's focused Pyright comparison had the same three existing evocation diagnostics on both sides. None of those results warrants restoring the candidate.

### Reassessment: actual interception boundaries

Production Trigger registrations, including dynamic lists, were checked for cast-EFFECT vetoes or attack/save-result replacements. None was found. Counterspell, Silence, Globe of Invulnerability and Antimagic Field intercept CAST_SPELL/EXECUTION. The six located spell-EFFECT subscriptions are Hidden reveal, Invisibility reveal, Greater Invisibility checks, Metamagic consumption, Slow action/bonus lockout and Sanctuary self-break. They update dependent state; they do not veto the cast or replace its attack/save outcome. Sanctuary's ward veto listens to ATTACK/DECLARATION. Trigger type/phase matching is exact; omitted identity filters do not create an any-phase subscription.

Three real public scenarios were executed without injected mechanical handlers. Observation callbacks only recorded current HP and phases:

| Shipped mechanic | Observed boundary and result |
| --- | --- |
| Counterspell against Fire Bolt | CAST_SPELL DECLARATION → EXECUTION → CANCEL; no spell EFFECT or damage children. Defender HP **60→60**. The caster's action and defender's reaction are spent. |
| Shield against Magic Missile | Each dart's TAKE_DAMAGE is canceled at EXECUTION before HP changes. All three darts are prevented; defender HP **60→60**; the spell still completes. |
| Death Ward against Fire Bolt | TAKE_DAMAGE/EFFECT is observed at HP **5**. The ward modifies the damage cap before commitment. An 8-point hit leaves HP **1**, consumes the ward and completes the cast. DAMAGE_APPLIED/EFFECT is observed afterward at HP **1**. |

Sources: [Counterspell's trigger](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/abjuration.py:1059), [Shield's damage trigger](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/abjuration.py:372), [Death Ward's cap](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/abjuration.py:2005), [receive_damage](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entity.py:2955), and [DamageApplied publication](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/entity.py:2865). TAKE_DAMAGE reaches EFFECT before health mutation; DAMAGE_APPLIED is a factual result after it. Prevention acts at the concrete owner's pre-commit boundary, not by undoing completed children. The phase name alone is insufficient.

Reproduction used the current content bootstrap and spell-family reset/builders. Counterspell/Shield: caster (1,1), hostile defender (4,1), caster slots `{1:1}`, defender slots `{3:1}` or `{1:1}`; register the actual reaction, update senses and publicly apply FireBolt/MagicMissile with `template=False`. Missile rolls use `fixed_dice_faces(2,2,2)`. Death Ward: priest (1,1) with slot `{4:1}`, friendly target (2,1) set to 5 HP, hostile caster (6,1); publicly apply DeathWard, then FireBolt with `fixed_dice_faces(18,8)`. Reset each scenario. The callbacks do not cancel or replace events.

These scenarios do not depend on the removed Fire Bolt guard. After withdrawal, four existing tests passed in **1.70s**:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider tests/engine/test_spell_families.py::test_eb_15_002_evocation_attack_save_and_area_damage_patterns tests/engine/test_spell_families.py::test_eb_15_010_shield_blocks_magic_missile_darts_against_its_target_only tests/engine/test_spell_families.py::test_eb_15_025_protective_abjurations_prevent_and_absorb_effects tests/engine/test_content_recovery_behavior_semantics.py::test_counterspell_uses_third_rank_floor_for_low_spells_and_cantrips -q --tb=short
```

## Planning requirement audit — 2026-09-09

The active plan was reviewed end to end after the user identified the unsupported interception premise. **One unsupported bug claim and eight groups of overreaching requirements were withdrawn or narrowed.** This is a count of planning corrections, not nine newly found gameplay bugs. Related repetitions are grouped below.

| # | Former planning burden | Evidence and correction |
| --- | --- | --- |
| 1 | Fire Bolt/spell-EFFECT repair prerequisite | No shipped cast-EFFECT veto/rewrite found; actual cast prevention works earlier. Remove the speculative patch/tests and the mechanics-repair stage. |
| 2 | Arbitrary late-child handling and complete objective-ancestor closure before the first cast | The late-child test manually constructs that case. Absent ancestors can also be outside retained history or undisclosed. Follow the selected real producer and require only the facts its permitted presentation needs. |
| 3 | Mandatory injected condition-removal veto case | The condition API supports veto preparation, but the cited test injects the veto and no production removal-veto subscriber was found. Preserve actual concentration cleanup; test this robustness contract when that owner is the selected work. |
| 4 | All outcomes and broad error/recovery playthrough before first integration | A finite positive-cast proof does not exercise every counterspell, concentration, A/B/A or fault case. Add actual families progressively; do not claim unrestricted gameplay support before implementing its real outcomes. |
| 5 | Generic transactional reduction, interleaved-cursor protocols and stale asynchronous completion fencing | Historical state ownership is required. It does not require recreating SDK leases/transactions or nonexistent callbacks around the pure Python sampler. Detect actual adapter failures; select additional recovery machinery only for a demonstrated exposure. |
| 6 | Pre-operation capacity reservation and byte-burst saturation policy | The current producer is finite and the first proof uses two casts. Preserve one pending owner without introducing an unbounded-service scheduling protocol. Measure real continuous production when that work is selected. |
| 7 | New scene/terminal-frame acknowledgement subsystem | Current Pygame samples/draws/flips before progress accounting. NeuroClient checks logical state/assets, not GPU acknowledgement. Retain observable output correctness without adding another commit protocol. |
| 8 | Monster-content migration before using a Goblin rig | Existing canonical materialization already builds and deploys a real Goblin. Use that owner; the missing work is the actual identity-to-rig connection, not assumed missing mechanics. |
| 9 | Repair equipment causal edges merely because roots differ | Separate roots are not by themselves a violated contract. Preserve actual facts/relationships; change ownership only when a concrete required consequence lacks its semantic cause. |

The Goblin evidence used [materialize_creature](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content_system/creature_materialization.py:87) with `BESTIARY_CREATURE_RECIPES_BY_ID['goblin']`, explicit entity UUID, deployment role and default possessions; then `compose_entity()` and `Game.deploy_entity()`. It succeeded in a fresh process with **10 HP**, content identity **creature.goblin** and committed creation. Calling the low-level factory without content initialization failed, but the canonical entry already performs that initialization. This proves the selected Goblin path, not all creature recipes.

The presentation review checked the finite producer at `game/app.py:1231`, existing queue ownership at `:1307`, reduction waiting on `current is None` at `:1364`, and ordinary draw/flip/progress at `:1399`. It compared NeuroClient's ClipQueue ownership and logical scene checks with the selected pure Python sampler. Original timing/rig/height checks remain useful; they do not need replacement frameworks or repeated engine fixtures for every pure-data edit.

**Preserved requirements:** complete existing lineages; established subjectivity; selected passive retained facts; independent latest reduction and historical presentation; original NeuroStudio JSON; pure Python/Pygame runtime; root/per-pack rig data; G5 support/timing; actual map composition; specialized ECS owners and the import DAG. Representation/capture work is finite to the consumed fields/families. A completion hook remains a candidate until actual value lifetime proves it insufficient.

Anti-slop and anti-OOP reviewers read the cleaned candidate; the presentation reviewer rechecked the runtime/source boundaries and the content reviewer verified the current Goblin path. All accepted removal of the inflated gates while retaining the core design. This review does not certify every other observation in this reference as a bug or as a required task.

**Continuation guard:** name the user requirement or real mechanic/consumer, the concrete owner/type/phase, and the observable mismatch before promoting a concern to a blocker. Distinguish shipped behavior, owner API robustness and an injected experiment. The next implementation remains one real lineage connected to the existing sampler, followed by the two-cast independent-progression proof.

## First cast integration contract — 2026-09-09

Step 1 now has a fresh public producer trace, reviewed for source reuse and ECS
ownership. The ignored `.runtime/first-cast-study.py` diagnostic uses the existing
content bootstrap, public entity composition/deployment, action discovery and
`Encounter.execute_action`. A second cast occurs only after ordinary turn
progression returns control to the caster. Each cast has 15 stored versions:
Spell declaration/execution; AttackD20 declaration/effect/completion; Spell
effect; TakeDamage declaration/execution/effect; DamageApplied
declaration/execution/effect/completion; TakeDamage completion; Spell completion.
The four logical nodes are the spell root, its attack-roll and incoming-damage
children, and the applied-damage grandchild. Both casts hit for 7: normal HP
80 → 73 → 66, temporary HP 0, life ALIVE. First/second source intervals in that
setup are [27,42) and [60,75); intervening turn events remain distinct from the
cast lineage. These offsets are diagnostic observations, not required IDs.

| Historical input | Existing fact and finite binding |
| --- | --- |
| Recipe | `behavior_id=spell.fire_bolt`, `spell_id=fire_bolt`; select the existing `spell.fire_bolt` draft by semantic identity. |
| Causality | Actual root/version/lineage and stable child relationships; Fire Bolt has no application ID. Allow `None` in the existing sampler input. |
| Normal/temp HP | `DamageAppliedEvent.resulting_normal_hp/resulting_temporary_hp`; packet `applied_damage` separately drives the number. |
| Initial actor state | Explicit known-actor startup baseline immediately before the first selected cast. Completed birth records supply unchanged appearance, item/equipment identity and HP; initial normal HP is `maximum_hit_points - damage_taken`, since birth `current_hit_points` includes temporary HP. Capture the existing active weapon-set enum separately. |
| Contact/support | Selected observer's historical SensesSnapshot and retained WorldTileState elevation; current contact does not retroactively make birth an observed event or authorize every birth field. |
| Life | Retain ALIVE from the baseline; an unchanged state binds `resulting_life_state=None`. Actual later life transitions are separate engine facts. |
| Appearance/gear | Root body/head/tints and Shadow from existing appearance fields; equipped dagger layers from the existing authored item-visual ledger. Fixed rig identity uses its existing rig metadata. |

The selected capture retains ordinary completed Event families and causal
version diagnostics. Family-specific copies retain concrete DiceRoll values,
passive costs/results and existing projected logs; they omit unconsumed live
ModifiableValue/Damage graphs. Copying concrete DiceRolls with `model_copy`
does not rerun their registering constructor. This is a consumed-fact boundary,
not a generic mechanical archive or a new disclosure policy.

**Requested behavior and verification boundary:** two real public casts feed
the existing Python compiler/sampler through retained history. After both
reduce, latest HP is 66 while the first active animation still shows 80 before
its authored HP anchor and 73 afterward. Its samples and timing must match a run
with no later cast pending. The next historical head starts at 73. Retained
reduction/binding must still work after engine reset. Existing map capture,
original timing, rig and drawing checks remain applicable.

Implementation uses the current presentation target/reducer, a finite
complete-lineage capture and semantic cast binder, and the existing sampler.
Anti-slop and anti-OOP review found no mechanics prerequisite or additional
timeline/queue framework. Actual map painter integration remains the next
distinct layer after this retained-history connection.

### Verification and plan checkpoint

The retained connection is now implemented in `game/presentation.py` and
`game/combat.py`, with appearance binding in `game/animation_data.py` and neutral
`RigLayer` values in `game/animation_types.py`. The sampler's application identity
now permits the actual single-target `None`; authored timing is unchanged.

`tests/game/test_combat_history.py` passed **3 tests in 1.65s**. Its public
two-turn example verifies the retained lineage relationships, latest HP
80 → 73 → 66, unchanged first-cast samples/HP anchor and replay after engine
reset. It also rejects a real unfinished declaration and a missing historical
recipient despite that Entity still existing live. Both casts are produced
before sampling in this test; live frame-pump overlap remains unverified.
Pyright on `game/presentation.py`, `game/combat.py` and this test reported
**0 errors, 0 warnings**.

The presentation-boundary/app-smoke and dependency/AI-import regression run
reported **45 passed, 2 failed in 73.87s**. Both failures are the already recorded
server boundary problems: `server/world_contracts.py` imports removed
`dnd.core.senses`, breaking fresh server import and the cold transport leaf
check. The existing Pygame smoke settled all three map intervals with
E=R=D=42. No server repair follows from these results.

Anti-slop and anti-OOP review found the plan's progress stale, with no newly
established architecture blocker. Steps 1–3 are complete for the selected
fully observed, surviving Fire Bolt case; the next work is actual same-thread
app/map integration and the displayed two-cast proof. The plan now states the
selected capture boundary, removes repeated abandoned concerns from active
instructions, and keeps their evidence in the existing audit record. Historical
equipment transitions, broader subjectivity and other spell outcomes remain
capabilities to demonstrate when selected.

## Integrated map playback and ordinary miss — 2026-09-09

`game/play.py` now runs the selected cast path through the existing map drawer.
`game/__main__.py` installs the existing content runtime and invokes that entry;
`game.app.run` remains the finite door/light regression tool. The composition
script in `game/combat_demo.py` reuses the actual visual-vertical-seam battlefield,
Entity composition, senses, startup capture/reduction, action discovery and
Encounter turns. The default caster starts at (16,25), one cell outside the stair
mouth, and the recipient at (16,20), height 2. Both have actual darkvision for
this dark map. A rendering test explicitly uses the lower stair cell (16,24)
to verify partial cliff occlusion.

Input deadlines at 0/1000ms use input time. The async frame loop executes each
due public operation synchronously, reduces latest state immediately, retains
its lineage in one deque and yields. Dispatch does not depend on pause or active
animation completion. One active `BoundCast` binds from historical state. Media
loads before its clock starts; the finite same-actors/loadout/facing/recipe script
reuses that media for its second cast. No general media-cache or scheduling
framework was introduced. The displayed sample is drawn and flipped before its
historical successor becomes the next baseline. Completed projected combat-log
text is displayed as text; it does not generate mechanics or timing.

`animation_draw_commands` shares image builders with the detached drawer and
supplies actors, shadows, projectiles and numbers to the map's existing sort.
`draw_frame(extra_commands=...)` consumes plain draw commands and stays unaware
of animation schemas. World effects use interpolated world contacts for depth;
authored image offsets/pivots continue to control only the image position.

The actual same-cell front-wall test found an actor overwriting 256 fully opaque
wall pixels. `painter_key` now accepts the actual boundary poses and sorts at the
frontmost half-edge; the authored blit contact is unchanged. A composite corner
supplies both real edges, avoiding interpretation of its representative art pose
as a straight wall normal. Six real raster cases pass: lower-caster cliff
occlusion in two views, and straight/NE-corner wall front/rear views. Corrected
images were inspected in `.runtime/combat-map-review/`.

The initial real X11 window run completed both positive casts with latest and
historical states equal: 277 published frames over 4.992 seconds of input time.
The second reduction occurred during first-cast travel. This is one observed
run, not a performance guarantee. The SDL frame-loop tests also verify later
reduction during travel and a frozen paused sample while latest HP changes.

After that integration review, the selected next case was ordinary miss. Public
MISS(seed 1) and CRIT_MISS(seed 31) produce a completed Spell root and attack-roll
child, no damage children, unchanged HP and the existing projected miss log.
The binder now uses those explicit outcomes to provide the already supported
`damage_applied=False` input. Capture, reduction, authored timing, sampler and
drawing require no miss-specific replacement. Other absent-damage cases retain
their own semantics. Two public miss cases plus the three retained-history cases
passed together (5 tests in 9.35s), including replay after engine reset.

The existing map-only subprocess's 8-second threshold was exceeded in several
runs despite successful settlement. A sequential comparison using HEAD's
`app.py`, `presentation.py` and `projection.py` over the same remaining runtime
also exceeded it: HEAD map owners 8.469s, current map owners 8.556s, both exit 0
with E=R=D=42. This does not establish a new combat regression or justify changing
the threshold. The existing water-row `.value` Pyright diagnostic in `app.py`
also remains on the identical HEAD source expression; it is separate from the
new typed playback owners.

The final combined app/map/projection/import run passed **171 tests in 81.15s**,
including the previously variable startup timing check. Its scope was the three
integrated playback cases, six new map raster cases, existing app/boundary/height/
projection suites, and the existing import-cycle, dependency-direction and
no-function-local-import checks. Earlier detached drawing/height regression
work passed 50 cases before the corner extension. These counts describe their
respective runs, not a claim that the entire repository suite is green.

The retained-history and public miss tests passed separately (5 in 9.35s).
The next selected case was an actual canonical Goblin recipient using the
already imported rig. Its completed integration is recorded below.

### Canonical Goblin integration contract — 2026-09-09

The selected extension is a surviving Fire Bolt hit followed by a miss against
the current canonical Goblin, through the same public scenario and map loop.
`materialize_creature` supplies its actual 10 HP, AC 15, scale 0.82, darkvision
and default equipment. Seed 17 hits for 7; seed 1 misses. Its birth identity is
`content.neurodragon:creature:creature.goblin@1`, the full existing content key.
The presentation binding maps that key to the already imported Goblin01 rig.

An actual positive-damage probe also produces the existing `HasTakenDamage`
condition application as a child of `DamageAppliedEvent`. Its tracker reacts
at DAMAGE_APPLIED/EFFECT; the marker has a one-round duration and no modifier,
handler or subcondition receipts. Its INTERNAL category already produces no
combat log in the engine. The retained lineage must keep this child, identity,
parent links and concrete condition/duration values. Copying this selected
marker clears runtime contexts and registration flags before deep copy; its
reducer contributes no actor/vital change. This does not introduce a condition
simulator or a general serialization contract for other condition families.

Acceptance: actual SDL playback shows the fixed rig and 10 → 3 → 3 HP; saved
lineages retain their child and original duration across later turn progression
and engine reset, and replay to the same historical result. Anti-slop and
anti-OOP review approved this finite junction after reading the real producer.
The scenario uses the canonical materializer's existing module-level content
dependency; the independent map-only application does not import this scenario.

The Goblin extension passed all four integrated SDL cases (25.63s), four retained
history cases (5.80s), and 50 selected miss/map/appearance/rig/import checks
(36.36s). The map-only cold-import check also passed. Its real-clock X11 run
published 264 frames over 4.707s of input time, completed both casts with matching
historical/latest state, and reduced the second during first-projectile travel.
These checks established progression and grounding; they did not establish
correct hand/body projectile attachment. The user's subsequent correction did.

### Projectile attachment correction — 2026-09-09

The user observed release above the caster's hand and impact above the Goblin's
body. The first visual review had checked map support, timing and feedback, and
missed this. A matching renderer sample does not prove its spatial assumptions.

Source evidence: NeuroClient `CastClip.ts:238` selects authored endpoints;
`projectileEndpoints.ts:155` adds their offsets to the rig root, while
`StudioActorBootstrap.ts:96` and `:160` supply scale-1 actors. Fire Bolt's original
128px projectile has anchor (0.5,1), scale 1 and canvas center 64px above its
logical endpoint. The new scene shrank the caster to 0.5 and used the Goblin's
actual 0.82, while retaining the full canvas padding and 24/-16px axis insets.
The measured mismatch and release/impact frames support this concrete diagnosis.

`project_projectile` now scales the authored local attachment and canvas-center
registration through each actor separately, then applies scaled axis insets on
that visible path. It subtracts the full-size sprite registration before the
drawer adds it. `projectile_center_offset` owns that shared registration math.
Support heights and effect size do not scale with the actor. The scale-1 case
preserves original source placement. The compiler's canonical timing metric,
original JSON and stored samples remain unchanged; this is the existing visual
projection adaptation, not a second timeline or a replacement socket system.

Eight attachment regressions failed before correction (0.5 and 0.82 scales in
four camera views). Older G5 spatial checks that required the incorrect
half-scale raw-root placement were corrected: source-position parity belongs
to Studio's unit-scale case, and scaled canvas offsets belong in smaller-actor
expectations. Duration, pause, independent reduction and support-lift assertions
remain. Fire Bolt uses the same asset in every phase; this does not establish
cross-phase registration for different asset canvases.

Final verification: **128 passed in 53.37s** across animation timing, spatial
attachment, imported drawing, retained history, integrated playback, map
composition and actual misses. Changed production/test owners pass Pyright with
the project interpreter. The corrected CLI completes both Goblin casts with
matching historical/latest state. Actual q0/q3 release frames show the effect
meeting the raised hand; all four impact views show body contact. Terrain hides
the caster in q1/q2, so those map frames do not prove release alignment there;
the four-view attachment regression covers their projection math. Original
assets and materialized JSON were not edited for this correction.

### Existing alignment data audit — 2026-09-09

The user accepted the visual correction and reminded us that alignment was
already authored data. The active path is `sourceAnchor`,
`sourceAnchorsByFacing`, `targetAnchor`, sprite offsets/anchor, asset dimensions
and the rig origin. The data README now maps these fields to their Python
consumers. No missing active table was found. The source-data and spatial
checks passed together: 38 tests in 3.05s.

NeuroClient commit `20832db` explicitly retired
`public/studio/spell-projectile-overrides.json` and
`src/render/data/animation/projectileDefaults.json` in favor of complete Studio
recipes and `generatedSpellPresentationProfile.json`. Their Fire Bolt offsets
survive in the imported v6 draft. Commit `f403f8b` changed the old 256px asset at
scale 0.5 to the current 128px asset at scale 1, preserving its displayed canvas
size. Restoring that obsolete 0.5 value on the new PNG would halve the effect.
The imported draft, projectile-assets file and generated profile are byte-exact
copies of the pinned current source. The original executor takes per-facing
forward/side/lift and a separate global source axis; the Python path follows it.
No retired defaults, per-spell alignment code or additional socket schema is
needed for the current case.

### Lethal Goblin integration contract — 2026-09-09

Two legal seed-17 casts against the canonical Goblin produce 10 → 3 → -4 normal
HP and ALIVE → DEAD on the second cast. Negative HP is the current engine's
actual monster fact. Death is selected from `LifeStateChangeEvent`, never
inferred from that number. The completed root has 10 terminal nodes; independent
Encounter progression after the root remains outside its lineage.

The newly consumed families are `DeathEvent` and a `SpatialChangeEvent` with
`PERCEIVABILITY_CHANGED`. That spatial child retains the exact Death EXECUTION
parent and position (16,20). The Goblin stays in GridMap membership, while its
life-state transform changes perceivability/blocking. Existing sensory children
remove the caster's current Goblin contact and the Goblin's own vision/contact.
Existing LifeStateChange and observer sensory reduction already own those
successor facts; death/spatial cause rows require no second mechanics reducer.

The initial capture gate required every terminal version to retain current
location, rejecting this real death. EventQueue intentionally accumulates
identity while replacing location evidence. The original life-state mapper
admits the identified life fact without requiring continued location. For the
selected known cast, initial-root identified/location evidence establishes the
historical participants; later terminal grants must remain unchanged and actual
contact removal must still reduce. Binding uses the historical visual contact.
This admission does not grant a current location or define unknown-source,
teleportation or corpse-discovery behavior.

Implemented: `capture_lineage` retains Death and the exact perceivability-change
family. Its initial-root participant evidence does not rewrite any terminal's
grants. `reduce_lineage` leaves those cause rows passive, using the existing life
and sensory handlers for state changes. `game.play --lethal` is exposed through
`python -m game --lethal`; it uses the existing sampler's Die clip and independent
input/playback clocks. Latest can be DEAD while the first cast still shows ALIVE.
The second effect commits the actual life fact at 1420.399660ms; the existing
death clip completes at 2587.066327ms and holds frame 14.

Anti-slop and anti-OOP review inspected the real producer and retained example.
Validation: five history cases passed in 10.02s, five SDL playback cases in
30.70s, and 112 selected animation/rig/miss/subjective-log/import-DAG regressions
in 19.38s. Changed owners pass Pyright with the project interpreter. The headless
`--lethal` CLI completes 2/2 casts with historical/latest state matching. Saved
release/impact/completion frames are output evidence, not proof that the path
between those endpoints clears terrain; that is the next user-raised study.

### Bolt through the stairs: trajectory-space study — 2026-09-09

The user observed that the straight bolt should clear the stairs, suggesting a
Bézier or hypotenuse. Intermediate frames confirm that most of the effect is
hidden at the upper stairs. Local diagnostic captures at travel fractions
0/0.2/0.4/0.6/0.8/1 in camera quadrants 0 and 3 are under
`.runtime/projectile-stairs-study/`. Release/impact alignment alone missed this
part of the path. No trajectory code or authored data was changed by this study.

Actual battlefield supports along x=16, y=25→20 are 0,0,1,2,2,2 five-foot steps.
A straight support-origin interpolation has heights 0,0.4,0.8,1.2,1.6,2 at those
centers, below the upper stair/platform before body attachments are included.
These values are a support-profile comparison, not a physical hand/body-ray
proof: the current authored attachment offsets are screen-local, and do not
define unique world-space sockets. The actual map captures show the visible
consequence with those offsets included.

Public gameplay probe: both optical and propagation `GridMap.raycast_clear`
queries accept the route, target discovery reports visual darkvision contact
and 25ft distance, and public Fire Bolt produces a HIT. Current ray transitions
are planar optical/propagation checks, not altitude-versus-terrain intersection.
Relevant owners are `battlefield_catalog.py:_build_visual_vertical_seam`,
`FireBolt._validate`, and `GridMap.raycast_clear`. An accepted target is therefore
not evidence that this particular visual trajectory clears the terrain.

Original NeuroClient `SpriteProjectileFx.ts:646–706` and
`ProjectileFx.ts:865–950` implement a quadratic Bézier in **screen space**. Its
control point is the endpoint midpoint plus the perpendicular chord vector
times authored curvature (with optional same-target spread). Both executors
derive duration from endpoint chord length and sample linear parameter t; they
do not measure curve arc length or query terrain. The imported Python schema
already preserves straight/Bézier and curvature; its selected compiler currently
accepts only straight. Fire Bolt is authored straight. Faithfully porting that
screen curve would not by itself create a vertical terrain-clearance arc.

`compile_cast` already adds support-height difference with `hypot` to its
canonical flat reference distance. The observed travel duration is 822.066327ms.
That is the accepted G5 presentation timing metric, not a mechanical 3D ray.
Changing distance alone cannot change clearance. `project_projectile` currently
joins projected attachments; `_effect_contact` supplies interpolated support
coordinates to the painter. Painter occlusion is not a collision decision.

Anti-slop review confirmed the original trajectory semantics and challenged
automatic terrain avoidance as an unstated gameplay policy. Anti-OOP review
confirmed the existing geometry, targeting and drawing owners with a public
probe. The bounded design question is how the existing trajectory vocabulary
acquires world-height meaning while preserving authored attachments and timing.
An upward world-space arc is a candidate for the user's intended appearance;
its height must clear the selected support profile and project consistently in
all camera views. This is an explicit 2.5D adaptation to settle, not an inherited
capability of the old screen Bézier or a request for a general routing system.

### Implemented vertical arc and validation — 2026-09-09

The comparison supported an explicit arc for this finite terrace scene. The
minimum apex above its support-origin chord is one five-foot step. The upper
stair cell starts at y=22.5, progress 0.5: linear support height is 1 and the
required surface height is 2. Checking only cell centers would wrongly accept
5/6 step. Treating each retained cell as its constant support-height envelope,
the one-step quadratic meets the upper entry and stays at or above the remaining
supports. This excludes sprite radius and physical hand/socket volumes.

`CastInput.travel_apex_steps` now freezes that explicit visual choice; default
zero preserves the original path. The existing terrace app binds 1. It adds
4t(1−t) times the apex to world height, zero at both attachments. One calculation
in `game.animation` supplies projection and the shared `projectile_contact`
used by both drawers. Fine rotation uses the projected vertical derivative and
keeps the incoming tangent at impact. This is an intentional height-orientation
adaptation, while original facing rows, offsets and `fineRotation=none` still
apply. Original Studio JSON and the compiled duration are unchanged. No runtime
terrain query, automatic routing rule or additional queue was introduced.

Anti-slop review inspected the changed owners and all four 60%-travel map views;
anti-OOP review checked the full-cell bound and wrote spatial acceptance. The
bolt is visible above the upper stair opening in every inspected view. Four
map raster cases require its bright core to remain substantially visible.
An isolated replay that disabled only the vertical projection reproduced the
q0 failure: 0 of 436 bright-core pixels visible, caught by the new test.

Validation completed: 84 authored timing/drawing/source-data cases in 11.58s;
38 spatial cases in 1.46s; 15 actual map/SDL playback cases in 41.91s. Changed
production and test owners pass Pyright with the repository interpreter. Real
X11 lethal playback published 286 frames, completed both casts, retained ALIVE
in the first displayed history while latest was DEAD, and finished with matching
historical/latest state. `.runtime/combat-stair-arc/live-evidence.json` retains
that result. Actual frame-loop video and GIF are in the same directory; they
record the integrated renderer rather than the earlier comparison harness.

### Equipment replacement: selected contract — 2026-09-10

The next selected case replaces a dagger in MELEE_MAIN with a carried shortsword,
both installed through `Entity.install_initial_items` before birth. A public
`Entity.equip_item` probe succeeds, leaves MELEE/HP/action economy unchanged, and
publishes four independent completed roots: dagger WeaponUnequip, shortsword
WeaponEquip, shortsword ItemLocation(EQUIPMENT), dagger ItemLocation(INVENTORY).
All retain their actual parent=None and empty child sets. Declaration/execution
phases overlap: the unequip/equip ranges in the probe are [6,12) and [8,14).
The current earliest-declaration cursor fence rejects their ordinary completion
order; completion progress, not declaration overlap, is the consumed boundary.

The two equipment roots explain the transition. Committed cold item-location
after-values supply actor item/slot changes. Incoming EQUIPMENT replaces the
exact slot occupant; the later displaced-item INVENTORY fact removes only that
item UUID's slot membership, preserving the replacement. Both item snapshots
remain in `ActorState.items`. This selected case does not require a new stance
event, reconstructed parent, batch-as-lineage or backend mechanics edit.

NeuroClient's existing `equipment_transition` context is Taunt, speed 3,
commitFrame 4, media empty. Its SwitchWeaponClip commits **displayed active set**
at frame 4 (111.111ms for the imported rig), completing at last index 14
(388.889ms). Existing actors retain their old full loadout during staging;
replacement item identities install with the historical frame commit. Thus a
same-MELEE replacement is not a new active-set switch, and frame 4 cannot be
treated as a universal item-replacement anchor. The Python context JSON is
already retained; no new authoring schema is needed.

Anti-OOP review traced the public four-root example and finite cold payloads.
Anti-slop review traced the exact original active-set versus item-loadout owners.
An initially suspected Fire Bolt weapon-hiding mismatch was withdrawn: the
existing action-VFX weapon override restores at Casting exit; it is distinct
from the selected empty `hiddenSlots` scope. Current Python behavior is correct.
The authored ledger already resolves dagger to Melee1 and shortsword to Melee3;
Melee3 media is a later bounded import when actual visual playback is connected.

The capture/reduction connection is now implemented. The finite copier retains
WeaponEquip/Unequip and the selected INVENTORY/EQUIPMENT item facts as passive
copies, preserving every original root identity. Reduction advances by completed
end cursor; overlapping declarations of these independent roots remain valid.
The two cause-only roots leave the earlier slot unchanged. The incoming cold
equipment fact installs the new slot, and the displaced inventory fact preserves
it. No active-set inference or live item/Entity lookup occurs during replay.

The public 3×3 self-observer test in `test_equipment_history.py` passes (1.39s):
old layers remain Melee1, latest resolves Melee3, roots and exact item after-values
survive reset, and HP/MELEE remain unchanged. The cast/history/miss and three
import-boundary checks also pass (10 tests, 24.49s); changed owners/tests pass
Pyright. This establishes retained equipment state, not a displayed equipment
gesture. The next connection is the existing context execution and actual media
for the changed historical appearance in the same application queue.

### Equipment replacement: integrated playback — 2026-09-10

`iter_combat_demo(replace_weapon=True)` now yields the baseline, one public cast,
the four separate roots of one `equip_item` command, and a second legal cast.
All four equipment roots are captured before the first of them is yielded.
Input deadlines are 0 ms for cast one, 1000 ms for that equipment operation's
four deliveries, and 1500 ms for cast two. These deadlines belong to the finite
input script; they do not schedule or resize the authored animations.

`game.play` retains one pending deque and one active cast/equipment head. Latest
reduces every root immediately. Historical playback drains cause-only roots
individually; `bind_equipment` selects a gesture only for an item-location fact
whose reduced appearance differs. In this producer the incoming EQUIPMENT root
owns that gesture. The later INVENTORY fact still commits separately and cannot
erase the replacement slot. This is a deliberate adaptation from the old mapper,
which attached a single equipment cue derived from a projected loadout patch to
the last matching item root in its batch. The old batch/frame machinery is not
being recreated here.

`EquipmentTransitionContext` types the imported body fields with original TS
bounds. `compile_equipment` and `sample_equipment` use the original Taunt/speed-3
context and last-index completion. At 111.111 ms the pose is Taunt frame 4 with
the dagger still present; at 388.889 ms it settles to Idle and the application
selects the replacement layers. The historical successor commits after that
frame is drawn and flipped. Nonempty equipment `media` remains retained JSON
and explicitly unsupported by this executor; the actual imported context is
empty. No general active-weapon-set switch producer is claimed by this case.

`BoundEquipment` retains source contact, known scene contacts, old appearances,
replacement layers and the reduced successor. The preceding displayed bodies
supply world facings, preventing a snap back to `_contact`'s default S. The
recipient continues sampling Idle through the gesture; existing DEAD settlement
is available from the same body helper. Contacts and gear come from historical
data, not current entities or a fake cast timeline.

The shared actor media loader in `animation_draw.py` accepts explicit contacts,
layers and clips, and retains pixels only. Its shared actor/shadow draw helper
is used by both casts and equipment with the existing map painter. Cast-specific
effects, numbers and media remain in the cast wrapper. Each new head preloads
the necessary pixels before starting its visual clock. Old/new appearances
stay separate, including after later reduction; no second cache of actor state
or scheduling manager was introduced.

The pinned importer added the five original Melee3 sheets (627,398 bytes).
Bindings/provenance changed; original source JSON and existing materialized
recipes did not. `--check` reproduces all 71 outputs. The native Bun used is
`/home/tommaso/.npm/_npx/5c4f1b4a21be27f7/node_modules/@oven/bun-linux-x64-baseline/bin/bun`;
it remains an offline tool, with no runtime TypeScript dependency.

Verification completed:

- 7 SDL application cases, 49.21 s: the two new mixed-sequence cases plus five
  existing cases. Latest shortsword/second damage advance during an unchanged
  paused first sample; dagger survives all gesture samples until completion;
  cast two starts at elapsed zero with Melee3; six roots reconcile final state.
- 9 retained cast/equipment/miss cases, 22.75 s, including public mixed input
  and engine-reset replay.
- 147 animation/equipment/drawer/rig/spatial/map cases, 19.96 s. The new pure
  cases check original frame-4/completion timing, disabled body, large seek,
  replay and visible Melee1/Melee3 pixel differences in every quadrant.
- 50 source/appearance/spatial cases, 4.57 s; this selection overlaps the
  spatial tests above and is not an additional unique total.
- 4 explicit import/DAG rules, 6.00 s, and Pyright on all changed production,
  importer and test files: zero errors/warnings.

Real X11 runs in every quadrant completed 2 casts/6 lineages with equal final
historical/latest state. Quadrant 2 also used the canonical Goblin hit/miss;
quadrant 3 used its actual death. The normal geometry occludes the lower caster
from the far side, while both actors continue contributing their body commands.
The final recorded X11 run retains 118 frames over 5.965 seconds, including 26
published equipment samples; its actual wall timestamps drive the video.
Evidence, snapshots and reproducible recorder live in `.runtime/equipment-play/`.
One earlier recording attempt closed before its first game frame and produced
no clip; the completed recording is the subsequent run described here.

Both final reviewers found the selected structure coherent. The anti-slop
review explicitly limited parity to the original empty-media equipment context;
the anti-OOP review checked separate roots, frozen body/layer values, retained
facing, independent clocks and post-publication historical commits. No backend
mechanics file was changed in this equipment playback session.


### Ordered Magic Missile applications: integrated playback — 2026-09-10

This cut extends the existing cast executor. It does not add an animation queue
per dart, recreate NeuroStudio authoring, or change backend mechanics. The useful
new distinction is between an ordered application and an actor: A/B/A has three
applications, two recipient bodies, and one caster body in one complete lineage.

**Producer and history.** `game/combat_demo.py` uses the existing public
`execute_by_index` with `extra_target_uuids=[B,A]` during real Encounter turns.
The narrower Encounter wrapper does not accept that allocation; no wrapper or
backend change was necessary. The caster starts with two level-1 slots and makes
two legal casts. Each root retains ten terminal events from 37 source versions:
the root Spell plus three application Spell, TakeDamage and DamageApplied
lineages. Application IDs/indices are the actual producer's values. Parent event
UUIDs may name intermediate phases, so the binder joins by `parent_lineage` and
`children_lineages`, not equality to a terminal version UUID.

The first cast's packet totals are 5/5/2: A 80→75→73, B 80→75. The next cast's
3/2/4 packets produce A 73→70→66, B 75→73. Each application keeps its own resulting
HP. Repeated A receives the same root-start retained contact; partial damage is
not used to mutate the next application's initial actor. Existing grant capture,
complete-lineage reduction and replay after runtime reset remain the owners.

`CastInput.applications` is now an ordered tuple of passive `CastApplication`
values; Fire Bolt is its one-application case, preserving its absent application
ID. `ApplicationTimeline` holds per-dart endpoints, arrival and feedback anchors.
`CastTimeline` retains the shared body/release/completion. `CastSample.vitals`
contains one value per recipient; numbers and projectiles retain application
identity. The body sampler reenters A's latest hit animation while preserving
both A numbers and distinct HP changes. The old singular target/timing fields
were migrated rather than kept as a second source of truth.

`game.play` still has one pending deque and one active cast/equipment value.
Latest reduces each complete root on receipt; the displayed successor commits
only after its historical completion frame is drawn and flipped. Paused tests
show initial visible A/B HP 80/80 while latest has already reached 66/73. The
optional weapon replacement retains all three bodies and the old dagger until
the existing gesture completes, then uses the shortsword on the next cast.

**Original authoring and execution.** Magic Missile uses the unchanged generated
Studio v6 record: Special1, release frame 8, body speed 1, 80 ms missile stagger,
Bézier curvature .3 and same-target spread. A's two curves have opposite signs;
B's singleton keeps the positive curve. No damage override is authored, so the
existing global damage context and the actual Force palette supply TakeDamage,
frame-zero HP/flash/number, the 150 ms flash and 900 ms number. Geometry uses the
existing generated dart style. Its impact flag does not create a sprite burst:
the original geometry is destroyed at arrival and waits for the hit reaction.

`devtools/trace_neuroclient_animation.ts --magic-missile` runs unchanged original
ClipQueue, CastClip, ProjectileFx, TakeDamageClip, AnimatedEntity and AnimationFSM
with three actors. The retained fixture is
`tests/game/fixtures/neuroclient_magic_missile_timing.json`. This is a detached
source-intent timing oracle; texture/font/GPU/diagnostic IO is substituted, not
the runtime timing formula. It is not an SDK/event-mapper or GPU pixel proof.

| Original flat source execution, 1 ms pump | A1 | B1 | A2 |
| --- | ---: | ---: | ---: |
| Launch | 667 ms | 747 ms | 827 ms |
| Arrival / TakingHit start | 867 ms | 951 ms | 1027 ms |
| HP / number callback | 868 ms | 952 ms | 1028 ms |
| Resulting HP | 75 | 75 | 73 |

The source caster becomes Idle at 1167 ms. B settles at 2118 ms; both A reaction
waiters settle together at 2194 ms, completing the one queued cast. A reenters
TakingHit instead of queuing a second full body animation. All 66 observed body
frames match Python. The source's frame-zero callback runs on the next 1 ms
actor update; the tests check that exact boundary, while the absolute Python
sampler applies the authored frame-zero value at arrival. Existing Fire Bolt
oracle output remains byte-for-byte identical after extending the generator.

The raised scene retains the earlier height-aware travel metric: its actual
first-cast arrivals are 866.945, 1005.687 and 1026.945 ms, with completion at
2193.612 ms. Source-flat B's 951 ms is not the raised-map B arrival. Camera
rotation and visual arc/basis corrections do not change the compiled clock.

**Explicit rendering adaptations.** Geometry has its own point/trail sample and
no fake sprite asset, atlas row or canvas offset. The source retains eight
actual rendered trail points; Python uses eight points on a fixed 60 Hz reference
cadence so seeking does not depend on previously rendered frames. The whole
trail shares its head's painter depth, as in the original geometry drawer.

Actual captures showed a low launch inherited from the source helper forcing
an actor-art root despite the point recipe's `tileCenter` basis. Geometry now
honors that existing ground basis in projection. Sprite registration and the
compiler's reference endpoints stay unchanged. Authored local offsets still
scale with the actor; no new hand-offset catalog or per-spell drawing branch
was introduced. The data remains original and byte-preserved.

A second observed issue was an above-floor dart disappearing under its own
target tile near arrival. Its authored vertical lift was still being interpreted
as ground displacement during inverse projection. Keeping that lift in visual
height preserves the rendered point while restoring the corresponding ground
depth. Forward/side offsets and the screen-space curve remain planar. The map
regression reproduced zero visible pixels from a 104-pixel head before this
correction. Neither correction changes the mechanics ray or routes around walls.

The whole-tile painter can still cover approaching darts from the reverse views.
Final release+200 captures show A1's near-target head covered in quadrant 2;
quadrant 0 now shows that head, while A2 can still disappear mid-flight near the
front terrace. Those are the concrete frames for the next visual review.
The numerical four-view check distinguishes that remaining cell-ordering limit
from the corrected vertical-lift accounting. Do not claim universal terrain
occlusion correctness, invent collision requirements, or conceal the remaining
case with an overlay. The next visual review has actual frames to inspect before
selecting a change to path placement or the existing painter.

**Reproduction.** Run `python -m game --magic-missile --replace-weapon` for the
real Pygame window, or append `--headless --capture-dir .runtime/missiles` for the
same finite loop with controlled frame deltas. Normal Fire Bolt, miss, Goblin,
lethal, gear and detached reference variants retain their entrypoints. The
Magic Missile option selects the two living modular recipients and is mutually
exclusive with the Fire Bolt outcome variants.

Original runtime fixture generation is offline only:

```sh
/path/to/native/bun devtools/trace_neuroclient_animation.ts \
  --source-app /home/tommaso/Dev/NeuroClient/app \
  --data-root game/data/neuroclient --magic-missile \
  --output tests/game/fixtures/neuroclient_magic_missile_timing.json
```

The current native Bun is
`/home/tommaso/.npm/_npx/5c4f1b4a21be27f7/node_modules/@oven/bun-linux-x64-baseline/bin/bun`.
Neither that executable nor the source checkout is a game runtime dependency.


**Verification and final scope.** The session exercised the following boundaries;
counts are per run, with overlap between regression selections:

- Ten public retained cast/miss/equipment/Magic Missile history cases passed,
  including replay after engine reset (29.13 s).
- Nine actual Pygame playback cases passed, including both Magic Missile variants,
  pause/latest independence and historical gear (62.57 s).
- Thirty-six drawing, map and imported-source cases passed (15.85 s), plus seven
  retained-appearance cases (1.76 s).
- The final affected pure timing, space, volley and near-impact map selection
  passed all 119 cases. The geometry-basis eight-case check and lift-depth
  four-case check were observed failing before their corrections. The map
  head-visibility regression likewise failed before the lift-depth correction.
- The new two-case source-oracle acceptance passed; its combined run with the
  existing animation file passed 60 cases (4.78 s). The original Fire Bolt
  fixture was regenerated separately and compared byte for byte.
- Current changed production modules and the selected changed/new tests pass
  Pyright. Four import-DAG/direction/local-import/TYPE_CHECKING checks passed
  (5.79 s); all 81 enumerated importer outputs reproduce with `--check`.

The final actual X11 run completed two casts and six separate roots, including
26 published equipment samples, then matched historical to latest. The
100-frame recording spans 5.06 wall-clock seconds; it uses actual display-flip
timestamps rather than an invented video speed. Recorders, images, before/after
comparisons, MP4 and GIF live under `.runtime/magic-missile-play/`. The reference
screens use the real captured map and actor state. Four camera views were
inspected. This is a finite script proof, not unrestricted player action input
or a claim that the whole game is finished.

The diff measured against this session's preserved starting files adds 307 net
runtime Python lines and 110 net offline-oracle TypeScript lines. Ten original
Special1 PNGs add 1,409,000 bytes; the selected NeuroClient set is now 62 PNGs /
8,448,567 bytes. The new source timing fixture is 61,252 bytes. Earlier untracked
recovery work and imported source JSON must not be attributed to this session.
No backend mechanics file or imported source JSON was edited here.

Anti-slop review checked existing authoring, one-body repeated hits, preserved
application identities, geometry/source discrepancies and the demonstrated
pixel failures before accepting their corrections. Anti-OOP review checked
lineage joins, passive data, the unchanged pending queue, real public action
execution and historical commit after publication. The independent numerical
review of lift depth preserved projected pixels in all four views and explicitly
identified the remaining reverse-view whole-tile ordering limit. No new
manager, reflection bypass, mechanics-interception rule or parallel scheduler
was introduced.
