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

### 1. Heavy duck typing in base_actions.py (BaseAction can't import Entity)
- **Found**: 2026-02-11
- **Files**: `dnd/core/base_actions.py` lines 275-642 (~15 instances)
- **Error**: Uses `getattr(entity, 'senses', None)`, `getattr(entity, 'is_ally', None)`, `getattr(ent, 'get_hp', lambda: 1)()` etc. Treats Entity as a duck-typed bag of attributes.
- **Why it's hard**: BaseAction is in `dnd/core/` and Entity is in `dnd/entity.py`. BaseAction CANNOT import Entity (dependency flows down, not up). The duck typing exists because BaseAction needs Entity features (senses, faction, HP) for target validation but can't reference the Entity type.
- **Possible approaches**: Protocol types, abstract base with the needed interface, or restructuring so target validation lives on Entity instead of BaseAction.
- **Status**: FIXED — virtual methods on BaseBlock (get_senses, get_hp), faction field moved to BaseBlock, resource_evaluator callback on Cost. 15/15 getattr calls removed.


