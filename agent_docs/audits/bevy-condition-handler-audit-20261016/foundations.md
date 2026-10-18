# Foundation and antiOOP audit — 2026-10-16

Scope: source inspection only; no production/test edits, no native execution qualification and no performance claim. Compared the current condition source to `agent_docs/BEVY_REACTIVE_ENGINE_DESIGN_2026-10-16.md`, especially §§6, 14–16, 24–25. Existing proposal already acknowledges shared graphs, provisional contributions, multislot sustain, live contextual evaluation and scoped completion. Those acknowledgments do not prove the cases below.

## Coverage and limits

- Reviewed implementations of all **27 BaseCondition subclasses** in `dnd/conditions.py` (29 top-level classes including ConcentrationSlot and PreparedConcentrationTransfer), all **3** tile condition classes, all **7** foundation classes in `dnd/core/base_conditions.py`, and both classes/protocols in `dnd/core/base_object.py`.
- Reviewed all **11 EventHandler construction sites** in conditions.py; there are zero handler construction/spatial registration sites in base_conditions.py or tile_conditions.py. Handler construction sites: 441, 463, 906, 1106, 1120, 1127, 1134, 2269, 2472, 2669, 2803.
- Reviewed BaseBlock condition data, handler installation/index/order/toggle methods (1003–1128), provisional discard (1129–1182), removal preparation/commit/publication (1235–1685), application and involuntary sustain (1718–1964), immunity ownership (1965–2143), graph participant/scope settlement (270–345).
- Read `dnd/creature_transforms.py` completely (362 lines), because named conditions delegate mechanics to it. Reviewed modifier evaluation (modifiers.py 250–424), scalar/factor representation (51–135), value aggregation/gating/contextual evaluation and exact cleanup in selected values.py spans (399–639, 860–1095, 1292–1335, 1490–1690, 2110–2245, 2450–2598). These files are supporting inspection, **not complete 747/2598-line modifier/value coverage**.
- Unreviewed BaseBlock non-condition spans include general composition, movement/object lifecycle and value/context propagation (346–1002, apart from condition state declarations and referenced hooks); removal public wrappers 1183–1234 and duration publication 1686–1717 were not deeply traced. Entity-level application/save/immunity gates, duration callers, events dispatcher internals, content binding implementation, item sustain owners, spatial conditions, class/spell/monster conditions and capture consumers belong to other reviewers. No claim of all-repository condition coverage from this file.
- This is static source evidence. Exception paths, declared data invariants, graph cycles, retained lifetime and native scheduling still need executable qualification.

## Complete assigned condition inventory

All references below are repository-relative source lines. “Contributions” means exact installed modifier IDs/handler IDs, not a replacement actor implementation.

