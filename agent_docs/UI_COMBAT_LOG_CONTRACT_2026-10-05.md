# Existing combat log: UI contract study — 2026-10-05

Status: source study and specific implementation decisions, not an implementation
or a passing-test report. Inspected working tree at base
`946fb23fe78d371e114ed6e2ef233b98d3069115`; uncommitted source remains relevant.
Read `RECOVERY_PLAN.md`, `agent_docs/USER_COMPLAINTS.md`, the historical companion,
and `HOW_TO_TEST.md`. This study changes no production or test source.

The October 5 removal decision governs this work: display the existing projected
combat log. There is no prose formatter, narrative fallback, transcript schema,
gesture narration, or new event bus. A fact without a combat log remains silent.
Interface labels such as “Details”, “New entries” and “Earlier entries removed”
are controls, not invented outcome sentences.

## 1. Concrete current path

| Owner | Actual behavior and consequence |
| --- | --- |
| `dnd/core/events.py:Event.phase_to` | On COMPLETION, calls the event's existing `generate_combat_log`, records observer grants, collects child logs, enriches multi-target summaries, and sends root logs to the encounter callback. |
| `dnd/core/events.py:Event._collect_child_combat_logs` | Chooses the latest logged version in each direct child lineage. If that child has no log, recursively promotes its logged descendants. Native lineage order determines child order. |
| `dnd/core/events.py:Event.post` | Allocates a fresh version UUID; lineage UUID stays stable. The log callback in `phase_to` occurs **before** this allocation. The callback carrier's UUID must not be mistaken for the posted completion UUID. |
| `dnd/encounter.py:Encounter.add_event_to_combat_log` | Appends one root tree, qualified by EventQueue generation; passive listeners get `(encounter, index, entry, event)`. |
| `dnd/encounter.py:Encounter.project_combat_log_range` | Projects an immutable generation-qualified range with the existing subjective projector. This is also the available owner for standalone informational entries. |
| `game/presentation.py:_capture_lineage` | Retains one terminal event per native lineage, including every descendant, in recorded source order. Canceled roots retain resolved child ancestry. |
| `game/presentation.py:_retained_event` | Invokes `project_combat_log` for each retained event, normalizes log data through JSON, detaches the event. Unsupported event payloads still retain the projected log on a passive header. |
| `game/player_projection.py:_project_nodes` | Copies exact event/lineage/parent/child identities and the projected log into `PlayerNode`. `_action_log` performs an additional foreign Font of Magic amount redaction. |
| `game/player_facts.py:PlayerNode` | Carries UUID, lineage UUID, native ancestry, phase, fact, resolution reference, cancellation and `CombatLogEntry`; it currently omits `turn_execution_id`. |
| `game/encounter_play.py:_log_lines` | Flattens all node compact strings, strips `{style:text}`, deduplicates equal strings. This can drop real repeated events. It does not recursively consume `sub_entries`. |
| `game/encounter_play.py:_run` | Holds 20 strings, draws three with a 170-character cutoff, and appends the whole group at completion. No scroll, detail, links or filters exist. It temporarily draws only the primary root's lines on its completion frame, then appends all reaction roots. Replace this path; do not retain it alongside the new panel. |

`CombatLogEntry` already contains all three verbosity strings, category,
source/target names and UUIDs, success, structured `data` and nested entries.
It has no event UUID. This is not an obstacle for the Pygame player path because
the containing `PlayerNode` already supplies that identity.

## 2. Complete production producer inventory

An AST scan of `dnd/**/*.py` found 31 `CombatLogEntry(...)` constructor sites.
Search of non-test, non-deprecated production Python found no additional sites
outside `dnd`. The two extra branches are blocked damage and blocked healing;
the table groups them by owning function. No producer manually constructs a
synthetic `sub_entries` tree: the central completion collector owns nesting.

