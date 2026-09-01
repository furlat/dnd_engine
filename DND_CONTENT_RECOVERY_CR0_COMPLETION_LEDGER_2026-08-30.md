# Content Recovery CR-0 Completion Ledger — 2026-08-30

Status: `CR-0 COMPLETE — TRIPLE-REVIEWED AND ACCEPTED`

## 1. Scope and authority

CR-0 froze the content-recovery evidence boundary. It did not migrate content,
change production behavior, restore deprecated transport, or begin CR-1.

- repository branch: `codex/july-reconstruction`
- repository HEAD at preflight: `205fd679fde51d5319d332f12ec241d7aecd93a6`
- accepted checkpoint: `513dd97`
- July reference: `4ebe523`
- broken-branch forensics: `1f2e525`
- governing plan:
  `DND_JULY_RECONSTRUCTION_CONTENT_RECOVERY_AUDIT_AND_MIGRATION_PLAN_2026-08-30.md`
  (`3e6a38a534331f0cdf92127fe5d9b765bf7e81a7d44baee08876bfd1613bec7b`)
- CR-0 implementation plan:
  `DND_CONTENT_RECOVERY_CR0_EVIDENCE_FREEZE_IMPLEMENTATION_PLAN_2026-08-30.md`
  (`55de34336d2e171fb158db5694cd2aed036c16719dbc0a3b10c920ef0b9b8fa5`)

No file under `dnd/` changed. The candidate adds one data-only evidence manifest,
one architecture/evidence test, three focused semantic test modules, and this
ledger; it strengthens one existing progression test through ordinary in-process
game composition and deployment.

## 2. Frozen deliverables

| Deliverable | SHA-256 |
| --- | --- |
| `content_data/ledgers/content_recovery_cr0_evidence.json` | `fdcd5c32b7ded90bb52e94fbb492181416b735eaddc4a3e0956540b613dbaa65` |
| `tests/architecture/test_content_recovery_cr0_evidence.py` | `087571cdda3b8ec5adee13787bb93daa352e2373dcdb45da7c42a46919ebbb70` |
| `tests/engine/test_content_recovery_behavior_semantics.py` | `a7275fcb8bd0c897eb6e7513f79dccb381952140f09ea5c2b3fb167e53b34c9a` |
| `tests/engine/test_content_recovery_item_semantics.py` | `2fa4ad865a8a792cef6f0ed973d82f2f2cbc24b45348893ed633a4786f3674c5` |
| `tests/progression/test_content_recovery_character_semantics.py` | `0bd09985c058039f4c007325aa3761d67b66f9196a6379e4c7ac20acb2f0c79c` |
| `tests/progression/test_sorcerer_spell_source_materialization.py` | `2c9d97457d6c743fafb3432bdb540c74240ad2b36feae27dde71454c99db3665` |

The evidence manifest is normalized, sorted JSON with a terminating newline.
It is not imported by production. There is no committed generator, loader,
schema class, policy engine, manager, compatibility facade, or runtime registry.

## 3. Evidence inventory

### Authority and content

- source artifacts: 14, all current/accepted bytes hash-exact
- legacy authorities: 1,551
  - declarations: 673
  - behavior identities: 395
  - materializable roots: 191
  - structural definitions: 87
  - recipe presets: 205
- implemented-content rows: 1,014
  - current and accepted: 972
  - current only: 11
  - accepted-only recovery: 30
  - explicit owner-cut conflict: 1
- production/tooling importer rows: 238
- Python-authored presentation bindings: 788
- binding artifact pairs: 8
- changed/collision binding rows: 121

### SRD and direct items

- immutable SRD source rows: 925
  - playable: 177
  - partial: 5
  - missing/deferred: 743
- SRD proof-overlay rows: 182
- current direct item/environment identities: 128
- frozen current baseline: 127
- accepted direct identities: 146
- current/accepted raw union: 149
- reconciled public identities: 147
- explicit collision merge: `environment.door` to
  `environment.directional_door`

### Default collection classification

The 81 collection-error modules are an exact partition of the fresh default
diagnostic:

- semantic cases rescued: 26
- deprecated transport: 23
- obsolete shape: 17
- blocked by a later content cut: 15

The manifest path set exactly equals the diagnostic error-module path set.

## 4. Semantic proof rescue

The focused tests preserve public in-process behavior rather than old bootstrap
or server shapes:

- Parry, Divine Smite, and Counterspell identity/resource semantics;
- the current spell-catalog composition boundary;
- active weapon stance, Club and armor mechanics, all 205 recipe presets, and
  current spell-item declaration/recipe ownership;
- appearance vocabulary, apparel, equipment packages, and all four premade
  character holdings;
- the strongest learned Counterspell source through a composed and deployed
  in-process game.

The Counterspell accepted pre-cost declaration-veto guarantee is recorded as an
explicit CR-2 conflict. Current code spends its committed resources before an
external veto boundary; CR-0 did not invent a replacement event path.

The accepted ordinary connector discovery-to-execution proof is recorded as
accepted-only evidence targeting CR-2. Current direct variant commit and veto
proofs remain green; CR-0 did not fabricate a behavior binding.

## 5. Frozen maintained lane

- exact sorted unique node count: 105
- normalized node-list SHA-256:
  `f689e92102b7a6e25c832cdc030d88618ab2048cd174e87869d76ed59cdcab33`
- exact execution: `105 passed in 73.86s`

The lane includes five CR-0 architecture nodes as row-level ownership or
reconciliation evidence. The 100 semantic maintained nodes prove execution.
The other six evidence-test nodes run through the focused and architecture
gates but are not described as gameplay proof.

## 6. Validation record

| Gate | Result |
| --- | --- |
| New evidence architecture file | `11 passed in 34.49s` |
| Exact maintained node list | `105 passed in 73.86s` |
| Exact CR-0.2 lane, before architecture nodes | `100 passed in 62.57s`; independent rerun `100 passed in 62.79s` |
| Active in-process architecture lane | `65 passed, 3 deselected in 74.73s` |
| Python compile | `.venv/bin/python -m compileall -q dnd tests`, exit 0 |
| Diff whitespace | `git diff --check`, clean except the existing LF/CRLF normalization notice |
| Production CR-0 manifest imports | zero |
| Production changes under `dnd/` | zero |
| Manifest members and source hashes | exact through the 11 evidence gates |
| Default repository collection diagnostic | `2554 tests collected, 81 errors in 26.72s` |
| Default error-module normalized SHA-256 | `0e99cb9302ba6553c65215e7f125e0d0791a0ce8d40929b9166c808151afcb90` |

The full owning-file diagnostic was deliberately broader than the frozen lane:
`467 passed, 4 failed in 224.99s`. The four failures are not candidate
regressions:

- one known Sleet Storm relighting behavior conflict belongs to later spell
  mechanics recovery;
- three tests assert retired `*_RECIPES_BY_LEGACY_ID` compatibility maps; the
  current public declaration/recipe proofs are green.

The unscoped full architecture diagnostic is
`65 passed, 3 failed in 112.75s`. All three
failures enter deprecated server/transport code and fail on the already removed
`dnd.core.senses` transport dependency. They were deselected only for the
active in-process architecture gate; no server compatibility shim was restored.

### Exact reproduction commands

```bash
.venv/bin/pytest -q tests/architecture/test_content_recovery_cr0_evidence.py
.venv/bin/python -c 'import json,subprocess,sys; from pathlib import Path; nodes=json.loads(Path("content_data/ledgers/content_recovery_cr0_evidence.json").read_text())["maintained_in_process_nodes"]; raise SystemExit(subprocess.call([sys.executable,"-m","pytest","-q",*nodes]))'
.venv/bin/pytest -q tests/architecture --deselect tests/architecture/test_dependency_boundaries.py::test_event_server_import_does_not_load_client_facing_ai_package --deselect tests/architecture/test_dependency_boundaries.py::test_world_contracts_are_a_cold_transport_leaf --deselect tests/architecture/test_spell_catalog_composition.py::test_content_bootstrap_and_composed_spell_catalog_cold_start
.venv/bin/pytest -q tests/architecture
.venv/bin/python -c 'import json,subprocess,sys; from pathlib import Path; nodes=json.loads(Path("content_data/ledgers/content_recovery_cr0_evidence.json").read_text())["maintained_in_process_nodes"]; paths=sorted({node.split("::",1)[0] for node in nodes}); raise SystemExit(subprocess.call([sys.executable,"-m","pytest","-q",*paths]))'
.venv/bin/python -c 'import hashlib,json,subprocess,sys; from pathlib import Path; p=subprocess.run([sys.executable,"-m","pytest","--collect-only","-q"],capture_output=True,text=True); output=p.stdout+"\n"+p.stderr; paths=sorted({line.removeprefix("ERROR ") for line in output.splitlines() if line.startswith("ERROR ")}); expected=sorted(row["path"] for row in json.loads(Path("content_data/ledgers/content_recovery_cr0_evidence.json").read_text())["excluded_or_rescued_test_modules"]); print(next(line for line in reversed(output.splitlines()) if "tests collected" in line)); print(f"error_paths={len(paths)} exact_manifest_match={paths == expected} sha256={hashlib.sha256((chr(10).join(paths)+chr(10)).encode()).hexdigest()}"); raise SystemExit(0 if p.returncode == 2 and paths == expected else 1)'
.venv/bin/python -m compileall -q dnd tests
git diff --check
rg -n "inspect|sys\.modules|\bvars\(|\bgetattr\(|TYPE_CHECKING|importlib" tests/architecture/test_content_recovery_cr0_evidence.py
rg -n "content_recovery_cr0_evidence|test_content_recovery_cr0_evidence" dnd ai server --glob '*.py'
git diff --name-only -- dnd
```

