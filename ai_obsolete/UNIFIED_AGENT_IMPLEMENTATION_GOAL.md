# Unified Subjective AI Architecture And Iterative Self-Play Goal

Status: active governing goal

Architecture reference:
[UNIFIED_AGENT_ARCHITECTURE.md](UNIFIED_AGENT_ARCHITECTURE.md)

Validation evidence:

- focused maintained behavior and performance regressions under `tests/ai/`
  and `tests/manual/`;
- exact retained Direct Codex artifacts under `ai/evidence/direct_codex/` and
  `ai/evidence/direct_codex_runs/`;
- the live read-only observer in [AI_AGENT_OBSERVER.html](AI_AGENT_OBSERVER.html).

The retired iteration dashboard, append-only stats/log ledgers, tournaments,
Elo reports, gauntlets, and promotion artifacts are not part of the active
architecture.

## 1. Objective

Build and validate one clean agent architecture for NeuroDragon that serves both
traditional videogame AI and LLM-controlled agents.

This document governs the whole continuing task. Individual implementation plans,
bug fixes, tactical findings, benchmarks, and playtest batches are subordinate to
it. Finishing the currently visible module or correcting the most recent combat
mistake does not complete the goal.

This is both an architecture goal and a continuing gameplay-improvement goal.
Implementing the runtime and policy framework without proving it through repeated
play is insufficient; accumulating playtest observations without replacing the
exception-driven policy architecture is also insufficient. The work is complete
only when the unified design is operational, measurably fast, strictly subjective,
and demonstrated through the required rotating self-play loop.

The implementation must preserve the engine's event-driven authority and strict
session subjectivity. Every controller must receive the same typed subjective
world, the same decision epochs, and the same legal action affordances. Policies
may reason differently, but they must not receive different truths or bypass the
same command authority.

The default AI must become a genuine hierarchical policy rather than an ordered
collection of action-specific exceptions. Its recommended structure is:

```text
subjective event history
    -> materialized subjective world
    -> typed facts and topology
    -> policy host
        -> goal or tactical-mode selection
        -> hierarchical behavior tree
        -> utility ranking at choice points
        -> bounded planning for multi-epoch objectives
    -> one epoch-authorized command
```

LLM agents must use this same structure. They may:

- observe and explain the default policy;
- select goals or tactical modes;
- modulate exposed behavior-tree parameters and utility weights;
- propose semantic multi-epoch plans;
- answer explicit escalations from the default policy;
- directly choose a legal current action when exact control is required.

LLM control must therefore be capable of operating both above the behavior tree
and at the direct-action level. It must not require a separate world model,
separate action endpoint, or separate tactical implementation.

This architecture must be developed through repeated real play. Each iteration
must discover friction in both the agent experience and the opposing AI, make a
focused improvement, record evidence, and validate that the improvement survives
different characters and scenarios.

### 1.1 Scope Hierarchy

The goal has four nested products. None may be substituted for another:

1. **Correct subjective substrate.** The server projects complete authorized
   knowledge, legal affordances, command results, and causal event deltas into
   one replayable typed client state.
2. **Unified decision architecture.** Traditional AI and LLM controllers share
   facts, action semantics, policy context, proposals, routines, traces, and the
   authoritative command path.
3. **Iteratively stronger play.** Retained games expose agent-interface friction
   and enemy-policy weakness; systemic fixes improve both without growing an
   ordered list of matchup exceptions.
4. **Reproducible evidence.** Tests, benchmarks, raw artifacts, the narrative
   log, and the JSON-driven dashboard show what changed and whether it survived
   the rotation.
5. **Gauntlet validation.** A structured AI-vs-AI gauntlet runs the production
   policy across a curated arena/monster/class matrix, records durable match
   summaries, and exposes live progress/results through a lightweight watcher.

The most recent tactical defect never becomes the whole project. A local fix is
accepted only when it belongs to the correct architectural layer and preserves
the wider contracts above.

## 2. Overall Iteration Loop

The continuing development loop is:

```mermaid
flowchart LR
    P["Play complete games"] --> O["Observe agent and enemy-AI friction"]
    O --> R["Record raw evidence and diagnosis"]
    R --> I["Implement one focused improvement"]
    I --> T["Run focused contract and policy tests"]
    T --> V["Replay rotating validation games"]
    V --> D["Update JSON evidence and HTML dashboard"]
    D --> G["Run/update gauntlet slice"]
    G --> W["Watcher displays progress and summary"]
    W --> P
```

Each cycle must include all of the following:

1. Play before changing behavior.
2. Record the observed problem using subjective inputs, decision traces, command
   results, and timings.
3. Classify the problem before implementing a fix.
4. Add or update a focused regression test.
5. Implement the smallest architectural improvement that explains the problem.
6. Replay the original situation.
7. Validate against the character rotation and at least one different scenario.
8. Update structured run data, the narrative log, and the generated dashboard.
9. When the change affects policy/content balance, run the smallest meaningful
   gauntlet slice and update the gauntlet summary.

The work must not become a sequence of speculative policy changes made without a
completed game or reproducible fixture.

### 2.1 Continuity And Progress Ledger

The iteration log is also the durable progress ledger. Before beginning a new
game or implementation slice, recover and record:

- the current architecture phase and incomplete acceptance criteria;
- the current position in the required character/controller rotation;
- the latest retained artifact and replayable failure fixture;
- open correctness, subjectivity, policy, UX, and latency findings;
- the one primary hypothesis being tested next;
- focused tests and benchmarks that guard previous improvements.

After every game, record findings for both perspectives even if only one is
changed in that cycle:

- **agent experience:** what information was ready, what required local
  querying, what was confusing, and what work or tokens were wasted;
