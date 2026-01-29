# Documentation Update Plan

## Summary

Update project documentation to reflect:
1. Shove action is now fully implemented (Phase 2 complete)
2. Document the refactored combat log system

---

## Changes Required

### 1. MOVEMENT_AOE_TERRAIN_PLAN.md

**Location**: `claude_docs/MOVEMENT_AOE_TERRAIN_PLAN.md`

**Changes**:
- Update status table: Phase 2 Shove → ✓ COMPLETE
- Update Phase 2 section header to show completion
- Update Step 2 checklist to show completion
- Add implementation notes about what was actually implemented

**Current**:
```
| Phase 2: Shove | TODO | Contested push with forced movement |
```

**New**:
```
| Phase 2: Shove | ✓ COMPLETE | Contested push with forced movement |
```

Also update sections:
- `## Phase 2: Shove Action (BG3-Style)` → add "- IMPLEMENTED ✓"
- `### Step 2: Shove Action` → mark substeps as complete
- Files table: update relevant files to show completion

---

### 2. MASTER_SUMMARY.md

**Location**: `claude_docs/MASTER_SUMMARY.md`

**Changes**:
- Add "Shove Action" to the implemented systems list
- Add brief mention of combat log system
- Update "Potential Next Features" to remove Shove-related items

**Add to "What's Implemented" table**:
```
| **Shove Action** | Complete | Contested Athletics push with forced movement |
| **Combat Log** | Complete | Event-driven log generation with 3 verbosity levels |
```

---

### 3. IMPLEMENTATION_GUIDE.md

**Location**: `claude_docs/IMPLEMENTATION_GUIDE.md`

**Changes**: Add new section "## Combat Log System" after Event Handlers section

**Content to add**:
```markdown
## Combat Log System

Events automatically generate combat log entries at COMPLETION phase via `generate_combat_log()`.

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `CombatLogEntry` | `dnd/core/combat_log.py` | Main log entry model |
| `CombatLogEntryType` | `dnd/core/combat_log.py` | Entry types enum |
| `Event.generate_combat_log()` | Each event subclass | Generates entry for that event |
| Typed data models | `dnd/core/combat_log.py` | AttackLogData, MovementLogData, etc. |

### CombatLogEntry Structure

```python
class CombatLogEntry(BaseModel):
    entry_type: CombatLogEntryType  # "attack", "movement", etc.
    source_name: str
    source_uuid: str
    target_name: Optional[str]
    target_uuid: Optional[str]

    # Three verbosity levels (contain markdown for Rich rendering)
    compact: str    # One-line summary
    verbose: str    # Summary + key details
    detailed: str   # Full breakdown with all modifiers

    data: Dict[str, Any]    # Typed data (AttackLogData, etc.)
    success: Optional[bool]  # For attacks, saves, checks
```

### Adding Combat Log to a New Event

Override `generate_combat_log()` in your event class:

```python
class MyActionEvent(ActionEvent):
    def generate_combat_log(self) -> Optional[CombatLogEntry]:
        # Build typed data
        data = MyActionLogData(
            entity_name=self.source_entity_name or "Unknown",
            entity_uuid=str(self.source_entity_uuid),
            # ... action-specific fields
        )

        # Build verbosity levels
        compact = f"{source_name} uses {action_name}"
        verbose = f"{source_name} uses {action_name}\n  Effect: {effect}"
        detailed = verbose + f"\n  Breakdown: {details}"

        return CombatLogEntry(
            entry_type=CombatLogEntryType.ACTION,
            source_name=self.source_entity_name or "Unknown",
            source_uuid=str(self.source_entity_uuid),
            compact=compact,
            verbose=verbose,
            detailed=detailed,
            data=data.model_dump(),
            success=True
        )
```

### Modifier Breakdown System

Use `ModifiableValue.get_breakdown()` to extract numerical modifiers:

```python
from dnd.core.combat_log import ModifierBreakdown

