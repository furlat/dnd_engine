# Gameplay Regression Work Packet 014 — Unarmed Attack Exact Icon Binding

Date: 2026-08-11
Owner: Planner / External Reviewer 1
Implementation owner: Implementation only after public Gate A 4/4 and Coordinator release
Execution owner: Tester only after changed-surface static 4/4 and Coordinator release

## 0. Decision and boundary

WP-013's one governed same-policy attempt causally vindicated the exact
state-only scene-appearance settlement correction but remained non-green. All
eight WP-012 chronology checkpoints reported backend/frontend parity
`pass/pass`, zero frontend mismatches, null mismatch signatures, and no
recurrence of either accepted equip/unequip lag-one appearance fault. The
unchanged console gate instead recorded three new icon control-plane failures
and exited 1.

The authorized read-only follow-up proves that those three reports are one
closed causal cascade:

1. after the maintained smoke lawfully unequips `weapon_melee_main`, the
   backend exposes the provider-less/unarmed `core.rules` `action.attack`
   affordance with `source_item_uuid = null`;
2. the exact built-in content ledger intentionally gives `action.attack` a
   null definition icon because weapon-backed Attack rows normally resolve
   through their exact source item;
3. the action-bar resolver therefore records one missing exact binding and
   selects `action.unavailable`;
4. the promised `action.unavailable` sentinel asset is absent, so the shared
   texture loader records the load failure and the action bar records the
   downstream rejection.

The failed ContentRef is exact, current, and present in the generated backend
ledger. It is not a stale digest or missing catalog entry. The reviewed icon
manifest contains 27 weapon-backed Attack variants but no provider-less Attack
variant. The backend test authority currently proves only equipped Attack
providers and explicitly expects the definition icon to be null. The lawful
unarmed state is the missing boundary.

This packet closes only that exact boundary. It promotes the existing reviewed
`ui.filter-attacks` crossed-swords asset to the exact definition fallback for:

`core.rules:action:action.attack@1#b348fe0a75aa991c675bf8a82df5884e50463d9a5181b6c224f631857506a8b0`

Weapon-backed Attack rows remain source-item-first in the frozen frontend
resolver. Only a provider-less/unarmed Attack reaches the new exact definition
binding. No name, display text, weapon slot, template string, or runtime
fallback inference is added.

The correction is confined to five existing backend-owned files:

- `devtools/import_neuroclient_content_icon_bindings.py`;
- `content_data/ledgers/content_icon_bindings.json`;
- `dnd/core/content/icon_bindings_generated.py`;
- `tests/manual/test_181_affordance_content_identity.py`;
- `tests/manual/test_183_content_icon_bindings.py`.

All NeuroClient production, its 528-asset current manifest, its asset files,
the pinned backend 521-asset index, WP-013 production, and the same-policy live
smoke remain byte-frozen.

### 0.1 Human authorization and automatic progression

The human authorized the owner-correct production path and standing automatic
progression for this identified blocker family. The read-only study has
selected a bounded existing content-binding owner. No architecture, public
contract, schema, persistence, dependency, framework, or mutually exclusive
product behavior decision is implicated.

### 0.2 Accepted natural red

The consumed WP-013 receipt is the natural runtime red for this packet. It used
the exact unchanged smoke that will be used for green and produced:

- one focused TypeScript pass and one checker pass;
- one direct no-force backend, one Vite, and one registered smoke;
- smoke exit 1 without timeout;
- one final JSON of 297,487 bytes / SHA-256
  `b15b177a9ac63684a7c628b4a13f96befe66dc65c3be4ebec4d8b336cfab1046`;
- zero render-parity faults or mismatches at every chronology checkpoint;
- all inherited fixture, readiness, Jump, Move, equipment, reset,
  objective-debug, bootstrap-two, and terminal-parity receipts complete;
- exactly the three icon faults described above;
- complete owned teardown.

No new red execution is authorized or necessary.

### 0.3 Strict claim

Successful Gate B may establish only:

