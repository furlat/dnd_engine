# Gameplay Regression Work Packet 016 — BUG-031 Stage 6 HUD Action Geometry Readiness Resolved Wait

Date: 2026-08-11
Owner: Planner / External Reviewer 1
Implementation owner: none; Tester owns both permitted files after governed release
Execution owner: Tester only after every required static sub-gate closes

## 0. Decision and boundary

WP-015 closed only the selected live-Shove Promise-valued readiness wait. The
refreshed inventory contains exactly thirteen remaining Promise-valued
`waitForFunction` call shapes:

- one in `hud-rpg-smoke.mjs`;
- two in `hosted-game-smoke.mjs`;
- three in `inventory-panel-smoke.mjs`;
- seven in `multi-character-live-smoke.mjs`.

This packet selects only the single call in the maintained HUD RPG smoke. If
accepted, twelve occurrences remain explicitly open.

The selected call waits for production `clientState === "my_turn_input"` and
at least one production action-bar geometry entry. It is Promise-valued and
has the same installed-Playwright one-shot defect already proven by WP-008
through WP-015.

The smoke also has two prerequisites that must be governed rather than
ignored:

1. a brand-new standalone profile contains no character, so the already
   accepted production-owned one-character prerequisite is required;
2. the smoke writes three PNG screenshots to repository-owned
   `agent_docs/assets` by default.

WP-016 preserves the default visual-review output behavior but adds one
test-only optional screenshot-directory environment override. The governed
run must point it to an exact directory below its fresh retained runtime. The
three existing repository screenshots are frozen and must remain byte- and
metadata-untouched.

Exactly two existing Tester files may change:

- `app/scripts/check-node-sources.mjs`;
- `app/scripts/hud-rpg-smoke.mjs`.

No production, package, Vite, Playwright, SDK, generated, backend, service,
schema, protocol, persistence, asset, dependency, public-contract, shared
framework, or second smoke edit exists.

### 0.1 Candidate triage and explicit deferral

- `hosted-game-smoke.mjs` remains deferred because its two waits require the
  real gateway plus per-game worker topology. No packet-local hosted launcher
  is authorized by this test-only seam.
- `inventory-panel-smoke.mjs` remains deferred because it combines three
  independent waits, a durable roster fixture, route-delayed equipment
  behavior, and six repository screenshot writes.
- `multi-character-live-smoke.mjs` remains deferred because it spans seven
  waits and independent multi-character roster, session, targeting,
  equipment, action, and handoff authorities.
- the absent `action.unavailable`, `item.unavailable`, `object.unavailable`,
  `reaction.unavailable`, and `condition.unavailable` family remains a
  separate multi-asset/content-design backlog. It is neither aliased nor
  claimed here.

### 0.2 Human authorization and progression

The human authorized automatic progression through bounded owner-correct
seams. This packet changes two Tester files and introduces no product behavior
choice, public contract, schema, persistence, dependency, framework, service,
or architecture expansion.

### 0.3 Strict claim

Successful Gate B may establish only:

> BUG-031 Stage 6: the maintained HUD RPG smoke is statically guarded against
> its single Promise-valued HUD admission wait and explicitly observes
> resolved `my_turn_input` plus a nonempty production action-bar geometry entry
> set on one fresh lawful character fixture before its inherited HUD layout
> receipt.

It does not claim character creation, HUD correctness, pixels, screenshots,
action behavior, layout correctness, presentation, replication, the remaining
twelve occurrences, the unavailable-sentinel family, or general product
correctness.

## 1. Frozen authority identity

Every identity is exact. Any mismatch fails intake closed. No refresh,
substitution, regeneration, or baseline carry is permitted.

### 1.1 Accepted predecessor and evidence

| Authority | Lines | SHA-256 |
|---|---:|---|
| `agent_working_folder_NOT_HUMAN_GUIDANCE/plans/GAMEPLAY_REGRESSION_WORK_PACKET_015_BUG_031_SHOVE_ACTION_READINESS_RESOLVED_WAIT_2026-08-11.md` | 588 | `4fec779661ed9f7682ce5bbb9718fd19e3e0bcb61cff60ee342c7d1bc630e489` |
| `/tmp/neurodragon-wp015-green-Qf3vLu/live-shove-presentation-smoke.stdout` | 5 | `fc6145681a4ec48e9110c0e811031d4a0505b5df58a114718614d4d6c416b846` |
| `/tmp/neurodragon-wp015-green-Qf3vLu/live-shove-presentation-smoke.stderr` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

