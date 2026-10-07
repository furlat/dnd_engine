# Server-only plan: independent reviews

**Latest: general-seat amendment approved independently by both reviewers.** The
earlier reviews and their hashes remain historical records. The final review below
covers the current server plan and normative stream/SDK contract, including the
opposing Python/TS match and unrestricted configured seat count. These are design
approvals, not completed schemas, SDK packages or executed tests.

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

## Second pass — stream, cursor following and both standalone SDKs

Human request: deepen the server plan on the new branch; preserve streaming,
provide TS and Python SDKs, enforce subjective-only information, minimize duplication
and settle the complete current-content schemas before runtime implementation.

Branch was clean at `feature/server-is-coming-back`, HEAD
`40eb37b9b4cac72ea75d00d7b1545a4e48a5d2a2`. The
[second-pass source record](STREAM_SDK_SOURCE_BASELINE.json) fingerprints 19 inspected
server/application/SDK/reference-client files. No other chat was read or contacted.

Reviewed documents:

- [Practical implementation plan](../../SERVER_IMPLEMENTATION_AND_ENGINE_PERFORMANCE_PLAN_2026-10-07.md).
- [Normative stream and SDK contract](../../SERVER_STREAM_AND_SDK_CONTRACT_2026-10-07.md).

Both reviewers independently inspected the old SDK/source. Confirmed SSE transport,
old objective exports/native-event generation, callback ordering and incomplete-EOF
decoder pitfalls. Neither old generation nor old client orchestration is inherited.

### Corrections made during this review

1. Retry-safe attachment acquisition uses request identity plus expected prior epoch;
   lost response cannot repeatedly displace the current attachment.
2. One socket per attachment, atomic spool backlog/live handover, persistent sent/ACK
   positions and explicit lost-ACK resend.
3. A successful initialization explicitly ACKs sequence zero. No first-command deadlock
   when the catch-up barrier is zero and no operation has yet been emitted.
4. Received, consumed, acknowledged and displayed positions have separate meanings;
   callback failure cannot advance recovery. Original payload bytes are available
   to recording consumers; incomplete EOF tails never become complete events.
5. Terminal/failed/closed status freezes final public head F. Retained prefix drains
   before normal completion/final failure; cursor waits and terminal EOF are explicit.
6. Audience-local public ordering and authorized token changes prevent raw native
   counters/unchanged HUD pulses from disclosing invisible operations. Paired hidden
   activity cases cover status, stream, queries, errors and nested references.
7. Canonical Python models generate standalone JSON declarations for both SDKs;
   installed packages contain no engine/old-server/renderer dependency. The normal
   probe uses the production SDK rather than another handwritten client.
8. The same Python public reduction functions serve server, probe and cold replay.
   TS recording tests prove transport/wire delivery, not completed TS state reduction.
   Shared-code agreement is supplemented by native outcome assertions.
9. A0 coverage is bidirectional: exported fields to cases and every existing required
   capability to authorized fields to cases. Exact schema versions, root closure,
   required/null/error variants, semantic validators and generator conformance must
   be settled before extraction/host/SDK behavior implementation.
10. Current content manifest enumerates all declarations regardless of visibility.
    PUBLIC seed and admitted OBSERVED additions now pass through the same shared
    reducer/catalog field before facts; cold recordings retain their public seed.
11. Encoded UTF-8 record limits and decoded heap consumption are distinct. H41–H52
    extend the full H01–H40 matrix with packaging, language parity, real-socket races,
    cursor waiting, privacy and cleanup.

### Independent verdicts

`server_plan_antislop`: **approved for planning scope; no remaining blockers found**.
Verified the corrected ACK/final-prefix/schema gates, content disclosure ownership
and standalone transport packages. No implementation, test or performance approval.

`client_plan_ecs`: **planning approval; no remaining blockers in review scope**.
Verified shared Python paths, generated passive declarations, import isolation,
complete-schema entry gate, causal/cursor ownership and independent verification.
No schema-completion or TS gameplay-reducer claim.

