# Free-aim preview repair — 2026-10-22

Human authorization: fix the preview bug and commit, then investigate the
cheapest useful AoE aiming computation. Follow the plan-following skill.

## Scope and acceptance

- Behavior: moving a ground aim within one discovery must return that aim's
  geometry, affected creatures and admission, including when revisiting an aim.
- Boundary: real worker Choices/Preview with detached serialized responses.
- Input: Fireball aimed at two empty ground positions, in both orders, followed
  by repeated aims and an illegal position in the same discovery.
- Output: correct centre and recipients for each legal position; an illegal aim
  cannot inherit a legal preview. Queries leave the event cursor unchanged.
- Repair only preview cache identity, preserving the existing bounded cache,
  discovery invalidation, lazy region contract and authoritative geometry.

## Execution

1. Add a public-boundary regression and demonstrate the current failure.
2. Include selected target coordinates in the existing cache key; run the new
   regression and relevant compact/compound/query tests.
3. Obtain antislop/scope and antiOOP/ECS review, including plan adherence. Record
   results and commit the bounded repair. No client changes or push.
4. After committing, inspect and compare economical ways to generate and score
   useful AoE centres. Distinguish geometric candidates from exact legal hits;
   account for barriers, subjective knowledge and friendly fire. Any benchmarks
   are exploratory, not a new gameplay implementation.

## Review and status

- Antislop/scope and ongoing plan adherence: free_aim_scope reviewer.
- AntiOOP/ECS: free_aim_ecs reviewer.
- Status: repair implemented; both independent reviews passed.

## Validation

- Before repair: both new regression cases failed at the second aim's geometry
  centre (2 failed in 4.83s). The first aim's cached result was reused.
- After repair: 31 passed in 7.76s across free-aim preview, compact choices,
  compound choices and handoff discovery regressions. The new cases include
  exact recipients, revisits, illegal-aim refusal and event-cursor purity.
- Command: `UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv uv run
  --no-sync python -m pytest tests/player/test_free_aim_preview.py
  tests/player/test_compact_choices.py tests/player/test_compact_compound_choices.py
  tests/player/test_handoff_discovery_regressions.py -q`.
- Source is on WSL's `/mnt/c`; the virtual environment is on `/home/tommaso`.
  These are suite durations, not gameplay latency benchmarks. No geometry,
  discovery or sensory computation changed. `git diff --check` passed.
