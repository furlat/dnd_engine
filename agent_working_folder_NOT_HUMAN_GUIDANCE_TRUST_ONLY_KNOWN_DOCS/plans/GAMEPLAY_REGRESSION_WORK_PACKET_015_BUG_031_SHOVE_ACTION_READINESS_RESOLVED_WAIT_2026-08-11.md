# Gameplay Regression Work Packet 015 — BUG-031 Stage 5 Shove Action Readiness Resolved Wait

Date: 2026-08-11
Owner: Planner / External Reviewer 1
Implementation owner: none; Tester owns both permitted files after governed release
Execution owner: Tester only after every required static sub-gate closes

## 0. Decision and boundary

WP-014 closed the exact provider-less Attack icon cascade and supplied the
clean same-policy receipt required for the bounded WP-013 scene-settlement and
WP-011 readiness claims. Those identities and receipts are accepted history
and are not revised here.

The refreshed static inventory contains exactly 14 remaining Promise-valued
`waitForFunction` call shapes:

- one in `live-shove-presentation-smoke.mjs`;
- one in `hud-rpg-smoke.mjs`;
- two in `hosted-game-smoke.mjs`;
- three in `inventory-panel-smoke.mjs`;
- seven in `multi-character-live-smoke.mjs`.

This packet selects only the single call in the maintained live Shove smoke.
If accepted, 13 occurrences remain explicitly open.

The selected smoke currently relies on an ambient durable character named
`Shove Smoke Fighter`. That dependency previously made the seam unsuitable
for a fresh owned run. WP-010 and WP-011 subsequently established the exact
lawful production-owned prerequisite for a brand-new standalone root: one
visible creation requirement, disabled New Match, one real premade-character
POST, one exact selected character card, enabled New Match, and the real
character-sheet close path. WP-015 applies that already accepted prerequisite
inside the selected smoke.

The fresh character remains AI-controlled. The existing authored
`encounter.sorcerer_barbarian_duel` opponent and its level-five Barbarian
remain human-controlled, so the inherited deterministic Shove actor,
approach, action, cue, forced-movement, cursor, backlog, and fault evidence are
not replaced by the fixture.

Exactly two existing Tester files may change:

- `app/scripts/check-node-sources.mjs`;
- `app/scripts/live-shove-presentation-smoke.mjs`.

No production, package, Vite, Playwright, SDK, generated, backend, service,
schema, protocol, persistence, asset, dependency, public-contract, or second
smoke edit exists.

### 0.1 Candidate triage and explicit deferral

The nearby candidates remain fail-closed for this stage:

- `hud-rpg-smoke.mjs` also needs a real character and writes screenshots into
  repository-owned `agent_docs/assets`, adding an unrelated artifact mutation
  boundary;
- `inventory-panel-smoke.mjs` has three independent waits and a durable roster
  fixture;
- `multi-character-live-smoke.mjs` spans seven waits and several independent
  session, roster, targeting, and action authorities;
- `hosted-game-smoke.mjs` requires a different hosted-service topology.

The absent `action.unavailable`, `item.unavailable`, `object.unavailable`,
`reaction.unavailable`, and `condition.unavailable` asset family remains a
separate multi-asset/content-design backlog. WP-014 removed it from the exact
maintained green path by correctly binding Attack; WP-015 does not alias,
generate, suppress, or claim that family.

### 0.2 Human authorization and progression

The human authorized automatic progression across bounded owner-correct
seams. This packet changes two existing Tester files, introduces no product
behavior choice, and requires no architecture, public contract, schema,
persistence, dependency, framework, or service expansion.

### 0.3 Strict claim

Successful Gate B may establish only:

> BUG-031 Stage 5: the maintained live Shove smoke is statically guarded
> against its single Promise-valued action-readiness wait and explicitly
> observes resolved `my_turn_input`, active-actor action ownership, and zero
> presentation backlog on one fresh lawful real-character fixture before its
> inherited Shove presentation receipt.

