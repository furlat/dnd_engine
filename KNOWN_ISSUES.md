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

### Combat log leaks information about non-visible entities
- **Found**: 2026-02-17 PvP session
- **Error**: When an entity goes invisible/hidden and moves, the combat log still reports their exact position and actions (e.g., "Hero moved to (0,7)"). Any player reading the combat log gets perfect information about enemies they can't see — effectively wallhacks.
- **Hypothesis**: The combat log entries are generated at COMPLETION phase without any perceivability filtering. The server `/combat_log` endpoint returns all entries to all sessions regardless of what each faction can actually see. Need per-session or per-faction filtering: only show combat log entries for events involving entities that the requesting session's entities can perceive.
- **Status**: OPEN

### Combat log shows pre-resistance damage instead of actual damage taken
- **Found**: 2026-02-18, observed during barbarian frenzy (rage resistance active)
- **Error**: Combat log displays full raw damage (e.g., 12) instead of resistance-reduced damage (e.g., 6 after rage halving). Actual HP reduction is correct — only the log is wrong.
- **Hypothesis**: Confirmed structural bug. The disconnect is in `dnd/actions.py` (`attack_consequences`): `target_entity.receive_damage(...)` returns the post-resistance `actual_damage` from `health.take_damage()`, but **the return value is discarded** — never captured or stored. Meanwhile, `AttackEvent.generate_combat_log()` computes `total_damage` by summing `self.damage_rolls[i].total` — these are the raw pre-resistance dice rolls. The resistance multiplier (0.5 for resistance, 0 for immunity, 2 for vulnerability) is applied deep inside `Health.take_damage()` (`dnd/blocks/health.py` ~line 351) and never flows back to the event or combat log. This affects ALL damage resistance/vulnerability/immunity display, not just barbarian rage — any condition that grants resistance (e.g., `Bear Totem`, `Protection from Energy`, `Absorb Elements`) will show wrong damage in the log.
- **Fix approach**: Capture `actual_damage = target_entity.receive_damage(...)` in `actions.py`, add an `actual_damage` field to `AttackEvent`, and use it in `generate_combat_log()` for the displayed total. The per-roll breakdown can stay raw for verbose mode, but the headline damage number should reflect what was actually taken.
- **Status**: OPEN

### Trap lever deactivation doesn't update tile name (LOW PRIORITY)
- **Found**: 2026-02-17 PvP session
- **Error**: When a trap lever deactivates spike traps, the damage-dealing condition is removed from the tiles but the tile name still shows "Spikes". Inspecting the tile after deactivation still says "Spikes", making it look like the lever did nothing.
- **Hypothesis**: The lever removes the trap condition but doesn't rename the tile back to "Floor". The `inspect` command only shows tile name/type, not active conditions, so there's no way to distinguish an active trap tile from a deactivated one.
- **Impact**: Distracted Claude during PvP — wasted time re-inspecting tiles and doubting the combat log which correctly reported "Deactivates a trap".
- **Status**: OPEN


### Dodging Attack test fails — dice roll extraction broken
- **Found**: 2026-02-18
- **Test file**: `examples/test_dodging_attack.py`
- **Error**: `[FAIL] No dice roll found in event` — both the control case (no dodging) and the test case (with dodging) fail at the dice roll extraction step
- **Hypothesis**: The test relied on extracting dice rolls from attack events but was missing grid setup (no tiles → no LOS → attacks canceled). NOT a dice extraction or dodge logic bug.
- **Fix**: Added `reset_combat_state()` + `get_map().create_rectangle(0, 0, 20, 20)` to test setup
- **Status**: FIXED (2026-02-18)

### Extra Attack Fails on Second Turn
- **Test**: `examples/test_pvp_extra_attack.py`
- **Symptom**: Extra Attack unavailable on Turn 3 (hero second turn) despite `HasAttacked=True`, `extra_attacks=1`, and `ExtraAttacksGranted` condition present
- **Root cause hypothesis**: Duplicate `HasAttacked Tracker` handlers registered for same entity (appears twice in EventQueue). May cause double-removal or state corruption on subsequent turns
- **Discovered**: 2026-02-18 during CLI attack display improvements

## Resolved Issues (2026-02-18 Test Cleanup)

### 7 tests failing due to missing grid tiles
- **Found**: 2026-02-18
- **Test files**: `test_dodging_attack.py`, `test_two_weapon_fighting.py`, `test_barbarian_frenzy.py`, `test_frenzy_maintenance.py`, `test_barbarian_fighter_combat.py`, `test_barbarian_srd_features.py`, `test_concentration_spells.py`
- **Root cause**: Tests had no `get_map().create_rectangle()` call. Without floor tiles, `GridMap.is_blocking()` returns `True` for all positions, `compute_fov()` returns empty, `senses.entities` is empty, and LOS validation fails — canceling all attacks/spells.
- **Fix**: Added `reset_combat_state()` + `get_map().create_rectangle(0, 0, 20, 20)` to each test. Replaced hand-rolled `reset_entities()` helpers with the standard utility.
- **Status**: FIXED

### test_inventory_use_actions.py intermittent failures
- **Found**: 2026-02-18
- **Two sub-issues**:
  1. `test_scroll_magic_missile_upcast_more_darts`: Assertion `damage_l3 > damage_l1` fails when L1 (3d4+3, range 6-15) rolls high and L3 (5d4+5, range 10-25) rolls low — overlapping ranges. Fixed by removing the comparison; per-level range assertions already prove correct dart counts.
  2. `test_scroll_fire_bolt_damage_on_hit`: `force_attack_hit()` adds AUTOHIT to `melee_attack_bonus` but Fire Bolt uses `spell_attack_bonus` which reads from `equipment.attack_bonus`. Fixed by adding AUTOHIT directly to `equipment.attack_bonus.self_static`.
- **Status**: FIXED

### 19 tests using old manual reset patterns
- **Found**: 2026-02-18
- **Issue**: Tests used `EventQueue.reset()` + `Entity._entity_registry.clear()` + `Entity._entity_by_position.clear()` or hand-rolled `reset_entities()` functions instead of the standard `reset_combat_state()`. Fragile and missing GridMap reset.
- **Fix**: Replaced all old patterns with `reset_combat_state()` + `get_map().create_rectangle(0, 0, 20, 20)` across 19 test files.
- **Status**: FIXED

### test_extra_attack.py intermittent failure from target death
- **Found**: 2026-02-18
- **Test file**: `examples/test_extra_attack.py`
- **Root cause**: Tests 1-3 and 7 used `create_goblin` (7 HP) as target without `set_hp()`. A skeleton crit with shortsword (2d6+2, up to 14) kills the goblin. Subsequent ExtraAttack against the dead target fails LOS validation (`validate_line_of_sight` checks `senses.entities`) → event canceled → `attacks_made` undercount → assertion failure.
- **Fix**: Added `set_hp(target, 200)` to tests 1, 2, 3, 7 (matching the pattern already used in tests 4, 5, 6).
- **Status**: FIXED

