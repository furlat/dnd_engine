# Cleanup test-repair plan — independent anti-slop review

**Verdict: APPROVE the reviewed repair plan.** No blocking anti-slop finding remains in this revision. This approves the bounded repair proposal, not the current implementation or any projected passing total. My independent implementation verdict remains **REQUEST CHANGES** until its reproduced defects and the other admitted blockers are repaired and verified.

Reviewed plan: [CLEANUP_TEST_REPAIR_PLAN_2026-10-03.md](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/CLEANUP_TEST_REPAIR_PLAN_2026-10-03.md).

Exact reviewed SHA256: `78f6cb43170e26eff5b8f37dbf886838d98070ec33e1b262ea8e93c4e7200c06`.

Baseline: `981079bc0208dbb23f3ccc927347eef77fef4c30`. The underlying implementation remains the snapshot in [my completed implementation review](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/CLEANUP_IMPLEMENTATION_ANTISLOP_REVIEW_2026-10-03.md), whose SHA256 is `ee7ed7c12901d3e12f3b44235717f72d3c9c0e11bafc1799ddfd13198c135a8c` and changed-production manifest digest is `22273712a7b6fb924976fb036feb30d84b126212543af811a346c9a9288843fa`.

## Review basis and limits

I read the full repair plan and checked it against AGENTS.md, RECOVERY_PLAN.md, HOW_TO_TEST.MD, the approved cleanup scope, the actual code inspected for my implementation review, and the independent ECS/event findings. I additionally inspected the existing condition admission boundary, contextual modifier evaluation/cache readers, the two server-dependent progression modules, and the named current character-build/durable-item tests.

The implementation review independently reproduced legacy Fire Shield ownership corruption and Spike Growth results being included in both the Thunderwave cast cue and standalone damage cues. Those reproductions, rather than another reviewer's approval, anchor the causal-identity portions of this plan review. The other reviewers' findings remain attributed evidence; this plan review does not claim to independently reproduce every ECS/event issue or reclassify all 294 game cases. No new production/test changes or test runs were made for this plan review.

## Concerns resolved in the revised plan

1. **The independently reproduced Spike Growth omission is now an exact repair.** [Plan lines 227 onward](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/CLEANUP_TEST_REPAIR_PLAN_2026-10-03.md:227) identify the existing entry handler, require `independent_resolution=True` and retained field origin, and preserve triggering ancestry. Acceptance uses the actual failed-save two-entry Thunderwave push: one 2-damage cast application and two independent 2-damage entries, with each result presented once and no early cast HP snapshot containing later exposure. Ordinary Move is also covered. This addresses the producer defect directly, without a spell-name filter in presentation or a new damage executor. Checking sibling writers is completion of the same ownership migration, not authorization for new spell rules.

2. **Paused-server disposition no longer promises an invented native persistence service.** [Plan lines 413 onward](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/CLEANUP_TEST_REPAIR_PLAN_2026-10-03.md:413) retain database/API/deployment assertions in an explicit paused lane and name the actual active boundaries: authenticated `CharacterItemV2` JSON, `CharacterBuild` / `create_character`, and native equipment behavior. These exist in the inspected tests. The earlier wording about a “real current persistence boundary” could have required building save/resume to replace server tests; the final plan explicitly forbids that expansion. This agrees with [RECOVERY_PLAN.md:368](/mnt/c/users/tommaso/documents/dev/dnd_engine/RECOVERY_PLAN.md:368), which retires old server failures from current game acceptance and states that playable save/resume is not connected. Paused failures must still be reported, as the plan requires.

3. **Concentration repair uses an existing admission mechanism and preserves replacement semantics.** [Plan lines 307 onward](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/CLEANUP_TEST_REPAIR_PLAN_2026-10-03.md:307) point to the real `required_condition` and prepared-removal path in [base_block.py:1276](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/base_block.py:1276). They account for Entity's additional admission checks and its narrower override instead of merely invoking the base method. They explicitly reject moving concentration admission earlier as a complete fix: child/sustainer failure must preserve the old owner and children. This is reuse of the current lifecycle boundary, with exact ownership, rather than a general rollback framework.

## Why the remaining plan is bounded and reviewable

