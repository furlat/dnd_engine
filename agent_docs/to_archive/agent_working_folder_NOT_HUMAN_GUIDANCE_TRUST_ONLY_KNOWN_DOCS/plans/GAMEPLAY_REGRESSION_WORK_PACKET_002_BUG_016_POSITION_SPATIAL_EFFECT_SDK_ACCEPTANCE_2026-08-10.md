# Gameplay Regression Work Packet 002

## BUG-016 Stage 1: position-only spatial-effect SDK acceptance

Date: 2026-08-10  
Status: Gate A Revision 2 draft; no production edit, test edit, build, or execution is
authorized until the frozen packet receives independent R1-R4 approval and
Coordinator governance verification.

## 1. Authority and selection

This packet is the next bounded objective in the already authorized
BUG-001--BUG-034 gameplay-regression program. It follows the accepted sequence
in Work Packet 001 Section 8: server projection to generated SDK acceptance,
beginning with BUG-016.

The regression ledger records the complete BUG-016 mismatch:

1. Python permits a position-only spell application whose child is a spatial
   effect;
2. the TypeScript SDK rejects any position-only application that has effects;
3. later NeuroClient mapping also contains incompatible position-only rules.

This packet closes only the first cross-language seam: an already lawful
Python presentation graph must be accepted by the TypeScript SDK wire gate.
It does not claim that the later NeuroClient mapper, reducer, or scene accepts
or renders the graph. BUG-016 remains open after this packet for those later
seams.

Routine progression is automatic only after unanimous R1-R4 approval and
Coordinator verification. Any material surface or architecture expansion
returns through Planner and Coordinator under the current human governance.

## 2. Frozen baseline identity

The Gate A baseline is:

| Surface | Lines | SHA-256 | Role |
|---|---:|---|---|
| `sdk/typescript/src/subjectiveSse.ts` | 1286 | `471011dd9cfb6e553197cfc9c3746a332f22c6c44f4d76cf0e4f373a3439b349` | proposed Implementation file |
| `sdk/typescript/src/tests/replication.test.ts` | 2505 | `35304bf3d82be384060766db5a08eac55645f91aa0acd20568b1d319029f7e03` | proposed Tester file |
| `server/player_replication_contract.py` | 2481 | `6c3639a0bea5de33b08f7405c42c20c3818d3e7c1e587e9cd509a5441ad9d3b6` | frozen Python authority |
| `tests/manual/test_117_player_replication_contract.py` | 2325 | `e37debe11189b70896139a8d0d235ad0b9de0f542bd9155bcab85a2988944f8d` | frozen negative proof |
| `tests/manual/test_121_canonical_presentation_mapper.py` | 4146 | `8f34e0a1861ec1ac6a014ac47899c4a3eb2703b7448ef2e0024301a168f3638e` | frozen positive projection proof |
| `sdk/typescript/package.json` | 27 | `7c557f07e848d4dfdd7d2b3d3572a10c8771c17b737101922e157ff7b741dbd3` | frozen command authority |

All seven scoped paths are clean at Gate A drafting time.

## 3. Frozen causal truth

### 3.1 Python contract authority is already correct

`SpellTargetPresentation.validate_target` requires at least one of
`target_uuid` or `position` and requires unique effect IDs. It deliberately
does not require an entity UUID merely because the application owns an
effect.

The frame graph validator then applies the type-specific rule:

1. a `SpatialEffectPresentationCue` is lawful only when the owning spell
   application has `target_uuid is None` and a non-null `position` contained
   in the effect's `affected_positions` or `previous_positions`;
2. every non-spatial spell effect requires an explicit entity target and must
   match that target;
3. existing source, parent, child, ordering, and uniqueness rules remain in
   force.

The canonical mapper already creates the matching application for a spell
owned spatial effect. The frozen test
`test_spell_created_spatial_effect_is_an_exact_position_application` proves a
real `SpellEvent` plus `SpatialEffectChangeEvent` becomes an exact two-cue
graph with reciprocal parent/child IDs and a position-only application whose
effect ID names that spatial cue.