> The exact built-in `core.rules` Attack definition owns the reviewed generic
> Attack icon when a lawful affordance has no source-item provider, while
> weapon-backed Attack affordances retain their exact source-item icon
> precedence. The three WP-013 icon-fault cascade reports no longer occur in
> the maintained live-subjective smoke.

It does not claim all icon bindings, every unavailable sentinel, general
equipment behavior, all actions, general action-bar correctness, general
asset loading, WP-013 technical acceptance before final review, or broader
BUG-031 closure.

## 1. Frozen authorities

All identities are exact. Any mismatch fails intake closed. No automatic
refresh, regeneration, or baseline substitution is allowed.

### 1.1 Accepted predecessor and evidence identities

| Authority | Lines | SHA-256 |
|---|---:|---|
| `agent_working_folder_NOT_HUMAN_GUIDANCE/plans/GAMEPLAY_REGRESSION_WORK_PACKET_013_STATE_ONLY_SCENE_APPEARANCE_SETTLEMENT_2026-08-11.md` | 539 | `b1a8a30f527c31ac09ba2f54d0059182194b66c3590cfc197df0f1764d45f511` |
| `/tmp/neurodragon-wp013-green-DHx49P/live-subjective-actions-smoke.stdout` | 5 | `0839e91801573911e5ebd93231df8b5c8994e9ffe4d185f83b52816b1896b616` |
| `/tmp/neurodragon-wp013-green-DHx49P/live-subjective-actions-smoke.stderr` | 9 | `2e4a6ccb541ee7053d390999fb24a73ee886d51ee33ad430bdba2422358525fe` |

The retained root and every earlier retained root are frozen evidence, never
mutable packet state.

### 1.2 Mutable binding and focused-test owners

| File | Lines | SHA-256 |
|---|---:|---|
| `devtools/import_neuroclient_content_icon_bindings.py` | 1731 | `4fadd62fc34585f474bd033495e3dbab0c8bb131cf3e99b1481d0d4df6a3c1ee` |
| `content_data/ledgers/content_icon_bindings.json` | 13714 | `2de8296b9808090ca2ad17e4468f212b711470ada979f6afbbb5aacc6dafd9c6` |
| `dnd/core/content/icon_bindings_generated.py` | 2699 | `5f5deff83628e18830cfa9eef3ead0113eeff16988ce457a63038ac98fae134c` |
| `tests/manual/test_181_affordance_content_identity.py` | 628 | `2e9837e353ee89dd124f898d2278df07eb0c5a6900adfe1e04146e315442bd94` |
| `tests/manual/test_183_content_icon_bindings.py` | 492 | `eaa2ea03af04c623811e4fbe358dc95dcd38749f49c9fbb06bb7fe0a93fabfc2` |

Only these five files may change after Gate A. The ledger and generated Python
are exact mirrors of the source decision; they are not independent design
owners.

### 1.3 Frozen backend content owners

| File | Lines | SHA-256 |
|---|---:|---|
| `content_data/ledgers/neuroclient_game_icon_asset_index.json` | 2617 | `1cf4d2620016b27e94591c1a757401e49a1e195fdc9b5b831d3abf84f71a7da4` |
| `dnd/core/content/descriptors.py` | 171 | `31f0ad8925fe53affd6ee0a3016e93e61a811f87a5b15ef3693721e864dbf1f4` |
| `dnd/content_system/icon_bindings.py` | 432 | `9be2c59267ad5b5a3b3a530287ee580ed9c58e8c9d735a8a2d4bfdf09d41544b` |
| `server/content_catalog.py` | 581 | `bcfdb9c17ab12694488c1532d18cf0f9608665ec8074ad0e4a9e628a32b59058` |

The asset index already contains `ui.filter-attacks` at SHA-256
`00b85f45f2ecb784e0fb1c79b00a01fee95bbc537fe1689260d29ac862f61bbc`.
It must remain byte-identical.

