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

### Trap lever deactivation doesn't update tile name (LOW PRIORITY)
- **Found**: 2026-02-17 PvP session
- **Error**: When a trap lever deactivates spike traps, the damage-dealing condition is removed from the tiles but the tile name still shows "Spikes". Inspecting the tile after deactivation still says "Spikes", making it look like the lever did nothing.
- **Hypothesis**: The lever removes the trap condition but doesn't rename the tile back to "Floor". The `inspect` command only shows tile name/type, not active conditions, so there's no way to distinguish an active trap tile from a deactivated one.
- **Impact**: Distracted Claude during PvP — wasted time re-inspecting tiles and doubting the combat log which correctly reported "Deactivates a trap".
- **Status**: OPEN

