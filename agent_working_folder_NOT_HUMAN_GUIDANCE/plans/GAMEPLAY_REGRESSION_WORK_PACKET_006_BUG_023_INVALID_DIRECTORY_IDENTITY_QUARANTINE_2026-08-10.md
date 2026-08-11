# Gameplay Regression Work Packet 006

## BUG-023 Stage 1: malformed persisted directory identity quarantine

Revision: **3 — real gateway service and deterministic inherited 404 prerequisite**

Date: 2026-08-10  
Owner model: Planner -> External Review R1-R4 -> Coordinator -> Tester ->
Implementation -> External Review R1-R4 -> Coordinator  
Execution state at Revision 3 intake: **fresh Gate A only; no source/test edit
or command is authorized by this artifact**

---

## 0. Decision and packet boundary

WP-005 closed BUG-022's separate pre-try presentation-persistence storage
denial boundary. The next bounded startup seam is BUG-023 Stage 1.

The current gateway directory identity owner reads one persisted
`PlayerIdentityResponse` from the exact key
`neuroclient.player.identity.v2`. When the stored JSON is syntactically or
contractually invalid, `loadDirectoryIdentity` deliberately throws:

`Stored player identity at neuroclient.player.identity.v2 is invalid; refusing to create a replacement identity.`

That throw occurs during ordinary directory discovery. The current main
startup owner catches it and mounts the generic startup-failure panel. The
application therefore still requires manual browser-storage repair even
though the invalid value has no lawful authentication authority.

The smallest truthful correction is not a general storage migration and does
not create a replacement principal. The existing pre-parse owner must remove
only the exact invalid identity value and return `null`. Ordinary gateway
startup then presents the existing player-identification form. The user must
explicitly identify again before any authenticated directory request occurs.

This packet is limited to:

- one production file:
  `app/src/api/directoryIdentity.ts`;
- one existing registered Tester file:
  `app/scripts/startup-transport-failure-smoke.mjs`;
- one malformed/schema-invalid value under the exact maintained identity key;
- automatic quarantine of only that exact value;
- anonymous gateway startup with no automatic replacement identity.

It does not change or claim:

- the already-existing exact profile-404 stale-principal cleanup in
  `gameDirectory.ts`;
- valid current `PlayerIdentityResponse` persistence;
- selected-character keys, because a malformed identity supplies no
  authenticated principal ID with which to associate one;
- presentation ledger/archive/fault persistence, already owned by the
  presentation persistence cut and WP-005;
- storage `SecurityError`/`QuotaExceededError` handling, already owned by
  WP-005;
- a prefix scan, global storage clear, cache migration, retry, fallback
  principal, or automatic player creation;
- backend source, generated SDK, wire, schema, public contract, service-worker,
  IndexedDB, Studio, gameplay, or Pixi behavior;
- BUG-023 beyond this malformed persisted gateway identity stage.

No material scope expansion or human design decision is implicated. The user
already required stale startup state to recover rather than demand manual
database deletion. This packet applies that direction at the one current
pre-parse owner without inventing new authority.

### 0.1 Revision 2 blocker receipt

The first governed first-red attempt stopped before Vite or Tester because the
direct-backend readiness observer used the Vite-only `/api` prefix. The fresh
corrected retry used exact direct-backend readiness URL
`http://127.0.0.1:8000/server/capabilities`, received HTTP 200, started one
owned Vite, and invoked the frozen Tester once.

That retry stopped before the new WP-006 case. The inherited stale-profile
case timed out waiting for `[data-testid="player-identity-form"]` after its
404 reload. Static source ownership explains the blocker:

- the fresh owned backend advertises standalone topology;
- the inherited fixture navigated before installing any gateway capability
  route;
- it created a gateway identity only conditionally if a player-identity form
  happened to exist;
- standalone discovery lawfully supplies `principalId` from the standalone
  local profile, not from `loadDirectoryIdentity()`;
- `refreshCharacterProfile()` clears a deleted credential and returns an
  anonymous identity form on HTTP 404 only when `context.serverMode` is
  `gateway` and `context.identity` is non-null.

