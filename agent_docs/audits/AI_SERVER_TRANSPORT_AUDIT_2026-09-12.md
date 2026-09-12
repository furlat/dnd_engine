# AI, server and transport audit — 2026-09-12

This is a read-only audit after the user's explicit stop on implementation,
tests and measurements. The only file written during this audit is this note.
It records unnecessary work and unresolved ownership questions; it does not
authorize a replacement architecture. Existing tests are evidence of an asserted
contract, not justification for that contract.

## Scope and coverage

Snapshot: `14b27f7`, with the already-pending performance changes visible in the
shared workspace. Owned roots are `ai/`, `dnd/ai/`, `server/`, `services/`,
`custom_ai/`, and `sdk/`. There are **217 Python/TypeScript source files and
115,755 lines**, including SDK tests and its generated TypeScript file.
Generated contracts were traced to their generators and consumers rather than
treated as thousands of independently authored decisions.

Every owned Python file was parsed statically; every owned Python/TypeScript
file was scanned for hashes, validation, copying, serialization, reflection,
caches and retained snapshots. Imports, module definitions and module purpose
were included in the inventory below. The execution paths and findings below
received focused source reads. This is not a claim of manually proving every
branch in all 115,755 lines. The inventory distinguishes static coverage from
focused review and generated-owner review. No game, server, test, benchmark or
generator was executed during this audit.

`git diff 16a6bfe -- ai dnd/ai server services custom_ai sdk` establishes an
important provenance fact: these trees are unchanged from the July
reconstruction except the current removal of the built-in artifact-digest field
in three server files, the SDK fixture and two generated SDK files. The remaining
machinery described here survived the rollback; it was not introduced by the
new Pygame playback. That explains provenance, not whether it should remain.

| Root | Source files | Lines | Role in the current game |
| --- | ---: | ---: | --- |
| `dnd/ai` | 27 | 9,848 | Active native controller, policy and subjective decision projection |
| `ai` | 67 | 32,495 | Separate remote subjective client, advanced policy and Codex tool stack |
| `server` | 88 | 53,215 | Retained HTTP/gateway/worker, replication, authoring and persistence stack |
| `services` | 7 | 1,028 | External AI policy service |
| `custom_ai` | 4 | 409 | Example tactical policy used by that service |
| `sdk` | 24 | 18,760 | TypeScript clients, reducers, validators, generated types and tests |

## Actual execution boundaries

The current path is `game/session.py:12` →
`dnd/ai/runtime/controller.py:114` → `NativeAIAssignment.execute_next_action`
(`assignment.py:182`) → state projection and native action discovery → basic
policy → `execution.py:57` → `dnd.action_dispatch.dispatch_available_action`.
The native policy uses the existing engine actions. It does not import the
top-level `ai/`, server, SDK or external policy service. Those systems therefore
cannot explain native-only measurements merely because their code is large.

Within this active path, `state_projection.py:68` builds a subjective world and
an exact execution epoch. `movement_revalidation.py:40` projects the world again
after each committed voluntary step. This produces the data used to stop a move
when a new hostile, hazard or actor-state change becomes known. The public
decision and private execution binding are different data, not two engines.
Their duplication should be judged at the actual conversion points below.

The old remote path is different: `ai/subjective/runtime.py:337` receives
observation snapshots/frames, `ai/subjective/store.py:61` retains them, hooks and
knowledge reducers build policy-facing facts, and `ai/policy/host.py:237` manages
proposals, decisions and results. `ai/codex_tools/hot_runtime.py:828` wraps this
again with command, inspection, representation, profile and takeover state.
The reference HTTP policy service composes native policy contracts through
`services/ai_policy_server/composition.py:41`; its tactical option comes from
`custom_ai/tactical/policy.py`. This is not the advanced `ai/policy` interpreter.

The retained server has three separate event-derived streams: objective source
slots (`event_stream.py:222`), agent observation state
(`agent_runtime/observation_journal.py:185`), and player replication
(`player_replication/runtime.py:524`). There are additional terminal summaries
and replay collectors. These are real retained owners with separate consumers;
calling them all one timeline would hide the amount of work. Conversely, their
existence does not prove that deleting one preserves its consumers.

## Prioritized findings

### A1. Active native projection allocates copies that are immediately discarded

**Confirmed unnecessary work; inherited; no isolated timing claim.**

`dnd/ai/runtime/subjective_projection.py:163` iterates every previously known
entity and calls `facts.setdefault(entity_uuid, remember_entity_fact(fact))`.
The remembering function at line 254 makes a model copy. The same pattern occurs
for objects at lines 418–428 and tiles at lines 496–505. Python evaluates the
default argument even when the dictionary already contains the freshly
projected value. Thus visible/rebuilt entities, objects and tiles cause a copy
whose result is discarded.

Retaining last-observed values for genuinely absent entries is required by the
current subjective design. Allocating an unused alternative for an existing
entry is not. This distinction is established directly by evaluation order and
callers, without assuming that all state copying is wasteful. It needs no new
state owner or cache to explain it. No change was made under the hard stop.

The earlier saved native profile reports `project_known_tiles` at **1.586s
cumulative**, `project_subjective_world` at **2.209s**, and 44 world projections.
These totals include geometry, visibility queries and DTO construction; they
are not the savings attributable to the discarded copies.

### A2. Native movement revalidation rebuilds the entire subjective world

**Active and measured at the aggregate owner; proportionality requires review.**

`movement_revalidation.py:50` calls its supplied `project_world` after each
committed step. `state_projection.py:91` reconstructs session/encounter rows and
the entity, object and tile maps. `subjective_projection.py:470` projects every
visible/seen tile, and line 541 asks for the subjective directional block map.
The saved profile attributes 1.298s to the guard's projection callback over 22
calls, inside the native movement/AI workload.