The frozen contract test
`test_presentation_graph_rejects_action_effect_ownership_mismatches` proves
that converting a non-spatial spell effect to a position-only application is
still rejected. These Python files require no edit.

### 3.2 The SDK rejects that lawful graph twice

In `sdk/typescript/src/subjectiveSse.ts`:

1. `assertSpellTargetSemantics` rejects every application with nonempty
   `effect_presentation_ids` and `target_uuid === null`, before it can inspect
   the child cue type;
2. the spell graph branch admits only damage, heal, condition, and forced
   movement children, then compares their entity target to the application
   target. It does not admit or validate a `spatial_effect` child.

The SDK test suite has an existing case named
"position target with entity effects", but that graph contains only a dangling
effect ID and no delivered effect cue. After the broad target guard is removed,
it still rejects at graph closure. It remains useful closure evidence but does
not prove the non-spatial explicit-entity rule. The suite has neither a lawful
spell-owned spatial-effect graph nor a closed non-spatial position-only matrix.
Those missing branch-isolating cases define the natural first-red seam and its
negative closure.

## 4. Objective and proof boundary

The packet is complete only when all of the following are true:

1. the existing SDK decoder accepts a spell application with
   `target_uuid: null`, a non-null position, and one spatial-effect child when
   that position appears in the child's current or previous disclosed
   geometry;
2. the SDK still rejects a target with neither entity nor position;
3. it still rejects position-only applications with damage, heal, condition,
   or forced-movement children;
4. it rejects a spatial child owned by an entity-target application;
5. it rejects a spatial child whose disclosed geometry does not contain the
   application position;
6. all existing SDK tests remain green after the correction;
7. the production and test diffs are confined to the two authorized files.

The proof is contract acceptance only. It does not prove journal ingestion,
NeuroClient planning, reducer settlement, scene creation, pixels, actual
Grease execution, or any other BUG-016 stage.

## 5. Exact allowed surfaces and owners

### 5.1 Implementation owner

Implementation may edit exactly:

- `sdk/typescript/src/subjectiveSse.ts`

Implementation must not edit tests, Python, generated model definitions,
package metadata, NeuroClient, or any other file. Implementation performs no
build or test command and reports only the exact diff, line count, and SHA-256
to Planner.

### 5.2 Tester owner

Tester may edit exactly:

- `sdk/typescript/src/tests/replication.test.ts`

Tester must not edit production, Python, package metadata, generated output,
or any other file. Tester may execute only the separately authorized one-shot
first-red and green commands described below, must stop after each invocation,
and returns complete results only to Planner.

### 5.3 Frozen read-only authorities

The following stay byte-identical throughout this packet:

- `server/player_replication_contract.py`;
- `tests/manual/test_117_player_replication_contract.py`;
- `tests/manual/test_121_canonical_presentation_mapper.py`;
- `sdk/typescript/package.json`.

The Python tests are already-reviewed reference evidence, not commands in this
packet. No Python, backend, or cross-repository execution is authorized.

## 6. Exact Implementation packet

Implementation makes the smallest type-aware correction in the existing
validation traversal:

1. In `assertSpellTargetSemantics`, retain the entity-or-position requirement
   and effect-ID uniqueness check. Remove only the overbroad rule that rejects
   all effect-bearing applications with `target_uuid === null`.
2. In the existing spell graph branch, add `spatial_effect` to the accepted
   spell-effect union.
3. For a spatial-effect child, require all of:
   - `target.target_uuid === null`;
   - `target.position !== null`;
   - the position equals an entry in `effect.affected_positions` or
     `effect.previous_positions`, using the existing `samePosition` helper.
4. After validating that spatial branch, continue without applying entity
   target/source rules that do not exist on a spatial-effect cue.
5. For all non-spatial effect kinds, explicitly require a non-null entity
   target before preserving the existing target match and caster-source
   checks.
6. Preserve every existing parent/child closure, duplicate-ID, application
   ordering, source, scalar, geometry, and content-ref validator.

