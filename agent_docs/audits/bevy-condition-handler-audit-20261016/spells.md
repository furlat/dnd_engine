# Spell conditions and handler audit — 2026-10-16

## Scope and evidence limits

Follow-up: [spells-integration.md](spells-integration.md) closes the integration-site reading gaps explicitly left below. Its I8 and the independent native exposure review narrow F3's Silence warning to a conditional implementation ambiguity: supported fixed-origin Silence exposes no demonstrated footprint-movement blocker and requires no alias framework in advance. Read the later conclusion rather than treating the initial warning as a mandatory design requirement.

Read `AGENTS.md`, `RECOVERY_PLAN.md`, the Bevy design, actual spell condition/processor bodies, and the called spatial transition seam. Reconciled against `inventory.json` partition `spells`: **21 files; 106 condition declarations; 3 specialized handler declarations; 83 handler construction/processor argument sites (80 plain EventHandler constructions plus 3 specialized constructions); 57 registration/direct-dispatch sites; 3 contextual-modifier callable argument sites; 121 condition constructions; 633 interaction-call sites**. These categories overlap and are not counts of independent behaviors. Inherited area installation and `bind_spatial_interactions` create additional runtime handlers without another spell-file constructor.

All 106 condition declarations were inspected at their source-defined method/data boundary; all 83 processor-site callback bodies were read, including the external `Frightened.retreat_step_for_source` callback and the native spatial-transition binder. This is source review, not translated gameplay qualification. The appendices identify each condition and callback site. Calls into common condition admission/removal, value composition, event dispatch, damage, movement, and perception are obligations for the companion audits; this review does not independently re-audit every callee. The 121 condition-construction and 633 interaction-call rows include ordinary spell action bodies: they were inventoried, **not all reviewed line by line**. In particular, every ordinary spell's damage/target selection/cast-claim flow is not certified here. `catalog_content.py` and `content_metadata.py` are inventoried composition metadata, not a fully reviewed dynamic-content admission implementation. No native implementation or tests were changed/run.

## Findings and concrete execution mapping

### F1 — Applied-result consumers require continuations, not enqueue-only substitution

**Guardian of Faith** (`conjuration.py:4565-4599`) takes `EventQueue.event_cursor()`, calls damage, scans subsequent `DamageAppliedEvent` COMPLETION records with source/target/parent ancestry checks, adds **applied**, not requested damage to `zone.damage_dealt`, and retires the guardian at the budget. Enqueue-only damage makes the scan run before any applied result and leaves the budget unchanged. Concurrent different recipients also share this budget and retirement authority.

Map the zone to `GuardianBudget { dealt, limit }`, the invocation to an identified request carrying original causal IDs and admission order, and the damage result to a retained canonical event handle. An ordinary native system submits the request and yields; its continuation waits for the exact required damage completion, reads the same filtered applied result, commits the shared budget and completes retirement before a later dependent trigger consumes the zone. Serial budget/retirement commitment is necessary even when target components differ. A resource-wide cursor interval alone is unsafe after yielding because unrelated roots can publish inside it; use exact ancestry/root membership. Design sections 17/21 acknowledge accepted results and causal membership but do not provide this concrete translation or proof.

Narrow proof: concurrent A/B entry requests at a near-exhausted guardian budget; reduced/canceled damage; nested retaliation; source/guardian retirement during damage; verify applied tally, later trigger eligibility, and exactly one retirement. Do not substitute a requested-damage reservation without proving equivalent over-budget semantics.

### F2 — Invocation-local reentrancy guards outlive submission

Gust of Wind (`evocation.py:3027-3079`) inserts the target in `_pushes_in_flight`, performs save/forced movement through `_apply_gust_push` (`3149-3201`), then clears it in `finally`. Nested entry while this move is executing sees the guard. Clearing the guard immediately after queue submission permits recursive pushes that source code suppresses. Retain a `(zone,target,invocation)` guard until dependent movement settles or fails; make cleanup idempotent on both paths. The movement consumer must release borrows before nested rule execution and re-read current position afterward. This is a semantic dependency across invocations, not a guarantee supplied by Bevy's component access analysis. Design has general reentry/continuation mechanisms; this spell-specific guard-lifetime proof is missing.

Eyebite Panicked (`necromancy.py:1169-1248`) similarly reads updated navigation, action economy, position and sight after Dash and Move. Command Flee (`enchantment.py:1778-1828`) moves before spending the remaining turn. Their continuation cannot apply turn caps before movement, and cannot use pre-move sight to decide the ending rule.

### F3 — Captured values have distinct alias policies

Silence's spell blocker captures `zone_positions = self.affected_positions` (`illusion.py:1306`); it tests that retained set object. Globe and Antimagic read `self.affected_positions` on each call (`abjuration.py:1205-1242,3450-3487`). A blanket rewrite to a current footprint query silently changes Silence when the footprint set is replaced. A blanket frozen copy also loses mutations to the captured original set. Use explicit captured-set identity/version data, or demonstrate that every allowed Silence lifecycle leaves these observations equivalent before simplifying. Do not invent a gameplay fix during the port.

Shield's attack interception captures a live NumericalModifier object (`abjuration.py:223-234`); Mirror Image captures its condition and mutates an existing AC modifier by its exact ID (`illusion.py:1102-1141`). Source-turn expiry captures `armed`, application turn and an expiry callable (`evocation.py:2035-2074`); Guiding Bolt captures a decrementing two-end counter (`2595-2638`); Divine Word captures a one-element mutable rounds list (`5196-5228`). Each installed instance needs its own typed component state. Sharing one system-local counter for all instances, copying these values per invocation, or exposing them as untracked global mutable closure state is wrong.

The design specifies typed retained state generally; no proof currently covers these alias distinctions, mutable callback state across yield, or destruction of an installed owner while a selected callback still retains it. Native storage supports these representations; that is not semantic proof.

### F4 — Reactions combine event changes, payments and children with different acceptance rules

Shield (`abjuration.py:283-356`) mutates live attack AC, consumes reaction/slot, calls buff admission, and returns MISS; it does **not** condition its result on successful buff admission. Magic Missile Shield similarly spends and cancels the dart. Design section 14 already explicitly preserves this; classify it **covered in design, unproven**, not a new missing rule. Translate through typed actor resources, canonical attack/value access, exact condition request and continuation; payment and attack result must not disappear because admission vetoed.

Counterspell (`945-1071`) depends on live sight/contact, enemy relation, range, current resources, incoming base/upcast level and selected learned casting source; it spends before its raw d20 check and completes its reaction evidence before returning cancellation. Hellish Rebuke (`infernal.py:127-234`) selects an exact current learned source/resource, consumes resources, creates child action phases, saves/damages the attacker and completes before returning the incoming event. Different triggering targets do not establish independence when the same reaction/slot/resource owner or learned-source set is shared. Query read/write sets plus explicit resource/selection claims and deterministic RNG ordering are needed; actor-wide payments should be committed in admitted reaction order.

