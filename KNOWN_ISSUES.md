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