- **opposing AI:** what it knew, which candidates it considered, why it chose its
  action, and whether the weakness belongs to facts, semantics, hierarchy,
  utility, planning, or content.

An observed defect is not closed merely because code changed. Closure requires a
focused regression, replay of the original situation, and a cross-character or
cross-scenario check. Failed, aborted, leaked, hung, or over-budget games remain
artifacts; they are not deleted from the evidence series.

The loop advances one completed rotation position at a time. A failed position
may be retried after its blocking defect is addressed, but repeated retries must
not turn into unscheduled specialization on that character. Once the fixture is
reproducible, implementation and focused tests replace further identical games
until the defect is ready for replay.

## 3. Problem Classification

Every observed friction point must be assigned to one primary layer:

| Layer | Typical failure |
|---|---|
| Subjective projection | Hidden information leaks, missing visible facts, stale memory |
| Runtime materialization | Cursor gap, duplicate application, world divergence |
| Action semantics | Legal row lacks effects, costs, targeting, or information meaning |
| Fact processing | Concentration, topology, threat, resource, or relationship fact missing |
| Policy structure | Incorrect branch, interruption, or plan-continuation behavior |
| Utility model | Correct candidates exist but are ranked badly |
| Planner | Multi-step objective is not discovered, repaired, or completed |
| LLM presentation | Required information exists but is costly or awkward to retrieve |
| Command protocol | Stale, rejected, duplicated, or unauthorized command |
| Performance | Correct path takes longer than its explicit budget |
| Content | Existing scenarios cannot exercise the mechanic under study |

Fix the owning layer. Do not compensate for a projection problem with policy
omniscience, a semantic problem with action-name parsing, or a policy problem by
changing creature statistics.

## 4. Non-Negotiable Invariants

### 4.1 Event Authority

- All game-state changes continue to flow through the D&D engine event system.
- The AI stream is a session-subjective projection of engine events, combat logs,
  sensory events, decision epochs, and controller command results.
- The AI runtime must not become an independent state bus.
- Accepted commands produce ordinary engine events and subsequent subjective
  projections.
- Rejected and stale commands remain controller-protocol events and do not
  mutate objective game state.

### 4.2 Subjectivity

Subjectivity is an absolute correctness boundary.

- Policies may consume only facts authorized for their session.
- Hidden enemies, objects, routes, hazards, statistics, and combat outcomes must
  not enter the subjective world, action affordances, derived facts, telemetry,
  policy memory, LLM prompt, or self-play decision input.
- Controlled observers may contribute a union of knowledge, but observer origin
  and freshness must remain explicit.
- Facts must distinguish visible, seen, remembered, inferred, and unknown.
- Unknown is not equivalent to false.
- Darkvision, light, hearing, blockers, stealth, invisibility, perception, and
  remembered contacts must be evaluated through engine senses rather than
  policy assumptions.
- Information-gathering actions may be valued by expected information gain, but
  their value must not reveal the hidden answer.
- Objective state may be used only by offline validation after a game, never as
  controller input.

Any confirmed information leak is a release-blocking defect. Tactical iteration
pauses until the leak is fixed and covered by a regression test.

### 4.3 Server Legality

- The server remains the sole authority for legal actions.
- Every active controlled actor receives a complete `DecisionEpoch` containing
  current affordances and action economy.
- Traditional AI and LLM agents must not deduce or reconstruct the legal action
  set client-side.
- Row identifiers are valid only for their basis epoch.
- Multi-epoch plans retain semantic intents, never future row identifiers.
- Every command is revalidated by the normal engine executor.
- LLM direct commands additionally require current ownership and a live,
  generation-fenced takeover lease.

### 4.4 One Subjective State

- One fully typed materialized subjective world is the source of truth for every
  production AI policy.
- Tactical summaries, briefs, indexes, hypotheses, and policy inputs are derived
  views, not competing world states.
- Compact policy and Codex summaries may exist only as read-only projections of
  the materialized subjective world. The former `TacticalState` migration path
  has been removed.
- No production policy may read live `Entity` objects or objective server state.
- No normal policy path may poll `/available-actions`; affordances arrive through
  the decision epoch.

### 4.5 One Command Writer

- Policy nodes generate proposals and never execute commands.
- A policy host arbitrates proposals and submits at most one command per epoch.
- Traditional policy, planner, and LLM outputs use the same proposal and command
  contracts.
- Mutable policy state is external to immutable policy definitions and keyed by
  `(session_id, actor_uuid, policy_id)`.
- Group or faction coordination memory is explicit and separate from actor
  memory.

## 5. Target Architecture

The implementation target is defined in
[UNIFIED_AGENT_ARCHITECTURE.md](UNIFIED_AGENT_ARCHITECTURE.md). The following
requirements are mandatory for this goal.

### 5.1 Neutral Protocol Layer

Create dependency-neutral typed contracts for:

- observation facts, snapshots, and subjective event envelopes;
- decision epochs and legal affordances;
- action semantics;
- command requests, acknowledgements, and streamed results;
- agent telemetry and replay artifacts.

Protocol models must import neither D&D engine classes nor runtime or policy
implementations. Decision epochs and commands must live below observation
envelopes because an observation may carry an epoch.

### 5.2 Subjective Runtime

The runtime must:

- bootstrap exactly once from a subjective snapshot;
- consume ordered subjective event envelopes continuously;
- apply duplicate frames idempotently;
- detect cursor gaps and bounded-history eviction;
- resynchronize only on explicit recovery conditions;
- maintain the current decision epoch locally;
- correlate commands with streamed command results;
- expose local read/query surfaces to both LLM and traditional policies;
- avoid post-action snapshot reloads on the normal accepted path.

### 5.3 Typed Knowledge Layer

The knowledge layer derives typed facts from the subjective world. Initial
first-class facts must include:

- active actor, ownership, round, turn, and action economy;
- known entities, relationships, death state, and freshness;
- visible threats, remembered contacts, target pressure, and ally state;
- concentration, conditions, immunities, resistances, and relevant resources;
- known objects, doors, interaction reachability, and object state;
- traversable topology, safe paths, hazards, slow terrain, water, blockers,
  chokepoints, line of sight, and observation frontiers;
- multi-target allocation and area-effect geometry;
- action semantic indexes and candidate families;
- hypotheses that remain explicitly distinct from observed facts.

Core facts must be typed fields or typed records. A generic extension namespace
may support experiments, but core policy behavior must not communicate through
unvalidated string-keyed bags.

### 5.4 Policy Host

The policy host must:

- select the configured policy profile;
- own actor-scoped policy memory;
- apply, validate, and expire LLM directives;
- tick the default hierarchical policy;
- invoke bounded planning only where useful;
- receive direct or high-level LLM proposals;
- arbitrate proposals through explicit authority and priority rules;
- resolve semantic intents against the current epoch;
- enforce decision deadlines and deterministic fallback;
- submit one command through the subjective runtime;
- consume the streamed result before deciding again;
- emit a complete decision trace.

### 5.5 Default Traditional Policy

The default policy must be a real hierarchical behavior tree. A flat ordered list
of action-specific branches does not satisfy this goal.

The default structure should combine:

- terminal and legality guards;
- emergency and survival behavior;
- active-plan continuation or repair;
- utility-based tactical goal selection;
- combat, support, control, interaction, exploration, and end-turn subtrees;
- utility selectors for comparing candidates inside a tactical concern;
- bounded planning for multi-step spatial or interaction objectives.

Behavior-tree conditions consume shared typed facts. Leaves return typed
proposals. Leaves must not own HTTP clients, execute actions, refresh snapshots,
or maintain private copies of world state.

FSMs may represent coarse persistent modes such as exploration, combat,
disengagement, or objective defense. Utility scoring compares candidates. GOAP
or another bounded planner handles meaningful multi-epoch objectives. These are
composable policy techniques over one context, not rival runtime architectures.

### 5.6 LLM Participation

The LLM adapter must support these authority levels:

1. **Observer:** inspect subjective state and policy traces without writing.
2. **Goal director:** select or reprioritize typed goals.
3. **Policy modulator:** modify allowlisted weights, thresholds, optional
   subtrees, focus targets, or resource budgets with finite scope and expiry.
4. **Plan proposer:** submit semantic intents for validation and epoch-by-epoch
   resolution.
5. **Direct actor:** select an exact current legal row under a fenced takeover
   lease.
6. **Escalation handler:** answer bounded questions raised by the default policy.

Modulation is typed data. The LLM must not generate or patch arbitrary Python in
the production controller path. Tree definitions and node implementations remain
registered engine assets. Overrides include an issuer, scope, basis cursor,
policy hash, bounds, and expiry.

The LLM may remain hot across the encounter and wait for subjective events while
preserving one conversation history. Lease renewal is independent from waiting
for observations. Timeout, invalid output, stale authority, or disconnection must
fall back deterministically to the default policy.

### 5.7 Agent Observability

Gameplay events and agent events remain separate but correlated:

- gameplay events describe what happened in the game;
- agent events describe what the policy observed, derived, considered, selected,
  rejected, and recovered from.

Every decision trace must identify:

- session, actor, observation cursor, epoch, command, and source event cursors;
- policy profile, immutable policy hash, and controller mode;
- active goal, plan, directives, and relevant memory;
- behavior-tree nodes visited and statuses;
- facts read and facts invalidated;
- candidates generated, filtered, and ranked;
- hard-constraint failures and utility score components;
- planner expansion and selected next intent;
- LLM model/prompt/directive identifiers when present;
- selected proposal and arbitration reason;
- command result, recovery, and fallback;
- timing for every stage.

The server must retain a bounded, monotonic per-session agent-event history and
SSE stream. NeuroClient and developer tools may observe it without gaining
authority to mutate policy or gameplay state.

## 6. Logical Annotations And Approximate World Model

Logical annotations are a required product of this work. They provide a typed,
inspectable approximation of action and routine meaning that supports debugging,
behavior-tree conditions, utility scoring, and future planning.

They are not comments, prose descriptions, or a second legality engine.

### 6.1 Action Semantics

Each standard action family must expose semantic annotations such as:

```python
class ActionSemantics(BaseModel):
    semantic_id: str
    tags: frozenset[ActionTag]
    preconditions: FactExpression
    guaranteed_effects: tuple[LogicalEffect, ...]
    conditional_effects: tuple[ConditionalEffect, ...]
    stochastic_effects: tuple[StochasticEffect, ...]
    economy_cost: ActionCostProfile
    resource_effects: tuple[ResourceEffect, ...]
    concentration_effect: ConcentrationEffect | None
    topology_effects: tuple[TopologyEffect, ...]
    information_effects: tuple[InformationEffect, ...]
    targeting: TargetingSemantics
```

The first annotation pass must cover:

- movement, Dash, Jump, Disengage, Dodge, and end turn;
- weapon and spell attacks;
- healing, buffs, debuffs, control, summons, and area effects;
- concentration start, preservation, replacement, and termination;
- multi-target selection and repeated target allocation;
- doors and other environment interactions;
- actions that reveal space, cross corners, alter light, or change topology;
- voluntary versus forced movement;
- action, bonus action, reaction, movement, item, charge, and spell-slot costs.

Annotations originate beside the engine action or a stable action-family
registry. They travel inside decision epochs and are reused by policy, LLM
presentation, telemetry, tests, and planning. The same meaning must not be
recreated independently in action-name tables.