Death Ward (`abjuration.py:2028-2055`) previews actual HP damage, consumes removal and returns a normal-HP damage cap or cancels instant death. Sanctuary (`2854-2956`) waits for an attacker save before cancellation, then separately removes its exact ward only on an actual harmful effect against enemies; positional roots and convolution children have different target evidence. Both need ordered nested outcome/removal work. Sanctuary can make one cast application depend on another actor’s save and shared ward lifetime; Death Ward has one-use membership and HP dependencies.

### F5 — Roll modification and one-use removal form an ordered chain

Guidance (`divination.py:257-287`), Resistance (`abjuration.py:2472-2494`), Bane/Bless (`enchantment.py:1244-1271`) read the effective prior roll, draw a d4, replace the roll with retained reason evidence, and, for one-use effects, remove the condition with the modified event as parent. Beacon of Hope (`abjuration.py:3092-3118`) resolves retained dice identity to maximize actual dice while retaining bonus. `fire_heal_roll_result` (`spell_utils.py:41-78`) explicitly deep-copies the original roll into final roll before Effect interception, completes it, and returns the accepted final roll.

Map roll/value records to typed retained components and modifier payloads to installed condition data. Each event's interception cursor waits for the previous accepted roll version and required removal invocation. Distinct roll requests can still conflict on one-use condition membership and RNG. Do not turn these into unordered observer side effects or assume one output per recipient per tick.

### F6 — Removal and repeat saves depend on exact effect identity and source-specific source-retirement policy

Hold Person/Monster, Fear, Blindness/Deafness, Slowed, Prismatic Restrained, Sickened, Sunburst, Power Word Stun use saved effect UUIDs, DCs and source UUIDs. Several remove themselves when the caster disappears (e.g. `enchantment.py:282-285`), whereas Power Word Stun and Sunburst construct saving requests from the retained source identity without requiring a live caster (`1125-1155`; `evocation.py:2137-2163`). The source-turn expiry helper instead falls back to ROUND_END if source absent, undeployed or dead. A universal source-despawn cascade or universal freeze-at-install policy would conflate these actual policies.

Each callback reads typed membership, source presence/life and saving context components and queues save/removal with explicit dependencies; preserve the callback's original exact identity check before work and define the accepted continuation boundary if membership changes during its child save. Sleep, Hypnotic Pattern and Eyebite Asleep wake on the installed DAMAGE_APPLIED event path, not merely attempted raw damage. Their removal must settle before the next capability-sensitive operation. These mechanisms fit the design but each policy branch remains unqualified.

### F7 — Shared manifestations and independent source clocks forbid tree cleanup

Hold Monster/Power Word Stun reuse a pre-existing Paralyzed/Stunned child and add shared parents; Hold Person has a distinct child-admission policy (`enchantment.py:216-255,441-479,1077-1113`). Fear and Hypnotic Pattern also admit their parent effect even when a child did not complete. Preserve these differences instead of replacing all with a generic all-or-nothing compound operation. Solar blindness shares one Blinded child (`evocation.py:2077-2084`); Silence and Color Spray use shared sensory admission. Web/Entangle/Tentacles leases and Spirit Guardians slow have exact source memberships (`conjuration.py:2180-2213`).

Harm and Heroes' Feast (`necromancy.py:1838-1962`; `conjuration.py:4713-4850`) select the strongest unsuppressed, unexpired source, breaking ties by application order from `EventQueue.event_cursor()`. They mutate an existing public manifestation modifier; switching winners does not reapply a condition. Harm clamps maximum HP to at least one and preserves normal HP; Feast grants the positive increase only for a newly committing stronger serving, not again on old-source fallback. Removing the public manifestation retires sources; source removal refreshes winner and publishes owner state at membership change.

Use source/manifestation entities with explicit multi-parent graph edges, mutable modifier record and typed winner selection. Serialize graph/winner/HP commitment for a shared manifestation; source applications with different IDs still conflict. Do not replace source application order with worker finish order. Generic graph and suppression design already addresses representation; neither generic relationship support nor the queue probe qualifies these source-winner and HP effects.

### F8 — Antimagic couples global handlers, owned tokens, items and retained presence

`abjuration.py:3199-3535`: installation/footprint change scans areas/items/entities, registers spell protection and global item handlers; exact provider UUID tokens gate contributions. It skips concentration and magical child roots as authored, preserves HP across suppression, refreshes contribution lights/perceivability and publishes changed condition snapshots. Retained summon/object return handlers explicitly run while suppressed and are installed on the **existence/creation condition**, not automatically on the field. Object return may remain pending while occupied; saved placement is restored or retained on failure. Zone removal separates runtime release from publication-time unsuppression and area refresh.

Map provider sets, active/pending presence, creation/existence owners and exact handler links to typed components; native systems query relevant collections and mutate suppression, HP, grid, lights and history. Initial broad scans require conservative world/grid/index access. Later indexed optimizations must preserve semantic reach: parent contribution suppression can change descendants outside the parent's cell. Cross-target jobs can conflict through one item, global field, shared child, occupancy return cell, or nested item publication. Do not claim these loops are independent because each iteration names a different actor. Generic design covers retained authority and exact tokens; no translated proof covers the complete reentrant refresh path or overlapping field removal.

### F9 — Prepared spatial cleanup and return have preflight, commitment and publication phases

Banished (`abjuration.py:1375-1478`) records original plane, suspends presence, uses terminal-release context, reserves/validates a prepared return or records pending return, and publishes only after membership changes. SolidWall (`wall_constructions.py:184-394`) prepares every section retirement and cancels the whole preparation when one refuses; failed formation uses a different cleanup route; committed removal clears deferred break events before section retirement so concentration expiry does not create new cold remnants. Destroying an ice section instead calls `leave_frigid_air` and links the admitted remnant. Stone permanence changes duration/tags and unlinks concentration at its authored progress boundary.

Use typed prepared-return/retirement work and reserved occupancy resources, explicit graph admission/commitment and separate publication jobs; these may initially be native exclusive owner systems. Release component borrows before nested admission and validate again afterward. Commands/despawn alone cannot replace vetoable retirement, reservation validation, publication or failed-formation cleanup. Design describes these principles but the source-specific branches require translated parity witnesses.

### F10 — Spatial interactions are rule processors behind indirect installation

Four spell sites call `bind_spatial_interactions`: Web `conjuration.py:1116`, Cloudkill `1864`, Fog Cloud `2627`, Stinking Cloud `3849`. The called binder (`dnd/spatial/transitions.py:104-149`) installs a position-indexed EventHandler with a closure retaining condition, transitions and optional builder. `apply_spatial_interaction` (`42-101`) intersects cells/layers, chooses the strongest admitted row, schedules delayed retirement or removes cells; secondary activation must succeed before removing original cells. Replacement admission passes exact replacing condition UUID.

