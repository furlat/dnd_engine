# Network server / NeuroClient / Studio plan reviews

Date: 2026-10-07. Planning only. No production implementation or tests were
performed for this study. Existing dirty source changes predate this planning work.

Reviewed documents:

- [Master plan](../../NETWORK_SERVER_NEUROCLIENT_STUDIO_PLAN_2026-10-07.md)
- [Authoring coverage](../../NEUROCLIENT_AUTHORING_COVERAGE_2026-10-07.md)
- Source/function/module/semantic-validator ledgers in this directory.

Two independent local reviewers examined the design and its source evidence.
No other chat was read or contacted.

## Anti-slop / server ownership

Reviewer: `server_plan_antislop`.

Initial findings and final corrections:

1. Deduplicate existing command identities before stale-action/revision checks.
2. Separate a writable attachment epoch from the shared seat credential; specify
   replacement, pending commands and monotonic command numbering.
3. Resume SSE from application `lastReduced`, not browser Last-Event-ID, which can
   advance before successful reduction. Stop on invalid data without acknowledging.
4. Release bounded live-delivery credit with contiguous reduction ACKs, independent
   of animation completion; avoid a permanently full retained-history window.
5. Specify whole-envelope limits, record-once private spool, quota/expiry and explicit
   unavailable resume. Do not introduce speculative fragmentation or durable saves.
6. Budget working/live-delivery/resource memory separately from retained native and
   public history. Do not promise flat total memory while retaining events.
7. Apply the immediate input-feedback budget to local UI acknowledgment; measure
   terminal native reply latency separately.

Final result: **approved as a planning document, no remaining concrete blockers
in review scope**. Approval covers design coherence, engine ownership, bounded
scope and staged validation, not implementation correctness or performance.

## ECS / import DAG / renderer and authoring coverage

Reviewer: `client_plan_ecs`.

Initial findings and final corrections:

1. Assign the integrating `game/app.py` map painter to R02/R03/R10/R21; it is not
   just an obsolete entrypoint. Correct both generated destination ledgers.
2. Cover world data outside AnimationData: AssetDocument/WaterSource, the 15-field
   AssetCatalog, WorldBindingsSource, EnvironmentDocument and UI sources, with
   canonical source/editability and versioned release ownership.
3. Distinguish structural JSON Schema from Python semantic validators. Inventory
   47 decorated validators plus loader-level rules; require shared accepted/rejected
   Python/TS fixtures and pure semantic validation for live admission and Studio.

Final result: **planning approval for ECS/DAG, renderer coverage and Studio
authoring; no remaining blocking findings**. Reviewer verified all 53 AnimationData
fields are covered exactly once, the map-painter ownership correction, and one
production TS compiler/sampler/renderer for live play, replay and Studio.

The source inventory contains 162 modules, 959 declared functions/methods,
50 public record declarations and 256 authored JSON files. These are coverage
denominators, not evidence of a completed port or visual/performance parity.

## Human UI correction and independent delta review

After the initial approvals, the human clarified that NeuroClient UI was better
than pygame but lacked many features. The initial inference of wholesale UI reuse
was wrong and was removed from the master, authoring companion and recovery index.

The revised §7.1 treats existing widgets as candidates. Retain/adapt/replace decisions
must meet the complete current feature requirements; neither old UI is the feature
authority. Icons/portraits are supplied separately and are not the whole UI task.
No blanket old-UI reuse or DOM rewrite is authorized by this plan.

Both reviewers approved this correction with no new blockers. The ECS reviewer
explicitly limited approval: **the per-component UI study, reuse decisions,
feature coverage and visual acceptance remain unfinished and unapproved**.
Backend approval is unchanged.

## Implementation proof still required

Actual GPU composition/picking/readiness, wire privacy/version fixtures, native
performance, functional UI coverage, live Studio parity and the complete playable
journey must pass the plan's staged gates. These reviews do not certify them.
Final source hashes below identify this documented revision; a review-status-only
edit to the master followed the architecture approvals.

| File | SHA-256 |
|---|---|
| NETWORK_SERVER_NEUROCLIENT_STUDIO_PLAN_2026-10-07.md | `473f014c67405ac7d4f67984e27a2867a1675aa05ffd94a008a385de8c236a52` |
| NEUROCLIENT_AUTHORING_COVERAGE_2026-10-07.md | `785d4ec7a8d9e770fb8913eb24ec16da7f82241213fc0c6f6b792fb7d64d8e30` |
| source-inventory.json | `eabdf73eb63ecde3c244c85fd11d273462f42f9780a71e0ea83fa6539d2865cf` |
| function-port-ledger.csv | `a9c6156ff1cdc39ff18f3f68da8ccf1108bb6a38820eed9d8e76e91f2e464f2d` |
| module-port-ledger.md | `9e3f44f09fd37e7608e24cf32cefa8a6f1c7d6f4b7878fc1e590ca981feecd6b` |
| semantic-validator-ledger.csv | `e3946cd675f86b98a585b6082921066ffdfdf6ffa6bf54695de4433ee4d992c9` |
| selected-content-index.json | `cd78a0649246ca9644b9997cec76eef286161fd0b96eb74fda386024dc9fa6d3` |
