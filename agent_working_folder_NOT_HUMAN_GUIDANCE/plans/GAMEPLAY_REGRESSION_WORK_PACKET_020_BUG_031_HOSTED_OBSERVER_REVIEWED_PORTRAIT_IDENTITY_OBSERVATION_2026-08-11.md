# Gameplay Regression Work Packet 020 — Hosted Observer Reviewed-Portrait Observation

Date: 2026-08-11
Owner: Planner / External Reviewer 1
Test author: Tester
Implementation: HOLD; no production edit exists

## 1. Decision and exact scope

WP-020 observes only successor B2: whether a distinct hosted observer receives the reviewed portrait identity and real reviewed asset for a persistent character assignment.

It does not fix product code, reopen successor A or B1, establish product green, establish Gate B, or make a human acceptance decision. WP-017 and WP-018 remain consumed NO RETRY. WP-019 remains protocol-ready and uninvoked. Historical PIDs 636020 and 636021 remain unclassified.

The only writable project file is:

- /home/tommaso/Dev/NeuroClient/app/scripts/hosted-observer-reviewed-portrait-observation.mjs

The package is already correct and remains byte-frozen:

- /home/tommaso/Dev/NeuroClient/app/package.json
- 167 lines / 16,589 bytes
- SHA-256 8b4de2a3bae5ab6f176ddd18d4c5916e30259431869c22e89f20bf8eb5087cd9
- exact existing nonaggregate key:
  "hosted-observer-reviewed-portrait:smoke": "node scripts/hosted-observer-reviewed-portrait-observation.mjs"

No production, SDK, schema, package, dependency, fixture, other test, documentation, or configuration edit is authorized. The consumed hosted smoke remains unread and unused.

## 2. Acceptance contract for the one script

### 2.1 Real public flow and independent owners

The script must use the visible production flow:

1. In a fresh fixture BrowserContext, create a persistent premade character through the real character creator and persist its reviewed portrait choice.
2. Through the existing public generated SDK/fixture path, create one hosted game with an explicit Codex assignment. Use the production DirectoryClient and generated request/response models; do not hand-build or fabricate a private request body.
3. Open the resulting game through the production setup owner, retain the visible prepared-lobby receipt and decoded Codex assignment, and stop before prepared.enter(), Enter, owner runtime attachment, or available-actions ownership. Do not click or depend on a hidden or standalone-only Codex control.
4. In a separate fresh BrowserContext with a distinct principal and storage, use the public hosted-game Observe control.
5. Attach page, console, Playwright request/response/failure, and CDP Network listeners before the relevant navigation or observation.

Fixture and observer identities, contexts, pages, storage, credentials, handles, and journals must remain separate.

Candidate A changes only fixture setup. The generated SDK/fixture creation supplies the prerequisite Codex assignment; the production prepared-lobby and public Observe UI remain the behavioral receipts. It may not enter the owner runtime, relax observer A/B1 isolation, use a hidden or standalone-only control, or change production behavior, contracts, schemas, persistence, dependencies, package bytes, or any file other than the WP-020 script.

Every pageerror and error-level console callback must both retain its evidence row and immediately add a fatal failure. Those failures participate in checkpoint gating, so an error observed before the checkpoint cannot produce a normal marker. Do not fatalize the same retained row a second time later.

### 2.2 Generated decoding, dual IDs, and assignments

Use the production SDK/model boundaries. Do not invent a DTO or hand-decode a substitute shape.

- Decode the fixture response as CreateHostedGameResponse and its creation as GameCreationStartResponse.
- Flatten creation.rosters[].entity_assignments.
- Decode observer game.creation_manifest.response independently as GameCreationStartResponse.
- Retain roster_id, member_id, entity_uuid, and character_id for every non-null assignment.
- Require independent fixture and observer assignment equality.

Keep the two ID domains explicit and require them to differ:

- gateway_game_id: GameRecord.game_id, both HostedGameConnection.game_id values, URLs/session identity, and the visible active hosted card.
- engine_game_id: fixture creation.game_id, both non-null GameRecord.engine_game_id values, and observer manifest response.game_id.

The structured portrait diagnostic runtime game_id is compared only with engine_game_id.

### 2.3 Production portrait resolution and diagnostics

