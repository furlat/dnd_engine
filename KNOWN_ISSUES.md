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



