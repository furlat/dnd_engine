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


### Walking next to an invisible creature triggers an opportunity attack (and breaks their invisibility)
- **Found**: 2026-02-19, code review
- **Files**: `dnd/reactions.py` (opportunity_attack_processor), `dnd/blocks/sensory.py` (get_threathened_positions), `dnd/conditions.py` (InvisibilityEffect, invisibility_reveal_processor)
- **Error**: When an entity walks away from an adjacent invisible creature, the invisible creature makes an opportunity attack. This OA also triggers the invisibility reveal handler, stripping the creature's invisibility. Both effects are wrong per D&D 5e rules.
- **Hypothesis**: `opportunity_attack_processor` in `dnd/reactions.py` (line 33) calls `reaction_source_entity.senses.get_threathened_positions()` to determine if the mover is leaving a threatened area. This is computed entirely from the threatening entity's perspective (adjacency + own visibility + walkable tiles). There is **no perceivability check** from the mover's perspective -- the code never asks whether `event_source_entity` (the mover) can actually see `reaction_source_entity` (the invisible creature). Since the invisible creature can see the mover and the position is adjacent/visible/walkable, `get_threathened_positions()` includes it, and the OA fires. The subsequent Attack event then triggers `invisibility_reveal_processor`, which removes the Invisible condition -- so the invisible creature both makes an illegal OA and loses its invisibility for doing so.
- **D&D 5e rule**: "You can't make an opportunity attack against a creature that you can't see" is not explicitly stated in the OA rules, but follows from: (1) PHB p.195: "You can make an opportunity attack when a hostile creature that **you can see** moves out of your reach" -- the OA triggering condition requires the OA-maker to see the target, and (2) the mover must be aware of a threat to provoke one. However, the deeper issue here is the reverse: an invisible creature shouldn't be generating threat against entities that can't perceive it. The OA handler should check whether the mover can perceive the would-be attacker.
- **Suggested fix**: Two-part problem requiring a configurable approach. (1) The mover shouldn't be threatened by creatures it can't perceive — but a blanket `senses.entities` check is too blunt since some homebrew/monster abilities may want imperceivable OAs. (2) The invisible creature shouldn't automatically make OAs that reveal it — in D&D 5e you can *choose* not to make an OA. The better design is a **reaction policy** system: conditions like Invisible could set a flag (e.g., `suppress_reactions=True`) that the OA processor checks. This way, Invisible/Hidden entities opt out of OAs by default (staying hidden), but the mechanism is general enough for other use cases. The perception check (mover can't see attacker) is the D&D RAW fix, while reaction suppression is the tactical fix (invisible entity *chooses* not to reveal itself).
- **Impact**: In PvP or AI combat, invisible creatures next to an enemy will incorrectly make OAs when the enemy moves, revealing themselves in the process. This punishes movement near invisible creatures and breaks stealth tactics.
- **Status**: OPEN

### Pathfinding is agnostic to tile conditions (routes through traps/hazards)
- **Found**: 2026-02-20, observed during gameplay
- **Files**: `dnd/core/dijkstra.py`, `dnd/core/gridmap.py`
- **Error**: Dijkstra pathfinding only considers walkability (walls, entities) when computing shortest paths. It is completely unaware of tile conditions like spike traps, fire, Spike Growth zones, Web, etc. This means the AI (and move action path computation) will happily route entities through hazardous tiles even when an equivalent or slightly longer safe path exists.
- **Hypothesis**: `compute_paths()` in `dijkstra.py` uses `is_walkable()` / `is_walkable_for()` checks which only test tile type and entity blocking. There is no cost weighting for tiles with active damaging/hindering conditions. All walkable tiles have equal movement cost, so the shortest geometric path always wins regardless of hazards.
- **Suggested fix**: Add a tile cost function that Dijkstra can use to weight hazardous tiles higher. Tiles with damaging conditions (spike traps, Spike Growth, fire) could have a high cost penalty, making the algorithm prefer safe routes when they exist. The cost could be configurable per condition (e.g., `movement_cost_penalty` field on tile conditions). Difficult terrain already doubles movement cost — this would extend that concept to hazard avoidance. The AI layer could also have a separate "danger-aware" pathfinding mode vs raw shortest path.
- **Impact**: AI entities walk through known traps and hazard zones unnecessarily, taking avoidable damage. In PvP, Claude's agent routes through spike traps when safe detours exist.
- **Status**: OPEN