| File and function | Entry type / explicit special behavior |
| --- | --- |
| `dnd/actions.py:MovementEvent.generate_combat_log` | MOVEMENT root summary |
| `dnd/actions.py:TraverseConnectorEvent.generate_combat_log` | MOVEMENT connector summary |
| `dnd/actions.py:AttackEvent.generate_combat_log` | ATTACK, attack/AC/damage/HP breakdown |
| `dnd/actions.py:JumpEvent.generate_combat_log` | MOVEMENT jump summary |
| `dnd/actions.py:ShoveEvent.generate_combat_log` | ACTION with shove outcome |
| `dnd/actions.py:SpellEvent.generate_combat_log` | Dispatches multi-target, save, attack, auto-hit or generic existing action wording |
| `dnd/actions.py:SpellEvent._generate_save_spell_log` | SPELL_SAVE, combined save and damage result |
| `dnd/actions.py:SpellEvent._generate_attack_spell_log` | ATTACK spell result |
| `dnd/actions.py:SpellEvent._generate_autohit_spell_log` | SPELL_DAMAGE |
| `dnd/core/base_actions.py:ActionEvent.generate_combat_log` | ACTION |
| `dnd/core/base_actions.py:ActionEvent._generate_multi_target_log` | MULTI_ENTITY_ACTION; collector supplies per-target descendants |
| `dnd/core/base_conditions.py:ConditionApplicationEvent.generate_combat_log` | CONDITION_APPLIED; INTERNAL category deliberately returns None; condition owns its application wording |
| `dnd/core/base_conditions.py:ConditionRemovalEvent.generate_combat_log` | CONDITION_REMOVED; INTERNAL deliberately silent |
| `dnd/core/events.py:SavingThrowEvent.generate_combat_log` | SAVING_THROW |
| `dnd/core/events.py:SkillCheckEvent.generate_combat_log` | SKILL_CHECK |
| `dnd/core/events.py:SpatialEffectChangeEvent.generate_combat_log` | SPATIAL_EFFECT creation/reveal/removal/transformation |
| `dnd/core/events.py:SpatialEffectInteractionEvent.generate_combat_log` | SPATIAL_EFFECT operation, without inferring its result |
| `dnd/core/events.py:ForcedMovementEvent.generate_combat_log` | MOVEMENT |
| `dnd/core/events.py:StepMovementEvent.generate_combat_log` | MOVEMENT; only committed steps produce entries |
| `dnd/core/events.py:DiceRollResultEvent.generate_combat_log` | ROLL_MODIFICATION; only actual modifications produce a log; derived roll families use this owner |
| `dnd/core/events.py:TakeDamageEvent.generate_combat_log` | DAMAGE_TAKEN, normal and canceled branches |
| `dnd/core/events.py:HealEvent.generate_combat_log` | HEAL, normal and blocked branches |
| `dnd/core/events.py:TurnStartEvent.generate_combat_log` | TURN_START |
| `dnd/core/events.py:TurnEndEvent.generate_combat_log` | TURN_END |
| `dnd/core/events.py:DeathSaveEvent.generate_combat_log` | SAVING_THROW with death-save fields |
| `dnd/core/events.py:DeathEvent.generate_combat_log` | DEATH |
| `dnd/spells/abjuration.py:CounterspellReactionEvent.generate_combat_log` | SPELL_INTERRUPTION, success and failed interruption |
| `dnd/conditions.py:greater_invisibility_check_processor` | Presets a SKILL_CHECK entry, then calls normal COMPLETION |
| `dnd/entity.py:Entity._declare_entity_condition` | Immunity entry, CONDITION_APPLIED with `success=False`; calls `EventQueue.push_combat_log` instead of registering a normal event |

`DamageAppliedEvent`, temporary-HP state, many equipment/world facts, sensory
snapshots and generic cancellation do not acquire new sentences from this UI.
ENTITY_SPOTTED and HAZARD_DETECTED exist in the category enum but currently have
no constructor in this production inventory. Support their category values
without claiming current event coverage.

## 3. Canonical rows and exact deduplication decision

**Use each non-null `PlayerNode.combat_log` once. Never recursively render its
`sub_entries`, and never enumerate `data.per_target_logs` as extra rows.** The
embedded trees are existing transport/summary data; their independent owning
nodes are the canonical UI source.

This choice is preferable to stamping every native log producer with another
ID. Complete-lineage capture already retains terminal nodes even when their
typed `fact` is None. It also keeps `_action_log`'s final public redaction; using
a parent's embedded child copy instead can miss that last projection step.