Wind Wall (`wall_fields.py:175-194`) reacts to cloud CREATED/FOOTPRINT_CHANGED COMPLETION as well as source turn start; it ignores its own change and nonintersecting clouds, then publishes a multi-phase disperse child. Sleet Storm emits douse interactions and separately douses currently exposed floor/carried items; Gust emits wind exposure. These callbacks query and mutate other owners and may recursively publish the event families that selected them. Store transition definitions as immutable authored data, invoke a native typed transition system with exact condition/event handles, retain replacement dependencies, and revalidate relevant footprint/index revision after admitted changes. Coalescing computations cannot erase separate causes/rows or bypass first-per-turn admission. General queued environmental design fits; this indirect handler family needs an actual proof, not merely counting 80 direct constructors.

Source-retirement behavior also varies within damaging zones: `wall_fields.py:46-49` and `walls.py:116-119` stop damage if the caster is absent; Cloudkill/Insect Plague/Incendiary Cloud/Spike Growth instead construct a zero base bonus when the caster is missing. Preserve this distinction with retained source identity plus an optional live source query. Spike Growth (`transmutation.py:154-185`) applies damage from each admitted spatial entry, excludes the source and parses its authored damage dice; no save dependency is introduced by that processor.

### F11 — Capability and inventory changes have exact owners beyond numerical modifier maps

See Invisibility/True Seeing/Darkvision commit exact sense-mode sources and notify after membership changes. Light/Continual Flame/Sunbeam/Fire Shield separate removed-light preparation from committed spatial publication (`evocation.py:4309,4436,3520,5300`). Continual Flame reanchors from floor object to equipped holder, suspends light when placement unavailable/destroyed, and retains condition identity. Shillelagh (`transmutation.py:2121-2166`) installs an exact weapon override and removes it on exact unequip or committed weapon-set change; its handler runs while suppressed. Expeditious Retreat installs BonusDash and removes its action by authored name; Haste installs an exact restricted action grant on commit and removes that owner on release, then applies Lethargy only after committed removal and outside terminal release. Slowed maintains action/bonus exclusion and multiplicity limits independently of its numerical modifiers. Fly grants/removes exact speed-source ownership.

Map each source set/override/grant/light record to typed component data with exact owner IDs; use domain lifecycle systems and explicit sensory/publication fences. Broad generic cleanup of modifiers alone leaks authority. A condition being suppressed must not stop its native duration/required release handlers, and must not be confused with lifetime removal. Basic numerical effect families use typed contribution maps (AC, saves, speeds, resistance, constraints), but Mage Armor and Enlarge/Reduce also mutate/restore stored mode/size; retain those side effects and their rollback/removal behavior. The design recognizes source-set lifetimes; individual installation/cleanup parity remains unproven.

### F12 — Custom callables and temporary execution identity are concrete seams

Three AST contextual modifier sites: poison save advantage (`abjuration.py:1882`, callable `1907` checks legacy `condition_context == 'Poisoned'`), Chill Touch (`necromancy.py:196`, partial binds caster), Attack Curse (`2180`, local callback compares current target with saved caster). Additional callable paths escape that count: Freedom of Movement immunity callback (`abjuration.py:2458`) reads incoming condition/tags context; Panicked passes `Frightened.frightener_in_senses_disadvantage` through a transform helper and installs the retreat partial. These require typed context/evaluator registrations with actual Query read sets; a function pointer alone does not declare hidden reads of senses/grid/membership. No Rust scripting ABI is implied.

SummonSpell (`summoning.py:38-96`) performs unpublished admission, temporarily registers a detached selected action for effect/direct admitted-system dispatch, then unregisters in finally. Queuing direct dispatch across that finally needs the selected invocation to remain addressable until logical dispatch settles; retaining only a template/provider ID loses this exact action. The existing design explicitly supplies selected-execution lifetime and pending invocation ownership, so classify as covered/unproven. No named pre-completion callback registration API occurs directly in the spell files searched; saves/damage/removal/movement/lighting child calls and membership callbacks are nevertheless mechanically pre-completion work. Zero direct API matches does not establish absence of pre-completion dependencies.

## Antislop verdict and narrow proofs

Native typed components, queries, resources, relationships and scheduled/exclusive systems can represent these reviewed rules without a domain object hierarchy. That statement does not establish all callback behavior is currently exposed, all work is freely parallel, queue semantics are complete, or the port is qualified. The existing mechanism examples demonstrate much smaller causal graphs. Independent targets alone are insufficient in every family above: reaction budgets, source winner sets, mutable values, guards, spatial claims, global handler reads, RNG, retirement and observation are real conflicts.

Prioritize **Guardian applied-budget continuation**, **Gust guard lifetime**, **Silence captured-set alias**, **shared Harm/Feast winner/HP under suppression**, **retained selected summon execution**, and **overlapping Antimagic item/presence return**. Existing Shield/Counterspell, committed working-view isolation, and shared-child removal probes remain needed; they should be reported as existing design qualification work rather than newly discovered impossibility. No claim here establishes a speedup or multithreaded gameplay execution.

## Appendix A — every inventoried condition declaration

Each row records source-defined boundary review and the interaction family above. Inherited mechanisms are identified through the declared bases and require the companion foundation audit. “No local methods” denotes data-only specialization, not missing runtime behavior.