### 6.2 Three-Valued Preconditions

Preconditions over subjective state use at least:

```text
TRUE
FALSE
UNKNOWN
```

Unknown facts cannot be treated as false merely to simplify planning. A planner
may instead choose an information-producing action or construct a contingent
plan.

### 6.3 Routine Semantics

High-level policy routines also expose logical annotations:

- facts read;
- applicability condition;
- protected invariants;
- generated intent family;
- expected progress facts;
- interruption and invalidation conditions;
- possible failure outcomes;
- resources the routine may consume;
- observation changes it expects to cause.

For example, a move-to-door routine should state that it requires a known closed
door and a known traversable approach, preserves the interaction action when
ordinary movement can reach the door, expects adjacency rather than an opened
door, and invalidates when the door opens, disappears, or becomes unreachable.

Annotations may initially be diagnostic only, but they must be serialized,
tested, and visible in the policy trace. They are intended to become the shared
language for behavior-tree conditions and bounded planning.

## 7. Tactical Quality Requirements

The new architecture must preserve working behavior while improving tactical
coherence.

### 7.1 Action Economy

- Policies reason over the whole variable-length turn, not one action per turn.
- After every action result, the policy receives a new epoch and replans against
  remaining action, bonus action, reaction, movement, and resources.
- The policy must understand when ordinary movement preserves an action that
  Dash would consume.
- An interaction that may reveal new information should preserve later economy
  when practical.
- The policy should use useful remaining economy or explicitly end the turn.
- Free, item, charge, class, spell-slot, and condition-gated resources must be
  represented rather than inferred from display text.

### 7.2 Spellcasting And Concentration

- Offensive casters must compare castable ranged attacks, area effects, control,
  and support before walking into melee.
- Multi-target spells must expose target count, repeated-target rules, allocation,
  affected entities, and friendly-fire semantics.
- Existing concentration is a first-class state and resource.
- A new concentration action must include the value lost by replacing the
  current effect.
- Policies must not repeatedly replace valuable concentration without an
  explicit comparative reason.
- Expected damage, control, support, resource cost, and concentration cost must
  appear separately in candidate traces.

### 7.3 Navigation, Doors, And Exploration

- Movement uses subjectively known topology and actual path cost, not Manhattan
  distance through walls, water, slow terrain, or blockers.
- Closed doors are topology-changing planning objects.
- If no enemy is known, the policy may navigate toward a known interaction,
  remembered objective, or observation frontier, but never toward an unknown
  enemy's objective position.
- Opening a door, crossing a corner, entering a new light boundary, or moving to
  a frontier should carry information-gain semantics.
- The policy may value potential revelation without learning what is hidden.
- Door behavior must support move-to-adjacency, open, observe the resulting
  event/epoch, and replan.

### 7.4 Coordination And Safety

- Multi-entity controllers maintain actor-specific state and explicit shared
  faction coordination.
- Target focus, support, spacing, chokepoints, threat, and friendly-fire rules are
  derived from shared semantics and facts.
- The policy must not target unknown entities or use hidden paths.
- Reactions and out-of-turn decisions receive explicit reaction epochs and do
  not borrow ordinary-turn assumptions.

## 8. Required Character And Scenario Rotation

The loop must always rotate among Barbarian, Sorcerer, and skeleton control. Do
not optimize repeatedly against only one character, faction, build, spell, or
arena.

A normal six-game validation rotation exercises both controller families, both
hero builds, and the skeleton faction:

1. Codex-controlled Barbarian versus default skeleton AI.
2. Codex-controlled Sorcerer versus default skeleton AI.
3. Codex-controlled skeleton faction versus default Barbarian AI.
4. Codex-controlled skeleton faction versus default Sorcerer AI.
5. Traditional AI versus traditional AI in the Barbarian matchup.
6. Traditional AI versus traditional AI in the Sorcerer matchup.

The Codex games must collectively exercise both exact direct action and
higher-level goal or policy modulation; a later batch may exchange which Codex
position uses which mode. The two autonomous games provide fast, deterministic
regression evidence using the same policy host and subjective runtime.

A failed or aborted run remains recorded and is retried after its blocking defect
has a focused reproduction. Never exceed two consecutive completed games on one
controlled character, faction, or matchup. Reproducing a failure through a
deterministic test or fixture does not count as another rotation game and is
preferred to repeatedly replaying the same full encounter.

Use external-AI-versus-external-AI runs for fast deterministic iteration. Use
LLM-controlled runs to evaluate information presentation, tool/query friction,
strategic modulation, and direct-control usability. Use NeuroClient games for
human-facing integration and visual observation, not as the only policy test.

Scenarios must rotate across relevant factors without changing too many at once:

- open combat and ranged spacing;
- closed doors and reveal boundaries;
- corners, chokepoints, and line of sight;
- water, slow terrain, blockers, and hazardous routes;
- multi-target and friendly-fire opportunities;
- concentration and resource competition;
- multiple controlled allies and focus fire;
- remembered contacts and loss of visibility.

## 9. Controlled Content Expansion

The existing engine content should be used broadly before adding more. New
content is allowed only when accumulated evidence shows that the current roster
cannot exercise an important behavior.

As a normal limit, add or materially alter content no more often than once per
approximately ten completed combat rounds across the recent playtest sequence.
This is a ceiling, not a quota.

Permitted controlled expansions include:

- one monster authored from the repository's SRD Markdown references;
- one item or equipment loadout;
- one existing implemented spell or ability added to a scenario;
- one narrowly designed arena variation;
- one environmental object needed to exercise planning.

For each expansion:

1. State which untested behavior requires it.
2. Record the SRD or existing engine source used.
3. Add focused engine/content tests where required.
4. Change one principal variable at a time.
5. Add the scenario to rotation without deleting the previous baseline.
6. Do not change creature statistics merely to hide a policy defect.

