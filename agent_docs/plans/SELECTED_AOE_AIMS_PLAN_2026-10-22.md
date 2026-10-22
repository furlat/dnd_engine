# Selected AoE aiming request and local agent computation

Status: planning only. The human clarified the propagation contract: within the
stamp, open connections let the blast through; a wall sealing off a section
blocks that section. Reuse this existing rule as a connectivity mask. The
remaining work is algorithm qualification/timing, not a product decision about
whether walls count.

Human requests: plan a request for one selected AoE spell, retain the stamped
algorithm, and ensure the agent CLI can compute locally from existing public
data. This continues the aiming investigation in FREE_AIM_PREVIEW_FIX_2026-10-22.md.
It does not authorize implementation in this turn.

## 1. Required result and boundaries

- Behavior: ask for useful ground aims for one selected action and casting rank;
  retain the affected creature identities needed to compare friendly fire and
  target-specific value. Normal Choices remains compact and deferred.
- Input: current authorized actor, state revision, discovery generation, action
  index, casting rank, and explicit known creature UUIDs whose coverage the
  caller wants. The seed targets select which centres are useful; they never
  exclude other recipients from the returned hit sets.
- Boundary: existing native functional owner -> session -> serial worker/HTTP ->
  Python and TypeScript SDKs -> agent's existing Monty workspace.
- Output: all supported useful centres in the declared domain and compact
  response-local hit sets. No silent top-K cutoff or truncation. Empty computed
  output and unsupported computation are different outcomes.
- Client-local boundary: disclosed input values -> portable stamping function ->
  candidate hit sets and caller-owned scores, with no implicit network request.
- First qualification is the ordinary actor-origin Fireball at its selected
  rank. Broader shapes/compound placements require their own native semantics
  and evidence; do not call all POSITION_AOE rows interchangeable.

No AI policy rewrite, native-AI decision-epoch redesign, terrain/height system,
new sensory computation, full client-world reducer, background service, FFT/GPU
path, or automatic work for every spell. Godot integration is a documented client
handoff; this backend plan does not edit the client repository.

## 2. Evidence and an existing contract mismatch

The retained [measurements](../audits/SELECTED_AOE_STAMP_2026-10-22/stamping_results.json)
and [qualification probe](../audits/SELECTED_AOE_STAMP_2026-10-22/qualification_probe.py)
use a creator-built level-5 Sorcerer, 30 enemies, three allies and the caster on
a bright unobstructed 28x28 floor. The probe writes exploratory output under
`/tmp/dnd_aoe_30_targets_2026_10_22`; its `stamp_algorithm` timings are the agreed
algorithm. Other timings are the exhaustive correctness/reference path.

| Layout | Useful aims in advertised region | Stamp + input preparation + packing + JSON | Uncompressed indexed reply |
| --- | ---: | ---: | ---: |
| Clustered | 149 | 2.14 ms median; 2.45 ms first | 7,870 bytes |
| Spread | 685 | 2.24 ms median; 2.45 ms first | 11,256 bytes |

All 834 returned aim/hit-set combinations matched native Preview within the
advertised region. Timing excludes initial Choices, endpoint/network overhead
and the exhaustive oracle. It proves neither wall-aware cost nor Monty speed.

The native advertised region excludes the caster's own tile, while Preview
accepts Fireball there. Before presenting a complete legal aim domain, reconcile
that mismatch through the existing targeting owner and test Choices/Preview/
Command together. Preserve Fireball's existing execution behavior; do not change
all position actions globally. Rebaseline counts after the repair and record
why they differ by the caster cell, rather than hiding it in test expectations.

## 3. One selected query and one compact representation

Proposed route: `POST /api/v1/games/{game_id}/aoe-aims`, beside Choices/Preview.
Use passive `AoeAimsRequest`/response types in the existing protocol owners.

Request fields: `actor_uuid`, `state_revision`, `discovery_generation`,
`action_index`, `cast_at_level`, `target_uuids`, `correlation_id`.
`cast_at_level` must resolve to an admitted rank of the exact retained row.
Seed UUIDs must name that actor's current perceived creature contacts, or the
caster itself when the native self policy allows it. Reject unknown/hidden IDs
without looking up or disclosing hidden occupants. A known creature excluded by
the selected spell's recipient policy simply contributes no stamp; that is not
an unknown-ID error. Canonicalize seed order and duplicates once. Empty seeds
produce a computed empty result. This array expresses requested coverage only;
do not add a faction-selection language or server scoring policy.

