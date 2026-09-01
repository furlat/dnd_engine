# Content Recovery CR-0 — Evidence Freeze and Executable Ledger

Status: `ACCEPTED_FOR_IMPLEMENTATION`

Date: 2026-08-30  
Repository: `/mnt/c/users/tommaso/documents/dev/dnd_engine`  
Branch at planning time: `codex/july-reconstruction`  
HEAD at planning time: `205fd679fde51d5319d332f12ec241d7aecd93a6`

## 1. Authority and purpose

This is the bounded implementation plan for CR-0 of
`DND_JULY_RECONSTRUCTION_CONTENT_RECOVERY_AUDIT_AND_MIGRATION_PLAN_2026-08-30.md`.
The governing plan SHA-256 is:

`3e6a38a534331f0cdf92127fe5d9b765bf7e81a7d44baee08876bfd1613bec7b`

CR-0 makes the later content migration mechanically auditable. It freezes the
current declarations, accepted behavior evidence, authored source rows,
importers, and collectible semantic proofs before any content family is moved.
It does not change runtime behavior and does not begin CR-1.

Evidence priority remains:

1. current reconstructed engine for present mechanics and ownership;
2. accepted checkpoint `513dd97` for accepted behavior and inventories;
3. July reference `4ebe523` when later evidence is absent;
4. broken checkpoint `1f2e525` and `dnd_engine_broken` for forensics only.

No lower-priority source may override a higher-priority source silently. A
disagreement becomes an explicit row-level disposition.

## 2. Hard boundary

### 2.1 Allowed work

CR-0 may change only:

- this implementation plan and one CR-0 completion ledger;
- one machine-readable, non-runtime evidence manifest under
  `content_data/ledgers/`;
- focused tests under `tests/architecture/`, `tests/engine/`,
  `tests/progression/`, or another existing test domain when necessary to
  preserve a genuine in-process semantic case from an uncollectible mixed
  module;
- test-only helpers local to those tests, only when repeated setup cannot be
  expressed clearly with existing public fixtures.

### 2.2 Forbidden work

CR-0 must not:

- modify any file under `dnd/` or change production behavior;
- restore `server`, deprecated-server paths, `dnd.core.senses`, `dnd.tiles`,
  `_entity_by_position`, deleted lookup dictionaries, or compatibility aliases;
- create a runtime registry, migration API, content adapter, facade, controller,
  service, manager, repository, index, cache, or generic evidence loader;
- add a second content authority, dual write, late import, circular import,
  `getattr`/reflection escape, or `TYPE_CHECKING` escape;
- materialize the 673 declarations as new target objects;
- claim the 743 missing SRD rows as implemented;
- migrate a content family, delete old content machinery, or start CR-1;
- alter server/SDK/transport/generated/renderer/editor/cross-language files.

The manifest is audit data. Production code must never import it.

## 3. Exact deliverables

### 3.1 CR-0 evidence manifest

Create:

`content_data/ledgers/content_recovery_cr0_evidence.json`

It is a normalized JSON document with stable key ordering and newline. It owns
evidence only, never gameplay state. Its schema is deliberately data-shaped:

```text
schema_version
authority
source_artifacts
legacy_authorities
implemented_content
binding_reconciliation
python_binding_overlay
srd_proof_overlay
production_importers
excluded_or_rescued_test_modules
maintained_in_process_nodes
```

No Python schema class or loader is added. The architecture test validates the
JSON shape directly.

Every row collection is sorted by its stable identity and rejects duplicates.
Every path is repository-relative. Every stored SHA is lowercase SHA-256.

### 3.2 CR-0 architecture/evidence proof

Create:

`tests/architecture/test_content_recovery_cr0_evidence.py`

It proves only durable public facts:

- the manifest parses and has the required top-level fields;
- all referenced repository paths and Git objects exist;
- current file hashes are exact;
- row identities are unique and deterministically ordered;
- declared counts equal the actual row arrays;
- all 673 current declarations have dispositions within the unified legacy
  authority inventory;
