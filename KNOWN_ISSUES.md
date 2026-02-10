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

### test_concentration_spells.py Test 3 "Call Lightning Strike Repeatable" always fails
- **Found**: 2026-02-10
- **Test file**: `examples/test_concentration_spells.py`, test_3_call_lightning_strike_repeatable (line 218)
- **Error**: `AssertionError: Strike should deal additional damage` -- the Call Lightning Strike action is canceled with "Target not in line of sight"
- **Root cause**: The target entity is created via `create_target()` which uses default `HealthConfig` (no hit dice), giving it 0 max HP. `set_hp(target, 200)` on line 182 has no effect because `set_hp` works by healing (reducing `damage_taken`), and `damage_taken` is already 0 -- you cannot heal above max HP. The target remains at 0 HP throughout the test. When Call Lightning's initial cast deals damage, HP goes negative, the Dead condition is applied, the entity is removed from senses visibility, and the subsequent `CallLightningStrike._validate()` fails the LOS check (`target.uuid not in caster.senses.entities.keys()`). This is a **deterministic failure**, not a flaky/intermittent test.
- **Fix**: Give the target entity a proper `HealthConfig` with hit dice so it has actual max HP (e.g., `HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=20, mode="maximums")])`), or set `set_hp` to work differently for entities with 0 max HP.
- **Note**: This is NOT related to senses/spatial event changes. It is a pre-existing test setup bug.
- **Status**: FIXED — Added HealthConfig with 200 max HP (20d10 maximums) to create_target()

### Duck-typed getattr in SpatialSensesCallback
- **File**: `dnd/blocks/sensory.py`, lines ~193 and ~199
- **Error**: `SpatialSensesCallback.__call__()` uses `getattr(event, 'position', None)` and `getattr(event, 'entity_uuid', None)` instead of proper type narrowing (isinstance checks or typed event access).
- **Why it matters**: Bypasses the type system entirely. If the callback receives an unexpected event type, these silently return `None` instead of failing loudly, masking bugs. Pylance/Pyright cannot verify correctness.
- **Fix**: Use `isinstance` checks to narrow to the specific event type, then access typed fields directly.
- **Status**: OPEN