| Class / source | Actual mechanics and dependencies |
|---|---|
| ExtraAttacksGranted, conditions.py:242 | One-round internal marker; Effect only. |
| HasAttacked :265 | Internal marker; mutable hostile-creature flag. Tracker :362 updates it with OR or creates a one-round condition; checks first phase occurrence and live enemy relation. |
| HasTakenDamage :288 | Internal marker. Tracker :403 creates only when absent, on DAMAGE_APPLIED Effect. |
| Underwater :314 | Contextual disadvantage/automiss installed on attack value. Functions :175/:212 read live bypass flags/swimming speed plus weapon name, range type and long-range context; these are invocation inputs, not installation snapshots. |
| Blinded :483 | Visual-access zero cap, outgoing attacker advantage, own attack disadvantage, sight-skill automiss. Multiple Effect publications while installing. |
| Charmed :531 | Captures charmer/conditioned UUIDs via partials (:582/:605); contextual own attack automiss against charmer and outgoing social advantage. Source/recipient argument direction matters. |
| Dashing :620 | No modifier. on_membership_changed :636 increments live turn dash_count when applied. Removing/replacing marker does not refund earned credit. |
| Deafened :651 | Hearing-skill automiss; no independent hearing system installed here. |
| Exhaustion :725 | Cumulative level transforms: skills, rational half speed, attack/save disadvantage, installation-time computed max-HP penalty, speed caps; level 6 invokes instant death :900 during _apply. Revive handler :906; long rest :770 and revive processor :700 replace/reduce exact condition. |
| Dodging :932 | Incoming attack disadvantage and own Dex-save advantage. No extra sight/movement validity check in this implementation. |
| Disengaging :966 | Owns provokes-opportunity-attacks zero cap through transform. |
| Frightened :1069 | See graph/history witness below. Live visual contact, source lifetime, residue occupancy/topology, movement/elevation and causal history. Four construction sites, with ordinary retreat and residue modes mutually selected. |
| Incapacitated :1352 | FULL_TURN agency + own action_permission/actions/bonus/reaction/all-speed zero caps. |
| Invisible :1390 | grants_invisibility + live unseen attacker/target contextual modifiers; commit/removal records pending notification and membership hook publishes perceivability. |
| Paralyzed :1486 | FULL_TURN; incapacitation + Str/Dex automiss + incoming advantage + contextual within-5-feet autocrit. |
| Petrified :1529 | FULL_TURN; stunned transform; all DamageType resistances; exact source-owned Poisoned immunity :1586; _remove :1597 removes that source. Description mentions disease but this class does not install disease immunity: do not infer behavior from prose. |
| Poisoned :1619 | Attack and all skill disadvantage. |
| Prone :1652 | If own turn/enough movement and opt-out unset, consumes half base movement then cancels application (:1686). Otherwise attack disadvantage + live outgoing distance-sensitive advantage/disadvantage. No stand-up handler constructed here despite description. |
| Stunned :1720 | FULL_TURN; incapacitation + Str/Dex automiss + incoming advantage. |
| Restrained :1762 | All-speed zero caps, attack/Dex-save disadvantage, incoming advantage. |
| Unconscious :1802 | FULL_TURN; paralyzed transform + visual denial + prone geometry; these are directly owned contributions, not required nested named conditions. |
| Concentrating :1867 | Creature **or item** sustainer with identified ordered slots, active-slot routing, exact linked effects, same-name reuse, capacity eviction/rejection, prepared ownership transfer, native occupancy revalidation, rollback, publication and runtime slot cleanup. See witness below. |
| ConcentrationActionMarker :2338 | Marker owns action grant cleanup by exact action UUID, fallback action name; _release_owned_runtime_state covers provisional discard too. |
| NoReactions :2373 | Reaction maximum zero contribution. |
| Hidden :2420 | Live unseen-attacker contextual modifier, creation lineage, commit stealth DC and remaining-source max on release; reveal processor :2525 removes on attack/damage/full-turn-denial application/revealing actions/very-bright light/entry/collision. is_last and lineage gates; light branch can use parent as removal cause. |
| InvisibilityEffect :2592 | Two unseen contextual modifiers; lineage + reveal flags; reveal handler :2669 has **runs_while_suppressed=True**. Attack/cast/revealing action can terminate suppressed membership. |
| GreaterInvisibilityEffect :2723 | Default permanent duration becomes ten rounds. Two unseen modifiers; ordinary (not runs_while_suppressed) handler :2803. Increasing DC = base_dc + check_count; live stealth evaluation + nested d20; success increments count, failure removes; decorates canonical roll event with combat log and completes it. |
| TileEffectCondition, tile_conditions.py:15 | Resolves live authoritative tile through grid, otherwise Effect-only base mechanics. |
| ZoneMarkerCondition :52 | Category-only authored marker. |
| SpikeTrapCondition :58 | Name/description/hazard_filter only; **does not install damage/step handlers**. Do not claim executable trap parity from this class name. |

Foundation classes: Duration (:57) supports rounds, permanent, long-rest and contextual callable expiry (None means unexpired), owns source/target/context and exact condition ID; ConditionApplicationEvent (:167), ConditionStateChangedEvent (:226), ConditionRemovalEvent (:237) retain condition/result facts; BaseCondition (:301) manages contributions/links/preparation/cleanup; SpellProtection (:1296) stores footprint, threshold and antimagic; SpellProtectionRegistry (:1310) supplies live overlap/source-inside/level decisions with multiple independent providers.