The two `rg` commands deliberately return no matches; the production-diff
command returns no paths. The importer inventory gate derives all 235 active
`dnd/` rows and all three scoped `ai/`/`devtools/` rows from tracked Python.
The binding gate derives all 788 authored overlay values and source locators
from explicit exports and static current/accepted source, with no runtime
registry lookup or reflection.

The owner gates independently derive the exact identity-to-owner relation from
source syntax for all 395 behavior identities, 191 materializable roots, and
87 structural definitions. They resolve declaration tables, decorators,
factory construction helpers, imported concrete definitions, and authored
collection membership; the manifest is compared to that derived relation, so
substituting another valid same-file owner fails.

## 7. Review record

### Plan acceptance

The implementation plan and the connector amendment were accepted before
implementation by:

- correctness/completeness: `/root/historical_content_audit`;
- anti-slop: `/root/e3e6_antislop_review`;
- anti-OOP/ECS/import-DAG: `/root/current_content_audit`.

### CR-0.2 exact-candidate acceptance

All three reviewers approved manifest SHA
`252cb03d2293111a92812b889039ac28888ac49b91dff126f61f1f752a4e45f9`,
the exact 100-node list, and normalized node SHA
`41d9fe154522898797ad36dc96518c0fdcafdcee04e6f4266dd60afa85904965`.

### Final CR-0 exact-candidate review

- reviewed candidate manifest SHA-256:
  `fdcd5c32b7ded90bb52e94fbb492181416b735eaddc4a3e0956540b613dbaa65`
- reviewed candidate evidence-test SHA-256:
  `087571cdda3b8ec5adee13787bb93daa352e2373dcdb45da7c42a46919ebbb70`
- reviewed candidate ledger SHA-256 before this metadata-only acceptance record:
  `3ce474514137b2b11b90a81dda15756dec0a7cefb226b8cc664c2bccacae4a1a`
- correctness/completeness: approved by `/root/historical_content_audit`;
  independently rejected valid same-file owner substitutions for behavior,
  generated-factory, and structural-collection authorities; reran the evidence
  gate (`11 passed`) and exact maintained lane (`105 passed`)
- anti-slop: approved by `/root/e3e6_antislop_review`; confirmed the static
  proof is necessary audit code rather than a runtime framework or duplicate
  content system; independently reran the evidence gate (`11 passed`)
- anti-OOP/ECS/import-DAG: approved by `/root/current_content_audit`; confirmed
  no runtime introspection, alternate registry, service layer, late import,
  circular dependency, or ECS ownership change; independently reran the
  evidence gate (`11 passed`)

Any substantive manifest or test repair after the final candidate is submitted
invalidates all three final approvals and the affected validation.

## 8. Deferred work

CR-0 authorizes planning CR-1; it does not authorize CR-1 implementation.
Deferred evidence remains explicit in the manifest, including:

- accepted-only direct items and content;
- the ordinary connector binding and Counterspell declaration boundary in CR-2;
- Sleet Storm and other later spell-family recovery;
- the retained specialized-skeleton arena, Eldritch Blast, and acid-flask
  characterization debt in the later creature/content cuts;
- presentation/binding recovery in CR-8 and CR-9;
- deprecated server, SDK, generated, and generic-runtime removal in CR-10.
