# Missing-log narrative dispositions — independent anti-slop review

Date: 2026-10-05. Read-only production audit. Scope: every concrete member of `game/player_facts.py:PlayerFact`, current `game/presentation_text.py`, projected wording and two archived permitted-input galleries. This is a finite fact-consumer recommendation, **not** approval of full narrative coverage and not a new content registry.

## Evidence and significant findings

`missing-log-corpus.json` records counts and exact first unlogged node witnesses. Corpus: 298 original all-spell inputs and 50 repair inputs, 348 files. Counts deduplicate UUID inside each file, not across files/observer perspectives. These are archived data, not fresh production results. Only `input.json.sequence.lineages.events` was inspected; private native recordings and final rendered pixels were not used.

Every 312 applied-damage fact in this sample lacks a direct log, while all 312 damage-request facts have a log. A concrete pair is recorded by the corpus witness: applied event `e353eda8-db52-471a-9f24-70d4c7f15af6` and request event `97e199ae-0a9f-414c-b396-027adce6e236` share resolution lineage `97df2c5e-a998-4800-81f4-20321bbc937c`; the request's projected log says “Target takes 4 lightning”. Therefore **unlogged applied damage is not automatically missing narrative**. Adding a second line for every unlogged applied fact would double-report normal damage. Request wording describes its completed result; do not treat that wording as permission to infer damage from a request fact without a result.

All sampled unlogged attack/spell examples inspected were canceled: Sanctuary attack and suppressed Fireball application. A generic “attacks/casts successfully” fallback is wrong. Node phase/canceled/cancellation and application identity must be checked before wording.

Of the original 298-file corpus, 97 unlogged condition facts are state updates: Concentrating 84, Mirror Image 4, Barkskin 4, Heroes' Feast 3, Harm 2. A blanket “gains condition” template would invent reapplications. Condition-state changes require comparison of the committed before/after public values, or inspection-only disposition when that comparison is unavailable.

30 unlogged object destruction records include spell construction retirement. `ObjectDestroyedFact` does not universally mean “smashed”: removal of an expired force panel is not physical destruction damage. Prefer neutral disappearance/removal without a witnessed destructive outcome.

## Complete finite disposition table

“Fallback” means only if the exact occurrence/outcome has no projected wording already covering it. Existing logs remain preferred. “Inspection” means update current known state without fabricating a new event sentence. Names and positions must come from permitted values at the event's commit, never final/latest state or catalog guesses.

| Concrete fact | Disposition and exact authoritative fields | Must not infer / duplicate |
|---|---|---|
| AttackFact | Fallback for permitted attempt/outcome from `source_entity_uuid`, target kind/UUID, `name`, `attack_outcome`; cancellation takes precedence. | Damage amount, successful hit from mere target, ammunition consumption. Canceled no-outcome attack is an attempt/interruption, not a hit. |
| SpellFact | Root cast/attempt and distinct disclosed application outcome; use `name`, `application`, `attack_outcome`, `suppressions`, cancellation. | Every application is not a new cast. A/B/A occurrences remain distinct; propagation batches are not casts. Empty/unknown reach does not mean failed spell. |
| AreaReachFact | Silent bookkeeping: `stage_index`, newly reached cells, destruction prerequisites link propagation. | No second explosion or “cast again” sentence. May annotate an actual causal outcome, not emit cell-list prose by default. |
| MovementFact | Fallback actual move summary from start/end, `trajectory`, `movement_mode`, disclosed path. | `requested_end_position` is not achieved destination; root and committed steps must not each summarize the whole move. |
| StepFact | Fallback committed visible step only (`committed`, from/to, disclosed path, mode). Usually detail under owning move. | Uncommitted step must not imply arrival. Hidden path continuation must remain hidden. |
| ForcedMovementFact | Fallback target displaced, actual start/end/distance, `landing_kind`, `drop_feet`. | Do not compute falling damage or Prone; those require their own outcomes. |
| PortalTransferFact | Fallback committed transfer using only disclosed endpoint(s), `portal_content_id` where public. | Do not reveal the other endpoint when absent; do not duplicate movement and portal-arrival outcome. |
| ShoveFact | Fallback attempt/contest success with `contest_success`, `knocked_prone`, `push_distance`. | No success if unset; displacement child remains authority for actual result. |
| DamageRequestFact | Silent as a fact fallback. Retain existing completed projected log when present and link to resolution. | Requested damage is not applied damage. No inferred shield/Relentless Rage intervention prose without disclosed intervention evidence. |
| DamageResultFact | Fallback actual `applied_damage`, `damage_type`, target, resulting HP only if not already covered by same-resolution damage log. | Do not suppress solely because ancestor has any log. Do not duplicate matching request's completed log. Zero damage is legitimate. |
| SavingThrowFact | Fallback save success/failure using ability/target/`succeeded`; explicit reroll may supply detail. | Success does not universally mean zero damage or no condition. |
| HealFact | Fallback `actual_healing` / `was_blocked`, target and permitted source. | Zero healing is not necessarily blocked; don't calculate healing from final HP. |
| TemporaryHitPointsFact | Fallback “now has N temporary HP” from `resulting_temporary_hp`; grant identity distinguishes replacement. | Value is after-total, not gained delta. Unknown donor remains unknown. |
| LifeFact | Fallback actual `previous_state` → `new_state`, `reason`; dying/dead/stable/alive must stay distinct. | No death from HP alone; no assumed corpse destruction from death art. |
| DeathSaveFact | Fallback this save's `succeeded`, optional disclosed natural roll. | One roll does not establish death/stability; LifeFact owns that. |
| EquipmentFact | Inspection always. Fallback equipment/loadout **change** only with a permitted prior snapshot and exact difference in `visual_loadout`/controlled items. | Snapshot re-emission is not equip action; inventory membership is not proof of pickup/drop. |
| ConditionChangeFact | Application/removal/consumption fallback for non-INTERNAL condition by event_type/name/UUID. State-change suppression, duplicate count, etc. only from explicit before/after fields. | State refresh is not reapplication. INTERNAL bookkeeping silent. Suppressed condition still exists; do not narrate removal. |
| ItemEffectChangeFact | Fallback item effect applied/removed/changed from `event_type`, `effect_uuid`, `item_uuid`, and permitted effect state at the commit. | Fact alone has no display name/palette; don't invent one or call it a creature condition. |
| SpatialFact | Inspection by default. Creation witness and terminal departure allow fallback creation/despawn; explicit public object appearance/removal can be neutral. | Perceivability change is not birth/death; ordinary movement occupancy changes must not duplicate movement. Respect `creation`, `terminal_departure`, `terminal_cause`. |
| FactionFact | Fallback explicit `control_lost` / known `faction_after` change. | Loss of control does not itself prove hostility/attack; no guessed faction if absent. |
| TurnFact | Fallback turn/round boundary from `event_type`, entity, round. Can group round bookkeeping in UI. | No narration of condition ticking unless its actual outcome exists. |
| ItemChargeFact | Inspection/resource detail from `charges_after`, `stack_count_after`, `item_destroyed`, optional `resource_change`. Fallback meaningful public resource loss/change if needed. | No fabricated expenditure delta or item use reason from after-total. No new ammunition mechanics. |
| ActionFact | Fallback named permitted action/attempt; reaction outcome uses `reaction.succeeded` and triggering lineage. | Name alone does not prove effect. Failed/canceled reaction must not read as successful action. |
| SensoryFact | Silent diff bookkeeping; inspection consumes permitted contact/light/access/spatial changes. A purposeful discovery notification can reference an actually acquired contact. | Contact loss is not departure/death. New contact is not summoning. Never narrate hidden cause from `cause_event_uuid`. |
| SpatialEffectStateFact | Fallback explicit operation/state/pressed transition; public creation/removal/activation using exact operation and affected subset. | Repeated same-state bookkeeping is silent; don't invent trap effects or full removal from subset. |
| MechanismActivationFact | Fallback committed mechanism discharge/activation, permitted origin/direction/target/affected cells. | Unknown origin stays unknown; don't infer hit/damage from affected cells. |
| ObjectDamageFact | Fallback actual object damage/remaining HP from explicit fields. | No assumed destruction at zero; destruction outcome is separate. |
| ObjectDestroyedFact | Fallback removal or witnessed break with `destruction_outcome`, `affected_volume`, `resulting_placement`, `remnant_state`; retain public identity before removal. | Expiry/removal is not smash. Partial section break is not whole object destroyed. |