- every current implemented/partial claim names a collectible current semantic
  proof, while accepted-only rows name an exact accepted Git proof;
- all current generic-content and `ContentRef` production importers have a
  disposition;
- the maintained node list is explicit, sorted, unique, collectible, and
  reproducibly hashed;
- the original 925-row SRD ledger remains byte-exact and the proof overlay names
  exactly its 177 implemented and 5 partial rows; the source ledger continues
  to own the 743 missing rows;
- current/accepted data bindings and Python-only authored bindings have exact
  row-level reconciliations;
- no production module imports the CR-0 manifest or its test.

This test must not assert private registry dictionary shapes, call counts, or
implementation-specific helper names.

### 3.3 Rescued semantic tests

Move or rewrite only genuine in-process semantic cases that are trapped inside
mixed deprecated-server modules. A rescued case must:

- exercise an engine/progression/spell/content capability through current public
  boundaries;
- be placed in the matching existing test domain;
- use current public fixtures and current ECS composition;
- preserve the old case's semantic assertion, not its server/bootstrap shape;
- cite its source module and old test name in the manifest;
- collect and pass without importing deprecated infrastructure.

Do not migrate:

- HTTP/session/client serialization contracts;
- SDK or generated-model checks;
- server boot/wiring assertions;
- removed architecture-shape assertions;
- assertions whose only subject is a retired compatibility surface.

If a mixed module contains both kinds, rescue only the semantic tests and mark
the remaining cases `deprecated_transport` or `obsolete_shape` row by row.

The accepted connector guarantee is frozen as accepted-only evidence at
`513dd97:tests/engine/test_traversal_connectors.py::test_connector_discovery_and_atomic_execution_share_one_typed_variant`.
CR-0 preflight proved that the current checkout cannot re-express that public
discovery-to-execution proof without a production change: ordinary discovery
rejects the current `TraverseConnector` variant because it has no authenticated
authored behavior binding. Record the exact accepted proof, current blocking
diagnostic, passing current direct-variant/veto proofs, and target `CR-2`.
Do not fabricate a test-only binding or change production in CR-0.

### 3.4 CR-0 completion ledger

Create:

`DND_CONTENT_RECOVERY_CR0_COMPLETION_LEDGER_2026-08-30.md`

It records:

- governing plan hashes and Git checkpoints;
- final deliverable hashes;
- exact counts by manifest section and disposition;
- the maintained test-node count and normalized node-list hash;
- exact validation commands and results;
- default-collection diagnostic and its classified failures;
- correctness, anti-slop, and anti-OOP/ECS review metadata;
- any deliberately deferred blockers.

It does not duplicate all manifest rows.

## 4. Manifest row contracts

### 4.1 Authority and source artifacts

`authority` pins the repository HEAD, branch, governing plan, accepted/July/
broken Git objects, and evidence precedence.

`source_artifacts` includes current and accepted versions where present. Each
row contains:

```text
artifact_id, source_tier, git_object_or_path, sha256, row_count, disposition
```

It freezes all seven current artifacts:

| Artifact | Current SHA-256 |
|---|---|
| `content_data/ledgers/srd_5_1_source_coverage.json` | `cb5c78be958636b158c0b9ce2a7005f76d6db6a7e795c609f8829124400879be` |
| `content_data/ledgers/content_icon_bindings.json` | `2129a753a0ad13d5fa472ad9dd9a3b354ae0f73299b753d12ef520ac17736ec8` |
| `content_data/ledgers/neuroclient_authored_item_visuals.json` | `7850493fb83395a363110e0c5e99d9da69a287a7b1f663c4906715af41ce7a4a` |
| `content_data/ledgers/neuroclient_game_icon_asset_index.json` | `da24829f890902b37e79ea4e31fff2893ff184db2fc6eea36877c22081b2ed8f` |
| `content_data/sources/neurodragon_original_b2b3930.json` | `14afc6255cd0353ce0e3005253e9f21eb8b6d52eec8fe3fa943c66f44e2cc7cb` |
| `content_data/sources/neurodragon_original_b2b3930.txt` | `5d5b9fd982162ffeb960166665ac4bf464f260fea7cb8cfe453039366874a2f9` |
| `content_data/sources/srd_5_1_cc.json` | `5a00ce5121a3aaa24cb6f6521b25868ef601925377cf91fccb4f72701dd5e578` |