- **Failure accounting is honest.** The 294 total is labeled a residual classification from prior receipts. Setup success is not asserted to imply behavioral success. Newly exposed failures require dispositions, final active suites collect every case, and paused cases retain explicit commands and identities. No mass xfail, `importorskip`, or filtered-catalog success is accepted.
- **Tests preserve their actual contracts.** Current production assets remain authoritative. Minimal authored fixtures are reserved for geometry/timing/conversion contracts and use the existing loader API. Finite media checks remain while current sustained glyph tests follow current assets. Ambient idle and simultaneous condition changes are checked at the correct presentation time with native order retained. Expected values cannot simply be sampled from the new output.
- **Archive repair does not fabricate causal proof.** [Plan lines 200 onward](/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/CLEANUP_TEST_REPAIR_PLAN_2026-10-03.md:200) reject immediate-parent, target/time, and presentation-recipe guesses. Unknown current-schema causes stay supported; ambiguous historical ownership receives an exact diagnostic with original data preserved. Explicit current references cannot be rewritten. This addresses my F1 in both input routes without requiring runtime rules during replay.
- **Presentation repairs retain one owner for each committed result.** Unknown-source damage uses its bound result identity and the existing scheduling route for normal and temporary HP. Construction commits sections before its existing CREATED publication. Terminal-provider exemption stays limited to the attacked section; intervening sections remain blockers. None requires duplicate timelines, synthetic creation events, or altered damage rules.
- **Read purity and provisional cleanup target existing owners.** Speed evaluation must stop mutating serialized modifier state through the current evaluator. Rejected effects use the current condition-owned release hook, with successful/replaced sources protected. The plan forbids restoring repeated full copies, adding parallel speed state, or making action interruption a global refund/rollback policy.
- **Schema and AI work complete existing passive contracts.** Named current authoring types and omitted native damage-profile fields are exported/projected directly. The plan neither introduces another schema language nor pulls live rule executors into client/AI data. Fresh-process import checks and actual round trips are required separately from gameplay checks.
- **Content and visual acceptance do not reopen product scope.** Evidence changes require explicit verified inventory deltas. Retained spells and powered items are checked at their ownership boundaries. The visual matrix uses current recordings/assets and real public replay. It does not authorize ammunition expansion, grapple work, new artwork, new gameplay rules, or broad scenario redesign.

## Delivery conditions already present in the plan

The final implementation must provide the specified public-boundary regressions, full active-suite receipts, paused-case dispositions, import/typing checks, visual evidence, and fresh independent implementation reviews. A passing plan review cannot substitute for them. If a proposed fix needs a new gameplay decision or another runtime framework, it falls outside this approval and must return with that concrete conflict.

No additional production abstraction or speculative test campaign is requested by this review.

## Supplementary inspected-file snapshot

Production files already appear in the implementation manifest; these exact hashes also anchor the extra plan-boundary checks. Paths are relative to `/mnt/c/users/tommaso/documents/dev/dnd_engine`.

| File | SHA256 |
| --- | --- |
| `dnd/core/base_block.py` | `f47a0d368848771b386a45e29cbb8a370c1199504c8319a7c1816b2c3913aa76` |
| `dnd/entity.py` | `001078733ea7a5b74e4a7023539c88b3578c18fff42f788c99242c25ca59f5ce` |
| `dnd/core/modifiers.py` | `ffb95f52ea8386e69031d8011e0dc726898c1458c3fdba2b87d0f72984897681` |
| `dnd/core/values.py` | `5c5eed5f140b235d2d98061d4b195c5a42b50149b936752de02aff635d382f40` |
| `tests/progression/test_direct_item_durable_and_proficiency.py` | `bbdd3c365cab9d7f77a8d5c0c36d64262e93748bf792bf918e186cae97a50bcf` |
| `tests/progression/test_direct_character_builds.py` | `d956d9477f8baf5451e84abc674a276ddba717fff27414efd36fd130ce1823a0` |
| `tests/progression/test_persistent_character_equipment_mutation.py` | `454e5c95c10cf0e607e8dda6e014333e174719c992e20ef6abe329d3a230b4dc` |
| `tests/progression/test_persistent_character_scenario_deployment.py` | `69ab8e3daf7f276a5442572ca2bd20444c79f53d442ddbb4c757873376ff22ab` |
| `HOW_TO_TEST.MD` | `7d02cf6ab9285bcad24ce386299ecf26a9b27ebe88494ccbb70907bfb317342c` |