The actual purpose is checking newly learned hostile/hazard information and
actor state (`movement_revalidation.py:67` onward). Full-world reconstruction is
an implementation choice carrying more work than the names of those checks
suggest. The native sensory system already supplies perception state; this
layer projects it again into policy DTOs. That is a concrete review target, not
authority to delete the interruption rule, skip committed steps or introduce an
alternate perception policy. This audit does not propose an incremental-state
framework as the automatic answer.

### A3. Active AI converts engine DTOs through JSON-shaped data into mirror DTOs

**Confirmed repeated adaptation; inherited; necessity is mixed.**

`decision_epoch.py:729` and line 852 dump `row.outcome_profile` in JSON mode and
validate another `ActionOutcomeProfile`. Lines 1053–1061 do the same per ordinary
and safe-path opportunity-attack exposure. The engine and AI really own distinct
models: `dnd/core/base_actions.py:209,2135` versus
`dnd/ai/contracts/control.py:103,190`. The engine target contains UUIDs and lists;
the public policy target uses string identities and immutable sequences.

This is not serialization across a process in the native game. It is an
in-process normalization/detachment adapter with duplicate schemas. Some
conversion is necessary under the current types; a dump-and-validate roundtrip
is not proved necessary simply because both types already exist. Any later
choice must first identify the actual primitive differences and their owner.
Do not replace this with generic reflection or unchecked construction as a
performance shortcut.

The surrounding code already contains its own compensating machinery:
4096-entry capability and descriptor caches (`decision_epoch.py:107`), target
identity reuse at line 1036, compact `CanonicalActionRow` records and lazily
materialized `ActionBucketRows` (`control.py:588,596`), plus nested collection
freezing (`control.py:30`). This is a substantial native projection substrate.
It deserves assessment as a connected design rather than another cache on top.

### A4. The old advanced policy still hashes executable Python source on import

**Confirmed matching pattern to the rejected source-attestation mechanism;
inactive in current native play; unmeasured here.**

`ai/policy/generations/registry.py:60` executes
`_build_active_implementation()` at import. Line 42 calls
`policy_source_snapshot()`: `ai/policy/source.py:41` reads 22 explicitly listed
source files, concatenates their contents and hashes them. Then
`definitions.py:79` resolves and reads 15 implementation paths, many overlapping,
and hashes the implementation bytes and the combined executable identity.

The callable policy is already selected by explicit imports and
`ACTIVE_GENERATION_ID`. The generated source identity is carried for inspection
and telemetry by `PolicyImplementation`; `hot_runtime.py:853` chooses that
implementation for its policy host. Source introspection and attestation have
become a prerequisite of importing that tool stack. That requirement is not
established by the user's current game objective. It is the strongest surviving
analogue in this scope to the source hashing just removed from built-in content.
No replacement hashing/cache scheme is proposed.

This mechanism arrived in `3fdc402` (`update ai/updated server`) and is unchanged
from July. It must not be charged to current `NativeAIController` timings.

### A5. The retained server repeatedly authenticates generated schemas at startup

**Confirmed build-output verification in a runtime path; inactive/stale here.**

Both `server/event_contract.py:20` and `server/timeline_contracts.py:32` read the
same generated event manifest, re-encode it canonically and recompute its hash
at module import. Their runtime needs are the concrete event discriminators and
field descriptors. Verifying the checked-in generated file against its own
embedded checksum is a separate requirement that survived the rollback.

The server also materializes JSON schemas and hashes them during import for
player replication (`player_replication_contract.py:1994`), objective replay
(`objective_replay.py:186`), player replay (`player_replay.py:340`) and timeline
contracts (`timeline_contracts.py:463`). These values are then protocol identity
fields checked by the SDK. That establishes their consumers, but does not
establish that regenerating them during every server startup is necessary.
These checks are distinct from actual parsing of incoming bytes and distinct
from secret-token hashing.

### A6. Server event capture has serial layers of copying and revalidation

**Confirmed repeated work with partially legitimate boundary purposes.**

`objective_timeline.py:120` deep-copies an engine event, serializes it, validates
the result as `WireEvent`, and canonicalizes it to bytes. Constructing the
`ObjectiveEventSourceSlot` validates those bytes again at line 74. Reading its
`wire_event()` validates and materializes them yet again at line 83.
`event_stream.py:476,620` supplies these slots to its journal.

Detaching a mutable engine graph at a recording boundary has a concrete purpose.
Verifying newly produced immutable bytes twice, and treating every read of
retained bytes as a fresh untrusted decode, adds separate obligations. The
current code does both. This is a connected owner to simplify if that server is
ever selected again; it is not a reason to remove the required record-once
boundary or import this machinery into current Pygame replay.

The player journal repeats a related pattern: each already-typed projected
frame is dumped to JSON then revalidated (`journal.py:375`); each log slot does
the same at line 435; the bootstrap world does it at line 587. It then performs
cursor/identity checks separately. Deep container ownership and protocol
continuity are real questions; the roundtrip is an implementation decision,
not automatically the only way to answer them.

### A7. Server spatial memory stores JSON strings and rehydrates them for projection

**Confirmed serialization used as internal storage, not transport.**

`player_replication/world_projection.py:59` stores remembered tile values as
JSON strings. `materialize()` validates each string and then copies the model
to change its visible flag at lines 73–75. Objects use the same arrangement at
lines 79–95. The memory owner also copies its dictionaries for working state at
line 108. This preserves event-time memory independently of live objects, but
ties that ownership to repeated encoding and decoding. It is unnecessary to
describe it as network work: both ends are in the same projector.

### A8. The server retains several independently guarded state/journal systems

**Confirmed architecture breadth; not all state is semantically duplicate.**

`event_stream.py:248` attaches an objective batch/log journal.
`agent_runtime/observation_journal.py:185` attaches completion, batch and log
callbacks for session-specific AI observations. `player_replication/runtime.py`
attaches a separate player batch bridge, maintains per-perspective worlds,
pending logs and source barriers, and feeds another locked journal.
`game_summary_store.py:129` attaches terminal-summary capture;
`player_replay_capture.py` retains a further replay archive.