It also freezes all seven accepted artifact blobs from `513dd97`:

| Accepted path | SHA-256 |
|---|---|
| `deprecated/content_data_deprecated/ledgers/content_icon_bindings.json` | `308d849b8e6e930409a611ace81fe86f819d9b370979882f7d3c0543252c7bbd` |
| `deprecated/content_data_deprecated/ledgers/neuroclient_authored_item_visuals.json` | `267ef479048dfd2fc52d78037e29becbd74d7ccc8939194a94dc44fa49118f08` |
| `deprecated/content_data_deprecated/ledgers/neuroclient_game_icon_asset_index.json` | `1cf4d2620016b27e94591c1a757401e49a1e195fdc9b5b831d3abf84f71a7da4` |
| `deprecated/content_data_deprecated/ledgers/srd_5_1_source_coverage.json` | `64aecb5cb2c253b9b236b1dba437a49986997afa2ce3a110a809b5f31955a18f` |
| `deprecated/content_data_deprecated/sources/neurodragon_original_b2b3930.json` | `198d9284aca94910fc5bd4717e94d1bdd3712f2657341265f8b564ce373a948e` |
| `deprecated/content_data_deprecated/sources/neurodragon_original_b2b3930.txt` | `5d5b9fd982162ffeb960166665ac4bf464f260fea7cb8cfe453039366874a2f9` |
| `deprecated/content_data_deprecated/sources/srd_5_1_cc.json` | `6b49392e563bc274162d9f065f6f8721e905f847bdabe97be880aa96bd462d89` |

Accepted blobs are read with `git show 513dd97:<path>` and hashed as bytes.
They are not copied into the working tree. The evidence proof verifies every
current file and accepted Git blob against the expected hash above.

### 4.2 Unified legacy-authority inventory

`legacy_authorities` is one evidence/disposition array, not a replacement
registry. Its `authority_kind` distinguishes declaration, recipe preset,
materializable root, behavior identity, and structural definition. Expected
source counts are 673 declarations, 205 recipe presets, 191 materializable
roots, 395 behavior identities, and 87 structural definitions; one source row
may participate in more than one derived count, so the unified array is not
required to equal their sum.

Every row records only:

```text
legacy_identity
authority_kind
semantic_id
source_path
source_symbol_or_row
target_cut
disposition
blocker
```

Capabilities, current owners, and proof nodes belong to `implemented_content`
and are not duplicated here.

The stable uniqueness and sort key is
`(authority_kind, legacy_identity, source_path, source_symbol_or_row)`. This
keeps distinct authority roles visible when the same legacy identity/source
participates in more than one derived authority count.

Allowed `disposition` values are intentionally finite:

- `retain_then_migrate`;
- `accepted_only_recover`;
- `current_only_keep`;
- `merge_by_semantic_id`;
- `obsolete_shape_delete_with_owner_cut`;
- `forensic_only_reject`.

`target_cut` is one of `CR-1` through `CR-10`. It does not name a new layer.

Rows are derived in a fresh Python process through the current public bootstrap
and explicit exports. The derivation script is an inline, reviewable command in
the completion ledger; it is not committed as a reusable framework.

### 4.3 Implemented and accepted content inventories

`implemented_content` freezes semantic inventories for:

- origins: species, variants, backgrounds, and origin features;
- classes/subclasses and levels;
- four premade character builds;
- items/environment objects;
- monsters/creature configurations;
- scenarios, deployments, encounters, slots, grants, and setup effects;
- actions, reactions, conditions, spells, traits, feats, and class features.

Each row uses the same semantic ID across current and accepted evidence when the
meaning is the same. It records capability/proofs and one of:

- `current_and_accepted`;
- `current_only_keep`;
- `accepted_only_recover`;
- `conflict_requires_owner_cut`;
- `missing_deferred`.

For `current_and_accepted` and `current_only_keep`, current implemented/partial
claims name full collectible current node IDs. An `accepted_only_recover` row
instead names an exact accepted commit/path/node and a target cut; it is not
required to invent a passing current test for absent behavior. The explicit
maintained node list contains current-checkout nodes only.

The item inventory mechanically re-derives:

- the frozen 127-item baseline;
- accepted direct identities and variants;
- current Oil Barrel content;
- the semantic union and any collision.

The plan's likely 147 total is not accepted by assertion. CR-0 records the
mechanically proven total and the exact set differences.

### 4.4 SRD proof overlay

The immutable 925-row ledger remains the sole full SRD inventory and is pinned
once under `source_artifacts`. `srd_proof_overlay` contains only the 177
implemented and 5 partial rows that require recovery proof, plus a conflict row
only if the audit discovers a status mismatch. Each overlay row contains only
`source_row_identity`, `implemented_content_row_id`, and an optional status
conflict. The referenced implemented-content row remains the sole owner of the
semantic ID, disposition, and proof nodes. The overlay does not copy authored
source payloads or the 743 missing identities.

Required aggregate result:

| Status | Count |
|---|---:|
| implemented/playable | 177 |
| partial | 5 |
| missing/deferred | 743 |
| total | 925 |

The five partial rows remain partial unless their complete mechanics already
exist and are proven independently. CR-0 may improve evidence; it may not fill
mechanics. The architecture proof recomputes aggregate totals from the original
ledger plus the overlay rather than trusting copied totals.

### 4.5 Importer inventory

`production_importers` is derived from tracked Python modules, excluding tests,
server/deprecated-server, SDK, generated, renderer/editor, and caches. It
records every module that:

- imports or references `dnd.content_system`;
- imports or references `dnd.core.content`;
- imports, annotates, or constructs `ContentRef`.

Each importer row records path, import category, owning domain, target CR cut,
and disposition. Initial audit expectations are 133 generic-content importers
and 64 modules mentioning `ContentRef`; CR-0 reports mechanically derived
counts and exact differences rather than forcing those numbers.

### 4.6 Bounded test classification and maintained lane

`excluded_or_rescued_test_modules` classifies only collection-error modules and
mixed modules whose semantic cases require rescue. It uses one of:

- `semantic_case_to_rescue`;
- `deprecated_transport`;
- `obsolete_shape`;
- `blocked_by_later_content_cut`.

Every row names a reason and, for rescued cases, the public capability and new
node. CR-0 does not create a second exhaustive test catalog.

`maintained_in_process_nodes` contains explicit full pytest node IDs. It is
constructed only after all selected files collect successfully. The baseline
command executes precisely that node list, never a directory whose membership
may drift silently. Its normalized hash is SHA-256 of sorted node IDs joined by
newline and terminated by newline.

The default repository diagnostic remains separate. Current preflight is 2,527
collected tests with 81 collection errors. CR-0 records the fresh final
diagnostic and classifications; it does not call that result the maintained
baseline and does not repair it by restoring deprecated dependencies.

### 4.7 Binding reconciliation

`binding_reconciliation` stores aggregate artifact-pair metadata plus normalized
changed/colliding row diffs for the seven current and seven accepted artifacts.
Unchanged rows remain owned by the pinned source artifacts and are not copied
into the manifest. The reconciliation covers:

- 77 authored item-visual categories, 205 variants, and the recorded source-ID
  collision;
- 205 recipe-preset icon bindings;
- 669 current versus 671 accepted icon definition bindings, including exact
  additions/removals rather than a count-only comparison;
- 515 current versus 521 accepted game-icon asset-index rows;
- source-ledger row/key/value differences needed to preserve provenance.