All retained roots are immutable evidence and never packet state.

### 1.2 Mutable Tester baselines

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/scripts/check-node-sources.mjs` | 112 | `d0128975b28cc25079dea97a649e03097359969564cdad1a2b630602bce441b0` |
| `/home/tommaso/Dev/NeuroClient/app/scripts/hud-rpg-smoke.mjs` | 204 | `039319bea9a58899d9175e93e65cf6e56791cdd9b76cdd0527b5fad8078dd9de` |

The five accepted checker targets remain frozen:

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/scripts/turn-burst-smoke.mjs` | 336 | `3e71c47d90d983df2a88d5483f288454bf476e4b81cb1f3108f35c1660495420` |
| `/home/tommaso/Dev/NeuroClient/app/scripts/real-character-game-creation-live-smoke.mjs` | 528 | `01650889d45e6d77db0f96ee22bbfd84f99125592db88ca2be1dd68f81fdcd5a` |
| `/home/tommaso/Dev/NeuroClient/app/scripts/replication-smoke.mjs` | 406 | `078a4cccc8f6a72d71baa9f8b22dbd8fc20e49144a13a524e3c5e080059f5ca1` |
| `/home/tommaso/Dev/NeuroClient/app/scripts/live-subjective-actions-smoke.mjs` | 780 | `c04a200674d41e4b2711cfabc4a9870f93421a59d84380aac37fbaf72bb69fa4` |
| `/home/tommaso/Dev/NeuroClient/app/scripts/live-shove-presentation-smoke.mjs` | 752 | `bc538d0aace98039b2e912f7d1f99f15379f62effc95eebcb8def5d64900ceae` |