The observed inherited timeout is therefore a missing fixture precondition,
not WP-006 source evidence and not a failure of the existing gateway 404
owner. The new malformed-identity case and its accepted natural red were
unreached. Both attempts performed complete owned teardown and changed no
source or test identity.

Revision 2 authorizes only one deterministic correction inside the already
owned Tester file: the inherited stale-profile page must force generated-valid
gateway capabilities before its first ordinary-root navigation, create a real
identity through the existing form and real identify endpoint, intercept one
exact profile request with HTTP 404, and prove the existing gateway cleanup
before the WP-006 case begins. It does not change production scope, the new
malformed-identity case, or the natural-red message.

### 0.2 Revision 3 service correction

Fresh Revision 2 review rejected that protocol before any Tester edit or
execution. `server.sh` starts `server.event_server`, whose capability response
truthfully declares standalone topology. A page-local gateway capability
response can change the frontend branch, but it cannot add gateway-only
backend routes. In particular:

- the production player form submits through the generated client to
  `POST /directory/players/identify`;
- the standalone event server's shared directory router does not own that
  endpoint;
- the endpoint exists on `server.game_gateway:app`;
- therefore a real form submission against `server.sh` would receive HTTP 404
  before a generated-valid gateway identity could be returned or persisted.

Revision 3 supersedes Revision 2's page-only topology correction. The governed
one-backend protocol must start the existing real gateway ASGI application,
with its database, hosted runtime, artifacts, and capability pepper isolated
under the fresh attempt. The inherited stale-profile page then consumes the
gateway's real `/server/capabilities`, real public catalog, and real identify
endpoint. No capability route is installed for that inherited case. Only its
later exact `/directory/players/me` 404 is intercepted to exercise the
already-existing decoded-stale-credential cleanup.

This is test orchestration using an existing supported deployment, not a
backend source change or material architecture expansion. It avoids both
false alternatives rejected by the packet: hand-authoring a valid
`PlayerIdentityResponse` and mocking `/directory/players/identify`.

---

## 1. Frozen identity

### 1.1 Program authorities

| Authority | Lines | SHA-256 | Role |
| --- | ---: | --- | --- |
| `agent_working_folder_NOT_HUMAN_GUIDANCE/USER_REPORTED_GAMEPLAY_AND_PRODUCT_REGRESSION_LEDGER_2026-08-10.md` | 607 | `9ac0633322a2203222076a54bd2a8edb23c10e17b49b84562a77d971b922a805` | BUG-023 user expectation and captured stale-principal/startup failures |
| `agent_working_folder_NOT_HUMAN_GUIDANCE/plans/CURRENT_GAMEPLAY_STABILIZATION_MANIFEST_2026-08-10.md` | 798 | `0048c7192773c2a0086a540fabda89023830408ad7ecaf9894c6e34e7529fe5b` | current startup/persistence boundary and remaining work |
| `agent_working_folder_NOT_HUMAN_GUIDANCE/plans/GAMEPLAY_REGRESSION_STATIC_CAUSAL_STUDY_AND_WORK_PACKET_001_2026-08-10.md` | 767 | `ede1cc4b074ed0bebc104f13197bf02b80ee9cca5311c804a9f29ef7f6d14eff` | BUG-023 current-source classification |
| `agent_working_folder_NOT_HUMAN_GUIDANCE/plans/GAMEPLAY_REGRESSION_WORK_PACKET_005_BUG_022_PRETRY_STORAGE_RECOVERY_2026-08-10.md` | 726 | `6217880b28296265073c4cac91fa5727cc648a9bff3ec7e9fb1729bc57b6c633` | adjacent accepted storage-denial boundary and non-goals |

### 1.2 Primary mutable baselines

| File | Lines | SHA-256 | Proposed owner |
| --- | ---: | --- | --- |
| `/home/tommaso/Dev/NeuroClient/app/src/api/directoryIdentity.ts` | 73 | `567fafa197701a484dcdede1d2396cfee03e6e893856a861b08814afbbef7411` | Implementation only |
| `/home/tommaso/Dev/NeuroClient/app/scripts/startup-transport-failure-smoke.mjs` | 293 | `4ff1611e7685c4b08797bd5e7b9449953d1473da8f1d6f8a33db30e45d880d78` | Tester only; Revision 1 WP-006 append is frozen while the inherited prerequisite is corrected |