attack_bonus = attacker.attack_bonus(slot, target.uuid)
breakdown = attack_bonus.get_breakdown()  # Returns List[ModifierBreakdown]
# Result: [ModifierBreakdown(name="Prof", value=2), ModifierBreakdown(name="DEX", value=3)]
```

Name cleanup is automatic: `"proficiency_bonus_base_value"` → `"Prof"`

### Entry Types

| Type | Used For |
|------|----------|
| `ATTACK` | Attack actions |
| `MOVEMENT` | Move, Jump |
| `ACTION` | Dash, Dodge, Disengage, Shove |
| `SAVING_THROW` | Saves from spells/effects |
| `SKILL_CHECK` | Contested checks, perception |
| `CONDITION_APPLIED` | Condition gained |
| `CONDITION_REMOVED` | Condition lost |
| `DAMAGE_TAKEN` | Environmental/other damage |
| `HEAL` | Healing effects |
| `DEATH` | Entity death |
| `TURN_START` / `TURN_END` | Turn boundaries |
```

---

### 4. EXAMPLE_PATTERNS.md

**Location**: `claude_docs/EXAMPLE_PATTERNS.md`

**Changes**: Add new section "## Working with Combat Logs" at the end

**Content to add**:
```markdown
## Working with Combat Logs

### Checking Combat Log Entries in Tests

Events generate combat log entries automatically. Access them via server or directly from events.

```python
from dnd.actions import Attack
from dnd.core.events import WeaponSlot

# Execute an attack
attack = Attack(
    source_entity_uuid=attacker.uuid,
    target_entity_uuid=target.uuid,
    weapon_slot=WeaponSlot.MELEE_MAIN
)
event = attack.apply()

# Get the combat log entry
log_entry = event.generate_combat_log()
if log_entry:
    print(f"Compact: {log_entry.compact}")
    print(f"Verbose: {log_entry.verbose}")
    print(f"Success: {log_entry.success}")

    # Access typed data
    attack_data = log_entry.data
    print(f"Total damage: {attack_data.get('total_damage', 0)}")
    print(f"Outcome: {attack_data.get('outcome')}")
```

### Verbosity Levels

```python
from dnd.core.combat_log import CombatLogVerbosity

# Get text at specific verbosity
text = log_entry.get_text(CombatLogVerbosity.COMPACT)   # One-line
text = log_entry.get_text(CombatLogVerbosity.VERBOSE)   # With details
text = log_entry.get_text(CombatLogVerbosity.DETAILED)  # Full breakdown
```

### Server-Side Combat Log

The server accumulates log entries. Fetch via API:

```python
# GET /combat-log?since=N returns entries after index N
# Each entry is CombatLogEntry.to_dict() (Pydantic model_dump())

entries = response.get("entries", [])
for entry in entries:
    print(f"{entry['entry_type']}: {entry['compact']}")
```
```

---

### 5. CLAUDE.md

**Location**: Root `CLAUDE.md`

**Changes**: The combat log documentation is already present. Just add Shove to the actions file reference.

**Update this line** in the Key Files Reference table:
```
| Attack, Move, Jump, Dash, Dodge, etc. | `dnd/actions.py` |
```
**To**:
```
| Attack, Move, Jump, Shove, Dash, Dodge, etc. | `dnd/actions.py` |
```

---

## Implementation Order

1. Update MOVEMENT_AOE_TERRAIN_PLAN.md (Shove complete)
2. Update MASTER_SUMMARY.md (add Shove + Combat Log)
3. Update IMPLEMENTATION_GUIDE.md (add Combat Log section)
4. Update EXAMPLE_PATTERNS.md (add Combat Log examples)
5. Update CLAUDE.md (add Shove to file reference)

---

## Files to Modify

| File | Changes |
|------|---------|
| `claude_docs/MOVEMENT_AOE_TERRAIN_PLAN.md` | Mark Phase 2 complete |
| `claude_docs/MASTER_SUMMARY.md` | Add Shove + Combat Log to implemented |
| `claude_docs/IMPLEMENTATION_GUIDE.md` | Add Combat Log System section |
| `claude_docs/EXAMPLE_PATTERNS.md` | Add Combat Log examples |
| `CLAUDE.md` | Add Shove to actions file reference |
