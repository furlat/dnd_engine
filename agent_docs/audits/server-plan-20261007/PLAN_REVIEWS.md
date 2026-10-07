# Server-only plan: independent reviews

Date: 2026-10-07. Scope: practical server architecture, independent verification
and the subsequent engine-performance iteration. Planning only; no implementation
or tests ran during these reviews.

Plan: [Independent game server](../../SERVER_IMPLEMENTATION_AND_ENGINE_PERFORMANCE_PLAN_2026-10-07.md).
Source evidence: [29-file fingerprints](SOURCE_BASELINE.json). Existing dirty
production changes were preserved, not attributed to this study.

## Anti-slop / server responsibility

Local reviewer: `server_plan_antislop`.

Source investigation identified invalid direct selections escaping as ValueError,
eventless handler changes, an unbounded per-discovery preview cache, private gap
diagnostics in the local reply and the difference between passive DTO values and
their current transitive imports.

The plan specifies typed native admission, a separate application revision, recorded
handler after-values, bounded preview retention and private fatal diagnostics. It
also makes command reservation/rejected-number consumption, attachment catch-up,
ACK bounds, storage reservation and shutdown observable to a headless consumer.

Final draft correction: host checks actor membership in its bound controlled set
before reserving a new command. Unauthorized actor is 403/no reservation. Native
turn/incapacitation/choice legality is checked in the worker after reservation and
produces a terminal rejected receipt. Existing receipt lookup still happens first.

Reviewer also caught the new handler descriptor's import dependency. The plan moves
that one shared passive definition to a suitable existing core leaf, re-exported
for old callers. It does not copy it or make cold reduction import executable
base_actions/EventQueue dependencies.

Final verdict: **approved for server-only implementation planning; no remaining
blockers in review scope**. Lifecycle, retries, catch-up, ACK, recording and failures
form a coherent independent test target. H01–H40 and Gate A before Gate B preserve
the user's requested order and exclude frontend/platform work.

## ECS / DAG / testing and performance

Local reviewer: `client_plan_ecs`.

Verified bounded extraction of existing session, public facts/commands/audience,
capture/projection/reduction and content descriptors. Native discovery, costs,
pathfinding, senses, rules and encounter/controller progression retain their owners.
The current controls helper is pure; its move is an ownership correction rather
than a proven pygame leak. Native definition imports are distinguished from live
session/bootstrap ownership in the host.

Verified operation-level reduction for eventless HUD/preferences and public replay,
three independent verification lanes, separate transport/native retention, and the
Gate A→B order. Performance E01–E13 distinguish source-confirmed work, earlier bounded
measurements and still-unmeasured suspects. Existing timing hook limitations and
cache ownership/invalidation are documented; a new cache is not a default fix.

Final verdict: **planning approval; no blocking ECS/DAG or verification findings**.

## Limits of approval

These are approvals of design, completeness of the planned work and scope. They do
not certify actual runtime imports, completed field/privacy dispositions, executed
H01–H40, engine speed, host deployment or gameplay correctness. Those remain the
explicit Gate A/Gate B deliverables. No browser/rendering/UI implementation is part
of this server-only plan. No external chat was read or contacted.

The final master-plan edit after review only records approval and this receipt link.
Hashes below identify the saved planning revision and source fingerprint artifact.

| File | SHA-256 |
|---|---|
| SERVER_IMPLEMENTATION_AND_ENGINE_PERFORMANCE_PLAN_2026-10-07.md | `1e74642850d0895a07436eec637e05bed1be5085797d999d9350d4091fe21d3c` |
| SOURCE_BASELINE.json | `947d9f08faeec00b710727100bf37849965bcd744fb9fd09fbb80f05575173a8` |
