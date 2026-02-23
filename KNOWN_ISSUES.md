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

(none)

## Fixed Issues

### Trap lever deactivation doesn't update tile name (LOW PRIORITY)
- **Found**: 2026-02-17 PvP session
- **Error**: When a trap lever deactivates spike traps, the damage-dealing condition is removed from the tiles but the tile name still shows "Spikes". Inspecting the tile after deactivation still says "Spikes", making it look like the lever did nothing.
- **Fix**: Spike traps reworked to Floor tiles + SpikeTrapCondition. Deactivation removes the condition, tile stays Floor. Inspect shows active conditions.
- **Status**: FIXED (2026-02-23, hazard system refactor)


### Pathfinding is agnostic to tile conditions (routes through traps/hazards)
- **Found**: 2026-02-20, observed during gameplay
- **Files**: `dnd/core/dijkstra.py`, `dnd/core/gridmap.py`
- **Error**: Dijkstra pathfinding only considers walkability (walls, entities) when computing shortest paths. It is completely unaware of tile conditions like spike traps, fire, Spike Growth zones, Web, etc.
- **Fix**: Two-pass Dijkstra with `walk_in_danger=False` default. Safe paths avoid hazardous tiles, auto-safe movement uses safe paths when available. HazardFilter enum + is_hazardous_for() for subjective hazard detection. condition_stealth_dc for perception-gated hazard visibility.
- **Status**: FIXED (2026-02-23, hazard system refactor)
