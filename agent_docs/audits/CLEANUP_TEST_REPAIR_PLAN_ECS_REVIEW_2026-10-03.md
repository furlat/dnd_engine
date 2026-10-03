# Cleanup repair plan — independent ECS / import-DAG review

**Final disposition: APPROVE.** This approves the concrete repair design and
acceptance boundaries below, not its implementation or permission to implement.
Both initial plan blockers were corrected and the revised plan was re-read.
There are no remaining blocking ECS/import-DAG findings against this revision.

Reviewed plan:
`agent_docs/CLEANUP_TEST_REPAIR_PLAN_2026-10-03.md`.
Exact SHA-256:
`78f6cb43170e26eff5b8f37dbf886838d98070ec33e1b262ea8e93c4e7200c06`.
Re-review date: 2026-10-03. Source context is the uncommitted cleanup against
`981079bc0208dbb23f3ccc927347eef77fef4c30`.

Read the full plan, current recovery checkpoint, prior independent implementation
ECS report and the relevant condition/composition/paused-test source. No production
or test edits, runtime patches, new tests, test runs or new agents were used for
this plan review. Only this audit document was authored.

## Resolution of the initial review

The initial revision
`26e8ae0166910812fb20b1183737482fd2be4f1e84face858b7e99c030949570`
received REQUEST CHANGES for RP-ECS-1 and RP-ECS-2. Their original reasoning is
retained below as review history; both are resolved in the approved revision.

| Finding | Verified plan correction |
| --- | --- |
| RP-ECS-1 | Step 8 explicitly reuses the block `required_condition` / prepared-removal boundary and shares the membership/replacement commit portion with Entity while preserving immunity, saving throws, names and provenance. It rejects simply moving `ensure_concentration` earlier, commits replacement only after both admissions and required removals, preserves previous owner/children on failure, requires exact accepted UUIDs, and retains same-cast reuse/item capacity. Acceptance now explicitly includes failed child, failed sustainer, failed replacement and vetoed removal with a prior active owner/children. |
| RP-ECS-2 | Step 11 names the actual `CharacterItemV2` authenticated round-trip tests, `CharacterBuild` / `create_character` composition and native equipment mutation/transfer boundaries. It preserves server database/API/deployment coverage in the proposed explicit paused lane, requires per-test disposition, and forbids new disk persistence/account/deployment services or claiming those native tests prove the paused server works. |

The new Spike Growth subsection of step 6 was also reviewed. Its native entry
producer in `dnd/spells/transmutation.py:148–184` currently calls the ordinary
damage path without the independent-resolution/origin parameters. The repair
uses those already-existing parameters, keeps movement/spell trigger ancestry,
and requires unchanged native amounts/saves/movement with one result per cue.
This completes the intended producer migration without a new event family or
spell-specific renderer workaround.

`CharacterItemV2` and its authenticated JSON test were verified directly in
`dnd/core/content/durable_characters.py:69` and
`tests/progression/test_direct_item_durable_and_proficiency.py:39`; the revised
plan no longer conflates durable item records with full live-character storage.

## Initial blockers — resolved

### RP-ECS-1 — P1, resolved: specify paired concentration/effect admission and failed replacement preservation

Initial plan location: step 8, lines 260–282, particularly “Establish successful
concentration admission before accessing/linking it.”

The plan correctly requires rejected concentration to leave no orphan effect,
but does not define the replacement commit boundary. Simply installing the new
concentration earlier can remove the old valid spell and its children before the
new child subsequently rejects. Calling the current helper later has the
opposite existing defect: the child has already committed before the owner can
reject. “Replacement/expiry still work” does not specify the failed replacement
case or preservation of the prior exact owner.

This is grounded in the current source:

- `dnd/actions.py:4999–5008` currently commits the target effect before requiring
  its concentration owner.
- `dnd/conditions.py:1990–2040` prepares old concentration/child removals, and
  `:2121–2140` transfers surviving children and commits the old removals during
  `Concentrating._apply`.
- `dnd/core/base_block.py:1276–1392` already has a `required_condition` admission
  path with prepared removals. `dnd/entity.py:1641–1755` overrides `add_condition`
  without that argument and separately owns immunity, saving throws and
  entity-specific behavior provenance. Bypassing that override to use the block
  implementation would lose those real admission rules.

**Required plan correction:** name the existing block/entity condition
admission/commit boundary being reused or narrowly consolidated for a dependent
effect and its required owner. Include `base_block.py`, `entity.py` and the
existing Concentrating replacement owner where necessary. Preserve Entity's
immunity/save/provenance admission; verify the exact accepted owner UUID before
assigning the cast reference or adding a link. Do not create a generic
transaction framework or rely on removing an already committed orphan afterward.