No generated union, model field, public type, wire shape, serializer, or error
transport changes. No generic validator framework or compatibility fallback.

## 7. Exact Tester packet

Tester adds a small local graph helper or equivalent inline fixtures using the
existing `cueBase`, `spellCue`, `spellTarget`, `spatialEffectCue`, and
`decodePresentationGraph` owners. No hand-authored decoder or parallel schema
is permitted.

### 7.1 Required lawful graphs

The suite must register two independently named tests and assert decode success
for:

1. a created spatial effect whose position-only spell application points to a
   coordinate in `affected_positions` and absent from `previous_positions`;
2. a removed spatial effect whose position-only spell application points to a
   coordinate in `previous_positions` and absent from `affected_positions`.
   The removed fixture may use empty current geometry while retaining valid
   former geometry and a valid disclosed anchor.

Each graph must have exactly reciprocal spell/spatial parent-child IDs, one
contiguous application, and the effect ID listed by both the spell child list
and the application effect list. Fixtures must pass through the existing
JSON/envelope decode helper, not call a private validator directly. The two
cases may share a small graph-construction helper, but they must be separate
Node test cases so a first-red result independently reports both the current-
geometry and previous-geometry boundaries.

### 7.2 Required malformed graphs

Every new malformed graph must otherwise be contract-valid and must be a
one-axis mutation of a lawful reciprocal graph. The suite must retain or add
explicit rejection for:

1. target UUID and position both null;
2. a closed matrix of position-only applications with real delivered
   non-spatial children covering damage, heal, condition, and forced movement.
   Each matrix row starts as a lawful entity-target spell graph with matching
   reciprocal IDs, target, source where applicable, parent, and other child
   fields; only the application changes to `target_uuid: null` plus a non-null
   position. The existing dangling `"effect"` fixture cannot satisfy this
   requirement and remains only child-closure evidence;
3. a spatial child whose otherwise-lawful application retains an in-geometry
   position and additionally sets a non-null entity UUID. Only the forbidden
   entity ownership changes;
4. a spatial child whose otherwise-lawful application retains
   `target_uuid: null` and all valid reciprocal cue fields while only its
   position moves outside both current and previous geometry;
5. existing duplicate IDs, child closure, geometry ordering, and scalar
   negatives.

The tests assert contract success or `ContractValidationError`; they do not
pin incidental full error prose beyond what is needed to discriminate these
boundaries.

## 8. First-red and green evidence sequence

### Gate A

This plan must first receive unconditional independent R1-R4 approval on one
frozen identity and Coordinator governance verification.

### Tester first-red

1. Planner dispatches only Section 7 to Tester as an edit-only assignment.
2. Tester returns the frozen test diff/identity without execution.
3. R1-R4 independently verify the test would accept the lawful backend shape
   and preserve malformed negatives; Coordinator verifies the ledger.
4. Planner may then authorize exactly one invocation against the unchanged
   SDK production file:

   `npm --prefix sdk/typescript test`

5. The intended red requires both independently named lawful tests from
   Section 7.1 to fail at the existing `assertSpellTargetSemantics` rule that
   rejects effect-bearing applications with `target_uuid === null`. The test
   runner must reach and report both names independently. Any one lawful case
   not reached, unexpected success, build failure, other test failure, or
   different causal boundary is frozen and reviewed; there is no rerun or
   workaround.

### Implementation and green

1. Only after the intended first red receives R1-R4 review and Coordinator
   verification may Planner dispatch Section 6 to Implementation.
2. Implementation returns its edit-only diff/identity and runs nothing.
3. The combined frozen production/test surface receives fresh independent
   R1-R4 static review and Coordinator verification.
4. Planner may then authorize Tester exactly one green invocation of the same
   command:

   `npm --prefix sdk/typescript test`

5. Tester stops immediately and returns the complete command result, SDK clean
   build result, Node test totals, failure details if any, and frozen identities
   only to Planner.
6. Gate B requires fresh R1-R4 review of plan, red, implementation, tests, and
   green evidence, followed by Coordinator governance verification.