Content breadth must remain small enough that regressions can be diagnosed.

## 10. Performance Goal

Every deterministic part of an external controller must be blazingly fast. There
is no artificial thinking delay, polling sleep, snapshot reload, or avoidable
request round trip in the normal decision path. This requirement applies equally
to the traditional controller and to the local runtime, reduction, query,
validation, and command plumbing surrounding an LLM controller.

Measure stages independently so slow engine work cannot be mislabeled as model
latency and policy work cannot hide inside command submission.

For standard small arenas, the initial budgets are:

| Stage | Target |
|---|---:|
| Apply one subjective frame | p95 below 2 ms |
| Incremental fact invalidation and recomputation | p95 below 2 ms |
| Default policy decision | p95 below 2 ms |
| Bounded planner | hard budget of 3 ms by default |
| Encode and validate controller command outside engine execution | p95 below 2 ms |
| Build a normal decision epoch | p95 below 5 ms |
| Total agent-owned path excluding engine action execution and network scheduling | p95 below 5 ms |

Maximums and outliers must also be reported. A good median does not excuse
hundreds-of-milliseconds stalls.

When a stage exceeds its budget:

1. Instrument it into named subphases.
2. Reproduce the slow path with a retained seed or fixture.
3. Identify whether work is repeated, eager, globally scanned, reserialized, or
   invalidated too broadly.
4. Optimize the owning layer without reducing the complete server epoch or
   leaking objective information.
5. Re-run tactical and subjectivity tests as well as timing tests.
6. Record before-and-after distributions in structured run data.

Do not optimize by silently omitting legal actions from the authoritative epoch.
A simple policy may build a derived candidate index or lazily score rows locally,
but the session must still receive complete authorized affordances.

LLM inference has a separate, explicitly reported latency budget because it is
not a millisecond-local deterministic operation. It may be amortized through hot
operation, opponent-turn planning, directives, and deterministic traditional
fallback. Excluding the model call itself, an LLM controller uses the same local
stage budgets as the traditional controller. Model or network latency must never
make the default AI slow, block unrelated actors, or disappear inside a broad
"agent latency" number.

## 11. Agent Experience Requirements

At every decision epoch, an attached agent must already possess all
session-authorized data needed to make a decision:

- current subjective world and recent deltas;
- current active actor and complete action economy;
- complete legal affordances and action semantics;
- known topology, relevant resources, conditions, and concentration;
- current policy goals, plan, recommendations, and warnings;
- correlated recent gameplay and command results.

The LLM must not need a server round trip to discover ordinary turn state or
available actions. Local query tools may reduce, filter, compare, or explain the
already materialized data. They exist to manage token cost and cognitive load,
not to fetch missing truth one field at a time.

The default brief should permit a reasonable immediate action. Local tools must
support deeper investigation of:

- entities and freshness;
- objects and topology;
- routes and hazards;
- action families and targets;
- multi-target allocations;
- candidate score breakdowns;
- concentration and resource consequences;
- policy trace and active plan;
- significant subjective events since the last interaction.

The implemented direct-Codex read contract uses one bounded turn index and one
typed batch query over a persistent local `SubjectiveRuntime`. The old cold
brief/actions/turn/watch/execute CLI and its duplicate snapshot-polling client
are not valid compatibility paths and must not be reintroduced.

Every LLM friction point must distinguish:

- information absent from the subjective state;
- information present but not processed;
- information processed but omitted from the brief;
- information available only through an awkward query;
- correct information that the LLM ignored or misinterpreted;
- policy recommendation that biased the LLM incorrectly.

Do not solve all LLM errors by adding more prompt text. Prefer typed local data,
automatic processors, focused summaries, and queryable detail.

## 12. Evidence And Dashboard

The HTML dashboard is a rendered view of structured evidence. Statistics and
time series must be read from logged JSON or generated artifacts, never entered
manually into chart code.

### 12.1 Run Artifacts

Every completed run must retain or reference a typed artifact containing:

- schema version, run ID, timestamp, seed, commit/worktree identity when known;
- scenario, arena, participants, builds, equipment, spells, and controllers;
- policy profile and policy hash;
- LLM mode, model, prompt-template hash, and directive IDs when applicable;
- winner, rounds, turns, actions, command results, and encounter termination;
- subjective observation and epoch cursor summaries;
- decision traces and agent telemetry references;
- rejected, stale, retried, fallback, resync, and timeout counts;
- per-stage latency distributions and maxima;
- agent tool calls, payload size, estimated tokens, and sequential query count;
- tactical findings and linked regression identifiers;
- whether objective validation found any subjectivity violation.

Unknown historical values remain `null`; they must not be plotted as zero.
Approximate reconstructed values must be explicitly marked.

### 12.2 Dashboard Requirements

The dashboard must:

- load its statistics from the versioned JSON evidence;
- show time series in chronological run order;
- use separate charts or axes for materially different scales such as token
  counts, tool calls, milliseconds, and game rounds;
- avoid empty leading regions caused by dirty sequence values or null history;
- expose filters for character, controlled side, scenario, controller mode, and
  policy version;
- show correctness, tactical, agent-experience, and performance metrics;
- distinguish missing data, failed runs, and zero values;
- link visible findings to the narrative iteration entry and raw run artifact;
- show before-and-after comparisons for claimed improvements;
- display policy and subjectivity regressions prominently rather than averaging
  them away.

### 12.3 Narrative Log

The Markdown iteration log records:

- context and hypothesis;
- observed evidence;
- root-cause classification;
- integrated change;
- focused validation;
- before-and-after measurements;
- remaining risks and next targets.

