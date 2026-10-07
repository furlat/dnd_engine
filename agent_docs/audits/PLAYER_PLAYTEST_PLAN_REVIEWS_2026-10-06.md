# Playtest recovery plan: independent review receipt

Date: 2026-10-06.

Plan: [PLAYER_PLAYTEST_RECOVERY_PLAN_2026-10-06.md](../PLAYER_PLAYTEST_RECOVERY_PLAN_2026-10-06.md).

**Verdict: both independent reviewers approve the design/scope. The human subsequently authorized implementation.** Neither review certifies code completion, passing suites, smooth live play or visual acceptance.

The base-design and subsequent amendment verdicts are recorded separately below.
Both reviewers also approved the later mandatory engine/startup regression audit
in section 2 and step 0. Those approvals remain design-only.

## Document identity

Both reviewers independently approved the same substantive document:

`712b5ba21d2ebb59920916a7231644b7ce4a8eb827388dce3f58f891985d9453`

After approval, two editorial lines were updated: the header now says independently approved design, and the final review paragraph now links this completed receipt. No design, implementation or acceptance requirement changed.

Base published document SHA-256 (before the later amendment):

`4d38330bd185a405c4351ecc59496d610c78ec3bdc389477eb7a1ceb46fc4527`

## Later engine/startup audit amendment

The human explicitly raised accumulated engine slowdowns and excessive loading.
The added section makes actual-launch and native-only cost measurement mandatory
before scheduling/rendering remedies can be accepted as sufficient. It reuses
existing timing hooks, bounds compatible historical comparisons, preserves live
rules, and requires ranked measured causes and repairs in existing owners.

Both reviewers approved the amendment and step 0 at SHA-256:

`afca7a697fbbf7e3cae3e9922e1775aa7f4c3d28daf1d39bdc9911e7cbce58ce`

- Anti-slop/performance: **“Amendment approved; no blocking findings.”**
- Anti-OOP/ECS: **“Approved: the engine/startup audit amendment has no ECS or scope blocker.”**

Both requested the same clarification: disabling recording/export in a baseline
means only optional video/frame/diagnostic exports. Required native event
retention/subscribers and normal player capture/projection remain active in the
actual-launch baseline. That clarification and the header's approved status were
then applied. Neither reviewer reran implementation tests or changed source.

Approved plan SHA-256 before the later editorial resume-status update:

`03d08e0730f2b48d7383ba59679d3dbdab22b1386e44b9c53504f81e311a7375`

## Anti-slop / performance

Reviewer: local task `/root/playtest_antislop_review`. Read-only code/evidence review, followed by review of the complete plan and its revisions. No source/test edits or suite runs by reviewer.

Initial approval was withheld for two findings:

1. The draft incorrectly said turn handoff cleared loaded body/world media caches. Source shows those caches survive; only presentation/history and some derived state reset. The plan now preserves that distinction and requires measured miss/eviction evidence.
2. Frame responsiveness alone could pass while actual commands remained slow. The plan now includes engine-inclusive commitment-to-playback-ready budgets for crypt movement, door interaction, weapon attack, Fireball and enemy decisions, separately from input/frame latency.

Other corrections: the Windows security failure does not prove the cause of import duration; startup has explicit parent/child import accounting; the independent worker module entry avoids importing its native bootstrap into SDL merely to obtain a callable target.

Final verdict: **“Approved as a plan. No remaining blocking anti-slop or performance findings.”** Reviewer explicitly confirmed P01–P29 coverage, measured-versus-hypothesized causes, bounded worker ownership and performance acceptance. This does not approve current provisional source changes.

## Anti-OOP / ECS / causality

Reviewer: local task `/root/playtest_ecs_review`. Read-only code/evidence review, process-boundary feasibility review and review of the complete revised plan. No source/test edits or suite runs by reviewer.

Initial approval was withheld for two findings:

1. Prior draft lighting selection referred to ordinary-versus-special per-cell provenance that current snapshots do not contain. The plan now selects one complete already-recorded effective-light observation and keeps its observer provenance, with overlapping-light/sight-loss acceptance.
2. Shared knowledge was initially specified only for discovery/current observations. The revised contract retains last authorized support/object values and observation cursors, passes the same scope through exact-row validation, and prevents hidden current walkability/door/hazard values from leaking into remembered route previews. Actual physical contact and spell-specific personal sight remain native constraints.

The reviewer additionally verified bootstrap inside the independent worker, detached public discovery fields, private native `Operation`/`AdvanceResult`, one native owner and one historical playback stream, generation/epoch validation, no automatic command retries, and adaptation of deterministic tests to real worker readiness.