### Completion boundary

This pass edits only documentation/source-fingerprint artifacts. No production code,
SDK package, test or benchmark was implemented or run. A0 remains a required contract
authoring/proof step before runtime migration, and Gate B still follows complete
headless Gate A correctness. Final document changes after approval only record these
verdicts and their hashes.

### Second-pass saved artifact hashes

| File | SHA-256 |
|---|---|
| SERVER_IMPLEMENTATION_AND_ENGINE_PERFORMANCE_PLAN_2026-10-07.md | `22b2fe44fbca289b53810a8049bba436fc2b2e0695718007f0d489d31d5ae4e6` |
| SERVER_STREAM_AND_SDK_CONTRACT_2026-10-07.md | `249bd2959589dc4b60117a8ce99c746912c671ee530354064ccaccc894c29514` |
| STREAM_SDK_SOURCE_BASELINE.json | `15377f35e1e977fa851c1f577221dbb9693709f700a7795663249de314b57953` |


## General-seat amendment — one encounter, independent Python/TS players

Human correction: do not impose a one-seat, two-seat or other artificial player
limit. An externally controllable entity may have its own seat, or one seat may
control a group. The primary gameplay proof must run opposing Python and TypeScript
SDK scripts concurrently against the same encounter, with separate credentials.

Both reviewers independently checked the written amendment against the existing
native controller/encounter, session, audience, HUD, log and capture responsibilities.
The concrete extraction changes are in the stream contract §5.2; H53–H56 extend the
same mandatory acceptance matrix. No external chat was read or contacted.

### Decisions verified

- One native encounter and existing HumanController/AI owners. Generalize configured
  roster/controller composition; do not introduce per-seat worlds or SDK controllers.
- One active-turn discovery cache qualified by seat/actor/revision/mode. Other-seat
  requests cannot replace it; attachments, command numbers and receipts are isolated.
- Freeze original private evidence once, then use existing audience admission and
  projection functions separately. Current audience-filtered capture cannot be shared
  between seats. Move original standalone log buffering out of discovery; filter HUD,
  catalog, ordering, history and status to each authorized audience.
- Stage complete audience results sequentially using bounded private IPC, then publish
  participating heads and the submitting seat's receipt together. Partial failure
  publishes none of the incomplete operation and fails the game without rerunning it.
- Spool-backed delivery cache is aggregate and allocated on use. Slow or disconnected
  readers cannot hold shared encoding workspace or block another seat's native turn.
  Actual recording capacity can pause scheduling; an absent current controller waits
  under native rules. Death/despawn/summons retain native ownership and recovery facts.
- H53 requires opposing Python/TS scripts, languages swapped, in one real game through
  terminal outcome. H54–H56 cover isolation, grouped/three-plus/per-entity assignments,
  slow readers, reconnect and partial-publication/capacity failure. Each audience is
  replayed against its own expected facts, not compared for identical private views.

The parent architecture's server sections now reference the canonical API/SDK
contract instead of repeating outdated single-seat, authentication or backpressure
rules. Final wording clarifies that the SSE connection limit is per attachment,
not per game, and slow-reader delivery stalls are distinct from native turn stalls.

### Independent verdicts

`server_plan_antislop`: **approved for planning scope; no remaining blockers found**.
Reviewed ownership/privacy isolation, lifecycle, common capture, complete audience
publication and the corrected spool/cache semantics. No implementation, schema or
performance approval implied.

`client_plan_ecs`: **planning approval; no remaining blockers in review scope**.
Reviewed ECS/import boundaries, common evidence versus audience admission, shared
reducers/controllers, native death/summon ownership and independent verification.
No runtime tests or schema-completion claims.

Only planning documents and source-evidence artifacts changed in this pass. No
production source, SDK, tests or benchmarks were implemented or executed. Gate A's
contract-completeness and implementation proof requirements remain mandatory.