The log explains the evidence. It is not the source of plotted numbers.

### 12.4 Gauntlet And Tournament Evidence

The gauntlet is the structured validation layer above one-off self-play. It is
not a replacement for debugging individual games; it answers whether a policy or
content change survives a broader matrix.

The gauntlet must support:

- a named schedule made from arena IDs, seeds, side order, controller profiles,
  class/loadout profiles, and monster roster entries;
- small smoke slices for fast iteration and larger retained batches for release
  confidence;
- AI-vs-AI execution without a human client;
- mixed barbarian, sorcerer, skeleton, SRD monster, custom arena, and future
  class setups without overfitting to one matchup;
- optional Elo-style rating summaries for arena sides, policies, monster groups,
  and class/loadout setups;
- raw per-match artifacts plus a compact `latest.json` summary;
- retained failed, timed-out, stale-command, and subjectivity-violation runs;
- stable schema versions so dashboard and watcher code can reject dirty data
  rather than silently plotting nonsense.

The gauntlet result summary must include:

- gauntlet ID, schema version, generated-at timestamp, schedule hash, and policy
  hash;
- match status, arena, seed, side order, participants, controller profiles, and
  final outcome;
- command counts, round/turn counts, elapsed time, timeout/stale/reject/resync
  counts, and performance percentiles;
- final HP/resource/concentration summaries by faction and by actor;
- tactical tags observed during the match, including doors, reveal boundaries,
  water/slow terrain, multi-target actions, concentration, reactions, and
  natural attacks;
- subjectivity validation status and any leak evidence;
- rating deltas and rating time series when rating is enabled;
- raw artifact paths for drill-down.

The gauntlet must be launchable in repeatable modes:

- `smoke`: a short schedule used during normal development;
- `rotation`: the current required barbarian/sorcerer/skeleton validation loop;
- `content`: SRD monster and custom arena breadth checks;
- `release`: larger retained batch used for milestone gates;
- `regression`: targeted replay of previously failing seeds.

### 12.5 Live Gauntlet Watcher

The live watcher is a developer-facing monitor for gauntlet progress and
results. It should be useful while a batch is running, but it does not need to
render live tactical movement.

The watcher should consume a bounded event stream when a server/harness is
running, and fall back to reading the latest JSON summary when opened as a
static file.

The stream should carry gauntlet-level events such as:

```text
GAUNTLET_STARTED
MATCH_STARTED
MATCH_PROGRESS
MATCH_COMPLETED
MATCH_FAILED
RATING_UPDATED
SUMMARY_WRITTEN
GAUNTLET_COMPLETED
```

Each event must be typed and cursor-addressed, using the same practical SSE
machinery as existing server streams where possible. Event payloads should be
summary-oriented: current match, status, elapsed time, key counters, latest
outcome, rating movement, and links to raw artifacts. Full gameplay truth
continues to live in the engine/subjective event streams and retained artifacts;
the watcher stream is observability, not authority.

The watcher UI must show:

- current gauntlet status and active match;
- completed/failed/pending counts;
- latest outcomes and failure reasons;
- running win rates and rating table;
- rating and outcome time series across matches;
- performance summaries and outlier flags;
- subjectivity violation warnings as hard red failures;
- links or paths to raw match artifacts and the compact summary JSON.

The watcher must not:

- read objective engine state as controller input;
- hide failed matches;
- average away leaks, hangs, or command protocol failures;
- require NeuroClient to be open;
- pretend to be a full tactical replay client.

## 13. Testing Requirements

### 13.1 Test Discipline

- Add or update a focused test before changing important behavior.
- Run tests after every implementation change.
- Run individual test files only; never run the full pytest suite.
- Run focused Pyright checks over touched modules.
- Preserve prior behavior unless the change is intentional and documented.
- Unrelated failures are recorded in `KNOWN_ISSUES.md` rather than silently
  repaired during another task.

### 13.2 Protocol And Subjectivity Tests

Required properties include:

- snapshot plus frames materializes the same subjective world as a fresh
  snapshot;
- duplicate frames are idempotent;
- cursor gaps and eviction trigger explicit resynchronization;
- hidden entities, objects, statistics, routes, and logs never leak;
- multi-observer unions retain observer attribution;
- decision epochs contain complete session-authorized legal rows;
- inactive sessions receive no executable epoch;
- stale and rejected commands do not mutate engine state;
- accepted commands correlate to resulting events and follow-up epochs;
- direct LLM commands require the current fenced lease generation.

### 13.3 Policy Framework Tests

- behavior-tree selectors, sequences, decorators, conditions, utility selectors,
  and running state produce deterministic traces;
- actor-scoped memory does not bleed between controlled creatures;
- policy nodes cannot execute commands;
- each epoch yields at most one submitted command;
- hard constraints remain distinct from utility preferences;
- deterministic tie-breaking is stable;
- directives are validated, scoped, and expired;
- plans contain semantic intents rather than future row IDs;
- plan repair occurs after relevant observations;
- planner time and node budgets are enforced;
- traditional fallback is deterministic.

### 13.4 Semantic Tests

- renaming display text does not alter policy classification;
- action semantics survive epoch serialization;
- costs and resource effects match engine behavior;
- concentration replacement is represented;
- multi-target and repeated-target behavior is represented;
- movement distinguishes voluntary and forced movement;
- doors expose interaction, topology, and information effects;
- routine preconditions use explicit unknown handling;
- logical annotations appear in decision traces.

### 13.5 Tactical Invariants

- do not pursue an enemy that is not known subjectively;
- do not use objective hidden paths;
- do not Dash to an interaction already reachable with ordinary movement when
  preserving the action has plausible value;