Final verdict: **“Approved for plan/scope from the anti-OOP/ECS/causality review. No remaining design blockers.”** Implementation must still verify pipe framing/output ownership, diagnostic draining, bounded intake and nonblocking shutdown on actual Windows.

## Evidence boundary

- The source tree remains dirty and provisional. Existing UI, rendering, native and test edits were neither committed nor rolled back by this planning phase.
- New deliverables in this phase are the plan, this receipt and status clarifications in the recovery plan/complaint ledger.
- No new implementation test results are claimed for the planning phase.
- Existing 35-frame SDL-dummy profiling identifies costs; it does not prove real-display FPS, WASD responsiveness, first-use spell performance or long-session behavior.
- P16's exact wrong-attack-motion cause and P23's exact threshold-pixel cause remain explicitly unverified. Step 0 requires concrete traces before changing those owners. The plan does not invent diagnoses for them.
- Production work resumes only when the human resumes implementation. Each independent implementation step requires the plan's review and acceptance gates; these plan approvals cannot substitute for them.

## October 7 — renderer/media-readiness amendment

The human requested pygame-ce/OpenGL first-principles work and later PixiJS
shader reuse. Both local reviewers approve **step 1 feasibility**, not a
production migration, in
[the integrated amendment](../GPU_RENDERER_AND_MEDIA_READINESS_2026-10-07.md).

Anti-slop required composition/picking/residency choices to be demonstrated
before contract freeze, plus direct GLSL ES 3.00 compilation/fixture checks.
The amendment includes these gates and separates byte-exact geometry/selection
from permitted specified color-rounding differences. The sparse CPU depth-band
shortcut was rejected because it can reverse translucent sibling order.

ECS required explicit latest-versus-historical admission semantics, bounded
decode result ownership/generation and pin transfer, preservation of native
cancellation media, and picking against the exact presented frame including
nonselectable occluders. These requirements are incorporated. Preparation may
not retry native actions or mutate lookahead contacts/facings/lifetime state.

No reviewer claimed to run the private GPU proofs or the complete game. Full
composition, working-set admission and input/picking gates remain open.

## October 7 — full migration addendum review

The human subsequently requested a complete migration plan integrated with the
remaining recovery, then clarified: repair oversized packing first, keep 32 FPS,
audit spells playing too fast separately, and avoid unnecessary XYZ work. The
[expanded addendum](../GPU_RENDERER_AND_MEDIA_READINESS_2026-10-07.md) now defines
G0–G8, complete family/entry-point/UI coverage, passive contracts, resource and
clock ownership, exact source-removal gates and all P01–P31 integrations.

Reviewed document identities:

- GPU addendum SHA-256:
  `86159cdd1199cb4b0232f32d398c6c87592adfa3daca6579cadfb5c9f32092be`.
- Parent recovery plan SHA-256:
  `59ed36a2f89e65fd4cb742f1914b59931739d40113dd143e410ded6ed8a2292a`.
- Recovery index SHA-256:
  `4e557bae6e8154319c350f5a6fe9ba44b60d9609b423edd6fd3ff0916d525e6f`.

Both local reviewers initially required one correction: no-XYZ **evaluation**
on the current frame must not be mistaken for proof that XYZ **resources** are
unneeded for the whole admitted interval. Rotation, retained effects or new
historical geometry can create later ordering/clipping consumers. The amended
plan makes conservative plane requirements part of readiness, including all
allowed views, persistent-media dependencies before subsequent admission and
global-depth/sibling/frame-mix semantics. G0 and G2 now prove those transitions
without late loads, changed pixels/picks or CPU XYZ images.

Final anti-slop/performance verdict, local `/root/playtest_antislop_review`:
**“Approved: the expanded full GPU migration plan has no remaining blocking plan
findings.”** Explicitly covers packing first, unchanged 32 FPS, separate speed
audit, GLSL portability, complete UI/renderer migration, removal and all complaints.

Final anti-OOP/ECS/import-DAG/causality verdict, local `/root/playtest_ecs_review`:
**“Approved: full GPU migration plan, from the ECS/import-DAG/causality review.
No remaining plan blockers.”** Explicitly covers G0–G8 ownership, dependencies,
historical/resource admission and removal gates.

Both reviews were read-only, with no tests or edits by reviewers. These are
**full-plan approvals**, not the earlier feasibility-only approvals. They do not
declare G0's unresolved measured choices complete, approve production cutover,
prove the packing repair's runtime parity or certify smooth gameplay. Each
implementation package and final actual Windows acceptance still require the
stated independent reviews/evidence. No other user chats were contacted.