The registered smoke before any WP-006 Tester work was 164 lines / SHA-256
`279c7cd8b23d162016cae89b44c5be2422ef8cd2efa9b09535f781d6a0e94c61`.
Revision 2 reviewers must inspect the complete current file and both the
original +129/-0 WP-006 append and the proposed inherited-fixture correction;
no Revision 1 vote carries forward.

### 1.3 Frozen supporting production/package authorities

| File | Lines | SHA-256 | Why frozen |
| --- | ---: | --- | --- |
| `/home/tommaso/Dev/NeuroClient/app/src/api/gameDirectory.ts` | 961 | `7c302315a8da021fb7652baf09d2d5c9575cd82893fe15729a80a85968fe6560` | sole directory discovery/profile/404 cleanup owner |
| `/home/tommaso/Dev/NeuroClient/app/src/main.ts` | 636 | `e8749ccf14f3a5eed27b5d3fc8e5deff4dbbe3fc45062524eeeca787ec816440` | accepted WP-005 startup recovery owner |
| `/home/tommaso/Dev/NeuroClient/app/src/errorText.ts` | 109 | `5d64b37c7c0281c8ec228d30a73d82a6c50628126f5b2e8c96c203bcf15fa77f` | error serialization remains unchanged |
| `/home/tommaso/Dev/NeuroClient/app/index.html` | 15 | `06d0f1e2a0be03f19ce4db213fa79929063f09feff201f09a9d30dc9b2025baf` | ordinary root and predeclared UI root |
| `/home/tommaso/Dev/NeuroClient/app/package.json` | 165 | `36515d20ea94ebc0c49a47b79bd455fee0eddceea2eb5e52713163eff159d9e3` | registered smoke command; no package edit |
| `sdk/typescript/src/client.ts` | 302 | `54643b9af5e6d1cae8d3ce91beb896419e0dc1c054e4bfc93a949f635cd9434c` | generated-model capability client |
| `sdk/typescript/src/directoryClient.ts` | 1016 | `f9f839cb1376c5a19611ea6d62c34591eb16c04acce95c694973ff093f0b5648` | generated-model directory request owner |
| `sdk/typescript/src/generated/contracts.generated.ts` | 7860 | `1d5da717cac4aa767bf87b789336b33649cf5e9567261ac71d31b069716a88b5` | `PlayerIdentityResponse` and capability schema authority |
| `server/game_gateway.py` | 2732 | `6f950eef1cf0fd94c23408f48462b9af5611b5f3d69641c2a1dc8ca087ca87af` | existing gateway capability/identify/directory owner; execution fixture only |
| `server/hosted_worker.py` | 599 | `f9ddd961c358d556718367690ad893a0fbd7d0f82bc168ef7f0734fae39173fc` | gateway-owned child lifecycle; frozen |
| `server/game_creation_preview.py` | 360 | `8f432d272f774b6e954e9e37b0b214a89ad08d22b243086cca1e7bd05db54957` | gateway lifespan preview child; frozen and included in teardown proof |
| `server/MULTI_GAME_GATEWAY.md` | 117 | `b4dbb526d197b3f315cf0e95caa85b53a037931107c9721214442278494501e6` | supported one-worker gateway launch authority |
| `/home/tommaso/Dev/NeuroClient/server.sh` | 19 | `fd4db2fc27366f963308a93dd6c07096566b8c58bb1515a4dfbc95e8e6f1a22a` | proves prior standalone-only orchestration; not used by Revision 3 |

Every identity above must be re-matched at each public sub-gate. Additional
dirty worktree paths are pre-existing shared work and must not be attributed
to WP-006 without exact evidence.

---

## 2. Current causal boundary

### 2.1 One persisted identity owner

`directoryIdentity.ts` owns the exact keys and the storage read/write/remove
operations for:

- `neuroclient.player.identity.v2` in local storage;
- `neuroclient.client-instance.v1` in session storage;
- per-principal selected-character keys.

`loadDirectoryIdentity` performs exactly:

1. `storage.getItem(IDENTITY_STORAGE_KEY)`;
2. null -> anonymous return;
3. `parseJson(stored)`;
4. generated-SDK `decodeModel("PlayerIdentityResponse", ...)`;
5. any parse/decode failure -> a new generic error.

The failed value remains in storage. Every later ordinary root repeats the
same failure.

### 2.2 Gateway discovery order

`gameDirectory.ts::discoverDirectory`:

1. obtains generated-SDK server capabilities;
2. when `server_mode === "gateway"`, invokes `loadDirectoryIdentity()`;
3. only afterward begins catalog/local-profile reads;
4. derives the principal ID only from a valid stored identity or standalone
   profile;
5. invokes authenticated profile/resource reads only for a non-null principal.

Therefore returning `null` after exact invalid-key quarantine has a complete
existing consumer meaning: anonymous gateway directory. It does not require a
new DTO, sentinel, status enum, route, or UI state.

### 2.3 Existing stale-but-decodable 404 behavior

`refreshCharacterProfile` already owns a different case. For a decoded gateway
identity whose exact profile request returns HTTP 404, it:

- knows the authenticated principal ID;
- clears the exact identity key;
- clears that principal's selected-character key;
- resets directory read-model state;
- returns to anonymous directory startup;
- suppresses later authenticated saved-resource reads.

WP-006 must not duplicate, move, or broaden that owner. Malformed identity data
has no validated principal ID, so a selected-character prefix scan would be
invented authority.

### 2.4 WP-005 interaction

If the exact quarantine `removeItem` itself throws a standard browser-storage
denial, that exception must remain uncaught in `directoryIdentity.ts`.
WP-005's existing startup catch/classifier then mounts the truthful storage
failure panel and stops. Continuing anonymously while the invalid key could
not be removed would recreate the failure on reload and falsely claim repair.

---

## 3. Accepted receipt

For one schema-invalid persisted directory identity on a gateway root load:

1. generated-SDK decode remains the sole validity authority;
2. the exact invalid identity key is removed once;
3. no other local/session key is touched;
4. the loader returns `null`;
5. ordinary directory discovery continues anonymously;
6. the existing player-identification form appears;
7. no profile or identify request uses the invalid value;
8. no automatic replacement principal is created;
9. no startup failure panel or page error appears.

This is quarantine, not fallback authentication.

---

## 4. Tester-first algorithm

### 4.1 File and placement

Tester edits only:

`app/scripts/startup-transport-failure-smoke.mjs`.

Preserve every inherited transport classification, runtime-route,
diagnostics, and cleanup assertion. Correct only the topology/admission proof
of the inherited stale-profile-404 case as specified in Section 4.1.1. Keep
the Revision 1 malformed-identity case otherwise byte-identical and only after
the corrected inherited stale-deleted-profile case passes and before the final
summary.

### 4.1.1 Deterministic inherited gateway-404 prerequisite

The stale-profile page must remain a fresh ordinary-root page and must use the
real production discovery, generated decoder, identify UI, and governed real
gateway backend. Before its first navigation:

1. attach its existing `pageerror` recorder;
2. do not route capabilities, catalog, identify, or another topology/identity
   endpoint; ordinary root must consume the real gateway response.

After the first navigation:

1. require exactly one visible `[data-testid="player-identity-form"]` instead
   of conditionally skipping identity creation;
2. fill the existing player-name field, submit the real production form, and
   wait for `[data-testid="change-player"]`, proving that the owned backend
   returned and production persisted a generated-valid gateway identity;
3. install an exact page-local route for `/api/directory/players/me`, record
   its invocation count, and fulfill it with the existing HTTP 404 fixture;
4. reload the same ordinary root;
5. require the identity form to reappear, the exact profile-404 route count to
   equal one, the persisted identity key to be `null`, zero startup-failure
   panels, and zero page errors.