| File:line / condition | Local method bodies at reviewed boundary | Finding |
| --- | --- | --- |
| `dnd/spells/abjuration.py:156` **ShieldBuff** | _apply:179, _post_removal_stats:276 | F4 |
| `dnd/spells/abjuration.py:422` **MageArmorCondition** | _apply:437, _remove:507 | F11 |
| `dnd/spells/abjuration.py:617` **ProtectionFromEnergyEffect** | snapshot_state:627, _apply:630 | F11 |
| `dnd/spells/abjuration.py:765` **StoneskinEffect** | _apply:778 | F11 |
| `dnd/spells/abjuration.py:1134` **GlobeZone** | _compute_positions:1161, _apply:1171, _release_owned_runtime_state:1192, _create_spell_blocker:1201, _create_condition_blocker:1253 | F8 |
| `dnd/spells/abjuration.py:1375` **BanishedCondition** | _apply:1390, _release_owned_runtime_state:1410, prepare_removal_state:1426, cancel_prepared_removal:1439, prepared_removal_occupancies:1444, validate_prepared_removal:1447, _remove:1451, on_membership_changed:1464 | F9 |
| `dnd/spells/abjuration.py:1841` **ProtectionFromPoisonEffect** | _apply:1851, _remove:1899 | F12 |
| `dnd/spells/abjuration.py:2007` **DeathWardEffect** | _apply:2017 | F4 |
| `dnd/spells/abjuration.py:2327` **FreedomOfMovementEffect** | _apply:2341, _remove:2363 | F12 |
| `dnd/spells/abjuration.py:2497` **ResistanceEffect** | _apply:2506 | F5 |
| `dnd/spells/abjuration.py:2591` **ShieldOfFaithEffect** | _apply:2600, _post_removal_stats:2626 | F11 |
| `dnd/spells/abjuration.py:2695` **AidEffect** | _apply:2705, _post_removal_stats:2733 | F11 |
| `dnd/spells/abjuration.py:2808` **SanctuaryEffect** | _apply:2823, _create_ward_handler:2847, _create_break_handler:2909 | F4 |
| `dnd/spells/abjuration.py:3046` **BeaconOfHopeEffect** | _apply:3055, _create_heal_maximizer:3087 | F5 |
| `dnd/spells/abjuration.py:3243` **AntimagicFieldZone** | _apply:3263, _refresh_items:3285, _publish_item:3330, _item_changed:3338, _refresh_areas:3342, _release_owned_runtime_state:3347, publish_runtime_owner_removal:3353, _apply_appearance_effect:3358, _set_suppression:3361, _suppress_entity:3383, _unsuppress_entity:3414, _unsuppress_all_entities:3428, _create_spell_blocker:3449, _change_footprint:3495, _create_zone_entry_handler:3516, _create_zone_exit_handler:3526 | F8 |
| `dnd/spells/conjuration.py:643` **GreaseZone** | _apply_slip_save:687, _apply_appearance_effect:707, _create_zone_entry_handler:717, _create_zone_turn_end_handler:744 | F10 |
| `dnd/spells/conjuration.py:904` **WebRestrained** | get_display_name:915 | F7 |
| `dnd/spells/conjuration.py:937` **WebZone** | get_spatial_observation:976, restraint_check_dc:1004, _apply_restraint_save:1007, _apply_appearance_effect:1026, _create_zone_entry_handler:1035, _create_zone_turn_start_handler:1057, _create_unanchored_collapse_handler:1085, _apply:1112 | F10 |
| `dnd/spells/conjuration.py:1290` **EntangleRestrained** | No local methods; inherited SpatialRestraintSource | F7 |
| `dnd/spells/conjuration.py:1311` **EntangleZone** | restraint_check_dc:1346, _apply_appearance_effect:1349 | F10 |
| `dnd/spells/conjuration.py:1498` **BlackTentaclesRestrained** | No local methods; inherited SpatialRestraintSource | F7 |
| `dnd/spells/conjuration.py:1522` **BlackTentaclesZone** | restraint_check_dc:1566, _deal_tentacle_damage:1569, _save_or_apply:1602, _create_zone_entry_handler:1620, _create_zone_turn_start_handler:1645 | F10 |
| `dnd/spells/conjuration.py:1802` **CloudkillZone** | _apply:1855, _apply_poison_damage:1872, _create_zone_entry_handler:1917, _create_zone_turn_start_handler:1944, _create_auto_move_handler:1974 | F10 |
| `dnd/spells/conjuration.py:2140` **SpiritGuardiansSlowed** | _apply:2153 | F7 |
| `dnd/spells/conjuration.py:2180` **SpiritGuardiansSlowSource** | create_manifestation:2185, _apply:2189 | F7 |
| `dnd/spells/conjuration.py:2220` **SpiritGuardiansZone** | get_spatial_observation:2271, membership_source_class:2276, membership_applies_to:2281, is_hazardous_for:2284, _affect_enemy:2289, _apply_effect_entry_effect:2335, _apply_effect_exit_effect:2344, _admit_trigger:2352, _create_zone_entry_handler:2364, _create_zone_turn_start_handler:2389, _create_zone_exit_handler:2419 | F7 |
| `dnd/spells/conjuration.py:2591` **FogCloudZone** | _apply:2619 | F10 |
| `dnd/spells/conjuration.py:2775` **DarknessZone** | No local methods; inherited AreaCondition | F10 |
| `dnd/spells/conjuration.py:2976` **DaylightZone** | No local methods; inherited AreaCondition | F10 |
| `dnd/spells/conjuration.py:3176` **InsectPlagueZone** | _damage_entity:3214, _apply_appearance_effect:3258, _create_zone_entry_handler:3268, _create_zone_turn_end_handler:3289 | F10 |
| `dnd/spells/conjuration.py:3415` **IncendiaryCloudZone** | _damage_entity:3459, _apply_appearance_effect:3503, _apply:3513, _create_zone_entry_handler:3520, _create_zone_turn_end_handler:3541, _create_auto_move_handler:3566 | F10 |
| `dnd/spells/conjuration.py:3692` **NauseatedCondition** | _apply:3701 | F10 |
| `dnd/spells/conjuration.py:3755` **StinkingCloudZone** | _create_zone_turn_start_handler:3791, _apply:3844 | F10 |
| `dnd/spells/conjuration.py:3958` **SleetStormZone** | _area_shape:3999, _save:4003, _douse_item_if_exposed:4012, _entity_carried_items:4029, _douse_exposed_flames_at:4036, douse_exposed_flames:4070, _emit_dousing_interaction:4084, _create_exposed_flame_handler:4107, _create_zone_entry_handler:4133, _create_zone_turn_start_handler:4162, _apply:4201 | F10 |
| `dnd/spells/conjuration.py:4494` **GuardianOfFaithZone** | _compute_affected_positions:4528, is_hazardous_for:4539, progress_spatial_duration:4546, _admit_trigger:4554, _create_zone_entry_handler:4562 | F1 |
| `dnd/spells/conjuration.py:4713` **HeroesFeastBuff** | _apply:4723, source_uuids:4741, refresh:4744, publish_owner_state:4763, _remove:4771, _release_owned_runtime_state:4782, on_membership_changed:4789 | F7 |
| `dnd/spells/conjuration.py:4799` **HeroesFeastSource** | model_post_init:4810, _apply:4814, _commit_application:4830, on_suppression_changed:4834, _remove:4840, on_membership_changed:4847 | F7 |
| `dnd/spells/conjuration.py:4987` **HeroesFeastLifetime** | progress_spatial_duration:5000 | F11 |
| `dnd/spells/divination.py:28` **SeeInvisibilityEffect** | _apply:37, _commit_application:43, _release_owned_runtime_state:51, on_membership_changed:58 | F11 |
| `dnd/spells/divination.py:139` **TrueSeeingEffect** | _apply:148, _commit_application:154, _release_owned_runtime_state:162, on_membership_changed:169 | F11 |
| `dnd/spells/divination.py:290` **GuidanceEffect** | _apply:299 | F5 |
| `dnd/spells/enchantment.py:205` **HoldPersonEffect** | _apply:216, _create_repeat_save_handler:257 | F6 |
| `dnd/spells/enchantment.py:429` **HoldMonsterEffect** | _apply:441, _create_repeat_save_handler:481 | F6 |
| `dnd/spells/enchantment.py:809` **SleepEffect** | _apply:829, _create_wake_on_damage_handler:855 | F6 |
| `dnd/spells/enchantment.py:1066` **PowerWordStunEffect** | _apply:1077, _create_repeat_save_handler:1115 | F6 |
| `dnd/spells/enchantment.py:1274` **BaneEffect** | _apply:1286 | F5 |
| `dnd/spells/enchantment.py:1327` **BlessEffect** | _apply:1339 | F5 |
| `dnd/spells/enchantment.py:1558` **CommandNextTurnEffect** | _apply:1575, _target_if_active:1602, _canonical_name:1615, _create_turn_start_handler:1624, _create_turn_end_handler:1664, _spend_commanded_turn:1702, _activate_commanded_turn:1713, _application_status:1718 | F11 |
| `dnd/spells/enchantment.py:1723` **CommandGrovelEffect** | _activate_commanded_turn:1732, _application_status:1743 | F11 |
| `dnd/spells/enchantment.py:1748` **CommandHaltEffect** | _application_status:1760 | F11 |
| `dnd/spells/enchantment.py:1765` **CommandFleeEffect** | _activate_commanded_turn:1778, _application_status:1827 | F2 |
| `dnd/spells/evocation.py:262` **RayOfFrostEffect** | _apply:277 | F6 |
| `dnd/spells/evocation.py:2087` **SunburstBlindedEffect** | _apply:2101, _create_repeat_save_handler:2127 | F6 |
| `dnd/spells/evocation.py:2507` **GuidingBoltMarked** | _apply:2524, _create_remove_on_attack_handler:2559, _create_caster_turn_expiry_handler:2595 | F3 |
| `dnd/spells/evocation.py:2946` **GustOfWindZone** | get_spatial_observation:2983, _compute_affected_positions:3004, _create_zone_entry_handler:3022, _create_zone_turn_start_handler:3053, _emit_wind_exposure:3092, _create_wind_exposure_turn_handler:3113, _apply:3137 | F2 |
| `dnd/spells/evocation.py:3315` **IceStormTerrain** | _apply:3333 | F6 |
| `dnd/spells/evocation.py:3501` **SunbeamBlindedEffect** | _apply:3507 | F6 |
| `dnd/spells/evocation.py:3520` **SunbeamEffect** | _apply:3530, _release_owned_runtime_state:3543, on_membership_changed:3550 | F11 |
| `dnd/spells/evocation.py:3848` **PrismaticRestrained** | _apply:3855, _create_repeat_save_handler:3882 | F6 |
| `dnd/spells/evocation.py:4309` **LightEffect** | _apply:4317, _release_owned_runtime_state:4341, on_membership_changed:4348 | F11 |
| `dnd/spells/evocation.py:4436` **ContinualFlameCondition** | snapshot_item_effect:4447, _commit_application:4453, on_owner_placement_committed:4456, _release_owned_runtime_state:4482, on_membership_changed:4490 | F11 |
| `dnd/spells/evocation.py:5105` **DivineWordEffect** | _apply:5112, _create_duration_handler:5196 | F3 |
| `dnd/spells/evocation.py:5300` **FireShieldEffect** | snapshot_state:5312, _apply:5316, _release_owned_runtime_state:5371, on_membership_changed:5383 | F11 |
| `dnd/spells/illusion.py:59` **BlurEffect** | _apply:68 | F11 |
| `dnd/spells/illusion.py:176` **FearEffect** | _apply:189, _create_repeat_save_handler:229 | F6 |
| `dnd/spells/illusion.py:413` **HypnoticPatternEffect** | _apply:434, _create_damage_break_handler:479 | F6 |
| `dnd/spells/illusion.py:648` **ColorSprayEffect** | _apply:657 | F7 |
| `dnd/spells/illusion.py:1018` **MirrorImageEffect** | snapshot_state:1036, _apply:1042, _post_removal_stats:1090, _create_miss_handler:1097 | F3 |
| `dnd/spells/illusion.py:1237` **SilenceZone** | get_spatial_observation:1270, membership_source_class:1288, _apply:1293, _create_spell_block_handler:1304 | F3 |
| `dnd/spells/illusion.py:1332` **_SilenceDeafened** | create_manifestation:1339, _apply:1346 | F7 |
| `dnd/spells/necromancy.py:129` **NoHealing** | No local methods; inherited BaseCondition | F11 |
| `dnd/spells/necromancy.py:137` **ChillTouchEffect** | undead_attack_disadvantage:162, _apply:179 | F12 |
| `dnd/spells/necromancy.py:537` **BlindnessDeafnessEffect** | _apply:549, _create_repeat_save_handler:578 | F6 |
| `dnd/spells/necromancy.py:928` **SickenedCondition** | _apply:944, _create_repeat_save_handler:986 | F6 |
| `dnd/spells/necromancy.py:1028` **EyebiteAsleepEffect** | _apply:1051, _wake_on_damage:1076 | F6 |
| `dnd/spells/necromancy.py:1083` **EyebitePanickedEffect** | model_post_init:1099, get_display_name:1104, _apply:1107, _distance_feet:1144, _path_cost_feet:1151, _path_is_hazardous:1161, _should_end:1169, _choose_flee_path:1176, _move_along_flee_path:1210, _create_flee_handler:1215 | F2 |
| `dnd/spells/necromancy.py:1263` **EyebiteCastingState** | No local methods; inherited ConcentrationActionMarker | F11 |
| `dnd/spells/necromancy.py:1838` **HarmEffect** | _apply:1848, source_uuids:1857, refresh:1860, publish_owner_state:1879, _remove:1889, on_membership_changed:1900 | F7 |
| `dnd/spells/necromancy.py:1910` **HarmSource** | model_post_init:1920, _apply:1924, _commit_application:1940, on_suppression_changed:1944, _remove:1950, on_membership_changed:1958 | F7 |
| `dnd/spells/necromancy.py:2079` **AbilityCurseEffect** | _apply:2096 | F12 |
| `dnd/spells/necromancy.py:2136` **AttackCurseEffect** | _apply:2153 | F12 |
| `dnd/spells/necromancy.py:2197` **InactionCurseEffect** | _apply:2217, _create_turn_start_handler:2241, _create_turn_end_handler:2300, _remove:2332 | F11 |
| `dnd/spells/necromancy.py:2343` **DamageCurseEffect** | _apply:2360, _create_damage_handler:2382 | F12 |
| `dnd/spells/transmutation.py:107` **SpikeGrowthZone** | model_post_init:143, _create_zone_entry_handler:148 | F10 |
| `dnd/spells/transmutation.py:303` **SlowedEffect** | _apply:322, _post_removal_stats:386, _release_owned_runtime_state:392, _create_repeat_save_handler:400 | F6 |
| `dnd/spells/transmutation.py:585` **HasteLethargyEffect** | _apply:602 | F11 |
| `dnd/spells/transmutation.py:621` **HasteEffect** | _apply:640, _post_removal_stats:687, _commit_application:693, _release_owned_runtime_state:727, on_membership_changed:732 | F11 |
| `dnd/spells/transmutation.py:827` **DarkvisionEffect** | _apply:836, _commit_application:842, _release_owned_runtime_state:850, on_membership_changed:857 | F11 |
| `dnd/spells/transmutation.py:1077` **JumpEffect** | _apply:1085 | F11 |
| `dnd/spells/transmutation.py:1217` **ExpeditiousRetreatEffect** | _apply:1223, _remove:1240 | F11 |
| `dnd/spells/transmutation.py:1286` **EnhanceAbilityEffect** | snapshot_state:1295, _apply:1298 | F11 |
| `dnd/spells/transmutation.py:1433` **EnlargeReduceEffect** | snapshot_state:1445, _apply:1448, _remove:1493 | F11 |
| `dnd/spells/transmutation.py:1851` **RegeneratingEffect** | _apply:1865, _on_turn_start:1893 | F6 |
| `dnd/spells/transmutation.py:1998` **LongstriderEffect** | _apply:2004 | F11 |
| `dnd/spells/transmutation.py:2042` **BarkskinEffect** | _apply:2048 | F11 |
| `dnd/spells/transmutation.py:2076` **FlyEffect** | _apply:2083, _remove:2090, _release_owned_runtime_state:2096 | F11 |
| `dnd/spells/transmutation.py:2121` **ShillelaghEffect** | snapshot_state:2129, _apply:2132, _release_owned_runtime_state:2161 | F11 |
| `dnd/spells/wall_constructions.py:38` **FrigidAirZone** | resolve_condition_footprint:47, admits_occupancy_transition:51, _occupancy_admits_trigger:57, get_trigger_positions:62, damage_contact_position:68 | F9 |
| `dnd/spells/wall_constructions.py:184` **SolidWallZone** | _commit_activation_footprint:204, resolve_condition_footprint:222, antimagic_exempt:225, allows_contribution_at:228, refresh_antimagic_suppression:231, blocks_crossing_between:240, blocks_physical_optics_at:250, get_spatial_observation:253, on_section_destroyed:262, leave_frigid_air:279, publish_removal_effect:293, prepare_removal_state:299, _prepare_section_retirements:305, cancel_prepared_removal:323, _release_owned_runtime_state:335, publish_runtime_owner_removal:363, progress:377 | F9 |
| `dnd/spells/wall_constructions.py:397` **WallOfIceZone** | No local methods; inherited SolidWallZone | F9 |
| `dnd/spells/wall_constructions.py:405` **WallOfStoneZone** | No local methods; inherited SolidWallZone | F9 |
| `dnd/spells/wall_constructions.py:414` **WallOfForceZone** | No local methods; inherited SolidWallZone | F9 |
| `dnd/spells/wall_fields.py:66` **WallFieldZone** | resolve_condition_footprint:80, get_spatial_observation:83, _apply_appearance_effect:90, admits_occupancy_transition:95, _create_zone_entry_handler:103, damage_contact_position:116, _create_zone_turn_end_handler:119 | F10 |
| `dnd/spells/wall_fields.py:131` **WallOfThornsZone** | No local methods; inherited WallFieldZone | F10 |
| `dnd/spells/wall_fields.py:143` **WindWallZone** | blocks_crossing_between:153, missile_deflection_contact:161, _emit_wind_exposure:165, _apply:175 | F10 |
| `dnd/spells/walls.py:42` **WallOfFireZone** | resolve_condition_footprint:67, _heat_reaches:86, get_trigger_positions:90, admits_occupancy_transition:95, blocks_physical_optics_at:104, get_spatial_observation:107, _deal_damage:117, _apply_appearance_effect:151, _create_zone_entry_handler:154, _create_zone_turn_end_handler:167 | F10 |

