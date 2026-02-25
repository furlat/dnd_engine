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

### API error messages need improvement
- **Found**: 2026-02-24
- **Test file**: N/A
- **Error**: HTTP 400 responses from the server return generic error messages with no structured detail, giving the AI agent no actionable information about what went wrong.
- **Hypothesis**: Error responses should include structured context: current action economy state (actions/bonus actions/reactions/movement remaining), the specific reason the request was rejected, and a list of valid alternatives or corrective steps. This would allow the AI agent to self-correct rather than retry blindly or stall.
- **Status**: OPEN

### MULTI_ENTITY spells (Magic Missile) cannot split targets via agent CLI
- **Found**: 2026-02-25, PvP session analysis
- **Error**: Claude can only cast Magic Missile at a single target — all darts hit the same enemy. The `cmd_cast` function in `cli/agent.py` only parses one target index and never passes `extra_target_uuids` to `client.execute_action()`. The full pipeline supports it: `APIClient.execute_action()` accepts `extra_target_uuids`, the server passes them to `execute_by_index()`, and `MagicMissile.get_all_targets()` fills remaining darts with the primary target when extras aren't provided. But the agent CLI is the bottleneck.
- **Affected spells**: All `TargetType.MULTI_ENTITY` spells — `MagicMissile` (evocation), `EldritchBlast` (evocation), `ScorchingRay` (evocation), `HoldPerson` (enchantment), `Command` (enchantment), `ChainLightning` (conjuration), `TestBless` (enchantment)
- **What's needed**:
  1. `cmd_cast` in `cli/agent.py` (~line 1800): detect MULTI_ENTITY spells and parse multiple target indices (e.g. `cast Magic Missile 0 0 1` = 2 darts at target 0, 1 at target 1). Resolve target indices to UUIDs and pass as `extra_target_uuids`.
  2. `watch` output (~line 875): show dart/projectile count for MULTI_ENTITY spells so Claude knows how many targets to specify.
  3. `dnd_auto_prompt.md`: add multi-target syntax example.
  4. Usage hints in `cmd_cast`: show `cast Magic Missile 0 0 1` style hint for MULTI_ENTITY spells.
- **Workaround**: Single-target cast works — all projectiles go to the same enemy. Suboptimal but functional.
- **Status**: OPEN

## Fixed Issues

### Killing invisible units shows "???" for sub-events in combat log
- **Found**: 2026-02-24, PvP session
- **Fixed**: 2026-02-24
- **Root cause**: Layer 1 (temporal) trumped Layer 2 (identity) — when a sub-entry's `perceiver_uuids` didn't include the observer, `_full_anonymize()` ran which ignored `revealed_entity_uuids` entirely. Condition events (ConditionRemoval, ConditionApplication) have source/target = the invisible entity itself, so the hero wasn't in `perceiver_uuids`.
- **Fix**: In `filter_combat_log()` (`log_filter.py`), when a sub-entry fails Layer 1 BUT involves a revealed entity, bypass `_full_anonymize` and use `_anonymize_entry` instead (which respects the revealed set).
- **Test**: `examples/test_info_leak_fixes.py` Test 10 (`test_invisible_kill_reveals_sub_events`)
- **Status**: FIXED

### Movement pathfinding leaks invisible entity positions
- **Found**: 2026-02-24
- **Fixed**: 2026-02-25
- **Root cause**: `is_walkable_for()` treated invisible/hidden entities the same as visible ones — blocked pathing regardless of observer perception, leaking position info through gaps in `senses.paths`.
- **Fix**: Subjective vs objective walkability. `compute_paths()` and `is_walkable_for()` accept `subjective=True` to skip imperceivable blockers. Actual movement uses objective check; collision fires `MOVEMENT_COLLISION` event which de-stealths Hidden entities. `collision_blocked` set on Senses remembers collision positions until turn start.
- **Test**: `examples/test_invisibility_pathfinding_leak.py` (13 tests, 31 assertions)
- **Files**: `gridmap.py`, `sensory.py`, `entity.py`, `actions.py`, `conditions.py`, `encounter.py`, `events.py`
- **Status**: FIXED