Transform details: creature_transforms.py:74 denies action permission and all channels including movement; :98 turn-spent deliberately retains reactions; :208/:231 calculate contextual autocrit/prone geometry from current Senses positions/distances; :295/:309/:322 compose directly owned modifiers rather than child condition actors. Source UUID denotes conditioned defender for outgoing modifiers; evaluator target is the incoming attacker.

## Handler/processor inventory

| Construction → processor | Trigger/observable result |
|---|---|
| conditions.py:441 → has_attacked_processor :362 | ATTACK Execution; nested condition application or mutable marker update; None output still changes world. |
| :463 → has_taken_damage_processor :403 | DAMAGE_APPLIED Effect; nested marker application; None output. |
| :906 → exhaustion_revive_processor :700 | REVIVE Effect restricted to owning source; nested condition-level reduction when ReviveEvent permits it. |
| :1106 → Frightened._on_retreat_step :1255 | STEP_MOVEMENT Effect; compares current source/target sensory/elevation distance and returns cancellation on approach. |
| :1120 → _on_residue_step :1278 | STEP_MOVEMENT Effect; captured condition origin heading; cancels non-outward move. |
| :1127 → _on_residue_exit :1288 | SPATIAL_ENTITY_LEFT Effect; current destination layer and connected residue region determine own-source expiration/removal. LEFT has arrival in old_position, deliberately read as such. |
| :1134 → _on_residue_removed :1301 | SPATIAL_TILE_CHANGED Effect globally; contacted material absence can end own fear source. |
| :2269 → nested concentration_break_processor :2194 | DAMAGE_APPLIED/DEATH Effect targeted owner; captures self.uuid; live owner lookup. Zero HP/death releases involuntary sustain directly; otherwise nested CON save and possible exact sustain release, returned replacement DamageAppliedEvent sets concentration_broken. |
| :2472 → hidden_reveal_processor :2525 | Eight trigger families; is_last + live owner/current named condition + lineage/light/agency gates; nested removal; no replacement output. |
| :2669 → invisibility_reveal_processor :2690 | ATTACK/CAST_SPELL/BASE_ACTION Effect; last/lineage/flags/actions; nested removal; runs while suppressed. |
| :2803 → greater_invisibility_check_processor :2824 | Same three families; last/lineage/actions, random nested stealth check, mutable check_count or removal, explicit check log completion. |

BaseBlock.add_event_handler :1003 binds before admission, associates owner, updates full/simple trigger indexes and registers queue; order mutation :1050 reorders local indexes, not a proof of dispatcher ordering. BaseCondition cleanup removes each exact handler registration and spatial UUID. No assigned condition directly mutates an incoming payload and returns None; several return None after mutations of conditions/roll records/world. Frightened returns cancellation; concentration failure returns a replacement with updates.

## Material qualification gaps / risky cases

Classification: items 1, 4, 5, 6, 7 and 8 are **covered conceptually, unproven** in the existing proposal; this audit supplies concrete counterexample-oriented proof cases. Item 2 is **partially covered conceptually, unproven**: generic shared graphs and zero-duration survival are stated, but exact Frightened source transfer, reverse retirement and causal retreat derivation are not enumerated. Item 3 adds **missing explicit boundary examples**, without establishing that the proposed typed systems cannot represent them. No source-backed impossibility of a Bevy translation was found in this assigned scope.

1. **Graph-wide settlement is more than children-before-parent despawn.** base_block.py:307–345 accumulates nested scope receipts, calls every graph-settled hook, then closes deferred removal completions; exceptions aggregate while attempting remaining work. :1520–1685 admits the whole forward/reverse graph, reuses accepted removals, applies any/last child policies, and changes mandatory removal behavior. :1445 checks all native participants plus return-cell conflicts. :1368 snapshots linked owners before committing reverse order and publishes only changed committed parent state. Required sustain :1937 removes REQUIRED children mandatorily before ordinary slot release. Proposed §§16/19 recognize the policy but have no executable proof of this ordering, double-admission reuse, exception settlement or two returns claiming one cell. Queue dependencies must include graph participants/receipts and exact cause; ordinary Bevy despawn hooks do not express it.