### General-seat saved artifact hashes

| File | SHA-256 |
|---|---|
| SERVER_IMPLEMENTATION_AND_ENGINE_PERFORMANCE_PLAN_2026-10-07.md | `6e8121a7bedea00bd446cc8d430ac1ee422ab6e12fd1c7c61eb4dff3d2a651a0` |
| SERVER_STREAM_AND_SDK_CONTRACT_2026-10-07.md | `87f3eb13450c943aafb7896cdd3869c959fcbec3c7be7401fa1b666bcdddc2b9` |
| NETWORK_SERVER_NEUROCLIENT_STUDIO_PLAN_2026-10-07.md | `52856c83c353a97041846e8ed22cb4ee56bf056643061c76433667958c26f2d9` |


## Concrete schema and upstream ownership review — October 7

Scope: proposed API fields, upstream typed logs, causal privacy, retained identity,
and one stream for an authorized audience. No production source, server or SDK
runtime was changed. The [concrete package](../../server-api-v1/README.md) records
314 shared definitions, 1,612 fields and 19 public roots, with current captures
separate from proposed examples.

One native capture pass completed 872 of 873 scenarios and all 28 fact variants.
`cloud-door-lifecycle` raised `ValueError: Item is out of reach`; it remains a
recorded failure, not a repaired scenario. One Python/JavaScript shape pass checked
131 examples; three subsequently added response examples received targeted checks
in both tools. This is shape evidence, not runtime privacy or SDK acceptance.

### Independent final findings and disposition

- `client_plan_ecs`: planning/ownership approval, with no architectural blocker.
  Clarify that target-child indices are distinct, in range and ordered, and that
  future log UI layout does not defer native identity/private-count text repairs.
  Both clarifications are now written; uniqueness is also schema-constrained.
- `server_plan_antislop`: ownership direction accepted; two remaining specification
  errors were found. `CombatLogEntry.data` could be omitted, and malformed-request
  HTTP status differed between prose and schema. The payload is now required and
  the status is consistently 400 `invalid_request`. The required-payload assertion
  passed. No second post-correction reviewer approval is claimed.

Earlier findings in this pass are incorporated: reuse native spatial enums and
existing type owners; finite log category/payload compatibility; explicit privacy
omissions; target-child membership instead of duplicated child logs; nullable
unknown causal references; and remapping of audience-local indices. Door-edge
opportunity deaths must preserve previously admitted identity without revealing
unobserved death/location. One audience stream covers the controlled group;
selecting another unit does not change the user's knowledge.

The human's execution constraint is explicit in the plan: no SDK generation or
validation treadmill. Implement upstream owners and the shared application first,
then thin transport/SDKs. Generate declarations when those owners exist, retire
the design overlays, and rerun checks only for actual changes or failures. No new
review cycle or broad scenario rerun follows this receipt. Runtime completion and
independent implementation reviews remain future work.

### Saved artifact hashes after the listed corrections

| File | SHA-256 |
|---|---|
| SERVER_IMPLEMENTATION_AND_ENGINE_PERFORMANCE_PLAN_2026-10-07.md | `0a510d92cc0673f5493547aff8072a28410bb502d6055f566b3ae953a9bcf8a3` |
| SERVER_STREAM_AND_SDK_CONTRACT_2026-10-07.md | `76d7bca6757ba80e1ba146476303dfbaafe574b8dbfd11e534df4bd6c1fd5b86` |
| server-api-v1/player-api-v1.schema.json | `3835f249c40abfcff6ac67e131a081e49cc462dc64cb94ef7e1f39c5638f89aa` |
| server-api-v1/COMBAT_LOG_CONTRACT.md | `863d0eac82d93927ec9a6ba587f8f90900b11458045857703731052576bce6ee` |
| server-api-v1/semantic-contract.md | `5dc8b5a0b8ceda31ad3d8d4da37b606bed37584f99e54f74a002c2808a524cb3` |