### 1.4 Frozen NeuroClient binding and catalog owners

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/src/ui/gameIconResolver.ts` | 228 | `939a61c7365bdbb9e5491cce34558abc017ef5f812721d2a6c8363186e6310d9` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/actionBar.ts` | 2429 | `0f741a9a0abcf69ff9d62ad2685ba052531d0b4ba842edcc5c72693c60a8f52e` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/actionBarModel.ts` | 441 | `939cca7b1d25a33961e884da4cb1c855fa0127d0eff9131845fc6393d642779f` |
| `/home/tommaso/Dev/NeuroClient/app/src/render/contentPresentationCatalog.ts` | 542 | `544b260908ea5bc1ebce9aa667a1f4f23b3fcfeb4d5ab1af81fe8d19ba0f6e93` |
| `/home/tommaso/Dev/NeuroClient/app/src/render/contentPresentationCatalogRepository.ts` | 143 | `af85d62b0e6615c6bc154d0a288d79d8c0280f3da6a4e2f55bb05ae4feefbee2` |
| `/home/tommaso/Dev/NeuroClient/app/src/render/gameIconCatalogDiagnostics.ts` | 300 | `d81642f27f675006d51cc402a2f7f9c86caa1c913f5818ab0ae2a3c4ffbd0c0e` |
| `/home/tommaso/Dev/NeuroClient/app/src/render/data/animation/contentActionPresentationRecipes.json` | 5478 | `8131f9215664ac5aa2dc072d2f184c426610123a5a96446df71723c3d49c8460` |
| `/home/tommaso/Dev/NeuroClient/app/public/game-icons/fantasy-classic-v1/manifest.json` | 46947 | `78891a850da2e1f0c908458b1e6dc7e2f93722f829790d2a518d3d1891b9e613` |

The current manifest contains the same `ui.filter-attacks` asset digest as the
pinned backend asset index. No manifest row, `used_by`, image, PNG master,
WebP, atlas, or icon-generation authority may change.

### 1.5 Frozen WP-013 production and execution owners

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/src/engine/stateSync.ts` | 618 | `d015d1c29e490c809faab1dd4f425f20dfbfc34433c36cff34dff731b8e5877a` |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/eventIngestion.ts` | 947 | `594f0776f9063aefff5bb737d0beb7463e014d1d978c08810b4254d7c853375a` |
| `/home/tommaso/Dev/NeuroClient/app/scripts/live-subjective-actions-smoke.mjs` | 780 | `c04a200674d41e4b2711cfabc4a9870f93421a59d84380aac37fbaf72bb69fa4` |
| `/home/tommaso/Dev/NeuroClient/app/scripts/check-node-sources.mjs` | 100 | `d46c4d12a5d23f4a2a496bafc544a7a8b7ac499e89c4496a00e564b88689c3d1` |
| `/home/tommaso/Dev/NeuroClient/app/package.json` | 165 | `36515d20ea94ebc0c49a47b79bd455fee0eddceea2eb5e52713163eff159d9e3` |
| `/home/tommaso/Dev/NeuroClient/app/vite.config.ts` | 235 | `7d70b9fae8cf5d4a8d38762865ac8f36adba1247721212fcb5b3d7455f247153` |
| `server/event_server.py` | 6978 | `eb1f6e891bc4cb149c8f054bb8ae36e4df7f2a7a7d47e6cc91af2a3e7394cdc5` |

No WP-013, Tester, package, Vite, service, or browser authority may change.

## 2. Frozen causal proof

### 2.1 Exact first fault

The first fault id is:

`2026-08-11T01:29:05.251Z:control_plane_failure:164`

It reports the exact five-field ContentRef for `core.rules` `action.attack`.
Its stack is:

`reportMissingIconBinding -> definitionIconKey -> actionIconKey ->
actionIconUrl -> PixiActionBar.iconUrls -> ensureIconsPreloaded ->
syncFromStore`.

Its runtime identifies `surface=game_icon_resolver`,
`binding_kind=content_ref`, and
`fallback_policy=visible_unavailable_sentinel`.

### 2.2 Exact downstream reports

The second and third faults share the later timestamp and URL:

`/game-icons/fantasy-classic-v1/icons/action.unavailable.webp`

The loader exhausts exactly two attempts and records the asset failure. The
action bar then records rejection of that same required icon. The file and
manifest row are absent. These reports are downstream of the exact missing
binding; they are not independent equipment or WP-013 scene faults.

### 2.3 Intentional dynamic-provider gap

The existing binding ledger row for the failed exact identity is:

- `decision = intentional_null`;
- `evidence_kind = intentional_dynamic_provider`;
- `icon_key = null`;
- `asset_sha256 = null`.

The importer owns that decision through
`_INTENTIONAL_DYNAMIC_PROVIDER_IDENTITIES`.

The reviewed manifest's Attack rows all resolve through a weapon item icon.
The backend affordance test proves equipped rows carry the exact weapon UUID
and the frontend resolver prefers the matching equipment item. After the
smoke's lawful unequip, the provider-less row carries no source item, so the
definition binding is the only canonical presentation owner available.

### 2.4 Existing exact asset

`ui.filter-attacks` is an existing reviewed crossed-swords generic Attack
emblem. Both the pinned backend asset index and current client manifest bind it
to the exact asset SHA-256
`00b85f45f2ecb784e0fb1c79b00a01fee95bbc537fe1689260d29ac862f61bbc`.

Reusing it requires no bitmap generation, manifest repin, asset-index update,
or visual design choice. Its semantic meaning is generic Attack, while weapon
specificity continues to come from the source-item-first resolver.

## 3. Required correction

### 3.1 Import decision

In `devtools/import_neuroclient_content_icon_bindings.py`:

1. add exactly one `_HUMAN_REVIEWED_BINDINGS` entry from
   `core.rules:action:action.attack@1` to `ui.filter-attacks`;
2. remove that exact identity from
   `_INTENTIONAL_DYNAMIC_PROVIDER_IDENTITIES`;
3. preserve every other reviewed binding, inherited-provider rule, evidence
   mapping, manifest identity pin, asset-index behavior, validation, output
   path, and CLI behavior.

No other identity may be promoted, repinned, inferred, or normalized.

### 3.2 Authenticated ledger row

Change exactly the existing `action.attack` definition row in
`content_data/ledgers/content_icon_bindings.json` to:

- `decision = "bind"`;
- `icon_key = "ui.filter-attacks"`;
- `asset_sha256 =
  "00b85f45f2ecb784e0fb1c79b00a01fee95bbc537fe1689260d29ac862f61bbc"`;
- `evidence_kind = "human_reviewed"`;
- `evidence_token =
  "reviewed_content_ref_to_manifest_asset:core.rules:action:action.attack@1->ui.filter-attacks"`.

Preserve the exact ContentRef and every other definition and preset row.
Recompute only the top-level canonical `binding_digest`. The precomputed exact
post-change digest is:

`f7d1642da1b9af7426a589a0457adff36471fc065a82880e3cce6bb8068326ee`

The source-manifest identity, asset-index digest, schema version, ordering,
format, and all unrelated values remain byte-preserved.

### 3.3 Generated runtime mirror

In `dnd/core/content/icon_bindings_generated.py`, change only the two values in
the existing exact `action.attack` row from `(None, None)` to:

`('ui.filter-attacks',
'00b85f45f2ecb784e0fb1c79b00a01fee95bbc537fe1689260d29ac862f61bbc')`.

Preserve its key, ordering, header, type, and every other generated row.

### 3.4 Focused tests

In `tests/manual/test_181_affordance_content_identity.py`:

1. update only the existing Attack affordance test so the public catalog must
   expose `ui.filter-attacks` for the exact definition;
2. retain the proof that every equipped Attack row carries its exact weapon
   `source_item_uuid` and is not item use;
3. do not weaken any authored behavior, reaction, handler, or content identity
   assertion.

In `tests/manual/test_183_content_icon_bindings.py`, add one focused importer
normalization assertion that starts from an intentional-null copy of the exact
Attack row, runs the existing in-memory `_definition_rows_from_existing`
owner, and requires the reviewed `ui.filter-attacks` binding, exact asset
digest, `bind` decision, and `human_reviewed` evidence. Preserve every existing
closure, tamper, inheritance, runtime-selection, and external-pack assertion.

No broad snapshot or hard-coded success flag may replace those owner checks.

### 3.5 Frozen runtime precedence

The frontend resolver remains unchanged:

1. exact source item first;
2. exact source floor object second;
3. exact definition icon third.

Therefore armed Attack remains item-specific and provider-less Attack uses the
new exact definition icon. No `content_id` special case, display-name lookup,
weapon-name parsing, slot inference, fallback asset substitution, or local
parallel icon table is authorized.

## 4. Explicitly deferred adjacent backlog

The read-only study also found that the literals `action.unavailable`,
`item.unavailable`, `object.unavailable`, `reaction.unavailable`, and
`condition.unavailable` have no reviewed manifest assets. That is a broader
sentinel-family coverage issue.

This packet does not add, generate, alias, filter, or claim those sentinels.
The exact WP-013 cascade becomes unreachable because its lawful Attack row is
correctly bound, not because an unavailable error is hidden. Any genuinely
missing future binding must still record its first control-plane fault and
fail the unchanged smoke gate.

The sentinel family remains explicit backlog for a separately bounded asset
coverage packet. It cannot expand WP-014.

## 5. Prohibited alternatives

- no frontend resolver or action-bar edit;
- no `content_id`, template-name, display-name, weapon-name, or slot special
  case;
- no new bitmap, reused hidden alias, manifest row, `used_by` mutation, atlas,
  PNG, WebP, or image-generation action;
- no repin from 521 to 528 assets and no asset-index refresh;
- no unavailable-sentinel creation or catalog-wide cleanup;
- no console filtering, fault suppression, clear, acknowledgement, recovery,
  or later-success override;
- no action/equipment behavior, API, SDK, schema, protocol, serialization,
  persistence, package, dependency, or service change;
- no WP-013 production or smoke edit;
- no retry before the frozen changed surface receives public static 4/4;
- no unrelated refactor, formatting, cleanup, or generated drift.

## 6. Authorized implementation phase

After Gate A reaches public 4/4 plus Coordinator verification, Implementation
may edit only the five files in Section 1.2 and only the exact Sections
3.1-3.4 surface.

Because the current NeuroClient manifest is intentionally newer than the
backend's frozen 521-asset provenance pin, the broad importer CLI must not be
run in this packet. Implementation must make the exact deterministic ledger
and generated-mirror edits specified above. The selected asset already exists
in the frozen pinned index; no generated inventory refresh is required.

Implementation runs no project command. It may use only read-only diff, line
count, SHA-256, canonical-digest verification, and whitespace checks. It
returns:

- exact current-vs-frozen diffs for all five files;
- final line counts and SHA-256 identities;
- proof the ledger digest is exactly the Section 3.2 value;
- proof the generated row and ledger row are identical;
- proof all frozen authorities remain unchanged;
- scoped diff-check evidence.

Tester remains HOLD during implementation.

## 7. Changed-surface static review

The frozen changed identities require fresh isolated R1-R4 review. Reviewers
must prove:

1. only the five authorized files changed;
2. exactly one ContentRef disposition changed;
3. the asset key and digest already exist in the frozen pinned index;
4. the importer source, ledger, generated mirror, and tests agree exactly;
5. the ledger canonical digest is correct;
6. armed source-item precedence remains frozen;
7. provider-less Attack obtains the catalog definition icon;
8. no manifest, bitmap, sentinel, frontend, equipment, SDK, or contract surface
   changed;
9. the accepted WP-013 scene correction and same-policy smoke remain frozen;
10. execution remains causal and bounded.

No execution is released before public static 4/4 plus Coordinator
verification.

## 8. Governed same-policy green

### 8.1 Focused backend prerequisites

From dnd_engine root, exactly once and stopping on nonzero:

1. `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider tests/manual/test_181_affordance_content_identity.py tests/manual/test_183_content_icon_bindings.py`;

The focused `test_183` authority already validates the frozen CLI/import
boundary through its existing `--help` subprocess. It must not receive a
manifest or write an output. No full Python collection is authorized; the
known stale relocation collection blocker is unrelated.

### 8.2 Frozen NeuroClient prerequisites

Only if Section 8.1 is green, from NeuroClient root exactly once each:

1. `./app/node_modules/.bin/tsc --noEmit -p ./app/tsconfig.json`;
2. `npm --prefix app run node-sources:check`.

No aggregate or alternate command is authorized.

### 8.3 Fresh owned stack

Only after every prerequisite exits zero:

1. prove ports 8000/5173 and matching packet processes absent;
2. create one brand-new disposable `/tmp` runtime root;
3. from dnd_engine root start exactly one owned backend without `--force`:

   `DND_LOCAL_PROFILE_RUNTIME_ROOT=<brand-new> ./.venv/bin/python -m server.event_server --host 127.0.0.1 --port 8000`

4. require direct `/server/capabilities` HTTP 200 with
   `server_mode=standalone` within 90 seconds;
5. start exactly one owned registered Vite and require exact-root HTTP 200 in a
   bounded window;
6. run `npm --prefix app run live-subjective-actions:smoke` exactly once as one
   recorded owned process session under an exact 300-second outer wall clock.

A preflight/start race must freeze on ordinary bind failure. The direct launch
omits `--force` and may never signal an unrelated listener.

### 8.4 Required green evidence

The smoke must exit zero without timeout and emit exactly one final JSON. It
must retain all accepted WP-011/WP-012/WP-013 actual and inherited receipts:

- real fresh-character creation and exact selected identity;
- resolved subjective readiness with equal non-null active/actions UUIDs;
- completed Jump and Move receipts;
- actual equip and unequip of the selected main-hand slot;
- same-generation reset and bootstrap count two;
- objective-debug isolation;
- terminal backend/frontend parity `pass/pass`;
- all eight exact chronology labels;
- zero console errors and zero page errors.

Every checkpoint must have zero faults, zero new fault ids/rows, no frontend
mismatch signature, and no frontend fail status. Specifically:

- neither WP-012 appearance lag-one fault may recur;
- no exact missing `action.attack` binding fault may occur;
- no `action.unavailable` load failure may occur;
- no downstream action-bar icon rejection may occur.

The actual equipment interval and later inherited receipts must complete. A
terminal pass alone is insufficient.

Any fault, console/page error, malformed/missing evidence, timeout, nonzero,
or unrelated error freezes with no rerun.

### 8.5 Teardown

On every exit:

1. allow browser `finally` first;
2. terminate/join only a still-active recorded smoke tree;
3. stop/join only the owned Vite and backend trees;
4. prove ports 8000/5173 closed;
5. prove every recorded PID/child and matching Playwright, Chromium, selected
   smoke, Vite, and event-server process absent;
6. retain the exact new runtime unless removal is separately governed.

Never touch `/tmp/neurodragon-wp013-green-DHx49P`,
`/tmp/neurodragon-wp012-diagnostic-JBdpUA`,
`/tmp/neurodragon-wp011-green-KZW8go`, or any earlier retained root.

## 9. Gate B acceptance

After the single green attempt, fresh R1-R4 must independently assess:

- same-smoke red-to-green causality for the exact icon cascade;
- exact ContentRef, asset key, and authenticated digest;
- source-item precedence for armed Attack;
- definition fallback for provider-less Attack;
- absence of both the prior appearance faults and all three icon cascade
  reports;
- every inherited action/reset/parity/error receipt;
- unchanged WP-013 scene ordering;
- process/runtime cleanup;
- performance, contracts, architecture, duplication, and strict claim scope.

Gate B closes only at public 4/4 plus Coordinator verification. Only then may
WP-013 and the inherited WP-011 chain be reconsidered for exact technical
closure. No general icon, sentinel, action-bar, equipment, or BUG-031 claim
follows.

## 10. Performance and architecture

The runtime change is one existing exact catalog row from null to an existing
asset key. The frontend performs the same map lookup and URL construction it
already performs for every bound definition. There is no new branch, loop,
allocation owner, fetch class, asset, render pass, retry, timer, or product hot
path.

Armed Attack remains source-item-first. Provider-less Attack avoids one
control-plane fault, one failing fallback fetch with two loader attempts, and
one downstream rejection. This reduces failure work.

The authenticated ledger and generated Python remain the sole built-in
binding authority. No parallel frontend table, public API, wire/schema change,
serializer, persistence key, dependency, package, service, or framework is
introduced.

## 11. Gate and owner matrix

| Stage | Owner | Authorized work |
|---|---|---|
| Plan Gate A | R1-R4 | Review this exact frozen plan only |
| Binding edit | Implementation | Five files, Sections 3.1-3.4 only |
| Changed-surface static | R1-R4 | Review exact changed identities |
| Same-policy green | Tester | Exact Section 8 sequence once |
| Gate B | R1-R4 | Technical acceptance on frozen evidence |

Coordinator performs governance verification and casts no technical vote.

## 12. Mandatory Gate A questions

Reviewers must answer every question on the identical frozen plan.

1. Does the accepted WP-013 receipt vindicate the appearance-settlement seam
   while remaining non-green because of the three icon faults?
2. Do the three faults form the exact missing-binding to missing-sentinel to
   action-bar-rejection cascade?
3. Is the first failing ContentRef exact and current rather than stale?
4. Does the existing ledger intentionally classify only `action.attack` as a
   dynamic provider identity?
5. Do all reviewed runtime Attack rows use exact weapon icons?
6. Does lawful unequip create a provider-less/unarmed Attack row?
7. Does the frozen resolver prefer source item before definition?
8. Does provider-less Attack necessarily reach the null definition binding?
9. Is `ui.filter-attacks` already an exact reviewed asset in both frozen
   authorities with the stated digest?
10. Is a generic crossed-swords icon semantically correct for the definition
    fallback without replacing weapon-specific icons?
11. Are exactly the importer decision, ledger row, generated mirror, and two
    focused tests sufficient?
12. Does adding the human-reviewed mapping remove the stale intentional-null
    classification without introducing inference?
13. Does the exact ledger row carry complete authenticated evidence?
14. Is the precomputed binding digest correct and isolated?
15. Does the generated row mirror the ledger exactly?
16. Does the focused importer test prove future existing-ledger normalization?
17. Does the affordance test retain equipped source-item identity proof?
18. Can the frozen same-policy smoke prove the lawful unequip path no longer
    faults?
19. Are all NeuroClient production and WP-013 files frozen?
20. Is no manifest, asset, image, atlas, or 521-to-528 provenance refresh
    required?
21. Is the unavailable-sentinel family explicitly deferred rather than hidden
    or broadened into this packet?
22. Will a genuinely missing future binding still fail through the unchanged
    first control-plane fault?
23. Are console/page gates and structured chronology unchanged and fatal?
24. Does required green exclude both prior appearance faults and all three icon
    cascade reports at every checkpoint?
25. Are the two focused Python files sufficient to validate ledger closure,
    generated resolution, importer normalization, and affordance identity?
26. Do focused tsc and the frozen checker add the unchanged frontend/source
    prerequisites without an aggregate suite conflict?
27. Is the one registered smoke sufficient and same-policy causal?
28. Is direct no-force service ownership safe and bounded?
29. Is teardown exclusive and are all retained roots protected?
30. Does the correction reduce runtime failure work and add no product hot-path
    complexity?
31. Does it add no public contract, schema, persistence, dependency, framework,
    service, or parallel icon owner?
32. Is there any concrete false-red, false-green, cleanup, concurrency,
    performance, scope, contract, or human-decision blocker?

Only an unconditional approval on all answers contributes to Gate A.