It does not claim character creation, Shove correctness, forced movement,
action execution, general presentation, general replication, hosted behavior,
the remaining 13 occurrences, the unavailable-sentinel family, or broader
BUG-031/product correctness.

## 1. Frozen authority identity

Every identity is exact. Any mismatch fails intake closed. No automatic
refresh, substitution, regeneration, or baseline carry is permitted.

### 1.1 Accepted predecessor and evidence

| Authority | Lines | SHA-256 |
|---|---:|---|
| `agent_working_folder_NOT_HUMAN_GUIDANCE/plans/GAMEPLAY_REGRESSION_WORK_PACKET_011_BUG_031_SUBJECTIVE_ACTION_READINESS_RESOLVED_WAIT_2026-08-11.md` | 428 | `1e7925843ff2832664e0e8eb99f1a7bac5e27cee02586cad5bf3e067af13fca0` |
| `agent_working_folder_NOT_HUMAN_GUIDANCE/plans/GAMEPLAY_REGRESSION_WORK_PACKET_014_UNARMED_ATTACK_EXACT_ICON_BINDING_2026-08-11.md` | 585 | `c12bb45d964f84d86bcfe7d588532f610ab6ecfe0b80efbeaa17aca204dba60d` |
| `/tmp/neurodragon-wp014-green-ZtYuMO/live-subjective-actions-smoke.stdout` | 5 | `c92c59fff0a30bb6ec6edc67cdb5f63f364ee5bd55dd4088effda3f0ba80f191` |
| `/tmp/neurodragon-wp014-green-ZtYuMO/live-subjective-actions-smoke.stderr` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

All retained roots are immutable evidence, never packet state.

### 1.2 Mutable Tester baselines

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/scripts/check-node-sources.mjs` | 100 | `d46c4d12a5d23f4a2a496bafc544a7a8b7ac499e89c4496a00e564b88689c3d1` |
| `/home/tommaso/Dev/NeuroClient/app/scripts/live-shove-presentation-smoke.mjs` | 537 | `9e50d2a9f2012167510151c46e7df0141b181d80dcaebf12a04a3ac6706ff1ab` |

The accepted checker rules and corrected target identities are frozen:

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/scripts/turn-burst-smoke.mjs` | 336 | `3e71c47d90d983df2a88d5483f288454bf476e4b81cb1f3108f35c1660495420` |
| `/home/tommaso/Dev/NeuroClient/app/scripts/real-character-game-creation-live-smoke.mjs` | 528 | `01650889d45e6d77db0f96ee22bbfd84f99125592db88ca2be1dd68f81fdcd5a` |
| `/home/tommaso/Dev/NeuroClient/app/scripts/replication-smoke.mjs` | 406 | `078a4cccc8f6a72d71baa9f8b22dbd8fc20e49144a13a524e3c5e080059f5ca1` |
| `/home/tommaso/Dev/NeuroClient/app/scripts/live-subjective-actions-smoke.mjs` | 780 | `c04a200674d41e4b2711cfabc4a9870f93421a59d84380aac37fbaf72bb69fa4` |