2. **Frightened's lifetime is an active ownership state machine, not just a parent set.** conditions.py:1094 harvests inherited shared parents; :1172 transfers still-live parents on replacement; :1181 avoids retiring transferred parents by inspecting causative ConditionApplicationEvent; :1192 may remove remaining source parents after membership removal. :1156 permits zero-round independent source to survive while additional parents remain; _source_disadvantage then gates the expired own source. :1019 residue_fear_origin walks ancestors and committed movement children, choosing max path_index. :1002 connected-material search reads current map across arbitrary cells. Needed native proof: independent fear + shared source, replacement/veto, remove one source, expire independent source, detach last borrowed parent, suppress/unsuppress each provider, residue enter/teleport/exit/material split. A generic “shared child survives” probe covers only a small part.

3. **Cancellation does not universally reverse side effects.** Prone :1686 spends movement then returns canceled; Exhaustion :900 invokes death while _apply is still producing provisional mechanics. Dashing :636 grants turn-owned credit on committed membership and never refunds it on marker removal. Application rollback releases returned IDs and special _release hooks, not arbitrary world changes (base_conditions.py:967; base_block.py:1152). Preserve authored commitment boundaries and costs; do not introduce transaction-wide undo or assert cancellation means unchanged world. Installation-time Exhaustion max-HP arithmetic must also retain its current semantics unless explicitly changed.

4. **Suppression is graph-sensitive and handler-specific.** BaseCondition.contributions_active :563 recursively reads all live parents; primary-parent and independent-child cases differ. allows_contribution_at :571 adds spatial overlap gating. :586 changes provider tokens without duration/link/ID deletion. BaseObject :71 fails closed for missing contribution owner; graph primary handoff chooses minimum UUID string (:942). Invisibility reveal runs suppressed, greater-invisibility check does not. A blanket Disabled marker, skipping all condition systems, or using only an aggregate active flag loses this. Need independent/multiple providers + shared parents + per-position suppression + handler lifetime test.

5. **Installation phase and contribution authority differ.** BaseCondition.prepare_application :1024 installs contributions, publishes Effect, collects returned handles, then binds their owner (:1092), before membership commitment. Concentrating installs its damage/death handler at commit (:2290), after that binding pass. Proposed “retained payloads without active membership contribute nothing” (§6) needs its explicit provisional exception (§16) carried through every consumer, rather than one membership-only universal gate. A probe must see intended provisional values in the effect handler and prevent unrelated accepted work from leaking speculative values across veto.

Exact gate refinement: `BaseCondition.contributions_active` (:563) never checks `applied` or authoritative membership. Its gate is the registered owner/parent/suppression graph, so adding `With<Applied>` to every contribution read changes provisional behavior. Concentrating._install_concentration_handler (:2269–2285) passes neither `contribution_owner_uuid` nor `runs_while_suppressed`; defaults are **None / False**. `BaseBlock.add_event_handler` binds behavior and owner_block only; no contribution-owner assignment occurs there. This late handler therefore passes the default BaseObject gate independently of the concentration contribution state; event_handlers_uuids still owns cleanup. Automatic native “installed-by implies suppressed-with-owner” would invent a gate absent here. Creature antimagic explicitly skips CONCENTRATION-tagged conditions (abjuration.py:3389–3391), so its damage/death sustain handler continues while child spell benefits can be suppressed. Item sustain does not install this Entity-only handler. Prove both ownership/cleanup and contribution-gating identity separately; this is a concrete refinement to the proposal, not just a generic lifetime note.

6. **Pure-looking evaluation has evidence writes and live inputs.** modifiers.py:331 recomputes each time; catches ordinary exceptions and logs/returns None; writes latest result by source/target/lineage key. execute_callable :378 is a separate strict boundary. Values combine current maps/channels, rational factors and bounds; values.py:2542 explicitly preserves repeated contextual evaluation. Greater invisibility :2890 reads cached explanations and completes the nested roll after log decoration. Query parallelism must return/store invocation-specific explanation evidence; shared last-result storage cannot be authoritative or allow one concurrent evaluation to overwrite another's recorded explanation. No purity guarantee follows from `ContextualModifier` type. No arbitrary contextual callable deduplication proof exists here.