Under the observer principal, discover a fresh DirectoryContext. For every observer-decoded non-null assignment character_id, retain independently:

- definition-map presence;
- presentation-preference-map presence;
- premade_id and portrait_key when present;
- selectedCharacterPortrait() result;
- authoredPortraitUrl() for the real replicated entity.

The smoke must not call configureRuntimeAuthoredPortraits(); main.ts remains its sole mutation owner. Diagnostics are snapshot-read only and may not be recorded, cleared, reconciled, filtered, or injected.

Capture diagnostics before deciding that a missing image is merely an asset failure. Retain the exact B2 fault kind, message, error/code, engine runtime ID, missing rows and reasons, plus every unrelated presentation fault. An exact B2 fault is useful causal evidence but remains nonzero. Every unrelated fault is independently fatal.

### 2.4 Exact asset corroboration

For each resolved assignment, compute the exact absolute authored URL against the observer page URL.

Require all of the following for that same URL:

- a Playwright request;
- a CDP requestWillBeSent row whose initiator is a retained non-null object with a concrete nonempty protocol initiator.type string;
- no matching request failure;
- a real Playwright response with status 200 and content-type beginning image/webp;
- the production initiative slot/image for the exact entity;
- exact portrait key;
- absolute src and currentSrc equality;
- complete=true, positive naturalWidth/naturalHeight, visibility, and no missing fallback marker.

Unrelated reviewed-root traffic cannot satisfy another assignment. Absence, cache-only inference, deliberate warming, self-fetch, fabricated events, screenshots, body-pixel substitution, or fallback cannot pass.

No route interception, fulfill, abort, continue, response rewrite, header rewrite, cache mutation, store/local-storage injection, fake directory map, private fallback, name guess, generated-body substitution, sleep, or networkidle is allowed.

### 2.5 A and B1 isolation

Both contexts must journal and require zero traffic for:

- the dynamic /entity/{encoded UUID}/available-actions route, including method, query, response and failure;
- diagnostics/objective/bootstrap;
- diagnostics/subjective-parity.

Retain structured affordance faults. Any A evidence is non-green deferred-A contamination and is not diagnosed here. Any B1 request is a non-green regression and does not reopen WP-018.

The observer must prove access_mode=observer, exact gateway game/session identity, and zero controlled entities.

### 2.6 Process checkpoint, output, and success law

The smoke participates in the existing process-only checkpoint:

- fixture-live.marker.json with schema wp020-process-handshake-v1;
- fixture-live.captured.ack.json with schema wp020-process-capture-ack-v1;
- normal marker only after fixture and observer contexts/listeners and all reached live resources exist;
- truthful finally-protected precheckpoint-failure marker on earlier failure;
- acknowledgement binds the exact marker and three owned process-tree receipt digests.

The checkpoint carries process evidence only and cannot supply behavioral success.

Initialize the result and journals before the first action. Preserve partial fixture, observer, assignment, directory, diagnostic, A/B1, network, handshake, page/console, request-failure, and cleanup evidence across later failures.

After nested context/browser cleanup attempts, emit exactly one compact JSON object. Every operational, assertion, page/console, request, structured-fault, asset, A/B1, handshake, or cleanup error remains visible and makes the command nonzero.

Exit zero only when dual IDs, independent assignments, production portrait resolution, exact Playwright/CDP/200-WebP evidence, semantic initiative-image load, zero A/B1 traffic, zero faults, and zero other errors all hold. Every outcome consumes the one governed execution.

## 3. Named authorities the Tester may read

Before authoring, Tester reads HOW_TO_TEST.MD completely and may read only this plan plus the following already selected authorities:

Engine/SDK:
- sdk/typescript/src/directoryClient.ts
- sdk/typescript/src/generated/contracts.generated.ts
- sdk/typescript/src/client.ts
- sdk/typescript/src/objectiveDiagnostics.ts
- sdk/typescript/src/validation.ts
- server/game_gateway.py
- server/hosted_worker.py

The Candidate A fixture must remain on the public generated DirectoryClient/request-model surface exposed by these authorities. The test may populate the explicit Codex assignment through that existing fixture path, but may not duplicate the DTO, hand-serialize a private body, or introduce a new helper outside the WP-020 script.