The player bridge also reconstructs the event suffix from `EventQueue` and
compares all event UUIDs with the callback's batch (`runtime.py:783`), failing
the generation on mismatch. That is a direct distrust/reverification of data
from the engine's own callback owner. No actual mismatch was reproduced in this
audit. The code documents a defensive invariant, not a user requirement.

The server's actor/AI and human/animation perspectives have different consumers,
and terminal archival is different from a live view. That does not justify every
intermediate retained world, barrier, journal and fail-closed state. The stack
needs an explicit map of each consumer before reuse. In particular, the current
game already has native event recording and a public player projection; importing
these server owners to obtain a queue would recreate a parallel system.

### A9. The SDK independently validates decoded frames, stream continuity and reduced worlds

**Confirmed layered validation; some layers answer different questions.**

`validation.ts:210` walks generated descriptors and exact field sets;
`subjectiveSse.ts:163` decodes each delivery; the stream follower checks cursor
continuity. `subjectiveJournal.ts:250` checks frame identity and continuity
again, serializes frames with `stableJson` for duplicate detection, reduces the
world, and validates that whole reduced world at line 278. The same frame later
drives presentation settlement through `commitPresentationFrame` at line 163.

The two authoritative/presentation states preserve the user's explicit
independent-reduction/playback design; their existence is not slop. Structural
wire decoding, retransmission detection and revalidating a locally reduced
world are different costs. The last two layers must not be defended merely by
pointing at the first. Duplicate frame payload strings are retained for 4096
slots and presentation IDs for the whole partition (lines 69–93,279).
This TypeScript stack is not executed by the current Python game.

### A10. Advanced-agent representation and policy layers remain much broader than current native play

**Confirmed retained systems; no claim that all are redundant.**

`ai/codex_tools/hot_runtime.py` is 2783 lines and wraps `SubjectiveRuntime`,
`PolicyHost`, representation registry/projector, predicate ledger, inspection,
transcript, lease and command indexes. The policy has additional generation,
planning, commitment, routine, outcome and scoring layers. The 4701-line
`ai/policy/candidates.py` and 3289-line `routines.py` implement policy valuation,
not engine action execution. `ai/subjective/hooks.py:79` adds ordered post-
processors and another derived `AgentState` on top of `SubjectiveWorldState`.

Some derived memory is necessary for a stateful policy. The quantity of policy,
representation and lifecycle machinery should not be mistaken for infrastructure
the current game needs. It is selectable only through its remote/tool consumers,
and it brings the source hashing in A4 with it. No clean replacement is invented
in this audit.

## Checks and state that have a concrete external purpose

These are inventoried rather than automatically recommended for removal:

- `services/ai_policy_server/external_ai_registry.py:260` hashes a complete
  decision request before consulting its bounded response cache. Reusing a
  decision ID with different input is an actual remote replay/conflict question.
  The entire request is dumped at line 586 even for a new request. Cost is
  unmeasured; the native controller does not make this request.
- `server/runtime_authority.py:405` hashes bearer tokens;
  `game_directory/canonical.py:43` uses HMAC for capability secrets. Those
  concern secret handling, not source-code authenticity. They are outside the
  rejected boot scan and cannot be removed by matching the word `hash`.
- `game_artifact_store.py:153` checks bytes against their content-addressed file
  name; `worker_terminal_spool.py:424,470` writes/verifies artifact digests;
  `terminal_evidence.py:132` reopens and validates persisted terminal artifacts.
  Their extra reads/validations are real and may be excessive at particular
  boundaries, but persistent artifact identity is not a gameplay hot path.
- `game_directory/database.py:53` opens SQLite with `check_same_thread=False`
  and owns an `RLock`; gateway, worker and subscription queues coordinate actual
  concurrent clients/processes. This is different from adding locks to the
  current single-thread native encounter.
- `dnd/ai/runtime/decision_epoch.py:236` acquires a process-wide automatic-GC
  suspension lease with a `finally` release. `runtime_gc.py` owns nested lease
  counters and a lock. This is a policy over the embedding process introduced
  for allocation behavior, not game mechanics. Its benefit was not measured
  here; do not add another GC controller or remove it on assumption alone.
- Native semantic hashes (`dnd/ai/contracts/semantics.py:917`) identify shared
  immutable semantic values; caches reduce repeated construction. The external
  client has another `SemanticContractPool` which checks received contents even
  on cache hits (`ai/subjective/semantic_pool.py:89`). This is not Python-source
  hashing, but shows the costs of choosing content-addressed internal DTOs.

## Stale server dependencies and generated contracts

Static `ImportFrom` resolution found **15 distinct missing local module
targets**, all in the retained server tree. The complete importer list is below.
The previously attempted SDK generator failed first at
`server/world_contracts.py:17 -> dnd.core.senses`; this audit did not retry it.
Other missing targets include whole retired character and item materialization
owners. Reinstating those imports would reconnect a displaced architecture,
not simply repair an incidental filename.

The SDK generated manifest contains 540 model descriptors, 140 enum descriptors
and 48 event identities. The server event manifest contains 89 model descriptors
and the same 48 event identities. Their owners are
`devtools/generate_typescript_sdk.py` and `devtools/generate_event_contract.py`.
Generated output is a snapshot of the old backend graph, not evidence that the
old server can currently run or that every field still belongs in the new game.

The pending built-in source-hash removal was followed through
`LoadedContentSystem`, bootstrap, content manifest and worker readiness. There
is no replacement artifact identity field. Existing `content_set_digest` now
uses declarations/pack versions and existing pack data, not arbitrary engine
source bytes. SDK JSON, its interface and embedded descriptors had the obsolete
field removed structurally. Only its existing aggregate SDK contract hash was
updated with the generator's canonicalization rule; other graph hashes stayed
unchanged. Full regeneration remains blocked by the old server imports. This
limited update must not be described as full generated-contract parity.