The one page-local profile route and the page must be owned by one case-local
`try/finally`; remove the installed route before closing the page. The fixture
must not seed or hand-author a valid `PlayerIdentityResponse`, invoke the
loader/discovery/cleanup helpers directly, change production, or mock the
catalog or identify endpoint. The real form submission supplies the valid
credential; production remains sole identity and HTTP-404 cleanup authority.

This is an inherited-fixture determinism correction, not a new WP-006 claim.
It proves the existing stale decoded gateway credential behavior before the
malformed pre-decode identity case is admitted.

### 4.2 Fresh ordinary-root page

Create one fresh browser page in a case-local `try/finally`.

Before navigation:

1. attach a `pageerror` recorder;
2. attach a request recorder which counts:
   - `/api/directory/players/me`;
   - `/api/directory/players/identify`;
3. install one `addInitScript` which uses the original storage setter to place:
   - one syntactically valid but generated-contract-invalid opaque JSON object
     at exact key `neuroclient.player.identity.v2`;
   - one unrelated sentinel at exact key
     `neuroclient.bug-023.unrelated-identity-sentinel`;
4. route only `/api/server/capabilities` to one generated-contract-valid
   gateway capability response:

```json
{
  "server_mode": "gateway",
  "game_directory_enabled": true,
  "persistent_game_history": true,
  "isolated_game_workers": true
}
```

The case must not import/call `loadDirectoryIdentity`, `discoverDirectory`,
`showStartupFailure`, or any future quarantine helper directly. It must use
ordinary `page.goto(baseUrl, {waitUntil: "domcontentloaded"})`.

The real owned backend continues to serve the existing character-creation
catalog. The capability route changes only the topology for this fresh page so
the maintained gateway identity loader is necessarily reached.

### 4.3 Bounded admission observation

Wait a fixed bounded interval for the first of:

- `[data-testid="player-identity-form"]`;
- `[data-startup-failure="true"]`.

Do not treat a timeout, navigation error, backend/catalog error, or unrelated
panel as the accepted red.

After one of those surfaces appears, the first new assertion must be:

`invalid stored directory identity crashed startup instead of being quarantined`

It passes only when the startup-failure panel count is zero.

Before emitting that exact natural red when a panel is present, the Tester
must parse the existing structured startup diagnostic and require:

- zero page errors; and
- `diagnostic.error.message` contains the exact current owner boundary:
  `Stored player identity at neuroclient.player.identity.v2 is invalid; refusing to create a replacement identity.`

If a panel instead reports catalog, route, backend, Vite, navigation, or any
other failure, stop with a distinct fixture/boundary assertion. This
conditional diagnostic prerequisite is not a green requirement to keep a
failure panel; it only proves that the frozen natural-red panel was caused by
the exact identity decoder before the panel-count assertion rejects it.

On the frozen production baseline:

- generated-SDK decode rejects the stored object;
- `loadDirectoryIdentity` throws its current wrapped error;
- main's existing recoverable startup catch mounts the generic panel;
- the structured diagnostic contains the exact invalid-identity owner message
  and no page error;
- the exact new assertion fails;
- no later green-only assertion or final summary is claimed reached.

### 4.4 Green-only assertions

After the natural-red boundary passes, require:

- exactly one visible player-identification form;
- zero startup-failure panels;
- exact identity-key value is `null`;
- exact unrelated sentinel value is unchanged;
- zero `/api/directory/players/me` requests;
- zero `/api/directory/players/identify` requests;
- zero page errors.

The zero identify request proves that returning anonymous did not silently
mint/reidentify a principal. The user-facing form owns the next action.

Return actual evidence:

- identity form count;
- failure panel count;
- stored identity value after startup;
- unrelated sentinel value after startup;
- profile-request count;
- identify-request count;
- page-error count.

Add those actual values to the final smoke summary. Do not emit hard-coded pass
booleans.

### 4.5 Case isolation and cleanup

- Use a fresh page/context realm, separate from the inherited pages.
- Route capabilities only on that page.
- Remove the page route in the case-local `finally` if it was installed.
- Close the page in the case-local `finally`, including on natural red.
- Preserve the outer browser `finally`.
- Do not clear shared storage or mutate another page/context.