Echo the complete submitted request, including rank and the original seed list,
plus existing game/epoch/audience identity. Canonical seed ordering belongs only
to computation/cache keys, not to the request echo. Return a single
self-contained result:

- `subjects`: UUIDs of disclosed creatures referenced by the result, each once.
- `hit_sets`: distinct arrays of subject-table indices.
- `aims`: fixed triples `[x, y, hit_set_index]`, ordered by `(x, y)`.

Hit sets match the existing subjective Preview on the current map: geometric
coverage filtered by connected reach and existing recipient policy. This does
not promise later recipients exposed by destruction during execution. No
unbounded integer bit masks on the wire,
duplicate counts/names/UUID lists per aim, repeated footprint cells, EV scores,
cross-response registries, custom hashes, or position-table indirection for a
coordinate that appears only once. Clients derive counts and scores locally.

Unsupported action geometry is explicit, not a computed empty response. Invalid
authority/index/rank/seed inputs use existing rejection conventions. Retain the
existing response-size bound and typed oversized-query failure; do not add
pagination or silently trim the aim set.

The response is query data, not execution authority. Submit the chosen coordinate
through existing ActionSelection.extra_target_positions. Preserve Preview and
Command validation and direct-command support.

## 4. Stamping filtered by existing connected reach

Clarification from the human's wall/allowed-position question: reuse the existing
aim region. Aim validity and blast reach are separate native rules. Fireball's
centre rule is visibility plus range, not a blanket exclusion of wall cells or
a destructibility test (`seen_point_error`). A native 9x1 probe confirmed that
an opaque, propagation-blocking tile at (2,0) is visible, appears in the caster's
aim region and passes discovery admission. A blast centred on floor at (1,0)
reaches that tile but stops there. Boundary walls can also obstruct travel between
cells rather than remove either cell from the aim region.

Here, exact wall-aware means matching the existing subjective Preview against
the current map. It cannot promise every eventual execution recipient: Fireball
damages breakable structures and expands after actual destruction through
`resolve_staged_area`. A surviving barrier continues to shield what is behind it.
Do not simulate future damage/destruction in this query or describe Preview as a
guarantee of the final post-destruction hit list. This distinction requires no
new aiming or terrain system.

The mandatory geometric computation is inverse stamping:

1. Resolve the selected form once and obtain its existing immutable shape,
   range origin, region and actor-local perception/recipient inputs once.
2. Derive offsets from native geometry. Fireball uses the current 49-cell circle;
   do not substitute the range rule's floored distance for footprint membership.
3. Stamp each eligible recipient into the possible centres around it. Include
   caster and allies according to the spell's native policy. Seed-target coverage
   selects useful centres; the other recipients retain friendly-fire evidence.
4. Intersect candidate centres with the existing aim-region mask; filter each
   stamped hit set by the connected-reach mask below, then retain centres that
   still reach a seed. Compact equal hit sets and encode the selected result.
   Keep arrays query-local. Internal storage
   must preserve more than 64 recipients, using multiple words/columns where
   needed; the measured 34-bit prototype is not a gameplay cap.

No per-aim Preview loop or all-aim native footprint loop may silently replace
these steps. Such loops belong in the correctness oracle outside timed paths.

The connected-reach mask is the part of each stamp connected to its centre.
A sealed divider removes the disconnected part. An opening within the stamp
connects the far side, so the blast reaches it. A path outside the stamp does
not connect the two sides for this cast. This is the existing native rule;
neither destructibility prediction nor a new terrain model belongs here.

Qualify a batched array implementation of that rule:

1. Read existing map-cell presence, propagation-edge blocks and terminal-cell
   blocks once over the union of candidate footprints. Keep the same four native
   neighbor directions; reuse their settled topology rather than reconstructing
   barriers from artwork or sensory visibility.
2. Represent reach as a candidate-centre by native-offset boolean array. Seed
   each existing centre. Expand through open neighbor connections while remaining
   inside that row's stamp. A reached solid terminal cell cannot forward the blast;
   preserve the native origin exception. Expand only newly reached frontier cells
   and stop when the frontier is empty; at most K-1 expansion rounds for K cells.
   Preserve directed edge orientation. This is masked flood fill batched over
   candidates.
3. Use that reach mask to filter the already stamped recipient identities.
   Actor visibility limits disclosed recipients, not the objective paths through
   which propagation can reach them. Retain existing protection/filter behavior.

