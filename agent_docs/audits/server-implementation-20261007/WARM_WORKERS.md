# Server phase closure: reusable native workers

October 7, 2026. The authorized server functionality is complete, including reuse
across successive games. The new client can build on this API and the existing
Python/TypeScript SDKs. This does **not** declare every broader Gate B performance
target met; those residual workloads remain in [PERFORMANCE.md](PERFORMANCE.md).

## Actual changes

- The existing native reset also clears Dice/DiceRoll ownership. Application close
  clears the existing AI decision, semantic-input and subjective-adjacency caches.
  Installed immutable content and completed Pydantic schemas remain loaded.
- The private worker protocol accepts EndGame only for its current epoch. It closes
  the session, drops runtime/results, resets and collects before acknowledging.
  Every subsequent Start resets randomness from its private seed or normal entropy.
  The pre-Start freeze remains once per process; live games are never frozen.
- `workers.py` owns exclusive process leases; `service.py` owns configured Hosts,
  credentials and recording reservations. A healthy retired worker becomes available
  to another game. Concurrent games use separate workers. Failed/uncertain exchanges
  discard their process, without retrying a possibly executed mutation.
- Existing HTTP/SSE routes resolve the credential's Host once per request. Old
  attachments, receipts, streams, recordings and delivery credits stay with that
  Host after its native world is retired. New games get independent scope identities.
- Explicit end finishes admitted work where possible; capacity waiters cancel before
  Start. Cancellation during acquisition, retirement or shutdown cannot abandon the
  owned process. Repeated end during reset does not cancel a healthy reset.
- Terminal, failed, cancelled and unpublished retired games keep an expiry owner.
  A recording's storage reservation is reclaimed only after deletion succeeds.
- The player application now calls the existing `dispatch_available_action` boundary,
  preserving its exact retained selection while using the existing actor-binding
  and affordability checks. This removes a direct lower-level call, not adds rules.

No spell/rule expansion, rendering changes, new public admin endpoint, public type
family or SDK regeneration. The exact protocol-1/player-4 schema test still passes.
Private usage and operator resource limits are in [the server README](../../../player_server/README.md#successive-and-simultaneous-games).

## Final measurements

Each platform ran **16 games in one production service on one reused worker**:
one cold ordinary game, ten warm ordinary games, Fireball, Wall of Fire, Conjure
Animals, mixed human/AI control and the crypt. The three spell fights on each
platform reached native terminal state. The other cases exercise normal commands;
the crypt's complete gameplay acceptance remains the earlier recorded journey.
The last ordinary game uses normal entropy after the preceding seeded games.
Independent SDK client and health-monitor processes use real HTTP/SSE.

| Boundary | Native Windows | WSL on mounted checkout |
| --- | ---: | ---: |
| First cold worker to human-ready, one sample | 1,972.59 ms | 3,974.48 ms |
| Subsequent ordinary game readiness, mean of 10 | **217.77 ms** | **208.27 ms** |
| Warm readiness range | 214.13–224.07 ms | 202.69–212.29 ms |
| Native retirement/reset/collection, ordinary warm mean | 32.38 ms | 30.92 ms |
| Committed SDK commands / consumed records | 96 / 374 | 95 / 373 |

Readiness includes worker acquisition, native construction, encoding, pipes, spool
commit and the first own human-input boundary. It excludes host-process imports
and fixture configuration. These are not full cold-service figures or percentiles;
§14 retains the separate full-host startup measurements. Cleanup is separate from
new-game readiness. Different spell/AI/map compositions have their own startup
costs; the mixed-AI cases are about 669/608 ms, not 218/208 ms.

Both workers exit successfully; both services report zero owned workers afterward.
Saved source fingerprints match the final production files. One preliminary Windows
run predates the last cancellation corrections; only `windows-final` and `wsl-final`
count in the table above.

After ordinary retirement, native WSL RSS is 190.94, 191.72, then **192.25 MB for
the next nine games**. Later first-use spell/AI content raises it (peak sampled
266.05 MB, last crypt 253.66 MB). This is not a claim of constant memory across all
content. Real summon/AI world weak-reference tests separately prove retired actors,
grid and Game objects become collectible, and old roll identities cannot be found.
The Windows RSS counter sampled the venv launcher process (~4.24 MB), **not the
interpreter**; it is excluded from native-memory conclusions. The probe's future
output now explicitly labels that scope. Public recordings intentionally remain:
21.33 MB Windows and 21.20 MB WSL at the end of these cohorts.

## Checks and independent review

- **147 distinct Python tests pass** across the final 146-pass cohort and one
  corrected static-consumer-list retest. That list now names the shared player
  application as a consumer of the existing dispatcher. Two exact neutral-value
  import allowances were updated; the runtime import constraints remain enforced.
- Real-worker lifecycle checks cover sequential/concurrent games, old credentials
  and replay, pending-command retirement, failed-worker replacement, bounded
  capacity, queued cancellation, failed Start, unpublished retirement, filesystem
  deletion failure, cancelled shutdown and concurrent/cancelled EndGame ACK.
- **24 TypeScript SDK tests pass**; the Python SDK tests are in the Python cohort.
  Scoped production Pyright reports **zero errors**.
- A separate process cold-replays **62 audience prefixes, 747 records and 191
  commands**, checking ordering, identities, content disclosure, HUD authority,
  causal references and the same production player reducer.
- The independent anti-slop and ECS/DAG reviewers approved the concrete design and
  repaired source. Their final evidence verdicts are recorded in the adjacent
  [anti-slop](ANTISLOP_REVIEW.md) and [ECS](ECS_REVIEW.md) receipts.

Raw evidence is ignored, not added to Git:
`.runtime/server-recovery/warm-worker-implementation-20261007/` contains the
source snapshots, final platform cohorts, summary, test logs and cold-replay result.
The initial `die.roll()` test typo and wrong Pyright interpreter invocation are
retained as unsuccessful harness attempts, not counted as successful checks.

## Boundary to the next phase

Server/API/shared application/SDK functionality is ready for client development.
Private deployment code creates games; public lobby/accounts/TLS remain deployment
scope. Whole-world durable save/load across service restart is not implemented;
existing recorded-prefix replay is not represented as that feature.

Broader engine work still includes largest-map/hidden-blocker scaling and dense
spell/native-AI latency distributions. Existing measured Fireball command cost is
not hidden by faster warm startup. Pixi rendering, authoring/Studio, asset packing,
playback speed and UI remain the new-client phase. No frontend migration was started
by this server change.