The concrete selection algorithm is:

1. Build the existing `index_player_lineage` index for each received lineage.
2. For each node with a log, create one row keyed by
   `(generation, observer_uuid, node.uuid)`. Retain `node.lineage_uuid` and the
   exact `VersionRow.source_index` for this UUID. The schema already selects one
   terminal node per lineage; do not invent “first/last text wins”.
3. Resolve its displayed parent by walking native `parent_lineage` to the nearest
   ancestor node that has a log. For a canceled node lacking normalized
   `parent_lineage`, resolve its exact `parent_event` through the existing
   `VersionRow.event_uuid -> lineage_uuid` mapping. Skip unlogged intermediary nodes. This reproduces
   the collector's promotion through silent children without matching text,
   names, dictionary equality, target IDs or list positions.
4. Sort siblings by recorded source index. Preserve roots in the received
   completion order. Grouped presentation is a view of that order, not a rewrite
   of `PlayerLineage` ancestry or its reducer cursor.
5. Default-collapse root/action summary rows. A weapon result can contain a
   DAMAGE_TAKEN child and a save-based application can contain a save and damage
   child: those remain selectable detail, not extra flat summaries.
6. An expanded row replaces its own compact text with the chosen existing
   verbose or detailed text; do not stack all three variants. Its child entries
   appear once, indented and individually expandable.
7. Retransmission of an identical key is idempotent. The same key with different
   contents is a malformed delivery, reported as such; do not silently overwrite
   history. Equal text with different event keys always survives.

Rows with no logged ancestor become top-level rows in the same causal group.
A canceled cast can therefore have a disclosed reaction or child log even when
the cast itself has no log. It must not gain a synthetic “cast canceled” row.

There is intentionally no sum of leaf damage rows. The native ATTACK,
SPELL_SAVE, SPELL_DAMAGE and MULTI_ENTITY_ACTION entries already own totals.
`DamageResultFact` is useful timing evidence, but must not become a second damage
sentence. Source summaries can contain overlapping mechanical detail by design;
the collapsed/expanded hierarchy controls repetition.

### Reaction and turn grouping

`game/presentation_group.py:presentation_groups` joins only consecutive reaction
roots whose `ActionFact.reaction.triggered_lineage_uuid` names the following root.
Its `lineages` tuple preserves the native received order. `reduce_presentation_group`
reduces that same order. Reuse this grouping exactly.

- A grouped Counterspell is displayed in the incoming action's group, marked
  as a reaction by its category/icon. Its native parent remains None.
- If the trigger has an eligible logged summary, a reaction's displayed parent
  can be that summary, with an explicitly separate presentation relationship.
  Before the trigger summary becomes eligible, show the reaction as a root row
  in the same neutral group container. Reparent the same keyed row when the
  summary arrives; do not delay a failed Counterspell result until the later
  attack damage. The native parent field is never edited.
- If the incoming cast has no log, the reaction is a visible root row inside
  the group's neutral container. No invisible parent row or invented sentence
  is required.
- An unmatched reaction remains an ordinary root, as it does today. Do not
  search other chats, future packets, names or nearby timestamps to force a match.
- Opportunity attacks and other true native children use native ancestry;
  they must not be reclassified as separately received Counterspell roots.

The exact turn ID is recorded already: `Event.model_post_init` inherits
`turn_execution_id` from its parent or `EventQueue.current_turn_execution_id`;
the encounter owns entering/leaving that turn. `_event_header` and
`ObjectiveRow` preserve it, but `PlayerNode` drops it. Add one optional passive
`turn_execution_id: UUID | None = None` field to `PlayerNode`, copied from the
retained event in `_project_nodes`. This is the only recommended ordinary-node
provenance addition. It changes no native rule, ancestry or timer.

Turn headings use only projected TURN_START/TURN_END labels and their existing
round/index data. Never fetch a hidden turn owner's name from Session. Legacy
packets without the optional turn ID retain received order and existing
projected turn delimiters; do not claim exact historical turn identity for them.

## 4. Timing: reuse the bound graphics dates

The live encounter can advance `latest` while paused history is unchanged. Log
visibility must follow the displayed group and its existing `elapsed_ms`, not
the newest received nodes or native wall-clock timestamp.