### 1.3 Package, helper, and Playwright authorities

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/package.json` | 165 | `36515d20ea94ebc0c49a47b79bd455fee0eddceea2eb5e52713163eff159d9e3` |
| `/home/tommaso/Dev/NeuroClient/app/vite.config.ts` | 235 | `7d70b9fae8cf5d4a8d38762865ac8f36adba1247721212fcb5b3d7455f247153` |
| `/home/tommaso/Dev/NeuroClient/app/scripts/player-identity.mjs` | 70 | `2196cf7af3841a88dc0396e99c38d041bf3ce4c7d07fc987c209a0d88843772c` |
| `/home/tommaso/Dev/NeuroClient/app/node_modules/playwright-core/package.json` | 48 | `d4b8727c495ff2632084e922ee1c7f19a608ed23d86e8f3b0ba0ff317eea58ec` |
| `/home/tommaso/Dev/NeuroClient/app/node_modules/playwright-core/lib/server/frames.js` | 1500 | `a0a5c3655b86edeb1e6acb8133d40769dda53c246340271251598dac5ff48594` |
| `/home/tommaso/Dev/NeuroClient/app/node_modules/playwright-core/lib/server/chromium/crExecutionContext.js` | 146 | `4b4da27c16c2ec7094dcc3cc78313eb9ac8f15a9ed3b7589118a883d6d339b7f` |

Installed Playwright is 1.59.1. No dependency action exists.

### 1.4 Frozen HUD and runtime owners

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/src/main.ts` | 636 | `e8749ccf14f3a5eed27b5d3fc8e5deff4dbbe3fc45062524eeeca787ec816440` |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/store.ts` | 431 | `b0c428f266cf3c23608143e3ee73fc048f82bfb0afb5ffee3e317b1aff859537` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/actionBar.ts` | 2429 | `0f741a9a0abcf69ff9d62ad2685ba052531d0b4ba842edcc5c72693c60a8f52e` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/animationCoveragePanel.ts` | 176 | `e99e949f4c8995437568f70665e10ec7a5823bff358ccb18703786a2dcf32c78` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/hudLayout.ts` | 197 | `e7dfdb2ef33df4a9c52645bb1cb63664cf107540f357ab8a1adc40a537a24960` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/tileInspector.ts` | 537 | `61077f70c5d86bee3167aef63987f12d59c2a8baf5ab938360ae9ea61218cda7` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/visibilityPanel.ts` | 158 | `d049e704ef5582ddc520a9287c1ce1763ae6bb7ba19a40d9cc044b8a3280a84a` |
| `/home/tommaso/Dev/NeuroClient/app/src/style.css` | 8710 | `55bf6a27b90aa40410c9acd716da0427f6345d8cd131603fe5725db2c59db019` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/rpgHud.css` | 721 | `f1abaf9411248b7410d9cd115ef401536b4737812eaeeed98b30106ca16612eb` |
| `/home/tommaso/Dev/NeuroClient/app/src/render/presentationDiagnostics.ts` | 1264 | `4271e3b7711b8964212f9d0994877768c386c1ac359b476f5c3b94d3d8233f69` |

### 1.5 Character, setup, service, and frozen screenshot authorities

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/src/ui/gameCreationReadiness.ts` | 38 | `1dd39360063376c67a8a028742e11fdab769c3888bd6b6599f5999498ea7c1ac` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/gameBrowser.ts` | 1097 | `6bf4ad5e856cd38ea671218b1e9d928d51e04bcc1c054329a587fef7b9cd896c` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/characterCreator.ts` | 2772 | `bb6365ca79164a13467699d2c3142134b61f71a3560b0ef89f5f31cd3f15e20b` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/characterSheet.ts` | 1266 | `9bdf076f1b1383e297143c044ff116b2f792c1ba1af994d29e731ebc6774ba0b` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/gameSetup.ts` | 2228 | `eba13f093bd5a8c6006e73d7b1918a1a1a9a7c64953adc20474d2e895baa17e1` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/gameSetupCharacterRoster.ts` | 347 | `6b666a0729d489088266b915b0f278e108e9f881bc5d6dc7368be6dc3cb57a20` |
| `/home/tommaso/Dev/NeuroClient/server.sh` | 19 | `fd4db2fc27366f963308a93dd6c07096566b8c58bb1515a4dfbc95e8e6f1a22a` |
| `server/event_server.py` | 6978 | `eb1f6e891bc4cb149c8f054bb8ae36e4df7f2a7a7d47e6cc91af2a3e7394cdc5` |
| `server/game_directory/local_profiles.py` | 420 | `7ce82baee1b1b413c1a5b35467489c52eae53d59fabe583446ac21fb856e0ade` |

Frozen repository screenshot bytes:

| File | Bytes | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/agent_docs/assets/hud-rpg-1440x1000.png` | 122347 | `6f19aa80faedd876d7d8e21c8c9f71fd199133e42b2afcb0ebf02ff361618a7d` |
| `/home/tommaso/Dev/NeuroClient/agent_docs/assets/hud-rpg-800x600.png` | 89277 | `4fe1e285f4637f0d7dbde6ae2a7dbdff09ea7e7a6086cb765a1096d5548e7f0a` |
| `/home/tommaso/Dev/NeuroClient/agent_docs/assets/hud-rpg-debug-hidden.png` | 49436 | `3f3703a4ee7c9029369bdefee2df42c2228bc2436c736308ec79b89e4bb22573` |

The three screenshot files are untracked but repository-owned evidence. Their
preflight stat metadata and bytes must remain unchanged. `server.sh` is
context only and must never be launched.

## 2. Causal finding

### 2.1 Installed Playwright behavior

Frozen Playwright invokes a `waitForFunction` predicate and branches on its
immediate return before later result adoption. An async predicate immediately
returns a truthy Promise object. Eventual false can therefore fulfill and
return the injected loop without another poll.

Ordinary Chromium `page.evaluate` uses `awaitPromise: true`, so explicit
Node-side polling observes the resolved serializable Boolean.

### 2.2 Selected stale wait

The HUD smoke contains exactly one Promise-valued `waitForFunction` call. It
occurs after Start Match and requires:

- production `clientState === "my_turn_input"`;
- `getActionBarDebugGeometry().entries` to have nonzero length.

One resolved false can currently complete it. The later tile attachment,
geometry reads, DOM visibility, screenshots, toggle checks, and layout
assertions can fail later, but none proves the named pre-HUD admission wait
repolled to resolved truth.

### 2.3 Fresh-character and artifact premises

A brand-new standalone root creates one local profile/principal/settings and
no character. The accepted real premade-character UI prerequisite is therefore
required before New Match.

The current output directory is `resolve("../agent_docs/assets")`. The smoke
writes exactly these successful-run names:

- `hud-rpg-1440x1000.png`;
- `hud-rpg-800x600.png`;
- `hud-rpg-debug-hidden.png`.

The default must remain unchanged for ordinary visual review. The governed run
must set `NEURODRAGON_HUD_SCREENSHOT_DIR` to an exact new directory below the
attempt root. No repository screenshot may be opened for write, removed,
renamed, or touched.

## 3. Checker-first natural red

### 3.1 Authorized checker block

After Gate A, Tester may first edit only `app/scripts/check-node-sources.mjs`.
Immediately after the accepted live-Shove block, add one target-local
path/read/regex rule for `scripts/hud-rpg-smoke.mjs` using:

`/\.waitForFunction\s*\(\s*async(?:\s+function\b|\s*\()/u`

and exact diagnostic:

`scripts/hud-rpg-smoke.mjs: Promise-valued waitForFunction predicate is forbidden; use explicit resolved page polling.`

Preserve the five accepted target blocks, recursive sorted `.mjs` traversal,
Node syntax checks, Vite diagnostics, failure aggregation, and success summary.
The rule reads only HUD and does not scan the remaining twelve occurrences.

### 3.2 Checker static sub-gate

The changed checker requires fresh isolated R1-R4 static approval. No command
is authorized before public 4/4 plus Coordinator verification.

### 3.3 Exact first red

Tester may then run once from NeuroClient root:

`npm --prefix app run node-sources:check`

Only nonzero with the sole exact Section 3.1 diagnostic is accepted. The
node-config prerequisite must pass. Any syntax, Vite, path, timeout,
predecessor-rule, or other error freezes. No service/browser/smoke starts.

### 3.4 Correction release

The exact red requires fresh R1-R4 causal approval before the HUD edit. The
checker freezes. The red releases only Section 4 and no execution.

## 4. Required HUD smoke correction

### 4.1 Governed screenshot output boundary

Change only the existing output-directory declaration to use:

`resolve(process.env.NEURODRAGON_HUD_SCREENSHOT_DIR ?? "../agent_docs/assets")`

The default path and three existing screenshot calls/names remain unchanged.
No other environment option, artifact owner, screenshot helper, image content
change, or cleanup behavior is authorized.

### 4.2 Real fresh-character prerequisite

After game-browser visibility and the inherited `ensurePlayerIdentity` call,
before the existing New Match click:

1. require exactly one visible create requirement;
2. record/require actual disabled New Match;
3. observe only POST plus exact parsed pathname
   `/api/directory/characters`;
4. use the real premade creator with fixed name `HUD Readiness Fixture`, arm
   the response wait before one create click, require success and creator
   detachment;
5. require exactly one selected card, exact rendered strong name, and non-null
   actual `data-select-character` ID;
6. require zero remaining requirements and enabled New Match;
7. require the real sheet visible, close it through the production control,
   require detachment, and require request count one;
8. click the same production New Match control;
9. require exactly one selected roster member and exact created-card/roster ID
   equality;
10. click that exact member's human controller, record its actual active state,
    and require `human` before the inherited opening/Start Match path.

No response body/DTO, interception, seed, retained profile, mock, or direct
store/directory mutation exists.

### 4.3 File-local resolved-poll helper

Add one file-local helper:

`waitForResolvedPageCondition(targetPage, evaluateCondition, evaluateArgument, timeoutMs, label, pollIntervalMs = 50)`

It must use one Node `performance.now()` start and absolute deadline; reject
before an expired evaluation; count one attempt per actual evaluation; race
one `targetPage.evaluate(evaluateCondition, evaluateArgument)` against one
timer for the current remaining budget; clear the timer in `finally`; reject
truth settling at/after deadline; bound false delay by
`min(50ms, pollIntervalMs, remaining)`; begin no post-expiry evaluation; retain
O(1) state; and use exact timeout:

`<label> did not resolve within <timeoutMs>ms`.

### 4.4 Selected wait replacement and independent receipt

Replace only the selected async wait with the helper using:

- `undefined` as the serializable page argument;
- timeout `30_000`;
- label `HUD action geometry readiness`;
- the exact existing direct production imports and predicate.

Immediately afterward, a separate `page.evaluate` must record actual:

- `clientState`;
- `activeEntityUuid`;
- `actionEntryCount` from production action-bar debug geometry.