## Cross-review of content identity and zero-pack startup

The root audit identified two connected points outside these owned trees.
`dnd/content_system/pack_loader.py:_content_set_digest` still includes each
declaration's full descriptor, including `ContentPresentation` fields. The
resulting whole-set identity is consumed by runtime installation, behavior and
creature bindings, and server character/replay operations. Therefore a cosmetic
change to descriptor metadata can invalidate an identity used for mechanical
content. This is a real coupling to question. It does **not** mean that every
PNG or `game/data` recipe change affects that digest after the Python-source
hash was removed, nor that observable appearance values are inherently illegal
in retained game state. The review question is the granularity and purpose of
whole-set invalidation, not a ban on appearance facts.

`load_content_system` also snapshots global engine state and invalidates import
caches when the installed external-pack list is empty. The protected external
import operation is absent in that branch. That is source-backed redundant
infrastructure, but the prior bootstrap execution measurement was roughly
0.018s; it must not be reported as the remaining multi-second import cost.
Neither observation authorizes a replacement registry, hashing scheme or
dependency framework during this audit.

## Non-Python/TypeScript executable coverage

`ai/AI_AGENT_OBSERVER.html` contains 1156 lines with inline JavaScript at
lines 487–1154. Its script was read as part of this audit. It is a standalone
telemetry viewer using `fetch` and `EventSource` against the old `/ai/sessions`
routes; it is not loaded by the Pygame game. It does not introduce executable-
source hashing, dynamic code evaluation, an engine or an animation queue.

It does contain concrete avoidable debug-UI work: `addPayload` at line 583 scans
for duplicate cursors, sorts the entire retained event array and rerenders the
viewer for each added row. Both history loading (line 615) and local artifact
loading (line 645) call it once per row, so bulk loads repeatedly redo sorting,
filtering, counts and DOM construction. `renderEvents` displays only the last
400 filtered rows (line 897), while the retained array itself has no bound.
These are source findings, not measured claims or reasons to touch native
gameplay. File-history validation at line 695 and normalization of bare event
rows at line 735 belong to this inspection view; their synthetic display cursors
are not authoritative engine lineage metadata.

`sdk/typescript/package.json` has only three scripts: TypeScript build,
build-then-Node-tests, and TypeScript no-emit checking. There is no install hook,
startup audit or code-generation side effect. `tsconfig.json` controls strict
TypeScript compilation and output maps; none of its checks execute in Python.
No package script or browser page was executed.

## Anti-OOP and anti-slop judgment

The live native controller is already a layered pipeline, but its policy does
not own another action engine: it resolves back to discovered native actions.
The meaningful boundary is between mutable native facts, retained subjective
knowledge and private command authority. It is not strengthened automatically
by another mirrored model, JSON roundtrip, ledger, queue or content address.

The inherited server/advanced-agent stack contains concrete source attestation,
revalidation and parallel retained-state machinery. Rollback retained these
files while removing some of their engine dependencies. Neither their old tests
nor a claim of generic robustness establishes that they belong in current game
work. The pending hash removal improves this by deleting a whole mechanism
instead of hiding its cost in a cache. The same standard should govern later
decisions about A1–A10.

The audit does **not** conclude that every invariant or copy is unnecessary.
An actual wire boundary needs decoding; a retained subjective state must not
silently consult live hidden data; command bindings must still resolve to the
engine. These are the user's and current consumers' contracts. Their existence
does not justify rechecking the same ownership at every intermediate stage.
No implementation is proposed or authorized by this note while the hard stop
remains in force.

## Measurement limits and provenance

Only prior parent-owned evidence was consulted:
`.runtime/performance-recovery/native-profile-before.txt` and its existing
profile, plus the earlier native-session timing report. No fresh profile was
created. The prior native run imported content/session without Pygame; 8 human
turns across 4 rounds included 22 AI actions. Profiled cumulative calls overlap
and contain instrumentation overhead. The measured native projection owners in
A1/A2 establish where work occurred, not the savings of any unimplemented change.
There are no new performance numbers for remote AI, server, SDK or persistence.

Introduction references inspected: native decision epoch and movement
revalidation in `b2b3930` (`restructured ai as owned by the paccakge and external
ai server`); player journal in `42b6490` (`tests fixed - multi server untested -
refactoring ai again`); advanced policy source identity in `3fdc402`
(`update ai/updated server`). All were present at `16a6bfe`.

## Source inventory

Coverage codes: **S** = full-file static text/AST/import scan;
**D** = that scan plus focused manual owner/caller reads;
**G** = generated data/type output traced to generator and consumers.
Keyword counts are screening signals, not defect counts. Columns H/V/C/J/R/K
mean hash, validation/assertion, copying, serialization, reflection and
cache/snapshot tokens. Strings/docstrings can contribute; no conclusion above
rests on token count alone. All Python files parsed successfully. SDK test
files are inventoried but were not executed and do not justify production code.


### `ai/`