Existing owners:

- `game/presentation_timing.py:presentation_milestones` exports state commits,
  attacks/casts, applications, body actions, equipment, damage, healing and
  movement. Application milestones retain `application_id` and exact result
  event UUIDs; motion folds retain their exact input UUIDs.
- `presentation_dependencies` exports producer-recorded `TimingEvidence`,
  including reaction alignment, transfers, formation/clearance and world floors.
  `validate_timing_evidence` verifies recorded arithmetic; it does not schedule.
- `game/choreography.py:StateCommitEvidence` records the exact nodes,
  observations/world updates and version rows actually folded at each date.
- `walk_bound_timelines` applies the existing nested motion/reaction offsets.
  Use it once; do not add offsets twice or date nested reactions at outer zero.
- `MotionStateProvenance.origin` distinguishes a real branch fold from
  `root_reconciliation` and `landing_prefix`. Reconciliation is not another
  occurrence and must never create another log row.

The row's reveal date is a **read-only gate over these existing clocks**. It is
not a scheduler: it never changes a binder date, duration, reduction order,
action readiness, or authored VFX. The panel samples `elapsed_ms >= ready_ms`.
Backward seek re-evaluates eligibility; it does not append another copy.

### Family-specific gates

The following table is the implementation rule. “Owned” means exact native
ancestry / `resolution_ref` / application identity, not shared actor/target or
nearest time. A parent entry's entire compact/verbose/detailed value is gated
at the maximum of its own gate and its canonical logged descendants' gates,
plus exact owned result dates required by the table. This is a conservative
bottom-up rule, not an attempt to parse prose to guess which descendants a
summary mentions. Do not display a compact result early and hope later details
repair it. A reaction's separate presentation relationship does not enter this
native-subtree calculation.

| Existing log family | Reveal gate | Evidence and safe fallback |
| --- | --- | --- |
| ATTACK from weapon or spell, hit | Later of its actual contact, owned damage-result HP commits and its canonical logged descendants' gates. | Action contact, application HP/result UUIDs, state commits, `index_player_lineage.results`. No HP result means use contact for a real resolved no-damage hit, not a fabricated HP update. |
| ATTACK miss | Existing attack contact or that spell application's contact. | Contact marks the resolved miss. Interrupted bindings intentionally suppress contact; then use the actual interruption/result date or group completion, never canceled travel time. |
| SPELL_DAMAGE / SPELL_SAVE application | Application contact plus the maximum owned HP/result date; save-only result uses its actual application contact. | Match `SpellFact.application`, `ResolutionRef` and application ID. A/B/A are distinct applications even with the same target/damage. |
| MULTI_ENTITY_ACTION summary | Maximum semantic reveal date of its projected application/outcome subtree. | The summary already names final observed targets/damage. Showing it at cast release leaks unplayed outcomes. Collapsed summary becomes available after those outcomes; expanded children remain exact separate rows. |
| DAMAGE_TAKEN | The HP date of its exact applied result(s); blocked/no-applied result uses the recorded owner contact/effect. | `damage_requests` / resolution ownership and state commits; standalone damage cue HP. Never create a row from an applied result lacking a log. |
| HEAL | Existing healing cue start / exact heal state commit. | `bind_choreography` appends heal state at this date. Blocked healing has no healing cue: use exact parent effect/contact; if absent, group completion. |
| CONDITION_APPLIED / CONDITION_REMOVED | Exact condition membership commit. | `finish_conditions` appends the condition node at `transition.start_ms`; state commit evidence includes it. Do not wait for the badge/fade tail and do not use an unrelated persistent aura's first creation date. |
| SAVING_THROW / SKILL_CHECK | Exact owned result/effect/contact if the existing binder supplies it; otherwise group completion. | Death saves use their lifecycle cue start. Fact-less skill entries still exist; their absence from typed graphics is not a reason to drop them or guess a zero date. |
| ROLL_MODIFICATION | Owning resolved roll's application/attack result boundary; damage-roll changes wait for the owned result gate. | Exact native parent/resolution identity only. If the graphics projection has no precise roll-result anchor, group completion. No second dice animation or reconstructed roll. |
| MOVEMENT root, jump, connector | End of the last actually bound movement leg or root completion when no leg exists, combined with canonical logged descendants' gates. | Existing motion leg dates and exact provenance. Do not show a destination while the actor is still traveling. Authored recovery may outlast arrival without delaying the factual destination if exact arrival is available. |
| MOVEMENT committed step | Exact branch-fold/arrival date for that step; not root reconciliation. | Motion state provenance names the step's UUID. If only reconciliation names it, use group completion and classify timing as fallback. |
| Forced movement / shove result | Destination/settled arrival for movement text; shove contact for an attempt/outcome that does not claim arrival. | `ForcedMovementCue` contact/arrivals and `ShoveCue.contact_ms`, or their exported dependencies. Portal endpoint consequences follow their independently admitted arrival/settled clocks. |
| Generic ACTION | Existing body effect date combined with canonical logged descendants' gates. | `BodyActionCue.effect_ms`, body milestones. Without a bound effect, group completion. Never choose body start merely because it exists. |
| SPELL_INTERRUPTION | The reacting body's aligned effect date. | `join_reactions` records `reaction_alignment`; reaction body effect is shifted to the incoming effect/cutoff. This works for success and failure and must not use separately stored root completion order as animation timing. |
| SPATIAL_EFFECT | Exact committed world/formation/clearance boundary for a state change; owned parent effect for an interaction description. | State commits plus recorded `world_floor`, `spatial_cause`, `sensory_owner` evidence. Delayed formation must not reveal complete walls early. No exact source means group completion. |
| DEATH | Owned life-transition/result boundary, after any preceding HP fact that the entry describes. | The DeathEvent itself currently projects primarily as a log/header; its exact LifeFact descendants and lifecycle start are the evidence. Do not infer death from a zero HP number. Missing exact life evidence uses group completion. |
| TURN_START / TURN_END | Their existing group boundary; TURN_START uses the bound `turn_starts` boundary if nested. | The text is a turn marker, not a claim that turn-start damage has finished. Round/current actor remain projected facts. No native wall-clock ordering. |
| Standalone informational log | Presentation completion of the native operation containing its captured append. | Its text is real but it has no registered native event/impact owner. Section 6 specifies this conservative boundary explicitly. |