Each artifact-pair metadata row supplies an ordered, deterministic set of
default disposition/target-cut rules for unchanged rows in that pair. Rules may
key only on stable authored row fields such as definition kind, binding domain,
or semantic-ID prefix; they may not call production code or create a general
policy engine. Static item/entity/map presentation resolves to CR-8, while
action/reaction/condition/spell/trait/feat/class-feature/spatial behavior
presentation resolves to CR-9. A pair with one homogeneous domain may use one
unconditional final rule. Each changed/colliding reconciliation row has
artifact pair, stable row identity, current value or absence, accepted value or
absence, exact disposition
(`mechanics`, `renderer_binding`, `source_only`, or `obsolete`), target cut, and
optional conflict. Values remain JSON values rather than Python wrapper types.
The architecture proof expands the pinned current/accepted row union logically
and proves every row resolves to exactly one changed/collision override or the
first matching ordered default rule; overlapping ambiguous rules and unmatched
rows fail. No source/binding row may be left without a disposition and target
cut.

`python_binding_overlay` freezes Python-authored bindings that have no complete
data-ledger equivalent:

- species/variant/background appearance choices;
- all four premade appearance selections;
- bestiary appearance constants and wardrobe keys;
- all 21 configured-SRD mappings;
- SRD icon, variant, and tint choices;
- Tile sprite bindings;
- traversal presentation keys and `gap.png`;
- item/environment presentation literals;
- spatial VFX profiles;
- Field Kit bindings.

Each row records semantic ID, owning domain, exact source path and line/symbol,
normalized authored value, evidence tier, disposition, and target cut. It is an
evidence overlay, not a runtime renderer map. Duplicate identities, unstable
ordering, missing sources, and unclassified current/accepted differences fail
the architecture proof.

## 5. Mandatory semantic anchors

The maintained node list must include:

- `tests/engine/test_action_discovery.py::test_eb_09_003_execute_by_index_instantiates_and_applies_costs`;
- `tests/engine/test_action_discovery.py::test_eb_09_007_action_overrides_change_cost_display_and_consumption`;
- all five nodes in
  `tests/architecture/test_action_discovery_requirements.py`;
- `tests/progression/test_spellcasting_source_action_propagation.py::test_spell_variants_and_executable_clones_preserve_exact_source`.

The accepted connector proof above is a mandatory accepted-only manifest row,
not a current maintained node. The maintained list instead includes the current
passing direct connector variant commit and veto proofs; CR-2 must restore the
accepted ordinary-discovery guarantee.

Additional proof selection follows public capabilities, not convenient module
counts. At minimum it covers:

- direct item construction/placement and Oil Barrel behavior;
- origins, class progression, multiclass add/remove, and all four premades;
- maintained monster creation/configuration and possessions;
- scenario/deployment/encounter chronology and setup effects;
- action/reaction/condition/spell/trait behavior identity and execution;
- the 182 implemented/partial SRD claims.

## 6. Ordered execution

### CR-0.0 — preflight and exact candidate boundary

1. Verify HEAD, working-tree status, governing-plan hash, and Git evidence
   objects.
2. Re-run default `pytest --collect-only -q` as a diagnostic and store the
   normalized error signature.
3. Inventory candidate changed paths. Stop if any required production edit is
   discovered.

Checkpoint: documentation/data/test-only scope is sufficient.

### CR-0.1 — evidence derivation

1. Derive current declaration/preset/root/behavior/structural inventories in a
   fresh process.
2. Extract accepted and July inventories from Git without checking them out.
3. Derive semantic current/accepted set differences for every content family.
4. Join SRD source rows to current/accepted semantic content and proofs.
5. Inventory importers and test classifications.
6. Write the normalized manifest once all rows have dispositions.

Checkpoint: counts, set differences, duplicates, unresolved joins, and blockers
are reviewed before test rescue.

### CR-0.2 — semantic test rescue and maintained node freeze

1. Read every candidate mixed/uncollectible test before editing.
2. Rescue only genuine in-process semantic cases into the matching test domain.
3. Run each rescued case alone, then its owning focused lane.
4. Collect the complete maintained file selection successfully.
5. Freeze the explicit sorted full-node list and hash in the manifest.

Checkpoint: no rescued test imports a forbidden dependency or asserts retired
shape.

