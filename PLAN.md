# Plan: Fix Frenzied Barbarian Test

## Problem

The test `test_mindless_rage_works_with_frenzied` in `examples/test_barbarian_mindless_rage.py:235` fails:

```
AssertionError: Should be raging (sub-condition)
assert 'Raging' in barbarian.active_conditions
```

## Root Cause Analysis

The test does this (incorrectly):
```python
# Apply Frenzied condition (includes Raging as sub-condition)  <-- WRONG ASSUMPTION
frenzied = Frenzied(
    source_entity_uuid=barbarian.uuid,
    target_entity_uuid=barbarian.uuid,
    rage_damage=2
)
barbarian.add_condition(frenzied)

assert "Raging" in barbarian.active_conditions  # FAILS - Raging is NOT a sub-condition
```

**The Architecture** (from `dnd/classes/rage.py`):
- `Frenzied` is a **sub-condition OF** `Raging`, NOT the other way around
- The `Frenzy` **action** creates both conditions properly:
  1. Creates `Raging` first
  2. Creates `Frenzied` with `parent_condition=raging.uuid`
  3. Links them: `raging.sub_conditions.append(frenzied.uuid)`

**Why it's designed this way**: Rage maintenance checks if the barbarian attacked or took damage. When rage ends (due to inactivity), removing `Raging` should cascade and remove `Frenzied`. Parent→child cascade removal makes this work.

## The Fix

The test should either:

### Option A: Use the Frenzy Action (Recommended)
```python
# Instead of directly applying Frenzied, use the Frenzy action
frenzy_action = Frenzy(
    source_entity_uuid=barbarian.uuid,
    template=False
)
frenzy_action.apply()

assert "Frenzied" in barbarian.active_conditions
assert "Raging" in barbarian.active_conditions
```

### Option B: Manually Create Both Conditions Correctly
```python
# Apply Raging first (it's the parent)
raging = Raging(
    source_entity_uuid=barbarian.uuid,
    target_entity_uuid=barbarian.uuid,
    rage_damage=2
)
barbarian.add_condition(raging)

# Apply Frenzied as sub-condition of Raging
frenzied = Frenzied(
    source_entity_uuid=barbarian.uuid,
    target_entity_uuid=barbarian.uuid,
    rage_damage=2,
    parent_condition=raging.uuid
)
barbarian.add_condition(frenzied)
raging.sub_conditions.append(frenzied.uuid)
```

## Recommendation

**Use Option A** - the test should use the action, not bypass it. This:
1. Tests the actual user-facing API
2. Ensures the test reflects real usage
3. Is less fragile (doesn't depend on internal parent-child wiring)

## Files to Modify

- `examples/test_barbarian_mindless_rage.py`: Fix `test_mindless_rage_works_with_frenzied()` to use `Frenzy` action

## Additional Considerations

The barbarian in the test needs:
1. Rage resource available (the FrenzyFeature or at least rage resource setup)
2. Bonus action available
3. No heavy armor equipped

This might require additional setup - check how other frenzy tests handle this.

## Verification

```bash
pytest examples/test_barbarian_mindless_rage.py -v
pytest examples/test_barbarian_frenzy.py -v  # Ensure existing frenzy tests still pass
```