For summary/detail nesting, a child's effective visibility also requires any
displayed ancestor summary to be eligible. Canonical children are open by
default; a Magic Missile cast does not expose its final total before the final missile. There is
no requirement to invent a “casting…” sentence to occupy the card beforehand.
When no logged ancestor exists, the child's own date controls its appearance.

### Specific timing-export gaps and their fixes

The milestone type allows `family='life'`, but `presentation_milestones` does
not currently emit lifecycle cue starts. Add these exact existing values to
that exporter for `timeline.lifecycle`; preserve their event UUID and offsets.
This enables death-save and life-owned parent rows without a new calculation.

For a fact-less logged node whose binder has no milestone, the rule is group
completion, recorded locally as `timing_basis='group_completion'`. Do not add
an all-events default at zero, reinterpret snapshot reconciliation, or walk
unrelated actor events for an apparently suitable time.

Condition dates already appear in state commits. Transfer dates already appear
in dependencies. Reuse those exports; no broad timing refactor is justified.
If the chosen row helper needs a stable transfer milestone, add a direct view
of the existing cue value in `presentation_timing.py`, not a new timing solver.

## 5. Disclosure, filter and text contract

`dnd/subjective_combat_log.py:project_combat_log` is the disclosure authority. It
admits controlled participants or event-time observations; a hidden parent may
survive because it has a visible child. It sanitizes hidden UUIDs, names and
coordinates, clears internal grants, and rebuilds noncontrolled movement and
multi-target summaries from admitted children. Identity and location are separate.

The panel must receive only the already-projected entry on the final PlayerNode.
Never pass Session/Entity/EventQueue/objective rows to the drawing, filters,
copy action, hover tooltip or search index. Do not reproject using present-day
visibility: a past observation remains a past observation.