No per-aim Preview/native-flood loop, automatic exhaustive fallback, or reverse
recipient flood pretending the centre's shifted envelope is unchanged. Plain
`stamp & non_wall_cells` is insufficient: it leaves isolated cells behind walls.
Measure the added mask calculation before endpoint implementation; the existing
open-floor stamping numbers do not yet include it.

A geometric enemy-minus-friendly score is neither exact expected value nor an
upper bound: a wall can shield an ally and improve an aim's actual value. Ranking
geometrically and previewing a shortlist is a heuristic, not proof of the global
optimum. The query supplies coverage identities; callers own such ranking.

Do not infer exactness from a client map that merely looks unobstructed. The
server contract is settled; qualification must establish parity and cost.

## 5. Agent CLI computation from existing public data

Verified current state:

- `PlayerAction` already has aiming shape/origin/propagation, position_region,
  range_origin and area-recipient policy (`dnd/player/choices.py`).
- Current contact rows carry coordinates and observer-membership bits; disclosed
  body facts carry faction/life/HP information (`dnd/player/facts.py`).
- Monty's `game_events` exposes authorized records, while `game_read` gives
  status/audience/receipts. `monty_sandbox/player.py` folds membership only.
- Visible cells are a composed seat view. Contact membership can identify the
  caster's perceived creatures, but the seat's visible-cell union cannot prove
  that every member can aim at a cell. Unknown recipient facts stay unknown.
- Monty supports a Python subset, not arbitrary imports. NumPy/SciPy/engine
  imports are unavailable, and existing tests reject set literals. Raw cell/row
  masks are packed base64url; do not assume Monty can import their SDK decoder.

Provide a small import-free function over explicit values: integer footprint
offsets, candidate cells, recipient UUID/position rows and seed UUIDs. The
function only stamps, intersects the supplied cell domain and compacts hit sets.
Use lists/dicts and actor-index hit sets;
no service classes or hidden callbacks. Ordinary Python can call it, and Monty
can load the same portable source through its existing toolkit mechanism.
Backend NumPy and portable implementations share behavior fixtures; the SDK must
not import engine code or acquire a NumPy dependency merely for this feature.

The input adapter runs in the CLI host's ordinary Python, using standard-library
mask decoding and pure functions over public record values. An explicitly local
Monty callback reads the existing `GameEntry.records` and the already fetched
selected action, and returns decoded input values. It never calls `game_read`,
status, Choices, Preview or any other HTTP operation. It can also consume an
archived game's records. Preparation is separate from stamping: after this local
input read, stamping and ranking run entirely inside Monty without callbacks.

The adapter consumes only current contacts, memberships, cells and disclosed
recipient fields, in record order. Apply the published range and recipient
policy here; use native-compatible footprint offsets for the supported geometry.
For actor-origin Fireball use the selected action's `range_origin`, never the
seat anchor's `SensoryFact.observer_position` as another actor's position. Unknown
life/faction/protection remains potential eligibility rather than being silently
excluded or used to label an aim safe. Keep the snapshot's cursor/revision with
these inputs and reject mixing a selected action from a different state; a local
adapter cannot refresh either silently. The cell domain from composed seat
visibility remains a candidate domain, not certified actor visibility.
Respect removals, partial updates, unknown values and audience-bit remapping
after summons/other control changes. Do not use Choices.subjects as the recipient
universe, operator journals as input, or remembered positions as current contacts.
Do not build a full replica, new Player-state API or rescan all historical
packets on each aim query. The adapter retains only these required columns and
its consumed cursor, not general object/effect/world state.

This permits local geometric computation without new server facts. It cannot
recover absent caster-specific cell visibility or undisclosed protection rules.
The helper's result remains predictive when those inputs are incomplete. The
same connected-reach rule can filter local stamps when the needed topology is
available; do not treat missing topology as open. The server's current-map hit
sets can also be ranked entirely clientside.
Expose the selected request through SDK/Monty separately so local computation
never causes an implicit HTTP call. No new enemy stat disclosure or server EV
service: caller weights use only already known facts and explicit estimates.

## 6. Ownership, transport and retention

- Native/functional code owns selected-form preparation and rules; a small
  pure computation function owns arrays. Player projection owns detached tables.
  Preserve the import DAG. No server reflection into arbitrary action fields.