- do not replace valuable concentration without comparative justification;
- do not include protected allies in forbidden area effects;
- do not ignore a clearly dominant ranged spell merely to approach melee;
- do not repeat a failed tactic indefinitely without new evidence;
- use or deliberately preserve remaining action economy;
- replan after visibility, topology, condition, concentration, resource, death,
  or active-actor changes.

Tests should prefer declared tactical properties and score relationships over a
brittle exact action where several choices are legitimately close. Exact-choice
tests are appropriate when the fixture makes one candidate decisively dominant.

### 13.6 LLM And Failure Tests

- observer mode cannot command;
- modulation changes only allowlisted policy parameters;
- malformed or adversarial model output cannot modify code or authority;
- prompt content from names, logs, and descriptions cannot invoke administrative
  tools;
- lease expiry during inference rejects the late command;
- superseded fencing tokens cannot write;
- timeouts, process failures, invalid outputs, and stale epochs invoke fallback;
- shadow mode records proposals without granting command authority;
- one LLM can coordinate several actors without out-of-turn commands.

### 13.7 Self-Play Validation

Self-play tests must use retained seeds and the real subjective runtime and epoch
command path. Decision input must never use objective state.

Each architecture milestone requires:

- a focused deterministic fixture for the changed behavior;
- replay of the original observed failure;
- one different-character regression game;
- one different-scenario regression game;
- completion of the next required rotation batch before broad tactical claims.

## 14. Implementation Order

The architecture migration proceeds in controlled phases.

### Phase 0: Baseline And Freeze

- Record current focused-test status and known failures.
- Retain representative seeds and raw artifacts for existing useful behavior.
- Stop adding action-specific priority branches except for correctness blockers.
- Inventory duplicate state models, name tables, and execution paths.

### Phase 1: Protocol And State Ownership

- Extract neutral observation, control, semantic, command, and telemetry models.
- Remove the observation-to-subjective dependency inversion.
- Make the materialized subjective world fully typed.
- Establish absolute monotonic cursor and eviction behavior.
- Add temporary read-only adapters for current consumers.

### Phase 2: Knowledge And Logical Annotations

- Implement typed facts and incremental invalidation.
- Add action and routine semantic contracts.
- Cover action economy, concentration, targeting, topology, information effects,
  and multi-target allocation.
- Carry semantics through decision epochs and telemetry.
- Remove core policy dependence on display-name parsing.

### Phase 3: Policy Framework

- Refactor behavior-tree primitives to consume shared `PolicyContext`.
- Move mutable running state into actor-scoped memory.
- Make every leaf return proposals rather than execute.
- Add shared candidate generation, hard constraints, utility components, and
  deterministic tie-breaking.
- Add explicit policy profiles and complete tree traces.

### Phase 4: Default Policy Migration

- Define tactical goals and the hierarchical default tree.
- Port existing useful behavior one subtree at a time.
- Implement concentration-aware casting, multi-target allocation, spatial
  interaction, exploration, coordination, and economy preservation through
  shared semantics.
- Compare every migrated subtree against retained baseline seeds.
- Remove obsolete selector branches only after parity or documented improvement.

### Phase 5: Bounded Planning

- Implement semantic intents and current-epoch resolution.
- Add bounded planning for doors, reveal boundaries, routes, spacing, and
  objective movement.
- Add plan continuation, invalidation, repair, and unknown-aware branching.
- Enforce strict time and expansion budgets.
- Represent temporary action-surface changes as generic typed capability
  transformations; project them only for planning, then bind to fresh epoch
  rows after authoritative acceptance.

### Phase 6: LLM Unification

- Adapt Codex/LLM tools to the same local runtime, facts, candidates, and traces.
- Keep the bounded `/v1/turn` index independent of legal-row count, and recover
  every omitted detail through revision-fenced local `/v1/query` pages.
- Implement goal directives, policy modulation, plan proposals, escalation, and
  direct current-row control.
- Add hot waiting, independent lease renewal, fenced authority, and fallback.
- Begin with observer and shadow modes before granting broader write authority.

### Phase 7: Observability And Dashboard

- Complete correlated agent-event emission and bounded SSE history.
- Expose policy observation to NeuroClient without altering human gameplay APIs.
- Version raw run artifacts and dashboard input data.
- Make every chart derive from structured evidence.
- Add phase-level performance distributions and policy trace views.
- Add a gauntlet event stream and watcher app that can display batch progress,
  outcomes, rating movement, failures, and summary links without rendering full
  tactical animation.

### Phase 8: Rotating Iteration

- Resume continuous mixed-character and mixed-scenario cycles.
- Alternate agent-experience, enemy-policy, correctness, and performance work.
- Add content sparingly under the ten-round evidence rule.
- Evaluate both direct LLM play and LLM modulation of the default policy.
- Preserve raw evidence for every claimed improvement.
- Run smoke gauntlet slices after policy/content changes and larger gauntlet
  batches before declaring release-readiness.

### Phase 9: Gauntlet Breadth And Ratings

- Define named gauntlet schedules for smoke, rotation, content, release, and
  regression replay.
- Expand the schedule across the SRD monster roster, custom arenas, class/loadout
  profiles, side order, and deterministic seeds.
- Persist compact summaries and raw match artifacts for every run.
- Compute rating tables and time series only from completed typed match records,
  while keeping failures visible outside the rating aggregate.
- Validate that watcher output, `latest.json`, raw artifacts, and narrative log
  agree on match counts and outcomes.

## 15. Change Discipline

- Prefer shared semantic or policy improvements over action-specific exceptions.
- Do not add a new branch until the existing hierarchy, facts, and utility model
  have been inspected as the likely owning layer.
- One iteration should have one primary hypothesis.
- Do not mix broad content changes, policy rewrites, protocol changes, and
  performance optimization in the same evidence comparison.