No `npm install`, dependency synchronization, network, Python, browser, Vite,
HTTP, service, alternate test command, debug command, formatter, second run,
or generated-file execution is authorized.

## 9. Performance, duplication, and serialization constraints

1. Validation stays inside the existing single presentation-graph traversal.
2. Spatial membership uses the existing coordinate equality helper over the
   child's already-decoded current/previous positions. No new graph pass,
   index, cache, registry, or persistent allocation.
3. No backend rule is copied into a new framework. The SDK necessarily checks
   its generated discriminated union at the wire boundary and reuses existing
   cue kinds and helpers.
4. No new DTO, public API, schema field, protocol version, serialization form,
   persistence, telemetry surface, diagnostic warehouse, fixture framework,
   dependency, or build step.
5. The test uses the existing production decoder and fixture vocabulary; it
   must not construct a second validation authority.

## 10. Non-goals

This packet does not:

- edit the Python backend or claim its existing contract is defective;
- run or expand backend tests;
- change generated TypeScript model fields or OpenAPI/schema generation;
- edit NeuroClient;
- fix projectile/missile mapper filtering;
- prove journal, reducer, scene, GPU, animation, UI, or pixels;
- implement or invoke a live Grease/Fog Cloud scenario;
- address BUG-010/011 or any other regression family;
- add broad cleanup, naming changes, formatting, or unrelated tests.

## 11. Stop conditions

Owners stop and return only to Planner if any of the following becomes true:

1. a third source or test file appears necessary;
2. a Python/backend/generated-schema/package/NeuroClient change appears
   necessary;
3. the lawful graph cannot be expressed through current generated types;
4. the first red is not the existing SDK position/spatial-effect mismatch;
5. another failing test or contract inconsistency is exposed;
6. a dependency, framework, schema, protocol, persistence, public-contract,
   or materially different architecture is proposed;
7. any owner would need a rerun, debug command, alternate command, workaround,
   or scope expansion.

The next client-side BUG-016 seam requires its own later packet and Gate A.

## 12. Gate A review questions

Each reviewer must independently answer all of the following against the
complete frozen packet and source surface:

1. Does the packet identify the real cross-language mismatch without changing
   the already-correct Python authority?
2. Is the exact SDK algorithm equivalent to the Python spatial/non-spatial
   graph rule, including current and previous geometry?
3. Do the positive and negative fixtures close false-acceptance paths without
   creating a second contract authority?
4. Is the natural first-red boundary discriminating and the one-shot evidence
   flow truthful?
5. Are Implementation and Tester surfaces coherent, separate, and complete?
6. Are performance, duplication, serialization, and scope constraints
   sufficient?
7. Is any hidden caller, generated-contract requirement, extra file, or
   material scope expansion necessary?

Allowed Gate A verdicts are exactly:

- `APPROVE_WORK_PACKET_002_GATE_A`
- `CHANGES_REQUIRED`

Verdicts return solely to Planner. Reviewers remain peer-isolated; no reviewer
contacts an owner, another reviewer, or Coordinator directly.

## 13. Revision record

### Gate A Revision 1

The blind initial ledger was R1 `CHANGES_REQUIRED`, R2
`APPROVE_WORK_PACKET_002_GATE_A`, R3 `CHANGES_REQUIRED`, and R4
`CHANGES_REQUIRED`. Revision 1 was rejected; its approval does not carry.

### Gate A Revision 2

Revision 2 makes only the converged in-scope test-specification corrections:

1. it identifies the existing position/effect case as dangling-child closure
   evidence rather than non-spatial target evidence;
2. it makes current-only and previous-only lawful graphs independently named
   tests and requires both to reach the intended first-red guard;
3. it requires closed, otherwise-lawful position-only negatives for all four
   supported non-spatial child kinds;
4. it makes the entity-owned spatial and geometry-mismatch negatives one-axis
   mutations of lawful reciprocal graphs.

No source owner, file surface, algorithm, command, scope, or governance
boundary changed.
