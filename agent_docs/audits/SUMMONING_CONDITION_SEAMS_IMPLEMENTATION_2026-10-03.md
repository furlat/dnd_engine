# Packet 2 — lower condition and concentration seams

Implementation handoff for approved summoning plan sections 3–9. This is **not independent approval**. The initial review rejected the first extraction; the corrections below address its concrete blockers. Higher summoning must wait for independent rereview of the combined owner changes.

Approved plan SHA256: `d2c83849488ebe40a2fe01ca36cc09fdd9fcede13724207e82d22739545f375b`.
Linked visual addendum SHA256: `28dbdf5dec4fcc45afe6a5434ca297ec22da58715a0f044dcd37b9ca18011075`.

## Native ownership and integration APIs

- `BaseBlock` owns prepared application/initial-batch/removal records, committed publication snapshots and graph-settled removal receipts. Neutral sustain-loss policy/cause values stay in `condition_types`; the receipt stays beside its real owner, avoiding an import allowlist expansion.
- `prepare_condition_application`, `commit_condition_application`, `publish_condition_application`, and `cancel_condition_application` separate admission, authority and observations. Existing `add_condition` callers retain Entity declaration/immunity/save gates. Generic old replacement removal commits before the incoming direct-state hook, preserving replacement invisibility and exact Haste grant ownership.
- `Concentrating` admits old-root/evicted-child removal and retained slot transfer, then commits them under the same outer removal scope. The partial transfer record exists before callbacks, so rejection or an admission exception can release every admitted native receipt without changing old slots or conditions.
- `SpellAction.prepare_concentration`, `commit_prepared_concentration`, and `publish_prepared_concentration` use these lower records. Ordinary `apply_owned_condition` follows this path and links exact ownership before successful publication.
- Aggregate consumers use `prepare_owned_condition_removals`, `commit_owned_condition_removals`, `publish_owned_condition_removals`, and `cancel_owned_condition_removals`; UUID exclusions cover only the already-admitted existence graph. Commitment requires the outer `condition_removal_scope`.
- Scope settlement occurs after complete publication. Nested scopes share exact receipts. Context is cleared before callbacks; one callback failure does not skip the others. Required sustain branches release before unrelated ordinary vetoes. Dismissal stays voluntary; typed expiry/defeat/close context identifies the exact terminal owner.
- `BaseCondition.terminal_release_for_expiration()` defaults to None, ready for the high existence condition's explicit override. No ordinary condition gains mandatory authority.

## Independent review corrections

1. Incoming preparation is exception guarded through replacement-tree and required-sustainer admission. Cancellation drains admitted native receipts and incoming artifacts despite another cleanup callback failing. Direct graph removal and slot-drop admission also release partial native preparations on an exception.
2. Invisible/Invisibility/Greater Invisibility only set their direct flag during native commitment; removal commits the flag silently and notifies perceivability afterward. Failed incoming effects release their exact modifier ownership without changing visibility. Same-name replacement retains the new owner.
3. Haste installs its restricted grant only on commitment. Failed incoming admission leaves no grant or modifiers and creates no lethargy. Committed removal releases the exact grant; its existing one-round lethargy is applied after membership commitment. Attack budgets and Haste policy are unchanged.
4. Banished return is prepared before replacement: `PreparedSpatialReturn` records the original return cell plus current-occupant displacement through the existing supported adjacent-cell rule. The native condition exposes these reserved cells through `prepared_removal_occupancies`; Concentrating aggregates them for final summon admission. Exact source membership/destinations are revalidated before any authority mutation. Commitment uses existing GridMap operations with publication disabled; publication follows afterward. Rejected/stale admission leaves the old banishment and positions intact. The exact actor retiring does not return, while its external banished targets do. Existing ordinary return error/publication semantics are retained.
5. `prepare_removal_state` admits native owner state for both voluntary and mandatory removal. It does not supply a general buffer or bypass placement validity. Antimagic suppression markers are exact linked children of their field; committed field cleanup no longer recursively calls public marker-removal APIs. Markers restore saved magical conditions only after the full removal authority commits; canceled field application retains its established compensation path.

## Evidence

