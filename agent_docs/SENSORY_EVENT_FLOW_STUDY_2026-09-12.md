# Sensory event flow study — September 12, 2026

Status: read-only investigation requested after the native timing work. The
empty-optical-query and duplicate-edge changes remain unimplemented. This study
asks why perception and AI knowledge are reconstructed despite existing events
and incremental inputs. It does not change subjectivity or event lifecycle rules.

## Finding

The input and output support incremental work, but the current native sensory
implementation narrows only the observer set, then recomputes each selected
observer's perception. It derives an output delta by comparing full before/after
snapshots. Native AI does not consume that delta stream; it separately rebuilds
its subjective world from live entities and GridMap at decision and movement
continuation boundaries.

These are two distinct issues. A consumer can apply an existing sensory delta
without perception queries. Producing that delta still requires the native
rules, but a changed entity or light region does not automatically require all
perception layers to be recomputed.

## Current producer, in execution order

1. The native owner commits a spatial change. `Entity.update_entity_position`
   commits the position and GridMap membership before publishing LEFT/ENTERED.
2. GridMap settles related state, including attached light, inside the cause's
   lifecycle. Sensory runs through the existing indexed pre-completion system.
3. `SpatialSensesSystem.candidate_observer_uuids` uses cell subscriptions,
   known-contact reverse indexes, and hints to select observers. A paired
   movement LEFT notification is already excluded; ENTERED owns the refresh.
4. `SpatialSensesSystem.__call__` captures a snapshot and calls
   `recompute_observer` unconditionally for each selected observer.
5. That function resolves capabilities, obtains geometric FOV, filters optical
   cells/light/obscurements, computes nonvisual reach where applicable, collects
   boundary evidence, scans contacts, replaces perception and updates indexes.
   Geometric FOV has a GridMap revision cache; this is not necessarily a fresh
   shadowcasting solve. The subsequent filtering and scans still happen.
6. Before/after comparison marks navigation dirty where needed and constructs
   `SensoryUpdateEvent`. An unchanged result produces no sensory event, after
   paying for the recomputation. Produced events retain the actual causal parent.
7. Navigation is separately materialized at existing query/action boundaries.
   It is not rebuilt automatically for every sensory callback.

Source: [sensory owner](../dnd/blocks/sensory.py), especially `recompute_observer`
at 578, candidate selection at 924, and dispatch at 984;
[spatial commits](../dnd/core/gridmap.py) at 229/2123/4045;
[Entity movement/navigation](../dnd/entity.py) at 767/4326;
[EventQueue pre-completion](../dnd/core/events.py) at 1939.

## What the existing input hints do today

The [schema](../dnd/core/events.py) at 3179 explicitly describes layer-specific
incremental updates. Current consumption falls short of that description.

| Input | Current use |
|---|---|
| Entity entered/left/died | Candidate positions and known-entity observers; no targeted contact update |
| Object placed/removed | Candidate positions and known-object observers; no targeted object update |
| `perceivability_entity` | Select observers, then recompute all their contacts |
| `light_changed_positions` | Select overlapping observers, then refilter their full optical field |
| `requires_paths` | Expand candidate selection and dirty navigation after refresh |
| Directional positions/neighbors | Select affected observers |
| `directional_channels_changed` | Does not select sensory computation layers |
| `requires_fov` | Not read by current sensory |
| `requires_propagation_recompute` | No current consumer found |
| `requires_light_recompute` | GridMap settles actual lighting before completion |

The event's light-value map also exists; current sensory reads live tile light
again instead of applying those changed cells as an incremental input.
Those objective light values still require the existing observer-specific
special-sense resolution; they are not already the observer's final light values.

## Observed native execution

A temporary diagnostic delegated every call to the unchanged native functions
and inspected the actual before/after values and returned sensory events. It ran
the established eight-human-turn encounter, retaining four rounds, 1,175 event
versions and the established actor outcomes. Setup and teardown were excluded.
This is one concrete encounter, not a claim about every condition or map.

| Cause/observer | Full refreshes | Actual sensory result |
|---|---:|---|
| Another entity moves; observer stays put | 117 | 90 contact/navigation-only deltas; 27 no delta. All 117 retained identical visible cells and light. |
| Observer itself moves | 39 | 30 emitted deltas; 9 were already updated by an earlier light child. |
| Light change | 36 | 36 emitted deltas; some also captured already-committed movement. |
| Condition application | 20 | No delta in these exercised cases. |
| Condition removal | 14 | No delta in these exercised cases. |
| Turn start | 14 | No delta in these exercised cases. |

The exercised conditions were Dodging, HasAttacked and HasTakenDamage. This is
evidence of broad recomputation for these transitions, not a rule that condition
or turn events can be ignored. Passive perception, special senses, visual access,
subject perceivability and world changes must still have their actual owners.

One stationary witness example rescanned its 172-cell visible field, retained
identical cells and light, and emitted exactly one changed entity contact plus
navigation dirtying. Its input carried `requires_fov=False`. Across stationary
witness refreshes the diagnostic measured about 0.51s; this is an attribution
from this run, not a measured saving from an implementation.

