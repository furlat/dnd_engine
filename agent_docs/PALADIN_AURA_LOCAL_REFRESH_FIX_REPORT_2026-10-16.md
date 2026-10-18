# Paladin aura local refresh repair

2026-10-16. Implemented in
`/home/tommaso/.codex/worktrees/spells-rank-one-two/dnd_engine` under the
[finite repair plan](plans/PALADIN_AURA_LOCAL_REFRESH_FIX_PLAN_2026-10-16.md).

## Change

Paladin aura provider refresh now visits native grid-local occupants and exact
recipient IDs in the zone's existing linked membership receipts. This preserves
cleanup of a retained lease whose previous removal was refused, even when its
recipient is now outside the footprint. IDs are deduplicated and processed in
deterministic order using existing membership apply/remove ownership.

When another entity changes faction, the aura considers only that entity if it
is inside the footprint or has a retained lease. A distant unrelated change
returns without local reconciliation. Provider faction changes refresh the
local occupants/retained leases. Native moving anchors and footprint/radius
updates retain their existing implementation.

The unused turn-start world-scan override was deleted. No additional membership
registry, manager, cache, shared event-dispatch mechanism or client work was added.
Production edits are limited to the aura implementations in
`dnd/classes/paladin.py`.

## Related recovery defect found by the new native control

Before the repair, a zero-HP Paladin moved and then healed to 5 HP/ALIVE did not
restore any of its three auras. That failed in the pre-edit native test lane;
the other 18 focused cases passed.

The old aura listener subscribed to LIFE_STATE_CHANGE/EFFECT. Entity only records
that derived fact at COMPLETION, and ordinary completion records do not dispatch
handlers. Changing the listener phase alone was also tested and did not fix it.
The final implementation replaces the inert trigger with existing
DAMAGE_APPLIED/EFFECT and HEALING_APPLIED/EFFECT for the provider. These run
after HP commits; Healing Applied also runs after recovery of the ALIVE state.
This is a separate correctness correction from removing the world scans.

This validation covers damage/healing recovery, not pure direct revival of a
DEAD provider. `commit_revival` has no matching post-commit handler fact; that
pre-existing aura coverage gap is outside this bounded locality repair. Shared
life-state dispatch was not changed to conceal it.

## Matched diagnostic

The same maintained script and 18 native operations were used before and after:

- Before: `GLOBAL_NATIVE_PALADIN_AURA_WORK_COUNTS_2026-10-16.jsonl`.
- After: `PALADIN_AURA_LOCAL_REFRESH_AFTER_WORK_COUNTS_2026-10-16.jsonl`.
- Runner: `python -m tests.manual.global_paladin_aura_refresh_performance`.

Environment: Python 3.13.12, Linux/WSL2, source on the Linux filesystem. Each
scenario has one level-10 Paladin with three auras, only its owner locally, and
1/25/100 unrelated distant actors.

| Native operation | Before global enumerations | Before remote removal attempts, 1/25/100 actors | After global enumerations | After remote removal attempts |
| --- | ---: | --- | ---: | ---: |
| Add Poisoned to owner | 3 | 3 / 75 / 300 | 0 | 0 |
| Change distant actor faction | 3 | 3 / 75 / 300 | 0 | 0 |
| Move owner one tile | 3 | 3 / 75 / 300 | 0 | 0 |
| Move distant actor | 0 | 0 / 0 / 0 | 0 | 0 |
| Owner turn start | 0 | 0 / 0 / 0 | 0 | 0 |
| Distant actor turn start | 0 | 0 / 0 / 0 | 0 | 0 |

Afterward, owner membership changes make three indexed occupant queries and
three existing-membership apply calls at every distant population size. Owner
movement makes 12 indexed occupant queries and six membership apply calls; it
previously made nine occupant queries in addition to its global scans. Distant
faction changes now make zero occupant queries and zero membership apply/remove
calls. The remote movement and both turn controls also remain at zero.

These are work-count comparisons, not a whole-engine latency or percentage
speedup claim. Work still scales with the actual aura footprint, local occupants
and exact retained membership recipients. An independent reviewer reproduced
all 18 after rows against the final implementation.

## Native behavior qualification

New cases in `tests/progression/test_paladin_aura_local_refresh.py` cover:

- Local recipient faction enter/leave and actual Protection save bonus.
- Unrelated distant faction change preserving existing local memberships.
- Owner faction changes with two overlapping Paladins, exact source survival
  and the stronger remaining Protection bonus.
- Unconsciousness and zero-HP recovery after moving to different neighbors.
- Undeploy/redeploy and subsequent local faction eligibility.
- Refused exit removal retaining an exact out-of-range lease, followed by a
  local provider refresh that retries cleanup and preserves unrelated Poisoned.

Existing native Paladin cases cover ordinary movement/reentry, level-18 radius
expansion/shrink, source removal, charm/fear handling, other class abilities and
death-save bonuses. The focused lane passes all **19 cases** (4.98s); each
review role independently reproduced 19 passes.

The final combined Paladin, shared spatial/anchored/occupancy/crossing,
prepared-condition/transform ownership and global audit-regression batch passed
**145 tests**, with the **36 pre-existing strict expected failures unchanged**
(19.19s). Ruff passes for the new native test file and the worktree diff check
is clean. No full-repository pass is claimed.

Anti-OOP and anti-slop reviewers approved the actual implementation. The
plan-adherence monitor checked scope, the related recovery correction and matched
diagnostic evidence. All existing unrelated dirty work is preserved.