---

## 5. Production algorithm

### 5.1 Exact edit

Implementation edits only:

`app/src/api/directoryIdentity.ts`.

In `loadDirectoryIdentity`, preserve:

- the exact `storage.getItem` call;
- the null return;
- generated-SDK `parseJson` and `decodeModel` as sole validity authority;
- the exact success return.

Replace only the current parse/decode catch behavior. On caught invalid stored
identity data:

1. call `storage.removeItem(IDENTITY_STORAGE_KEY)` exactly once;
2. return `null`.

### 5.2 Failure safety

Do not catch a failure thrown by `removeItem`. If exact quarantine cannot be
completed, the original storage failure must reach the existing WP-005
startup-recovery UI.

Do not:

- clear localStorage/sessionStorage;
- scan keys or prefixes;
- remove selected-character keys;
- remove presentation ledger/archive/fault keys;
- retry parse/decode;
- generate or request a new identity;
- add a tombstone, quarantine copy, telemetry schema, or return discriminator;
- log or retain the invalid raw credential;
- change `saveDirectoryIdentity`, `clearDirectoryIdentity`, client-instance,
  or selected-character functions.

### 5.3 Why no additional owner is needed

`loadDirectoryIdentity` already owns:

- the exact identity key;
- the pre-parse storage value;
- generated-SDK validity admission;
- the anonymous `null` receipt.

No other production file can remove the invalid value more precisely without
duplicating that authority. `gameDirectory.ts` already understands `null` and
needs no branch. UI already renders the identity form for anonymous gateway
state. Main already owns later startup recovery.

---

## 6. Red-to-green discrimination

### 6.1 Unchanged production

The frozen Tester must establish:

- every inherited startup-transport case passes;
- the exact gateway capability route is used;
- the schema-invalid identity is present before main startup;
- ordinary root reaches the current identity decoder;
- the generic startup-failure panel appears;
- the first new assertion fails exactly:
  `invalid stored directory identity crashed startup instead of being quarantined`.

Any earlier inherited, service, route, catalog, Vite, navigation, or timeout
failure is a blocker, not an accepted red.

### 6.2 Correct production

With the one-file correction:

- the same opaque invalid value fails generated-SDK decode;
- only the exact identity key is removed;
- anonymous gateway startup continues;
- the real player-identification form appears;
- no failure panel/page error appears;
- no profile or identify request is sent;
- the unrelated sentinel remains byte-equal;
- inherited backend transport and stale-profile-404 behavior remains green.

### 6.3 False greens excluded

The test cannot turn green through:

- direct invocation of the loader or UI;
- hand-authoring a `DirectoryContext`;
- suppressing the gateway capability path;
- returning a replacement identity;
- clearing all storage;
- deleting the unrelated sentinel;
- sending the invalid credential to `/players/me`;
- automatically calling `/players/identify`;
- showing a generic or storage failure panel;
- swallowing a page error;
- skipping the real directory catalog/UI path.

---

## 7. Execution protocol

No command is authorized until the relevant frozen identity receives fresh
isolated R1-R4 approval plus Coordinator verification.

### 7.1 Tester edit-only

After Gate A 4/4 and Coordinator verification:

- Tester may edit only
  `app/scripts/startup-transport-failure-smoke.mjs`;
- Tester runs nothing;
- Tester returns exact diff, line count, and SHA-256;
- changed Tester identity receives fresh R1-R4 static review.

### 7.2 One-shot natural red

After Tester static approval and Coordinator verification:

1. from NeuroClient root run exactly once:
   `./app/node_modules/.bin/tsc --noEmit -p ./app/tsconfig.json`;
