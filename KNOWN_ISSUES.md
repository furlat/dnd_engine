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

### Orchestrator drain timeout causes commands to execute against wrong entity
- **Found**: 2026-02-25, PvP session (Match 1, Round 2)
- **Test file**: N/A (orchestrator/CLI issue, not game engine)
- **Error**: After a 45-second drain timeout kills the Claude subprocess, buffered commands (e.g. `dodge`) execute against the *next* entity in turn order instead of the intended entity. In the observed case, a `dodge` command meant for Skeleton Warlock was applied to Skeleton Archer after the turn auto-advanced.
- **Root cause**: Two problems:
  1. **Why the subprocess got stuck for 45s**: Claude's reasoning/output exceeded the drain buffer capacity or the subprocess hung during output. The drain thread waits for the subprocess to complete writing, but if Claude is mid-generation when `end` fires, the remaining output can take arbitrarily long. The 45s timeout is a safety net, but it's also possibly too short for complex reasoning.
  2. **Why the wrong entity gets the command**: After `process.kill()`, the orchestrator advances to the next entity's turn and writes a new session file. But orphaned/buffered commands from the killed subprocess can still execute via the agent CLI. The agent CLI loads the *current* session file (now pointing to the next entity) and executes against it. There's no validation that the command originated from the correct entity's turn.
- **Impact**: Entity gets actions applied without spending action economy (Archer got Dodging for free). Turn log file for the affected entity is never created.
- **Potential fixes**:
  1. After `process.kill()`, discard any remaining buffered output instead of letting it execute
  2. Add a turn-sequence token to commands so stale commands from killed subprocesses are rejected
  3. Validate entity UUID at command execution time against the server's actual active entity
  4. Investigate why the subprocess takes 45+ seconds to drain — may need to interrupt Claude's generation more aggressively or increase the timeout
- **Status**: OPEN

### SELF-range AOE spells filtered out when no visible targets in range
- **Found**: 2026-02-25, PvP session (Match 1, Round 4)
- **Error**: Burning Hands and Thunderwave completely vanish from the action list when no visible enemies are nearby, even though the caster has spell slots. The agent cannot cast them at empty ground to flush hidden/invisible enemies (area denial). Fireball does NOT have this problem because it has `RangeType.RANGE` (150ft) and `include_self=True`.
- **Root cause**: `_collect_aoe_actions()` in `entity.py` uses `aoe_require_targets=True` (default) which prefilters positions to only those near visible entities. For SELF-range spells with `include_self=False`, the caster's area is excluded from the prefilter candidates, so when no enemies are visible nearby, ALL positions are filtered out.
- **Fix**: When prefilter yields 0 positions for a SELF-range AOE, include the spell with empty `valid_targets` instead of skipping it. The AI/CLI can then cast at any visible position via `execute_position_action`. Also updated `cmd_cast` in agent.py to not error on 0 valid_targets when coords are provided.
- **Affected spells**: BurningHands, Thunderwave, LightningBolt (and any future SELF-range AOE spells)
- **Test**: `examples/test_self_range_aoe_availability.py`
- **Status**: FIXED

## Fixed Issues

### Torch-driven Hidden removal during movement has no visible combat log
- **Found**: 2026-02-25, PvP session (Match 2, Round 3)
- **Fixed**: 2026-02-25
- **Root cause**: `_on_light_movement_event` callback called `move_light_source()` → `_fire_light_batch_events()` without passing `parent_event`. The `SPATIAL_LIGHT_CHANGED` events were orphaned from the movement event tree. When `hidden_reveal_processor` called `remove_condition("Hidden", parent_event=light_change_event)`, the ConditionRemovalEvent was a child of the orphaned light event — invisible to `StepMovementEvent._collect_child_combat_logs()`.
- **Fix**: Threaded `parent_event` through the light callback chain (`_on_light_movement_event` → `move_light_source` → `_fire_light_batch_events` → Tier 1 SPATIAL_LIGHT_CHANGED events). In `hidden_reveal_processor`, walk up to the parent event (step event) for the removal so ConditionRemovalEvent becomes a direct child of StepMovementEvent. This makes the removal appear in the movement combat log and propagates `revealed_entity_uuids` correctly.
- **Files**: `dnd/core/gridmap.py`, `dnd/conditions.py`
- **Status**: FIXED

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



