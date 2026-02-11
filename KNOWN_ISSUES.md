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

### Duck-typed getattr in SpatialSensesCallback
- **File**: `dnd/blocks/sensory.py`, lines ~193 and ~199
- **Error**: `SpatialSensesCallback.__call__()` uses `getattr(event, 'position', None)` and `getattr(event, 'entity_uuid', None)` instead of proper type narrowing (isinstance checks or typed event access).
- **Why it matters**: Bypasses the type system entirely. If the callback receives an unexpected event type, these silently return `None` instead of failing loudly, masking bugs. Pylance/Pyright cannot verify correctness.
- **Fix**: Use `isinstance` checks to narrow to the specific event type, then access typed fields directly.
- **Status**: OPEN

## Claude Test-Writing Pitfalls

Errors made by Claude when writing `test_lighting_stealth_integration.py` (2026-02-11). Documented so Claude doesn't repeat them.

### Wrong attribute name on Encounter
- **Error**: Used `encounter.current_entity_uuid` - attribute doesn't exist.
- **Fix**: Use `encounter.get_current_entity()` method instead.
- **Root cause**: Claude guessed the API instead of reading `dnd/encounter.py` first.

### Wrong understanding of Encounter turn lifecycle
- **Error**: Called `encounter.end_turn()` + `encounter.next_turn()` + `encounter.start_turn()` after `start_encounter()`, causing "Turn already in progress" error.
- **Fix**: After `start_encounter()`, call `start_turn()` once. Then use `next_turn()` which auto-ends the current turn and starts the next one. Never manually call `end_turn()` before `next_turn()` (it does it internally).
- **Correct pattern**:
  ```python
  encounter.start_encounter()
  encounter.start_turn()           # Start first turn
  # ... do actions ...
  encounter.next_turn()            # Auto: end_turn() + advance + start_turn()
  ```

### Wrong understanding of light source dim_radius_feet
- **Error**: Assumed `dim_radius_feet=40` means total range is 40ft. Actually `dim_radius_feet` is ADDITIVE on top of `bright_radius_feet`, so bright=20 + dim=40 = 60ft total range.
- **Fix**: Read `_compute_light_tiles()` in `gridmap.py` line 811: `total_radius_feet = source.bright_radius_feet + source.dim_radius_feet`.
- **Root cause**: Claude assumed the API semantics instead of reading the implementation.

### Forgot melee range when testing attack targeting
- **Error**: Placed observer at (0,1) and target at (3,1) (15ft apart) for attack targeting test. Skeleton has shortsword with 5ft reach, so target was out of range. Test passed visibility but failed targeting.
- **Fix**: Place entities at adjacent positions (1 tile = 5ft) for melee attack targeting tests.
- **Root cause**: Claude focused on the magical darkness aspect and forgot the basic melee range constraint.