NeuroClient:
- app/src/api/gameDirectory.ts
- app/src/api/bootstrap.ts
- app/src/main.ts
- app/src/ui/portraitUtils.ts
- app/src/ui/characterPresentationPreferences.ts
- app/src/ui/gameSetupArt.ts
- app/src/ui/characterCreator.ts
- app/src/ui/gameSetup.ts
- app/src/ui/gameSetupCharacterRoster.ts
- app/src/ui/gameBrowser.ts
- app/src/ui/initiativeBar.ts
- app/src/engine/runtimeConnection.ts
- app/src/engine/eventStream.ts
- app/src/engine/presentedAffordanceLease.ts
- app/src/render/presentationDiagnostics.ts

Ordinary bounded reads and output chunking are normal tool operation. Review or authoring stops only when a warning, truncation, or tool condition creates real uncertainty about bytes, scope, ownership, evidence, or safety. A known non-mutating line-ending advisory is retained but is not by itself a waiver or a reason to redesign the protocol.

## 4. Authoring stage

After one fresh isolated Plan Gate A R1-R4 approval and Coordinator verification, Tester may perform one authoring turn.

Tester may read the guide, this plan, the named authorities, the existing WP-020 script, and the frozen package solely to confirm its identity. Tester then replaces the entire WP-020 script once using one successful full-file apply_patch Update File operation built from the actual file it read. The operation must contain the complete old file and complete new file, touch only the script path, and avoid guessed mid-file context.

No package, production, SDK, schema, other test, or other path may change. No syntax check, test, service, browser, process inspection, behavioral execution, cleanup, or one-shot action occurs in the authoring stage.

If the writer fails before mutation, Tester stops and reports the exact error. After independent confirmation that scoped bytes are unchanged, Coordinator may release a fresh authoring turn under this same approved plan; patch mechanics alone do not require a new plan identity or another Plan Gate A. A partial or uncertain mutation instead fails closed and requires explicit governance disposition.

After a successful writer, freeze and return:

- script line count, byte count, SHA-256, final LF, and absence of CR;
- complete new-file diff for the script;
- package line/byte/SHA and exact key neighborhood, unchanged;
- scoped status proving only the pre-existing package modification and the one WP-020 script path.

The script must be nonempty, no more than 1,200 lines or 60,000 bytes. The authoring receipt and actual resulting bytes, not patch mechanics, are the static review identity.

## 5. Combined-static gate

Coordinator freezes the exact plan, script, package, scoped-status and complete-diff identities.

Fresh isolated R1-R4 reviewers independently read the actual script and named authorities. They verify:

- exact two-file scope, with only the script newly changed and package byte-identical;
- the complete acceptance contract in Section 2;
- generated DTO and production-owner use;
- no duplicated production authority, mock, fallback, interception, private probe, or suppressed failure;
- one-JSON/fatal-error behavior;
- marker/ack compatibility;
- no execution in authoring.

Any reviewer may request a concrete correction. Execution remains closed until all four approve the same actual artifact identity and Coordinator verifies the unanimous ledger.

## 6. Governed one-shot and owned teardown

Only after combined-static 4/4 plus Coordinator release may Tester perform one attempt.

Before any live launch, run the existing focused static prerequisites from their exact project roots:

- TypeScript no-emit check;
- node --check on the frozen script;
- the frozen node-sources/Vite checker;
- exact package-key lookup.

Stop on any failure. No install, broad build, broad suite, retry, or substitute command is authorized.

Use one fresh short retained evidence root. Launch:

- direct no-force Uvicorn gateway on 127.0.0.1:8000, one worker, DND_HOSTED_WARM_WORKERS=0;
- one strict-port Vite owner on 127.0.0.1:5173;
- the one registered WP-020 smoke under the existing 180-second outer owner.

Each launch is in non-job-control mode and is accepted only after the returned generation becomes an exact nonterminal session/process-group leader with stable PID, starttime, PPID, PGID and SID.

At the fixture-live checkpoint, capture parent-complete owned trees for gateway/preview/conditional hosted worker, Vite, and smoke/browser. Tree rows bracket cmdline/children reads with stable generation, parent, group and session evidence. The source-derived hosted UDS is the only mutable path outside the fresh root.