| File | Lines | Coverage | H/V/C/J/R/K |
| --- | ---: | :---: | --- |
| `ai/__init__.py` | 1 | S | 0/0/0/0/0/0 |
| `ai/codex_tools/__init__.py` | 1 | S | 0/0/0/0/0/0 |
| `ai/codex_tools/__main__.py` | 7 | S | 0/0/0/0/0/0 |
| `ai/codex_tools/artifacts.py` | 506 | S | 0/4/0/1/5/23 |
| `ai/codex_tools/client.py` | 150 | S | 0/2/0/0/2/0 |
| `ai/codex_tools/commands.py` | 355 | S | 0/0/0/5/7/0 |
| `ai/codex_tools/contracts.py` | 59 | S | 0/0/0/0/0/0 |
| `ai/codex_tools/direct_game.py` | 345 | D | 2/8/0/1/0/0 |
| `ai/codex_tools/heavy_cli.py` | 7 | S | 0/0/0/0/0/0 |
| `ai/codex_tools/hot_runtime.py` | 2,783 | D | 0/4/1/13/89/61 |
| `ai/codex_tools/local_client.py` | 307 | D | 0/3/0/1/16/0 |
| `ai/codex_tools/representation/__init__.py` | 27 | S | 0/0/0/0/1/0 |
| `ai/codex_tools/representation/components.py` | 1,121 | S | 0/1/0/0/9/0 |
| `ai/codex_tools/representation/geometry.py` | 352 | S | 4/3/0/5/0/0 |
| `ai/codex_tools/representation/inspection.py` | 1,117 | S | 4/4/1/5/74/0 |
| `ai/codex_tools/representation/models.py` | 612 | S | 4/20/0/6/11/0 |
| `ai/codex_tools/representation/oracle.py` | 78 | S | 0/0/0/0/1/0 |
| `ai/codex_tools/representation/predicates.py` | 995 | S | 0/6/1/0/12/9 |
| `ai/codex_tools/representation/profiles.py` | 796 | S | 0/1/0/0/6/0 |
| `ai/codex_tools/representation/projector.py` | 1,646 | S | 0/3/0/2/27/13 |
| `ai/codex_tools/representation/registry.py` | 200 | S | 0/2/0/0/0/0 |
| `ai/codex_tools/session_transcript.py` | 400 | S | 4/3/0/9/2/11 |
| `ai/codex_tools/wire_cli.py` | 258 | S | 0/0/0/3/3/0 |
| `ai/knowledge/__init__.py` | 31 | S | 0/0/0/0/0/0 |
| `ai/knowledge/deriver.py` | 849 | S | 0/1/0/0/15/0 |
| `ai/knowledge/models.py` | 292 | S | 0/0/0/0/0/0 |
| `ai/knowledge/replay.py` | 35 | D | 0/0/0/0/0/0 |
| `ai/knowledge/topology.py` | 236 | S | 0/0/0/0/0/12 |
| `ai/ordered_delivery.py` | 132 | S | 0/0/0/0/0/0 |
| `ai/planning/__init__.py` | 29 | S | 0/0/0/0/0/0 |
| `ai/planning/composition.py` | 330 | S | 0/0/0/4/5/0 |
| `ai/planning/contracts.py` | 259 | S | 0/0/0/0/1/0 |
| `ai/planning/registry.py` | 87 | S | 0/0/0/0/3/0 |
| `ai/policy/__init__.py` | 153 | S | 0/0/0/0/0/0 |
| `ai/policy/candidates.py` | 4,701 | S | 0/12/2/0/9/57 |
| `ai/policy/commands.py` | 441 | S | 0/2/1/0/2/0 |
| `ai/policy/contracts.py` | 788 | S | 0/2/0/0/6/1 |
| `ai/policy/default.py` | 181 | S | 0/1/0/0/0/0 |
| `ai/policy/definitions.py` | 113 | D | 6/0/0/0/0/0 |
| `ai/policy/economy.py` | 429 | S | 0/0/1/0/1/3 |
| `ai/policy/generations/__init__.py` | 13 | S | 0/0/0/0/0/0 |
| `ai/policy/generations/current_annotations.py` | 82 | S | 0/0/0/0/0/0 |
| `ai/policy/generations/current_candidate.py` | 1,169 | S | 0/0/6/0/5/0 |
| `ai/policy/generations/current_commitments.py` | 981 | S | 6/6/7/0/2/0 |
| `ai/policy/generations/current_options.py` | 85 | S | 0/0/0/0/0/0 |
| `ai/policy/generations/current_scoring.py` | 326 | S | 0/0/1/0/6/0 |
| `ai/policy/generations/registry.py` | 65 | D | 0/0/0/0/0/0 |
| `ai/policy/host.py` | 1,061 | D | 4/8/5/0/12/1 |
| `ai/policy/memory.py` | 346 | S | 0/4/1/2/1/0 |
| `ai/policy/outcomes.py` | 799 | S | 0/1/1/0/1/27 |
| `ai/policy/routines.py` | 3,289 | S | 0/10/18/0/5/28 |
| `ai/policy/source.py` | 61 | D | 4/0/0/0/0/1 |
| `ai/policy/telemetry.py` | 73 | S | 0/0/0/0/1/0 |
| `ai/policy/tree.py` | 191 | S | 0/0/0/0/0/0 |
| `ai/policy/utility.py` | 28 | S | 0/0/0/0/1/0 |
| `ai/remote_connection.py` | 79 | S | 0/2/0/1/1/0 |
| `ai/subjective/__init__.py` | 2 | S | 0/0/0/0/0/0 |
| `ai/subjective/hooks.py` | 150 | D | 0/0/2/0/2/0 |
| `ai/subjective/models.py` | 52 | S | 0/0/0/0/0/0 |
| `ai/subjective/printers.py` | 44 | S | 0/0/0/0/1/0 |
| `ai/subjective/processors.py` | 76 | S | 0/0/0/1/0/0 |
| `ai/subjective/queries.py` | 422 | S | 0/0/0/0/0/0 |
| `ai/subjective/runtime.py` | 1,368 | D | 0/7/2/10/10/13 |
| `ai/subjective/semantic_pool.py` | 118 | D | 0/2/2/1/8/1 |
| `ai/subjective/store.py` | 248 | D | 0/2/2/0/4/14 |
| `ai/telemetry/__init__.py` | 2 | S | 0/0/0/0/0/0 |
| `ai/telemetry/observer_projection.py` | 156 | S | 0/4/0/0/10/0 |

### `dnd/ai/`