## Appendix B — every direct processor argument site

All listed callback bodies were read. Site numbers are constructor lines, not callback definition lines. Scope disambiguates repeated `processor`/`process` names; the callback expressions come directly from the AST inventory. Policy/trigger keywords remain in `inventory.json`; these rows do not claim one unique processor behavior per site. Indirect spatial binder closures are separately traced in F10.

| File:site | Installing scope / callback |
| --- | --- |
| `dnd/spells/abjuration.py:211` | `dnd.spells.abjuration.ShieldBuff._apply` → `shield_magic_missile_blocker` |
| `dnd/spells/abjuration.py:236` | `dnd.spells.abjuration.ShieldBuff._apply` → `shield_attack_interception` |
| `dnd/spells/abjuration.py:253` | `dnd.spells.abjuration.ShieldBuff._apply` → `shield_turn_start_processor` |
| `dnd/spells/abjuration.py:390` | `dnd.spells.abjuration.create_shield_reaction_handler` → `shield_reaction_processor` |
| `dnd/spells/abjuration.py:484` | `dnd.spells.abjuration.MageArmorCondition._apply` → `mage_armor_equip_processor` |
| `dnd/spells/abjuration.py:1093` | `dnd.spells.abjuration.create_counterspell_reaction_handler` → `counterspell_reaction_processor if learned_spell_ref is None else partial(counterspell_reaction_processor, learned_spell_ref=learned_spell_ref)` |
| `dnd/spells/abjuration.py:1244` | `dnd.spells.abjuration.GlobeZone._create_spell_blocker` → `processor` |
| `dnd/spells/abjuration.py:1304` | `dnd.spells.abjuration.GlobeZone._create_condition_blocker` → `processor` |
| `dnd/spells/abjuration.py:2058` | `dnd.spells.abjuration.DeathWardEffect._apply` → `death_ward_processor` |
| `dnd/spells/abjuration.py:2514` | `dnd.spells.abjuration.ResistanceEffect._apply` → `_resistance_processor` |
| `dnd/spells/abjuration.py:2891` | `dnd.spells.abjuration.SanctuaryEffect._create_ward_handler` → `processor` |
| `dnd/spells/abjuration.py:2958` | `dnd.spells.abjuration.SanctuaryEffect._create_break_handler` → `processor` |
| `dnd/spells/abjuration.py:3120` | `dnd.spells.abjuration.BeaconOfHopeEffect._create_heal_maximizer` → `processor` |
| `dnd/spells/abjuration.py:3268` | `dnd.spells.abjuration.AntimagicFieldZone._apply` → `self._item_changed` |
| `dnd/spells/abjuration.py:3315` | `dnd.spells.abjuration.AntimagicFieldZone._refresh_items` → `partial(_refresh_antimagic_created_object, item_uuid=item.uuid)` |
| `dnd/spells/abjuration.py:3403` | `dnd.spells.abjuration.AntimagicFieldZone._suppress_entity` → `partial(_refresh_antimagic_summon_presence, entity_uuid=entity.uuid)` |
| `dnd/spells/abjuration.py:3488` | `dnd.spells.abjuration.AntimagicFieldZone._create_spell_blocker` → `block` |
| `dnd/spells/abjuration.py:3522` | `dnd.spells.abjuration.AntimagicFieldZone._create_zone_entry_handler` → `entered` |
| `dnd/spells/abjuration.py:3534` | `dnd.spells.abjuration.AntimagicFieldZone._create_zone_exit_handler` → `left` |
| `dnd/spells/conjuration.py:734` | `dnd.spells.conjuration.GreaseZone._create_zone_entry_handler` → `processor` |
| `dnd/spells/conjuration.py:764` | `dnd.spells.conjuration.GreaseZone._create_zone_turn_end_handler` → `processor` |
| `dnd/spells/conjuration.py:1047` | `dnd.spells.conjuration.WebZone._create_zone_entry_handler` → `processor` |
| `dnd/spells/conjuration.py:1075` | `dnd.spells.conjuration.WebZone._create_zone_turn_start_handler` → `processor` |
| `dnd/spells/conjuration.py:1101` | `dnd.spells.conjuration.WebZone._create_unanchored_collapse_handler` → `processor` |
| `dnd/spells/conjuration.py:1635` | `dnd.spells.conjuration.BlackTentaclesZone._create_zone_entry_handler` → `processor` |
| `dnd/spells/conjuration.py:1661` | `dnd.spells.conjuration.BlackTentaclesZone._create_zone_turn_start_handler` → `processor` |
| `dnd/spells/conjuration.py:1934` | `dnd.spells.conjuration.CloudkillZone._create_zone_entry_handler` → `processor` |
| `dnd/spells/conjuration.py:1964` | `dnd.spells.conjuration.CloudkillZone._create_zone_turn_start_handler` → `processor` |
| `dnd/spells/conjuration.py:2011` | `dnd.spells.conjuration.CloudkillZone._create_auto_move_handler` → `processor` |
| `dnd/spells/conjuration.py:2379` | `dnd.spells.conjuration.SpiritGuardiansZone._create_zone_entry_handler` → `processor` |
| `dnd/spells/conjuration.py:2409` | `dnd.spells.conjuration.SpiritGuardiansZone._create_zone_turn_start_handler` → `processor` |
| `dnd/spells/conjuration.py:2439` | `dnd.spells.conjuration.SpiritGuardiansZone._create_zone_exit_handler` → `processor` |
| `dnd/spells/conjuration.py:3279` | `dnd.spells.conjuration.InsectPlagueZone._create_zone_entry_handler` → `processor` |
| `dnd/spells/conjuration.py:3304` | `dnd.spells.conjuration.InsectPlagueZone._create_zone_turn_end_handler` → `processor` |
| `dnd/spells/conjuration.py:3531` | `dnd.spells.conjuration.IncendiaryCloudZone._create_zone_entry_handler` → `processor` |
| `dnd/spells/conjuration.py:3556` | `dnd.spells.conjuration.IncendiaryCloudZone._create_zone_turn_end_handler` → `processor` |
| `dnd/spells/conjuration.py:3595` | `dnd.spells.conjuration.IncendiaryCloudZone._create_auto_move_handler` → `processor` |
| `dnd/spells/conjuration.py:3834` | `dnd.spells.conjuration.StinkingCloudZone._create_zone_turn_start_handler` → `processor` |
| `dnd/spells/conjuration.py:4123` | `dnd.spells.conjuration.SleetStormZone._create_exposed_flame_handler` → `processor` |
| `dnd/spells/conjuration.py:4152` | `dnd.spells.conjuration.SleetStormZone._create_zone_entry_handler` → `processor` |
| `dnd/spells/conjuration.py:4191` | `dnd.spells.conjuration.SleetStormZone._create_zone_turn_start_handler` → `processor` |
| `dnd/spells/conjuration.py:4602` | `dnd.spells.conjuration.GuardianOfFaithZone._create_zone_entry_handler` → `damage_hostile` |
| `dnd/spells/divination.py:322` | `dnd.spells.divination.GuidanceEffect._apply` → `_guidance_processor` |
| `dnd/spells/enchantment.py:300` | `dnd.spells.enchantment.HoldPersonEffect._create_repeat_save_handler` → `repeat_save_processor` |
| `dnd/spells/enchantment.py:520` | `dnd.spells.enchantment.HoldMonsterEffect._create_repeat_save_handler` → `repeat_save_processor` |
| `dnd/spells/enchantment.py:877` | `dnd.spells.enchantment.SleepEffect._create_wake_on_damage_handler` → `wake_processor` |
| `dnd/spells/enchantment.py:1158` | `dnd.spells.enchantment.PowerWordStunEffect._create_repeat_save_handler` → `repeat_save_processor` |
| `dnd/spells/enchantment.py:1301` | `dnd.spells.enchantment.BaneEffect._apply` → `_bane_processor` |
| `dnd/spells/enchantment.py:1354` | `dnd.spells.enchantment.BlessEffect._apply` → `_bless_processor` |
| `dnd/spells/enchantment.py:1650` | `dnd.spells.enchantment.CommandNextTurnEffect._create_turn_start_handler` → `processor` |
| `dnd/spells/enchantment.py:1688` | `dnd.spells.enchantment.CommandNextTurnEffect._create_turn_end_handler` → `processor` |
| `dnd/spells/evocation.py:2064` | `dnd.spells.evocation._source_turn_expiry_handler` → `processor` |
| `dnd/spells/evocation.py:2165` | `dnd.spells.evocation.SunburstBlindedEffect._create_repeat_save_handler` → `repeat_save_processor` |
| `dnd/spells/evocation.py:2583` | `dnd.spells.evocation.GuidingBoltMarked._create_remove_on_attack_handler` → `remove_on_attack_processor` |
| `dnd/spells/evocation.py:2625` | `dnd.spells.evocation.GuidingBoltMarked._create_caster_turn_expiry_handler` → `expire_on_caster_turn_end` |
| `dnd/spells/evocation.py:3043` | `dnd.spells.evocation.GustOfWindZone._create_zone_entry_handler` → `processor` |
| `dnd/spells/evocation.py:3082` | `dnd.spells.evocation.GustOfWindZone._create_zone_turn_start_handler` → `processor` |
| `dnd/spells/evocation.py:3126` | `dnd.spells.evocation.GustOfWindZone._create_wind_exposure_turn_handler` → `processor` |
| `dnd/spells/evocation.py:3915` | `dnd.spells.evocation.PrismaticRestrained._create_repeat_save_handler` → `processor` |
| `dnd/spells/evocation.py:5218` | `dnd.spells.evocation.DivineWordEffect._create_duration_handler` → `processor` |
| `dnd/spells/evocation.py:5360` | `dnd.spells.evocation.FireShieldEffect._apply` → `retaliate` |
| `dnd/spells/illusion.py:276` | `dnd.spells.illusion.FearEffect._create_repeat_save_handler` → `repeat_save_processor` |
| `dnd/spells/illusion.py:500` | `dnd.spells.illusion.HypnoticPatternEffect._create_damage_break_handler` → `damage_break_processor` |
| `dnd/spells/illusion.py:1145` | `dnd.spells.illusion.MirrorImageEffect._create_miss_handler` → `processor` |
| `dnd/spells/illusion.py:1322` | `dnd.spells.illusion.SilenceZone._create_spell_block_handler` → `processor` |
| `dnd/spells/infernal.py:243` | `dnd.spells.infernal.create_hellish_rebuke_reaction_handler` → `partial(_rebuke_processor, spell_ref=HELLISH_REBUKE_SPELL_DECLARATION.ref)` |
| `dnd/spells/necromancy.py:617` | `dnd.spells.necromancy.BlindnessDeafnessEffect._create_repeat_save_handler` → `repeat_save_processor` |
| `dnd/spells/necromancy.py:1016` | `dnd.spells.necromancy.SickenedCondition._create_repeat_save_handler` → `processor` |
| `dnd/spells/necromancy.py:1063` | `dnd.spells.necromancy.EyebiteAsleepEffect._apply` → `self._wake_on_damage` |
| `dnd/spells/necromancy.py:1128` | `dnd.spells.necromancy.EyebitePanickedEffect._apply` → `partial(Frightened.retreat_step_for_source, self.source_entity_uuid, target.uuid)` |
| `dnd/spells/necromancy.py:1251` | `dnd.spells.necromancy.EyebitePanickedEffect._create_flee_handler` → `processor` |
| `dnd/spells/necromancy.py:2288` | `dnd.spells.necromancy.InactionCurseEffect._create_turn_start_handler` → `turn_start_processor` |
| `dnd/spells/necromancy.py:2320` | `dnd.spells.necromancy.InactionCurseEffect._create_turn_end_handler` → `turn_end_processor` |
| `dnd/spells/necromancy.py:2428` | `dnd.spells.necromancy.DamageCurseEffect._create_damage_handler` → `damage_processor` |
| `dnd/spells/transmutation.py:189` | `dnd.spells.transmutation.SpikeGrowthZone._create_zone_entry_handler` → `processor` |
| `dnd/spells/transmutation.py:440` | `dnd.spells.transmutation.SlowedEffect._create_repeat_save_handler` → `processor` |
| `dnd/spells/transmutation.py:1875` | `dnd.spells.transmutation.RegeneratingEffect._apply` → `self._on_turn_start` |
| `dnd/spells/transmutation.py:2152` | `dnd.spells.transmutation.ShillelaghEffect._apply` → `released` |
| `dnd/spells/wall_fields.py:112` | `dnd.spells.wall_fields.WallFieldZone._create_zone_entry_handler` → `process` |
| `dnd/spells/wall_fields.py:126` | `dnd.spells.wall_fields.WallFieldZone._create_zone_turn_end_handler` → `process` |
| `dnd/spells/wall_fields.py:187` | `dnd.spells.wall_fields.WindWallZone._apply` → `process` |
| `dnd/spells/walls.py:161` | `dnd.spells.walls.WallOfFireZone._create_zone_entry_handler` → `process` |
| `dnd/spells/walls.py:173` | `dnd.spells.walls.WallOfFireZone._create_zone_turn_end_handler` → `process` |