Raw rows and summaries are in
`.runtime/performance-recovery/native-play-20260912/sensory-deltas.json` and
`sensory-delta-summary.json`; the temporary runner is `sensory_delta_probe.py`.
The previous targeted timing results remain in
[the performance record](PERFORMANCE_REPAIR_RESULTS_2026-09-12.md).

## An actual causal ordering that narrowing must preserve

The current movement chain can be:

1. Position and Tile membership commit.
2. ENTERED advances to EFFECT.
3. Its attached light moves and publishes a light child.
4. Sensory refresh during that child already sees the committed new origin and
   entity positions, and publishes those perception changes.
5. ENTERED reaches its own pre-completion refresh, whose result may be unchanged.

The diagnostic observed this, not merely a hypothetical concern: nine mover
refreshes at ENTERED emitted nothing because the light child had already updated
them. In one light child, six hinted light cells accompanied an observer origin
change, one newly visible cell and fifteen removed cells. Twenty-seven stationary
witness ENTERED refreshes likewise found contacts already current.

Therefore a replacement cannot classify required work solely by the immediate
event's type or its `requires_fov` flag. It must also account for the committed
origin/capability changes and the existing causal spatial context. This does not
require inventing a new ordering or waiting for the entire action to end.

## Incrementality existed before reconstruction

`4ebe523` already combined an indexed `SpatialSensesSystem` with a targeted
`SpatialSensesCallback._apply_hint`. It updated specific contacts/light regions
and compared observer capabilities before selecting broader work.
Its direct child `205fd67` removed that callback and recomputed selected observers
fully. `16a6bfe` and this recovery branch inherited that choice.

The old helpers establish the intended scoped work; they used older tuple contacts
and simpler boundary/nonvisual semantics. Restoring those files wholesale would
discard current capabilities. The current typed contacts, height/edge rules,
source-owned senses and event-only replay are the contracts to retain.

## AI's second reconstruction path

[`SubjectiveAIStateProjector.project_world`](../dnd/ai/runtime/state_projection.py)
at 91 increments a projection-call counter, resolves live controlled entities,
and rebuilds from their senses and current world state. Assignment startup does
not install a knowledge-event consumer. Policy memory reduction then receives
that rebuilt world. The native controller's event cursor accessor is diagnostic;
it does not turn world construction into an event fold.

Reusable current pieces already exist:

- [`reduce_senses_snapshot`](../dnd/types/senses.py) at 129 consumes the neutral
  `SensoryDelta` contract, including recorded initialization, contacts, cells,
  light and capability after-values. Native sensory events satisfy it.
- Current [player projection](../game/player_projection.py) and
  [player reduction](../game/player_reduction.py) fold recorded actor/world facts
  and preserve acquisition-time admissions. They already account for sensory
  children preceding their spatial parent's completion.
- EventQueue has immediate event callbacks; action batching does not delay them.
  A new server, event bus or background process is unnecessary for this connection.
- The AI-shaped `apply_observation_frame` reducer exists, but its native caller
  is absent. Its retired server producer uses obsolete sensory field names;
  reconnecting that producer would not satisfy current event contracts.

Directly substituting the Pygame player state would also be incomplete. AI merges
the assignment's explicit controlled observers, with their attribution and existing
memory rules. Player state has one observer. Its actor representation omits fields
AI currently uses, including faction/creature type/affinities and condition-related
details. Some are already in birth events and are discarded by that player fold;
this is not evidence that native initialization lacks them. Dynamic after-values
need their actual owners checked before claiming complete AI event coverage.

AI continuation also runs after each committed movement Step while the enclosing
Movement lineage remains open. The visual capture requires complete lineages.
Knowledge must advance at the existing Step boundary; rendering can still wait
for the complete lineage. Routing AI through finished visual clips would break
that established separation.

The historical SDK at D&D commit `74cc1f9`,
`sdk/typescript/src/subjectiveJournal.ts:468–482`, reduces and installs the
authoritative world before queuing presentation. NeuroClient at `d274f2d`,
`app/src/engine/eventIngestion.ts:318`, previews presentation; `:541` commits it;
`:826–828` independently wake presentation. These sources support the intended
separation and do not justify current live rebuilding.

## Direction established; implementation not selected here

The next design should restore scoped native updates using existing change facts
and retained sensory state, preserving current contact resolution. A moving
observer or actual geometry change can require a broad solve; a stationary
observer tracking one nonblocking subject has a much smaller dependency. Light
and nested movement must retain the concrete ordering above. Condition names
should not become a manual list of exceptions; actual changed capabilities and
subjects determine the relevant work.

Downstream, AI knowledge should advance from those authoritative event facts at
its existing owner and consumption boundary. The neutral reducers are reusable;
the shared-observer composition and required AI fields need explicit mapping.
Action availability/execution authority remains an engine query, distinct from
reconstructing already-known world facts.

Existing cold-recompute equivalence, directed-boundary/height, nonvisual sense,
light/door ordering, initial replay and paired visibility/concealment cases are
the behavioral references. This investigation added no tests, runtime machinery
or production changes. Anti-slop reviewer `recorded_gallery` independently traced
hint consumption/history; anti-OOP reviewer `lifecycle_source_review` traced AI
ownership and reusable reducers. Root recorded the actual delta trace serially.