| File | Lines | Coverage | H/V/C/J/R/K |
| --- | ---: | :---: | --- |
| `dnd/ai/__init__.py` | 2 | S | 0/0/0/0/0/0 |
| `dnd/ai/contracts/__init__.py` | 2 | S | 0/0/0/0/0/0 |
| `dnd/ai/contracts/control.py` | 1,202 | D | 0/5/7/3/16/3 |
| `dnd/ai/contracts/decision.py` | 37 | S | 0/0/0/0/0/0 |
| `dnd/ai/contracts/immutable.py` | 41 | D | 0/0/0/0/0/0 |
| `dnd/ai/contracts/observation.py` | 381 | D | 0/2/0/3/0/5 |
| `dnd/ai/contracts/observation_replay.py` | 284 | D | 0/9/5/0/9/17 |
| `dnd/ai/contracts/semantics.py` | 990 | D | 4/9/0/5/6/6 |
| `dnd/ai/feedback.py` | 34 | S | 0/0/0/0/0/0 |
| `dnd/ai/instrumentation.py` | 266 | S | 0/0/0/0/0/0 |
| `dnd/ai/policies/__init__.py` | 2 | S | 0/0/0/0/0/0 |
| `dnd/ai/policies/basic.py` | 923 | D | 0/0/0/0/4/0 |
| `dnd/ai/policy.py` | 65 | S | 0/0/0/0/0/0 |
| `dnd/ai/registry.py` | 185 | S | 0/0/0/0/0/0 |
| `dnd/ai/runner.py` | 55 | D | 0/0/0/0/2/0 |
| `dnd/ai/runtime/__init__.py` | 1 | S | 0/0/0/0/0/0 |
| `dnd/ai/runtime/action_semantics.py` | 1,788 | D | 0/0/4/0/1/4 |
| `dnd/ai/runtime/assignment.py` | 359 | D | 0/3/0/0/4/1 |
| `dnd/ai/runtime/assignment_lifecycle.py` | 130 | D | 0/2/0/0/0/0 |
| `dnd/ai/runtime/controller.py` | 153 | D | 0/1/0/0/0/0 |
| `dnd/ai/runtime/decision_epoch.py` | 1,341 | D | 0/4/1/6/13/16 |
| `dnd/ai/runtime/execution.py` | 205 | D | 0/11/0/0/3/0 |
| `dnd/ai/runtime/movement_revalidation.py` | 175 | D | 0/0/0/0/0/0 |
| `dnd/ai/runtime/state_projection.py` | 197 | D | 0/0/1/0/0/0 |
| `dnd/ai/runtime/subjective_projection.py` | 674 | D | 0/0/4/0/9/8 |
| `dnd/ai/runtime_gc.py` | 89 | D | 0/0/0/0/0/0 |
| `dnd/ai/specification.py` | 267 | D | 4/3/0/2/1/0 |

### `server/`

