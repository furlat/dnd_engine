# Known Issues

Bugs, failing tests, and hypotheses documented during implementation sessions. Updated by dispatching background sub-agents when issues are found during unrelated work.

## Format

```
### [SHORT TITLE]
- **Found**: [date or session context]
- **Test file**: `examples/test_xxx.py` (if applicable)
- **Error**: [brief error description]
- **Hypothesis**: [what might be causing it]
- **Status**: OPEN | INVESTIGATING | FIXED
```

## Open Issues

### Movement pathfinding leaks invisible entity positions
- **Found**: 2026-02-24
- **Test file**: N/A
- **Error**: `is_walkable_for()` blocks movement through cells occupied by invisible entities, allowing observers to deduce their position by noticing gaps in reachable paths.
- **Hypothesis**: The walkability check treats invisible entities the same as visible ones — it blocks pathing regardless of whether the observer can perceive the entity. An observer who cannot see an invisible entity should still be able to path through (or attempt to path through) that cell, rather than receiving an implicit "something is here" signal via unreachable positions.
- **Status**: OPEN

### API error messages need improvement
- **Found**: 2026-02-24
- **Test file**: N/A
- **Error**: HTTP 400 responses from the server return generic error messages with no structured detail, giving the AI agent no actionable information about what went wrong.
- **Hypothesis**: Error responses should include structured context: current action economy state (actions/bonus actions/reactions/movement remaining), the specific reason the request was rejected, and a list of valid alternatives or corrective steps. This would allow the AI agent to self-correct rather than retry blindly or stall.
- **Status**: OPEN

## Fixed Issues

### Killing invisible units shows "???" for sub-events in combat log
- **Found**: 2026-02-24, PvP session
- **Fixed**: 2026-02-24
- **Root cause**: Layer 1 (temporal) trumped Layer 2 (identity) — when a sub-entry's `perceiver_uuids` didn't include the observer, `_full_anonymize()` ran which ignored `revealed_entity_uuids` entirely. Condition events (ConditionRemoval, ConditionApplication) have source/target = the invisible entity itself, so the hero wasn't in `perceiver_uuids`.
- **Fix**: In `filter_combat_log()` (`log_filter.py`), when a sub-entry fails Layer 1 BUT involves a revealed entity, bypass `_full_anonymize` and use `_anonymize_entry` instead (which respects the revealed set).
- **Test**: `examples/test_info_leak_fixes.py` Test 10 (`test_invisible_kill_reveals_sub_events`)
- **Status**: FIXED