- Session retains only the last selected-AoE result inside its existing discovery
  lifetime. Key: actor/seat/discovery context, row, resolved rank and seed tuple.
  Reuse existing revision/event-cursor invalidation. No TTL, background cache,
  per-turn precomputation or fresh sensory pass for each queried centre.
- Correlation belongs to each response envelope, not cached query data. Replay a
  cached answer with the current request identity. Clear on the same boundaries
  that invalidate normal choices/previews, including controller handoff.
- Extend existing host query admission, supersession, worker dispatch and size
  error handling. Keep the serial owner; do not add jobs, workers or polling.
- Export the changed protocol once from its real types, increment the current
  schema version according to repo practice, regenerate both SDK declarations
  and validate every response-local reference and echoed request field.
- Monty adds an explicit selected-request callback through its existing SDK
  bridge. Its local helper stays callable without a game callback. The client
  handoff states endpoint fields, result semantics, staleness and free aiming.

## 7. Implementation order and acceptance

1. Correct the Fireball domain mismatch and make the 30-target
   qualification reproducible with creator fixtures. Record source/environment.
2. Implement/qualify the pure stamping functions and public-input adapter first.
   Qualify the batched connectivity mask against native propagation before
   transport, including its additional timing and preparation cost.
3. Add the selected query, one retained result and existing transport plumbing.
4. Export schema and add SDK validation/lookups plus the explicit Monty callback
   and portable helper. Provide the client handoff; no client-repository edits.
5. Run focused checks and independent reviews, record timings and actual bytes.
   Do not declare completion from a geometry microbenchmark alone.

Feature checks:

- Empty-ground centre hits multiple enemies while avoiding caster/allies;
  both dense and spread 30-target cases preserve exact output within the declared
  semantics. Exhaustive native checks are an untimed oracle, not implementation.
- Visibility, recipient policy, zero HP, own-cell aiming, ranks, hidden enemies,
  multiple occupants, region edges, more than 64 recipients and unsupported shapes.
- Wall/door/unknown-cell behavior follows section 4. Test a sealed divider, an
  opening inside the stamp, an opening reachable only outside the stamp, and a
  wall shielding an ally as well as an enemy; no false friendly-fire guarantee.
- Unauthorized/stale actor, seat, revision, generation, row, rank or seed cannot
  reuse another query's result. Queries emit no events or state changes.
- Real worker/HTTP and both SDKs round-trip shared indices, empty/unsupported
  results, oversized replies and request identity without target-index confusion.
- Real Monty executes the portable helper with actual disclosed input records,
  persists its result, ranks an aim and emits an ordinary free-aim selection.
  The local host adapter decodes packed masks without HTTP; stamping itself uses
  no NumPy, unsupported sets or callbacks. Assert this with the real sandbox,
  not CPython alone. Cover multi-observer divergence and non-anchor casters,
  movement/contact loss, unknown life/faction and summon membership changes in
  the input adapter. Reuse saved input values in an unattached Monty session.

Measure initial selected request, repeated request, input preparation, actual
stamping, packing, JSON, worker/HTTP overhead and raw reply bytes separately.
Retain the 2–3 ms native open-floor baseline and 8–12 kB payload evidence as
reference; investigate material regressions without chasing busy-machine ~1 ms
noise. Measure Monty separately. Ordinary Choices and sensory/movement control
setups must not acquire eager AoE work. Wall latency requires its own evidence.

## 8. Independent review

- Antislop/scope and implementation plan-adherence reviewer: free_aim_scope.
- AntiOOP/ECS, data ownership and correctness reviewer: free_aim_ecs.
- Both must review the settled plan before implementation. During implementation
  keep an adherence reviewer active; reject silently changing the timed method,
  treating prediction as legality, adding a framework or expanding AI policy.
- Antislop review: plan design approved, including the clarified connectivity
  mask. Explicit seed selection and the narrow
  input adapter are justified by the requested coverage and CLI behavior; no
  server scoring policy, global optimum claim or exhaustive fallback is added.
- AntiOOP/ECS review: plan design approved, including batched frontier expansion.
  Pure value computation, retained-public
  input decoding, active-actor origin, conservative unknowns and request/cache
  identity satisfy the ownership and local-computation boundary.
- The human has settled the propagation rule and both reviewers checked the
  batched-connectivity clarification. Qualify parity and timings during
  implementation before endpoint work. Design review is not measured evidence
  for the new mask calculation. No production implementation has started.