| File | Lines | Coverage | H/V/C/J/R/K |
| --- | ---: | :---: | --- |
| `server/__init__.py` | 0 | S | 0/0/0/0/0/0 |
| `server/action_serialization.py` | 53 | S | 0/0/0/1/2/0 |
| `server/agent_event_stream.py` | 175 | S | 0/1/1/0/3/0 |
| `server/agent_protocol/__init__.py` | 1 | S | 0/0/0/0/0/0 |
| `server/agent_protocol/objective_diagnostics.py` | 120 | S | 0/2/0/0/0/1 |
| `server/agent_protocol/observation_legacy.py` | 158 | S | 0/0/0/2/10/1 |
| `server/agent_protocol/telemetry.py` | 84 | S | 0/0/0/0/0/0 |
| `server/agent_runtime/__init__.py` | 1 | S | 0/0/0/0/0/0 |
| `server/agent_runtime/movement_revalidation.py` | 105 | S | 0/0/0/0/0/0 |
| `server/agent_runtime/observation_journal.py` | 2,046 | D | 0/0/8/10/22/34 |
| `server/ai_policy_composition.py` | 37 | S | 0/0/0/0/0/0 |
| `server/ai_takeover_manager.py` | 296 | S | 0/0/0/0/0/0 |
| `server/api_models.py` | 1,772 | S | 21/10/0/6/3/11 |
| `server/canonical_json.py` | 59 | S | 0/0/0/3/9/0 |
| `server/character_build_preview.py` | 130 | S | 2/2/0/1/0/2 |
| `server/character_build_preview_worker.py` | 119 | S | 4/1/0/1/0/0 |
| `server/character_content_rebase.py` | 355 | S | 0/3/2/0/7/0 |
| `server/character_deployment.py` | 51 | S | 0/0/0/0/1/6 |
| `server/character_directory_contracts.py` | 836 | S | 4/1/0/0/1/0 |
| `server/character_directory_routes.py` | 701 | S | 0/14/0/2/0/0 |
| `server/character_directory_service.py` | 2,245 | S | 17/22/8/8/15/21 |
| `server/character_equipment_mutation.py` | 192 | S | 1/1/0/1/0/0 |
| `server/character_equipment_mutation_worker.py` | 242 | S | 1/2/0/1/4/0 |
| `server/character_settlement.py` | 243 | S | 0/0/0/0/2/13 |
| `server/combat_log_projection.py` | 653 | S | 0/0/5/0/17/6 |
| `server/combat_log_source.py` | 112 | S | 0/1/0/0/0/0 |
| `server/content_catalog.py` | 545 | D | 18/7/4/4/0/1 |
| `server/content_http.py` | 70 | S | 1/0/0/0/0/2 |
| `server/directory_event_stream.py` | 195 | S | 0/0/0/0/3/1 |
| `server/event_contract.py` | 83 | D | 8/0/0/4/1/0 |
| `server/event_server.py` | 6,845 | S | 10/21/9/22/45/48 |
| `server/event_stream.py` | 969 | D | 0/1/1/5/3/7 |
| `server/external_ai_protocol.py` | 320 | S | 6/4/0/2/0/0 |
| `server/game_artifact_store.py` | 226 | D | 8/0/0/0/0/0 |
| `server/game_creation_catalog.py` | 41 | S | 0/0/0/0/0/0 |
| `server/game_creation_composition.py` | 374 | S | 7/0/1/5/9/23 |
| `server/game_creation_preview.py` | 360 | S | 4/2/0/10/1/4 |
| `server/game_creation_preview_contracts.py` | 90 | S | 1/0/0/0/0/0 |
| `server/game_creation_preview_worker.py` | 153 | S | 3/2/2/4/1/0 |
| `server/game_directory/__init__.py` | 5 | S | 0/0/0/0/0/0 |
| `server/game_directory/canonical.py` | 61 | D | 7/0/0/1/0/0 |
| `server/game_directory/contracts.py` | 1,126 | S | 0/0/0/0/0/0 |
| `server/game_directory/database.py` | 204 | S | 0/0/0/0/0/1 |
| `server/game_directory/errors.py` | 37 | S | 0/0/0/0/0/0 |
| `server/game_directory/local_profiles.py` | 420 | S | 0/3/0/0/1/0 |
| `server/game_directory/migrations.py` | 2,120 | S | 0/0/0/0/0/0 |
| `server/game_directory/repository.py` | 5,635 | S | 0/14/0/36/1/0 |
| `server/game_gateway.py` | 2,723 | S | 13/10/0/8/17/13 |
| `server/game_gateway_models.py` | 240 | S | 0/0/0/0/0/0 |
| `server/game_history.py` | 562 | S | 0/2/0/0/0/0 |
| `server/game_history_contracts.py` | 24 | S | 0/0/0/0/0/0 |
| `server/game_runtime_identity.py` | 7 | S | 0/0/0/0/0/0 |
| `server/game_summary_store.py` | 463 | D | 4/0/8/3/5/10 |
| `server/hosted_worker.py` | 598 | D | 5/3/4/1/0/0 |
| `server/local_game_lifecycle.py` | 604 | S | 0/4/0/2/0/25 |
| `server/mapeditor_support.py` | 1,066 | S | 21/11/1/4/18/19 |
| `server/objective_replay.py` | 210 | D | 4/1/0/3/0/1 |
| `server/objective_state.py` | 213 | D | 0/0/0/3/2/2 |
| `server/objective_timeline.py` | 417 | D | 0/5/3/2/12/0 |
| `server/player_replay.py` | 369 | D | 4/3/1/1/2/0 |
| `server/player_replay_capture.py` | 582 | S | 0/3/1/1/3/1 |
| `server/player_replication/__init__.py` | 1 | S | 0/0/0/0/0/0 |
| `server/player_replication/combat_log_projection.py` | 55 | S | 0/0/1/0/0/0 |
| `server/player_replication/journal.py` | 966 | D | 0/5/1/3/6/2 |
| `server/player_replication/mapper.py` | 2,798 | S | 0/1/0/2/121/9 |
| `server/player_replication/presentation.py` | 173 | D | 0/1/0/0/0/0 |
| `server/player_replication/runtime.py` | 842 | D | 0/2/1/0/6/0 |
| `server/player_replication/world_projection.py` | 643 | D | 0/2/1/6/13/0 |
| `server/player_replication_contract.py` | 2,114 | D | 4/35/0/1/44/0 |
| `server/registered_ai_controller.py` | 508 | S | 0/2/0/0/3/0 |
| `server/registered_ai_provider.py` | 924 | S | 0/1/0/5/7/0 |
| `server/replicated_world.py` | 51 | S | 0/1/0/0/0/0 |
| `server/replication_perspective.py` | 101 | D | 0/0/0/0/0/0 |
| `server/request_timing.py` | 72 | S | 0/0/0/0/0/0 |
| `server/runtime_authority.py` | 407 | D | 4/3/2/0/3/3 |
| `server/runtime_performance.py` | 36 | S | 0/0/0/0/0/0 |
| `server/session.py` | 525 | S | 0/1/0/0/0/0 |
| `server/spell_catalog.py` | 114 | S | 0/0/0/0/1/2 |
| `server/subjective_authority.py` | 139 | D | 0/0/0/0/0/0 |
| `server/subjective_parity_diagnostics.py` | 785 | S | 9/1/0/13/14/0 |
| `server/terminal_evidence.py` | 300 | D | 0/8/0/0/0/0 |
| `server/timeline_contracts.py` | 495 | D | 10/8/0/4/20/0 |
| `server/worker_player_replay.py` | 62 | S | 0/0/0/0/0/0 |
| `server/worker_proxy.py` | 314 | S | 0/4/0/2/0/6 |
| `server/worker_replay.py` | 87 | S | 0/0/0/0/0/0 |
| `server/worker_terminal_spool.py` | 686 | D | 10/3/0/0/1/0 |
| `server/world_contracts.py` | 606 | D | 0/5/0/6/1/6 |
| `server/world_projection.py` | 668 | S | 2/7/1/9/11/0 |

### `services/`

| File | Lines | Coverage | H/V/C/J/R/K |
| --- | ---: | :---: | --- |
| `services/__init__.py` | 2 | S | 0/0/0/0/0/0 |
| `services/ai_policy_server/__init__.py` | 28 | S | 0/0/0/0/0/0 |
| `services/ai_policy_server/__main__.py` | 67 | S | 0/0/0/0/0/1 |
| `services/ai_policy_server/app.py` | 128 | S | 0/0/0/0/0/0 |
| `services/ai_policy_server/composition.py` | 80 | D | 0/0/0/0/0/0 |
| `services/ai_policy_server/external_ai_registry.py` | 609 | D | 4/1/0/2/0/7 |
| `services/ai_policy_server/policies.py` | 114 | S | 0/0/0/0/0/0 |

### `custom_ai/`

| File | Lines | Coverage | H/V/C/J/R/K |
| --- | ---: | :---: | --- |
| `custom_ai/__init__.py` | 2 | S | 0/0/0/0/0/0 |
| `custom_ai/tactical/__init__.py` | 29 | S | 0/0/0/0/0/0 |
| `custom_ai/tactical/memory.py` | 177 | S | 0/0/0/0/0/3 |
| `custom_ai/tactical/policy.py` | 201 | D | 0/0/0/0/0/0 |

### `sdk/`