- Preserve working human/NeuroClient APIs during the AI migration.
- Preserve one videogame ruleset; AI work must not introduce rules profiles or
  alternate D&D behavior.
- Do not silently reduce complete action affordances for speed.
- Do not use comments as logical annotations. Use typed models with Pydantic
  field descriptions and Google-style docstrings where documentation is needed.
- Do not preserve obsolete AI paths indefinitely. Temporary adapters must have a
  named removal phase and no new features may depend on them.

## 16. Satisfaction Criteria

The architecture implementation milestone is satisfied only when all of the
following are true.

### 16.1 Unified Runtime

- Traditional AI and LLM agents consume the same typed subjective world and
  decision epochs.
- No production AI policy reads objective state, live entities, or a separate
  available-actions endpoint.
- Snapshot bootstrap, continuous events, command results, and resync operate
  without per-action snapshot polling.
- Complete subjectivity and replay contract tests pass.

### 16.2 Unified Policy

- The default AI is implemented as a hierarchical behavior tree with shared
  utility scoring and bounded planning where appropriate.
- The flat action-specific selector is no longer the production policy.
- Behavior-tree, FSM, utility, planner, and LLM adapters share one typed policy
  context and proposal contract.
- Policy definitions are immutable; actor memory is isolated and replayable.
- Every selected command has an inspectable decision trace.

### 16.3 Logical Model

- Standard action families carry typed prerequisites, effects, costs, targeting,
  topology, concentration, information, and uncertainty annotations.
- High-level routines carry applicability, progress, and invalidation semantics.
- Policy behavior no longer depends on broad display-name parsing.
- Logical annotations are serialized in epochs or traces and covered by focused
  tests.

### 16.4 LLM Control

- The LLM can observe, direct goals, modulate allowlisted policy behavior,
  propose plans, answer escalations, and directly execute current legal actions.
- All modes use the same subjective state and policy host.
- Direct writes are epoch-bound and lease-fenced.
- Invalid or slow LLM behavior falls back deterministically without hanging the
  encounter.

### 16.5 Tactical And Performance Validation

- Barbarian, Sorcerer, and skeleton sides complete the required rotation without
  command deadlocks or subjectivity violations.
- Door opening, reveal boundaries, water/slow terrain, ranged casting,
  concentration, multi-target actions, and multi-entity coordination have
  retained regression scenarios.
- Standard external-AI stages meet the declared millisecond budgets, with no
  unexplained hundred-millisecond outliers.
- Accepted tactical improvements survive at least one different character and
  one different scenario.

### 16.6 Evidence

- Raw run artifacts, structured statistics, and narrative findings agree.
- The HTML dashboard reads its metrics from structured JSON and displays valid
  time series with scale-appropriate charts.
- Missing historical data is represented honestly.
- Every major architecture and policy change has before-and-after evidence.

### 16.7 Gauntlet And Watcher

- A named smoke gauntlet can run AI-vs-AI without NeuroClient and write a typed
  compact summary plus raw match artifacts.
- A larger content/release gauntlet can cover multiple arenas, seeds, monster
  groups, class/loadout profiles, and side orders.
- The watcher app can load the latest summary from JSON and, when available,
  follow a bounded gauntlet event stream for progress updates.
- The watcher displays progress, outcomes, failures, rating movement, and
  subjectivity warnings without needing live tactical animation.
- Gauntlet events are observability data only; they do not replace engine events,
  subjective streams, command results, or raw artifacts.
- Failed, timed-out, leaked, stale-command, and aborted matches remain visible in
  gauntlet summaries and are never silently excluded from release decisions.

## 17. Completion Gate For The First Stable Release

After the architecture milestone is satisfied, complete at least three
consecutive six-game rotation batches under the unified production policy and
one retained release gauntlet batch.

Across those batches:

- every encounter must terminate normally;
- no controller may receive hidden information;
- no accepted command may bypass the current epoch;
- no run may hang because an LLM or external controller disappeared;
- rejected and stale commands must remain bounded and explained;
- all three controlled character/faction categories must appear in every batch;
- direct LLM control and policy modulation must both be exercised;
- performance budgets must be reported from raw traces;
- no tactical fix may regress an earlier retained invariant without an explicit
  design decision.

The retained release gauntlet additionally requires:

- no subjectivity violations;
- no unexplained hangs;
- no hidden failed matches in the watcher or summary;
- rating/outcome tables derived only from typed match records;
- at least one SRD monster roster scenario, one custom arena, one barbarian
  profile, one sorcerer profile, one skeleton-side profile, and both side orders;
- a watcher-visible summary that matches the written JSON artifact.

The broader play-improve-document-repeat loop remains the ongoing development
method after this release gate. Passing the gate means the unified architecture
is stable enough to continue iteration without returning to parallel controller
products or ordered tactical exception patches.

## 18. Non-Goals

This goal does not require:

- a second ruleset or runtime rules profile;
- client-side reconstruction of action legality;
- a complete probabilistic belief-state solver;
- an objective engine clone for planning;
- arbitrary LLM-generated controller code in production;
- an LLM model call for every trivial action;
- replacing NeuroClient's working human state and action surfaces;
- adding a large monster or item catalog before the policy architecture is
  diagnosable;
- optimizing win rate by granting the AI information unavailable to a player;
- declaring success from a dashboard summary without retained raw evidence.

## 19. Guiding Standard

Every improvement must answer four questions:

1. **What did the controller know?**
2. **Why did the policy consider and choose this behavior?**
3. **Which authoritative event and command contract made it happen?**
4. **What reproducible evidence shows the change is faster, clearer, or more
   tactically correct without leaking information?**

If any answer is unavailable, the system is not yet sufficiently instrumented
to justify the next tactical exception. Improve the architecture or evidence
surface first.