Nodes with no fact but a projected log are legitimate wording sources (1,579 sampled); do not drop them while introducing fact dispatch. Nodes with neither fact nor log are causal structure/bookkeeping, not missing prose (7,247 sampled).

## Minimal integration, timing and duplicate boundaries

1. Keep the existing projected log path. Add a finite typed fact fallback function beside it, not a spell-name/behavior registry. Use passive existing facts and optional committed before/after public state. Explicit silent cases are part of coverage, not missing implementations.
2. Distinguish a missing direct log from a missing outcome. Damage request/result is the concrete mandatory same-resolution join. Generic ancestor-log suppression is forbidden: “uses Fire Shield” does not describe a later damage, condition or disappearance. Do not deduplicate repeated applications by target, name, text or damage value.
3. If generic coverage metadata is eventually needed, it should be passive semantic evidence ownership on the existing narrative row, not regex parsing of prose or a second spell configuration. Start only with proven finite relationships (especially same-resolution damage). Do not guess that every aggregate contains every child fact.
4. Fallback outcome lines use exact commit evidence; root reconciliation remains a latest safe fallback, never an instruction to replay all children. Cancellation/attempt prose cannot imply success. Preserve event UUID/source-version ordering and zero-time admission.
5. State inspection is a distinct channel. Public before/after state is required for equipment, condition-state and charge delta descriptions. If unavailable, state after-value or remain silent; do not compare against latest state.
6. Future motion/gesture/material prose is authored rendering semantics, separate from fact outcomes. The table closes neither that work nor complete inspection coverage.

## Evidence gaps and acceptance requirements

This corpus contains no `shove`, `death_save`, `object_damage`, or `mechanism_activation` witness. Their dispositions above come from declared source fields, not runtime demonstrations. Newer summoning/drop/reappearance details are also not certified by these old galleries. Current typed aliases must remain the denominator.

Before claiming complete narrative outcomes, require tests with: damage request+result once and result-only once; canceled attack/spell; repeated A/B/A applications; condition state update versus real application and suppression; expiry versus broken object section; committed versus rejected transfer; retained unseen actor state versus actual discovery; zero-time action; reaction nested in movement. Run through both observer projections. This is focused evidence for the finite consumer, not a request for a new replay engine.

Verdict: existing projected-log reuse remains sound. A naive “all unlogged facts get sentences” implementation is rejected because the archived evidence proves it would duplicate damage, invent condition applications and misdescribe canceled casts and expired constructions. The table provides the concrete completion path while preserving current ECS and causal owners.
