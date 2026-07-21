# Agent UX Iteration Log

This log records completed games, observed control friction, and the next interface changes made from those observations. Each development phase should be anchored by a finished game first.

## 2026-07-17 - Bulk Subscriber Union For Light-Batch Sensory Dispatch

### Change

`GridMap` now exposes a bulk subscriber-union helper for a set of cells, and
`SpatialSensesSystem` uses it for `SPATIAL_LIGHT_CHANGED` candidate selection.
This avoids copying subscriber sets once per changed light cell during a light
batch. The observer-local `SpatialSensesCallback` still remains the final
authority for whether a selected observer's subjective facts actually change.

The change is intentionally limited to light-batch dispatch. Other spatial
events keep the existing position/hint candidate logic because they combine
path, occupancy, perceivability, object, and directional topology signals.

### Evidence

Focused checks:

- `uv run pyright dnd/core/gridmap.py dnd/blocks/sensory.py tests/manual/test_43_ai_runtime_performance.py`
- `uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "light_batch_candidate_selection_uses_bulk_subscriber_union or bright_visibility_skips_per_tile_effective_light or dark_visibility_still_uses_subjective_light_resolution"`
- `uv run pytest tests/manual/test_12_perception_light_stealth_and_invisibility.py -q -k "light or visibility or senses"`
- `uv run pytest tests/manual/test_28_subjective_observation_stream.py -q -k "lit_to_lit_light_changes_do_not_refilter_visible_occupants or removed_visible_tile_delta_reuses_materialized_boundary_memory or hidden_entities_do_not_leak"`

Results: pyright `0 errors`; focused performance-light tests `3 passed, 42
deselected`; perception/light tests `10 passed`; subjective observation checks
`2 passed, 42 deselected`.

No-artifact smoke after the change:

- `gauntlet_id`: `20260716T231129Z-ai-gauntlet-smoke-0e1ec339`;
- result: `encounter_ended`, outcome `heroes`;
- commands: `11/11` accepted;
- subjectivity: `passed`, `0` violations;
- normal command p95/p99: `50.246 ms`;
- normal server command p95/p99: `37.086 ms`;
- normal local decision p95/p99: `5.329 ms`;
- latency: still `failed`.

One-command diagnostic on `standard_skeleton_doors`, seed `707`:

- selected row: `position|Move|pos=7,12`;
- command status: `accepted`;
- total command time: about `100.550 ms`;
- server total: about `53.900 ms`;
- `execute.action_by_index_ms`: about `29.488 ms`;
- `publish.post_command_control_ms`: about `24.139 ms`;
- `publish.followup_epoch.build_decision_epoch_total_ms`: about `23.917 ms`;
- `grid.move_light_source.publish_batch_ms`: about `4.489 ms`;
- `SpatialSensesSystem`: about `4.021 ms`.

### Remaining Issue

This removes avoidable copying in light-batch dispatch, but the latency gate is
still dominated by authoritative movement execution plus follow-up decision
epoch construction. The next larger cuts need to reduce post-command epoch
generation and movement sensory publication, not the controller policy.

## 2026-07-17 - Required-Target AoE Prefilter Uses Relationship Semantics

### Change

AoE discovery now prefilters required-target candidate centers with the action's
own relationship semantics before doing expensive footprint preview work. An
enemy-only AoE no longer asks allied positions to seed candidate centers; ally,
self-or-ally, all-target, and self-including AoEs keep their corresponding
relationship behavior.

The final legal rows are still produced by `_compute_aoe_at_position`, so this
does not replace server legality or change friendly-fire spells. Fireball,
Lightning Bolt, Shatter, and similar area damage spells remain `all`-target
spells in this ruleset and still consider allies where their rule does.

The same helper is used by registered position-AoE actions and item-use AoEs,
and item-use candidate-neighborhood lookups now reuse the actor's nearby-AoE
candidate cache.

### Evidence

Focused checks:

- `uv run pyright dnd/entity.py tests/manual/test_43_ai_runtime_performance.py`
- `uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "required_target_aoe_prefilter_uses_action_relationship_filter or aoe_shape_definition_is_not_serialized_per_candidate_cell or aoe_origin_fov_cache_survives_preview_cache_invalidation or aoe_discovery_reuses_one_preview_shape_per_variant or directional_aoe_discovery_compacts_duplicate_target_rays"`
- `uv run pytest tests/manual/test_37_ai_validation_arenas.py -q -k "arcane_device or item_resource"`

Results: pyright `0 errors`; AoE performance tests `5 passed, 39 deselected`;
device/item arena checks `2 passed, 37 deselected`.

Targeted `caster_crossfire` action-discovery timing sample:

- AoE rows: Fireball `36`, Lightning Bolt `12`, Shatter slot 2 `21`,
  Shatter slot 3 `21`;
- `available_actions.collect_aoe_actions_ms`: about `5.452 ms`;
- `available_actions.aoe_footprint_cache_miss_ms`: about `3.181 ms` across
  `131` misses.

No-artifact smoke after the change:

- `gauntlet_id`: `20260716T230732Z-ai-gauntlet-smoke-1461fa0b`;
- result: `encounter_ended`, outcome `heroes`;
- commands: `11/11` accepted;
- subjectivity: `passed`, `0` violations;
- normal command p95/p99: `49.655 ms`;
- normal server command p95/p99: `37.032 ms`;
- normal local decision p95/p99: `4.657 ms`;
- latency: still `failed` on end-to-end command timing.

### Remaining Issue

The local decision loop is under target again in this smoke, but command and
server latency remain far above the formal gate. The next high-value work is
still movement/light/sensory publication and follow-up decision-epoch
construction, not policy ordering.

## 2026-07-17 - Sparse Seen-Tile Deltas Preserve Replay Truth

### Change

Removed visible-cell deltas now send sparse `seen` tile facts instead of
rebuilding adjacent-domain boundary metadata for every removed cell in the
projector. The materializer carries forward only the previous
`adjacent_domain` field when a visible tile becomes seen/remembered and the
incoming tile fact is sparse.

This keeps the stream event-first and subjective: the frame no longer repeats
derivable remembered boundary data, while replay still materializes to the same
state as a fresh subjective snapshot. The merge intentionally does not retain
visible-only terrain fields such as current walkability, tile conditions, light
level, or directional blockers after the tile is no longer visible.

### Evidence

Focused checks:

- `uv run pyright ai/observation/materializer.py ai/observation/projector.py tests/manual/test_28_subjective_observation_stream.py`
- `uv run pytest tests/manual/test_28_subjective_observation_stream.py -q -k "dense_sensory_tile_updates_are_batched_and_replayable or removed_visible_tile_delta_reuses_materialized_boundary_memory or lit_to_lit_light_changes_do_not_refilter_visible_occupants"`

Result: `3 passed, 41 deselected`; pyright reported `0 errors`.

Short diagnostic on `standard_skeleton_doors`, seed `707`, one command:

- status: `command_cap_reached`;
- selected row: `position|Move|pos=7,12`;
- command status: `accepted`;
- total command time: about `104.942 ms`;
- server command time: about `56.028 ms`;
- local decision time: about `1.998 ms`;
- sampled max `sensory_patches.removed_tile_patches_ms`: about `0.393 ms`.

No-artifact smoke after the replay change:

- `gauntlet_id`: `20260716T230131Z-ai-gauntlet-smoke-886bbf60`;
- result: `encounter_ended`, outcome `heroes`;
- commands: `11/11` accepted;
- subjectivity: `passed`, `0` violations;
- normal command p95/p99: `48.860 ms`;
- normal server command p95/p99: `35.849 ms`;
- normal local decision p95/p99: `5.328 ms`;
- latency: still `failed`.

### Remaining Issue

This is a correct small cut, not the latency fix. The first movement command is
still dominated by authoritative movement/sensory work and follow-up
decision-epoch construction, especially movement light publication,
`SpatialSensesSystem`, AoE footprint generation, and `get_available_actions`
during epoch construction.

## 2026-07-17 - Smoke Gate, Client Reuse, And Remaining Server Latency

### Current Smoke Evidence

`20260716T225242Z-ai-gauntlet-smoke-e145e491` reran the
`standard_skeleton_doors` smoke slice with seed `707`. The match completed
cleanly with `11/11` accepted commands, outcome `heroes`, subjectivity
`passed`, and `0` subjectivity violations. The gate passed for gameplay
correctness and hidden-information safety.

The latency gate remains red, but the shape is now clearer. Local decision
latency is within the target on this smoke: normal local-decision p95/p99 was
`4.552 ms`, below the `5 ms` target. End-to-end command latency is still high:
normal command-total p95/p99 was `48.089 ms`, and normal server-command p95/p99
was `35.554 ms`. Diagnostic samples showed the first movement command at
`100.310 ms` total and `56.225 ms` server-side, dominated by movement sensory
publication plus the follow-up decision epoch.

### Diagnostic Attribution

A four-command diagnostic on the same arena/seed sampled every command. The
first movement command spent its server time in two real engine surfaces:
authoritative movement/sensory publication and follow-up legal-affordance
construction. The largest first-command phases were:

- `execute.action_by_index_ms`: about `30 ms`;
- `execute_by_index.event_queue.pre_completion.callback.SpatialSensesSystem_ms`:
  about `15-17 ms`;
- `execute_by_index.grid.move_light_source.publish_batch_ms`: about `7-8 ms`;
- `publish.followup_epoch.build_decision_epoch_total_ms`: about `20-24 ms`;
- `publish.followup_epoch.get_available_actions_ms`: about `15-18 ms`;
- `publish.followup_epoch.available_actions.collect_aoe_actions_ms`: about
  `11-12 ms`.

Later commands confirmed separate hot paths: Fireball execution is dominated by
multi-target damage/save application, while post-Dash follow-up epochs are
dominated by dirty path recomputation for the expanded movement budget. These
are legitimate engine costs, not policy tree confusion.

### Harness Infrastructure

`ArenaApiClient` now reuses one in-process ASGI transport, `AsyncClient`, and
event runner per client instance instead of creating fresh request plumbing for
every `GET` and `POST`. This keeps repeated self-play and gauntlet runs from
measuring client construction as command latency. The change did not explain
away the remaining red latency; command overhead outside server timing remains
small relative to engine execution and epoch construction. The self-play runner
closes the reusable client on its normal completion path.

### Checks

- `uv run pyright server/arena_mode.py ai/external_selfplay.py tests/manual/test_43_ai_runtime_performance.py`
- `uv run pytest tests/manual/test_23_standard_arena_game_modes.py -q`
- `uv run pytest tests/manual/test_29_external_ai_subprocess.py -q`
- `uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "aoe_shape_definition_is_not_serialized_per_candidate_cell or aoe_origin_fov_cache_survives_preview_cache_invalidation or aoe_discovery_reuses_one_preview_shape_per_variant or directional_aoe_discovery_compacts_duplicate_target_rays or post_request_does_not_retain_its_caller_until_cyclic_gc"`
- `uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id standard_skeleton_doors --seed 707 --no-run-artifacts --no-summary-file --require-gate-pass`

### Next Optimization Target

Do not spend the next slice on policy ordering. The policy is locally bounded
on this smoke. The next aligned work is reducing server-side event/epoch cost
without weakening the event-first subjective contract: lit actor movement,
sensory tile/entity projection, AoE preview construction after reveal, and
dirty path refresh after Dash are the current dominant paths.

## 2026-07-14 - Single-Pass Epochs And Gated Projection Timing V140-V141

`evidence/runs/20260714-v140-single-pass-epoch-validation.json` validates
single-pass per-epoch action-variant discovery and capability metadata reuse.
The deduplication was correct, but V140 did not improve end-to-end p95 beyond
run-to-run noise; it is not claimed as a latency win.

`evidence/runs/20260714-v141-gated-projection-timing-validation.json` then
disabled projector timing clocks during normal commands while retaining sampled
deep diagnostics. V141 reproduced V140's semantic outcome and passed the same
subjectivity audit. Normal total p95 fell from `75.325 ms` to `63.124 ms`,
command HTTP p95 from `49.628 ms` to `44.872 ms`, and follow-up synchronization
p95 from `8.254 ms` to `6.093 ms`.

This isolates measurable observer overhead without explaining away the
remaining latency. The residual cost is genuine pathfinding, legal-affordance
construction, event application, and subjective event processing; those paths
remain the next optimization target.

## 2026-07-14 - Sampled Diagnostics Door Validation V139

### Honest Normal And Diagnostic Timing

`evidence/runs/20260714-v139-sampled-diagnostics-door-validation.json`
validates sampled deep diagnostics in `standard_skeleton_doors`. All `9/9`
commands were accepted, the subjectivity audit passed without violations, and
the encounter ended in round 2 with the Sorcerer at 37 HP. Eight commands used
the normal lightweight timing path; one command explicitly enabled deep server
diagnostics. The artifact and dashboard projection retain those populations as
separate `normal_stages` and `diagnostic_stages` rather than blending probe
overhead into production latency.

The normal path remained fast locally: policy evaluation was `4.182 ms` p95 and
the complete local decision was `5.622 ms` p95. End-to-end latency is still
well above target, however. Across the eight normal commands, command HTTP was
`49.324 ms` p95, command submission was `53.923 ms` p95, pre-command stream
synchronization was `28.008 ms` p95, and total epoch-to-result work was
`71.033 ms` p95. Removing always-on deep probes therefore corrected the
measurement, but did not explain away the server cost.

The sampled diagnostic command identifies genuine action and epoch hot paths.
Authoritative action execution took `42.945 ms`; its follow-up decision epoch
took `26.451 ms`, including `18.519 ms` for available-action discovery,
`14.307 ms` for AoE action collection, and `7.362 ms` for affordance-set
construction. Capability construction contributed `3.002 ms`, principally
`2.725 ms` of metadata and model construction. These nested phases overlap and
must not be added as independent totals, but they locate the next work:
deduplicate per-epoch action variants and capability metadata while preserving
fresh legality, subjective targets, and authoritative execution.

### Result

Sampled diagnostics now provide useful deep evidence without taxing every
command. The validation proves the timing split itself and confirms that the
remaining latency is real engine/epoch work, not merely instrumentation
overhead. It does not satisfy the latency gate yet.

## 2026-07-14 - Semantic Replay And Revalidating Door Search V138

### Identity-Independent Decisions

Same-seed combat previously changed across fresh processes because opaque UUIDs
ordered equal-score target rows, multi-projectile allocation axes, and final
execution order. The same seeded roll stream was therefore assigned to
different semantic targets. Production proposals now carry an explicit
`replay_key`. Equal utility is ordered by disclosed action semantics, known
positions, normalized names, and selected target allocation. HP, AC,
conditions, and damage affinities remain scored facts rather than accidental
tie-break preferences. UUID-bearing row ids are retained only as compatibility
fallbacks for custom proposals that provide no semantic replay key.

Multi-target damage and control allocation, outcome evidence, remembered
contact selection, spacing references, door targets, and enable-then-act
routines use the same identity-independent rule. A UUID-permutation unit test
preserves primary position and ordered projectile allocation. A fresh-process
test uses disjoint actor UUIDs and different `PYTHONHASHSEED` values while
preserving composite policy hash, normalized action trace, command count, final
round, and name-keyed HP.

### Retained Validation

`evidence/runs/20260714-v137-semantic-replay-sorcerer-validation.json`
replays the formerly divergent split-skeleton seed. It now reproduces the V133
semantic outcome exactly: `26/26` accepted commands, subjectivity passed,
encounter end in round 5, Sorcerer at 31 HP, and skeleton HP at `-2/-3/-5`.

`evidence/runs/20260714-v138-semantic-replay-door-validation.json` exercises
frontier search and routine revalidation. All `25` commands were accepted,
subjectivity passed, and policy latency was `3.964 ms` p95. With no visible
enemy, the Sorcerer moved toward a known closed door. The movement revealed the
Archer, so the next epoch correctly abandoned blind door completion and chose
ranged spacing from the newly observed state. The encounter ended in round 4
with the Sorcerer at 37 HP.

The composite policy is now versioned as
`2026-07-14.shared-policy-v18-semantic-replay`. The exact source hash remains
the authoritative identity when two artifacts share a human-readable feature
version.

## 2026-07-14 - Honest Shared Policy Identity V136

### Composite Policy Evidence

Validation artifacts previously hashed only `ai/external/policy.py`, even after
normal decisions moved into `PolicyHost` and the shared `ai/policy` hierarchy.
That allowed changes to candidates, utility, routines, or knowledge derivation
to retain the same apparent policy identity. The policy snapshot now records a
stable ordered manifest covering the decision-bearing `ai/knowledge`,
`ai/policy`, and external fallback sources. Its primary entry point is
`ai/policy/host.py`; the manifest hash changes when any included source changes.
Legacy artifacts remain readable with an empty `source_paths` compatibility
default.

A focused regression simulates a source change in
`ai/policy/candidates.py` and proves that the composite SHA-256 changes. New
artifacts identify the policy as `shared_subjective_hierarchical_policy`,
version `2026-07-14.shared-policy-v17-bounded-spacing`.

### Retained Barbarian Rotation

`evidence/runs/20260714-v136-composite-policy-barbarian-validation.json`
records an AI-versus-AI Sorcerer/Barbarian duel with seed `2026071417` and the
Barbarian-side opening configuration. All `7` commands were accepted,
subjectivity passed, the shared `PolicyHost` owned every decision, and no
compatibility fallback was used. Policy latency was `2.046 ms` p95.

The Sorcerer landed Hold Person, held ranged spacing, and defeated the locked
Barbarian with two level-3 Scorching Ray casts in round 3 while remaining at 37
HP. This is evidence that control state and the no-action fallback remained
coherent; it is not broad challenge evidence because the failed saves produced
a short control-lock trajectory.

### Replay Limitation

Same-seed replay is not yet stable across fresh UUID allocation. Policy and
multi-target allocation still use opaque UUIDs as final tie-breakers in some
equal-score cases. Sequential projectile rolls can then attach the seeded roll
stream to different semantic targets and change the rest of combat. The issue
is retained in `KNOWN_ISSUES.md` with a UUID-renaming unit test and normalized
cross-process replay test proposed before deterministic replay is claimed.

## 2026-07-14 - Subjective Delivery, Bounded Spacing, And Honest Timing V135

### Subjective Event Delivery

Two event-time projection errors are now closed. Condition-application
completion merges the event-owned condition only into the event target; a new
Hold Person replay check proves that the target receives the complete
`Hold Person -> Paralyzed -> Incapacitated` tree while the caster does not.
Standalone `ENTITY_SPOTTED` and `HAZARD_DETECTED` logs now enter the initialized
session stream through the encounter's existing combat-log listener. Their
unregistered carrier is explicitly marked as standalone, registered event logs
remain owned by EventQueue completion projection, and observer identity metadata
prevents synchronous filtering from disclosing a detection to another session.

Sensory completions remain eager immutable event boundaries, but observer-local
events now invoke projection only for sessions controlling that observer. A
focused two-session test proves one projector update, one immediate sensory
frame for the owning session, and no frame for the unrelated session. This does
not remove per-cell movement, spatial enter/leave, opportunity attacks, forced
movement distinctions, light, darkvision, or hidden-state filtering.

### Bounded Spacing Policy

The slow Hold decisions were not behavior-tree traversal. The policy eagerly
materialized `187-196` spacing proposals from roughly `214` legal movement rows,
creating about `1,774` utility components and `2,486` Pydantic validations for
one decision. Spacing now evaluates legal rows as lightweight seeds and
materializes only the best representative in each semantic, economy, and
disclosed-risk class plus the explicit Hold proposal. Safe, hazardous, and
opportunity-attack-exposed alternatives remain distinguishable. Zero-weight
components retain evaluated, applicable, and represented row counts for audit.

A dense 15-by-15 structural regression reduced `217` full proposals to `2` and
remained invariant under reversed row order. Two hundred warm evaluations over
`224` rows measured `0.578 ms` p95 and `0.628 ms` maximum. In the retained live
validation, Hold policy ticks fell from `4.539-5.483 ms` with `187-196`
proposals to `0.793-1.047 ms` with `3` representatives.

### Retained Validation And Timing

`evidence/runs/20260714-v133-spacing-sensory-validation.json` repeats the split
skeleton arena with seed `2026071406`. All `26` commands were accepted,
subjectivity passed, and the outcome exactly matched V132: encounter end in
round 5, Sorcerer at 31 HP, and all three skeletons defeated.

Self-play timing previously merged pre-command catch-up with post-command
follow-up. Traces now retain both buckets separately while preserving aggregate
frame timing fields for compatibility. The artifact builder and dashboard
projection can therefore report pre-command sync/fetch/apply independently from
command-result and follow-up fetch/apply.

`evidence/runs/20260714-v134-nonoverlapping-timing-validation.json` shows the
largest warm trace as `36.882 ms` pre-command sync over 24 persisted frames,
`5.003 ms` policy, `52.382 ms` command HTTP/server work, and `13.394 ms`
follow-up sync. This harness uses persisted-history polling between actors;
production `SubjectiveRuntime` uses a persistent client and SSE. Harness
catch-up is transport validation cost, not policy-thinking time.

### Remaining Friction

The same nominal random seed produced a different V134 combat outcome in a
separate process. The artifacts remain retained because this exposes an
important replay weakness: random dice state is seeded, but UUID or unordered
tie-breaking can still influence multi-target allocation. Exact cross-process
determinism is under focused audit and must be fixed before same-seed artifacts
are treated as behaviorally identical.

Multi-target damage policy remains the local policy tail at roughly `4-5 ms`.
Server action execution, available-action discovery, dirty-senses refresh, and
pathfinding remain the larger command tail. The next rotation should use the
seamless runtime measurements rather than conflating self-play history polling
with decision latency.

## 2026-07-14 - Immutable Event Truth And Autonomous Rotation V132

### Event-Time Subjective Truth

An attempted optimization deferred subjective projection of child completions
until their top-level causal root completed. The focused boundary test initially
passed, but a deeper temporal audit disproved the design. Two damage children
under one parent could be reconstructed from the final mutable entity state as
`[14, 14]` instead of the event-time HP sequence `[16, 14]`. Late children of an
already completed parent could also remain unpublished until an unrelated
request happened to reconcile the cache.

The root-only projector was removed. Subjective projection continues to capture
every immutable completion boundary eagerly. New tests prove that child damage
frames retain event-time HP, ordinary child completions are captured before the
root changes state again, and a late child wakes the subjective stream without a
poll or control frame. This is now an explicit architectural constraint: frame
publication may eventually be batched, but historical facts may never be
reconstructed from later mutable engine state.

### Retained Performance Improvements

`SensoryUpdateEvent` is observational information. Repository-wide consumers
use its completion payload; there are no declaration, execution, or effect
handlers for this event type, and both NeuroClient and the subjective projector
already ignore those earlier versions. Sensory deltas now transition through
`phase_to(COMPLETION)` to preserve parent lineage and register one completed
event rather than four empty lifecycle versions.

The four-cell Warrior movement in `skeleton_anti_aoe_split` provides a direct
comparison with the retained V131 movement:

- intermediate entered-cell events remained `4`;
- sensory callback invocations remained `52`;
- sensory delta emissions changed from `13 x 4` stored versions to `13 x 1`;
- total EventQueue versions fell from `113` to `74` exactly;
- EventQueue storage fell from `10.202 ms` to `8.304 ms`;
- action execution fell from about `31.3 ms` to `27.376 ms`;
- the measured command fell from roughly `55 ms` to `44.779 ms`.

No intermediate movement, observer-specific delta, voluntary-movement
semantics, or replay fact was removed. Perception, subjective replay, engine-book
senses, live replication, and seamless command tests remain green.

Empty AoE previews are now cacheable values. In the split arena, Burning Hands
and Thunderwave previously evaluated all `83` candidate positions again for
their slot-2 variants when slot 1 found no target. The cache now distinguishes a
missing entry from an empty result, so each base shape is evaluated once and a
second unchanged epoch performs no AoE target recomputation. Positive previews,
topology invalidation, and subjective-contact invalidation retain their existing
behavior.

### Condition Projection Finding

The first autonomous Barbarian run appeared to leave `Paralyzed` and
`Incapacitated` behind after `Hold Person`. A bounded reproduction separated
engine truth from agent truth: the engine condition tree was correct. The
subjective projector observed a condition application completion synchronously
before the owning entity indexed the top-level condition, so replay included the
already indexed subconditions but omitted `Hold Person` itself.

Condition application frames now merge the condition carried by the completed
event into the projected entity fact. A new replay test applies the complete
`Hold Person -> Paralyzed -> Incapacitated` tree and proves that snapshot plus
frames equals a fresh snapshot. Repeating the same seeded duel now shows the
complete tree on every held Barbarian turn.

### Retained Rotation Evidence

Rotation slot 5 used external AI on both sides of
`sorcerer_barbarian_duel`, with the Barbarian initiative slot first. The
corrected immutable artifact is
`evidence/runs/20260714-rotation-2-05-ai-vs-ai-barbarian-condition-projection-fixed.json`.
All `16` commands were accepted, the subjectivity audit passed, and the Sorcerer
won in round 6 with 37 HP. The Barbarian repeatedly failed its initial or repeat
Wisdom saves; its empty epochs were legal consequences of Incapacitated rather
than policy refusal.

Rotation slot 6 used external AI on both sides of
`skeleton_anti_aoe_split`. The artifact is
`evidence/runs/20260714-rotation-2-06-ai-vs-ai-sorcerer.json`. All `26` commands
were accepted, the subjectivity audit passed, and the Sorcerer won in round 5
with 31 HP after defeating the Warrior, Archer, and Warlock. The same shared
PolicyHost selected multi-projectile spells, ranged attacks, bounded ranged
holds, a four-cell move-then-attack routine, melee follow-ups, and terminal End
Turn commands.

### Remaining Friction

The rotation is complete, but speed is not at target. Slot 6 command p95 was
`92.674 ms`; policy p95 was `5.168 ms`; command HTTP p95 was `45.675 ms`.
Spell follow-up epochs reached `22 ms` when a death invalidated paths and forced
an `8 ms` senses refresh with a `5.8 ms` Dijkstra pass. The four-cell movement
still spent `14.302 ms` across 52 sensory callbacks. These costs are fully
instrumented and no longer unexplained, but they remain too high.

The next performance work should reduce path recomputation and per-observer
spatial callback cost while preserving the event-time projection invariant.
Separately, standalone `ENTITY_SPOTTED` and `HAZARD_DETECTED` combat logs still
need a live subjective observation listener so they cannot wait for an unrelated
registered event to reach initialized sessions.

## 2026-07-14 - Seamless Handoff, Canonical Decisions, And Skeleton Rotation V131

### Integrated Architecture

The hot Codex runtime can now adopt the exact takeover claim created by
validation startup. Supplying `claim_id` performs a typed heartbeat and checks
the expected session; it does not create a replacement claim, does not require
`--force`, and rejects a session mismatch. One live isolated check preserved
the same claim id, session id, encounter id, and three controlled skeleton UUIDs
from startup through the hot runtime.

`PolicyHost` now emits one canonical `policy.decision_evaluated` event for each
fresh epoch binding. The event carries policy identity/version, controller mode,
subjective cursor, epoch, actor, selected intent, candidate utilities, evidence,
and behavior-tree trace. Agent-event storage deduplicates retries by stable event
id. Policy telemetry remains observational: failed HTTP delivery is logged but
cannot change command authority or game state.

Ranged spacing now uses typed deficits rather than unbounded distance reward.
Hostile and allied spacing rewards saturate at their floors, movement must reduce
a real deficit, typed normal attack range is preserved, and equivalent anchors
prefer lower movement cost. In live play the Archer held at seven cells because
its six-cell safety floor was already satisfied and its normal attack range was
sixteen cells.

### Retained Rotation Evidence

Rotation slot 4 used direct Codex control of the Warrior, Archer, and Warlock
against the external AI level 5 Sorcerer in `skeleton_anti_aoe_split`. The
immutable artifact is
`evidence/direct_codex_runs/20260714-rotation-2-04-codex-skeletons-vs-ai-sorcerer-live-proof.json`.
It contains 175 subjective frames, 130 correlated agent events, 19 accepted
commands, no rejected or stale commands, and exactly 19 canonical policy
decision events.

The external Sorcerer won in round 5 with 29 HP. The Warlock and Archer applied
ranged pressure, the Warrior used a bounded move-then-attack routine, and every
actor ended its turn through the typed terminal affordance. Replaying only the
initial subjective snapshot and retained frames reconstructs the ended encounter
and all four final entity facts; no objective state or compatibility
available-actions polling was used.

### Performance Evidence

Speed remains the unresolved part of this slice. The artifact anchors its
slowest subjective-runtime command at `84.741 ms`. The Warrior's four-cell move
retains enough low-level evidence to explain its `31.298 ms` action server span:

- four entered-cell events consumed `18.878 ms`;
- 52 `SpatialSensesCallback` invocations consumed `18.150 ms`;
- 16 observer-specific sensory emissions consumed `9.398 ms`;
- 113 event versions consumed `10.202 ms` in EventQueue storage;
- the one final path recomputation consumed `5.895 ms`.

The multiplicity is semantically meaningful: voluntary movement must preserve
intermediate terrain, perception, and opportunity-attack boundaries. The next
optimization must reduce implementation cost or safely batch transport work; it
must not remove those events or replace them with endpoint-only movement.

Server timing now retains aggregate duration, invocation count, and maximum
single-call duration for every phase, including named EventQueue callbacks.
Hot command responses separately report validation/policy preparation,
subjective-runtime command, policy-result correlation, and follow-up projection.

### Focused Verification

- `test_34_agent_event_stream.py`: 10 passed;
- `test_36_seamless_subjective_runtime.py`: 24 passed;
- `test_38_ai_validation_server_start.py`: 4 passed;
- `test_44_typed_agent_policy.py`: 38 passed;
- `test_48_policy_host.py`: 16 passed;
- `test_49_hot_codex_runtime.py`: 11 passed;
- exact-claim Codex client checks: 3 passed;
- shared external-policy host checks: 2 passed;
- focused Pyright over the touched runtime, policy, server, event, and tests: clean.

### Next Targets

- Profile and reduce EventQueue projection and sensory-event construction while
  preserving every intermediate voluntary-movement observation.
- Reduce decision-epoch construction, especially path and position-action
  collection for spell-rich actors.
- Remove avoidable command-follow-up round trips or synchronous telemetry work
  without moving gameplay truth into command acknowledgements.
- Continue rotation slot 5 with external AI versus external AI on the Barbarian
  matchup, then slot 6 on the Sorcerer matchup.

## 2026-07-14 - Direct Codex Skeleton Rotation V130

### Evidence

Rotation slot 3 used direct Codex control of the Guard, Archer, and Mage
against the external AI Barbarian in `caster_crossfire`. The immutable artifact
is
`evidence/direct_codex_runs/20260714-rotation-2-03-codex-skeletons-vs-ai-barbarian.json`.
It contains 201 subjective frames, 85 correlated agent events, 15 accepted
commands, no rejected or stale commands, and four evidence-anchored friction
annotations.

The direct controller bootstrapped one subjective snapshot, consumed local
decision epochs, and submitted revision-fenced row commands. It did not query
objective state, objective visibility, or the compatibility available-actions
endpoint. The isolated backend and hot runtime were stopped after collection.

### Combat Result

The monster squad won in round 3. The Archer and Guard applied weapon pressure,
the Mage allocated repeated Magic Missile projectiles to the single visible
Barbarian, and typed End Turn remained available whenever meaningful economy
was exhausted. The external Barbarian closed distance, used its two attacks to
kill the 2 HP Guard, and was then defeated by the Archer at 1 HP. One controlled
monster died; the Archer and Mage survived.

This was a useful mixed-role validation rather than another Sorcerer-only
replay. Multi-projectile allocation, melee and ranged attacks, movement,
resource expenditure, actor changes, death, and encounter termination all
crossed the same subjective runtime without a resync loop.

### Friction Findings

- After its first attack, the Archer was already six cells from the visible
  Barbarian. `RangedSpacing` still selected a full 30 ft move to `(14,0)`,
  valuing additional hostile and ally separation without a clear saturation
  point. This is retained as policy bias, not yet patched from one sample.
- That movement command took `59.903 ms` end to end, with `48.659 ms` in the
  HTTP submission span. Across the run, projected command total p95 was
  `77.913 ms` and server-command p95 was `47.607 ms`, while local policy
  decisions observed during play remained below `3 ms`.
- The hot PolicyHost returned full candidate scores and traces locally, but the
  server-retained agent event history contains command and timing telemetry,
  not policy-selection telemetry. The durable artifact can prove what command
  ran but cannot reconstruct why it beat the alternatives.
- Validation startup pre-created the correct Codex session and takeover claim,
  but the hot runtime could not attach to that claim. It required a forced
  replacement claim for the same session before direct play could start.

### Interpretation

The event-first state and command substrate is working. The remaining problems
are now above and around that substrate: controller handoff is awkward,
decision telemetry is incomplete, command transport is far slower than local
reasoning, and ranged spacing needs a principled goal-relative utility rather
than unbounded distance reward.

No tactical coefficient changed in this iteration. The run is evidence for the
next focused tests and architectural changes, not post-hoc proof that those
changes already work.

### Next Targets

- Make the hot runtime attach to the validation claim it is given, without
  replacing ownership or requiring `--force`.
- Emit one correlated policy-decision telemetry event per fresh epoch so the
  server and NeuroClient can observe candidate ranking and selection.
- Split command submission into transport, validation, executor, projection,
  epoch construction, history fetch, local apply, and deferred telemetry spans.
- Define ranged-spacing utility around a typed desired interval and marginal
  risk reduction, then add focused tests before changing live behavior.
- Advance rotation slot 4 with direct Codex skeletons against an external AI
  Sorcerer after the controller path is seamless enough to trust the run.

## 2026-07-14 - Voluntary Movement Threat Parity V129

### Evidence

Three direct Sorcerer diagnostics retain the complete live progression from
the V128 fixes to the corrected movement contract:

- `evidence/direct_codex_runs/20260714-v128-live-total-fallback-sorcerer-diagnostic.json`
  proves the shared policy emits and executes End Turn after an action and all
  movement are spent. It contains 67 subjective frames and 24 agent events.
- `evidence/direct_codex_runs/20260714-v128-jump-threat-disclosure-regression.json`
  retains the adjacent-Warrior defect before correction. It contains 57
  subjective frames, 24 agent events, and two friction annotations anchored to
  cursor 58.
- `evidence/direct_codex_runs/20260714-v129-live-voluntary-movement-threat-fixed.json`
  repeats the same adjacent state after correction. It contains 81 subjective
  frames and 29 agent events.

The diagnostic sequence used the normal `standard_skeleton_doors` arena, an
external skeleton process, a hot Codex Hero takeover, a single bootstrap
snapshot, local subjective reduction, and server-issued decision epochs. No
objective state, objective visibility, or available-action polling was used.

### Correctness Finding

The first live replay reached the exact Sorcerer `(7,12)` and Warrior `(7,11)`
geometry. Move was already correct: 92 of 97 destinations disclosed the first
visible Warrior threat exit. Jump was not. None of 35 Jump rows carried an
exposure, so `RangedSpacing` selected Jump to `(10,14)` as an apparently free
escape.

That was an affordance-contract defect. Jump is typed as voluntary movement,
and execution emits one `StepMovementEvent` per traversed cell. The same
opportunity-attack handler used by Move therefore reacts during Jump. The
policy was not making a poor comparison; the authoritative epoch omitted a
known consequence from one legal movement family.

### Integrated Change

- `BaseAction.get_disclosed_movement_path()` now provides an action-owned
  contract for deterministic, subjectively knowable traversal.
- Jump uses the same straight-line route method during target discovery and
  event creation, preventing discovery/execution geometry drift.
- Plain position discovery includes the action semantic key and visible threat
  signature in its cache key, then derives route-specific threat exits from
  the disclosed path.
- Teleports and nonmovement actions continue to return no traversed path. They
  do not inherit voluntary movement consequences accidentally.
- The disclosure remains subjective: it uses only living hostiles visible to
  the mover and reveals potential threat-boundary exposure, not hidden
  reaction availability or handler state.

### Live Result

The corrected replay reached the same adjacent state after the Sorcerer spent
its action on Dodge. The epoch contained 97 Move rows with 92 exposed routes
and 35 Jump rows with 32 exposed routes. The remaining unexposed destinations
stay inside the Warrior's threat area.

`RangedSpacing` selected its explicit hold-position proposal at `(7,12)` with
score `65.0`, represented by a typed End Turn intent. Policy evaluation took
`2.427 ms`. The command was accepted without movement or opportunity-attack
execution.

### Verification

- `uv run pytest tests/manual/test_31_subjective_runtime_epochs.py` - 28 passed
- focused Jump execution and lethal-opportunity-attack checks in
  `tests/engine_book/test_chapter_10_core_actions_combat.py` - 2 passed
- focused typed spacing policy check in
  `tests/manual/test_44_typed_agent_policy.py` - 1 passed
- focused Pyright over the action, entity, epoch, and regression-test modules -
  clean

### Next Targets

- Advance rotation slot 3 with direct Codex control of skeletons against the
  external AI Barbarian in `caster_crossfire`.
- Remove the forced claim replacement currently required when the hot runtime
  attaches to the Codex session pre-created by validation startup.
- Audit every voluntary movement action for an action-owned traversal contract
  before adding another movement type.
- Continue reducing epoch construction and local history latency.
- Unify the compact recommendation and PolicyHost surfaces.

## 2026-07-14 - Total Policy And Typed Threat Exposure V128

### Evidence

The completed direct Sorcerer artifact from V127 remains the behavioral source
for this follow-up. At the adjacent-Warrior decision, the shared policy selected
a retreat which crossed the Warrior's threatened boundary. The engine then
correctly resolved an opportunity attack for 3 damage. After that move, the
actor had no remaining action, movement, or visible contact, but the policy
returned no proposal instead of the legal End Turn command.

Those two failures were reproduced as typed policy and epoch tests before the
implementation changed. The retained game is still the pre-fix evidence; it
has not been rewritten to imply that the corrected policy made the original
choice.

### Integrated Change

- `TerminalFallback` is now an unconditional final branch of the shared
  behavior tree. Unknown tactical semantics on opaque or unaffordable rows no
  longer make the controller non-total.
- Movement targets now carry typed opportunity-attack exposure for both their
  ordinary route and safe route. The server derives it from the full path and
  only from subjectively visible, living hostile threat geometry.
- The disclosure says that a route exits a visible hostile's threatened area;
  it does not reveal whether the hostile secretly has an available reaction or
  an enabled reaction handler. Actual reaction execution remains authoritative
  engine behavior.
- `RangedSpacing` prices disclosed exposure as a utility cost and compares
  movement against an explicit hold-position proposal. A safe retreat can
  still win, while a provoking retreat must justify its risk.
- Codex move summaries consume exactly the same server-authored exposure. The
  client no longer invents opportunity-attack risk from endpoint adjacency.

### Verification

- `uv run pytest tests/manual/test_10_combat_resolution.py` - 7 passed
- `uv run pytest tests/manual/test_30_codex_takeover_tools.py` - 80 passed
- `uv run pytest tests/manual/test_31_subjective_runtime_epochs.py` - 27 passed
- `uv run pytest tests/manual/test_44_typed_agent_policy.py` - 36 passed
- `uv run pytest tests/manual/test_48_policy_host.py` - 15 passed
- focused external shared-host checks in
  `tests/manual/test_35_subjective_external_ai.py` - 4 passed
- focused Pyright over production modules and the new epoch, policy, host, and
  Codex-tool tests - clean

### Next Targets

- Replay the exact adjacent Sorcerer retreat and verify the live policy holds
  position or selects a genuinely safe route.
- Continue the rotation with Barbarian and skeleton-controlled perspectives
  before another Sorcerer-specific policy change.
- Profile movement execution, follow-up epoch construction, and local history
  consumption separately.
- Unify or remove the compact recommendation surface that currently competes
  with PolicyHost.
- Keep the complete affordance set locally while replacing exhaustive
  LLM-facing row dumps with typed selectors and summaries.

## 2026-07-14 - Direct Codex Sorcerer And Movement Cache Reconciliation V127

### Evidence

Rotation slot 2 used direct Codex control of the validation Sorcerer against
the external skeleton party in `standard_skeleton_doors`. The first attempt is
retained as
`evidence/direct_codex_runs/20260714-rotation-2-02-codex-sorcerer-vs-ai-transient-contact-regression.json`.
It stopped after the opening movement exposed a disagreement between the local
subjective world and the next legal-action epoch.

The completed replay is
`evidence/direct_codex_runs/20260714-rotation-2-02-codex-sorcerer-vs-external-ai-fixed.json`.
It ended in round 5 with the Sorcerer winning at 27 of 37 HP. The retained
record contains 217 subjective frames and 70 correlated agent events. Direct
play used only the hot local runtime and server-issued decision epochs; it did
not poll objective state, objective visibility, or `/available-actions`.

The Sorcerer explored until contact, hit the visible Archer and Warlock with
Fireball, allocated repeated Magic Missile projectiles across multiple
targets, and adapted to the Warlock's Shield reaction. After missiles killed
the Archer and Warrior, Shatter supplied guaranteed non-missile damage against
the 1 HP Warlock and ended the encounter.

### Correctness Finding

The apparent stream-removal bug was one layer deeper than the first diagnosis.
At each movement step, the spatial callback computed a visibility-only cache
before the mover's attached light source relocated. The light event then
updated live senses correctly, but movement completion reused the older
pre-light cache and erased the newly visible entities. The local materializer
retained the legitimate light-reveal events while the next authoritative epoch
had no hostile rows.

Incremental sensory updates now invalidate the one-shot visibility cache.
Movement completion also compares the observer cache before and after its full
refresh and emits any real reconciliation through the same typed
`SensoryUpdateEvent` lifecycle used by ordinary spatial callbacks. In the
replayed position, the Archer and Warlock remain visible, the warm refresh
matches a cold recomputation, and the next local epoch contains legal Fire
Bolt, Ray of Frost, Magic Missile, Scorching Ray, Shatter, and Fireball rows.

### Remaining Friction

- The first fixed movement measured about 116 ms end to end: 81 ms in the
  server command, 52 ms in movement execution, 29 ms constructing and
  publishing the next epoch, and 14 ms fetching local frame history. This is
  correctly instrumented but well above the external-runtime target.
- The compact recommendation and shared PolicyHost disagree at bootstrap:
  the former recommends `(2,4)`, while the latter selects `(7,12)`. Both
  objective functions are visible, but the operator surface does not explain
  or resolve the competing recommendations.
- After attacking, `RangedSpacing` moved away from an adjacent Warrior without
  pricing the disclosed opportunity attack. The Sorcerer took 3 damage. The
  spacing utility needs typed threatened-movement risk, not another
  action-name exception.
- When that move left no action, no movement, and no visible contact, every
  policy branch failed. A total policy must always emit the legal `End Turn`
  fallback when no stronger proposal survives.
- The bootstrap epoch contained 209 exhaustive rows. Completeness is correct,
  but routine decisions should use typed local selectors without serializing
  the entire row table into an LLM-facing response.

### Verification

- `uv run pytest tests/manual/test_12_perception_light_stealth_and_invisibility.py` - 9 passed
- focused movement-cache and paired-sensory tests in `tests/engine_book/test_chapter_12_senses_light_stealth.py` - 2 passed
- `uv run pytest tests/manual/test_28_subjective_observation_stream.py` - 18 passed
- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py` - 23 passed
- focused Pyright over the touched senses, action, and regression-test modules - clean

### Next Targets

- Make the shared policy total with an explicit terminal `End Turn` leaf.
- Add typed opportunity-attack exposure to movement affordances and spacing
  utility, then replay the exact adjacent-retreat decision.
- Continue rotation with the next Barbarian and skeleton-side slots rather
  than tuning only the Sorcerer matchup.
- Profile movement callbacks, cold AoE epoch construction, and local frame
  consumption separately until ordinary external commands are consistently
  in the low-millisecond range.

## 2026-07-14 - Typed Area Frontier And Exact Outcome Workspace V126

### Evidence

The standard Sorcerer-versus-skeleton replay used seed `8675315` throughout.
The baseline artifact
`evidence/runs/20260714-rotation-06j-ai-vs-ai-sorcerer-outcome-workspace.json`
ended in round 4 after 20 accepted commands. Its first dense Fireball decision
contained 439 disclosed legal rows, selected among 55 policy-distinct damage
seeds, and reached `7.355 ms` policy time.

The retained optimized replay is
`evidence/runs/20260714-rotation-06n-ai-vs-ai-sorcerer-bounded-allocation.json`.
It ended in round 1 after five accepted commands with the Sorcerer at 37 HP.
The command sequence was exploration, Haste Potion, bounded approach, then two
safe Fireballs. The objective post-run subjectivity audit passed with no
violations. This is a tactical behavior change, not merely a benchmark change:
independent area damage is no longer penalized as if damage applied to one
target consumed a finite projectile that could have hit another.

### Integrated Change

- Instantaneous `EACH_AFFECTED_ENTITY` damage rows now use a typed Pareto
  frontier. A row can dominate another only when the complete semantic
  reference, exact outcome profile, exact economy and resource costs, execution
  provenance, and unknown-or-neutral affected entities match.
- Hostile supersets and known-friendly subsets define dominance. Known friendly
  entities include both session-controlled actors and subjectively visible
  allies, so multiplayer allies are not treated as expendable unknowns.
- Allocated projectiles, persistent zones, summons, control, concentration,
  movement, topology changes, and information-changing actions are excluded
  from area pruning.
- `DamageOutcomeWorkspace` now shares raw dice distributions across targets
  with the same typed damage profile and subjectively known affinity
  multipliers. AC, save, HP, and application summaries remain target-specific.
- Multi-target allocation runs only for rows declaring more than one
  projectile. Ordinary entity and position rows no longer enter the allocator.
- Nested engine action timing, command HTTP time, and follow-up subjective
  synchronization are recorded separately in artifacts and dashboard series.

The typed frontier reduced the dense damage seeds from 55 to 32. The final
replay measured `5.427 ms` for its single dense policy decision. This is a
substantial reduction from the earlier `14.199 ms` ungrouped baseline, but it
is still near the 5 ms local-stage target and needs evidence across rotated
matchups rather than more repetitions of this seed.

### Verification

- `uv run pytest tests/manual/test_44_typed_agent_policy.py` - 28 passed
- `uv run pytest tests/manual/test_39_ai_validation_harness.py` - 16 passed
- `uv run pytest tests/manual/test_48_policy_host.py` - 14 passed
- `uv run pytest tests/manual/test_35_subjective_external_ai.py` - 121 passed
- `uv run pytest tests/manual/test_46_ai_dashboard_projection.py` - 5 passed
- focused Pyright over the touched policy, outcome, and test modules - clean

### Next Targets

- Start the next rotation with direct Codex Barbarian, then direct Codex
  Sorcerer; do not continue tuning this one Sorcerer seed.
- Move remaining compatibility selectors into explicit shared routines and
  utility choice points before adding new tactical exceptions.
- Continue reducing authoritative movement, senses/FOV, and epoch-generation
  latency without suppressing objective or subjective event envelopes.

## 2026-07-13 - Legal Spell Progression And Subjective Projection Performance V125

### Rotation Evidence

Rotation slots 5 and 6 completed the current six-game cycle with autonomous
external AI on both factions:

- slot 5: Barbarian versus the caster-crossfire party, seed `8675312`;
- slot 6: Sorcerer versus the standard skeleton party, seed `8675313`.

The final retained artifacts are:

- `evidence/runs/20260713-rotation-05e-ai-vs-ai-barbarian-path-cache.json`;
- `evidence/runs/20260713-rotation-06e-ai-vs-ai-sorcerer-path-cache.json`.

Both encounters ended normally, every selected command was accepted, and both
subjectivity audits passed. The Barbarian survived at 13 HP after 36 commands
and three rounds. The Sorcerer survived at 29 HP after 10 commands and two
rounds. Replays `05b` through `05e` and `06` through `06e` retained the same
seeded tactical outcomes after the deterministic-order correction.

### Correctness Findings

Generic caster progression was granting every spell-slot level from 1 through
9 to a level-5 caster. This made validation actors appear more capable than
their configured level and multiplied discovery variants. Full-caster slots
and proficiency now come from the shared progression table. Scenario actors
that intentionally exercise higher-level spells now declare a legally adequate
level.

AoE execution converted a set of affected UUIDs directly to a list. UUID hash
order therefore assigned the seeded random save and damage sequence to
different targets between processes. Both subjective previews and objective
execution now use one semantic target ordering: position, name, then UUID as a
final identity fallback. A seeded self-play regression compares both the
semantic command trace and final HP across complete runs.

Plain `POSITION` spells had been collected by the movement-action branch. The
resulting rows:

- omitted legal spell-slot variants;
- reported movement rather than spell costs;
- restricted spell centers to path-reachable cells;
- repeatedly created validation events for every path cell.

`PositionDiscoveryContract` now declares subjective candidate prerequisites.
Visible ground and zone spells use visible cells within range. Dimension Door
uses perceived walkability and perceived occupancy. Jump declares visible,
walkable, unoccupied, range-bounded destinations whose distance is also the
movement cost. Hidden occupancy does not remove a destination and leak its
existence; authoritative execution may reject the attempted destination.
Daylight, Telekinesis Move, and other custom-origin actions remain on their
specialized validators until their distinct contracts are modeled explicitly.

### Performance Changes

The optimization sequence followed focused failing contracts rather than a
whole-result legality cache:

1. GridMap caches barrier positions and propagation FOV by propagation
   revision.
2. AoE shape signatures serialize every stable shape-definition field, so cone
   angles and future shape fields cannot collide.
3. Actor-local AoE footprints are reused until visible geometry or propagation
   topology changes.
4. Actor-local AoE previews are keyed by visible contacts, perceived positions,
   faction, name, life state, and topology. Hidden entities never enter the
   key.
5. Plain-position and visible-center candidates are shared across equivalent
   spell variants.
6. Walking and swimming rows reuse revisioned subjective path facts. Swimming
   keeps its movement-mode terrain and missing-swim-speed penalties.
7. GridMap Dijkstra now shares per-cell walkability and per-edge directional
   side results across one query.
8. Propagation origins share revision-scoped directional blocker, edge, and
   blocking-cell facts.

Microbenchmarks on fresh validation actors changed as follows:

| Probe | Earlier warm | Current warm | Current cold |
|---|---:|---:|---:|
| standard Sorcerer | about 7 ms | about 1.7 ms | about 8.6 ms |
| Web control mage | above 5 ms | about 3.2 ms | about 15 ms |
| high-level Archmage | about 52 ms | about 4.4 ms | about 9-10 ms |
| 20-tile subjective path search | about 10 ms | about 4.5 ms | about 4.5 ms |

The final rotation artifacts kept local decision p95 below 4.1 ms. Slot 5
command-submit p95 fell from about 83 ms in `05c` to about 66 ms in `05e`.
Slot 6 fell from about 71 ms in `06c` to about 60 ms in `06e`.

### Remaining Cost

Cold caster discovery remains above the 5 ms local-stage target because the
first epoch materializes hundreds of AoE centers and their first physical
propagation footprints. Command submission also includes authoritative action
execution, event handling, sensory recomputation, next-actor advancement, and
follow-up epoch construction. These phases remain separately instrumented;
they must not be reported as policy time.

The next architectural performance step should make large spatial target
domains parametric in the decision epoch instead of eagerly materializing every
center as an independent row. That representation must still be complete,
typed, locally reducible, subjectively safe, and executable through the same
server legality boundary.

### Verification

- `uv run pytest tests/manual/test_31_subjective_runtime_epochs.py`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -k "seed_replays_semantic_decisions_and_outcomes"`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -k "external_epoch_projection_compacts_position_spell_rows_for_policy or external_epoch_projection_keeps_affordances_typed_for_speed or caster_policy_prefers_visible_offensive_spell or external_ai_normal_path_does_not_fetch_available_actions"`
- `uv run pytest tests/manual/test_09_action_discovery_and_costs.py`
- `uv run pytest tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py`
- focused Pyright over the touched engine, spell, and epoch modules

### Next Targets

- Replace eager spatial row expansion with a typed parametric target-domain
  contract while retaining server-authoritative execution.
- Continue the next six-game rotation from slot 1 with direct Codex Barbarian,
  then rotate to Sorcerer rather than tuning one matchup repeatedly.
- Keep engine execution, event projection, fact reduction, policy selection,
  and command transport timings separate in artifacts and dashboard charts.

## 2026-07-13 - Shared Combat Policy And Terminal Hot Runtime V124

### Context

Rotation slot 4 put direct Codex control over the three validation skeletons
against the external Sorcerer in `standard_skeleton_doors`. The Sorcerer won in
round 3 after killing the Warrior and Archer with area damage and finishing the
retreating Warlock with Fire Bolt. The immutable subjective record is
`evidence/direct_codex_runs/20260713-rotation-04-codex-skeletons-vs-ai-sorcerer.json`.

The game exercised the first shared PolicyHost combat slice. Both Codex and the
external Sorcerer received the same typed direct-damage candidates and complete
utility traces. The host selected the Archer's legal shortbow attack and both
Warlock Eldritch Blasts without relying on action display-name substrings. Door
navigation remained on the same shared hierarchy. Unsupported support,
movement, defense, and end-turn choices still fell through to the compatibility
policy, so this is an incremental migration rather than a completed AI stack.

Three live frictions were retained:

- the first local turn view took only `0.044 ms` to read, but contained 268
  legal rows, 23,580 characters, and an estimated 5,895 tokens;
- after encounter completion, `/v1/watch` consumed the final subjective state
  but waited forever for an epoch that could no longer exist;
- the direct-damage utility preferred free Fire Bolt over Magic Missile against
  a wounded last target because it knows generic resource cost but has no typed
  expected-outcome or kill-probability facts.

### Integrated Change

- Paired voluntary movement now emits one subjective movement transition per
  step while preserving both objective spatial-left and spatial-enter events.
  This removes duplicate observer removal/addition work without changing
  opportunity-attack or zone semantics.
- Added the first native shared combat candidates under PolicyHost. The
  hierarchy evaluates every tactical branch before utility ranking, preserves
  typed semantic tags, enforces visible-hostile subjectivity, and records the
  selected proposal and every rejected branch.
- External AI executes a host-owned combat proposal directly when one exists;
  its old reduced command DTO is a compatibility/telemetry adapter, not the
  authority for migrated direct-damage decisions.
- Attack events now distinguish raw damage rolls from actual HP loss after
  resistance and immunity. Parent event totals and combat logs report actual
  damage, while raw component rolls remain inspectable.
- Action API death reporting now walks the causal combat-log subtree and
  resolves target HP for multi-entity actions. Lethal Magic Missile therefore
  reports its exact death once even after the target leaves the living entity
  registry.
- `SubjectiveRuntime.wait_for_epoch()` now terminates explicitly when its local
  subjective encounter reaches `ended`. The hot runtime returns a typed
  terminal view with no epoch or legal rows, and the external subprocess exits
  cleanly instead of waiting on an impossible future turn.

No objective visibility, hidden target, creature statistic, spell effect, die
roll, or encounter setup was altered to improve the outcome.

### Verification

- `tests/manual/test_49_hot_codex_runtime.py`: 9 passed, including terminal
  watch completion and nonblocking health reads.
- Two focused external subjective-runtime tests passed, including terminal
  epoch-wait exit and stream-eviction recovery.
- `tests/manual/test_44_typed_agent_policy.py` and
  `tests/manual/test_48_policy_host.py`: 20 passed.
- Focused external host combat, typed semantics, and routine tests passed.
- `tests/manual/test_20`/Chapter 10 focused damage and lethal multi-target
  regressions passed; the unrelated exhausted-generator test defect remains in
  `KNOWN_ISSUES.md`.
- Chapter 12 senses tests and the complete subjective observation-stream file
  passed after the paired movement projection change.
- Focused Pyright over the shared policy, subjective runtime, hot runtime,
  external controller, event/damage paths, and regressions reported zero
  errors.

### Next Targets

- Run rotation slots 5 and 6 as autonomous Barbarian and Sorcerer matchups,
  retaining immutable JSON before further character-specific tuning.
- Add typed outcome estimates derived from disclosed action semantics and known
  target facts, then test resource reliability against cantrip conservation
  without introducing omniscient AC, saves, resistances, or HP.
- Factor repeated movement and area-target rows into a compact local query
  surface. Preserve the complete server-issued affordance set while avoiding a
  multi-thousand-token default LLM turn dump.
- Move the hot runtime from waiter-driven stream consumption to one background
  reducer so local health and turn reads remain current during opponent turns;
  keep exactly one subjective stream and one local materialization.
- Continue migrating visible-enemy movement, support/concentration, defense,
  and end-turn behavior into the shared hierarchy before deleting the
  compatibility policy.

## 2026-07-13 - Causal Identity And Monotonic Terminal Knowledge V123

### Context

The retained direct Sorcerer rotation exposed three subjective-state defects
that could mislead both a traditional policy and an LLM operator:

- the third Magic Missile dart could rename an already identified target to
  `Unknown` after an earlier dart killed it and removed it from live senses;
- a subjectively observed death survived only in a recent-log summary, while
  the canonical remembered entity regressed from `is_dead=True` to
  `is_dead=None`;
- Scorching Ray's parent summary treated three projectile applications as a
  requirement for three distinct target names, recursively promoting a Hero
  metamagic cleanup and a Skeleton Warrior concentration cleanup into spell
  targets.

The source evidence remains unchanged in
`evidence/direct_codex_runs/20260713-rotation-02-codex-sorcerer-vs-ai.json`.
Its seven friction annotations retain the original observations and cursors.

### Integrated Change

- Event registration now copies and unions identity-disclosure grants from the
  direct causal parent. This inheritance is naturally transitive, but cannot
  import sibling or completion-time information. A parent that never
  identified an entity still contributes no identifying observer.
- Death-caused sensory removal establishes a remembered `is_dead=True` fact.
  Full entity replay preserves that terminal knowledge when later redaction
  supplies `None`; an explicitly visible living fact can still clear it after
  resurrection.
- Snapshot and ownership replacement preserve known death while continuing to
  redact current HP, AC, conditions, faction, and affinities for non-visible
  entities.
- Typed `ContactFacts` now separates `known_dead_entity_uuids` from living
  visible contacts, living remembered contacts, and unknown contacts.
- The Codex turn summary includes remembered known-dead enemies directly from
  canonical entity memory. Recent combat logs explain the death but are no
  longer the only temporary death database.
- Objective and subjective multi-target summaries derive action targets from
  direct per-target child logs only. Nested reactions, deaths, and condition
  cleanup remain in `sub_entries`, but cannot redefine the parent action's
  target set.
- Dashboard projection schema 2 now validates and hashes both autonomous run
  artifacts and direct Codex artifacts. Direct rows derive command outcomes,
  frame/event counts, friction categories, and latency distributions from raw
  retained streams; absent policy identity and subjectivity-audit claims remain
  null.
- The dashboard renderer handles those intentionally absent claims as `n/a`
  and plots generic accepted/nonaccepted command counts across both controller
  modes. The generated ledger now contains eight autonomous and two direct
  immutable runs.

No objective rules, damage resolution, creature content, encounter setup, or
visibility range changed.

### Verification

- `tests/manual/test_28_subjective_observation_stream.py`: 18 passed, including
  causal-child identity, replay/resync death continuity, hidden identity, and
  multi-projectile summary isolation.
- `tests/manual/test_32_subjective_runtime_store.py`: 9 passed, including
  `True -> None` death preservation and explicit visible resurrection.
- `tests/manual/test_44_typed_agent_policy.py`: 11 passed with the dedicated
  known-dead contact partition.
- Focused Codex summary tests: 2 passed.
- Focused Magic Missile and Fireball engine tests: 2 passed.
- `tests/manual/test_05_event_lifecycle.py`: 6 passed.
- `tests/manual/test_46_ai_dashboard_projection.py`: 5 passed.
- The regenerated dashboard JSON validates with `json.tool`, and the extracted
  dashboard JavaScript passes `node --check`.
- Focused Pyright over the event, projection, materialization, typed fact,
  Codex presentation, dashboard projection, and regression files reported zero
  errors.

### Next Targets

- Replay the Sorcerer projectile/death sequence and retain a new immutable
  artifact proving the corrections in live event ordering.
- Continue rotation slot 3 with Codex controlling skeletons against the AI
  Barbarian after the replay, rather than tuning another Sorcerer policy case.
- Preserve the measured distinction between fast local reads and the current
  `84-100 ms` direct-command path when choosing the next performance target.

## 2026-07-13 - Hot Codex Runtime And Shared Policy Host V122

### Context

The engine-facing `SubjectiveRuntime` was already event-first and long-lived,
but every Codex CLI command launched a new interpreter, fetched another full
snapshot, rematerialized state, rebuilt the turn summary, submitted a command,
and often fetched a third snapshot. The typed policy contracts were similarly
incomplete in production: the door routine produced a real `PolicyProposal`,
but only after or before being adapted through the old external command DTO,
and no object owned one-command-per-epoch correlation.

### Integrated Change

- Added one authenticated loopback `hot-serve` process per Codex task. It owns a
  single `SubjectiveRuntime`, keeps the takeover lease alive independently of
  operator think time, and serves local brief, actions, turn, watch, execute,
  end-turn, health, and release calls.
- Local reads use the materialized subjective world and embedded decision epoch;
  they do not query `/available-actions`, `/state`, or `/visibility`.
- Every write carries the exact runtime, session, encounter, observation,
  epoch, and actor revision viewed by Codex. One nonblocking command-writer lock
  rejects concurrent writers, while the server remains the legality authority.
- Added a transport-free `PolicyHost` with actor/session/policy-scoped memory,
  immutable decision bindings, one submission per epoch, command-id
  correlation, and acceptance-gated routine advancement.
- Exposed the host's typed door proposal and trace directly in the hot Codex
  turn view. Selecting that row correlates the streamed result back into the
  same host; direct LLM selection of another legal row remains valid.
- Migrated the external subprocess's door lifecycle to the same host. The old
  external command model is now only a telemetry adapter for that already
  selected routine; combat behavior remains on the compatibility policy for
  later migration.
- Added a separate `direct_codex_run/v1` artifact containing only the initial
  subjective snapshot, later subjective frames, agent telemetry, perspective,
  rotation identity, and explicit friction notes. It does not fabricate winner,
  latency, or subjectivity metrics.
- Added local view-stage and command timing so daemon projection cost can be
  separated from authoritative engine execution.

### Live Smoke

An isolated Barbarian arena on port 8012 exercised real takeover and the local
daemon. The daemon bootstrapped at observation cursor 0, displayed the complete
Barbarian resource/economy state, submitted `Move` using the viewed epoch, and
settled at cursor 12 with a new action-completed epoch without a recovery
snapshot. Release restored the prior human controller.

The accepted movement took 43.185ms in the server command path. The action
executor reported 42.967ms, dominated by final FOV/senses/path recomputation:
directional FOV 7.761ms, entity-enter handling 13.740ms, and Dijkstra/safe-path
work about 24ms. This was a diagnostic smoke, not a retained rotation game,
because its pre-play snapshot was not captured by the new artifact collector.

### Verification

- `test_47_direct_codex_artifacts.py`: 5 passed.
- `test_48_policy_host.py`: 7 passed.
- `test_49_hot_codex_runtime.py`: 6 passed.
- `test_45_policy_routines.py`: 9 passed.
- Five focused external-policy/runtime checks passed, including live host-owned
  door selection and acceptance-gated memory.
- `test_36_seamless_subjective_runtime.py`: 17 passed.
- Focused Pyright over the new runtime, policy, artifact, external adapter, and
  tests reported zero errors.

### Next Targets

- Capture the initial subjective snapshot, then replay and retain the direct
  Codex Barbarian rotation slot through the hot daemon.
- Follow immediately with the direct Codex Sorcerer slot before another
  Barbarian-focused policy change.
- Measure the new local view timings in retained games and optimize only stages
  that violate the 5ms budget.
- Reduce the measured movement FOV/path recomputation without weakening senses,
  path correctness, or strict subjectivity.
- Migrate one combat choice point from compatibility commands to native host
  proposals after the two retained direct games expose the highest-value seam.

## 2026-07-13 - Immutable Subjective Ownership Transitions V121

### Context

A direct Codex Barbarian diagnostic completed against the external skeleton AI,
but its session history could not be retained honestly. Releasing the takeover
cleared every observation cache. The next read rebuilt old engine events from
cursor zero using the session's new empty ownership, current senses, and ended
encounter state. Previously observed frames changed identity and cursors, while
the original command and combat causality disappeared.

This was a subjective-runtime defect, not an operator-presentation problem. A
new game artifact or policy adjustment would have preserved evidence produced
by an invalid replay contract.

### Integrated Change

- New session projections begin at the current objective event cursor. The
  snapshot supplies current subjective state; pre-bootstrap engine events are
  not fabricated as session frames.
- Initialized sessions project completion events eagerly at event time, even
  when no observation SSE client is currently waiting.
- Takeover, release, lease expiry, validation takeover, and `/game/join`
  assignments now flush pending frames before ownership mutation.
- Ownership changes preserve the existing frame list and append one typed
  `session_control` state-replacement frame with a monotonic observation cursor.
- State replacement atomically updates session authority, encounter knowledge,
  observers, remembered entities and objects, seen tiles, logs, and the current
  epoch. Hot clients converge without a recovery snapshot.
- Previously observed logs remain session memory after release. Existing logs
  are filtered once at bootstrap and are never refiltered under later
  ownership.
- Takeover no longer clears unrelated projection caches, observation
  subscribers, or every session's epoch state. Only affected session epochs are
  invalidated and the active session receives a fresh epoch when appropriate.

No gameplay rule, creature content, policy priority, or objective event was
changed.

### Verification

- `tests/manual/test_28_subjective_observation_stream.py`: 15 passed.
- `tests/manual/test_32_subjective_runtime_store.py`: 8 passed.
- `tests/manual/test_36_seamless_subjective_runtime.py`: 17 passed.
- Six focused takeover claim, release, immutable-history, conflict, expiry, and
  session-reuse checks in `test_30_codex_takeover_tools.py` passed.
- Focused Pyright over the observation models, materializer, projector, server
  composition, and regressions reported zero errors.
- `test_18_sessions_api_client_contract.py` had four passing contracts and two
  unrelated hardcoded EventQueue-count failures. Those stale expectations are
  recorded in `KNOWN_ISSUES.md`.

### Evidence Status

The completed Barbarian diagnostic is not promoted to a rotation artifact: its
pre-fix subjective history was destroyed by release. The next direct Codex game
must exercise the corrected append-only stream and retain its JSON during play.

### Next Targets

- Run the missing direct Codex Barbarian rotation slot again and retain the
  subjective timeline before and after release.
- Replace the stateless Codex snapshot-rematerialization path with the shared
  long-lived `SubjectiveRuntime` and PolicyHost.
- Retain separate POST, server execution, projection, and post-command replay
  timing distributions before optimizing the measured Move and epoch hotspots.
- Continue the strict Barbarian, Sorcerer, skeletons rotation without treating
  diagnostic or unreplayable games as completed slots.

## 2026-07-13 - Typed Door Routine, Self-Target Saves, And Artifact Dashboard V120

### Context

The first hierarchical migration targeted the no-contact door sequence because
it spans several decision epochs and cannot be represented honestly as one
ordered action exception. The intended behavior is: approach a subjectively
known closed door, extend mobility only when ordinary movement cannot continue,
open the exact known object, then discard the routine and reassess the newly
revealed world.

The first seeded live validation reached both doors correctly but later stopped
on repeated Barbarian attack rejections. The trace initially made Reckless
Attack look suspicious. A full engine stack trace showed the real cause was the
target Archer's concentration check after taking damage: a self-origin
Constitution save was incorrectly treated as a cross-entity modifier contest.

The subsequent Sorcerer rotation remained tactically stable but exceeded the
local decision target because its migration adapter normalized 96 movement rows
plus up to 160 position-spell rows. The authoritative decision epoch already
retained every legal row; this was duplicate derived policy pressure.

Finally, the HTML dashboard still read a manually maintained iteration ledger.
Seven immutable run artifacts, including the new routine validations, were
absent from every time series. Historical nonnumeric policy metrics could also
produce invalid SVG `NaN` paths.

### Integrated Change

- Added the typed `routine.approach_open_reassess` contract with logical
  applicability, invariants, completion conditions, expected effects,
  preserved resources, explicit steps, and revalidation boundaries.
- Added actor/session-scoped routine progress and revalidation traces. Visible
  enemy contact interrupts the no-contact routine; accepted commands alone
  advance its step state.
- Bound door interaction to the exact subjectively known object UUID and
  explicit `is_open` fact. Production routine decisions do not parse display
  names.
- Preserved ordinary movement before mobility extension. Dash is selected only
  when the known door route can continue and no ordinary movement row makes
  progress.
- Fixed `Entity.saving_throw_bonus(self.uuid, ...)` and
  `Entity.skill_bonus(self.uuid, ...)` to aggregate local modifiers without
  importing the entity's own outgoing channels as `from_target` state. The
  strict cross-entity validator remains unchanged.
- Bounded the external policy's derived candidate projection to 48
  motive-diverse movement rows, eight centers per position-spell family, and 32
  position-spell rows overall. The local subjective store still retains the
  complete server-issued epoch.
- Bumped the traditional policy identity to
  `2026-07-13.enemy-policy-v16-typed-routines`.
- Added a deterministic schema-v2 dashboard projector. Human development
  `iterations` remain separate from machine-owned `runs`; every run records its
  artifact path, exact artifact-byte SHA-256, complete distributions,
  subjectivity result, and canonical chart metrics.
- Added separate run charts for local decision latency, server command latency,
  subjective transport, candidate pressure, command outcomes, and subjectivity.
  Invalid historical numeric values are excluded before SVG geometry is built.

### Retained Validation

`ai/evidence/runs/20260713-phase4-double-door-dark-hunt-seed8675310.json`:

- encounter ended in round 5;
- 59 accepted commands, zero rejected/stale/error commands;
- both closed doors were approached and opened through the typed routine;
- local decision p95/maximum: 3.179ms / 4.696ms;
- command submission p95/maximum: 75.384ms / 87.241ms;
- subjectivity audit passed with zero violations.

`ai/evidence/runs/20260713-phase4b-sorcerer-barbarian-seed8675311.json`:

- encounter ended in round 4;
- 22 accepted commands, zero rejected/stale/error commands;
- the Sorcerer retained the same Hold Person, Haste-item, Magic Missile, and
  ranged-spacing sequence after candidate reduction;
- local decision p95/maximum: 3.996ms / 4.049ms;
- command submission p95/maximum: 62.366ms / 65.424ms;
- subjectivity audit passed with zero violations.

The generated dashboard now preserves 173 prior human iterations and projects
all eight retained game artifacts as a separate ordered run series. A headless
browser rendered eight run rows, 173 iteration rows, six run charts, and 137
data points with no load errors, console errors, or invalid SVG geometry.

### Verification

- `tests/engine_book/test_chapter_06_entity_composition.py`: 17 passed.
- `tests/engine_book/test_chapter_14_spellcasting_core.py`: 19 passed.
- `tests/engine_book/test_manual_19_monsters_and_preset_actors.py`: 6 passed.
- `tests/manual/test_28_subjective_observation_stream.py`: 13 passed.
- `tests/manual/test_29_external_ai_subprocess.py`: 17 passed.
- `tests/manual/test_31_subjective_runtime_epochs.py`: 10 passed.
- `tests/manual/test_33_subjective_runtime_processors.py`: 3 passed.
- `tests/manual/test_35_subjective_external_ai.py`: 117 passed.
- `tests/manual/test_41_ai_run_artifacts.py`: 6 passed.
- `tests/manual/test_44_typed_agent_policy.py`: 11 passed.
- `tests/manual/test_45_policy_routines.py`: 9 passed.
- `tests/manual/test_46_ai_dashboard_projection.py`: 4 passed.
- Focused Pyright over the projector, candidate reducer, tests, and routine
  modules reported zero errors. The separately documented fast-Move annotation
  mismatch in `dnd/entity.py:3459` remains open.

### Next Targets

- Reduce the 60-90ms server command path. Local policy speed now satisfies the
  target, but authoritative action execution and follow-up epoch construction
  do not.
- Replace the remaining duplicate `ExternalAgentState` action representation
  with shared typed affordances and facts.
- Extend typed revalidating routines to move-attack, multi-target allocation,
  concentration management, defense, and remembered-contact search.
- Hash the complete policy bundle, not only `ai/external/policy.py`, so reducer,
  routine, fact, and semantic changes participate in exact policy identity.
- Complete the missing LLM-controlled rotation slots through the same
  subjective runtime and policy host rather than labeling deterministic
  self-play as Codex play.

## 2026-07-13 - Typed Action Semantics And Runtime Stall Removal V119

### Context

The retained phase-one duel proved that policy selection was already fast while
the surrounding runtime suffered unexplained 150-300ms stalls. At the same
time, the external policy still reconstructed action meaning from names and
compatibility dictionaries. This iteration classified those as two separate
problems: missing action semantics and process/runtime allocation behavior.

The known `Guardian of Faith` versus `Magic Missile` policy regression remains
intentionally unfixed. Adding another ordered spell exception would contradict
the hierarchical-policy goal.

### Integrated Change

- Added immutable typed action semantics with three-valued planning
  preconditions, costs, resources, concentration transitions, targeting,
  movement, topology, and information effects.
- Added stable action-definition semantic keys. Display and generated variant
  names no longer determine semantic classification.
- Carried deduplicated semantics through decision epochs by content address and
  interned repeated contracts in each subjective store.
- Fixed `AvailableActionInfo.requires_concentration`, which previously existed
  in the model but was never populated by entity discovery.
- Made fact-expression shapes canonical and compatibility tag ordering
  deterministic.
- Prevented duplicate or cursor-gap frames from mutating the local semantic
  cache and stopped deep-copying immutable prior subjective worlds for hooks.
- Replaced decorator-based request timing middleware with pure ASGI middleware.
  The former retained every POST caller through cancellation traceback cycles.
- Replaced whole-entity copies during contested saves/checks with scoped live
  targeting contexts that restore both entities in `finally`.
- Made spell discovery variants share their read-only definition graph; one
  deep executable instance is still created before mutable spell execution.
- Added a scoped runtime GC policy: young-generation cleanup remains normal,
  while useless full scans of the large live engine graph are deferred outside
  gameplay cadence.

No action was removed from a decision epoch, no hidden information was added,
and no tactical priority changed.

### Root-Cause Evidence

Before the fixes, one duel left roughly 209,000 objects in cancellation cycles.
Most were affordance, target, reduced-state, and subjective models retained by
POST caller frames. Pure ASGI timing reduced this to roughly 31,000 objects.

The remaining garbage consisted of complete Sorcerer copies created only to
evaluate contextual modifiers. After scoped target evaluation, full collections
reclaimed effectively no gameplay garbage, but still spent 110-175ms scanning
the large live Pydantic graph. Raising only the full-collection cadence removed
those scans from the active game without disabling normal young collection.

### Retained Validation

Artifact:

`ai/evidence/runs/20260713-phase2b-sorcerer-barbarian-seed8675309.json`

Same arena and seed as phase one:

- result: encounter ended in round 4;
- commands: 14 accepted, 0 rejected, 0 stale;
- elapsed self-play time: 896.682ms;
- policy p95/maximum: 0.333ms;
- reduction p95/maximum: 3.206ms;
- frame-apply batch p95/maximum: 8.826ms across up to 23 frames;
- command submission p95/maximum: 56.379ms including engine execution and
  in-process ASGI transport;
- total command path p95/maximum: 71.589ms;
- no generation-two collection occurred during the measured game.

The retained phase-one total-command maximum was 229.951ms, and the intermediate
phase-two artifact recorded a 338.523ms maximum. The unexplained
hundreds-of-milliseconds stalls are removed. Per-frame and engine subphase
budgets still require finer artifact aggregation; the current frame metric is a
whole catch-up batch, not one frame.

### Verification

- `uv run pytest tests/manual/test_42_action_semantics.py` passed 15/15.
- `uv run pytest tests/manual/test_32_subjective_runtime_store.py` passed 8/8.
- `uv run pytest tests/manual/test_43_ai_runtime_performance.py` passed 3/3.
- `uv run pytest tests/manual/test_13_spellcasting_core.py` passed 8/8.
- `uv run pytest tests/engine_book/test_chapter_06_entity_composition.py`
  passed 17/17.
- `uv run pytest tests/engine_book/test_manual_10_standard_conditions.py`
  passed 6/6.
- Focused Pyright over the semantic, store, epoch, server timing, and regression
  modules reported zero errors.

### Next Targets

- Replace `AgentState.variables` and the external reducer's duplicate action
  models with a typed shared `FactStore` and `PolicyContext`.
- Add typed routine semantics for facts read, applicability, progress,
  interruption, and invalidation.
- Build the first guarded hierarchical fallback subtree without changing
  tactical precedence.
- Add per-frame rather than per-catch-up latency distributions to retained
  artifacts.
- Continue the required rotation with a skeleton-controlled perspective after
  the fact/policy boundary is usable.

## 2026-07-13 - Unified Protocol, One Subjective World, And Durable Evidence V118

### Context

The unified-agent architecture work began from the existing event-first
subjective runtime rather than changing tactical behavior. The initial audit
found three foundational defects:

- observation envelopes imported decision-epoch and command models from the
  higher-level subjective runtime;
- `SubjectiveStore` retained separate observation and policy world objects with
  duplicated facts and epoch ownership;
- validation summaries survived, but their referenced raw `/tmp` traces did
  not, so dashboard claims could not be replayed.

The existing policy baseline was also measured before migration. Runtime and
stream tests were green, while the known persistent-zone expectation remained
red: `Magic Missile` was selected where the test expects `Guardian of Faith`.
This was retained as policy-architecture evidence rather than patched with a new
priority exception.

### Integrated Change

Added a dependency-neutral `ai.protocol.control` package for:

- action costs and action economy;
- affordance targets, rows, and sets;
- decision epochs and reasons;
- execute/end-turn requests;
- command result statuses and payloads.

Observation models now depend on this neutral protocol. Existing imports from
`ai.subjective.models` are temporary identity aliases only.

Added `SubjectiveWorldState` as the single materialized session world. It owns
typed session, encounter, observer, entity, object, tile, and current-epoch
state. `SubjectiveStore.world` is the only stored world object;
`store.materialized`, `ObservationMaterializedState`, and `WorldState` are
identity compatibility aliases rather than separately rebuilt state.

Agent telemetry now uses an absolute per-session cursor independent of bounded
deque length. History responses expose the earliest retained cursor and
`resync_required`; SSE subscribers receive `agent_history_evicted` when their
requested cursor can no longer be replayed completely.

Added a typed immutable validation artifact with:

- run identity, UTC timestamp, source revision, seed, arena, and controller
  mode;
- exact policy name, version, and source hash;
- participants and command-result counts;
- per-stage latency distributions;
- explicit subjectivity-audit status;
- the complete typed self-play result and raw command traces.

Seeded self-play restores the caller's random state after the run. Artifact
writes use exclusive creation and cannot silently overwrite prior evidence.

### Validation

Focused checks:

- `uv run pytest tests/manual/test_28_subjective_observation_stream.py -q`
  passed 13/13;
- `uv run pytest tests/manual/test_29_external_ai_subprocess.py -q` passed
  17/17;
- `uv run pytest tests/manual/test_31_subjective_runtime_epochs.py -q` passed
  9/9;
- `uv run pytest tests/manual/test_32_subjective_runtime_store.py -q` passed
  6/6;
- `uv run pytest tests/manual/test_34_agent_event_stream.py -q` passed 7/7;
- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q`
  passed 17/17;
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q -k
  "external_selfplay"` passed 4/4;
- `uv run pytest tests/manual/test_40_unified_agent_protocol.py -q` passed
  4/4;
- `uv run pytest tests/manual/test_41_ai_run_artifacts.py -q` passed 3/3;
- focused Pyright checks over the touched protocol, observation, subjective,
  server, external, evaluation, and test modules reported zero errors.

The complete external-policy file remained at the pre-existing baseline:

- 116 passed;
- 1 known failure for persistent-zone versus immediate-damage selection.

### Retained Baseline

Artifact:

`ai/evidence/runs/20260713-phase1-sorcerer-barbarian-seed8675309.json`

Run facts:

- arena: `sorcerer_barbarian_duel`;
- seed: `8675309`;
- result: encounter ended in round 4;
- commands: 14 accepted, 0 rejected, 0 stale;
- elapsed self-play time: 1618.869 ms;
- subjectivity audit: `not_run`, recorded honestly rather than inferred from
  passing controller tests.

Latency evidence:

- policy maximum: 0.312 ms;
- reduction p95/maximum: 3.096 ms;
- frame apply p95/maximum: 10.616 ms;
- frame fetch p95/maximum: 209.893 ms;
- command submission p95/maximum: 198.281 ms;
- total command path p95/maximum: 229.951 ms.

The policy itself is blazingly fast. Frame retrieval and command processing are
still far outside the declared few-millisecond budget.

### Next Targets

- Generate the dashboard evidence index from retained artifacts instead of
  manually copying run values.
- Add an objective post-run subjectivity validator so artifacts can prove, not
  assume, the disclosure boundary.
- Complete the typed knowledge and action-semantic layer before replacing the
  flat production selector.
- Build the first guarded hierarchical subtree without changing tactical
  precedence.
- Profile the retained `209.893 ms` frame-fetch and `198.281 ms` command-submit
  outliers by server subphase.

## 2026-07-04 - Target Pool Cache And Movement Candidate Compaction V117

### Context

V116 made damage/healing observation patches cheap enough that the next
alternating self-play batch exposed a different bottleneck: decision-epoch
available-action generation, especially repeated target-pool scans for
high-level spell variants and large movement/AoE candidate sets.

### Finding

The pre-change timing batch showed:

- `publish.followup_epoch.available_actions.entity_actions.target_pool_total_ms`
  up to 545.667ms;
- `target_pool.aid_slot_7_ms` up to 541.410ms;
- `target_pool.healing_word_slot_3_ms` up to 442.425ms;
- client-side `compact_position_actions_ms` up to 355.392ms in one noisy
  mixed run.

The target-pool work was repeated for many spell-slot variants even though
the subjective candidate set for a relationship filter is identical inside one
action-discovery call. Separately, the simple external behavior tree was still
receiving every movement row, even though it only needs a bounded candidate set
for approach, retreat, door movement, spacing, and exploration.

### Integrated Change

`Entity.get_available_actions()` now reuses per-call entity target pools for
registered entity actions and item/use entity actions. The cache is scoped to
one discovery request and keyed by:

- relationship filter;
- include-dead flag;
- include-self flag.

Template validation still runs per action and target, so the server remains
authoritative and subjectivity is unchanged.

The external AI reducer now compacts movement rows before policy reduction.
The server epoch remains complete; only the first simple external policy gets
a bounded, motive-diverse candidate set:

- approach visible or remembered enemies;
- approach known closed doors;
- retreat from visible threats;
- spread away from allies;
- keep safe/cheap fallback movement;
- keep frontier/exploration and long-distance fill rows.

### Validation

Focused checks:

- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q -k "timing or epoch or command"`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q -k "external_selfplay_runs_sorcerer_barbarian_duel_through_epoch_commands or external_selfplay_continues_after_counterspell or traces_spacing_reference_context or area_spell_affected_entities"`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "external_epoch_projection_compacts_movement_rows_by_motive or external_epoch_projection_keeps_affordances_typed_for_speed or external_projection_and_reducer_populate_timing_sinks"`
- `uv run pyright ai/external/state.py dnd/entity.py tests/manual/test_35_subjective_external_ai.py tests/manual/test_39_ai_validation_harness.py`

Post-change alternating external-vs-external batch:

- total runs: 8;
- encounter-ended: 8/8;
- rejected/non-accepted commands: 0;
- total commands: 127;
- average run time: 2320.343ms;
- `policy_ms` max: 0.870ms;
- `reduce_ms` max: 49.668ms;
- `compact_position_actions_ms` max: 44.900ms;
- `normalize_position_actions_ms` max: 3.461ms;
- follow-up target-pool max: 0.111ms;
- active-turn target-pool max: 0.080ms.

The target-pool spike is gone. Client-side position reduction is still not
perfect, but it is no longer the dominant hundreds-of-ms path in this sample.

### Next Targets

- Server-side position/AoE discovery still spikes:
  `collect_aoe_actions_ms` reached 417.643ms and
  `collect_path_actions_ms` reached 258.263ms.
- Observation projection still had a noisy partial HP patch outlier around
  203ms in this batch; verify whether this is real work or measurement noise.
- Continue rotating Sorcerer, Barbarian, and skeleton-side validation while
  checking behavior, not only speed.

## 2026-07-04 - Partial HP Entity Patches V116

### Context

V115 removed redundant full entity fact patches from roll-result bookkeeping
events. The next timing pass showed that damage and sensory visibility updates
were still spending too much time in entity fact construction, especially AC
and repeated HP/death calculations.

### Finding

The first probe after adding `_entity_fact` subphase timing showed:

- `publish.command_result.projection.entity_fact.ac_ms` up to 181.152ms;
- `publish.command_result.projection.project_completion_event_detail.take_damage.state_patches.entity_fact_ms` remained a visible source of command latency;
- sensory entity-added work also routed through full entity fact construction.

Damage and healing do not change AC, conditions, damage affinities, faction, or
position. They need to update HP and dead/alive state only.

### Integrated Change

Observation projection now emits partial `entity_update` patches for damage
and healing events:

- `hp`;
- `is_dead`.

The materializer merges those partial updates into the existing known entity
fact instead of replacing the whole fact. Full entity facts remain in place for
initial visibility, conditions, equipment, movement, perceivability, and death
events.

The HP/death helper now computes total HP, max HP, and normal-HP death state in
one pass. That avoids repeated Constitution/max-HP work and avoids calling
`has_hp` after HP was already computed.

### Validation

Focused checks:

- `uv run pytest tests/manual/test_28_subjective_observation_stream.py -q`
- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q -k "timing or epoch or command"`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q -k "external_selfplay_runs_sorcerer_barbarian_duel_through_epoch_commands or external_selfplay_continues_after_counterspell or traces_spacing_reference_context or area_spell_affected_entities"`
- `uv run pyright ai/observation/projector.py ai/observation/materializer.py tests/manual/test_28_subjective_observation_stream.py ai/external_selfplay.py tests/manual/test_39_ai_validation_harness.py`

Post-change alternating external-vs-external batch:

- total runs: 8;
- encounter-ended: 8/8;
- rejected/non-accepted commands: 0;
- total commands: 168;
- snapshot loads: 15;
- `policy_ms` max: 0.602ms;
- `reduce_ms` max: 15.133ms;
- entity fact `ac_ms` max: 5.172ms;
- take-damage partial HP patch max: 6.589ms;
- `command_submit_ms` max: 668.097ms;
- `total_command_ms` max: 705.725ms.

This removes the avoidable entity-fact/HP projection spike. The system is still
too slow overall, but the bottleneck has moved again.

### Next Targets

- Investigate follow-up `get_available_actions` target-pool generation for
  support spells such as Aid, Bless, and Healing Word.
- Investigate dirty-senses/path recomputation outliers where Dijkstra and
  `can_enter` dominate command time.
- Continue alternating Sorcerer, Barbarian, and skeleton-side validation while
  measuring speed and behavior.

## 2026-07-04 - Roll Event Entity Patch Pruning V115

### Context

V114 moved self-play onto persistent subjective stores and exposed compact
server timing for each command. The next timing probe rotated through:

- `sorcerer_barbarian_duel`;
- `standard_skeleton_doors`;
- `skeleton_mark_focus_fire`;
- `high_level_spell_resource_duel`;
- `concentration_control_crossroads`.

The behavior remained useful, but timing showed that projection still rebuilt
full entity facts for some roll-result bookkeeping events.

### Finding

Before this change, the slowest projection state-patch subphases included:

- `save_d20_roll.state_patches.entity_fact_ms` up to 251.282ms;
- `attack_d20_roll.state_patches.entity_fact_ms` up to 208.040ms;
- broad command totals still reached 839.059ms in the sampled batch.

Those roll-result events do not mutate the entity facts that the local
subjective store keeps. They are important as subjective event/log evidence,
but they do not need to refresh hp, AC, conditions, position, faction, or
damage affinities.

### Integrated Change

Projection now only emits referenced-entity fact patches for event types that
can change visible entity facts:

- movement and forced movement;
- damage and healing;
- condition application/removal;
- equipment changes;
- spatial entity/perceivability changes;
- death-related events.

Roll-result event frames still project when visible, and combat-log visibility
filtering is unchanged. The patch only removes redundant entity-fact refreshes
from non-mutating roll bookkeeping events.

Projection timing now also records state-patch subphases for session,
encounter, entity fact, tile, and object patch construction, so future speed
passes can rank the exact slow path instead of reading only broad
`build_patches_ms`.

### Validation

Focused checks:

- `uv run pytest tests/manual/test_28_subjective_observation_stream.py -q`
- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q -k "timing or epoch or command"`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q -k "external_selfplay_runs_sorcerer_barbarian_duel_through_epoch_commands or external_selfplay_continues_after_counterspell or traces_spacing_reference_context or area_spell_affected_entities"`
- `uv run pyright ai/observation/projector.py ai/external_selfplay.py tests/manual/test_28_subjective_observation_stream.py tests/manual/test_39_ai_validation_harness.py`

Post-change alternating external-vs-external batch:

- total runs: 8;
- encounter-ended: 8/8;
- rejected/non-accepted commands: 0;
- total commands: 219;
- snapshot loads: 15;
- `policy_ms` max: 0.751ms;
- `reduce_ms` max: 14.616ms;
- state-patch entity fact max in the sampled batch: 9.040ms;
- `command_submit_ms` max: 690.310ms;
- `total_command_ms` max: 747.818ms.

The targeted projection waste is reduced, but the overall system is still not
fast enough. The newly visible top costs are sensory update patch construction,
spell/action execution, action economy spell-slot normalization, and follow-up
available-action generation.

### Next Targets

- Optimize sensory-update tile patching without losing terrain/hazard
  subjectivity.
- Investigate the spell-slot/action-economy timing outlier in follow-up epoch
  generation.
- Keep alternating Sorcerer, Barbarian, and skeleton-side rotations while
  measuring speed.

## 2026-07-04 - Persistent Self-Play Subjective Stores V114

### Context

V113 made behavior cleaner across Sorcerer, Barbarian, and skeleton rotations,
but the fast validation loop still rebuilt a subjective snapshot for every
selected command. That was both slower than the intended agent architecture and
a weaker test of the event-first subjective runtime.

### Integrated Change

The in-process external-vs-external self-play harness now keeps one
`SubjectiveStore` per AI session:

- the store bootstraps from `/ai/sessions/{session_id}/observation/snapshot`
  once per session;
- before each command, it catches up through
  `/ai/sessions/{session_id}/observation/frames`;
- after each command, it applies the command-result and follow-up epoch frames;
- if a cursor gap appears, it resyncs through the subjective snapshot endpoint.

This preserves the same fairness boundary: the harness still consumes only
session-subjective observation and command endpoints. It does not read
objective state for decision input.

Self-play traces now include:

- whether a command loaded a snapshot;
- frame fetch/apply timings;
- frame count;
- compact server-side command timing payloads.

### Validation

Focused checks:

- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q -k "external_selfplay_runs_sorcerer_barbarian_duel_through_epoch_commands or external_selfplay_continues_after_counterspell or traces_spacing_reference_context or area_spell_affected_entities"`
- `uv run pyright ai/external_selfplay.py tests/manual/test_39_ai_validation_harness.py`

Post-change alternating external-vs-external batch:

- total runs: 12;
- encounter-ended: 12/12;
- rejected/non-accepted commands: 0;
- total commands: 254;
- snapshot loads: 21, bounded to session bootstraps/resyncs rather than every command;
- Sorcerer vs Barbarian duel: 4/4 ended;
- skeleton door/focus-fire runs: 4/4 ended;
- high-level spell-resource runs: 2/2 ended;
- concentration-control runs: 2/2 ended.

Timing is now more informative, but not yet acceptable:

- `policy_ms` max: 0.892ms;
- `frame_fetch_ms` max: 425.560ms;
- `frame_apply_ms` max: 41.800ms;
- `reduce_ms` max: 320.932ms;
- `command_submit_ms` max: 727.614ms;
- `total_command_ms` max: 768.999ms.

The policy selector itself is fast. The remaining speed work is in projection,
affordance/reduction, and command endpoint phases.

### Next Targets

- Use the preserved server timing payloads to rank command endpoint phases in
  high-level spell duels.
- Reduce observation projection/catch-up cost when many frames are accumulated.
- Keep the rotation balanced across Sorcerer, Barbarian, skeleton doors, and
  skeleton focus-fire while optimizing.

## 2026-07-04 - Bounded Remembered Search And Self-Play Class Pressure V113

### Context

V112 fixed rejected movement recovery, but a class-pressure batch still showed
one command-cap run where an actor repeatedly pursued an invisible or
last-known enemy without reacquiring contact. This rotation deliberately used
faster external-AI-vs-external-AI self-play instead of NeuroClient:

- `high_level_spell_resource_duel` x4;
- `concentration_control_crossroads` x3;
- `sorcerer_barbarian_duel` x6;
- `standard_skeleton_doors` x1;
- `skeleton_mark_focus_fire` x1.

### Finding

The Sorcerer vs Barbarian duel is useful and already runs cleanly through the
external self-play harness. The harder failure mode was not the old
pre-contact perception leak. It appeared after subjective contact, when the
policy had remembered-position facts but no strong reveal/search model.

Two related issues came out:

- remembered-position pursuit needed a local bound, otherwise the same
  non-reacquired last-known target could keep consuming turns;
- opening with Invisibility or Greater Invisibility is poor for this simple
  policy until the agent has a principled search/reveal model for invisible
  actors.

### Integrated Change

Added `ExternalPolicyMemory`, shared by the live external agent and the
in-process external self-play harness. It records accepted
`move_toward_remembered_enemy` attempts by target UUID and remembered position,
then suppresses that remembered target after repeated failed pursuit. It clears
automatically when the target becomes visible again or its remembered position
changes.

The policy now annotates remembered-pursuit commands with their reference
entity UUID/name/position/distance so traces explain which subjective fact drove
the move.

The simple external policy no longer treats Invisibility or Greater
Invisibility as preferred opening support/self-buff rows. This does not remove
those spells or items from content; it only avoids a weak tactical choice until
the policy has proper reveal/search handling.

### Validation

Focused checks:

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "policy_memory or remembered_enemy or self_buff or support_policy or annotations or invisibility"`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q -k "external_selfplay_runs_sorcerer_barbarian_duel_through_epoch_commands or external_selfplay_continues_after_counterspell or traces_spacing_reference_context"`
- `uv run pyright ai/external/policy.py ai/external/__init__.py ai/external_melee_agent.py ai/external_selfplay.py tests/manual/test_35_subjective_external_ai.py tests/manual/test_39_ai_validation_harness.py`

Post-fix external-vs-external batch:

- total runs: 15;
- encounter-ended: 15/15;
- command-cap: 0/15;
- rejected/non-accepted commands: 0;
- Sorcerer vs Barbarian duel: 6/6 ended;
- total commands: 396;
- average commands per run: 26.40;
- average run time: 4259.33ms;
- `snapshot_ms` max: 597.456ms;
- `reduce_ms` max: 285.249ms;
- `command_submit_ms` max: 518.786ms;
- `total_command_ms` max: 647.182ms.

The self-play loop is now the right fast iteration path for class-pressure and
monster-AI changes. NeuroClient should be used after that for UI-facing feel,
not as the primary policy debugger.

### Next Targets

- Move self-play closer to the long-lived subjective runtime path instead of
  snapshot-loading every command.
- Add a real search/reveal model before re-enabling Invisibility as a preferred
  tactical setup.
- Continue rotating Sorcerer, Barbarian, skeleton-door, and mark/focus-fire
  arenas before adding more monster content.

## 2026-07-04 - Class Pressure Rejected Movement Recovery V112

### Context

After the skeleton V111 slice, this rotation returned to class-pressure arenas:

- `sorcerer_barbarian_duel` x2;
- `high_level_spell_resource_duel` x2;
- `concentration_control_crossroads` x2;
- `teleport_escape_skirmish` x2.

The first batch had 7/8 encounter-ended runs and one
`command_rejected` run. The rejected command was a `Move` selected by
`move_toward_remembered_enemy` after a long remembered-position pursuit.

### Finding

The rejected movement was not a false enemy leak. It happened after subjective
contact had already been established and the actor was pursuing a last-known
position. The problem was command reliability at the POMDP boundary:

- the local policy selected a movement row that appeared useful for remembered
  pursuit;
- the engine rejected the action because the movement produced zero steps;
- the self-play harness treated that single rejected row as a terminal run
  failure, even though the live external agent already blocks rejected rows and
  retries within the current turn.

An intermediate attempt to make unreachable remembered pursuit hold in place
was too conservative. It produced long invisible/remembered-target stalls, so
that behavior was removed instead of becoming policy.

### Integrated Change

`move_toward_remembered_enemy` now only claims remembered-route progress when
the selected movement target carries a concrete route starting at the actor.
Rows without path proof can still be used by later generic exploration, but
they are no longer labeled as known last-position pursuit.

The in-process external-vs-external self-play harness now mirrors the live
external agent's rejected-row behavior more closely:

- rejected rows are stored by actor/round/turn and suppressed on the next tick;
- repeated rejection can suppress the broader template after local evidence
  accumulates;
- one rejected row no longer aborts the whole validation run.

This is agent-interface reliability and validation-harness fidelity work. It
does not change D&D rules, legal action generation, subjective visibility,
monster gear, or NeuroClient endpoints.

### Validation

Focused checks:

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "remembered_enemy or concrete_route or no_contact or typed_for_speed"`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q -k "external_selfplay_runs_sorcerer_barbarian_duel_through_epoch_commands or external_selfplay_continues_after_counterspell or traces_spacing_reference_context"`
- `uv run pyright ai/external/policy.py ai/external_selfplay.py tests/manual/test_35_subjective_external_ai.py tests/manual/test_39_ai_validation_harness.py`

Post-fix class-pressure batch:

- total runs: 10;
- encounter-ended: 9/10;
- command-cap: 1/10;
- rejected/non-accepted commands: 0;
- total commands: 387;
- average run time: 7185.10ms;
- `reduce_ms` max: 390.742ms;
- `snapshot_ms` max: 598.630ms;
- `command_submit_ms` max: 837.943ms.

The reliability problem is fixed for this sample, but the one command-cap run
shows the next behavior problem clearly: remembered/invisible target pursuit can
still alternate between last-known movement, exploration, and end-turn for too
long without a better search/reacquisition model.

### Next Targets

- Add a bounded remembered-target search state so invisible/last-known pursuit
  does not loop indefinitely after repeated non-reacquisition.
- Move self-play closer to the long-lived subjective runtime path so validation
  does not snapshot-load every command.
- Keep rotating class-pressure with skeleton door/spacing checks before adding
  more monster content.

## 2026-07-04 - Subjective Remembered Snapshot Skeleton Rotation V111

### Context

The previous Sorcerer-heavy probes exposed a subjective-state problem at the
snapshot/resync boundary. During ordinary frame replay, an enemy that left sight
could become a remembered last-known entity. A fresh snapshot, however, rebuilt
known entities only from current senses and controlled actors, so a long-lived
agent that resynced could lose a living enemy it had already perceived.

This pass finished that fix and rotated back to skeleton-facing validation:

- `standard_skeleton_doors` x2;
- `double_door_dark_hunt` x2;
- `skeleton_anti_aoe_split` x2;
- `skeleton_mark_focus_fire` x2.

All games used the fast in-process external-vs-external epoch loop. The live
NeuroClient backend was not touched.

### Finding

The data-layer issue was not a new omniscience leak. It was the opposite:
session-subjective memory could disappear during fresh snapshot construction.
The materialized stream had already learned a remembered entity through safe
projected frames, but snapshot construction did not merge those remembered
facts back into the bootstrap/recovery payload.

That matters for the agent-side runtime because resync must be conservative and
complete: it should not expose objective hidden state, but it also should not
erase facts the session had already earned.

### Integrated Change

`build_observation_snapshot()` now projects the current session frame history
before final snapshot assembly and merges only session-projected remembered
entity facts into the snapshot entity surface. The merge is restricted to facts
that already appeared in that session's subjective frames, so it preserves
subjectivity. Fresh snapshots now carry last-known position and knowledge state
for remembered entities without leaking currently hidden HP.

This is a subjective sensor/runtime correctness change. It does not alter legal
actions, engine visibility, controller policy ordering, monster content, gear,
or the human/NeuroClient endpoints.

### Validation

Focused checks:

- `uv run pytest tests/manual/test_28_subjective_observation_stream.py -q -k "fresh_snapshot_preserves_remembered_entity or snapshot_plus_frames_replays or unseen_enemy_movement or nested_hidden_identity"`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "remembered_enemy or no_contact or typed_for_speed"`
- `uv run pyright ai/observation/projector.py ai/external/state.py tests/manual/test_28_subjective_observation_stream.py tests/manual/test_35_subjective_external_ai.py`

Skeleton-facing external-vs-external batch:

- total runs: 8;
- encounter-ended: 8/8;
- total commands: 345;
- average run time: 4367.21ms;
- non-accepted commands: 0;
- broad `reduce_ms` max: 5.657ms;
- `snapshot_ms` max: 396.175ms;
- `command_submit_ms` max: 511.235ms.

The behavior stayed plausible: doors opened, double-door navigation completed,
anti-AoE spacing appeared, Mark Target/focus-fire appeared, and no pre-contact
enemy leakage was visible in the reduced state.

### Next Targets

- Move self-play closer to the long-lived subjective runtime path so it does
  not snapshot-load every command.
- Investigate the command-submit boundary cost separately from reducer/policy
  cost.
- Rotate next to Sorcerer/Barbarian class pressure rather than another skeleton
  pass.

## 2026-07-04 - Barbarian Typed Affordance Projection V110

### Context

After the skeleton-side V109 pass, this rotation moved to Barbarian-facing
validation and used the fast in-process external-vs-external loop:

- `ranged_loadout_kiting_ring` x3;
- `teleport_escape_skirmish` x3;
- `condition_lock_sanctum` x3;
- `zone_control_web_gauntlet` x3.

The games all completed and the behavior remained plausible: Barbarian martial
setup appeared, ranged spacing appeared, control zones landed, mobility escape
appeared, and no non-accepted commands were observed.

### Finding

The V109 fix removed position-row serialization, but the same avoidable
dict-roundtrip remained for the other buckets. In the pre-fix Barbarian batch:

- `entity_rows_ms` max: 367.053ms;
- `self_rows_ms` max: 15.187ms;
- broad `reduce_ms` max: 419.393ms;
- `compact_position_actions_ms` max: 416.546ms.

The behavior tree itself was still not the slow path:

- policy max: 0.843ms;
- materialization max: 0.171ms;
- `normalize_position_actions_ms` max: 3.897ms.

### Integrated Change

`available_actions_payload_from_epoch()` now keeps entity, position, self, and
object rows as typed `ActionAffordance` objects for the internal external-AI
payload. The reducer already supports both typed rows and legacy dict rows, so
this removes the remaining avoidable serialization while preserving older dict
payload compatibility where tests and debug helpers still use it.

This is an internal agent-interface performance change. It does not alter legal
actions, action economy, targeting, command execution, subjectivity, spells,
monster content, or gear.

### Validation

Focused checks:

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "epoch_projection or projection_and_reducer or position_spell_compaction or typed_for_speed or filter_action_payload_rows"`
- `uv run pyright ai/external/state.py tests/manual/test_35_subjective_external_ai.py`

Post-fix Barbarian-facing batch:

- total runs: 8;
- encounter-ended: 8/8;
- total commands: 303;
- average run time: 4429.23ms;
- `compact_position_actions_ms` max: 7.369ms;
- broad `reduce_ms` max: 10.826ms;
- `normalize_position_actions_ms` max: 2.899ms;
- policy max: 0.718ms.

The newly visible slow boundaries are now outside the reducer:

- `snapshot_ms` max: 447.039ms;
- `command_submit_ms` max: 453.244ms;
- `total_ms` max: 501.871ms.

### Next Targets

- Move self-play closer to the long-lived subjective runtime path so it does
  not snapshot-load every command.
- Investigate command-submit boundary cost separately from policy/reducer cost.
- Rotate next to Sorcerer-facing validation before more Barbarian tuning.

## 2026-07-04 - Skeleton Typed Position Affordance Projection V109

### Context

This pass answered two validation questions at once:

- yes, `sorcerer_barbarian_duel` is already available and should be part of the
  regular challenge loop;
- yes, the in-process external-vs-external runner is the right fast iteration
  surface for bulk AI probes.

Before the fix I ran `sorcerer_barbarian_duel` x6 with alternating initiative
order. The fixture behaved like a useful pressure test: Sorcerer-first won 3/3
by using `Hold Person` and `Magic Missile`, while Barbarian-first won 3/3 by
closing and using martial setup/attacks. The same run also showed that
position-row projection was still doing wasted serialization work:

- pre-fix duel `position_rows_ms` max: 257.451ms;
- pre-fix duel broad `reduce_ms` max: 260.953ms.

### Integrated Change

`available_actions_payload_from_epoch()` now keeps compacted position rows as
typed `ActionAffordance` objects instead of converting them to legacy dicts and
then immediately normalizing them back into policy rows. The external reducer
now accepts both shapes:

- entity/self/object rows remain legacy dicts for compatibility;
- position rows use the typed epoch affordance path;
- local suppression/filtering works for dict rows and typed affordance rows.

This is an agent-interface performance change only. It does not alter legal
actions, target selection, command execution, subjectivity, action economy, or
monster/class content.

### Validation

Focused checks:

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "epoch_projection or projection_and_reducer or position_spell_compaction or typed_for_speed"`
- `uv run pyright ai/external/state.py tests/manual/test_35_subjective_external_ai.py`

Post-fix `sorcerer_barbarian_duel` x6:

- encounter-ended: 6/6;
- average commands: 18.33;
- average run time: 1959.20ms;
- `position_rows_ms` max: 0.001ms;
- broad `reduce_ms` max: 4.445ms;
- `normalize_position_actions_ms` max: 3.168ms.

Post-fix skeleton-side sweep:

- arenas: `standard_skeleton_doors` x2, `double_door_dark_hunt` x2,
  `skeleton_anti_aoe_split` x2, `skeleton_mark_focus_fire` x2;
- encounter-ended: 8/8;
- total commands: 368;
- `position_rows_ms` max: 0.001ms;
- `compact_position_actions_ms` max: 2.248ms;
- broad `reduce_ms` max: 5.911ms;
- `normalize_position_actions_ms` max: 2.700ms.

The behavior stayed plausible: door/exploration, ranged spacing, visible-enemy
pressure, and focus-fire branches all appeared in the skeleton sweep.

### Next Targets

- Make the self-play harness closer to the long-lived subjective runtime path
  instead of snapshotting every command.
- Keep `sorcerer_barbarian_duel` in the regular rotation as a high-signal class
  pressure fixture.
- Move the next behavior pass to challenge quality, not projection speed, unless
  snapshot or command-submit latency becomes the new bottleneck.

## 2026-07-04 - Sorcerer Lean Affordance Serialization V108

### Context

This rotation moved to Sorcerer-facing validation after the Barbarian timing
attribution slice. The batch stressed spell-heavy and reaction-heavy arenas:

- `high_level_spell_resource_duel` x4;
- `concentration_control_crossroads` x4;
- `reaction_counterspell_lab` x4;
- `multi_projectile_no_aoe_lab` x4.

The goal was to test the V107 finding in the worst possible place: Sorcerer
epochs with many spell, counterspell, area, and position rows.

### Finding

The pre-fix Sorcerer run confirmed that the external behavior tree is not the
slow path:

- policy average: 0.263ms;
- policy max: 0.723ms;
- reduced-state subphases stayed small, with `normalize_position_actions_ms`
  maxing at 5.604ms.

The expensive path was still epoch-to-policy projection:

- `position_rows_ms`: 759.110ms;
- `entity_rows_ms`: 663.668ms;
- `self_rows_ms`: 406.659ms;
- `compact_position_actions_ms`: 629.153ms.

The serializer was doing avoidable per-row work: Pydantic `model_dump()` for
every cost object, duplicated target serialization code, and nested list
conversions for path-like fields that the reducer can already normalize from
tuples.

### Integrated Change

- Added lean cost serialization for external affordance projection.
- Centralized target serialization through `_target_to_legacy_dict()`.
- Removed duplicated `num_projectiles` output.
- Kept single `position` values JSON-style for existing row-shape compatibility.
- Avoided list conversion for path and affected-position collections inside the
  internal reducer payload.

This is an internal agent-interface performance change. It does not alter legal
actions, available epochs, command execution, targeting, subjectivity, or spell
rules.

### Validation

Focused checks:

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "epoch_projection or projection_and_reducer or position_spell_compaction or multi_entity_target_options"`
- `uv run pyright ai/external/state.py tests/manual/test_35_subjective_external_ai.py`

Post-fix Sorcerer batch:

- total runs: 16;
- encounter-ended: 14;
- command-cap: 2, both in `high_level_spell_resource_duel`;
- total commands: 768;
- policy average: 0.236ms;
- policy max: 0.876ms;
- broad reduce average: 16.376ms, down from 45.762ms pre-fix.

Projection timing changes:

- `entity_rows_ms` max: 663.668ms -> 5.274ms;
- `self_rows_ms` max: 406.659ms -> 0.961ms;
- `compact_position_actions_ms` max: 629.153ms -> 374.573ms;
- `position_rows_ms` max: 759.110ms -> 645.800ms.

So the optimization worked for entity/self rows and improved the broad average,
but position rows remain too expensive. The next performance slice should stop
serializing large position-row payloads through the legacy dict shape and either
compact harder or let the policy consume epoch rows directly.

### Next Targets

- Rotate next to skeleton-side before more Sorcerer-specific work.
- Target position-row projection directly: movement and position-spell rows
  still dominate the slow path.
- Investigate high-level no-contact command caps separately; those are behavior
  search/end-state issues, not the same as projection cost.

## 2026-07-04 - Barbarian Self-Play Timing Attribution V107

### Context

This rotation moved to Barbarian-facing validation after the skeleton open-door
frontier slice. I sampled hazard and control arenas rather than replaying the
same V104 healing pair:

- `forced_movement_hazard_bridge` x4;
- `trap_lever_killzone` x4;
- `condition_lock_sanctum` x4.

The policy behavior was mostly plausible: forced-movement/hazard spells fired,
trap levers were used when hazard pressure existed, and Barbarian martial setup
remained aggressive. The recurring friction was speed diagnosis.

### Finding

Across recent rotations we kept seeing hundreds-of-ms spikes under a broad
`reduce_ms` label. That label was too coarse. The Barbarian batch proved the
actual reducer subphases are cheap:

- known tiles stayed below 0.4ms;
- state construction stayed below 0.03ms;
- position action normalization stayed below 4.4ms.

The expensive part is earlier: projecting decision-epoch affordances into the
external policy row shape, especially position rows. In the post-instrumentation
batch:

- max `position_rows_ms`: 588.781ms;
- max `compact_position_actions_ms`: 396.761ms;
- max `entity_rows_ms`: 248.870ms.

So the useful next performance target is not the reduced `ExternalAgentState`
itself. It is the epoch-to-policy projection surface, especially large movement
and position-spell row sets.

### Integrated Change

- `ExternalSelfPlayTrace` now stores `affordance_timing`.
- `ExternalSelfPlayTrace` now stores `reduction_timing`.
- The self-play runner passes timing sinks into
  `available_actions_payload_from_epoch()` and `reduce_external_agent_state()`.
- The dashboard runtime-subphase chart now includes self-play projection and
  reduction series.

This is an agent-interface and diagnostics improvement. It does not change
subjective data, legal action validation, enemy policy ordering, or engine rules.

### Validation

Focused checks:

- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q -k "external_selfplay_runs_sorcerer_barbarian_duel_through_epoch_commands"`
- `uv run pyright ai/external_selfplay.py tests/manual/test_39_ai_validation_harness.py`

Post-change Barbarian batch:

- total runs: 12;
- encounter-ended: 10;
- command-cap: 2, both in `condition_lock_sanctum` opening-order runs;
- total commands: 566;
- policy average: 0.169ms;
- policy max: 0.573ms;
- broad reduce average: 14.077ms;
- broad reduce max: 592.869ms.

Timing attribution:

- max projection `position_rows_ms`: 588.781ms;
- max projection `compact_position_actions_ms`: 396.761ms;
- max projection `entity_rows_ms`: 248.870ms;
- max reduction `normalize_position_actions_ms`: 4.349ms;
- max reduction `known_tiles_ms`: 0.393ms;
- max reduction `build_state_ms`: 0.025ms.

### Next Targets

- Rotate next to Sorcerer before another Barbarian or skeleton change.
- Treat epoch-to-policy projection as the next serious performance target:
  movement/position rows should be compacted or consumed without expensive
  legacy serialization.
- Keep the eventual larger goal in sight: the self-play harness should move
  closer to the long-lived subjective runtime path instead of snapshotting every
  command.

## 2026-07-04 - Skeleton Open Door Frontier Guard V106

### Context

This rotation moved back to skeleton-side validation after the Sorcerer duel
slice. I used the fast external-vs-external harness instead of touching the live
NeuroClient backend:

- `standard_skeleton_doors` x6;
- `skeleton_anti_aoe_split` x6;
- `double_door_dark_hunt` x4.

The open-field anti-AoE arena completed cleanly. The useful friction appeared in
the door arenas.

### Finding

The policy correctly treats a closed door as an information-gain/reveal-boundary
object. The problem was after the door opened: the same open doorway could remain
a sticky no-contact route anchor even after the actor had already reached or
crossed the doorway frontier.

That showed up as late-game movement churn:

- `move_toward_known_open_door`;
- `explore_no_contact`;
- `end_turn`;
- repeat across turns.

This was not a subjectivity leak. The actors were working from known open-door
facts and no visible enemy. The clunk was that "known open door exists" stayed
true longer than "known open door is still the best frontier anchor".

### Integrated Change

- `_move_toward_known_open_door` now refuses to fire once the actor is on or
  adjacent to that open doorway.
- Generic no-contact exploration takes over after the open-door frontier has
  been reached.
- The logical annotation for `_move_toward_known_open_door` now says the actor
  must not have already reached the frontier, and records why this avoids sticky
  oscillation.

This does not change door rules, object state, line of sight, or subjective
knowledge. It only tightens the policy proposition for when an open door is still
a meaningful no-contact anchor.

### Validation

Focused checks:

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "open_door or known_open_door or logical_annotations or preserves_action or door_dash"`
- `uv run pyright ai/external/policy.py tests/manual/test_35_subjective_external_ai.py`

Post-fix external-vs-external door validation:

- `standard_skeleton_doors` x6: 5 encounter-ended, 1 command-cap;
- `double_door_dark_hunt` x4: 4 encounter-ended, 0 command-cap;
- total post-fix door commands: 534;
- `move_toward_known_open_door`: 56;
- `explore_no_contact`: 65.

The double-door arena improved from 3/4 ended before the fix to 4/4 after the
fix. The standard skeleton arena still produced one cap, but the late trace
looked like a different clunk: no-contact/invisibility search after most actors
were dead, not the original adjacent open-door loop.

Timing remained comfortably below policy-budget expectations:

- combined policy selection average about 0.168ms;
- combined policy max 0.490ms;
- reducer and snapshot still have occasional hundreds-of-ms spikes, which remain
  separate instrumentation targets.

### Next Targets

- Rotate next to Barbarian or Sorcerer before another skeleton-specific policy
  change.
- Investigate late-game no-contact/invisibility search separately from door
  frontier movement.
- Keep measuring reducer/snapshot spikes; the behavior-tree policy itself is not
  the slow path.

## 2026-07-04 - Sorcerer External Duel Control Outcome V105

### Context

This rotation moved to Sorcerer-heavy validation, specifically to answer whether
we should be using harder class matchups and external-vs-external loops for
faster iteration. The answer is yes.

The batch used:

- `sorcerer_barbarian_duel` x6;
- `high_level_spell_resource_duel` x4 after fixing the discovered outcome
  classification bug.

Both sides were driven by the external subjective runtime/policy path. No live
NeuroClient backend or frontend process was touched.

### Finding

The Sorcerer-Barbarian duel is a much better tactical probe than skeleton-only
debugging. It stresses:

- control spells versus martial pressure;
- concentration outcomes;
- burst damage follow-up;
- healing and rage pressure;
- ranged spacing under real threat.

The concrete bug found before this entry was in control-outcome classification.
Banishment can report a save with text like:

```text
Validation Duel Sorcerer resists Banishment (CHA save)
```

The agent recognized `target saved` and `resisted`, but not `resists`. That made
some resisted Banishments appear as `control_landed` in telemetry and prevented
same-turn control-family suppression from firing reliably.

### Integrated Change

- Updated the live external agent outcome classifier.
- Updated the external-vs-external self-play outcome classifier.
- Added a focused Banishment regression test.

This is not a rules change and not a spell-content change. It only makes the
agent-side interpretation match the engine result message.

### Validation

Focused checks:

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "control_resisted or banishment or suppresses_resisted_control"`
- `uv run pyright ai/external_melee_agent.py ai/external_selfplay.py tests/manual/test_35_subjective_external_ai.py`

External-vs-external batch:

- `sorcerer_barbarian_duel` x6: 6 encounter-ended, 0 command-cap;
- `high_level_spell_resource_duel` x4: 4 encounter-ended, 0 command-cap;
- total commands: 285;
- post-fix control outcomes: 15 landed, 13 resisted;
- Sorcerer-Barbarian outcomes: 4 landed, 4 resisted;
- high-level spell duel outcomes: 11 landed, 9 resisted.

Timing across the batch:

- policy selection average 1.394ms, max 332.936ms;
- reduction average 23.560ms, max 498.225ms;
- snapshot average 37.145ms, max 459.288ms;
- command submit average 90.142ms, max 702.289ms.

### Next Targets

- Treat external-vs-external as the default fast AI iteration harness.
- Keep Sorcerer-Barbarian in the rotation instead of only using skeleton arenas.
- Investigate high-level spell-duel reducer/epoch spikes separately; the policy
  itself is usually sub-millisecond, but large high-level action rows still
  produce occasional heavy frames.

## 2026-07-04 - Barbarian Active Self-Heal Discipline V104

### Context

This rotation moved back to Barbarian-facing validation after the skeleton Acid
Flask slice. The batch used:

- `ranged_loadout_kiting_ring`, where a level 5 Barbarian crosses terrain under
  ranged pressure;
- `class_party_mirror_scramble`, where the enemy side includes a real Berserker
  Barbarian alongside a Fighter archer and Sorcerer.

Both arenas were already stable. The useful friction point was resource
discipline around healing, not encounter completion.

### Finding

The healing policy had a single flat rule: heal any controlled creature missing
at least 30 percent of maximum HP. That was fine for preserving wounded allies,
but active martial actors with Haste or follow-up action economy could drink
multiple potions in a turn and top off from shallow wounds while visible enemies
were still available.

Examples in the pre-fix trace included active Barbarian actors healing around
the 30-39 percent missing range before returning to Reckless/Move/Attack. This
made the Barbarian feel cautious in a very videogame-ish way: not illegal, but
too willing to spend pressure tempo once it was already above the danger band.

### Integrated Change

- Added `_healing_wound_threshold()`.
- Controlled ally healing keeps the old 30 percent missing threshold.
- Active self-healing while visible enemies are present now requires at least
  40 percent missing HP.
- Logical annotations for `_heal_wounded_controlled_ally` now describe the
  stricter active self-heal prerequisite.

This is a policy-resource discipline change only. It does not change potion
inventory rules, item stacks, healing action legality, or engine action economy.

### Validation

Focused checks:

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "healing_policy or support_policy_heals_wounded_ally or external_policy_logical_annotations"`
- `uv run pyright ai/external/policy.py tests/manual/test_35_subjective_external_ai.py`

Twelve post-fix external-vs-external Barbarian-facing runs:

- `ranged_loadout_kiting_ring` x6;
- `class_party_mirror_scramble` x6;
- encounter-ended runs: 12;
- command-cap runs: 0;
- shallow active self-heals under visible pressure: 0;
- deep active self-heals under visible pressure: 28;
- policy selection timing: average 0.165ms, max 0.636ms.

### Next Targets

- Rotate next to Sorcerer or skeleton-side validation before another Barbarian
  tweak.
- Expose wound percentage directly in self-play telemetry so future healing
  analysis does not need actor-name max-HP estimates.
- Keep same-item repeated potion use under observation, but do not touch
  inventory semantics without a separate engine-level finding.

## 2026-07-04 - Skeleton Offensive Item Pressure V103

### Context

This rotation returned to skeleton-side validation after the Sorcerer duel. The
specific friction point was the Skeleton Warrior's Acid Flask: the monster
factory gives the warrior a thrown consumable, and the epoch/reducer can expose
that item, but recent full-game traces never selected it.

### Finding

The issue was not missing data. In `standard_skeleton_doors` and
`skeleton_anti_aoe_split`, Acid Flask appeared as an affordable item-use
`position_actions` row. The row often had:

- a currently visible enemy in `affected_entity_uuids`;
- zero controlled entities in the affected set;
- enough range to pressure before a melee chase completed.

The policy simply had no branch for offensive item-use pressure. Item-use logic
covered self-buffs such as Haste/Invisibility and tactical objects such as trap
levers or loot caches, but not thrown consumables. As a result, the warrior
often moved or dashed while holding a legal flask throw.

### Integrated Change

- Added `_use_visible_enemy_offensive_item` to the external policy tree after
  ordinary attacks and before chase movement.
- Added high-confidence offensive item recognition for rows such as Acid Flask.
- The branch requires at least one visible enemy hit and zero controlled hits.
- Adjacent/legal attacks still win before item throws.
- Added logical annotations for the new branch so traces can explain the
  prerequisite/consequent proposition behind offensive item pressure.

### Validation

Focused checks:

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "offensive_item_policy or external_policy_logical_annotations"`
- `uv run pyright ai/external/policy.py tests/manual/test_35_subjective_external_ai.py`

Twelve post-fix external-vs-external skeleton runs:

- `skeleton_anti_aoe_split` x6;
- `standard_skeleton_doors` x6;
- encounter-ended runs: 10;
- command-cap runs: 2;
- Acid Flask commands: 12;
- Acid Flask commands with visible enemy hits: 12;
- Acid Flask commands with controlled hits: 0;
- policy selection timing: average 0.215ms, max 0.702ms.

The command-cap runs remain a separate long-endgame friction point. This slice
only claims the ignored offensive item surface.

### Next Targets

- Rotate next to Barbarian or Sorcerer before another skeleton policy change.
- Investigate command-cap long endings separately from offensive item pressure.
- Consider moving item semantics into epoch tags so the agent does not need
  name-based Acid Flask recognition.

## 2026-07-04 - Sorcerer Control Retry Memory V102

### Context

This rotation moved from Skeleton and Barbarian validation into the harder
`sorcerer_barbarian_duel` matchup. Both sides were driven through the external
subjective epoch/command contract, with initiative alternated across twelve
runs so the duel did not overfit to the opening actor.

The duel was already stable and roughly balanced, but the command traces showed
a flat tactical pattern: when `Hold Person` was resisted and the Sorcerer still
had action economy from Haste or follow-up actions, it could immediately try the
same control spell again in the same actor turn.

### Finding

The policy already handled landed control correctly. When the Barbarian was
known `Paralyzed`, the Sorcerer exploited the exposed target with damage instead
of duplicating `Hold Person`. The clunky behavior happened specifically after a
resisted control outcome:

- the command result was accepted by the engine;
- the target saved, so the policy had no known control condition to suppress;
- the next epoch still contained `Hold Person__slot_2` and upcast variants;
- the local retry memory only suppressed rejected rows such as Counterspell
  interruptions.

That made resisted control behave like a slot-machine loop instead of a
decision point where the actor pivots to damage, setup, spacing, or turn end.

### Integrated Change

- `ExternalMeleeAgent.play_current_turn()` now treats accepted
  `control_resisted` outcomes as per-turn local memory.
- The self-play harness uses the same memory so fast validation matches the
  subprocess controller path.
- `filter_action_payload_rows()` now suppresses slot/upcast variants as one
  template family, so blocking `Hold Person__slot_2` also blocks
  `Hold Person__slot_3`.
- Damage, setup, movement, and non-matching spell rows remain available; this is
  not a broad spell lockout.

### Validation

Twelve post-fix external-vs-external `sorcerer_barbarian_duel` runs all ended
cleanly:

- Sorcerer wins: 6;
- Barbarian wins: 6;
- command counts: min 6, max 29;
- `Hold Person` commands: 10, down from 25 in the prior twelve-run sample;
- control outcomes: 8 landed, 2 resisted;
- same-turn resisted-control template retries: 0;
- policy selection timing: average 0.206ms, max 1.598ms.

Focused checks:

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "suppressed_template_family or suppresses_resisted_control or entity_control_policy"`
- `uv run pyright ai/external/state.py ai/external_melee_agent.py ai/external_selfplay.py tests/manual/test_35_subjective_external_ai.py`
- `uv run python - <<'PY' ... run_external_selfplay('sorcerer_barbarian_duel', max_commands=80) x12 alternating initiative ... PY`

### Next Targets

- Rotate back to skeleton-side validation and inspect offensive item pressure,
  especially whether Acid Flask rows are being ignored.
- Keep the timing investigation separate from policy selection: policy remains
  sub-millisecond, while snapshot/reduce/submit still have occasional spikes.
- Consider making resisted-control memory a first-class planner proposition in
  agent telemetry, not only a local row-filter input.

## 2026-07-04 - Barbarian Control-Zone Affordance V101

### Context

This rotation returned to Barbarian-facing validation through
`zone_control_web_gauntlet`. The arena is meant to pressure the enemy controller
to use Web, Grease, Spike Growth, and Fog Cloud as battlefield-shaping tools
instead of treating the control mage as a Magic Missile turret.

### Finding

The authoritative decision epoch for the Web Mage already contained the control
spells, but the external reduced action payload dropped them before policy
selection. The compaction pass only preserved mobility spells and a small set of
persistent zones, so Web, Grease, Spike Growth, and Fog Cloud were squeezed out
by ordinary offensive position rows. The Web Mage then selected
`press_exposed_visible_enemy` / `Magic Missile__slot_1`, which made the arena
look like a policy valuation problem when the first bug was actually in the
agent-facing candidate surface.

After preserving the rows, a second issue appeared: these spells are
`POSITION` zone spells, not `POSITION_AOE` rows, so many legal targets do not
carry `affected_entity_uuids` or `affected_positions`. The reducer/policy now
uses a small known-spell zone-size estimate to rank centers against subjective
visible enemy and controlled-ally positions. This is a local agent heuristic,
not a replacement for server authority; a future improvement should expose
authoritative zone preview cells directly in the epoch.

### Integrated Change

- External position-action compaction now preserves battlefield-control zone
  rows: Web, Grease, Spike Growth, and Fog Cloud.
- Control-zone rows are ranked by visible enemy relevance and controlled-ally
  safety before the per-template cap is applied.
- Exposed-target pressure can delegate to a safe control-zone command when
  containment is better than non-finishing chip damage.
- Selected command traces infer affected entity UUIDs, names, positions, enemy
  count, and controlled-ally count from zone geometry when rows do not provide
  explicit affected entity UUIDs.
- A self-play crash discovered during the batch was fixed: Prone auto-stand now
  checks current movement before spending half speed, so constrained prone
  actors stay prone instead of raising during turn start.

### Validation

Six post-fix external-vs-external `zone_control_web_gauntlet` runs all ended
cleanly:

- command counts: 60, 49, 60, 63, 52, 44;
- control-zone commands: 31;
- Web commands: 18;
- Grease commands: 13;
- controlled allies knowingly caught by selected control zones: 0;
- policy selection timing: average 0.220ms, max 0.705ms.

The remaining timing spikes are not in behavior selection. The harness still
shows snapshot/reduce/submit spikes, with command-loop max around 581ms. That is
a separate runtime/data-path target.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "control_zone or compaction_preserves or compaction_prioritizes or exposed_visible_enemy_finisher"`
- `uv run pytest tests/manual/test_10_combat_resolution.py -q -k "prone_auto_stand"`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q -k "external_selfplay"`
- `uv run pytest tests/manual/test_37_ai_validation_arenas.py -q -k "zone_control_web_gauntlet or sorcerer_barbarian_duel"`
- `uv run pyright ai/external/state.py ai/external/policy.py dnd/actions_functional.py tests/manual/test_35_subjective_external_ai.py`

### Next Targets

- Rotate next to skeleton-side validation instead of staying on the Barbarian
  Web Gauntlet.
- Investigate snapshot/reduce/submit timing spikes separately from policy
  selection.
- Consider adding authoritative affected-position previews for `POSITION` zone
  spells so the agent does not need local zone-size heuristics.

## 2026-07-04 - Sorcerer Area Target Set Trace V100

### Context

This rotation moved to Sorcerer-facing spell-shape validation after the skeleton
focus-fire telemetry pass. The arena was `line_aoe_corridor`, where a Sorcerer
can punish aligned enemies with area rows while avoiding known friendly fire.

### Finding

The Sorcerer selected `Fireball__slot_3` area rows, and the policy already
filtered out obvious friendly-fire targets. The friction was observability:

- the trace showed the target position;
- it did not show which subjective entities were affected;
- it did not show affected enemy count;
- it did not show controlled-ally hit count.

That made spell-shape review blind. A human could see `cast_visible_area_spell`
but could not verify from the trace whether the row hit two, three, or four
enemies, or whether a controlled ally was knowingly included.

### Integrated Change

- `AgentCommand` now carries selected area/position affected-target facts:
  - `affected_entity_uuids`;
  - `affected_entity_names`;
  - `affected_entity_positions`;
  - `affected_enemy_count`;
  - `affected_controlled_count`.
- `ExternalSelfPlayTrace` records the same fields.
- Multi-enemy area selections now emit `target_allocation`.
- Added regressions for both direct policy output and self-play traces.
- Added dashboard observability series for area affected-target tracing.

### Batch Notes

- Pre-fix sample: six `line_aoe_corridor` runs, all encounters ended, command
  count `3-47`.
- Pre-fix area commands: `11`, with no affected entity names/counts in trace.
- Post-fix sample: six runs, five encounters ended and one reached the
  `90` command cap.
- Post-fix area commands: `12/12` carried affected entity names/counts.
- Post-fix area spell affected enemy counts:
  - two enemies: `5`;
  - three enemies: `4`;
  - four enemies: `3`.
- Post-fix controlled-ally hits from selected area rows: `0`.
- Policy selection remained cheap: average `0.187 ms`, max `0.488 ms`.
- The slow spots remain outside the selector: max snapshot `506.293 ms`, max
  reduction `325.073 ms`, max submit `494.967 ms`.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "caster_policy_prefers_safe_enemy_aoe or does_not_spend_leveled_aoe or external_policy_snapshot"`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q -k "area_spell_affected_entities or external_selfplay"`
- `uv run pyright ai/external/policy.py ai/external_selfplay.py tests/manual/test_35_subjective_external_ai.py tests/manual/test_39_ai_validation_harness.py`

### Next Targets

- Rotate next to Barbarian-facing validation.
- Investigate command-cap no-contact loops only if they repeat in the next
  relevant spell-shape or navigation pass.
- Continue reducing snapshot, reduction, and command-submission spikes.

## 2026-07-04 - Skeleton Focus-Fire Follow-Up Tags V99

### Context

This rotation moved back to skeleton-side validation after the Barbarian kiting
trace pass. The arena was `skeleton_mark_focus_fire`, where a skeleton guard,
archer, and warlock pressure a high-AC shield fighter. The scenario exists to
prove that `Mark Target` becomes coordinated focus-fire rather than decorative
support noise.

### Finding

The behavior was mostly correct. The archer used `Mark Target`, and then the
archer, guard, and warlock attacked the marked fighter. The trace problem was
that only the setup command carried `focus_fire`:

- `Mark Target` had `focus_fire`;
- follow-up `press_exposed_visible_enemy` attacks and spells had only
  `pressure`.

That made the dashboard undercount coordinated focus-fire. It could show that a
mark was applied, but not that later attacks were intentionally exploiting the
mark.

### Integrated Change

- `press_exposed_visible_enemy` now appends `focus_fire` when the selected
  target has a known focus marker:
  - `Marked`;
  - `Guiding Bolt Marked`.
- Reckless, prone, restrained, and other exposed-target pressure remains plain
  `pressure` unless it is also marked.
- The policy logical annotation for exposed pressure now documents
  marked-target follow-up as focus-fire telemetry.
- The dashboard observability chart now includes the marked follow-up
  focus-fire feature flag.

### Batch Notes

- Pre-fix sample: six `skeleton_mark_focus_fire` runs, all encounters ended,
  command count `30-50`.
- Pre-fix focus-fire tags: `6`, all from `Mark Target`.
- Post-fix sample: six runs, all encounters ended, command count `33-63`.
- Post-fix focus-fire tags:
  - `Mark Target` setup commands: `6`;
  - marked follow-up commands: `59`;
  - total `focus_fire=65`.
- Post-fix tags included:
  - `pressure=127`;
  - `spacing_control=72`;
  - `anti_aoe_spacing=54`;
  - `route_progress=52`.
- Policy selection remained cheap: average `0.186 ms`, max `1.797 ms`.
- The slow spots remain outside the selector: max snapshot `330.716 ms`, max
  reduction `336.590 ms`, max submit `426.988 ms`.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "marked_target_follow_up_is_tagged_as_focus_fire or presses_exposed or uses_mark_target or does_not_repeat_mark_target or external_policy_snapshot"`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q -k "external_selfplay"`
- `uv run pyright ai/external/policy.py tests/manual/test_35_subjective_external_ai.py ai/external_selfplay.py tests/manual/test_39_ai_validation_harness.py`

### Next Targets

- Rotate next to Sorcerer-facing validation.
- Continue reducing snapshot, reduction, and command-submission spikes.
- Watch whether focus-fire should become an explicit target-plan object later,
  rather than only a tag.

## 2026-07-04 - Barbarian Kiting Reference Trace V98

### Context

This rotation moved to a Barbarian-facing escape arena after the Sorcerer
support-resource pass. The arena was `teleport_escape_skirmish`, where a level
5 Barbarian pressures a mage, goblin archer, and guard. The scenario stresses
Misty Step, ranged pressure, retreat movement, and hold-spacing decisions.

### Finding

The enemy behavior was not the main problem in this pass. The mage used
`Misty Step`, the goblin archer held or retreated, and the guard gave the
Barbarian something to chew through. The friction was the trace surface:

- `AgentCommand` knew the reference enemy for hold-spacing commands;
- `AgentCommand` knew the spacing floor and anchor position;
- `ExternalSelfPlayTrace` dropped those fields.

That made kiting reviews awkward. A trace showed `hold_ranged_spacing`, but not
which enemy the actor was spacing from, how far away that enemy was, or which
anchor position satisfied the spacing floor.

### Integrated Change

- Added reference context to `ExternalSelfPlayTrace`:
  - `reference_entity_uuid`;
  - `reference_entity_name`;
  - `reference_entity_position`;
  - `reference_entity_distance_cells`.
- Added spacing context to `ExternalSelfPlayTrace`:
  - `spacing_floor_cells`;
  - `spacing_anchor_position`.
- Added a regression proving teleport-escape self-play traces expose the
  Barbarian reference context behind hold-spacing decisions.
- Added dashboard observability series for self-play reference context.

### Batch Notes

- Pre-fix sample: six `teleport_escape_skirmish` runs, all encounters ended,
  command count `41-56`.
- Post-fix sample: six runs, all encounters ended, command count `40-52`.
- Post-fix trace context:
  - `hold_spacing_reference_context_count=25`;
  - `spacing_floor_trace_context_count=25`;
  - `spacing_anchor_trace_context_count=25`;
  - `escape_mobility_trace_context_count=8`;
  - `Misty Step` commands: `8`.
- Post-fix tags included:
  - `pressure=112`;
  - `spacing_control=48`;
  - `route_progress=54`;
  - `forced_movement=13`;
  - `hazard_exploit=13`.
- Policy selection remained cheap: average `0.194 ms`, max `0.836 ms`.
- The slow spots remain outside the selector: max snapshot `419.242 ms`, max
  reduction `382.504 ms`, max submit `412.315 ms`.

### Verification

- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q -k "spacing_reference_context or external_selfplay"`
- `uv run pyright ai/external_selfplay.py tests/manual/test_39_ai_validation_harness.py ai/external/policy.py tests/manual/test_35_subjective_external_ai.py`
- `uv run python -m json.tool ai/AGENT_UX_ITERATION_STATS.json > /tmp/dnd_ai_v98_stats_precheck.json`
- `node --check /tmp/dnd_ai_dashboard_v98_script.js`

### Next Targets

- Rotate next to skeleton-side validation.
- Continue reducing snapshot, reduction, and command-submission spikes.
- Consider escape-result outcome tags only after observing a behavior failure,
  not merely because teleport exists.

## 2026-07-04 - Sorcerer Support Resource Discipline V97

### Context

This rotation moved to a Sorcerer-facing control arena after the skeleton
anti-AoE spacing pass. The arena was `concentration_control_crossroads`, where
a level 5 Sorcerer fights a guard, controller, and support caster with control,
support, friendly-fire, and concentration pressure.

### Finding

The pre-fix six-run batch showed that support behavior was tactically active,
but resource discipline was missing from support-row scoring. The support side
selected rows such as:

- `Shield of Faith__slot_9`;
- `Shield of Faith__slot_8`;
- `Shield of Faith__slot_7`;
- `Invisibility__slot_8`;
- `Invisibility__slot_5`;
- `Invisibility__slot_4`.

That is not a scenario-content issue. The policy was ranking support priority,
beneficiary count, and target name, but not spell-slot cost. Equivalent support
rows could therefore drift into wasteful high-level slots.

### Integrated Change

- Controlled-support spell scoring now ranks:
  - support priority;
  - beneficiary count;
  - spell-slot cost;
  - target name.
- Higher slots can still win when they add beneficiaries.
- Equivalent single-target support rows prefer the lowest available slot.
- Support-spell commands now emit `resource_discipline`.
- The dashboard now plots `resource_discipline`.

### Batch Notes

- Pre-fix sample: six `concentration_control_crossroads` runs, all encounters
  ended, command count `3-80`.
- Post-fix sample: six runs, all encounters ended, command count `3-32`.
- Post-fix support templates were:
  - `Bless__slot_1`;
  - `Shield of Faith__slot_1`;
  - `Shield of Faith__slot_2`;
  - `Shield of Faith__slot_3`.
- Post-fix slot `4+` support selections: `0`.
- Post-fix tags included:
  - `resource_discipline=9`;
  - `support_setup=25`;
  - `control_effect=12`;
  - `control_landed=10`;
  - `control_resisted=2`.
- Policy selection remained cheap: average `0.236 ms`, max `0.744 ms`.
- The slow spots remain outside the selector: max snapshot `327.778 ms`, max
  reduction `302.394 ms`, max submit `436.061 ms`.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "support_policy_prefers_lower_slot_for_equivalent_single_target_buff or support_policy_allows_upcast_when_it_adds_beneficiaries or caster_policy_opens_with_group_support_before_single_target_cantrip or support_policy_keeps_opening_group_buff_before_healing"`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q -k "external_selfplay"`
- `uv run pyright ai/external/policy.py ai/external_selfplay.py tests/manual/test_35_subjective_external_ai.py tests/manual/test_39_ai_validation_harness.py`

### Next Targets

- Rotate next to Barbarian-facing validation.
- Keep reducing snapshot, reduction, and command-submission spikes.
- Watch support and control spells for concentration overwrite or
  duplicated-condition waste in longer matches.

## 2026-07-04 - Skeleton Anti-AoE Spacing Trace V96

### Context

This rotation moved back to skeleton-side validation after the Barbarian control
telemetry pass. The arena was `skeleton_anti_aoe_split`, where a level 5 blast
Sorcerer pressures a split skeleton Warrior, Archer, and Warlock formation.

### Finding

The policy behavior was better than the old “walk into the fireball” failure:
the ranged skeletons often held position after spending their pressure action.
The problem was reviewability. A hold-spacing command only exposed
`spacing_control`, so a trace reviewer could not tell whether the actor was
preserving a genuinely spread anti-AoE formation or merely stopping because no
better move existed.

The pre-fix six-run batch had `109` `spacing_control` tags and zero explicit
anti-AoE tags. That meant the dashboard could show that spacing was happening,
but not whether the formation proposition was true.

### Integrated Change

- Added `anti_aoe_spacing` as a policy logical tag.
- Added command and self-play trace fields:
  - `nearest_controlled_ally_distance_cells`;
  - `ally_spacing_floor_cells`.
- Hold-spacing commands now add `anti_aoe_spacing` only when the nearest
  controlled ally is already at or beyond the anti-AoE floor.
- Spread-from-allies commands tag `anti_aoe_spacing` as formation improvement.
- The dashboard now plots `anti_aoe_spacing` and the new spacing observability
  fields.

### Batch Notes

- Post-fix sample: six `skeleton_anti_aoe_split` external-vs-external runs.
- All six encounters ended; no command-cap runs.
- Command count ranged from `51` to `90`.
- Post-fix tags included:
  - `pressure=147`;
  - `spacing_control=119`;
  - `anti_aoe_spacing=41`;
  - `route_progress=105`.
- All `41` anti-AoE spacing commands logged nearest ally distances between
  `10` and `16` cells, well above the `5` cell anti-AoE floor.
- Policy selection remained cheap: average `0.224 ms`, max `4.601 ms`.
- The slow spots are still outside the selector: max snapshot `494.211 ms`,
  max reduction `447.499 ms`, max submit `490.125 ms`.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "spent_sorcerer_holds_when_already_beyond_spacing_floor or ranged_enemy_spreads_from_allies_after_spending_pressure_action or ranged_enemy_does_not_spread_by_collapsing_below_spacing_floor"`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q -k "external_selfplay"`
- `uv run pyright ai/external/policy.py ai/external_selfplay.py tests/manual/test_35_subjective_external_ai.py tests/manual/test_39_ai_validation_harness.py`
- `uv run python -m json.tool ai/AGENT_UX_ITERATION_STATS.json > /tmp/dnd_ai_v96_stats_checked.json`
- `node --check /tmp/dnd_ai_dashboard_v96_script.js`
- `git diff --check -- ai/external/policy.py ai/external_selfplay.py tests/manual/test_35_subjective_external_ai.py ai/AGENT_UX_ITERATION_DASHBOARD.html ai/AGENT_UX_ITERATION_STATS.json ai/AGENT_UX_ITERATION_LOG.md`

### Next Targets

- Rotate next to Sorcerer-facing validation.
- Keep using external-vs-external batches as the fast default loop.
- Continue latency work on snapshot, reduction, and command submission spikes.

## 2026-07-04 - Barbarian Control Outcome Telemetry V95

### Context

This rotation moved back to a Barbarian-facing control arena after the Sorcerer
Counterspell pass. The arena was `condition_lock_sanctum`, where a level 5
Barbarian closes on a guard, a controller, and a support caster.

### Finding

The enemy AI was winning the scenario consistently and policy selection remained
cheap. The friction was reviewability:

- `Hold Person` and `Bane` were tactically important but appeared mostly as
  generic `pressure`;
- accepted command results buried outcome differences inside message strings;
- a saved `Hold Person` looked the same in high-level charts as a landed
  `Hold Person`.

The batch also exposed a likely engine/rules issue: one saved `Hold Person`
reported `target saved (still concentrating)`. I logged that separately in
`KNOWN_ISSUES.md` instead of changing spell rules inside this telemetry slice.

### Integrated Change

- Added `control_effect` as a policy logical tag for entity-targeted control,
  control zones, and persistent battlefield zones.
- Added control outcome inference to external runtime and self-play command
  results:
  - `control_landed`;
  - `control_resisted`.
- Added dashboard series for `control_effect`, `control_landed`, and
  `control_resisted`.

### Batch Notes

- Pre-fix sample: six runs, all encounter ended, about `19-40` commands and
  roughly `2.7-5.8` seconds.
- Post-fix sample: six runs, all encounter ended, about `22-35` commands and
  roughly `3.9-5.6` seconds.
- Post-fix control telemetry: `control_effect=12`, `control_landed=11`,
  `control_resisted=1`.
- Policy selection remained cheap: average `0.231 ms`, max `0.932 ms`.
- Command-loop cost is still outside the selector: max snapshot `364.088 ms`,
  max reduction `369.823 ms`, max submit `371.797 ms`.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "entity_control_policy_uses_hold_person or traces_control_resisted or traces_rejected_execute_results"`
- `uv run pyright ai/external/policy.py ai/external_melee_agent.py ai/external_selfplay.py tests/manual/test_35_subjective_external_ai.py`

### Next Targets

- Rotate next to skeleton-side validation.
- Isolate the Hold Person initial-save concentration issue before changing spell
  behavior.
- Continue latency work on snapshot/reduce/submit phases, not the policy
  selector.

## 2026-07-04 - Sorcerer Counterspell Continuation V94

### Context

This rotation moved to a Sorcerer-facing reaction surface after the skeleton
object-room pass. The arena was `reaction_counterspell_lab`, which places a
level 5 Sorcerer against a Counterspell Abjurer, Shield Mage, and guard.

### Finding

The first six-run sample did not expose a policy-selection cost problem. Policy
selection stayed sub-millisecond. The real friction was outcome handling:

- every run terminated as `command_rejected`;
- opening `Fireball__slot_3` was counterspelled by the Abjurer;
- the fast self-play runner treated that reaction outcome as a terminal harness
  failure;
- after one Counterspell, the next local epoch could still expose spell rows,
  so a naive continuation could immediately select another spell and hit a
  generic engine rejection.

Counterspell is not an agent crash. It is gameplay information that should be
observable and should change the current-turn local action selection.

### Integrated Change

- Added `filter_action_payload_rows()` for local row suppression before policy
  reduction.
- External runtime and self-play now tag Counterspell outcomes as
  `spell_interruption`.
- After `spell_interruption`, the current actor-turn memory suppresses spell
  rows for the rest of that turn, preventing immediate repeated spell attempts
  into a just-observed interruption.
- Rejected command results remain structured and observable instead of being
  collapsed to `None`.
- Added dashboard support for the `spell_interruption` tag.

### Batch Notes

- Pre-fix sample: six runs, all six ended as `command_rejected`, usually on the
  first Sorcerer `Fireball`.
- Post-fix sample: six runs, zero terminal `command_rejected` outcomes.
- Post-fix statuses: four encounters ended; two reached the 90-command cap in
  a longer reaction duel.
- Post-fix outcome tags included `36` `spell_interruption` entries.
- Policy selection remained cheap: average `0.269 ms`, max `0.619 ms`.
- Command-loop spikes are still outside the selector: max snapshot `788.038 ms`,
  max reduction `769.302 ms`, max submit `876.314 ms`.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "traces_rejected_execute_results or filter_action_payload_rows"`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q -k "external_selfplay_continues_after_counterspell or external_selfplay_runs_sorcerer_barbarian"`
- `uv run pyright ai/external/state.py ai/external/__init__.py ai/external_melee_agent.py ai/external_selfplay.py tests/manual/test_35_subjective_external_ai.py tests/manual/test_39_ai_validation_harness.py`

### Next Targets

- Rotate next to Barbarian-facing validation.
- Investigate why reaction-heavy long duels can hit command cap rather than
  ending decisively.
- Keep latency pressure on snapshot/reduce/submit phases rather than the policy
  selector.

## 2026-07-04 - Skeleton Object Room Resource And Backtrack V93

### Context

This rotation moved to skeleton-side/environment-object validation after the
Barbarian hazard bridge and Sorcerer projectile allocation passes. The arena was
`multi_object_control_room`, which puts an object-controller actor beside a trap
lever and loot cache while the rest of the side has to fight through visible
terrain and object pressure.

### Finding

The policy was already using the important object rows, but the traces hid one
of the propositions and exposed a real movement clunk:

- `Pull Lever` was tagged as `hazard_exploit`;
- `Loot All` was selected correctly but had no logical tag, so resource pickup
  disappeared in dashboard review;
- the object guard could oscillate between `(7, 5)` and `(7, 6)` after a Dash
  because the only local route-progress candidate was often the cell it had
  just left.

### Integrated Change

- Added `resource_acquisition` as a logical tag for recognized `Loot All`
  battlefield-cache rows.
- Added `actor_previous_position` to the reduced external state and self-play
  traces, inferred only from subjective movement combat logs.
- Changed pursuit movement so immediate backtracking is not considered route
  progress. Detours still work when there is no previous-position evidence.
- Added dashboard support for the `resource_acquisition` logical tag.

### Batch Notes

- Pre-fix sample: three `multi_object_control_room` self-play runs showed
  `10` immediate backtracks in the guard movement trace and `Loot All` had no
  logical tag.
- Post-fix sample: three runs, all encounter ended, about `49-64` commands and
  roughly `4.7-6.1` seconds.
- Post-fix object rows: three `Pull Lever` commands tagged `hazard_exploit` and
  three `Loot All` commands tagged `resource_acquisition`.
- Immediate backtracks dropped from `10` to `0` in the matched three-run sample.
- Policy selection remained cheap: average `0.187 ms`, max `0.555 ms`.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "loots_adjacent_cache or movement_policy_uses_known_route or movement_policy_avoids_immediate_backtrack or movement_policy_declines_immediate_backtrack"`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q -k "external_selfplay"`
- `uv run pyright ai/external/state.py ai/external/policy.py ai/external_selfplay.py tests/manual/test_35_subjective_external_ai.py`

### Next Targets

- Rotate next to Sorcerer-facing validation.
- Keep watching snapshot/reduce/submit latency spikes; the policy selector is
  still not the hot path.
- Use `actor_previous_position` in future trace review before adding broader
  memory or planner state.

## 2026-07-04 - Barbarian Hazard Bridge Tags And Route Trace V92

### Context

This rotation moved back to Barbarian-facing validation after the Sorcerer
projectile allocation pass. The arena was `forced_movement_hazard_bridge`,
which places a level 5 Barbarian near a Thunderwave-capable Warlock, a caster,
an archer, water, and spike-zone terrain.

### Finding

The policy was already finding useful hazard pressure: Warlock and Mage selected
`Thunderwave` through `cast_visible_forced_movement_hazard_spell`, and movement
rows avoided hazardous paths in the sampled runs. The friction was again the
agent interface:

- forced-movement hazard plays were tagged only as generic `pressure`;
- Frenzy/Reckless/Haste setup commands had no self-setup tag;
- self-play traces did not expose selected path cost, safe-path cost, or
  whether the selected route crossed known hazards.

This made the behavior hard to audit from dashboard traces even when the choices
were tactically reasonable.

### Integrated Change

- Added `forced_movement` and `hazard_exploit` logical tags for Thunderwave-style
  hazard displacement.
- Added `self_setup` logical tags for opening self setup such as Frenzy,
  Reckless Attack, Haste, and Greater Invisibility.
- Added selected path cost, safe path cost, hazardous-path flag, and path cells
  to external self-play traces.
- Added dashboard series for `forced_movement`, `hazard_exploit`, and
  `self_setup`.

### Batch Notes

- Initial post-hazard-tag batch: six runs, all encounter ended, about 41-52
  commands and roughly 4.0-5.3 seconds; `Thunderwave` hazard plays appeared 16
  times and were tagged as forced movement and hazard exploitation.
- Final post-self-setup sample: three runs, all encounter ended, about 40-48
  commands and roughly 4.3-5.6 seconds.
- Final sample tags: `self_setup=22`, `forced_movement=7`,
  `hazard_exploit=7`, `route_progress=36`, `pressure=43`.
- Selected hazardous movement paths stayed at zero in the final sample.
- Free Haste and Greater Invisibility consumables remain a balance concern:
  the final sample still used six Haste potion rows and three Greater
  Invisibility potion rows.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "forced_movement_spell or trap_lever or barbarian_policy_uses_frenzy or opening_haste_consumable"`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q -k "external_selfplay"`
- `uv run pyright ai/external/policy.py ai/external_selfplay.py tests/manual/test_35_subjective_external_ai.py tests/manual/test_39_ai_validation_harness.py`
- `uv run python -m json.tool ai/AGENT_UX_ITERATION_STATS.json > /tmp/dnd_ai_v92_stats_checked.json`
- `node --check /tmp/dnd_ai_dashboard_v92_script.js`

### Next Targets

- Rotate next to skeleton-side validation.
- Keep the free-consumable action-economy question visible rather than tuning
  around it silently.
- Use the new route trace fields when investigating future water/hazard movement
  complaints.

## 2026-07-04 - Sorcerer Projectile Allocation Trace V91

### Context

This rotation moved back to a Sorcerer-facing pressure case after the skeleton
focus-fire pass. The arena was `multi_projectile_no_aoe_lab`, which removes
area spell escape hatches and forces the policy to reason about Magic Missile
and Scorching Ray style target allocation against several wounded visible
enemies.

### Finding

The first diagnostic run immediately exposed an interface gap: the Sorcerer
ended the encounter with multi-target projectile pressure, but the self-play
trace did not expose `extra_target_names` or `extra_target_positions`, so the
game looked like a single-target spell in the batch output.

After exposing the extra targets, the policy behavior was readable but
tactically awkward: every sampled run drank a Haste potion before casting the
fight-ending Magic Missile. That was a tempo-ordering bug in the item self-buff
branch, not a targeting bug.

### Integrated Change

- Added extra target UUIDs, names, and positions to external self-play traces.
- Added a `target_allocation` logical tag for multi-entity projectile rows.
- Added a dashboard series for `target_allocation`.
- Tightened opening self-buff policy so Haste/Invisibility item buffs step
  aside when:
  - a repeatable projectile row can immediately remove multiple visible enemies;
  - a cheap attack or cantrip can finish a visible low-HP enemy.

### Batch Notes

- Pre-guard sample: six runs, all encounter ended in 2-3 commands; each opened
  with Haste, then Magic Missile with two extra targets.
- Post-guard sample: six runs, all encounter ended; each opened with Magic
  Missile and explicit extra targets for the Goblin and Warrior.
- Post-guard Haste count dropped from six opening uses to two follow-up uses
  after projectile cleanup when a survivor remained.
- Policy selection remained small: about `0.21 ms` average and `0.355 ms` max
  in the final sample.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "projectile_cleanup or cheap_finisher or opening_haste_consumable or multi_target_cleanup or magic_missile_can_split or unique_multi_entity"`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q -k "external_selfplay"`
- `uv run pyright ai/external/policy.py ai/external_selfplay.py tests/manual/test_35_subjective_external_ai.py tests/manual/test_39_ai_validation_harness.py`
- `uv run python -m json.tool ai/AGENT_UX_ITERATION_STATS.json > /tmp/dnd_ai_v91_stats_checked.json`
- `node --check /tmp/dnd_ai_dashboard_v91_script.js`

### Next Targets

- Rotate next to Barbarian-facing validation.
- Keep watching free Haste semantics: the policy now avoids pre-cleanup Haste,
  but free consumable action economy still affects challenge balance.
- Use `target_allocation` traces to review richer multi-target spells beyond
  Magic Missile.

## 2026-07-04 - Skeleton Focus-Fire Tags And Timing Trace V90

### Context

This rotation moved to a skeleton-side pressure case after the Barbarian-facing
consumable/contact-memory pass and the Sorcerer-Barbarian duel regression. The
main arena was `skeleton_mark_focus_fire`, run through the in-process
external-vs-external epoch loop so both the shield-fighter hero and skeleton
side used the same subjective command contract.

### Finding

The skeleton behavior was mostly healthy:

- the archer used `Mark Target` before ranged pressure in every sampled run;
- the warlock usually opened with `Necrotic Bless` support;
- the guard maintained melee pressure;
- ranged/caster actors continued to move or hold for spacing after spending
  their pressure action.

The friction was observability. `Mark Target` selected the correct
`use_visible_enemy_tactical_ability` branch, but the selected command had no
logical tag, so dashboard charts could not distinguish focus-fire setup from an
unclassified utility row.

The timing sample also showed that policy selection itself is not the speed
problem: policy selection averaged about `0.19 ms` and stayed below `1 ms`.
The full command loop is slower because snapshot fetch/validation,
available-payload reduction on dense movement epochs, and command submission
dominate the surrounding harness cost.

### Integrated Change

- Added a `focus_fire` logical tag.
- Tagged visible-enemy tactical ability rows, currently `Mark Target`, with
  both `support_setup` and `focus_fire`.
- Added self-play timing fields for snapshot, materialization, reduction,
  policy selection, command submission, and total command-loop time.
- Added a dashboard series for `focus_fire` logical tags.

### Batch Notes

- Initial skeleton batch: six `skeleton_mark_focus_fire` runs, all encounter
  ended, about 36-56 commands and roughly 3.8-6.1 seconds.
- Post-tag sample: three runs, all encounter ended, and all three `Mark Target`
  commands carried both `support_setup` and `focus_fire`.
- Timing sample: three runs, two ended and one hit the 60-command cap; policy
  selection averaged `0.19 ms` with `0.635 ms` max, while snapshot, reduction,
  and command submission showed the largest spikes.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "mark_target or logical_annotations"`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q -k "external_selfplay"`
- `uv run pyright ai/external/policy.py ai/external_selfplay.py tests/manual/test_35_subjective_external_ai.py tests/manual/test_39_ai_validation_harness.py`
- `uv run python -m json.tool ai/AGENT_UX_ITERATION_STATS.json > /tmp/dnd_ai_v90_stats_checked.json`
- `node --check /tmp/dnd_ai_dashboard_v90_script.js`

### Next Targets

- Rotate next to Sorcerer-facing validation.
- Use the new timing fields to separate policy cost from epoch/reduction/server
  command cost in future batches.
- Keep the free-Haste balance question visible; the shield-fighter hero used an
  opening Haste potion in this self-play arena too.

## 2026-07-04 - Barbarian Crossfire Consumables And Contact Memory V89

### Context

This rotation moved back to Barbarian-facing validation after the skeleton-door
pass. The main batch used `caster_crossfire`; a follow-up sample used
`buff_consumable_ambush` because the crossfire arena was a clean Barbarian sweep
and did not stress monster consumables enough. Both were run through
external-vs-external self-play with no live backend or frontend process touched.

### Finding

`caster_crossfire` showed healthy Barbarian setup and monster pressure:

- Barbarian opened with Frenzy and Reckless Attack, then moved into melee;
- enemy mage used `Magic Missile` and `Thunderwave`;
- archer used ranged pressure and `Mark Target`;
- ranged/caster monsters retreated or held spacing after pressure.

The friction points were:

- when the Barbarian had no visible or remembered enemy after kills, self-play
  traces did not make it clear whether this was genuine no-contact exploration
  or unresolved hostile memory;
- in `buff_consumable_ambush`, monsters carried Haste and Greater Invisibility
  potions, but the policy treated them as inert rows and attacked instead;
- one later run exposed an unresolved movement contract issue where a legal
  epoch `Move` row was rejected by execute-by-index.

### Integrated Change

- Added `unresolved_hostile_uuids` and `unresolved_hostile_names` to the
  reduced external state, derived only from subjective combat logs.
- Added a contact-memory behavior leaf:
  - if no visible or remembered enemy exists, but subjective logs prove an
    unresolved hostile participant, the actor Dodges when possible;
  - otherwise it ends turn with `contact_memory` telemetry instead of labeling
    the turn as no-contact exploration.
- Added `CONTACT_MEMORY` logical tag and policy annotations for that leaf.
- Added `remembered_enemy_names` and `unresolved_hostile_names` to self-play
  traces.
- Added a narrow `use_opening_item_self_buff` branch for visible-contact
  Haste/Invisibility self-buff consumables.

### Batch Notes

- `caster_crossfire`: six initial runs, all encounter-ended Barbarian wins,
  about 27-50 commands and roughly 2.4-5.5 seconds.
- `buff_consumable_ambush`: before the item-buff branch, monsters exposed
  Haste/Greater Invisibility rows but did not use them.
- After the branch, four buff-ambush runs produced accepted Haste or Greater
  Invisibility consumable commands from the mage, goblin archer, and guard.
- The branch also lets the Barbarian use a visible-contact Haste potion, which
  confirms the older balance warning: free Haste rows are powerful and should
  remain visible in challenge notes until potion action-economy policy is
  decided.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "opening_haste_consumable or unresolved_hostile_contact or logical_annotations"`
- `uv run pyright ai/external/state.py ai/external/policy.py ai/external_selfplay.py tests/manual/test_35_subjective_external_ai.py`

### Next Targets

- Isolate the epoch Move row rejected as `Failed to move for Move`.
- Keep the next rotation off Barbarian; return to Sorcerer or skeleton-side
  validation.
- Decide whether free Haste/Greater Invisibility potion rows are intended
  videogame policy or need explicit action-economy costs.

## 2026-07-04 - Skeleton Door Self-Play And Spacing Metadata V88

### Context

After the Sorcerer-Barbarian rotation, this pass returned to the skeleton side
with `standard_skeleton_doors`. The arena was run through the in-process
external-vs-external self-play runner so both the hero Sorcerer and skeleton
monsters used the same subjective snapshot, decision epoch, command endpoint,
and behavior-tree policy path. No live backend or frontend process was touched.

### Finding

The skeleton-door loop is currently healthier than the earlier live repros:

- monsters do not chase the unseen hero before contact;
- the first skeleton side reaches the known closed door, opens it, and then
  uses movement for information gain;
- later skeletons route through the known open doorway rather than requiring a
  second object-action query;
- longer 60-command-cap runs ended in 26-36 commands;
- the extended-run post-pressure detector found no repeated "attack, then
  random door exploration" loop.

The one actionable friction point was telemetry rather than tactics. A broader
external-AI regression exposed that `reference_entity_position` was being used
as if it were both "the enemy I am spacing from" and "the anchor position I am
choosing to preserve." That muddles review tools and future planning
annotations.

### Integrated Change

- Added `spacing_anchor_position` to external `AgentCommand`.
- Kept `reference_entity_position` as the actual subjective enemy position.
- Updated hold-spacing regressions to assert both the reference enemy and the
  preserved spacing anchor explicitly.
- Resolved the `KNOWN_ISSUES.md` entry for ranged-harrier hold-spacing
  metadata.

### Batch Notes

Seven `standard_skeleton_doors` self-play runs were used this pass:

- four short 35-command-cap runs: two ended and two reached the cap;
- three longer 60-command-cap runs: all ended;
- elapsed time range observed: roughly 2.95-4.04 seconds per run;
- opening pattern: `move_toward_closed_door`, `Open Door`, then
  no-contact exploration with information-gain/reveal-boundary tags;
- pressure pattern after contact: Sorcerer Fireball/Fire Bolt/Magic Missile
  versus Skeleton Archer ranged attacks, Skeleton Warrior melee pressure, and
  Skeleton Warlock Eldritch Blast.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q`
- `uv run pytest tests/manual/test_37_ai_validation_arenas.py -q -k "catalog_has_diverse or sorcerer_barbarian_duel"`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q -k "external_selfplay"`
- `uv run pyright ai/external/policy.py tests/manual/test_35_subjective_external_ai.py`

### Next Targets

- Rotate next to Barbarian-facing validation rather than another skeleton pass.
- Use the self-play runner before live NeuroClient checks, then spot-check live
  only when a batch finds a meaningful policy change.
- Consider a small policy annotation for "hold spacing from X at anchor Y" so
  future planning/debug tools do not infer it from free text.

## 2026-07-04 - Committed Sorcerer Barbarian Self-Play Harness V87

### Context

The previous external-vs-external probe was useful but transient. This rotation
promoted the matchup into the validation catalog as `sorcerer_barbarian_duel`
and added a reusable in-process external self-play runner. Both factions are
controlled through the same subjective snapshot, decision epoch, and command
endpoints used by the normal external AI path. The live NeuroClient backend and
frontend were not touched.

### Finding

The faster loop answered the practical question: yes, Sorcerer versus Barbarian
is a more challenging validation case, and yes, external-vs-external is fast
enough for routine policy iteration. Six randomized self-play duels completed
or hit the command cap in about 1.7 to 3.1 seconds each. Outcomes split both
ways: some runs were control-lock wins for the Sorcerer, while others let the
Barbarian reach melee and kill the Sorcerer.

The new harness also found one agent-contract fuzz point. Incapacitated rows
were correctly marked `can_afford = false`, but decision epochs still attached
a synthetic target index to no-target rows. That made diagnostic rows look more
command-like than they really were.

### Integrated Change

- Added `sorcerer_barbarian_duel` to the AI validation arena catalog.
- Added `ai.external_selfplay.run_external_selfplay()` for fast in-process
  external-vs-external duels through the epoch command surface.
- Added validation coverage proving the arena uses real level 5 Sorcerer and
  Berserker Barbarian factories, real spell lists, real gear, and real class
  actions.
- Added a self-play regression for the Hold Person case: the held Barbarian
  sees unaffordable self rows but selects `end_turn`, not `Reckless Attack`.
- Tightened decision epoch rows so unaffordable/no-target rows expose zero
  executable targets.
- Hardened the AI command endpoint so non-special rows that are unaffordable or
  have no legal targets are rejected before reaching the engine executor.

### Batch Notes

Six `sorcerer_barbarian_duel` self-play runs showed:

- command counts: 16, 19, 27, and command-cap 30 runs;
- elapsed time range: roughly 1.7-3.1 seconds per duel;
- Sorcerer control pattern: `Hold Person__slot_2`, hold spacing, then
  `Magic Missile__slot_1` pressure;
- Barbarian pressure pattern after control breaks: Rage/Frenzy/Reckless,
  movement, melee attacks;
- policy issue still worth improving: the Sorcerer sometimes recasts Hold
  Person when damage tempo may be better.

### Verification

- `uv run pytest tests/manual/test_37_ai_validation_arenas.py -q -k "catalog_has_diverse or sorcerer_barbarian_duel"`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q -k "external_selfplay"`
- `uv run pytest tests/manual/test_15_class_features.py -q -k "paralyzed_barbarian_cannot_use_zero_cost_reckless_attack"`
- `uv run pyright ai/external_selfplay.py ai/subjective/epochs.py dnd/scenarios/ai_validation_arenas.py tests/manual/test_37_ai_validation_arenas.py tests/manual/test_39_ai_validation_harness.py server/event_server.py`

### Next Targets

- Use the self-play runner for small batches before live NeuroClient checks.
- Add policy notes for repeated control recasts versus switching to damage.
- Rotate the same runner through door arenas after the Sorcerer-Barbarian loop
  stays stable.

## 2026-07-04 - External Duel Incapacitated Guard V86

### Context

This rotation used a transient external-vs-external open-floor duel:
`Probe Duel Sorcerer` against `Probe Duel Barbarian`. Both sides were driven
in-process through the same subjective snapshot, decision epoch, and command
endpoints. No live backend or frontend process was touched.

### Finding

The faster duel loop immediately exposed a real engine legality issue. The
Sorcerer selected `Hold Person__slot_2`, which was reasonable. While held, the
Barbarian still received and executed the zero-cost `Reckless Attack` self
action even though `Paralyzed` applies `Incapacitated` and should prevent
actions. This made the duel look like weak AI, but the root problem was a false
legal affordance.

### Integrated Change

- `BaseAction.check_costs()` now treats `Dead` and `Incapacitated` as global
  action blockers, including zero-cost self actions.
- Actions can explicitly opt out through `allow_while_incapacitated` if a
  future rules surface genuinely needs it.
- A class-feature regression proves a paralyzed Barbarian receives no
  executable `Reckless Attack` row and direct execution returns `None`.
- The dashboard now tracks that an external-vs-external duel probe was used
  and that incapacitated zero-cost actions are blocked.

### Result

The rerun changed the Barbarian's held turns from repeated fake `Reckless
Attack` commands to clean end-turns with zero actions and zero movement. Once a
save broke the hold, the Barbarian used `Frenzy`, `Reckless Attack`, movement,
main attack, and Extra Attack, making the duel a real pressure test again.

### Verification

- `uv run pytest tests/manual/test_15_class_features.py -q -k "paralyzed_barbarian or frenzied_strike_discovery"`
- `uv run pyright dnd/core/base_actions.py tests/manual/test_15_class_features.py`

### Next Targets

- Promote external-vs-external probing into a reusable validation harness.
- Consider adding a committed `sorcerer_barbarian_duel` arena if the matchup
  keeps finding class-policy issues.
- Watch Sorcerer post-melee behavior: in the rerun it drank multiple potion
  uses and retreated after the Barbarian reached contact.

## 2026-07-04 - Skeleton Frontier Momentum V85

### Context

This rotation moved to skeleton-side validation with `standard_skeleton_doors`
in `codex_monsters` mode. The Hero side was driven in-process by the external
AI until the first Codex monster turn, then the Codex monster side followed the
current top recommendation sequence. No live backend or frontend process was
touched.

### Finding

The subjective surface was correct: the skeletons did not know a visible enemy
before contact and used the known door objective. The awkward part appeared
after the door opened. Once a skeleton crossed the doorway, used Dash, and still
had no visible enemy, the frontier sorter could recommend a long move back
toward the starting side because it favored long axis-aligned movement without
remembering the actor's just-observed exploration direction.

### Integrated Change

- Codex frontier sorting now derives a recent movement vector from the actor's
  visible subjective combat logs.
- No-contact frontier moves aligned with that vector are ranked ahead of
  sideways or backward long runs.
- Same-turn backtracking protection still removes recently occupied cells.
- The dashboard `Policy Observability` chart tracks the frontier-momentum fix.

### Result

The rerun kept skeleton exploration moving through the opened boundary. One
representative sequence changed from a post-Dash sideways/backward move toward
`(13, 6)` to continued exploration through the boundary, such as `(0, 7)` for
the Skeleton Archer after crossing the door.

### Verification

- `uv run pytest tests/manual/test_30_codex_takeover_tools.py -q -k "frontier or open_door_route or reaching_open_door_anchor or objectward"`

### Next Targets

- Rotate next to Sorcerer-facing validation.
- Watch whether no-contact frontier momentum overcommits when the actor should
  regroup instead of continuing alone.
- If this remains stable, expose a compact `frontier_momentum` note in the turn
  summary rather than requiring log inspection.

## 2026-07-04 - Barbarian Hold-Spacing Telemetry V84

### Context

This rotation moved back to a Barbarian-facing validation using
`ranged_loadout_kiting_ring` in `human_hero` mode. The probe ran fully
in-process through the ASGI test client with external subprocess spawning
disabled, so the live backend and NeuroClient frontend were not touched.

The pre-contact leak investigation stays closed. This probe looked only at the
post-contact ranged-monster behavior after the Barbarian was visible.

### Finding

The ranged monsters behaved mostly as intended: they used pressure rows,
spread from allies, and then held position instead of walking into melee.
The friction was observability. A `hold_ranged_spacing` command carried only
the reason and `spacing_control` tag, so reviewing the trace did not explain
which visible enemy and spacing threshold made holding correct.

### Integrated Change

- `AgentCommand` now carries `reference_entity_uuid`,
  `reference_entity_name`, `reference_entity_position`,
  `reference_entity_distance_cells`, and `spacing_floor_cells`.
- The `hold_ranged_spacing` branch fills those fields from the nearest
  subjectively visible enemy and the ranged spacing floor.
- The dashboard `Policy Observability` chart tracks whether hold-spacing
  reference enemy and floor data are present.

### Result

The policy behavior is unchanged, but selected-command telemetry now explains
why the AI held its turn: the trace can show, for example, that the Hero was
the reference enemy, at a concrete grid position, with the actor already at or
above the six-cell spacing floor.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "hold_ranged_spacing or holds_spacing or hold_spacing"`

### Next Targets

- Run another Barbarian-facing live-length validation and watch whether ranged
  actors overuse spread movement after their pressure rows.
- Rotate to skeleton-side or Sorcerer only after one more non-leak
  enemy-behavior pass.
- If a ranged actor loses sight after spreading, decide whether that needs
  line-of-sight-preserving spread scoring rather than more trace metadata.

## 2026-07-04 - Sorcerer Projectile Allocation Telemetry V83

### Context

This rotation moved back to a Sorcerer validation after the skeleton-side
objective pass. The probe used `multi_projectile_no_aoe_lab` in
`codex_monsters` mode and drove the external Sorcerer Hero in-process. No live
backend or frontend process was touched.

The first probe showed that the engine and epoch surface exposed Magic Missile
rows correctly, but the fixture had drifted out of the conservative one-dart
cleanup threshold: the visible enemies were at `4`, `4`, and `5` HP, while the
policy only splits Magic Missile when one dart is likely to remove the extra
target at `3` HP or less. The observed command was therefore a one-target
`Fire Bolt`, which did not exercise the multi-target path this arena is meant
to validate.

### Integrated Change

- The no-AoE projectile lab now starts the three visible enemies at `3`, `2`,
  and `3` HP so level-1 `Magic Missile` is the clear multi-target cleanup row.
- `AgentCommand` now exposes `extra_target_names` and
  `extra_target_positions` alongside `extra_target_uuids`.
- `_execute()` resolves those extra-target display facts from the same
  subjective action target options and visible/controlled facts already present
  in the reduced state.
- The dashboard `Policy Observability` chart now tracks whether extra target
  names and positions are logged.

### Result

The rerun selected `Magic Missile__slot_1`, primary target
`Validation Projectile Archer`, with extra targets `Validation Projectile
Goblin` at `(8, 11)` and `Validation Projectile Warrior` at `(8, 3)`. The
in-process command timing for the execute path was `20.132 ms`.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "magic_missile or multi_entity"`
- `uv run pytest tests/manual/test_37_ai_validation_arenas.py -q -k "multi_projectile_no_aoe_lab"`
- `uv run pyright ai/external/policy.py dnd/scenarios/ai_validation_arenas.py tests/manual/test_35_subjective_external_ai.py tests/manual/test_37_ai_validation_arenas.py`
- `uv run python -m json.tool ai/AGENT_UX_ITERATION_STATS.json > /tmp/dnd_ai_v83_stats_checked.json`
- `node --check /tmp/dnd_agent_dashboard_v83.js`

### Next Targets

- Rotate next to Barbarian or skeleton-side validation before another Sorcerer
  slice.
- If projectile timing regresses in longer games, instrument the post-action
  command-result projection path rather than policy selection.
- Keep checking that multi-target allocation details are derived from
  subjective epoch rows, not objective state.

## 2026-07-04 - Codex Turn Objectives V82

### Context

This rotation moved from the Barbarian-facing route-metadata pass to a
skeleton-side Codex validation. The probe started `standard_skeleton_doors` in
`codex_monsters` mode, let the external Hero act in-process, and then inspected
the Codex monster turn surface. No live backend or frontend process was touched.

The Codex-controlled monsters correctly did not know a visible enemy at their
first turn boundary. The active actor was the Skeleton Warlock; the subjective
surface contained the skeleton side, the known closed door, torches, and no
living enemies. The top recommendation was a multi-target `Necrotic Bless`,
which is reasonable setup. The friction was that the known door objective was
buried in `objectward_moves`; because `multi_target_actions` occupied the
primary recommendation category, route progress was not visible in the top
shortlist.

### Integrated Change

- Added `TurnObjectiveSummary` to the Codex tool contracts.
- `TurnSummaryResult` now exposes an `objectives` list beside
  `recommendations`.
- The summary builder derives objectives from already-subjective sections:
  visible enemies, remembered enemies, objectward moves, retreat moves, useful
  moves, and frontier moves.
- No-contact support turns now preserve a deferred known-object objective such
  as "approach Door at `(7, 7)`; best move reaches `(7, 7)`" even when support
  remains the highest-ranked recommendation.
- The dashboard `Policy Observability` chart now plots objective availability
  and deferred door objective coverage.

No monster content, spells, gear, scenario setup, projection rules, human
client endpoints, or global rules were changed.

### Result

The Codex operator surface now separates "what should I click first?" from
"what objective should I not forget after this click?" This makes no-contact
skeleton-side turns easier to review without adding another backend query or
leaking objective state.

### Verification

- `uv run pytest tests/manual/test_30_codex_takeover_tools.py -q -k "deferred_door_objective or legal_adjacent_open_door or remembered_enemy_search_objectives"`
- `uv run pyright ai/codex_tools/contracts.py ai/codex_tools/client.py tests/manual/test_30_codex_takeover_tools.py`

### Next Targets

- Rotate next to a Sorcerer hero validation or a non-door skeleton-side arena.
- Feed objective counts into live probe artifacts so we can compare objective
  visibility across arenas.
- If post-reveal routing still looks wrong in NeuroClient, add directional
  blocker facts to the reduced route model and test wall-side oscillation
  explicitly.

## 2026-07-04 - Selected Command Route Metadata V81

### Context

After the strict pre-contact subjectivity fix, the next rotation moved back to
a Barbarian baseline with skeleton-side external AI. The in-process probe used
the standard door arena without touching the live backend/frontend processes.
Before the monsters acted, their subjective state contained only the skeleton
side, the known door, and skeleton initiative rows. No Hero fact or anonymous
enemy placeholder was present.

The first observed skeleton-side commands were plausible: the warlock opened
with support setup, moved toward the known closed door, then held ranged
spacing after the Hero became legitimately visible. The friction point was
reviewability rather than target leakage: selected commands named the routine
and row id, but did not carry the selected target position, path cost, hazard
flag, or selected path. That made route choices hard to audit during live
reviews.

### Integrated Change

- `AgentCommand` now carries selected target UUID/name/position, distance,
  path cost, safe path cost, hazard flag, path cells, and safe-path cells.
- `_execute()` fills those fields directly from the selected subjective
  affordance row.
- Policy telemetry now includes those fields inside `selected_command`, so a
  live policy tick can explain which square/path was chosen without another
  backend query.
- The dashboard now has a `Policy Observability` chart and a metric card for
  selected-command route metadata.

No monster spells, gear, arena content, human/NeuroClient endpoints,
subjective projection rules, or global rules were changed.

### Result

The next live review should be able to distinguish "the AI moved toward the
door through this route and cost" from "the AI wandered for unclear reasons."
This does not yet solve every post-reveal routing issue, but it gives the
agent event stream enough typed local evidence to debug those choices without
guessing.

### Verification

- `uv run pytest tests/manual/test_29_external_ai_subprocess.py -q -k "moves_toward_visible_enemy or moves_toward_known_closed_door or preserves_action_when_movement_can_reach_door or sorcerer_side_move_before_contact"`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "normal_path_does_not_fetch_available_actions or preserves_action_when_movement_can_reach_door"`
- `uv run pyright ai/external/policy.py tests/manual/test_29_external_ai_subprocess.py tests/manual/test_35_subjective_external_ai.py`

### Next Targets

- Rotate to skeleton-side validation with Codex controlling monsters or a
  Sorcerer hero run, rather than continuing to tune Barbarian-door behavior.
- Add candidate summaries for skipped movement/spacing branches so review can
  explain why a ranged actor held position instead of moving.
- If post-reveal routing still looks wrong in NeuroClient, add directional
  blocker facts to the reduced route model and test wall-side oscillation
  explicitly.

## 2026-07-04 - Unknown Initiative Placeholder Subjectivity Guard V80

### Context

The NeuroClient repro raised a stricter subjectivity requirement than the
existing precontact guards covered: before contact, the monster AI must not even
know that an unseen enemy exists. Earlier regressions already proved that the
Hero UUID, name, movement path, and visible/remembered enemy facts were absent
from the monster-side subjective state. However, the projected encounter state
still included an `Unknown Combatant` placeholder in `initiative_order` for an
unseen uncontrolled combatant.

That placeholder did not reveal identity or position, but it still leaked
existence and initiative-order structure. Under the AI POMDP contract, that is
not acceptable as default subjective data.

### Integrated Change

- AI subjective encounter projection now omits unseen uncontrolled combatants
  from `initiative_order`.
- `current_turn_index` in `ObservationEncounterState` is now documented as a
  subjective index, with `-1` meaning the active combatant is not known to the
  session.
- The hidden-enemy observation regression now asserts that hidden enemies do not
  appear as either entity facts or `Unknown Combatant` initiative rows.
- The Sorcerer side-move regression now checks bootstrap snapshot, streamed
  frames after the human move/end-turn boundary, and final monster snapshot for
  hidden Hero UUID/name and `Unknown Combatant`.
- The dashboard subjectivity chart now has an explicit
  `unknown_combatant_placeholder_removed` guard series.

No monster spells, gear, arena content, human/NeuroClient endpoints, or global
rules were changed.

### Result

In the standard door arena, the monster AI precontact stream now contains only
the monster-controlled side, perceived objects such as the known door, and
session/turn facts for controlled actors. It does not expose the Hero, a hidden
Hero movement frame, or an anonymous initiative placeholder.

The remaining observed oddity is separate: after the door opens and the Hero is
legitimately visible, some movement ranking can still look strange around
walls/doors. That belongs to reduced route scoring, not precontact
subjectivity.

### Verification

- `uv run pytest tests/manual/test_28_subjective_observation_stream.py -q -k "hidden_enemy_is_not_leaked or unseen_enemy_movement"`
- `uv run pytest tests/manual/test_29_external_ai_subprocess.py -q -k "sorcerer_side_move_before_contact"`
- `uv run pyright ai/observation/projector.py ai/observation/models.py tests/manual/test_28_subjective_observation_stream.py tests/manual/test_29_external_ai_subprocess.py`

### Next Targets

- Rotate next to skeleton-side control or a Barbarian validation rather than
  continuing to tune Sorcerer precontact.
- If post-reveal movement still looks wrong in NeuroClient, add directional
  blocker facts to the reduced route model and test the wall-side oscillation
  explicitly.
- Add candidate summaries for skipped movement/spacing branches so review can
  explain why a ranged actor held position or picked a route.

## 2026-07-02 - Codex Barbarian vs Base External AI

### Setup

- Server: local `server.event_server` on `127.0.0.1:8765`.
- Arena: `/simulation/start-human?character_class=barbarian`.
- Codex takeover: `faction=heroes`.
- Monster side: default external behavior-tree AI session.
- Result: Codex barbarian victory in round 4.
- Final hero state: `42/50 HP`, position `(12, 8)`.
- Defeated enemies:
  - Skeleton Archer: killed round 2 by Greataxe plus Frenzied Strike.
  - Skeleton Warrior: killed round 3 by Greataxe attacks plus Frenzied Strike.
  - Skeleton Warlock: killed round 4 by Frenzied Strike after Shield raised AC to 18.

### Play Summary

Round 1 was a setup turn. Codex used Frenzy, moved from `(2, 7)` to `(6, 7)`, opened the door at `(7, 7)`, moved to `(10, 7)`, dashed, then moved to `(11, 7)` to anchor melee near the archer.

Round 2 started with the hero at `49/50 HP`. Codex used Reckless Attack, attacked the Skeleton Archer with Greataxe, used Extra Attack on the same target, then killed it with Frenzied Strike.

Round 3 started with the hero at `45/50 HP`. Codex used Reckless Attack, attacked the Skeleton Warrior, used Extra Attack, then killed it with Frenzied Strike. The hero then moved to `(12, 8)` to pin the Skeleton Warlock.

Round 4 started with the hero at `42/50 HP`. Codex used Reckless Attack, missed the first Greataxe attack, hit with Extra Attack, observed the warlock's AC increase to 18 from Shield, then killed it with Frenzied Strike.

### What Worked

- Runtime Codex takeover worked for the hero side without spawning a Codex subprocess.
- `watch` kept the takeover alive and returned control promptly after the base AI turns.
- Decision epochs had the legal rows needed to play the full game.
- Door interaction, movement after Dash, Extra Attack, Reckless Attack, Frenzy, and Frenzied Strike all flowed through the epoch command path.
- The base external AI stayed alive after the takeover stream reset and completed its monster turns.

### Main Friction

- `actions` returns too many rows to use directly. Early turns had 200+ rows, mostly movement. This makes the agent spend attention on table parsing instead of tactical choice.
- The brief has no tactical grouping. It lists visible entities and objects, but does not say "you are adjacent to archer and warrior", "warlock is 10 ft away", or "move to `(11, 7)` pins the archer".
- Command acks are inconsistent as combat feedback. One attack returned `"Attack missed"`, but most hits returned only `"Attack completed"`, forcing a follow-up brief to learn damage.
- Affordability exists in `ActionChoice.can_afford`, but the normal CLI output does not emphasize it. Unaffordable rows are easy to misread as choices.
- Item rows remain affordable after action/bonus economy is spent, but their cost is opaque. This makes potions look like free tactical power unless the agent already knows the rule policy.
- AoE, route, opportunity-risk, and target-priority helpers are still absent. This mattered less for barbarian than sorcerer, but movement-to-melee still required manual coordinate reasoning.
- `recent_combat_logs` in the Codex brief remained empty during this run, so the agent could not rely on the brief for event narration.
- Final subjective brief did not list the killed warlock in `visible_entities`, while it still listed other dead enemies. That may be a visibility/materialization edge case worth checking.

### Next Improvement

Build a compact operator-facing turn summary for Codex tools:

- Group entities into controlled actor, visible living enemies, visible dead enemies, and known objects.
- Add simple distance and adjacency labels from the active actor.
- Group action rows into affordable attacks, affordable self/object actions, movement candidates, and unaffordable rows.
- Highlight likely useful movement anchors near living enemies and known closed doors.
- Show top attack rows with target name, target HP, AC, distance, and row id.
- Keep the raw `actions` command available, but add a compact command so Codex can play quickly without parsing hundreds of rows.

### Implemented Improvement

Added a compact Codex `turn` command backed by `CodexToolClient.turn_summary()`.

The summary keeps raw `brief` and `actions` intact, but gives the operator a smaller tactical surface:

- active actor facts;
- visible living enemies and visible dead enemies;
- known objects;
- affordable entity rows with target HP, AC, distance, and row id;
- affordable self/object interaction rows;
- useful movement rows that close to or become adjacent to living enemies;
- unaffordable row counts by bucket;
- warnings when the subjective brief lacks recent combat logs or lacks a current epoch.

Smoke result against the completed barbarian session:

- `turn` returned the hero at `(12, 8)` with `42/50 HP`.
- `is_my_turn` was `false` because the encounter had ended.
- No living enemies remained.
- The warning about missing recent combat logs appeared, matching the playthrough friction.

### Follow-Up UX Targets

- Add combat-log summaries to command results and briefs.
- Add explicit item/action cost text to compact rows.
- Add route and opportunity-risk summaries for movement rows.
- Add AoE preview summaries for position-targeted spells.
- Investigate why the final killed warlock disappeared from the final subjective visible/dead lists.

## 2026-07-02 - Codex Monsters vs Base External Fighter

### Setup

- Server: local `server.event_server` on `127.0.0.1:8765`.
- Arena: `/simulation/start-human?character_class=fighter`.
- Codex takeover: `faction=monsters`.
- Hero side: manually attached existing external melee agent to a session controlling the hero.
- Result: Codex monster victory in round 5.
- Final monster state:
  - Skeleton Warlock: `17/17 HP`, position `(7, 8)`.
  - Skeleton Warrior: `11/31 HP`, position `(3, 7)`.
  - Skeleton Archer: `24/24 HP`, position `(12, 7)`.
- Final hero state: defeated by the Skeleton Warrior after being reduced to `8/44 HP`.

### Play Summary

Round 1 exposed the door and engagement problem. The external hero AI acted first, saw no enemies and no known closed doors, and ended its turn. Codex used the Skeleton Warlock to move to the door, open it, and cast Necrotic Bless on the Skeleton Warrior. The Archer marked and shot the hero but missed. The Warrior moved through the door, dashed, and engaged the hero at `(3, 7)`.

Rounds 2 through 5 became a damage race. The Warrior held the hero in melee while the Archer kept firing down the open line. The Warlock had no hostile spell rows after the opening buff, so Codex preserved concentration and used Dodge each round. The hero repeatedly attacked the Warrior but never broke through fast enough.

### What Worked

- Codex could play the monster side through takeover without being a subprocess.
- The same epoch command path supported multi-entity monster control.
- Door opening, ranged pressure, melee engagement, Dash plus movement, and final encounter end all worked through Codex tools.
- `turn` was much better than raw `actions` for ranged and melee attacks once enemies were visible.
- The final command result correctly reported `encounter_ended: true` and cleared the current epoch.

### Main Friction

- `turn` did not accept `--json`, even though other tool commands produce JSON and the flag is natural muscle memory.
- `turn` showed only the active actor and enemies. I had to call `brief` to confirm the other controlled skeletons were alive.
- Ally/self entity rows such as Invisibility and Necrotic Bless were grouped under `attacks`, which made the tactical surface misleading.
- Before Dash, the Warrior's legal move to `(6, 7)` was a useful long closing move, but `turn` showed `useful_moves: []` because the destination was still more than 15 ft from the hero.
- The Warlock never surfaced an offensive spell row after opening the door. This may be build/loadout/action-discovery behavior, but it needs investigation because a "Skeleton Warlock" that only buffs and dodges feels suspicious.
- `recent_combat_logs` stayed empty. I inferred hero attacks and damage from HP deltas instead of getting event narration.
- The external hero AI did not explore toward the door before enemies were visible, confirming that door/object exploration needs to be part of the agent-side state processors.

### Implemented Improvement

Updated the Codex `turn` surface after this run:

- `turn --json` is accepted for CLI consistency.
- The summary now includes all controlled entities plus visible non-actor allies.
- Hostile entity rows stay in `attacks`; self/ally/neutral entity rows move to `support_actions`.
- Long movement rows are kept when they improve distance to a visible enemy, even if they do not end within 15 ft.

### Follow-Up UX Targets

- Put recent subjective combat/event summaries into `brief` and `turn`.
- Add action-economy/cost text to each compact row.
- Add a route/path explanation for movement rows, including why a move is recommended.
- Investigate the Warlock's missing hostile rows.
- Teach the baseline external AI to use known doors/exploration objectives before enemies are visible.

## 2026-07-02 - Codex Sorcerer vs Base External AI

### Setup

- Server: local `server.event_server` on `127.0.0.1:8765`.
- Arena: `/simulation/start-human?character_class=sorcerer`.
- Codex takeover: `faction=heroes`.
- Monster side: default external behavior-tree AI session.
- Result: Codex sorcerer victory in round 2.
- Final hero state: `37/37 HP`, position `(6, 7)`.
- Defeated enemies:
  - Skeleton Warlock: killed by Fireball in round 1.
  - Skeleton Warrior: killed by Quickened Magic Missile in round 1.
  - Skeleton Archer: killed by Magic Missile in round 2.

### Play Summary

The opening subjective state did not reveal enemies or the door, but movement rows allowed the hero to move toward the corridor. Codex moved to `(6, 7)`, revealed and opened the door, then saw all three skeletons clustered around `(12, 7)`.

The compact `turn` view showed many single-target spell rows but did not preview AoE. Codex inspected raw epoch rows, selected `Fireball` centered at `(12, 7)`, killed the Warlock, and damaged the Warrior and Archer without hitting the hero.

After Fireball, Quickened Spell remained available. Codex activated it and used Magic Missile at level 2 to kill the Warrior. Codex then closed the door and ended the turn. The external Archer opened the door and moved adjacent but did not hurt the hero. On round 2, Codex used another Magic Missile level 2 to kill the Archer and end the encounter.

### What Worked

- The epoch command path handled position-targeted Fireball, Quickened Spell, and follow-up Magic Missile in one turn.
- The improved `turn` summary correctly separated self Invisibility from hostile rows when self-targeted.
- Dead enemy rows remained visible for the Warlock and Warrior after the first round.
- The external AI could open the door and re-engage after Codex closed it.
- Command results correctly reported the final `encounter_ended: true`.

### Main Friction

- `turn` did not preview AoE rows. I had to inspect raw `actions` and manually infer that Fireball at `(12, 7)` would hit all skeletons and spare the hero.
- Opening exploration remains weak. With no visible enemies, `useful_moves` listed arbitrary low-coordinate movement rows instead of likely objective moves toward doors, chokepoints, or remembered threats.
- After closing the door, the living Archer disappeared from the subjective enemy list instead of appearing as remembered or last-known.
- `turn` treated enemy-targeted Invisibility as an attack because classification was based mostly on target hostility, not action semantics.
- Combat logs were still absent, so damage had to be inferred from HP changes and command messages.
- Action economy and resource consequences were not explicit enough. Quickened Spell worked, but the interface did not explain why spell rows reappeared or what resource/cost was consumed.

### Next Improvement

Add AoE previews and improve hostile/support spell classification in the Codex `turn` surface:

- show position-targeted damaging rows as `area_actions`;
- estimate visible enemies/allies/self affected by each candidate center;
- sort rows that hit more enemies and avoid allies/self first;
- keep this as an agent-facing preview, not engine authority;
- classify hostile entity actions by likely action semantics, not only by enemy target.

### Implemented Improvement

Added heuristic AoE previews and stricter hostile/support entity-action classification to the Codex `turn` surface.

- Position-targeted spell rows such as Fireball now appear in `area_actions`.
- The preview estimates visible enemies, allies, and self included in each area.
- Clean enemy-heavy area rows sort first.
- Non-damaging enemy-targeted spells such as Invisibility stay in `support_actions`.
- The transport/network wrapper now returns structured request errors instead of surfacing a traceback.

## 2026-07-02 - Codex Fighter vs Base External AI

### Setup

- Server: local `server.event_server` on `127.0.0.1:8765`.
- Arena: `/simulation/start-human?character_class=fighter`.
- Codex takeover: `faction=heroes`.
- Monster side: default external behavior-tree AI session.
- Result: Codex fighter victory in round 4.
- Final hero state: `23/44 HP`, position `(11, 7)`.
- Defeated enemies:
  - Skeleton Warlock: killed round 1 after Action Surge and four longbow attempts.
  - Skeleton Warrior: killed round 3 by offhand dagger after melee pressure at the door.
  - Skeleton Archer: killed round 4 by Extra Attack shortsword.

### Play Summary

Round 1 started with no visible enemies and no door in the compact view. Codex inspected raw epoch rows, moved to `(6, 7)`, opened the door, saw all three skeletons, then focused the Skeleton Warlock with longbow attacks. The first and third shots missed, but Action Surge exposed a fresh attack sequence and the fourth shot killed the Warlock. Codex closed the door before ending the turn.

The external AI reopened the door, moved the Warrior adjacent to the hero, and dealt minor damage. Rounds 2 and 3 became a doorway melee. Codex used shortsword, Extra Attack, and offhand dagger rows against the Warrior, killing it in round 3, then used remaining movement to move adjacent to the Archer at `(12, 7)`.

The Archer hit the hero during its last turn, bringing the hero to `23/44 HP`. Round 4 exposed adjacent melee rows and Second Wind. Codex chose offense, hit the Archer with shortsword, then killed it with Extra Attack.

### What Worked

- Codex played the full hero side through runtime takeover and session-authorized epoch commands.
- No Codex subprocess was spawned.
- No normal control path relied on the debug `/available-actions` endpoint; action rows came from decision epochs embedded in the subjective snapshot.
- Door open/close, longbow attacks, melee attacks, offhand attacks, Action Surge, Extra Attack, movement after attacks, and encounter end all flowed through the new command endpoints.
- The compact `turn` summary was enough to complete the fight once enemies were visible.
- The base external AI did open the door and continued to act against the Codex-controlled hero.

### Main Friction

- With no visible enemies, `turn` still showed arbitrary movement rows instead of exploration objectives such as "move toward remembered/known door" or "advance along newly visible corridor".
- Raw `actions` was still needed once at the start to choose the first door-revealing move.
- Combat logs are still absent from the Codex brief, so incoming enemy damage had to be inferred from HP deltas.
- Action rows lacked cost/economy text during play. This made Action Surge, Extra Attack, offhand attacks, Second Wind, and potions harder to reason about than they should be.
- Weapon rows lacked weapon-slot and damage metadata in the compact summary, so choosing shortsword vs dagger vs longbow still depended on outside knowledge.
- Movement rows did not display path/safe-path/hazard details, even though the subjective epoch has path fields.
- Item and object rows remained visible late in the turn, but the compact view did not explain their costs. This is especially risky for potions, where the agent should not infer they are free unless the epoch explicitly says so.

### Next Improvement

Expose cost, economy, and route metadata in the Codex `turn` surface:

- show the active actor's current action economy and resources;
- attach compact `cost_summary` text to attacks, support actions, interactions, and area actions;
- preserve weapon name, weapon slot, spell level, and cast-at level on compact rows;
- show path cost, safe path cost, and hazard flags on movement candidates;
- warn when item/object rows report no nonzero cost in the decision epoch.

### Implemented Improvement

Added cost, economy, and route metadata to the Codex `turn` surface.

- `turn` now includes `action_economy` for the active actor.
- Compact attacks, support actions, interactions, and area rows include `cost_summary`.
- Weapon rows preserve `weapon_name` and `weapon_slot`.
- Spell rows preserve `spell_level` and `cast_at_level`.
- Movement rows preserve `path_cost`, `safe_path_cost`, and `is_path_hazardous`.
- Item/object rows that report no nonzero cost produce a warning instead of quietly looking free.

## 2026-07-02 - Codex Monsters vs External Fighter, Cost Surface Check

### Setup

- Server: local `server.event_server` on `127.0.0.1:8765`.
- Arena: `/simulation/start-human?character_class=fighter`.
- Hero side: external behavior-tree agent attached to an AI session controlling the Hero.
- Codex takeover: `faction=monsters`.
- Result: Codex monster victory in round 6.
- Final surviving monsters:
  - Skeleton Archer: `24/24 HP`, position `(12, 7)`.
  - Skeleton Warlock: `17/17 HP`, position `(7, 7)`.
- Dead monster:
  - Skeleton Warrior: killed by the Hero in round 6 after holding melee pressure for several rounds.
- Final hero state: defeated by the Skeleton Archer after being reduced to `2/44 HP` by Eldritch Blast.

### Play Summary

Codex joined after the external hero and the original external monster side had already advanced into round 3. The battlefield was already open: the Door at `(7, 7)` was open, the Skeleton Warrior was adjacent to the Hero near `(3, 7)`, the Warlock was at the door, and the Archer was firing from the far side.

Round 3 started with the Warlock active. Codex used Eldritch Blast, missed, then kept the Warlock at range rather than moving into melee. The Archer used Mark Target as a visible `bonus:1` row, then shot the Hero for 6 damage. The Warrior attacked in melee but missed.

Round 4 repeated the pressure. The Warlock hit for 2 force damage, the Archer missed, and the Warrior hit the Hero for 8. The cost surface made it easy to distinguish the Archer's `bonus:1` Mark Target from the `action:1` Shortbow row and to avoid wasting action economy.

Round 5 nearly ended the fight. The Hero damaged the Warrior, but the monsters kept pressure: Warlock missed, Archer missed, and Warrior hit the Hero down to 10.

Round 6 the Hero killed the Warrior, leaving two ranged monsters. The Warlock hit with Eldritch Blast for 8, dropping the Hero to 2 HP. The Archer then landed the final Shortbow attack and ended the encounter.

### What Worked

- Runtime takeover over all monsters worked in the middle of an already-running fight.
- A separate external AI session could control the Hero even though the arena originally presents the Hero as a human-controlled combatant.
- The new `turn` surface made action economy readable:
  - Warlock: `actions`, `bonus_actions`, spell slots, and cantrip rows.
  - Archer: `Mark Target` as `bonus:1`, `Shortbow` as `action:1`.
  - Warrior: `Longsword` as `action:1`.
- Weapon metadata made the compact attack rows much more legible.
- Movement path costs appeared and helped identify that post-attack Warlock movement into melee was possible but tactically undesirable.
- The command path handled a late takeover, multiple active controlled entities, concentration, misses, hits, deaths, and final encounter end.

### Main Friction

- Recent combat logs were still empty. I repeatedly inferred the external Hero's behavior from HP deltas.
- Command messages are inconsistent: some hits report exact damage, while other successful hits only say `"Attack completed"`.
- The turn summary recommends adjacent movement based only on closeness. For a caster, moving adjacent to the Hero after Eldritch Blast was a bad suggestion.
- Spell rows showed `spell_level` and `cast_at_level`, but cost summaries initially showed only `action:1`. Leveled non-item spells need to show both action and slot cost.
- Item-provided spells and scrolls must not be mislabeled as spending spell slots just because they have a cast level.
- Joining as monsters after the hero agent started meant Codex missed the opening phase. That is valid for takeover testing, but a cleaner "start with Codex monsters and external hero" harness would be better for repeatable games.

### Next Improvement

Fix spell cost summaries:

- preserve explicit slot costs when the epoch supplies them;
- infer `slot:N` only for non-item spell variants where `cast_at_level > 0`;
- keep item/scroll spell rows action/item-costed rather than pretending they spend a spell slot;
- keep cantrips as action-only rows.

### Implemented Improvement

Updated the Codex tool cost normalizer for spell rows.

- Explicit epoch `spell_slot_cost` values are preserved.
- Non-item spell rows with `cast_at_level > 0` now summarize as action plus slot, such as `action:1, slot:3`.
- Cantrips remain action-only.
- Item/scroll spells no longer infer a spell-slot cost from their cast level.

## 2026-07-02 - Current Codex Attach Surface, Fighter vs Base External AI

### Setup

- Server: local `server.event_server` on `127.0.0.1:8765`.
- Arena: `/simulation/start-human?character_class=fighter`.
- Codex control path: `ai.codex_tools attach --faction heroes`.
- Monster side: default external behavior-tree AI session.
- Result: Codex fighter victory in round 5.
- Final hero state: `37/44 HP`, position `(11, 7)`.
- Defeated enemies:
  - Skeleton Warlock: killed round 1 by the Action Surge longbow sequence.
  - Skeleton Warrior: killed round 3 by Extra Attack shortsword.
  - Skeleton Archer: killed round 5 by Extra Attack shortsword.

### Play Summary

This run validated the explicit "Codex as this thread" surface. `attach` claimed the Hero, returned the Codex session id, takeover claim id, current subjective brief, current turn summary, and ready-to-run watch/turn/execute/end-turn commands. No Codex subprocess was spawned.

Round 1 used a direct movement row to reach `(6, 7)`, because no enemies were visible and the compact surface still did not prioritize exploration. From there, the door appeared in subjective state, `Open Door` appeared as an epoch row, and opening it revealed all three skeletons. Codex focused the Warlock with longbow attacks and Action Surge. Shield raised the Warlock's AC to 18 after the first miss, but the final Extra Attack killed it.

Rounds 2 and 3 were a melee exchange at the door. The external AI moved the Warrior adjacent to the Hero. Codex used Shortsword, Extra Attack, and offhand Dagger across two turns, killing the Warrior in round 3, then moved adjacent to the Archer. The move immediately exposed a remaining offhand Dagger row against the Archer, proving the variable-length turn loop was working.

Rounds 4 and 5 finished the Archer. Codex stayed adjacent, used the melee attack sequence, and killed the Archer with Extra Attack. The final command response reported `encounter_ended: true` and the turn summary cleared the current epoch.

### What Worked

- `attach` is now a real current-Codex operator entry point, not a second controller mode.
- The command path stayed on session-authorized subjective epochs and `/commands/...` endpoints.
- `watch` kept the takeover lease alive and woke the current thread when the Hero's next epoch started.
- Door reveal, door use, Shield reaction state, Action Surge, Extra Attack, offhand attack, movement after attacks, and encounter end all worked through the same row-id command flow.
- State after every command was good enough to continue playing without querying objective `/state` or debug `/available-actions`.
- Moving after attacks correctly produced new local affordances, including offhand attack after repositioning.

### Main Friction

- `turn` still lacks exploration intent when no enemies are visible. It shows low-coordinate movement rows before likely corridor/door progress.
- `recent_combat_logs` remained empty for the entire run, so the agent inferred monster actions from HP and position deltas.
- Command result text is inconsistent. Some misses are explicit, while many hits are only `"Attack completed"`.
- Final dead enemy visibility is still inconsistent: after the Archer died, the final compact `dead_enemies` list showed Warlock and Warrior but not the Archer.
- Item/object rows still often report `free`, including potions, which makes them look like exploits unless the agent already knows the policy.
- Attack row sorting can put a bonus-action offhand row before the free Extra Attack row, even when the free follow-up is tactically the natural next step.

### Implemented Improvement

Added the explicit Codex operator attach surface:

- `CodexToolClient.attach()` wraps takeover plus subjective brief/turn loading.
- `ai.codex_tools attach` prints a typed `AttachResult`.
- `AttachResult` includes claim id, session id, claim payload, current brief, optional current turn summary, and ready-to-run watch/turn/execute/end-turn/release commands.
- The existing takeover endpoint and controller semantics remain unchanged.

### Follow-Up Implemented Improvement

Added visible combat-log history to subjective snapshots so fresh Codex `brief` and `turn` calls can show recent narration without replaying from cursor zero.

- `ObservationSnapshot` now carries session-visible `combat_logs`.
- `materialize_snapshot()` seeds `ObservationMaterializedState.combat_logs` from the snapshot.
- The observation projector filters snapshot logs through the same perceiver/direct-involvement rules used for frames.
- Subjective frame replay now emits combat-log narration only at the top-level engine combat-log boundary, matching `Encounter.combat_log` with nested `sub_entries` instead of duplicating child logs as standalone entries.
- The next game should validate that `turn.recent_combat_logs` now explains enemy actions and damage directly.

## 2026-07-02 - Codex Monsters vs External Barbarian

### Setup

- Server: local `server.event_server` on `127.0.0.1:8765`.
- Arena: `/simulation/start-human?character_class=barbarian`.
- Codex control path: runtime monster takeover through `ai.codex_tools`.
- Hero side: existing external behavior-tree agent attached to a session controlling the Barbarian.
- Result: Codex monster victory in round 5.
- Final surviving monsters:
  - Skeleton Archer: `24/24 HP`, position `(7, 7)`.
  - Skeleton Warrior: `15/31 HP`, position `(7, 6)`.
  - Skeleton Warlock: `17/17 HP`, position `(7, 8)`.
- Final hero state: defeated by the Skeleton Warlock's Eldritch Blast after being reduced to `1/50 HP`.

### Play Summary

The external Barbarian started with no visible enemies or known door and immediately ended its first turn. Codex took over all monsters. The Skeleton Archer moved from `(12, 7)` to the door at `(7, 7)`, opened it, revealed the Hero at `(2, 7)`, and hit with a Shortbow shot for 5 damage.

The Skeleton Warrior moved to `(7, 6)`, dashed, but could not route through the doorway because the Archer occupied the chokepoint. The Skeleton Warlock moved to `(7, 8)` and used Necrotic Bless on the Warrior instead of taking friendly-fire AoE rows.

After the Hero moved to `(6, 7)` and hit the Warrior, the fight became a doorway surround. The Archer repeatedly used main-hand and off-hand dagger attacks. The Warrior made several Longsword attempts, only one of which connected. The Warlock used Eldritch Blast when safe. The final Eldritch Blast hit for 5 force damage and ended the encounter.

### What Worked

- The current Codex session controlled the monster side through takeover and typed command rows, not through a Codex subprocess.
- The strict subjective stream contained enough information to play a complete multi-entity side.
- Door movement, door opening, reveal, ranged attack, melee attacks, off-hand attacks, Dash, support spell, concentration, cantrip attacks, misses, hits, and encounter end all worked through the epoch command path.
- `watch` now contained recent combat logs with useful top-level narration and nested movement/attack details.
- AoE previews correctly warned that Burning Hands and Thunderwave would hit allies.
- The command result for the final attack reported `encounter_ended: true` and cleared the current epoch.

### Main Friction

- `turn` did not expose `recent_combat_logs`, even though `brief`, `watch`, and the subjective snapshot had them. This made the operator-facing command poorer than the watch output.
- `useful_moves` is too narrow around chokepoints. After the Warrior dashed, the epoch contained many legal movement rows, but `turn.useful_moves` was empty because none improved the simple visible-enemy distance score.
- Chokepoint blockage was not explained. The Warrior had movement remaining but could not get through because the Archer stood in the doorway; the tool did not surface "ally blocks route" or "doorway occupied".
- The first Hero turn exposed an external AI exploration weakness: with no enemies visible and no known door in its reduced state, it ended its turn instead of searching toward the likely door/corridor.
- The `actions` command is still too large for tactical inspection. The dashed Warrior produced 136 position rows.
- The turn surface does not flag opportunity-attack risk when moving away from an adjacent enemy.
- At 1 HP, the Warlock had no guaranteed single-target damage surfaced. AoE rows probably guaranteed the kill through save-half damage but correctly flagged ally risk; the tool should make this trade-off explicit.

### Implemented Improvement

Exposed visible combat-log history directly on `TurnSummaryResult`.

- `turn` now includes `recent_combat_logs` using the same brief data that already powered the missing-log warning.
- The existing missing-log warning remains, but when logs are present the operator can read them directly from the compact turn payload.
- The regression test now verifies that `build_turn_summary()` preserves `brief.recent_combat_logs`.

### Follow-Up UX Targets

- Add chokepoint/path blockage explanations to movement summaries.
- Add opportunity-attack risk to movement summaries.
- Add guaranteed-damage or save-half kill hints when a target is at very low HP.
- Teach the baseline external AI to explore toward known or likely doors before visible enemies exist.
- Keep `actions` as raw debug output, but add filtered row groups for "best closer", "best disengage/kite", "best guaranteed finish", and "blocked route reason".

### Follow-Up Implemented Improvement

Added opportunity-risk metadata to compact movement rows.

- `TurnMoveSummary` now includes `opportunity_attack_risk_names`.
- The Codex `turn` summarizer marks movement rows that start adjacent to a visible enemy and end outside that enemy's adjacent reach.
- Movement rows without opportunity risk sort ahead of risky rows when other tactical value is comparable.
- The regression test covers the doorway case from this run: moving from `(7, 7)` to `(7, 6)` stays adjacent to the Hero and is not risky, while moving to `(8, 7)` leaves reach and is marked as risking the Hero's opportunity attack.

This is still a visibility-level heuristic, not final engine authority. It does not yet account for Disengage, spent enemy reactions, reach weapons, forced movement, or conditions that suppress opportunity attacks.

## 2026-07-02 - Current Codex Barbarian vs External Skeletons

### Setup

- Server: local `server.event_server` on `127.0.0.1:8765`.
- Arena: `/simulation/start-human?character_class=barbarian`.
- Codex control path: current-thread Codex takeover of the Hero faction through `ai.codex_tools`.
- Monster side: default external behavior-tree AI controlling the three skeletons.
- Result: Codex Barbarian victory in round 7.
- Final hero state: `12/50 HP`, position `(14, 1)`.
- Defeated enemies:
  - Skeleton Warlock: killed in round 3 after being focused in melee.
  - Skeleton Archer: killed in round 5.
  - Skeleton Warrior: killed in round 7 after a shove-and-kite sequence.

### Play Summary

This run validated that the current Codex thread can play the hero side through the new hot controller surface. Codex attached to the Hero faction, used `turn`, `watch`, `execute`, and `end-turn`, and never needed objective `/state` or legacy available-action polling to make normal decisions.

Round 1 used Frenzy, movement to the door, `Open Door`, and continued movement into the skeleton room. The hero ended adjacent to multiple skeletons. The monsters returned fire and the Warlock used Shield during the following melee sequence.

Rounds 2 through 4 focused the Warlock first, then the Archer. Recent combat logs were essential: they showed Shield, incoming Archer hits, Warrior crits, Reckless Attack expiry, and the actual damage behind generic command acknowledgements. The hero dropped to `12/50 HP`, making Reckless Attack a bad risk.

Round 5 killed the Archer without Reckless, damaged the Warrior, and tried a bonus-action Shove for survival. The first Shove failed and the Warrior missed on its turn.

Round 6 exposed the most useful tactical discovery of the run. The hero crit the Warrior, missed the extra attack, then successfully shoved the Warrior 20 ft from `(11, 8)` to `(7, 8)`. The compact `turn` summary did not surface the obvious retreat to `(14, 0)`, but the full epoch affordances did. Moving to `(14, 0)` forced the Warrior to spend its turn moving 30 ft to `(13, 2)` without attacking.

Round 7 stepped back into melee at `(14, 1)` and finished the Warrior with Attack plus Extra Attack.

### What Worked

- The current Codex thread could play as a real controller, not as a subprocess or test harness.
- The epoch command path handled variable-length turns: move, attack, extra attack, shove, move again, end turn.
- `recent_combat_logs` on `turn` materially improved decision quality. They made Shield, crits, deaths, misses, movement paths, shove results, and monster turns visible without extra backend spelunking.
- Opportunity-risk movement metadata helped avoid unnecessary opportunity attacks in melee.
- Shove plus movement produced a real tactical survival pattern in the current engine.
- `actions` exposed the complete epoch when the compact brief was not enough.

### Main Friction

- Compact movement summaries were too aggressive about closing and adjacency. After a successful Shove, the best move was a retreat/kite row, but `useful_moves` hid it.
- The `actions` CLI emitted JSON but did not accept the same `--json` flag as `turn`, making the operator surface inconsistent.
- Command acknowledgements still often say only `"Attack completed"`; the agent must read combat logs to know hit details and damage.
- Potions and some item/object rows still report `free`, which makes survival choices look exploitative unless the agent already knows not to use them.
- The Barbarian still shows `self|Frenzy|index=0` on later turns but does not expose the expected damaging Frenzy bonus attack row.
- The final compact `dead_enemies` list can omit enemies that are no longer visible/remembered even though combat logs prove they died.

### Implemented Improvement

Added explicit retreat/kiting movement rows to Codex turn summaries.

- `TurnSummaryResult` now includes `retreat_moves`.
- Retreat rows are legal movement affordances that increase distance from the nearest visible enemy.
- Rows carry the same path cost, hazard, nearest-enemy, adjacent-enemy, and opportunity-risk metadata as `useful_moves`.
- Non-risky, non-hazardous, farthest retreats sort first.
- A regression test covers the round-6 shove situation where `(14, 0)` was the best retreat row after pushing the Warrior to `(7, 8)`.

Also normalized the CLI surface:

- `ai.codex_tools actions` now accepts `--json`, matching `turn`.
- A command-level regression verifies `actions --json` emits the typed `ActionsResult` payload.

## 2026-07-02 - Current Codex Sorcerer vs External Skeletons

### Setup

- Server: local `server.event_server` on `127.0.0.1:8765`.
- Arena: `/simulation/start-human?character_class=sorcerer`.
- Codex control path: current-thread Codex takeover of the Hero faction through `ai.codex_tools`.
- Monster side: default external behavior-tree AI controlling the three skeletons.
- Result: Codex Sorcerer victory in round 2.
- Final hero state: `37/37 HP`, position `(6, 7)`.

### Play Summary

This run exercised the same current-thread controller surface with a spellcaster. Codex attached to the Hero faction, opened the door, evaluated visible enemies from the subjective turn surface, and used the server-issued epoch rows to cast `Fireball` and `Magic Missile` without calling objective state APIs.

Round 1 moved from `(2, 7)` to the door at `(6, 7)`, opened it, revealed all three skeletons, and selected the clean `Fireball` row centered at `(11, 7)`. The blast killed the Skeleton Warlock and Skeleton Archer and left the Skeleton Warrior badly wounded. The newly added `retreat_moves` surface immediately paid off: after the action, Codex retreated to `(4, 5)` instead of staying in the doorway.

The Sorcerer then activated `Quickened Spell`. This spent 2 sorcery points, but the row summary still reported the action as `free`, and the metamagic state persisted into round 2. On round 2, Codex moved back to `(6, 7)`, reacquired the Warrior, used a bonus-action level-3 `Magic Missile`, then finished the Warrior with a level-1 `Magic Missile` using the remaining action.

### What Worked

- The current Codex thread could play the hero side through the new takeover and epoch command surface.
- The server supplied spell rows inside the decision epoch, including `Fireball` area rows and cast-at-level variants.
- The turn summary's area preview was good enough to choose a clean Fireball without manually inspecting every position row.
- `retreat_moves` improved practical play on the first run after implementation.
- Variable-length spellcaster turns worked: movement, object interaction, action spell, metamagic, later bonus-action spell, normal action spell, and encounter end.

### Main Friction

- The final compact `dead_enemies` list only included visible dead enemies. It missed the Warrior after the final Magic Missile even though the nested combat log proved the death.
- The raw `recent_combat_logs` were truthful but too large for quick operator use. Important facts like "Warrior died" and "Warrior took 13 force damage" were buried in nested sub-entries.
- When Codex retreated out of sight, `turn` lost living enemy facts. The only proof that the Warrior still existed was in prior logs. We need remembered enemy and last-known-position facts to be first-class in the subjective turn surface.
- `Quickened Spell` reports as `free` in the compact row cost even though it spends 2 sorcery points. That row needs resource-cost clarity.
- Quickened's persistence into the next round needs a policy review and focused test. It may be correct for the local design, but it should not be accidental.
- Area rows can flood the turn surface when no visible enemies exist. The summary should hide or demote no-target area rows unless they are explicitly useful.

### Implemented Improvement

Added compact recent-combat digest fields to Codex turn summaries.

- `TurnSummaryResult.recent_defeated_names` now extracts defeated entity names from nested visible combat logs.
- `TurnSummaryResult.recent_damage` now extracts compact damage facts from nested `damage_taken` entries.
- The regression test models the Sorcerer run's nested `Magic Missile` log shape and verifies that `Skeleton Warrior` death and force damage are surfaced directly.

This keeps the gameplay truth in the subjective event/log stream while giving the current Codex operator a smaller, typed summary for turn decisions.

### Follow-Up UX Targets

- Add remembered/last-known enemy facts to the subjective turn summary.
- Show resource costs for metamagic and item/object use rows accurately.
- Review and test Quickened Spell duration and follow-up action economy.
- Add a compact "last enemy status" panel derived from visible facts plus recent logs.
- Filter area rows by tactical usefulness when no visible enemies are present.

## 2026-07-02 - Current Codex Fighter vs External Skeletons

### Setup

- Server: local `server.event_server` on `127.0.0.1:8765`.
- Arena: `/simulation/start-human?character_class=fighter`.
- Codex control path: current-thread Codex takeover of the Hero faction through `ai.codex_tools`.
- Monster side: default external behavior-tree AI controlling the three skeletons.
- Result: Codex Fighter victory in round 4.
- Final hero state: `27/44 HP`, position `(6, 7)`.

### Play Summary

This run tested a weapon-and-resource-heavy hero rather than a caster or Barbarian. Codex attached to the Hero faction, opened the same door, killed the Skeleton Warlock with longbow attacks plus Action Surge, kited the Warrior, used Second Wind under pressure, and finished the Skeleton Archer with a longbow Extra Attack.

Round 1 exposed the strongest opener issue. With no visible enemies, `turn.useful_moves` showed early grid rows but did not highlight the doorward/frontier move to `(6, 7)`. The door became visible only after moving adjacent. Once opened, the attack rows correctly prioritized the low-HP Warlock, and the new combat digest made hit damage and death visible without expanding nested logs.

Round 2 validated kiting, but also showed the remembered-enemy gap. Moving to `(0, 7)` hid the Archer from the compact enemy list even though it had already been seen and was still shooting. The only reliable way to reason about it was through recent logs and human memory.

Round 3 exposed action-economy ordering problems. When the Warrior was adjacent, the compact `attacks` list put the bonus-action off-hand Dagger above normal action attacks, and after the main attack it still put the off-hand Dagger above the free Extra Attack. Correct play required manually choosing the Shortsword main attack, then the free Extra Attack, then the off-hand attack only when the Warrior survived at 2 HP.

Round 4 tested Fighter recovery. Second Wind worked correctly and restored 10 HP, but it was buried under Dash, Disengage, Dodge, doors, and item rows. After healing, longbow Attack plus Extra Attack killed the Archer and ended the encounter.

### What Worked

- Current-thread Codex played a complete Fighter game through the subjective epoch command path.
- Action Surge correctly restored an action, and taking that action later created its own Extra Attack follow-up.
- Extra Attack rows, off-hand rows, Second Wind, Action Surge, ranged attacks, melee attacks, movement, door interactions, and encounter end all worked through the command endpoints.
- The damage/death digest added after the Sorcerer run paid off immediately. It made Warlock and Warrior deaths easy to see from `turn`.
- `retreat_moves` again helped with tactical kiting.

### Main Friction

- Opening exploration still lacks a doorward/frontier movement summary when no enemies are visible.
- The compact turn summary only exposes visible living enemies. It needs remembered and last-known hostiles, especially when an Archer drops out of sight after already attacking.
- Attack row ordering must respect action economy. A bonus-action off-hand row should not appear before a normal main attack or free Extra Attack against the same target.
- Adjacent ranged attacks need clearer notes. Longbow appeared next to Shortsword against an adjacent Warrior without warning that melee is usually the better row.
- Survival/resource interactions need priority. Second Wind should be near the top when the actor is damaged, not below generic actions and object rows.
- Healing facts are still visible only in raw logs, not in a compact `recent_healing` digest.

### Implemented Improvement

Improved operator-facing row ordering in Codex turn summaries.

- Hostile attack rows now sort by target priority and then by action economy:
  - free Extra Attack follow-ups;
  - normal action attacks;
  - other free rows;
  - bonus-action attacks.
- Against adjacent targets, melee rows sort before ranged rows at the same economy tier.
- Interactions now put damaged-actor recovery and limited-resource rows ahead of generic/object rows:
  - Second Wind when damaged;
  - Action Surge;
  - healing potion rows;
  - basic actions;
  - doors and other object rows.
- A focused regression test covers the Fighter run shape: Extra Attack before Shortsword before Longbow before off-hand Dagger, and Second Wind before Action Surge/potion/Dash.

### Follow-Up UX Targets

- Add remembered/last-known enemy facts to the compact turn surface.
- Add a frontier/doorward movement group for no-visible-enemy turns.
- Add adjacent-ranged warnings or disadvantage hints to attack rows.
- Add compact recent healing facts alongside recent damage and defeated names.
- Add a bonus-action conflict hint when off-hand attacks compete with Second Wind or other survival tools.

## 2026-07-02 - Current Codex Skeletons vs External Fighter Hero

### Setup

- Server: local `server.event_server` on `127.0.0.1:8765`.
- Arena: `/simulation/start-codex-monsters?character_class=fighter`.
- Codex control path: current-thread Codex takeover of the monster faction through `ai.codex_tools`.
- Opponent side: external behavior-tree AI controlling the Hero.
- Result: Codex skeleton victory in round 4.
- Final monster state:
  - Skeleton Warrior: `19/31 HP`, position `(3, 7)`.
  - Skeleton Archer: `24/24 HP`, position `(12, 7)`.
  - Skeleton Warlock: `17/17 HP`, position `(7, 7)`.

### Play Summary

This run required a new skeleton-side setup because the existing human arena starts with a human/Codex-capable Hero and external AI monsters, while the older PvP route leaves the Hero as a human-controlled actor. I added `/simulation/start-codex-monsters`, which starts the Hero under the external AI session and leaves the monster faction claimable by current Codex.

The Hero AI opened by ending its first turn with no visible enemy. Codex attached to the skeleton faction and took the Skeleton Warrior's turn. Unlike the hero-side opening, the monster-side subjective state already knew about the closed door at `(7, 7)`, but `useful_moves` still did not label doorward moves explicitly. The Warrior moved to the door, opened it, revealed the Hero at `(2, 7)`, stepped forward to `(6, 7)`, and ended.

The Archer then used `Mark Target` on the Hero and fired a shortbow, missing the first shot. The Warlock used `Necrotic Bless` on the Warrior, moved toward the doorway, and later found Eldritch Blast lines by repositioning. The Warrior pinned the Hero in melee while Archer and Warlock added ranged pressure. The final kill came from the Archer's shortbow in round 4 after the Warrior crit the Hero down to `8 HP`.

### What Worked

- Current-thread Codex can now play the skeleton side against an automated Hero.
- One Codex session cleanly controlled all three skeletons with per-turn active actor switching.
- The watcher was efficient for multi-entity side control: it woke on Warrior, Archer, and Warlock turns and preserved the shared faction view.
- Door opening, body blocking, Mark Target, Necrotic Bless, Eldritch Blast, melee attacks, ranged attacks, misses, crits, deaths, and encounter end all worked through the same epoch command path.
- The compact damage/death digest made the final state easy to read: Hero death surfaced in `recent_defeated_names`.

### Main Friction

- There was no skeleton-side self-play setup before this run. The new route fixes that for local/controller development.
- Known closed doors are visible in `known_objects`, but `useful_moves` does not label moves that progress toward or adjacent to the door.
- `Mark Target` was initially classified as `support_actions` even though it is an enemy-targeting hostile setup ability.
- Warlock repeatedly had a visible enemy but no hostile row until it moved to specific cells. The summary warned that no hostile rows existed, but it did not explain whether line of sight, range, cover, ally blocking, or spell geometry was responsible.
- Area spell previews flooded the Warlock surface with rows that hit only allies and no enemies.
- Ranged attacks into an allied melee were legal and useful, but the surface did not explain any risk, cover, or disadvantage policy.

### Implemented Improvements

Added a non-disruptive skeleton-side self-play route.

- `/simulation/start-codex-monsters` creates the standard arena with the Hero controlled by an external AI subprocess.
- The monster faction remains available for current-Codex takeover.
- The existing human/NeuroClient `/simulation/start-human` flow is unchanged.
- A focused setup regression verifies Hero `external_ai`, monsters `codex`, one `AI Hero` session, one spawned external process, and three monster rows in the payload.

Improved compact turn classification for monster-side play.

- `Mark Target`, `hex`, and `curse` style entity rows are now treated as hostile rows when they target living enemies.
- Position-targeted area rows are hidden when they include no visible enemies, even if they would hit allies or self.
- Regression coverage models the Archer's `Mark Target` row and the Warlock's no-enemy Thunderwave noise.

### Follow-Up UX Targets

- Add `doorward_moves` or `objectward_moves` for known closed doors and other tactical objects.
- Add a no-hostile-row explanation layer using available movement, line of sight, range, and blocker facts.
- Add warnings for ranged attacks made while an ally is adjacent to the target if the local rules impose any cover/disadvantage/shot-risk policy.
- Add compact miss/outcome summaries, not only damage and death summaries.
- Add active condition summaries for important setup effects such as Marked, Necrotic Bless, Shield, concentration, or invisibility.

## 2026-07-02 - Current Codex Skeletons vs External Sorcerer Hero

### Setup

- Server: local `server.event_server` on `127.0.0.1:8765`.
- Arena: `/simulation/start-codex-monsters?character_class=sorcerer`.
- Codex control path: current-thread Codex takeover of the monster faction through `ai.codex_tools`.
- Opponent side: external behavior-tree AI controlling the Hero.
- Result: Codex skeleton victory in round 3.
- Final monster state:
  - Skeleton Warrior: `14/31 HP`, position `(3, 7)`.
  - Skeleton Archer: `24/24 HP`, position `(8, 7)`.
  - Skeleton Warlock: `17/17 HP`, position `(6, 7)`.

### Play Summary

This was the first run after explicitly requiring the current Codex thread to use the same controller surface as an agent would use. Codex attached to the monster faction, consumed subjective turn briefs, executed epoch row ids, and played the full encounter without using objective state.

The Archer opened the door from `(7, 7)`, used `Mark Target`, and attacked with Shortbow. The Warlock moved into line of sight and used `Eldritch Blast` instead of unsafe `Burning Hands` rows. The Warrior had to solve the doorway approach with Dash plus Jump before reaching adjacency at `(3, 7)`.

The Sorcerer Hero repeatedly used `Fire Bolt`; one hit dealt `17` fire damage to the Warrior, then the Hero later missed by one against AC `15`. The Hero's temporary Shield AC change was visible in the logs and then removed at turn start. The skeleton side won after Archer, Warlock, and Warrior combined ranged and melee pressure.

### What Worked

- Current-thread Codex successfully played against the base external AI without being a spawned controller subprocess.
- The command lifecycle was event-first: commands returned small acks, and follow-up epochs arrived with new observation cursors.
- The turn brief carried enough combat history to understand hits, misses, crits, Shield removal, damage types, and current HP totals.
- `Mark Target` now appeared as a hostile attack/setup row, not support.
- Area rows now estimated visible enemies, allies, and self inclusion. The Warlock's `Burning Hands` rows correctly showed `risk: allies`, so Codex chose `Eldritch Blast`.
- Encounter end flowed cleanly through an accepted command with `encounter_ended: true` and no follow-up epoch.

### Main Friction

- `execute` did not accept `--json`, unlike `actions` and `turn`.
- Jump rows were legal after Dash, but `turn.useful_moves` ignored them because the compact movement summarizer only accepted `Move` rows.
- When a hostile row was unavailable, the warning still did not explain whether range, line of sight, ally blocking, or action economy was the cause.
- Door/object progress still depends on reading raw coordinates; there is no first-class `doorward_moves` group.
- `Necrotic Bless` can appear as support even when targeting an enemy. The row may be legally targetable, but the compact surface needs a stronger ally/enemy usefulness policy before an automated agent should trust it.
- The brief says `meaningful_commands_remaining` when only movement remains after a ranged/spell attack. That is technically true, but the operator still needs a "no useful follow-up" summary.

### Implemented Improvements

- `execute --json` is now accepted for CLI consistency; output remains JSON.
- Movement summaries now treat `Jump` as movement, not as an ignored position action.
- Jump movement rows fall back to target `distance` when no explicit `path_cost` is supplied.
- Jump rows are labeled with notes such as `jump closing`, while existing Move notes remain stable.
- Focused regressions cover the `execute --json` flag and the Dash/Jump closing-move shape from this run.

### Follow-Up UX Targets

- Add `doorward_moves` or `objectward_moves` for known closed doors and other tactical objects.
- Add a no-hostile-row explanation layer using line of sight, range, blocker, and action economy facts.
- Add compact miss summaries alongside recent damage and defeated names.
- Add active condition summaries for Shield, Marked, Necrotic Bless, concentration, invisibility, and other tactical conditions.
- Add a "no useful follow-up" or "only movement remains" conclusion when all hostile/support rows are exhausted.

## 2026-07-02 - Current Codex Skeletons vs External Barbarian Hero

### Setup

- Server: local `server.event_server` on `127.0.0.1:8765`.
- Arena: `/simulation/start-codex-monsters?character_class=barbarian`.
- Codex control path: current-thread Codex takeover of the monster faction through `ai.codex_tools`.
- Opponent side: external behavior-tree AI controlling the Barbarian Hero.
- Result: Codex skeleton victory in round 4.
- Final monster state:
  - Skeleton Warrior: `7/31 HP`, position `(3, 7)`.
  - Skeleton Archer: `24/24 HP`, position `(14, 7)`.
  - Skeleton Warlock: `17/17 HP`, position `(12, 7)`.

### Play Summary

The Archer opened the closed door at `(7, 7)`, used `Mark Target`, hit the Barbarian with Shortbow, and then retreated to clear the corridor. The Warrior used Move plus Dash to pin the Hero at `(3, 7)`. The Warlock first had no hostile row from `(12, 9)`, moved to `(6, 7)` to gain line of sight, missed once, then later retreated to `(12, 7)` while preserving a long Eldritch Blast line.

The Barbarian hit the Warrior twice, reducing it from `31` to `7`, but the Warrior held the pin long enough for the Archer and Warlock to kite safely. Force and piercing damage did the real work: the Warrior's longsword only dealt `1` damage on one hit, which strongly suggests Barbarian resistance or a similar defensive condition that the compact turn surface does not yet summarize.

The final kill came from the Archer's 60-foot Shortbow shot while the Warlock and Warrior maintained the firing lane.

### What Worked

- Current-thread Codex controlled the full monster side again without spawning a Codex subprocess.
- The `execute --json` fix worked live; action execution commands were consistent with the other JSON-emitting tools.
- Retreat moves were tactically useful: Archer retreated to `(14, 7)` and Warlock retreated to `(12, 7)` while keeping line of sight.
- The Jump/Move fix held up during the Warrior's Dash turn. Adjacent candidates stayed visible after Dash.
- Area previews again kept Warlock from friendly-firing `Burning Hands` into the Warrior.
- The event stream carried enough information to follow the front-line pin, misses, crits, HP changes, and final death.

### Main Friction

- `attach --json` was still missing even though `attach` emits JSON. This immediately slowed the opening workflow.
- Known closed door facts were available, but opening play still required manually connecting `known_objects` to raw movement coordinates.
- No-hostile-row warnings still do not explain line of sight or range blockers. This appeared when Warlock at `(12, 9)` could see the Hero but had no Eldritch row until moving.
- The compact surface did not explain why the Barbarian reduced slashing damage so heavily.
- Misses remain visible in recent combat logs but not in a compact `recent_misses` or outcome digest.
- `Necrotic Bless` targeting the Hero still appears as a support row. It may be legally targetable, but the usefulness policy is unsafe for automation.

### Implemented Improvements

- Added `attach --json` for command-surface consistency.
- Added `objectward_moves` to turn summaries.
- `objectward_moves` combines known tactical objects with movement rows, prioritizing known closed doors before other usable or pickable objects.
- Closed-door movement rows now show facts such as object name, object UUID, object position, distance after movement, path cost, and notes like `at closed door`.
- Focused regressions cover the skeleton Archer opening shape: known closed door at `(7, 7)` and no visible enemies.

### Follow-Up UX Targets

- Add no-hostile-row explanations that distinguish range, line of sight, blockers, action economy, and target visibility.
- Add compact attack outcome summaries for misses, crits, and hit-with-zero/low-damage cases.
- Add active condition/resistance summaries for rage, Shield, Marked, Necrotic Bless, concentration, invisibility, and similar state.
- Add a target usefulness policy for support rows so hostile targets do not appear in buff-like recommendations without a warning.
- Add line-preservation hints for retreat/kiting moves so agents can prefer safe squares that keep ranged/spell attacks available.

## 2026-07-02 - Current Codex Barbarian Hero vs External Skeletons

### Setup

- Server: local `server.event_server` on `127.0.0.1:8765`.
- Arena: `/simulation/start-human?character_class=barbarian`.
- Codex control path: current-thread Codex takeover of the hero faction through `ai.codex_tools`.
- Opponent side: external behavior-tree AI controlling the three skeletons.
- Result: Codex Barbarian victory in round 3.
- Final hero state:
  - Hero: `44/50 HP`, position `(11, 8)`.

### Play Summary

The first turn exposed the hero-side exploration problem. Before the door was known, `objectward_moves` correctly surfaced visible potions and the trap lever, but it had no reason to prefer the center route. Codex manually moved to `(6, 7)`, which revealed the closed door at `(7, 7)`. Once the door was known, `objectward_moves` immediately became useful and surfaced closed-door adjacency rows.

Codex opened the door, revealed all three skeletons, used `Frenzy`, moved to `(10, 7)`, dashed, and ended adjacent to the Warlock and Archer at `(11, 8)`. The skeletons hit the Barbarian, but Rage/Frenzy reduced the incoming damage heavily.

On round 2, Codex used `Reckless Attack`, killed the Warlock with Attack plus Extra Attack, then killed the Archer with `Frenzied Strike`. On round 3, Codex used `Reckless Attack` again and killed the Warrior with Attack, Extra Attack, and `Frenzied Strike`.

### What Worked

- Hero-side takeover through the same Codex tool surface worked cleanly.
- `attach --json` worked live.
- `objectward_moves` became useful as soon as the door entered subjective knowledge.
- Action economy sequencing was readable: Attack created Extra Attack, then Frenzied Strike remained as the bonus-action finisher.
- The target ordering was useful: Warlock was prioritized first, then Archer, then Warrior.
- `recent_defeated_names` and `recent_damage` made the Warlock and Archer kills easy to confirm.

### Main Friction

- With no visible enemies and no known door, movement still needs an exploration/frontier surface. `useful_moves` is only coordinate soup in that state.
- Frenzy/Rage/Reckless state is inferred from resources, interactions, and combat logs rather than an active condition/status summary.
- Rage resistance is visible only indirectly through low or zero damage facts. The surface should say why damage was reduced or negated.
- Misses, crits, and zero-damage hits were visible in raw combat logs but not in a compact outcome digest.
- Several item rows still report `free`, which keeps generating a generic warning.

### Implemented Improvements

- Added `recent_attack_outcomes` to turn summaries.
- The digest extracts visible attack logs, including attacker, target, weapon, outcome, success, total damage, and compact text.
- This makes misses, crits, and hit-for-zero cases first-class alongside `recent_damage`.
- A focused regression models the Barbarian run shape: a Warrior miss, a Warrior hit for `0`, and a Hero crit.

### Follow-Up UX Targets

- Add an exploration/frontier movement group for no-enemy/no-known-door openers.
- Add active condition summaries for Rage, Frenzy, Reckless Attack, Dashing, Shield, Marked, concentration, and invisibility.
- Add resistance/mitigation explanations where logs expose pre/post-damage or modifier data.
- Split item/action warnings so legitimately free environmental interactions do not obscure suspicious free consumables.

## 2026-07-02 - Dev Pass: Actor Status And Economy Surface

### Trigger

The completed Barbarian run proved that the Codex operator can win through the new current-thread takeover surface, but it also exposed a state-reading gap. During the fight, Rage/Frenzy/Reckless Attack materially explained the best action sequence and incoming damage, yet the `turn` surface forced the operator to infer those statuses from actions, resources, and combat logs.

### Implemented Improvements

- `BriefEntity` now preserves known active `conditions` from the subjective observation layer.
- `TurnSummaryResult` now includes `actor_status`, with HP, position, active conditions, bloodied state, death state, and compact condition notes.
- `TurnSummaryResult` now includes `economy_summary`, a typed digest of actions, bonus actions, reactions, movement, extra attacks, resources, spell slots, item charges, gates, and short economy notes.
- Common live-run statuses now receive compact notes, including `Raging`, `Frenzied`, `Reckless Attacking`, `Dashing`, `Dodging`, `Disengaging`, `Hidden`, `Invisible`, `Concentrating`, `Prone`, `Grappled`, `Restrained`, `Poisoned`, and severe control conditions.

### Verification

- `uv run pytest tests/manual/test_30_codex_takeover_tools.py -q`
- `uv run pyright ai/codex_tools tests/manual/test_30_codex_takeover_tools.py`

### Next Game Questions

- Does the actor-status summary make Barbarian and Fighter resource turns faster to play?
- Does the economy summary reduce redundant `actions` calls during variable-length turns?
- Do we need the same status digest for visible enemies and allies, or is carrying `conditions` on each `BriefEntity` enough for now?

## 2026-07-02 - Current Codex Fighter Hero vs External Skeletons

### Setup

- Server: local `server.event_server` on `127.0.0.1:8765`.
- Arena: `/simulation/start-human?character_class=fighter`.
- Codex control path: current-thread Codex takeover of the hero faction through `ai.codex_tools attach`.
- Opponent side: external behavior-tree AI controlling the three skeletons.
- Result: Codex Fighter victory in round 5.
- Final hero state:
  - Hero: `39/44 HP`, position `(11, 8)`, active `Haste`.
- Defeated enemies:
  - Skeleton Warlock: killed round 1 by offhand dagger after Action Surge longbow pressure.
  - Skeleton Archer: killed round 3 by shortsword.
  - Skeleton Warrior: killed round 5 by shortsword.

### Play Summary

The fighter opened with `Drink Haste Potion`, moved to `(6, 7)`, opened the door, revealed all three skeletons, and focused the Skeleton Warlock with longbow attacks. Several arrows missed, but `Action Surge` exposed another attack sequence and reduced the Warlock to low HP. `Drink Greater Invisibility Potion` plus movement to `(11, 8)` exposed the offhand dagger row and killed the Warlock.

Rounds 2 and 3 became a melee cleanup. The Archer and Warrior engaged near the doorway. The Fighter killed the Archer first, then spent a full hasted round into the Warrior. The Warrior survived at `3 HP`, attacked once on its turn, missed AC 18, then died to the first shortsword attack on round 5.

### What Worked

- Current-thread Codex controlled the hero through the runtime takeover surface; no Codex subprocess was needed.
- `turn` exposed Haste-expanded action economy, Extra Attack rows, Action Surge resources, and offhand dagger rows well enough to sequence a long variable-length turn.
- The compact economy summary reduced some raw `actions` calls once combat was underway.
- `watch` returned the next hero epoch after the external Warrior turn.
- The enemy turn was fully present in the subjective combat logs: Warrior attacked once, missed, and ended.

### Main Friction

- The first live `turn` payload was huge enough to become scrollback noise: one raw JSON response printed `1675` terminal lines before local filtering.
- This run still needed many tool interactions because action results did not yet include the next compact turn surface. The reconstructed count is about `44` tool calls including setup, one failed `end-turn --json`, watches, executes, and compact verification probes.
- `end-turn --json` failed even though the command always emits JSON.
- `Haste`, `Action Surge Feature`, `Second Wind Feature`, `Extra Attack`, `ExtraAttacksGranted`, `Improved Critical`, `Fighting Style: Two-Weapon Fighting`, and `HasAttacked` appeared as raw conditions without notes.
- The warning `Visible living enemies exist, but no affordable hostile rows were found` appeared after all attacks and bonus action were spent, but did not explain that action economy was exhausted.
- The final killed Warrior appeared in `recent_defeated_names`, but not in `dead_enemies` immediately after the finishing action.
- Damage sub-entries still report `source_name: terrain` for weapon damage, even when the parent attack clearly identifies the weapon attacker.
- Greater Invisibility disappeared from actor status after attacking, and the compact surface did not explain whether that was an intended ruleset consequence or a bug.

### Measurement

- Retrospective complete-game tool interactions: approximately `44`.
- Largest observed raw turn response before this pass: `1675` terminal lines.
- Final postgame `turn` summary after this pass: `23018` JSON characters, roughly `5755` tokens.
- Final postgame raw recent-combat-log payload: `17433` JSON characters, roughly `4359` tokens.
- Final postgame summary included all three dead enemies after recent death facts were merged into `dead_enemies`.
- Per-sub-action flow before this pass: typically `execute -> turn -> execute`.
- Desired next-run flow after this pass: `execute` returns `follow_up_turn`, so most same-turn sub-actions can be `execute -> execute`.
- New metric fields added for future runs:
  - `payload_metrics.summary_characters`;
  - `payload_metrics.estimated_summary_tokens`;
  - `payload_metrics.recent_combat_log_characters`;
  - `payload_metrics.action_choice_count`;
  - `payload_metrics.raw_action_row_count`;
  - `payload_metrics.tool_http_request_count`.

### Implemented Improvements

- `end-turn --json` is now accepted for command-surface consistency.
- `execute` now defaults to returning `follow_up_turn` when the command is accepted and the actor still has a fresh subjective turn surface.
- `execute --no-follow-up` remains available for low-payload automation.
- `ExecuteResult` records `tool_http_request_count`.
- `TurnSummaryResult` now records `payload_metrics` so every turn response reports approximate character/token pressure and row counts.
- Actor condition notes now cover the Fighter/Haste markers from this run.
- Recent death logs now produce remembered `dead_enemies` facts when the entity fact has not refreshed yet.
- No-hostile-row warnings now include action-economy reasons when actions, bonus actions, or extra attacks are spent.

### Follow-Up UX Targets

- Replace the extra post-action snapshot used by `follow_up_turn` with streamed command-result plus decision-epoch materialization.
- Add an enemy-turn digest so the raw combat log does not dominate the turn payload.
- Add a compact cause/effect explanation for invisibility loss or persistence.
- Fix weapon damage sub-entry source names currently reported as `terrain`.
- Add exploration/frontier movement for the no-visible-enemy opener before the door is known.

## 2026-07-02 - Current Codex Skeletons vs External Sorcerer Hero

### Setup

- Server: local `server.event_server` on `127.0.0.1:8765`.
- Arena: `/simulation/start-codex-monsters?character_class=sorcerer`.
- Codex control path: current-thread Codex takeover of the monster faction through `ai.codex_tools attach`.
- Opponent side: external behavior-tree AI controlling the Sorcerer Hero.
- Result: Codex skeleton victory in round 4.
- Final monster state:
  - Skeleton Warrior: `1/31 HP`, position `(1, 7)`.
  - Skeleton Archer: `24/24 HP`, position `(8, 7)`.
  - Skeleton Warlock: `17/17 HP`, position `(12, 6)`.
- Final hero state:
  - Hero: defeated at `-2/37 HP`, position `(2, 7)`.

### Play Summary

The Sorcerer Hero opened under external AI control and did not reveal or engage the skeletons before the monster side took over. The Skeleton Warrior used the known closed-door objective, moved to `(8, 6)`, opened the door, dashed, and eventually pinned the Hero at `(1, 7)`. The action-result follow-up surface made this variable-length opener much smoother: move results immediately exposed Open Door, Dash exposed further movement, and later movement exposed adjacent squares.

The Archer marked the Hero and shot from the corridor. A first retreat to `(14, 1)` preserved distance but lost line of fire; the next turn had to spend movement returning to `(8, 7)` to regain a Shortbow row. This proved that retreat/kiting candidates need a "preserves current attack line" or "will lose attack rows" hint.

The Warlock initially had no hostile row at `(12, 9)`, moved to `(6, 7)`, gained Eldritch Blast, then later retreated to `(12, 6)`. That retreat did preserve Eldritch Blast at 50 ft, but the interface did not predict it beforehand. The Warlock and Archer reduced the Hero to `1 HP`; the Warrior survived at `1 HP` and landed the final Longsword hit.

The external Sorcerer mostly used Fire Bolt and Shield rather than high-impact leveled spells. It hit the Warrior for `20` with Fire Bolt once, but did not behave like a strong spellcaster.

### What Worked

- The current-thread Codex monster-side control path worked for the whole game.
- `execute` returning `follow_up_turn` materially reduced same-turn back-and-forth.
- `target_ac` surfaced Shield correctly: Hero AC rose to `20`, then returned to `15` after Shield expired.
- `recent_attack_outcomes` was enough to understand misses, hits, and the final kill without opening raw logs.
- `dead_enemies` included the final defeated Hero immediately after the finishing action.
- `objectward_moves` handled the opening door plan for the Warrior.

### Main Friction

- `watch` wakes on the next active Codex actor but returns only `brief`, not the compact `turn` surface, forcing a separate `turn` call after every watch.
- Raw recent combat logs dominated payload pressure. Typical turn summaries were `27k-34k` JSON characters, with `12k-22k` characters coming from raw logs.
- Final postgame summary was `20448` JSON characters, roughly `5112` tokens; raw recent combat logs were `15178` characters, roughly `3795` tokens.
- Full-game tool interactions were approximately `50`, including setup, watches, turn pulls, commands, and one malformed local pipe that still executed the move.
- No-hostile-row warnings still cite "no extra attack resource" even when the real blocker is range, line of sight, or spent main action.
- Retreat moves do not say whether they preserve line of fire or spell rows. This caused the Archer to lose a shot lane after moving to `(14, 1)`.
- Damage summaries still report `source_name: terrain`, even when attack outcomes correctly identify the attacker.
- Support rows still include questionable enemy-targeted `Necrotic Bless` as a neutral `entity` support row.
- The compact condition notes do not yet explain `Shield`, `Marked`, `Mark Cooldown`, `Draconic Resilience`, or `Sorcery Points Feature`.

### Measurement

- Approximate complete-game tool interactions: `50`.
- Largest observed summary in this run: about `34475` JSON characters, roughly `8619` tokens.
- Largest observed raw recent-combat-log segment in this run: about `22272` JSON characters, roughly `5568` tokens.
- Final action result with `follow_up_turn`: `20448` summary characters, `15178` raw-log characters.
- `execute` with follow-up required `3` HTTP requests per action in the current implementation: action snapshot, command post, follow-up snapshot.

### Implemented Improvements To Build Next

- Add compact combat digests to `TurnSummaryResult`.
- Make raw recent combat logs optional for `turn`, `execute` follow-up turns, and ideally `watch`.
- Keep raw logs available for debugging, but default the operator surface toward compact digests.
- Add focused tests proving payload metrics drop when raw logs are excluded.

### Implemented Improvement

- Added `combat_digest` to `TurnSummaryResult`, with short plain-text recent combat lines, flattened event counts, attack counts, damage-event counts, defeated names, and a `raw_logs_included` flag.
- `turn` now omits raw recent combat logs by default and accepts `--include-raw-logs` for debugging.
- `execute` follow-up turns omit raw logs by default and accept `--include-raw-logs`.
- `watch` now includes a compact `turn` payload when it wakes on an active Codex actor, and omits raw logs by default.
- Damage summaries inherit the parent attack/spell source when nested damage entries report `source_name: terrain`, so the Codex-facing digest names the actual attacker.
- Live postgame measurement on this run:
  - compact default `turn`: `5693` JSON characters, roughly `1424` tokens, `0` raw log rows;
  - `turn --include-raw-logs`: `20979` JSON characters, roughly `5245` tokens, `10` raw log rows;
  - raw-log omission saved about `72%` of final turn-summary characters.

### Follow-Up UX Targets

- Add line-preservation hints for move/retreat rows.
- Add blocker-aware no-hostile-row explanations: range, line of sight, target visibility, action economy.
- Fix damage source names or patch the Codex digest to inherit source from parent attack logs until the engine log source is corrected.
- Add condition notes for `Shield`, `Marked`, `Mark Cooldown`, `Draconic Resilience`, and `Sorcery Points Feature`.
- Improve external spellcaster policy: the sorcerer should use leveled spells and value AoE or Magic Missile instead of mostly Fire Bolt.

## 2026-07-02 - Current Codex Sorcerer Hero Fast Clear

### Setup

- Server: local `server.event_server` on `127.0.0.1:8765`.
- Arena: `/simulation/start-human?character_class=sorcerer`.
- Codex control path: current-thread Codex takeover of the hero faction through `ai.codex_tools`.
- Opponent side: external behavior-tree AI controlling the three skeletons.
- Result: Codex Sorcerer victory in round 1.
- Final hero state:
  - Hero: `37/37 HP`, position `(6, 7)`.
- Defeated enemies:
  - Skeleton Archer: defeated by Quickened Fireball.
  - Skeleton Warrior: defeated by Quickened Fireball.
  - Skeleton Warlock: defeated by Quickened Fireball.

### Play Summary

The opening turn started with no visible enemies and no known door. The compact surface still exposed potions and the trap lever through `objectward_moves`, but it did not yet have an exploration-specific movement group. Codex used the known manual opener and moved from `(2, 7)` to `(6, 7)`, which revealed the closed door at `(7, 7)`.

The move result returned a follow-up turn with `Open Door` immediately available. Opening the door revealed all three skeletons clustered around the far room. The compact area rows were good enough to choose a clean `Fireball` centered at `(11, 7)`: the row showed all three skeletons in `enemy_names`, no allies, and `self_included=false`.

The first Fireball damaged all three skeletons but left them alive. The follow-up turn showed no affordable hostile rows because the main action was spent, while `Quickened Spell` remained available. Codex activated Quickened Spell, then used the last level-3 Fireball as a bonus action. The final follow-up turn had no living enemies, listed all three skeletons in `dead_enemies`, and surfaced all three names in `recent_defeated_names`.

### What Worked

- The current-thread Codex hero-side control path completed the whole encounter without objective `/state` or debug `/available-actions`.
- Action responses contained enough follow-up information for the next sub-action:
  - move exposed the door;
  - open door exposed area and spell rows;
  - Fireball exposed Quickened Spell as the next meaningful command;
  - Quickened Spell exposed bonus-action spell rows;
  - the final spell exposed encounter completion facts.
- Compact combat digest and damage summaries stayed small because raw logs were omitted by default.
- Area previews were tactically useful: Fireball rows exposed affected enemy names and ally/self risk directly.
- Quickened Spell resource loss was visible in the economy summary: sorcery points dropped from `5` to `3`.
- Death continuity worked: final `dead_enemies`, `recent_defeated_names`, and combat digest all agreed.

### Main Friction

- The no-enemy opener still needed human memory. Before the door was known, the tool had no `frontier_moves` or "advance along corridor" group.
- The first door-open spell-choice payload was still large because the epoch had `478` legal action rows.
- The Quickened turn payload was also large at `27019` summary characters because area and spell variants still produce many legal choices.
- Actor condition notes did not explain `MetamagicActive`, `Draconic Resilience`, or `Sorcery Points Feature`.
- Item/object rows still report `free`, producing the generic warning even when the current tactical line does not need items.
- `execute` with follow-up still uses `3` HTTP requests per accepted command: action snapshot, command post, follow-up snapshot.

### Measurement

- Complete-game gameplay tool interactions: `6`.
- Largest full CLI response: `32069` JSON characters on the open-door follow-up.
- Largest turn summary: `28515` JSON characters, roughly `7129` tokens.
- Largest raw recent-combat-log segment: `2` JSON characters because raw logs were omitted.
- Largest normalized action row count: `478`.
- Final compact turn summary: `5255` JSON characters, roughly `1314` tokens.
- Final raw recent-combat-log segment: `2` JSON characters.
- Final action row count: `0`, because the encounter was complete.

### Implemented Improvement

Added `frontier_moves` to `TurnSummaryResult`.

- Frontier moves appear when there are no visible living enemies and no known closed door.
- They reuse `TurnMoveSummary` and carry notes such as `frontier` or `jump frontier`.
- The scorer prefers non-hazardous, straight/cardinal exploration that uses meaningful movement, while keeping side-object movement separate in `objectward_moves`.
- A focused regression models the exact Sorcerer opener: no enemies, no known door, two potions and a trap lever known, and the corridor move to `(6, 7)` surfaces before side-object movement.

### Follow-Up UX Targets

- Add line-preservation hints for move/retreat rows.
- Add blocker-aware no-hostile-row explanations: range, line of sight, target visibility, action economy.
- Add condition notes for `MetamagicActive`, `Draconic Resilience`, `Sorcery Points Feature`, `Shield`, `Marked`, and `Mark Cooldown`.
- Reduce large spellcaster turn payloads by grouping or capping redundant area/slot/scroll variants without hiding legal options.
- Replace post-action follow-up snapshots with streamed command-result plus decision-epoch materialization.

## 2026-07-02 - Current Codex Barbarian Hero Frontier Validation

### Setup

- Server: local `server.event_server` on `127.0.0.1:8765`.
- Arena: `/simulation/start-human?character_class=barbarian`.
- Codex control path: current-thread Codex takeover of the hero faction through `ai.codex_tools`.
- Opponent side: external behavior-tree AI controlling the three skeletons.
- Result: Codex Barbarian victory in round 4.
- Final hero state:
  - Hero: `40/50 HP`, position `(11, 8)`, active Rage/Frenzy.
- Defeated enemies:
  - Skeleton Warlock: killed by Greataxe Attack plus Extra Attack.
  - Skeleton Archer: killed by Greataxe Attack.
  - Skeleton Warrior: killed by Greataxe Extra Attack after one missed finishing swing.

### Play Summary

This run started immediately after adding `frontier_moves`. The first attached turn did expose the new group, but the ordering was not good enough: jump rows toward the southern side-object area appeared above the obvious corridor move to `(6, 7)`. Codex still used the correct corridor move, but this proved the first implementation was only partially integrated.

Codex used `Frenzy`, moved to `(6, 7)`, opened the door, moved to `(10, 7)`, dashed, and moved to `(11, 8)` to engage the Warlock and Archer. The first monster turn was easy to read from the compact digest: Warrior and Archer missed, Warlock hit for `2` force damage.

Round 2 used `Reckless Attack`, then Greataxe Attack plus Extra Attack killed the Warlock. `Frenzied Strike` hit the Archer for `14`, leaving it at `10 HP`. Enemy attacks on the following turn showed Rage mitigation clearly: `5` slashing became `2`, and `8` piercing became `4`.

Round 3 killed the Archer with the main attack, hit the Warrior with Extra Attack, and hit again with Frenzied Strike. The Warrior survived at `1 HP`, hit once for `2` mitigated damage, and then died on round 4 after the first Greataxe swing missed and Extra Attack hit.

### What Worked

- Current-thread Codex played a full Barbarian game through the hot takeover and epoch-command path.
- The compact combat digest was sufficient for enemy turns; no raw combat logs were needed.
- Status notes for `Raging`, `Frenzied`, and `Reckless Attacking` were useful and accurate.
- Damage and attack-outcome digests made misses, hits, deaths, and Rage mitigation readable.
- Follow-up turns after actions were enough to continue chaining Attack, Extra Attack, and Frenzied Strike without raw `actions`.
- Death continuity held for all three skeletons in the final compact turn.

### Main Friction

- `frontier_moves` existed but initially sorted a bad jump-to-side-room row above the corridor move. That made the previous improvement feel unfinished.
- `watch --json` was missing even though the watch command always emits JSON and every other operator command accepts the consistency flag.
- `meaningful_commands_remaining` remains too literal: after all attacks are spent, it stays true because movement remains even when no useful tactical follow-up exists.
- The no-hostile-row warning is still too shallow. At `(10, 7)` it mentioned spent bonus action, while the real problem was no melee target in reach and no movement remaining before Dash.
- Large melee turns still produce around `250` legal rows even though the compact surface only needs a handful of attack and movement candidates.
- Item/object rows still report `free`, preserving the generic warning across the whole game.

### Measurement

- Successful saved operator responses: `23`.
- Complete-game operator interactions including the failed `watch --json`: `24`.
- Total saved response characters: `389921`.
- Largest full CLI response: `26167` JSON characters.
- Largest turn summary: `21345` JSON characters, roughly `5337` tokens.
- Largest raw recent-combat-log segment: `2` JSON characters because raw logs were omitted.
- Largest normalized action row count: `253`.
- Final compact turn summary: `5542` JSON characters, roughly `1386` tokens.
- Final action row count: `0`, because the encounter was complete.

### Implemented Improvement

Tightened the frontier and CLI surfaces based on the live run.

- `frontier_moves` now demotes jump rows behind equivalent move rows.
- Frontier scoring now prefers straight/cardinal exploration, then distance away from known side-object clusters, before raw movement length.
- The regression test includes the exact bad row shape from the live run: a jump to `(2, 14)` must not outrank the corridor move to `(6, 7)`.
- `watch --json` is now accepted for command-surface consistency.

### Follow-Up UX Targets

- Add "useful command remains" separate from "legal command remains" so leftover movement does not imply there is a good follow-up.
- Add blocker-aware no-hostile-row explanations: range, line of sight, target visibility, movement remaining, and action economy.
- Reduce high-row-count melee turns by grouping repeated movement rows more aggressively.
- Split item/action warnings so legitimate free environmental interactions do not obscure suspicious free consumables.
- Add line-preservation hints for move and retreat rows.

## 2026-07-02 - Multi-Target Spell Affordance Fix

### Trigger

During the current skeleton-side run, Codex cast `Necrotic Bless` on only the Skeleton Warrior and did not surface the fact that the spell can affect up to four creatures. The same problem was suspected for `Magic Missile`, where the spell can split darts across multiple targets.

### Finding

The engine spell/action layer already supported the rule correctly.

- `Magic Missile` is `MULTI_ENTITY`, has `allow_same_target=True`, and fills unspecified darts onto the primary target.
- `Necrotic Bless` is `MULTI_ENTITY`, has `allow_same_target=False`, and accepts up to four unique selected creatures.
- The command endpoint already accepted `extra_target_uuids`.

The broken part was the Codex-facing affordance reduction. Decision epochs flattened each action into one row per primary target, but the row no longer carried the full legal target option list or the multi-target metadata. The Codex client then always sent `extra_target_uuids=None`, so the operator surface made multi-target spells look single-target.

### Implemented Improvement

- Subjective `ActionAffordance` rows now preserve:
  - all source `target_options`;
  - `num_projectiles`;
  - `allow_same_target`.
- Codex `ActionChoice` and turn summaries now expose:
  - multi-target count;
  - repeat-target rule;
  - legal target option names;
  - suggested extra target UUIDs and names.
- `execute` now accepts explicit extra target UUIDs and forwards them to the epoch command endpoint.
- CLI `execute` now supports repeated `--extra-target <uuid>`.

### Expected UX Impact

For `Necrotic Bless`, a Warrior-primary support row can now recommend `Skeleton Archer` and `Skeleton Warlock` as extra targets instead of hiding the group-buff shape. For `Magic Missile`, rows now say how many darts exist and list other legal targets when multiple enemies are visible, so Codex can choose between focused damage and split damage intentionally.

### Tests

- `uv run pytest tests/manual/test_30_codex_takeover_tools.py -q`
- `uv run pyright ai/codex_tools ai/subjective server/event_server.py tests/manual/test_30_codex_takeover_tools.py`

### Follow-Up UX Targets

- Teach the automated policy layer to choose extra targets automatically for obvious group buffs and split-damage cases.
- Render multi-target options compactly in the dashboard/playtest notes so they do not inflate every spellcaster turn.
- Add combat-log digest handling for multi-target spell outcomes so each selected target's result remains readable without raw logs.

## 2026-07-02 - Current Codex Skeletons With Mid-Run Interface Patch

### Setup

- Server: local `server.event_server` on `127.0.0.1:8765`.
- Arena: `/simulation/start-codex-monsters?character_class=fighter`.
- Codex control path: current-thread Codex takeover of the monster faction.
- Opponent side: external fighter hero.
- Result: Codex skeleton victory in round 5.
- Final battlefield:
  - Hero defeated by Skeleton Warrior critical hit for `15` slashing.
  - Skeleton Warrior survived at `11/31 HP`.
  - Skeleton Archer survived at `24/24 HP`.
  - Skeleton Warlock survived at `17/17 HP`.

### Play Summary

The opening sequence worked well. Archer moved to the door, opened it, marked the Hero, and landed a critical Shortbow hit. Warlock moved to the doorway side and cast `Necrotic Bless`, but only on the Warrior; this exposed that the Codex surface hid multi-target spell semantics even though the engine supported them. Warrior then moved, dashed, and eventually used a short jump plus movement to tie the Hero down.

The game was paused for the multi-target affordance fix. During that pause the takeover lease expired, so the Codex session lost monster ownership and had to reclaim the monster faction. This made the next command flow noisy and proved that long patch/debug pauses need either explicit heartbeat discipline or a developer-safe long lease.

After reclaiming, Warrior stayed adjacent and absorbed the Hero's attacks while Archer repeatedly shot from the doorway. Warlock initially had no clean hostile row until it used a bonus-action jump from `(7,8)` to `(5,6)`, which immediately exposed `Eldritch Blast`. The Warlock missed several times, but later hit for `4`, setting up the final Warrior critical.

### What Worked

- The compact follow-up after Warlock jumped was excellent: it immediately exposed the new `Eldritch Blast` row, so no extra action query was needed.
- The combat digest was enough to track the story without raw logs: Hero hits on Warrior, Archer chip damage, Warlock misses, final death.
- Keeping Archer at range rather than moving into "useful" adjacent move rows was tactically correct.
- Warrior's adjacent pressure forced the Hero to spend turns attacking the tank instead of the archer or warlock.
- The final death surface was compact and readable: no living enemies, Hero in `dead_enemies`, defeated name in the digest, and encounter ended.

### Main Friction

- The running server did not have the new multi-target fields because it predated the patch. The next restarted game should validate the improved surface live.
- The takeover lease expired during the patch/debug pause and silently removed the Codex session's controlled entities until game status was inspected.
- `Jump` to `(5,8)` was advertised as affordable and useful but was rejected by the engine. The rejection payload did not include the underlying validation detail.
- `meaningful_commands_remaining` stayed true when only legal but low-value movement remained.
- Warlock had no explanation for missing hostile entity rows before moving: likely line-of-sight/geometry, but the surface did not say that.
- Area rows still rely on heuristic radius previews and do not carry authoritative affected entity lists; this made Burning Hands/Thunderwave too risky to trust.
- Raw `actions` dumps remain enormous: the largest saved raw action response was `225187` JSON characters.

### Measurement

- Saved JSON responses: `61`.
- Total saved response characters: `1513063`.
- Largest full response: `225187` JSON characters from a raw Warlock action dump.
- Largest compact turn summary: `21168` JSON characters, roughly `5292` tokens.
- Largest raw recent-combat-log segment: `2` JSON characters because raw logs were omitted.
- Largest normalized action row count: `169`.
- Final compact turn summary: `5858` JSON characters, roughly `1465` tokens.
- Final action row count: `0`, because the encounter ended.

### Implemented Improvement

The multi-target patch was integrated during this run and tested independently:

- `ActionAffordance` rows preserve all source target options and multi-target metadata.
- Codex turn summaries expose multi-target counts, repeat rules, target option names, and suggested extra target UUIDs.
- CLI `execute` supports repeated `--extra-target`.

### Follow-Up UX Targets

- Keep takeover heartbeat alive during long operator sessions, or make developer takeover leases explicit in the tool output.
- Include engine rejection detail in `COMMAND_RESULT` payloads.
- Filter or demote invalid/stale Jump rows that the engine later rejects.
- Add row-level explanations for missing hostile actions: no line of sight, out of range, target blocked, action spent, or no visible enemy.
- Add authoritative affected entity lists for AoE rows instead of relying on heuristic radius previews.
- Teach automated policy to use multi-target extra UUIDs for group buffs and split-damage spells after the server is restarted with the new fields.

## 2026-07-02 - Rejected Command Detail Fix

### Trigger

During the skeleton victory run, `Jump` to `(5,8)` was advertised as affordable but rejected. The immediate Codex tool response only said `Command was rejected by the engine` and carried an empty payload, so the operator had to inspect surrounding state rather than seeing the concrete validation reason.

### Finding

Jump validation already produces useful cancel messages such as `Path to (5, 8) is blocked`. The route-level `ActionResult` also preserves action success and message. The missing piece was the AI command wrapper:

- non-HTTP action failures were not explicitly converted into rejected command results with action detail;
- `_command_ack()` stripped rejected command payloads down to `{}`.

### Implemented Improvement

- Failed `ActionResult` responses now become `CommandResultStatus.REJECTED`.
- The command result payload preserves the engine message and a compact safe action-result subset.
- Rejected/stale/error HTTP acks now keep diagnostic payloads, while accepted command acks stay compact.
- The full observation stream still receives the detailed command result frame, followed by an `ACTION_REJECTED` decision epoch.

### Tests

- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q`
- `uv run pytest tests/manual/test_30_codex_takeover_tools.py -q`
- `uv run pyright server/event_server.py tests/manual/test_36_seamless_subjective_runtime.py`

### Follow-Up UX Targets

- Use the new rejection detail to downrank or annotate repeated failing rows in the local Codex runtime.
- Add authoritative pre-execution validation metadata to Jump rows so obviously blocked landings are not proposed as top choices.
- Show rejected-command diagnostics in the lightweight dashboard once agent-event telemetry is wired into the UI.

## 2026-07-02 - External Multi-Target Spell Awareness

### Trigger

The skeleton-side run showed that `Necrotic Bless` was being used as if it were a one-target spell. The same concern applies to `Magic Missile`: the engine can split darts across targets, but an agent that only sees a primary target row will not know that.

### Finding

The engine spell layer was already correct:

- `Necrotic Bless` is a `MULTI_ENTITY` spell with four unique selected targets and `allow_same_target=False`.
- `Bless` uses the same unique-target pattern, with the target count scaling by slot level.
- `Magic Missile` is `MULTI_ENTITY`, has `allow_same_target=True`, and fills omitted darts onto the primary target.

The gap was in the external AI reduced-state path. Decision epochs preserved the multi-target metadata, and the Codex tool surface already exposed `target_options`, `num_projectiles`, `allow_same_target`, and `suggested_extra_target_uuids`. The external reducer collapsed epoch rows back into legacy one-target rows and the behavior-tree command model had no field for `extra_target_uuids`.

### Implemented Improvement

- External action rows now preserve source target options, multi-target count, and repeat-target rules.
- External commands now carry `extra_target_uuids` through `SubjectiveRuntime.execute()`.
- The behavior tree can cast controlled-side support spells after direct offense has been considered.
- Unique-target spells fill additional same-side legal targets.
- Repeat-allowed spells such as `Magic Missile` keep focus fire by default, but split onto visible low-HP enemies when that is a plausible cleanup play.

### Tests

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q`
- `uv run pytest tests/manual/test_29_external_ai_subprocess.py -q`
- `uv run pytest tests/manual/test_30_codex_takeover_tools.py -q`
- `uv run pyright ai/external ai/external_melee_agent.py tests/manual/test_29_external_ai_subprocess.py tests/manual/test_35_subjective_external_ai.py`

### Follow-Up UX Targets

- Keep the Codex operator surface explicit: row id selects the primary target; extra targets must still be chosen intentionally.
- Add compact multi-target outcome digesting so each selected target's result is readable without raw combat logs.
- Improve value scoring for repeat-allowed projectile spells beyond the current low-HP cleanup heuristic.

## 2026-07-02 - Rejected Row Follow-Up Annotation

### Trigger

The previous game exposed a bad feedback loop: after a `Jump` command was rejected, the immediate operator surface did not automatically explain or suppress that same failed row. That makes it too easy for a hot Codex controller to retry the same bad move.

### Implemented Improvement

- `execute()` now requests a follow-up turn summary for `rejected` and `stale` command acks, not only accepted commands.
- The failed row is removed from the immediate compact candidate lists: attacks, support actions, area actions, interactions, useful moves, objectward moves, retreat moves, and frontier moves.
- The follow-up warnings now include the concrete server reason, for example `Rejected row position_actions|Jump|pos=5,8: Path to (5, 8) is blocked`.
- Raw epoch/actions access remains unchanged; this is an operator-facing downrank/filter for the next local decision surface, not a mutation of game truth.

### Tests

- `uv run pytest tests/manual/test_30_codex_takeover_tools.py -q`
- `uv run pyright ai/codex_tools tests/manual/test_30_codex_takeover_tools.py`

### Follow-Up UX Targets

- Add authoritative pre-execution validation metadata to Jump rows so obviously blocked landings are not proposed as top choices.
- Surface rejected-command telemetry in the lightweight dashboard once agent-event visualization is connected.

## 2026-07-02 - Barbarian Hero Victory With Current Interface

### Setup

Codex controlled the Barbarian Hero through runtime takeover of the `heroes` faction. The opponent side used the current external skeleton AI. This exercised a different class profile from the recent sorcerer and skeleton-side runs: high movement, Haste, Rage/Frenzy, Reckless Attack, Extra Attack, Frenzied Strike, door approach, and melee lockdown.

### Result

Victory in round 3. The Hero ended at `47 / 50` HP. Skeleton Warlock died in round 1, Skeleton Archer died in round 2, and Skeleton Warrior died at the start of round 3.

### Combat Summary

Round 1 started with no visible enemies and no known door. Codex used the free Haste potion, moved to `(6,7)`, opened the door, moved to `(11,8)`, used Reckless Attack, killed the Warlock with Attack plus Extra Attack, hit the Archer once, entered Frenzy, then repositioned to `(11,6)` to engage both Archer and Warrior.

The enemy AI dealt only small damage through Rage. On round 2, Codex refreshed Reckless Attack, killed the Archer with Attack plus Extra Attack, hit the Warrior with the remaining Haste action, and used Frenzied Strike to leave the Warrior at `5 HP`. On round 3, Codex refreshed Reckless Attack and killed the Warrior.

### What Worked

- The command follow-up loop was strong. After Haste, the follow-up showed AC, Haste condition notes, two actions, and 70 ft movement without another query.
- Moving to `(6,7)` immediately revealed the door; opening it immediately revealed all three skeletons in the follow-up surface.
- Combat digest was enough to understand enemy turns without raw logs: Warrior missed, Archer hit for 4, Rage reduced it to 2; later Warrior hit for 3 and Rage reduced it to 1.
- Extra Attack and Frenzied Strike rows surfaced clearly once their conditions existed.
- Dead enemy continuity was good for Warlock and Archer, and the final summary correctly had no living enemies.

### Friction

- Frenzy was opaque before use. The post-use status note explained it, but the pre-click row did not. This caused a wasted expectation that Frenzy might immediately attack.
- `meaningful_commands_remaining` still stayed true when only movement remained after action and bonus action were spent.
- Free item/object rows remain suspicious. Haste potion, Greater Invisibility potion, healing potion, torch use, and door use all appear as `free`; the warning is correct but too broad to distinguish expected free environmental actions from likely broken consumable costs.
- The final Warrior death degraded to a remembered fact with missing position, max HP, AC, and faction, even though the death had just been observed in melee.
- Largest compact turn surfaces were still around five to six thousand estimated tokens because raw action row counts hit 311 after door reveal.

### Measurement

- Saved JSON responses: `23`.
- Estimated server/tool HTTP requests: `65`.
- Total saved response characters: `593022`.
- Largest full response: `37841` JSON characters from the round-2 watch result.
- Largest compact turn summary: `23271` JSON characters, roughly `5817` tokens.
- Largest raw recent-combat-log segment: `2` JSON characters because raw logs were omitted.
- Largest normalized action row count: `311`.
- Final compact turn summary: `5806` JSON characters, roughly `1451` tokens.
- Final action row count: `0`, because the encounter ended.

### Implemented Improvement

The Frenzy confusion was addressed immediately:

- Barbarian self-feature rows now carry pre-execution notes.
- `Reckless Attack` explains both the advantage and incoming-advantage tradeoff.
- `Frenzy` explains that it spends rage and a bonus action, then enables Frenzied Strike while raging.
- `End Rage` explains that it drops rage/frenzy damage and resistance benefits.

### Tests

- `uv run pytest tests/manual/test_30_codex_takeover_tools.py -q`
- `uv run pyright ai/codex_tools tests/manual/test_30_codex_takeover_tools.py`

### Follow-Up UX Targets

- Fix `meaningful_commands_remaining` so movement-only leftovers do not imply useful tactical commands remain.
- Split free-row warnings into environmental free actions versus suspicious free consumables.
- Preserve full known facts for entities that die visibly at encounter end.
- Reduce payload size after door reveal by grouping redundant movement and item rows without hiding legal commands.

## 2026-07-02 - Skeleton Victory After Multi-Target Fix

### Setup

Codex controlled the full skeleton faction against the external Barbarian Hero through `/simulation/start-codex-monsters`. This run specifically tested the multi-target spell fix under the same situation that exposed the bug: Skeleton Warlock opening with `Necrotic Bless`, then coordinating Warrior/Archer/Warlock turns around the door, water geometry, line of sight, and ally blockers.

### Result

Skeleton victory in round 5. All three skeletons survived:

- Skeleton Warrior: `10 / 31` HP.
- Skeleton Archer: `24 / 24` HP.
- Skeleton Warlock: `17 / 17` HP.

The Hero was defeated by `Eldritch Blast` after being reduced to `1 HP` by the Archer.

### Combat Summary

Round 1 verified the multi-target fix immediately. The Warlock cast `Necrotic Bless` on himself with Archer and Warrior supplied through `extra_target_uuids`; the follow-up state showed all three skeletons had `Bless`. Warrior moved to the door, opened it, dashed, and advanced through the chokepoint. Archer marked the Hero, shot through the open door, and hit.

Rounds 2-4 were mostly positional pressure. The Barbarian kept attacking the Warrior, but several misses and Rage-reduced damage let the front line hold. Warlock repeatedly needed to solve line of sight by stepping or jumping out from behind allies, casting `Burning Hands` or `Eldritch Blast`, then retreating. Archer lost line after retreating behind the door, moved back to `(6,7)` to reacquire the shot, and repeatedly hit the Hero.

Round 5 ended cleanly: Hero missed Warrior at `1 HP`, Warlock had a direct `Eldritch Blast` row from `(5,4)`, hit for `10 force`, and ended the encounter.

### What Worked

- Multi-target `Necrotic Bless` worked end to end. The summary showed target count, no-repeat policy, full target options, and suggested extra targets; execution applied `Bless` to Warlock, Archer, and Warrior.
- The immediate follow-up after moving adjacent to the door exposed `Open Door`, so object interaction appeared exactly when it became legal.
- The compact combat digest was enough to understand enemy turns without raw logs: Hero hit/missed Warrior, Archer/Warlock damage, and final defeat were readable.
- Area rows were useful when clean: after Warlock moved to `(5,7)`, `Burning Hands` at `(0,8)` showed `clean` and hit only the Hero.
- Path-aware movement mattered. The interface correctly showed different rows when ally blockers made `Move` impossible and `Jump` legal.

### Friction

- A stale local row produced two enormous `stale_action` responses. The requested `Move` to `(5,7)` was no longer legal because Archer occupied the path; the fresh legal row was `Jump` to `(5,7)`. Before the fix, the tool returned full refreshed actions instead of a compact turn surface.
- The no-attack state did not explain why attacks were absent. Archer and Warlock both had turns where line of sight or ally blockers removed hostile rows, but the summary only showed no attacks plus movement rows.
- `meaningful_commands_remaining` remained true when only movement was left, including cases with no movement remaining.
- Free-row warnings are still too broad and can appear when the actionable choice is unrelated.
- Final dead Hero degraded to remembered with missing position/max HP/AC/faction despite being defeated in sight. The digest preserved the defeat, but the dead entity fact was weaker than expected.

### Measurement

- Saved JSON responses: `59`.
- Estimated server/tool HTTP requests: `97`.
- Total saved response characters: `4260886`.
- Largest full response before the stale-payload fix: `1811527` minified JSON characters, from a `stale_action` response; the pretty-printed file was about `3.84M` characters.
- Stale responses: `2`.
- Largest normal compact turn summary: `22923` JSON characters, roughly `5731` tokens.
- Largest raw recent-combat-log segment: `2` JSON characters because raw logs were omitted.
- Largest normalized action row count: `227`.
- Final compact turn summary: `6940` JSON characters, roughly `1735` tokens.
- Final action row count: `0`, because the encounter ended.

### Implemented Improvement

The stale-row payload issue was addressed immediately:

- Local row-resolution failures now return a compact `follow_up_turn` with a warning instead of embedding the full fresh `ActionsResult`.
- The warning names the stale row and explains that it was not found in fresh actions.
- Raw action listing remains available through the explicit `actions` command, but `execute` no longer dumps it accidentally.

### Tests

- `uv run pytest tests/manual/test_30_codex_takeover_tools.py -q`
- `uv run pyright ai/codex_tools tests/manual/test_30_codex_takeover_tools.py`

### Follow-Up UX Targets

- Add blocker-aware no-hostile-row explanations for range, line of sight, target visibility, movement remaining, action economy, and ally blockers.
- Fix `meaningful_commands_remaining` so movement-only leftovers and no-movement states do not imply useful tactical commands remain.
- Preserve full known facts for entities that die visibly at encounter end.
- Add path/blocker notes that explain why a destination is only reachable by `Jump`, not `Move`.

## 2026-07-02 - Operator Command Availability And Multi-Target Execute Hints

### Trigger

The skeleton-side playtest exposed two operator mistakes that came from weak UX rather than missing rules:

- `meaningful_commands_remaining` could stay true after the only remaining rows were tactically pointless movement leftovers.
- Multi-target rows exposed suggested extra targets, but the execute call still required the operator to remember to pass `extra_target_uuids`.

The second issue showed up with `Necrotic Bless` and applies to `Magic Missile`: both are legal as single-primary-target commands, so the interface must make the split or group-cast choice explicit.

### Implemented Improvement

- Codex turn summaries now refine the engine-level economy flag into an operator-facing useful-command flag.
- Attacks, support rows, area rows, meaningful interactions, object/frontier/retreat movement, and non-adjacent closing movement count as useful.
- Adjacent leftover movement no longer keeps the turn artificially alive.
- Multi-entity action rows now include a typed `execution_hint` object.
- The hint carries the exact `execute_kwargs` for suggested extra targets.
- For repeat-allowed rows such as `Magic Missile`, the hint explains the tactical difference between splitting projectiles with extras and omitting extras to focus remaining projectiles on the primary target.
- For unique-target rows such as `Bless` and `Necrotic Bless`, the hint states that omitted extras are not affected.

### Expected UX Impact

When I see a row like `Necrotic Bless (Level 2)`, the compact turn surface now includes the exact extra UUID list to pass with the execute command. When I see `Magic Missile`, the surface makes it clear whether I am choosing split damage or focus fire, instead of letting the one-target default look like the whole spell.

The useful-command flag should reduce wasted end-of-turn probing. If only irrelevant movement remains after attacking an adjacent enemy, the summary now says no affordable non-end-turn command remains.

### Tests

- `uv run pytest tests/manual/test_30_codex_takeover_tools.py -q`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py::test_unique_multi_entity_spell_sends_same_side_extra_targets tests/manual/test_35_subjective_external_ai.py::test_magic_missile_can_split_onto_low_hp_visible_enemies -q`
- `uv run pyright ai/codex_tools ai/external tests/manual/test_30_codex_takeover_tools.py tests/manual/test_35_subjective_external_ai.py`

### Follow-Up UX Targets

- Add blocker-aware no-hostile-row explanations for range, line of sight, target visibility, movement remaining, action economy, and ally blockers.
- Preserve full known facts for entities that die visibly at encounter end.
- Add path/blocker notes that explain why a destination is only reachable by `Jump`, not `Move`.
- Consider an explicit `execute-suggested` helper only after the split-vs-focus policy is designed carefully.

## 2026-07-02 - Sorcerer Hero Multi-Target Hint Victory

### Setup

- Server: local `server.event_server` on `127.0.0.1:8000`.
- Arena: `/simulation/start-human?character_class=sorcerer`.
- Codex takeover: `faction=heroes`.
- Monster side: current external skeleton AI.
- Result: Codex sorcerer victory in round 2.
- Final hero state: `37 / 37 HP`, `17 AC`, position `(4, 7)`.
- Defeated enemies:
  - Skeleton Warrior: killed by split Magic Missile in round 1.
  - Skeleton Warlock: killed by Shatter in round 2.
  - Skeleton Archer: killed by focused Magic Missile in round 2.

### Combat Summary

Round 1 started with no visible enemies. Codex drank the Haste potion, moved to `(6, 7)`, opened the door, and revealed all three skeletons. The new multi-target execution hints were visible immediately on Magic Missile rows, while area rows also showed clean Fireball centers.

Codex used `Fireball` centered at `(11, 7)`, damaging all three enemies without hitting the hero. With the extra Haste action still available, Codex then cast `Magic Missile` at level 2 with Skeleton Warrior as the primary target and Skeleton Archer plus Skeleton Warlock as explicit extra targets. The split killed Warrior, chipped Archer, and forced Warlock's Shield reaction, which blocked its missile.

Codex closed the door, retreated to `(0, 7)`, and ended the turn. The external AI did not hang: Warlock opened the door and moved to `(6, 7)`, while Archer shot and missed. On round 2, Codex killed Warlock with `Shatter`, moved to `(4, 7)` to reacquire Archer, then focused a level-3 Magic Missile on Archer with no extra targets. Archer died and the encounter ended.

### What Worked

- Multi-target `execution_hint` worked in live play. The row exposed the exact extra UUIDs needed to split Magic Missile.
- The split-vs-focus reminder prevented the previous one-target misunderstanding. Supplying extras split projectiles; omitting extras focused all remaining projectiles on the primary target.
- Fireball area previews were good enough to select a clean center without raw geometry work.
- The combat digest made the Warlock's Shield reaction readable: the Warlock missile dealt `0 force` because Shield blocked it.
- Closing the door and retreating was valid, and the external AI recovered by opening the door and continuing its turn.
- Final command handling was clean: after Archer died, the follow-up had no current epoch and `is_my_turn=false`.

### Friction

- The compact surface still lacks a proper remembered or last-known enemy list. After Warlock died, Archer had acted last round but was not visible in the living-enemy list, so Codex had to move forward to rediscover it.
- Dead enemy facts can still degrade after visibility changes or encounter end. The final Archer fact was remembered with missing position, max HP, AC, and faction even though the death was observed.
- Spellcaster payload size is still too high after door reveal. The largest compact summary reached `41294` characters, about `10324` estimated tokens, with `632` action rows.
- `meaningful_commands_remaining` is better than before, but the operator still needs separate "combat-useful", "positioning-useful", and "housekeeping/free item" categories.
- The multi-target suggestion is explicit but not yet smart. It explains how to split Magic Missile, but it does not compute the best projectile allocation, overkill risk, Shield risk, or kill probability.

### Measurement

- Saved JSON responses: `15` normal artifacts, `17` including heartbeat artifacts.
- Estimated server/tool HTTP requests from payload metrics: `12`.
- Total saved response characters: `433910` minified JSON characters, `585461` characters across saved files.
- Largest full response: `128837` minified JSON characters from the final objective `/state` snapshot.
- Largest compact turn summary: `41294` JSON characters, roughly `10324` tokens, after the Fireball follow-up.
- Largest normalized action row count: `632`, after opening the door and after Fireball.
- Largest raw recent-combat-log segment: `2` JSON characters because raw logs were omitted.
- Final compact turn summary: `4975` JSON characters, roughly `1244` tokens.
- Final action row count: `0`, because the encounter ended.

### Follow-Up UX Targets

- Add remembered and last-known enemy summaries with last seen position, last observed HP, AC, faction, and source cursor.
- Add a projectile allocation helper for repeat-allowed multi-target spells such as Magic Missile.
- Split useful-command reporting into combat-useful, positioning-useful, and housekeeping/free-item remaining.
- Reduce high-row-count spellcaster surfaces by grouping equivalent AoE centers, spell slots, scroll variants, and repeated item rows.
- Preserve full known facts for entities that die visibly at encounter end.

## 2026-07-02 - Remembered Enemy And Projectile Allocation Surface

### Trigger

The Sorcerer victory proved that multi-target execution works, but it also exposed two operator-facing problems:

- after visibility dropped, a living enemy that had recently acted was not surfaced as a remembered search objective;
- Magic Missile hints explained split versus focus, but they did not make an allocation recommendation based on whether the primary target needed all projectiles.

### Implemented Improvement

- Codex briefs now carry `remembered_entities` separately from `visible_entities`.
- Turn summaries now carry `remembered_enemies`.
- When no living enemy is visible, remembered living enemies with positions generate `last_known_enemy_moves`.
- The useful-command flag treats movement toward a last-known enemy as meaningful.
- The warning surface now explicitly says remembered enemies are search objectives, not legal direct targets.
- Multi-target execution hints now include typed `target_allocations`.
- Repeat-allowed projectile rows such as Magic Missile now prefer focus fire when the primary target appears to need every projectile.
- If the primary likely does not need every projectile, the hint suggests extra targets and shows the implied allocation, for example `Bandit x2, Cultist x1`.

### Tests

- `uv run pytest tests/manual/test_30_codex_takeover_tools.py -q`
- `uv run pyright ai/codex_tools tests/manual/test_30_codex_takeover_tools.py`

### Follow-Up UX Targets

- Validate remembered-enemy moves and projectile allocation in the next live game.
- Add reaction-aware Shield risk to projectile allocation once enemy reaction state is reliably available.
- Split useful-command reporting into combat-useful, positioning-useful, and housekeeping/free-item remaining.
- Reduce high-row-count spellcaster surfaces by grouping equivalent AoE centers, spell slots, scroll variants, and repeated item rows.
- Preserve full known facts for entities that die visibly at encounter end.

## 2026-07-02 - Skeletons vs External Barbarian, Remembered Surface Validation

### Setup

- Server: local `server.event_server` on `127.0.0.1:8000`.
- Arena: `/simulation/start-codex-monsters?character_class=barbarian`.
- Codex takeover: `faction=monsters`.
- Opponent: external Barbarian Hero AI.
- Result: Codex skeleton victory in round 4.
- Final skeleton state:
  - Skeleton Archer: `24 / 24 HP`, position `(8, 7)`, concentrating on Mark Target, Blessed.
  - Skeleton Warrior: `11 / 31 HP`, position `(3, 7)`.
  - Skeleton Warlock: `17 / 17 HP`, position `(5, 2)`, concentrating on Bless.
- Final hero state: defeated at `(2, 7)` by the Skeleton Archer's final shortbow shot.

### Combat Summary

The external Barbarian opened but did not find a useful target before the skeleton side took over. Skeleton Archer moved to the closed door, opened it, marked the Hero, missed the first shot, retreated to `(8, 7)`, then closed the door. Closing the door immediately reproduced the critical observation bug: the Hero disappeared from both `living_enemies` and `remembered_enemies`.

Skeleton Warrior then used the known door objective to move to the door, open it, Dash, and take the melee anchor at `(3, 7)`. Skeleton Warlock first cast `Necrotic Bless` on itself and Skeleton Archer using the `execution_hint.extra_target_uuids`, then moved into position.

Rounds 2 through 4 were stable pressure. Archer landed repeated Blessed shortbow hits, Warrior pinned the Barbarian in melee, and Warlock had to move from `(7, 8)` to `(4, 5)` before `Eldritch Blast` appeared. Once the angle was fixed, Warlock landed two blasts. The Barbarian damaged Warrior but never broke through. Archer finished the Hero in round 4.

### What Worked

- The objectward movement surface was strong. With no visible enemy, both Archer and Warrior saw clear movement rows toward the known closed door.
- Door actions appeared exactly when adjacent.
- Combat digest was useful and compact: it reported the Barbarian miss, Warrior damage, Archer crit, Warlock blast damage, and final defeat without raw logs.
- `Necrotic Bless` multi-target hints worked live from the monster side. The hint exposed the exact extra target and typed allocation.
- Moving Warlock before casting correctly changed the legal offensive surface. After moving to `(4, 5)`, `Eldritch Blast` appeared.
- The area preview correctly warned that Burning Hands and Thunderwave would hit Skeleton Warrior, so Codex avoided risky AoE.
- The useful-command flag behaved well after Warlock spent action and movement: it flipped to no meaningful commands remaining.

### Friction

- The remembered-enemy feature is only half complete. The Codex brief and turn summary have typed fields, but the observation projector did not retain the Hero as remembered when the door closed. The interface cannot surface what the stream does not preserve.
- The no-hostile-row warning is still too shallow. Warlock had visible Hero facts but no hostile rows until movement changed line of sight; the warning blamed generic economy or extra attack instead of range, line of sight, ally blockers, or route-to-shot.
- `meaningful_commands_remaining` can still be noisy when free door actions remain. In this game that was tactically valid, but it proves the next split should distinguish combat, positioning, and environmental commands.
- Final dead Hero facts degraded in the subjective follow-up: the dead row had `position=None`, `max_hp=None`, `ac=None`, and `faction=None`, even though the final state still knew those facts objectively.
- One CLI consistency issue remains: `heartbeat` does not accept `--json`, unlike most other Codex tools.

### Measurement

- Saved normal JSON responses: `42`.
- Valid saved JSON responses including heartbeat: `43`.
- Estimated server/tool HTTP requests from payload metrics: `31`.
- Total saved response characters: `624142` minified JSON characters, `899983` characters across saved files.
- Largest full response: `129269` minified JSON characters from the final objective `/state` snapshot.
- Largest game-tool response: `23187` minified JSON characters from the round-2 Warlock watch.
- Largest compact turn summary: `20971` JSON characters, roughly `5243` tokens, after moving Warlock to `(4, 5)`.
- Largest normalized action row count: `206`, after Warrior used Dash.
- Largest raw recent-combat-log segment: `2` JSON characters because raw logs were omitted.
- Final compact turn summary: `6134` JSON characters, roughly `1534` tokens.
- Final action row count: `0`, because the encounter ended.

### Follow-Up UX Targets

- Fix observation projection so entities that leave visibility become remembered with last-known position and retained known combat facts.
- Add no-hostile-row diagnostics for line of sight, range, ally blockers, movement-to-shot, and action economy separately.
- Split meaningful-command reporting into combat-useful, positioning-useful, environmental, and housekeeping/free-item categories.
- Preserve full known facts for entities that die visibly at encounter end.
- Add `--json` support to `heartbeat` for CLI consistency.

## 2026-07-02 - Curated Multi-Target Allocation Surface

### Finding

The engine already supports the multi-target distinction correctly, but the controller surface was still easy to misread:

- `Magic Missile` is `MULTI_ENTITY`, allows repeated targets, and fills omitted darts onto the primary target.
- `Necrotic Bless` is `MULTI_ENTITY`, forbids repeated targets, and only affects the explicitly selected primary plus extra unique targets.
- Decision epochs preserve `target_options`, `num_projectiles`, and `allow_same_target`.
- The command path forwards `extra_target_uuids` into `execute_by_index()`.

The weak point was presentation. The generic `attacks` and `support_actions` lists contained the data, but a spellcaster turn could still look like one row equals one target unless the operator inspected each execution hint.

### Change

Turn summaries now include a curated `multi_target_actions` section. Existing `attacks` and `support_actions` remain unchanged for compatibility, while the new section highlights the real allocation choice:

- unique-target group rows prefer the active actor as the primary when available, then suggest same-side extras;
- repeatable projectile rows show one split candidate and one focus candidate when both choices are meaningful;
- warnings now call out that multi-target rows are available and that `execution_hint.execute_kwargs` should be used when adding or splitting targets.

### Tests

- `uv run pytest tests/manual/test_30_codex_takeover_tools.py::test_codex_multi_entity_actions_preserve_target_options tests/manual/test_30_codex_takeover_tools.py::test_codex_epoch_multi_entity_rows_keep_source_target_options tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_suggests_extra_targets_for_multi_entity_rows tests/manual/test_30_codex_takeover_tools.py::test_codex_execute_sends_multi_entity_extra_targets tests/manual/test_35_subjective_external_ai.py::test_unique_multi_entity_spell_sends_same_side_extra_targets tests/manual/test_35_subjective_external_ai.py::test_magic_missile_can_split_onto_low_hp_visible_enemies -q`
- `uv run pyright ai/codex_tools tests/manual/test_30_codex_takeover_tools.py tests/manual/test_35_subjective_external_ai.py`

## 2026-07-02 - Enemy AI Tactical Ranking Pass

### Finding

The default external enemy AI was better than the retired melee stub, but it was still too linear:

- entity spells were selected by row order, so a support/debuff-looking row could crowd out real damage;
- weapon attacks used the first visible target instead of focusing kill pressure;
- position-targeted spells existed in epochs, but the enemy policy ignored AoE affected-entity metadata;
- safe route metadata existed, but the policy still needed the same style of scoring for offensive rows.

### Change

The enemy behavior tree now makes a first tactical ranking pass before it acts:

- safe AoE spell rows are considered before single-target spells;
- AoE rows are selected only when they hit visible enemies and no controlled allies;
- known damaging spells such as `Magic Missile`, `Fireball`, `Shatter`, `Eldritch Blast`, and `Fire Bolt` receive offensive priority;
- known support spells such as `Necrotic Bless`, `Bless`, and `Haste` are not treated as generic enemy attacks;
- weapon attacks focus weaker visible enemies instead of the first target row;
- the reduced external state preserves AoE affected entity UUIDs and affected positions.

This is not the final enemy AI architecture yet. It is the first real challenge pass on the default enemy behavior, and the next game should specifically test whether the external Hero/Skeleton side feels sharper.

### Tests

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q`
- `uv run pyright ai/external ai/external_melee_agent.py tests/manual/test_35_subjective_external_ai.py`

### Follow-Up Enemy AI Targets

- Play a full game against this improved enemy policy and measure whether it actually increases pressure.
- Add a versioned enemy policy script/snapshot surface so each AI iteration is inspectable without relying on git.
- Add resource-aware spell-slot valuation so enemy casters do not spend premium slots on marginal turns.
- Add line-of-sight repositioning for casters when no hostile row is exposed but an enemy is visible.

## 2026-07-02 - Barbarian Hero vs Improved External Skeleton AI

### Setup

- Server: fresh local `server.event_server` on `127.0.0.1:8001` so the improved enemy policy was loaded.
- Arena: `/simulation/start-human?character_class=barbarian`.
- Codex takeover: `faction=heroes`.
- Codex side: Hasted/Frenzied Barbarian Hero.
- Enemy side: default external AI controlling Skeleton Warrior, Skeleton Archer, and Skeleton Warlock.
- Result: Codex Hero victory in round 3.
- Final Hero state: `43 / 50 HP`, position `(11, 6)`.
- Final enemy state:
  - Skeleton Warlock: defeated in round 1.
  - Skeleton Archer: defeated in round 2.
  - Skeleton Warrior: defeated in round 3.

### Combat Summary

The Hero drank the Haste potion, entered Frenzy, moved to the door, opened it, and engaged the skeleton side. The Hero focused Skeleton Warlock first. Warlock reacted with `Shield` against one extra attack, which made the second attack miss, but the Hero used the Haste action to finish Warlock before it received a normal turn.

The improved enemy AI then had two meaningful turns. Skeleton Warrior selected a direct melee attack against the Hero and hit. Skeleton Archer selected its ranged attack against the Hero and hit. Both attacks landed while the Hero was still benefiting from Rage resistance, so they dealt `3` and `4` applied damage. In round 2 the Warrior attacked again but missed. The Hero then cleaned up Archer and Warrior through Reckless/Frenzied/Extra Attack pressure.

### What This Validated

- The improved external AI path was active in the real subprocess, not only in unit tests.
- Enemy trace events showed `policy_tick` and `selected_command` for Warrior and Archer.
- Warrior and Archer both chose offensive rows immediately instead of wasting movement or housekeeping actions.
- The action response carried enough information to continue the Hero turn without separate action polling after most commands.
- Enemy agent telemetry is usable for post-game review: `external_ai.policy_tick`, `external_ai.command_result`, row ids, command reasons, and actor UUIDs were all present in server logs.

### What This Did Not Validate Enough

- The new caster/AoE ranking was not live-tested well because the Hero killed Warlock before Warlock's first normal turn.
- The game was too favorable to the Hero because Haste potion is currently a free item row and doubled the Barbarian's action economy immediately.
- Enemy pressure was real but not scary: the skeleton side dealt only `7` applied damage before dying.
- External AI still hit stale-epoch retries at turn start before accepting commands. It recovered, but this is avoidable latency/noise.
- The no-hostile-row warning is still not explanatory enough when enemies are visible but melee/ranged rows are unavailable before repositioning.

### Measurement

- Saved JSON artifacts: `28`.
- Valid saved JSON responses: `28`.
- Total saved response characters: `711920` minified JSON characters.
- Largest full response: `129499` minified JSON characters from the final objective `/state` snapshot.
- Turn/action payloads with embedded metrics: `22`.
- Total tool HTTP requests counted from turn metrics: `22`.
- Largest compact turn summary: `23663` JSON characters, roughly `5916` tokens.
- Largest normalized action row count: `253`.
- Final compact turn summary: `5822` JSON characters, roughly `1456` tokens.
- Final action row count: `0`, because the encounter ended.

### Follow-Up Enemy AI Targets

- Run a second enemy-AI validation where Warlock is allowed to act, so `Necrotic Bless`, `Eldritch Blast`, and any safe AoE policy can be observed live.
- Fix or classify the free Haste/Greater Invisibility potion rows, because they dominate Barbarian playtests.
- Add stale-epoch retry reduction for external AI turn starts.
- Add a versioned enemy policy script/snapshot surface so each AI iteration is inspectable without relying on git.

## 2026-07-02 - Enemy Policy Snapshot And Free Consumable Classification

### Finding

The previous Barbarian validation was a real enemy-AI test, but two things made review weaker than it should be:

- the exact enemy policy source/hash was not exposed as a first-class artifact, so dashboard rows could say that the improved AI was active but could not anchor to the policy text that made the decisions;
- free map interactions and free consumable item rows were reported through the same generic warning, even though free `Open Door` is a legitimate environment interaction while free `Drink Haste Potion` and `Drink Greater Invisibility Potion` are balance-sensitive.

This matters for enemy-AI improvement because playtests can look easier or harder for the wrong reason if the Hero is getting powerful free consumables.

### Change

- Added a versioned source snapshot for the built-in external enemy policy: policy name, version label, source path, source hash, line count, and exact source text.
- Exposed that snapshot through `/ai/external-policy/source`.
- Kept the existing enemy behavior improvements intact: safe AoE priority, offensive-spell priority, support-spell filtering, weak-target focus, Magic Missile split suggestions, and route-aware movement.
- Replaced the generic free item/object warning with a specific free-consumable warning.
- Kept legitimate free environment interactions such as doors and levers out of that warning.
- Marked free consumable interaction rows as `free consumable; balance-sensitive` in turn summaries.

Potion action-economy costs were not silently changed in this slice. That is a rules/balance decision and should be handled deliberately.

### Tests

- `uv run pytest tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_warns_for_free_consumables_not_free_doors tests/manual/test_30_codex_takeover_tools.py::test_external_policy_source_endpoint_returns_hashable_enemy_policy -q`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py::test_external_policy_snapshot_identifies_current_enemy_policy tests/manual/test_35_subjective_external_ai.py::test_caster_policy_prefers_visible_offensive_spell tests/manual/test_35_subjective_external_ai.py::test_caster_policy_ignores_support_spell_on_enemy_when_damage_spell_exists tests/manual/test_35_subjective_external_ai.py::test_magic_missile_can_split_onto_low_hp_visible_enemies -q`
- `uv run pyright ai/codex_tools/client.py ai/external ai/external_melee_agent.py server/event_server.py tests/manual/test_30_codex_takeover_tools.py tests/manual/test_35_subjective_external_ai.py`

### Follow-Up Enemy AI Targets

- Run a second enemy-AI validation where Warlock survives long enough to take a normal turn.
- Include the external policy hash in future playtest records.
- Decide potion action-economy policy explicitly instead of letting free Haste dominate challenge measurements.
- Reduce stale-epoch retries for external AI turn starts.

## 2026-07-02 - Sorcerer Hero vs Improved External Skeleton AI

### Setup

- Server: fresh local `server.event_server` on `127.0.0.1:8001`.
- Arena: `/simulation/start-human?character_class=sorcerer`.
- Codex takeover: `faction=heroes`.
- Enemy policy: `external_melee_behavior_tree`, version `2026-07-02.enemy-policy-v1`, SHA-256 prefix `9d47fd6695f94f38`.
- Constraint: no free Haste, Greater Invisibility, or healing potion rows were used, so challenge measurement was not distorted by free consumables.
- Result: Codex Hero victory in round 4.
- Final Hero state: `17 / 37 HP`, position `(6, 7)`.
- Final enemy state:
  - Skeleton Warlock: defeated in round 3.
  - Skeleton Archer: defeated in round 4.
  - Skeleton Warrior: defeated in round 4.

### Combat Summary

The Hero opened the central door, deliberately avoided alpha-striking Warlock, and used a level-1 `Magic Missile` on Archer. This let the enemy caster act. Warlock selected `Eldritch Blast` via the improved `cast_visible_enemy_spell` branch and hit Hero for `9` force damage.

The Warrior used the new move-then-attack behavior: it moved from the enemy side to the door and attacked Hero in the same turn. On the next round, Warlock selected `Eldritch Blast` again and missed, Archer continued ranged attacks, and Warrior forced the Hero's `Shield` reaction.

Hero then used a split `Scorching Ray` to damage Warrior and Warlock, a `Fireball` centered on the enemy cluster to kill Warlock and heavily wound Warrior/Archer, and a split level-2 `Magic Missile` to finish Warrior and Archer.

### What This Validated

- Warlock got two real normal turns, so caster enemy policy was validated live rather than only by tests.
- Warlock chose `Eldritch Blast` both times when a visible enemy was targetable.
- Archer chose ranged attacks and Warrior chose move-to-melee plus melee attacks.
- The enemy side dealt `20` total damage without free Hero consumables: `9` force, `6` slashing, and `5` piercing.
- Split multi-target execution worked twice from the Codex surface: `Scorching Ray` and `Magic Missile`.
- The policy source/hash endpoint worked and was captured as a playtest artifact.

### What Felt Clunky

- Spellcaster action surfaces are still far too large. Visible-enemy turns reached `776` normalized choices and compact summaries around `54k` characters.
- Area rows said `clean`, but did not show affected enemy names. I used Fireball anyway, but this should be explicit before future spellcaster games.
- External AI still hit stale decision epochs at turn starts, then resynced and retried. The run produced `3` stale acks and `25` resync starts.
- The combat digest is good for damage and deaths, but per-ray hit/miss detail for multi-attack spells is still too indirect.
- The `useful_moves` section remains misleading when no enemy is visible; opener navigation relies on `frontier_moves` and `objectward_moves`.

### Measurement

- Saved JSON artifacts: `21`.
- Valid saved JSON responses: `21`.
- Total saved response characters: `882467` minified/read JSON characters.
- Largest full response: `128826` characters from the final objective `/state` snapshot.
- Largest Codex game-tool response: `75310` characters from the post-door turn surface.
- Turn/action payloads with embedded metrics: `11`.
- Total tool HTTP requests counted from turn metrics: `11`.
- Largest compact turn summary: `54005` characters, roughly `13502` tokens.
- Largest normalized action row count: `776`.
- Final compact turn summary: `5784` characters, roughly `1446` tokens.
- Final action row count: `0`, because the encounter ended.
- Enemy agent telemetry: `123` agent events, including `12` policy ticks, `17` command results, `3` stale acks, and `25` resync starts.

### Follow-Up Targets

- Add affected enemy/ally names to area-action summaries.
- Reduce spellcaster action payloads by grouping equivalent area centers, slot variants, scroll variants, and repeated item rows.
- Reduce stale-epoch retries at enemy turn starts.
- Add compact per-projectile hit/miss digesting for Scorching Ray and similar multi-attack spells.

## 2026-07-02 - Area Action Affected-Entity Surface

### Finding

The Sorcerer playtest showed that area rows were still too vague for confident spellcaster play. `Fireball` rows were marked `clean`, but the compact turn surface did not name the affected enemies or allies when the server already had exact affected-entity data.

### Change

- Codex action targets now preserve `affected_entity_uuids`, `affected_entity_names`, and `affected_positions`.
- Area-action summaries now prefer exact affected entity UUIDs from the decision epoch.
- Radius estimation remains only as a fallback when exact affected entities are absent.
- Area summaries now expose `affected_entity_uuids` alongside `enemy_names`, `ally_names`, and `self_included`.

### Tests

- `uv run pytest tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_previews_area_actions_and_non_hostile_spells tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_uses_exact_area_affected_entities_when_available -q`
- `uv run pyright ai/codex_tools/client.py ai/codex_tools/contracts.py tests/manual/test_30_codex_takeover_tools.py`

### Next UX Target

The next biggest spellcaster issue is payload size: visible-enemy Sorcerer turns can still expose hundreds of slot, scroll, item, and area-center variants. The interface needs row grouping without hiding legal execution.

## 2026-07-02 - Multi-Target Hint Deduplication

### Finding

The last Sorcerer turn summaries duplicated expensive multi-target guidance. The generic `attacks` and `support_actions` sections carried full target-option lists and long execution hints, then `multi_target_actions` carried the same allocation guidance again in the curated place where the operator is supposed to look.

On the previous large Sorcerer turn, this duplication contributed about `7760` characters, roughly `14.3%` of the compact payload.

### Change

- Generic `attacks` and `support_actions` rows still include executable row ids, target names, costs, spell levels, and multi-target counts.
- Heavy multi-target details now live only in `multi_target_actions`:
  - target-option names;
  - suggested extra target UUIDs/names;
  - execution hints;
  - allocation reminders.
- The warning already points operators to `multi_target_actions`, so the detailed guidance remains discoverable in one place.

This is a deduplication pass, not the full spellcaster row-grouping solution. The next bottleneck is still equivalent spell slots, scroll variants, and area centers.

### Tests

- `uv run pytest tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_suggests_extra_targets_for_multi_entity_rows tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_previews_area_actions_and_non_hostile_spells tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_uses_exact_area_affected_entities_when_available -q`
- `uv run pyright ai/codex_tools/client.py ai/codex_tools/contracts.py tests/manual/test_30_codex_takeover_tools.py`

## 2026-07-02 - Spell And Area Variant Groups

### Finding

The previous deduplication removed repeated multi-target instructions, but the spellcaster surface still carried many tactically equivalent variants as full primary rows:

- `Magic Missile (Level 1/2/3)` and scroll copies against the same target;
- `Scorching Ray (Level 2/3)` against the same target;
- `Burning Hands`, `Thunderwave`, and similar area rows repeated across nearby centers and spell levels while affecting the same visible entities;
- sorcery-point conversion rows repeated as separate interactions.

The old large Sorcerer turn had `776` normalized choices. A compact summary still needed to preserve legal execution, but it did not need every variant to occupy a full primary command row.

### Change

- Added `variant_groups` to turn summaries.
- Entity spell variants are grouped by base action and target.
- Area spell variants are grouped by base action and exact affected visible entity set.
- Interaction variants can be grouped by shared utility role.
- Primary `attacks`, `support_actions`, `area_actions`, and `interactions` keep the representative executable row.
- Every hidden alternate remains executable through `variant_groups[*].variants[*].row_id`.

Estimated against the previous large Sorcerer turn:

- compact payload: about `54238` characters before grouping;
- estimated grouped payload: about `45626` characters;
- estimated savings: `8612` characters, about `15.9%`;
- visible attack rows: about `12 -> 6`;
- visible area rows: about `12 -> 2`;
- variant groups: `7`.

### Tests

- `uv run pytest tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_suggests_extra_targets_for_multi_entity_rows tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_uses_exact_area_affected_entities_when_available tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_groups_spell_variants_without_hiding_row_ids -q`
- `uv run pyright ai/codex_tools/client.py ai/codex_tools/contracts.py tests/manual/test_30_codex_takeover_tools.py`

### Next Validation

Run another full game after this grouping pass and compare largest turn payload, action-choice pressure, and operator decision quality against the previous Sorcerer run.

## 2026-07-02 - Grouped Sorcerer Interface Validation

### Setup

- Server: fresh local `server.event_server` on `127.0.0.1:8002`.
- Arena: `/simulation/start-human?character_class=sorcerer`.
- Codex takeover: `faction=heroes`.
- Enemy policy loaded in that server: `external_melee_behavior_tree`, version `2026-07-02.enemy-policy-v1`, SHA-256 prefix `9d47fd6695f94f38`.
- Result: Codex Hero victory in round 3.
- Final Hero state: `37 / 37 HP`, position `(6, 7)`.
- Final enemy state:
  - Skeleton Warlock: defeated in round 1.
  - Skeleton Archer: defeated in round 1.
  - Skeleton Warrior: defeated in round 3.

### What This Validated

- `variant_groups` worked in a live spellcaster game and preserved executable row ids for hidden variants.
- The first post-door spellcaster surface dropped from the previous comparable `50202` character payload to `43048` summary characters.
- The largest compact summary in this run was `43048` characters, down from the previous Sorcerer validation's `54005`.
- Primary visible rows were smaller: post-door attacks were `6`, area rows were `1`, and hidden alternatives were carried by `7` variant groups.
- The grouped row ids were still usable: the Hero cast `Fireball`, then level-3 `Magic Missile`, then scroll `Magic Missile` through the command path.

### What This Did Not Validate

This was not a useful enemy-AI challenge benchmark. The Hero killed Skeleton Warlock and Skeleton Archer with an opening `Fireball` before either could take a normal turn. The only enemy behavior observed was Skeleton Warrior moving toward the Hero and attacking. That means the run validates interface grouping, not the difficulty of the enemy policy.

The Magic Missile finish also exposed a digest/state clarity issue: the immediate follow-up death summary showed Warrior at `-3 HP`, while the final objective state showed Warrior at `-12 HP`. That likely means the compact digest is summarizing an intermediate death event while later missiles continue to resolve. The engine may be correct, but the digest should make overkill/projectile continuation explicit.

### Measurement

- Saved JSON artifacts: `18`.
- Valid saved JSON responses: `18`.
- Total saved response characters: `671693`.
- Largest full response: `128766` characters from the final objective `/state` snapshot.
- Largest game-tool response with metrics: `66114` characters from the post-door turn.
- Turn/action payloads with embedded metrics: `9`.
- Total tool HTTP requests counted from turn metrics: `9`.
- Largest compact turn summary: `43048` characters, roughly `10762` tokens.
- Largest normalized action row count: `604`.
- Enemy agent telemetry: `54` events, including `5` policy ticks, `5` command results, and `2` stale acks.

### Follow-Up Targets

- Treat this as an interface validation only.
- Run the next challenge validation on a fresh server with the current enemy policy.
- Add compact per-projectile/overkill outcome digesting for Magic Missile and Scorching Ray.
- Continue reducing stale-epoch retries at enemy turn starts.

## 2026-07-02 - Enemy Policy V2 Opening Group Support

### Finding

You were right to call out the drift: interface work helps Codex operate, but the goal also explicitly requires the built-in enemy AI to become more challenging. The current enemy policy already knew how to cast damaging spells, focus weak targets, use safe AoE, move through doors, and send multi-target extras. The remaining problem was intent ordering: when a Warlock-style caster saw a Hero, it preferred immediate single-target damage over a high-value group support spell even when multiple skeletons were unbuffed.

### Change

- Added known conditions to the reduced external entity facts.
- Added `controlled_entities` to `ExternalAgentState`, so policy code can inspect controlled allies, HP, positions, and known conditions without querying the server.
- Added an opening support branch before single-target spell damage:
  - safe AoE remains first;
  - high-value group support can now beat a low-value cantrip when at least two controlled creatures would benefit;
  - already-buffed allies are skipped for support valuation and extra-target selection.
- Updated the external policy source version to `2026-07-02.enemy-policy-v2`.

This should make Skeleton Warlock more dangerous in the standard arena: if `Necrotic Bless` is legal and the skeleton group is unbuffed, it can open with a real team buff instead of immediately defaulting to `Eldritch Blast`.

### Tests

- `uv run pytest tests/manual/test_35_subjective_external_ai.py::test_caster_policy_opens_with_group_support_before_single_target_cantrip tests/manual/test_35_subjective_external_ai.py::test_caster_policy_does_not_recast_group_support_on_blessed_allies tests/manual/test_35_subjective_external_ai.py::test_caster_policy_prefers_visible_offensive_spell tests/manual/test_29_external_ai_subprocess.py::test_reducer_extracts_actor_enemies_doors_and_action_rows -q`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q`
- `uv run pytest tests/manual/test_29_external_ai_subprocess.py::test_behavior_tree_casts_visible_enemy_spell_before_weapon_attack tests/manual/test_29_external_ai_subprocess.py::test_behavior_tree_attacks_before_movement_or_doors tests/manual/test_29_external_ai_subprocess.py::test_behavior_tree_moves_toward_known_closed_door tests/manual/test_29_external_ai_subprocess.py::test_reducer_extracts_actor_enemies_doors_and_action_rows -q`
- `uv run pyright ai/external tests/manual/test_29_external_ai_subprocess.py tests/manual/test_35_subjective_external_ai.py`

### Next Validation

Start a fresh game with policy v2 loaded and specifically let Warlock act before alpha-striking it. The target measurement is not only win/loss; it should check whether Warlock uses opening support, whether Warrior/Archer benefit from it, and whether enemy damage or survival improves without relying on free Hero consumables.

## 2026-07-02 - Sorcerer Hero vs Enemy Policy V2

### Setup

- Server: fresh local `server.event_server` on `127.0.0.1:8003`.
- Arena: `/simulation/start-human?character_class=sorcerer`.
- Codex takeover: `faction=heroes`.
- Enemy policy: `external_melee_behavior_tree`, version `2026-07-02.enemy-policy-v2`, SHA-256 prefix `607fc5a96ceddadf`.
- Constraint: no free Haste, Greater Invisibility, or healing potion rows were used.
- Result: Codex Hero victory in round 3.
- Final Hero state: `31 / 37 HP`, position `(6, 7)`.
- Final enemy state:
  - Skeleton Warrior: defeated in round 3.
  - Skeleton Archer: defeated in round 3.
  - Skeleton Warlock: defeated in round 3.

### Combat Summary

The Hero moved to the central door, opened it, and deliberately avoided the alpha-strike. Instead of Fireballing immediately, the Hero used `Fire Bolt` on Skeleton Archer for `7` fire damage and ended the turn with all three enemies alive.

Policy v2 immediately did the thing it was designed to do. Skeleton Warlock selected `Necrotic Bless__slot_2` through `cast_opening_controlled_support_spell`, with Skeleton Archer as the primary target and Skeleton Warrior plus Skeleton Warlock supplied through `extra_target_uuids`. The subjective Hero state then showed all three skeletons with `Bless`, and Warlock concentrating.

The buffed enemy round produced real pressure even though the attack rolls did not convert into much damage. Archer attacked and forced the Hero's `Shield`. Warrior moved into the doorway pressure position. On the next enemy round, Warlock selected `Burning Hands__slot_1` through `cast_visible_area_spell` and dealt `6` fire damage to the Hero; Archer and Warrior attacked again but missed.

The Hero then used `Fireball`, leaving all three skeletons at `4 HP`. A Quickened `Magic Missile` into Warlock was completely blocked by Warlock's `Shield`, which kept Bless online. On the following Hero turn, `Thunderwave` killed Warrior and Warlock and broke concentration, then Quickened `Magic Missile` finished Archer.

### What This Validated

- Enemy policy v2 was loaded and anchored by the policy-source endpoint.
- Warlock used opening group support before single-target damage when the skeleton group was unbuffed.
- Multi-target support was not one-target fake behavior: Archer, Warrior, and Warlock all gained `Bless`.
- Warlock later selected an offensive area spell through `cast_visible_area_spell`.
- Enemy AI used reaction defense effectively: Warlock's `Shield` blocked an attempted Magic Missile kill at `4 HP`.
- The group survived long enough to create a round-3 Hero turn, whereas the prior grouped-interface validation killed Warlock and Archer before they acted.

### What Stayed Weak Or Clunky

- Actual HP damage was only `6`, because Archer and Warrior missed and Hero Shielded. Behavior quality improved, but one game does not prove higher damage output.
- Stale/resync churn remains too high: the final enemy telemetry had `2` stale acks and `20` resync starts.
- The server log still prints `Task was destroyed but it is pending!` for abandoned SSE subscriptions; this is observability noise and may hide real stream lifecycle bugs.
- The largest Hero turn grew to `825` choices and `49876` summary characters after enemies clustered around the door. Grouping helped, but close-range spellcaster turns still need stronger top-recommendation/capping.
- The Magic Missile surface correctly showed allocation, but not reaction risk. Warlock's Shield made a tactically plausible Magic Missile finish fail completely.

### Measurement

- Saved JSON artifacts, excluding the intentionally failed `/health` probe: `25`.
- Valid saved JSON responses: `25`.
- Total saved response characters: `852054`.
- Largest full response: `128822` characters from the final objective `/state` snapshot.
- Largest game-tool response: `81204` characters from the round-3 Hero turn.
- Turn/action payloads with embedded metrics: `12`.
- Total tool HTTP requests counted from turn metrics: `12`.
- Largest compact turn summary: `49876` characters, roughly `12469` tokens.
- Largest normalized action row count: `825`.
- Final compact turn summary: `5807` characters, roughly `1452` tokens.
- Final action row count: `0`, because the encounter ended.
- Enemy agent telemetry: `102` events, including `12` policy ticks, `14` command results, `2` stale acks, and `20` resync starts.
- Enemy damage to Hero HP: `6`.
- Defensive pressure: Hero used or gained `Shield` twice; Warlock used `Shield` to block Magic Missile.

### Follow-Up Targets

- Add reaction-risk notes for Magic Missile and other projectile rows when a visible caster can still cast Shield.
- Reduce stale/resync churn in the external AI hot loop.
- Add stronger top-recommendation or row-capping for close-range spellcaster turns.
- Add stream lifecycle cleanup so abandoned SSE subscriptions do not leave pending-task warnings.

## 2026-07-02 - Magic Missile Shield Reaction Risk Notes

### Finding

The v2 playtest exposed a tactical presentation gap. Warlock was at `4 HP`, and a focused Quickened `Magic Missile` looked like a clean finish. It was not: Warlock still had a reaction and cast `Shield`, blocking every dart and keeping `Bless` concentration alive for another enemy round.

The row was legal, and the engine result was good. The weak point was the operator surface: it did not warn that a Shield-capable-looking caster could invalidate Magic Missile.

### Change

- Magic Missile rows now add a tactical note when the target looks Shield-capable from subjective facts.
- The first heuristic uses only local known facts:
  - target name contains a caster marker such as `warlock`, `wizard`, `sorcerer`, or `mage`;
  - or target conditions include caster/reaction clues such as `Concentrating` or `Shield`.
- The row remains legal and visible. The note is advisory, not an action filter.

Example note:

`living enemy; reaction risk: Shield can block Magic Missile`

### Tests

- `uv run pytest tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_warns_magic_missile_into_shield_caster tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_suggests_extra_targets_for_multi_entity_rows tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_groups_spell_variants_without_hiding_row_ids -q`
- `uv run pyright ai/codex_tools/client.py tests/manual/test_30_codex_takeover_tools.py`

### Next UX Target

The next step is stronger turn-level recommendation/capping. The warning helps avoid one mistake, but a `825`-choice close-range spellcaster surface still requires too much scanning.

## 2026-07-02 - Turn Recommendation Shortlist

### Finding

The enemy-policy v2 validation produced the largest operator surface so far: `825` normalized choices and a compact turn summary of about `49876` characters. The legal rows were present, but the first decision still required too much manual scanning.

This is interface work, not enemy-challenge work by itself. It exists to make Codex and future operators less likely to waste turns while the enemy policy continues improving separately.

### Change

- Added typed `recommendations` to `TurnSummaryResult`.
- Recommendations are generated from already summarized legal rows, not from a new backend query.
- Each recommendation carries:
  - row id;
  - section name;
  - display/target/position;
  - cost summary;
  - reason;
  - execution kwargs for multi-target rows when useful;
  - tactical note.
- Ranking currently favors:
  - clean AoE rows;
  - low-HP finishers;
  - multi-target allocations;
  - high-value support;
  - Quickened Spell exposure;
  - movement only when no offensive candidate exists.
- Magic Missile into Shield-risk casters is demoted behind cleaner low-HP finishers and keeps the reaction-risk warning in the recommendation reason.

### Tests

- `uv run pytest tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_warns_magic_missile_into_shield_caster tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_suggests_extra_targets_for_multi_entity_rows tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_groups_spell_variants_without_hiding_row_ids tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_groups_tactical_rows -q`
- `uv run pyright ai/codex_tools/client.py ai/codex_tools/contracts.py tests/manual/test_30_codex_takeover_tools.py`

### Next UX Target

The shortlist helps find the first few good commands, but it does not yet reduce raw payload size. The next UX-side pass should cap or group equivalent rows after preserving exact executable row ids.

## 2026-07-02 - Enemy Policy V3 Resource Discipline

### Finding

The goal is not only a better Codex interface. The enemy AI itself must become harder to play against.

After v2, the Warlock could open with group support, cast safe AoE, and defend with Shield. A remaining tactical weakness was resource discipline: the policy treated high-slot single-target spells as always better than cheaper finishers. That can waste pressure resources on a nearly dead target and make later enemy turns weaker.

### Change

- Preserved action-cost metadata through the external reduced state:
  - `cost`;
  - `spell_level`;
  - `cast_at_level`;
  - tactical `tags`.
- Changed offensive spell scoring so resource spending is target-aware.
- Slot spells still win on healthy targets when their spell priority is higher.
- If the visible target is at low HP and a legal cheap finisher exists, the policy avoids slot overkill:
  - cantrip finisher beats Magic Missile on a `4 HP` Hero;
  - if no cantrip is legal, weapon fallback beats Magic Missile on that same `4 HP` target.
- Repeat-allowed projectile spells still stay valuable when they can clean up multiple low-HP enemies in one command.
- Updated the external policy source version to `2026-07-02.enemy-policy-v3-resource-discipline`.

### Tests

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q`
- `uv run pytest tests/manual/test_29_external_ai_subprocess.py::test_reducer_extracts_actor_enemies_doors_and_action_rows tests/manual/test_29_external_ai_subprocess.py::test_start_human_external_mode_creates_ai_session_and_spawns_once -q`
- `uv run pytest tests/manual/test_30_codex_takeover_tools.py::test_external_policy_source_endpoint_returns_hashable_enemy_policy -q`
- `uv run pyright ai/external ai/external_melee_agent.py tests/manual/test_29_external_ai_subprocess.py tests/manual/test_35_subjective_external_ai.py`

### Next Enemy Target

Run a fresh playtest against policy v3 and measure resource preservation: does Warlock keep meaningful spell pressure after low-HP cleanup moments, and does the monster side force more Hero defensive economy without relying on lucky rolls?

## 2026-07-02 - Barbarian Hero vs Enemy Policy V3

### Setup

- Server: fresh local `server.event_server` on `127.0.0.1:8014`.
- Arena: `/simulation/start-human?character_class=barbarian&monster_ai=external`.
- Codex takeover: `faction=heroes`.
- Enemy policy: `external_melee_behavior_tree`, version `2026-07-02.enemy-policy-v3-resource-discipline`, SHA-256 prefix `b83fcb6d18b281cd`.
- Constraint: no free Haste, Greater Invisibility, or healing potion rows were used.
- Result: Codex Barbarian Hero victory in round 4.
- Final Hero state: `24 / 50 HP`, position `(11, 8)`.
- Final enemy state:
  - Skeleton Warrior: defeated in round 2.
  - Skeleton Warlock: defeated in round 3.
  - Skeleton Archer: defeated in round 4.

### Combat Summary

The Hero opened from a non-Sorcerer surface. Turn 1 moved to the central door, opened it, entered Frenzy/Rage, moved forward, and Dodged. This exposed a useful diagnostic gap: the summary correctly showed visible enemies and no hostile rows, but it did not explain that the Hero was still just outside melee reach and should either Dash, Dodge, or move adjacent first.

The enemy side created real pressure. Warrior and Archer attacked; Warlock used `cast_visible_area_spell` and dealt fire damage. On round 2 the Hero used Reckless Attack, killed Warrior with the action attack plus Extra Attack, then moved adjacent and used Frenzied Strike on Warlock. Warlock survived at `3 HP`.

Round 3 validated enemy pressure again. Archer crit the Reckless Hero, and Warlock dealt another `10` fire damage before dying. The Hero tried to use the bonus-action Frenzied Strike to finish Warlock first, which was the correct economy plan, but missed; Warlock used `Shield`. The Hero then used Reckless Attack and a main action attack to kill Warlock, followed by Extra Attack into Archer.

Round 4 ended the fight. Archer hit once more, then the Hero used Reckless Attack and killed Archer with a Greataxe action attack.

### What This Validated

- Policy v3 was loaded and anchored through the policy-source endpoint.
- Barbarian class flow is usable through the hot Codex interface:
  - Frenzy/Rage;
  - Reckless Attack;
  - main attack;
  - Extra Attack;
  - Frenzied Strike.
- The enemy side dealt `26` effective HP damage to a raging Barbarian without free Hero consumables.
- Warlock remained dangerous even at `3 HP`, using fire damage before dying.
- Warlock's `Shield` reaction meaningfully disrupted a low-HP finisher.
- The new recommendation shortlist helped on Extra Attack turns, where it correctly surfaced the free follow-up attack first.

### What Stayed Weak Or Clunky

- A melee row was recommended while out of reach. Artifact `014_frenzied_warlock_r2.json` shows `entity|Frenzied Strike|...` against Warlock rejected with `Target entity not in reach for Frenzied Strike (Greataxe)`.
- The summary-layer mitigation now suppresses obviously out-of-reach melee rows and recommends adjacent movement first, but the server-side epoch can still expose an invalid melee row. This is now tracked in `KNOWN_ISSUES.md`.
- Door recommendations still prefer `move toward Door` even when `Open Door` is already legal. The operator can work around it, but the shortlist should treat adjacent open/close-door rows as better than more doorward movement.
- When enemies are visible but hostile rows are absent, the warning still needs sharper diagnostics: out of reach, line of sight, action spent, bonus spent, Dash useful, Dodge useful.
- Enemy telemetry still shows stale/resync churn: `3` stale command acks, `21` resync starts, and `20` resync completions.
- Server logs still print pending `BoundedSubscription.get()` task warnings after SSE clients disconnect.

### Integrated Improvement

After finishing the game, the operator summary was patched to avoid repeating the exact mistake:

- hostile melee weapon rows with known target distance greater than `5 ft` are suppressed from `attacks`;
- recommendation ranking therefore selects adjacent movement instead of an invalid attack;
- the warning now says: `Visible living enemies exist, but current hostile rows are out of reach; move adjacent before attacking.`

### Measurement

- Raw saved JSON responses: `30`.
- Total raw saved response characters: `918397`.
- Largest raw response: `129428` characters from the final `/state` snapshot.
- Turn/action payloads with embedded metrics: `22`.
- Total tool HTTP requests counted from turn metrics: `22`.
- Largest compact turn summary: `24735` characters, roughly `6184` tokens.
- Largest normalized action row count: `259`.
- Final compact turn summary: `5707` characters, roughly `1427` tokens.
- Final action row count: `0`, because the encounter ended.
- Enemy agent telemetry: `100` events.
- Enemy policy ticks: `10`.
- Enemy command results: `12`.
- Enemy stale command acks: `3`.
- Enemy resync starts/completions: `21 / 20`.
- Enemy selected-policy reasons: `move_toward_visible_enemy` `2`, `attack_visible_enemy` `6`, `cast_visible_area_spell` `2`.
- Enemy damage to Hero HP: `26`.

### Verification

- `uv run pytest tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_filters_out_of_reach_melee_recommendations tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_groups_tactical_rows tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_warns_magic_missile_into_shield_caster -q`
- `uv run pyright ai/codex_tools/client.py tests/manual/test_30_codex_takeover_tools.py`

### Next Targets

- Fix server-side epoch generation so melee affordances are not emitted when execution will reject them as out of reach.
- Prioritize legal adjacent object interactions, especially `Open Door`, above additional movement toward the same object.
- Reduce stale/resync churn in the external AI hot loop.
- Continue enemy policy work with focus-fire coordination across monster turns.

## 2026-07-02 - Enemy AI Challenge Pass: Legal Melee, Dash, And Dodge

### Finding

You were right to call out the drift. The goal is not only to make Codex read the game better; the built-in enemy side must become harder to play against.

The Barbarian playtest exposed one concrete engine/action bug and one enemy-policy weakness:

- `Frenzied Strike` discovery could expose out-of-reach visible targets because its `pre_validate()` skipped the full attack validation path.
- When an enemy saw a target but had no immediate spell, attack, or useful movement row, the behavior tree could fall through toward passive end-turn behavior instead of spending defensive or mobility economy.

### Change

- Fixed `FrenziedStrike.pre_validate()` so discovery now uses the same validation path as execution after confirming a melee weapon exists.
- Added enemy policy branches after normal movement:
  - `dash_toward_visible_enemy`;
  - `dodge_under_pressure`.
- Updated the external policy source version to `2026-07-02.enemy-policy-v4-legal-melee-dash-dodge`.
- Preserved existing higher-priority behavior:
  - safe AoE;
  - opening group support;
  - visible enemy spells;
  - weapon attacks;
  - normal movement;
  - door opening/search.

### Why This Improves Challenge

The enemy policy now wastes fewer command attempts on impossible melee rows, and pressured enemies with no immediate offense can still spend action economy to close distance or defend. This is a small tactical layer, not a new strategic brain, but it directly improves enemy turns rather than merely improving the Codex operator interface.

### Verification

- `uv run pytest tests/manual/test_15_class_features.py::test_frenzied_strike_discovery_excludes_targets_outside_weapon_reach -q`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py::test_enemy_policy_dashes_when_visible_enemy_exists_but_no_move_progresses tests/manual/test_35_subjective_external_ai.py::test_enemy_policy_dodges_under_pressure_when_no_better_row_exists tests/manual/test_35_subjective_external_ai.py::test_caster_policy_prefers_visible_offensive_spell tests/manual/test_35_subjective_external_ai.py::test_movement_policy_prefers_safe_route_metadata tests/manual/test_15_class_features.py::test_frenzied_strike_discovery_excludes_targets_outside_weapon_reach -q`
- `uv run pytest tests/manual/test_29_external_ai_subprocess.py::test_behavior_tree_attacks_before_movement_or_doors tests/manual/test_29_external_ai_subprocess.py::test_behavior_tree_casts_visible_enemy_spell_before_weapon_attack tests/manual/test_29_external_ai_subprocess.py::test_behavior_tree_moves_toward_visible_enemy_when_attack_is_unavailable tests/manual/test_29_external_ai_subprocess.py::test_behavior_tree_opens_adjacent_door_when_no_enemy_is_visible tests/manual/test_29_external_ai_subprocess.py::test_behavior_tree_moves_toward_known_closed_door tests/manual/test_29_external_ai_subprocess.py::test_behavior_tree_ends_turn_without_enemy_or_closed_door tests/manual/test_29_external_ai_subprocess.py::test_behavior_tree_waits_when_it_is_not_the_ai_turn -q`
- `uv run pytest tests/manual/test_15_class_features.py::test_sorcerer_quickened_spell_overrides_template_and_cleans_after_cast tests/manual/test_15_class_features.py::test_frenzied_strike_discovery_excludes_targets_outside_weapon_reach -q`
- `uv run pytest tests/manual/test_30_codex_takeover_tools.py::test_external_policy_source_endpoint_returns_hashable_enemy_policy -q`
- `uv run pyright ai/external/policy.py dnd/classes/rage.py tests/manual/test_35_subjective_external_ai.py tests/manual/test_15_class_features.py`

### Next Targets

- Play another fresh Barbarian and Sorcerer challenge run against this enemy policy and compare enemy damage, wasted commands, and defensive actions.
- Add focus-fire coordination across monster turns so Warrior, Archer, and Warlock converge on wounded targets.
- Improve adjacent `Open Door` priority in Codex-facing recommendations.
- Reduce stale/resync churn in the external AI hot loop.

## 2026-07-02 - Sorcerer Challenge Validation Against Enemy Policy V4

### Setup

- Artifact folder: `/tmp/dnd_sorcerer_v4_iteration`.
- Server: isolated `127.0.0.1:8020` run, shut down after capture.
- Enemy policy version: `2026-07-02.enemy-policy-v4-legal-melee-dash-dodge`.
- Enemy policy SHA-256: `ff12e6f26b62e733172151b20d2ba7040f6f32ac9768a852a8775c89af515eb8`.
- Scenario: Sorcerer Hero versus Skeleton Warrior, Skeleton Archer, and Skeleton Warlock.
- Constraint: no free consumable abuse; deliberately avoided an opening Fireball so the enemy side could take a meaningful turn.

### Combat Summary

The Hero moved to the central door, opened it, revealed all three skeletons, split `Scorching Ray` across Warlock, Archer, and Warrior, then used `Quickened Spell` into `Fire Bolt` to kill Warlock before the enemy caster could act. The Hero then closed the door to force the enemy policy through the object-navigation path.

The enemy side did the important part correctly. Warrior moved to the door, opened it, reacquired the Hero, and attacked in melee. Archer then used a ranged attack. Both attacks missed, so the Hero took `0` damage, but the enemy policy did not hang and did not ignore the door.

On the next Hero turn, `Fireball` hit the remaining Archer and Warrior and ended the encounter. Final state: Hero `37/37 HP`; Warrior `-1/31 HP`; Archer `-8/24 HP`; Warlock `-3/17 HP`.

### What This Validated

- Enemy policy v4 is the active default enemy path in this arena.
- The enemy AI no longer polls `/available-actions` in the normal path; the server log showed `0` available-action debug endpoint hits.
- Door navigation works in a live challenge loop:
  - move toward closed door;
  - open adjacent door;
  - attack after visibility returns.
- Multi-target Hero execution worked from the Codex surface: `Scorching Ray` carried `extra_target_uuids` and split rays across multiple skeletons.
- The policy-source endpoint gives a reproducible source hash for the exact enemy code used in the run.

### What Stayed Weak Or Clunky

- The first enemy command was incorrectly rejected as `stale` even though it used the just-published turn-start epoch. Root cause: validation recomputed a snapshot epoch after the decision-epoch control frame advanced the observation cursor.
- The enemy runtime still produced too much stream churn in this short fight:
  - `41` snapshot requests;
  - `20` observation subscribe requests;
  - `10` resync starts;
  - `10` resync completions;
  - `1` stale command ack before the epoch-cache fix.
- Closing the door made the living Archer and Warrior disappear from the Codex subjective surface instead of becoming remembered enemies with last-known facts. They reappeared after Warrior opened the door.
- The Codex recommendation surface still prefers some spell/metamagic lines over obvious exploration/object steps, and adjacent `Open Door` is still not promoted enough when it is the next natural command.
- Server logs still show pending `BoundedSubscription.get()` task warnings after SSE clients disconnect.
- A suspicious Shield/reaction trace appeared around an Archer miss in the digest. This needs source inspection before calling it a gameplay bug.

### Integrated Improvement

After the game, command validation was patched to reuse the server's published current decision epoch while it still matches the active actor, round, and turn. A decision epoch is now stable across its own control-frame cursor advancement and rotates only when a real command/action boundary publishes a new epoch or clears the turn.

This directly removes the false stale retry observed on Warrior's first move. The enemy should spend its first command on gameplay instead of protocol recovery.

### Measurement

- Raw saved JSON responses: `15`.
- Total raw saved response characters: `586113`.
- Largest raw response: `128825` characters from the final `/state` snapshot.
- Largest game-tool response: `75672` characters after the enemy round.
- Largest compact turn summary: `46553` characters, roughly `11639` estimated tokens.
- Largest normalized action row count: `725`.
- Final compact turn summary: `5267` characters, roughly `1317` estimated tokens.
- Final action row count: `0`, because the encounter ended.
- Enemy agent telemetry: `51` events.
- Enemy policy ticks: `5`.
- Enemy command results: `6`.
- Enemy stale command acks before the fix: `1`.
- Enemy resync starts/completions: `10 / 10`.
- Enemy selected-policy reasons:
  - `move_toward_visible_enemy`;
  - `move_toward_closed_door`;
  - `open_adjacent_door`;
  - `attack_visible_enemy`.
- Enemy damage to Hero HP: `0`.

### Verification

- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py::test_stale_command_emits_subjective_result_without_engine_mutation tests/manual/test_36_seamless_subjective_runtime.py::test_published_epoch_survives_control_cursor_advancement tests/manual/test_36_seamless_subjective_runtime.py::test_accepted_command_publishes_result_then_followup_epoch -q`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py::test_external_ai_normal_path_does_not_fetch_available_actions tests/manual/test_35_subjective_external_ai.py::test_enemy_policy_dashes_when_visible_enemy_exists_but_no_move_progresses tests/manual/test_35_subjective_external_ai.py::test_enemy_policy_dodges_under_pressure_when_no_better_row_exists tests/manual/test_35_subjective_external_ai.py::test_caster_policy_prefers_visible_offensive_spell tests/manual/test_35_subjective_external_ai.py::test_movement_policy_prefers_safe_route_metadata -q`
- `uv run pytest tests/manual/test_29_external_ai_subprocess.py::test_behavior_tree_attacks_before_movement_or_doors tests/manual/test_29_external_ai_subprocess.py::test_behavior_tree_casts_visible_enemy_spell_before_weapon_attack tests/manual/test_29_external_ai_subprocess.py::test_behavior_tree_moves_toward_visible_enemy_when_attack_is_unavailable tests/manual/test_29_external_ai_subprocess.py::test_behavior_tree_opens_adjacent_door_when_no_enemy_is_visible tests/manual/test_29_external_ai_subprocess.py::test_behavior_tree_moves_toward_known_closed_door tests/manual/test_29_external_ai_subprocess.py::test_behavior_tree_ends_turn_without_enemy_or_closed_door -q`
- `uv run pytest tests/manual/test_15_class_features.py::test_frenzied_strike_discovery_excludes_targets_outside_weapon_reach -q`
- `uv run pyright ai/external/policy.py ai/external/policy_source.py dnd/classes/rage.py tests/manual/test_35_subjective_external_ai.py tests/manual/test_15_class_features.py server/event_server.py tests/manual/test_36_seamless_subjective_runtime.py`

### Next Targets

- Re-run a fresh challenge game after the epoch-cache fix and confirm enemy stale command acks drop to `0`.
- Fix subjective memory so living enemies that leave sight become remembered/last-known instead of disappearing.
- Add focus-fire coordination across monster turns so Warrior, Archer, and Warlock converge on wounded priority targets.
- Promote legal adjacent object interactions such as `Open Door` above more objectward movement.
- Reduce stream resync churn and pending SSE task warnings.

## 2026-07-03 - Barbarian Challenge Validation After Epoch Stability Fix

### Setup

- Artifact folder: `/tmp/dnd_barbarian_epochfix_iteration`.
- Server: isolated `127.0.0.1:8021` run, shut down after capture.
- Enemy policy version: `2026-07-02.enemy-policy-v4-legal-melee-dash-dodge`.
- Enemy policy SHA-256: `ff12e6f26b62e733172151b20d2ba7040f6f32ac9768a852a8775c89af515eb8`.
- Scenario: Barbarian Hero versus Skeleton Warrior, Skeleton Archer, and Skeleton Warlock.
- Constraint: no free Haste, invisibility, or healing consumables.

### Combat Summary

The Hero moved to the central door, opened it, entered Frenzy/Rage, advanced to just outside melee, Dodged, and ended turn. This deliberately gave the enemy a real first turn.

Enemy round 1 applied pressure without stale-command waste: Warrior moved adjacent and attacked, Archer acted, and Warlock dealt fire damage. The Hero returned at `42/50 HP`.

Round 2 validated the Barbarian action flow: Reckless Attack, main Greataxe attack, Extra Attack, movement into a two-enemy position, and Frenzied Strike. Warrior died, but Warlock survived the missed Frenzied Strike. Enemy round 2 punished the exposed Hero: Archer hit for reduced piercing damage and Warlock used Thunderwave for thunder damage. The Hero returned at `34/50 HP`.

Round 3 killed Warlock with main attack plus Extra Attack and wounded Archer with Frenzied Strike. Archer missed on the final enemy turn. Round 4 ended the encounter with one Greataxe hit.

Final state: Hero `34/50 HP`; Warrior `-5/31 HP`; Warlock `-1/17 HP`; Archer `-2/24 HP`.

### What This Validated

- The epoch-cache fix worked in a full external-enemy game: enemy `command.ack.stale` count was `0`.
- The enemy did not poll `/available-actions`; available-action debug endpoint hits were `0`.
- Enemy pressure is materially better than the trivial old behavior:
  - Warrior moved and attacked in melee;
  - Archer used ranged attacks;
  - Warlock used damaging area spells;
  - total Hero HP damage was `16`.
- The Barbarian Codex surface is usable:
  - Frenzy/Rage;
  - Dodge setup;
  - Reckless Attack;
  - main attack;
  - Extra Attack;
  - movement after attacks;
  - Frenzied Strike.
- The recommendation layer correctly prioritized free Extra Attack over bonus Frenzied Strike after the main attack.

### What Stayed Weak Or Clunky

- Adjacent legal `Open Door` was still not recommended over more movement toward the door.
- After action and bonus action were spent, leftover adjacent movement still kept `meaningful_commands_remaining=True` and recommended shuffling between adjacent squares.
- Free consumables kept appearing in recommendations even when they were intentionally excluded from the challenge measurement.
- Stream churn remains high: `75` snapshots, `36` observation subscriptions, `15` resync starts, and `15` resync completions for one short Barbarian fight.
- SSE disconnect cleanup remains noisy: `26` pending `BoundedSubscription.get()` task warnings in this run.
- Enemy AI still lacks side-level focus-fire coordination. It is locally tactical, not yet a squad.

### Integrated Improvement

After the game, the Codex turn-summary recommendation layer was patched:

- legal adjacent `Open Door` / `Close Door` rows now enter the recommendation shortlist as real tactical interactions;
- `Open Door` beats additional movement toward the same door;
- when epoch economy is present and the operator-facing meaningful-command flag is false, the recommendation shortlist is empty;
- adjacent leftover movement after attacks/bonus are spent no longer pretends a useful command remains.

This directly addresses the two operator mistakes the live run forced me to override manually: opening an already-adjacent door and ending turn instead of pointless adjacent shuffling.

### Measurement

- Raw saved JSON responses: `28`.
- Total raw saved response characters: `837952`.
- Largest raw response: `129308` characters from the final `/state` snapshot.
- Largest game-tool response: `24314` summary characters after enemy round 2.
- Largest compact turn summary: `24314` characters, roughly `6079` estimated tokens.
- Largest normalized action row count: `257`.
- Final compact turn summary: `5792` characters, roughly `1448` estimated tokens.
- Final action row count: `0`, because the encounter ended.
- Turn/action payloads with embedded metrics: `20`.
- Enemy agent telemetry: `82` events.
- Enemy policy ticks: `7`.
- Enemy command results: `13`.
- Enemy stale command acks: `0`.
- Enemy resync starts/completions: `15 / 15`.
- Enemy selected-policy reasons:
  - `move_toward_visible_enemy` `1`;
  - `attack_visible_enemy` `4`;
  - `cast_visible_area_spell` `2`.
- Enemy damage to Hero HP: `16`.

### Verification

- `uv run pytest tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_recommends_legal_adjacent_open_door_before_door_movement tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_does_not_count_adjacent_leftover_movement_as_meaningful tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_counts_non_adjacent_closing_movement_as_meaningful tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_filters_out_of_reach_melee_recommendations tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_warns_for_free_consumables_not_free_doors -q`
- `uv run pyright ai/codex_tools/client.py tests/manual/test_30_codex_takeover_tools.py`

### Next Targets

- Reduce subjective runtime stream churn. The enemy decision path is functionally better, but 75 snapshots for this fight is too much.
- Add focus-fire coordination across monster turns so the enemy side has a shared target plan.
- Fix subjective observation memory so line-of-sight changes produce remembered/last-known living enemies.
- Demote or hide balance-sensitive free consumables from top recommendations during challenge measurement.

## 2026-07-03 - Subjective Runtime Command Sync Churn Fix

### Problem

The Barbarian validation run proved the enemy AI was no longer wasting turns on stale epochs, but it still produced `75` snapshot requests, `36` observation subscriptions, and `15 / 15` resync start/completion events in one short fight. That made the enemy side feel slower than the policy actually was.

The command follow-up path had a specific bug: after submitting a command, it opened the observation SSE stream from the current cursor. The stream correctly sent a normal `sync` envelope before replaying frames. `SubjectiveRuntime._wait_for_command_followup()` interpreted that `sync` as a resync condition, fetched a fresh snapshot immediately, and returned before consuming the streamed `COMMAND_RESULT` plus follow-up `DECISION_EPOCH`.

### Integrated Improvement

- `sync` during command follow-up is now informational.
- The runtime continues waiting for the command-result frame and the paired follow-up epoch or epoch-clear frame.
- `evicted` still forces resync.
- Cursor gaps still force resync through normal frame application.
- The fix is pinned by a regression that simulates `sync -> command_result -> decision_epoch` and fails if `resync()` is called.

This is an enemy-AI runtime improvement, not only an operator-interface improvement: the default external enemy policy should now spend less time reloading snapshots after each accepted command.

### Verification

- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py::test_runtime_command_followup_ignores_initial_stream_sync tests/manual/test_36_seamless_subjective_runtime.py::test_accepted_command_publishes_result_then_followup_epoch tests/manual/test_35_subjective_external_ai.py::test_external_ai_normal_path_does_not_fetch_available_actions -q`
- `uv run pyright ai/subjective/runtime.py tests/manual/test_36_seamless_subjective_runtime.py`

### Next Targets

- Re-run a fresh challenge game and confirm snapshot/resync counters drop.
- Separately clean up abandoned SSE subscription pending-task warnings if they remain after the command-follow-up fix.
- Add side-level focus-fire coordination so the enemy team chooses a shared wounded target instead of acting as three local policies.

## 2026-07-03 - Enemy Policy V5 Attack Row Fit And Epoch-Clear Correction

### Correction

The goal is not only to make Codex easier to operate. The default monster AI must also become more challenging and more inspectable. Interface improvements are useful only when they help us measure or drive better play; they are not a substitute for improving the enemy policy.

### Playtest Evidence

- Artifact folder: `/tmp/dnd_syncfix_validation_rerun`.
- Scenario: Barbarian Hero versus Skeleton Warrior, Skeleton Archer, and Skeleton Warlock.
- Result: Hero won in round 4 at `37/50 HP`.
- Raw saved JSON payloads: `40`.
- Total saved JSON characters: `981445`.
- Largest saved payload: `47856` characters.
- Largest compact turn summary: `24286` characters, roughly `6072` estimated tokens.
- Largest action-choice count: `251`.
- Operator calls: `37`.
- Estimated HTTP requests: `103`.
- Enemy `/available-actions` debug endpoint hits: `0`.
- Enemy policy ticks: `12`.
- Enemy command results: `14`.
- Enemy stale command acks: `3`.
- Enemy resync starts/completions: `3 / 3`.
- Enemy selected-policy reasons:
  - `attack_visible_enemy`: `6`;
  - `move_toward_visible_enemy`: `3`;
  - `cast_opening_controlled_support_spell`: `2`;
  - `end_turn`: `1`.

The run proved the game no longer hung after the command-followup sync fix, and the Codex watch surface woke only on real ready turns. It also proved there was still a server-side enemy-runtime bug: a late epoch-clear for the previous actor could erase the newer active actor epoch on the server. The next snapshot then minted a fresh `snapshot` epoch for the same actor/round/turn, making a perfectly reasonable command look stale.

### Integrated Runtime Fix

Server-side epoch clear is now target-aware:

- an epoch-clear frame still enters the subjective stream;
- the server only clears `_current_epoch_by_session` when the clear belongs to the same actor as the stored current epoch;
- a clear for actor A no longer discards actor B's newer epoch;
- this prevents false-stale retries after turn handoff.

This is runtime work, but it directly matters to enemy challenge because stale retries make monsters slow and can waste pressure windows.

### Integrated Enemy Policy Fix

The external enemy policy is now `2026-07-03.enemy-policy-v5-attack-row-fit`.

The policy already had these challenge branches:

- safe enemy AoE;
- opening controlled support such as multi-target `Necrotic Bless`;
- visible offensive spells;
- weapon focus pressure;
- support fallback;
- safe movement toward visible enemies;
- Dash fallback;
- adjacent door use;
- movement toward closed doors;
- Dodge fallback.

The missing piece in weapon fallback was row quality. `_attack_visible_enemy()` ranked the target but not the attack row itself, so two legal attacks against the same target could fall back to row order. That is bad for challenge: an archer can appear to choose a melee row at range, or an adjacent combatant can choose a ranged row when a melee row is cleaner.

The v5 policy now ranks attack rows by:

- target HP pressure;
- target distance;
- melee/ranged fit at that distance;
- stable row tie-breaker.

Concretely:

- far target plus legal ranged attack beats a melee fallback row;
- adjacent target plus legal melee attack beats a ranged row;
- weakest visible target is still preserved as the first-order pressure rule.

### Verification

- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py::test_epoch_clear_for_previous_actor_does_not_invalidate_current_server_epoch tests/manual/test_36_seamless_subjective_runtime.py::test_late_epoch_clear_does_not_clear_next_actor_epoch tests/manual/test_36_seamless_subjective_runtime.py::test_published_epoch_survives_control_cursor_advancement -q`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py::test_attack_policy_prefers_ranged_row_when_target_is_not_adjacent tests/manual/test_35_subjective_external_ai.py::test_attack_policy_prefers_melee_row_when_target_is_adjacent tests/manual/test_35_subjective_external_ai.py::test_attack_policy_focuses_weakest_visible_enemy tests/manual/test_35_subjective_external_ai.py::test_caster_policy_prefers_visible_offensive_spell tests/manual/test_35_subjective_external_ai.py::test_external_policy_snapshot_identifies_current_enemy_policy -q`
- `uv run pyright server/event_server.py ai/external/policy.py ai/external/policy_source.py ai/external/state.py tests/manual/test_35_subjective_external_ai.py tests/manual/test_36_seamless_subjective_runtime.py tests/manual/test_29_external_ai_subprocess.py`

### Next Targets

- Run a fresh challenge game with enemy policy v5 loaded and confirm stale command acks drop to `0`.
- Measure whether snapshot/resync counts fall after the target-aware epoch clear.
- Add side-level focus-fire coordination across monster turns.
- Keep improving enemy behavior from playtest evidence, not only the Codex operator surface.

## 2026-07-03 - Sorcerer V5 Challenge Playtest And Spacing Recommendation Fix

### Setup

- Artifact folder: `/tmp/dnd_sorcerer_v5_iteration`.
- Server: isolated `127.0.0.1:8023`, stopped after the run.
- Enemy policy: `external_melee_behavior_tree`, version `2026-07-03.enemy-policy-v5-attack-row-fit`.
- Enemy policy SHA-256: `bc26a7c3e5914b4895979b2b0feaf4c26e7f83e19baecce4739cfad8d276efdf`.
- Scenario: Sorcerer Hero versus Skeleton Warrior, Skeleton Archer, and Skeleton Warlock.
- Constraint: no free consumable exploitation and no opening alpha-strike intended to delete the enemy caster before the monster side could act.

### Combat Summary

The Hero won in round 5 at `27/37 HP`. All three skeletons died:

- Skeleton Warrior: `-6/31 HP`;
- Skeleton Archer: `-9/24 HP`;
- Skeleton Warlock: `-12/17 HP`.

The enemy policy v5 validation was successful on the runtime side:

- stale command acks: `0`;
- resync starts/completions: `0 / 0`;
- `/available-actions` debug hits: `0`;
- accepted command acks: `26`;
- enemy policy ticks: `20`;
- enemy command results: `25`.

Enemy selected-policy reasons:

- `move_toward_visible_enemy`: `14`;
- `attack_visible_enemy`: `6`;
- `cast_visible_enemy_spell`: `6`;
- `dash_toward_visible_enemy`: `4`;
- `cast_opening_controlled_support_spell`: `2`;
- `open_adjacent_door`: `2`;
- `end_turn`: `6`;
- `end_turn_after_offense`: `5`.

### Measurements

- High-level tool calls: `43`.
- Estimated HTTP requests: `113`.
- Saved JSON payloads: `43`.
- Total saved JSON characters: `1757063`.
- Largest saved payload: `470022` characters (`enemy_agent_events`).
- Largest game-tool payload: `83492` characters (`watch`).
- Largest compact turn summary: `48324` characters, roughly `12081` estimated tokens.
- Largest normalized action-choice count: `635`.
- Snapshot requests in server log: `133`.
- Observation subscribe requests in server log: `102`.
- Pending `BoundedSubscription.get()` task warnings: `85`.

### Findings

The v5 enemy-runtime direction worked. The earlier false-stale and command-followup resync problems did not reappear. Enemy behavior was active throughout the fight: the skeleton side moved, opened doors, supported, dashed, attacked, and used Warlock spell pressure.

The Codex operator surface still created two obvious Sorcerer mistakes:

- Before contact, the recommendation list prioritized `Quickened Spell`, then `Invisibility`, then `Quickened Spell` again. This spent setup economy before there were visible enemies or hostile rows to exploit.
- After the Hero spent meaningful offensive economy, the recommendation list repeatedly prioritized movement adjacent to Skeleton Warrior. For a Sorcerer, that is the wrong default; if no hostile row remains, spacing or ending the turn is usually better than walking into melee.

The run also reconfirmed the open observation-memory issue: after some line-of-sight changes, living enemies could disappear from the immediate visible surface, causing frontier exploration recommendations while a surviving Warlock still existed elsewhere.

### Integrated Improvement

The Codex turn recommendation layer now treats caster spacing as a first-class recommendation policy:

- `Quickened Spell` is no longer recommended before contact, while already active, or when no hostile row exists to exploit.
- `Invisibility` is no longer recommended as a pre-contact default or when the actor is already invisible.
- A spellcaster adjacent to a visible enemy with no hostile row can still treat retreat as a meaningful command.
- Spellcaster retreat rows now outrank adjacent closing rows in the recommendation shortlist.
- Melee-oriented actors keep the previous closing behavior, so Barbarian and skeleton melee pressure are not flattened into caster kiting behavior.

### Verification

- `uv run pytest tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_does_not_recommend_precontact_quickened_or_invisibility tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_prefers_retreat_over_adjacency_for_spellcaster_without_offense tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_counts_non_adjacent_closing_movement_as_meaningful tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_does_not_count_adjacent_leftover_movement_as_meaningful tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_surfaces_retreat_moves_after_shove -q`
- `uv run pyright ai/codex_tools/client.py tests/manual/test_30_codex_takeover_tools.py`

### Next Targets

- Run the next full game from the skeleton side to keep the Barbarian/Sorcerer/skeleton rotation honest.
- Fix observation memory so living enemies that leave line of sight become remembered/last-known instead of disappearing.
- Fix SSE subscription cleanup; pending task warnings are now the clearest remaining runtime noise.
- Add side-level focus-fire coordination for the enemy AI.

## 2026-07-03 - Skeleton Side Versus External Barbarian And No-Contact AI V6

### Setup

- Artifact folder: `/tmp/dnd_barbarian_skeleton_side_iteration`.
- Server: isolated `127.0.0.1:8024`, stopped after the run.
- Arena: `/simulation/start-codex-monsters?character_class=barbarian`.
- Controlled side: Codex-controlled Skeleton Warrior, Skeleton Archer, and Skeleton Warlock.
- Opponent: external-AI Barbarian Hero.
- Starting enemy policy: `2026-07-03.enemy-policy-v5-attack-row-fit`.

### First Failure

The first skeleton-side driver attempt exposed a serious operator-surface loop. After the Skeleton Warrior or Warlock reached the door, the compact turn surface kept making `Open Door` / `Close Door` look like progress after the visible Hero had already been found and the actor had no real combat/movement follow-up.

The scratch driver hit its 80-command cap without finishing:

- `78` commands were door interactions;
- the active actor stayed on the skeleton side;
- the Barbarian never got a real follow-up turn;
- the subjective surface alternated between visible Hero and no visible enemy as the door opened and closed.

This proved the interface needed to make end-turn boundaries explicit, not merely list every legal row.

### Integrated Interface Fix

The Codex turn-summary recommendation layer now treats pressure turns differently:

- useful movement toward a visible enemy outranks objectward movement when both are present;
- `Dodge` is recommended as the defensive fallback when visible enemies exist but no attack, spell, or progress movement is available;
- `Open Door` and `Close Door` are not recommended while a visible enemy is already present;
- door rows no longer count as operator-meaningful progress under visible-enemy pressure;
- when `economy_summary.meaningful_commands_remaining` is false, agents should end the turn rather than falling back to raw interaction rows.

The validation driver was updated to respect that boundary. This mirrors how an LLM operator should use the compact surface: recommendations and economy summary are the decision surface; raw interactions are supporting detail.

### Completed Validation Run

After the fix, the same skeleton-side scenario completed. The skeleton side defeated the external Barbarian in round 7.

Final state:

- Hero: `-1/50 HP`, dead at `(5, 7)`.
- Skeleton Warrior: `22/31 HP`, alive at `(4, 6)`.
- Skeleton Archer: `0/24 HP`, dead at `(6, 7)`.
- Skeleton Warlock: `17/17 HP`, alive at `(14, 4)`.

Skeleton-side command reasons:

- `recommendation:attack Hero`: `10`;
- `recommendation:keep distance from Hero`: `7`;
- `summary_end_turn_boundary`: `15`;
- `move_toward_object`: `10`;
- `recommendation:defensive action under pressure`: `3`;
- `recommendation:close toward Hero`: `3`;
- `recommendation:finish low-HP Hero`: `2`;
- single-use support/opening reasons for `Necrotic Bless`, opening the door, and wounded-Hero pressure.

The end-turn boundary was not cosmetic: it is what stopped the door loop and let the external Hero act.

### Enemy AI Finding And V6 Improvement

The external Barbarian Hero still showed an enemy-AI weakness on its first turn. Its first policy tick had no visible enemies, no known closed doors, and many legal movement rows, yet the behavior tree selected `end_turn`. This is the old no-contact failure mode: if nothing is visible and no door has been perceived, the actor can stand still even though exploration movement is legal.

The external enemy policy is now `2026-07-03.enemy-policy-v6-no-contact-exploration`.

New policy behavior:

- when no visible enemy and no known closed door exists;
- and legal movement rows exist;
- choose an exploratory movement row instead of ending the turn;
- prefer rows that make real movement progress, avoid known hazards when possible, and move toward the centroid of legal movement targets.

This keeps the policy intentionally simple, but it removes the worst no-contact passivity without adding another server query or objective-state leak.

### Measurements

- High-level skeleton-side commands: `56`.
- Saved JSON payloads: `176`.
- Total saved JSON characters: `7328411`.
- Largest saved payload: `245579` characters (`hero_agent_events`).
- Largest watch payload: `103650` characters.
- Largest compact turn summary: `37941` characters, roughly `9486` estimated tokens.
- Largest normalized action-choice count: `227`.
- External Hero agent telemetry events: `97`.
- External Hero selected-policy reasons:
  - `attack_visible_enemy`: `6`;
  - `move_toward_visible_enemy`: `1`;
  - `end_turn`: `1`.
- Final-run server-log slice:
  - snapshots: `249`;
  - observation subscribes: `72`;
  - command executes: `55`;
  - command end-turns: `29`;
  - debug `/available-actions` hits: `0`;
  - pending subscription task warnings: `87`.

### Remaining Friction

- The subjective memory problem is still visible: closing the door can make the living Hero disappear from the immediate enemy surface instead of becoming a remembered/last-known target.
- The compact surface still produces large payloads in multi-entity skeleton turns; `37k` summary characters is better than raw actions but still too much for repeated play.
- Stream lifecycle cleanup remains a real runtime issue. The completed run still produced `87` pending subscription task warnings.
- The skeleton side won, but it required direct Codex control. The default policy still needs squad-level coordination and should be re-tested with v6 controlling the monster side directly.

### Verification

- `uv run pytest tests/manual/test_29_external_ai_subprocess.py::test_behavior_tree_explores_when_no_enemy_or_closed_door_is_known tests/manual/test_29_external_ai_subprocess.py::test_behavior_tree_ends_turn_without_enemy_door_or_movement tests/manual/test_29_external_ai_subprocess.py::test_behavior_tree_moves_toward_known_closed_door tests/manual/test_29_external_ai_subprocess.py::test_behavior_tree_opens_adjacent_door_when_no_enemy_is_visible tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_recommends_legal_adjacent_open_door_before_door_movement tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_prefers_dodge_over_door_toggle_under_pressure tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_does_not_treat_door_toggle_as_progress_under_pressure -q`
- `uv run pyright ai/codex_tools/client.py ai/external/policy.py ai/external/policy_source.py tests/manual/test_29_external_ai_subprocess.py tests/manual/test_30_codex_takeover_tools.py`

### Next Targets

- Run the next full game with v6 as the default monster AI against a Barbarian or Sorcerer hero, without Codex manually controlling the skeleton side.
- Fix observation memory so living enemies blocked by doors remain remembered/last-known.
- Fix SSE subscription cleanup and snapshot pressure.
- Add side-level focus-fire coordination so the skeleton team shares target pressure rather than acting as three local policies.

## 2026-07-03 - Default Monster AI V6 Attempt And Route-Aware Enemy Policy V7

### Setup

- Artifact folder: `/tmp/dnd_barbarian_v6_default_monsters`.
- Server: isolated `127.0.0.1:8025`.
- Arena: `/simulation/start-human?character_class=barbarian`.
- Controlled side: Codex-controlled Barbarian Hero through takeover.
- Opponent: default external monster AI controlling Skeleton Warrior, Skeleton Archer, and Skeleton Warlock.
- Starting enemy policy: `2026-07-03.enemy-policy-v6-no-contact-exploration`.

### What Failed

This run did not complete. The first driver attempt hit a `100` command cap in round 1 because harmless utility rows kept the Codex operator surface alive:

- `Extinguish Torch`: `48` selections;
- `Ignite Torch`: `47` selections;
- only a few real frontier moves happened before the loop.

After light-toggle/free-consumable cleanup and Shove classification, the run progressed far enough for the default monsters to act repeatedly, but the long rerun timed out before a winner was produced.

The enemy telemetry was the important evidence:

- `71` enemy policy ticks;
- selected reasons were almost entirely movement, dash, doors, and support;
- `0` actual attack or direct damage spell selections in the collected slice;
- visible Hero distances often sat around `35-50 ft`;
- legal entity-action rows were often `0`, while legal movement rows were large (`65-175` rows);
- command-result latency was still high, with observed p50 around `5077 ms` and a max around `21047 ms`.

The monsters were not simply blind. They often had the Hero visible, but the movement policy used direct Manhattan progress. On a map with water, blockers, and corridors, that can select local moves that look closer without actually improving the route to contact.

### Integrated Operator-Surface Cleanup

The Codex turn-summary layer now treats common utility rows as non-progress:

- light toggles are not recommended;
- light toggles do not keep `meaningful_commands_remaining` alive;
- free consumables are not recommended as generic progress;
- hostile `Shove` rows are classified with pressure actions instead of support rows.

This is not enough by itself, but it removes one source of fake action churn during playtests.

### Integrated Enemy AI V7 Improvement

The external enemy policy is now `2026-07-03.enemy-policy-v7-route-aware-pursuit`.

New reduced-state facts:

- remembered enemies: seen/remembered non-controlled living entities with last-known positions;
- known tiles: subjective walkable terrain, walking cost, and hazard flags.

New policy behavior:

- when moving toward a visible enemy, remembered enemy, or closed door, first score legal movement targets by route cost through known walkable tiles;
- allow a temporary step that does not reduce Manhattan distance if it advances along the known route;
- keep the old direct-distance movement rule as fallback when no known route exists;
- pursue remembered enemy positions before generic no-contact exploration;
- keep closed-door movement/opening priority ahead of remembered pursuit.

This is still subjective and does not query objective map state. The monster can only route through tiles delivered by its observation stream.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py tests/manual/test_29_external_ai_subprocess.py -q`
- `uv run pyright ai/external/state.py ai/external/policy.py ai/codex_tools/client.py tests/manual/test_35_subjective_external_ai.py tests/manual/test_29_external_ai_subprocess.py`

### Next Targets

- Run a fresh default-monster playtest with policy v7 loaded from process start.
- Add a measured smoke that proves a monster behind water/blockers reaches attack range faster than v6.
- Add side-level focus-fire coordination so monster turns share target pressure instead of acting as isolated policies.
- Reduce command-result latency and snapshot/subscription churn before larger batches.

## 2026-07-03 - Sorcerer Versus Default Monster AI V7

### Setup

- Artifact folder: `/tmp/dnd_sorcerer_v7_default_monsters`.
- Server: isolated `127.0.0.1:8026`.
- Arena: `/simulation/start-human?character_class=sorcerer`.
- Controlled side: Codex-controlled Sorcerer Hero through takeover.
- Opponent: default external monster AI controlling Skeleton Warrior, Skeleton Archer, and Skeleton Warlock.
- Enemy policy: `2026-07-03.enemy-policy-v7-route-aware-pursuit`.

### Result

The Hero won. Final state:

- Hero: `28/37 HP`, alive at `(3, 1)`.
- Skeleton Warrior: `-31/31 HP`, dead at `(3, 2)`.
- Skeleton Archer: `-21/24 HP`, dead at `(2, 6)`.
- Skeleton Warlock: `-25/17 HP`, dead at `(6, 7)`.

The fight ended quickly in game terms, but the driver timed out because the Codex `watch` call kept waiting after `encounter_active=false`.

### Measurements

- Turn summaries captured: `13`.
- Executed Codex commands: `9`.
- Accepted end-turn commands: `2`.
- Largest compact turn summary: `50222` characters, roughly `12556` estimated tokens.
- Largest action-choice count: `653`.
- Server-log slice:
  - snapshots: `105`;
  - observation subscribes: `90`;
  - agent-events requests/stream frames: `327`;
  - command executes: `43`;
  - command end-turns: `14`;
  - debug `/available-actions` hits: `0`;
  - pending subscription task warnings: `75`.
- Enemy policy trace:
  - `20` policy ticks;
  - `23` command results;
  - selected reasons included `attack_visible_enemy: 2`, `cast_visible_enemy_spell: 1`, `move_toward_visible_enemy: 10`, `dash_toward_visible_enemy: 2`, `open_adjacent_door: 1`, and support/end-turn rows;
  - command-result latency remained high, with p50 around `2731 ms` and max around `24178 ms`.

### Friction Found

The Sorcerer still won because Fireball dominated the encounter, but the agent surface had several weak points:

- `watch` had no terminal encounter-ended return path, so the driver blocked after the fight was already over.
- Empty recommendations with `meaningful_commands_remaining=true` caused fallback execution of weak utility rows:
  - `Invisibility (Level 2)` before contact;
  - `2SP->Slot L1` conversion;
  - free healing potion use after the action was spent.
- Sorcerer turns remain too large. The worst captured summary was `50k` characters and `653` choices.
- The enemy AI attacked and cast this time, but command latency is still too slow for pleasant iteration.

### Integrated Interface Fix

The Codex tool client now treats completed encounters as terminal:

- `watch()` checks `/game/status` before opening another observation stream;
- when `encounter_active` is false, it returns `status="encounter_ended"` immediately;
- the live ended server validated this in about `14 ms`.

The turn-summary economy boundary was also tightened:

- non-recommended support rows no longer keep `meaningful_commands_remaining` true;
- sorcery-point/spell-slot conversion rows no longer count as automatic tactical progress;
- support spells such as pre-contact Invisibility are still visible in `support_actions`, but no longer force fallback execution when they are not recommended.

### Verification

- Live ended-server watch check returned `{"status": "encounter_ended", "event": "encounter_ended"}` in `13.73 ms`.
- `uv run pytest tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_support_only_invisibility_does_not_keep_turn_alive tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_sorcery_conversion_only_does_not_keep_turn_alive tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_does_not_recommend_precontact_quickened_or_invisibility tests/manual/test_30_codex_takeover_tools.py::test_codex_watch_returns_when_encounter_already_ended tests/manual/test_30_codex_takeover_tools.py::test_codex_watch_waits_past_non_ready_frames_by_default -q`

### Next Targets

- Rotate back to skeleton-side control for the next playtest.
- Reduce Sorcerer spell-summary payload size; `50k` characters is still too high.
- Fix SSE subscription cleanup and command latency; terminal watch is fixed, but stream churn remains.
- Add measured route-v7 smoke around water/blockers.

## 2026-07-03 - Skeleton Side Versus External Barbarian After V7

### Setup

- Artifact folder: `/tmp/dnd_skeletons_v7_vs_external_barbarian`.
- Server: isolated `127.0.0.1:8027`.
- Arena: `/simulation/start-codex-monsters?character_class=barbarian`.
- Controlled side: Codex-controlled Skeleton Warrior, Skeleton Archer, and Skeleton Warlock.
- Opponent: external-AI Barbarian Hero.
- Enemy/external policy: `2026-07-03.enemy-policy-v7-route-aware-pursuit`.

### Result

The skeleton side won, and the terminal `watch` fix worked: the driver received `encounter_ended` instead of hanging after victory.

Final state:

- Hero: `-1/50 HP`, dead at `(11, 5)`.
- Skeleton Warrior: `14/31 HP`, alive at `(12, 5)`.
- Skeleton Archer: `-2/24 HP`, dead at `(10, 4)`.
- Skeleton Warlock: `17/17 HP`, alive at `(8, 8)`.

### Measurements

- Driver duration: `254.97 s`.
- Codex-side commands: `38`.
- Executed commands: `24`.
- End-turn commands: `14`.
- Largest compact turn summary: `22601` characters, roughly `5651` estimated tokens.
- Largest action-choice count: `153`.
- Server-log slice:
  - snapshots: `173`;
  - observation subscribes: `68`;
  - agent-events requests/stream frames: `229`;
  - command executes: `42`;
  - command end-turns: `28`;
  - debug `/available-actions` hits: `0`;
  - pending subscription task warnings: `56`.
- External Hero AI trace:
  - `10` policy ticks;
  - `16` command results;
  - selected reasons included `attack_visible_enemy: 6`, `explore_no_contact: 1`, `dash_toward_visible_enemy: 1`, `move_toward_visible_enemy: 1`, and `end_turn: 1`;
  - command-result latency remained high, with p50 around `7183 ms` and max around `28936 ms`.

### Friction Found

The recommendations were much better than the earlier door-loop runs, but one skeleton-side gap remained:

- Skeleton Warlock had spent its action, had no retreat moves, but had useful movement rows toward the visible Hero.
- Because Warlock is classified as a spacing-preferring caster, the recommendation builder refused useful closing moves unless no spacing preference existed.
- The driver therefore used raw `fallback:useful_moves` three times.

### Integrated Interface Fix

The movement recommendation builder now handles this case:

- if an actor prefers spacing and a retreat row exists, retreat still wins;
- if an actor prefers spacing but no retreat row exists, useful movement toward the visible enemy can be recommended;
- this removes the observed Warlock `fallback:useful_moves` path without weakening the caster-retreat rule.

### Verification

- `uv run pytest tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_prefers_retreat_over_adjacency_for_spellcaster_without_offense tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_recommends_caster_closing_when_no_retreat_exists tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_support_only_invisibility_does_not_keep_turn_alive tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_sorcery_conversion_only_does_not_keep_turn_alive tests/manual/test_30_codex_takeover_tools.py::test_codex_watch_returns_when_encounter_already_ended -q`

### Next Targets

- Rotate to Barbarian Hero next.
- Reduce stream churn and command latency; this remains the largest runtime problem.
- Add measured route-v7 smoke around water/blockers.
- Add side-level focus-fire coordination across monster turns.

## 2026-07-03 - Enemy Ranged Spacing Policy Fix

### Why This Matters

The enemy-AI goal is not only a Codex/operator-interface goal. The autonomous monsters also need to make the game more challenging on their own.

The specific gap fixed here was tactical spacing after an action: a ranged or caster monster could spend its main pressure action, still have movement left, and then walk toward the visible hero because the generic pursuit branch was the next behavior-tree fallback. That made warlocks and archers easier to punish.

### Integrated Enemy Policy Fix

The external enemy reducer now carries the action-economy values from decision epochs:

- actions remaining;
- bonus actions remaining;
- movement remaining;
- extra attacks remaining.

The behavior tree now has a ranged-spacing branch before generic visible-enemy pursuit:

- ranged/caster actors that have spent their pressure action try to move farther from the nearest visible enemy;
- if no farther safe movement row exists, they hold range instead of walking closer;
- ordinary melee actors still close after spending their action.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py::test_ranged_enemy_retreats_after_spending_pressure_action tests/manual/test_35_subjective_external_ai.py::test_ranged_enemy_holds_spacing_after_spending_action_when_no_retreat_exists tests/manual/test_35_subjective_external_ai.py::test_melee_enemy_still_closes_after_spending_action tests/manual/test_35_subjective_external_ai.py::test_caster_policy_prefers_visible_offensive_spell tests/manual/test_35_subjective_external_ai.py::test_enemy_policy_dashes_when_visible_enemy_exists_but_no_move_progresses -q`
- `uv run pyright ai/external/state.py ai/external/policy.py tests/manual/test_35_subjective_external_ai.py`

### Next Targets

- Run the next Barbarian Hero playtest against this updated autonomous enemy spacing policy.
- Add side-level focus-fire coordination across monster turns.
- Keep stream churn and command latency as a separate runtime performance track.

## 2026-07-03 - Barbarian Hero Dash Fix Validation

### Setup

- Failed artifact folder: `/tmp/dnd_barbarian_v8_vs_spacing_enemies`.
- Validation artifact folder: `/tmp/dnd_barbarian_v8_dash_fix_validation`.
- Arena: `/simulation/start-human?character_class=barbarian`.
- Controlled side: Codex-controlled Barbarian Hero through runtime takeover of `faction=heroes`.
- Opponent: autonomous external skeleton AI with the current ranged-spacing policy.

### Failure Before Fix

The first Barbarian run hit the step limit with the encounter still active:

- Status: `step_or_time_limit`.
- Commands: `90`.
- Torch toggles: `56` total (`28` extinguish, `28` ignite).
- Free potion fallbacks: `2`.
- Final state: Hero alive at `50/50 HP`, Skeleton Warrior dead, Skeleton Archer and Skeleton Warlock still alive.

The saved turn surface showed the root cause:

- no visible enemies;
- no movement rows;
- no recommendations;
- `meaningful_commands_remaining=true`;
- interactions still included Dash, Disengage, Dodge, Reckless Attack, torch toggles, and free consumables.

This made raw fallback choose utility rows even though no tactical recommendation existed.

### Integrated Interface Fix

The Codex turn summary now treats utility/basic interactions more carefully:

- Dash is explicitly recommended when no-contact exploration stalls with zero movement and an action remains.
- Frenzy and Reckless Attack are recommended only when there is living-enemy pressure context.
- End Rage does not keep a turn alive.
- Torch toggles and free consumables do not keep a spent turn alive.

### Validation Result

The fresh validation run completed normally:

- Status: `encounter_ended`.
- Result: Barbarian Hero victory.
- Commands: `26`.
- Torch toggles: `0`.
- Dash recommendations: `2`.
- Final Hero state: `19/50 HP`, alive at `(4, 7)`.
- All skeletons dead.

Enemy behavior was also more interesting than the earlier trivial loops:

- Skeleton Warlock used Invisibility.
- Skeleton Warlock used Burning Hands twice.
- External enemy policy reasons included `cast_opening_controlled_support_spell`, `cast_controlled_support_spell`, `cast_visible_area_spell`, `dash_toward_visible_enemy`, `open_adjacent_door`, and `move_toward_closed_door`.

### Measurements

Validation server-log slice:

- snapshots: `98`;
- observation subscriptions: `55`;
- agent-events requests/stream frames: `408`;
- command executes: `43`;
- command end-turns: `12`;
- debug `/available-actions` hits: `0`;
- pending subscription warnings: `213`.

External enemy trace:

- policy trace rows: `55`;
- command results: `29`;
- command-result latency p50: `3661 ms`;
- command-result latency max: `21948 ms`.

### Verification

- `uv run pytest tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_light_toggles_do_not_keep_turn_alive tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_recommends_dash_for_no_contact_exploration_when_movement_spent tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_end_rage_and_light_toggles_do_not_keep_spent_turn_alive tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_prefers_dodge_over_door_toggle_under_pressure tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_does_not_treat_door_toggle_as_progress_under_pressure tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_explains_barbarian_self_actions -q`
- `uv run pyright ai/codex_tools/client.py tests/manual/test_30_codex_takeover_tools.py`

### Next Targets

- Rotate to Sorcerer next.
- Reduce frontier wandering before first contact.
- Fix stream cleanup and command latency; validation still produced many pending subscription warnings.

## 2026-07-03 - Enemy Tactical Ability And Spacing Identity

### Why This Matters

The enemy-AI work is part of the goal, not a side concern. The autonomous skeletons should make the standard arena more challenging even when Codex or a human controls the hero.

The latest Sorcerer trace showed a policy gap: the Skeleton Archer could reach a good 25 ft engagement band but then keep walking into contact because the behavior tree only understood damaging spells and weapon attacks as pressure. Enemy-targeted utility rows such as Mark Target existed in the legal affordance set but were not selected by the policy.

### Integrated Enemy Policy Fix

The external enemy behavior tree now has an enemy-targeted tactical ability branch before generic movement:

- known tactical abilities such as Mark Target are selected against visible enemies;
- duplicate tactical effects are skipped when the target already has the matching condition;
- Skeleton Archer, Skeleton Warlock, and other named ranged/caster roles preserve spacing even when the current legal row set does not expose a ranged attack row;
- ranged/caster pursuit now approaches to a spacing band instead of voluntarily rushing adjacent when a better band-preserving move exists.

### Validation Result

Artifact folder: `/tmp/dnd_enemy_policy_v10_validation`.

The validation used a passive Sorcerer Hero through runtime takeover so the autonomous monster side could act for three enemy phases.

Observed enemy policy choices:

- Skeleton Archer moved to the closed door, opened it, used Mark Target on the Hero at 25 ft, then fired `Attack_RANGED_MAIN` from range.
- Skeleton Warlock opened with Necrotic Bless on the monster group, then later used Eldritch Blast instead of only walking.
- Skeleton Warrior continued behaving as the melee closer.

Enemy policy reason counts from the run:

- `attack_visible_enemy`: 5
- `move_toward_visible_enemy`: 4
- `cast_visible_enemy_spell`: 2
- `end_turn`: 2
- `move_toward_closed_door`: 1
- `open_adjacent_door`: 1
- `use_visible_enemy_tactical_ability`: 1
- `cast_opening_controlled_support_spell`: 1
- `dash_toward_visible_enemy`: 1

### Measurements

- Enemy policy ticks: `18`.
- Enemy command results: `24`.
- Command-result latency p50: `4184.01 ms`.
- Command-result latency max: `23224.01 ms`.
- Server-log slice:
  - snapshots: `61`;
  - observation subscriptions: `78`;
  - agent-events requests/stream frames: `336`;
  - command executes: `32`;
  - command end-turns: `21`;
  - debug `/available-actions` hits: `0`;
  - pending subscription warnings: `53`.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q`
- `uv run pytest tests/manual/test_29_external_ai_subprocess.py -q`
- `uv run pyright ai/external/policy.py ai/external/policy_source.py tests/manual/test_35_subjective_external_ai.py`

### Next Targets

- Continue improving the autonomous enemy side, especially side-level focus fire across skeleton turns.
- Reduce stream churn and command latency.
- Rotate to a full Sorcerer Hero run next and compare whether the improved archer/warlock pressure changes the difficulty curve.

## 2026-07-03 - Skeleton-Side Close-Door Loop Fix And Sorcerer Pressure Check

### Why This Matters

The goal is both sides of the AI product: autonomous enemies must become harder to play against, and the Codex/operator surface must stop causing silly choices when we take over a side manually.

The enemy-policy v8 work was real: autonomous monsters now use Mark Target, support, ranged spacing, and route-aware movement better than the older trivial melee policy. The follow-up skeleton-side validation then exposed a separate operator-surface bug: when no enemy was visible, an adjacent `Close Door` row looked like exploration progress and could keep a turn alive forever.

### Integrated Interface Fix

The Codex turn summary now treats door interactions asymmetrically:

- `Open Door` can still be recommended when no enemy is visible, because it can reveal new map state.
- `Close Door` is never recommended as no-contact exploration progress.
- a lone `Close Door` row no longer makes `meaningful_commands_remaining` true.
- Dash and frontier/objectward movement stay responsible for exploration progress.

This is not an enemy-policy change, but it is directly relevant to using Codex to play the skeleton side during AI challenge tests.

### Validation Result

Failure artifact: `/tmp/dnd_skeletons_v9_vs_external_sorcerer`.

- The first skeleton-side run hit the step limit.
- The recommendation driver alternated `Open Door` and `Close Door` after opening the doorway.
- Reason counts included `34` open-door recommendations and `34` close-door recommendations.

Fixed validation artifact: `/tmp/dnd_skeletons_v9_close_door_fix_validation`.

- Status: `encounter_ended`.
- Commands: `41`.
- Door recommendations after the fix:
  - `open the adjacent door`: `1`
  - `close the adjacent door`: `0`
- Attack recommendations after first contact: `10`.
- Useful movement recommendations toward the Hero: `3`.
- Frontier exploration recommendations: `13`.

The external Sorcerer ultimately won. Final visible state from the skeleton-side watch:

- Hero: `37 / 37 HP`, alive at `(7, 2)`.
- Skeleton Archer: dead at `-13 / 24 HP`.
- Skeleton Warlock: dead at `-4 / 17 HP`.
- Skeleton Warrior: dead at `-5 / 31 HP`.

That is the important gameplay conclusion: the latest enemy policy applies more pressure than before, but Sorcerer still has too much room to clear the encounter with Fireball once contact is established.

### Measurements

Skeleton-side validation:

- Commands: `41`.
- Command statuses:
  - `executed`: `31`;
  - `accepted`: `10`.
- Largest turn summary: `41922` characters.
- Largest action-choice count in a turn payload: `130`.
- Server-log slice:
  - snapshots: `178`;
  - observation subscriptions: `47`;
  - agent-events requests/stream frames: `168`;
  - command executes: `45`;
  - command end-turns: `20`;
  - debug `/available-actions` hits: `0`;
  - pending subscription warnings: `64`.

External Sorcerer policy in the same run:

- Policy ticks: `8`.
- Reason counts:
  - `cast_visible_area_spell`: `5`;
  - `cast_controlled_support_spell`: `1`;
  - `explore_no_contact`: `1`;
  - `end_turn`: `1`.
- Command-result latency p50: `8199.96 ms`.
- Command-result latency max: `46977.86 ms`.

### Verification

- `uv run pytest tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_recommends_legal_adjacent_open_door_before_door_movement tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_prefers_dodge_over_door_toggle_under_pressure tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_does_not_treat_door_toggle_as_progress_under_pressure tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_does_not_recommend_no_contact_close_door_loop tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_close_door_alone_does_not_keep_no_contact_turn_alive tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_recommends_dash_for_no_contact_exploration_when_movement_spent -q`
- `uv run pyright ai/codex_tools/client.py tests/manual/test_30_codex_takeover_tools.py`

### Next Targets

- Continue enemy-AI challenge work, not just interface cleanup.
- Add side-level focus-fire coordination so monsters pressure the same vulnerable target or protect key casters.
- Reduce Sorcerer dominance after doorway contact; Fireball wiped all three skeletons while Hero stayed at full HP in this validation.
- Fix SSE subscription cleanup and command latency; this validation still produced `64` pending subscription warnings and a `46977.86 ms` max external command-result latency.

## 2026-07-03 - Barbarian V9 Surface Cleanup And Exposed-Target Pressure

### Why This Matters

This run rotated back to the Barbarian side after the skeleton-side Sorcerer validation. The goal is still two-sided: the Codex/operator surface must be clean enough to drive turns, and the autonomous monster policy must make the arena meaningfully dangerous.

Artifact folder: `/tmp/dnd_barbarian_v9_enemy_policy_v8`.

### Playtest Result

Setup:

- Hero: Codex-controlled Barbarian via runtime takeover of the `heroes` faction.
- Enemies: current external skeleton AI.
- Driver: recommendation-first, falling back only if the turn summary had no recommendation.

Result:

- Status: `encounter_ended`.
- Hero victory.
- Hero final HP: `44 / 50`.
- Final enemy state: all three skeletons dead.
- Commands: `26`.
- Fallback commands: `0`.
- Debug `/available-actions` hits: `0`.

Hero-side recommendation counts:

- `frontier_moves: explore frontier`: `7`
- `interactions: dash to continue exploration`: `2`
- `interactions: enable advantage before melee pressure`: `3`
- `interactions: enter frenzy for bonus-action pressure`: `1`
- `useful_moves: move adjacent to Skeleton Warlock`: `1`
- `useful_moves: move adjacent to Skeleton Archer`: `1`
- attacks against skeletons: `7`
- end-turn boundaries: `4`

Enemy-side trace:

- `move_toward_visible_enemy`: `7`
- `dash_toward_visible_enemy`: `3`
- `attack_visible_enemy`: `3`
- `move_toward_closed_door`: `2`
- `use_visible_enemy_tactical_ability`: `1`
- support/control/dodge/end-turn events made up the rest.

The important gameplay finding is blunt: the Barbarian won too comfortably. The improved enemies reached the fight and used Mark Target/support, but only landed enough pressure to leave the Hero at `44 / 50 HP`.

### Agent-Surface Friction

The driver did not need any fallback commands, which is good. The rough part was the pre-contact surface:

- the no-contact opener still included `useful_moves` rows;
- those rows could carry the recommendation reason `move toward a visible enemy` even though `living_enemy_count` was `0`;
- exploration did remain mostly in `frontier_moves`, but the false useful-move section was misleading noise.

### Integrated Interface Fix

`useful_moves` now requires at least one known living enemy. No-contact movement is separated into:

- `frontier_moves`;
- `objectward_moves`;
- `last_known_enemy_moves`.

Live surface validation after the patch:

- `living_enemy_count`: `0`
- `useful_move_count`: `0`
- `frontier_move_count`: `8`
- `objectward_move_count`: `10`
- useful-move recommendations: `0`

### Integrated Enemy-Policy Fix

Enemy policy is now `2026-07-03.enemy-policy-v9-exposed-target-pressure`.

The behavior tree has a new exposed-target pressure branch before opening support. A visible target carrying an advantage-granting or vulnerability-like condition now draws immediate offense before slow setup.

Initial exposed conditions:

- `Reckless Attacking`
- `Marked`
- `Guiding Bolt Marked`
- `Prone`
- `Restrained`
- `Paralyzed`
- `Stunned`
- `Unconscious`

This is not Barbarian-specific. The policy reads known subjective conditions and treats the target as a high-value pressure opportunity.

### Measurements

Original playtest:

- largest turn summary: `25315` characters;
- largest estimated summary tokens: `6329`;
- largest action-choice count: `246`;
- snapshots: `144`;
- observation subscriptions: `90`;
- agent-events requests/stream frames: `416`;
- command executes: `62`;
- command end-turns: `22`;
- pending subscription warnings: `80`.

Surface validation after the interface fix:

- summary characters: `13843`;
- estimated summary tokens: `3461`;
- action-choice count: `203`;
- useful moves: `0`;
- useful-move recommendations: `0`.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q`
- `uv run pytest tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_surfaces_frontier_moves_before_door_is_known tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_surfaces_remembered_enemy_search_objectives tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_recommends_dash_for_no_contact_exploration_when_movement_spent -q`
- `uv run pyright ai/external/policy.py ai/external/policy_source.py tests/manual/test_35_subjective_external_ai.py`
- `uv run pyright ai/codex_tools/client.py tests/manual/test_30_codex_takeover_tools.py`

### Next Targets

- Rotate to Sorcerer next.
- Validate whether v9 exposed-target pressure actually increases damage when the Hero uses Reckless Attack or is Marked.
- Add side-level focus-fire and caster protection; v9 still does not coordinate the skeleton side as a squad.
- Fix stream churn and pending subscription cleanup; this run still produced `90` observation subscriptions and `80` pending subscription warnings.

## 2026-07-03 - Sorcerer V10 Enemy Ranged Reposition Pressure

### Playtest Finding

Artifact folder: `/tmp/dnd_sorcerer_v10_enemy_policy_v9`.

The Sorcerer run reached round 11 before the driver timeout, and it exposed a real enemy-policy weakness rather than only a Codex-interface issue.

The important enemy trace was the Skeleton Warlock:

- visible target: `Hero`, repeatedly around `25 ft`;
- legal entity pressure rows: `0`;
- legal position rows: more than `120`;
- selected command: `Dodge`;
- follow-up selected command: `End Turn`;
- total `dodge_under_pressure` selections in the run: `28`.

That is not challenging behavior. A ranged/caster monster with sight but no legal spell or attack row should try to recover a line or angle before becoming defensive.

### Integrated Enemy-Policy Fix

Enemy policy is now `2026-07-03.enemy-policy-v10-ranged-reposition-pressure`.

The behavior tree has a new `reposition_for_visible_pressure` branch before door/no-contact/dodge fallbacks. It applies only when:

- a visible enemy exists;
- the actor is a ranged/caster identity;
- no known attack/spell row can pressure the visible enemy;
- a safe movement row can preserve or improve spacing.

This preserves the previous archer/warlock rule that they should not blindly rush adjacent. If the only movement rows collapse spacing, the older Dodge fallback still applies. If a lateral or backward movement row exists, the enemy now moves first so the next epoch can reveal whether a legal shot opens.

### Remaining Separate Finding

The same run also showed a Codex-side subjective memory gap: when enemies disappeared from the hero surface late in combat, the Sorcerer had no remembered or last-known enemy objective while the encounter remained active. That is tracked separately because it is an agent subjective-state problem, not the enemy policy patch above.

### Measurements

- enemy policy ticks: `29`;
- `dodge_under_pressure`: `28`;
- `move_toward_visible_enemy`: `20`;
- direct attacks: `4`;
- offensive spell casts: `4`;
- command executes: `70`;
- command end-turns: `36`;
- snapshots: `203`;
- observation subscriptions: `122`;
- agent-events requests/stream frames: `484`.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q`
- `uv run pyright ai/external/policy.py ai/external/policy_source.py tests/manual/test_35_subjective_external_ai.py`

### Next Targets

- Run a fresh Sorcerer Hero playtest against enemy policy v10 and compare Dodge count, damage taken, and encounter duration against this timed-out v9 run.
- Fix subjective observation memory so living enemies blocked by doors become remembered or last-known instead of disappearing from the decision surface.
- Add side-level focus-fire and caster protection; v10 still makes per-actor decisions rather than squad plans.

## 2026-07-03 - Skeleton V11 Explicit End Turn And Epoch Readiness

### Playtest Setup

Artifact folders:

- failed slice: `/tmp/dnd_skeleton_v11_vs_ai_hero`;
- fixed validation: `/tmp/dnd_skeleton_v14_followup_actor_validation`.

Rotation:

- Codex controlled the skeleton side.
- The automated opponent was a Barbarian Hero driven by the external AI runtime.
- The run used the current event-first subjective stream and decision epochs; `/available-actions` remained unused.

### Finding

The first skeleton-side run reproduced a familiar but sharper failure:

- total commands: `80`;
- raw fallback commands: `67`;
- `Open Door` / `Close Door` executions: `53`;
- encounter still active at the command cap.

The turn summaries actually knew that the current actor had no useful command:

- `meaningful_commands_remaining=false`;
- warning: `no affordable non-end-turn command remains`;
- no hostile rows;
- no useful movement;
- no movement remaining.

But the recommendation list was empty, so a simple controller fell through into raw `interactions` and toggled the door. Empty recommendations were too ambiguous for an agent loop.

A second related bug appeared after the first patch: accepted command follow-ups could request a summary for the previous actor after the turn had advanced. The fresh snapshot already had the next actor's epoch, but forcing the old entity UUID produced a no-row, no-recommendation summary.

### Integrated Fix

The Codex control surface now makes end-turn explicit:

- `TurnSummaryResult.recommendations` includes `special|End Turn|index=0` when no meaningful command remains.
- `CodexToolClient.execute()` can execute that special row through the normal execute path.
- `attach()` and `watch()` only report `ready` when the session owns the active actor and a current decision epoch exists.
- accepted command follow-ups summarize the current active actor, not the actor that just finished acting.
- non-actionable follow-ups with no epoch are suppressed so callers return to `watch()`.

### Validation

Fixed validation slice:

- total command records: `20`;
- recommendation-driven executes: `20`;
- explicit End Turn recommendations executed: `7`;
- no-recommendation end-turn fallbacks: `0`;
- frame-without-ready count: `0`;
- door toggle executions: `0`;
- `/available-actions` hits: `0`.

Remaining runtime problem:

- snapshots: `68`;
- observation subscriptions: `34`;
- agent-events requests/stream frames: `108`;
- pending subscription warnings: `32`.

The interface fix worked, but stream/subscription cleanup is still too noisy.

### Verification

- `uv run pytest tests/manual/test_30_codex_takeover_tools.py::test_codex_execute_accepts_special_end_turn_row tests/manual/test_30_codex_takeover_tools.py::test_codex_execute_drops_follow_up_without_epoch tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_does_not_treat_door_toggle_as_progress_under_pressure tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_close_door_alone_does_not_keep_no_contact_turn_alive tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_support_only_invisibility_does_not_keep_turn_alive tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_sorcery_conversion_only_does_not_keep_turn_alive -q`
- `uv run pyright ai/codex_tools/client.py tests/manual/test_30_codex_takeover_tools.py`
- live validation summary: `/tmp/dnd_skeleton_v14_followup_actor_validation/000_play_summary.json`

### Next Targets

- Rotate back to Barbarian Hero next.
- Fix SSE subscription cleanup and command latency; the skeleton validation still showed `34` subscriptions and `32` pending subscription warnings in only `20` commands.
- Fix subjective observation memory so living enemies blocked by doors become remembered or last-known instead of disappearing from the decision surface.

## 2026-07-03 - Barbarian V16 Enemy Reposition Throttle And Dead-Actor Advancement

### Playtest Setup

Artifact folders:

- completed pre-fix reference: `/tmp/dnd_barbarian_v15_enemy_v10_endturn_surface`;
- timed validation slice: `/tmp/dnd_barbarian_v16_enemy_v11_reposition_throttle`.

Rotation:

- Codex controlled the Barbarian Hero through the recommendation-first command surface.
- The opponent side used the default external skeleton AI subprocess.
- The run used decision epochs; `/available-actions` remained unused in the normal path.

### Enemy-AI Finding

The previous Barbarian run confirmed that the default enemy side is being improved, not only the Codex-facing interface. The skeletons reached contact, opened the door, used support/marking, and made attacks, but the ranged/caster recovery branch was still too permissive.

The suspicious enemy behavior was:

- `reposition_for_visible_pressure` appeared as a repeated fallback after the enemy already had the desired spacing band;
- the archer/warlock could spend turns looking busy with movement instead of converting position into threat;
- a real validation run then showed the Archer attacking twice and trying a reposition after being reduced below 0 HP during its own turn.

### Integrated Enemy-Policy Fix

Enemy policy is now `2026-07-03.enemy-policy-v11-ranged-reposition-throttle`.

The `reposition_for_visible_pressure` branch is now narrower:

- it only applies to ranged/caster actors;
- it only applies when a visible enemy exists and no attack/spell pressure row is legal;
- it only fires while the actor is still inside the desired spacing floor;
- the chosen movement must increase distance from the nearest visible enemy.

Once a ranged actor is already at the spacing floor and still has no legal shot, the policy falls through to defensive behavior instead of lateral shuffling.

### Integrated Runtime Fix

The live validation exposed a command/turn boundary bug. An accepted command can return `turn_continues=false` when the actor dies or otherwise cannot continue. The AI command endpoint previously published an epoch clear but did not advance the encounter, leaving the dead actor as `active_entity_uuid`.

The command endpoint now advances the encounter after an accepted non-continuing action result. If the same session controls the next actor, the existing decision-epoch stream exposes the next actor; otherwise the old session receives an epoch clear.

### Validation

The first live validation slice timed out because it hit the dead-active-actor bug:

- active entity after timeout: Skeleton Archer;
- Archer HP in command result: `-8`;
- encounter still active;
- current epoch: `null`;
- repeated watcher subscriptions followed because the human/Codex side was waiting for the monster turn to finish.

The focused regression now proves the fixed boundary without needing a long playtest:

- a command result with `turn_continues=false` advances from the first controlled actor to the second controlled actor;
- the follow-up snapshot contains a valid current epoch for the next actor.

### Verification

- `uv run pytest tests/manual/test_30_codex_takeover_tools.py::test_ai_command_advances_when_accepted_action_ends_actor_turn -q`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py::test_ranged_enemy_repositions_when_visible_enemy_has_no_pressure_row tests/manual/test_35_subjective_external_ai.py::test_ranged_enemy_does_not_shuffle_when_already_spaced_without_pressure_row -q`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q`
- `uv run pyright server/event_server.py ai/external/policy.py ai/external/policy_source.py tests/manual/test_30_codex_takeover_tools.py tests/manual/test_35_subjective_external_ai.py`

### Next Targets

- Rerun the Barbarian Hero rotation on a fresh server after the dead-active-actor fix.
- Continue enemy-AI challenge work: side-level focus fire, caster protection, and better ranged pressure selection.
- Fix SSE subscription cleanup and command latency; the timed validation still produced pending subscription warnings.
- Fix subjective observation memory so living enemies blocked by doors become remembered or last-known instead of disappearing from the decision surface.

## 2026-07-03 - Enemy Policy V12 Follow-Up Kiting

### Finding

The enemy-AI goal is not only about improving the Codex operator interface. The default autonomous monsters also need to become more challenging.

While reviewing the latest Sorcerer validation and the existing ranged/caster tests, I found a mismatch between the behavior tree and the live subprocess loop:

- the policy already had branches for `retreat_from_visible_enemy` and `hold_ranged_spacing`;
- the isolated policy tests proved those branches worked when the action was already spent;
- but `ExternalMeleeAgent.play_current_turn()` ended the monster turn immediately after any offensive command;
- that meant a Warlock or Archer could cast/shoot and then skip the follow-up epoch where leftover movement should have let it kite.

So the enemy AI looked flatter in real games than the policy file suggested.

### Integrated Enemy-AI Fix

Enemy policy/runtime label is now `2026-07-03.enemy-policy-v12-follow-up-kiting`.

The subprocess loop no longer auto-submits `end_turn_after_offense` after attacks, offensive spells, or clean area spells. Instead it now:

- executes the offensive command;
- consumes the streamed command result and follow-up decision epoch;
- continues ticking the behavior tree if the session still has an active epoch;
- lets ranged/caster actors spend leftover movement on `retreat_from_visible_enemy` or end with `hold_ranged_spacing`;
- returns normally if the encounter ended or the active epoch cleared.

This keeps the server authoritative: the agent still only uses streamed decision epochs and never polls `/available-actions`.

### Regression

Added a live-loop regression where a Skeleton Warlock:

1. casts `Eldritch Blast`;
2. receives a follow-up epoch with action spent and movement remaining;
3. retreats away from the visible Hero;
4. then ends turn via `hold_ranged_spacing`.

Before the fix the same test would have produced `cast_visible_enemy_spell` followed by the artificial `end_turn_after_offense`.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py::test_external_agent_uses_follow_up_epoch_after_offense_for_ranged_spacing -q`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py::test_ranged_enemy_retreats_after_spending_pressure_action tests/manual/test_35_subjective_external_ai.py::test_ranged_enemy_holds_spacing_after_spending_action_when_no_retreat_exists tests/manual/test_35_subjective_external_ai.py::test_caster_policy_prefers_visible_offensive_spell -q`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q`
- `uv run pytest tests/manual/test_29_external_ai_subprocess.py -q`
- `uv run pyright ai/external_melee_agent.py ai/external/policy_source.py tests/manual/test_35_subjective_external_ai.py`

### Next Targets

- Run the next full live rotation against v12 and check whether ranged/caster monsters actually kite after offensive turns.
- Continue enemy-AI challenge work: side-level focus fire, caster protection, and better ranged pressure selection.
- Fix SSE subscription cleanup and command latency.

## 2026-07-03 - Barbarian V12 Live Validation And Observation Wait Cleanup

### Playtest Setup

Artifact folder: `/tmp/dnd_barbarian_v12_followup_kiting_validation`.

Rotation:

- Codex controlled the Barbarian Hero through the recommendation-first command surface.
- The opponent side used the default external skeleton AI subprocess.
- Enemy policy/runtime label: `2026-07-03.enemy-policy-v12-follow-up-kiting`.
- The run used decision epochs; `/available-actions` remained unused in the normal path.

### Result

The Barbarian Hero won after `34` executed Hero commands. The final observed Hero state was `40 / 50 HP`.

The important enemy-AI evidence was that v12 worked in a real subprocess, not only in unit tests:

- Skeleton Warrior moved to the known door, opened it, closed to melee, dashed, attacked, and pressured exposed/Reckless Hero turns.
- Skeleton Warlock used `Necrotic Bless`, later cast `Burning Hands`, then consumed the follow-up epoch and selected `reposition_for_visible_pressure` instead of being auto-ended by the wrapper.
- Skeleton Archer used reposition and defensive fallback branches while the Hero chased it.

Enemy selected reasons:

- `move_toward_visible_enemy`: `7`;
- `reposition_for_visible_pressure`: `5`;
- `dodge_under_pressure`: `6`;
- `press_exposed_visible_enemy`: `3`;
- `cast_visible_area_spell`: `1`;
- `cast_opening_controlled_support_spell`: `1`;
- `cast_controlled_support_spell`: `1`;
- `attack_visible_enemy`: `1`;
- `open_adjacent_door`: `1`;
- `move_toward_closed_door`: `1`;
- `dash_toward_visible_enemy`: `2`;
- `end_turn`: `14`.

### Friction

The first driver timed out even though the encounter was still progressing. Resuming the same game completed it quickly, which means the biggest issue was not tactical deadlock but stream/runtime churn.

Measured server log counts for this run:

- snapshots: `182`;
- observation subscriptions: `173`;
- agent event posts/frames: `616`;
- command executes: `86`;
- command end-turns: `34`;
- pending subscription warnings: `179`;
- `/available-actions` hits: `0`.

The largest Hero turn summary was `36,211` characters with `266` normalized choices. That is much better than the largest Sorcerer turns, but still chunky.

### Integrated Runtime Fix

The AI observation SSE route created two child wait tasks per live subscription:

- one waiting on the objective engine event stream;
- one waiting on the session-local control wakeup stream.

The old code cancelled the losing task only after `asyncio.wait()` returned normally. If the client disconnected or the response generator was cancelled while inside the wait, the child `BoundedSubscription.get()` task survived and later produced `Task was destroyed but it is pending!`.

The route now uses a cancellation-safe helper:

- `_first_subscription_envelope()` creates wait tasks;
- returns the first envelope or `None` on timeout;
- always cancels and drains all child tasks in `finally`;
- the observation subscribe route uses that helper for objective/control stream races.

### Verification

- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py::test_observation_subscription_race_cancels_losing_wait_task -q`
- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q`
- `uv run pytest tests/manual/test_28_subjective_observation_stream.py -q`
- `uv run pytest tests/manual/test_30_codex_takeover_tools.py::test_codex_watch_waits_past_non_ready_frames_by_default tests/manual/test_30_codex_takeover_tools.py::test_codex_watch_returns_when_encounter_already_ended -q`
- `uv run pyright server/event_server.py tests/manual/test_36_seamless_subjective_runtime.py`

### Next Targets

- Run the next rotation as Sorcerer or skeleton side after the stream cleanup and compare pending subscription warnings.
- Continue enemy-AI challenge work: side-level focus fire, caster protection, and better ranged pressure selection.
- Reduce stream request count, not only leaked pending tasks.
- Reduce remaining turn-summary payload size for large combat turns.

## 2026-07-03 - Skeleton-Side V13 Route And Ranged Spacing Cleanup

### Playtest Setup

Artifact folder: `/tmp/dnd_skeletons_v13_stream_cleanup_validation`.

Rotation:

- Codex controlled Skeleton Warrior, Skeleton Archer, and Skeleton Warlock through the recommendation-first command surface.
- The opponent side used the default external Sorcerer Hero subprocess.
- The run used decision epochs; `/available-actions` remained unused in the normal path.

### Result

The validation completed in `145.374` seconds with `37` saved turn records. The terminal event was `encounter_ended_watch`.

Server instrumentation after the observation wait cleanup:

- snapshots: `120`;
- observation subscriptions: `57`;
- agent event posts/frames: `152`;
- command executes: `44`;
- command end-turns: `13`;
- pending subscription warnings: `0`;
- `/available-actions` hits: `0`.

The stream cleanup worked: the prior pending-task leak did not recur, and normal agent play still avoided the debug available-actions endpoint.

### Enemy-AI And Control-Surface Findings

The tactical problem was not the stream. It was route and ranged behavior:

- Skeleton Archer repeatedly oscillated during no-contact exploration, mostly `14,7 -> 13,7 -> 14,7`, because generic `frontier_moves` tied with `objectward_moves` and sorted first.
- Wall Torch objects were treated as movement goals, which made no-contact navigation noisier.
- After using Mark Target and Shortbow, Skeleton Archer had no remaining pressure row but the top recommendation was `move adjacent to Hero`. That is the wrong lesson for a ranged actor and would make any policy built on the surface worse.
- The actual external enemy reducer only retained closed doors. Once a door was open, the enemy policy lost the doorway as a route anchor and fell back to generic exploration.

### Integrated Enemy-AI Fix

The real external enemy AI is now at policy version `2026-07-03.enemy-policy-v13-door-anchored-exploration`.

Changes:

- The external reducer carries known door-like objects, not only closed doors.
- The behavior tree has `move_toward_known_open_door` before generic no-contact exploration.
- Open doors remain route anchors after they are opened, so enemies can move toward the chokepoint before wandering.
- The Codex turn-summary scorer now treats names like `Skeleton Archer` as ranged spacing identities.
- Ranged actors with no remaining pressure row prefer `retreat_moves` over adjacent `useful_moves`.
- Door/objectward route moves now outrank generic frontier wandering.
- Static light objects such as `Wall Torch` are filtered out as movement goals, and wall-torch light toggles are treated like other light-only utility rows.

### Verification

- `uv run pytest tests/manual/test_29_external_ai_subprocess.py::test_reducer_extracts_actor_enemies_doors_and_action_rows tests/manual/test_29_external_ai_subprocess.py::test_behavior_tree_moves_toward_known_open_door_before_generic_exploration tests/manual/test_29_external_ai_subprocess.py::test_behavior_tree_explores_when_no_enemy_or_closed_door_is_known -q`
- `uv run pytest tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_prefers_archer_retreat_over_post_attack_adjacency tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_prefers_open_door_route_over_frontier_wander tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_prefers_retreat_over_adjacency_for_spellcaster_without_offense tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_surfaces_moves_toward_known_closed_doors -q`
- `uv run pytest tests/manual/test_29_external_ai_subprocess.py -q`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q`
- `uv run pytest tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_light_toggles_do_not_keep_turn_alive tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_recommends_dash_for_no_contact_exploration_when_movement_spent tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_does_not_recommend_no_contact_close_door_loop tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_surfaces_frontier_moves_before_door_is_known tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_prefers_archer_retreat_over_post_attack_adjacency tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_prefers_open_door_route_over_frontier_wander -q`
- `uv run pyright ai/external/state.py ai/external/policy.py ai/external/policy_source.py ai/codex_tools/client.py tests/manual/test_29_external_ai_subprocess.py tests/manual/test_30_codex_takeover_tools.py`

### Next Targets

- Run a fresh default external skeleton AI game against a human/Codex hero to validate v13 in the actual monster subprocess.
- Continue enemy challenge work: focus fire, caster protection, and smarter target selection across the monster side.
- Reduce stream request count and large turn-summary payloads.

## 2026-07-03 - Sorcerer V14/V15 Frontier And Optional-Object Cleanup

### Playtest Setup

Full-fight artifact folder: `/tmp/dnd_sorcerer_v14_frontier_validation`.

Opening-smoke artifact folder: `/tmp/dnd_sorcerer_v15_frontier_smoke`.

Rotation:

- Codex controlled the Sorcerer Hero through the recommendation-first command surface.
- The opponent side used the default external skeleton AI subprocess.
- The run used decision epochs; `/available-actions` remained unused in the normal path.

### Result

The first Sorcerer validation after v13 exposed a severe navigation bug before combat: the hero was repeatedly sent toward visible healing potions, all through hazardous movement rows, and died to environmental piercing damage before any skeleton acted. That run is preserved at `/tmp/dnd_sorcerer_v13_default_enemy_validation`.

After demoting optional object movement, the full v14 rerun reached combat and completed:

- Hero won at `28 / 37 HP`.
- Skeleton Archer, Warrior, and Warlock were all defeated.
- Enemy AI acted in the real subprocess, not only tests.
- External enemy selected reasons included `move_toward_visible_enemy`, `open_adjacent_door`, `use_visible_enemy_tactical_ability`, `cast_opening_controlled_support_spell`, `attack_visible_enemy`, and `cast_visible_enemy_spell`.
- Server counts: `94` snapshots, `73` observation subscriptions, `306` agent event posts/frames, `40` command executes, `15` command end-turns, `0` `/available-actions` hits, and `0` pending subscription warnings.

### Findings

- Optional floor loot was treated as a tactical object route goal. In the standard arena this made `Potion of Healing` movement beat safe frontier movement and could route through hazards.
- No-contact frontier movement was memoryless inside a variable-length turn. The hero bounced `2,7 -> 2,4 -> 2,7 -> 2,4 -> 2,7` before ending the turn.
- The full v14 fight still had large spellcaster surfaces: max summary `46,619` characters and max action choices `532`.
- The v15 smoke proved the anti-backtracking fix changes the opening to `2,7 -> 2,4 -> 5,4` instead of returning to `2,7`.
- The v15 smoke also exposed the next frontier-quality problem: after Dash the surface explored toward `(5,0)`, which avoids backtracking but is still not a strong map-goal policy for finding the central combat route.

### Integrated Fixes

- Non-door objectward movement now has lower recommendation priority than frontier exploration.
- Hazardous non-door objectward movement is demoted further when no safe path exists.
- Door movement remains high priority as a route anchor.
- Frontier movement now uses recent movement logs to avoid immediately recommending cells the actor just occupied, when another frontier row exists.

### Verification

- `uv run pytest tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_prefers_safe_frontier_over_optional_hazardous_loot tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_surfaces_frontier_moves_before_door_is_known tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_prefers_open_door_route_over_frontier_wander tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_surfaces_moves_toward_known_closed_doors -q`
- `uv run pytest tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_frontier_avoids_same_turn_backtracking tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_prefers_safe_frontier_over_optional_hazardous_loot tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_surfaces_frontier_moves_before_door_is_known tests/manual/test_30_codex_takeover_tools.py::test_codex_turn_summary_prefers_open_door_route_over_frontier_wander -q`
- `uv run pyright ai/codex_tools/client.py tests/manual/test_30_codex_takeover_tools.py`

### Next Targets

- Improve no-contact frontier scoring with map-goal/topology awareness so exploration moves toward likely route openings instead of arbitrary map edges.
- Continue enemy challenge work: focus fire, caster protection, and smarter target selection across the monster side.
- Reduce large Sorcerer turn surfaces by grouping/capping equivalent spells and area centers more aggressively.

## 2026-07-03 - Barbarian V17 Unlinked Epoch Runtime Fix

### Playtest Setup

Failure artifact folder: `/tmp/dnd_barbarian_v16_v13_enemy_validation`.

Passing artifact folder: `/tmp/dnd_barbarian_v17_unlinked_epoch_fix_validation`.

Rotation:

- Codex controlled the Barbarian Hero through the recommendation-first command surface.
- The opponent side used the default external skeleton AI subprocess.
- The run used decision epochs; `/available-actions` remained unused in the normal path.

### Failure Found

The first Barbarian run timed out after `14` Hero commands. The game status showed the encounter still active, with the active entity set to Skeleton Archer and the AI Monsters session owning the turn.

The server log showed the important ordering:

- Skeleton Warlock selected `reposition_for_visible_pressure`.
- That movement became non-continuing and advanced the encounter to Skeleton Archer.
- The server published Skeleton Archer's `turn_start` decision epoch.
- The old Warlock command result then arrived.
- The external runtime waited for a command-linked follow-up epoch and never emitted a Skeleton Archer `policy_tick`.

That is a runtime protocol bug, not a tactics bug: the next actor epoch was real, but it was published by encounter advancement rather than directly by the command-result helper.

### Integrated Runtime Fix

`SubjectiveRuntime._wait_for_command_followup()` now treats the command follow-up as complete when the command-result frame arrives and the local store already contains a newer epoch context.

This covers the event-first ordering where:

1. command A ends actor A's turn;
2. encounter advancement publishes actor B's unlinked turn-start epoch;
3. command A's result frame arrives after that epoch.

The regression test `test_runtime_command_followup_accepts_unlinked_next_actor_epoch` preserves that exact order and fails if the runtime tries to keep reading the stream after result plus newer epoch context.

### Passing Result

The fixed v17 rerun completed in `149.068` seconds with `23` Hero commands. The terminal event was `encounter_ended_watch`.

Hero won at `5 / 50 HP`, which is a good challenge signal: the skeleton side is now dangerous enough to nearly kill a Barbarian instead of merely moving around.

Server instrumentation:

- snapshots: `133`;
- observation subscriptions: `67`;
- agent event posts/frames: `290`;
- command executes: `46`;
- command end-turns: `17`;
- pending subscription warnings: `0`;
- stream closes/evictions/resyncs: `0`;
- `/available-actions` hits: `0`.

Enemy selected reasons:

- `press_exposed_visible_enemy`: `6`;
- `end_turn`: `7`;
- `move_toward_visible_enemy`: `2`;
- `reposition_for_visible_pressure`: `2`;
- `use_visible_enemy_tactical_ability`: `1`;
- `cast_visible_area_spell`: `1`;
- `attack_visible_enemy`: `1`.

### Remaining Friction

- The no-contact opening still needed four `frontier_moves` and one Dash before combat stabilized. The route was better than the previous potion/hazard failure, but it is still not a high-level map-goal planner.
- Barbarian turn summaries peaked at `23,172` characters and `314` normalized choices. That is lower than Sorcerer, but still more surface than an operator or model should have to read for straightforward melee turns.
- The enemy side is threatening, but still lacks side-level focus fire and protection logic. It pressures exposed targets well, but each monster still reasons locally rather than as a coordinated side.

### Verification

- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py::test_runtime_command_followup_accepts_unlinked_next_actor_epoch -q`
- `uv run pyright ai/subjective/runtime.py tests/manual/test_36_seamless_subjective_runtime.py`

### Next Targets

- Run the next rotation as skeleton-side control or Sorcerer, not Barbarian again.
- Improve no-contact frontier scoring with map-goal/topology awareness.
- Continue enemy challenge work with side-level focus fire, caster protection, and target selection.
- Reduce melee turn-summary payloads by grouping repeated weapon rows and less useful movement candidates.

## 2026-07-03 - Skeleton V18/V19 Door Anchor Boundary

### Playtest Setup

Failure artifact folder: `/tmp/dnd_skeletons_v18_vs_sorcerer_validation`.

Passing smoke artifact folder: `/tmp/dnd_skeletons_v19_door_anchor_smoke`.

Rotation:

- Codex controlled the skeleton side through the hot takeover tool surface.
- The opponent was an external Sorcerer Hero using the normal subjective-runtime AI.
- The goal was enemy-AI quality: make monsters keep progressing after route doors have done their job.

### Failure Found

The v18 full run ended with the external Sorcerer Hero winning at `29 / 37 HP`. The important failure was not the loss by itself; it was wasted enemy tempo before contact.

The skeleton recommendation counts showed `39` selected `objectward_moves:move toward Door` commands. The trace repeatedly alternated around the already-open central doorway:

- Skeleton Warrior moved through `7,7`, `6,7`, and `6,6` instead of pushing exploration/contact.
- Skeleton Warlock bounced between `7,7` and `7,6`.
- Skeleton Archer also kept receiving door-anchored rows after the open door was no longer a useful objective.

This was a policy bug: closed doors should be tactical route objectives, and distant open doors can still be route anchors, but an open doorway that the actor has already reached should not keep beating frontier movement.

### Integrated Enemy-AI Fix

`TurnObjectMoveSummary` now carries `actor_object_distance_ft`, so door policy can distinguish approaching a route anchor from already occupying that route anchor.

Object-directed movement now behaves as:

- known closed doors keep high priority;
- distant open doors remain useful route anchors;
- open door movement at/adjacent to a doorway already reached by the actor is demoted below frontier exploration;
- same-turn open-door backtracking cells are filtered from objectward movement when another option exists.

This keeps the desirable route-opening behavior while removing the door magnet that made enemies waste turns.

### Passing Smoke Result

The v19 smoke completed in `89.576` seconds with `23` skeleton-side commands. The external Sorcerer Hero still won, ending at `33 / 37 HP`, and all skeletons died.

The enemy behavior changed in the intended way:

- objectward door commands dropped from `39` in v18 to `4` in v19;
- frontier commands rose to `5`;
- all commands were accepted;
- `/available-actions` hits stayed at `0`;
- there were `0` pending subscription warnings, `0` tracebacks, and `0` server errors.

Representative sequence:

- Skeleton Warlock cast `Necrotic Bless`, moved to the closed door, opened it, then switched to frontier movement.
- Skeleton Warrior and Skeleton Archer used the opened doorway as a route anchor once, then moved into frontier/contact instead of bouncing around the door.
- The Archer later used `Mark Target`, made a ranged attack, and retreated instead of moving adjacent.

### Remaining Friction

- The external Sorcerer Hero still punished clustered skeletons with Fireball. That is the next enemy challenge issue: side-level formation/spread and anti-AoE pressure.
- Door routing is better, but the map-goal planner is still primitive. Frontier movement progresses, but it does not yet reason about high-value route corridors, cover, firing lanes, or group positioning.
- The external Hero runtime emitted one stream eviction and two resync starts during the smoke. It recovered cleanly, but this remains runtime noise worth tracking.

### Verification

- `uv run pytest tests/manual/test_30_codex_takeover_tools.py -q -k "known_closed_doors or open_door_route or reaching_open_door_anchor or hazardous_loot or frontier_avoids_same_turn_backtracking or frontier_moves_before_door"`
- `uv run pytest tests/manual/test_30_codex_takeover_tools.py -q -k "open_door or closed_doors or frontier"`
- `uv run pyright ai/codex_tools/client.py ai/codex_tools/contracts.py tests/manual/test_30_codex_takeover_tools.py`

### Next Targets

- Continue enemy challenge work with side-level formation/spread so skeletons do not donate all bodies to Fireball.
- Improve no-contact frontier scoring with route topology, firing lanes, and likely enemy corridors.
- Keep rotating: next validation should be Sorcerer-side or Barbarian-side against the default enemy AI, then skeleton-side again after formation logic.
- Reduce Codex tool snapshot churn so hot takeover behaves more like the seamless subjective runtime.

## 2026-07-03 - Enemy Policy V14 Anti-AoE Spread

### Why This Is Enemy-AI Work

The active goal is not just to make the Codex operator interface easier. The default enemy side itself needs to become a better videogame opponent.

The v19 smoke confirmed a concrete challenge gap: even after door routing improved, the external Sorcerer Hero still won at `33 / 37 HP` because clustered skeletons kept offering clean Fireball value. That is a monster-policy problem, not only an observation/UI problem.

### Integrated Enemy-AI Fix

The external behavior tree now has an anti-AoE spread branch for ranged/caster monsters.

The branch applies only when:

- the actor is a ranged/caster identity;
- the actor has already spent its main pressure action;
- the actor is still near another living controlled ally;
- a legal movement row can increase ally spacing;
- the movement does not collapse the actor below its desired ranged band.

This means a Skeleton Archer or Skeleton Warlock can now cast or shoot, then use leftover movement to avoid standing in a Fireball-shaped pack. Melee monsters are not affected by this branch and still close for pressure.

Enemy policy is now `2026-07-03.enemy-policy-v14-anti-aoe-spread`.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "ranged_enemy_spreads or collapsing_below_spacing or ranged_enemy_retreats_after_spending or ranged_enemy_holds_spacing or melee_enemy_still_closes or caster_policy_prefers_visible_offensive_spell"`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q`
- `uv run pytest tests/manual/test_29_external_ai_subprocess.py -q`
- `uv run pytest tests/manual/test_30_codex_takeover_tools.py -q -k "external_policy_source_endpoint or watch_stream_heartbeats"`
- `uv run pyright ai/external/policy.py ai/external/policy_source.py tests/manual/test_35_subjective_external_ai.py`

### Next Targets

- Run a fresh Sorcerer-side validation against default skeleton AI v14 and compare clean area-spell hits against v13/v19.
- Continue enemy challenge work with side-level focus fire and caster protection.
- Improve no-contact frontier scoring with route topology, firing lanes, and likely enemy corridors.
- Reduce Codex tool snapshot churn so hot takeover behaves more like the seamless subjective runtime.

## 2026-07-03 - Enemy Policy V15 And Arena Diversity

### What Was Missing

The validation loop had not yet used enough of the implemented content. Most live runs were still variations on Sorcerer, Barbarian, and the standard Skeleton Warrior / Archer / Warlock arena. That was useful for fixing the subjective runtime, door routing, ranged spacing, and anti-AoE behavior, but it risks overfitting the enemy policy to one doorway and one monster party.

The simulator already has richer content available: goblins, goblin archers, generic casters, skeleton variants, class heroes, potions, scrolls, water, difficult terrain, spike zones, directional doors, wall strips, torches, and levers. Those should be sampled by validation fixtures before we keep tuning enemy behavior.

### V15 Enemy-AI Finding

The v14 Sorcerer validation completed with the Hero winning at `10 / 37 HP`. It exposed a policy bug: `spread_from_allies_after_pressure` never fired. After a ranged/caster monster spent its main pressure action, the next decision epoch could contain zero affordable attack/spell rows. The v14 spread branch required a visible pressure row, so the Archer/Warlock sometimes fell through to movement toward the Hero and re-created Fireball geometry.

Enemy policy v15 removes that pressure-row gate for actors that already spent their primary action. Ranged/caster monsters can now use leftover movement to spread, retreat, or hold spacing even when the follow-up epoch no longer lists the spent attack or spell row.

The v15 smoke showed the intended branches in live traces:

- `spread_from_allies_after_pressure`: selected `2` times;
- `hold_ranged_spacing`: selected `12` times;
- `retreat_from_visible_enemy`: selected `10` times;
- `/available-actions` hits stayed at `0`;
- server errors and tracebacks stayed at `0`.

The same run also exposed unresolved runtime noise: the trace log contained repeated `resync` telemetry and the final probe found an inconsistent active-turn state, so this is not a final stability victory. The temp validation servers on ports `8052` and `8053` were stopped.

### Integrated Arena Catalog

Added `dnd.scenarios.ai_validation_arenas` as an opt-in validation catalog, not a NeuroClient/default-arena change.

The catalog currently contains:

- `standard_skeleton_doors`: the current skeleton trio behind the closed standard door, with darkness, water, difficult terrain, spike zone, torches, trap lever, and potions.
- `goblin_water_skirmish`: a level 5 archer Fighter against a goblin skirmisher, goblin archer with scenario-local Nimble Escape, and a generic caster across water and difficult terrain.
- `skeleton_anti_aoe_split`: a level 5 Sorcerer against the skeleton trio split across an open field to catch clustering regressions.
- `caster_crossfire`: a level 5 Barbarian against a frontline skeleton, archer, and caster through an already-open doorway.
- `item_resource_gauntlet`: a level 5 archer Fighter carrying wands, scrolls, a Greater Invisibility potion, and a weapon coat against mixed skeleton, goblin, and caster pressure.
- `double_door_dark_hunt`: a level 5 Barbarian in a dark three-room arena split by two closed directional doors, with enemies initially out of sight.
- `arcane_device_control`: a level 5 Sorcerer near a central environmental Fireball cannon and floor potion against mixed skirmisher, archer, and caster pressure.

The point is to let future AI loops sample different map factors and actor kits without rewriting the live game setup or silently changing the player-facing arena.

### V16 Arena Diversity Slice

Expanded the validation catalog from four arenas to seven without changing the default simulator path or the underlying monster factories. The new fixtures deliberately sample item-backed actions, charged objects, repeated door navigation, darkness, floor pickups, mixed monster factions, and environmental spell devices.

This is meant to fight enemy-policy overfitting: the next AI loops can rotate through standard door contact, water routing, spread anti-AoE, caster crossfire, item-rich decisions, multi-door exploration, and environmental-object control instead of only replaying the same skeleton doorway.

### V17 Validation Rotation Harness

Added `ai.validation_harness`, a typed runner surface for the validation catalog. The harness does three small but important things:

- fetches the live `/simulation/ai-validation-arenas` catalog;
- builds a deterministic schedule that alternates Hero-side validation with `codex_monsters` monster-side slots;
- starts scheduled rows through `/simulation/start-ai-validation` without creating a second gameplay path.

The default eight-slot schedule covers all seven current validation arenas while keeping the recurring focus cycle anchored on Sorcerer Hero, monster side, Barbarian Hero, monster side, skirmish/ranged Hero, monster side, resource Hero, and environmental-object Hero. This is intentionally a harness step rather than a gameplay claim: it makes the next playtest loop repeatable instead of manually selecting endpoints from memory.

The HTML dashboard now surfaces validation arena coverage as a top metric card using the JSON ledger, so fixture/harness work is visible without being misclassified as a completed playtest.

### V18 Validation Arena Expansion

Expanded the opt-in validation catalog from seven arenas to eleven. This is directly aimed at the overfitting risk from tuning enemy AI against one familiar skeleton doorway.

New arenas:

- `skeleton_mark_focus_fire`: high-AC shield Fighter against skeleton Warrior, Archer, and Warlock roles, centered on Mark Target and focus-fire support behavior.
- `buff_consumable_ambush`: Barbarian against monsters carrying haste, greater invisibility, and Hold Person scroll pressure, so buff/consumable rows stay visible during enemy-policy tuning.
- `forced_movement_hazard_bridge`: Barbarian near water and spike-zone terrain with Thunderwave-capable monsters, so movement, forced movement, and hazard valuation can be measured separately.
- `line_aoe_corridor`: Sorcerer and mixed enemies aligned on a corridor-like lane, so Lightning Bolt, Magic Missile target sets, friendly-fire, and formation scoring get explicit coverage.

The standard NeuroClient arena remains unchanged. These fixtures live behind `/simulation/start-ai-validation` and the typed `ai.validation_harness` schedule. A short eight-slot schedule still alternates Hero-side and monster-side validation, while an eleven-slot schedule now reaches every current arena exactly once.

### Server Validation Surface

Added explicit server routes for the catalog:

- `GET /simulation/ai-validation-arenas` lists validation specs, tags, map notes, and expected pressure.
- `POST /simulation/start-ai-validation?arena_id=...&mode=human_hero` starts a validation arena with a human/Codex-capable Hero and external-AI monsters.
- `POST /simulation/start-ai-validation?arena_id=...&mode=codex_monsters` starts a validation arena with an external-AI Hero and Codex-controlled monsters.

This keeps `/simulation/start-human` and the NeuroClient default arena untouched while giving self-play and debugging a real rotated scenario entry point.

### Live Crossfire Smoke

Smoke artifact folder: `/tmp/dnd_ai_validation_caster_crossfire_smoke_v2`.

The first crossfire smoke exposed a fixture bug: the Barbarian had no lit torch, saw no enemies, and used `explore_no_contact` repeatedly. The validation hero factories now give heroes the same lit torch assumption used by the normal arena, and the crossfire test asserts the hero has at least one visible enemy at start.

The corrected smoke started:

`POST /simulation/start-ai-validation?arena_id=caster_crossfire&mode=codex_monsters`

Result:

- start status: `waiting_for_ai`;
- external Hero: `Validation Barbarian`;
- after the external Hero turn, active actor was `Validation Crossfire Guard`;
- selected enemy-policy reasons from the external Hero trace:
  - `move_toward_visible_enemy`: `1`;
  - `attack_visible_enemy`: `2`;
  - `end_turn`: `1`;
- combat log:
  - Barbarian moved `25 ft` to `(7, 7)`;
  - hit `Validation Crossfire Guard` for `16`;
  - hit `Validation Crossfire Guard` again for `12`;
  - ended turn;
- `/available-actions` hits: `0`;
- server errors: `0`;
- tracebacks: `0`;
- `resync` telemetry mentions: `8`.

This is the first useful proof that the new arena catalog is not just pure fixture data: it can drive the live server, spawn the external process, and put the game on a Codex-controlled monster turn.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q`
- `uv run pytest tests/manual/test_29_external_ai_subprocess.py -q`
- `uv run pytest tests/manual/test_37_ai_validation_arenas.py -q`
- `uv run pytest tests/manual/test_38_ai_validation_server_start.py -q`
- `uv run pyright ai/external/policy.py ai/external/policy_source.py tests/manual/test_35_subjective_external_ai.py`
- `uv run pyright dnd/scenarios/ai_validation_arenas.py tests/manual/test_37_ai_validation_arenas.py`
- `uv run pyright server/event_server.py dnd/scenarios/ai_validation_arenas.py tests/manual/test_38_ai_validation_server_start.py`
- `uv run pyright dnd/scenarios/ai_validation_arenas.py tests/manual/test_37_ai_validation_arenas.py tests/manual/test_38_ai_validation_server_start.py`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q`
- `uv run pyright ai/validation_harness.py tests/manual/test_39_ai_validation_harness.py`
- `uv run pytest tests/manual/test_37_ai_validation_arenas.py -q`
- `uv run pytest tests/manual/test_38_ai_validation_server_start.py -q`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q`
- `uv run pyright dnd/scenarios/ai_validation_arenas.py ai/validation_harness.py tests/manual/test_37_ai_validation_arenas.py tests/manual/test_38_ai_validation_server_start.py tests/manual/test_39_ai_validation_harness.py`

### Next Targets

- Run the extended eleven-arena validation schedule through live external AI and Codex-monster smokes.
- Continue enemy challenge work against the new arenas: Mark Target focus fire, buff/consumable valuation, forced movement near hazards, and line/AoE geometry.
- Investigate the v15 smoke's repeated resync telemetry and inconsistent final active-turn ownership.
- Keep the default NeuroClient arena stable while scenario selection remains an explicit validation/testing surface.

## 2026-07-03 - Subjective Runtime Replay Batching V19

### Arena-Diversity Status

I have not changed global monster, spell, item, or gear definitions for the player-facing simulator. The diversity work is scenario-level: the opt-in validation catalog now has eleven arenas behind `/simulation/start-ai-validation`, and the standard NeuroClient arena remains unchanged.

That catalog now samples more of the existing content surface:

- skeleton Warrior / Archer / Warlock role pressure;
- goblins, goblin archers, and generic casters;
- wands, scrolls, potions, weapon coats, and floor pickups;
- water, difficult terrain, spike zones, darkness, double doors, and environmental devices;
- Mark Target focus fire, buff/consumable pressure, Thunderwave-style forced movement, and line/AoE geometry.

This is the right anti-overfitting setup: enemy policy can be tuned against varied fixtures without silently rewriting the underlying rules or default arena.

### Latency Finding

The `line_aoe_corridor` smoke exposed a runtime bottleneck before the next full schedule run. The command itself was fast, but the external AI waited too long for its streamed command result after a rich spell action:

- before store batching: command ack-to-stream result was `66609.2 ms`;
- command HTTP ack itself was only `112.04 ms`;
- the selected command was `position|Fireball__slot_3|pos=4,4`;
- the initial decision epoch exposed `2772` position actions.

The slow path was command follow-up replay, not action execution. Even after batching runtime hooks, `SubjectiveStore.apply_frame()` still deep-copied the entire `WorldState` for every replayed frame so hooks could receive `previous_world`. After a spell, those repeated copies included growing combat-log/world payloads.

### Integrated Runtime Fix

Two changes landed:

- `SubjectiveRuntime` now batches command-follow-up hook effects: replay frames still apply in order, but expensive derived-state processors run once at the batch boundary.
- `SubjectiveStore.apply_frame(..., capture_previous=False)` lets replay batches capture the previous world only once, then apply later frames without deep-copying the whole local state again.

The repeated deep copy was the practical killer.

### Live Smoke Result

Reran the same `line_aoe_corridor` validation smoke on a private server at `127.0.0.1:8061`.

After the fix:

- first command smoke elapsed: `6.906 s`;
- command submitted-to-ack: `238.66 ms`;
- command ack-to-stream result: `1727.67 ms`;
- command submitted-to-stream result: `1966.34 ms`;
- external AI command elapsed: `2498.97 ms`;
- improvement from the prior ack-to-stream sample: about `97.41%`.

Artifacts:

- before store batching: `/tmp/dnd_ai_iteration_v18_live/line_aoe_corridor_after_batch.json`;
- after store batching: `/tmp/dnd_ai_iteration_v18_live/line_aoe_corridor_after_store_batch.json`;
- server log: `/tmp/dnd_ai_iteration_v18_live/server_after_store_batch.log`.

### Verification

- `uv run pytest tests/manual/test_32_subjective_runtime_store.py -q`
- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q`
- `uv run pytest tests/manual/test_28_subjective_observation_stream.py -q -k 'sensory or snapshot_plus_frames'`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q`
- `uv run pytest tests/manual/test_29_external_ai_subprocess.py -q`
- `uv run pytest tests/manual/test_37_ai_validation_arenas.py -q`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q`
- `uv run pyright ai/subjective/store.py ai/subjective/runtime.py tests/manual/test_32_subjective_runtime_store.py tests/manual/test_36_seamless_subjective_runtime.py`
- `uv run pyright ai/external/policy.py ai/external/state.py ai/external_melee_agent.py tests/manual/test_35_subjective_external_ai.py tests/manual/test_29_external_ai_subprocess.py`

### Next Targets

- Run the extended eleven-arena validation schedule now that rich post-action replay is no longer minute-scale.
- Tune enemy support, buff, forced-movement, and AoE geometry policies against the expanded catalog.
- Profile remaining large action-space costs separately from command follow-up replay, especially position-heavy spell epochs.

## 2026-07-03 - Anti-Overfit Arena Expansion V20

### Answer To The Arena Question

Yes, the simulator has enough content that we should not tune enemy AI only against the default skeleton room. I did not change global monster definitions, standard NeuroClient startup, spell implementations, or gear rules here. This pass adds opt-in validation arenas that deliberately sample more of the existing content surface.

The catalog now has fourteen arenas. The three new ones are:

- `zone_control_web_gauntlet`: a Barbarian-facing control arena with Web, Grease, Spike Growth, Fog Cloud, goblin skirmishing, water, and difficult terrain.
- `support_attrition_cache`: a shield Fighter-facing support arena with a wounded skeleton guard, Bless, Bane, Aid, Healing Word, Shield of Faith, Sanctuary, a healing potion, and a lightning weapon coat.
- `high_level_spell_resource_duel`: a level 9 Sorcerer duel with a high-slot enemy caster carrying Cone of Cold, Cloudkill, Hypnotic Pattern, Slow, Banishment, and Dimension Door.

### Why This Matters

The default arena is still useful as the player-facing smoke test, but it is a bad sole teacher for enemy AI. It encourages policies that overfit to:

- three skeleton roles;
- level 5 spell lists;
- one door rhythm;
- a small set of support and movement problems.

The validation catalog is now better shaped for enemy policy iteration: terrain, doors, darkness, water, support, healing, buffs, consumables, environmental objects, forced movement, line AoE, control zones, and higher spell slots all have explicit fixtures.

### Verification

- `uv run pytest tests/manual/test_37_ai_validation_arenas.py -q`
- `uv run pytest tests/manual/test_38_ai_validation_server_start.py -q`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q`
- `uv run pyright dnd/scenarios/ai_validation_arenas.py tests/manual/test_37_ai_validation_arenas.py tests/manual/test_38_ai_validation_server_start.py tests/manual/test_39_ai_validation_harness.py`

### Next Targets

- Run the fourteen-arena validation schedule through live external AI and Codex-monster smokes.
- Tune control-zone, healing/support, and expensive spell-slot valuation against the new arenas.
- Keep profiling the remaining rich-spell follow-up latency separately from policy quality.

## 2026-07-03 - Support Healing And Logical Annotations V21

### Probe

Ran an isolated three-arena probe on `127.0.0.1:8064` using the real validation startup and external AI subprocess:

- `zone_control_web_gauntlet`: Barbarian-facing control/pathing surface.
- `support_attrition_cache`: shield Fighter-facing skeleton support surface.
- `high_level_spell_resource_duel`: Sorcerer/high-slot pressure surface.

Artifacts:

- `/tmp/dnd_ai_v21_probe/three_arena_probe_summary.json`
- `/tmp/dnd_ai_v21_probe/support_after_healing_policy.json`
- `/tmp/dnd_ai_v21_probe/server.log`

### Finding

The support arena exposed a clean enemy-policy miss. The support caster opened well with `Bless`, but then selected `Shield of Faith` while a controlled frontline guard was already wounded. That is exactly the sort of behavior the new arena was meant to catch: not illegal, but strategically off.

The same probe also left two useful next notes:

- `zone_control_web_gauntlet` still favored direct pressure over control-zone spells, so Web/Grease/Spike Growth valuation needs a separate pass.
- Rich support spell commands are still slow. In the post-fix live rerun, the `Bless` command took about `14992.12 ms`.

### Integrated Improvement

The external enemy policy now carries enough reduced state to reason about wounds:

- `ExternalEntity` includes `max_hp`.
- The behavior tree has a `heal_wounded_controlled_ally` leaf after opening group support and before ordinary damage/support fallback.
- Healing rows target controlled entities missing at least about `30%` HP.
- Opening group support still wins when it can buff multiple unbuffed controlled allies.

Live rerun result in `support_attrition_cache`:

- `Bless__slot_1` selected first with `cast_opening_controlled_support_spell`.
- `Healing Word__slot_1` selected second with `heal_wounded_controlled_ally`.
- Later archer behavior still used `Mark Target` and exposed-target pressure.

### Logical Annotations

Added the first typed logical annotation surface for the external policy. `ai.external.external_policy_logical_annotations()` returns nineteen approximate propositions over behavior leaves and scoring helpers:

- prerequisites, such as visible enemies, known wounded allies, affordable rows, known route tiles, or no-contact exploration state;
- consequents, such as expected HP recovery, pressure improvement, door open state, route progress, support conditions, or reduced future melee access.

These annotations are not used as authority yet. They are a debug/planning affordance and a future basis for behavior-tree conditions or planner-style world-model checks.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q`
- `uv run pytest tests/manual/test_29_external_ai_subprocess.py -q`
- `uv run pyright ai/external/__init__.py ai/external/state.py ai/external/policy.py ai/external_melee_agent.py tests/manual/test_29_external_ai_subprocess.py tests/manual/test_35_subjective_external_ai.py`

### Next Targets

- Use `zone_control_web_gauntlet` to decide when Web, Grease, or Spike Growth should beat direct Magic Missile pressure.
- Profile rich support-spell command latency separately from policy quality.
- Extend logical annotations into agent event telemetry so NeuroClient/debug views can show why a branch fired.

## 2026-07-03 - Class And Gear Arena Expansion V22

### Motivation

The validation catalog needed more enemy-side variety before further policy tuning. The prior wave already covered skeletons, goblins, doors, water, darkness, items, support, forced movement, line AoE, zone control, and high-level spell slots. The remaining overfit risk was that the enemy policy could still look decent mainly because it was seeing the same bespoke monster factories and the same basic loadout shapes.

### Integrated Arenas

Added three opt-in validation arenas:

- `class_party_mirror_scramble`: a monster-side party built from real level 5 Barbarian, Fighter, and Sorcerer class factories, exposing Rage, Reckless Attack, Second Wind, Action Surge, metamagic, spell slots, class gear, and consumables.
- `ranged_loadout_kiting_ring`: a Barbarian-facing standard terrain arena where ranged enemies have legal longbow, shortbow, Eldritch Blast, support spell, and fallback melee options across water and difficult terrain.
- `concentration_control_crossroads`: a Sorcerer-facing crossroads arena mixing a frontline guard, a control Sorcerer with Web/Hypnotic Pattern/Slow/Fireball, and a support caster with Bless/Bane/Aid/Healing Word/Shield of Faith/Sanctuary.

This brings the validation catalog to 17 arenas.

### Verification

- `uv run pytest tests/manual/test_37_ai_validation_arenas.py -q`
- `uv run pytest tests/manual/test_38_ai_validation_server_start.py -q`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q`
- `uv run pyright dnd/scenarios/ai_validation_arenas.py tests/manual/test_37_ai_validation_arenas.py tests/manual/test_38_ai_validation_server_start.py tests/manual/test_39_ai_validation_harness.py`

### Next Targets

- Run the larger catalog through a live rotating validation schedule instead of continuing to tune on one or two arenas.
- Keep the next enemy-policy pass anchored on observed failures from the class/gear arenas.
- Continue profiling command latency separately from policy quality; fixture variety should not hide runtime slowness.

## 2026-07-03 - External Runtime Timing Instrumentation V23

### Motivation

Recent live validation runs still showed command durations in the hundreds or thousands of milliseconds, and earlier support-spell runs reached multi-second command follow-up latency. A single `command_result.elapsed_ms` value was not enough: it could not distinguish policy thinking, local state reduction, HTTP command submission, history replay, SSE waiting, hook flushing, or resync work.

### Integrated Instrumentation

The subjective runtime now emits a `runtime.command_timing` agent event for each command lifecycle. The payload includes:

- `wait_for_epoch_ms`
- `submit_http_ms`
- `ack_parse_ms`
- `history_fetch_ms`
- `history_apply_ms`
- `history_frames`
- `history_done`
- `sse_wait_ms`
- `sse_events`
- `sse_frames`
- `sse_sync_events`
- `sse_evicted_events`
- `deferred_flush_ms`
- `resync_ms`
- `total_ms`

The external enemy loop also adds policy-tick timing to `external_ai.policy_tick`:

- `epoch_wait_ms`
- `affordance_projection_ms`
- `state_reduction_ms`
- `policy_selection_ms`
- total tick `elapsed_ms`

`external_ai.command_result` now includes the runtime timing payload captured from the command that just completed, so the normal AI log line and the agent-event stream both carry the breakdown.

The dashboard now has a command-latency bucket chart ready for live playtest metrics:

- `max_command_total_ms`
- `max_command_sse_wait_ms`
- `max_command_history_fetch_ms`
- `max_command_deferred_flush_ms`
- `max_policy_selection_ms`

### Verification

- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "normal_path or timing"`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q`
- `uv run pyright ai/subjective/runtime.py ai/external_melee_agent.py tests/manual/test_35_subjective_external_ai.py tests/manual/test_36_seamless_subjective_runtime.py`
- `node --check /tmp/agent_dashboard_script.js`

### Next Targets

- Run a live validation schedule and sort slow commands by `runtime.command_timing.total_ms`.
- Treat any repeated `sse_wait_ms`, `history_fetch_ms`, or `deferred_flush_ms` spike as a runtime bug, not a policy-quality issue.
- Keep policy fixes anchored on observed arena failures after latency attribution is in place.

## 2026-07-03 - Subjective Runtime Hook Flush Optimization V24

### Motivation

The V23 timing probes showed the external enemy loop was not waiting on SSE. The worst delays were local command follow-up work, especially `deferred_flush_ms`, which reached roughly 1.6s in the standard skeleton-door probe and 3.5s in the zone-control probe after the first materializer-only optimization.

### Integrated Change

The subjective runtime hook registry now avoids deep-copying the whole `AgentState` on every processor pass. It shallow-copies the top-level derived-state containers, trims append-only histories to the latest 20 rows, and keeps the affordance index lightweight instead of duplicating every full affordance row as JSON inside `agent_state.variables`.

The observation materializer also avoids deep-copying the whole materialized state when applying one frame; it now copies the top-level mutable containers and updates only the affected fact dictionaries.

### Live Probe Result

Three isolated 8072 probes returned to the human turn:

- `zone_control_web_gauntlet`: max command total 811.762ms, max history apply 617.091ms, max deferred flush 5.455ms.
- `line_aoe_corridor`: max command total 1155.396ms, max history apply 486.405ms, max deferred flush 5.422ms.
- `standard_skeleton_doors`: max command total 1066.966ms, max history apply 487.106ms, max deferred flush 5.694ms.

This fixes the pathological hook-flush bucket. Remaining latency is now mostly command HTTP execution, history apply, and affordance projection/state reduction.

### Verification

- `uv run pytest tests/manual/test_32_subjective_runtime_store.py -q`
- `uv run pytest tests/manual/test_33_subjective_runtime_processors.py -q`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q`
- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q`
- `uv run pyright ai/subjective/hooks.py ai/subjective/processors.py ai/subjective/queries.py ai/observation/materializer.py ai/subjective/runtime.py tests/manual/test_33_subjective_runtime_processors.py tests/manual/test_36_seamless_subjective_runtime.py`

### Next Targets

- Add per-processor timing if `history_apply_ms` or affordance projection keeps spiking.
- Profile command HTTP execution separately from local replay, because the old hook-flush bottleneck is no longer hiding it.
- Keep collecting live metrics across diverse arenas rather than returning to a single skeleton-door benchmark.

## 2026-07-03 - Existing-Content Arena Expansion V25

### Motivation

The enemy AI should not be tuned only against skeleton doors or a small spell surface. The simulator already has broader content, so the validation catalog should sample it without inventing new rules content or fake monster behavior.

### Integrated Arenas

Added three opt-in validation arenas using existing factories, spell registrations, items, terrain, and light mechanics:

- `teleport_escape_skirmish`: a Barbarian-facing skirmish where a caster has Misty Step, Dimension Door, Blur, Mirror Image, and Ray of Frost while ranged allies pressure across water and difficult terrain.
- `darkness_reveal_labyrinth`: a dark two-door labyrinth with Darkness, Fog Cloud, Invisibility, Greater Invisibility, Silence, See Invisibility, Daylight, Darkvision, Light, and True Seeing.
- `guardian_zone_shrine`: a shield-Fighter-facing support shrine with a wounded skeleton guard and a caster exposing Spirit Guardians, Guardian of Faith, Beacon of Hope, Mass Healing Word, Flame Strike, and Sanctuary.

The validation catalog now contains 20 arenas. The rotation harness classifier now routes support/healing arenas into resource focus and zone/summon-object arenas into environment focus.

### Verification

- `uv run pytest tests/manual/test_37_ai_validation_arenas.py -q`
- `uv run pytest tests/manual/test_38_ai_validation_server_start.py -q`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q`
- `uv run pyright dnd/scenarios/ai_validation_arenas.py ai/validation_harness.py tests/manual/test_37_ai_validation_arenas.py tests/manual/test_38_ai_validation_server_start.py tests/manual/test_39_ai_validation_harness.py`

### Next Targets

- Run the 20-arena schedule through live external AI and Codex-monster smokes.
- Prioritize enemy-policy fixes only after the new teleport, vision, and guardian-zone arenas produce observed failures.
- Keep arena additions fixture-level unless a playtest exposes a real missing engine mechanic.

## 2026-07-03 - Object, Condition, And Necromancy Arena Expansion V26

### Motivation

The validation catalog was much better than the default skeleton doorway, but it still risked over-weighting damage, movement, doors, and broad spell AoE. The next enemy-AI tuning passes need executable pressure for non-door object interactions, disabling condition spells, anti-healing status, and high-slot necromancy without changing global monster, spell, gear, or NeuroClient behavior.

### Integrated Arenas

Added three opt-in validation arenas using existing simulator content:

- `trap_lever_killzone`: a Barbarian-facing standard hazard room with the door open, active spike-zone cells, the standard trap lever, and monsters close enough to pull the lever or deliberately ignore it.
- `condition_lock_sanctum`: a Barbarian-facing control room with a guard, a class-built Sorcerer controller exposing Command, Hold Person, Fear, Hypnotic Pattern, Slow, and Banishment, plus a support caster exposing Bless, Bane, Guiding Bolt, Shield of Faith, and Sanctuary.
- `necrotic_anti_healing_duel`: a wounded shield-Fighter duel against a necromancer with Chill Touch, Blindness/Deafness, Bestow Curse, Blight, Harm, and Finger of Death, with healing resources present so anti-healing is not just flavor text.

The validation catalog now contains 23 arenas. The new tests assert concrete action surfaces, including an available `Pull Lever` row for the adjacent guard, not just object placement.

### Verification

- `uv run pytest tests/manual/test_37_ai_validation_arenas.py -q`
- `uv run pytest tests/manual/test_38_ai_validation_server_start.py -q`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q`
- `uv run pyright dnd/scenarios/ai_validation_arenas.py tests/manual/test_37_ai_validation_arenas.py tests/manual/test_38_ai_validation_server_start.py tests/manual/test_39_ai_validation_harness.py`

### Next Targets

- Run the 23-arena validation schedule through live external AI and Codex-monster smokes.
- Use `trap_lever_killzone` to decide whether the default enemy policy should value non-door object interactions.
- Use `condition_lock_sanctum` and `necrotic_anti_healing_duel` to tune control, anti-healing, and high-slot spell valuation from observed failures.

## 2026-07-03 - Entity Control Spell Policy V27

### Probe

Ran a five-case one-turn live validation probe against the new and existing validation arenas:

- `trap_lever_killzone` with the Barbarian hero.
- `darkness_reveal_labyrinth` with the Sorcerer hero.
- `standard_skeleton_doors` as the baseline skeleton-door case.
- `condition_lock_sanctum` with the Barbarian hero.
- `necrotic_anti_healing_duel` with the shield Fighter hero.

All five cases returned to the human boundary. The probe artifact is `/tmp/dnd_ai_v26_probe/v26_sequential_probe_v2.json`.

### Findings

- `trap_lever_killzone` exposed that non-door object interactions are still not valued under visible-enemy pressure. The guard had a `Pull Lever` surface from the fixture test, but the live policy chose movement, retreat, attacks, support, and end-turn behavior instead.
- `condition_lock_sanctum` exposed a clearer policy bug: the controller caster had disabling condition spells available, but the old policy selected `Fire Bolt`, `Bless`, `Shield of Faith`, attacks, movement, and end turns without first-class control/debuff valuation.
- `necrotic_anti_healing_duel` showed that high-slot necromancy and anti-healing choices still need deeper scoring. The AI selected `Magic Missile`, Mark Target, attacks, and movement, but did not demonstrate a targeted anti-healing plan in the one-turn probe.
- Runtime speed is still suspicious for rich spell and turn-end follow-up. The worst pre-fix command total was 6976.391 ms in `condition_lock_sanctum`; the post-fix validation still reached 5708.044 ms, dominated by `history_apply_ms`.

### Integrated Improvement

Added an entity-targeted control/debuff branch to the default external enemy behavior tree:

- `Hold Person` / `Hold Monster`
- `Banishment`
- `Command`
- `Blindness/Deafness`
- `Bestow Curse`
- `Bane`
- `Charm Person`

The branch checks visible hostile targets, skips duplicate known control conditions, and outranks generic damage when the control spell is legal and relevant.

### Live Rerun

Reran `condition_lock_sanctum` after the policy change. The live rerun selected `Hold Person__slot_2` through the new `cast_visible_enemy_control_spell` branch, then continued through attacks, movement, support, and end turns. The artifact is `/tmp/dnd_ai_v26_probe/v26_condition_after_control_policy.json`.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k 'control or support or spell or caster_policy'`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q`
- `uv run pyright ai/external/policy.py tests/manual/test_35_subjective_external_ai.py`

### Next Targets

- Instrument and reduce `history_apply_ms` / `history_fetch_ms` for rich spell and turn-end command follow-up.
- Use `trap_lever_killzone` to decide whether non-door object actions need a policy branch under visible-enemy pressure.
- Extend entity-control scoring to anti-healing and high-slot necromancy once `necrotic_anti_healing_duel` produces more observed failures.

## 2026-07-03 - Subjective Runtime Epoch Payload Shrink V28

### Probe

Ran repeated three-case live probes on the isolated `8075` server, alternating:

- `condition_lock_sanctum` as the Barbarian-facing control-spell case.
- `darkness_reveal_labyrinth` as the Sorcerer-facing vision/exploration case.
- `standard_skeleton_doors` as the skeleton-door baseline.

The final current-code artifact is `/tmp/dnd_ai_v27_probe/v27_epoch_shrink_probe.json`. Earlier comparison artifacts are:

- `/tmp/dnd_ai_v27_probe/v27_transport_shrink_probe.json`
- `/tmp/dnd_ai_v27_probe/v27_replay_copy_probe.json`
- `/tmp/dnd_ai_v27_probe/v27_lean_runtime_probe.json`

### Findings

- The policy branch was not the slow path. The agent selected `Hold Person__slot_2`, `Magic Missile__slot_1`, `Shield of Faith__slot_1`, movement, and attacks quickly enough once the epoch was local.
- The multi-second replay spike came from data shape and runtime copying. Control frames duplicated heavy command/epoch payloads in patch data, command catch-up still deep-copied the previous `WorldState`, and movement affordances accidentally carried duplicated `target_options` on every position row.
- The biggest remaining timing bucket is now `submit_http_ms`, not history replay. In the final condition-control probe, the worst command total was 563.959 ms and almost all of that was server-side submit time: 526.103 ms.

### Integrated Changes

- Control-frame patches now carry only small metadata. The authoritative typed payload remains on `ObservationFrame.command_result` or `ObservationFrame.decision_epoch`.
- Command follow-up replay no longer captures a deep copy of the previous world when effects are deferred and hooks run once after materialization.
- The external behavior-tree subprocess now uses a lean subjective runtime with no Codex-facing post-processors; it still emits runtime and policy telemetry.
- Ordinary position affordance rows no longer duplicate their source target option list. They keep one executable `targets` entry, while true multi-entity rows can still preserve `target_options`.

### Live Result

Final current-code probe:

- `condition_lock_sanctum`: max command total 563.959 ms, max `history_fetch_ms` 19.578 ms, max `history_apply_ms` 11.065 ms, max hook flush 3.976 ms.
- `darkness_reveal_labyrinth`: max command total 249.350 ms, max `history_apply_ms` 1.368 ms.
- `standard_skeleton_doors`: max command total 180.527 ms, max `history_apply_ms` 3.562 ms.

The condition-control replay/apply path improved from 6474.102 ms `history_apply_ms` in the pre-fix probe to 11.065 ms in the final probe. That is the right direction, but not the end state: submit-side command execution still needs instrumentation.

### Verification

- `uv run pytest tests/manual/test_31_subjective_runtime_epochs.py -q`
- `uv run pytest tests/manual/test_32_subjective_runtime_store.py -q`
- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q -k 'accepted_command_publishes_result_then_followup_epoch or snapshot_current_epoch_is_bootstrap_only_not_frame_decoration'`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k 'lean_subjective_runtime or entity_control_policy'`
- `uv run pyright ai/subjective/epochs.py server/event_server.py tests/manual/test_31_subjective_runtime_epochs.py`
- `uv run pyright ai/external_melee_agent.py ai/subjective/runtime.py ai/observation/projector.py tests/manual/test_35_subjective_external_ai.py tests/manual/test_36_seamless_subjective_runtime.py`

### Next Targets

- Instrument `submit_http_ms` inside server command execution and turn advancement.
- Use `trap_lever_killzone` to decide whether non-door object actions need a policy branch under visible-enemy pressure.
- Extend entity-control scoring to anti-healing and high-slot necromancy after `necrotic_anti_healing_duel` produces more observed failures.

## 2026-07-03 - Server Command Timing And Diverse Arena Probe V29

### Content Scope

No global monster, spell, item, gear, or NeuroClient default setup was changed for this slice. The validation diversity work is fixture-level: the opt-in catalog behind `/simulation/start-ai-validation` now contains 23 arenas built from existing simulator content, including class-built enemies, skeleton and skirmisher factories, spell registrations, doors, water, difficult terrain, darkness, reveal tools, trap levers, scrolls, wands, potions, weapon coats, support magic, control spells, anti-healing necromancy, forced movement, line/AoE geometry, and ranged loadouts.

This is the right shape for enemy-AI work because it avoids overfitting the policy to the standard three-skeleton doorway without mutating the player-facing simulator baseline.

### Integrated Instrumentation

AI command acknowledgements now carry a compact `server_timing` payload with phase timings from the server-side command route. The external runtime copies that payload into `runtime.command_timing`, and the agent-event stream records it alongside the existing client-side timing buckets.

The timing now separates:

- local subjective runtime replay and history catch-up;
- HTTP submit time;
- command execution;
- command-result publication;
- turn advancement;
- active/follow-up decision epoch generation;
- epoch subphases such as `get_available_actions`, serialization, affordance row building, and action-economy projection.

### Live Probe

Ran a four-arena live probe on isolated server `8076` using `human_hero` validation mode. The probe created a real human session for the hero, ended hero turns, and let the external monster process act from local subjective decision epochs.

Artifact: `/tmp/dnd_ai_v29_probe/v29_epoch_phase_probe.json`

Results:

- `standard_skeleton_doors`: 30 commands, max command total 365.652 ms, max submit 356.113 ms. The policy opened the door, used Necrotic Bless with extra targets, moved through the door, used Mark Target, attacked, and held ranged spacing.
- `goblin_water_skirmish`: 35 commands, max command total 591.790 ms, max submit 436.123 ms. The policy used Magic Missile, ranged attacks, jumps, retreats, and spacing around water/skirmish terrain.
- `condition_lock_sanctum`: 23 commands, max command total 1265.424 ms, max submit 1213.590 ms. The policy used Hold Person, Bless, Shield of Faith, attacks, and movement, but this arena exposed the current rich-epoch bottleneck.
- `ranged_loadout_kiting_ring`: 38 commands, max command total 462.450 ms, max submit 450.841 ms. The policy used ranged attacks, Extra Attack, Necrotic Bless, Dodge, Invisibility, retreat, and remembered-enemy movement.

### Findings

- The local replay regression from V28 stayed fixed. Across this probe, worst `history_apply_ms` was 149.216 ms and most runs were much lower.
- The remaining large spikes are server-side submit work, especially decision-epoch construction for actors with rich spell/control affordances.
- `condition_lock_sanctum` is the clearest pressure case: `advance.publish_active_epoch.get_available_actions_ms` reached 847.817 ms, `advance.publish_active_epoch.build_affordance_set_ms` reached 440.819 ms, and `publish.followup_epoch.get_available_actions_ms` reached 604.529 ms.
- The enemy policy is no longer just walking forward in these probes. It is exercising support, control, ranged identity, door navigation, kiting, defensive fallback, multi-target support, and class/gear resources. The clunky part is now performance and deeper valuation, not the basic event-first control loop.

### Verification

- `uv run pytest tests/manual/test_37_ai_validation_arenas.py -q`
- `uv run pytest tests/manual/test_38_ai_validation_server_start.py -q`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q`
- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q -k 'accepted_command_publishes_result_then_followup_epoch or snapshot_current_epoch_is_bootstrap_only_not_frame_decoration or runtime_emits_command_timing_breakdown_event'`
- `uv run pytest tests/manual/test_31_subjective_runtime_epochs.py -q`
- `uv run pytest tests/manual/test_32_subjective_runtime_store.py -q`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k 'lean_subjective_runtime or entity_control_policy or door'`
- `uv run pytest tests/manual/test_30_codex_takeover_tools.py -q -k 'multi_entity or epoch or command'`
- `uv run pyright ai/subjective/epochs.py server/event_server.py ai/subjective/runtime.py tests/manual/test_36_seamless_subjective_runtime.py`

### Next Targets

- Optimize server-side decision-epoch construction for rich spell/control actors.
- Use `trap_lever_killzone` to decide whether non-door object interactions need a branch under visible-enemy pressure.
- Extend control scoring toward anti-healing and high-slot necromancy after more `necrotic_anti_healing_duel` observations.
- Keep adding arenas only as opt-in fixtures unless an observed playtest exposes a genuinely missing engine mechanic.

## 2026-07-03 - AoE Preview Cache And Direct Epoch Affordances V30

### Motivation

V29 proved that `condition_lock_sanctum` was dominated by server-side decision-epoch construction. The support/control side was not slow because the policy was thinking too hard; it was slow because action discovery recomputed identical AoE previews for every upcast spell variant, then the epoch builder serialized all available actions to JSON and immediately rebuilt Pydantic affordance rows from that JSON.

### Integrated Changes

- Added a per-query AoE preview cache inside `Entity` action discovery. Upcast variants with the same shape, candidate centers, and target filters now reuse the already-computed `AvailableTarget` list.
- Applied the same cache to item-provided AoE actions so scrolls, wands, and devices can benefit from the same path.
- Changed `ai.subjective.epochs.build_decision_epoch()` to build `AffordanceSet` and `ActionEconomyState` directly from `AvailableActionsResult`.
- Kept `serialize_available_actions()` intact for compatibility/debug endpoints.
- Added tests proving direct epoch rows preserve the legacy serialized row ids and that upcast AoE variants no longer recompute one preview per row.

### Live Probe

Ran the same four-arena live probe on isolated server `8077`.

Artifact: `/tmp/dnd_ai_v30_probe/v30_epoch_optimization_probe.json`

Before/after against V29:

- `condition_lock_sanctum`: max command total 1265.424 ms -> 577.465 ms; max submit 1213.590 ms -> 307.595 ms.
- `condition_lock_sanctum`: active epoch `get_available_actions` 847.817 ms -> 66.207 ms.
- `condition_lock_sanctum`: active epoch affordance building 440.819 ms -> 7.868 ms.
- `condition_lock_sanctum`: follow-up epoch `get_available_actions` 604.529 ms -> 28.195 ms.
- `ranged_loadout_kiting_ring`: max command total 462.450 ms -> 316.294 ms.
- `goblin_water_skirmish`: max command total 591.790 ms -> 351.067 ms, but still showed a follow-up `get_available_actions` outlier around 308 ms.

### Findings

- The rich spell/control pathological epoch spike is gone.
- Local replay stayed low: worst V30 `history_apply_ms` was 6.658 ms across the four probes.
- The system is still not fast enough. The remaining targets are now narrower: non-AoE `get_available_actions` spikes and occasional follow-up affordance-building outliers.
- Enemy behavior remained broad after the optimization: door opening, Mark Target, Necrotic Bless with extra targets, Hold Person, Magic Missile, Shield of Faith, ranged attacks, Extra Attack, Dodge, Invisibility, retreat, and remembered-enemy movement all appeared in the probe.

### Verification

- `uv run pytest tests/manual/test_31_subjective_runtime_epochs.py -q`
- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q -k 'accepted_command_publishes_result_then_followup_epoch or snapshot_current_epoch_is_bootstrap_only_not_frame_decoration or runtime_emits_command_timing_breakdown_event'`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k 'lean_subjective_runtime or entity_control_policy or door or multi_entity'`
- `uv run pytest tests/manual/test_30_codex_takeover_tools.py -q -k 'multi_entity or epoch or command'`
- `uv run pyright dnd/entity.py ai/subjective/epochs.py ai/external ai/external_melee_agent.py tests/manual/test_31_subjective_runtime_epochs.py tests/manual/test_35_subjective_external_ai.py`

### Next Targets

- Instrument the remaining non-AoE submit spikes in `goblin_water_skirmish` and the standard skeleton follow-up outlier.
- Use `trap_lever_killzone` for observed object-interaction policy tuning.
- Keep pressure-testing anti-healing/high-slot necromancy after the speed path is less noisy.

## 2026-07-03 - Necrotic Anti-Heal And Burst Policy V31

### Motivation

The simulator already had the right content surface for this problem. `necrotic_anti_healing_duel` creates a wounded shield fighter with a healing potion and a monster necromancer carrying `Chill Touch`, `Blindness/Deafness`, `Bestow Curse`, `Blight`, `Harm`, and `Finger of Death`. The policy gap was not missing monsters or gear; it was that the enemy spell scorer still recognized a narrow low-level damage list, so necromancy-heavy turns could collapse back toward Magic Missile-style pressure.

### Integrated Changes

- Added a behavior-tree anti-healing leaf before generic control/damage spell selection.
- The new leaf selects `Chill Touch` against wounded visible enemies when they are not already under a known anti-healing condition.
- Added high-slot necromancy priorities for `Finger of Death`, `Harm`, `Blight`, and `Inflict Wounds`.
- Added a logical annotation for the anti-healing routine so later planning/debug surfaces can see the prerequisite and intended consequent.
- Did not add new global monsters, spells, gear, NeuroClient defaults, or arenas in this pass.

### Findings

- The validation catalog is already broad enough to expose this class of overfit: the useful move was to improve policy valuation, not add another fixture.
- Multi-target behavior remains preserved: Necrotic Bless still carries extra ally targets, and Magic Missile still splits only when the policy sees low-HP cleanup targets.
- This is not yet a live-play victory. The next step is a real `necrotic_anti_healing_duel` probe to confirm these choices survive initiative, visibility, range, and resource constraints.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k 'necromancer or logical_annotations or caster_policy_ignores_support_spell_on_enemy_when_damage_spell_exists or caster_policy_preserves_slot_pressure_on_healthy_target'`
- `uv run pytest tests/manual/test_37_ai_validation_arenas.py -q -k 'necrotic_anti_healing_duel'`
- `uv run pyright ai/external/policy.py tests/manual/test_35_subjective_external_ai.py`

### Next Targets

- Run a live `necrotic_anti_healing_duel` probe and inspect the actual selected command sequence.
- Continue instrumenting the remaining non-AoE submit spikes in `goblin_water_skirmish`.
- Use `trap_lever_killzone` to decide whether non-door object actions need an explicit policy branch.

## 2026-07-03 - Necrotic Live Probe And Boundary Helper V32

### Live Probe

Ran isolated server `8078` with `necrotic_anti_healing_duel` in `human_hero` mode.

Artifacts:

- `/tmp/dnd_ai_v31_probe/necrotic_live_probe.json`
- `/tmp/dnd_ai_v31_probe/necrotic_live_summary.json`
- `/tmp/dnd_ai_v31_probe/server.log`

The external monster AI produced 12 policy ticks and 12 command results. It selected `Mark Target`, ranged attacks, movement/spacing, guard melee, and `Finger of Death__slot_7`. The encounter ended after the archer killed the marked fighter in round 2. The apparent second-boundary timeout was a probe-script bug: `/game/status` exposed `encounter_active=false`, so the fight was finished.

### Findings

- High-slot necromancy is live: `Finger of Death__slot_7` survived real initiative, visibility, range, and resource constraints.
- `Chill Touch` did not fire in this run because exposed-target pressure selected lethal/high-slot burst first. The next design question is whether anti-healing should override burst only when known healing resources are visible.
- External policy selection stayed cheap: max `policy_selection_ms` was 0.33 ms.
- Worst command remained too slow: max total 330.527 ms, max submit 230.702 ms, max server `get_available_actions` 183.001 ms.

### Integrated Change

Added typed boundary helpers in `ai.validation_harness`:

- `game_status()`
- `ping_session()`
- `wait_for_session_boundary()`

The boundary helper returns `session_turn`, `encounter_ended`, `inactive`, or `timeout`, so validation scripts stop mislabeling completed fights as timeouts.

### Verification

- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q`
- `uv run pyright ai/validation_harness.py tests/manual/test_39_ai_validation_harness.py`

### Next Targets

- Investigate the Finger of Death follow-up `get_available_actions` spike at 183.001 ms.
- Decide the anti-healing versus lethal-burst behavior.
- Continue alternating away from the necrotic arena next turn.

## 2026-07-03 - Line AoE Action Discovery Speed V33

### Live Probe

Ran an alternating non-necrotic probe on isolated server `8079`:

- `trap_lever_killzone` for Barbarian, skeleton, hazard, and object-interaction pressure.
- `line_aoe_corridor` for Sorcerer, skeleton formation, Magic Missile, and position-AoE pressure.

Artifacts:

- `/tmp/dnd_ai_v33_probe/live_probe.json`
- `/tmp/dnd_ai_v33_probe/live_summary.json`
- `/tmp/dnd_ai_v33_probe/server.log`

After optimization, restarted the isolated server and reran `line_aoe_corridor`.

Artifacts:

- `/tmp/dnd_ai_v33_probe/live_probe_after.json`
- `/tmp/dnd_ai_v33_probe/live_summary_after.json`
- `/tmp/dnd_ai_v33_probe/server_after.log`

### Findings

- The first `line_aoe_corridor` run reproduced the rich-caster speed issue: worst live `get_available_actions` was 430.709 ms and worst live `build_affordance_set` was 294.187 ms.
- Profiling showed AoE preview target filtering calling `Entity.has_hp` hundreds of times. That path allocated combined Constitution modifier values for a simple alive/dead preview filter.
- The external AI handled the tactical loop without action polling and selected Mark Target, ranged attacks, Magic Missile, movement, spacing, melee pressure, and end-turn rows.
- `trap_lever_killzone` did not select `Pull Lever`; that is now a real environment-object policy gap rather than a routing/server gap.

### Integrated Changes

- Decision epochs now keep `target_options` only for multi-target rows such as Magic Missile and Necrotic Bless.
- The direct decision-epoch builder constructs trusted internal `ActionTarget`, `ActionCostProfile`, and `ActionAffordance` models without repeated validation churn.
- Direct row building computes shared action metadata once per action row instead of once per flattened target.
- AoE discovery now uses a discovery-local positive-normal-HP predicate instead of the heavy public `has_hp` property.

### Results

- Local `line_aoe_corridor` mage `get_available_actions`: roughly 70-205 ms before, 37-39 ms after.
- Local 2,802-row `build_affordance_set`: median about 25 ms after.
- Live worst `get_available_actions`: 430.709 ms -> 41.729 ms.
- Live worst `build_affordance_set`: 294.187 ms -> 16.513 ms.
- Remaining live bottleneck shifted to subjective publication/projection: `publish.command_result_ms` reached 203.102 ms and `advance.publish_active_epoch_ms` reached 338.94 ms.

### Verification

- `uv run pytest tests/manual/test_31_subjective_runtime_epochs.py -q`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k 'multi_entity or necrotic_bless or magic_missile or reducer_preserves_multi_entity_target_options'`
- `uv run pyright ai/subjective/epochs.py ai/external/state.py dnd/entity.py tests/manual/test_31_subjective_runtime_epochs.py`
- `uv run pytest tests/manual/test_09_action_discovery_and_costs.py -q`
- `uv run pytest tests/manual/test_37_ai_validation_arenas.py -q -k 'line_aoe_corridor or condition_lock_sanctum or catalog'`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q`

### Next Targets

- Instrument subjective publication/projection subphases.
- Add explicit value comparison for tactical environment objects such as trap levers.
- Continue alternating character and monster surfaces instead of staying on the line-AoE fixture.

## 2026-07-03 - Trap Lever Tactical Object Policy V34

### Live Probe

Ran isolated server `8080` with `trap_lever_killzone` in `human_hero` mode.

Artifacts:

- `/tmp/dnd_ai_v34_probe/trap_lever_probe.json`
- `/tmp/dnd_ai_v34_probe/trap_lever_summary.json`
- `/tmp/dnd_ai_v34_probe/server.log`

The monster AI produced 31 policy ticks and 31 command results. The selected sequence included `Necrotic Bless__slot_2`, movement/spacing, Dodge, `Pull Lever__item_...`, melee attacks, and Eldritch Blast. The important correction is that `Pull Lever` appeared in the live trace with reason `use_tactical_environment_object`.

### Findings

- The lever was already a legal item-use row in `self_actions`; the bug was policy-side, not action discovery.
- The behavior tree only had object logic for doors, so tactical environment objects were invisible to high-level choice.
- A narrow trap-lever branch is enough for this fixture and avoids turning the enemy policy into arbitrary object clicking.
- A remaining speed issue persists: the live probe still produced one follow-up `get_available_actions` spike at 208.841 ms after Dodge.

### Integrated Changes

- Added `_use_tactical_environment_object` before ordinary damage pressure.
- Added `_is_trap_lever_action` and `_has_known_hazard_pressure`.
- Added a logical annotation for the tactical environment-object branch.
- Kept the branch intentionally narrow: it only uses recognized trap-lever rows when hazardous tiles are known.
- Fixed the external reducer so simple rows do not repopulate empty `target_options` from `valid_targets`; multi-target rows still preserve target options.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k 'trap_lever or tactical_environment_object or logical_annotations or reducer_keeps_simple_entity_rows_lean or reducer_preserves_multi_entity_target_options'`
- `uv run pyright ai/external/policy.py ai/external/state.py tests/manual/test_35_subjective_external_ai.py`
- `uv run pytest tests/manual/test_37_ai_validation_arenas.py -q -k 'trap_lever_killzone or catalog'`
- `uv run pytest tests/manual/test_29_external_ai_subprocess.py -q -k 'known_objects or door or external_ai'`

### Next Targets

- Investigate the remaining 208.841 ms follow-up `get_available_actions` spike after Dodge.
- Instrument subjective publication/projection subphases that still show live spikes.
- Test other tactical objects carefully, especially Fireball cannon and floor potions, before generalizing the object branch.

## 2026-07-03 - Subjective Projection Speed V35

### Motivation

The V33/V34 speed work moved the bottleneck away from rich action discovery and into subjective publication. Live probes showed `publish.command_result_ms` and `advance.publish_active_epoch_ms` spikes, with `projection.project_events_ms` consuming roughly 183 ms in the V35 line-AoE timing artifact. That path needed tighter attribution before more enemy-policy tuning, because a slow subjective stream makes every controller feel worse regardless of tactical quality.

### Integrated Changes

- `EventQueue.iter_events_since()` now yields raw events lazily instead of allocating a sliced list of every post-cursor event.
- The subjective observation projector now skips non-completion lifecycle events before invoking the expensive subjective projection path.
- Projection timing now separates completion-event projection from observation-cursor assignment.
- The change keeps the event stream semantics intact: callers still iterate `(index, event)` rows with zero-based raw event indexes.

### Live Probe

Ran isolated server `8082` with `zone_control_web_gauntlet` in `human_hero` mode to rotate back to a Barbarian-facing surface rather than staying on Sorcerer line-AoE.

Artifacts:

- `/tmp/dnd_ai_v36_probe/validation_probe.json`
- `/tmp/dnd_ai_v36_probe/validation_probe_summary.json`
- `/tmp/dnd_ai_v36_probe/server.log`

The probe produced 29 policy ticks and 29 command results. The selected command sequence included movement, ranged attacks, melee attacks, `Magic Missile__slot_1`, `Jump`, `Dodge`, `Invisibility__slot_2`, and turn boundaries.

### Findings

- The old subjective publication/projection spike did not reproduce in this arena after the iterator/projection filter change. No publication/projection subphase crossed the 1 ms reporting threshold.
- Max server command total was 101.402 ms.
- The remaining reported server spike was `execute.action_by_index_ms` at 101.161 ms, which means the next latency layer is actual action execution, not observation publication.
- Policy selection stayed cheap: max `policy_selection_ms` was 0.16 ms and max state reduction was 0.42 ms.
- Boundary behavior was healthy: after human pass turns, the external AI returned control to the human boundary in 3.56 ms and 1045.981 ms across the two waits.

### Verification

- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q -k 'timing or command_result or epoch or snapshot'`
- `uv run pytest tests/manual/test_28_subjective_observation_stream.py -q`
- `uv run pytest tests/manual/test_25_live_replication_streams.py -q`
- `uv run pytest tests/engine_book/test_chapter_04_event_lifecycle.py -q`
- `uv run pytest tests/manual/test_37_ai_validation_arenas.py -q`
- `uv run pyright ai/observation/projector.py dnd/core/events.py server/event_server.py`

### Next Targets

- Instrument `execute.action_by_index_ms` around concrete action execution internals.
- Run the next rotation as Sorcerer Hero or skeleton-side control.
- Keep using the 23-arena validation catalog before adding more global content.

## 2026-07-03 - Action Execution And Arena Breadth V36

### Context

I did not change global monster, spell, item, gear, or NeuroClient defaults in this slice. The anti-overfit surface is currently scenario-level: the opt-in validation catalog already has 23 arenas built from existing simulator content, including class-built enemies, skeleton/goblin factories, registered spells, scrolls, wands, potions, weapon coats, doors, water, difficult terrain, darkness, reveal tools, trap levers, environmental devices, support/control spells, anti-healing necromancy, forced movement, line/AoE geometry, and ranged loadouts.

That is the right place to vary enemy-AI pressure for now. New bestiary or global gear changes should come only when an observed behavior gap cannot be exercised with the existing catalog.

### Integrated Changes

- AI command execution now requests lean action results with `include_state=false`, so the AI command path does not pay to serialize the full human client state after every command.
- Timed AI action results carry nested `action_server_timing`, preserving the outer command timing separately from the underlying `/action/execute` route timing.
- Added optional low-level action timing hooks through `dnd.action_timing`.
- Instrumented `Move._apply()` and `GridMap.move_entity()` to attribute movement cost to event posting, grid updates, position updates, and final senses refresh.
- Tightened `SpatialSensesCallback` so cheap relevance checks run before expensive snapshots, while preserving reveal behavior for perceivability changes in subscribed cells.

### Live Probe

Ran isolated server `8083` with `line_aoe_corridor` in `human_hero` mode, rotating back to Sorcerer-facing pressure after the V35 Barbarian-facing probe.

Artifacts:

- `/tmp/dnd_ai_v37_probe/line_aoe_probe.json`
- `/tmp/dnd_ai_v37_probe/line_aoe_summary.json`
- `/tmp/dnd_ai_v37_probe/server.log`

The monster AI produced 34 policy ticks and 34 command results over three human pass-turn cycles. It selected Magic Missile, Mark Target, ranged attacks, melee attacks, movement toward the visible enemy, retreat, spread-from-allies movement, hold-spacing end turns, and ordinary turn ends.

### Findings

- The old full-state serialization problem is no longer the main AI command-path cost.
- Policy work is cheap: average policy tick was 5.582 ms, and the policy-selection part remains sub-millisecond in ordinary ticks.
- Movement is still too expensive in worst cases: max `execute_by_index_ms` was 101.528 ms, with `movement.update_position_ms` at 69.58 ms, `grid.move_entity.fire_entity_entered_ms` at 44.31 ms, `grid.move_entity.fire_entity_left_ms` at 24.958 ms, and `movement.final_update_senses_ms` at 22.019 ms.
- End-turn can still spike because it publishes the next active epoch: max `end_turn.total_route_ms` was 377.441 ms, max `advance.publish_active_epoch_ms` was 347.417 ms, and max `advance.publish_active_epoch.build_affordance_set_ms` was 267.903 ms.
- Command-result projection still has rare spikes: max `publish.command_result_ms` was 151.476 ms.
- The validation catalog already covers the “don’t overfit to skeleton door” concern at fixture level; the next priority is rotating through it and improving the shared runtime/policy, not adding global content noise.

### Verification

- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q -k 'accepted_command or failed_action_result or snapshot_current_epoch'`
- `uv run pytest tests/manual/test_18_sessions_api_client_contract.py -q -k 'execute_action_by_index_returns_state_logs_and_cursors'`
- `uv run pytest tests/manual/test_08_world_model_and_movement.py -q`
- `uv run pytest tests/engine_book/test_manual_11_grid_tiles_terrain_movement.py -q -k 'movement or opportunity or difficult or forced or path'`
- `uv run pytest tests/manual/test_12_perception_light_stealth_and_invisibility.py -q`
- `uv run pyright dnd/action_timing.py dnd/actions.py dnd/core/gridmap.py server/api_models.py server/event_server.py tests/manual/test_36_seamless_subjective_runtime.py`
- `uv run pyright dnd/blocks/sensory.py dnd/core/gridmap.py dnd/actions.py server/event_server.py`

### Next Targets

- Optimize movement spatial event dispatch and senses refresh; that is now the clearest action-execution cost.
- Instrument active-epoch publishing/build-affordance spikes on end-turn, especially the rare `build_affordance_set` and command-result projection spikes.
- Rotate the next live validation into skeleton-side control or one of the existing non-line-AoE arenas.
- Keep using the existing 23-arena catalog before adding new global monsters/spells/gear.

## 2026-07-03 - Known-Space Path Invalidation V37

### Integrated Change

Tightened `SpatialSensesCallback` path invalidation for spatial movement hints. A movement event now dirties an observer's path cache only when the affected position touches that observer's known path domain:

- currently visible cells;
- previously seen cells;
- current path destinations;
- current safe-path destinations.

Self movement and visible/perceivable entity changes still use the existing sensory update behavior. The change is intended to stop off-screen movement from mutating unrelated observer caches without removing the engine event itself.

### Verification

- `uv run pytest tests/engine_book/test_chapter_12_senses_light_stealth.py -q -k 'self_movement or distant_movement or perceivability or passive_perception or hidden_cell'`
- `uv run pytest tests/manual/test_12_perception_light_stealth_and_invisibility.py -q`
- `uv run pytest tests/manual/test_08_world_model_and_movement.py -q`
- `uv run pytest tests/engine_book/test_manual_11_grid_tiles_terrain_movement.py -q -k 'movement or opportunity or difficult or forced or path'`
- `uv run pyright dnd/blocks/sensory.py tests/engine_book/test_chapter_12_senses_light_stealth.py`

### Live Probe

Ran isolated server `8084` with `caster_crossfire` in `codex_monsters` mode, rotating away from the previous Sorcerer-human probe and ending at a Codex monster-side boundary.

Artifacts:

- `/tmp/dnd_ai_v38_probe/caster_crossfire_codex_monsters_probe.json`
- `/tmp/dnd_ai_v38_probe/caster_crossfire_codex_monsters_summary.json`
- `/tmp/dnd_ai_v38_probe/server.log`

The external Barbarian hero produced 4 policy ticks and 3 command results before handing control to the Codex monster side after 3556.047 ms. It selected:

- move toward visible enemy;
- melee attack;
- extra attack;
- end turn.

### Findings

- The new negative parity case passed: distant off-screen movement no longer dirties an unrelated observer's paths or emits a sensory update for that observer.
- The rotated live probe still shows visible movement as the hard cost. The one Move command reached `execute_by_index_ms` 89.82 ms, with `grid.move_entity.fire_entity_entered_ms` 47.11 ms and `movement.final_update_senses_ms` 38.644 ms.
- Policy selection remained cheap: max policy tick was 2.64 ms and average policy tick was 1.82 ms.
- Follow-up epoch work was healthy in this small probe: max `publish.followup_epoch_ms` was 10.291 ms.

### Next Targets

- Optimize visible movement sensory emission and final senses recomputation; off-screen filtering is correct but not enough for open visible arenas.
- Add deeper timing inside `update_entity_visibility()` and `update_entity_senses()` to separate FOV, light filtering, entity/object refiltering, pathing, safe-pathing, and subscription updates.
- Keep the next validation rotation away from `caster_crossfire` and `line_aoe_corridor`.

## 2026-07-03 - Senses Recompute Timing V38

### Integrated Change

Added AI-command-scoped timing inside:

- `Entity.compute_senses_from_position()`
- `Entity.update_entity_senses()`
- `Entity.update_entity_visibility()`

The timing only activates when the existing action-timing context is active, so ordinary engine calls do not pay detailed timing overhead. I also replaced the movement aggregate timing idiom with an explicit `record_action_elapsed()` helper so aggregate phase labels are easier to audit.

### Verification

- `uv run pytest tests/engine_book/test_chapter_12_senses_light_stealth.py -q -k 'self_movement or distant_movement or perceivability or passive_perception or hidden_cell'`
- `uv run pytest tests/manual/test_12_perception_light_stealth_and_invisibility.py -q`
- `uv run pytest tests/manual/test_08_world_model_and_movement.py -q`
- `uv run pytest tests/engine_book/test_manual_11_grid_tiles_terrain_movement.py -q -k 'movement or opportunity or difficult or forced or path'`
- `uv run pyright dnd/action_timing.py dnd/actions.py dnd/entity.py dnd/blocks/sensory.py tests/engine_book/test_chapter_12_senses_light_stealth.py`

### Live Probe

Ran isolated server `8085` with `ranged_loadout_kiting_ring` in `human_hero` mode, avoiding the recent `caster_crossfire` and `line_aoe_corridor` fixtures.

Artifacts:

- `/tmp/dnd_ai_v39_probe/ranged_loadout_probe.json`
- `/tmp/dnd_ai_v39_probe/ranged_loadout_summary.json`
- `/tmp/dnd_ai_v39_probe/server.log`

The external monster AI produced 25 policy ticks and 24 command results across two human pass-turn cycles. The selected sequence included Necrotic Bless with multiple allies, movement/spread/retreat rows, ranged attacks, extra attacks, Jump, Invisibility from an item, and end turns.

### Findings

- Policy remains cheap: average policy tick was 0.954 ms and max policy tick was 2.16 ms.
- Worst command result was 319.81 ms, mostly from server-side work rather than policy.
- The movement bottleneck is now concretely split:
  - max `execute_by_index_ms`: 92.978 ms;
  - max `movement.update_position_ms`: 46.955 ms;
  - max `grid.move_entity.fire_entity_entered_ms`: 43.667 ms;
  - max `movement.final_update_senses_ms`: 40.398 ms;
  - max `entity.update_visibility.compute_fov_ms`: 34.228 ms;
  - max `entity.update_senses.compute_ms`: 39.858 ms;
  - max `senses.compute_paths_ms`: 16.946 ms;
  - max `senses.compute_safe_paths_ms`: 15.757 ms.
- The small probe also reproduced a command-result projection spike: max `publish.command_result_ms` was 135.685 ms.
- A broad FOV cache is not safe to add casually: the grid has no current topology revision key, and FOV must invalidate on tile/object/directional vision changes.

### Next Targets

- Design an invalidation-safe FOV/path cache, probably with explicit grid topology revisions for vision, movement, light, and propagation.
- Investigate why command-result projection can still spike over 100 ms after the EventQueue iterator/filter work.
- Keep rotating through the validation catalog; avoid `ranged_loadout_kiting_ring`, `caster_crossfire`, and `line_aoe_corridor` next.

## 2026-07-03 - Movement Visibility Cache V40

### Integrated Change

Added a one-shot visibility cache for movement-end senses refreshes:

- `Entity.update_entity_visibility()` stores the last visibility-only result on the observer's `Senses` block.
- `Entity.update_entity_senses(..., reuse_visibility_cache=True)` reuses that result only when the caller explicitly opts in and the observer position plus `max_distance` still match.
- `Move` and `Jump` final refreshes opt in, because their self-movement spatial events already recompute visibility before the final full senses refresh.
- Movement actions clear any previous visibility cache before stepping, so failed or interrupted movement cannot consume stale visibility from an unrelated earlier update.
- Ordinary senses updates still cold-recompute visibility. This avoids pretending we have a global FOV cache before the grid has explicit topology/light revision keys.

### Verification

- `uv run pytest tests/engine_book/test_chapter_12_senses_light_stealth.py -q -k 'final_movement_refresh or self_movement or distant_movement or perceivability or passive_perception or hidden_cell'`
- `uv run pytest tests/manual/test_12_perception_light_stealth_and_invisibility.py -q`
- `uv run pytest tests/manual/test_08_world_model_and_movement.py -q`
- `uv run pytest tests/engine_book/test_manual_11_grid_tiles_terrain_movement.py -q -k 'movement or opportunity or difficult or forced or path'`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k 'lean_subjective_runtime or entity_control_policy or door or multi_entity'`
- `uv run pyright dnd/blocks/sensory.py dnd/entity.py dnd/actions.py tests/engine_book/test_chapter_12_senses_light_stealth.py`

### Live Probe

Ran isolated server `8086` with `darkness_reveal_labyrinth` in `codex_monsters` mode, rotating to a Sorcerer-facing setup after the previous Barbarian-facing ranged loadout run.

Artifacts:

- `/tmp/dnd_ai_v40_probe/darkness_reveal_probe.json`
- `/tmp/dnd_ai_v40_probe/darkness_reveal_summary.json`
- `/tmp/dnd_ai_v40_probe/server.log`

The external Sorcerer hero produced 3 policy ticks and 3 command results before handing control to the Codex monster side after 3355.833 ms. It selected:

- `Invisibility__slot_2` on self through `cast_controlled_support_spell`;
- `Move` to `(5, 1)` through `explore_no_contact`;
- `End Turn`.

### Findings

- The one-shot cache is live in command timing: the Move command reports `senses.reuse_visibility_cache_ms` and `senses.reuse_visible_entities_objects_ms` during final senses refresh.
- In this rotated probe, movement final refresh dropped to pathing-only work: `movement.final_update_senses_ms` maxed at 19.52 ms, with `senses.compute_paths_ms` at 18.522 ms.
- The remaining visible movement cost is now mostly the spatial-enter visibility update: `grid.move_entity.fire_entity_entered_ms` reached 40.556 ms and `entity.update_visibility.compute_fov_ms` reached 22.107 ms.
- Policy stayed cheap: average policy tick was 1.617 ms and max policy tick was 2.49 ms.
- The probe exposed one operator ergonomics issue: direct script startup with `uv run python server/event_server.py` failed to import the top-level `ai` package. The module form, `uv run python -m server.event_server`, started cleanly.

### Next Targets

- Optimize per-step visible movement sensory emission; final refresh now reuses visibility, but self-entered spatial events still recompute FOV for every visible movement step.
- Add explicit grid revision keys before attempting broader FOV/path caches across unrelated calls.
- Keep rotating through the validation catalog; the next autonomous probe should avoid `darkness_reveal_labyrinth`, `ranged_loadout_kiting_ring`, `caster_crossfire`, and `line_aoe_corridor`.

## 2026-07-03 - Grid FOV Revision Cache V41

### Integrated Change

Added invalidation-aware FOV caching inside `GridMap`:

- Grid topology now tracks spatial channel revisions for vision, movement, light, and propagation.
- `GridMap.compute_fov()` caches geometric FOV by origin, max distance, observer UUID, magical-darkness-piercing capability, and vision revision.
- Vision-cache invalidation is wired through tile creation/removal, intrinsic directional borders, object placement/removal, object blocking changes, directional blocker recomputation, magical-darkness-relevant light batches, and grid clearing.
- The cache returns copies to callers, so callers cannot mutate cached FOV lists.
- Added a regression test that warms FOV, places a vision-blocking object, and proves the next FOV recompute sees the new blocker instead of using stale cache data.

### Verification

- `uv run pytest tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py -q -k 'directional_channels or fov_cache or directional_borders or replacing_object'`
- `uv run pytest tests/engine_book/test_chapter_12_senses_light_stealth.py -q -k 'final_movement_refresh or self_movement or distant_movement or magical_darkness or light_sources'`
- `uv run pytest tests/manual/test_08_world_model_and_movement.py -q`
- `uv run pytest tests/manual/test_12_perception_light_stealth_and_invisibility.py -q`
- `uv run pytest tests/engine_book/test_manual_11_grid_tiles_terrain_movement.py -q -k 'movement or opportunity or difficult or forced or path'`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k 'lean_subjective_runtime or entity_control_policy or door or multi_entity'`
- `uv run pyright dnd/core/gridmap.py dnd/blocks/base_item.py dnd/blocks/sensory.py dnd/entity.py dnd/actions.py tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py tests/engine_book/test_chapter_12_senses_light_stealth.py`

### Live Probe

Ran isolated server `8087` with `skeleton_anti_aoe_split` in `codex_monsters` mode, rotating into the skeleton-side validation slot after the previous Sorcerer-facing run.

Artifacts:

- `/tmp/dnd_ai_v41_probe/skeleton_split_probe.json`
- `/tmp/dnd_ai_v41_probe/skeleton_split_summary.json`
- `/tmp/dnd_ai_v41_probe/server.log`

The external Sorcerer hero produced 3 policy ticks and 3 command results before handing control to the Codex monster side after 3643.368 ms. It selected:

- level-1 `Magic Missile` into the split Warlock through `cast_visible_enemy_spell`;
- retreat movement to `(1, 13)` through `retreat_from_visible_enemy`;
- `End Turn` through `hold_ranged_spacing`.

### Findings

- The cache is active and timed: the Move command reported `grid.compute_fov.cache_miss_ms`.
- This particular probe mostly missed the FOV cache because the actor moved into a position that had not previously computed FOV. That means V41 is a correctness-safe scaffold, not yet the full per-step visibility speed win.
- Cold per-step visibility improved versus the prior worst case but remains meaningful: `entity.update_visibility.compute_fov_ms` reached 13.806 ms, while `grid.move_entity.fire_entity_entered_ms` reached 39.065 ms.
- Final movement refresh still used the V40 one-shot cache and remained pathing-only: `movement.final_update_senses_ms` reached 19.482 ms, with `senses.compute_paths_ms` at 17.509 ms.
- Policy stayed cheap enough but was not as tiny as the previous small probe: average policy tick was 3.857 ms and max policy tick was 6.19 ms, mostly from affordance projection and state reduction over a larger open arena.
- End-turn publication still has an unexplained aggregate spike: `advance.publish_active_epoch_ms` reached 212.027 ms even though measured subphases were small. That needs its own attribution pass.

### Next Targets

- Reduce cold per-step `update_entity_visibility()` work; FOV cache only helps repeated origins.
- Attribute the `advance.publish_active_epoch_ms` aggregate spike where subphase timing does not explain the total.
- Rotate the next live validation to a Barbarian-facing or environment/resource arena, avoiding the recent skeleton split, darkness reveal, ranged loadout, caster crossfire, and line-AoE fixtures.

## 2026-07-03 - Damage Affinity Policy V42

### Integrated Change

Added the first damage-affinity data path for enemy policy:

- Visible subjective entity facts now expose known damage vulnerabilities, resistances, and immunities.
- Available-action rows now expose known action damage types for equipped weapon attacks and spells with `spell_damage_type`.
- Decision epochs, compatibility action serialization, the external reducer, and the behavior-tree action rows preserve those damage type labels.
- The external policy now applies a bounded `_damage_matchup_score()` in attack and offensive spell scoring.
- Added `damage_affinity_weapon_lab`, a validation arena where a monster-side Fighter carries a Shortsword and Club against a hero-side skeleton with bludgeoning vulnerability.

### Verification

- `uv run pytest tests/manual/test_37_ai_validation_arenas.py -q`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q`
- `uv run pytest tests/manual/test_28_subjective_observation_stream.py -q`
- `uv run pytest tests/manual/test_29_external_ai_subprocess.py -q -k 'reducer or policy or subprocess or damage or door or external'`
- `uv run pytest tests/manual/test_31_subjective_runtime_epochs.py -q -k 'epoch or rows or affordance or hidden'`
- `uv run pyright dnd/core/base_actions.py dnd/entity.py server/event_server.py ai/subjective/models.py ai/subjective/epochs.py ai/observation/models.py ai/observation/projector.py ai/external/state.py ai/external/policy.py dnd/scenarios/ai_validation_arenas.py tests/manual/test_28_subjective_observation_stream.py tests/manual/test_29_external_ai_subprocess.py tests/manual/test_35_subjective_external_ai.py tests/manual/test_37_ai_validation_arenas.py`

### Findings

- The current validation catalog was already broad enough for terrain, doors, spells, resources, and support logic, so this slice did not add new monsters or global equipment.
- A real missing enemy-AI input was identified instead: the reduced state could not express that a target was vulnerable, resistant, or immune to a damage type.
- The policy improvement is deliberately small. Vulnerability lowers a row score; resistance and immunity raise it. This nudges choices without replacing kill pressure, action economy, range fit, or resource discipline.

### Next Targets

- Run a live validation probe through a Barbarian-facing or environment/resource arena before sampling the new weapon-affinity lab too heavily.
- Extend spell damage-type valuation only after live evidence shows whether the bounded matchup term improves tactical play without over-prioritizing weak damage-type matches.
- Continue the performance line from V41: reduce cold per-step visibility work and attribute the active-epoch publication spike.

## 2026-07-03 - Validation Catalog Diversity V43

### Integrated Change

Expanded the AI validation catalog with three fixture-only arenas:

- `field_cache_loot_race`: an archer Fighter starts adjacent to a lootable `StorageChest` containing scrolls, an acid flask, a healing potion, and a weapon coat while mixed enemies apply pressure.
- `cleanse_support_triage`: a support caster starts with a wounded poisoned ally and a blinded ranged ally, making restoration and healing rows visible beside attacks.
- `multi_target_missile_allocation`: a Sorcerer faces several wounded visible enemies so Magic Missile and Scorching Ray expose multi-target projectile and target metadata.

No core spell, item, equipment, or enemy-policy behavior was changed in this slice.

### Verification

- `uv run pytest tests/manual/test_37_ai_validation_arenas.py -q`
- `uv run pytest tests/manual/test_38_ai_validation_server_start.py -q`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q`
- `uv run pyright dnd/scenarios/ai_validation_arenas.py tests/manual/test_37_ai_validation_arenas.py tests/manual/test_38_ai_validation_server_start.py tests/manual/test_39_ai_validation_harness.py`
- `uv run python -m json.tool ai/AGENT_UX_ITERATION_STATS.json`

### Findings

- The simulator already has enough implemented content to avoid tuning only against the standard skeleton door fight.
- The validation catalog now covers 27 arenas across doors, water, hazards, items, support, high-level spells, class enemies, teleports, vision, conditions, damage affinities, chests, restoration, and multi-target pressure.
- Multi-target spell discovery exposes legal targets and projectile counts, but it still does not precompute explicit allocation bundles. That likely explains part of the observed Magic Missile / Necrotic Bless targeting weakness.

### Next Targets

- Run a live Barbarian-facing or environment/resource probe through one of the broader fixtures before adding more policy code.
- If the multi-target allocation probe confirms the same behavior, design bundle metadata for `MULTI_ENTITY` actions instead of expecting the agent to infer allocations from raw target rows.
- Keep new arena additions evidence-driven; the next enemy-AI improvement should come from live probe notes, not from making the catalog bigger for its own sake.

## 2026-07-04 - Trap Lever Live Probe V44

### Integrated Change

Ran `trap_lever_killzone` in `human_hero` mode as a live Barbarian-facing environment probe. The human-side Barbarian only ended turns, so the run isolated the external enemy AI.

Artifacts:

- `/tmp/dnd_ai_v44_probe/trap_lever_human_hero_probe.json`
- `/tmp/dnd_ai_v44_probe/trap_lever_summary.json`
- `/tmp/dnd_ai_v44_probe/server.log`

The probe completed 4 hero boundaries and 65 combat log entries. The external side emitted 41 `policy_tick` traces and 41 command results. Most importantly, `Validation Lever Guard` selected `Pull Lever` through `use_tactical_environment_object`, proving the environment-object branch works outside the standard skeleton doorway setup.

Added nested external-client timing attribution:

- `affordance_timing` for compact position rows and action-row normalization.
- `reduction_timing` for materialized-state validation, session context, controlled entities, visible/remembered enemies, known objects, known closed doors, known tiles, action normalization, and final state construction.

These timings are now included in `external_ai.policy_tick`, so future live probes can identify whether a client-side spike came from projection, reduction, row normalization, or the behavior policy itself.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k 'normal_path or timing_sinks or epoch_projection or reducer or policy or door or tactical or multi_entity'`
- `uv run pytest tests/manual/test_29_external_ai_subprocess.py -q -k 'reducer or policy or subprocess or damage or door or external'`
- `uv run pyright ai/external/state.py ai/external_melee_agent.py tests/manual/test_35_subjective_external_ai.py tests/manual/test_29_external_ai_subprocess.py`
- `uv run python -m json.tool ai/AGENT_UX_ITERATION_STATS.json`

### Findings

- Environment-object policy succeeded: the guard pulled the lever before closing and attacking.
- Policy selection itself remained tiny: average 0.09 ms, max 0.34 ms.
- One policy tick reached 97.21 ms, almost entirely from a 95.39 ms affordance-projection outlier.
- A separate state-reduction outlier reached 82.47 ms.
- Command execution still has the larger user-visible spikes: max command elapsed was 356.82 ms, with `advance.publish_active_epoch_ms` reaching 248.199 ms and `execute_action_by_index_ms` reaching 91.078 ms.
- Movement remains the speed path: movement-heavy commands still spent roughly 17-19 ms in `senses.compute_paths` / final senses refresh.
- The Goblin Archer behavior looked clunky: it often moved, retreated, or Dodged instead of maintaining a clean ranged pressure pattern.
- `Necrotic Bless` reported `total_targets=2` but `target_names=[]`, which looks like a combat-log detail issue for multi-entity support actions.

### Next Targets

- Rotate the next live probe to a Sorcerer-facing or skeleton-side validation slot; avoid another Barbarian/environment fixture immediately.
- Use the new nested policy-tick timings to attribute the next projection/reduction spike instead of guessing.
- Investigate ranged spacing/line/range behavior for archer-style enemies.
- Keep the multi-target allocation issue on deck, but validate it in the dedicated `multi_target_missile_allocation` arena before changing spell semantics.

## 2026-07-04 - Multi-Target Log Enrichment V45

### Live Probe

Ran `multi_target_missile_allocation` in `codex_monsters` mode to rotate away from the previous Barbarian/environment run and directly inspect Sorcerer multi-target pressure.

Pre-fix artifacts:

- `/tmp/dnd_ai_v45_probe/multi_target_codex_monsters_probe.json`
- `/tmp/dnd_ai_v45_probe/multi_target_codex_monsters_summary.json`
- `/tmp/dnd_ai_v45_probe/server.log`

The first run showed the external Sorcerer made a strong tactical choice: `Fireball__slot_3` at `(8, 5)`, hitting all three wounded enemies. That means the current geometry did not force Magic Missile allocation. The real defect was observability: the parent `multi_entity_action` log had `target_names=[]`, `per_target_damage=[]`, and empty per-target detail even though child logs contained the actual target names, damage, and save results.

### Integrated Change

Changed event completion so parent `MULTI_ENTITY_ACTION` combat logs are enriched after child combat logs are attached.

The parent data now aggregates:

- child target names;
- per-target final damage;
- save success/failure counts;
- per-target structured child payloads.

This is deliberately an event/combat-log fix, not an AI policy workaround. The authoritative event tree already had the data; the parent summary now exposes it cleanly to the agent stream and dashboard.

### Patched Rerun

Post-fix artifacts:

- `/tmp/dnd_ai_v45_probe_rerun/multi_target_codex_monsters_probe.json`
- `/tmp/dnd_ai_v45_probe_rerun/multi_target_codex_monsters_summary.json`
- `/tmp/dnd_ai_v45_probe_rerun/server.log`

The patched rerun produced:

- 3 policy ticks;
- selected `Fireball__slot_3`, then `Move`, then `End Turn`;
- parent Fireball target names: `Validation Missile Archer`, `Validation Missile Warrior`, `Validation Missile Goblin`;
- parent per-target damage: `13`, `25`, `11`;
- parent save counts: 2 succeeded, 1 failed;
- parent per-target payload count: 3.

Policy remained cheap:

- first policy tick: 5.63 ms;
- max policy selection: 0.15 ms;
- max affordance projection: 2.19 ms;
- max state reduction: 3.29 ms;
- max `normalize_position_actions`: 2.692 ms.

The server-side command path is still the slow part:

- first Fireball command total: 313.119 ms;
- `execute.action_by_index_ms`: 261.5 ms;
- `publish.command_result.projection.project_completion_events_ms`: 17.292 ms;
- follow-up epoch `get_available_actions_ms`: 31.419 ms;
- end-turn `advance.publish_active_epoch_ms`: 99.19 ms.

### Verification

- `uv run pytest tests/manual/test_13_spellcasting_core.py -q -k 'magic_missile_auto_hits_multiple_darts'`
- `uv run pytest tests/manual/test_37_ai_validation_arenas.py -q -k 'multi_target'`
- `uv run pytest tests/manual/test_28_subjective_observation_stream.py -q -k 'combat or log or frame'`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k 'multi_entity or normal_path or timing_sinks'`
- `uv run pyright dnd/core/events.py tests/manual/test_37_ai_validation_arenas.py`
- `uv run python -m json.tool ai/AGENT_UX_ITERATION_STATS.json`

Pyright over the full `tests/manual/test_13_spellcasting_core.py` file still reports pre-existing optional-narrowing issues unrelated to the new assertions, so the clean type gate was run on the engine change and the new validation test.

### Findings

- The Sorcerer policy made the correct high-level AoE decision in this fixture.
- This arena does not yet prove Magic Missile allocation is fixed or broken, because Fireball was simply better.
- Multi-target parent logs are now agent-usable; the previous empty `target_names` issue is fixed at the event/log layer.
- The dominant speed issue in this probe is spell execution, especially Fireball `execute_by_index`, not policy selection or client reduction.

### Next Targets

- Rotate next to skeleton-side or resource/gear pressure; do not run another Sorcerer spell fixture immediately.
- Investigate the Fireball execution cost path before trying to optimize client-side policy again.
- Use the enriched `per_target_logs` in agent summaries for multi-target spells.
- Test Magic Missile allocation only in a geometry where AoE is not the obvious best row.

## 2026-07-04 - Damage Affinity And Arena Breadth V46

### Live Probe

Ran `damage_affinity_weapon_lab` in `human_hero` mode so the external monster side had to play against a hero-side skeleton with bludgeoning vulnerability.

Artifacts:

- `/tmp/dnd_ai_v46_probe/damage_affinity_human_hero_probe.json`
- `/tmp/dnd_ai_v46_probe/damage_affinity_human_hero_summary.json`
- `/tmp/dnd_ai_v46_probe/damage_affinity_human_hero_rerun_probe.json`
- `/tmp/dnd_ai_v46_probe/damage_affinity_human_hero_rerun_summary.json`
- `/tmp/dnd_ai_v46_probe/server.log`

The first probe was useful failure: I sent `entity_uuid` to `/game/join`, but the current API expects `entity_uuids`. The join returned `success=false` and the human session controlled no entities, so the encounter sat on the hero turn and no monster policy ticks fired. This is a real operator/API footgun to fix or wrap before more manual probes.

After rerunning with the correct payload, the external monster side completed the fight in about 4.0 seconds:

- 65 agent events;
- 9 policy ticks;
- 9 command acks;
- 8 command results;
- 15 combat log entries.

The key tactical result was correct: `Validation Crusher Captain` selected `Attack_MELEE_OFF` with `Club` into `Validation Vulnerable Skeleton Hero`, producing bludgeoning damage and ending the encounter. That validates the gear/damage-affinity path outside a pure unit test.

### Integrated Change

Expanded the opt-in validation catalog from 27 to 29 arenas:

- `resistance_weapon_counterplay`
  - non-skeleton shield Fighter target;
  - piercing resistance;
  - bludgeoning vulnerability;
  - monster-side Fighter carrying Shortsword and Club.
- `multi_projectile_no_aoe_lab`
  - Sorcerer with Magic Missile and Scorching Ray;
  - no Fireball or Lightning Bolt;
  - spread wounded enemies so projectile allocation can be tested without an AoE escape hatch.

This is fixture/content breadth only. It does not change global monster factories, spell implementations, gear defaults, NeuroClient startup, or the default arena.

### Verification

- `uv run pytest tests/manual/test_37_ai_validation_arenas.py -q`
- `uv run pyright dnd/scenarios/ai_validation_arenas.py tests/manual/test_37_ai_validation_arenas.py`
- `uv run python -m json.tool ai/AGENT_UX_ITERATION_STATS.json`

### Findings

- The external enemy policy can use streamed weapon damage types and target vulnerabilities in a real server-run fight.
- The existing catalog was already broad: class-built enemies, scrolls, wands, potions, weapon coats, doors, darkness, reveal tools, traps, levers, loot chests, support/restoration, high-level spells, teleport, and zone control were already present.
- The old `multi_target_missile_allocation` arena did not force Magic Missile because Fireball was simply stronger. The new no-AoE projectile lab closes that testing hole.
- A policy tick still spiked to 95.36 ms, almost entirely from `normalize_position_actions_ms=94.328`.
- The slowest command ack reached 198.345 ms, mostly from `project_completion_events_ms=167.836`.

### Next Targets

- Run `multi_projectile_no_aoe_lab` live to inspect Magic Missile and Scorching Ray allocation without Fireball.
- Fix or wrap the `/game/join` singular `entity_uuid` footgun.
- Keep rotating resource/gear arenas, but do not over-sample damage-affinity fixtures now that this path has one live win.

## 2026-07-04 - Projectile Allocation And Join Alias V47

### Interface Fix

The V46 damage-affinity probe exposed a practical API footgun: a one-entity join sent as `entity_uuid` was syntactically accepted by FastAPI/Pydantic but controlled no entity because the contract only accepted `entity_uuids`.

Integrated fix:

- `JoinGameRequest` now accepts `entity_uuid` as a singular convenience alias.
- The server merges `entity_uuids` and `entity_uuid` into one de-duplicated request list.
- Existing `entity_uuids` list behavior is preserved.

### Live Probe

Ran `multi_projectile_no_aoe_lab` in `codex_monsters` mode to rotate back to a Sorcerer-side probe and test projectile allocation without Fireball.

Artifacts:

- `/tmp/dnd_ai_v47_probe/multi_projectile_no_aoe_codex_monsters_probe.json`
- `/tmp/dnd_ai_v47_probe/multi_projectile_no_aoe_codex_monsters_rerun_probe.json`
- `/tmp/dnd_ai_v47_probe/multi_projectile_no_aoe_codex_monsters_final_probe.json`
- `/tmp/dnd_ai_v47_probe/multi_projectile_no_aoe_codex_monsters_final_summary.json`
- `/tmp/dnd_ai_v47_probe/server.log`

The first run found a bad fixture: `Hold Person` was still in the supposedly projectile-only spell list, so the policy correctly selected control. After removing it, the second run found a subtler fixture issue: only one enemy was at cleanup HP, so the policy correctly used `Fire Bolt` to avoid slot overkill.

The final fixture sets all three visible enemies to low HP and keeps the Sorcerer list to projectile/cantrip spells. The final live probe selected:

- `Magic Missile__slot_1`;
- primary target: `Validation Projectile Warrior`;
- extra targets: `Validation Projectile Archer`, `Validation Projectile Goblin`;
- result: three target names and `per_target_damage=[5, 3, 5]` in the parent combat log.

### Integrated Change

- Removed `Hold Person` from `multi_projectile_no_aoe_lab`.
- Adjusted the fixture HPs to Warrior 4 HP, Archer 4 HP, Goblin 5 HP.
- Added a policy regression proving Magic Missile splits across several low-HP enemies instead of falling back to Fire Bolt.

### Verification

- `uv run pytest tests/manual/test_18_sessions_api_client_contract.py -q -k 'join or single_entity_uuid'`
- `uv run pyright server/api_models.py server/event_server.py tests/manual/test_18_sessions_api_client_contract.py`
- `uv run pytest tests/manual/test_37_ai_validation_arenas.py -q -k 'projectile or catalog'`
- `uv run pyright dnd/scenarios/ai_validation_arenas.py tests/manual/test_37_ai_validation_arenas.py`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k 'magic_missile or projectile or slot_overkill'`
- `uv run pyright ai/external/policy.py tests/manual/test_35_subjective_external_ai.py`
- `uv run python -m json.tool ai/AGENT_UX_ITERATION_STATS.json`

### Findings

- The policy and command path can correctly send multi-target `extra_target_uuids`.
- Parent multi-target logs now carry the useful summary data for Magic Missile too, not only Fireball.
- The agent-side decision path was fast: max policy tick 3.63 ms, max projection 1.54 ms, max reduction 2.58 ms.
- The server bottleneck shifted to post-action legal-row rebuild: after Magic Missile, `publish.followup_epoch.get_available_actions_ms` hit 179.773 ms while `execute.action_by_index_ms` was only 8.748 ms.
- Movement remains a smaller but persistent cost: the follow-up retreat had `execute.action_by_index_ms=63.75 ms`.

### Next Targets

- Investigate why Magic Missile follow-up epoch generation costs 179.773 ms after the projectile action.
- Rotate next to Barbarian-side or `resistance_weapon_counterplay`; do not run another Sorcerer probe immediately.
- Keep using failed validation fixtures as signal: if a lab can accidentally test the wrong thing, tighten the fixture or add an assertion.

## 2026-07-04 - Teleport Escape Reducer And Policy V48

### Content Scope

No global monster factories, spell implementations, gear rules, NeuroClient defaults, or default arena setup were changed in this slice. The anti-overfit surface remains opt-in validation content behind `/simulation/start-ai-validation`.

The current validation catalog already contains 29 arenas using existing simulator systems: class-built enemies, skeleton and goblin factories, ranged and melee loadouts, scrolls, wands, potions, weapon coats, doors, water, difficult terrain, darkness, reveal tools, trap levers, loot chests, support and restoration, high-level spells, teleport, guardian/zone effects, anti-healing necromancy, damage resistance/vulnerability, and multi-projectile target allocation.

### Live Probe

Ran `teleport_escape_skirmish` in `human_hero` mode so the human-side Barbarian passed the turn and the external monster side played the full round.

Artifacts:

- `/tmp/dnd_ai_v48_probe/teleport_escape_human_hero_probe.json`
- `/tmp/dnd_ai_v48_probe/teleport_escape_human_hero_summary.json`
- `/tmp/dnd_ai_v48_probe/server.log`

The monster round returned control to the human in about 4.7 seconds:

- 91 agent events;
- 13 policy ticks;
- 12 command results;
- max policy tick: 4.30 ms;
- max command timing: 236.227 ms;
- max `project_completion_events_ms`: 148.167 ms;
- max follow-up `get_available_actions_ms`: 9.732 ms.

The selected command sequence was tactically mixed but exposed a mobility gap:

- guard: moved toward the Barbarian, attacked, ended turn;
- goblin archer: moved into ranged pressure, attacked, spread/retreated, held spacing;
- escape mage: cast `Magic Missile__slot_1`, then used `Jump` and `Move` for retreat, then held spacing.

### Integrated Change

The bug was not missing content. `Misty Step` and `Dimension Door` were already legal actions in the arena. The local reducer was compacting position spell rows by enemy-hit relevance, which is right for Fireball/Web pruning but wrong for teleport-style self-positioning. The behavior tree also had no leaf that owned “use a mobility spell to escape when a ranged/caster actor is too close.”

Changes:

- Position-spell compaction now preserves teleport-style mobility rows such as `Misty Step` and `Dimension Door` even when they affect no enemy.
- The external enemy policy now has `escape_with_mobility_spell`, placed after offense/support/control and before ordinary spacing movement.
- The branch only fires for ranged/caster actors when a visible enemy is inside the preferred spacing band and the selected position increases distance.
- It prefers cheaper adequate mobility first, so `Misty Step` beats `Dimension Door` when both reach safe spacing.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k 'mobility_spell or compaction or follow_up_epoch'`
- `uv run pyright ai/external/state.py ai/external/policy.py tests/manual/test_35_subjective_external_ai.py`

### Findings

- The validation catalog is broad enough to catch this kind of enemy-AI overfit; adding more arenas was less useful than making the reducer stop dropping legal non-damaging position spells.
- The escape mage did not use teleport in the live run because the policy had no ownership branch and the reducer could drop those rows from local state.
- The round was not catastrophically slow in this probe. The highest server timing spike was still event projection after movement/command completion, not policy selection.

### Next Targets

- Run a close-range teleport probe to confirm the new branch selects `Misty Step` under real server conditions.
- Keep adding arenas only when an observed playtest exposes a genuinely missing pressure surface.
- Continue improving enemy AI against existing validation content before changing global monster/spell/gear definitions.

## 2026-07-04 - Skeleton Focus Fire And Human Boundary Epoch Skip V49

### Live Probe

Ran `skeleton_mark_focus_fire` in `human_hero` mode so the external monster side controlled a guard, archer, and warlock against a durable shield Fighter.

Artifacts:

- `/tmp/dnd_ai_v49_probe/skeleton_mark_focus_fire_human_hero_probe.json`
- `/tmp/dnd_ai_v49_probe/skeleton_mark_focus_fire_human_hero_summary.json`
- `/tmp/dnd_ai_v49_probe_after/skeleton_mark_focus_fire_human_hero_probe.json`
- `/tmp/dnd_ai_v49_probe_after/skeleton_mark_focus_fire_human_hero_summary.json`

The first summary pass falsely reported zero policy ticks because agent telemetry history returns an envelope with the event nested under `event`. The live telemetry itself was present. That is a small but real observability footgun for ad hoc probes and dashboard tooling.

Actual skeleton-side command sequence:

- Archer used `Mark Target`;
- Archer attacked the marked shield Fighter;
- Archer spread/retreated and held spacing;
- Warlock used `Eldritch Blast` through `press_exposed_visible_enemy`;
- Warlock spread/retreated and held spacing;
- Guard moved in, attacked with `Attack_MELEE_MAIN`, then ended turn.

This was good enemy behavior: the mark/focus-fire policy and exposed-target branch worked against a high-AC target without needing new monster content.

### Integrated Change

The timing friction was at the human boundary after the final monster ended turn. `advance_encounter()` was publishing an AI decision epoch for the returning human session, even though the human/NeuroClient path uses `/state`, `/visibility`, and standard action endpoints rather than the AI subjective epoch stream.

Change:

- `_publish_decision_epoch_for_active_session()` now skips `PlayerType.HUMAN`.
- The skip is explicitly timed as `advance.publish_active_epoch.skip_human_session_ms`.
- AI and Codex sessions still publish decision epochs normally.

### Before / After

Same arena, same command sequence:

- Before: max command timing 328.173 ms, elapsed probe 5172.015 ms.
- After: max command timing 158.841 ms, elapsed probe 4254.769 ms.
- After: `advance.publish_active_epoch.skip_human_session_ms=0.001`.

### Verification

- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q -k 'active_epoch_publication_skips_human_sessions or published_epoch_survives'`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k 'mobility_spell or compaction or follow_up_epoch'`
- `uv run pyright server/event_server.py tests/manual/test_36_seamless_subjective_runtime.py ai/external/state.py ai/external/policy.py tests/manual/test_35_subjective_external_ai.py`

### Findings

- The enemy AI looked stronger here than in earlier probes: Mark Target, exposed-target pressure, ranged spacing, and melee closing all appeared in the same round.
- Agent telemetry history is useful but easy to misread because rows are envelopes; dashboard/probe code should consistently unwrap `row["event"]`.
- Human-boundary epoch publication was wasted work. Skipping it is a clean interface separation: human clients keep their existing flow, while AI/Codex clients keep subjective epochs.

### Next Targets

- Rotate away from skeletons next; use a Sorcerer-side or Barbarian-side arena.
- If touching dashboard code, add a small helper that normalizes agent-event envelopes before charting or summarizing.
- Continue chasing server command timings above 100 ms, especially movement/event-projection paths.

## 2026-07-04 - Concentration Control And Epoch Build Speed V50

### Live Probe

Ran `concentration_control_crossroads` in `codex_monsters` mode. This flips the validation shape: the external AI controlled the hero-side Sorcerer, while the monster side was Codex-claimed and stopped at the monster boundary.

Artifacts:

- `/tmp/dnd_ai_v50_probe/concentration_control_crossroads_codex_monsters_probe.json`
- `/tmp/dnd_ai_v50_probe/concentration_control_crossroads_codex_monsters_summary.json`
- `/tmp/dnd_ai_v50_after/concentration_control_crossroads_codex_monsters_after.json`
- `/tmp/dnd_ai_v50_after/concentration_control_crossroads_codex_monsters_after_summary.json`
- `/tmp/dnd_ai_v50_after/server.log`

External Sorcerer sequence:

- cast `Fireball__slot_3` at `position|Fireball__slot_3|pos=8,5`, hitting the guard, controller, and support caster;
- moved to `position|Move|pos=0,1` through `retreat_from_visible_enemy`;
- ended turn through `hold_ranged_spacing`, reaching the Codex monster boundary.

This was tactically acceptable for the current simple policy. It also confirms that we are not only sampling skeleton melee/ranged baselines: this arena uses support/control casters, concentration choices, friendly-fire geometry, and richer spell rows.

### Content Coverage Answer

The validation catalog already has 29 opt-in arenas. These are fixture-level setups using the existing simulator content rather than global monster/spell rewrites. Current coverage includes doors, water, darkness, goblins, skeletons, class-built enemies, casters, support/healing, consumables, wands, scrolls, environmental devices, line AoE, zone control, teleport, trap levers, conditions, resistances/vulnerabilities, loot caches, and multi-target projectile allocation.

That means the immediate anti-overfit move is not to keep adding random content. It is to make the enemy policy consume this existing variety: class kits, consumables, object interactions, support rows, terrain/pathing, and multi-target spells must be used through general state/affordance reasoning rather than arena-specific hacks.

### Integrated Change

The live probe exposed a large Codex-side turn-boundary cost. Before the patch, ending the Sorcerer turn into the Codex support/control monster turn spent:

- `advance.publish_active_epoch.build_affordance_set_ms=187.963`;
- `advance.publish_active_epoch.get_available_actions_ms=54.619`;
- max command total `372.38 ms`.

The support caster epoch had 2028 affordance rows. The row data was already normalized from trusted engine models, but the hot path still paid repeated Pydantic validation and GC interruptions.

Change:

- direct epoch construction now uses `model_construct` for trusted internal row models;
- the short affordance-flattening window suppresses cyclic GC and re-enables it immediately after;
- no action semantics, spell data, monster gear, or arena setup changed.

After the patch, the same live probe showed:

- `advance.publish_active_epoch.build_affordance_set_ms=15.005`;
- `advance.publish_active_epoch.get_available_actions_ms=48.749`;
- max command total `348.871 ms`.

Local micro-benchmark for the 2028-row support caster build:

- average `16.111 ms`;
- median `15.728 ms`;
- p90 `17.167 ms`;
- max `23.267 ms`.

### Verification

- `uv run pytest tests/manual/test_31_subjective_runtime_epochs.py -q -k 'direct_epoch_affordance_builder_matches_serialized_legacy_rows or simple_entity_epoch_rows_are_lean or position_epoch_rows_do_not_duplicate or aoe_discovery'`
- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q -k 'accepted_command_publishes_result_then_followup_epoch or active_epoch_publication_skips_human_sessions'`
- `uv run pytest tests/manual/test_37_ai_validation_arenas.py -q`
- `uv run pyright ai/subjective/epochs.py server/event_server.py tests/manual/test_31_subjective_runtime_epochs.py tests/manual/test_36_seamless_subjective_runtime.py tests/manual/test_37_ai_validation_arenas.py`

### Findings

- The arena battery is broad enough to prevent obvious skeleton-only overfitting. We should use it before adding global content.
- The old ad hoc summary filter missed events because telemetry now uses `external_ai.policy_tick` and `runtime.command_timing`; dashboard/probe helpers need a normalized event accessor.
- The worst remaining V50 cost is now command-result event projection: `publish.command_result.projection.project_completion_events_ms` was about `176 ms`.
- Fireball execution itself still took about `248 ms`, so richer spell/event execution remains a more important speed target than adding more scenarios immediately.

### Next Targets

- Optimize command-result completion-event projection after accepted commands.
- Run a Barbarian-side or `resistance_weapon_counterplay` probe next to keep role rotation honest.
- Improve enemy policy consumption of the existing validation catalog before creating more fixture content.

## 2026-07-04 - Resistance Counterplay And Harrier Spacing V51

### Live Probe

Ran `resistance_weapon_counterplay` in `human_hero` mode. This rotated away from the Sorcerer/control probe into a non-skeleton shield Fighter target with piercing resistance and bludgeoning vulnerability.

Artifacts:

- `/tmp/dnd_ai_v51_probe/resistance_weapon_counterplay_human_hero_probe.json`
- `/tmp/dnd_ai_v51_probe/resistance_weapon_counterplay_human_hero_summary.json`
- `/tmp/dnd_ai_v51_probe_after/resistance_weapon_counterplay_human_hero_probe.json`
- `/tmp/dnd_ai_v51_probe_after/resistance_weapon_counterplay_human_hero_summary.json`
- `/tmp/dnd_ai_v51_probe_after/server.log`

Before the patch, the monster side selected:

- Mage: `Magic Missile__slot_1`, spread, retreat, end turn;
- Harrier: `Attack_RANGED_MAIN`, then `Move` adjacent, then `Attack_MELEE_OFF` with a dagger;
- Captain: `Attack_MELEE_OFF` with Club, `Attack_MELEE_MAIN` with Shortsword, then `Extra Attack_MELEE_OFF` with Club.

The good news: the captain used the club/bludgeoning row first against the non-skeleton target, so visible damage vulnerabilities/resistances are flowing through the real subjective stream and real decision epochs.

The bad news: the harrier behaved like a ranged unit for the first action, then forgot that identity once the bow row disappeared from the follow-up epoch and walked into melee for a healthy-target dagger attack.

### Integrated Changes

Enemy policy:

- Ranged/caster actors that already spent their primary pressure action now skip melee follow-up attacks unless the adjacent target is a clear low-HP finisher.
- Actor spacing identity now recognizes `harrier` and `scout` names in addition to archer/caster labels.
- The `_attack_visible_enemy` logical annotation now states this prerequisite explicitly.

External reducer speed:

- The reduced-state builder now uses trusted `model_construct` for internal entity/object/tile/action/state wrappers.
- The validated reduction pass suppresses cyclic GC during the short allocation burst.

### Before / After

Behavior:

- Before: `Attack_RANGED_MAIN` -> `Move` adjacent -> `Attack_MELEE_OFF` dagger.
- After: `Attack_RANGED_MAIN` -> `Move` to spacing -> `hold_ranged_spacing`.

Speed:

- max `state_reduction_ms`: `93.12` -> `2.96`;
- max `normalize_position_actions_ms`: `92.779` -> `2.47`;
- max policy tick: `94.74` -> `11.11`.

Local reducer micro-benchmark for the 306-position-row captain epoch:

- average `2.618 ms`;
- median `2.573 ms`;
- p90 `2.75 ms`;
- max `3.733 ms`.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k 'harrier or normal_path or compaction or ranged_enemy_holds_spacing or attack_policy_prefers_known_vulnerability_damage_type or melee_enemy_still_closes'`
- `uv run pyright ai/external/state.py ai/external/policy.py tests/manual/test_35_subjective_external_ai.py`

### Findings

- The resistance/counterplay fixture is doing useful work: it proves weapon-affinity policy is not skeleton-specific.
- Ranged identity cannot be inferred only from currently affordable rows. Follow-up epochs can hide spent ranged rows, so actor naming and remembered role cues matter.
- The dominant remaining delay is now server command-result projection after richer spell events. In the patched run, Magic Missile still hit `project_completion_events_ms=146.779`.

### Next Targets

- Optimize command-result completion-event projection.
- Rotate next into skeleton-side or field-cache/object-interaction validation instead of repeating resistance or Sorcerer/control.
- Keep adding policy-level logical annotations when fixing behavior branches.

## 2026-07-04 - Field Cache Loot Policy V52

### Live Probe

Ran `field_cache_loot_race` in `codex_monsters` mode. This validates the external AI hero against Codex-controlled monsters and stresses object interaction, carried resources, and follow-up epoch handling.

Artifacts:

- `/tmp/dnd_ai_v52_probe/field_cache_loot_race_codex_monsters_probe.json`
- `/tmp/dnd_ai_v52_probe/field_cache_loot_race_codex_monsters_summary.json`
- `/tmp/dnd_ai_v52_probe_after/field_cache_loot_race_codex_monsters_probe.json`
- `/tmp/dnd_ai_v52_probe_after/field_cache_loot_race_codex_monsters_summary.json`
- `/tmp/dnd_ai_v52_probe_after/server.log`

Before the patch, the AI stood next to the validation cache but selected:

- `Attack_RANGED_MAIN` against Cache Harrier;
- `Extra Attack_RANGED_MAIN` against Cache Harrier;
- `Move` to `(8, 7)`;
- end turn.

The cache already exposed a legal `Loot All (Validation Field Cache)` item-use row, so this was an over-narrow object policy rather than a missing engine affordance.

### Integrated Change

The tactical environment-object leaf now recognizes adjacent battlefield cache loot rows in addition to trap levers. It still ignores generic item-use rows, so this is not an arbitrary "click every object" policy.

No global monsters, spells, gear, or class content changed. This was a policy fix against existing fixture content.

### Before / After

Behavior:

- Before: `Attack_RANGED_MAIN` -> `Extra Attack_RANGED_MAIN` -> `Move` -> end turn.
- After: `Loot All` -> looted `Fireball` item -> `Move` -> end turn.

Speed:

- policy ticks stayed small: max `5.64 ms`;
- `Loot All` command total: `53.61 ms`;
- `Fireball` command total: `331.616 ms`, with `execute.action_by_index_ms=257.762`;
- end turn command total: `168.9 ms`, with active Codex epoch publication still costing `117.246 ms`.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k 'tactical_environment_object or loot or trap_lever or cache'`
- `uv run pyright ai/external/policy.py tests/manual/test_35_subjective_external_ai.py`

### Findings

- Existing validation fixtures are already rich enough to expose object-use blind spots; we should keep rotating them before adding global content.
- Fixture-level content is the right pressure valve for now: combine existing spells, items, gear, terrain, doors, hazards, resistances, and action-economy stress without expanding the canonical content layer.
- The agent-event payload extractor was looking for an old `data` key; the stream now carries details under `payload`. Probe/dashboard helpers need a single normalized event accessor.
- The next performance target is still server-side action/event work for multi-target spells and active-epoch publication, not the behavior-tree policy itself.

### Next Targets

- Normalize agent-event envelopes in dashboard/probe helpers before computing event-type series.
- Optimize rich spell execution and command-result projection, especially Fireball and Magic Missile.
- Create additional validation arenas only as fixture-level recombinations of existing content until repeated evidence shows the content layer itself needs expansion.

## 2026-07-04 - Dashboard Live-Probe Charts And Movement Projection V53

### Live Probe

Ran `skeleton_mark_focus_fire` in `human_hero` mode. A temporary human session joined the shield fighter, ended the hero turn, and let the external AI play the skeleton side back to the next hero turn.

Artifacts:

- `/tmp/dnd_ai_v53_probe/skeleton_mark_focus_fire_human_hero_probe.json`
- `/tmp/dnd_ai_v53_probe/skeleton_mark_focus_fire_human_hero_summary.json`
- `/tmp/dnd_ai_v53_probe_after/skeleton_mark_focus_fire_human_hero_probe.json`
- `/tmp/dnd_ai_v53_probe_after/skeleton_mark_focus_fire_human_hero_summary.json`
- `/tmp/dnd_ai_v53_probe_after/server.log`

Before the patch, the skeleton side selected:

- Guard: move toward visible enemy, attack, end turn;
- Warlock: Necrotic Bless, spread movement, retreat movement, end turn;
- Archer: Mark Target, ranged attack into the exposed target, retreat movement, end turn.

The policy behavior was broadly sensible. The friction was transport/runtime cost: a Warlock retreat movement spent `170.692 ms` in `publish.command_result.projection.project_completion_events_ms`.

### Integrated Changes

Dashboard:

- live-probe iterations now participate in charts when they have matching metrics;
- runtime timing is split into command total latency, command subphase latency, and policy tick latency;
- newer metric names such as `after_command_total_max_ms`, `after_policy_tick_max_ms`, and agent-event counts are aliased by the dashboard.

Observation stream:

- child `STEP_MOVEMENT`, `SPATIAL_ENTITY_ENTERED`, and `SPATIAL_ENTITY_LEFT` events with a parent event are skipped as standalone subjective envelopes;
- the parent movement event still carries the path and nested step logs;
- damage, conditions, reactions, sensory updates, top-level spatial/tile/object changes, and command frames still project normally.

### Before / After

Projection speed:

- max `project_completion_events_ms`: `170.692` -> `15.417`;
- max runtime command total: `242.677` -> `192.188`;
- max policy tick stayed tiny: `4.38` -> `4.72`.

Behavior:

- The skeleton side still used support, marking, focus-fire pressure, and ranged spacing.
- Initiative order differed between the two live runs, so exact command order is not a semantic regression check.

New friction:

- The after-run exposed a separate attack execution spike: `execute.action_by_index_ms=163.798` for a Guard longsword critical hit. Projection was no longer the bottleneck for that command.

### Verification

- `uv run pytest tests/manual/test_28_subjective_observation_stream.py -q -k 'movement_projection_skips_redundant_child_breadcrumbs or snapshot_plus_frames_replays_to_fresh_subjective_state'`
- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q -k 'accepted_command_publishes_result_then_followup_epoch or runtime_command_followup_ignores_noise_until_matching_command_result or snapshot_current_epoch_is_bootstrap_only_not_frame_decoration'`
- `uv run pyright ai/observation/projector.py tests/manual/test_28_subjective_observation_stream.py`
- `node --check /tmp/agent_ux_dashboard_script.js`
- `uv run python -m json.tool ai/AGENT_UX_ITERATION_STATS.json`

### Findings

- The dashboard was under-reporting recent live probes because it filtered charts to `playtest`-typed iterations.
- Parent movement logs already contain the step path; sending every child movement/spatial breadcrumb as a subjective frame was redundant and slow.
- The next core speed target is attack execution, not policy selection or projection.

### Next Targets

- Instrument/fix the attack execution spike seen in V53.
- Keep the skeleton-side focus-fire fixture in rotation for enemy policy checks.
- Continue alternating into Sorcerer or Barbarian after this skeleton-side slice.

## 2026-07-04 - Projectile Target Allocation And Unwatched Codex Epoch Skip V54

### Live Probe

Ran `multi_projectile_no_aoe_lab` in `codex_monsters` mode. This rotated back to a Sorcerer-side validation fixture after the skeleton-side focus-fire run and specifically avoided Fireball/Lightning Bolt dominance so Magic Missile and multi-projectile target allocation were visible.

Artifacts:

- `/tmp/dnd_ai_v55_final_probe/summary_nested.json`
- `/tmp/dnd_ai_v55_skip_unwatched_codex/summary_nested.json`
- `/tmp/dnd_ai_v55_skip_unwatched_codex/server.log`

Behavior stayed correct in both runs:

- selected `Magic Missile__slot_1`;
- supplied two `extra_target_uuids`;
- engine combat data reported three target names and per-target damage;
- then moved for spacing and ended turn.

### Integrated Changes

Observation/runtime:

- added nested timing from active decision-epoch publication into `get_observation_cursor()`;
- added per-event-type projection timing while projecting completion events;
- added `observation_wakeup_stream.has_subscribers()`;
- skipped automatic active-epoch frame publication for unwatched Codex sessions.

Codex remains lazy-correct: `brief`, `actions`, and `watch` fetch a snapshot first, and that snapshot still builds the current epoch. A hot Codex watcher still receives live decision-epoch frames because it has an observation subscription.

No global monster factories, spell implementations, gear rules, or standard simulator defaults changed. The anti-overfit work here is fixture-level: the validation catalog uses existing content in richer combinations, while the normal content layer stays stable.

### Before / After

Before the skip, the external Sorcerer's final end-turn was paying to cold-project the Codex monster session even though no Codex client was watching:

- max runtime command total: `260.525 ms`;
- max server command total: `250.698 ms`;
- `advance.publish_active_epoch_ms`: `219.617 ms`;
- `advance.publish_active_epoch.get_observation_cursor_ms`: `204.44 ms`;
- cold projection was dominated by `condition_removal` completion projection at `149.629 ms`.

After the skip:

- max runtime command total: `82.762 ms`;
- max server command total: `74.018 ms`;
- final end-turn command elapsed: `41.7 ms`;
- `advance.publish_active_epoch_ms`: `0.026 ms`;
- the timing payload records `advance.publish_active_epoch.skip_unwatched_codex_session_ms`.

Policy cost remained tiny:

- max policy tick: `2.67 ms`;
- max state reduction: `1.79 ms`;
- max affordance projection: `0.67 ms`.

### Verification

- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q -k 'active_epoch_publication or accepted_command_publishes_result_then_followup_epoch or runtime_command_followup_uses_persisted_frames_before_sse or runtime_command_followup_ignores_initial_stream_sync'`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k 'multi_entity or normal_path or timing_sinks or magic_missile'`
- `uv run pyright server/event_server.py ai/observation/projector.py ai/subjective/epochs.py tests/manual/test_36_seamless_subjective_runtime.py`

### Findings

- The multi-target spell path is working for this fixture: the policy selected Magic Missile with extra targets and the engine applied per-target damage.
- The large perceived delay was not the behavior tree. It was cold subjective projection for an unwatched Codex session at handoff.
- The deeper architectural issue remains: newly-created sessions can still cold-project old setup/history when first observed. The skip removes that cost from normal external-AI handoff, but proper snapshot baselining should be considered later.

### Next Targets

- Rotate back to a skeleton-side or Barbarian-facing fixture instead of overfitting on the Sorcerer projectile lab.
- Continue using fixture-level arena diversity before adding global monsters/spells/gear.
- Investigate attack execution spikes when they recur, especially `execute.action_by_index_ms` outliers.

## 2026-07-04 - Condition Lock Spacing Policy And Passive Timing V55

### Live Probe

Ran `condition_lock_sanctum` in `human_hero` mode. A temporary human session joined the Barbarian, ended the hero turn, and let the external monster AI play the Lock Support, Lock Guard, and Lock Controller side back to the next hero turn.

Artifacts:

- `/tmp/dnd_ai_v56_condition_lock/summary.json`
- `/tmp/dnd_ai_v56_condition_lock_after/summary.json`
- `/tmp/dnd_ai_v56_condition_lock_final/summary.json`
- `/tmp/dnd_ai_v56_condition_lock_final/server.log`

Before the patch, the validation fixture exposed a real enemy-policy overfit:

- Controller cast `Hold Person__slot_2`, then moved toward the Barbarian and ended too close for a control caster.
- Guard moved and attacked as expected.
- Support cast `Magic Missile__slot_1`, then `Shield of Faith__slot_1`, then also moved toward the Barbarian.

The problem was not the arena content. The fixture was doing its job: once the controller/support had spent their best spell rows, the policy no longer recognized their role and fell through to ordinary melee-style chase movement.

### Integrated Changes

Enemy policy:

- `_actor_prefers_spacing()` now recognizes named controller/support/caster identities such as `controller`, `support`, `cleric`, `priest`, and `necromancer`.
- Spent support/control actors now choose spacing branches after their direct spell rows are gone.
- Added focused tests for named `Validation Lock Controller` and `Validation Lock Support` actors so this exact regression stays covered.

Instrumentation:

- Added passive-skill timing inside `Entity.passive_skill()` so action execution can distinguish passive perception score calculation from the actual senses refresh.

No global monster factories, spell implementations, gear rules, or standard simulator defaults changed. The anti-overfit work remains fixture-level: validation arenas combine existing content and local loadouts without moving the canonical rules underneath the AI.

### Before / After

After the policy change, the same arena shape produced more plausible monster-side behavior:

- Support opened with `Bless__slot_1`, followed with `Shield of Faith__slot_1`, then spread and retreated instead of closing into melee.
- Guard still moved toward the visible Barbarian and attacked.
- Controller cast `Hold Person__slot_2`, then retreated and held ranged/control spacing.

Final run command reasons:

- `cast_opening_controlled_support_spell`
- `cast_controlled_support_spell`
- `spread_from_allies_after_pressure`
- `retreat_from_visible_enemy`
- `hold_ranged_spacing`
- `move_toward_visible_enemy`
- `attack_visible_enemy`
- `end_turn`
- `cast_visible_enemy_control_spell`
- `retreat_from_visible_enemy`
- `hold_ranged_spacing`

Timing from the final run:

- max external command result: `233.55 ms`;
- max runtime command total: `232.35 ms`;
- max server command total: `218.596 ms`;
- max action-server total: `138.343 ms`;
- max policy tick: `7.44 ms`;
- max subjective projection phase: `publish.command_result.projection.project_completion_event.condition_application_ms=172.075`;
- max action phase: `execute_by_index.passive_skill.perception.skill_bonus_ms=135.672`.

The current latency target is therefore not policy selection. It is engine/runtime work around passive skill calculation on first rich support spell execution and subjective projection of nested condition-application events.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k 'controller_spreads or support_holds or spacing or ranged_enemy_spreads or melee_enemy_still_closes'`
- `uv run pyright ai/external/policy.py dnd/entity.py tests/manual/test_35_subjective_external_ai.py`
- `uv run python -m json.tool ai/AGENT_UX_ITERATION_STATS.json`

### Findings

- The existing validation catalog is already broad enough to catch overfitting: this bug appeared because `condition_lock_sanctum` used a controller/support enemy composition instead of another generic skeleton trio.
- Fixture-level content changes are the right tool for now. The catalog already samples doors, water, difficult terrain, traps, items, scrolls, wands, potions, high-level spells, class-party loadouts, damage affinities, restoration, visibility, teleport, and multi-target projectile allocation.
- The next content move should be more systematic rotation through the current catalog, not changing global monster/spell/gear definitions.

### Next Targets

- Rotate through existing validation arenas before adding more fixtures.
- Investigate the passive `skill_bonus` spike and nested condition-application projection spike.
- Add a new arena only when repeated runs show a missing pressure class, not as a substitute for fixing policy/runtime behavior.

## 2026-07-04 - Skeleton Damage Affinity And Action Discovery Timing V56

### Live Probe

Ran `damage_affinity_weapon_lab` in `human_hero` mode to rotate into a skeleton-focused slice. A temporary human session joined the hero-side skeleton warrior, ended the hero turn, and let the external monster AI play the Affinity Archer, Affinity Mage, and Crusher Captain.

Artifacts:

- `/tmp/dnd_ai_v57_damage_affinity/summary.json`
- `/tmp/dnd_ai_v57_damage_affinity_after/summary.json`
- `/tmp/dnd_ai_v57_damage_affinity_after/server.log`

### Findings

Enemy behavior:

- The damage-type policy worked in live play.
- The Crusher Captain selected `Attack_MELEE_OFF` with the Club against the bludgeoning-vulnerable skeleton.
- In the repeated run, the Crusher then used `Attack_MELEE_MAIN` with the Shortsword only after the Club row had already been spent, which is a sane follow-up.
- The Archer used `Mark Target`, pressed the exposed target, then repositioned and held spacing.
- The Mage used `Magic Missile` against the exposed skeleton and retreated.

Speed:

- Before instrumentation, the slowest command was an archer end-turn at `257.32 ms`; the server timing showed `advance.publish_active_epoch.get_available_actions_ms=179.737`.
- After instrumentation, the repeated run exposed the internal action-discovery shape:
  - `advance.publish_active_epoch.get_available_actions_ms=39.708`;
  - `advance.publish_active_epoch.available_actions.collect_aoe_actions_ms=23.409`;
  - `advance.publish_active_epoch.available_actions.collect_los_actions_ms=10.694`;
  - `advance.publish_active_epoch.available_actions.collect_path_actions_ms=8.742`.
- The slowest command in the repeated run was `Magic Missile__slot_1` at `188.28 ms`. The nested action payload and the outer command timing still disagree on where the full route time is spent, so the next speed pass needs better route-boundary timing around nested action execution and result conversion.

### Integrated Changes

- Decision-epoch construction now installs the existing action timing recorder around `get_available_actions()`.
- `Entity.get_available_actions()` now records subphase timings for target selection, self/entity action discovery, dirty-senses refresh, path/LOS/AoE/object/use action discovery, and handler metadata.
- Added a regression test proving published decision-epoch timing includes available-action discovery subphases.
- Updated the dashboard runtime subphase chart to include available-action, AoE-discovery, and LOS-discovery time series.

No new monsters, spells, or gear were added in this slice. This was a validation pass over existing fixture-level content and a timing-instrumentation improvement.

### Verification

- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q -k 'published_epoch_timing_breaks_down_available_action_discovery or active_epoch_publication or accepted_command_publishes_result_then_followup_epoch'`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k 'attack_policy_prefers_known_vulnerability_damage_type or timing_sinks'`
- `uv run pyright ai/subjective/epochs.py dnd/entity.py tests/manual/test_36_seamless_subjective_runtime.py tests/manual/test_35_subjective_external_ai.py`

### Next Targets

- Optimize or narrow AoE/LOS discovery for decision epochs; the agent does not need a slow full map expansion every turn.
- Add missing outer route-boundary timing around nested action execution, especially for multi-damage spells like Magic Missile.
- Continue the rotation with a Sorcerer-facing or Barbarian-facing fixture next, rather than staying on skeleton weapon affinity.

## 2026-07-04 - Sorcerer Area Spell Action Lifecycle Timing V57

### Live Probe

Ran `line_aoe_corridor` in `codex_monsters` mode. The external hero AI controlled the level 5 Sorcerer while the monster side was claimed by a Codex session, so the run exercised the Sorcerer-facing slice after the skeleton-focused damage-affinity pass.

Artifacts:

- `/tmp/dnd_ai_v57_sorcerer_action_lifecycle/summary.json`
- `/tmp/dnd_ai_v57_sorcerer_action_lifecycle/agent_events_raw.json`
- `/tmp/dnd_ai_v57_sorcerer_action_lifecycle/probe_status.json`
- `/tmp/dnd_ai_v57_sorcerer_action_lifecycle/server.log`

### Findings

Behavior:

- The Sorcerer selected `Fireball__slot_3` at `(8, 7)` with reason `cast_visible_area_spell`.
- The selected area hit all four visible enemies: Line Archer, Line Guard, Off-Line Goblin, and Line Mage.
- Follow-up behavior was plausible: after the spell, the Sorcerer retreated and then ended the turn with `hold_ranged_spacing`.

Speed:

- The policy tick itself remained fast: the first tick was `6.09 ms`, with only `0.17 ms` spent in policy selection.
- The Fireball command was still too slow: command result elapsed time was `397.19 ms`.
- New low-level timing showed the slow path is inside action application:
  - `execute_by_index.base_action.apply_total_ms=316.442`;
  - `execute_by_index.base_action.convolution_apply_targets_ms=314.412`;
  - `execute_by_index.base_action.convolution_target_apply_ms=314.404`;
  - `execute_by_index.base_action.resolve_convolution_targets_ms=0.577`.
- This means the route-boundary mystery is resolved for this slice. The bottleneck is the per-target spell/event convolution, not the behavior tree and not target discovery.

### Integrated Changes

- `BaseAction.apply()` now records low-level lifecycle timings when an action timing recorder is installed.
- Added focused coverage proving a real position-AoE spell exposes BaseAction lifecycle and convolution timing.
- Added an Action Lifecycle chart to the dashboard so BaseAction timing is separated from command totals and available-action discovery.
- Made the dashboard latest-change renderer accept both string and object entries.

No monsters, spells, gear, or global arena defaults were changed in this slice.

### Verification

- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q -k 'position_aoe_action_lifecycle_timing_records_convolution_phases or published_epoch_timing_breaks_down_available_action_discovery'`

### Next Targets

- Optimize or further instrument per-target spell/event convolution, especially save/damage event generation inside multi-target spells.
- Continue the rotation with a Barbarian-facing fixture next, not another Sorcerer spell probe.
- Keep using the current validation catalog before adding more content; it is already exposing real policy and runtime issues.

## 2026-07-04 - Barbarian Forced Movement Hazard Policy V58

### Live Probe

Ran `forced_movement_hazard_bridge` in `human_hero` mode. A temporary human session controlled the level 5 Barbarian only long enough to end the opening turn, then the external monster AI played the Hazard Mage, Hazard Warlock, and Hazard Archer.

Artifacts:

- `/tmp/dnd_ai_v58_barbarian_forced_movement/summary.json`
- `/tmp/dnd_ai_v58_barbarian_forced_movement_after/summary.json`
- `/tmp/dnd_ai_v58_barbarian_forced_movement_final/summary.json`
- `/tmp/dnd_ai_v58_barbarian_forced_movement_final/agent_events_raw.json`
- `/tmp/dnd_ai_v58_barbarian_forced_movement_final/hero_handoff.json`
- `/tmp/dnd_ai_v58_barbarian_forced_movement_final/server.log`

### Findings

Before the policy change:

- The Warlock had the Barbarian visible at 10 ft and had `Thunderwave` position rows available.
- It still selected `Eldritch Blast`, then retreated.
- The root cause was policy ordering and area-spell filtering:
  - normal leveled area spells require at least two enemy hits;
  - Thunderwave is a position-AoE spell, so it was skipped as a one-target area row;
  - after the Archer marked the Barbarian, `press_exposed_visible_enemy` selected Eldritch Blast before any displacement reasoning could run.

After the policy change:

- The Warlock selected `Thunderwave__slot_1` with reason `cast_visible_forced_movement_hazard_spell`.
- The Barbarian failed the CON save, took 12 thunder damage, and was pushed 10 ft from `(4, 10)` to `(2, 10)`.
- The raw combat log contains the forced-movement sub-entry:
  - `{yellow:Validation Hazard Barbarian} pushed {green:10ft}`;
  - data type `forced_movement`;
  - direction `(-1, 0)`.
- The Warlock then retreated and held spacing.

Speed:

- Max policy tick was `3.21 ms`.
- Max policy selection was `0.28 ms`.
- Max command result elapsed was `242.14 ms`, from the Thunderwave command.
- Max `execute.action_by_index_ms` was `179.241 ms`.
- Max `execute_by_index.base_action.convolution_apply_targets_ms` was `176.994 ms`.

The behavior improvement worked, but the speed finding is consistent with the prior Sorcerer run: position-AoE spell application is still far too slow relative to the intended external-AI budget.

### Integrated Changes

- Added `_cast_visible_forced_movement_hazard_spell` to the enemy behavior tree.
- The new branch uses only subjective reduced-state facts: actor position, visible enemy positions, affected entity UUIDs, controlled entity UUIDs, and known hazardous tiles.
- Added helper scoring for forced-movement spell priority and approximate push-path hazard relevance.
- Added logical annotations for the new behavior leaf.
- Added focused policy tests proving:
  - Thunderwave beats generic blast when it can push a visible enemy into known hazard pressure, even if the target is marked;
  - single-target Thunderwave does not displace Eldritch Blast when there is no hazard relevance.

No monsters, spells, gear, or global arena defaults were changed in this slice.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k 'forced_movement_spell or logical_annotations'`

### Next Targets

- Continue the rotation with a skeleton-facing fixture next.
- Optimize or further instrument position-AoE spell application, since both Fireball and Thunderwave now point at BaseAction convolution as the hot path.
- Keep the forced-movement branch narrow until more hazard/displacement fixtures prove it needs broader generalization.

## 2026-07-04 - Skeleton Door Baseline Enemy AI Validation V59

### Live Probe

Ran `standard_skeleton_doors` in `human_hero` mode. A temporary human session controlled the level 5 Sorcerer only long enough to end the opening turn, then the external monster AI played the Skeleton Archer, Skeleton Warlock, and Skeleton Warrior through the first monster round.

Artifacts:

- `/tmp/dnd_ai_v59_skeleton_doors/summary.json`
- `/tmp/dnd_ai_v59_skeleton_doors/agent_events_raw.json`
- `/tmp/dnd_ai_v59_skeleton_doors/hero_handoff.json`
- `/tmp/dnd_ai_v59_skeleton_doors/status.json`
- `/tmp/dnd_ai_v59_skeleton_doors/server.log`

### Findings

Behavior:

- The Archer saw the Sorcerer at 50 ft, moved to `(8, 7)`, opened the closed door, used `Mark Target`, fired `Attack_RANGED_MAIN`, then retreated to `(10, 5)`.
- The Warlock selected `Necrotic Bless__slot_2` and supplied both other skeleton UUIDs as extra targets, confirming the multi-target support path survived the door baseline run.
- The Warlock then moved toward the remembered/visible hero line and held ranged spacing.
- The Warrior moved to the door lane, dashed, jumped through the opened route, moved adjacent to the Sorcerer, and ended turn at 5 ft.
- The server returned to the human-controlled Sorcerer at round 2 without hanging.

Speed:

- Max policy tick was `3.73 ms`.
- Max policy selection was `0.39 ms`.
- Max command result elapsed was `214.93 ms`.
- The slowest server-side epoch path was still available-action generation:
  - `advance.publish_active_epoch.get_available_actions_ms=159.259`;
  - `advance.publish_active_epoch.available_actions.collect_path_actions_ms=151.87`.

The policy behavior was good for this baseline: doors, support, ranged pressure, retreat, dash, jump, and frontline engagement all appeared in one round. The speed finding points back to path-action generation, not behavior-tree selection.

### Integrated Changes

- Fixed the server catalog regression test so it matches the current 29-arena validation catalog.
- Confirmed the validation catalog itself already covers varied monsters, class-factory enemies, gear loadouts, spell lists, items, doors, water, hazards, conditions, vision, teleport, damage affinities, and multi-target spell allocation.

No global monster factories, spell definitions, or default gear packages were changed in this slice. The correct anti-overfit surface remains fixture-level arena composition.

### Verification

- `uv run pytest tests/manual/test_37_ai_validation_arenas.py -q`
- `uv run pytest tests/manual/test_38_ai_validation_server_start.py -q`

### Next Targets

- Keep rotating through the existing 29-arena catalog before adding more content.
- Prioritize optimizing or reducing `collect_path_actions_ms`, because the first skeleton epoch spent most of its command latency there.
- Use the non-skeleton class-party, ranged-loadout, condition, and item-cache arenas before changing monster factories or global spell lists.

## 2026-07-04 - Teleport Escape Skirmish Enemy AI Validation V60

### Live Probe

Ran `teleport_escape_skirmish` in `human_hero` mode. A temporary human session controlled the level 5 Barbarian long enough to end the opening turn, then the external monster AI played the Escape Guard, Escape Mage, and Goblin Archer through the first monster round.

Artifacts:

- `/tmp/dnd_ai_v60_teleport_escape/harness_start.txt`
- `/tmp/dnd_ai_v60_teleport_escape_after/summary.json`
- `/tmp/dnd_ai_v60_teleport_escape_final/summary.json`
- `/tmp/dnd_ai_v60_teleport_escape_optimized/summary.json`
- `/tmp/dnd_ai_v60_teleport_escape_optimized/agent_events_raw.json`
- `/tmp/dnd_ai_v60_teleport_escape_optimized/hero_handoff.json`
- `/tmp/dnd_ai_v60_teleport_escape_optimized/status.json`
- `/tmp/dnd_ai_v60_teleport_escape_optimized/server.log`

### Findings

Behavior:

- The Escape Guard moved to the visible Barbarian, attacked in melee, and ended turn.
- The Escape Mage cast `Magic Missile__slot_1`, spread away from allies, used `Misty Step`, retreated twice, and held ranged spacing at 75 ft.
- The Goblin Archer moved into range, fired `Attack_RANGED_MAIN`, retreated, and held spacing.
- The optimized run did not show the earlier clunk where the fragile caster moved toward the Barbarian after pressure.

Speed:

- Max policy tick was `3.4 ms`.
- Max policy selection was `0.37 ms`.
- Max command runtime was `176.506 ms`, on `Magic Missile__slot_1`.
- Removing the duplicate `actor.is_spellcaster` gate fixed the action-economy spike:
  - before: `publish.followup_epoch.build_action_economy_ms=144.34`;
  - after: max `build_action_economy_ms=0.598`;
  - after: max `action_economy.spell_slots_total_ms=0.561`.
- The new real hotspot is subjective projection of spell completion:
  - `publish.command_result.projection.project_completion_event.cast_spell_ms=140.695`;
  - `publish.command_result_ms=145.765`.
- Movement remains moderately expensive, with the slowest action route at `66.59 ms` for the Guard's opening move.

The fixture behavior is encouraging: teleport, ranged pressure, retreat, and melee screening all appeared without adding new monsters, changing spells, or changing gear. The speed story moved from action-economy construction to spell-event projection, which is a cleaner and narrower next target.

### Integrated Changes

- Added final response-construction timing to the old `/action/execute` route so action-server timing no longer hides response assembly work.
- Added fine-grained action-economy timing inside decision-epoch construction.
- Removed the duplicate `actor.is_spellcaster` gate from action-economy construction and directly scans spell-slot values.
- Added focused assertions for the new timing fields.

No global monster factories, spell definitions, gear packages, or arena defaults were changed in this slice. Variety is coming from existing validation arenas and fixture-level composition, which is the right anti-overfit surface for enemy AI.

### Verification

- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q -k 'published_epoch_timing_breaks_down_available_action_discovery or accepted_command_publishes_result_then_followup_epoch'`
- `uv run pyright ai/subjective/epochs.py server/event_server.py tests/manual/test_36_seamless_subjective_runtime.py`

### Next Targets

- Investigate and reduce `project_completion_event.cast_spell_ms`, especially for multi-projectile spells such as Magic Missile.
- Continue rotating through the existing 29-arena catalog before adding more fixtures.
- If the current catalog proves thin, add gap-filling arenas at fixture level: reaction/counterspell pressure, summon/body-block pressure, and objective-control pressure with multiple usable map objects.

## 2026-07-04 - Concentration Crossroads Projection And Entity-Action Timing V61

### Live Probe

Ran `concentration_control_crossroads` in `human_hero` mode to rotate back to a Sorcerer-facing fixture. A temporary human session controlled the level 5 Sorcerer long enough to end the opening turn, then the external monster AI played the Guard, Support caster, and Controller caster.

Artifacts:

- `/tmp/dnd_ai_v61_concentration_crossroads/summary.json`
- `/tmp/dnd_ai_v61_concentration_crossroads_optimized/summary.json`
- `/tmp/dnd_ai_v61_concentration_crossroads_instrumented/summary.json`
- `/tmp/dnd_ai_v61_concentration_crossroads_instrumented/agent_events_raw.json`
- `/tmp/dnd_ai_v61_concentration_crossroads_instrumented/human_session.json`
- `/tmp/dnd_ai_v61_concentration_crossroads_instrumented/boundary_after_ai.json`
- `/tmp/dnd_ai_v61_concentration_crossroads_instrumented/server.log`

### Findings

Behavior:

- The control/support composition worked without changing global monsters, spells, or gear.
- Across the optimized/instrumented probes, the enemy side selected control and support spells such as `Hold Person__slot_2`, `Magic Missile__slot_1`, and `Shield of Faith__slot_1`.
- The Guard still screened with movement and melee pressure.
- The AI did not collapse into "walk forward and basic attack" despite a mixed control/support fixture.

Agent/operator friction:

- `start-ai-validation?mode=human_hero` starts the monster AI session but does not create or return a human operator session for the hero.
- The probe had to call `/session/create`, `/game/join`, and then `/action/end-turn` before the external AI round could run.
- This should become a validation-harness improvement, because the arena start payload already has enough information to make the operator handoff seamless.

Speed:

- The projection cache fix worked:
  - condition-application projection fell from `164.296 ms` to about `1.107 ms`;
  - cast-spell projection fell from `8.428 ms` in the first crossroads run to about `0.142 ms` in the instrumented run.
- The remaining slow path moved elsewhere:
  - max command runtime was `300.133 ms`;
  - max server total was `250.537 ms`;
  - max `get_available_actions_ms` was `208.388`;
  - max `collect_entity_actions_ms` was `165.745` in the optimized probe;
  - max `collect_aoe_actions_ms` in the instrumented probe was `29.221`.
- Movement/path instrumentation now shows:
  - max `senses.compute_paths_ms=19.211`;
  - max `grid.compute_paths.dijkstra_total_ms=19.201`;
  - max `grid.compute_paths.can_enter_ms=10.327`.

The projection layer is no longer the main issue in this fixture. The next hotspot is entity-action discovery for caster/controller epochs, and it needs per-template or per-target-generation timing before changing semantics.

### Integrated Changes

- Reused a combat-log visibility context for each projection pass.
- Avoided recursive combat-log model copies when the visible log tree is unchanged.
- Dumped the filtered combat log once and reused the JSON payload for both frame and patch.
- Added a projection-pass entity fact cache so repeated condition-application events do not recompute the same visible entity fact.
- Added core `GridMap.compute_paths` callback timing for Dijkstra total, walkability checks, tile-cost checks, and transition checks.
- Added focused assertions for the new path timing fields.

No global monster factories, spell definitions, gear packages, or arena defaults were changed in this slice.

### Verification

- `uv run pyright dnd/core/gridmap.py ai/observation/projector.py tests/manual/test_36_seamless_subjective_runtime.py`
- `uv run pytest tests/manual/test_28_subjective_observation_stream.py -q -k 'combat_logs or replayable or sensory_updates'`
- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q -k 'accepted_command_publishes_result_then_followup_epoch or published_epoch_timing_breaks_down_available_action_discovery'`

### Next Targets

- Add per-template/per-target timing inside entity-action collection so caster epochs explain `collect_entity_actions_ms`.
- Improve the validation harness so `human_hero` startup returns or creates a usable operator session.
- Rotate to a skeleton-side fixture next before returning to Barbarian pressure.

## 2026-07-04 - Skeleton Mark Focus Fire Arena Coverage And Passive Perception V62

### Live Probe

Ran `skeleton_mark_focus_fire` in `human_hero` mode to rotate back to a skeleton-side fixture. A temporary human session controlled the shield Fighter long enough to end the opening turn, then the external monster AI played the Focus Guard, Focus Archer, and Focus Warlock.

Artifacts:

- `/tmp/dnd_ai_v62_skeleton_mark_focus/summary.json`
- `/tmp/dnd_ai_v62_postfix_skeleton_mark_focus/summary_final.json`
- `/tmp/dnd_ai_v62_postfix_skeleton_mark_focus/telemetry_summary.json`

### Findings

Behavior:

- The scenario uses fixture-level composition only. No global monster factories, spell definitions, or gear packages were changed.
- The enemy side selected `Mark Target`, `Attack_RANGED_MAIN`, `Eldritch Blast`, `Attack_MELEE_MAIN`, movement, spacing, and end-turn branches.
- The focus-fire fixture did what it was meant to do: it made support marker behavior visible without forcing a bespoke monster or spell implementation.

Arena coverage:

- The local validation catalog already has 29 arenas. It samples doors, water, difficult terrain, anti-AoE spacing, class-party enemies, ranged kiting, control/support casters, high-level spells, darkness/reveal tools, trap levers, condition locks, anti-healing, weapon resistance/vulnerability, field loot, restoration triage, and multi-target projectile allocation.
- The bigger issue was not the number of arenas. The harness scheduler was failing to sample `resistance_weapon_counterplay`, so a catalog arena existed but was unreachable in long rotations.
- The harness now treats weapon-loadout, weapon-choice, damage-affinity, resistance, and vulnerability as schedulable pressure tags, and the long-schedule test compares against the full catalog.

Speed:

- New per-template entity-action timing showed this skeleton-side fixture is not slow in entity-action discovery:
  - max `collect_entity_actions_ms=0.811`;
  - max variant generation `0.142 ms`;
  - max target-pool build `0.061 ms`;
  - max target validation `0.183 ms`;
  - max action-info build `0.014 ms`.
- The slow command was a movement-end senses refresh:
  - movement row `position|Move|pos=7,7`;
  - total action server timing `173.459 ms`;
  - final `update_senses` timing `162.230 ms`;
  - `snapshot_perception_ms=142.634`, almost entirely `passive_skill.perception.skill_bonus_ms=142.589`.
- Passive no-target skill reads now avoid the unnecessary final deep copy used by the public `skill_bonus()` method. In a local micro-benchmark, `get_passive_perception()` dropped from about `1.477 ms` per call to about `0.252 ms` after warmup.
- A post-fix live probe confirmed the passive-perception spike is gone:
  - max `snapshot_perception_ms=0.388`;
  - max `passive_skill.perception.skill_bonus_ms=1.064`;
  - max movement `final_update_senses_ms=21.544`.
- The remaining live movement spike moved to a different path:
  - row `position|Move|pos=14,0`;
  - max action server timing `210.038 ms`;
  - `grid.move_entity.fire_entity_entered_ms=182.895`;
  - `entity.update_visibility.compute_fov_ms=174.604`;
  - path/Dijkstra stayed around `19.661 ms`.

### Integrated Changes

- Added per-template/per-bucket entity-action timing assertions for decision-epoch publication.
- Optimized `Entity.passive_skill()` for the no-target passive-read path used by senses snapshots, while leaving public `skill_bonus()` behavior unchanged.
- Fixed validation harness focus matching so resistance and weapon-choice arenas are reachable.
- Made the long-schedule harness test compare against the full arena catalog instead of a stale hand-written subset.

### Verification

- `uv run pyright dnd/entity.py dnd/scenarios/ai_validation_arenas.py tests/manual/test_37_ai_validation_arenas.py tests/manual/test_38_ai_validation_server_start.py tests/manual/test_36_seamless_subjective_runtime.py`
- `uv run pyright ai/validation_harness.py tests/manual/test_39_ai_validation_harness.py dnd/entity.py`
- `uv run pytest tests/engine_book/test_chapter_06_entity_composition.py -q`
- `uv run pytest tests/engine_book/test_chapter_12_senses_light_stealth.py -q -k 'passive_perception'`
- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q -k 'published_epoch_timing_breaks_down_available_action_discovery'`
- `uv run pytest tests/manual/test_37_ai_validation_arenas.py -q`
- `uv run pytest tests/manual/test_38_ai_validation_server_start.py -q`
- `uv run pytest tests/manual/test_39_ai_validation_harness.py -q`

### Next Targets

- Investigate movement `update_position` -> `fire_entity_entered` -> `update_visibility.compute_fov`, which is now the remaining movement spike after the passive-skill optimization.
- Improve validation startup so `human_hero` mode returns or creates a usable operator session.
- Rotate through the 29-arena catalog before adding more fixtures. If the current catalog proves thin, likely additions are counterspell/reaction pressure, summon/body-block pressure, and objective-control pressure with multiple usable map objects.

## 2026-07-04 - Ranged Loadout Kiting Directional FOV V63

### Live Probe

Ran `ranged_loadout_kiting_ring` in `human_hero` mode to rotate back to a Barbarian-facing fixture. A temporary human session controlled the Barbarian long enough to end the opening turn, then the external monster AI played the kiting Warlock, Archer Captain, and Goblin Archer through the first monster round.

Artifacts:

- `/tmp/dnd_ai_v63_ranged_loadout_kiting/summary.json`
- `/tmp/dnd_ai_v63_ranged_loadout_kiting/agent_events_final.json`
- `/tmp/dnd_ai_v63_ranged_loadout_kiting/after_status_final.json`
- `/tmp/dnd_ai_v63_ranged_loadout_kiting/telemetry_summary.json`
- `/tmp/dnd_ai_v63_ranged_loadout_kiting/server.log`

### Findings

Behavior:

- This was still fixture-level composition only. No canonical monster factories, spell definitions, gear packages, or default arena setup were changed.
- The Warlock opened with `Necrotic Bless__slot_2` and carried two extra target UUIDs, confirming the enemy policy can use multi-target support metadata rather than treating the spell as single-target.
- The Archer Captain used `Attack_RANGED_MAIN` and `Extra Attack_RANGED_MAIN`, then spent movement to spread instead of collapsing into melee.
- The Goblin Archer moved from remembered contact back into line, fired `Attack_RANGED_MAIN`, spread, retreated, and ended turn.
- The AI returned control to the human Barbarian after 103 agent telemetry events without hanging.

Speed:

- The old passive-perception spike stayed fixed:
  - max `snapshot_perception_ms=0.439`;
  - max `passive_skill.perception.skill_bonus_ms=0.9`.
- The directional-FOV spike from the V62 post-fix probe was reduced sharply:
  - previous max `entity.update_visibility.compute_fov_ms=174.604`;
  - current max `grid.directional_fov.total_ms=10.651`;
  - current max transition checks `4.672 ms`;
  - current max blocking checks `1.452 ms`;
  - current max supercover-line generation `1.346 ms`.
- The remaining movement cost is now route/path refresh:
  - max `final_update_senses_ms=35.653`;
  - max path/Dijkstra timing `34.581 ms`.
- The slowest full command was still acceptable for this slice:
  - max runtime command timing `166.753 ms`;
  - max action-server timing `148.696 ms`;
  - max `get_available_actions_ms=8.77`;
  - max `collect_entity_actions_ms=0.431`.

The fixture helped avoid overfitting: without adding new content, it exercised ranged loadouts, extra attacks, support spell targeting, remembered contact, spacing, and retreat behavior.

### Integrated Changes

- Added local caching inside directional FOV computation for supercover lines, directional transition checks, and cell blocking checks.
- Added directional-FOV timing fields for line generation, transition checks, blocking checks, and total directional FOV time.
- Preserved the event-driven movement path; movement still emits entered/left spatial events and does not skip intermediate terrain or subjective visibility updates.

### Verification

- `uv run pyright dnd/core/gridmap.py`
- `uv run pytest tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py -q -k 'directional or path or movement or hidden_hazard'`
- `uv run pytest tests/manual/test_37_ai_validation_arenas.py -q -k 'standard_skeleton_door or double_door_dark_hunt or trap_lever or forced_movement'`
- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q -k 'published_epoch_timing_breaks_down_available_action_discovery'`

### Next Targets

- Investigate path recomputation and safe-path filtering during movement-end senses refresh, which is now the main movement cost after passive-skill and directional-FOV fixes.
- Improve validation startup so `human_hero` mode returns or creates a usable operator session.
- Keep rotating through the existing 29 arenas before adding new fixtures. If gaps remain after rotation, add fixture-level counterspell/reaction pressure, summon/body-block pressure, and objective-control pressure with multiple usable objects.

## 2026-07-04 - Multi-Projectile Sorcerer Allocation And Path Callback Cache V64

### Live Probe

Ran `multi_projectile_no_aoe_lab` in `codex_monsters` mode to rotate into a Sorcerer-controlled probe. The external AI controlled the hero-side Sorcerer, while the monster side was Codex-claimed and stopped at the first monster turn.

Artifacts:

- `/tmp/dnd_ai_v64_multi_projectile_no_aoe/start.json`
- `/tmp/dnd_ai_v64_multi_projectile_no_aoe/agent_events_final.json`
- `/tmp/dnd_ai_v64_multi_projectile_no_aoe/after_status_final.json`
- `/tmp/dnd_ai_v64_multi_projectile_no_aoe/telemetry_summary.json`
- `/tmp/dnd_ai_v64_multi_projectile_no_aoe/state.json`
- `/tmp/dnd_ai_v64_multi_projectile_no_aoe/server.log`

### Findings

Behavior:

- This was a fixture-level Sorcerer probe only. No canonical monster factories, spell definitions, gear packages, or default arena setup were changed.
- The Sorcerer selected `Magic Missile__slot_1` with two extra target UUIDs, proving the external policy can consume multi-entity spell metadata and does not collapse every projectile into the first visible target.
- The combat log reported three targets and `7` total force damage:
  - Warrior took `2`;
  - Archer took `2`;
  - Goblin took `3`.
- After the spell, the Sorcerer retreated with `Move` to `(0, 8)` and ended turn at the Codex monster boundary.
- The post-turn objective state left all three enemies alive at `2 HP`, which exposes the next projectile-policy issue: the policy recognizes low-HP split targets, but it does not yet estimate whether splitting actually kills targets versus leaving multiple enemies barely alive.

Speed:

- The per-query path callback cache improved the concrete kiting-ring path micro-benchmark:
  - before: average `16.938 ms`;
  - after: average `12.836 ms`;
  - same actor, same position, same `210` path results.
- In the live Sorcerer probe:
  - max policy tick `3.42 ms`;
  - max command runtime `69.466 ms`;
  - max action-server timing `47.882 ms`;
  - max `final_update_senses_ms=16.938`;
  - max `senses.compute_paths_ms=14.933`;
  - max `grid.compute_paths.dijkstra_total_ms=14.873`;
  - max `grid.compute_paths.can_enter_ms=11.411`.
- The remaining low-level path hotspot is transition validation inside `can_enter`, not policy selection or entity-action discovery.

### Integrated Changes

- Added per-call caches inside `GridMap.compute_paths()` for:
  - walkability checks;
  - tile movement costs;
  - transition/can-enter checks.
- Kept cache scope local to one Dijkstra query, avoiding stale global path data across entity movement, hidden blockers, door changes, and hazard updates.
- Verified that hidden subjective blockers, path-dirty updates, hazards, and decision-epoch timing still behave.

### Verification

- `uv run pyright dnd/core/gridmap.py dnd/core/dijkstra.py`
- `uv run pytest tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py -q -k 'path or movement or hazard or directional'`
- `uv run pytest tests/engine_book/test_chapter_12_senses_light_stealth.py -q -k 'paths or movement or hazard or visibility_cache or blocker'`
- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q -k 'published_epoch_timing_breaks_down_available_action_discovery or accepted_command_publishes_result_then_followup_epoch'`

### Next Targets

- Add projectile allocation scoring that estimates kill thresholds for repeat-allowed spells such as Magic Missile and Scorching Ray. Splitting should beat focus only when it removes or meaningfully disables multiple enemies.
- Continue optimizing `GridMap.can_transition()` / `can_enter` subpaths, because `can_enter` is now most of live path computation time.
- Rotate next into a skeleton-side fixture before returning to Barbarian-facing or Sorcerer-facing probes.

## 2026-07-04 - Kill-Threshold Projectiles And Skeleton-Side Anti-AoE V65

### Integrated Change

Tightened repeat-allowed projectile allocation in the external policy. Magic Missile now uses a conservative one-dart likely-kill threshold of `3 HP`: extra darts are split only onto visible enemies whose known HP is likely removed by one dart. Otherwise, repeatable projectiles stay focused on the primary target so the AI is trying to remove one enemy action source instead of leaving several enemies barely alive.

This is still a policy estimate because the current affordance payload exposes projectile count, repeatability, cost, target options, and damage type, but not per-projectile damage dice. A better future version should serialize damage estimates into the decision epoch instead of hardcoding Magic Missile in policy.

### Live Probe

Ran `skeleton_anti_aoe_split` in `human_hero` mode to rotate back into enemy-side validation. The human-side `Validation Blast Sorcerer` ended the opening turn, the spawned external monster AI controlled the skeleton side, and control returned to the human boundary.

Artifacts:

- `/tmp/dnd_ai_v65_skeleton_anti_aoe/probe.json`
- `/tmp/dnd_ai_v65_skeleton_anti_aoe/telemetry_summary.json`
- `/tmp/dnd_ai_v65_skeleton_anti_aoe/server.log`

### Findings

Behavior:

- No canonical monster factories, spell definitions, gear packages, or default arena setup were changed.
- The existing validation arena content was enough to exercise enemy variety:
  - Warrior moved into melee, attacked, and ended turn;
  - Warlock cast `Necrotic Bless__slot_2` with two extra target UUIDs, then retreated and held spacing;
  - Archer used `Mark Target`, followed with `Attack_RANGED_MAIN`, then retreated and held spacing.
- The AI returned control to the human boundary after `75` agent telemetry events.

Speed:

- Total probe time to human boundary: `4752.1 ms`.
- Agent telemetry stayed empty until roughly `4294.1 ms`, which points at cold subprocess/import/bootstrap latency before the first visible AI event.
- Once active, steady-state decisions were fast:
  - max policy tick `2.06 ms`;
  - max policy selection `0.49 ms`;
  - max affordance projection `1.04 ms`;
  - max state reduction `1.3 ms`;
  - max command runtime `68.64 ms`;
  - max server command timing `51.049 ms`.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "magic_missile or multi_entity or caster_policy"`
- `uv run pyright ai/external/policy.py tests/manual/test_35_subjective_external_ai.py`
- Live `skeleton_anti_aoe_split` `human_hero` probe on `http://127.0.0.1:8130`

### Next Targets

- Serialize repeat-projectile damage estimates into decision epochs so projectile allocation is data-driven rather than Magic Missile-specific.
- Reduce cold external-AI startup latency or prewarm the external agent before the first monster boundary.
- Keep rotating through the existing validation arenas before adding more fixtures. The next real fixture gaps are counterspell/reaction pressure, summon/body-block pressure, and multi-object objective control.

## 2026-07-04 - Barbarian Martial Setup Policy V66

### Content Scope

This pass did not change canonical monster factories, spell definitions, gear packages, or validation arena fixtures. The simulator already had enough content to expose the issue: `caster_crossfire` streams a level 5 Barbarian with legal `Frenzy`, `Reckless Attack`, movement, and melee attack affordances against a guard, archer, and mage.

The problem was policy, not content. The Barbarian received the right rows, but the behavior tree treated the turn like generic melee movement and skipped its own class setup.

### Live Probe

Ran `caster_crossfire` in `codex_monsters` mode twice:

- before patch artifact: `/tmp/dnd_ai_v66_barbarian_caster_crossfire/probe.json`
- after patch artifact: `/tmp/dnd_ai_v66_barbarian_caster_crossfire_after/probe.json`
- after patch telemetry summary: `/tmp/dnd_ai_v66_barbarian_caster_crossfire_after/telemetry_summary.json`
- server log: `/tmp/dnd_ai_v66_barbarian_caster_crossfire_after/server.log`

Before the patch, the external Barbarian selected:

1. `Move` - `move_toward_visible_enemy`
2. `Attack_MELEE_MAIN` - `attack_visible_enemy`
3. `Extra Attack_MELEE_MAIN` - `attack_visible_enemy`
4. `End Turn`

After the patch, the same fixture selected:

1. `Frenzy` - `use_opening_combat_self_setup`
2. `Reckless Attack` - `use_opening_combat_self_setup`
3. `Move` - `move_toward_visible_enemy`
4. `Attack_MELEE_MAIN` - `attack_visible_enemy`
5. `Extra Attack_MELEE_MAIN` - `attack_visible_enemy`
6. `End Turn`

The post-patch run returned control to the Codex monster boundary after `3985.6 ms`, with `45` agent telemetry events.

### Integrated Change

Added an opening combat self-setup branch to the external behavior tree. The branch is intentionally narrow:

- it only runs when visible enemies exist;
- it only consumes legal, streamed self-action rows;
- it prefers `Frenzy` or `Rage` when the actor is not already raging/frenzied;
- it then prefers `Reckless Attack` when not already active;
- it does not invent actions client-side.

The branch also has the same kind of logical annotation as the other high-level routines, so future policy reviews can distinguish its prerequisites, ranking signal, and intended consequences.

### Findings

- Existing arena content is already useful enough to prevent overfitting if we rotate properly. Adding more arenas is useful, but the immediate fix was not to add more monsters or gear.
- The current weak point is that setup semantics are still inferred from names such as `Frenzy`, `Rage`, and `Reckless Attack`. A stronger version should serialize action tags/effects in the decision epoch.
- Cold external-agent startup remains visible. In this run, the first telemetry event arrived around `3751.0 ms`; once the policy was active, ticks were small.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "barbarian or opening_combat_self_setup or logical_annotations or caster_policy or support_policy or tactical_environment"`
- `uv run pyright ai/external/policy.py tests/manual/test_35_subjective_external_ai.py`
- Live `caster_crossfire` `codex_monsters` before/after probes on isolated ports `8131` and `8132`

### Next Targets

- Serialize action semantics and expected self-setup effects in decision epochs instead of relying on display-name matching for martial setup.
- Reduce or prewarm cold external-AI startup latency before the first active agent turn.
- Continue rotating through existing validation arenas before adding new fixtures. Useful new gaps are counterspell/reaction pressure, summon/body-block pressure, and multi-object objective control.
- Next rotation should be Sorcerer-facing, then skeleton-side again, to avoid overtraining on Barbarian openings.

## 2026-07-04 - Sorcerer Spacing Floor After Area Spell V67

### Live Probe

Rotated back to a Sorcerer-controlled validation after the V66 Barbarian run. The probe used existing simulator content only:

- arena: `arcane_device_control`
- mode: `codex_monsters`
- controlled actor: `Validation Device Sorcerer`
- artifacts:
  - `/tmp/dnd_ai_v67_arcane_device_control/probe.json`
  - `/tmp/dnd_ai_v67_arcane_device_control_after/probe.json`
  - `/tmp/dnd_ai_v67_arcane_device_control_after/telemetry_summary.json`
  - `/tmp/dnd_ai_v67_arcane_device_control/server.log`

Before the patch, the external Sorcerer selected:

1. `Fireball__slot_3` at `position|Fireball__slot_3|pos=8,7` - `cast_visible_area_spell`
2. `Move` to `position|Move|pos=0,1` - `retreat_from_visible_enemy`
3. `End Turn` - `hold_ranged_spacing`

That was tactically clunky. The Fireball was good, but the follow-up retreat was wasteful: after the spell, visible enemies were already outside the preferred ranged/caster spacing floor. The agent burned leftover movement to maximize distance rather than holding tempo.

After the patch, the same probe selected:

1. `Fireball__slot_3` at `position|Fireball__slot_3|pos=8,7` - `cast_visible_area_spell`
2. `End Turn` - `hold_ranged_spacing`

The Sorcerer stayed at `(3, 7)` instead of sprinting to `(0, 1)`, and control returned to the Codex monster boundary.

### Integrated Change

Updated the post-pressure spacing branch in the external policy:

- anti-AoE spread from nearby allies still runs first;
- pure retreat now only runs when the ranged/caster actor is inside the preferred enemy spacing floor;
- if the actor is already at or beyond that floor, it holds spacing instead of moving just to increase distance.

This keeps the good ranged/caster survival behavior while removing a noisy, wasteful movement recommendation.

### Timing

The policy itself stayed fast:

- post-patch max policy tick: `4.94 ms`;
- post-patch command sequence: Fireball, then end turn;
- post-patch agent events: `17`.

The slow path is still command execution for area spells, not policy selection:

- post-patch Fireball command runtime: `296.91 ms`;
- server action timing: `247.134 ms`;
- top action phase: `execute_by_index.base_action.convolution_target_apply_ms = 244.377 ms`.

That instrumentation is useful but still too coarse. The next performance pass should split Fireball/area-spell target application into save, damage, condition, death, and event subcosts.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "spacing or sorcerer_holds or ranged_enemy or spent_named or external_agent_uses_follow_up_epoch"`
- `uv run pyright ai/external/policy.py tests/manual/test_35_subjective_external_ai.py`
- Live `arcane_device_control` `codex_monsters` before/after probes on isolated port `8133`

### Next Targets

- Run the next validation on skeleton-side behavior to keep the rotation honest.
- Add per-target area-spell timing under `convolution_target_apply` before trying to optimize Fireball.
- Reduce or prewarm cold external-AI startup latency before the first active agent turn.
- Add new fixture content later only for accumulated gaps: counterspell/reaction pressure, summon/body-block pressure, and multi-object objective control.

## 2026-07-04 - Barbarian Door Dash And Arena Diversity V69

### Live Probe

Rotated back to Barbarian-side validation after the V68 skeleton baseline.

- arena: `double_door_dark_hunt`
- mode: `codex_monsters`
- controlled actor: `Validation Door Barbarian`
- artifacts:
  - `/tmp/dnd_ai_v69_double_door_dark_hunt/probe.json`
  - `/tmp/dnd_ai_v69_double_door_dark_hunt_after/probe.json`
  - `/tmp/dnd_ai_v69_double_door_dark_hunt_after/telemetry_summary.json`
  - `/tmp/dnd_ai_v69_double_door_dark_hunt/server.log`

Before the patch, the Barbarian selected:

1. `Move` to `position|Move|pos=5,0` - `explore_no_contact`
2. `Move` to `position|Move|pos=5,1` - `move_toward_closed_door`
3. `End Turn` - `end_turn`

That was clunky because the actor had found a closed door and still had `Dash` available, but ended the turn before using the action economy to continue the exploration route.

After the patch, the same setup selected:

1. `Move` to `position|Move|pos=5,0` - `explore_no_contact`
2. `Move` to `position|Move|pos=5,1` - `move_toward_closed_door`
3. `Dash` - `dash_toward_closed_door`
4. `Move` to `position|Move|pos=5,7` - `move_toward_closed_door`
5. `Open Door` - `open_adjacent_door`
6. `End Turn` - `end_turn`

The final Barbarian position changed from `(5, 1)` before the patch to `(5, 7)` after the patch, and the first door was opened in the same turn.

### Integrated Change

Added a behavior-tree leaf for no-contact door exploration:

- routine: `_dash_toward_closed_door`;
- prerequisites: no visible enemies, actor position known, at least one known closed door, and an affordable `Dash` row;
- consequents: spend the action to gain movement, then let the next epoch produce route/open-door rows.

The visible-enemy branch remains higher priority. If an enemy is visible and ordinary movement is exhausted, `Dash` still routes through `dash_toward_visible_enemy`.

### Arena Diversity Answer

The simulator already has broad content, and the validation catalog is the correct place to sample it without changing the default game setup. This pass added three opt-in fixtures built from existing engine content:

- `reaction_counterspell_lab`: Counterspell and Shield reaction handlers, spell-interrupt pressure, and caster resources.
- `guardian_choke_body_block`: Guardian of Faith, Spirit Guardians, a blocking frontline body, and a narrow open-door lane.
- `multi_object_control_room`: nearby trap lever, loot cache, wall torch, and Fireball cannon in one decision epoch.

The validation catalog now has `32` arenas. Canonical monster factories, spell implementations, gear defaults, and the default NeuroClient arena were not changed.

### Timing

Policy selection stayed fast:

- max post-patch policy tick: `2.09 ms`;
- max post-patch command runtime: `181.99 ms`;
- post-patch agent events: `45`.

The biggest remaining time cost is still command execution and follow-up epoch production, not the behavior tree itself.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "dash_toward_closed_door or closed_door or visible_enemy_exists_but_no_move_progresses or logical_annotations or movement_policy or remembered_enemy"`
- `uv run pytest tests/manual/test_37_ai_validation_arenas.py -q -k "catalog or reaction_counterspell or guardian_choke or multi_object"`
- `uv run pytest tests/manual/test_38_ai_validation_server_start.py -q -k "arena_list"`
- `uv run pyright ai/external/policy.py tests/manual/test_35_subjective_external_ai.py`
- `uv run pyright dnd/scenarios/ai_validation_arenas.py tests/manual/test_37_ai_validation_arenas.py tests/manual/test_38_ai_validation_server_start.py`
- Live `double_door_dark_hunt` `codex_monsters` before/after probes on isolated port `8135`

### Next Targets

- Run one of the new validation arenas next, preferably `reaction_counterspell_lab` or `multi_object_control_room`.
- Teach enemy policy to reason about reaction-defense capability and multi-object priority using epoch data rather than hardcoded object names.
- Split movement command wall time into route execution, senses recompute, follow-up epoch generation, and runtime history fetch.
- Keep canonical monster, spell, and gear factories stable until a validation fixture repeatedly proves a default-game change is needed.

## 2026-07-04 - Sorcerer Reaction Telemetry And Information-Gain Annotations V70

### Design Note

The V69 door-Dash change needed one refinement before the next playtest: Dash should not steal the action if ordinary movement can still approach the door. That invariant is now local to `_dash_toward_closed_door`, not only implied by behavior-tree ordering.

Door and corner actions also need better logical labels. Opening a door, moving through an open doorway, and exploring around corners are not just movement/object actions; they are information-gain boundaries that may reveal new enemies, objects, hazards, terrain, and line-of-sight facts.

### Live Probe

Rotated to Sorcerer-side validation after the V68 skeleton and V69 Barbarian passes.

- arena: `reaction_counterspell_lab`
- mode: `codex_monsters`
- controlled actor: `Validation Counterspell Sorcerer`
- artifacts:
  - `/tmp/dnd_ai_v70_reaction_counterspell_lab/probe.json`
  - `/tmp/dnd_ai_v70_reaction_counterspell_lab_after/probe.json`
  - `/tmp/dnd_ai_v70_reaction_counterspell_lab_after/telemetry_summary.json`
  - `/tmp/dnd_ai_v70_reaction_counterspell_lab_after/server.log`

The live behavior was tactically interesting:

1. `Fireball__slot_3` - `cast_visible_area_spell`
2. rejected by `Validation Counterspell Abjurer` via Counterspell
3. `Fireball__slot_3` again - `cast_visible_area_spell`
4. accepted, because the Abjurer's reaction had been spent
5. `Move` - `retreat_from_visible_enemy`
6. `End Turn` - `hold_ranged_spacing`

This is not automatically bad gameplay. Baiting Counterspell and then recasting can be correct when the actor can spend another slot and the enemy reaction is gone. The problem was observability: before the patch, the rejected Counterspell appeared as `command.ack.rejected` and `runtime.command_timing`, but not as an `external_ai.command_result`. A dashboard or reviewer looking at external policy events saw two Fireball policy ticks and only one accepted Fireball command result.

### Integrated Changes

External command telemetry:

- rejected/stale execute commands now emit `external_ai.command_result`;
- rejected/stale end-turn commands also emit the same family;
- the event includes status, row id, template, reason, message, result payload, and runtime timing.

Logical annotations:

- `_open_adjacent_door` now labels observation-frontier expansion;
- `_move_toward_known_open_door` now explicitly documents doorway/corner crossing as information-gain movement;
- `_explore_when_no_contact` now marks high-information movement over corners, doorways, and light boundaries;
- spell rows now note that high-value spells may force defensive reactions such as Counterspell or Shield.

Door-Dash policy:

- `_dash_toward_closed_door` now refuses to fire if ordinary movement can still progress toward the door;
- focused regression proves the actor chooses `Move` instead of `Dash` when both are legal and movement advances toward the door.

### Before/After Telemetry

Before:

- external command results: accepted Fireball, accepted Move, accepted End Turn;
- rejected external command results: `0`;
- rejected command acks: `1`.

After:

- external command results: rejected Fireball, accepted Fireball, accepted Move, accepted End Turn;
- rejected external command results: `1`;
- rejected command acks: `1`.

The policy remained cheap:

- max post-patch policy tick: `7.17 ms`;
- max post-patch command runtime: `269.33 ms`.

The command runtime is still dominated by accepted Fireball execution and follow-up publication, not behavior selection.

### Remaining Friction

The reduced agent state still does not explicitly carry reaction-defense facts. The agent can now observe the Counterspell rejection cleanly, but the policy does not yet make an intentional proposition like:

- enemy has shown Counterspell;
- enemy reaction is probably spent this round;
- recasting a high-value spell is now more attractive;
- lower-value bait spells might be preferred when the reaction is still live.

That should be the next reaction-lab policy slice.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "dash_toward_closed_door or preserves_action or logical_annotations or known_open_door"`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "traces_rejected_execute or logical_annotations or preserves_action"`
- `uv run pyright ai/external_melee_agent.py ai/external/policy.py tests/manual/test_35_subjective_external_ai.py`
- Live `reaction_counterspell_lab` `codex_monsters` before/after probes on isolated port `8136`

### Next Targets

- Add reaction-defense facts to the reduced agent state so repeated spell casting after Counterspell can become deliberate.
- Run a skeleton-side validation next to keep the Barbarian/Sorcerer/skeleton rotation honest.
- Teach the policy to distinguish valuable reaction bait from accidental repeated command attempts.
- Continue keeping canonical monster, spell, and gear factories stable until repeated validation evidence justifies promotion.

## 2026-07-04 - Skeleton Baseline Actor Telemetry V68

### Live Probe

Rotated to skeleton-side validation after the V67 Sorcerer probe.

- arena: `standard_skeleton_doors`
- mode: `human_hero`
- controlled side: external monster AI
- temporary human role: joined the `Validation Sorcerer`, ended the opening hero turn, then waited for control to return
- artifacts:
  - `/tmp/dnd_ai_v68_standard_skeleton_doors/probe.json`
  - `/tmp/dnd_ai_v68_standard_skeleton_doors_after/probe.json`
  - `/tmp/dnd_ai_v68_standard_skeleton_doors_after/telemetry_summary.json`
  - `/tmp/dnd_ai_v68_standard_skeleton_doors/server.log`

The skeleton behavior itself looked solid enough that I did not add a gameplay rule blindly:

- the Warlock used `Necrotic Bless__slot_2`;
- the skeleton side navigated to and opened the door;
- the Warrior used movement plus `Dash` to close;
- the Archer used `Mark Target`, followed with `Attack_RANGED_MAIN`;
- the encounter returned to the human boundary.

### Friction

The real clunk was observability. Before the patch, the policy trace made each multi-actor monster turn harder to review:

- policy ticks with missing `actor_name`: `14`;
- command-result events with missing event actor UUID: `14`.

That meant the dashboard or a human reviewer had to infer which skeleton was acting from surrounding state and UUIDs. That is too much friction for a controller loop where we want every decision to be inspectable.

### Integrated Change

Added readable actor facts to external policy telemetry:

- `actor_name`;
- `actor_position`;
- `actor_conditions`.

Also changed external trace correlation so `command_result` events use `entity_uuid` as the event actor UUID when no explicit `actor_uuid` is supplied.

Post-patch:

- missing policy actor names: `0`;
- missing command-result actor UUIDs: `0`;
- policy ticks are directly readable as `Validation Skeleton Warlock`, `Validation Skeleton Warrior`, and `Validation Skeleton Archer`.

### Timing

Policy selection stayed fast:

- max post-patch policy tick: `3.09 ms`.

The main performance note from this run is not policy selection:

- max post-patch command runtime: `222.95 ms`;
- max raw action execution timing: `47.381 ms`;
- top raw action phase: `execute_by_index_ms = 46.606 ms`.

The gap between command wall time and raw action time means the next instrumentation pass should split movement command wall time into route execution, senses recompute, follow-up epoch generation, and runtime history fetch.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "normal_path or trace_uses_entity_uuid or policy_tick or spacing or tactical_environment or support_policy"`
- `uv run pyright ai/external_melee_agent.py tests/manual/test_35_subjective_external_ai.py`
- Live `standard_skeleton_doors` `human_hero` before/after probes on isolated port `8134`

### Next Targets

- Rotate next to Barbarian-side or Sorcerer-side validation, not another skeleton baseline.
- Split movement command wall time into route execution, senses recompute, follow-up epoch generation, and runtime history fetch.
- Reduce or prewarm cold external-AI startup latency before the first active agent turn.
- Add new fixture content later only for accumulated gaps: counterspell/reaction pressure, summon/body-block pressure, and multi-object objective control.

## 2026-07-04 - Skeleton Persistent Zone Projection And Policy V71

### Live Probe

Rotated back to skeleton-side validation after the Sorcerer reaction pass.

- arena: `guardian_choke_body_block`
- mode: `human_hero`
- controlled side: external monster AI
- temporary human role: joined the `Validation Choke Barbarian`, ended the opening hero turn, then waited for control to return
- artifacts:
  - `/tmp/dnd_ai_v71_guardian_choke_body_block_after/probe.json`
  - `/tmp/dnd_ai_v71_guardian_choke_body_block_after2/probe.json`
  - `/tmp/dnd_ai_v71_guardian_choke_body_block_after2/policy_sequence.json`
  - `/tmp/dnd_ai_v71_guardian_choke_body_block_after2/telemetry_summary.json`

### Friction

The first probe confirmed the policy still preferred direct damage over persistent battlefield shaping:

- `Validation Guardian Caster` selected `Magic Missile__slot_1`;
- reason: `cast_visible_enemy_spell`;
- `Guardian of Faith` was legal in the decision epoch, but the external projection compacted position spells by keeping rows that already affected visible enemies;
- durable zone rows with empty `affected_entity_uuids` were therefore erased before the behavior tree could reason about them.

This was a state-transmission bug more than a pure priority bug. The server knew the action existed, but the reduced agent state did not preserve the tactical candidate.

### Integrated Change

Kept the previous information-gain and door-Dash fixes, then added the missing persistent-zone path:

- policy annotations label door opening and doorway/corner movement as information-gain boundaries;
- `dash_toward_closed_door` now only fires after ordinary movement toward the door cannot produce a command, preserving the action when possible;
- `available_actions_payload_from_epoch()` now preserves persistent position-zone rows such as `Guardian of Faith` even when `affected_entity_uuids` is empty;
- external policy now has `cast_persistent_zone_spell` before direct single-target spell damage.

### Verification

The clean rerun selected durable battlefield shaping:

- `Validation Guardian Caster` selected `Guardian of Faith`;
- reason: `cast_persistent_zone_spell`;
- status: `accepted`;
- returned to the human boundary in `2400.047 ms`;
- max policy tick: `5.36 ms`;
- max command runtime: `190.47 ms`.

Checks:

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "persistent_zone or control_zone or logical_annotations or preserves_action"`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "persistent_zone or compaction_preserves_persistent or compaction_preserves_mobility or control_zone or preserves_action"`
- `uv run pyright ai/external/state.py ai/external/policy.py tests/manual/test_35_subjective_external_ai.py`
- live `guardian_choke_body_block` `human_hero` probe on isolated port `8137`

### Next Targets

- Add reaction-defense facts to the reduced agent state so repeated spell casting after Counterspell can be deliberate.
- Inspect why high-level spell variants expose `spell_slot_cost` as `null` in epoch costs; slot economy should be explicit to the policy.
- Add richer policy debug summaries for skipped candidate families so branch ineligibility is visible without replaying internals.
- Continue rotating Barbarian, Sorcerer, and skeleton-side validation before changing canonical monster, spell, or gear defaults.

## 2026-07-04 - Barbarian Spell Cost Contract V72

### Live Probe

Rotated to Barbarian-side validation after the skeleton persistent-zone pass.

- arena: `condition_lock_sanctum`
- mode: `human_hero`
- controlled side: external monster AI
- temporary human role: joined the Barbarian, ended the opening hero turn, then waited for control to return
- artifacts:
  - `/tmp/dnd_ai_v72_condition_lock_sanctum/probe.json`
  - `/tmp/dnd_ai_v72_condition_lock_sanctum_after/probe.json`
  - `/tmp/dnd_ai_v72_condition_lock_sanctum_after/telemetry_analysis.json`
  - `/tmp/dnd_ai_v72_condition_lock_sanctum_after/telemetry_summary.json`

The behavior was tactically reasonable before the fix:

- `Validation Lock Support` cast `Bless__slot_1`;
- the same support caster followed with `Shield of Faith__slot_1`;
- the support caster spread away after pressure;
- `Validation Lock Controller` cast `Hold Person__slot_2`;
- the controller then spread away;
- the guard moved, attacked, and ended.

### Friction

The bug was in the decision-epoch cost contract, not in the selected behavior:

- pre-fix affordable leveled spell rows with missing `spell_slot_cost`: `773`;
- pre-fix rows with explicit spell-slot cost: `0`;
- post-fix affordable leveled spell rows with missing `spell_slot_cost`: `0`;
- post-fix rows with explicit spell-slot cost: `773`.

The engine already knew the spell variants and slot levels, but `AvailableActionInfo` only exposed the primary action-economy cost. Downstream AI saw `spell_level` and `cast_at_level`, but not the concrete slot resource cost it should reason about.

### Integrated Change

Added the missing cost contract:

- `AvailableActionInfo` now carries full effective costs, not only `cost_type` and `cost_amount`;
- subjective epoch construction aggregates action, bonus action, reaction, movement, spell slot, and named resource costs;
- direct and serialized epoch builders now agree on `spell_slot_cost` for leveled spells such as `Bless__slot_1`.

### Timing

Policy choice stayed fast; the remaining cost is projection/reduction volume:

- max pre-fix policy tick: `24.28 ms`;
- max post-fix policy tick: `19.91 ms`;
- first post-fix support tick: `affordance_projection_ms = 14.52`, `state_reduction_ms = 4.11`, `policy_selection_ms = 0.39`;
- first post-fix position row serialization: `10.784 ms`;
- first post-fix position row normalization: `2.697 ms`.

The next performance target is still position-row projection payload size, not behavior-tree search.

### Verification

- `uv run pytest tests/manual/test_31_subjective_runtime_epochs.py -q -k "spell_epoch_rows_expose_full_spell_slot_costs or direct_epoch_affordance_builder_matches_serialized_legacy_rows or simple_entity_epoch_rows"`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "normal_path or projection_and_reducer_populate_timing_sinks or spell_slot or caster_policy_prefers_visible_offensive_spell"`
- `uv run pyright ai/external/state.py ai/external/policy.py ai/subjective/epochs.py dnd/core/base_actions.py dnd/entity.py tests/manual/test_31_subjective_runtime_epochs.py tests/manual/test_35_subjective_external_ai.py`
- live `condition_lock_sanctum` `human_hero` before/after probes on isolated port `8138`

### Next Targets

- Optimize external position-row projection/reduction so the first support-caster tick is single-digit ms despite hundreds of movement candidates.
- Add skipped-branch candidate summaries so ineligible controls/support/position rows can be reviewed without replaying internals.
- Run Sorcerer next to keep rotation.
- Continue avoiding canonical content changes until repeated evidence justifies them.

## 2026-07-04 - Door Information-Gain Command Tags V73

### Review Note

The user called out two related policy semantics:

- door opening, corner crossing, and similar actions that reveal a lot of state should carry a logical label;
- the AI should not Dash to a door if ordinary movement can reach or approach it, because keeping the action available after opening the door is often the better play.

### Existing Behavior Verified

The no-waste door Dash guard was already present from the previous slice:

- `_move_toward_closed_door` runs before `_dash_toward_closed_door`;
- `_dash_toward_closed_door` refuses to fire if ordinary movement toward the same door can produce a command;
- Dash remains available only when movement is already spent or cannot progress, and no immediate Open Door row is legal.

That policy shape is intentional:

1. Move toward the door with ordinary movement when possible.
2. Open the door when adjacent.
3. Preserve the action for the newly revealed state whenever possible.
4. Use Dash only as a mobility-extension fallback.

### Integrated Change

The missing part was machine-readable labeling. Information-gain semantics existed in prose annotations and command reasons, but not in the command contract consumed by telemetry and future planners.

Added:

- `PolicyLogicalTag`;
- `AgentCommand.logical_tags`;
- central tag derivation from policy reason/action.

Current tags include:

- `information_gain`;
- `reveal_boundary`;
- `preserve_action_economy`;
- `mobility_extension`;
- `route_progress`;
- `pressure`.

Pinned examples:

- `open_adjacent_door` -> `information_gain`, `reveal_boundary`;
- `move_toward_closed_door` -> `information_gain`, `reveal_boundary`, `route_progress`, `preserve_action_economy`;
- `dash_toward_closed_door` -> `mobility_extension`, without `preserve_action_economy`.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "logical_annotations or preserves_action or dashes_toward_known_closed_door or tags_open_door or door_dash_does_not_steal"`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "tags_open_door or preserves_action or dashes_toward_known_closed_door"`
- `uv run pyright ai/external/policy.py ai/external/__init__.py tests/manual/test_35_subjective_external_ai.py`

### Next Targets

- Propagate `logical_tags` into dashboard time series and policy trace grouping so reveal-boundary actions are visible during live reviews.
- Optimize external position-row projection/reduction so support-caster ticks are single-digit ms despite hundreds of movement candidates.
- Run Sorcerer next to keep rotation.
- Add skipped-branch candidate summaries so ineligible controls/support/position rows can be reviewed without replaying internals.

## 2026-07-04 - Subjective Hidden Movement Leak V74

### NeuroClient Repro

The user reported a frontend repro from NeuroClient:

- with the Sorcerer staying still before contact, the enemy AI reliably opens the door;
- if the Sorcerer moves sideways before contact, the enemy AI stops prioritizing the door and routes through slow terrain;
- this happens before any legitimate contact or remembered-enemy state should exist.

### Root Cause

The leak was in AI subjective observation projection, not in the door behavior tree:

- `Encounter._compute_perceivers()` is position-based, so a movement or turn event can be stamped perceivable when one affected tile is visible;
- `_event_state_patches()` then emitted entity facts for referenced event entities using the default `VISIBLE` fallback;
- that meant an entity that was not in the observer's senses could still become a live visible entity fact in the AI observation stream;
- turn-start combat logs also carried hidden actor UUIDs in structured data such as `entity_uuid` and in `perceiver_uuids`;
- movement logs could carry hidden actor identity and path/end-position data.
- multi-target parent combat logs could retain hidden child `target_names` and
  `per_target_logs` after the child entries themselves were filtered;
- visible logs could leak hidden nearby entities through `perceiver_uuids` even
  when source/target identity had already been sanitized.

This matches the symptom: the reducer could receive a fake visible enemy before contact, so the policy would choose visible-enemy movement instead of the known-door branch.

### NeuroClient Audit

NeuroClient's human UI does not consume `/ai/sessions/{session_id}/observation/...` subjective combat logs.

It uses:

- raw `/combat-log`;
- `/events/subscribe` `combat_log` frames;
- `ActionResult.combat_log_entries`.

Those paths still use the encounter's raw combat log. The new sanitizer is scoped to `ai.observation.projector`, which feeds AI/controller subjective snapshots and frames.

The regression now asserts both sides:

- raw `/combat-log` still contains the hidden entity UUID for the normal client path;
- the AI subjective snapshot and follow-up stream do not expose that hidden UUID/name/live position/path.
- a deliberately dirty nested combat-log payload keeps its raw identity on
  `/combat-log`, while the AI subjective snapshot strips hidden UUIDs/names from
  text, nested data, multi-target parent data, and `perceiver_uuids`.

### Integrated Change

Hardened `ai.observation.projector`:

- event entity patches now emit full facts only for controlled or currently visible entities;
- unseen event participants no longer become `visible` facts just because an affected tile is visible;
- AI subjective combat logs sanitize hidden source/target identity;
- hidden UUIDs are removed from `data`, `perceiver_uuids`, and `revealed_entity_uuids`;
- unseen movement logs become generic observed movement without path or end-position.
- structured combat-log data is sanitized recursively across nested dicts, lists,
  and tuples;
- multi-target parent summaries are rebuilt from filtered child logs so hidden
  child payloads cannot survive in parent `per_target_logs`.

### Verification

- `uv run pytest tests/manual/test_28_subjective_observation_stream.py -q -k "unseen_enemy_movement or movement_projection_skips_redundant"`
- `uv run pytest tests/manual/test_28_subjective_observation_stream.py -q -k "unseen_enemy_movement"`
- `uv run pytest tests/manual/test_28_subjective_observation_stream.py -q -k "unseen_enemy_movement or nested_hidden_identity"`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "preserves_action or dashes_toward_known_closed_door or tags_open_door"`
- `uv run pyright ai/observation/projector.py ai/external/policy.py tests/manual/test_28_subjective_observation_stream.py tests/manual/test_35_subjective_external_ai.py`
- `uv run pyright ai/observation/projector.py tests/manual/test_28_subjective_observation_stream.py`

### Next Targets

- After backend restart, run the NeuroClient Sorcerer door repro and record whether the enemy still receives false pre-contact target pressure.
- Continue the rotation with Sorcerer before adding more content or arenas.
- Collect `logical_tags` from completed live games and compare whether information-gain decisions correlate with useful reveals.

## 2026-07-04 - Barbarian Kiting Spacing Telemetry V79

### Context

The rotation moved back to a Barbarian-facing validation after several Sorcerer
and support-policy checks. The selected arena was
`ranged_loadout_kiting_ring`: a Frenzied Barbarian starts across an already-open
door from a ranged-heavy monster side. This is a good pressure test for whether
the enemy AI can attack, spread, and hold spacing without looking like it is
randomly wandering.

### Probe

The run was executed in-process with the external subprocess spawn disabled, so
it did not touch the live NeuroClient backend.

- arena: `ranged_loadout_kiting_ring`;
- mode: `human_hero`;
- hero opening: `Frenzy`;
- enemy commands observed: `10`;
- artifact: `/tmp/dnd_ai_v79_barbarian_kiting_after/summary.json`.

Observed enemy reasons:

- `attack_visible_enemy`: `3`;
- `move_toward_visible_enemy`: `1`;
- `spread_from_allies_after_pressure`: `2`;
- `hold_ranged_spacing`: `3`;
- `cast_opening_controlled_support_spell`: `1`.

Observed logical tags:

- `pressure`: `3`;
- `route_progress`: `3`;
- `spacing_control`: `5`;
- `support_setup`: `1`.

### Integrated Change

The policy already had coherent spacing behavior, but the telemetry was too
weak: spread decisions looked like ordinary route progress, and
`hold_ranged_spacing` was an unclassified end-turn command. That made the
dashboard bad at separating "the archer is preserving a ranged band" from
"the AI gave up."

The spacing surface is now explicit:

- `spread_from_allies_after_pressure`, `retreat_from_visible_enemy`,
  `reposition_for_visible_pressure`, and teleport-style spacing escapes emit
  `spacing_control`;
- `hold_ranged_spacing` emits `spacing_control` even though it is an end-turn
  command without a row id;
- focused tests assert the tag on movement and end-turn spacing branches;
- the dashboard plots `tag_count_spacing_control` beside the existing policy
  tag series.

No monster spells, gear, arena content, or global rules were changed.

### Result

The Barbarian kiting probe looked sane for this slice:

- the archer captain attacked twice, then spread and held spacing;
- the goblin archer moved into useful ranged pressure, attacked, then spread;
- the warlock used `Necrotic Bless` support and held spacing instead of walking
  into melee.

The main remaining friction is explanatory rather than mechanical: the agent
still needs skipped-branch/candidate summaries so we can explain why it held
spacing instead of choosing a different legal movement row.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "mobility_spell or retreat_from_visible_enemy or holds_when_already_beyond_spacing_floor or holds_spacing_after_spending_action or holds_spacing_even_when_epoch_hides_unaffordable_attack or spent_ranged_enemy_spreads or repositions_when_visible_enemy_has_no_pressure_row or spreads_from_allies_after_spending_pressure_action or spent_named_controller_spreads or spent_named_support_holds or does_not_spread_by_collapsing"`
- `node --check /tmp/agent_dashboard_script.js`
- `uv run pyright ai/external/policy.py tests/manual/test_35_subjective_external_ai.py`
- `uv run python -m json.tool ai/AGENT_UX_ITERATION_STATS.json > /tmp/dnd_ai_v79_stats_checked.json`

### Next Targets

- Rotate to skeleton-side or Sorcerer validation next instead of continuing to
  tune Barbarian kiting.
- Add candidate summaries for skipped movement/spacing branches so review can
  explain why a ranged actor held instead of moving.
- If post-reveal routing still looks strange in NeuroClient, add directional
  blocker facts to the reduced route model rather than using raw objective
  state.

## 2026-07-04 - Support Setup Tags And Precontact Guard V78

### Context

The Sorcerer side-move repro needed one more guardrail. The V77 regression
proved that the reduced monster state had no visible or remembered Hero before
door contact, but it did not scan the entire subjective snapshot payload. That
left a possible gap where nested combat logs could still carry the Hero UUID or
name without creating an enemy fact.

At the same time, support/healing policy decisions were still awkward in
telemetry: they were selected deliberately, but they had no clear top-level
logical tag and could be confused with pressure decisions in review charts.

### Integrated Change

- Added `support_setup` as a policy logical tag.
- Support and healing commands such as opening Necrotic Bless and ally healing
  now emit `support_setup` and do not emit `pressure`.
- The dashboard now plots `support_setup` beside `pressure` in the Logical
  Policy Tags chart.
- The Sorcerer side-move regression now scans the full monster-side subjective
  snapshot JSON and fails if the hidden Hero UUID or `"Hero"` name appears
  before contact.

This remains telemetry and test hardening. No monster spells, gear, arena
content, or global rules were changed.

### Investigation Result

I could not reproduce the reported current leak in isolated in-process runs. In
the current code, both the stay-still and side-move paths make the monsters
navigate to the known closed door, open it, and only then receive a visible Hero
fact. A sweep over sampled first-turn Sorcerer side moves also found no
pre-open Hero identity leak in the AI subjective snapshot.

The remaining live discrepancy is likely one of:

- the running NeuroClient backend is still using an older loaded module;
- the issue is post-reveal movement/routing that visually feels like precontact;
- the reduced route model needs directional blocker facts so post-reveal
  movement does not score strange wall-side or slow-terrain positions.

### Verification

- `uv run pytest tests/manual/test_29_external_ai_subprocess.py -q -k "sorcerer_side_move or behavior_tree_opens_adjacent_door_when_no_enemy_is_visible or behavior_tree_moves_toward_known_closed_door"`
- `uv run pytest tests/manual/test_28_subjective_observation_stream.py -q -k "unseen_enemy_movement or nested_hidden_identity"`
- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "opening_group_support or heals_wounded_ally or keeps_opening_group_buff or normal_path_does_not_fetch_available_actions"`
- `uv run pyright ai/observation/projector.py ai/external/policy.py tests/manual/test_28_subjective_observation_stream.py tests/manual/test_29_external_ai_subprocess.py tests/manual/test_35_subjective_external_ai.py`
- `node --check /tmp/agent_dashboard_script.js`
- `uv run python -m json.tool ai/AGENT_UX_ITERATION_STATS.json > /tmp/dnd_ai_v78_stats_checked.json`

### Next Targets

- If the live NeuroClient run still differs, restart the backend and compare the
  first monster `policy_tick` trace against the in-process side-move regression.
- Add directional blocker facts to the reduced route model if post-reveal
  movement still prefers visually strange wall-side or slow-terrain positions.
- Continue the rotation with Barbarian or skeleton-side live validation before
  adding more content or arenas.

## 2026-07-04 - Sorcerer Precontact Side Move Validation V77

### Context

The frontend repro was specifically a Sorcerer moving sideways before contact in
the standard door arena. The projector-level leak tests proved the lower-level
side channel was fixed, but the actual arena flow still needed an in-process
product-path regression.

### Validation

Added a public API regression in `tests/manual/test_29_external_ai_subprocess.py`:

- start `/simulation/start-human?character_class=sorcerer` with external spawn monkeypatched;
- create and join a human session to the Hero;
- fetch public Hero actions and execute a `Move` to `(2, 8)`;
- end the Hero turn;
- fetch the monster AI session observation snapshot;
- materialize the snapshot, build the current decision epoch payload, reduce it to `ExternalAgentState`, and run the policy.

### Result

The monster reduced state after the side move has:

- `0` visible enemies;
- `0` remembered enemies;
- at least one known closed door;
- no selected visible/remembered enemy pressure branch.

The first selected command in this in-process flow is currently
`cast_opening_controlled_support_spell`, which is no-contact support behavior,
not target chasing. That means the remaining live question is not "does the
side move leak the Hero?" but "does the live restarted NeuroClient backend now
match this in-process contract?"

### Verification

- `uv run pytest tests/manual/test_29_external_ai_subprocess.py -q -k "sorcerer_side_move"`
- `uv run pytest tests/manual/test_29_external_ai_subprocess.py -q -k "sorcerer_side_move or behavior_tree_opens_adjacent_door_when_no_enemy_is_visible or behavior_tree_moves_toward_known_closed_door"`
- `uv run pytest tests/manual/test_28_subjective_observation_stream.py -q -k "unseen_enemy_movement or nested_hidden_identity"`
- `uv run pyright tests/manual/test_29_external_ai_subprocess.py tests/manual/test_28_subjective_observation_stream.py ai/observation/projector.py`

### Next Targets

- After backend restart, run the same Sorcerer side-move repro in NeuroClient and compare the live enemy action trace.
- Continue the rotation with skeleton-side control or Barbarian before adding more content or arenas.
- Collect `logical_tags` from completed live games and compare whether information-gain decisions correlate with useful reveals.

## 2026-07-04 - Logical Tags Agent Telemetry V76

### Context

`AgentCommand.logical_tags` existed, and the policy tick included the full
`selected_command` payload, but the tags were not easy to consume:

- dashboard code had to inspect nested command JSON;
- command-result events did not expose the tags directly;
- accepted/rejected action outcomes were harder to correlate with the policy proposition that selected the action.

### Integrated Change

Updated `ai/external_melee_agent.py`:

- `external_ai.policy_tick` events now include top-level `logical_tags`;
- `external_ai.command_result` events now include top-level `logical_tags`;
- nested `selected_command.logical_tags` is preserved for full command auditing.

This is telemetry-only. It does not change behavior-tree ordering, legal action
validation, command execution, or subjectivity.

### Verification

- `uv run pytest tests/manual/test_35_subjective_external_ai.py -q -k "normal_path_does_not_fetch_available_actions or traces_rejected_execute_results"`
- `uv run pyright ai/external_melee_agent.py tests/manual/test_35_subjective_external_ai.py`

### Next Targets

- After backend restart, run the NeuroClient Sorcerer door repro and record whether the enemy still receives false pre-contact target pressure.
- Continue the rotation with Sorcerer before adding more content or arenas.
- Collect `logical_tags` from completed live games and compare whether information-gain decisions correlate with useful reveals.

## 2026-07-04 - Dashboard Subjectivity And Policy Series V75

### Context

The V73/V74 slices added two review surfaces that were not visible in the dashboard:

- policy `logical_tags` for information-gain, reveal-boundary, action-economy preservation, and mobility-extension decisions;
- subjectivity guard metrics for hidden movement, nested combat-log payloads, hidden perceiver metadata, and raw-client path preservation.

The previous dashboard had good separation for payload size, tokens, tool calls, request pressure, latency, and raw-log pressure, but it did not visualize these newer safety and behavior-annotation metrics.

### Integrated Change

Updated `ai/AGENT_UX_ITERATION_DASHBOARD.html`:

- added a `Subjectivity Guards` chart with boolean leak-regression series on their own `0/1` scale;
- added a `Logical Policy Tags` chart with per-iteration tag counts computed from logged JSON arrays;
- kept these charts separate from latency, token, tool-call, and payload charts to avoid scale distortion;
- preserved JSON-backed loading from `AGENT_UX_ITERATION_STATS.json`.

### Verification

- `node --check /tmp/agent_dashboard_script.js`
- `uv run python -m json.tool ai/AGENT_UX_ITERATION_STATS.json > /tmp/dnd_ai_v75_stats_checked.json`

### Next Targets

- After backend restart, run the NeuroClient Sorcerer door repro and record whether the enemy still receives false pre-contact target pressure.
- Continue the rotation with Sorcerer before adding more content or arenas.
- Add dashboard grouping for policy `logical_tags` in completed live games once those tags are emitted in every command event.

## 2026-07-14 - Single Shared Policy Stack V144

### Context

The event-first subjective runtime and shared `PolicyHost` were operational, but
the external controller still retained a complete second reduced-state policy
package as a fallback. Codex turn summaries also ranked actions with an
independent display-name-aware recommendation system. Either path could silently
preempt or disagree with the shared hierarchy.

### Integrated Change

- Removed `ai.external.state`, `ai.external.policy`, and their public exports.
- Moved the surviving typed command projection into `ai.policy.commands`.
- Moved actor search-memory reconciliation and telemetry into `ai.policy.memory`.
- Made external AI and self-play rerank rejected rows through
  `PolicyExecutionConstraints` on the same `PolicyHost` and epoch.
- Applied execution constraints to candidates and multi-step routines before
  proposal selection.
- Removed the production available-actions polling method from the external
  controller.
- Replaced Codex's independent recommendation scorer with a readable projection
  of the exact shared `PolicyDecision`; the raw typed decision remains attached
  to the turn summary.
- Updated the policy source manifest so retained evidence fingerprints only the
  shared knowledge, policy, routine, utility, and command modules.
- Replaced reducer-specific tests with event-first integration, policy-host,
  routine, and command-correlation tests.

### Verification

- `uv run pyright` over the touched policy, subjective runtime, external AI,
  Codex tools, server, and focused test files: `0 errors`.
- `tests/manual/test_29_external_ai_subprocess.py`: `6 passed`.
- `tests/manual/test_30_codex_takeover_tools.py`: `54 passed`.
- `tests/manual/test_31_subjective_runtime_epochs.py`: `29 passed`.
- `tests/manual/test_35_subjective_external_ai.py`: `5 passed`.
- `tests/manual/test_42_action_semantics.py`: `16 passed`.
- `tests/manual/test_44_typed_agent_policy.py`: `39 passed`.
- `tests/manual/test_45_policy_routines.py`: `11 passed`.
- `tests/manual/test_48_policy_host.py`: `18 passed`.
- `tests/manual/test_49_hot_codex_runtime.py`: `11 passed`.
- Focused self-play fallback/counterspell checks: `2 passed`.

### Next Targets

- Resume the Barbarian/Sorcerer/skeleton rotation from the retained V142/V143
  baseline with the single policy stack.
- Replace message-text outcome classification with typed command outcome facts.
- Retain a fresh JSON run artifact before changing policy utility or content.

## 2026-07-14 - Direct Barbarian Review And Typed Agency Value V145

### Retained Play Evidence

The first direct Codex game after the single-stack cleanup is retained at
`ai/evidence/direct_codex_runs/20260714-rotation-3-01-codex-barbarian-vs-ai-v144-single-stack.json`.
Codex controlled the Barbarian through the same hot subjective runtime and
epoch-authorized commands used by the default AI. The game ended in a Barbarian
victory with 15 HP, 248 observation frames, 154 agent events, and five anchored
manual-friction annotations.

The run exposed three separate problems:

- the compact turn response was not compact: one epoch rendered 205 choices,
  including 197 movement rows, into roughly 21,670 characters;
- ordinary movement commands spent roughly 47-58 ms inside engine action
  execution, despite local policy projection remaining below one millisecond;
- the shared utility model ranked Shove above immediate lethal damage because
  every control semantic was credited with a full future denied action, even
  when the action only represented forced movement with no known denial effect.

The third problem belonged to utility interpretation rather than the behavior
tree. Semantic tags determine which utility dimensions are eligible; they do
not establish the magnitude of an outcome that the action model does not
describe.

### Integrated Change

- Soft control remains a typed, inspectable candidate but receives no inferred
  future-action denial value.
- Hard control may receive future-action denial value because its typed
  semantics establish denied agency.
- Forced movement with an unknown endpoint does not inherit hard-control value.
- Added a name-independent regression in
  `tests/manual/test_44_typed_agent_policy.py` proving modeled damage wins over
  unvalued displacement under equal action-economy costs.

The seeded V145 replay is retained at
`ai/evidence/runs/20260714-v145-soft-control-agency-validation.json`. It passed
the subjectivity audit and accepted all 29 commands. Shove remained legal and
was still selected twice, but only after the Barbarian had spent its action and
extra attack. It no longer preempted damage pressure.

## 2026-07-14 - Durable Self-Setup Semantics V146

### Diagnosis

V145 also showed that the default Barbarian never activated Rage, Frenzy, or
Reckless Attack. The available actions existed, but the shared semantic model
could not distinguish durable combat setup from a generic self action. Adding
an ordered name check would have recreated the duplicate policy architecture
that V144 removed.

### Integrated Change

- Added the stable `setup.self` action capability.
- Added typed `SelfSetupSemantics` describing duration, weapon-damage benefit,
  damage resistances, bonus-action attack access, outgoing advantage, and
  incoming-advantage risk.
- Registered exact engine template identities for Rage, Frenzy, and Reckless
  Attack in the shared action-semantic catalog.
- Added a `Preparation/DurableSelfSetup` candidate to the existing utility
  selector. It is a peer proposal, not an ordered exception.
- The conservative autonomous policy currently admits durable setup only.
  Reckless Attack is fully typed and available to LLM control, but the default
  policy does not collapse its short-lived offensive benefit and defensive
  liability into a guessed constant.

The V146 seeded replay is retained at
`ai/evidence/runs/20260714-v146-durable-self-setup-validation.json`. It passed
the subjectivity audit and accepted all 32 commands. The Barbarian selected
Frenzy as command 0, used Frenzied Strike in rounds 2 and 3, killed the guard,
and reduced the archer to 1 HP. In V145 the guard survived at -4 only after the
Barbarian died and the archer remained at 24 HP.

The Barbarian still lost at 8 HP. Its epoch contained healing-potion rows, but
the policy has no typed restoration/resource semantics with which to value
them. That is the next semantic gap; it is not evidence against the setup
branch.

## 2026-07-14 - Complete Policy Provenance V147

### Provenance Correction

The V146 source hash covered candidate generation and policy selection but did
not cover the typed semantic definitions or epoch builder that determine what
the policy can understand. Existing artifacts remain immutable. The policy
source manifest now includes:

- `ai/protocol/control.py`;
- `ai/protocol/semantics.py`;
- `ai/semantics/actions.py`;
- `ai/subjective/epochs.py`;
- the shared knowledge and policy modules already present in V144.

The policy version is now
`2026-07-14.shared-policy-v20-durable-self-setup`.

The identical seeded V147 replay is retained at
`ai/evidence/runs/20260714-v147-policy-manifest-and-setup-validation.json`.
It reproduced V146 exactly: 32 accepted commands, no rejected/stale/error
commands, subjectivity passed, Frenzy on command 0, Frenzied Strike in rounds 2
and 3, and the same final HP vector. Policy evaluation remained around two
milliseconds at its maximum; end-to-end command time still reached 73.624 ms.

### Verification

- `tests/manual/test_35_subjective_external_ai.py`: `5 passed`.
- `tests/manual/test_41_ai_run_artifacts.py`: `6 passed`.
- Focused policy-source endpoint check in
  `tests/manual/test_30_codex_takeover_tools.py`: `1 passed`.
- `tests/manual/test_42_action_semantics.py`: `17 passed`.
- `tests/manual/test_44_typed_agent_policy.py`: `41 passed`.
- `tests/manual/test_48_policy_host.py`: `18 passed`.
- `tests/manual/test_35_subjective_external_ai.py`: `5 passed` after the setup
  integration.

### Next Targets

- Advance the rotation to direct Codex Sorcerer play rather than tuning the
  Barbarian fixture again.
- Model healing/restoration and consumable costs through typed semantics before
  teaching the default policy to use potions.
- Reduce the LLM-facing movement-row presentation without removing any legal
  affordance from the local typed runtime.
- Instrument and reduce the engine movement execution path responsible for the
  47-58 ms action phase.
- Replace command-result message scanning with typed outcome provenance.

## 2026-07-14 - Direct Sorcerer Metamagic And Read-Surface Review V148

### Retained Rotation Evidence

Rotation slot 2 is retained at
`ai/evidence/direct_codex_runs/20260714-rotation-3-02-codex-sorcerer-vs-ai-v148-single-stack.json`.
It contains the pre-action subjective snapshot at cursor 1, all 77 later
observation frames through cursor 78, 40 correlated agent events, and three
evidence-anchored friction annotations. Six submitted commands were accepted;
there were no stale or rejected writes.

The level 5 Sorcerer defeated the Warrior, Archer, and Warlock in round 2 and
ended at 37/37 HP. The command sequence was:

1. use the shared information-gathering proposal to move from `(2,7)` to
   `(7,12)`;
2. use the shared direct-pressure proposal to cast Fireball at `(10,6)`;
3. directly activate Quickened Spell after the main action was spent;
4. use the next shared damage proposal to allocate three level-1 Magic Missile
   darts to the 8 HP Archer;
5. end the turn;
6. use the shared round-2 proposal to allocate three Magic Missile darts to the
   3 HP Warrior and end the encounter.

### Subjective Event Authority

At Fireball selection time, the Sorcerer knew the visible Archer and Warlock.
The selected proposal's typed target evidence contained exactly those two
entities. Objective execution also hit the hidden Warrior inside the selected
area. The resulting combat log then disclosed that collateral outcome through
the normal causal event path.

This is the intended boundary: the policy selected a legal location from
subjective information; the authoritative engine applied area geometry to the
objective world; only the resulting perceivable event introduced the third
identity. No hidden target UUID entered the proposal, target plan, or command.

### Metamagic Gap

After Fireball, the epoch still contained a legal Quickened Spell row, but its
semantics were `unknown`. The shared policy therefore recommended End Turn.
Direct Codex activated Quickened Spell, after which the next epoch correctly
changed spell costs from one action to one bonus action. The existing shared
damage policy immediately selected a useful multi-projectile follow-up.

The missing behavior is therefore not another spell-name preference. It is a
typed action-economy transition and a bounded, revalidating routine:

```text
main action spent + bonus action available + useful spell blocked by action cost
    -> activate a disclosed economy transformer
    -> receive a new authoritative epoch
    -> re-evaluate all transformed spell affordances
    -> execute the best legal follow-up or abandon safely
```

Twinned Spell and future action transformers should use the same contract rather
than receiving separate policy branches.

### Read-Surface And Latency Findings

The hot runtime keeps a complete typed local world as intended, but `/v1/turn`
serializes far too much of it as the default LLM read:

- bootstrap: 209 legal rows and 503,598 JSON characters;
- final decision epoch: 442 legal rows and 1,003,230 JSON characters.

The largest growth comes from flattened movement and area-target rows plus the
complete candidate/evidence trace. The locally cached view can be read in less
than one millisecond, so this is an LLM read-model and serialization-volume
problem, not missing local data or a reason to query the game server again.

The opening five-step movement remained far outside budget:

- task-local command: 113.329 ms;
- server command: 69.343 ms;
- engine action execution: 43.943 ms;
- follow-up epoch construction: 25.135 ms.

The Fireball command took 70.617 ms task-local. The final terminal command fell
to 23.390 ms because encounter completion required no new full decision epoch.

### Adjacent Healing Finding

The preceding Barbarian run exposed unused healing potions. Source tracing now
shows why: the engine currently defines `DrinkPotionAction` with no action or
bonus-action cost, but successful execution consumes one item charge. The epoch
reports neither the charge cost nor a healing effect, and the subjective actor
facts do not distinguish normal HP, temporary HP, or blocked healing. The
shared policy therefore has no sound basis for valuing the row.

This remains an open engine/semantic contract decision. The policy must not add
a potion-name check or invent an action-economy cost. The chosen videogame rule
must first be made authoritative in the engine, then projected as typed healing
and source-item charge semantics.

### Next Targets

- Add a generic typed action-economy transformation contract and a bounded
  transform-then-reassess routine for Quickened Spell.
- Replace the monolithic turn response with a compact default projection and
  typed local queries over the same in-process world and epoch. Do not remove
  legal rows or add game-server polling.
- Decide and pin the single videogame rule for potion action economy, then add
  normal-HP/healing and item-charge semantics before policy support.
- Advance rotation slot 3 to direct Codex skeletons against an AI Barbarian
  after the metamagic/read-surface slice is covered.
- Continue profiling movement execution and epoch construction separately.

## 2026-07-14 - Typed Capability Transformations And Self-Play V149

### Architecture Change

The shared semantic protocol now represents temporary action-surface changes as
typed `CapabilityTransformation` contracts. Selectors match owned capabilities
by category, target allocation, tags, and cost resources. Rewrites describe
cost replacement, additive level-scaled cost, targeting changes, and the action
shape that consumes the temporary effect.

Quickened Spell and Twinned Spell are the first registrations. Their UI labels
are irrelevant to policy behavior. Quickened replaces a positive spell action
cost with the same bonus-action cost. Twinned rewrites single-entity targeting
to two-target multi-entity targeting and projects its additional sorcery-point
cost from the base spell level rather than the upcast level. Twinned preserves
the source spell's repeat-target rule because that is what the engine currently
does.

`ActionCapability` now carries `base_spell_level`. The policy projects a
transformation only to compare combined affordability and sequence utility. It
submits the legal setup row, retains a semantic goal without any future row ID,
and rebinds only after the next authoritative epoch.

### Lifecycle Finding And Repair

The first real replay revealed a lifecycle defect. Quickened correctly enabled
a bonus-action Fireball, but Fireball outranked the particular projected
follow-up. The engine consumed metamagic while routine memory remained active.

The repair uses the generic `consumed_by` selector. A prepared command retains
only the selected row's structural action shape until result correlation. Any
accepted action matching the active transformation's consumption selector
clears that routine progress, including a higher-utility action selected outside
the routine branch. No spell-name or metamagic-specific host logic was added.

### Retained Evidence

The corrected seed-2101 replay is retained at
`ai/evidence/runs/20260714-v149-capability-transform-selfplay.json`.

- arena: `standard_skeleton_doors`;
- result: encounter ended in 10 commands, all accepted;
- subjectivity audit: passed with zero violations;
- final Sorcerer HP: 37/37;
- round 1 sequence: move, Quickened Spell, bonus-action Fireball, normal-action
  Magic Missile, end turn;
- after Fireball, the next epoch reported `no_active_routine`, proving consumed
  transformation memory did not leak into the normal-action follow-up;
- Quickened policy evaluations took 4.178 ms and 2.006 ms;
- all policy evaluations remained at or below 4.178 ms.

### Verification

- `tests/manual/test_31_subjective_runtime_epochs.py`: `30 passed`.
- `tests/manual/test_42_action_semantics.py`: `19 passed`.
- `tests/manual/test_45_policy_routines.py`: `13 passed`.
- `tests/manual/test_48_policy_host.py`: `21 passed`.
- `tests/manual/test_44_typed_agent_policy.py`: `41 passed`.
- `tests/manual/test_35_subjective_external_ai.py`: `5 passed`.
- `tests/manual/test_49_hot_codex_runtime.py`: `11 passed`.
- focused Quickened and Twinned engine tests: `2 passed`.
- touched AI protocol, semantic, epoch, policy, and test files: Pyright clean.

### Next Targets

- Add compact local Codex read projections over the complete cached world and
  epoch without removing legal affordances or adding server polling.
- Advance the rotation to direct Codex skeletons against an AI Barbarian.
- Continue movement and epoch latency work independently of policy evaluation.
- Decide the single potion action-economy rule before adding typed healing and
  item-charge semantics.

## 2026-07-14 - Single Persistent Codex Read Path V150

### Removed Duplicate Path

The old cold Codex CLI and HTTP client performed fresh snapshot reads for
briefs, action lists, turn summaries, watches, row resolution, and command
follow-up. That path duplicated `SubjectiveRuntime`, rebuilt policy state, and
could expose a megabyte-scale turn payload. It has been deleted rather than
retained as a compatibility mode.

`CodexToolClient` now owns takeover lease transport only: create, adopt,
heartbeat, release. The CLI exposes only `hot-serve`, `takeover`, `heartbeat`,
and `release`. Gameplay reads and writes belong exclusively to the authenticated
persistent hot daemon.

### Local Read Contract

`GET /v1/turn` and `POST /v1/watch` now return `HotCodexTurnIndex`. The index
contains the exact subjective revision, actor and action economy, faction-aware
contact partitions, known objects, bounded topology and combat-log summaries,
legal-row counts by bucket and semantic tag, capability count, and only the
selected policy proposal. Full candidate sets and traces are not duplicated.

`POST /v1/query` is revision fenced and reads only the local materialization.
One batch may select exact entities, objects, tiles, observers, capabilities,
or rows; a known map rectangle; a deterministic filtered and paged affordance
set; recent subjective logs; complete session/encounter state; and the full
shared-policy decision. Exact row reads preserve authoritative paths, safe
paths, affected cells, outcome profiles, and resolved typed semantics.

Unknown IDs remain explicit misses. Area selection iterates only accumulated
subjective facts. A stale observation cursor or epoch produces `409` before any
read, so mixed-revision batches cannot be assembled.

### Retained Artifact Proof

The V148 Sorcerer artifact was replayed to cursor 65, its densest epoch:

- 443 complete authoritative rows;
- 18 shared-policy candidates;
- 6 known objects and 1 visible living hostile;
- former turn payload: approximately 1,003,230 characters;
- new default index: 9,782 characters;
- all 443 row IDs reconstructed in deterministic 100-row local pages;
- exact movement paths and the complete 18-candidate policy decision recovered
  on demand from the same revision;
- one bootstrap and zero subsequent upstream reads.

### Validation Harness Repair

The duel harness had an obsolete exact-first-action assertion. Typed capability
transformations now produce the valid sequence `Quickened Spell` followed by
`Hold Person__slot_2`. The test now verifies both commands and the
`TransformThenAct` revalidation trace rather than requiring Hold Person to be
the first command.

### Verification

- `tests/manual/test_30_codex_takeover_tools.py`: `13 passed`.
- `tests/manual/test_33_subjective_runtime_processors.py`: `3 passed`.
- `tests/manual/test_39_ai_validation_harness.py`: `17 passed`.
- `tests/manual/test_49_hot_codex_runtime.py`: `13 passed`.
- `tests/manual/test_50_codex_local_read_model.py`: `2 passed`.
- focused Codex, subjective-query, and test files: Pyright clean.

### Next Targets

- Advance rotation slot 3 to direct Codex skeletons against an AI Barbarian.
- Profile movement action execution and follow-up epoch construction separately.
- Decide the single potion action-economy rule before adding typed healing and
  source-item charge semantics.

## 2026-07-14 - Direct Codex Skeleton Rotation V151

### Runtime Validation

Direct Codex controlled the Guard, Mage, and Archer in `caster_crossfire`
against the normal AI Barbarian through the single persistent hot runtime. The
run used only the compact default turn index, revision-fenced local queries,
and streamed command results and epochs. No gameplay read used the removed
cold CLI path or requested fresh available actions from the game server.

The default opening projection was 8,996 bytes. The Mage's dense epoch exposed
395 legal rows while its default projection remained 9,710 bytes. A complete
policy query was available locally on demand without an upstream request.

### Tactical Result

The three skeleton roles remained distinct without encounter-specific policy
branches:

- the Guard opened with its legal melee attack;
- the Mage selected third-level Magic Missile against a raging Barbarian,
  moved from `(12, 8)` to `(12, 11)` to increase separation, and later used a
  first-level Magic Missile for the final blow;
- the Archer attacked at range, moved from `(12, 6)` to `(13, 5)`, and held
  spacing when further movement had no useful tactical value.

The Barbarian defeated the Guard and damaged the Mage. The Mage and Archer
survived, and the final subjective encounter state marked the Barbarian dead.
All 13 direct Codex commands were accepted; no stale or rejected command was
observed.

### Retained Evidence

The immutable artifact is retained at
`ai/evidence/direct_codex_runs/20260714-rotation-3-03-codex-skeletons-vs-ai-barbarian-v150-local-reads.json`.

- initial subjective snapshot retained before the first command;
- 161 ordered subjective frames through observation cursor 162;
- 87 correlated agent telemetry events;
- one evidence-anchored latency annotation;
- no objective state, visibility, event, or combat-log endpoint used for
  collection.

### Latency Finding

Policy projection remained within a few milliseconds. The slower path was
server-side state transition and reconstruction:

- Mage movement execution: 23.890 ms;
- Mage follow-up epoch construction: 9.517 ms;
- complete server command path: 33.609 ms;
- Archer movement execution: 18.508 ms;
- ordinary attack execution: approximately 7-9 ms.

The movement command is anchored to observation cursor 31, command id
`1b2ebd67-c92b-419f-b39f-64e9e8e83307`, and the exact basis epoch in the raw
artifact. Movement execution and epoch construction must be profiled as
separate engine phases; policy ordering is not implicated by this evidence.

### Next Targets

- Instrument movement across event application, spatial callbacks, senses
  updates, and path recomputation, then remove measured redundant work.
- Profile epoch action discovery, affordance construction, semantics, and
  capability construction independently.
- Decide the single potion action-economy rule before adding typed healing and
  source-item charge semantics.

## 2026-07-14 - Single Typed AI Runtime And Epoch Cleanup V152

### Deleted Alternate Runtime Paths

The controller stack now exposes one AI data and command path. The external AI
owns one `SubjectiveRuntime`, consumes one subjective observation stream, stores
one canonical `SubjectiveWorldState` in `SubjectiveStore.world`, and acts only
from streamed `DecisionEpoch` affordances. The following obsolete surfaces were
deleted rather than retained behind aliases or compatibility flags:

- the external agent's second HTTP client, ad hoc fresh-snapshot fallback, and
  private SSE parser;
- `ObservationMaterializedState`, `WorldState`, `store.materialized`, and the
  `entities`/`objects`/`tiles` aliases over canonical `known_*` fields;
- both JSON-to-affordance reconstruction builders;
- the AI session `/available-actions` polling endpoint;
- the unused JSON-to-semantics adapter;
- the deprecated `/agent/ping` endpoint;
- the unused event-serialization shim.
- the one-value `monster_ai` selector and response field;
- the obsolete `external_melee_agent` module, class, and spawn-method names.

The human `/entity/{entity_uuid}/available-actions` API remains because it is a
NeuroClient presentation contract. Its serializer now lives in
`server.action_serialization`; no human JSON payload is used to construct an AI
epoch.

### Epoch Construction Work

Profiling the direct skeleton rotation isolated repeated behavior-neutral work
inside follow-up epoch construction. Three redundant transforms were removed:

- AoE shape-definition keys: `185` computations became `10`, one per
  affordable AoE variant;
- outcome-profile validation: `98` repeated validations became `8`, one per
  source action row;
- semantic contract hashes: `50` hashes for `24` contracts became exactly `24`
  through structural epoch-local interning.

Warm affordance construction in `caster_crossfire` is now approximately
`4.0-4.5 ms`. Movement remains above the local-stage target because legitimate
cell-by-cell events, sensory updates, light propagation, and final path
recomputation still dominate; that work remains a measured engine target and
was not bypassed.

### Verification

- `tests/manual/test_28_subjective_observation_stream.py`: `26 passed`.
- `tests/manual/test_29_external_ai_subprocess.py`: `4 passed`.
- `tests/manual/test_32_subjective_runtime_store.py`: `9 passed`.
- `tests/manual/test_35_subjective_external_ai.py`: `5 passed`.
- `tests/manual/test_36_seamless_subjective_runtime.py`: `25 passed`.
- `tests/manual/test_38_ai_validation_server_start.py`: `4 passed`.
- `tests/manual/test_40_unified_agent_protocol.py`: `3 passed`.
- `tests/manual/test_42_action_semantics.py`: `19 passed`.
- `tests/manual/test_43_ai_runtime_performance.py`: `9 passed`.
- `tests/manual/test_49_hot_codex_runtime.py`: `13 passed`.
- focused observation replay, removed-route, typed epoch, and human serializer
  checks pass.
- production observation, subjective runtime, semantics, knowledge, policy,
  Codex, external-agent, self-play, and server modules are Pyright clean.

The complete Chapter 31 file remains too slow for a normal focused regression
and exceeded the `180 s` limit; selected epoch cases pass. Chapter 18 also has
two pre-existing magic-number assertions for exact internal event counts; the
semantic client contract passes, and the brittle count issue is recorded in
`KNOWN_ISSUES.md` rather than shaping engine behavior around it.
`test_50_codex_local_read_model.py` executes successfully but its
`_ArtifactRuntime` test double omits three methods required by the complete
runtime protocol; that static-test defect is also recorded in
`KNOWN_ISSUES.md`.

### Next Targets

- Continue measured movement-event and sensory latency work without weakening
  event or subjectivity semantics.
- Decide and implement the single potion action-economy rule, typed healing
  semantics, and item-charge effects.
- Advance rotation slot 4 to direct Codex skeletons against an AI Sorcerer.

## 2026-07-14 - Rotation 3 Slot 4: Direct Codex Skeletons Versus AI Sorcerer V153

### Setup And Runtime Boundary

The fourth slot used `skeleton_anti_aoe_split` in `codex_monsters` mode. One
persistent hot Codex runtime controlled the separated Warrior, Archer, and
Warlock skeletons. The ordinary external agent controlled the level-5
Sorcerer. Codex bootstrapped one subjective snapshot, consumed streamed
epochs, and submitted revision-fenced row IDs through the local hot runtime.
No objective state, visibility, event, combat-log, or available-action route
was used for direct play or artifact collection.

### Combat Sequence And Result

The AI Sorcerer won in the second round. Its policy showed coherent spell and
target-allocation behavior rather than walking into melee:

- the opening five-dart Magic Missile dealt 19 total damage across the three
  skeletons; the Warlock's Shield blocked one dart and the concentrated darts
  killed the Warrior;
- the Warlock critically hit the Sorcerer with Eldritch Blast for 19 force
  damage, and the Archer followed with a nine-damage ranged hit;
- the Sorcerer's next three-dart Magic Missile killed the Archer;
- after the Warlock's second Eldritch Blast missed, Shatter dealt 13 damage and
  killed the last skeleton.

All six direct Codex commands were accepted. There were no stale, rejected,
errored, or missing command results. The final Codex subjective state marked
all three controlled skeletons dead and the encounter ended.

### Retained Evidence

The immutable artifact is retained at
`ai/evidence/direct_codex_runs/20260714-rotation-3-04-codex-skeletons-vs-ai-sorcerer-v153-single-runtime.json`.

- initial subjective snapshot retained before the first direct Codex command;
- 67 ordered subjective frames through observation cursor 68;
- 42 correlated Codex-session telemetry events;
- six accepted command-result correlations;
- two evidence-anchored friction annotations;
- dashboard run 69 generated exclusively from the artifact bytes.

The direct-run schema currently retains only the Codex session. It therefore
proves the controlled side's command lifecycle and terminal subjective state,
but does not independently retain the opposing external agent's policy
identity and telemetry. That is an evidence-schema limitation, not permission
to mix objective information into the Codex stream.

### Causal Read Friction And Fix

At observation cursor 49, the bounded turn index summarized Magic Missile as
three targets and five aggregate damage but omitted which visible skeletons
received the darts. The complete filtered child logs were already present in
the local subjective world. The missing information was therefore a local
projection defect, not absent server data and not a reason for another query
endpoint.

`HotCodexCombatLogSummary` now retains up to eight typed direct causal children
from the already-subjective log. Each child exposes the visible target,
compact outcome, entry type, and success value. Larger actions report an
explicit omitted-child count, while complete detail remains locally queryable.
The projection performs no new discovery and cannot introduce identities that
the subjective event projector removed.

### Performance Finding

Shared policy projection remained approximately 1.6-2.1 ms in the inspected
turns. Complete command processing remained above the local target:

- total command p95/max: 49.575 ms;
- HTTP command submission p95/max: 33.155 ms;
- server command p95/max: 32.106 ms;
- frame fetch p95/max: 4.984 ms;
- frame apply p95/max: 2.847 ms;
- deferred telemetry flush p95/max: 5.241 ms.

Per-command server diagnostics separated engine execution/advancement from
follow-up epoch construction. The first Eldritch Blast spent 6.426 ms in
engine action execution and 5.253 ms constructing its follow-up epoch. Ending
the Archer's turn spent 13.250 ms advancing the autonomous actor and 16.244 ms
constructing the next session epoch. Policy ranking is not the dominant path.

### Verification And Rotation State

- `tests/manual/test_50_codex_local_read_model.py`: `3 passed`;
- focused Pyright for the hot runtime and local read-model test: clean;
- the retained direct artifact validates against schema version 1;
- the JSON dashboard projection completed with 69 artifact-backed runs.

The same test cleanup made `_ArtifactRuntime` implement the complete typed
runtime protocol and removed its dependency on the deleted `materialized`
alias. The corresponding known issue is resolved. Rotation 3 is now four of
six slots complete; slot 5 is the AI-versus-AI Barbarian matchup.

## 2026-07-14 - Evented Item Recovery And Typed Self-Buffs V154-V155

### Retained Pre-Fix Evidence

Rotation 3 slot 5 used `buff_consumable_ambush`, with a level-5 Barbarian
against a caster, Goblin Archer, and skeleton guard. Both factions ran through
the same external subjective runtime and shared `PolicyHost`. The immutable
pre-fix artifact is
`evidence/runs/20260714-rotation-3-05-ai-vs-ai-barbarian-item-economy-v154.json`.

All `21/21` commands were accepted and the objective subjectivity audit passed.
The monster side won in round 3. Haste and greater-invisibility potion rows
were legal, affordable, and present in the relevant decision epochs, but no
actor selected them. The engine exposed bonus-action and finite-charge costs;
semantic conversion reduced both effects to generic `support.buff`, leaving no
typed outcome from which the utility tree could construct a proposal.

### Shared Architecture Repair

Finite consumables now consume charges through a four-phase item event before
their parent action completes. Decision epochs disclose the same charge cost
and remaining pool used by execution. Fixed healing exposes normal HP,
temporary HP, healing prohibition, expected restoration, waste, economy cost,
and finite-item cost to the shared utility selector.

Self buffs use that same architecture rather than a potion branch:

- `ActionSelfSetupProfile` is an engine-owned logical annotation carried by
  action discovery, analogous to the existing stochastic outcome profile;
- the semantic adapter converts any such profile into `SelfSetupSemantics`, so
  custom and localized actions require no AI class-key or display-name rule;
- subjective entity facts project stable condition type keys with explicit
  unknown versus known-empty state;
- duplicate suppression compares those canonical keys, never condition display
  text;
- `Preparation/DurableSelfSetup` remains one utility peer beside pressure,
  control, recovery, positioning, information gathering, and routines;
- setup evidence records duration, active-effect keys, AC, speed, extra actions,
  advantage, invisibility, finite charge cost, and removal liability.

### Corrected Same-Seed Replay

The corrected immutable artifact is
`evidence/runs/20260714-rotation-3-05-ai-vs-ai-barbarian-typed-self-buffs-v155.json`.
It uses the same arena, hero-first rule, seed `2026071435`, and command cap as
V154. All `20/20` commands were accepted, with no stale, rejected, errored, or
missing results. The subjectivity audit again passed.

The behavioral difference follows directly from the new typed outcomes:

- the mage used greater invisibility after landing Hold Person;
- the guard used greater invisibility, then moved and attacked in the same turn;
- the Goblin used Haste, then spent its two actions on two ranged attacks before
  repositioning;
- the mage later used Haste between two level-3 Magic Missile casts in one turn.

The monster side won one round earlier, in round 2, with the Barbarian at `-2`
HP. This is not treated as proof that every buff is optimally calibrated. It is
proof that legal finite buffs now participate in the same typed arbitration and
that the granted action economy is immediately visible in the next epoch.

### Performance And Remaining Work

Local decision work met the current per-stage target in the corrected run:
policy p95 was `2.819 ms` with `3.088 ms` maximum, and complete local decision
p95 was `3.798 ms` with `4.299 ms` maximum. End-to-end work remains above the
goal. Normal total p95 was `91.596 ms`, command HTTP p95 was `55.954 ms`, and
follow-up frame application reached `10.461 ms`.

The outliers are instrumented rather than unexplained. The sampled opening move
spent `61.803 ms` in authoritative position update, including `59.595 ms` in
spatial-enter event delivery and `50.304 ms` in EventQueue storage/projection.
The slow normal end-turn path spent `41.383 ms` constructing the next session's
decision epoch. Hold Person also caused `47.390 ms` of local pre-command stream
catch-up after the preceding session boundary. These engine/event/epoch costs,
not behavior-tree ranking, remain the speed target.

Two rules questions were deliberately not changed during AI work. Haste potion
text says no lethargy while its current `HasteEffect` applies incapacitation on
ordinary removal, and potion-created Haste/greater-invisibility effects omit
the magical condition tag used by their spell counterparts. Both are recorded
in `KNOWN_ISSUES.md` for an explicit single-ruleset decision.

Focused verification: action semantics `21 passed`; typed policy `44 passed`;
subjective observation stream `27 passed`; monster presets `6 passed`; artifact
contracts `6 passed`; touched production modules pass Pyright with zero errors.
Rotation 3 is now five of six slots complete. Slot 6 is the AI-versus-AI
Sorcerer matchup.

## 2026-07-14 - Rotation 3 Slot 6: Source-Action Families And Utility-Aligned Allocation V156-V158

### Retained Baseline And Profile

The baseline slot-6 artifact is
`evidence/runs/20260714-rotation-3-06-ai-vs-ai-sorcerer-typed-self-buffs-v156.json`.
It used `skeleton_anti_aoe_split`, seed `2026071436`, hero-first initiative,
and the same external subjective runtime for both factions. All `14/14`
commands were accepted and the subjectivity audit passed. The Sorcerer won in
round 2, but its opening Quickened Spell decision took `6.769 ms` in policy and
`8.359 ms` for the complete local decision. The next two Scorching Ray choices
took `5.373-6.492 ms` in policy.

The first epoch contained 297 typed damage rows: 153 Fireball positions, 102
Shatter positions, 21 Lightning Bolt positions, 15 flattened repeatable
multi-target rows, and six single-target rows. Those rows became 33 policy
proposals. Profiling proved there was no combinatorial target enumeration; the
dominant duplication was one bounded allocation per flattened primary-target
encoding plus repeated target-independent action-contract and exact outcome
work.

### Source-Action Identity

`ActionAffordance.source_action_id` now identifies every executable row
flattened from one server-discovered action. It is epoch-local control metadata,
not a policy guess and not a display-name classifier. Individual `row_id`
values remain the sole server-executable choices.

The shared policy uses that identity to treat repeatable multi-target rows as
one tactical action family:

- visible legal target options are collected from the subjective epoch;
- one bounded allocation is solved for the family;
- a deterministic legal primary row is retained as the command encoding;
- remaining applications are submitted as extra target UUIDs;
- represented primary rows remain visible in `equivalent_legal_rows` evidence.

Target-independent cost, outcome, and semantic contract keys are computed once
per source action. Slot-scaled Magic Missile and Scorching Ray variants also
share their exact one-application probability model when only the application
count differs. Dense finite-distribution convolution preserves exact
probabilities while reducing Python mapping work.

Typed affordance derivation now groups rows by source action before resolving
semantic indexes. The dense opening's affordance fact section fell from roughly
`1.5-1.6 ms` to `0.4-0.5 ms` without moving work to an objective or alternate
state path.

### Rejected Intermediate Objective

The immutable intermediate artifact
`evidence/runs/20260714-rotation-3-06-ai-vs-ai-sorcerer-source-action-families-v157.json`
is intentionally retained. It passed subjectivity and reduced proposal count,
but the family allocator maximized expected HP loss and a small defeat term
while the outer utility also valued hostile coverage, expected defeats,
reliability, wounded pressure, and expected waste. Four opening Scorching Rays
therefore ignored the Warrior. The same seed took 34 commands and five rounds.

That mismatch was not accepted as a tactical improvement. The bounded dynamic
program now optimizes the same allocation-dependent typed components reported
by `PolicyProposal`. Its state retains used applications, peak wounded pressure,
peak nonzero probability, additive expected HP loss, defeat value, coverage,
and expected waste. The behavior tree, target planner, and utility trace now
have one objective rather than nested conflicting scores.

### Corrected Replay

The corrected artifact is
`evidence/runs/20260714-rotation-3-06-ai-vs-ai-sorcerer-utility-aligned-families-v158.json`.
It uses the exact V156 arena, seed, initiative rule, and command cap. All `27/27`
commands were accepted; stale, rejected, errored, and missing results remained
zero; and the objective disclosure audit passed with no violations.

The Sorcerer again opened with Quickened Spell and two level-3 Scorching Rays.
Both allocations covered the separated Warrior, Archer, and Warlock when the
typed utility justified it. Later turns used lower-level Scorching Ray, Magic
Missile, Haste, and Ray of Frost as slots and enemy HP changed. The Sorcerer won
in round 4 with 37 HP; all three skeletons ended at `-3` HP. The longer outcome
than V156 follows a different deterministic target order and random consumption
path, not hidden information or altered combat rules.

Normal policy p95/max fell to `3.647/4.045 ms`. Affordance-fact p95/max was
`0.453/0.492 ms`, and complete local-decision p95/max was `4.046/4.537 ms`.
The first deep-diagnostic cold decision remained an isolated `5.132 ms` policy
and `5.570 ms` local sample. End-to-end work is still the larger open target:
normal total p95 was `72.006 ms`, command HTTP p95 `40.819 ms`, and follow-up
sync p95 `21.309 ms`.

### Verification And Rotation State

- typed policy: `45 passed`;
- policy host and metamagic routines: `21 passed`;
- action semantics: `21 passed`;
- subjective observation stream: `27 passed`;
- seamless subjective runtime: `25 passed`;
- external AI subprocess: `4 passed`;
- runtime performance contracts: `9 passed`;
- touched production modules: Pyright clean.

Rotation 3 now has all six required slots represented by retained JSON evidence.
The architecture and subjectivity gates passed; end-to-end event/HTTP latency
and the isolated cold-start local sample remain explicit targets before three
consecutive rotations can satisfy the complete goal.

## 2026-07-14 - Rotation 4 Slot 1: Direct Codex Barbarian At The Guardian Choke V159

### Direct Hot-Runtime Match

The immutable artifact is
`evidence/direct_codex_runs/20260714-rotation-4-01-codex-barbarian-vs-ai-guardian-choke-v159.json`.
Codex claimed the hero faction at runtime and controlled the level-6 Barbarian
through the hot typed interface. The normal external shared policy controlled
the Guard, Archer, and Caster in `guardian_choke_body_block`. The retained
evidence contains the pre-command subjective snapshot, 142 later subjective
event envelopes, and 65 correlated agent telemetry events.

Codex issued ten commands and all ten were accepted without stale, rejected,
errored, missing, or resync results. Round 1 established Frenzy, moved through
the open choke, and landed two greataxe attacks that reduced the Guard from 31
HP to 2 HP. Round 2 spent Frenzied Strike first, missed, killed the Guard with
the main attack, moved adjacent to the Archer, and used Extra Attack for 10
damage. The Barbarian then had no action or bonus-action economy and ended the
turn.

The monster policy won during the second enemy sequence. The Archer first
missed, then dealt one post-resistance piercing damage. The Caster's first
Magic Missile used six typed applications for 19 force damage. It then drank a
Haste potion and used the granted action for a three-application Magic Missile.
The latter reduced the Barbarian from 5 HP to -7 and the encounter ended in
round 2. The death transition during the second dart and damage from the final
dart are one already-declared multi-target action, not a new policy command
against a dead target.

### Subjectivity And Agent Experience

The retained stream passed the practical subjectivity checks exercised by the
match. Before re-observation, the Caster's turn and spell were delivered as an
unknown combatant while damage to the controlled Barbarian remained visible.
The Caster persisted as a remembered contact with last-known position and
unknown current combat facts; it did not become a legal target or route input.
When later visible, its identity and current facts were restored through
ordinary sensory events. The direct controller used only its bootstrapped
subjective state, local queries, server-issued epoch affordances, and typed
commands. It did not call objective state, visibility, or available-action
routes.

No manual friction annotation was added to V159. The policy recommendation was
useful at every epoch, but remained advisory: Codex inspected the local typed
state and selected each command through the same command contract used by the
shared policy. The run therefore validates the intended unified surface rather
than a separate LLM controller path.

### Measured Performance

The JSON-derived dashboard reports ten command-timing samples. Runtime total
p95/max was `80.827 ms`; command submission p95/max was `62.793 ms`; server
command p95/max was `61.652 ms`; frame fetch p95/max was `6.661 ms`; frame
application p95/max was `3.822 ms`; and deferred-flush p95/max was `4.224 ms`.
The local frame reducer remained below the current 5 ms stage target, while
authoritative command execution and epoch publication again dominated the
end-to-end budget. These values are retained measurements, not dashboard
defaults or hand-entered estimates.

The direct-artifact contract passed all five focused tests, and the dashboard
projection now contains 75 artifact-backed runs. Rotation 4 is one of six slots
complete; the next slot is direct Codex Sorcerer versus the shared external AI.

## 2026-07-15 - Rotation 4 Slot 2: Direct Codex Sorcerer And Subjective Memory V160-V161

### Direct Hot-Runtime Match

The immutable direct artifact is
`evidence/direct_codex_runs/20260715-rotation-4-02-codex-sorcerer-vs-ai-concentration-crossroads-v160.json`.
Codex claimed the Sorcerer in `concentration_control_crossroads`; the Guard,
Controller, and Support used the same shared external policy. The retained
artifact contains the pre-command subjective snapshot, 125 subsequent
subjective event envelopes, 72 correlated agent telemetry events, and four
manual friction annotations.

All `11/11` direct commands were accepted without stale, rejected, errored, or
resync results. The Sorcerer used Quickened Spell and two level-3 Fireballs to
kill the Guard and Controller in round 1. The surviving Support became
invisible. Codex moved toward its last-known position, cast Shatter, healed,
survived a Shield-blocked Magic Missile sequence, and ended the encounter in
round 3 with Burning Hands.

One choice was an agent-side mistake rather than a disclosure failure. The
Shatter affordance explicitly listed both the Support and controlled Sorcerer
among the affected UUIDs, but Codex did not inspect that typed consequence and
accepted 13 self-damage while dealing 11 damage to the Support. The artifact
retains this as `agent_ignored_or_misinterpreted`; the server neither hid the
risk nor changed the spell rule.

### Subjective Identity Repair

The first systemic defect appeared after the Support became invisible. The
subjective stream correctly retained its UUID, name, and last-known position,
but the remembered fact lost its previously observed faction. The contact was
therefore reclassified as having an unknown relationship, and the shared
search policy said that no remembered hostile existed. This was a loss of
subjective knowledge during redaction, not an omniscience problem.

Remembered entity materialization now preserves previously established faction
knowledge while continuing to redact volatile facts such as HP, AC,
conditions, and current position. Proven death also remains stable across
later redacted envelopes. Fresh snapshots rebuilt from projected history and
incremental replay now produce the same remembered-hostile classification.
Focused regression coverage proves both the retained relationship and the
continued absence of volatile combat facts.

### Typed Damage And Control Arbitration

The direct endgame also exposed a utility mismatch. After Quickened Spell, the
policy recommended Hold Person against the last enemy at 7 of 40 HP even though
direct damage could end the encounter. Hard control had been valued as a fixed
boolean agency denial independent of the amount of agency the wounded target
still possessed.

Hard-control value now scales continuously with the target's known remaining
HP fraction. Healthy targets retain the full denial value; nearly defeated
targets no longer receive the same future-action premium. The change is a
typed outcome rule in the shared utility model, not a spell-name exception or
an arbitrary HP threshold.

Burning Hands and Thunderwave also now expose engine-owned stochastic outcome
profiles with their save ability, half-on-save behavior, affected-entity
scope, damage type, and slot-scaled dice. These annotations do not change spell
execution. They allow the behavior tree and utility layer to compare the real
legal consequences that the engine already implements.

### Corrected Autonomous Replay

The corrected replay is
`evidence/runs/20260715-concentration-crossroads-memory-agency-replay-v161.json`.
It uses the same arena, the shared subjective runtime on both factions, seed
`2026071542`, and policy version
`2026-07-15.shared-policy-v26-subjective-memory-and-agency-value`.

All `16/16` commands were accepted, the disclosure validator passed with zero
violations, and the Sorcerer won in round 3 with 37 HP. The final epoch still
contained a legal Hold Person proposal, but the utility selector ranked
Shatter's lethal damage above it. The selected Shatter affected only the final
hostile and no controlled entity. This validates branch arbitration while
retaining the behavior-tree trace showing both alternatives.

### Performance And Verification

The V160 direct run remained far outside the end-to-end target: runtime total
p95/max was `85.937 ms`, command submission p95/max was `62.323 ms`, and the
worst server command took `61.217 ms`. Frame fetch reached `21.794 ms`, frame
application `12.869 ms`, deferred publication `6.125 ms`, and epoch
construction `16.998 ms` on the sampled Quickened Spell outlier.

V161 separated the same costs more precisely. Fact derivation remained fast at
`0.467/0.483 ms` p95/max. Policy was `5.238/5.980 ms`, and complete local
decision work was `5.716/6.442 ms`. Runtime total was `85.153/114.738 ms`,
command submission `58.574/60.846 ms`, server command `49.034/50.394 ms`,
frame fetch `20.732/22.966 ms`, and frame application `12.552/13.575 ms`.
The remaining latency is therefore primarily synchronous engine/sensory event
fanout, epoch projection/publication, HTTP command transport, and stream
catch-up rather than fact or utility computation.

Focused verification passed: subjective observation stream `27 passed`;
subjective runtime store `9 passed`; spellcasting core `10 passed`; subjective
runtime epochs `30 passed`; typed policy `46 passed`; policy host `21 passed`;
external AI subprocess `4 passed`; direct artifact contracts `5 passed`; and
dashboard projection `5 passed`. Targeted Pyright over the changed observation,
policy, and spell modules reported zero errors. The JSON-driven dashboard now
contains 77 artifact-backed runs.

Rotation 4 is two of six slots complete. Slot 3 is direct Codex control of the
skeleton side against the shared AI Barbarian.

## 2026-07-15 - Rotation 4 Slot 3: Direct Skeleton Side And Conditional Target Effects V162-V164

### Direct Hot-Runtime Match

The immutable direct artifact is
`evidence/direct_codex_runs/20260715-rotation-4-03-codex-skeletons-vs-ai-barbarian-double-door-v162.json`.
Codex claimed the Guard, Archer, and Warlock in `double_door_dark_hunt`; the
Barbarian used the shared external policy. The artifact retains the initial
subjective snapshot, 361 later subjective event envelopes, 196 correlated
agent events, and three evidence-anchored friction annotations.

The Warlock found and opened both closed doors without enemy knowledge. The
Archer then traversed the opened corridor, and the Guard dashed through it and
made first contact with the Barbarian. Later, the Warlock deliberately cast
Necrotic Bless with the Barbarian as the living primary target and the Archer
and Warlock as additional undead targets. The Barbarian failed its Charisma
save and received Bane; both undead recipients received Bless. This proved the
engine's multi-target execution path was already correct.

All authoritative commands were accepted. One attempted command used an old
local revision and was rejected by the hot runtime before it reached the
engine, proving the local revision fence rather than creating a stale engine
command. The Barbarian won in round 5 after killing the Guard, Archer, and
Warlock.

### Retained Friction

The first policy defect was cross-actor corridor use. After the Warlock opened
both doors, the Archer policy proposed an unrelated frontier at `(10, 10)`
instead of traversing the newly known open corridor. Codex overrode it with the
legal move to `(6, 7)`. The session knew the topology change; the exploration
policy did not convert that shared fact into a useful actor-local objective.

The strongest semantic defect was Necrotic Bless itself. Its epoch rows
contained all legal target options, a four-target unique allocation, resource
costs, and concentration replacement, but the action contract was only generic
`spell.effect`. It did not disclose the rule branch "undead receives Bless;
non-undead makes a Charisma save against Bane." The shared policy therefore
could not create a candidate and proposed only Eldritch Blast. Codex had to
inspect engine code to understand a rule that belonged in the epoch.

The Guard's movement to `(5, 7)` also took `66.473 ms` locally. Runtime work was
`57.795 ms`, server command work `41.252 ms`, and
`execute.action_by_index` alone `35.341 ms`. This remains a measured engine and
projection latency regression rather than policy computation.

### Engine-Owned Conditional Target Semantics

Actions can now expose an `ActionTargetEffectProfile` beside outcome and
self-setup profiles. Each branch declares:

- a stable effect identity;
- beneficial, harmful, or neutral disposition;
- included and excluded creature types;
- automatic or saving-throw resolution with actor-known save data;
- resulting planning facts and stable condition keys.

Necrotic Bless declares two branches directly on the spell rule. The undead
branch automatically establishes Bless; the non-undead branch uses the
caster's current Charisma save DC and establishes Bane on failure. Target
count, uniqueness, costs, and concentration remain in their existing typed
contracts rather than being duplicated.

The semantic adapter converts any engine target-effect profile into
`TargetEffectSemantics`. The subjective entity fact now includes creature type
only while the entity's live details are observable. Hidden entities remain
absent, remembered entities do not gain undisclosed live creature data, and
the policy never infers type from names.

### Generic Composite Allocation

The shared candidate layer now groups flattened rows by source action, matches
each legal target against its observable branch predicate, rejects unknown
predicates, and allocates:

- beneficial branches only to controlled or known allied recipients;
- harmful branches only to visible hostiles;
- no branch to a recipient already observed with every resulting condition;
- no more than the server-declared maximum, respecting unique-target rules.

The action and resource cost is charged once, and concentration replacement is
penalized once. The selected proposal retains per-recipient branch evidence so
command telemetry can distinguish the action's complete possibility set from
the exact effects selected in this command. There is no display-name or
Necrotic-Bless-specific policy branch.

### Autonomous Replays

V163 is
`evidence/runs/20260715-double-door-dark-hunt-necrotic-semantics-replay-v163.json`.
Both factions used the same shared subjective external policy with seed `163`.
The Warlock autonomously cast Necrotic Bless in round 1 across the Archer,
Warlock, and Guard before hostile contact. All `71/71` commands were accepted,
the encounter ended in round 6, and the subjectivity audit passed. The
Barbarian survived with 30 HP; all three monsters were defeated.

That replay exposed an observability defect: the command carried the union of
the spell's support and control tags, so a buff-only allocation was reported as
`control_landed`. V164 is
`evidence/runs/20260715-double-door-dark-hunt-target-telemetry-replay-v164.json`.
Per-recipient target-effect evidence now drives command logical tags. The same
deterministic cast reports `support_setup` and `target_allocation`, with no
control command or control outcome. V164 again ended normally with `71/71`
accepted commands and a passed subjectivity audit.

### Performance And Verification

V164 local decision work remained fast: `2.710/4.008 ms` p95/max. Fact
derivation was `0.294/0.334 ms`, and policy evaluation was
`2.541/3.839 ms`. End-to-end runtime remained over budget at
`48.246/58.200 ms`; command submission was `41.731/56.287 ms`, frame fetch
`9.887/11.456 ms`, and frame application `5.886/6.946 ms`. The semantic repair
did not move the bottleneck into local policy work.

Focused verification passed: spellcasting core `11 passed`; action semantics
`22 passed`; typed policy `47 passed`; strict subjective observation
`27 passed`; subjective runtime epochs `30 passed`; external AI subprocess
`4 passed`; run artifacts `6 passed`; direct artifacts `5 passed`; and dashboard
projection `5 passed`. Targeted Pyright over all changed engine, observation,
semantic, policy, and command modules reported zero errors. The JSON-driven
dashboard now contains 80 artifact-backed runs.

Rotation 4 is three of six direct slots complete. The next scheduled slot is
direct Codex control of the skeleton side against the shared AI Sorcerer. The
cross-actor corridor objective and engine-side command latency remain open
systemic work for later evidence-driven repairs.

## 2026-07-15 - Rotation 4 Slots 4-6: Direct Anti-AoE Match And Log Contracts V165-V167

### Direct Skeleton-Side Match

The immutable direct artifact is
`evidence/direct_codex_runs/20260715-rotation-4-04-codex-skeletons-vs-ai-sorcerer-anti-aoe-v165.json`.
Codex controlled the Warrior, Archer, and Warlock in
`skeleton_anti_aoe_split`; the level 5 Sorcerer used the shared external
policy. The artifact retains the pre-command subjective snapshot, 161 later
subjective event envelopes, 101 correlated agent events, and four
evidence-anchored friction annotations.

The Sorcerer opened with Quickened Spell, Scorching Ray, and Magic Missile.
The Warlock then used the new conditional target-effect semantics to cast
Necrotic Bless on the hostile Sorcerer and all three undead. The Sorcerer
failed its Charisma save and received Bane; the Warlock, Archer, and Warrior
all received Bless. The Archer pressured at range while the Warrior used a
server-issued path to enter melee. The Sorcerer won in round 4 with 32 HP.
Every direct command was accepted, and local policy evaluation remained about
1.2-3.1 ms during the live match.

### Complete Causal Reconstruction

The bounded hot brief initially made Magic Missile damage appear inconsistent
with current HP. The retained stream proved the engine and complete combat log
were correct:

- round 1 damage was Scorching Ray 17 plus Magic Missile 6;
- round 2 used two Magic Missiles for 8 and 9;
- round 3 used two Magic Missiles for 12 and 12;
- round 4 ended with a 10-damage Fire Bolt.

Across five Magic Missile casts, all 47 damage was represented by one
`spell_damage` child per dart and matched the entity patches exactly. Shielded
darts remained zero-damage children. Deaths for the Warlock, Archer, and
Warrior each appeared once in the relevant damage subtree. The apparent gap
was therefore a local-read-model problem: `recent_combat_logs` retained only
three top-level entries without disclosing how many earlier local entries had
been omitted.

`HotCodexTurnIndex` now exposes `omitted_combat_log_count`. The compact index
remains bounded, but Codex can tell immediately when the complete already-local
history contains additional actions.

### Generic Combat-Log Repairs

The direct cast exposed two real target-metadata defects.

First, generic non-damage spell children were serialized through the
self-action payload. The three successful undead branches of Necrotic Bless
therefore repeated the Warlock identity instead of identifying the distinct
recipients. `SelfActionLogData` has been replaced by one `ActionLogData`
contract with optional target name and UUID. Generic targeted effects now
carry target identity both on the log entry and in typed log data; no alias or
parallel compatibility model remains.

Second, multi-target enrichment previously treated every direct causal child
as a target application. A `MetamagicActive` cleanup child consequently added
the Sorcerer to one Magic Missile `target_names` list. Target summaries, damage
rows, save counts, and `per_target_logs` are now derived only from typed target
application children, bounded by the parent action's declared application
count. Auxiliary cleanup remains visible in `sub_entries` without becoming a
spell target.

The same trace found a repeated-log cursor collision: the second structurally
identical Quickened Spell resolved to the first log occurrence. Subjective log
cursor lookup now searches the latest matching occurrence, matching the live
append boundary used by initialized observation sessions.

### Autonomous Closing Replays

V166 is
`evidence/runs/20260715-rotation-4-05-anti-aoe-log-contract-replay-v166.json`.
Both factions used the shared external policy in `skeleton_anti_aoe_split`
with seed `2026071544`. All `12/12` commands were accepted, the subjectivity
audit passed, and the Sorcerer won in round 2 with 32 HP. The run exercised
Quickened Spell, repeated Scorching Ray allocation, movement-to-melee
follow-up, ranged pressure, and two multi-target Magic Missile casts.

V167 is
`evidence/runs/20260715-rotation-4-06-sorcerer-barbarian-contrast-v167.json`.
The contrasting `sorcerer_barbarian_duel` used seed `2026071545`. All `18/18`
commands were accepted and the subjectivity audit passed. The Sorcerer won in
round 3 with 30 HP after using Quickened Spell, Hold Person, Scorching Ray, and
Magic Missile. The Barbarian used Frenzy, moved into a legal melee follow-up,
spent Extra Attack, and consumed a healing potion without waste.

V166 local decision p95/max was `4.590/4.590 ms`; fact derivation was
`0.503/0.503 ms`, and policy was `4.139/4.139 ms`. V167 local decision p95/max
was `3.759/3.759 ms`; fact derivation was `0.497/0.497 ms`, and policy was
`3.262/3.262 ms`. End-to-end work remains over budget: V166 runtime p95/max was
`84.110/84.110 ms`, and V167 was `72.139/72.139 ms`. Command submission,
frame fetch, and frame application still dominate rather than local policy.

### Verification And Remaining Friction

Focused verification passed: spellcasting core `13 passed`; validation arenas
`37 passed`; strict subjective observation `27 passed`; hot Codex runtime
`14 passed`; subjective runtime epochs `31 passed`; and targeted combat-log
model integrity `2 passed`. Pyright over the touched engine, projector, and
hot-runtime modules reported zero errors.

The broad book-integrity file still has four unrelated metadata/documentation
failures, and test-file Pyright exposes six pre-existing optional-value errors
in Chapter 13. Both are recorded in `KNOWN_ISSUES.md`; source-only Pyright is
clean.

One policy-semantic defect remains open from V165. The Warrior's correct move
toward an already visible Sorcerer predicted a bounded melee follow-up, but its
proposal was labeled goal `other` with `information.explore` and
`information.reveal`. The action was tactically sound; its logical annotation
was false. Cross-actor exploration objectives and authoritative command/stream
latency also remain open systemic work.

Rotation 4 is six of six slots complete: direct Barbarian, direct Sorcerer,
direct skeletons against Barbarian, direct skeletons against Sorcerer, one
corrected anti-AoE autonomous replay, and one contrasting Sorcerer/Barbarian
autonomous duel. The regenerated JSON-driven dashboard now contains 83
artifact-backed runs.

## 2026-07-15 - Visible-Contact Routine Semantics V168

The retained V165/V166 Warrior approach was tactically correct but described
incorrectly. Every Move affordance truthfully advertises that movement can
cross a reveal boundary, yet those action capabilities are not necessarily the
reason a policy selected the row. Under established visible contact, the
Warrior selected movement because a bounded counterfactual predicted a legal
same-turn melee follow-up.

Routine contracts now carry a typed `RoutinePurpose`. Door approach is
`subjective_discovery`, movement that enables an attack is
`offensive_enablement`, and metamagic-style rewrites are
`capability_transformation`. Proposed door and attack-enabling steps use the
`routine` policy goal. Command annotations combine the chosen routine purpose
with the executed action capabilities instead of matching human-readable
reason strings.

This keeps the two levels distinct:

- the Move row retains `movement.voluntary`, `information.explore`, and
  `information.reveal` as capabilities;
- a door-approach command reports information gain, reveal boundary, route
  progress, and preserved action economy;
- a visible-hostile approach reports route progress, pressure, and preserved
  action economy, without claiming that exploration motivated the command.

V168 is
`evidence/runs/20260715-visible-contact-routine-annotations-v168.json`. It
replayed `skeleton_anti_aoe_split` with the V166 seed. All `12/12` commands
were accepted, the subjectivity audit passed, and the Sorcerer won normally in
round 2 with 32 HP. The Warrior's command 4 moved from `(2, 2)` to `(6, 6)`,
retained `routine.enable_then_act` step `enable -> act`, and emitted exactly
`route_progress`, `pressure`, and `preserve_action_economy`.

Focused verification passed: policy routines `13 passed`; typed policy `47
passed`; policy host `20 passed` with one unrelated stale trace fixture
deselected; and source Pyright reported zero errors. The stale fixture expects
the old trace without `ConditionalTargetEffects` and is recorded in
`KNOWN_ISSUES.md`.

Local decision work remains much faster than the full command lifecycle. V168
fact derivation was `0.419 ms` p95, policy evaluation `5.260 ms`, and local
decision `5.679 ms`; command submission was `60.156 ms`, frame fetch `18.314
ms`, frame application `12.722 ms`, and total command processing `101.304 ms`
p95. Rotation 5 should therefore treat engine execution, epoch construction,
and local frame materialization as measured optimization targets while
continuing the full character rotation.

## 2026-07-15 - Rotation 5 Slot 1: Direct Barbarian At The Hazard Bridge V169

The immutable direct artifact is
`evidence/direct_codex_runs/20260715-rotation-5-01-codex-barbarian-vs-ai-hazard-bridge-v169.json`.
Codex controlled the level 5 Barbarian in `forced_movement_hazard_bridge`; the
Warlock, Mage, and Archer used the shared external policy. The artifact retains
the pre-command subjective snapshot, 154 later subjective event envelopes, 71
correlated agent events, and two evidence-anchored friction annotations.

The Barbarian used Frenzy, crossed to the visible Warlock, and spent both
attacks. In round 2 it killed the Warlock, ending Necrotic Bless concentration,
then killed the Archer with Attack and Extra Attack. The hidden Mage remained
anonymous through its first Magic Missile volley. Its later spellcasting
legitimately revealed identity and last-known position through the subjective
stream before two round-2 volleys reduced the Barbarian from 24 to 0 HP. The
Mage won; no objective state or visibility route was consulted during play.

The direct turn exposed a false exploration proposal. After the Barbarian moved
through `(5, 8)` to `(8, 5)`, the policy proposed moving back to `(5, 8)` and
credited four unknown-frontier adjacencies. A same-revision local tile query
showed that the only four unknown cells were the remote corner cells `(0, 0)`,
`(0, 1)`, `(1, 0)`, and `(2, 0)`. The proposed destination bordered none of
them and was already traversed. The retained annotation anchors the mismatch to
observation cursor 113 and its exact decision epoch.

Movement latency also remains materially above budget. The accepted 25-foot
Move to `(8, 5)` took `85.125 ms` in the hot runtime and `70.401 ms`
server-side. Other commands in the run were materially faster, preserving
movement execution and its event/projection fan-out as a measured optimization
target rather than attributing the delay to local policy evaluation.

Rotation 5 is one slot complete. The next rotation slot returns to direct
Sorcerer control after the exploration geometry is repaired with a focused
regression test. The shared policy remains the only normal AI architecture;
this rotation does not reintroduce a legacy controller path.

### Frontier Knowledge And Epoch Descriptor Replay V170

The false frontier was a knowledge-state predicate defect rather than stale
streaming or coordinate geometry. `exploration_candidates()` counted only
currently visible and remembered tiles as known, while canonical retained map
knowledge uses `seen`. The four neighbors credited at cursor 113 were real
`seen` tiles around the already-traversed path. Exploration now treats every
tile present in the materialized subjective world as accumulated knowledge;
unknown terrain remains represented by absence.

The regression surrounds one legal movement destination with a mixture of
visible and seen tiles and proves that no information-gathering proposal is
generated. Existing tests continue to prove that a genuine frontier is
explored at the exact movement boundary and that equal information gain uses
ordinary movement before consuming a bonus action.

Epoch construction also now derives one immutable build-local descriptor per
available source row. Capability and affordance views share its semantics,
content address, normalized cost, and tags only within that epoch build. No
cross-epoch cache was added, so legality, resources, targets, item charges, and
action rewrites remain freshly authoritative. The representative performance
contract reduced semantics and cost derivations from 110 to the required 61:
one per legal source row plus one per actor-owned capability without a legal
row.

V170 is
`evidence/runs/20260715-rotation-5-frontier-and-epoch-replay-v170.json`. It ran
both factions through the shared external policy in
`forced_movement_hazard_bridge` with seed `2026071551`. All `25/25` commands
were accepted, the subjectivity audit passed, and the encounter ended in round
2 with the Mage and Archer surviving. No exploration proposal was selected in
the fully accumulated state that previously caused false backtracking.

V170 local decision p95/max was `3.028/4.710 ms`; frame fetch was
`12.783/20.040 ms`, frame application `7.366/11.501 ms`, and total command
processing `83.378/89.116 ms`. The build-local duplication is gone, while the
remaining command, movement, and replay costs stay explicit optimization work.
Focused verification passed: latency-sensitive runtime `10 passed`, subjective
epochs `31 passed`, action semantics `22 passed`, typed policy `48 passed`, and
source/test Pyright reported zero errors.

## 2026-07-15 - Rotation 5 Slot 2: Direct Sorcerer In The Darkness Labyrinth V171

The immutable direct artifact is
`evidence/direct_codex_runs/20260715-rotation-5-02-codex-sorcerer-vs-ai-darkness-labyrinth-v171.json`.
Codex controlled the level 5 Sorcerer in `darkness_reveal_labyrinth`; the
Shadow Mage, Reveal Mage, and Shadow Scout used the same shared external policy
as every normal AI combatant. The artifact retains the pre-command subjective
snapshot, 242 later subjective event envelopes, 117 correlated agent events,
and four evidence-anchored friction annotations.

The Sorcerer opened with Invisibility, crossed the subjective map, discovered
and opened the Shadow Door, and reached contact without receiving hidden enemy
positions. Quickened Scorching Ray then enabled two casts in one turn. A later
level-2 cast explicitly allocated one ray to each visible hostile, killing the
Shadow Mage and Shadow Scout and proving that direct Codex control can inspect
and execute repeated multi-target applications locally. The surviving Reveal
Mage won in round 4 with a six-dart Magic Missile volley. No objective state,
visibility route, or available-action polling endpoint was used during play.

The match exposed three shared-model defects. First, a target's natural-20
Hold Person save correctly left the caster non-concentrating, while the command
message incorrectly claimed it was still concentrating; the top-level
spell-save log also omitted the roll retained by its nested saving-throw entry.
Second, a spacing retreat was immediately followed by a same-turn exploration
proposal back toward the remembered contact, showing that individually valid
goals need coherent routine intention across action boundaries. Third, after a
visible Shield condition reduced every Magic Missile dart to zero, the typed
outcome model still predicted ordinary missile damage and recommended the same
spell again. Codex selected Burning Hands instead and dealt real damage, but
both direct and autonomous controllers require the same condition-aware model.

Movement remains the largest measured hot-path outlier. The accepted spacing
move took `69.541 ms` at the hot command surface, including `66.902 ms` in the
runtime command path, while policy result handling took `0.019 ms`. The four
issues are anchored to exact cursors, epochs, and command ids in V171. The next
slice adds focused regressions before changing policy or engine output; the
architecture remains one subjective event-first stack with no legacy
controller branch.

### Typed Save, Protection, And Spatial-Intention Repair V172

The V171 findings were repaired at their owning layers rather than by policy
name checks or selector ordering. `SpellAction.resolve_saving_throw()` now owns
the child save and synchronizes its roll, bonus, DC, ability, and result onto
the parent spell event. Hold Person and Hold Monster use that path, and a
successful initial save reports only that the target saved; empty
concentration cleanup remains authoritative after the action.

Damage effects can now disclose a stable `effect_id`. Active conditions can
declare typed outcome protections against those identities, and visible entity
facts project the protections together with their source condition type.
Remembered contacts discard them with every other live defense. Magic
Missile's dart effect and Shield's protection use this contract in both engine
damage handling and subjective outcome estimation. A matching visible
protection yields an exact guaranteed-zero distribution and blocker evidence;
fully nullified recipients no longer earn effective hostile-coverage utility.
The renamed-spell regression proves the rule has no display-name dependency.

Accepted spacing movement now stages a typed same-turn
`MaintainMinimumDistanceIntention`. `PolicyHost` commits it only after an
accepted command, refreshes the target from visible or remembered subjective
facts, constrains later voluntary movement before arbitration, and expires the
intent on turn transition, death, knowledge loss, or explicit invalidation.
Rejected and stale commands commit nothing. This is actor/session/policy memory
shared by direct Codex and external AI, not a new controller branch.

V172 is
`evidence/runs/20260715-rotation-5-shield-spacing-save-replay-v172.json`.
It replayed `darkness_reveal_labyrinth` with seed `2026071552`. All `18/18`
commands were accepted, the subjectivity audit passed, and the encounter ended
in round 1 with all three monster combatants surviving. After the Reveal Mage
accepted ranged spacing, the next same-turn epoch retained a four-cell floor
and selected `hold_ranged_spacing`; it did not reverse into exploration. This
seed did not trigger defensive Shield, so the replay is evidence for spatial
intent and general integration only. Shield is instead proven end to end by
the renamed engine spell, visible-to-remembered projection, action transport,
and typed policy-outcome regressions.

V172 local-decision p95/max was `5.112/5.112 ms`; frame fetch was
`28.974/28.974 ms`, frame application `17.649/17.649 ms`, and total command
processing `111.635/111.635 ms`. Focused verification passed: action semantics
`23 passed`, typed policy `50 passed`, observation projection `28 passed`,
spell families `46 passed`, runtime performance `10 passed`, external AI
`5 passed`, hot Codex runtime `14 passed`, seamless runtime `25 passed`, and
source/test Pyright reported zero errors. Policy-host behavior passed `28` tests;
its one stale exact-trace fixture remains separately documented in
`KNOWN_ISSUES.md` because it omits the established `ConditionalTargetEffects`
trace node.

## 2026-07-15 - Rotation 5 Slot 3: Direct Monsters Against The Barbarian V173

The immutable direct artifact is
`evidence/direct_codex_runs/20260715-rotation-5-03-codex-monsters-vs-ai-barbarian-caster-crossfire-v173.json`.
Codex controlled the Guard, Archer, and Mage in `caster_crossfire`; the
Barbarian used the shared external policy. The retained evidence contains 147
subjective frames, 78 correlated agent events, twelve accepted direct
commands, and one latency annotation.

The Mage opened with Greater Invisibility, used a level-3 Magic Missile, and
moved to a ranged-spacing floor. On its next turn it used another level-3
Magic Missile, drank a Haste Potion, and spent the added action on a level-2
Magic Missile that killed the Barbarian. The Guard attacked and missed; the
Archer attacked and then moved to spacing. Both ranged actors subsequently
selected `hold_ranged_spacing`, so the V172 same-turn intention prevented the
backtracking regression under direct control as well as autonomous replay.
The monster side won in round 2.

Command latency remains outside the project target. The opening item command
took `53.736 ms` locally and `47.241 ms` inside `SubjectiveRuntime`; the server
spent `10.219 ms` rebuilding its follow-up epoch. A later end-turn handoff
spent `12.626 ms` building the next Codex epoch. Policy reads remained around
`1.7-4.8 ms`, retaining transport, event projection, and epoch publication as
the measured optimization surfaces.

## 2026-07-15 - Rotation 5 Slot 4: Direct Skeletons Against The Sorcerer V174-V175

The first diagnostic artifact is
`evidence/direct_codex_runs/20260715-rotation-5-04-diagnostic-ai-sorcerer-opening-wipe-v174.json`.
In `standard_skeleton_doors`, the external Sorcerer killed all three skeletons
before Codex received a turn. This initially resembled hidden-position
leakage, but the retained subjective evidence cleared that suspicion. The
Sorcerer first moved to a disclosed subjective frontier with no visible enemy,
then saw only the Archer and Warlock, used Quickened Spell, and cast two
Fireballs. The unseen Warrior died as physical area collateral and never
appeared in the policy's affected-target evidence. Subjectivity and the chosen
videogame action economy were both correct.

The meaningful replay is
`evidence/direct_codex_runs/20260715-rotation-5-04-codex-skeletons-vs-ai-sorcerer-anti-aoe-v175.json`.
It used `skeleton_anti_aoe_split` so Codex received a real turn after the
Sorcerer's opening Scorching Ray. The Warrior executed a typed move-then-attack
routine from `(2, 2)` to `(6, 6)`, revalidated the target, and attacked. The
Archer's attack triggered Shield; the following epoch exposed the exact typed
protection `dnd.spells.abjuration.ShieldBuff.magic_missile`, blocking
`dnd.spells.evocation.MagicMissile.damage`. The Archer then held its seven-cell
spacing floor. The Sorcerer won in round 2.

V175 retains 83 subjective frames, 34 agent events, five accepted direct
commands, and one latency annotation. The accepted movement took `52.321 ms`
locally and `49.847 ms` in `SubjectiveRuntime`; the later end-turn handoff took
`59.423 ms`. Local policy reads remained around `3.3 ms`, again separating
decision quality from command-lifecycle cost.

## 2026-07-15 - Rotation 5 Slots 5-6: Autonomous Condition And Reaction Arenas V176-V178

V176 is
`evidence/runs/20260715-rotation-5-05-ai-vs-ai-barbarian-condition-sanctum-v176.json`.
It replayed `condition_lock_sanctum` with seed `2026071555`. All `19/19`
commands were accepted, the subjectivity audit passed, and the control team
defeated the Barbarian in round 2. Local-decision p95 was `10.404 ms`, frame
fetch p95 `61.508 ms`, and total command p95 `131.508 ms`, so this arena
preserved both condition-pressure evidence and a serious runtime regression.

V177 is the pre-repair Counterspell evidence at
`evidence/runs/20260715-rotation-5-06-ai-vs-ai-sorcerer-counterspell-lab-v177.json`.
It completed `reaction_counterspell_lab` with seed `2026071556`, passed the
subjectivity audit, and ended in round 2. Its command summary was `30 accepted,
3 rejected`; every rejection was actually a legal spell canceled by
Counterspell after engine execution had begun. The controller protocol had
collapsed command admission and gameplay resolution into one boolean, while
the external agents compensated with message parsing and ordered spell
suppression. This was an architectural defect, not a tactical corner case.

The protocol now represents the two dimensions independently. A legal epoch
row is `accepted` once admitted by the controller boundary. Its gameplay
resolution is separately `completed` or `canceled`, and the engine supplies a
stable outcome code. Counterspell emits `spell.counterspell.interrupted`; an
accepted cancellation publishes an `action_canceled` epoch and does not commit
routine, transformation, or spacing memory. Invalid rows and stale epochs
remain rejected or stale and cannot mutate engine state. The external agent
and self-play runner no longer infer Counterspell from display text or suppress
the spell category through a special rejection branch.

V178 is the exact-seed repaired replay at
`evidence/runs/20260715-rotation-5-06-ai-vs-ai-sorcerer-counterspell-lab-v178.json`.
All `11/11` commands were protocol-accepted, the subjectivity audit passed, and
both interrupted casts were retained as `accepted + canceled` with the typed
Counterspell outcome. The Sorcerer side won in round 2. Local-decision p95 was
`4.742 ms`, frame fetch p95 `27.600 ms`, and total command p95 `129.855 ms`.
The replay also made an independent engine rules defect explicit: the second
Counterspell used a level-2 slot. Caster cost consumption, cantrip handling,
minimum Counterspell slot level, cancellation logging, and duplicate cancel
history are documented separately in `KNOWN_ISSUES.md`; they were not hidden
inside the controller-protocol repair.

Focused verification passed: seamless subjective runtime `25 passed`,
external AI `5 passed`, run artifacts `6 passed`, hot Codex runtime `14
passed`, the Counterspell self-play and canceled-memory regressions passed, and
touched source/test Pyright reported zero errors.

### Counterspell Engine Contract And Typed Evidence V179-V180

The protocol repair exposed a deeper engine boundary: execution-phase
interruption had been treated like declaration rejection. Counterspell
therefore canceled the effect but returned before the caster paid its action
or selected spell slot. It also ignored cantrips, could spend an illegal
level-1 or level-2 reaction slot, and registered the same canceled event object
twice. These were engine and event-history defects, not policy behavior.

Cancellation now records the phase from which it occurred. Declaration
cancellation remains cost-free, while an execution-interrupted `SpellAction`
settles its serialized action and exact selected-slot costs once. Counterspell
accepts cantrips, searches reaction slots from level 3 upward, and emits a
typed `CounterspellReactionEvent`. Its subjectivity-filtered
`SPELL_INTERRUPTION` log records success or failure, spell level, selected
slot, check, and DC. The command result carries the stable
`spell.counterspell.interrupted` outcome but only the generic message `The
spell was interrupted.`; a hidden reactor's identity is disclosed solely to
authorized perceivers through the event/log projection.

EventQueue identity is now explicit. Re-registering the exact stored event
object is idempotent. A distinct handler-produced event version with the same
UUID receives a fresh UUID and timestamp while retaining lineage, so handler
`model_copy()` mutations remain observable without corrupting cursor history.
The live replication fixtures consequently record unique event versions at
cursors `42/68`, while preserving the same 26-event attack delta.

V179 is
`evidence/runs/20260715-counterspell-engine-contract-replay-v179.json`. It
replayed `reaction_counterspell_lab` with seed `2026071556`: all `26/26`
commands were accepted, the subjectivity audit passed, both Counterspells were
typed accepted cancellations, and the encounter ended in round 2. V179 was
mechanically correct but its action traces lacked the typed pre-command
economy needed to prove resource transitions from retained evidence alone.

V180 is
`evidence/runs/20260715-counterspell-typed-economy-replay-v180.json`. The
trace schema now includes the actor's exact `ActionEconomyState` from each
decision epoch. Before the interrupted level-3 Fireball, the Sorcerer had one
action and two level-3 slots; the following same-turn epoch had zero actions
and one level-3 slot. Before the interrupted level-2 Magic Missile, it had one
action and three level-2 slots; the next epoch had zero actions and two slots.
The replay again accepted `26/26` commands, passed subjectivity, and reproduced
the round-2 outcome.

V180 local-decision p95/max was `3.500/4.558 ms`, meeting the current local
stage target in this run. Frame fetch was `25.736/41.877 ms`, frame application
`13.849/22.853 ms`, command HTTP `44.922/60.852 ms`, and total command p95/max
`79.084/127.702 ms`. The remaining speed problem is therefore the transport,
projection, and command lifecycle rather than policy selection.

Focused verification passed: Counterspell engine contracts `8 passed`, event
lifecycle `13 passed`, spell families `46 passed`, subjective observation `28
passed`, live replication `8 passed`, seamless runtime `25 passed`, run
artifacts `6 passed`, and touched source/test Pyright reported zero errors. The
unrelated exhausted forced-movement iterator remains documented in
`KNOWN_ISSUES.md`.

## 2026-07-15 - Rotation 6 Slot 1: Direct Barbarian At The Trap Lever V181-V183

V181 is
`evidence/direct_codex_runs/20260715-rotation-6-01-codex-barbarian-vs-ai-trap-lever-v181.json`.
Direct Codex controlled the Barbarian in `trap_lever_killzone` while the
opposing side used the shared external policy. All `16/16` commands were
accepted. The artifact retains 146 subjective frames, 102 correlated agent
events, and six cursor-anchored findings.

This match exercised a noncombat object as part of the tactical route. The
Barbarian approached and pulled the lever, crossed the deactivated hazard
region, reached the enemy group, and used Reckless Attack before the killing
follow-up. The run exposed four distinct contract problems. A movement combat
log disclosed an enemy's final destination after visual contact had been lost,
while the remembered entity fact correctly retained its last perceived
position. The distant lever exposed generic usability but not the typed
hazard-deactivation effect needed to plan toward it. After use, the local
object charge and hazard topology remained stale. Finally, the shared policy
underweighted both zero-cost Reckless Attack and useful next-turn movement
after the current turn's attacks were spent. The longest 35-foot movement
spent `54.757 ms` in the server command route and about `80 ms` through the hot
runtime, with event execution dominating.

The owning layers now carry the missing contracts. Subjective movement logs
retain only steps whose positions were perceived by the session and sanitize
the hidden remainder of their parent movement entry. Item-use and linked tile
mutations project replayable object and spatial patches, including the lever's
remaining charges and removal of the deactivated hazard conditions. The lever
capability and adjacent legal row share the typed semantic identity
`interaction.trap.deactivate`, with an explicit hazard-topology effect. The
shared policy models Reckless Attack as a transient outcome augmentation: it
projects the relevant direct-damage candidates, selects the setup only for
positive marginal value, revalidates after acceptance, and then executes the
improved attack. Exhausted actors with remaining movement now retain a typed
future-capability envelope rather than treating End Turn as the only possible
transition.

The autonomous repair evidence is V182 and V183. V182,
`evidence/runs/20260715-augmentation-envelope-caster-crossfire-v182.json`,
completed `caster_crossfire` in round 2 with `27/27` accepted commands and a
passing zero-violation subjectivity audit. The Barbarian selected Frenzy,
moved, attacked, enabled Reckless Attack, and used the improved Extra Attack;
the enemy Mage used Greater Invisibility, Magic Missile, a Haste Potion, and
the added action through the same typed policy. Local-decision p95/max was
`3.047/3.307 ms`; command-HTTP p95/max remained `54.633/60.492 ms`.

V183,
`evidence/runs/20260715-augmentation-envelope-trap-lever-v183.json`, replayed
the trap arena through the autonomous path. All `28/28` commands were accepted,
the subjectivity audit passed, and the Barbarian won in round 3 with 46 HP.
It again used Reckless Attack before the corresponding attacks and continued
positioning after pressure actions. Local-decision p95/max was
`1.617/2.375 ms`; command-HTTP p95/max was `60.989/63.884 ms`. These replays
validate the shared augmentation and future-envelope architecture, while the
focused observation tests own the exact hidden-log and lever-state contracts.

## 2026-07-15 - Rotation 6 Slot 2: Direct Sorcerer Dense-Spell Duel V184

V184 is
`evidence/direct_codex_runs/20260715-rotation-6-02-codex-sorcerer-vs-ai-high-level-duel-v184.json`.
Direct Codex controlled the Sorcerer in `high_level_spell_resource_duel`.
All `11/11` commands were accepted; the artifact retains 151 subjective
frames, 76 agent events, and three findings.

The match deliberately stressed a dense spell epoch. The first bounded Codex
read spent `125.548 ms` in shared policy projection over 1,763 legal rows, and
later dense epochs still approached `60 ms`. Compact wire transport had
reduced repeated payload work, but candidate evaluation remained too broad.
The policy also labeled a forced End Turn after Hypnotic Pattern as
`hold_future_tactical_envelope`, even though the actor had no action economy or
movement left. The opposing 13-HP Archmage repeatedly preferred control and
movement over converting its early advantage into damage, extending the duel
to round 5.

The policy context now builds immutable, revision-bound indexes from the typed
subjective facts. Entity ordering, known-HP keys, affected targets, primary
targets, and target geometry are computed once per observation/epoch revision
and reused by damage and control reducers. Equivalent flattened damage and
movement rows are bounded before full proposal construction. An actor with no
meaningful command remaining now reaches the explicit
`TurnLifecycle/EndTurn` branch without fabricated spacing evidence. Focused
dense-policy and runtime-performance tests keep the local stage below the
current 5 ms target on the repaired implementation.

The enemy's control-versus-damage weakness remains an open policy-quality
finding. It should be addressed through typed projected state value and
concentration/control transitions, not by placing a spell-name exception
before the existing behavior tree.

## 2026-07-15 - Rotation 6 Slots 3-4: Future-Capability Envelope Repair V185-V186

V185 is
`evidence/direct_codex_runs/20260715-rotation-6-03-codex-skeletons-vs-ai-barbarian-double-door-v185.json`.
Codex controlled the three skeletons in `double_door_dark_hunt` against the
external Barbarian. The Barbarian won in round 4. All `27/27` direct commands
were accepted, with 338 subjective frames, 176 agent events, and four findings.

Before contact, the Warlock and Archer independently selected remote map-edge
frontiers instead of following the opened corridor or maintaining party
cohesion. That remains a search-objective defect. After contact, the Archer
hit from six cells away, spent its primary action, and was then told to move
adjacent because spacing evaluated its weaker melee fallback as an independent
future capability. The first Guard movement also retained the transport gap:
`37.412 ms` locally and `22.764 ms` on the server, including `15.379 ms` of
action execution and `7.243 ms` of follow-up epoch publication.

V186 is
`evidence/direct_codex_runs/20260715-rotation-6-04-codex-skeletons-vs-ai-sorcerer-anti-aoe-v186.json`.
The Sorcerer won `skeleton_anti_aoe_split` in round 2. All `10/10` commands
were accepted, with 146 subjective frames and 67 agent events. The split
formation caused the opening Scorching Ray to allocate four rays across three
separate skeletons. The Warlock's mixed Necrotic Bless correctly routed Bane
to the non-undead Sorcerer and Bless to all three undead allies, then began
concentrating. Nevertheless, both the Archer after a ranged attack and the
concentrating Warlock after support casting selected a one-cell melee future
envelope. The same defect reproduced across two arenas and two opposing hero
classes.

The repair makes capability choice a separate stage from position scoring.
Future envelopes disclose pressure, preferred and maximum range, persistent
resource cost, and current distance deficit. Dominated envelopes are removed,
then one role-compatible capability is selected deterministically before any
movement or hold row is valued. Geometry can no longer switch the actor's
action family by scoring every movement destination against every fallback.
Telemetry records evaluated, retained, and selected envelope counts, and the
hold replay identity includes the selected capability.

This replay audit also found that Eldritch Blast executed level-scaled force
damage but disclosed no `ActionOutcomeProfile`. The engine action now exports
the same level-scaled d10 attack contract it actually resolves. Replaying the
retained V185 Archer and V186 Archer/Warlock epochs against the repaired policy
selects ranged holds at six or seven cells instead of melee closure. Focused
spellcasting, epoch-contract, typed-policy, routine, policy-host, and runtime
performance tests pass; touched-source Pyright reports zero errors.

The broader catalog audit found nine direct-damage semantic families without
outcome profiles. Immediate damage spells need ordinary typed contracts.
Persistent zones and delayed effects need temporal outcome semantics rather
than invented one-shot damage. The policy also still represents unmodeled,
insufficient-fact, and genuine-zero future pressure as the same numeric zero;
that distinction is the next model boundary.

## 2026-07-15 - Rotation 6 Slots 5-6: Autonomous Kiting And Concentration V187-V189

V187 is
`evidence/runs/20260715-rotation-6-05-ai-vs-ai-barbarian-kiting-ring-v187.json`.
It completed `ranged_loadout_kiting_ring` in round 3. All `26/26` commands were
accepted and the subjectivity audit passed with zero violations. The Barbarian
won with 40 HP; the Archer Captain, Goblin Archer, and Warlock ended at
`0/-1/-9` HP. The Captain attacked twice and held a six-cell ranged floor, and
the Warlock used Necrotic Bless before preserving ranged distance. This is
live evidence for the repaired future-envelope selection. The Goblin Archer
made a more ambiguous trade: it fired at range, moved adjacent, and spent a
newly legal off-hand attack. That was not the old collapse because the movement
immediately enabled a legal command, but its exposure cost is not yet modeled
well enough to decide whether the exchange was sound.

V187 fact-processing p95/max was `0.743/0.928 ms`, policy p95/max was
`1.865/2.092 ms`, and local-decision p95/max was `2.043/2.478 ms`.
Command-HTTP p95/max was `55.720/65.745 ms`, and total-command max was
`76.737 ms`. The local AI is fast; transport, authoritative execution, and
epoch publication are now the isolated performance problem.

V188,
`evidence/runs/20260715-rotation-6-06-ai-vs-ai-sorcerer-concentration-crossroads-v188.json`,
is a valid but tactically shallow diagnostic. Quickened Spell followed by two
Fireballs ended `concentration_control_crossroads` in round 1 before the enemy
side acted. All `3/3` commands were accepted and subjectivity passed, but this
could not validate concentration behavior and therefore did not satisfy the
rotation slot by itself.

V189 is the replacement evidence at
`evidence/runs/20260715-rotation-6-06-ai-vs-ai-sorcerer-barbarian-duel-v189.json`.
The Sorcerer used Quickened Spell, landed Hold Person, retained concentration,
and allocated all four level-3 Scorching Ray attacks to the paralyzed
Barbarian. On round 2 it kept Hold Person instead of replacing concentration,
used Quickened Spell again, and killed the Barbarian with another four-ray
cast. The duel ended in round 2 with the Sorcerer at 37 HP and the Barbarian at
`-4` HP. All `7/7` commands were accepted and the subjectivity audit passed.
Local-decision p95/max was `2.552/2.552 ms`; command-HTTP p95/max was
`31.421/31.421 ms`.

Rotation 6 is complete as retained evidence, but it is not the first clean
rotation for the completion criterion. Slots 3 and 4 discovered the
future-capability collapse, and the repair landed only after those games. The
clean-rotation counter therefore remains at zero. The next rotation starts
from the repaired capability/outcome boundary and must cover all six slots
without leaks, hangs, polling, memory contamination, unexplained local-stage
latency, or a new architectural regression.

## 2026-07-15 - Rotation 7 And Bounded Routine Exhaustion V190-V197

Rotation 7 exercised all six required controller and character positions.
V190 retained direct Codex Barbarian play in `guardian_zone_shrine`; V192 is
the clean direct Codex Sorcerer replacement in the missile-allocation arena;
V193 retained direct Codex monsters against the external Barbarian in
`trap_lever_killzone`; and V194 retained direct Codex monsters against the
external Sorcerer in `darkness_reveal_labyrinth`. The direct artifacts remain
the evidence for the LLM operator surface, cursor-fenced local queries,
subjective observations, typed action allocation, and correlated agent
telemetry.

The V194 follow-up replay exposed a routine lifecycle defect. An accepted
`EnableThenAct` move predicted a damage row at the next epoch. When the server
did not issue that row, revalidation erased the accepted progress. The routine
registry then treated the same turn as a fresh start and proposed the inverse
movement. This was not a pathfinding error or a tactical scoring exception.
The formal routine omitted the `reassess` state used by the other multi-epoch
routines, so it forgot that its one permitted enabler had already been
consumed.

The shared policy now declares `enable -> reassess -> act` and represents a
disproven accepted enabler as `RoutineRevalidationStatus.EXHAUSTED`. Exhausted
progress remains actor-, session-, target-, and turn-scoped. Other behavior
tree branches continue to compete normally, while the same routine cannot
restart until its scope expires. A host-level regression reproduces an
accepted move, an absent fresh attack row, and a legal reverse endpoint. It
proves the policy ends or selects another branch, retains the exhausted
progress, and permits a new routine only after the turn changes.

V195 is
`evidence/runs/20260715-rotation-7-05-ai-vs-ai-barbarian-kiting-ring-v195.json`.
It completed `ranged_loadout_kiting_ring` in round 3 with `35/35` accepted
commands and a zero-violation subjectivity audit. The Barbarian won with 29 HP.
Frenzy and Reckless Attack preceded their attacks, ranged actors used their
stronger envelopes, and the trace contains no immediate position reversal.
Policy p95/max was `2.824/3.663 ms`.

V196 is
`evidence/runs/20260715-rotation-7-06-ai-vs-ai-sorcerer-barbarian-duel-v196.json`.
It completed the duel in round 2 with `7/7` accepted commands and a passing
subjectivity audit. The Sorcerer retained Hold Person concentration across the
round boundary and allocated all four level-3 Scorching Ray attacks to the
paralyzed Barbarian. Policy p95/max was `1.919/1.919 ms`.

V197 is
`evidence/runs/20260715-bounded-routine-exhaustion-darkness-replay-v197.json`.
It completed `darkness_reveal_labyrinth` in round 2 with `31/31` accepted
commands and zero subjectivity violations. The trace contains two explicit
`EXHAUSTED` revalidations. After an enabling move, the Shadow Mage selected a
stronger legal Fireball from the ordinary pressure branch. The retained
single-target routine then exhausted, allowed one future-envelope movement,
and ended the turn without restarting or reversing. Policy p95/max was
`2.807/3.891 ms`.

Focused verification passed: policy host `37 passed`, policy routines `13
passed`, retained runtime performance `13 passed`, and touched-source Pyright
reported zero errors. Rotation 7 is complete, but it does not increment the
clean-rotation counter because the routine lifecycle defect was discovered
and repaired after slot 4. Rotation 8 starts from shared-policy version
`2026-07-15.shared-policy-v29-bounded-routine-exhaustion` with the clean count
still at zero.

## 2026-07-15 - Rotation 8 And Committed Metamagic Cancellation V198-V205

Rotation 8 exercised all six controller positions and found one engine
lifecycle defect during direct Sorcerer play. V198 retained the direct Codex
Barbarian in `condition_lock_sanctum`. The Barbarian used Frenzy, an explicit
Reckless Attack override, and both weapon attacks to remove the guard. Hold
Person then exposed an action-economy-bounded paralyzed turn, and the support
caster finished the Barbarian in round 2. All `8/8` controller commands were
accepted.

V199 is the immutable diagnostic from the first direct Codex Sorcerer attempt
in `reaction_counterspell_lab`. Quickened Spell rewrote the next spell to use a
bonus action, and Counterspell canceled that Fireball from the execution phase.
The committed cast correctly spent the bonus action and spell slot, but
`MetamagicActive` remained applied. Every spell template therefore remained
rewritten to the already-spent bonus action while the caster still had one
normal action. The authoritative epoch contained no affordable damage spell.

The defect was an event-boundary mismatch. `MetamagicActive` consumed itself on
`CAST_SPELL/EFFECT`, but an execution-canceled spell never reaches EFFECT. The
condition now also observes `CAST_SPELL/CANCEL` and removes itself only when
`canceled_from_phase` is `EXECUTION`. Declaration-time validation failures keep
the pending metamagic. Cleanup still flows through condition-removal events and
the condition continues to own template restoration; Counterspell has no
Sorcerer-specific cleanup. The focused regression failed on the retained state
before the repair and then passed. The complete Counterspell file reports `9
passed`, the existing successful Quickened-cast cleanup test passes, and
touched-source Pyright reports zero errors.

V200 is the clean slot-2 replacement. In each of two rounds, the Sorcerer used
Quickened Spell, had the first spell canceled by Counterspell, immediately
received normal-action spell affordances after cleanup, and resolved the second
spell after the enemy reaction was spent. All `8/8` commands were accepted;
the artifact retains `103` subjective frames and `53` agent events.

V201 retained policy-guided direct Codex control of the monster faction in
`guardian_choke_body_block`. The side used Greater Invisibility, bounded
enabling movement, upcast Magic Missile, weapon attacks, Haste, and a final
spell. All `15/15` commands were accepted, policy decisions stayed below `3.6
ms`, and no enabling routine restarted or reversed.

V202 records an unsuitable first slot-4 arena rather than hiding it. The shared
AI Sorcerer in `multi_projectile_no_aoe_lab` allocated its opening Magic Missile
across all three pre-wounded monsters and killed the claimed side before it
received an epoch. The terminal snapshot and two runtime events are retained,
but the run does not satisfy the slot. V203 is the replacement in
`line_aoe_corridor`: one 3 HP guard survived the opening line spell, received a
subjective epoch, advanced `EnableThenAct` from movement to a legal melee row,
attacked, and ended without reversal. All `3/3` commands were accepted.

V204 completed autonomous `condition_lock_sanctum` in round 2 with `23/23`
accepted commands and a zero-violation subjectivity audit. The monster
controller retained Hold Person concentration, used Haste's extra action, and
completed a Quickened Fire Bolt sequence. Policy p95/max was
`3.415/3.430 ms`.

V205 completed autonomous `reaction_counterspell_lab` in round 2 with `19/19`
accepted commands and a passing subjectivity audit. It independently exercised
the repaired lifecycle twice: an interrupted Fireball was followed by
Quickened Spell and a successful Fireball, then an interrupted Magic Missile
was followed by Quickened Spell and a successful Magic Missile. Every policy
decision was below `4.1 ms`; the Sorcerer killed the guard but lost to the two
remaining casters.

Rotation 8 is complete as diagnostic evidence but does not increment the clean
rotation counter because V199 found and repaired the committed-cast metamagic
defect. Rotation 9 starts after that repair with the clean count still at zero.

## 2026-07-15 - Rotation 9 And Traversed-Movement Event Truth V206-V212

Rotation 9 exercised all six required controller positions and exposed one
event-contract defect during direct Barbarian play. V206 retained the direct
Codex Barbarian in `forced_movement_hazard_bridge`. The hot runtime accepted
all `25/25` commands and retained 278 subjective frames plus 160 agent events.
The Barbarian killed the initially visible Warlock, explored from unknown
frontier facts, pursued only the Mage's last-known position after contact was
lost, then finished the Mage and Archer through Frenzy, Reckless Attack,
Frenzied Strike, and Extra Attack. It won at 2 HP without a stale command,
poll, resync, or objective-state query.

One partial move revealed that authoritative position and economy could be
correct while the completed event remained false. The Barbarian requested a
six-step route, traversed three cells, discovered an objective collision on
step four, stopped at `(3, 6)`, and correctly spent 15 feet. The parent
`MovementEvent` nevertheless retained the requested path through `(6, 9)` and
its 30-foot cost. Besides producing a false compact and typed combat log, that
untraversed tail could reach another observer whenever all actual step logs
were perceived and the projector therefore retained the parent summary.

`Move._apply()` now constructs completion data from successful step events:
the traversed path, actual end position, and terrain-adjusted traversed cost.
Partial and complete movement both advance from the EFFECT event using that
truthful payload. The collision remains a separate spatial event. The focused
regression first reproduced the stale tail while position and economy passed;
after the repair it proves the event path, affected positions, structured log,
cost, child count, and compact distance contain only the three completed
steps. The complete action-discovery file reports `12 passed`, the existing
subjective partial-observation projection test passes, and `dnd/actions.py`
reports zero Pyright errors.

V207 retained the direct Codex Sorcerer in
`multi_target_missile_allocation`. Codex used the typed allocation contract to
send repeated Magic Missile darts to the 6-HP Goblin while assigning another
dart to the Archer. After Quickened Spell, it issued a second mixed allocation.
On round 2 the shared policy independently selected a five-dart level-3 row:
one dart for the 2-HP Archer and four for the 13-HP Warrior. All `6/6` commands
were accepted and the artifact retains 72 frames and 40 agent events.

V208 retained policy-guided Codex control of all three monsters in
`trap_lever_killzone` against the autonomous Barbarian. The Warlock, Guard,
and Archer switched through one participant stream and used Necrotic Bless,
melee pressure, jump, ranged pressure, and movement. All `9/9` commands were
accepted and every observed policy decision stayed below 2 ms.

V209 retained policy-guided Codex monsters in
`darkness_reveal_labyrinth` against the autonomous Sorcerer. The side used
Daylight as an information action, jumped to and opened a door, moved through
the new topology, then composed ranged pressure, Greater Invisibility,
Fireball, Magic Missile, and Fire Bolt across all three controlled actors. All
`21/21` commands were accepted and every observed policy decision stayed below
3 ms. The artifact retains 264 frames and 135 agent events.

V210 completed autonomous `sorcerer_barbarian_duel` in round 2 with `18/18`
accepted commands and a zero-violation subjectivity audit. Policy p95/max was
`3.212/3.212 ms`, and local-decision p95/max was `3.657/3.657 ms`.

V211 retained an unsuitable first autonomous Sorcerer slot rather than hiding
it. The Sorcerer ended `concentration_control_crossroads` in three accepted
commands before the opposing faction selected an action. Subjectivity passed,
but the run did not satisfy the two-sided slot. V212 is the replacement in
`skeleton_anti_aoe_split`: it ran for three rounds, represented both factions
and four actors, accepted all `18/18` commands, and passed the subjectivity
audit. Policy p95/max was `3.167/3.167 ms`; local-decision p95/max was
`4.359/4.359 ms`.

The fresh-process replay check initially compared item-bound template labels,
whose required `__item_<uuid>` suffix changes with object allocation. The two
processes had identical 22-command decisions, rounds, outcomes, and final HP;
only the embedded Haste Potion UUID differed. The semantic replay contract now
compares the existing stable `semantic_key`, and the cross-process check passes.

Rotation 9 is complete as diagnostic evidence but does not increment the clean
rotation counter because V206 found and repaired the traversed-movement event
defect. The dashboard now projects 128 immutable artifacts: 80 autonomous runs
and 48 direct Codex runs. Rotation 10 starts from the repaired event boundary
with the clean count still at zero.

## 2026-07-15 - Rotation 10 And Subjective Topology Workspace V213-V218

Rotation 10 completed all six controller positions without a hidden-state
violation, rejected command, stale epoch, or gameplay correctness defect. It
nevertheless remains diagnostic evidence because two dense direct decisions
exceeded the local five-millisecond target.

V213 retained the direct Codex Barbarian in `zone_control_web_gauntlet`. All
`12/12` commands were accepted across Frenzy, movement, and weapon pressure;
the run retained 158 subjective frames and 77 agent events and ended without
interface friction. Maximum observed policy time was `3.513 ms`.

V214 retained the direct Codex Sorcerer in `arcane_device_control`. Fireball,
Quickened Spell, and Magic Missile ended the encounter in `6/6` accepted
commands. The stronger legal spell pressure correctly outranked the cannon,
but the first cold dense epoch took `5.161 ms` locally. The artifact records
that latency regression rather than treating the terminal outcome as success.

V215 retained policy-guided Codex control of the monster faction in
`teleport_escape_skirmish`. The Guard, Goblin, and Mage switched cleanly through
one participant stream and used ranged and melee pressure, Greater
Invisibility, Magic Missile, and Haste. All `16/16` commands were accepted and
maximum observed policy time was `3.518 ms`.

V216 retained policy-guided Codex monsters in
`high_level_spell_resource_duel`. The claimed side used Hypnotic Pattern,
invisibility and haste potions, Magic Missile, and future-envelope movement;
all `14/14` commands were accepted. One Archmage movement epoch contained 253
legal rows, including 247 position rows and 48 future capabilities. Its policy
selected `position|Move|pos=13,10` after evaluating 224 voluntary movement rows,
but the local decision took `5.808 ms`.

V217 completed autonomous `caster_crossfire` in round 2 with `28/28` accepted
commands, three represented actors, both factions acting, and a zero-violation
subjectivity audit. Fact derivation p95/max was `0.860/1.356 ms`, policy was
`2.827/2.893 ms`, and the complete local decision was `3.329/3.495 ms`.

V218 completed autonomous `darkness_reveal_labyrinth` in round 2 with `31/31`
accepted commands, four represented actors, both factions acting, and a passing
subjectivity audit. Fact derivation p95/max was `2.493/2.711 ms`, policy was
`2.718/2.929 ms`, and local decision p95/max was `4.997/5.142 ms`. The separately
measured HTTP/SSE transport remained outside the local policy-stage contract.

The retained V216 epoch made the local defect reproducible. Before repair, 101
fresh decisions preserved the same tactical output but measured `5.337 ms`
median. Profiling attributed about 97 percent of decision CPU to candidate
construction: every hypothetical movement origin repeatedly string-keyed the
same subjective tiles, scanned the same visible blocker objects, and recomputed
shared cardinal and diagonal transitions while preserving the engine's
supercover line rule.

`KnownLineOfSightWorkspace` now derives one decision-local index from the
session-subjective world and typed visible-blocker facts. It memoizes only
directional transition results for that world revision. It neither imports
objective map state nor changes LOS, legality, endpoint coverage, scoring, or
selection. The retained regression freezes the complete policy-decision hash,
selected row, 224 evaluated movement rows, 200 applicable rows, 149 rows
represented by the winning risk class, 12 capability-target envelopes, and
four non-dominated envelopes. After repair, 201 decisions measured `2.740 ms`
median, `2.983 ms` p95, `3.373 ms` p99, and `4.174 ms` maximum.

Focused verification reports: retained runtime performance `14 passed`, typed
policy `82 passed`, policy host plus routines `50 passed`, and touched-source
Pyright zero errors. Rotation 10 does not increment the clean-rotation counter
because the latency defect was found and repaired after its evidence was
captured. Rotation 11 begins with the clean count still at zero.

## 2026-07-16 - Rotation 11 And Counterspell Allegiance V219-V224

Before the six-slot rotation, a retained Barbarian replay exposed an error in
transient-augmentation valuation: Reckless Attack received credit for only one
weapon attack even when the actor still owned a matching Extra Attack. The
shared routine now adds the marginal utility of every typed, matching
attack-slot capability while charging the turn-wide incoming-advantage
exposure once. The focused regression proves the additional attack contributes
to the same inspectable proposal without forcing Reckless at low health.

V219 retained the direct Codex Barbarian in `condition_lock_sanctum`. Codex
used Frenzy, movement, Reckless Attack, and both available attacks in `6/6`
accepted commands. The opposing side then dealt 65 damage and ended the match
in round 1. The artifact records first-contact opponent-capability uncertainty
as policy friction rather than claiming the recommendation was objectively
wrong.

V220 retained the direct Codex Sorcerer in `reaction_counterspell_lab`. The
first Fireball was interrupted, Quickened Spell enabled a second Fireball, and
the second cast killed the Guard while wounding both casters. During the enemy
turn, the Counterspell Abjurer then interrupted the allied Shield Mage's
Shatter. The retained subjective combat log anchored the defect at observation
cursor 42.

The Counterspell processor checked visibility, range, reactions, and slots but
never faction allegiance. A focused red test reproduced the allied
interruption. `entity.is_enemy(spell_caster)` now gates the reaction before any
resource is spent. The full Counterspell contract reports `10 passed`, and an
exact live replay preserved enemy Counterspell while allowing the allied spell
to resolve without interference.

V221 retained direct Codex control of the monster side in
`trap_lever_killzone` against the autonomous Barbarian. The side used melee
pressure, Necrotic Bless, movement, Jump, Burning Hands, and ranged pressure;
all `14/14` commands were accepted. The Barbarian won in round 3. The Trap
Lever's typed semantics correctly identified it as hazard deactivation, so the
monster side did not spend its action disabling its own killzone.

V222 retained direct Codex monsters in `skeleton_anti_aoe_split` against the
autonomous Sorcerer. Necrotic Bless used one typed four-target allocation:
Bane against the hostile Sorcerer and Bless for the Warlock, Archer, and
Warrior. Concentration cleanup removed all linked effects when the Warlock
died. All `9/9` commands were accepted; the Sorcerer won in round 3 at 19 HP.

The direct Sorcerer-side slot first attempted `line_aoe_corridor`, but repeated
openings ended the encounter before a monster decision epoch existed. Those
outcomes are valid AoE-policy evidence but cannot exercise direct-controller
UX, so V222 used the spread arena and the corridor remained in the autonomous
slot.

V223 completed autonomous `condition_lock_sanctum` in round 1 with `17/17`
accepted commands, zero rejected/stale/error results, and a passing
subjectivity audit. The Barbarian reached 0 HP while all three opponents
survived.

V224 completed autonomous `line_aoe_corridor` in round 1 with `3/3` accepted
commands, zero rejected/stale/error results, and a passing subjectivity audit.
The Sorcerer remained at full health and the spread includes the intentionally
off-line Goblin, proving the result came from legal disclosed AoE rows rather
than hidden target injection.

The JSON-driven dashboard now projects 204 immutable artifacts. Focused
verification reports: dashboard projection `5 passed`, direct artifact
contracts `8 passed`, autonomous artifact contracts `6 passed`, Counterspell
engine contracts `10 passed`, and JSON validation succeeded.

Rotation 11 is diagnostic evidence and does not increment the clean-rotation
counter because the Counterspell allegiance defect was repaired after V220.
Rotation 12 begins from the repaired faction boundary with the clean count at
zero.

## 2026-07-16 - Rotation 12 And Damage-Ending Control Semantics V225-V232

Rotation 12 completed all six controller positions through the subjective hot
runtime and retained every result. It found one shared-policy defect, so the
clean-rotation counter remains zero.

V225 retained direct Codex Barbarian play in
`forced_movement_hazard_bridge`. The Barbarian used Frenzy, Reckless Attack,
weapon pressure, and safe partial movement, suppressed Reckless at low HP, and
lost in round 3. All commands flowed through the local subjective world and
server-issued epochs; the artifact retains 188 frames and 107 agent events.

V226 retained direct Codex Sorcerer play in
`high_level_spell_resource_duel`. Fireball removed the Skirmisher, Quickened
Spell plus Hypnotic Pattern controlled the Guard and Archmage, and focused
Scorching Ray and Magic Missile pressure preserved control on the second
target. The Sorcerer won in round 3 at 65 HP. Manual policy review found that
the shared repeatable-damage allocator would instead spread damage over both
controlled targets because damage carried no cost for restoring enemy agency.

V227 retained direct Codex control of the monster faction in
`ranged_loadout_kiting_ring` against the autonomous Barbarian. The Captain used
Haste and ranged attacks, the Warlock allocated Necrotic Bless by typed target
relationship, and the Goblin kited. The Barbarian won in round 3. The retained
spacing recommendation also records that one proposed Captain move remained
adjacent rather than creating useful separation; this remains evidence for a
later spacing pass rather than being folded into the control repair.

V228 retained direct Codex monsters in
`concentration_control_crossroads` against the autonomous Sorcerer. After the
Guard and Support died to Fireball, the Controller used Quickened Hold Person,
Shield, healing, Haste, and Ray of Frost to recover and win in round 4 at 14
HP. Subjective combat memory observed the blocked Magic Missile episode and
changed effect families without hidden target data.

V229 completed autonomous `ranged_loadout_kiting_ring` with `56/56` accepted
commands, a passing subjectivity audit, and a round-5 Barbarian victory at 15
HP. It independently reproduced the weak adjacent Captain spacing move but did
not expose a gameplay or protocol failure.

V230 completed autonomous `high_level_spell_resource_duel` with `25/25`
accepted commands and a passing subjectivity audit. It reproduced the control
defect three times: the Archmage cast Hypnotic Pattern and then damaged the
same surviving target with Magic Missile during the same turn, immediately
removing its own control. The engine behaved correctly; positive post-
mitigation damage is the rule boundary that removes Hypnotic Pattern, Sleep,
and Eyebite's asleep option. The missing concept was entirely in shared policy
truth and valuation.

The repair adds engine-owned `ConditionRemovalTrigger` and
`ConditionAgencyDenial` annotations to complete conditions. Hypnotic Pattern,
Sleep, and Eyebite Asleep declare positive applied damage as their removal
trigger and full-turn agency denial as their active effect. Conditions and
encounters retain event cursors for their application and current turn-start
boundaries. The subjective projector exposes these typed facts only while the
entity is currently observable, redacts them from remembered contacts, and
preserves exact snapshot-plus-frame replay. A completion-frame race discovered
by the red test was repaired by projecting the authoritative source cursor
directly rather than waiting for object indexing.

Shared damage utility now estimates restored enemy agency as the known healthy
fraction multiplied by the probability of positive damage without defeat. It
charges the same `35 + 20` hard-control value in direct arbitration,
repeat-projectile allocation, and area-damage frontier pruning. Lethal and
guaranteed-zero damage carry no restoration cost. A new behavior-tree proposal
can end the current turn to preserve damage-ending full control established
since the known turn-start event. It values only the retained future-action
denial, so useful non-damaging preparation can still win first, and the
proposal disappears on the caster's next turn rather than producing permanent
inaction.

V231 was the first exact-seed repair replay. It correctly changed the opening
sequence to Hypnotic Pattern, Haste, and `PreserveNewControl`, but retained a
later low-health case where level-one Magic Missile narrowly outranked
preservation. That artifact remains immutable diagnostic evidence. Aligning
the preservation proposal with the existing typed future-action-denial value
resolved the remaining comparison without an identity or spell-name rule.

V232 replayed exact seed `2026071612` under
`2026-07-16.shared-policy-v30-control-preservation`. Both same-turn control
episodes now end with `yield_after_establishing_damage_ending_control`; Haste
still precedes the first yield, and damage becomes eligible again on a later
turn. The encounter ended normally in round 5 with `25/25` accepted commands,
zero stale or rejected results, and a zero-violation subjectivity audit.

Focused verification reports: typed shared policy `95 passed`; subjective
observation `37 passed`; spell-family rules `13 passed`; external self-play
contracts `7 passed`; external AI `5 passed`; subprocess integration `4
passed`; policy host `49 passed` with one documented stale LOS monkeypatch
deselected; Codex takeover `12 passed` with one documented stale executor
monkeypatch deselected; and touched production sources report zero Pyright
errors.

The JSON corpus now contains 212 immutable artifacts: 100 autonomous runs and
112 direct Codex runs. Rotation 12 remains diagnostic because V230 found the
defect. Rotation 13 begins from the typed control-lifecycle boundary with the
clean count still at zero.

## Rotation 13 continuation: ranged spell threat repair and direct monster-side diagnostic

Rotation 13 is not a clean rotation. It remains diagnostic because live play
found a rules/engine defect: ranged spell attacks did not inherit Threatened
disadvantage while the caster was adjacent to a visible hostile. The Sorcerer
direct run in `standard_skeleton_doors` exposed the issue when adjacent
Scorching Ray attacks recorded no disadvantage evidence. The repair moved
ranged-spell threat handling into the shared spell-attack resolution path so
spell attack logs, action profiles, and attack resolution agree.

Focused verification after the repair:

- `tests/manual/test_14_spell_families.py`: `14 passed`.
- `tests/engine_book/test_chapter_15_spell_families.py`: `46 passed`.
- `tests/manual/test_47_direct_codex_artifacts.py`: `8 passed`.
- Touched spell-attack production sources reported zero Pyright errors in the
  repair pass.

V233 completed autonomous `standard_skeleton_doors` from the repaired baseline.
The validation Sorcerer won in round 3 with `17/17` accepted commands, zero
stale, zero rejected, zero errors, and a passing subjectivity audit. This
confirmed that the autonomous epoch-command path still functions after the
spell-attack repair.

V234 completed autonomous `caster_crossfire` with seed `2026071613` and wrote
`ai/evidence/runs/20260716T151257_686349_0000-caster_crossfire-a91fe18a.json`.
The encounter ended in round 2 with `29/29` accepted commands, zero stale, zero
rejected, zero errors, and a passing subjectivity audit. The Validation
Barbarian died at `-7` HP while the Crossfire Archer and Mage survived. This is
not a protocol failure; it reinforces that the crossfire arena is a hard
Barbarian matchup and remains useful pressure for defense, focus-fire, and
opening-turn survival policy.

V235 manually exercised a direct Codex monster-side run in
`double_door_dark_hunt` against the autonomous Validation Door Barbarian. The
run was not persisted as a direct Codex artifact because the initial subjective
snapshot was not captured before the first direct command; this log entry is
therefore diagnostic bookkeeping rather than immutable direct-run evidence.
The command contract behaved correctly:

- The initial monster-side snapshot exposed only controlled monsters and known
  open doors; no Barbarian entity fact was present.
- Exploratory movement toward the door corridor triggered a movement
  revalidation frame when the Barbarian became newly visible, stopping the
  Archer at `(10, 8)` and issuing a follow-up decision epoch.
- The Archer successfully used `Mark Target`, then a ranged attack, and then
  ended turn through epoch-fenced command endpoints.
- The Guard moved adjacent, found no immediate attack row until a later turn,
  used Dodge, and later performed a melee attack when a row became legal.
- The Warlock could see the session-shared hostile fact only through other
  observers and did not receive an actor-specific Eldritch Blast row until it
  had its own line of sight. This supports actor-scoped affordance filtering.
- The Warlock was killed before a second Warlock turn; the Barbarian won after
  killing the remaining monsters.

Friction from V235:

- Direct runs must start the artifact collector before the first command; the
  tooling should make this harder to forget.
- `meaningful_commands_remaining` remained true after action and bonus action
  were spent because movement and utility rows still existed. Policy should
  distinguish "technically legal" from "worth extending this turn".
- The Guard's first adjacent turn exposed no attack row despite standing next
  to the Barbarian; this needs follow-up as either valid content configuration
  or an action-discovery/occupation edge case.
- Multi-target support rows such as `Necrotic Bless (Level 2)` are tagged as
  `target.multi`, but the row-selection surface still feels too primary-target
  oriented for a direct operator. This matches earlier Magic Missile/Necrotic
  Bless friction and remains a UI/protocol clarity issue.
- Server-side command timings in this live path frequently measured roughly
  `10-25 ms`, with movement and epoch rebuild dominating. Functional behavior
  comes first, but the existing timings are enough to guide later profiling.

The JSON corpus after V234 contains 216 immutable artifacts: 102 autonomous
runs and 114 direct Codex runs, before dashboard projection refresh. Rotation
13 remains diagnostic, and the clean count stays at zero.

The V235 evidence gap produced a tooling repair: direct Codex validation now
has a typed starter that starts the validation arena, immediately captures the
session-subjective bootstrap snapshot, and returns a run context before the
operator can issue the first command. Focused verification for the direct
artifact contract reports `10 passed`, and Pyright reports zero errors over the
touched direct-evidence files.

V236 used that starter for a real direct Codex monster-side run in
`skeleton_anti_aoe_split` against the autonomous Validation Blast Sorcerer. The
run wrote
`ai/evidence/direct_codex_runs/20260716T152625_573004_0000-skeleton_anti_aoe_split-direct-codex-6d213bda.json`
with a pre-command subjective snapshot, `129` retained subjective frames, and
three manual friction annotations. The Codex takeover lease was released after
the encounter ended.

V236 behavior summary:

- The AI Sorcerer opened before monster control and damaged all three split
  monsters, leaving the Warlock at `2` HP and both frontliners wounded.
- The Warlock used Eldritch Blast twice from legal actor-specific rows and
  missed both times, then repositioned after the first shot.
- The Warrior had no entity attack from the far split corner, moved toward
  center, and died before producing pressure.
- The Archer used `Mark Target`, then a ranged attack, missed, and later
  attacked again before the encounter ended.
- Subjectivity remained coherent: the artifact is built from the initial
  subjective snapshot, later subjective observation frames, and agent telemetry
  only.

Friction from V236:

- The monster side is extremely fragile against the Sorcerer opening in this
  arena. That is valid pressure, but the enemy policy needs better anti-AoE
  setup, defensive recovery, or first-turn survival valuation.
- The direct operator still has to manually infer multi-target/allocation
  semantics from rows such as `Necrotic Bless`; row presentation should make
  allocation capacity explicit.
- Movement commands again reported server totals in the approximate `20-33 ms`
  range, with movement execution and follow-up epoch rebuild dominating.

The JSON corpus after V236 contains 217 immutable artifacts: 102 autonomous
runs and 115 direct Codex runs. Dashboard projection was refreshed from JSON
only. Rotation 13 remains diagnostic, and the clean count stays at zero.

The V235/V236 multi-target friction produced a direct-interface repair. The
hot Codex turn index now carries a bounded `multi_target_rows` summary inside
the action index. Each summary exposes the row id, display name, semantic
family, primary target, number of selectable target options, total allocation
count, extra target slots, and whether repeated allocation is legal. This does
not replace local detail queries or server legality; it makes the existing
epoch contract legible enough that direct Codex and policy tooling can see
Magic Missile/Necrotic Bless-style allocation capacity before selecting a row.

Focused verification after the repair:

- `tests/manual/test_49_hot_codex_runtime.py`: `17 passed`.
- Pyright over `ai/codex_tools/hot_runtime.py` and
  `tests/manual/test_49_hot_codex_runtime.py`: zero errors.
- `tests/manual/test_47_direct_codex_artifacts.py`: `10 passed`.
- Dashboard projection still reports `217` artifact-backed runs.

## Rotation 14 start: repaired multi-target interface baseline

V237 started the next repaired-baseline replay set with autonomous
`high_level_spell_resource_duel` under seed `2026071614`. The run wrote
`ai/evidence/runs/20260716T153638_567665_0000-high_level_spell_resource_duel-599f9d44.json`.
It ended in round 3 with `13/13` accepted commands, zero stale, zero rejected,
zero errors, and a passing subjectivity audit.

The trace specifically exercised the multi-target/allocation surface that was
just repaired:

- The Sorcerer opened with `Fireball__slot_5`, affecting Guard, Skirmisher, and
  Archmage through the area target profile.
- Quickened Spell into Hold Person remained legal: after the Archmage saved
  against one Hold Person, the Sorcerer spent the remaining action economy on a
  second Hold Person in the same turn and established control.
- The final kill used two Scorching Ray casts on the Archmage. Each retained
  repeated `extra_target_names` for the same visible target, matching the
  repeated-projectile allocation contract.
- The controlled Archmage turns were end-turns because the held actor had no
  meaningful legal commands. This is a rules effect, not a controller hang.

V237 did not expose a protocol failure, hidden-information leak, stale command,
or multi-target allocation bug. It does show that this duel remains lopsided
when the Sorcerer wins opening control and preserves it correctly. That is
acceptable baseline pressure, but enemy recovery/defense against early hard
control remains a design surface for later policy work.

The clean-rotation count is not incremented yet because Rotation 14 is only
partially complete.

V238 continued the repaired-baseline autonomous checks with
`caster_crossfire` under seed `2026071615`. The run wrote
`ai/evidence/runs/20260716T153928_642893_0000-caster_crossfire-d3c04bf8.json`.
It ended in round 2 with `23/23` accepted commands, zero stale, zero rejected,
zero errors, and a passing subjectivity audit. The Crossfire side again killed
the Barbarian, this time with the Mage finishing via `Magic Missile__slot_2`
and the trace reason `allocate_visible_multi_target_damage`.

V238 did not expose a protocol failure. It reinforces two baseline facts:

- The repaired multi-target allocation path is exercised by autonomous policy,
  not only by direct Codex surfaces.
- `caster_crossfire` remains a severe Barbarian survival matchup; this is
  useful pressure for future defensive/opening policy work, but it does not
  block the event-first subjective substrate.

## 2026-07-16 state check after compaction

Two fresh autonomous self-play runs were executed through the current
event-first subjective command path and persisted as JSON artifacts:

- `ai/evidence/runs/20260716-state-check-standard-doors.json`
- `ai/evidence/runs/20260716-state-check-high-level-duel.json`

Both runs completed encounters with a passing subjectivity audit and no stale,
rejected, errored, or missing command results.

`standard_skeleton_doors` under seed `2026071621` ended in round 2 after `10`
accepted commands. The Sorcerer won with `37` HP remaining. The trace confirms
that the policy still uses the repaired repeated-target allocation surface:
`Magic Missile__slot_1` allocated two extra missiles into the Archer, and
`Magic Missile__slot_3` later allocated four extra missiles into the Warrior.
The Skeleton Warrior did reach and attack the Sorcerer once, so the monster
side was not frozen, but it was still strategically outpaced.

`high_level_spell_resource_duel` under seed `2026071622` ended after only `3`
accepted commands. The Sorcerer opened with `Fireball__slot_5`, enabled
`Quickened Spell`, then used `Scorching Ray__slot_4` with four repeated extra
ray allocations into the Archmage. Final HP was Sorcerer `65`, Archmage `0`,
Guard `-9`, Skirmisher `-6`.

Current state:

- The subjective runtime and command protocol are functioning in these checks.
- Multi-target/projectile allocation is visible in artifacts and is being used.
- Subjectivity remains preserved by the artifact audit.
- The major open problem is tactical quality and encounter pressure, not basic
  transport correctness: the Sorcerer policy can wipe many validation fixtures
  before enemy recovery/defense matters.

## 2026-07-16 immediate-defense policy repair

The state-check evidence suggested that enemy survival and defensive arbitration
were weaker than the transport layer. The shared policy already had durable
self-setup scoring, but ordinary defensive rows tagged `DEFENSE_SELF` such as
`Dodge` were not represented as policy candidates unless they also looked like
durable setup. That meant a wounded actor could have a legal defensive row in
the decision epoch and still fail to consider it.

The policy now adds a typed immediate-defense candidate family:

- it consumes only server-issued rows tagged `DEFENSE_SELF`;
- it excludes durable `SETUP_SELF` rows, which remain handled by the existing
  setup branch;
- it requires a direct defensive condition effect, currently
  `actor.condition.dodging`;
- it scores visible hostile pressure and known missing-HP fraction;
- it suppresses repeats when the defensive condition is already observed.

This is deliberately not display-name policy. The first replay exposed an
overcorrection: `Disengage` was also tagged `DEFENSE_SELF`, and the policy used
it as standalone immediate defense. That was wrong because Disengage is useful
as part of a movement/routine plan, not as a terminal defensive action. The
candidate family was tightened to require a direct Dodging-style defensive
condition, leaving Disengage for future movement-aware routine logic.

Focused verification:

- `tests/manual/test_44_typed_agent_policy.py`: `96 passed`.
- Pyright over `ai/policy/candidates.py`: zero errors.

New evidence:

- `ai/evidence/runs/20260716-defense-branch-v2-standard-doors.json`
  completed in `4` accepted commands with subjectivity passed and no command
  errors. No immediate-defense action was selected; the Sorcerer opening still
  wiped the skeleton side, preserving the known alpha-strike pressure issue.
- `ai/evidence/runs/20260716-defense-branch-v2-support-attrition.json`
  completed in `25` accepted commands with subjectivity passed and no command
  errors. `Dodge` appeared as `take_immediate_self_defense`; `Disengage` did
  not appear under that reason.

Open policy note: the support arena still selected Dodge at high HP when three
hostiles were visible and no stronger immediate pressure was available. That is
plausible but not proven optimal. The next architecture-level improvement should
make defensive choices compare explicit incoming-threat estimates, not only
visible-hostile count and HP fraction.

## 2026-07-16 smoke gauntlet gate check

The new gauntlet gate was exercised against a real production smoke run without
writing artifacts:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id standard_skeleton_doors --seed 20260716 --max-commands 80 --no-run-artifacts --no-summary-file --require-gate-pass
```

Result:

- `gate_status`: `passed`
- `gate_reasons`: `[]`
- `status_counts`: `{"encounter_ended": 1}`
- `command_status_counts`: `{"accepted": 4}`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- outcome: heroes
- max command total: `100.329 ms`
- max local decision: `5.046 ms`

This proves the current production self-play stack can satisfy the new
gauntlet gate on the smallest retained smoke surface. It does not satisfy the
larger goal yet: max command time remains far above the long-term interactive
target, and this was only one smoke match rather than a full six-game rotation
or release gauntlet.

## 2026-07-16 six-game rotation gate check

After fixing `rotation` mode to produce exactly the six required schedule rows,
the production stack was exercised through the full rotation gate without
writing artifacts:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode rotation --max-commands 80 --no-run-artifacts --no-summary-file --require-gate-pass
```

Result:

- `gate_status`: `passed`
- `gate_reasons`: `[]`
- `completed_count`: `6`
- `failed_count`: `0`
- `pending_count`: `0`
- `status_counts`: `{"encounter_ended": 6}`
- `command_status_counts`: `{"accepted": 100}`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- outcomes: `{"heroes": 6}`
- average commands: `16.667`
- max match elapsed: `1368.0 ms`
- max command total: `105.536 ms`
- max local decision: `4.663 ms`

Per-match command counts were `11`, `33`, `10`, `24`, `11`, and `11` across
seeds `1..6`. This is a meaningful transport and gate validation milestone:
the six-game rotation passed with no stale, rejected, errored, missing, or
leaking command evidence.

It is not a tactical-completeness milestone. All six outcomes favored the
heroes, and max command total remains far above the long-term interactive
target. The next iteration should either retain this rotation with artifacts
for dashboard history or move to content/release surfaces that stress monster
pressure, survival, control, and pathing rather than only the standard door
arena.

## 2026-07-16 content gauntlet gate check

The first content gauntlet pass exposed two real issues before going green.

First, `srd_undead_crypt` crashed when the Ogre Zombie rolled its Large-size
extra damage. The extra `Damage` packet had no `damage_bonus`, violating the
engine invariant used by `Damage.get_dice()`. The same nullable-bonus shape
also existed in SRD bonus-damage trait packets. The fix made size damage and
bonus trait damage carry explicit zero `ModifiableValue` bonuses.

Second, `srd_low_cr_patrol` seed `2` with `hero_first=false` capped at `200`
commands. The trace showed the archer repeatedly choosing:

```text
Dodge -> Shove adjacent Wolf -> Move -> End Turn
```

while the adjacent wolf kept attacking and a distant bandit kept dodging. This
was a policy-calibration bug: immediate defense could beat pressure even when a
visible adjacent hostile needed to have its agency reduced. The policy now adds
an explicit engaged-damage opportunity cost to Dodge-style immediate defense
when legal direct damage exists against visible hostiles.

The shield-fighter validation helper also now equips a `Longbow` in the ranged
main slot, preserving the intended BG3-style independent melee/ranged loadout
and preventing melee-only chase loops in content arenas that include ranged
kiters.

Focused checks:

```bash
uv run pytest tests/manual/test_53_srd_monster_traits.py -q
uv run pytest tests/manual/test_37_ai_validation_arenas.py -q -k "srd_undead_crypt_gives_shield_fighter_ranged_counterplay or each_ai_validation_arena"
uv run pytest tests/manual/test_44_typed_agent_policy.py -q -k "immediate_defense or adjacent_hostile_before_moderate_defense_loop"
uv run pytest tests/manual/test_56_gauntlet_runner_cli.py -q
uv run pyright ai/evaluation/gauntlet_runner.py ai/policy/candidates.py dnd/entity.py dnd/monsters/traits.py dnd/scenarios/ai_validation_arenas.py
```

Final content gate:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode content --no-run-artifacts --no-summary-file --require-gate-pass
```

Result:

- `gate_status`: `passed`
- `gate_reasons`: `[]`
- `completed_count`: `6`
- `failed_count`: `0`
- `status_counts`: `{"encounter_ended": 6}`
- `command_status_counts`: `{"accepted": 485}`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- outcomes: `{"heroes": 4, "monsters": 2}`
- average commands: `80.833`
- max match elapsed: `3623.729 ms`
- max command total: `73.815 ms`
- max local decision: `19.066 ms`

Per-match command counts were:

- `srd_low_cr_patrol`, seed `1`, hero first: `66`
- `srd_low_cr_patrol`, seed `2`, monsters first: `80`
- `srd_undead_crypt`, seed `1`, hero first: `85`
- `srd_undead_crypt`, seed `2`, monsters first: `70`
- `srd_goblinoid_warband`, seed `1`, hero first: `79`
- `srd_goblinoid_warband`, seed `2`, monsters first: `105`

This is the first green content gauntlet over the SRD low-CR, undead, and
goblinoid arenas. It is not a release milestone: local decision outliers still
exceed the long-term target, and the release gauntlet has not yet passed.

## 2026-07-16 retained release and three-rotation gate check

The current production stack passed one retained release gauntlet and then
three consecutive six-game rotations.

Release command:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode release --require-gate-pass
```

Release artifact:

- `ai/evidence/gauntlets/20260716T181616Z-ai-gauntlet-release-a2c474b3.json`

Release result:

- `gate_status`: `passed`
- `gate_reasons`: `[]`
- `completed_count`: `12`
- `failed_count`: `0`
- `status_counts`: `{"encounter_ended": 12}`
- `command_status_counts`: `{"accepted": 730}`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- outcomes: `{"heroes": 6, "monsters": 6}`
- average commands: `60.833`
- max match elapsed: `4805.803 ms`
- max command total: `108.468 ms`
- max local decision: `19.402 ms`
- raw run artifacts retained: `12`

The release schedule covered:

- `standard_skeleton_doors`, seeds `1..3`
- `caster_crossfire`, seeds `1..3`
- `srd_low_cr_patrol`, seeds `1..3`
- `srd_undead_crypt`, seeds `1..3`

Three consecutive rotation commands:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode rotation --require-gate-pass
uv run python -m ai.evaluation.gauntlet_runner run --mode rotation --require-gate-pass
uv run python -m ai.evaluation.gauntlet_runner run --mode rotation --require-gate-pass
```

Rotation artifacts:

- `ai/evidence/gauntlets/20260716T181721Z-ai-gauntlet-rotation-a03da228.json`
- `ai/evidence/gauntlets/20260716T181734Z-ai-gauntlet-rotation-f8d74aba.json`
- `ai/evidence/gauntlets/20260716T181746Z-ai-gauntlet-rotation-952a50c1.json`

All three rotations passed with:

- `completed_count`: `6`
- `failed_count`: `0`
- `status_counts`: `{"encounter_ended": 6}`
- `command_status_counts`: `{"accepted": 100}`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- outcomes: `{"heroes": 6}`
- per-match command counts: `[11, 33, 10, 24, 11, 11]`

Performance across the three rotations:

- rotation 1 max command total: `107.127 ms`, max local decision: `5.027 ms`
- rotation 2 max command total: `105.145 ms`, max local decision: `4.636 ms`
- rotation 3 max command total: `103.765 ms`, max local decision: `4.951 ms`

Outlier notes:

- The release max local decision was `19.402 ms`, from the low-CR patrol
  archer selecting `Drink Haste Potion`. Its trace attributes the outlier to
  policy work (`policy_ms=18.278`, `fact_ms=1.124`), not command transport.
- Similar low-CR patrol setup decisions were `18.745..19.402 ms`. This is now
  explained but not yet acceptable for the final speed target.
- The release max command total was `108.468 ms` on the standard-door opening
  `Move` with deep diagnostics enabled. Server timing attributes the bulk to
  movement execution, visibility/senses updates, AoE footprint/FOV work, and
  follow-up decision-epoch construction.
- Several 60-75 ms command totals in release are server-side action execution
  plus follow-up epoch rebuild, especially movement, shove, ranged attacks,
  and Fireball/AoE turns.

This satisfies the current functional gate evidence for one retained release
gauntlet plus three consecutive rotations, with no leaks, stale commands,
rejections, errors, hangs, or hidden failed rows in those gates.

It does not complete the overall goal yet. The latency targets are still not
met, the worst policy/setup path needs optimization or caching, and the final
architecture/documentation audit still needs to prove every required substrate,
semantics, LLM mode, watcher contract, and extension point from the goal.

## 2026-07-16 - Dominant Setup Routine-Planning Bound

Followed up on the retained release outlier where the low-CR patrol archer
spent `18.278 ms` of policy time selecting `Drink Haste Potion`.

New self-play policy diagnostics showed the cause precisely:

- selected command: `Drink Haste Potion`
- selected reason: `establish_durable_combat_setup`
- previous policy time: about `18.5 ms`
- previous routine-planning time: about `18.1 ms`
- previous routine counters: `242` movement endpoints, `2` damage
  capabilities, `1240` affordability pair evaluations, and `635` line-of-sight
  evaluations

This was not a damage-outcome scoring issue. The behavior tree eventually
selected a dominant durable setup, but the routine planner had already spent a
full future-movement search on offensive routine starters that could not beat
that setup.

Implemented an explicit dominance rule in `ai/policy/routines.py`: when there
is no active routine, no legal direct pressure, and a high-scoring durable
self-setup is already available, starter routine planning is skipped for that
epoch. Active routine revalidation still happens first, and the server remains
authoritative for legality.

Added self-play trace diagnostics:

- `ExternalSelfPlayTrace.policy_diagnostics`
- policy host stage timings
- routine bounded-work counters

Also fixed an import-boundary bug exposed by the probe: importing
`ai.evaluation.gauntlet_contract` through the server pulled in the eager
`ai.evaluation` package initializer, which imported artifacts, which imported
`ai.external_selfplay`, creating a circular import. The package initializer is
now intentionally lightweight; concrete symbols should be imported from their
own modules.

Focused proof:

- `uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "dominant_durable_setup"`
  - passed
- `uv run pytest tests/manual/test_56_gauntlet_runner_cli.py -q`
  - passed
- `uv run pyright ai/evaluation/__init__.py ai/external_selfplay.py ai/policy/routines.py tests/manual/test_43_ai_runtime_performance.py`
  - 0 errors

Post-fix low-CR probe for the Haste decision:

- selected command remained `Drink Haste Potion`
- policy time dropped to about `0.388 ms`
- local decision time dropped to about `1.196 ms`
- routine-planning time dropped to about `0.015 ms`
- movement endpoints, damage capabilities, affordability-pair evaluations, and
  line-of-sight evaluations dropped to `0`

Remaining latency gap:

- a later low-CR archer `end_turn` / `hold_future_tactical_envelope` decision
  still measured around `7.3 ms` policy time, mostly routine planning without
  the old movement-endpoint counters.
- a smoke low-CR gauntlet slice passed subjectivity and gate checks, but still
  reported max local decision around `8.634 ms` and max command total around
  `67.617 ms`.
- Server-side command totals remain above the final target and need their own
  follow-up pass around movement execution, visibility/senses updates, and
  follow-up epoch construction.

## 2026-07-16 - Pursuit Starter Preemption For Hold-Turn Latency

Followed the remaining low-CR patrol local spike after the dominant setup fix.
The slow command was the patrol archer's `end_turn` decision with reason
`hold_future_tactical_envelope`.

Measured cause:

- selected command: `end_turn`
- selected reason: `hold_future_tactical_envelope`
- previous policy time: about `7.5 ms`
- previous routine-planning time: about `6.5 ms`
- per-routine timing showed `routine.pursue_capability` owning about `6.1 ms`
  across the short probe
- existing routine counters were zero, proving this was a blind spot in
  planner observability rather than the prior movement/LOS counter path

Implemented a utility-bound starter preemption in `ai/policy/routines.py`.
When no routine is active and an already-built non-routine candidate outranks
the fixed `PURSUE_CAPABILITY` starter score, the pursuit starter planner is
not run. Active pursuit revalidation is unaffected, and pursuit still plans
when it can matter to the selected command.

Post-fix low-CR probe:

- archer `hold_future_tactical_envelope` selected the same `end_turn` command
- policy time dropped to about `1.1 ms`
- local decision time dropped to about `1.9 ms`
- routine-planning stage dropped to about `0.046 ms`

Focused proof:

- `uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "dominant_durable_setup or dominated_pursuit_starter"`
  - passed
- `uv run pyright ai/evaluation/__init__.py ai/external_selfplay.py ai/policy/routines.py tests/manual/test_43_ai_runtime_performance.py`
  - 0 errors

Low-CR smoke gauntlet check:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id srd_low_cr_patrol --seed 606 --no-run-artifacts --no-summary-file --require-gate-pass
```

Result:

- `gate_status`: `passed`
- `completed_count`: `1`
- `failed_count`: `0`
- `command_status_counts`: `{"accepted": 51}`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- `max_local_decision_ms`: `3.915`
- `max_command_total_ms`: `64.361`

This brings the retained low-CR local policy slice under the current 5 ms local
stage target. The remaining visible gap is server-side command total latency,
especially movement/action execution plus follow-up epoch construction.

## 2026-07-16 - Gauntlet Server Timing Split

The gauntlet and watcher evidence contract now separates command latency into
the existing end-to-end command total and a promoted server-side command total.
This keeps the dashboard honest: a slow command can now be attributed to local
policy, command transport/synchronization, or server validation/mutation/epoch
publication without collapsing everything into one number.

Added fields:

- `TournamentMatchRecord.max_server_command_ms`
- `GauntletPerformanceSummary.max_server_command_ms`
- `MATCH_PROGRESS.payload.max_server_command_ms`
- watcher metric card and performance table column for server command latency

Focused proof:

- `uv run pytest tests/manual/test_52_ai_tournament_elo.py -q`
  - passed
- `uv run pytest tests/manual/test_54_ai_gauntlet_watcher.py -q`
  - passed
- `uv run pytest tests/manual/test_56_gauntlet_runner_cli.py -q`
  - passed
- `uv run pytest tests/manual/test_57_gauntlet_watcher_html.py -q`
  - passed
- `uv run pyright ai/evaluation/tournament.py ai/evaluation/gauntlet_contract.py ai/evaluation/gauntlet.py tests/manual/test_52_ai_tournament_elo.py tests/manual/test_54_ai_gauntlet_watcher.py tests/manual/test_57_gauntlet_watcher_html.py`
  - 0 errors

Low-CR smoke gauntlet check:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id srd_low_cr_patrol --seed 606 --no-run-artifacts --no-summary-file --require-gate-pass
```

Result:

- `gate_status`: `passed`
- `command_status_counts`: `{"accepted": 51}`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- `max_command_total_ms`: `64.137`
- `max_server_command_ms`: `43.894`
- `max_local_decision_ms`: `4.809`

The local decision path stayed below the current 5 ms target in this smoke
slice. The next meaningful latency work should focus on server command phases:
action execution, senses/path recomputation, and follow-up decision epoch
construction.

## 2026-07-16 - Dashboard Projection Server Timing Promotion

The JSON dashboard projection now promotes server command timing for external
self-play artifacts in the same style as the gauntlet watcher. This closes a
small observability mismatch: retained validation artifacts already stored
`trace.server_timing.total_ms`, but dashboard rows did not expose a stable
`max_server_command_ms` key.

Added dashboard metric keys:

- `server_command_sample_count`
- `server_command_p95_ms`
- `server_command_max_ms`
- `max_server_command_ms`

Focused proof:

- `uv run pytest tests/manual/test_46_ai_dashboard_projection.py::test_projection_preserves_manual_rows_and_derives_artifact_metrics -q`
  - passed
- `uv run pytest tests/manual/test_46_ai_dashboard_projection.py -q`
  - passed
- `uv run pyright ai/evaluation/dashboard_projection.py tests/manual/test_46_ai_dashboard_projection.py`
  - 0 errors

The full projection test remains relatively slow because it loads retained
direct-Codex artifacts from disk, but the projected statistics are now
consistent with the gauntlet summary and live watcher metrics.

## 2026-07-16 - Event-Time Projection Instrumentation And Movement Patch Bound

Investigated the remaining server-side command latency after local policy
latency was brought under target. A first attempt to project subjective event
frames only at EventQueue batch boundaries was rejected by focused tests:
batched damage frames must preserve HP at each completion boundary, and sensory
frames must be captured immediately while only delivery is deferred. That
optimization was not kept.

Added detailed observation projection timing under action traces instead:

- `observation_projection.projection.project_events_ms`
- `observation_projection.projection.project_completion_events_ms`
- per-event-type projection totals
- sensory patch subphase timings
- entity fact construction subphase timings

The new timing showed the hot path for movement commands was sensory
`visible_entities_moved` projection rebuilding a full entity fact. That rebuilt
HP, AC, damage affinities, conditions, and model data even when the sensory
delta only changed the known position of an already visible entity.

Implemented a narrower subjective patch:

- `visible_entities_moved` now emits a partial `entity_update` containing
  `uuid`, `knowledge_state=visible`, and `position`.
- Full entity facts are still used for newly visible entities, removed/
  remembered entities, damage, conditions, and other state-changing events.
- The materializer normalizes partial JSON `position` and `knowledge_state`
  values when applying entity updates.

Focused before/after probe on low-CR patrol command index 16:

- before: `capture_initialized_sessions_on_events_ms` about `7.8 ms`
- before: `projection.sensory_patches.entity_moved_ms` about `4.3 ms`
- after: `capture_initialized_sessions_on_events_ms` about `1.6 ms`
- after: `projection.sensory_patches.entity_moved_ms` about `0.018 ms`
- after: sampled server total for that command about `19.6 ms`

Focused proof:

- `uv run pytest tests/manual/test_28_subjective_observation_stream.py -q`
  - passed
- `uv run pytest tests/manual/test_32_subjective_runtime_store.py -q`
  - passed
- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q`
  - passed
- `uv run pyright ai/observation/projector.py ai/observation/materializer.py tests/manual/test_28_subjective_observation_stream.py`
  - 0 errors

Low-CR smoke gauntlet check:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id srd_low_cr_patrol --seed 606 --no-run-artifacts --no-summary-file --require-gate-pass
```

Result:

- `gate_status`: `passed`
- `command_status_counts`: `{"accepted": 49}`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- `max_command_total_ms`: `67.124`
- `max_server_command_ms`: `39.173`
- `max_local_decision_ms`: `3.757`

The server max is still above the final target, but the projector now exposes
more precise subphase evidence and no longer rebuilds full entity facts for
simple sensory movement deltas.

## 2026-07-16 - Movement Completion Position-Only Projection

Continued the server latency pass after sensory moved-entity patches. The next
remaining projection cost was movement and forced-movement completion frames:
they were still rebuilding full entity facts for simple final-position updates.

Implemented a second narrow projection bound:

- `MOVEMENT` completion frames now emit a partial `entity_update` for the
  mover position.
- `FORCED_MOVEMENT` completion frames now emit a partial `entity_update` for
  the moved target position.
- Damage, healing, condition, reveal, and newly visible/remembered entity
  paths still use their existing HP patches or full facts.

Focused contracts:

- `test_sensory_moved_entity_uses_partial_position_update`
- `test_movement_completion_uses_partial_position_update`

Focused proof:

- `uv run pytest tests/manual/test_28_subjective_observation_stream.py -q`
  - passed
- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q`
  - passed
- `uv run pyright ai/observation/projector.py ai/observation/materializer.py tests/manual/test_28_subjective_observation_stream.py`
  - 0 errors

Low-CR patrol diagnostic slice:

- movement completion projection now spends about `0.03 ms` on referenced
  entity position patches instead of rebuilding entity facts.
- forced-movement completion projection now spends about `0.03 ms` on
  referenced entity position patches instead of rebuilding entity facts.

Low-CR smoke gauntlet check:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id srd_low_cr_patrol --seed 606 --no-run-artifacts --no-summary-file --require-gate-pass
```

Result:

- `gate_status`: `passed`
- `command_status_counts`: `{"accepted": 49}`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- `max_command_total_ms`: `64.009`
- `max_server_command_ms`: `36.527`
- `max_local_decision_ms`: `3.939`

At this point the observation projection overhead for movement-like updates is
small. The remaining movement command latency is mostly real sensory/FOV/path
work: `SpatialSensesSystem`, final `update_entity_senses`, and follow-up epoch
`get_available_actions` after dirty path invalidation.

## 2026-07-16 - Dirty Path Deferral When Movement Is Exhausted

Investigated follow-up epoch `get_available_actions` after dirty path
invalidation. A correctness-preserving guard was added for the no-movement
case: if an actor has dirty paths but `remaining_movement == 0`, action
discovery no longer recomputes Dijkstra just to discover that movement rows are
empty.

Semantics:

- Dirty paths remain dirty.
- Dash and other self actions are still discovered.
- If movement is restored later, the next action discovery recomputes paths
  before exposing movement rows.
- This does not affect visible entity, object, spell, or self-action discovery.

Focused proof:

- `test_zero_movement_dirty_paths_are_deferred_until_movement_exists`
- `uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "zero_movement_dirty_paths or dominant_durable_setup or dominated_pursuit_starter"`
  - passed
- `uv run pytest tests/manual/test_09_action_discovery_and_costs.py -q`
  - passed
- `uv run pyright dnd/entity.py tests/manual/test_43_ai_runtime_performance.py`
  - 0 errors

Low-CR smoke gauntlet check:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id srd_low_cr_patrol --seed 606 --no-run-artifacts --no-summary-file --require-gate-pass
```

Result:

- `gate_status`: `passed`
- `command_status_counts`: `{"accepted": 49}`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- `max_command_total_ms`: `65.556`
- `max_server_command_ms`: `37.692`
- `max_local_decision_ms`: `3.958`

This guard did not materially affect the current low-CR seed because the
observed expensive epochs still had movement available. It does cover a
previously obvious bad epoch shape and keeps future no-movement turns from
spending pathfinding work before Dash or a later resource restores movement.

## 2026-07-16 - No-Hazard Movement Discovery And Path-Cost Cache

Continued the same server-tail pass. The remaining movement epoch cost was not
coming from subjective projection anymore; it was mostly legal movement row
construction after dirty path invalidation. Two small, correctness-preserving
guards were added:

- maps with no active hazard conditions skip per-step `is_position_hazardous`
  checks during senses and movement-row construction;
- fast movement target discovery caches per-cell movement cost within one
  discovery pass, so overlapping legal paths do not repeatedly ask tiles for
  the same movement cost.

Focused diagnostic on `srd_low_cr_patrol`, seed `606`, with deep diagnostics
enabled on every command:

- `status`: `encounter_ended`
- `commands`: `49`
- `max_server_command_ms`: `34.699`
- `max_local_decision_ms`: `3.648`
- `publish.followup_epoch.available_actions.collect_path_actions_ms`: max
  `5.238 ms`, average `1.587 ms`
- `advance.publish_active_epoch.available_actions.collect_path_actions_ms`: max
  `3.352 ms`, average `2.300 ms`
- `publish.followup_epoch.available_actions.fast_move_targets.path_cost_ms`:
  max `1.962 ms`, average `0.844 ms`
- `advance.publish_active_epoch.available_actions.fast_move_targets.path_cost_ms`:
  max `0.914 ms`, average `0.839 ms`
- no-hazard path checks stayed effectively zero:
  `fast_move_targets.hazard_ms` max `0.009 ms`

The remaining top server phases in that diagnostic were still real command and
epoch work: `execute.action_by_index_ms` max `28.052 ms`,
`publish.post_command_control_ms` max `20.089 ms`,
`publish.followup_epoch.build_decision_epoch_total_ms` max `19.807 ms`, and
dirty-senses recomputation at about `8 ms` when paths were invalidated.

Focused proof:

- `test_zero_movement_dirty_paths_are_deferred_until_movement_exists`
- `test_no_hazard_map_skips_per_path_hazard_checks`
- `uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "zero_movement_dirty_paths or no_hazard_map_skips_per_path_hazard_checks"`
  - passed
- `uv run pyright dnd/core/gridmap.py dnd/entity.py tests/manual/test_43_ai_runtime_performance.py`
  - 0 errors

Low-CR smoke gauntlet check:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id srd_low_cr_patrol --seed 606 --no-run-artifacts --no-summary-file --require-gate-pass
```

Result:

- `gate_status`: `passed`
- `command_status_counts`: `{"accepted": 49}`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- `max_command_total_ms`: `67.186`
- `max_server_command_ms`: `35.646`
- `max_local_decision_ms`: `3.923`

This is progress, not a completed latency gate. Local policy remains under the
current target in this smoke slice, while the server tail is still above the
final objective and should next be attacked in dirty-senses recomputation,
epoch publication, and authoritative action execution.

## 2026-07-16 - Subjective Path Cache With Occupancy And Perception Keys

Investigated the next dirty-senses tail. Repeated row construction can call
`GridMap.compute_paths()` with the same subjective query more than once during
one command/epoch boundary, while truly dirty actor movement still needs a new
Dijkstra from the new origin. Added a bounded `GridMap` path cache with keys
covering:

- path origin, radius, movement mode, danger policy, and terrain policy;
- movement-topology revision;
- entity occupancy revision;
- subjective collision and directional-collision memory;
- requester passive perception, invisibility bypass capability, magical
  darkness piercing, and sense modes for subjective queries.

The perception key was required. A focused senses regression caught the first
version: after an observer gained truesight, cached paths from the previous
"invisible blocker is unknown" state still ignored that blocker. The cache key
now includes observer-local perception state, so truesight/stealth/invisibility
changes do not reuse stale subjective paths.

Correctness invalidation added:

- entity register/unregister/move increments occupancy revision;
- death and resurrection non-blocking changes invalidate occupancy paths;
- movement-topology changes still clear the path cache.

Focused diagnostic on `srd_low_cr_patrol`, seed `606`, with deep diagnostics
on every command:

- `status`: `encounter_ended`
- `commands`: `49`
- `max_server_command_ms`: `38.248`
- `max_local_decision_ms`: `3.916`
- `publish.followup_epoch.grid.compute_paths.cache_hit_ms`: `20` hits
- `publish.followup_epoch.grid.compute_paths.cache_miss_ms`: `19` misses
- `publish.followup_epoch.available_actions.collect_path_actions_ms`: max
  `4.566 ms`
- `publish.followup_epoch.available_actions.fast_move_targets.path_cost_ms`:
  max `1.529 ms`
- remaining dirty refresh cost stayed high:
  `publish.followup_epoch.senses.compute_paths_ms` max `7.077 ms`

Focused proof:

- `test_grid_compute_paths_reuses_same_revision_result`
- `test_grid_compute_paths_invalidates_on_occupancy_change`
- `test_eb_12_007_subjective_paths_do_not_leak_imperceivable_blockers`
- `uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "grid_compute_paths or zero_movement_dirty_paths or no_hazard_map_skips_per_path_hazard_checks"`
  - passed
- `uv run pytest tests/engine_book/test_chapter_12_senses_light_stealth.py -q -k "subjective_paths_do_not_leak or self_movement_updates_visibility or distant_movement_does_not_dirty"`
  - passed
- `uv run pytest tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py -q -k "dijkstra_paths_sum_tile_costs or dead_entities_become_non_blocking or hazards_can_be_excluded or hidden_hazard"`
  - passed
- `uv run pyright dnd/core/gridmap.py dnd/entity.py dnd/conditions.py tests/manual/test_43_ai_runtime_performance.py`
  - 0 errors

Low-CR smoke gauntlet check:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id srd_low_cr_patrol --seed 606 --no-run-artifacts --no-summary-file --require-gate-pass
```

Result:

- `gate_status`: `passed`
- `command_status_counts`: `{"accepted": 49}`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- `max_command_total_ms`: `69.459`
- `max_server_command_ms`: `37.969`
- `max_local_decision_ms`: `4.009`

This closes one repeated-query inefficiency and protects the subjective
perception boundary, but it does not solve dirty-senses recomputation after
movement. A tempting next optimization is to recompute action-discovery paths
only up to current movement budget instead of the full senses radius. That must
first model path radius on `Senses`, because Dash or other movement-restoring
effects can make a previously truncated path cache insufficient later in the
same turn.

## 2026-07-16 - Movement-Budget Path Radius With Dash Expansion

Implemented the next safe dirty-senses optimization by separating visibility
radius from path radius. `Senses` now records `path_max_distance`, and action
discovery treats cached paths as usable only when they are clean and deep
enough for the current movement budget.

Behavior:

- normal full senses refreshes still compute paths to the full visibility
  radius unless a narrower path radius is explicitly requested;
- dirty action-discovery refreshes keep visibility at `20` cells but compute
  movement paths only to `ceil(remaining_movement / 5)`;
- if Dash or another effect later increases movement, action discovery sees
  that the current path radius is insufficient and expands paths before
  exposing movement rows;
- zero-movement dirty paths remain deferred so Dash/self actions are still
  visible without a Dijkstra refresh.

Focused proof:

- `test_dirty_action_discovery_limits_path_radius_to_movement_budget`
- `test_dash_expands_limited_path_radius_when_movement_budget_grows`
- `uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "dirty_action_discovery_limits_path_radius or dash_expands_limited_path_radius or grid_compute_paths or zero_movement_dirty_paths or no_hazard_map"`
  - passed
- `uv run pytest tests/engine_book/test_chapter_12_senses_light_stealth.py -q -k "subjective_paths_do_not_leak or self_movement_updates_visibility or visibility_cache or distant_movement_does_not_dirty"`
  - passed
- `uv run pytest tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py -q -k "dijkstra_paths_sum_tile_costs or dead_entities_become_non_blocking or hazards_can_be_excluded or hidden_hazard"`
  - passed
- `uv run pyright dnd/blocks/sensory.py dnd/core/gridmap.py dnd/entity.py dnd/conditions.py tests/manual/test_43_ai_runtime_performance.py`
  - 0 errors

Deep diagnostic on `srd_low_cr_patrol`, seed `606`, with every command sampled:

- `status`: `encounter_ended`
- `commands`: `49`
- `max_server_command_ms`: `37.168`
- `max_local_decision_ms`: `3.744`
- `publish.followup_epoch.available_actions.update_dirty_senses_ms`: max
  `9.091 ms`, average `7.052 ms`
- `publish.followup_epoch.senses.compute_paths_ms`: max `6.872 ms`, average
  `5.036 ms`
- `publish.followup_epoch.grid.compute_paths.dijkstra_total_ms`: max
  `6.555 ms`, average `1.787 ms`
- `publish.followup_epoch.available_actions.collect_path_actions_ms`: max
  `4.892 ms`, average `1.762 ms`

This improved the average dirty path cost but did not eliminate the worst-case
Dijkstra tail. It is still an aligned change because it gives the engine a
typed invariant for path coverage instead of relying on a single dirty boolean.

Low-CR smoke gauntlet check:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id srd_low_cr_patrol --seed 606 --no-run-artifacts --no-summary-file --require-gate-pass
```

Result:

- `gate_status`: `passed`
- `command_status_counts`: `{"accepted": 49}`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- `max_command_total_ms`: `63.429`
- `max_server_command_ms`: `34.803`
- `max_local_decision_ms`: `3.852`

Remaining server-tail targets are now clearer: authoritative movement
execution, follow-up epoch publication, and the few dirty path recomputes that
still have enough reachable cells to exceed the final latency target.

## 2026-07-16 - Movement Final Refresh Path Radius

Bounded the authoritative post-move senses refresh by remaining movement while
preserving full visibility refresh. A completed move still updates subjective
visibility at the normal radius, but the cached movement paths are rebuilt only
to `ceil(remaining_movement / 5)`. When movement is fully spent, the path radius
is `0`, which avoids a pointless full-radius Dijkstra pass before the next
decision epoch.

The important invariant is that visibility and path coverage are now separate:
controllers can still learn newly visible cells/entities/objects after moving,
while movement affordances are computed only from path data deep enough for the
current economy. Dash and other movement-restoring effects still expand paths
when needed because `Senses.path_max_distance` records the current coverage.

Focused proof:

- `test_full_budget_move_refreshes_visibility_without_full_path_radius`
- `test_dirty_action_discovery_limits_path_radius_to_movement_budget`
- `test_dash_expands_limited_path_radius_when_movement_budget_grows`
- `uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "full_budget_move_refreshes_visibility_without_full_path_radius or dash_expands_limited_path_radius or dirty_action_discovery_limits_path_radius"`
  - passed
- `uv run pytest tests/engine_book/test_chapter_12_senses_light_stealth.py -q -k "self_movement_updates_visibility or visibility_cache or subjective_paths_do_not_leak"`
  - passed
- `uv run pytest tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py -q -k "dijkstra_paths_sum_tile_costs or dead_entities_become_non_blocking or hazards_can_be_excluded or hidden_hazard"`
  - passed
- `uv run pyright dnd/actions.py dnd/blocks/sensory.py dnd/core/gridmap.py dnd/entity.py dnd/conditions.py tests/manual/test_43_ai_runtime_performance.py`
  - 0 errors

Deep diagnostic on `srd_low_cr_patrol`, seed `606`, with every command sampled:

- `status`: `encounter_ended`
- `commands`: `49`
- `final_round`: `5`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- `max_server_command_ms`: `35.452`
- `max_local_decision_ms`: `3.868`
- `execute_by_index.movement.final_update_senses_ms`: max `4.43 ms`,
  average `2.938 ms`
- `execute_by_index.entity.update_senses.compute_ms`: max `4.047 ms`,
  average `2.542 ms`
- `execute_by_index.senses.compute_paths_ms`: max `3.248 ms`, average
  `1.643 ms`
- `execute_by_index.grid.compute_paths.dijkstra_total_ms`: max `2.79 ms`,
  average `1.238 ms`

Previous sampled movement-final refresh cost was approximately max `7.769 ms`
and average `7.303 ms`, so this removes the known post-move full-path rebuild
tail. Remaining authoritative movement tail now sits in actual step execution:

- `execute_by_index.movement.update_position_ms`: max `16.522 ms`, average
  `8.41 ms`
- `execute_by_index.grid.move_entity.fire_entity_entered_ms`: max `14.479 ms`,
  average `7.785 ms`
- `execute_by_index.event_queue.pre_completion.callback.SpatialSensesSystem_ms`:
  max `12.853 ms`, average `2.894 ms`

Those are not safe to collapse into a cache blindly because they are the real
event-driven spatial/sensory side effects of movement. They are the next
profiling target, not part of this optimization.

Low-CR smoke gauntlet check:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id srd_low_cr_patrol --seed 606 --no-run-artifacts --no-summary-file --require-gate-pass
```

Result:

- `gate_status`: `passed`
- `command_status_counts`: `{"accepted": 49}`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- `max_command_total_ms`: `65.647`
- `max_server_command_ms`: `34.388`
- `max_local_decision_ms`: `3.939`

## 2026-07-16 - Bright-Map Visibility Light Fast Path

Reduced one self-movement sensory cost without changing the event model. The
movement step still fires objective spatial events and still emits subjective
`SensoryUpdateEvent` deltas, but the visibility reducer now avoids
observer-specific light resolution when every FOV tile is already objectively
bright or brighter.

Rules preserved:

- bright-or-brighter FOV cells are visible to every observer;
- dark, dim, and magical-darkness cells still call
  `Tile.get_effective_light_for()` so darkvision, truesight, and magical
  darkness behavior stay subjective;
- no-observer calls preserve the previous objective behavior;
- this does not skip spatial events, senses events, or movement revalidation.

Focused proof:

- `test_bright_visibility_skips_per_tile_effective_light`
- `test_dark_visibility_still_uses_subjective_light_resolution`
- `uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "bright_visibility or dark_visibility or full_budget_move_refreshes_visibility_without_full_path_radius or dirty_action_discovery_limits_path_radius"`
  - passed
- `uv run pytest tests/engine_book/test_chapter_12_senses_light_stealth.py -q -k "self_movement_updates_visibility or visibility_cache or darkvision_extends_darkness or magical_darkness"`
  - passed
- `uv run pytest tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py -q -k "dijkstra_paths_sum_tile_costs or dead_entities_become_non_blocking or hazards_can_be_excluded or hidden_hazard"`
  - passed
- `uv run pyright dnd/entity.py tests/manual/test_43_ai_runtime_performance.py`
  - 0 errors

Deep diagnostic on `srd_low_cr_patrol`, seed `606`, with every command sampled:

- `status`: `encounter_ended`
- `commands`: `49`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- `max_server_command_ms`: `37.025`
- `max_local_decision_ms`: `4.425`
- `execute_by_index.entity.update_visibility.filter_visible_light_ms`: max
  `1.871 ms`, average `1.037 ms`
- `execute_by_index.sensory_callback.handle_spatial_event_ms`: max `7.724 ms`,
  average `3.675 ms`
- `execute_by_index.grid.move_entity.fire_entity_entered_ms`: max `13.429 ms`,
  average `7.521 ms`
- `execute_by_index.movement.update_position_ms`: max `15.442 ms`, average
  `8.173 ms`

The previous sampled bright-map movement visibility filter averaged about
`1.516 ms`, and the sensory spatial handler averaged about `4.206 ms`. This is
a modest but real improvement. The remaining movement-step tail is still mostly
FOV computation and event/epoch publication, not per-tile light resolution.

Low-CR smoke gauntlet check:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id srd_low_cr_patrol --seed 606 --no-run-artifacts --no-summary-file --require-gate-pass
```

Result:

- `gate_status`: `passed`
- `command_status_counts`: `{"accepted": 49}`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- `max_command_total_ms`: `63.528`
- `max_server_command_ms`: `34.921`
- `max_local_decision_ms`: `4.111`

During an over-broad Chapter 12 regression selection, the existing Fireball
visibility test reported an unexpected level-3 slot count after otherwise
correct damage/Hidden behavior. That failure was recorded in `KNOWN_ISSUES.md`
as unrelated to this movement visibility performance slice.

## 2026-07-16 - Unit-Cost Pathfinding Fast Path

Added a conservative breadth-first pathfinder for unit-cost movement maps.
`GridMap.compute_paths()` now keeps the existing weighted Dijkstra path unless
every tile has effective movement cost `1` for the requested movement mode. The
fast path still calls the same walkability and transition callbacks, so
subjective blockers, doors, remembered collision blockers, directional borders,
occupancy, hazards, and max-distance pruning stay on the same legality path.

Rules preserved:

- non-unit or difficult terrain uses weighted Dijkstra;
- `ignore_difficult_terrain` is respected when deciding whether costs are unit;
- diagonal movement remains cost `1`, matching the existing engine semantics;
- cached `compute_paths()` results keep returning mutable copies to callers;
- occupancy changes still invalidate the path cache.

Focused proof:

- `test_unit_cost_paths_use_breadth_first_fast_path`
- `test_weighted_paths_keep_dijkstra_selection`
- `test_grid_compute_paths_reuses_same_revision_result`
- `test_grid_compute_paths_invalidates_on_occupancy_change`
- `uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "bright_visibility or dark_visibility or full_budget_move_refreshes_visibility_without_full_path_radius or dirty_action_discovery_limits_path_radius or dash_expands_limited_path_radius or unit_cost_paths_use_breadth_first_fast_path or weighted_paths_keep_dijkstra_selection or grid_compute_paths"`
  - passed
- `uv run pytest tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py -q -k "dijkstra_paths_sum_tile_costs or diagonal_cost_return or diagonal_transitions_need_one_cardinal_bridge_route or negative_coordinate_tiles_are_reachable or hazards_can_be_excluded or hidden_hazard"`
  - passed
- `uv run pytest tests/engine_book/test_chapter_12_senses_light_stealth.py -q -k "self_movement_updates_visibility or visibility_cache or darkvision_extends_darkness or magical_darkness or subjective_paths_do_not_leak"`
  - passed
- `uv run pyright dnd/core/dijkstra.py dnd/core/gridmap.py dnd/entity.py tests/manual/test_43_ai_runtime_performance.py`
  - 0 errors

Deep diagnostic on `srd_low_cr_patrol`, seed `606`, with every command sampled:

- `status`: `encounter_ended`
- `commands`: `49`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- `max_server_command_ms`: `30.653`
- `max_local_decision_ms`: `3.497`
- `publish.followup_epoch.available_actions.update_dirty_senses_ms`: max
  `4.84 ms`, average `3.939 ms`
- `publish.followup_epoch.senses.compute_paths_ms`: max `3.095 ms`, average
  `2.395 ms`
- `publish.followup_epoch.grid.compute_paths.bfs_total_ms`: max `2.839 ms`,
  average `2.107 ms`
- `publish.followup_epoch.grid.compute_paths.dijkstra_total_ms`: max
  `2.918 ms`, average `0.85 ms`
- `publish.followup_epoch.available_actions.collect_path_actions_ms`: max
  `5.035 ms`, average `1.638 ms`

The comparable pre-BFS dirty path recompute sample was approximately
`publish.followup_epoch.available_actions.update_dirty_senses_ms` max `8.47 ms`,
average `6.339 ms`, and `publish.followup_epoch.senses.compute_paths_ms` max
`6.498 ms`, average `4.696 ms`. This is a large enough improvement to matter
for epoch latency while keeping weighted terrain behavior intact.

Low-CR smoke gauntlet check:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id srd_low_cr_patrol --seed 606 --no-run-artifacts --no-summary-file --require-gate-pass
```

Result:

- `gate_status`: `passed`
- `command_status_counts`: `{"accepted": 49}`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- `max_command_total_ms`: `60.506`
- `max_server_command_ms`: `29.288`
- `max_local_decision_ms`: `3.694`

## 2026-07-16 - Senses Path-Cost Facts

Carried movement path costs as first-class subjective topology facts. The
pathfinder already computes movement-cost distances; `Senses` now stores those
distances in feet alongside `paths` and `safe_paths`, and movement affordance
discovery reuses them instead of rescanning every path tile-by-tile.

Rules preserved:

- path legality still comes from the same subjective `GridMap.compute_paths()`
  call;
- weighted terrain, difficult terrain, hazards, safe paths, blockers, doors,
  and directional transitions still affect the pathfinder result;
- direct/manual path consumers can still fall back to `_movement_path_cost_feet`;
- cached movement targets include path-cost signatures so stale target caches
  do not survive cost fact changes.

Focused proof:

- `test_move_discovery_uses_cached_senses_path_costs`
- `test_weighted_move_discovery_uses_cached_senses_path_costs`
- `test_move_discovery_reuses_subjective_path_projection`
- `uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "bright_visibility or dark_visibility or full_budget_move_refreshes_visibility_without_full_path_radius or dirty_action_discovery_limits_path_radius or dash_expands_limited_path_radius or unit_cost_paths_use_breadth_first_fast_path or weighted_paths_keep_dijkstra_selection or move_discovery_uses_cached_senses_path_costs or weighted_move_discovery_uses_cached_senses_path_costs or grid_compute_paths"`
  - passed
- `uv run pytest tests/manual/test_31_subjective_runtime_epochs.py -q -k "move_discovery_reuses_subjective_path_projection"`
  - passed
- `uv run pytest tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py -q -k "dijkstra_paths_sum_tile_costs or diagonal_cost_return or diagonal_transitions_need_one_cardinal_bridge_route or negative_coordinate_tiles_are_reachable or hazards_can_be_excluded or hidden_hazard"`
  - passed
- `uv run pytest tests/engine_book/test_chapter_12_senses_light_stealth.py -q -k "self_movement_updates_visibility or visibility_cache or subjective_paths_do_not_leak or hidden_hazard"`
  - passed
- `uv run pyright dnd/blocks/sensory.py dnd/core/dijkstra.py dnd/core/gridmap.py dnd/entity.py tests/manual/test_43_ai_runtime_performance.py tests/manual/test_31_subjective_runtime_epochs.py`
  - 0 errors

Deep diagnostic on `srd_low_cr_patrol`, seed `606`, with every command sampled:

- `status`: `encounter_ended`
- `commands`: `49`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- `max_server_command_ms`: `29.826`
- `max_local_decision_ms`: `3.645`
- `publish.followup_epoch.available_actions.fast_move_targets.path_cost_ms`:
  max `0.023 ms`, average `0.013 ms`
- `publish.followup_epoch.available_actions.collect_path_actions_ms`: max
  `3.71 ms`, average `1.486 ms`
- `publish.followup_epoch.available_actions.update_dirty_senses_ms`: max
  `4.734 ms`, average `4.026 ms`
- `publish.followup_epoch.senses.compute_paths_ms`: max `3.166 ms`, average
  `2.509 ms`
- `publish.followup_epoch.build_decision_epoch_total_ms`: max `15.93 ms`,
  average `5.72 ms`

Compared with the previous post-BFS sample, path-cost work dropped from
approximately max `1.309 ms`, average `0.521 ms` to effectively zero. The
remaining epoch tail is now mostly dirty senses recomputation, target-model
construction, opportunity exposure, and affordance/capability serialization.

Low-CR smoke gauntlet check:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id srd_low_cr_patrol --seed 606 --no-run-artifacts --no-summary-file --require-gate-pass
```

Result:

- `gate_status`: `passed`
- `command_status_counts`: `{"accepted": 49}`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- `max_command_total_ms`: `59.958`
- `max_server_command_ms`: `28.57`
- `max_local_decision_ms`: `3.589`

## 2026-07-16 - Canonical Affordance Row Construction

Reduced duplicate in-memory row work during decision epoch construction. The
epoch builder now creates compact `CanonicalActionRow` references directly and
stores them in `ActionBucketRows`, instead of first constructing full
`ActionAffordance` views and immediately canonicalizing them again inside the
`AffordanceSet`.

Rules and contracts preserved:

- public bucket access still resolves normal `ActionAffordance` rows lazily;
- row ids, execution authority, target bindings, semantic catalog references,
  compact JSON transport, and round-trip validation are unchanged;
- the server remains authoritative for legality and execution;
- no objective state, hidden visibility, or `/available-actions` polling was
  added to production AI paths.

Focused proof:

- `uv run pytest tests/manual/test_42_action_semantics.py -q -k "healing_potion_exposes_bonus_action_healing_and_item_depletion or damage_effect_identity_survives_affordance_transport_and_display_rename or multi_target_affordance_rejects_undisclosed_and_invalid_allocations or single_target_affordance_rejects_additional_targets or semantics_travel_inside_epoch_affordances_and_survive_json_round_trip or affordance_wire_catalog_preserves_content_addressed_semantics"`
  - passed, `6 passed`
- `uv run pytest tests/manual/test_31_subjective_runtime_epochs.py -q -k "affordance or epoch or move_discovery_reuses_subjective_path_projection"`
  - passed, `40 passed`
- `uv run pytest tests/manual/test_42_action_semantics.py -q -k "semantics_travel_inside_epoch_affordances_and_survive_json_round_trip or affordance_wire_catalog_preserves_content_addressed_semantics or multi_target_affordance_rejects_undisclosed_and_invalid_allocations or dense_epoch_wire"`
  - passed, `3 passed`
- `uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "dense_epoch_wire_factors_shared_action_metadata_and_round_trips or epoch_build_expands_registered_action_variants_once or move_discovery_uses_cached_senses_path_costs or weighted_move_discovery_uses_cached_senses_path_costs"`
  - passed, `4 passed`
- `uv run pyright ai/subjective/epochs.py ai/protocol/control.py`
  - 0 errors

Deep diagnostic on `srd_low_cr_patrol`, seed `606`, with every command sampled:

- before:
  - `status`: `encounter_ended`
  - `commands`: `49`
  - `subjectivity_status`: `passed`
  - `subjectivity_violation_count`: `0`
  - `max_server_command_ms`: `33.212`
  - `max_local_decision_ms`: `3.619`
  - `publish.followup_epoch.build_decision_epoch_total_ms`: max `17.289 ms`,
    average `6.028 ms`
  - `publish.followup_epoch.build_affordance_set_ms`: max `4.86 ms`,
    average `2.858 ms`
- after:
  - `status`: `encounter_ended`
  - `commands`: `49`
  - `subjectivity_status`: `passed`
  - `subjectivity_violation_count`: `0`
  - `max_server_command_ms`: `31.142`
  - `max_local_decision_ms`: `3.695`
  - `publish.followup_epoch.build_decision_epoch_total_ms`: max `16.254 ms`,
    average `5.748 ms`
  - `publish.followup_epoch.build_affordance_set_ms`: max `4.342 ms`,
    average `2.522 ms`

Low-CR smoke gauntlet check:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id srd_low_cr_patrol --seed 606 --no-run-artifacts --no-summary-file --require-gate-pass
```

Result:

- `gauntlet_id`: `20260716T201200Z-ai-gauntlet-smoke-b7ae8fa3`
- `gate_status`: `passed`
- `command_status_counts`: `{"accepted": 49}`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- `max_command_total_ms`: `66.18`
- `max_server_command_ms`: `29.737`
- `max_local_decision_ms`: `3.517`

## 2026-07-16 - Live Gauntlet Watcher Server Cursors

Tightened the live gauntlet watcher stream contract. Externally mirrored
gauntlet runners can carry local event cursors in retained summary JSON, but
the backend live stream must own its replay cursor namespace. The server now
assigns a fresh monotonic cursor to every ingested watcher event instead of
trusting the posted `cursor` field.

Why this matters:

- two independent gauntlet producers may both submit local cursor `1`;
- a server may already have live events before an external process mirrors its
  first event;
- SSE ids, `since=` replay, `next_cursor`, and bounded-history eviction all
  depend on one monotonic server stream.

Focused proof:

- Added `test_gauntlet_event_ingest_uses_server_monotonic_cursors`.
- `uv run pytest tests/manual/test_55_gauntlet_live_watcher_server.py -q -k monotonic`
  - passed, `1 passed`
- `uv run pyright server/gauntlet_event_stream.py tests/manual/test_55_gauntlet_live_watcher_server.py`
  - 0 errors
- `uv run pytest tests/manual/test_55_gauntlet_live_watcher_server.py -q`
  - passed, `8 passed`
- `uv run pytest tests/manual/test_54_ai_gauntlet_watcher.py -q`
  - passed, `11 passed`
- `uv run pytest tests/manual/test_56_gauntlet_runner_cli.py -q`
  - passed, `9 passed`
- `uv run pytest tests/manual/test_57_gauntlet_watcher_html.py -q`
  - passed, `1 passed`

This is observability-only. It does not change engine events, subjective
controller streams, command validation, NeuroClient, or retained gauntlet
summary semantics.

## 2026-07-16 - Threat Fact Invalidation Scope

Tightened incremental typed-fact reuse for immediate pressure. `ThreatFacts`
only depends on the active actor's known position plus visible hostile
classification and positions. Damage-only entity updates were unnecessarily
invalidating both `contacts` and `threat`; they now rebuild contacts while
reusing threat.

Rules and subjectivity preserved:

- threat still derives only from session-subjective visible hostiles;
- hidden, remembered, unknown-relationship, allied, dead, and uncontrolled
  facts are not converted into threats;
- hostile position, faction relationship, death state, actor position, turn, or
  epoch changes still invalidate threat;
- HP-only updates continue to refresh contact health indexes without implying a
  change in immediate pressure.

Focused proof:

- Extended `test_fact_derivation_reuses_only_unchanged_sections` so HP-only
  enemy patches reuse `ThreatFacts`, while visible hostile movement invalidates
  threat and records the new adjacent hostile.
- `uv run pytest tests/manual/test_44_typed_agent_policy.py -q -k fact_derivation_reuses_only_unchanged_sections`
  - passed, `1 passed`
- `uv run pytest tests/manual/test_44_typed_agent_policy.py -q`
  - passed, `97 passed`
- `uv run pytest tests/manual/test_45_policy_routines.py -q`
  - passed, `13 passed`
- `uv run pytest tests/manual/test_33_subjective_runtime_processors.py -q`
  - passed, `7 passed`
- `uv run pyright ai/knowledge/deriver.py`
  - 0 errors

## 2026-07-16 - Retained Codex Replay And Shared Routine LOS Cache

Fixed two LLM/shared-policy validation gaps exposed by focused Codex runtime
tests.

### Retained Direct-Codex Replay

Older retained direct-Codex artifacts used the pre-location semantic shape for
information/topology effects. Direct artifact loading already migrated those
known historical contracts, but raw subjective materialization did not. This
broke local read-model replay for retained dense Codex artifacts.

The known legacy migration now lives under `ai.observation` and is applied by
`materialize_snapshot()` and `apply_observation_frame()` before Pydantic
validation. Unknown incomplete historical shapes still fail validation; only
known old contracts are migrated.

### Shared Routine LOS Cache

`EnableThenAct` and `PursueCapability` were each maintaining local
line-of-sight caches. Equivalent endpoint-to-hostile geometry could therefore
be evaluated once per planner instead of once per policy decision. The
decision-local `RoutinePlanningInstrumentation` now owns the LOS cache shared
across registered routine planners.

Focused proof:

- `uv run pytest tests/manual/test_50_codex_local_read_model.py -q`
  - passed, `3 passed`
- `uv run pytest tests/manual/test_47_direct_codex_artifacts.py tests/manual/test_49_hot_codex_runtime.py tests/manual/test_50_codex_local_read_model.py -q`
  - passed, `30 passed`
- `uv run pytest tests/manual/test_48_policy_host.py -q -k enable_then_act_reuses_los_for_equivalent_subjective_geometry`
  - passed, `1 passed`
- `uv run pytest tests/manual/test_48_policy_host.py -q`
  - passed, `50 passed`
- `uv run pytest tests/manual/test_45_policy_routines.py -q`
  - passed, `13 passed`
- `uv run pyright ai/policy/routines.py ai/observation/legacy_semantics.py ai/observation/materializer.py ai/evaluation/direct_codex_artifacts.py`
  - 0 errors

Low-CR smoke gauntlet check:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id srd_low_cr_patrol --seed 606 --no-run-artifacts --no-summary-file --require-gate-pass
```

Result:

- `gauntlet_id`: `20260716T202443Z-ai-gauntlet-smoke-d16cdd69`
- `gate_status`: `passed`
- `command_status_counts`: `{"accepted": 49}`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- `max_command_total_ms`: `66.231`
- `max_server_command_ms`: `32.523`
- `max_local_decision_ms`: `4.405`

## 2026-07-16 - Gauntlet Watcher Backend-First Loading

The static gauntlet watcher can now act as a live observer when opened from
disk. `Load latest` tries the configured backend first through
`GET /ai/gauntlets/latest`, connects the SSE watcher stream for that gauntlet,
and only then falls back to retained JSON or file input if the backend is not
available.

This removes the awkward file-first path where a `file://` browser could fail
local JSON loading before ever reaching the live server. The watcher remains
observability-only: it consumes retained gauntlet summaries and live watcher
events, not engine events or subjective gameplay frames.

Focused proof:

- `uv run pytest tests/manual/test_57_gauntlet_watcher_html.py -q`
  - passed, `1 passed`
- `uv run pytest tests/manual/test_58_ai_runtime_readme.py -q`
  - passed, `1 passed`

## 2026-07-16 - Gauntlet Summary Evidence Validation

Added a retained gauntlet-summary validator to the shared lightweight watcher
contract. A summary can no longer pass through watcher projection, retained
`check`, or summary writing by merely claiming a clean `gate_status`; its audit
metadata must agree with the underlying retained rows.

Validated fields now include:

- completed, failed, and pending counts against schedule and match rows;
- failed match ids and visible failure rows against abnormal retained matches;
- command-status totals against match command-result counts;
- subjectivity violation totals and match ids;
- status/outcome aggregates;
- performance match and command totals;
- gate reasons and gate status;
- watcher event cursor ordering and gauntlet id ownership.

The current retained latest release summary still passes under the stricter
contract:

- `gauntlet_id`: `20260716T204237Z-ai-gauntlet-release-3474e7a7`
- `gate_status`: `passed`
- completed/failed/pending: `12 / 0 / 0`
- subjectivity: `passed`, `0` violations
- command status counts: `{"accepted": 706}`

Focused proof:

- `uv run pytest tests/manual/test_54_ai_gauntlet_watcher.py tests/manual/test_56_gauntlet_runner_cli.py -q`
  - passed, `26 passed`
- `uv run pytest tests/manual/test_55_gauntlet_live_watcher_server.py tests/manual/test_57_gauntlet_watcher_html.py -q`
  - passed, `10 passed`, `1 warning`
- `uv run pytest tests/manual/test_58_ai_runtime_readme.py -q`
  - passed, `1 passed`
- `uv run pyright ai/evaluation/gauntlet_contract.py ai/evaluation/gauntlet.py ai/evaluation/gauntlet_runner.py tests/manual/test_54_ai_gauntlet_watcher.py tests/manual/test_56_gauntlet_runner_cli.py`
  - passed, `0 errors`
- `uv run python -m ai.evaluation.gauntlet_runner check ai/evidence/gauntlets/latest.json --require-gate-pass`
  - passed
- `awk '/<script>/{flag=1;next}/<\\/script>/{flag=0}flag' ai/AI_TOURNAMENT_MONITOR.html | node --check -`
  - passed

## 2026-07-17 - Decision Epoch Descriptor Cache And Smoke Evidence

Added a bounded row-descriptor cache in `ai.subjective.epochs` so repeated
decision-epoch construction can reuse stable typed action descriptors while
still registering the cached semantic references in each epoch-local semantic
catalog. This targets epoch publication overhead without changing server
legality or the subjective stream contract.

The focused v216 dense-spacing regression had a stale full-model hash. The
selected command, selected source node, selected reason, movement row, and old
exhaustive counters still matched; the hash drift came from richer
capability-projection counters now present in the decision evidence. The test
now pins those counters explicitly:

- `capability_projection_modeled == 11`;
- `capability_projection_unmodeled == 1`;
- `capability_projection_insufficient_facts == 0`;
- `capability_projection_guaranteed_zero == 0`.

Fresh retained smoke evidence:

- gauntlet summary:
  `ai/evidence/gauntlets/20260717T005149Z-ai-gauntlet-smoke-d88c183c.json`;
- raw run:
  `ai/evidence/runs/20260717T005149Z-ai-gauntlet-smoke-d88c183c-0000-standard_skeleton_doors.json`;
- outcome: heroes win, `11` accepted commands, `0` rejected/stale/error;
- subjectivity: passed, `0` violations;
- gate: passed;
- latency: failed, with `command_total_p95_ms == 93.883` and
  `normal_command_total_p95_ms == 46.752`;
- local decision remains under target, with
  `normal_local_decision_p99_ms == 4.649`.

Interpretation: local policy/fact work is inside the current target, but
server-command and follow-up epoch costs still dominate. The next speed pass
should not chase policy micro-optimizations first; it should inspect command
HTTP/validation, engine execution, follow-up frame publication, and epoch
generation around high-surface actions.

Focused proof:

- `uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "dominant_durable_setup or dominated_pursuit or dense_spacing_epoch or footprint_limited_propagation_reuses_identical_candidate_filters"`
  - passed, `4 passed, 54 deselected`
- `uv run pytest tests/manual/test_31_subjective_runtime_epochs.py -q -k "row_descriptor_cache or epoch_bindings_preserve_exact_duplicate_named_action_sources or epoch_row_id_falls_back_to_semantic_key_not_display_name"`
  - passed, `3 passed, 40 deselected`
- `uv run pyright ai/subjective/epochs.py tests/manual/test_31_subjective_runtime_epochs.py tests/manual/test_43_ai_runtime_performance.py`
  - 0 errors
- `uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id standard_skeleton_doors --seed 707`
  - retained summary and raw run above
- `uv run python -m ai.evaluation.gauntlet_runner check ai/evidence/gauntlets/latest.json --require-gate-pass`
  - passed

## 2026-07-16 - Gauntlet Latency Audit Split

Separated correctness/release cleanliness from speed compliance in retained
gauntlet summaries. `gate_status` still describes whether a batch is clean of
failed, stale, missing, leaked, or pending matches. New latency fields describe
whether the retained timing evidence meets the current interactive target:

- `latency_status`
- `latency_reasons`
- `latency_thresholds`

The audit currently checks retained max command total against `10.0 ms` and max
local decision against `5.0 ms`. This is intentionally conservative because the
compact summary retains maxima, not full p95/p99 distributions. It keeps the
goal honest: a gauntlet can be release-clean for correctness while still failing
speed.

Wired the audit through:

- summary construction and writing;
- retained `gauntlet_runner check`;
- regression-source loading;
- `/ai/gauntlets/latest`;
- `/ai/gauntlets/{gauntlet_id}/watch`;
- the static gauntlet watcher latency card;
- README documentation.

The current latest retained release remains correctness-clean but not yet fast
enough:

- `gauntlet_id`: `20260716T204237Z-ai-gauntlet-release-3474e7a7`
- `gate_status`: `passed`
- `latency_status`: `failed`
- `latency_reasons`: `["command_total_over_10ms", "local_decision_over_5ms"]`
- thresholds: `{"max_command_total_ms": 10.0, "max_local_decision_ms": 5.0}`

Focused proof:

- `uv run pytest tests/manual/test_54_ai_gauntlet_watcher.py tests/manual/test_56_gauntlet_runner_cli.py tests/manual/test_57_gauntlet_watcher_html.py tests/manual/test_58_ai_runtime_readme.py -q`
  - passed, `31 passed`
- `uv run pytest tests/manual/test_55_gauntlet_live_watcher_server.py -q`
  - passed, `8 passed`, `1 warning`
- `uv run pyright ai/evaluation/gauntlet_contract.py ai/evaluation/gauntlet.py ai/evaluation/gauntlet_runner.py server/event_server.py tests/manual/test_54_ai_gauntlet_watcher.py tests/manual/test_56_gauntlet_runner_cli.py tests/manual/test_57_gauntlet_watcher_html.py tests/manual/test_58_ai_runtime_readme.py`
  - passed, `0 errors`
- `awk '/<script>/{flag=1;next}/<\\/script>/{flag=0}flag' ai/AI_TOURNAMENT_MONITOR.html | node --check -`
  - passed
- `uv run python -m ai.evaluation.gauntlet_runner check ai/evidence/gauntlets/latest.json --require-gate-pass`
  - passed with `latency_status: failed`
- `uv run python -m ai.evaluation.gauntlet_runner check ai/evidence/gauntlets/latest.json --require-gate-pass --require-latency-pass`
  - exited `3`, proving strict speed automation currently fails as expected

## 2026-07-16 - Percentile Latency Evidence In Gauntlet Summaries

Improved the latency audit from max-only evidence toward the formal target in
the goal. Match records now retain per-command timing samples for:

- total command time;
- server command time;
- local decision time.

They also compute nearest-rank p95 and p99 per match. Gauntlet performance
summaries aggregate the retained samples across the batch and expose:

- `command_total_sample_count`;
- `command_total_p95_ms`, `command_total_p99_ms`, `max_command_total_ms`;
- `server_command_p95_ms`, `server_command_p99_ms`, `max_server_command_ms`;
- `local_decision_p95_ms`, `local_decision_p99_ms`, `max_local_decision_ms`.

The latency audit now checks the goal-shaped targets where samples exist:

- command-total p95 <= `5.0 ms`;
- command-total p99 <= `10.0 ms`;
- local-decision p99 <= `5.0 ms`.

Legacy retained summaries without sample/percentile fields still use the older
max fallback, which keeps old JSON readable without fabricating percentiles.

No-file smoke proof with the new summary shape:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id standard_skeleton_doors --seed 707 --no-run-artifacts --no-summary-file --require-gate-pass
```

Result:

- `gauntlet_id`: `20260716T213210Z-ai-gauntlet-smoke-17294481`
- `gate_status`: `passed`
- `latency_status`: `failed`
- `latency_reasons`: `["command_total_p95_over_5ms", "command_total_p99_over_10ms"]`
- `command_status_counts`: `{"accepted": 11}`
- sample counts: command/server/local `11 / 11 / 11`
- command p95/p99/max: `85.808 / 85.808 / 85.808 ms`
- server p95/p99/max: `47.605 / 47.605 / 47.605 ms`
- local p95/p99/max: `4.727 / 4.727 / 4.727 ms`

This is strong evidence that the current local policy path is under the
local-decision target for this smoke slice, while the command/server path is
still far above the total command target.

Focused proof:

- `uv run pytest tests/manual/test_52_ai_tournament_elo.py tests/manual/test_54_ai_gauntlet_watcher.py tests/manual/test_55_gauntlet_live_watcher_server.py tests/manual/test_56_gauntlet_runner_cli.py tests/manual/test_57_gauntlet_watcher_html.py tests/manual/test_58_ai_runtime_readme.py -q`
  - passed, `42 passed`, `1 warning`
- `uv run pyright ai/evaluation/tournament.py ai/evaluation/gauntlet_contract.py ai/evaluation/gauntlet.py ai/evaluation/gauntlet_runner.py server/event_server.py tests/manual/test_52_ai_tournament_elo.py tests/manual/test_54_ai_gauntlet_watcher.py tests/manual/test_55_gauntlet_live_watcher_server.py tests/manual/test_56_gauntlet_runner_cli.py tests/manual/test_57_gauntlet_watcher_html.py tests/manual/test_58_ai_runtime_readme.py`
  - passed, `0 errors`
- `awk '/<script>/{flag=1;next}/<\\/script>/{flag=0}flag' ai/AI_TOURNAMENT_MONITOR.html | node --check -`
  - passed
- `uv run pytest tests/manual/test_46_ai_dashboard_projection.py -q`
  - passed, `5 passed` in `127.13s`

## 2026-07-16 - Agent Observer Retained History Metadata Validation

Tightened the retained agent-telemetry projection contract. Raw legacy rows can
still be normalized into `AgentEventHistoryResponse`, but a payload that claims
to be a full cursor-addressed history must now keep honest metadata:

- `count` must match the number of retained rows;
- agent cursors must be positive, unique, and ordered;
- `next_agent_cursor` must describe the final returned row;
- `total` and `earliest_agent_cursor` must not contradict the retained rows.

This prevents malformed direct-Codex or agent-event artifacts from being
silently recomputed into a clean-looking observer history. The observer and
future watcher tooling should preserve bad evidence as bad evidence, not make
it look release-clean.

Focused proof:

- `uv run pytest tests/manual/test_60_agent_observer_projection.py -q`
  - passed, `7 passed`
- `uv run pytest tests/manual/test_59_agent_observer_html.py tests/manual/test_58_ai_runtime_readme.py -q`
  - passed, `6 passed`
- `uv run pyright ai/evaluation/agent_observer_projection.py tests/manual/test_60_agent_observer_projection.py`
  - passed, `0 errors`
- `awk '/<script>/{flag=1;next}/<\\/script>/{flag=0}flag' ai/AI_AGENT_OBSERVER.html | node --check -`
  - passed

## 2026-07-16 - Agent Observer Browser Metadata Validation

Mirrored the strict retained-history validation in the browser observer. The
static `ai/AI_AGENT_OBSERVER.html` artifact loader now distinguishes raw legacy
rows from full `AgentEventHistoryResponse`-shaped envelopes. Raw rows can still
be normalized for replay, but a history envelope with `count`, `total`,
`next_agent_cursor`, `earliest_agent_cursor`, or `resync_required` must keep
metadata consistent with the retained rows before anything is rendered.

This closes a UI evidence gap: the Python projection helper and browser
observer now agree that malformed retained telemetry should stay visibly bad
instead of being silently recomputed into a clean-looking stream.

Focused proof:

- `uv run pytest tests/manual/test_59_agent_observer_html.py tests/manual/test_60_agent_observer_projection.py tests/manual/test_58_ai_runtime_readme.py -q`
  - passed, `14 passed`
- `uv run pyright ai/evaluation/agent_observer_projection.py tests/manual/test_60_agent_observer_projection.py`
  - passed, `0 errors`
- `awk '/<script>/{flag=1;next}/<\\/script>/{flag=0}flag' ai/AI_AGENT_OBSERVER.html | node --check -`
  - passed

## 2026-07-16 - Agent Observer Decision Panels

Improved `ai/AI_AGENT_OBSERVER.html` from a raw telemetry row browser into a
first-pass decision review surface. It still consumes only `AgentEventPayload`
history/SSE data, but now derives local panels for:

- latest selected command;
- latest shared-policy decision;
- top candidate rows from decision telemetry;
- recent command flow across submitted, ack, stream-result, and external result
  events;
- latest subjective command timing breakdown.

The raw payload panel remains available for full inspection. No new gameplay
authority, objective state fetch, visibility fetch, or legal-action polling was
added.

Focused proof:

- `uv run pytest tests/manual/test_59_agent_observer_html.py -q`
  - passed, `4 passed`
- `uv run pytest tests/manual/test_58_ai_runtime_readme.py -q`
  - passed, `1 passed`
- `awk '/<script>/{flag=1;next}/<\\/script>/{flag=0}flag' ai/AI_AGENT_OBSERVER.html | node --check -`
  - passed

## 2026-07-16 - Retained Agent Telemetry Projection Contract

Added `ai.evaluation.agent_observer_projection` as the Python-side contract for
the agent observer's retained JSON inputs. It normalizes:

- direct-Codex artifacts with `agent_events_response.events`;
- retained histories under `agent_events.events` or `agent_event_history.events`;
- raw arrays of agent event rows;

into `AgentEventHistoryResponse`, the same envelope shape used by the live
agent-event stream. This keeps retained artifact review aligned with live
telemetry instead of inventing another dashboard-specific parser.

The projection stays telemetry-only. It rejects retained payloads with no agent
telemetry and does not derive map state, visibility, HP, routes, or legal
actions.

Focused proof:

- `uv run pytest tests/manual/test_60_agent_observer_projection.py -q`
  - passed, `3 passed`
- `uv run pytest tests/manual/test_59_agent_observer_html.py tests/manual/test_58_ai_runtime_readme.py -q`
  - passed, `6 passed`
- `uv run pyright ai/evaluation/agent_observer_projection.py tests/manual/test_60_agent_observer_projection.py`
  - passed, `0 errors`
- `awk '/<script>/{flag=1;next}/<\\/script>/{flag=0}flag' ai/AI_AGENT_OBSERVER.html | node --check -`
  - passed

## 2026-07-16 - Agent Observer Retained Artifact Replay

Extended `ai/AI_AGENT_OBSERVER.html` so the same decision/command panels can be
used against retained JSON evidence, not only live server sessions. The observer
now accepts a local JSON artifact and extracts agent telemetry rows from:

- `agent_events_response.events`;
- `agent_events.events`;
- `agent_event_history.events`;
- raw arrays of agent event rows.

Loaded rows pass through the same local rendering path as live SSE
`AgentEventPayload`s. The feature remains telemetry-only: it does not replay map
state, request objective state, request visibility, or poll legal actions.

Focused proof:

- `uv run pytest tests/manual/test_59_agent_observer_html.py -q`
  - passed, `5 passed`
- `uv run pytest tests/manual/test_58_ai_runtime_readme.py -q`
  - passed, `1 passed`
- `awk '/<script>/{flag=1;next}/<\\/script>/{flag=0}flag' ai/AI_AGENT_OBSERVER.html | node --check -`
  - passed

## 2026-07-16 - Agent Telemetry Observer Surface

Added a lightweight static per-session observer at `ai/AI_AGENT_OBSERVER.html`.
It complements the gauntlet watcher: the gauntlet watcher tracks batch progress
and retained results, while the agent observer follows one AI session's
telemetry stream.

The observer consumes only the agent-event contract:

- `GET /ai/sessions/{session_id}/agent-events?since=<cursor>&limit=<n>`
- `GET /ai/sessions/{session_id}/agent-events/subscribe?since=<cursor>`

It renders agent cursor, observation cursor, epoch id, event type, level,
source, actor, summary, tags, counts by event type, and selected structured
payload. It intentionally does not fetch objective state, raw visibility, or
debug legal-action polling surfaces.

Documentation:

- Added the `Agent Observer` section to `ai/readme.md`.

Focused proof:

- `uv run pytest tests/manual/test_59_agent_observer_html.py -q`
  - passed, `3 passed`
- `uv run pytest tests/manual/test_58_ai_runtime_readme.py -q`
  - passed, `1 passed`

## 2026-07-16 - Agent Observer Session Index

Made the per-session observer usable without manually discovering session ids.
The backend now exposes `GET /ai/sessions`, a read-only AI/Codex observer index.
Rows include session identity, connection status, owned entity labels,
controller labels, telemetry cursors, observation cursor, cached epoch id, and
takeover claim ids.

The endpoint intentionally omits tactical state: no HP, positions, opponents,
raw visibility, routes, legal-action rows, or hidden facts. This keeps the
observer aligned with the subjective/debugging contract instead of turning it
into an objective state shortcut.

Updated `ai/AI_AGENT_OBSERVER.html` with a session picker that loads
`GET /ai/sessions`, fills the selected session id, and still replays telemetry
from cursor `0` so retained history is not skipped.

Focused proof:

- `uv run pytest tests/manual/test_59_agent_observer_html.py -q`
  - passed, `3 passed`
- `uv run pytest tests/manual/test_34_agent_event_stream.py -q`
  - passed, `11 passed`, `1 warning`
- `uv run pyright server/api_models.py server/event_server.py tests/manual/test_34_agent_event_stream.py tests/manual/test_59_agent_observer_html.py`
  - passed, `0 errors`
- `uv run pytest tests/manual/test_58_ai_runtime_readme.py -q`
  - passed, `1 passed`

## 2026-07-16 - Command Row IDs Do Not Use Display Labels

Tightened decision-epoch command identity. When an engine action row has no
template name, row ID construction now falls back to `base_template_name` and
then `semantic_key`, not `display_name`.

This keeps localized or player-facing labels out of command identity. Display
names still render for humans, but policy, command binding, replay, and
duplicate disambiguation use stable action-family data plus the selected target.

Focused proof:

- Added `test_epoch_row_id_falls_back_to_semantic_key_not_display_name`.
- `uv run pytest tests/manual/test_31_subjective_runtime_epochs.py -q`
  - passed, `41 passed`
- `uv run pyright ai/subjective/epochs.py tests/manual/test_31_subjective_runtime_epochs.py`
  - 0 errors

## 2026-07-16 - Gauntlet Summaries Preserve Server Command Timing

The retained run artifacts already contained per-command `server_timing`
payloads, but older compact gauntlet summaries could show
`max_server_command_ms: null`. Strengthened the watcher/runner contracts so
server timing must survive from trace evidence into `MATCH_PROGRESS`, match
records, performance summaries, and retained `latest.json` output.

Focused proof:

- Extended `test_runner_can_publish_directly_to_server_live_stream` with a
  traced `server_timing.total_ms` sample and assertions on the event payload,
  match record, and gauntlet performance summary.
- Extended `test_gauntlet_runner_run_writes_raw_artifacts_and_latest_summary`
  with traced timing and assertions on compact retained output.
- `uv run pytest tests/manual/test_55_gauntlet_live_watcher_server.py tests/manual/test_56_gauntlet_runner_cli.py -q`
  - passed, `17 passed`
- `uv run pyright tests/manual/test_55_gauntlet_live_watcher_server.py tests/manual/test_56_gauntlet_runner_cli.py ai/evaluation/tournament.py ai/evaluation/gauntlet.py`
  - 0 errors

Real no-file smoke check:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id standard_skeleton_doors --seed 707 --no-run-artifacts --no-summary-file --require-gate-pass
```

Result:

- `gauntlet_id`: `20260716T203918Z-ai-gauntlet-smoke-92ed68a1`
- `gate_status`: `passed`
- `command_status_counts`: `{"accepted": 11}`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- `max_command_total_ms`: `91.313`
- `max_server_command_ms`: `50.833`
- `max_local_decision_ms`: `4.631`

## 2026-07-16 - Fresh Retained Rotation And Release Gauntlet Evidence

Refreshed retained gauntlet evidence with the current timing contract. The
older retained summaries passed tactically but had compact
`max_server_command_ms: null` values. New retained summaries now carry
server-command timing through match rows, performance summaries, watcher
projection, and the static `latest.json` path.

Fresh retained rotations:

- `20260716T204133Z-ai-gauntlet-rotation-6a096a85`
  - passed, 6 completed, 0 failed, `{"accepted": 100}`
  - subjectivity passed, 0 violations
  - max command/server/local ms: `101.498` / `56.27` / `5.085`
- `20260716T204211Z-ai-gauntlet-rotation-6e91220c`
  - passed, 6 completed, 0 failed, `{"accepted": 100}`
  - subjectivity passed, 0 violations
  - max command/server/local ms: `97.197` / `56.928` / `5.225`
- `20260716T204211Z-ai-gauntlet-rotation-7191632f`
  - passed, 6 completed, 0 failed, `{"accepted": 100}`
  - subjectivity passed, 0 violations
  - max command/server/local ms: `98.224` / `55.518` / `5.413`

Fresh retained release gauntlet:

- `20260716T204237Z-ai-gauntlet-release-3474e7a7`
  - passed, 12 completed, 0 failed, `{"accepted": 706}`
  - subjectivity passed, 0 violations
  - max command/server/local ms: `92.365` / `65.978` / `5.139`

Latency notes:

- The repeated local-decision max outliers are small, isolated samples just over
  the 5 ms target.
- Rotation outliers came from `Validation Sorcerer` executing the semantic
  capability-transformation branch: policy `3.436-4.476 ms`, fact derivation
  `0.937-1.649 ms`, with large position-action surfaces up to 416 rows.
- Release outliers came from `Validation SRD Patrol Archer` selecting visible
  soft control: policy `3.7-3.947 ms`, fact derivation `1.192-1.426 ms`, with
  334-335 position rows.
- Server maxima are dominated by engine execution and follow-up epoch/action
  discovery: standard-door rotations spend most of the top command in
  `execute.action_by_index_ms`, `publish.followup_epoch.build_decision_epoch_total_ms`,
  and `available_actions.collect_aoe_actions_ms`; the release max is an undead
  crypt movement/action execution spike.

Dashboard projection:

- Regenerated `ai/AGENT_UX_ITERATION_STATS.json` from retained JSON.
- Projection now contains 295 artifact-backed runs: 180 autonomous runs and 115
  direct-Codex runs.

Focused proof:

- `uv run python -m ai.evaluation.gauntlet_runner check ai/evidence/gauntlets/latest.json --require-gate-pass`
  - passed; latest is `20260716T204237Z-ai-gauntlet-release-3474e7a7`
- `uv run python -m ai.evaluation.dashboard_projection`
  - projected 295 artifact-backed dashboard runs
- `uv run pytest tests/manual/test_46_ai_dashboard_projection.py -q`
  - passed, `5 passed`
- `uv run python -m json.tool ai/AGENT_UX_ITERATION_STATS.json > /tmp/dnd_ai_stats_after_gauntlet_refresh.json`
  - valid JSON
- `uv run pytest tests/manual/test_55_gauntlet_live_watcher_server.py tests/manual/test_56_gauntlet_runner_cli.py -q`
  - passed, `17 passed`

## 2026-07-16 - Watcher Null-Vs-Zero Audit Semantics

Tightened the gauntlet watcher evidence rendering so retained zero values are
not treated as missing values. Audit metrics now use nullish fallbacks for
subjectivity violations, stale/rejected counts, failure counts, pending counts,
and command latency fields.

This matters for release evidence: `0` stale commands, `0` subjectivity
violations, and `0.0` command latency samples are real data. They should not be
replaced by fallback aggregates or `n/a`.

Focused proof:

- `uv run pytest tests/manual/test_57_gauntlet_watcher_html.py -q`
  - passed, `2 passed`
- `uv run pytest tests/manual/test_58_ai_runtime_readme.py -q`
  - passed, `1 passed`

## 2026-07-16 - Production And Diagnostic Latency Split

Promoted the timing split that already existed in raw self-play artifacts into
the compact tournament and gauntlet summaries. Match records and batch
performance summaries now retain:

- all command/server/local latency samples;
- non-diagnostic production command/server/local samples;
- diagnostic-probe command/server/local samples.

The latency audit now prefers production percentiles when non-diagnostic
samples exist, then falls back to all-sample percentiles and legacy max fields
for older retained summaries. Diagnostic probes remain visible in watcher JSON
and the static monitor, but they no longer by themselves fail the production
responsiveness gate.

Focused proof:

- `uv run pytest tests/manual/test_52_ai_tournament_elo.py tests/manual/test_54_ai_gauntlet_watcher.py tests/manual/test_56_gauntlet_runner_cli.py tests/manual/test_57_gauntlet_watcher_html.py tests/manual/test_58_ai_runtime_readme.py -q`
  - passed, `36 passed`
- `uv run pyright ai/evaluation/tournament.py ai/evaluation/gauntlet_contract.py ai/evaluation/gauntlet.py tests/manual/test_52_ai_tournament_elo.py tests/manual/test_54_ai_gauntlet_watcher.py tests/manual/test_56_gauntlet_runner_cli.py`
  - 0 errors
- `awk '/<script>/{flag=1;next}/<\\/script>/{flag=0}flag' ai/AI_TOURNAMENT_MONITOR.html | node --check -`
  - passed

Real no-file smoke check:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id standard_skeleton_doors --seed 707 --no-run-artifacts --no-summary-file --require-gate-pass
```

Result:

- `gauntlet_id`: `20260716T214840Z-ai-gauntlet-smoke-1c8e5b07`
- `gate_status`: `passed`
- `latency_status`: `failed`
- `latency_reasons`: `["command_total_p95_over_5ms", "command_total_p99_over_10ms"]`
- total command samples: `11`
- production command samples: `9`
- diagnostic command samples: `2`
- all command p95/p99/max ms: `87.422` / `87.422` / `87.422`
- production command p95/p99/max ms: `56.681` / `56.681` / `56.681`
- diagnostic command p95/p99/max ms: `87.422` / `87.422` / `87.422`
- production local-decision p99/max ms: `4.82` / `4.82`

Follow-up diagnostic run on the same seed:

- normal command total p95/p99/max ms: `65.685` / `65.685` / `65.685`
- normal server p95/p99/max ms: `49.449` / `49.449` / `49.449`
- normal local p95/p99/max ms: `4.746` / `4.746` / `4.746`
- slowest normal command: Validation Sorcerer `cast_visible_area_spell`
  - total `65.685 ms`, server `49.449 ms`, local `3.06 ms`
  - dominant server phase: `execute.action_by_index_ms = 40.497 ms`
  - follow-up epoch publication: `8.787 ms`, mostly
    `build_decision_epoch_total_ms = 8.558 ms`
- next server-bound outliers were follow-up epoch rebuilds around `10-18 ms`
  and one end-turn handoff with `build_decision_epoch_total_ms = 17.835 ms`.

Conclusion: the policy/runtime local path is now within the local 5 ms p99
target on this smoke, but the end-to-end command budget still fails on server
execution and follow-up epoch construction. The next optimization target should
therefore be the server action execution/epoch rebuild path, not another policy
selector tweak.

## 2026-07-16 - Fireball Save Log Hot Path Split

Continued the server latency pass from the diagnostic trace. The slow
`standard_skeleton_doors` seed showed two distinct remaining classes of
outlier:

- reveal-boundary movement, dominated by sensory updates, movement light
  propagation, and subjective projection;
- Fireball execution, previously mostly opaque inside
  `base_action.convolution_target_apply_ms`.

Added Fireball-specific action timing around entity resolution, save DC,
saving-throw request construction, saving throw resolution, effect event,
damage roll, damage application, and completion event. Also removed one
duplicate save-bonus rebuild from the spell summary log path. The actual
saving throw child log still owns detailed modifier/advantage breakdowns; the
spell summary keeps the resolved roll, bonus, total, success, and damage fields
without recomputing the same modifier stack.

Focused proof:

- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py tests/manual/test_43_ai_runtime_performance.py -q -k "position_aoe_action_lifecycle_timing or fireball_uses_resolved_save_roll_bonus"`
  - passed, `2 passed, 75 deselected`
- `uv run pytest tests/manual/test_14_spell_families.py tests/engine_book/test_chapter_15_spell_families.py -q -k "save or Fireball or fireball or Hold_Person or Hold_Monster or hold_person or hold_monster"`
  - passed, `9 passed, 51 deselected`
- `uv run pyright dnd/actions.py dnd/spells/evocation.py tests/manual/test_43_ai_runtime_performance.py`
  - 0 errors

Targeted pyright over `tests/manual/test_36_seamless_subjective_runtime.py`
still reports pre-existing fake-request/stream typing errors unrelated to this
change, so the type check above covered the edited runtime files and the new
latency contract.

Diagnostic replay on `standard_skeleton_doors`, seed `707`, first four
commands:

- Fireball command total improved from the previous diagnostic range around
  `63.815 ms` to `48.215 ms`.
- Fireball `execute_by_index_ms` improved from `38.472 ms` to `26.641 ms`.
- New inner Fireball timings show the remaining spell cost:
  - `spell.fireball.receive_damage_ms`: `12.380 ms`;
  - `spell.fireball.saving_throw_ms`: `6.067 ms`;
  - `spell.fireball.effect_event_ms`: `3.211 ms`;
  - subjective projection around damage/death/condition frames remains about
    `4.929 ms`.
- Reveal movement remains the larger diagnostic outlier:
  - command total `91.010 ms`;
  - movement `execute_by_index_ms`: `26.458 ms`;
  - `SpatialSensesSystem`: `15.596 ms`;
  - movement light publish: `7.827 ms`;
  - sensory-update projection: about `5.013 ms`.

Real no-file smoke check:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id standard_skeleton_doors --seed 707 --no-run-artifacts --no-summary-file --require-gate-pass
```

Result:

- `gauntlet_id`: `20260716T221138Z-ai-gauntlet-smoke-45f42125`
- `gate_status`: `passed`
- `latency_status`: `failed`
- `latency_reasons`: `["command_total_p95_over_5ms", "command_total_p99_over_10ms"]`
- production command p95/p99/max ms: `46.193` / `46.193` / `46.193`
- production server p95/p99/max ms: `38.095` / `38.095` / `38.095`
- production local-decision p99/max ms: `4.775` / `4.775`

Conclusion: this was a real but partial improvement. The local decision target
still holds; correctness and subjectivity gates still pass. The next latency
target is movement/reveal-boundary sensory work and the remaining
`receive_damage`/projection cost, not action-selection policy.

## 2026-07-16 - Dense Sensory Tile Patch Batching

Continued the reveal-boundary latency pass without changing subjective data
semantics. The observation stream previously emitted one `tile` patch per
visible/seen cell in dense sensory updates. That preserved correctness but
created extra patch models and JSON payload entries exactly where light/movement
reveals are already expensive.

Changed sensory projection to batch multiple tile facts inside one
`ObservationPatchType.TILE` payload:

- single-tile updates keep the existing `{"tile": ...}` shape;
- multi-tile updates use `{"tiles": [...]}`;
- the materializer accepts both forms;
- tile facts are still generated from the same session-subjective visible/seen
  data and replay into the same `known_tiles` map.

Focused proof:

- `uv run pytest tests/manual/test_28_subjective_observation_stream.py -q -k "dense_sensory_tile_updates_are_batched_and_replayable"`
  - passed, `1 passed, 41 deselected`
- `uv run pytest tests/manual/test_28_subjective_observation_stream.py tests/manual/test_32_subjective_runtime_store.py -q -k "sensory or snapshot_plus_frames or visible_lever_charge or store_loads_snapshot or store_owns_one_typed_subjective_world or cursor_gap"`
  - passed, `11 passed, 40 deselected`
- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q -k "position_aoe_action_lifecycle_timing or execute_does_not_fetch_snapshot or runtime_waits_for_matching_command_result or duplicate_frames"`
  - passed, `1 passed, 36 deselected`
- `uv run pyright ai/observation/projector.py ai/observation/materializer.py tests/manual/test_28_subjective_observation_stream.py`
  - 0 errors

Diagnostic replay on `standard_skeleton_doors`, seed `707`, first four
commands:

- first reveal move command total: about `101.550 ms` in the diagnostic run;
- movement action server total: `29.459 ms`;
- `movement.update_position_ms`: `22.144 ms`;
- `SpatialSensesSystem`: `16.981 ms`;
- movement light publish: `8.354 ms`;
- subjective event projection: `5.624 ms`;
- sensory tile patch build split:
  - visible tile patches: `2.307 ms`;
  - removed/remembered tile patches: `1.531 ms`.

Real no-file smoke check:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id standard_skeleton_doors --seed 707 --no-run-artifacts --no-summary-file --require-gate-pass
```

Result:

- `gauntlet_id`: `20260716T222352Z-ai-gauntlet-smoke-91439612`
- `gate_status`: `passed`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- command statuses: `11 accepted`
- `latency_status`: `failed`
- `latency_reasons`: `["command_total_p95_over_5ms", "command_total_p99_over_10ms"]`
- production command p95/p99/max ms: `46.397` / `46.397` / `46.397`
- production server p95/p99/max ms: `37.490` / `37.490` / `37.490`
- production local-decision p99/max ms: `4.851` / `4.851`

Conclusion: batching reduces transport overhead and keeps replay exact, but it
does not solve the main remaining latency gate. The next systemic target is the
movement-light/sensory recomputation boundary and follow-up decision-epoch
generation, especially `SpatialSensesSystem`, `grid.move_light_source`, and
post-command `get_available_actions`/AoE affordance generation.

## 2026-07-16 - Light Refresh Pruning And AoE Origin FOV Cache

Continued the same latency investigation with two conservative changes:

- light-change sensory updates now skip visibility refiltering for subscribed
  positions that remain lit and already visible;
- entity AoE discovery now keeps a propagation-FOV cache keyed by map
  propagation revision, so preview/footprint cache invalidation does not
  necessarily force grid propagation recomputation for the same AoE origins.

The light change preserves the rule currently implemented by the engine:
visibility changes only at the darkness/lit boundary. Dim-to-bright and
bright-to-dim changes do not make new entities or objects visible under the
current senses rules, so those positions do not need entity/object churn. A
reactive darkness-to-light reveal still emits one subjective sensory update
with both the visible cell and revealed target.

Focused proof:

- `uv run pytest tests/manual/test_28_subjective_observation_stream.py -q -k "lit_to_lit_light_changes_do_not_refilter_visible_occupants or dense_sensory_tile_updates_are_batched_and_replayable"`
  - passed, `2 passed, 41 deselected`
- `uv run pytest tests/manual/test_28_subjective_observation_stream.py -q -k "sensory or light_changes or dense_sensory or snapshot_plus_frames or visible_lever_charge"`
  - passed, `9 passed, 34 deselected`
- `uv run pytest tests/manual/test_12_perception_light_stealth_and_invisibility.py -q -k "light or visibility or senses"`
  - passed, `10 passed`
- `uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "aoe_shape_definition_is_not_serialized_per_candidate_cell or aoe_origin_fov_cache_survives_preview_cache_invalidation or fireball_uses_resolved_save_roll_bonus"`
  - passed, `3 passed, 38 deselected`
- `uv run pyright dnd/entity.py dnd/blocks/sensory.py tests/manual/test_43_ai_runtime_performance.py tests/manual/test_28_subjective_observation_stream.py tests/manual/test_12_perception_light_stealth_and_invisibility.py`
  - 0 errors

Diagnostic replay on `standard_skeleton_doors`, seed `707`, first four
commands:

- first reveal move total: `92.406 ms`;
- first reveal move `execute_by_index_ms`: `25.941 ms`;
- first reveal move `movement.update_position_ms`: `20.071 ms`;
- `SpatialSensesSystem`: `15.151 ms`;
- moving-light publish: `7.424 ms`;
- follow-up epoch `get_available_actions_ms`: `17.228 ms`;
- follow-up epoch `collect_aoe_actions_ms`: `12.041 ms`;
- AoE footprint first misses remain expensive: `7.960 ms`;
- Fireball total: `56.065 ms`, still dominated by `receive_damage_ms`
  (`12.987 ms`) and `saving_throw_ms` (`7.260 ms`).

Real no-file smoke check:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id standard_skeleton_doors --seed 707 --no-run-artifacts --no-summary-file --require-gate-pass
```

Result:

- `gauntlet_id`: `20260716T223440Z-ai-gauntlet-smoke-ea8d9372`
- `gate_status`: `passed`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- command statuses: `11 accepted`
- `latency_status`: `failed`
- `latency_reasons`: `["command_total_p95_over_5ms", "command_total_p99_over_10ms", "local_decision_p99_over_5ms"]`
- production command p95/p99/max ms: `52.675` / `52.675` / `52.675`
- production server p95/p99/max ms: `39.494` / `39.494` / `39.494`
- production local-decision p99/max ms: `5.512` / `5.512`

Conclusion: these changes are correct and reduce avoidable duplicate work, but
the formal latency gate still fails. The next speed work should target either
first-miss AoE footprint generation, per-step movement sensory publication, or
Fireball damage/save application internals. The local decision p99 can also
still drift over 5 ms in smoke, so policy/fact derivation needs continued
watching even though the dominant cost is still server-side.

## 2026-07-17 - Static Geometry Cache Follow-Up

Added a conservative pure-geometry cache for repeated AoE and line helpers:

- `circle_positions()` now translates cached relative circle offsets;
- `rectangle_positions()` now translates cached centered/directional offsets;
- `supercover_line()` now copies from a bounded immutable cached line result;
- directional FOV now compares squared distance instead of computing square
  roots for every candidate cell.

Focused proof:

- `uv run pyright dnd/core/geometry.py dnd/core/gridmap.py tests/manual/test_43_ai_runtime_performance.py`
  - 0 errors
- `uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "static_aoe_geometry_reuses_relative_offset_caches or supercover_line_reuses_immutable_geometry_cache or aoe_origin_fov_cache_survives_preview_cache_invalidation or directional_aoe_discovery_compacts_duplicate_target_rays or light_batch_candidate_selection_uses_bulk_subscriber_union"`
  - passed, `5 passed, 42 deselected`
- `uv run pytest tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py -q -k "geometry_and_aoe_are_grid_aware_where_needed or zone_control_cone_and_line_use_directional_geometry or cylinder_subjective_preview_matches_targeting_footprint"`
  - passed, `3 passed, 20 deselected`

Diagnostic note:

- repeated same-process diagnostics show warm-cache improvement in directional
  FOV line work, but the first cold decision command remains dominated by
  server-side action execution and follow-up epoch generation;
- this is a safe cleanup and repeated-gauntlet helper, not a formal latency-gate
  fix.

Real no-file smoke check:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id standard_skeleton_doors --seed 707 --no-run-artifacts --no-summary-file
```

Result:

- `gauntlet_id`: `20260716T231957Z-ai-gauntlet-smoke-1ab25d3b`
- `gate_status`: `passed`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- command statuses: `11 accepted`
- `latency_status`: `failed`
- `latency_reasons`: `["command_total_p95_over_5ms", "command_total_p99_over_10ms"]`
- production command p95/p99 ms: `50.582` / `50.582`
- production server command p99 ms: `36.660`
- production local decision p99 ms: `4.432`
- diagnostic command p99 ms: `99.168`
- diagnostic server command p99 ms: `54.337`

Conclusion: correctness remains clean, and local policy/fact derivation stayed
under the 5 ms p99 target in this smoke. The remaining latency failure is still
server dominated. The next systemic target should be follow-up decision-epoch
construction after commands, especially available-action/AoE affordance work,
because that path is hit on every multi-action turn and directly determines
epoch-to-command responsiveness.

## 2026-07-17 - Self-Play Store Reuse For Hot Epochs

Removed one harness-side polling artifact from `external_selfplay`: if the
local subjective store already contains the active actor's current epoch, the
self-play loop now reuses it instead of issuing an empty pre-command
`/observation/frames` request. If the cached epoch is missing or belongs to a
different actor, the harness still catches up before policy evaluation.

This does not change gameplay rules, subjectivity, or command execution. It
makes the validation harness closer to the intended hot-stream runtime: after a
command follow-up has already materialized the next epoch, the next same-turn
decision can act from local state.

Focused proof:

- `uv run pyright ai/external_selfplay.py tests/manual/test_43_ai_runtime_performance.py`
  - 0 errors
- `uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "selfplay_reuses_current_epoch_without_empty_pre_command_fetch or selfplay_catches_up_when_cached_epoch_is_stale"`
  - passed, `2 passed, 47 deselected`

Retained smoke:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id standard_skeleton_doors --seed 707
```

Result:

- `gauntlet_id`: `20260716T232537Z-ai-gauntlet-smoke-d2839d39`
- retained artifact:
  `ai/evidence/runs/20260716T232537Z-ai-gauntlet-smoke-d2839d39-0000-standard_skeleton_doors.json`
- `gate_status`: `passed`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- command statuses: `11 accepted`
- `latency_status`: `failed`
- `latency_reasons`: `["command_total_p95_over_5ms", "command_total_p99_over_10ms"]`
- production command p95/p99 ms: `50.732` / `50.732`
- production server command p99 ms: `37.815`
- production local decision p99 ms: `4.370`
- diagnostic command p99 ms: `98.640`
- diagnostic server command p99 ms: `55.559`

Trace effect:

- same-turn `pre_command_frame_fetch_ms` is now `0.0` for the inspected early
  command sequence;
- production local decision p99 moved back under the 5 ms target;
- total command latency still fails because the dominant remaining work is
  server-side command execution plus follow-up epoch generation.

Conclusion: the client/harness side is now less noisy and closer to the hot
subjective runtime model. The next latency target remains the authoritative
server path, especially movement/spell execution and follow-up
`build_decision_epoch -> get_available_actions -> collect_aoe_actions`.

## 2026-07-17 - Directional FOV Uses Relative Ray Offsets

Moved directional FOV ray traversal from translated absolute line lists to
cached relative supercover offsets. This preserves the same line-of-effect,
transition, and blocker checks, but avoids rebuilding or allocating a full
absolute path for every translated ray during AoE preview and visibility work.

Focused proof:

- `uv run pyright dnd/core/geometry.py dnd/core/gridmap.py tests/manual/test_43_ai_runtime_performance.py`
  - 0 errors
- `uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "supercover_line_reuses_immutable_geometry_cache or supercover_line_reuses_relative_geometry_for_translated_rays"`
  - passed, `2 passed, 48 deselected`
- `uv run pytest tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py -q -k "geometry_and_aoe_are_grid_aware_where_needed or zone_control_cone_and_line_use_directional_geometry or cylinder_subjective_preview_matches_targeting_footprint"`
  - passed, `3 passed, 20 deselected`

Retained smoke:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id standard_skeleton_doors --seed 707
```

Result:

- `gauntlet_id`: `20260716T233115Z-ai-gauntlet-smoke-ba82f75a`
- retained artifact:
  `ai/evidence/runs/20260716T233115Z-ai-gauntlet-smoke-ba82f75a-0000-standard_skeleton_doors.json`
- `gate_status`: `passed`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- command statuses: `11 accepted`
- `latency_status`: `failed`
- `latency_reasons`:
  `["command_total_p95_over_5ms", "command_total_p99_over_10ms", "local_decision_p99_over_5ms"]`
- production command p95/p99 ms: `49.154` / `49.154`
- production server command p99 ms: `36.044`
- production local decision p99 ms: `5.018`
- diagnostic command p99 ms: `90.129`
- diagnostic server command p99 ms: `47.822`

First diagnostic epoch comparison against the previous retained clean baseline:

- `publish.followup_epoch.grid.directional_fov.supercover_line_ms`:
  `2.691` -> `0.267`
- `publish.followup_epoch.grid.directional_fov.total_ms`:
  `7.633` -> `5.156`
- `publish.followup_epoch.available_actions.aoe_footprint_cache_miss_ms`:
  `10.924` -> `7.390`
- `publish.followup_epoch.available_actions.collect_aoe_actions_ms`:
  `14.792` -> `11.159`
- `publish.followup_epoch.get_available_actions_ms`:
  `20.214` -> `15.828`
- first diagnostic server total:
  `55.559` -> `47.822`

Conclusion: the relative-offset path is a real server-side improvement inside
the authoritative epoch builder, but the release latency gate still fails.
Remaining work is now split between action execution cost
(`execute.action_by_index_ms`) and still-heavy exhaustive AoE affordance
generation. The slight local decision miss (`5.018 ms`) should be watched, but
the dominant budget failure remains server-side.

## 2026-07-17 - AoE Preview Intersection Cleanup

Tightened `AoEShape.compute_subjective()` and `compute_objective()` so AoE
preview generation avoids avoidable intermediate set allocations:

- barrier checks use `geometric.isdisjoint(barrier_positions)` instead of
  allocating `geometric & barrier_positions`;
- subjective previews use one intersection over geometric footprint, caster
  visibility, and origin propagation FOV;
- when the origin propagation FOV is already the geometric footprint, the
  preview intersects only with caster visibility;
- objective AoE propagation uses `isdisjoint()` and a direct footprint/FOV
  intersection.

This preserves the exact target rows and affected-position payloads. It does
not collapse candidate centers or weaken server-authoritative legality.

Focused proof:

- `uv run pyright dnd/core/aoe.py tests/manual/test_43_ai_runtime_performance.py`
  - 0 errors
- `uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "subjective_aoe_preview_intersects_visibility_and_propagation or aoe_shape_definition_is_not_serialized_per_candidate_cell or aoe_origin_fov_cache_survives_preview_cache_invalidation or required_target_aoe_prefilter_uses_action_relationship_filter"`
  - passed, `4 passed, 47 deselected`
- `uv run pytest tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py -q -k "geometry_and_aoe_are_grid_aware_where_needed or zone_control_cone_and_line_use_directional_geometry or cylinder_subjective_preview_matches_targeting_footprint"`
  - passed, `3 passed, 20 deselected`

Retained smoke:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id standard_skeleton_doors --seed 707
```

Result:

- `gauntlet_id`: `20260716T233611Z-ai-gauntlet-smoke-5ba61436`
- retained artifact:
  `ai/evidence/runs/20260716T233611Z-ai-gauntlet-smoke-5ba61436-0000-standard_skeleton_doors.json`
- `gate_status`: `passed`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- command statuses: `11 accepted`
- `latency_status`: `failed`
- `latency_reasons`:
  `["command_total_p95_over_5ms", "command_total_p99_over_10ms"]`
- production command p95/p99 ms: `47.155` / `47.155`
- production server command p99 ms: `35.085`
- production local decision p99 ms: `4.477`
- diagnostic command p99 ms: `91.653`
- diagnostic server command p99 ms: `49.153`

First diagnostic epoch after the prior relative-ray improvement:

- `publish.followup_epoch.get_available_actions_ms`: `15.828` -> `16.082`
- `publish.followup_epoch.available_actions.collect_aoe_actions_ms`:
  `11.159` -> `11.236`
- `publish.followup_epoch.available_actions.aoe_footprint_cache_miss_ms`:
  `7.390` -> `7.636`
- `publish.followup_epoch.grid.directional_fov.transition_checks_ms`:
  `2.236` -> `1.832`
- production command p99 improved in the retained smoke:
  `49.154` -> `47.155`

Conclusion: this is a low-risk allocation cleanup in the exact hot path, but it
is not a decisive latency-gate fix. The next meaningful server-side target is
larger: either reduce movement/event/sensory execution cost or make exhaustive
AoE affordance construction less expensive without removing legal choices.

## 2026-07-17 - Adjacent Domain Projection Cache

Added a small topology cache for `_adjacent_domain_knowledge()` in the
subjective observation projector. Adjacent-domain facts disclose only whether
neighboring map cells exist (`invalid` versus `unknown`); they do not depend on
observer visibility, hidden entities, terrain contents, or session ownership.
The cache invalidates on the grid movement-topology revision and is cleared
with the observation projection cache.

This targets the first movement command's sensory-update projection cost, where
visible tile patches repeatedly rebuild the same static neighbor-domain maps
while the actor reveals cells along a path.

Focused proof:

- `uv run pyright ai/observation/projector.py tests/manual/test_43_ai_runtime_performance.py`
  - 0 errors
- `uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "adjacent_domain_projection_reuses_static_topology_cache"`
  - passed, `1 passed, 51 deselected`
- `uv run pytest tests/manual/test_28_subjective_observation_stream.py -q -k "dense_sensory_tile_updates_are_batched_and_replayable or removed_visible_tile_delta_reuses_materialized_boundary_memory or lit_to_lit_light_changes_do_not_refilter_visible_occupants"`
  - passed, `3 passed, 41 deselected`

Retained smoke:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id standard_skeleton_doors --seed 707
```

Result:

- `gauntlet_id`: `20260716T234112Z-ai-gauntlet-smoke-8a5e8685`
- retained artifact:
  `ai/evidence/runs/20260716T234112Z-ai-gauntlet-smoke-8a5e8685-0000-standard_skeleton_doors.json`
- `gate_status`: `passed`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- command statuses: `11 accepted`
- `latency_status`: `failed`
- `latency_reasons`:
  `["command_total_p95_over_5ms", "command_total_p99_over_10ms"]`
- production command p95/p99 ms: `48.581` / `48.581`
- production server command p99 ms: `36.296`
- production local decision p99 ms: `4.893`
- diagnostic command p99 ms: `89.095`
- diagnostic server command p99 ms: `48.641`

First movement diagnostic comparison against the previous retained artifact:

- `execute_by_index.movement.update_position_ms`: `20.164` -> `19.437`
- `execute_by_index.event_queue.pre_completion.callback.SpatialSensesSystem_ms`:
  `14.665` -> `14.075`
- `execute_by_index.observation_projection.projection.project_events_ms`:
  `5.520` -> `5.102`
- sensory update patch build:
  `4.971` -> `4.509`
- visible tile patch build:
  `2.909` -> `2.731`
- removed tile patch build:
  `0.929` -> `0.795`
- action execution total:
  `27.336` -> `26.316`

Conclusion: this removes repeated static map-boundary work from the subjective
projection path, but the latency gate still fails. The next larger win must
come from reducing repeated sensory callback/event projection work during
multi-step movement, or from making the remaining exhaustive AoE epoch
generation cheaper without hiding legal actions.

## 2026-07-17 - Hot Projection And AoE Footprint Cache Split

Tightened two latency-sensitive server paths while preserving the event-first
subjective contract.

Projection changes:

- `_update_projection_cache()` now returns immediately when the session cache is
  already at the current `EventQueue` cursor and ownership has not changed.
- `SENSORY_UPDATE` projection now handles observer-specific sensory frames
  before combat-log filtering. Sensory frames cannot use combat logs, so this
  removes work without changing the frame payload.

AoE discovery changes:

- AoE footprint cache entries now store geometry plus propagation only.
- Current actor visibility is intersected after the cache read, and entity UUIDs
  are resolved from the current subjective `Senses` state.
- Preview caches still invalidate on visibility/contact changes, so legal rows
  remain session-subjective.

Focused proof:

- `uv run pyright ai/observation/projector.py tests/manual/test_43_ai_runtime_performance.py`
  - 0 errors
- `uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "projection_cache_current_cursor_skips_context_rebuild or sensory_projection_skips_combat_log_filtering or normal_subjective_projection_does_not_run_deep_timing_probes"`
  - passed, `3 passed, 51 deselected`
- `uv run pytest tests/manual/test_28_subjective_observation_stream.py -q -k "sensory_updates_for_unrelated_observers_are_excluded or dense_sensory_tile_updates_are_batched_and_replayable or removed_visible_tile_delta_reuses_materialized_boundary_memory or lit_to_lit_light_changes_do_not_refilter_visible_occupants or child_projection_captures_at_its_completion_boundary or projection_immediacy_classifier_preserves_movement_sensory_and_hp_boundaries"`
  - passed, `5 passed, 39 deselected`
- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q -k "decision_epoch or command_result or sensory"`
  - passed, `1 passed, 36 deselected`
- `uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "aoe_shape_definition_is_not_serialized_per_candidate_cell or aoe_origin_fov_cache_survives_preview_cache_invalidation or aoe_propagation_footprints_survive_visibility_only_changes or aoe_discovery_reuses_one_preview_shape_per_variant or directional_aoe_discovery_compacts_duplicate_target_rays or required_target_aoe_prefilter_uses_action_relationship_filter"`
  - passed, `6 passed, 49 deselected`
- `uv run pytest tests/manual/test_31_subjective_runtime_epochs.py -q -k "aoe_discovery or directional_aoe or occupancy_resolution"`
  - passed, `8 passed, 33 deselected`
- `uv run pyright tests/manual/test_31_subjective_runtime_epochs.py dnd/entity.py tests/manual/test_43_ai_runtime_performance.py ai/observation/projector.py`
  - 0 errors

Retained same-seed smoke:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id standard_skeleton_doors --seed 707
```

Result:

- `gauntlet_id`: `20260716T235656Z-ai-gauntlet-smoke-ab2ed3dc`
- retained artifact:
  `ai/evidence/runs/20260716T235656Z-ai-gauntlet-smoke-ab2ed3dc-0000-standard_skeleton_doors.json`
- `gate_status`: `passed`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- command statuses: `11 accepted`
- `latency_status`: `failed`
- `latency_reasons`:
  `["command_total_p95_over_5ms", "command_total_p99_over_10ms"]`
- normal command p95/p99 ms: `48.091` / `48.091`
- normal server command p99 ms: `36.099`
- normal local decision p99 ms: `4.613`
- diagnostic command p99 ms: `92.385`
- diagnostic server command p99 ms: `49.906`

Same-seed comparison against
`20260716T234859Z-ai-gauntlet-smoke-bc6f221c`:

- normal command p99: `48.968` -> `48.091`
- normal server command p99: `36.748` -> `36.099`
- diagnostic server command p99: `51.579` -> `49.906`
- local decision p99 stayed below the target: `4.587` -> `4.613`
- sensory-update combat-log filter timing disappeared from the retained trace.

Conclusion: these changes are correct and directionally useful, but the
latency gate remains red. The next significant work should focus on the two
remaining real costs:

- carried-light movement causes an event/sensory cascade before the follow-up
  epoch;
- follow-up epoch construction still builds dense legal affordances after
  every continuing action.

## 2026-07-17 - Filtered Passive Event Callbacks

Reduced event-system callback churn without changing event storage, handlers,
combat logs, subjective projection semantics, or public streams.

EventQueue changes:

- `EventQueue.add_on_event_callback()` now accepts optional `event_types` and
  `phases` filters.
- `EventQueue.add_on_event_sequence_callback()` now accepts the same optional
  filters.
- Existing callers remain unfiltered by default.
- Filter state is removed with the callback and cleared on `EventQueue.reset()`.

Runtime wiring:

- `GridMap._on_light_movement_event` now receives only completed
  `SPATIAL_ENTITY_ENTERED` events.
- `GridMap._on_vision_blocking_changed` now receives only declaration-phase
  spatial topology/perceivability/object events that can carry blocking hints.
- The subjective observation projector sequence callback now receives only
  sequences containing completion events; declaration/effect-only sequences no
  longer wake it just to return.

Focused proof:

- `uv run pyright dnd/core/events.py dnd/core/gridmap.py ai/observation/projector.py tests/manual/test_43_ai_runtime_performance.py`
  - 0 errors
- `uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "filtered_event_callbacks_skip_unrelated_events or normal_subjective_projection_does_not_run_deep_timing_probes or directional_aoe_discovery_compacts_duplicate_target_rays"`
  - passed, `3 passed, 53 deselected`
- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q -k "decision_epoch or command_result or sensory or event_projection"`
  - passed, `1 passed, 36 deselected`
- `uv run pytest tests/manual/test_05_event_lifecycle.py -q -k "callback"`
  - passed, `1 passed, 5 deselected`

Retained same-seed smoke:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id standard_skeleton_doors --seed 707
```

Latest result:

- `gauntlet_id`: `20260717T000619Z-ai-gauntlet-smoke-2f0153e1`
- retained artifact:
  `ai/evidence/runs/20260717T000619Z-ai-gauntlet-smoke-2f0153e1-0000-standard_skeleton_doors.json`
- `gate_status`: `passed`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- command statuses: `11 accepted`
- `latency_status`: `failed`
- `latency_reasons`:
  `["command_total_p95_over_5ms", "command_total_p99_over_10ms"]`
- normal command p95/p99 ms: `46.311` / `46.311`
- normal server command p99 ms: `34.882`
- normal local decision p99 ms: `4.622`
- diagnostic command p99 ms: `88.961`
- diagnostic server command p99 ms: `48.897`

Same-seed comparison against
`20260716T235656Z-ai-gauntlet-smoke-ab2ed3dc`:

- normal command p99: `48.091` -> `46.311`
- normal server command p99: `36.099` -> `34.882`
- diagnostic command p99: `92.385` -> `88.961`
- diagnostic server command p99: `49.906` -> `48.897`
- local decision p99 stayed below target: `4.613` -> `4.622`
- first movement `GridMap_on_light_movement_event` callback invocations dropped
  from `85` to `5`; the remaining time is real light movement, sensory
  updates, and follow-up epoch construction.

Conclusion: the callback filters are correct and measurable, but still not
enough for the latency gate. The remaining first-move spike is dominated by
real carried-light sensory updates plus dense AoE affordance construction after
the move reveals enemies.

## 2026-07-17 - Deferred HP Projection And Candidate-Bounded AoE Propagation

Two narrow latency changes landed after the passive callback filters.

Subjective projection change:

- HP-only damage/death/combat-result sequences no longer force immediate
  projection inside an active action batch.
- Movement, spatial-enter/leave, perceivability, and sensory-update completions
  still project immediately because local controller revalidation can depend on
  the materialized subjective world after a committed step.
- Damage and HP patches remain event-ordered and replayable; they are just
  captured at the action batch boundary instead of once per child event.

AoE preview change:

- AoE propagation previews no longer compute a full origin FOV and then
  intersect it with the candidate footprint.
- `GridMap.filter_propagation_positions()` applies the existing propagation
  blocking rules only to the candidate cells supplied by the shape footprint.
- `Entity._compute_aoe_propagation_footprint()` now uses this bounded helper
  when terrain/object barriers intersect the geometric footprint.
- The retained trace for the latest same-seed smoke contains
  `grid.filter_propagation_positions` samples and zero
  `grid.compute_propagation_fov` samples for AoE preview work.

Focused proof:

- `uv run pyright ai/observation/projector.py tests/manual/test_28_subjective_observation_stream.py`
  - 0 errors
- `uv run pytest tests/manual/test_28_subjective_observation_stream.py -q -k "projection_immediacy_classifier_preserves_movement_sensory_and_hp_boundaries or roll_result_events_do_not_force_redundant_entity_fact_patches"`
  - passed, `2 passed, 42 deselected`
- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q -k "subjective_projector_defers_delivery_but_not_event_time_capture or damage_projection_defers_until_action_batch_boundary or command_result"`
  - passed, `3 passed, 35 deselected`
- `uv run pyright dnd/core/gridmap.py dnd/entity.py tests/manual/test_43_ai_runtime_performance.py`
  - 0 errors
- `uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "footprint_limited_propagation_matches_full_fov_for_candidates or aoe_preview_filters_footprints_without_full_origin_fov or aoe_propagation_footprints_survive_visibility_only_changes or directional_aoe_discovery_compacts_duplicate_target_rays"`
  - passed, `4 passed, 53 deselected`
- `uv run pytest tests/manual/test_31_subjective_runtime_epochs.py -q -k "aoe_discovery or directional_aoe or occupancy_resolution"`
  - passed, `8 passed, 33 deselected`

Known type-check caveat:

- `uv run pyright ai/observation/projector.py tests/manual/test_28_subjective_observation_stream.py tests/manual/test_36_seamless_subjective_runtime.py`
  still reports the pre-existing Starlette private-type issues in
  `tests/manual/test_36_seamless_subjective_runtime.py`. These are already
  tracked in `KNOWN_ISSUES.md`; the implementation module and the modified
  Chapter 28 tests type-check cleanly.

Retained same-seed smoke:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id standard_skeleton_doors --seed 707
```

Latest result:

- `gauntlet_id`: `20260717T001404Z-ai-gauntlet-smoke-1f01cfa7`
- retained artifact:
  `ai/evidence/runs/20260717T001404Z-ai-gauntlet-smoke-1f01cfa7-0000-standard_skeleton_doors.json`
- `gate_status`: `passed`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- command statuses: `11 accepted`
- `latency_status`: `failed`
- `latency_reasons`:
  `["command_total_p95_over_5ms", "command_total_p99_over_10ms"]`
- normal command p95/p99 ms: `45.338` / `45.338`
- normal server command p99 ms: `33.502`
- normal local decision p99 ms: `4.458`
- diagnostic command p99 ms: `88.264`
- diagnostic server command p99 ms: `47.599`

Same-seed comparison:

- vs `20260717T000619Z-ai-gauntlet-smoke-2f0153e1`:
  - normal command p99: `46.311` -> `45.338`
  - normal server command p99: `34.882` -> `33.502`
  - diagnostic command p99: `88.961` -> `88.264`
  - diagnostic server command p99: `48.897` -> `47.599`
  - local decision p99 stayed below target: `4.622` -> `4.458`
- vs `20260717T001051Z-ai-gauntlet-smoke-b5d35aee`:
  - normal command p99: `46.972` -> `45.338`
  - normal server command p99: `34.468` -> `33.502`
  - local decision p99: `4.851` -> `4.458`

Conclusion: the changes are semantically correct and directionally useful.
The latency gate remains red because command submission still pays for
server-side execution, stream follow-up, and follow-up epoch/affordance
construction. The next slice should inspect whether the high normal samples
are dominated by follow-up epoch construction, frame application, or remaining
movement/light sensory work before touching policy behavior.

## 2026-07-17 - Legal-Only Decision Epoch Rows And Propagation Filter Cache

Two more contracts landed around the same latency surface.

Decision-epoch affordance split:

- `Entity.get_available_actions()` keeps its default public/debug behavior:
  unaffordable rows can still appear with explanatory `can_afford=False`
  metadata for human and compatibility clients.
- `Entity.get_available_actions(legal_only=True)` omits unaffordable rows and
  skips their expensive target discovery.
- `ai.subjective.epochs.build_decision_epoch()` now uses the legal-only view,
  matching the AI stream contract: a `DecisionEpoch` contains executable
  affordances plus separate capabilities, not every debug row.
- The test coverage proves Dash remains visible as unaffordable in classic
  discovery after it is spent, while the AI epoch omits the non-executable Dash
  row and still exposes `End Turn`.

Grid propagation cache:

- `GridMap.filter_propagation_positions()` is now cached by propagation
  revision, origin, max distance, and sorted candidate footprint.
- The cache is cleared with propagation topology revisions and bounded to 256
  entries.
- This lets different spell templates with the same physical footprint share
  the same propagation result instead of repeating line/transition checks.

Focused proof:

- `uv run pyright dnd/entity.py dnd/actions_functional.py ai/subjective/epochs.py tests/manual/test_31_subjective_runtime_epochs.py`
  - 0 errors
- `uv run pytest tests/manual/test_31_subjective_runtime_epochs.py -q -k "decision_epoch_omits_unaffordable_debug_rows or snapshot_includes_epoch_on_active_ai_turn or epoch_rows_have_stable_row_ids_and_action_economy"`
  - passed, `3 passed, 39 deselected`
- `uv run pytest tests/manual/test_36_seamless_subjective_runtime.py -q -k "decision_epoch or command_result or current_epoch"`
  - passed, `2 passed, 36 deselected`
- `uv run pyright dnd/core/gridmap.py dnd/entity.py dnd/actions_functional.py ai/subjective/epochs.py tests/manual/test_31_subjective_runtime_epochs.py tests/manual/test_43_ai_runtime_performance.py`
  - 0 errors
- `uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "footprint_limited_propagation_matches_full_fov_for_candidates or footprint_limited_propagation_reuses_identical_candidate_filters or aoe_preview_filters_footprints_without_full_origin_fov or aoe_propagation_footprints_survive_visibility_only_changes or directional_aoe_discovery_compacts_duplicate_target_rays"`
  - passed, `5 passed, 53 deselected`
- `uv run pytest tests/manual/test_31_subjective_runtime_epochs.py -q -k "decision_epoch_omits_unaffordable_debug_rows or snapshot_includes_epoch_on_active_ai_turn or epoch_rows_have_stable_row_ids_and_action_economy or aoe_discovery or directional_aoe or occupancy_resolution"`
  - passed, `11 passed, 31 deselected`

Retained smoke after legal-only split but before propagation-filter cache:

- `gauntlet_id`: `20260717T002259Z-ai-gauntlet-smoke-cf7483d2`
- `gate_status`: `passed`
- `subjectivity_status`: `passed`
- command statuses: `11 accepted`
- `latency_status`: `failed`
- normal command p99 ms: `50.211`
- normal server command p99 ms: `36.981`
- normal local decision p99 ms: `5.03`

Conclusion for that intermediate run: legal-only epoch rows are the right AI
contract, but they were not a latency win by themselves. They also exposed
normal run noise by pushing the local p99 sample just over the strict 5 ms
threshold.

Retained same-seed smoke after the propagation-filter cache:

```bash
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id standard_skeleton_doors --seed 707
```

Latest result:

- `gauntlet_id`: `20260717T002559Z-ai-gauntlet-smoke-5a688052`
- retained artifact:
  `ai/evidence/runs/20260717T002559Z-ai-gauntlet-smoke-5a688052-0000-standard_skeleton_doors.json`
- `gate_status`: `passed`
- `subjectivity_status`: `passed`
- `subjectivity_violation_count`: `0`
- command statuses: `11 accepted`
- `latency_status`: `failed`
- `latency_reasons`:
  `["command_total_p95_over_5ms", "command_total_p99_over_10ms"]`
- normal command p95/p99 ms: `44.787` / `44.787`
- normal server command p99 ms: `33.7`
- normal local decision p99 ms: `4.474`
- diagnostic command p99 ms: `90.493`
- diagnostic server command p99 ms: `48.809`

Same-seed comparison against
`20260717T001404Z-ai-gauntlet-smoke-1f01cfa7`:

- normal command p99: `45.338` -> `44.787`
- normal server command p99: `33.502` -> `33.7`
- normal local decision p99: `4.458` -> `4.474`
- diagnostic command p99: `88.264` -> `90.493`
- diagnostic server command p99: `47.599` -> `48.809`

Trace evidence:

- latest retained trace has six
  `grid.filter_propagation_positions.cache_miss_ms` samples and six
  `grid.filter_propagation_positions.cache_hit_ms` samples;
- latest retained trace still has zero `grid.compute_propagation_fov` samples
  for AoE preview work;
- the first movement's propagation-filter total was `4.891 ms`, with cache-hit
  time totaling only `0.007 ms`.

Conclusion: the latest smoke is the best normal command p99 in this local
series and restores local decision p99 below target, but the strict command
latency gate remains red. Remaining spikes are now broader server/transport and
engine execution costs, especially Fireball/Magic Missile execution and
follow-up epoch publication after high-surface turns.

## 2026-07-17 - Live-Only Gauntlet Watcher Projection

Closed an observability gap in the gauntlet watcher. Before this slice, live
gauntlet events could be published to the backend before a retained summary was
written, but the ergonomic watcher path still assumed summary JSON existed.
That meant the data stream existed while the user-facing monitor could fail to
discover the currently running gauntlet.

Changes:

- added a live-event watcher projection that builds `GauntletWatcherState`
  directly from retained live gauntlet events;
- added `LiveGauntletEventStream.latest_gauntlet_id()` and retained gauntlet-id
  listing support;
- added `GET /ai/gauntlets/live/latest` for the monitor's "open and observe
  the currently running gauntlet" path;
- made `GET /ai/gauntlets/{gauntlet_id}/watch` fall back to live projection
  only when summary JSON is not yet written;
- kept invalid retained summary JSON loud instead of hiding it behind live
  fallback;
- added `scheduled_count` to `GAUNTLET_STARTED` payloads so pending counts are
  visible before summary write;
- updated the static watcher HTML to try the live backend first, then retained
  latest JSON, then static/file fallback;
- normalized `recent_events` and `events` in the HTML so live watcher state and
  retained summary JSON render through the same table.

Focused proof:

- `uv run pyright ai/evaluation/gauntlet_contract.py ai/evaluation/gauntlet.py server/gauntlet_event_stream.py server/event_server.py tests/manual/test_55_gauntlet_live_watcher_server.py tests/manual/test_57_gauntlet_watcher_html.py`
  - 0 errors
- `uv run pytest tests/manual/test_55_gauntlet_live_watcher_server.py -q -k "live_gauntlet_watch_endpoint or runner_can_publish_directly_to_server_live_stream or latest_gauntlet_summary"`
  - passed, `4 passed, 6 deselected`
- `uv run pytest tests/manual/test_57_gauntlet_watcher_html.py -q`
  - passed, `2 passed`
- `uv run pytest tests/manual/test_54_ai_gauntlet_watcher.py -q`
  - passed, `18 passed`
- `uv run pytest tests/manual/test_56_gauntlet_runner_cli.py -q -k "run or check or watcher"`
  - passed, `12 passed`

This moves the watcher closer to the intended role: observability while the
gauntlet is running, not only after artifacts are already finalized.

## 2026-07-17 - Live Watcher Contract Documentation

Updated the AI runtime README so the documented gauntlet watcher contract
matches the implemented live-first path.

The watcher now documents:

- first attempting `GET /ai/gauntlets/live/latest`;
- using that endpoint before retained summary JSON exists;
- falling back to `GET /ai/gauntlets/latest`, static
  `ai/evidence/gauntlets/latest.json`, and legacy tournament JSON;
- treating live projection as observability, not durable evidence;
- refusing to hide invalid retained summary JSON behind live projection.

Focused proof:

- `uv run pytest tests/manual/test_58_ai_runtime_readme.py -q`
  - passed, `1 passed`
- `uv run pytest tests/manual/test_57_gauntlet_watcher_html.py -q`
  - passed, `2 passed`
- `uv run pyright ai/evaluation/gauntlet_contract.py ai/evaluation/gauntlet.py server/gauntlet_event_stream.py server/event_server.py tests/manual/test_55_gauntlet_live_watcher_server.py tests/manual/test_58_ai_runtime_readme.py`
  - 0 errors
- `awk '/<script>/{flag=1;next}/<\\/script>/{flag=0}flag' ai/AI_TOURNAMENT_MONITOR.html | node --check -`
  - passed

## 2026-07-17 - Direct Subjective Frame Catch-Up For In-Process Gauntlets

Closed the most obvious remaining client-transport cost in the in-process
gauntlet harness. The harness was still catching up subjective frames through
the HTTP `/ai/sessions/{session_id}/observation/frames` route, even though it
runs inside the same process as the authoritative simulation. That added route
and JSON overhead to every self-play command without adding any fairness or
subjectivity guarantee.

The new path calls the same session-subjective observation projector directly
through `iter_observation_frames()`, applies the returned `ObservationFrame`
models to `SubjectiveStore`, and falls back to the HTTP route only if session
access fails. This is not an objective-state shortcut: the data still comes
from the observation projector and still passes through the same local
materializer.

Focused code proof:

- added direct catch-up in `ai/external_selfplay.py`;
- added `test_selfplay_catch_up_uses_direct_subjective_projection()` in
  `tests/manual/test_43_ai_runtime_performance.py`;
- kept the existing stale-epoch and no-empty-prefetch tests green.

Focused commands:

```bash
uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "selfplay_catch_up_uses_direct_subjective_projection or selfplay_reuses_current_epoch_without_empty_pre_command_fetch or selfplay_catches_up_when_cached_epoch_is_stale"
uv run pyright ai/external_selfplay.py tests/manual/test_43_ai_runtime_performance.py
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id standard_skeleton_doors --seed 707
uv run python -m ai.evaluation.gauntlet_runner check ai/evidence/gauntlets/latest.json --require-gate-pass
```

Focused results:

- tests: passed, `3 passed, 56 deselected`;
- pyright: `0 errors`;
- retained summary:
  `ai/evidence/gauntlets/20260717T010229Z-ai-gauntlet-smoke-2964476a.json`;
- retained raw run:
  `ai/evidence/runs/20260717T010229Z-ai-gauntlet-smoke-2964476a-0000-standard_skeleton_doors.json`;
- `gate_status`: `passed`;
- `subjectivity_status`: `passed`;
- `subjectivity_violation_count`: `0`;
- command statuses: `11 accepted`;
- `latency_status`: `failed`.

Same-seed comparison against
`20260717T005149Z-ai-gauntlet-smoke-d88c183c`:

- elapsed run time: `654.362 ms` -> `517.819 ms`;
- raw frame fetch p95: `12.752 ms` -> `0.031 ms`;
- follow-up frame fetch p95: `7.356 ms` -> `0.030 ms`;
- follow-up sync p95: `12.165 ms` -> `1.307 ms`;
- total command p95: `93.883 ms` -> `71.942 ms`;
- normal command total p95: `46.752 ms` -> `34.731 ms`;
- normal server command p95: `34.828 ms` -> `32.281 ms`;
- normal local decision p99: `4.649 ms` -> `5.083 ms`.

Conclusion: the subjective transport path is no longer the dominant cost for
the in-process harness. The strict latency gate remains red, but the failure is
now in real command execution and epoch publication rather than client-side
frame polling.

Current bottleneck evidence from the latest retained trace:

- command `0`, sorcerer reveal-boundary `Move`: `71.942 ms` total,
  `44.622 ms` server, `25.167 ms` action execution,
  `19.077 ms` follow-up epoch build;
- that movement spends most of its action time in position update, spatial
  enter events, carried-light movement, sensory callbacks, and visibility
  projection;
- its follow-up epoch spends most of its time in available-action generation,
  especially AoE collection and propagation filtering;
- command `2`, `Fireball__slot_3`: `34.731 ms` total, `30.737 ms` server,
  mostly action execution;
- command `8`, skeleton `end_turn`: `34.133 ms` total, `32.281 ms` server,
  mostly encounter advancement and active-epoch publication;
- command `10`, `Magic Missile__slot_3`: `21.455 ms` total, `17.486 ms`
  server, mostly multi-target action execution and subjective projection of
  resulting damage/death/condition events.

Next likely safe slices:

- optimize epoch-time AoE and propagation filtering without weakening
  visibility or target legality;
- inspect movement sensory publication for duplicate work while preserving
  reveal-on-move correctness;
- split command latency dashboards by action execution, epoch generation,
  stream delivery, and local policy so watcher views show where the red bar
  actually lives;
- keep the movement/sensory path conservative until there is a failing
  subjectivity test protecting any proposed cache.

## 2026-07-17 - JSON-Driven Latency Stage Summaries In The Watcher

Closed a watcher gap exposed by the direct frame catch-up work. Raw self-play
artifacts retained detailed stage samples, but gauntlet summaries collapsed the
view down to command total, server command, and local decision. That made the
HTML watcher good at saying "latency is red" but weak at showing whether the
red bar came from frame catch-up, command transport, local policy, server
validation, or follow-up synchronization.

Changes:

- added per-stage latency sample retention to `TournamentMatchRecord`;
- aggregated those samples into typed `GauntletLatencyStageSummary` rows under
  `performance.stages`, `performance.normal_stages`, and
  `performance.diagnostic_stages`;
- included the same stage sample payload in live `MATCH_PROGRESS` watcher
  events, so live and retained watcher modes use the same evidence model;
- extended the gauntlet evidence validator so stage sample counts must match
  retained match rows;
- added a stage breakdown table to `ai/AI_TOURNAMENT_MONITOR.html` showing
  sample counts and p95/p99/max for normal, all, and diagnostic command paths.

Focused proof:

```bash
uv run pyright ai/evaluation/tournament.py ai/evaluation/gauntlet.py ai/evaluation/gauntlet_contract.py tests/manual/test_54_ai_gauntlet_watcher.py
uv run pytest tests/manual/test_54_ai_gauntlet_watcher.py -q -k "latency_audit_uses_normal_samples or performance or watcher_projection"
uv run pytest tests/manual/test_55_gauntlet_live_watcher_server.py -q -k "live_gauntlet_watch_endpoint or runner_can_publish_directly_to_server_live_stream or latest_gauntlet_summary"
uv run pytest tests/manual/test_57_gauntlet_watcher_html.py -q
awk '/<script>/{flag=1;next}/<\\/script>/{flag=0}flag' ai/AI_TOURNAMENT_MONITOR.html | node --check -
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id standard_skeleton_doors --seed 707
uv run python -m ai.evaluation.gauntlet_runner check ai/evidence/gauntlets/latest.json --require-gate-pass
```

Focused results:

- pyright: `0 errors`;
- watcher/performance tests: passed;
- live watcher tests: passed, `4 passed, 6 deselected`;
- HTML tests: passed, `2 passed`;
- monitor script syntax check: passed;
- retained summary:
  `ai/evidence/gauntlets/20260717T011203Z-ai-gauntlet-smoke-6f625e47.json`;
- retained raw run:
  `ai/evidence/runs/20260717T011203Z-ai-gauntlet-smoke-6f625e47-0000-standard_skeleton_doors.json`;
- `gate_status`: `passed`;
- `subjectivity_status`: `passed`;
- `subjectivity_violation_count`: `0`;
- command statuses: `11 accepted`;
- `latency_status`: `failed`.

Latest retained stage evidence:

- normal `frame_fetch_ms`: p95 `0.029 ms`, max `0.029 ms`;
- normal `command_followup_sync_ms`: p95 `0.799 ms`, max `0.799 ms`;
- normal `command_http_ms`: p95 `36.851 ms`, max `36.851 ms`;
- normal `command_submit_ms`: p95 `37.405 ms`, max `37.405 ms`;
- normal `local_decision_ms`: p95/p99 `6.019 ms`;
- normal `policy_ms`: p95/p99 `5.048 ms`;
- normal `total_ms`: p95/p99 `40.035 ms`.

Conclusion: the monitor can now show that the stream catch-up optimization
worked and that current latency is dominated by command/server work plus a
small local policy outlier. This is the right level of observability before
touching movement, sensory, or epoch-generation internals.

## 2026-07-17 - Shared Outcome Cache For Transformation Planning

Closed the latest local-policy latency outlier without changing behavior. The
slowest non-diagnostic local decision in the retained smoke was a sorcerer
`Quickened Spell` decision. Diagnostics showed that candidate generation and
`TransformThenAct` routine planning were recomputing exact projected damage
evidence for the same disclosed target/action values already handled elsewhere
by the policy outcome cache.

The planner now uses `DamageOutcomeWorkspace(shared_value_cache=True)` when
checking projected transformed follow-ups. This keeps the computation pure and
subjective: the shared key is based on the action outcome profile, target
fields disclosed in `ObservationEntityFact`, application count, and bounded
effect-block evidence. It does not introduce hidden target data or server-side
legality shortcuts.

Focused code proof:

- changed `ai/policy/routines.py` so `TransformThenAct` projected-damage checks
  use the shared disclosed-value outcome cache;
- added
  `test_transform_planner_uses_shared_outcome_cache_for_projected_damage()` in
  `tests/manual/test_45_policy_routines.py`;
- adjusted the local routine test context helper to include actor-owned
  capabilities and extra semantic catalog rows, matching the real epoch
  contract.

Focused commands:

```bash
uv run pytest tests/manual/test_45_policy_routines.py -q -k "transform_planner_uses_shared_outcome_cache or quickened_projection or twinned_projection"
uv run pytest tests/manual/test_48_policy_host.py -q -k "transformed_followup or transformed or transform"
uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "dense_spacing_epoch or dominant_durable_setup or selfplay_catch_up_uses_direct_subjective_projection"
uv run pyright ai/policy/routines.py ai/external_selfplay.py ai/evaluation/tournament.py ai/evaluation/gauntlet.py ai/evaluation/gauntlet_contract.py tests/manual/test_45_policy_routines.py tests/manual/test_43_ai_runtime_performance.py
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id standard_skeleton_doors --seed 707
uv run python -m ai.evaluation.gauntlet_runner check ai/evidence/gauntlets/latest.json --require-gate-pass
```

Focused results:

- routine tests: passed, `3 passed, 11 deselected`;
- policy-host transform tests: passed, `5 passed, 45 deselected`;
- runtime performance slice: passed, `3 passed, 56 deselected`;
- pyright: `0 errors`;
- retained summary:
  `ai/evidence/gauntlets/20260717T011928Z-ai-gauntlet-smoke-ccb365ec.json`;
- retained raw run:
  `ai/evidence/runs/20260717T011928Z-ai-gauntlet-smoke-ccb365ec-0000-standard_skeleton_doors.json`;
- `gate_status`: `passed`;
- `subjectivity_status`: `passed`;
- `subjectivity_violation_count`: `0`;
- command statuses: `11 accepted`;
- `latency_status`: `failed`.

Same-seed comparison against
`20260717T011203Z-ai-gauntlet-smoke-6f625e47`:

- `latency_reasons`:
  `["command_total_p95_over_5ms", "command_total_p99_over_10ms", "local_decision_p99_over_5ms"]`
  ->
  `["command_total_p95_over_5ms", "command_total_p99_over_10ms"]`;
- normal local decision p99: `6.019 ms` -> `4.754 ms`;
- normal policy p99: `5.048 ms` -> `3.886 ms`;
- normal command total p95: `40.035 ms` -> `38.174 ms`;
- normal server command p95: `35.729 ms` -> `34.219 ms`;
- max command total: `80.208 ms` -> `78.058 ms`;
- max server command: `48.986 ms` -> `47.389 ms`.

Conclusion: local policy is back under the strict 5 ms p99 target in the latest
retained smoke. The remaining latency gate failure is command total p95/p99,
with the stage table pointing primarily at command HTTP/server execution rather
than local policy or subjective frame transport.

## 2026-07-17 - Server And Engine Phase Stages In Gauntlet Evidence

Promoted nested server and engine timing phases into retained gauntlet stage
summaries. Before this slice, raw self-play traces already contained useful
`server_timing.phases` and `action_server_timing.phases`, but the normal
observer path could only say that command latency was red. The watcher summary
now carries prefixed stage keys such as
`server.execute.action_by_index_ms`,
`server.publish.followup_epoch.build_decision_epoch_total_ms`, and
`engine.execute_by_index.base_action.apply_total_ms`.

Focused code proof:

- `ai/evaluation/tournament.py` now folds nested `server.*` and `engine.*`
  phase samples into `stage_samples_ms`, `normal_stage_samples_ms`, and
  `diagnostic_stage_samples_ms`;
- `tests/manual/test_52_ai_tournament_elo.py` proves nested phase samples are
  retained with the correct normal/diagnostic split;
- `tests/manual/test_54_ai_gauntlet_watcher.py` proves the gauntlet performance
  summary exposes those promoted phases for the watcher.

Focused commands:

```bash
uv run pytest tests/manual/test_52_ai_tournament_elo.py -q -k "build_tournament_match_record"
uv run pytest tests/manual/test_54_ai_gauntlet_watcher.py -q -k "latency_audit_uses_normal_samples or performance or watcher_projection"
uv run pytest tests/manual/test_57_gauntlet_watcher_html.py -q
uv run pyright ai/evaluation/tournament.py ai/evaluation/gauntlet.py ai/evaluation/gauntlet_contract.py tests/manual/test_52_ai_tournament_elo.py tests/manual/test_54_ai_gauntlet_watcher.py tests/manual/test_57_gauntlet_watcher_html.py
awk '/<script>/{flag=1;next}/<\\/script>/{flag=0}flag' ai/AI_TOURNAMENT_MONITOR.html | node --check -
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id standard_skeleton_doors --seed 707
uv run python -m ai.evaluation.gauntlet_runner check ai/evidence/gauntlets/latest.json --require-gate-pass
```

Focused results:

- tournament timing test: passed, `1 passed, 2 deselected`;
- gauntlet watcher timing tests: passed, `2 passed, 16 deselected`;
- watcher HTML tests: passed, `2 passed`;
- pyright: `0 errors`;
- monitor script syntax check: passed;
- retained summary:
  `ai/evidence/gauntlets/20260717T012548Z-ai-gauntlet-smoke-b323949d.json`;
- retained raw run:
  `ai/evidence/runs/20260717T012548Z-ai-gauntlet-smoke-b323949d-0000-standard_skeleton_doors.json`;
- `gate_status`: `passed`;
- `subjectivity_status`: `passed`;
- `subjectivity_violation_count`: `0`;
- command statuses: `11 accepted`;
- `latency_status`: `failed`.

Latest retained normal-stage evidence:

- normal command total p95/p99: `39.654 ms`;
- normal server command p95/p99: `34.815 ms`;
- normal local decision p95/p99: `5.078 ms`;
- top normal server phase:
  `server.execute.action_by_index_ms` max/p95 `26.751 ms`;
- epoch publication:
  `server.publish.post_command_control_ms` max/p95 `18.042 ms`;
- follow-up epoch build:
  `server.publish.followup_epoch.build_decision_epoch_total_ms` max/p95
  `17.950 ms`;
- end-turn advancement:
  `server.end_turn.advance_encounter_ms` max/p95 `18.654 ms`.

Conclusion: the observer client is now useful for this layer of debugging. The
next optimization target is no longer vague "AI slowness"; it is the
server/engine command path, especially action execution with sensory updates
and decision-epoch publication after commands.

## 2026-07-17 - Command Latency Time Series In Gauntlet Watcher

Added a command-level latency timeline to the gauntlet watcher so retained
JSON exposes the command/server/local split without opening raw artifacts by
hand. The chart uses only `command_total_samples_ms`,
`server_command_samples_ms`, and `local_decision_samples_ms` from match rows.
Command/server latency and local decision latency are drawn on separate scales
so local policy cost is not visually flattened by server command cost. Missing
samples render as gaps instead of zeroes.

Focused code proof:

- `ai/AI_TOURNAMENT_MONITOR.html` now renders a `Command Latency Time Series`
  section under the performance panel;
- command total and server timings share one chart;
- local decision timings use their own chart;
- the watcher still reads retained JSON or live watcher summaries only;
- `tests/manual/test_57_gauntlet_watcher_html.py` asserts the new JSON fields
  and rendering helpers stay present.

Focused commands:

```bash
uv run pytest tests/manual/test_57_gauntlet_watcher_html.py -q
awk '/<script>/{flag=1;next}/<\\/script>/{flag=0}flag' ai/AI_TOURNAMENT_MONITOR.html | node --check -
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id standard_skeleton_doors --seed 708
uv run python -m ai.evaluation.gauntlet_runner check ai/evidence/gauntlets/latest.json --require-gate-pass
```

Focused results:

- watcher HTML tests: passed, `2 passed`;
- monitor script syntax check: passed;
- retained summary:
  `ai/evidence/gauntlets/20260717T013756Z-ai-gauntlet-smoke-08d1ff2a.json`;
- retained raw run:
  `ai/evidence/runs/20260717T013756Z-ai-gauntlet-smoke-08d1ff2a-0000-standard_skeleton_doors.json`;
- `gate_status`: `passed`;
- `subjectivity_status`: `passed`;
- `subjectivity_violation_count`: `0`;
- command statuses: `11 accepted`;
- `latency_status`: `failed`.

Fresh retained latency evidence:

- normal command total p95/p99: `41.079 ms`;
- normal server command p95/p99: `36.513 ms`;
- normal local decision p95/p99: `4.768 ms`;
- max command total: `80.828 ms`;
- max server command: `48.205 ms`;
- max local decision: `4.768 ms`.

Latest diagnostic hot spots remain concentrated in the server/engine aftermath:

- `engine.execute_by_index.movement.update_position_ms`: `19.335 ms`;
- `engine.execute_by_index.grid.move_entity.fire_entity_entered_ms`:
  `17.899 ms`;
- `engine.execute_by_index.event_queue.pre_completion.callback.SpatialSensesSystem_ms`:
  `14.444 ms`;
- `engine.execute_by_index.grid.move_light_source.publish_batch_ms`:
  `8.043 ms`;
- `server.publish.followup_epoch.build_decision_epoch_total_ms`:
  `21.058 ms`;
- `server.publish.followup_epoch.get_available_actions_ms`: `16.453 ms`;
- `server.publish.followup_epoch.available_actions.collect_aoe_actions_ms`:
  `11.913 ms`.

Conclusion: the observer client is now scoped and implemented enough to watch
retained gauntlet progress, aggregate timing stages, and per-command latency
time series. The next code target should be the actual command/epoch hot path:
movement-triggered sensory/light publication and area-spell affordance
generation, not more UI plumbing.

## 2026-07-17 - No-Hazard Tile Projection Fast Path

Tightened subjective observation projection for visible tile facts. Before this
slice, each visible tile fact asked `GridMap.is_position_hazardous_for(...)`
even when the current map had no tile or object hazards at all. The movement
diagnostic path showed sensory patch construction as a persistent sub-cost, and
visible tile patching was a measurable part of it.

The projector now computes `has_any_hazards()` once for a snapshot/projection
pass and skips per-tile entity-aware hazard checks when it is false. If any
hazard exists, the projection still uses the normal observer-aware hazard
resolution path, preserving subjectivity and correctness for filters that
depend on the perceiving/acting entity.

Focused code proof:

- `ai/observation/projector.py` carries a per-pass hazard-presence cache in
  `_ProjectionPassContext`;
- snapshot tile projection passes the hazard-presence value through to visible
  tile facts;
- sensory tile projection reuses the same per-pass value while preserving
  entity-aware checks when hazards exist;
- `tests/manual/test_43_ai_runtime_performance.py` asserts safe maps skip
  `is_position_hazardous_for(...)` and hazard-present projections still call it.

Focused commands:

```bash
uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "observation_tile_projection or adjacent_domain_projection or light_batch_candidate_selection or no_hazard_map"
uv run pyright ai/observation/projector.py tests/manual/test_43_ai_runtime_performance.py
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id standard_skeleton_doors --seed 709
uv run python -m ai.evaluation.gauntlet_runner check ai/evidence/gauntlets/latest.json --require-gate-pass
```

Focused results:

- focused pytest slice: passed, `5 passed, 56 deselected`;
- pyright: `0 errors`;
- retained summary:
  `ai/evidence/gauntlets/20260717T014217Z-ai-gauntlet-smoke-954e0e34.json`;
- retained raw run:
  `ai/evidence/runs/20260717T014217Z-ai-gauntlet-smoke-954e0e34-0000-standard_skeleton_doors.json`;
- `gate_status`: `passed`;
- `subjectivity_status`: `passed`;
- `subjectivity_violation_count`: `0`;
- command statuses: `12 accepted`;
- `latency_status`: `failed`.

Smoke comparison against the prior retained run:

- sensory visible tile patch max: `2.790 ms` -> `2.725 ms`;
- sensory update build-patches max: `4.872 ms` -> `4.669 ms`;
- projection project-events max: `5.399 ms` -> `5.187 ms`;
- light movement publish-batch max: `8.043 ms` -> `7.603 ms`;
- follow-up epoch build max: `21.058 ms` -> `20.334 ms`;
- AoE discovery max: `11.684 ms` -> `11.398 ms`.

Current retained latency status:

- normal command total p99: `41.633 ms`;
- normal server command p99: `36.987 ms`;
- normal local decision p99: `6.860 ms`.

Conclusion: this is a correct narrow projection cleanup, not the main latency
fix. The remaining hot path is still command aftermath: moving an actor with
attached light, publishing sensory changes, and rebuilding dense area-spell
decision epochs. The new local-decision p99 outlier also needs continued
rotation evidence before treating it as a systemic policy regression.

## 2026-07-17 - Bright-Light Sensory Refresh Fast Path

Aligned incremental sensory light refresh with the existing full-visibility
fast path. Full FOV filtering already skips observer-specific
`Tile.get_effective_light_for(...)` when every tile is objectively bright or
brighter. Incremental light updates still resolved subjective light for each
changed bright tile, which is unnecessary because the subjective light resolver
only improves dark/dim perception through senses such as darkvision,
truesight, blindsight, or devil's sight. It does not make objectively bright
tiles dark.

The sensory callback now centralizes that rule in
`SpatialSensesCallback._is_tile_lit_for_observer(...)` and reuses it across
incremental entity/object/light refresh paths. Bright-or-brighter tiles return
lit immediately. Darkness, magical darkness, and dim light still call
`get_effective_light_for(...)`, preserving subjectivity for skeleton
darkvision, adjacent darkness, and later magical darkness cases.

Focused code proof:

- `dnd/blocks/sensory.py` imports `Tile` and adds
  `_is_tile_lit_for_observer(...)`;
- `_try_add_visible_entity`, `_recheck_entity_perceivability`,
  `_light_positions_requiring_visibility_refresh`,
  `_update_visibility_for_light_positions`, `_try_add_visible_object`, and
  `_refilter_all_visible_entities` now use the shared helper;
- `tests/manual/test_43_ai_runtime_performance.py` asserts bright incremental
  light refresh does not call `Tile.get_effective_light_for(...)`;
- the same test file asserts dark incremental light refresh still calls
  `Tile.get_effective_light_for(...)`.

Focused commands:

```bash
uv run pytest tests/manual/test_43_ai_runtime_performance.py -q -k "bright_light_refresh or dark_light_refresh or bright_visibility or dark_visibility or light_batch_candidate_selection"
uv run pyright dnd/blocks/sensory.py tests/manual/test_43_ai_runtime_performance.py
uv run python -m ai.evaluation.gauntlet_runner run --mode smoke --arena-id standard_skeleton_doors --seed 709
uv run python -m ai.evaluation.gauntlet_runner check ai/evidence/gauntlets/latest.json --require-gate-pass
```

Focused results:

- focused pytest slice: passed, `5 passed, 58 deselected`;
- pyright: `0 errors`;
- retained summary:
  `ai/evidence/gauntlets/20260717T083734Z-ai-gauntlet-smoke-c7f42054.json`;
- retained raw run:
  `ai/evidence/runs/20260717T083734Z-ai-gauntlet-smoke-c7f42054-0000-standard_skeleton_doors.json`;
- `gate_status`: `passed`;
- `subjectivity_status`: `passed`;
- `subjectivity_violation_count`: `0`;
- command statuses: `12 accepted`;
- `latency_status`: `failed`;
- latency reasons:
  `command_total_p95_over_5ms`, `command_total_p99_over_10ms`,
  `local_decision_p99_over_5ms`.

Same-seed smoke comparison against the previous retained run:

- elapsed match time: `631.960 ms` -> `561.534 ms`;
- max command total: `76.431 ms` -> `72.107 ms`;
- max server command: about `49.991 ms` -> `44.562 ms`;
- max local decision: `6.860 ms` -> `6.161 ms`;
- visible tile patch sample: `2.725 ms` -> `2.741 ms`;
- light movement publish sample: `7.603 ms` -> `8.137 ms`;
- sensory callback total sample: `8.172 ms`.

Conclusion: correctness is intact and the same-seed smoke moved in the right
direction overall, but the specific light-movement publication path remains
too expensive and noisy. The next speed slice should not chase more tiny light
resolver calls first; it should attack the command aftermath structure that
still shows `SpatialSensesSystem`, `GridMap_on_light_movement_event`, event
store callbacks, and follow-up epoch construction dominating the worst
commands.

## 2026-07-21 - Live Balanced Codex Harness Playtest

Ran a complete human-versus-Codex match through the persistent hot harness to
validate the operator experience above the subjective runtime. This was a live
manual playtest, not a traditional-policy or gauntlet run. Codex controlled the
monster faction through `codex.balanced-v2` without invoking the optional
traditional-policy oracle. A human controlled a level-5 Barbarian through
NeuroClient.

### Retained Evidence

- runtime id: `de347bd0-ca43-42fa-b65f-c7dbcca47494`;
- session id: `f4693786-92bb-4db4-b83b-3adf13a569b3`;
- claim id: `8c0ac65b-e58a-46d4-9d94-f82c4d3b5ad7`;
- encounter id: `bf02a0b3-acdd-4e77-85b7-c006e82b1708`;
- profile: `codex.balanced-v2`;
- profile manifest digest:
  `461568ed37a82a6a319e6fb4baa7d58a6d96eee6e5cbbc7e4dad861c4565a00b`;
- finalized transcript:
  `game_logs/codex_sessions/20260721T163157.658040Z-de347bd0-ca43-42fa-b65f-c7dbcca47494.json`;
- outcome: monsters won in round 3;
- surviving controlled entity: `monster_3`, 40/40 HP;
- defeated controlled entities: `monster_1`, `monster_2`;
- observed damage dealt/taken: `58 / 35`;
- commands: `15`;
- explicit inspections: `1`.

The finalized JSON contains 413 ordered records:

| Record type | Count |
|---|---:|
| subjective frame | 249 |
| agent event | 80 |
| operator interaction | 36 |
| command intent | 15 |
| command acknowledgement | 15 |
| command lifecycle | 15 |
| session start | 1 |
| subjective snapshot | 1 |
| terminal summary | 1 |

### Tactical Sequence Exercised

1. `monster_1` attacked the Barbarian with its scimitar for 2 damage, used
   `Nimble Escape: Disengage`, and retreated from `(12,3)` to `(14,3)`.
2. `monster_3` allocated all five darts from a level-3 `Magic Missile` to the
   same target for 21 force damage, then drank a Greater Invisibility potion.
3. `monster_2` made a legal Shortbow attack and missed.
4. During the human turn, the Barbarian killed both low-HP monsters and opened
   the door. The hot process remained idle until a new controlled epoch.
5. `monster_3` cast another five-dart level-3 `Magic Missile` for 10 damage,
   drank a Haste potion, received the new same-turn action in the follow-up
   epoch, and spent it on a four-dart level-2 `Magic Missile` for 14 damage.
6. The hasted caster then used a safe route witness to move from `(12,7)` to
   `(14,12)` while invisible.
7. The human healed from 3 HP to 10 HP and advanced. A final four-dart level-2
   `Magic Missile` dealt 11 damage and ended the encounter.

This sequence deliberately covered repeated-target allocation, resource and
item costs, multiple commands inside one variable-length turn, same-turn
action-economy mutation, route execution, wait/wakeup behavior, subjective
memory, and terminal finalization.

### What Worked

- The hot daemon maintained one persistent `SubjectiveRuntime`; ordinary
  decisions did not bootstrap a new world or poll `/available-actions`.
- `hot-watch` slept across human turns and resumed on the next controlled
  decision epoch.
- Repeated `--extra-target` values correctly represented all Magic Missile
  allocations, including repeated use of one target UUID.
- Every accepted command produced a new revision and current legal follow-up
  affordances. Haste adding an immediate action was visible without a manual
  state refresh.
- Safe movement consumed a server-issued row and preserved its route witness;
  the local helper did not manufacture a legal destination.
- The match remained active in the backend and in the Codex runtime when an
  unrelated NeuroClient edit reset the browser UI. The next subjective epoch
  still arrived correctly.
- The terminal frame cleared the actor and epoch, exposed a subjective winner,
  and finalized the transcript automatically.
- No objective endpoint or policy oracle was used. No hidden-information leak
  was observed in this playtest. This is supporting evidence, not a substitute
  for adversarial subjectivity tests.
- Knowledge state remained explicit: objects no longer in view appeared as
  `remembered` rather than silently disappearing or remaining falsely visible.

### Harness Friction Found

#### 1. Balanced automatic output is still much too large

Two ordinary `hot-watch` responses were approximately 14,255 and 12,783
tokens. `action_families` provides the useful tactical index, but the response
also includes a long capability catalog that repeats many of the same names,
costs, semantic keys, and tags. The full catalog is valuable for inspection
and ablation evidence, but it should not be repeated automatically every turn.

Required direction:

- keep actor, economy, visible/remembered contacts, changed facts, warnings,
  action-family summaries, multi-target requirements, and recent causal events
  in the automatic turn brief;
- move the complete capability catalog behind a typed local inspection call;
- provide an explicit manifest/digest change notice when capabilities change;
- retain all omitted data in the local canonical document and transcript.

#### 2. Command responses repeat the whole follow-up representation

Several `hot-execute` and `hot-end-turn` calls returned thousands of tokens;
one end-turn response was about 9,417 tokens. The command result needs the
status, causal ids, concise resolution, resulting revision, changed economy,
important observed effects, and whether another controlled action is possible.
It does not need to inline the complete next-turn representation because the
runtime already stores it locally.

Required direction:

- make CLI command output a compact typed command delta by default;
- keep the complete follow-up available through `hot-turn`,
  `hot-representation`, and local inspection;
- preserve the current full response as an explicit diagnostic mode.

#### 3. Exact action-row lookup is functional but unnecessarily generic

Finding `position|Move|pos=14,3` with `hot-search` scanned 16,853 JSON nodes to
return one JSON pointer. Direct execution by a known stable row id was clean,
but discovering exact movement/AoE rows should not require searching the whole
canonical document.

Required direction:

- add typed local indexes for row id, action family, target UUID, and target
  position;
- expose exact local lookup commands without contacting the game server;
- keep generic search for exploratory inspection, not routine row selection.

#### 4. Multi-target allocation is correct but verbose for repeated targets

The explicit repeated `--extra-target` interface is unambiguous and worked,
but four identical flags for a five-dart Magic Missile are cumbersome.

Required direction:

- retain the exact repeated-target list in the typed command;
- add a convenience syntax such as target UUID plus allocation count;
- expand convenience input into the same typed list before validation and
  transcript recording, so semantics and experimental evidence do not change.

#### 5. Reported local command latency is not sufficiently decomposed

Observed CLI `local_total_ms` values were roughly 66-123 ms. These samples
include more than tactical computation: a fresh CLI process, local HTTP,
serialization, daemon work, server submission, engine execution, stream
reconciliation, representation rebuilding, and output construction. The
persistent runtime itself remained responsive, but the current headline does
not show which boundary the operator paid for.

Required direction:

- report CLI startup/client overhead, local daemon processing, server command,
  stream wait/reduction, representation projection, and output serialization
  separately;
- preserve end-to-end wall time as a distinct user-experience metric;
- do not optimize from the aggregate number without this decomposition.

#### 6. Semantic coverage is technically complete but unevenly specific

No available capability was marked unknown, but the caster's initial turn
reported 34 capabilities with 14 category fallbacks. Generic category semantics
are better than display-name inference, but they do not provide the same
logical prerequisite/effect quality as exact or structured spell semantics.

Required direction:

- list category-fallback semantic keys in inspection and retained evidence;
- prioritize exact structured semantics for actually exercised spells, items,
  reactions, and class features;
- keep `unknown_count == 0` separate from the stronger claim that all semantics
  are tactically and logically complete.

#### 7. Terminal statistics explicitly remain incomplete

The subjective terminal summary correctly declares the following incomplete:
`resources_spent`, `temporary_hp_gained`, `condition_names`, and
`unperceived_events`. Declaring incompleteness is preferable to inventing a
score, but a PvP-style result screen will need all perceived resource and
condition statistics that can be derived from the retained event history.
`unperceived_events` must remain unknowable to a participant summary; an
authorized objective observer/replay summary is a different product.

### Acceptance Evidence From This Match

The vertical harness path is operational: one balanced Codex process can remain
attached, wait through another participant's variable-length turn, inspect only
its local subjective state, execute server-issued affordances, receive causal
follow-up epochs, and finish with a retained terminal transcript. The next
harness pass is therefore a representation-density and operator-ergonomics
pass, not another transport rewrite.