7. **Perception and causal history are mechanics inputs.** Unseen/fear/geometry evaluate current Senses; Hidden reads current light at reaction boundary and event hints; lineage avoids revealing on own creation. residue_fear_origin needs committed ancestors/children, not just a producer's pending-request identity. Delaying refresh/evidence until the whole action ends changes subsequent modifiers and retreat decisions. Freeze or settle the exact required input boundary; a queue fence named “perception” alone is insufficient proof.

8. **Concentration transfer must survive interleaving and partial lifetime.** conditions.py:2100–2335 keeps old owner live through admission, identifies evictions by insertion order, transfers retained slot objects and reverse links, commits old removals without publication, installs new handler, then publishes. Full item capacity rejects; creature capacity evicts. Slot dropping prepares all linked children before mutation, shared graph veto cancels whole drop; no-effects cleanup may remove root. Child unlink removes empty slots and owner-state publication compares retained prior event snapshots. Needed proof: creature capacity 2 + item full reject + same-spell reuse + veto in one evicted child + retained independent spatial child + failed save + death/zero HP + exact action grant cleanup.

Source/documentation caution: BaseCondition.cleanup_own_state (:1235) says `_expire` hooks are preserved, but its implementation calls `_remove`, releases owned state and clears applied; no `._expire(` call was found under `dnd`. Do not infer authored expiration work from that docstring. BaseBlock.advance_duration (:1695, additionally inspected) progresses interval, requests removal on expiration and otherwise publishes duration change; its boolean return is expiry, not proof that vetoable removal committed.

## Native Bevy exposure and antiOOP review

The proposal's native entity/component/system direction fits these source responsibilities **if** translated cases are proven. Suitable concrete storage is: condition data/payload components, exact contribution IDs in typed owner value maps, source and recipient IDs, independent duration component, explicit primary/additional/cross-owner links, typed concentration-slot data with stable order, and per-invocation graph/evaluation state. Native Query/SystemParam access can expose current senses, map/residue and owner resources; handler entities carry processor identity and captured configuration/condition handles. No condition class hierarchy or universal “apply effect” operation interpreter is necessary.

Removal participant registration in Python should become explicit native domain systems and typed admission/receipt data, not `dyn BaseBlock`/`dyn Condition` owners. The source's existing structural Protocol is evidence of capability separation, not a requirement to introduce equivalent domain trait-object dispatch. A typed address index for value IDs is justified by exact modifier cleanup; reflection/getattr routing or a second opaque ECS resource is not.

Safe candidate queueing: passive retained snapshot/log delivery after required causative children settle; immutable map/geometry computations against a named revision; disjoint admitted contribution arithmetic with invocation-owned evidence. Constrained/ordered work: all admission/replacement/cleanup scopes, shared condition graphs, same-recipient marker/credit updates, random saves/check_count, global material/senses reads, source/slot changes, and cancellation/returned-event interception. Distinct recipients do not prove independence because shared source parents, connected material and global hooks can couple them. Native memory conflict checks alone cannot identify those semantic dependencies.

The current mechanism probes establish a useful implementation seam. They do **not** establish full condition-port coverage, the listed graph/lifetime proofs, arbitrary parallel handler safety or a speedup. The design's §25 “no remaining blocking contradiction” should be treated as a reviewed structural hypothesis with these concrete unqualified cases, not a completed behavioral audit.

## AST coverage cross-check

Cross-checked against `inventory.json` foundations partition: 30 condition classes, 11 handler constructors, 11 processor arguments, 13 contextual constructors/13 callable arguments, 9 registrations/direct dispatch sites. The condition and processor tables above are the semantic ledger; exact class spans below prevent blanket file coverage claims. All rows below were implementation-reviewed; native qualification remains unproven.