Make the acceptance cases explicit: failed new-owner admission, failed new-child
admission, and vetoed removal/replacement each preserve the prior accepted
condition, its exact children/grants and relevant concentration slots; a rejected
same-name replacement releases only its own provisional state. Include an actor
sustainer and an item sustainer, including retained slots in a multi-slot owner.
Successful replacement still removes only admitted displaced children. Vetoed
ordinary removal must leave the active effect unchanged. Preserve committed
action/item costs and independently completed child results.

This closes the actual ECS-1/ECS-2 intersection; adding an early null check alone
does not.

### RP-ECS-2 — P2, resolved: bound the native persistence promise before moving paused tests

Initial plan location: step 11, lines 360–371, requiring a “real current persistence
boundary” and active coverage of “save/load, equipment identity and mutations.”

The proposed explicit paused-server lane is a defensible disposition, and the
plan correctly forbids silent filtering and a false repository-wide green claim.
The active replacement coverage is nevertheless unnamed and broader than the
native boundaries inspected here:

- `dnd/content/characters/builds.py:81–101` defines saveable *authored input*;
  `prepare_character` at `:271` constructs an entity/loadout and
  `create_character` at `:339` composes it. This does not itself establish a
  running-character save/load contract retaining exact possession identities.
- `dnd/content/characters/progression.py:489` reconstructs progression owners
  from already-loaded semantic rows. Its existing test at
  `tests/progression/test_direct_character_progression.py:286` verifies receipt
  hydration, not live equipment persistence.
- The failing persistent-equipment module contains server-specific revision,
  ownership/idempotency and deployment-lease contracts. The deployment module
  also includes native scenario composition assertions alongside server request
  and database setup. Ordinary equip/unequip or an authored-input JSON round trip
  cannot be reported as replacement coverage for those different contracts.

**Required plan correction:** identify the exact supported native API and test
IDs for the active persistence claim. If full live save/load is absent, limit
this repair to existing authored-input round trips, progression hydration and
native equipment mutation/identity contracts, and explicitly disclose the
remaining persistence contract as paused/unimplemented rather than inventing it
inside cleanup. Map the moved tests to the named paused lane and any extracted
native assertions to their actual existing public boundaries. Preserve the
server revision/lease tests and their failures without claiming equivalent
active coverage. Approval must not implicitly authorize a new persistence owner
or resurrection of removed server services.

## Parts that satisfy this review

- ECS-2's existing release hook is the correct owner for provisional direct
  weapon/light/action state. Exact-instance cleanup and preservation of already
  committed resource releases are retained. The revised RP-ECS-1 remedy supplies
  the missing replacement/veto detail without a second lifecycle.
- ECS-3's remedy keeps one value/economy authority and separates contextual
  computation/cache ownership from serialized rule state. It explicitly rejects
  the prior deep-copy workaround and a parallel speed model, with relevant
  contextual content and invalidation checks.
- Steps 5–6 retain passive causal references, unknown visible causes and one
  authored damage-commit schedule. They do not infer owners from recipes or add
  rule execution to presentation. Legacy ambiguity is distinct from an explicit
  current unknown cause.
- Step 7's intended mutation/publication ordering is correct: preflight, commit
  exact native sections, then publish their creation. Targeted terminal-provider
  identity belongs in the existing spatial query; intervening providers remain
  authoritative blockers. No wall-art or geometry rewrite is authorized.
- Step 9 expands schema roots using the actual passive authoring types and keeps
  the fresh-process no-runtime-import gate. That addresses missing vocabulary
  without duplicating Python rules or creating a second client schema model.
- Step 10 keeps AI projection passive and item/content evidence nonauthoritative.
  Step 12 explicitly requires independent anti-slop, ECS and event/presentation
  implementation reviews against the final source. Plan approval cannot stand
  in for them.
- The setup/fixture repairs and full-suite accounting do not erase failed
  assertions, retired admissions or historical records. Unblocking setup is
  correctly distinguished from passing all affected tests.

The review has not found a need to change the accepted movement policy, spell
rules, item charges, wall geometry or artwork. The approved plan preserves those
contracts. Execution still requires the plan's public-boundary reproductions,
complete active-suite accounting, explicit paused-test disclosure, visual
acceptance and fresh independent implementation reviews. The earlier ECS
implementation REQUEST CHANGES remains in force until those defects are fixed
and their actual implementation is re-reviewed.