2. only if zero, preflight ports 8000 and 5173 free;
3. create one fresh `/tmp` attempt root;
4. from the dnd_engine root start exactly one owned gateway process with:
   - `DND_DIRECTORY_DATABASE=<fresh>/game-directory.sqlite3`;
   - `DND_HOSTED_RUNTIME_ROOT=<fresh>/hosted-games`;
   - `DND_GAME_ARTIFACT_ROOT=<fresh>/game-artifacts`;
   - one attempt-local non-production
     `DND_DIRECTORY_CAPABILITY_PEPPER` value;
   - `DND_HOSTED_WARM_WORKERS=0`, because this smoke creates no hosted game;
   - command `.venv/bin/uvicorn server.game_gateway:app --host 127.0.0.1
     --port 8000 --workers 1`;
5. probe exactly `http://127.0.0.1:8000/server/capabilities` with the accepted
   existing observer, a 90-second maximum, and require HTTP 200 plus
   `server_mode` equal to `gateway`;
6. only after backend readiness, start one owned
   `npm --prefix app run dev` and use bounded readiness;
7. run exactly once:
   `npm --prefix app run startup-transport-failure:smoke`;
8. inherited cases must pass, including the deterministic gateway identity
   creation, exactly one intercepted profile 404, and post-404 anonymous form;
   the only accepted red is exactly
   `invalid stored directory identity crashed startup instead of being quarantined`;
9. stop immediately on any other result;
10. always interrupt/join only owned Vite and gateway process trees, including
    the gateway lifespan's preview child, and prove ports/PIDs/children absent;
11. no edit, rerun, alternate probe/command, debug, formatter, workaround, or
    unrelated inspection.

### 7.3 Implementation edit-only

After the exact natural red receives fresh 4/4 release approval and
Coordinator verification:

- Implementation may inspect the accepted plan and production file;
- Implementation edits only `directoryIdentity.ts`;
- only read-only diff/wc/SHA evidence commands are allowed;
- no typecheck/test/build/service/browser/formatter/project execution;
- Tester remains byte-frozen.

### 7.4 One-shot green

After the combined identity receives fresh 4/4 static approval plus
Coordinator verification, repeat the same fresh atomic sequence once:

- focused tsc once;
- free-port preflight;
- fresh attempt root and isolated gateway database/runtime/artifact paths;
- one owned real gateway with the exact direct `/server/capabilities`
  HTTP-200/gateway readiness observer and 90-second bound;
- one owned Vite with bounded readiness;
- registered startup-transport smoke once;
- require exit 0 with inherited cases and the complete invalid-identity
  evidence;
- mandatory owned teardown and no rerun.

---

## 8. Complexity, duplication, and serialization

### 8.1 Complexity

Successful current identity load is unchanged: one read, one parse/decode.

Invalid identity recovery adds:

- one exact-key `removeItem`;
- one null return.

Time and transient memory remain O(1). There is no key scan, prefix search,
retry loop, cache, listener, or retained allocation.

### 8.2 Authority

- generated SDK remains sole identity-shape authority;
- `directoryIdentity.ts` remains sole exact key/pre-parse owner;
- `gameDirectory.ts` remains sole HTTP 404 and principal-specific cleanup
  owner;
- main/WP-005 remains sole storage-denial startup UI owner;
- UI remains sole explicit reidentification owner.

The test injects one opaque invalid value and observes production. It does not
copy the decoder or cleanup algorithm.

### 8.3 Serialization/public contract

There is no change to:

- `PlayerIdentityResponse`;
- stored key name or valid JSON representation;
- generated SDK descriptors;
- request/response bodies or headers;
- backend routes/models;
- diagnostic schema;
- package scripts/dependencies;
- public production exports.

---

## 9. Explicit non-goals

WP-006 does not:

- close all of BUG-023;
- reinterpret a valid identity whose server profile returns non-404;
- change the existing exact 404 cleanup;
- delete per-principal selected-character state without a validated principal;
- clean unrelated cache/presentation/preferences/replay values;
- create, identify, or authenticate a replacement user;
- repair unavailable browser storage;
- add a quarantine ledger or migration version;
- change standalone local-profile startup;
- test mounted gameplay, Pixi, backend persistence, or real player creation;
- address BUG-011 or any other held/new-contract seam;
- normalize unrelated dirty worktree state;
- address advisory full-suite blockers.

---

## 10. Mandatory halt conditions

Stop and return to Planner if:

1. the malformed value can reach another loader before
   `loadDirectoryIdentity`;
2. anonymous gateway context does not already render the identity form;
3. the fix requires scanning keys or inferring a principal ID;
4. a selected-character/presentation/cache cleanup becomes necessary for this
   exact malformed-value receipt;
5. valid identity decode would change;
6. the existing 404 cleanup must change;
7. `removeItem` failure would be swallowed;
8. a backend/SDK/generated/public contract change is proposed;
9. a second production or second Tester file is needed;
10. the natural red differs from the exact message;
11. any inherited startup-transport case fails after the Revision 3 Tester
    identity is frozen;
12. any owner requests a rerun/debug/workaround after a governed run;
13. any material human product/architecture decision appears.
14. the supported real gateway cannot start with all database/runtime/artifact
    paths isolated under the fresh attempt;
15. the inherited form submission does not reach the real gateway identify
    endpoint or does not persist a generated-decoded identity.

---

## 11. Gate A review questions

Each isolated reviewer must answer the complete packet, not only the diff
summary.

1. Is `directoryIdentity.ts` the sole exact persisted identity pre-parse owner?
2. Does generated-SDK decode remain the sole validity decision?
3. Is `null` already a complete anonymous gateway receipt?
4. Can a malformed identity supply no lawful principal ID for broader cleanup?
5. Does exact-key removal avoid a storage/prefix scan and preserve unrelated
   state?
6. Must remove failure propagate into the already-accepted WP-005 UI?
7. Does the existing 404 cleanup remain separate and unchanged?
8. Does the ordinary-root fixture necessarily force gateway identity loading?
9. Is the capability fixture generated-contract valid and minimal?
10. Can the real backend supply the remaining catalog without topology
    mutation?
11. Is the exact generic-panel assertion the natural first red after inherited
    cases?
12. Do zero profile/identify requests exclude invalid-credential use and
    automatic replacement?
13. Does the unrelated sentinel exclude broad storage clearing?
14. Are returned summary fields actual observed values?
15. Is one production plus one existing Tester file complete?
16. Is the backend+Vite one-shot protocol sufficient and bounded?
17. Does the change add any schema, serializer, public contract, dependency,
    or persistent authority?
18. Is runtime cost O(1) with no scan/retry/cache?
19. Is the claim correctly limited to BUG-023 malformed identity Stage 1?
20. Does any hidden scope or human decision remain?
21. Did the governed retry stop before the WP-006 case for the proven
    standalone-versus-gateway fixture precondition rather than product code?
22. Does replacing standalone orchestration with the existing real gateway
    make the existing profile-404 cleanup reachable without a backend source
    or application-contract change?
23. Does real form submission preserve generated/backend identity authority
    while avoiding a hand-authored valid credential fixture?
24. Do exact profile-route count, cleared identity, anonymous form, zero panel,
    and zero page errors make the inherited prerequisite non-vacuous before
    the natural red?
25. Does the frozen gateway source own both generated-valid gateway
    capabilities and the real `/directory/players/identify` endpoint?
26. Are database, hosted runtime, artifacts, and capability authority isolated
    under the fresh attempt without sharing durable test state?
27. Is `DND_HOSTED_WARM_WORKERS=0` lawful for this directory-only smoke while
    leaving gateway capability/identify/catalog ownership unchanged?
28. Does gateway lifespan shutdown plus owned process-tree verification cover
    the retained preview child and prevent service leakage?
29. Does using the real gateway avoid both a hand-authored identity fixture and
    an identify-route mock while keeping the one-production/one-Tester file
    boundary?

Gate A approval authorizes no edit or execution by itself.

---

## 12. Expected closure claim

If and only if the identical frozen Tester moves from the exact natural red to
green after the one-file production correction, WP-006 may claim:

> NeuroClient quarantines one malformed persisted gateway directory identity
> at its existing generated-SDK pre-parse owner, preserves unrelated storage,
> performs no authenticated or automatic-replacement request, and returns to
> the existing anonymous player-identification UI.

It may not claim full BUG-023 closure or general storage/principal recovery.