### 1.3 Package and Playwright authorities

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/package.json` | 165 | `36515d20ea94ebc0c49a47b79bd455fee0eddceea2eb5e52713163eff159d9e3` |
| `/home/tommaso/Dev/NeuroClient/app/vite.config.ts` | 235 | `7d70b9fae8cf5d4a8d38762865ac8f36adba1247721212fcb5b3d7455f247153` |
| `/home/tommaso/Dev/NeuroClient/app/node_modules/playwright-core/package.json` | 48 | `d4b8727c495ff2632084e922ee1c7f19a608ed23d86e8f3b0ba0ff317eea58ec` |
| `/home/tommaso/Dev/NeuroClient/app/node_modules/playwright-core/lib/server/frames.js` | 1500 | `a0a5c3655b86edeb1e6acb8133d40769dda53c246340271251598dac5ff48594` |
| `/home/tommaso/Dev/NeuroClient/app/node_modules/playwright-core/lib/server/javascript.js` | 291 | `134f2aae953ca802c3d8c4da2ddb0857129ae3044f8958cdb857993341aec257` |
| `/home/tommaso/Dev/NeuroClient/app/node_modules/playwright-core/lib/server/chromium/crExecutionContext.js` | 146 | `4b4da27c16c2ec7094dcc3cc78313eb9ac8f15a9ed3b7589118a883d6d339b7f` |

Installed Playwright is 1.59.1. No dependency action exists.

### 1.4 Frozen action and presentation owners

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/src/main.ts` | 636 | `e8749ccf14f3a5eed27b5d3fc8e5deff4dbbe3fc45062524eeeca787ec816440` |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/store.ts` | 431 | `b0c428f266cf3c23608143e3ee73fc048f82bfb0afb5ffee3e317b1aff859537` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/actionBar.ts` | 2429 | `0f741a9a0abcf69ff9d62ad2685ba052531d0b4ba842edcc5c72693c60a8f52e` |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/actionResultHandler.ts` | 81 | `7dc73b4db848bbc57e97ca8ba493438462e44d12f7d95ff641d5c27e052bc34d` |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/eventStream.ts` | 974 | `912ef41889c5a1a753d8969037550e3fabc6ecbd126e1d417e4cced6290fd522` |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/clientStateMachine.ts` | 393 | `960b5efad1012accc86633f7be42c66d6ff3109114f1dce92d5cbb82a8d9d285` |
| `/home/tommaso/Dev/NeuroClient/app/src/api/actions.ts` | 111 | `857d866984ac43699d019aa4490dfa2cd0ff1fa68d82b961cb2b1a0112503462` |
| `/home/tommaso/Dev/NeuroClient/app/src/render/presentationDiagnostics.ts` | 1264 | `4271e3b7711b8964212f9d0994877768c386c1ac359b476f5c3b94d3d8233f69` |

These owners remain byte-frozen. The smoke observes their actual state,
actions, cursors, coverage, and faults.

### 1.5 Character, setup, and service prerequisites

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/src/ui/gameCreationReadiness.ts` | 38 | `1dd39360063376c67a8a028742e11fdab769c3888bd6b6599f5999498ea7c1ac` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/gameBrowser.ts` | 1097 | `6bf4ad5e856cd38ea671218b1e9d928d51e04bcc1c054329a587fef7b9cd896c` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/characterCreator.ts` | 2772 | `bb6365ca79164a13467699d2c3142134b61f71a3560b0ef89f5f31cd3f15e20b` |
| `/home/tommaso/Dev/NeuroClient/app/src/api/gameDirectory.ts` | 961 | `7c302315a8da021fb7652baf09d2d5c9575cd82893fe15729a80a85968fe6560` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/characterSheet.ts` | 1266 | `9bdf076f1b1383e297143c044ff116b2f792c1ba1af994d29e731ebc6774ba0b` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/gameSetup.ts` | 2228 | `eba13f093bd5a8c6006e73d7b1918a1a1a9a7c64953adc20474d2e895baa17e1` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/gameSetupCharacterRoster.ts` | 347 | `6b666a0729d489088266b915b0f278e108e9f881bc5d6dc7368be6dc3cb57a20` |
| `/home/tommaso/Dev/NeuroClient/server.sh` | 19 | `fd4db2fc27366f963308a93dd6c07096566b8c58bb1515a4dfbc95e8e6f1a22a` |
| `server/event_server.py` | 6978 | `eb1f6e891bc4cb149c8f054bb8ae36e4df7f2a7a7d47e6cc91af2a3e7394cdc5` |
| `server/game_directory/local_profiles.py` | 420 | `7ce82baee1b1b413c1a5b35467489c52eae53d59fabe583446ac21fb856e0ade` |

`server.sh` is context only and must never be launched. No character,
encounter, Shove, backend, or service correctness claim is added.

## 2. Causal finding

### 2.1 Installed Playwright behavior

Frozen Playwright invokes the injected `waitForFunction` predicate and
branches on the immediate return value before later result adoption. An async
predicate returns an immediately truthy Promise object. If its eventual value
is false, the injected polling loop has already fulfilled and returned, so no
next poll is scheduled.

Ordinary `page.evaluate` uses Chromium `awaitPromise: true`. Explicit Node-side
polling therefore receives the resolved serializable Boolean instead of
testing Promise-object truthiness.

### 2.2 Selected stale wait

The selected smoke has exactly one Promise-valued `waitForFunction` call. It
occurs after game setup detaches and live module URLs are discovered. Its exact
condition is:

- production `clientState === "my_turn_input"`;
- a non-null active actor action row from
  `availableActionsByEntityId.get(active_entity_uuid)`;
- `presentationBacklog === 0`.

One resolved false can complete the current wait. The later large browser
evaluation reads the initial actor/session/action state and its inherited
action helpers check state again, but those later failures or waits do not
prove the named pre-action readiness boundary.

### 2.3 Exact fresh-character premise

A brand-new standalone root creates one local profile/principal/settings but
no character. Production therefore renders exactly one create requirement and
disabled New Match.

The correction uses only the real production premade-character UI and one
observed exact-path `POST /api/directory/characters`. It neither parses nor
copies the response body and introduces no request DTO, route interception,
API seed, store write, retained profile, or mock.

The fixed input name is `Shove Readiness Fixture`. Success requires an actual
HTTP success status, creator detachment, exactly one selected card with exact
rendered text, zero remaining requirements, enabled New Match, the real
production-opened character sheet, its real close control, and exactly one
observed request.

The card's actual `data-select-character` ID must equal the only selected
`data-roster-member` ID in game setup. That exact roster member is then set to
AI. The authored opponent choice and human Barbarian controller remain the
unchanged inherited Shove actor.

## 3. Checker-first natural red

### 3.1 Authorized checker block

After Gate A closes, Tester may first edit only
`app/scripts/check-node-sources.mjs`.

Immediately after the accepted live-subjective-actions block, add one
target-local path/read/regex rule for:

`scripts/live-shove-presentation-smoke.mjs`

Use the exact accepted async-first-argument regex semantics:

`/\.waitForFunction\s*\(\s*async(?:\s+function\b|\s*\()/u`

and exact diagnostic:

`scripts/live-shove-presentation-smoke.mjs: Promise-valued waitForFunction predicate is forbidden; use explicit resolved page polling.`

Preserve the four accepted target blocks, recursive sorted `.mjs` traversal,
per-file Node syntax checks, Vite diagnostics, failure aggregation, and success
summary byte-for-byte outside the adjacent block. The rule reads only the
named Shove smoke and does not scan the remaining 13 occurrences.

### 3.2 Checker static sub-gate

The changed checker identity requires fresh isolated R1-R4 static approval.
No command is authorized before public 4/4 plus Coordinator verification.

### 3.3 Exact first red

After that sub-gate closes, Tester may run once from NeuroClient root:

`npm --prefix app run node-sources:check`

The only accepted result is nonzero with the sole exact Section 3.1
diagnostic. The node-config TypeScript prerequisite must pass. Any path,
syntax, Vite, timeout, earlier-rule, or other error freezes. No service,
browser, product smoke, focused app TypeScript, edit, rerun, or alternate
probe is authorized.

### 3.4 Correction release

The exact red receipt requires fresh R1-R4 causal approval before the smoke
edit. The checker then freezes byte-for-byte. The red releases only Section 4
in the selected smoke and no execution.

## 4. Required smoke correction

### 4.1 Real fresh-character prerequisite

After game-browser visibility and before the inherited New Match action:

1. require exactly one visible create requirement;
2. record and require actual disabled New Match;
3. install one observation-only request counter matching POST plus exact
   parsed pathname `/api/directory/characters`;
4. open the real premade creator, fill `Shove Readiness Fixture`, arm the
   response wait before one real enabled create click, require successful
   status, and require creator detachment;
5. require exactly one selected card, exact rendered name, and record its
   non-null actual `data-select-character` ID;
6. require zero remaining requirements and enabled New Match;
7. require the real character sheet visible, use its existing close control,
   and require detachment;
8. require the exact character request count to be one;
9. click the same production New Match control;
10. in game setup require exactly one selected roster member and require its
    actual ID to equal the created card ID;
11. set that exact roster member to AI, record its actual active controller,
    and require it to be `ai`;
12. after the inherited authored opponent selection and human-controller
    action, record the actual active opponent controller and require it to be
    `human`.

Remove the durable `Shove Smoke Fighter` name lookup, ambient initial-character
toggle, and related durable-fixture errors. No other game-setup behavior may
change. Preserve the authored opponent selection, opponent human controller,
encounter/local/opening choices, Start Match readiness, bootstrap/subscribe,
and setup detachment.

### 4.2 File-local resolved-poll helper

Add one file-local helper:

`waitForResolvedPageCondition(targetPage, evaluateCondition, evaluateArgument, timeoutMs, label, pollIntervalMs = 50)`

It must:

1. use one Node `performance.now()` start and one absolute deadline for the
   complete wait;
2. reject before starting an evaluation when budget is exhausted;
3. increment attempts exactly once per actual evaluation;
4. call `targetPage.evaluate(evaluateCondition, evaluateArgument)`;
5. race that one evaluation against one timer for the freshly computed
   remaining budget;
6. clear the timer in `finally` on every settlement;
7. reject a truthy result settling at or after the deadline;
8. delay a false result by no more than `min(50ms, remaining budget)`;
9. begin no post-expiry evaluation;
10. use exact timeout text
    `<label> did not resolve within <timeoutMs>ms`;
11. retain only O(1) state with one evaluation and timer in flight.

No shared helper, Playwright wrapper, polling framework, timer workaround, or
production change is authorized.

### 4.3 Selected wait replacement

Replace only the selected async `waitForFunction` call with the Section 4.2
helper using:

- the already discovered serializable `runtimeModuleUrls` object as the one
  explicit page-evaluation argument;
- timeout `60_000`;
- label `shove action readiness`;
- the exact existing predicate:
  `my_turn_input`, non-null active action row, and zero presentation backlog.

The page function imports only the provided production store module URL and
captures no Node closure.

### 4.4 Independent readiness receipt

Immediately after helper success and before the inherited large page
evaluation, perform a separate `page.evaluate` with the same serialized module
URL object. Record actual:

- `clientState`;
- `activeEntityUuid`;
- `actionsEntityUuid` from the active-keyed row;
- `presentationBacklog`.

Require exact `my_turn_input`, non-null active identity, equal action/active
identities, and backlog zero. A Promise object, resolved false, missing actor,
wrong cached row, nonzero backlog, or hard-coded summary cannot green.

### 4.5 Actual output evidence

Extend the one final JSON only with actual values for:

- `initialCreateRequirementCount`;
- `initialNewMatchDisabled`;
- `characterCreateRequestCount`;
- `characterCreateStatus`;
- `createdCharacterCardCount`;
- `characterFixtureName`;
- `createdCharacterId`;
- `remainingCreateRequirementCount`;
- `finalNewMatchEnabled`;
- `gameSetupRosterCharacterId`;
- `gameSetupRosterController`;
- `authoredOpponentController`;
- `shoveReadinessWait` attempts/elapsed;
- `shoveReadinessState`.

The fixed name is input identity and must be independently proven by rendered
DOM text. All status, count, ID, state, and backlog values are observations.

### 4.6 Frozen inherited behavior

Outside Sections 4.1-4.5 preserve byte-for-byte:

- browser/pageerror and selected fatal console collection;
- authored opponent and controller topology;
- Start Match, bootstrap, subscribe, and setup-detachment waits;
- live module discovery;
- production diagnostics API availability;
- exact actor/session/action ownership;
- one-attempt Shove loop;
- reach/open-door/Move/End Turn approach behavior;
- real executeAction/processActionResult transitions;
- presentation cursor and backlog barriers;
- Shove and ForcedMovement cue ownership and endpoint assertions;
- reconciliation-fault rejection;
- result fields and browser-error diagnostics;
- browser close in `finally`.

No response-body parsing, API seed, mock, route interception, action shortcut,
state/store mutation outside the inherited production actions, fault filter,
diagnostic clear, screenshot, or second file is authorized.

## 5. Combined static review

The frozen checker and revised smoke identities require fresh isolated R1-R4
review. Reviewers must prove:

1. only the two Tester files changed;
2. checker order and inherited behavior are preserved;
3. no Promise-valued wait remains in the selected smoke;
4. the fresh-character prerequisite uses real production UI/API ownership;
5. created-card and game-setup roster IDs agree exactly;
6. the new character remains AI while the authored Barbarian remains the
   inherited human Shove actor;
7. the helper has one absolute deadline and resolved page values;
8. the independent snapshot proves exact state/action identity/backlog;
9. inherited Shove and error/cleanup behavior is unchanged;
10. no production, package, service, screenshot, artifact, or third-file edit
    exists.

No execution is authorized before public static 4/4 plus Coordinator
verification.

## 6. Governed same-policy green

### 6.1 Frozen prerequisites

From NeuroClient root, exactly once each and stopping on nonzero:

1. `./app/node_modules/.bin/tsc --noEmit -p ./app/tsconfig.json`;
2. `npm --prefix app run node-sources:check`.

No aggregate check/build or alternate command is authorized.

### 6.2 Fresh owned stack

Only after both prerequisites exit zero:

1. prove ports 8000/5173 and matching packet processes absent;
2. create one brand-new disposable `/tmp` runtime root;
3. from dnd_engine root start exactly one owned backend without `--force`:

   `DND_LOCAL_PROFILE_RUNTIME_ROOT=<brand-new> ./.venv/bin/python -m server.event_server --host 127.0.0.1 --port 8000`

4. require direct `/server/capabilities` HTTP 200 with
   `server_mode=standalone` within 90 seconds;
5. start one owned registered Vite and require exact-root HTTP 200 in a bounded
   window;
6. run `npm --prefix app run live-shove-presentation:smoke` exactly once as one
   recorded owned process session under an exact 300-second outer wall clock.

A preflight/start race must freeze on ordinary bind failure. The direct launch
omits `--force` and may never signal an unrelated listener.

### 6.3 Required green evidence

The smoke must exit zero without timeout and emit exactly one final JSON. It
must prove:

- one initial requirement and disabled New Match;
- exactly one successful character POST and one exact selected fixture card;
- zero remaining requirements and enabled New Match;
- created card ID equals the sole selected game-setup roster ID;
- the created roster member's actual active controller is AI and the authored
  opponent's actual active controller is human;
- resolved helper attempts/elapsed;
- independent `my_turn_input`, equal active/actions IDs, and backlog zero;
- all inherited Shove result fields;
- a presented Shove cue and lawful optional child ForcedMovement ownership;
- presentation cursor reaches the action receipt and backlog is zero;
- no presentation/reconciliation/browser error.

Any fault, malformed/missing evidence, timeout, nonzero, unrelated error, or
cleanup mismatch freezes with no rerun.

### 6.4 Teardown

On every exit:

1. allow browser `finally` first;
2. terminate/join only a still-active recorded smoke tree;
3. stop/join only the owned Vite and backend trees;
4. prove ports 8000/5173 closed;
5. prove every recorded PID/child and matching Playwright, Chromium, selected
   smoke, Vite, and event-server process absent;
6. retain the exact new runtime unless removal is separately governed.

Never touch `/tmp/neurodragon-wp014-green-ZtYuMO`, any WP-013/WP-012/WP-011
root, or any earlier retained evidence.

## 7. Gate B acceptance

After the single green attempt, fresh R1-R4 must independently assess:

- same-policy checker red-to-green causality;
- actual fresh-character and roster-identity receipts;
- resolved readiness and independent state/action/backlog proof;
- inherited Shove/cue/forced-movement/cursor/backlog evidence;
- unchanged fatal diagnostics and browser cleanup;
- direct no-force service ownership and exclusive teardown;
- performance, contracts, architecture, duplication, and strict claim scope.

Gate B closes only at public 4/4 plus Coordinator verification.

## 8. Performance and architecture

The checker adds one constant file read and regex. The smoke adds one bounded
real character creation and one O(1) resolved-poll helper with one
evaluation/timer under 60 seconds. The independent snapshot is one read-only
evaluation.

There is no product hot-path, renderer, action, backend, serializer,
persistence, schema, wire, SDK, public-contract, dependency, package, service,
or framework change. No duplicate readiness owner is introduced: the helper
observes the production store, and the inherited Shove evaluation continues
to own action behavior.

## 9. Gate and owner matrix

| Stage | Owner | Authorized work |
|---|---|---|
| Plan Gate A | R1-R4 | Review this exact frozen plan |
| Checker edit | Tester | Section 3.1 only |
| Checker static | R1-R4 | Review frozen checker identity |
| First red | Tester | Section 3.3 once |
| Red release | R1-R4 | Release exact Section 4 correction |
| Smoke edit | Tester | Sections 4.1-4.5 only |
| Combined static | R1-R4 | Review frozen two-file identity |
| Same-policy green | Tester | Section 6 once |
| Gate B | R1-R4 | Technical acceptance on frozen evidence |

Coordinator performs governance verification and casts no technical vote.

## 10. Mandatory Gate A questions

Reviewers must answer every question on the identical frozen plan.

1. Does package.json directly register the selected Shove smoke and include it
   in live:check?
2. Is there exactly one Promise-valued wait in that smoke?
3. Does installed Playwright branch on the immediate Promise object?
4. Can an eventual false complete without another poll?
5. Is the selected condition exactly input state, active action row, and zero
   presentation backlog?
6. Do later action checks fail to prove the named readiness boundary?
7. Is the checker rule target-local and ordered after the four accepted rules?
8. Does the stale call deterministically produce the sole exact diagnostic?
9. Is first red entirely static and service-free?
10. Does ordinary page.evaluate return the resolved Boolean?
11. Does the helper use one absolute Node-monotonic deadline?
12. Does every evaluation use fresh remaining budget and a cleared timer?
13. Do late truth, repeated false, stall, and post-expiry behavior fail closed?
14. Is runtimeModuleUrls an ordinary serializable page argument?
15. Does the replacement preserve the exact existing predicate?
16. Does the independent snapshot prove state, active/action identity, and
    backlog before Shove behavior?
17. Is a brand-new standalone local profile character-empty by construction?
18. Do one requirement and disabled New Match exclude ambient profile state?
19. Does the fixture use one real exact-path character POST without body/DTO,
    route, seed, or store authority?
20. Do the card name/ID, requirement removal, enabled New Match, sheet close,
    and request count provide truthful receipts?
21. Does the created card ID equal the only selected game-setup roster ID?
22. Does setting that member AI preserve the authored human Barbarian as the
    inherited Shove actor, with both controller states actually recorded and
    asserted?
23. Are all output additions actual DOM/network/helper/store observations?
24. Are Shove execution, approach, cue ownership, forced movement, cursor,
    backlog, faults, and browser finally frozen?
25. Do exactly the checker and selected smoke suffice?
26. Is focused tsc plus checker plus one registered smoke sufficient?
27. Is the direct no-force backend launch ownership-safe?
28. Is the recorded 300-second smoke session enforceably bounded?
29. Is teardown exclusive and are all retained roots protected?
30. Is runtime cost bounded and product hot-path cost zero?
31. Are the 13 remaining waits and unavailable-sentinel family explicitly
    open without being hidden?
32. Does the packet add no public contract, schema, persistence, dependency,
    framework, service, asset, screenshot, or parallel authority?
33. Is the strict claim limited to BUG-031 Stage 5 readiness rather than
    character creation, Shove, forced movement, or general presentation?
34. Is there any concrete false-red, false-green, cleanup, concurrency,
    performance, scope, contract, or human-decision blocker?

Only an unconditional approval on every answer contributes to Gate A.