- Before corrections: focused original suites 174 passed; initial six new contracts passed. Independent review correctly found untested direct-state/publication blockers; those counts were insufficient for approval.
- After corrections: **143 passed** across prepared lifecycle, condition transforms, ordinary lifecycle, roster support spells and gear ownership. The prepared-lifecycle file contains **29 cases**, including failed/canceled incoming effects, partial replacement admission exceptions, silent commitment, native restoration, mandatory exact-owner behavior, stale occupancy, and replacement direct-state ownership.
- Expanded native/architecture run: **470 passed, 1 failed**. Dependency boundaries, concentration presentation, shared sensory conditions, senses/stealth, Haste matrix and device concentration passed. The one failure is `tests/engine/test_spatial_conditions.py::test_spatial_parent_retires_block_owned_child_before_terminal`: the independently implemented spatial publication split emitted the parent terminal before its ordinary child's terminal. Reported to root, who owns that loop; this report does not waive it.
- Final correction recheck: **69 passed** (29 prepared-lifecycle cases, 17 condition-transform ownership checks, two concentration-presentation checks and 21 dependency-boundary checks).
- Final scoped typing: **0 errors** for lower seams, actions, Entity, abjuration and transmutation after the correction pass.

## Remaining combined integration gate

Root owns the separate independent spatial-owner commit/publication changes, including the required child-before-parent event order and exact mandatory spatial removal preparation. The retirement worker owns world sections/items. These must pass combined tests and independent review before packet 2 approval. In particular, a mandatory removal cannot feed a plain condition event into an owner requiring a typed spatial-change event.

No rendering, artwork, attack-cost policy, content expansion, generic event buffering, or new movement resolver was introduced in this correction. Native Entity return methods are the specifically authorized bounded Banishment seam. No other-chat communication or subagents were used.

## ECS rereview correction — remaining native publishers

A further ECS review correctly identified direct removal notifications in Hidden,
sense-grant conditions, light-owner conditions, and shared spatial manifestations.
These were canonical live paths, not speculative future extensions.

- Hidden's exact stealth DC commits silently and notifies after membership, matching
  the existing invisibility seam. A rejected incoming Hidden application releases
  its provisional attack modifier without changing the target's stealth.
- See Invisibility, True Seeing and Darkvision retain the exact passive SenseMode
  they grant, install it at commitment and remove only that instance. A creature's
  identical natural sense is preserved. Perceivability publication follows removal.
- GridMap.remove_light_source already supported silent removal; it now returns the
  existing typed light-delta snapshot when silent. Light, Produce Flame and Fire
  Shield retain that one native observation until membership publication. Continual
  Flame appends it to its already-existing spatial removal publication. This is not
  an arbitrary event queue, generic transaction framework, or new schema.
- Spirit Guardians and spatial restraints use BaseCondition's existing shared
  subcondition ownership for the public slow/restraint. Last-source public removal
  is therefore admitted into the same graph, respects its veto, commits silently,
  and publishes child-first. Removing one source preserves another source's public
  manifestation. Borrowed standalone conditions retain independent ownership.
  The existing restraint replacement callback reconnects its replacement child to
  the surviving sources. Nested public removals and bespoke Spirit Guardians
  owner-transfer flags are removed.

First regression run after these production edits: **107 passed** (prepared
lifecycle, jaw traps, Web restraint status, roster support spells); scoped typing
**0 errors**. Added `tests/engine/test_condition_silent_removal.py` for the remaining
owners, identical natural senses, canceled prepared sense/stealth, shared-child
vetoes and callback-free commitment. Its run and the broader perception run were
blocked before collection by concurrent catalog integration:
`missing=['ConjureAnimals', 'ConjureFey', 'ConjureFiend']` in
`dnd/spells/catalog_content.py`. Root was notified; do not claim these new cases
passed until that shared bootstrap registration is coherent and rerun.

## I9 integration correction — consequences during exact actor retirement

Haste lethargy and AntimagicSuppression restoration are native post-removal
consequences. During aggregate retirement the actor remains registered until all
condition publications finish, so checking only `is_active` could recreate a
condition on that departing actor and prevent final ownership release.

Both existing `on_membership_changed` hooks now consult the already-established
`BaseBlock._terminal_release` context and skip their consequence only when its
`entity_uuid` equals the condition's target. This includes voluntary dismissal
and mandatory expiry. The check deliberately does not compare the effect's
source: external recipients surviving the summoner's departure still receive
Haste lethargy or regain their suppressed condition. There is no new context,
registry, event, transaction layer or BaseBlock change.

`tests/engine/test_summon_terminal_consequences.py` adds eight real native summon
cases: dismissal and expiry, Haste and suppression, each both on the departing
actor and on an external surviving recipient linked to its concentration.
They verify completed Game/Encounter/GridMap/runtime removal and the absence of
new condition completion events on the departed actor, plus retained native
consequences on survivors.

Evidence for this correction: **51 passed** across the eight new cases,
`test_summon_retirement_ownership.py` and
`test_prepared_condition_lifecycle.py`; scoped pyright for the two edited spell
modules reports **0 errors**. An earlier overlapping run including the actively
changing `test_summoning_lifecycle.py` was terminated before completion and is
not counted. Root owns that expanded lifecycle and full-suite run. Production
changes and focused tests are frozen for independent review.