Category filtering uses `CombatLogEntryType`. Source and target filters use only
the entry's nonempty projected UUID fields. An “involving actor” filter matches
either role. Matching descendants retain their necessary ancestor rows as
context, visibly distinguished; do not recalculate or rewrite a native total to
pretend it is the filtered total. Empty UUID is unknown, not a shared actor ID.

Participant links are explicit source/target chips derived from those fields.
Do not guess which occurrence of “Goblin” in a string is source or target.
Two actors with the same display name retain different chip identities; two
unknown participants do not acquire identities from their names. A chip can
select/focus only a currently disclosed actor through the ordinary UI boundary;
old history does not authorize revealing an actor's present location.

The category determines an interface icon; success supplies a visual status
only when non-None. Neither becomes new wording. Full breakdown uses existing
`verbose`/`detailed`; `data` can provide exact existing fields to an inspector,
but the UI does not recompute attack bonus, AC, resistances, damage or saves.

### Actual markup to support

`dnd/core/combat_log.py` is not HTML or full Markdown. Existing producers use:

- `{cyan:text}`, `{yellow:text}`, `{red:text}`, `{green:text}`;
- `{bold:text}`, `{dim:text}`, `{bold red:text}`, `{bold yellow:text}`;
- `**text**`, including condition names and immunity;
- literal newlines and indentation in verbose/detailed breakdowns;
- ordinary punctuation and glyphs: `→`, `☠`, `───`, `[]`, dice parentheses,
  signs and numeric comparisons.

Implement a small pure tokenizer with this explicit style vocabulary. Each
token becomes plain text plus color/bold/dim attributes. Preserve all original
characters other than recognized delimiters. Unknown style names, unbalanced
braces/stars and unsupported nesting remain readable literal text. Do not
execute links, markup directives or arbitrary style names. Word-wrap measured
spans while retaining explicit line breaks and aligned continuation indentation;
wrap exceptionally long tokens without deleting the tail. Copy emits the
selected existing text with recognized style delimiters removed.

There is one source formatting defect worth naming precisely:
`greater_invisibility_check_processor` appends a plain string containing
`{{red:loses invisibility!}}`; its doubled braces are not an f-string escape.
If this case is included in UI acceptance, correct that producer to one pair
of braces. Do not build a generic malformed-source repair parser for it.

### Interaction state

Keep passive UI state only: selected row key, expanded row keys, verbosity,
category/source/target filters, scroll anchor and follow-latest flag. Use a row
key plus an intra-row vertical offset for the scroll anchor so wrapping, resize,
new rows and expand/collapse preserve the same reading position.

Scrolling away from the newest row disables follow mode. Incoming eligible rows
increment a “New entries” control without moving the reader. Jump-to-latest
restores follow mode. Receiving future rows while playback is paused does not
increment this count until those rows become presentation-eligible.

Choose the integrated plan's explicit 10,000-canonical-row history bound; evict
oldest completed causal groups first. An oversized single completed group is
trimmed by source order with a visible truncation indicator, preserving remaining
rows by promoting children whose parent was removed. Active rows are bounded by
the same cap. UI surface caching must have its own fixed bound and invalidate
on width/font/theme changes; never cache one Pygame surface forever per event.
The complete recorded sequence remains the replay source; this bound is the
live panel's retained view, not deletion of native history.

## 6. Real uncovered producer: standalone immunity logs

`EventQueue.push_combat_log` creates an unregistered carrier with
`context={'combat_log_origin': 'standalone'}` and directly invokes the encounter
callback. The only current production caller is immunity in
`Entity._declare_entity_condition`. It then cancels the real condition event.

`Session._operation` only reads EventQueue registered terminal roots, and
`capture_lineage` requires its root UUID in that queue. Therefore the restored
HUD and ordinary PlayerSequence cannot contain this existing immunity log.
This is a capture omission; adding an invented CONDITION_APPLIED sentence from
a canceled fact would be the wrong repair.

The bounded repair design is:

1. At the session/recording composition seam, install the existing passive
   `Encounter.add_combat_log_listener`. Recognize only the existing standalone
   carrier marker; ordinary root callbacks must not create a second copy of
   node-based rows. Remove the listener on close, and reset its local buffer on
   generation change. No event class is added or registered.