### CR-0.3 — evidence proof and certification

1. Add the focused architecture/evidence test.
2. Run the exact maintained node list.
3. Run focused content/item/origin/progression/monster/scenario/behavior/SRD
   lanes named in the manifest.
4. Run architecture, compileall, `git diff --check`, importer/hard-cut scans,
   manifest member/hash verification, and default collection diagnostic.
5. Freeze the completion ledger and exact candidate hashes.
6. Obtain independent correctness, anti-slop, and anti-OOP/ECS/import-DAG
   reviews of the same candidate bytes.

Any substantive manifest/test repair invalidates affected validation and all
three final reviews.

## 7. Validation commands

Before executing tests, follow `HOW_TO_TEST.MD`. The final ledger records exact
commands, but the required gates are:

```bash
.venv/bin/pytest --collect-only -q
.venv/bin/pytest <explicit maintained full node IDs>
.venv/bin/pytest tests/architecture -q
.venv/bin/python -m compileall -q dnd tests
git diff --check
```

Additional focused lanes are taken from manifest proof nodes, not broad default
directories with known deprecated collection failures.

The evidence test must also run in a fresh process and prove manifest hashes,
counts, ordering, unique identities, importer closure, SRD totals, and
collectibility of every claimed proof.

## 8. Review questions

### Correctness/completeness reviewer

- Does every governing CR-0 requirement have one deliverable and gate?
- Can every current implemented/partial claim be traced from authored source
  through semantic ID to a collectible current public proof, and every
  accepted-only row to an exact accepted Git proof plus target cut?
- Are current, accepted, July, and forensic evidence conflicts explicit?
- Is the maintained baseline exact and reproducible despite default collection
  failures?

### Anti-slop reviewer

- Is any committed helper or schema becoming a hidden generic content system?
- Can any field, artifact, duplicate inventory, or validation layer be removed
  without losing auditability?
- Do rescued tests prove behavior rather than implementation shape?
- Does CR-0 avoid work belonging to CR-1 or later?

### Anti-OOP/ECS/import-DAG reviewer

- Does the candidate leave entities as data/system composers and avoid new
  owners, managers, callback chains, or service objects?
- Is the evidence manifest entirely outside runtime dependency flow?
- Are there no late imports, cycles, reflection cheats, or production imports
  of audit data?
- Does each future disposition point to the existing owning content/system
  family instead of a new cross-domain layer?

## 9. Completion gate

CR-0 is complete only when all are true:

1. every one of the 673 current declarations has an explicit disposition;
2. every retained/partial content row and every current old importer has one
   owner-aligned disposition;
3. current and accepted evidence hashes and row-level differences are frozen;
4. the 925 SRD source rows remain hash-exact, with 177 implemented, 5 partial,
   and 743 missing/deferred;
5. the item baseline/accepted/current semantic union is mechanically proven;
6. every current implemented/partial row names a collectible current public
   proof, while every accepted-only row names an exact accepted Git proof and
   target cut;
7. the explicit maintained in-process node list collects and passes exactly;
8. rescued semantic tests contain no deprecated infrastructure or obsolete
   architecture assertions;
9. architecture, compileall, diff-check, importer/hard-cut, and evidence gates
   pass;
10. correctness, anti-slop, and anti-OOP/ECS/import-DAG reviewers approve the
    exact final candidate;
11. no production behavior changed and CR-1 was not started.

Completion of CR-0 authorizes planning CR-1. It does not authorize CR-1
implementation by itself.

## 10. Independent plan acceptance

The preflight plan was accepted after all requested corrections by:

- correctness/completeness reviewer `/root/historical_content_audit`;
- anti-slop reviewer `/root/e3e6_antislop_review`;
- anti-OOP/ECS/import-DAG reviewer `/root/current_content_audit`.

Execution then discovered the connector infeasibility documented in sections
3.3 and 5. All three reviewers accepted that substantive amendment. The final
accepted SHA-256 is recorded by the coordinator after this metadata-only status
update is frozen.
