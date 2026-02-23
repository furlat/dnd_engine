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



### Trap lever deactivation doesn't update tile name (LOW PRIORITY)
- **Found**: 2026-02-17 PvP session
- **Error**: When a trap lever deactivates spike traps, the damage-dealing condition is removed from the tiles but the tile name still shows "Spikes". Inspecting the tile after deactivation still says "Spikes", making it look like the lever did nothing.
- **Hypothesis**: The lever removes the trap condition but doesn't rename the tile back to "Floor". The `inspect` command only shows tile name/type, not active conditions, so there's no way to distinguish an active trap tile from a deactivated one.
- **Impact**: Distracted Claude during PvP — wasted time re-inspecting tiles and doubting the combat log which correctly reported "Deactivates a trap".
- **Status**: OPEN




### Pathfinding is agnostic to tile conditions (routes through traps/hazards)
- **Found**: 2026-02-20, observed during gameplay
- **Files**: `dnd/core/dijkstra.py`, `dnd/core/gridmap.py`
- **Error**: Dijkstra pathfinding only considers walkability (walls, entities) when computing shortest paths. It is completely unaware of tile conditions like spike traps, fire, Spike Growth zones, Web, etc. This means the AI (and move action path computation) will happily route entities through hazardous tiles even when an equivalent or slightly longer safe path exists.
- **Hypothesis**: `compute_paths()` in `dijkstra.py` uses `is_walkable()` / `is_walkable_for()` checks which only test tile type and entity blocking. There is no cost weighting for tiles with active damaging/hindering conditions. All walkable tiles have equal movement cost, so the shortest geometric path always wins regardless of hazards.
- **Suggested fix**: Add a tile cost function that Dijkstra can use to weight hazardous tiles higher. Tiles with damaging conditions (spike traps, Spike Growth, fire) could have a high cost penalty, making the algorithm prefer safe routes when they exist. The cost could be configurable per condition (e.g., `movement_cost_penalty` field on tile conditions). Difficult terrain already doubles movement cost — this would extend that concept to hazard avoidance. The AI layer could also have a separate "danger-aware" pathfinding mode vs raw shortest path.
- **Impact**: AI entities walk through known traps and hazard zones unnecessarily, taking avoidable damage. In PvP, Claude's agent routes through spike traps when safe detours exist.
- **Status**: OPEN