| File | Lines | Coverage | H/V/C/J/R/K |
| --- | ---: | :---: | --- |
| `sdk/typescript/src/client.ts` | 302 | S | 0/0/0/0/0/0 |
| `sdk/typescript/src/directoryClient.ts` | 1,016 | S | 0/8/0/0/0/0 |
| `sdk/typescript/src/generated/contracts.generated.ts` | 7,233 | G | 28/0/0/0/0/2 |
| `sdk/typescript/src/index.ts` | 13 | S | 0/0/0/0/0/0 |
| `sdk/typescript/src/objectiveDiagnostics.ts` | 506 | S | 0/0/0/0/0/0 |
| `sdk/typescript/src/objectiveSse.ts` | 317 | S | 0/0/0/0/0/0 |
| `sdk/typescript/src/reducer.ts` | 357 | S | 0/0/0/0/0/0 |
| `sdk/typescript/src/renderProjection.ts` | 991 | S | 0/0/0/0/0/0 |
| `sdk/typescript/src/replay.ts` | 324 | D | 0/0/0/0/0/0 |
| `sdk/typescript/src/sse.ts` | 147 | S | 0/0/0/0/0/0 |
| `sdk/typescript/src/subjectiveClient.ts` | 452 | D | 0/1/0/0/0/0 |
| `sdk/typescript/src/subjectiveJournal.ts` | 595 | D | 0/0/0/0/0/0 |
| `sdk/typescript/src/subjectiveSse.ts` | 1,047 | D | 0/0/0/0/0/0 |
| `sdk/typescript/src/tests/characterDirectory.test.ts` | 838 | S | 1/25/0/0/0/0 |
| `sdk/typescript/src/tests/contentCatalog.test.ts` | 429 | S | 2/28/0/0/0/0 |
| `sdk/typescript/src/tests/fixtures.ts` | 283 | S | 0/0/0/0/0/0 |
| `sdk/typescript/src/tests/gameCreation.test.ts` | 309 | S | 0/19/0/0/0/0 |
| `sdk/typescript/src/tests/gameRouting.test.ts` | 641 | S | 0/39/0/0/0/0 |
| `sdk/typescript/src/tests/objectiveDiagnostics.test.ts` | 400 | S | 0/26/0/0/0/0 |
| `sdk/typescript/src/tests/renderProjection.test.ts` | 576 | S | 0/43/0/0/0/0 |
| `sdk/typescript/src/tests/replay.test.ts` | 292 | S | 0/16/0/0/0/0 |
| `sdk/typescript/src/tests/replication.test.ts` | 1,358 | S | 0/81/0/0/0/0 |
| `sdk/typescript/src/tests/sse.test.ts` | 18 | S | 0/7/0/0/0/0 |
| `sdk/typescript/src/validation.ts` | 316 | D | 0/16/0/0/0/0 |

## Missing static local import targets

This list checks exact absolute `from <local module> import ...` module paths,
not whether every imported member still exists. It therefore establishes a
minimum stale dependency set, not complete server compatibility.

| Missing module | Importer and line |
| --- | --- |
| `dnd.content_system.background_starting_holdings` | `server/character_directory_service.py:17` |
| `dnd.content_system.builtin_character_builds` | `server/character_directory_service.py:25`, `server/game_creation_composition.py:10` |
| `dnd.content_system.character_appearance` | `server/character_content_rebase.py:16`, `server/character_directory_service.py:20` |
| `dnd.content_system.character_build_validation` | `server/character_directory_contracts.py:18`, `server/character_directory_service.py:12` |
| `dnd.content_system.character_content_migrations` | `server/character_content_rebase.py:20` |
| `dnd.content_system.character_materialization` | `server/character_build_preview_worker.py:10`, `server/character_equipment_mutation_worker.py:12` |
| `dnd.content_system.item_bindings` | `server/character_settlement.py:16`, `server/mapeditor_support.py:17`, `server/world_projection.py:14` |
| `dnd.content_system.item_materialization` | `server/mapeditor_support.py:21` |
| `dnd.content_system.starting_apparel_definitions` | `server/character_directory_service.py:29` |
| `dnd.core.content.item_definitions` | `server/content_catalog.py:45`, `server/mapeditor_support.py:36` |
| `dnd.core.content.premade_characters` | `server/character_build_preview.py:16`, `server/character_build_preview_worker.py:18`, `server/character_content_rebase.py:32`, `server/character_directory_contracts.py:44`, `server/character_directory_service.py:49` |
| `dnd.core.content.starting_equipment` | `server/character_directory_contracts.py:51`, `server/character_directory_service.py:55` |
| `dnd.core.senses` | `server/world_contracts.py:17` |
| `dnd.items.environment_content` | `server/mapeditor_support.py:43` |
| `dnd.tiles` | `server/mapeditor_support.py:53` |

## Supplemental generated/configuration inputs

| File | Coverage | Owner |
| --- | --- | --- |
| `server/event_contract.generated.json` | G: descriptor counts, runtime readers, generator traced | `devtools/generate_event_contract.py`; `server/event_contract.py`; `server/timeline_contracts.py` |
| `sdk/typescript/src/generated/contract.generated.json` | G: full JSON parse, descriptor counts and exact removed field traced | `devtools/generate_typescript_sdk.py`; `sdk/typescript/src/validation.ts` |
| `sdk/typescript/package.json` | S: commands/dependencies; no command executed | TypeScript build/test tooling |
| `sdk/typescript/tsconfig.json` | S: compiler configuration; no compiler executed | TypeScript build tooling |
| `ai/AI_AGENT_OBSERVER.html` | D: 1156-line HTML scanned; inline JavaScript read at 487–1154 | Standalone legacy agent telemetry viewer |

Markdown plans/READMEs are ancillary documentation, not executable source in the
counts above. They were inventoried by file discovery and were not used as proof of runtime
requirements. Generated lockfiles, installed dependencies, bytecode and build
output were excluded.
