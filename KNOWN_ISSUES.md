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

### Agent CLI: No state delta returned after map-changing actions
- **Found**: 2026-02-18 PvP session (skeleton had to manually refresh state after opening door)
- **Error**: After actions that change the map (opening a door, casting a zone spell, moving into new visibility), `ActionResult` only returns combat log + remaining action economy. No map delta, no visibility changes, no newly spotted entities. Agent must manually run `state` or `actions` to discover what changed.
- **Hypothesis**: `ActionResult` in `server/api_models.py` lacks a state delta field. The incremental senses system already computes visibility changes via `SensesUpdateHint`, but these are never serialized into the action response. Fix: capture senses before/after action execution, compute delta, include in response.
- **Impact**: Wastes agent tokens on redundant `state`/`actions` queries. Confuses Claude about whether actions had effect (e.g., "did the door actually open?").
- **Status**: OPEN