2. Project the entry immediately for the active observer with the existing
   `project_combat_log`; detach via the same JSON normalization as
   `_retained_event`. A None result remains absent. Implementation review proved that the immunity producer omitted existing declaration-time
   evidence. Copy that original declaration identity/location evidence and use the existing
   installed event-time perceiver policy; the UI cannot grant
   bystanders a new right to see it.
3. Store a passive append value with generation, observer, encounter log index,
   projected `CombatLogEntry`, and the completed operation's end cursor.
   Its key is `(generation, observer, 'encounter_log', index)`, not the
   unregistered carrier UUID. The operation boundary is a display gate, **not
   claimed causal ancestry**. No exact impact association is fabricated.
4. Retain these append values alongside the existing saved sequence, as an
   optional `combat_log_appends=()` field on `RecordedSequence` and
   `PlayerSequence`. They are already observer-projected in the private
   observer-specific recording. `project_sequence` copies them unchanged after
   checking generation/observer ownership. Add optional keyword input to the
   existing encode helper so old callers remain valid. Do not introduce a
   parallel transcript file/schema.
5. The UI replay entry point must keep the decoded sequence model as well as
   the reduced baseline/lineages: `decode_player_sequence` currently returns
   only those two latter values. Keep that existing reducer convenience API
   valid; parse/retain the sequence once at the UI boundary instead of losing
   the append field through that convenience return.
6. The live `Operation` carries the newly captured append values to the same
   log view. Admit them when historical presentation has completed all received
   groups from that operation. Operations with no disclosed group gate at the
   next settled historical boundary. In replay, the recorded operation end
   cursor determines that boundary among the retained heads; it never turns
   the standalone entry into a mechanical event.

This adds data capture and a field to existing recording owners, not outcome
formatting. Current schema versions are both 2; defaulted additive fields permit
old packets to read without inventing omitted standalone logs. Tests must show
old packets still load and new packets retain the append. No claim is made that
old recordings can recover a log they did not save.

Do not stamp all normal `CombatLogEntry` objects with event IDs to solve this
one distinct unregistered producer. Their containing nodes already solve the
normal identity problem, and the pre-post callback ordering makes an indiscriminate
event-UUID stamp error-prone.

## 7. Minimal UI data and file boundaries

The proposed `game/ui/combat_log.py` owns selection/hierarchy/filtering and its
passive UI state. The shared `game/ui/rich_text.py` owns tokenization and wrapped
spans; a Pygame-facing drawer consumes those results. These are functions and
small passive records, not widget subclasses, visitors or registries.

An ordinary row needs only references/copies of existing values:

```text
key: (generation, observer_uuid, event_uuid)
lineage_uuid, source_index, turn_execution_id
native_parent_lineage, displayed_parent_key, presentation_group_key
entry: existing projected CombatLogEntry
ready_ms, timing_basis: exact_existing_anchor | group_completion
```

Standalone rows have the separately tagged encounter-log key and operation
boundary specified above. Do not unify an unregistered append into a fake
PlayerNode. The row is a presentation index, not a new portable event model.

Allowed source edits, with their reason:

| File | Bounded change |
| --- | --- |
| `game/encounter_play.py` | Replace `_log_lines`, string deque and bottom log draw with one panel; pass group, existing bound clocks and elapsed time; route panel input before camera/world. |
| `game/ui/combat_log.py` and shared rich-text/layout owner | Canonical row view, identity dedup, hierarchy, filters, selection/copy, wrapping and bounded scrollback. |
| `game/player_facts.py`, `game/player_projection.py` | Optional copied turn execution ID; optional existing-log append field on the sequence. No facts acquire prose. |
| `game/presentation_timing.py` | Export existing lifecycle cue start values; any needed transfer exposure is a direct value view. |
| `game/session.py`, `game/replay.py`, capture composition caller | Capture and retain standalone log appends through the existing encounter listener; preserve encode compatibility. |
| `dnd/conditions.py` | Only the named doubled-brace correction if that displayed case is included. |

Domain code never imports `game/ui`. Drawing does not import native entities,
execute actions, call event formatters or query live registries. No reflective
`getattr`, runtime type-name routing, late imports or circular ownership is
needed. The existing typed fact variants and enums supply dispatch.

## 8. Observable examples and acceptance