## Appendix C — inventory-only coverage and remaining proof limits

| File | Source lines | Conditions | Processor sites | Boundary status |
| --- | --- | --- | --- | --- |
| `dnd/spells/__init__.py` | 6 | 0 | 0 | Inventoried only; no declared condition/direct processor |
| `dnd/spells/abjuration.py` | 3594 | 15 | 19 | Condition/processor boundaries reviewed; ordinary action bodies not exhaustively reviewed |
| `dnd/spells/base.py` | 8 | 0 | 0 | Inventoried only; no declared condition/direct processor |
| `dnd/spells/catalog_content.py` | 1032 | 0 | 0 | Inventoried only; no declared condition/direct processor |
| `dnd/spells/conjuration.py` | 5114 | 23 | 23 | Condition/processor boundaries reviewed; ordinary action bodies not exhaustively reviewed |
| `dnd/spells/content_metadata.py` | 454 | 0 | 0 | Inventoried only; no declared condition/direct processor |
| `dnd/spells/divination.py` | 397 | 3 | 1 | Condition/processor boundaries reviewed; ordinary action bodies not exhaustively reviewed |
| `dnd/spells/effect_ids.py` | 6 | 0 | 0 | Inventoried only; no declared condition/direct processor |
| `dnd/spells/enchantment.py` | 1962 | 10 | 8 | Condition/processor boundaries reviewed; ordinary action bodies not exhaustively reviewed |
| `dnd/spells/evocation.py` | 5430 | 12 | 10 | Condition/processor boundaries reviewed; ordinary action bodies not exhaustively reviewed |
| `dnd/spells/ice_knife.py` | 167 | 0 | 0 | Inventoried only; no declared condition/direct processor |
| `dnd/spells/illusion.py` | 1457 | 7 | 4 | Condition/processor boundaries reviewed; ordinary action bodies not exhaustively reviewed |
| `dnd/spells/infernal.py` | 323 | 0 | 1 | Condition/processor boundaries reviewed; ordinary action bodies not exhaustively reviewed |
| `dnd/spells/necromancy.py` | 2604 | 13 | 8 | Condition/processor boundaries reviewed; ordinary action bodies not exhaustively reviewed |
| `dnd/spells/reaction_spell_content.py` | 235 | 0 | 0 | Inventoried only; no declared condition/direct processor |
| `dnd/spells/spell_utils.py` | 78 | 0 | 0 | Both helpers read; healing roll seam reviewed (F5) |
| `dnd/spells/summoning.py` | 116 | 0 | 0 | SummonSpell admission/dispatch body reviewed (F12) |
| `dnd/spells/transmutation.py` | 2221 | 14 | 4 | Condition/processor boundaries reviewed; ordinary action bodies not exhaustively reviewed |
| `dnd/spells/wall_constructions.py` | 779 | 5 | 0 | Condition/processor boundaries reviewed; ordinary action bodies not exhaustively reviewed |
| `dnd/spells/wall_fields.py` | 377 | 3 | 3 | Condition/processor boundaries reviewed; ordinary action bodies not exhaustively reviewed |
| `dnd/spells/walls.py` | 314 | 1 | 2 | Condition/processor boundaries reviewed; ordinary action bodies not exhaustively reviewed |

Source-defined condition declarations left uninspected: **0 of 106**. Direct processor callback bodies left unread: **0 of 83 sites**. Native gameplay cases qualified in this audit: **0**. Complete transitive call graphs qualified here: **0**. Ordinary action/construction/interaction rows cannot be counted as fully reviewed from this condition-focused audit; they remain explicitly inventory-only except named source excerpts in F1–F12. A full “ALL conditions/handlers/interactions” conclusion must combine companion engine/foundation/spatial audits and separately resolve action-body coverage.