| Source span | Condition | Inspection |
|---|---|---|
| dnd/conditions.py:242–262 | ExtraAttacksGranted | Reviewed; behavior above |
| dnd/conditions.py:265–285 | HasAttacked | Reviewed; behavior above |
| dnd/conditions.py:288–304 | HasTakenDamage | Reviewed; behavior above |
| dnd/conditions.py:314–359 | Underwater | Reviewed; behavior above |
| dnd/conditions.py:483–521 | Blinded | Reviewed; behavior above |
| dnd/conditions.py:531–610 | Charmed | Reviewed; behavior above |
| dnd/conditions.py:620–641 | Dashing | Reviewed; behavior above |
| dnd/conditions.py:651–672 | Deafened | Reviewed; behavior above |
| dnd/conditions.py:725–922 | Exhaustion | Reviewed; behavior above |
| dnd/conditions.py:932–956 | Dodging | Reviewed; behavior above |
| dnd/conditions.py:966–988 | Disengaging | Reviewed; behavior above |
| dnd/conditions.py:1069–1342 | Frightened | Reviewed; behavior above |
| dnd/conditions.py:1352–1381 | Incapacitated | Reviewed; behavior above |
| dnd/conditions.py:1390–1439 | Invisible | Reviewed; behavior above |
| dnd/conditions.py:1486–1519 | Paralyzed | Reviewed; behavior above |
| dnd/conditions.py:1529–1609 | Petrified | Reviewed; behavior above |
| dnd/conditions.py:1619–1643 | Poisoned | Reviewed; behavior above |
| dnd/conditions.py:1652–1711 | Prone | Reviewed; behavior above |
| dnd/conditions.py:1720–1753 | Stunned | Reviewed; behavior above |
| dnd/conditions.py:1762–1792 | Restrained | Reviewed; behavior above |
| dnd/conditions.py:1802–1835 | Unconscious | Reviewed; behavior above |
| dnd/conditions.py:1867–2335 | Concentrating | Reviewed; behavior above |
| dnd/conditions.py:2338–2363 | ConcentrationActionMarker | Reviewed; behavior above |
| dnd/conditions.py:2373–2410 | NoReactions | Reviewed; behavior above |
| dnd/conditions.py:2420–2516 | Hidden | Reviewed; behavior above |
| dnd/conditions.py:2592–2687 | InvisibilityEffect | Reviewed; behavior above |
| dnd/conditions.py:2723–2821 | GreaterInvisibilityEffect | Reviewed; behavior above |
| dnd/tile_conditions.py:15–49 | TileEffectCondition | Reviewed; behavior above |
| dnd/tile_conditions.py:52–55 | ZoneMarkerCondition | Reviewed; behavior above |
| dnd/tile_conditions.py:58–66 | SpikeTrapCondition | Reviewed; behavior above |

| Source | Handler processor / captured configuration | Inspection |
|---|---|---|
| dnd/conditions.py:441 | `has_attacked_processor` | Reviewed; trigger/result above |
| dnd/conditions.py:463 | `has_taken_damage_processor` | Reviewed; trigger/result above |
| dnd/conditions.py:906 | `exhaustion_revive_processor` | Reviewed; trigger/result above |
| dnd/conditions.py:1106 | `self._on_retreat_step` | Reviewed; trigger/result above |
| dnd/conditions.py:1120 | `self._on_residue_step` | Reviewed; trigger/result above |
| dnd/conditions.py:1127 | `self._on_residue_exit` | Reviewed; trigger/result above |
| dnd/conditions.py:1134 | `self._on_residue_removed` | Reviewed; trigger/result above |
| dnd/conditions.py:2269 | `concentration_break_processor` | Reviewed; trigger/result above |
| dnd/conditions.py:2472 | `hidden_reveal_processor` | Reviewed; trigger/result above |
| dnd/conditions.py:2669 | `invisibility_reveal_processor` | Reviewed; trigger/result above |
| dnd/conditions.py:2803 | `greater_invisibility_check_processor` | Reviewed; trigger/result above |