Teardown signals only still-matching recorded generations/groups. No PID/name/port matcher, census, prior root, sibling socket listing, broad cleanup, or signal to a reused/mismatched generation is allowed. Normal green requires no reuse, errors, survivors, forced fallback, listener, or exact UDS. Emergency cleanup uses only safe partial receipts and is always non-green.

Retain the database, runtime/log/artifact inventories and hashes, handshake files, process receipts, exact socket/port absence, command stdout/stderr/exit/timing, final scoped status, and the fresh root on every outcome. No retry or timeout extension exists.

## 7. Gate sequence and ownership

1. Planner freezes this concise plan.
2. Fresh isolated Plan Gate A R1-R4 4/4.
3. Coordinator releases Tester authoring.
4. Tester writes only the one script and freezes the real artifact.
5. Fresh isolated combined-static R1-R4 4/4 on that artifact.
6. Coordinator releases exactly one governed execution.
7. Tester performs the one-shot with owned teardown.
8. Fresh receipt-only R1-R4 review classifies the observation.
9. Coordinator closes WP-020.

Planner routes every assignment and ledger. Tester owns test code and execution. Implementation owns nothing in WP-020 and remains HOLD. Reviewers are peer-isolated and never implement. Advisory monitors remain non-gating and cannot change this packet.

No earlier vote or failed authoring evidence carries into a different artifact identity. Ordinary authoring-tool failures with proven unchanged bytes may reuse the same approved plan as stated in Section 4.

## 8. Frozen deferrals and no-waiver law

The following remain outside WP-020:

- successor A diagnosis or correction;
- B1/WP-018 retry;
- WP-019 invocation;
- WP-016 SELF/TARGET;
- hosted-agent and other authorization policy;
- API/schema/SDK/server-policy/privacy/persistence/asset-policy changes;
- inventory, multi-character, and unavailable-sentinel successors;
- historical PID classification;
- product correction, fallback policy, or human acceptance.

No formatter, normalization, platform, expected-noise, generic-warning, or future-byte waiver may change acceptance evidence. A diagnostic may be judged non-mutating only when bytes, scope, ownership, evidence, and safety remain certain and the exact advisory is retained.

## 9. Mandatory Plan Gate A questions

Reviewers answer these on the same plan identity:

1. Is scope exactly one WP-020 script with package and production read-only?
2. Does the plan select only B2 and preserve all consumed/deferred boundaries?
3. Does Candidate A use only the existing public generated SDK/fixture path for the explicit Codex assignment while preserving production prepared-lobby/Observe receipts and avoiding hidden controls or owner runtime entry?
4. Are generated request/response models, decode, dual-ID domains, independent assignments, and owner separation correct?
5. Is observer directory/portrait evidence assignment-owned and production-derived?
6. Are exact B2 and unrelated diagnostics retained before image gating and fatal?
7. Is asset success tied to each exact absolute URL through Playwright, a concrete retained CDP initiator object/type, 200 WebP, and semantic image state?
8. Are A and B1 journals dynamic, complete, zero-required, and non-green on evidence?
9. Are mutation, interception, warming, self-fetch, guessing, fallback, sleeps, and filtering forbidden?
10. Are pageerror/error-console rows immediately fatal before checkpoint gating without duplicate fatalization, and is one-JSON output complete with zero limited to the full resolved conjunction?
11. Does Tester own one bounded whole-file script authoring operation after Gate A?
12. Are failed writer mechanics handled honestly without forcing irrelevant plan churn when bytes are proven unchanged?
13. Does the resulting real artifact receive fresh isolated 4/4 static review before execution?
14. Is the one-shot separately released, single-use, and preceded by focused static prerequisites?
15. Are launch ownership, marker/ack, generation-pinned trees, exact UDS, teardown, and final absence fail-closed?
16. Are package/production scope, NO RETRY, no-waiver, owner separation, and deferrals preserved?
17. Is there any concrete false-green, false-red, safety, scope, contract, performance, or human-decision blocker?

## 10. Current authorization

This plan authorizes nothing by itself. Tester, Implementation, reviewers, packet execution, and product changes remain HOLD until Coordinator matches this exact plan identity and opens fresh Plan Gate A. The protected script and package remain untouched during planning.