These are proposed acceptance cases, not results run during this study. Use
native producers once, save the event/player input, then replay those bytes for
UI/timing/layout checks. Follow `HOW_TO_TEST.md`: assertions concern displayed
content, disclosure, order and command/input behavior, not private helper calls.

| Case | Required observable result |
| --- | --- |
| Two identical weapon hits | Two root summaries with different event keys. Expanding either shows only its own damage/save details once. Replaying the same packet adds zero rows. |
| Magic Missile A/B/A with equal damage | One native cast summary with open children: three distinct application nodes in recorded order, including both A applications. The user may collapse them. No target-based or string-based merging. Parent total is unavailable before the final owned result. |
| Save-based multi-target cast | Existing projected summary and each target application's combined save/damage entry; its save/damage primitives stay nested. No client-added aggregate or leaf sum. |
| Reaction and concentration failure after damage | Each existing log appears once under exact native/presentation ownership. Counterspell remains a distinct native root. Concentration/condition logs retain their original wording and own result dates. |
| Successful Counterspell | Reaction result appears at the aligned body effect/cutoff. No attack/contact/damage row from the canceled incoming cast, no synthetic cancellation sentence. Failed Counterspell is a real failed-interruption row followed by the cast's real results. |
| Movement with opportunity attack | Root destination text waits for actual arrival; steps are details. Attack and damage use the nested motion group's offset. Root reconciliation produces no extra log. |
| Unknown attacker, identified victim | All three verbosity variants, participant chips, filters, copied text and stored search text preserve the existing redaction. No objective source name/position appears. |
| Partial movement observation | Display existing rebuilt observed path/distance text; do not reconstruct an unobserved path from actor memory or root intent. |
| Same-name actors | Each disclosed actor chip/filter resolves by UUID. No click target is inferred by locating a name substring. |
| Internal condition / unworded state | No row, even if the player fact exists and has visible mechanics. |
| Standalone immunity | One existing immunity entry survives live capture, save/load and replay; it has an encounter-log key, no fabricated native UUID, and follows the containing operation's historical completion. |
| No exact timing anchor | Entry survives and appears once at group completion. Diagnostics identify fallback timing; there is no silent zero-time default. |
| Long detailed attack/roll | All native text is readable after wrapping; color/bold/indentation survive; no 170-character truncation; copied text contains the same words/numbers without recognized style delimiters. |
| Scroll, filter, expansion and resize | Reader's anchored row stays in place; new-entry count waits for actual eligibility; ancestor context remains clear; filters never rewrite totals. |
| Pause / hitch / backward seek / finish skip | Paused history reveals no future logs despite intake advancement. One large sample step and many small steps reach identical eligible keys. Backward seek hides future rows without deleting identities; finish reaches the same final keys as ordinary play. |
| Recorded generations / observer switch | Equal UUID/text from a different generation/observer cannot join existing rows. No cross-observer cache or filter options. |
| History cap | Bound is honored, truncation is visible, surviving child rows remain readable, and the full recorded replay remains intact. |

Existing relevant regression owners: `tests/game/test_encounter_play.py`,
`test_counterspell_presentation_group.py`, `test_interruption_replay.py`,
`test_presentation_commit_evidence.py`, `test_transfer_timing_evidence.py`,
`test_player_projection.py`, and
`tests/engine/test_subjective_combat_log_replay.py`. New UI checks should extend
the public packet-to-visible-row boundary, plus a thin real Pygame interaction
and pixel pass at the planned window sizes. Static tests do not establish
readability; a screenshot does not establish disclosure or replay identity.

The implementation plan must include two independent review gates:

- **Anti-slop reviewer:** one existing wording source, no alternate narrative,
  no flattened summary/detail duplication, no text dedup, honest fallback timing,
  complete wrapping/scroll/replay evidence and no unsupported completion claim.
- **Anti-OOP/ECS reviewer:** passive records and function composition, imports
  remain a DAG, no live-domain reads from UI, original native identities/reducer
  order/disclosure preserved, and standalone capture is an append record rather
  than a synthetic rules event.

Both reviews assess the final source and the concrete acceptance evidence.
This source study is input to those reviews, not a substitute for them.