Require exact `my_turn_input` and `actionEntryCount > 0` before tile/HUD
behavior. The active identity is recorded only as an additional observation;
it is not asserted and does not become a new predicate authority.

### 4.5 Actual output evidence

Add exactly one final single-line JSON object before the existing pass line,
only after all inherited failures remain empty. It may contain only actual:

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
- `hudReadinessWait`;
- `hudReadinessState`;
- `hudScreenshotOutputDir`.

The fixed name and output directory are input identities but must be proven by
rendered DOM and the governed process environment/artifact boundary. Every
status, count, ID, controller, state, geometry count, attempt, and elapsed
value is observed.

### 4.6 Frozen inherited behavior

Outside Sections 4.1-4.5 preserve:

- identity helper and browser/pageerror/selected console collection;
- all rectangle/selection geometry owners and overlap/bounds checks;
- tile inspector and target selection setup;
- action-bar debug geometry ownership;
- desktop and compact viewport validation;
- diagnostic toggle hide/restore and action-bar reclaim checks;
- condition-icon load and frame containment checks;
- the three screenshot calls, names, clip behavior, and ordering;
- failure aggregation, existing pass text, and browser close in `finally`.

No screenshot comparison, pixel claim, store mutation beyond the inherited
selection setup, timing workaround, extra wait, fault filter, or diagnostic
clear is authorized.

## 5. Combined static review

Fresh R1-R4 must prove:

1. only checker and HUD smoke changed;
2. checker predecessors/inherited behavior remain frozen;
3. no Promise-valued wait remains in HUD;
4. screenshot override preserves the default and changes no screenshot call;
5. fixture/card/roster/controller receipts are production-owned and actual;
6. helper deadline/race behavior is exact;
7. independent state/active/geometry evidence precedes HUD behavior;
8. every inherited HUD assertion/error/finally path is unchanged;
9. no repository screenshot or third file changed;
10. twelve waits and sentinel backlog remain open.

No execution before public static 4/4 plus Coordinator verification.

## 6. Governed same-policy green

### 6.1 Frozen prerequisites

From NeuroClient root, exactly once each, stop on nonzero:

1. `./app/node_modules/.bin/tsc --noEmit -p ./app/tsconfig.json`;
2. `npm --prefix app run node-sources:check`.

### 6.2 Fresh owned stack and screenshot boundary

Only after both pass:

1. prove ports 8000/5173 and matching packet processes absent;
2. capture byte hashes and stat metadata for all three frozen repository HUD
   screenshots;
3. create one brand-new `/tmp` runtime root and exact child directory
   `<fresh-root>/hud-rpg-screenshots`;
4. start one owned direct backend without `--force`:

   `DND_LOCAL_PROFILE_RUNTIME_ROOT=<fresh-root> ./.venv/bin/python -m server.event_server --host 127.0.0.1 --port 8000`

5. require direct capabilities HTTP200 with `server_mode=standalone` within
   90 seconds;
6. start one owned Vite and require exact-root HTTP200 in a bounded window;
7. run once as one recorded session under exact 300 seconds:

   `NEURODRAGON_HUD_SCREENSHOT_DIR=<fresh-root>/hud-rpg-screenshots npm --prefix app run hud-rpg:smoke`

A bind race freezes on ordinary failure and may never signal another listener.

### 6.3 Required green evidence

Require exit0, no timeout, exactly one final JSON, and:

- one initial requirement/disabled New Match;
- one successful character POST/card/name/ID, requirement0/enabled/sheet close;
- exact card/sole-roster ID equality and actual human controller;
- helper attempts/elapsed and independent input/nonempty-entry receipt, with
  active identity retained only as an observation;
- all inherited desktop/compact/toggle/geometry/icon/layout checks green;
- zero page/selected-console runtime errors;
- exactly three nonempty PNG files with the frozen names under the exact fresh
  screenshot directory;
- zero file below repository `agent_docs/assets` opened for write, and exact
  pre/post bytes plus stat metadata for all three frozen repository images.

No pixel or screenshot-content correctness claim follows from file existence.

### 6.4 Teardown

On every exit:

1. allow browser `finally` first;
2. terminate/join only a still-active recorded smoke tree;
3. stop/join only owned Vite/backend trees;
4. prove ports closed and recorded PIDs/children/matching processes absent;
5. retain the fresh root and its three new screenshot artifacts;
6. re-prove all repository screenshot bytes/stat metadata unchanged;
7. never touch WP-015 or any earlier retained root.

Any mismatch freezes without rerun or cleanup expansion.

## 7. Gate B acceptance

Fresh R1-R4 must assess same-policy red-to-green causality; actual fixture and
resolved readiness; inherited HUD evidence; screenshot isolation; service and
process ownership; cleanup; performance/contracts; and strict claim scope.
Gate B closes only at public 4/4 plus Coordinator verification.

## 8. Performance and architecture

The checker adds one constant read/regex. The smoke adds one bounded real
character creation, one O(1) resolved poll with one evaluation/timer, one
snapshot, and one test-only output-path lookup. Existing HUD geometry reads and
three screenshots are not duplicated.

There is no product hot-path, renderer, backend, schema, persistence, wire,
SDK, public-contract, dependency, package, service, or framework change. The
environment variable is private test-process configuration and preserves the
existing default.

## 9. Gate and owner matrix

| Stage | Owner | Authorized work |
|---|---|---|
| Plan Gate A | R1-R4 | Review this exact frozen plan |
| Checker edit | Tester | Section 3.1 only |
| Checker static | R1-R4 | Review changed checker |
| First red | Tester | Section 3.3 once |
| Red release | R1-R4 | Release exact Section 4 |
| HUD edit | Tester | Sections 4.1-4.5 only |
| Combined static | R1-R4 | Review frozen two-file identity |
| Same-policy green | Tester | Section 6 once |
| Gate B | R1-R4 | Review frozen evidence |

Coordinator verifies governance and casts no technical vote.

## 10. Mandatory Gate A questions

1. Does package.json directly register HUD RPG smoke and include it in the
   ordinary browser check?
2. Is there exactly one Promise-valued wait in HUD?
3. Does installed Playwright branch on its immediate Promise object?
4. Can eventual false complete without another poll?
5. Is the exact predicate input state plus nonempty action-bar geometry?
6. Do later HUD assertions fail to prove that admission boundary?
7. Is the checker target-local and ordered after five accepted rules?
8. Does stale HUD deterministically produce the sole exact diagnostic?
9. Is first red static and service-free?
10. Does ordinary page.evaluate return the resolved Boolean?
11. Does the helper own one absolute Node-monotonic deadline?
12. Do current-budget race, timer clearing, late truth, stall, repeated false,
    and no-post-expiry behavior fail closed?
13. Does replacement preserve the exact existing imports and predicate?
14. Does the independent snapshot prove state and entry count before HUD
    behavior while retaining active identity only as a non-authoritative
    observation?
15. Is the fresh standalone profile character-empty by construction?
16. Do requirement1 and disabled New Match exclude ambient state?
17. Is one real exact-path POST used without body/DTO/interception/seed/store
    authority?
18. Do exact card/name/ID, requirement removal, enabled New Match, sheet close,
    and request count provide truthful receipts?
19. Does created card ID equal the sole roster ID and actual controller human?
20. Does the screenshot override preserve the existing default?
21. Does the governed environment constrain every new screenshot below the
    fresh root?
22. Are the three repository images frozen by bytes and stat metadata?
23. Are all output fields observed, with fixed inputs independently proven?
24. Are geometry, layout, toggle, icon, screenshot, failure, and finally paths
    frozen?
25. Do exactly checker and HUD smoke suffice?
26. Is focused tsc/checker/one registered HUD smoke sufficient?
27. Is the no-force launch ownership-safe and the 300-second owner enforceable?
28. Is teardown exclusive, are fresh artifacts retained, and prior roots plus
    repository screenshots protected?
29. Is cost bounded and product hot-path cost zero?
30. Are hosted2, inventory3, multi-character7—twelve total—and sentinel assets
    explicitly open?
31. Does the packet add no public contract, schema, persistence, dependency,
    framework, service, asset, screenshot-content, or parallel authority?
32. Is the claim strictly BUG-031 Stage 6 readiness rather than HUD, pixels,
    layout, action, presentation, or product correctness?
33. Is there any concrete false-red, false-green, cleanup, artifact,
    concurrency, performance, scope, contract, or human-decision blocker?

Only unconditional approval on every answer contributes to Gate A.
