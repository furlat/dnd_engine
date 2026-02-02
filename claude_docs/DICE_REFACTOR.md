# Dice System Refactoring Notes

This document captures issues with the current dice system and ideas for future refactoring.

---

## Current State

### The Problem: `AttackOutcome` Used for Everything

The `determine_attack_outcome()` function in `dnd/entity.py` is used for **all** d20 rolls:
- Attack rolls (correct semantics)
- Saving throws (incorrect - using attack terminology)
- Skill checks (incorrect - using attack terminology)

```python
# Current code (dnd/entity.py:1150)
outcome = determine_attack_outcome(roll, dc)
success = outcome not in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]
```

This works functionally but:
1. **Wrong semantics**: A save "HIT" means success, which is confusing
2. **Tight coupling**: Attack-specific logic (CRIT_MISS, AUTOHIT) leaks into saves/checks
3. **BG3-style nat 1 behavior**: Currently nat 1 is always auto-fail on saves (line 83-84), which is BG3-style, not 5e RAW

### Natural 1/20 Behavior

Current `determine_attack_outcome()` logic:

```python
# Natural 1 = auto-miss for ATTACKS (D&D 5e RAW)
# Natural 1 = auto-fail for SAVES/CHECKS (BG3-style, NOT 5e RAW)
elif natural_roll == 1:
    return AttackOutcome.CRIT_MISS  # Applied to ALL rolls!

# Natural 20 = crit for attacks, but saves just need to beat DC
elif roll.total >= target_ac:
    if natural_roll >= crit_threshold:
        return AttackOutcome.CRIT  # CRIT on saves makes no sense!
```

**5e RAW**:
- **Attacks**: Nat 1 = auto-miss, Nat 20 = auto-hit + crit
- **Saves**: No auto-fail/success on nat 1/20 (just use the total vs DC)
- **Checks**: No auto-fail/success on nat 1/20 (just use the total vs DC)

**BG3-style** (current implementation):
- All d20 rolls: Nat 1 = auto-fail, Nat 20 = auto-success

### Test Flakiness From This

Tests expecting "guaranteed" save outcomes are flaky due to nat 1/20 edge cases:

**Example 1 - Guaranteed Fail:**
- Target has WIS -5 vs DC 15
- Expected: Always fail (max roll = 20-5=15, needs >15)
- Actual: Nat 20 gives exactly 15 = DC, which **succeeds** (5% flakiness)

**Example 2 - Guaranteed Success:**
- Target has +17 to CON save vs DC 15
- Expected: Always pass (1+17=18 > 15)
- Actual: Nat 1 auto-fails in BG3-style (5% flakiness)

**Current fix**: Adjust bonuses/DCs to make outcomes truly deterministic:
- For guaranteed fail: Increase DC so nat 20 + bonus < DC (e.g., DC 16 vs +15 max)
- For guaranteed success: Increase bonus so nat 1 + bonus > DC (e.g., +18 vs DC 15)

---

## Deterministic Testing Patterns

**The Problem**: No way to force specific dice outcomes in tests. We rely on extreme bonuses/DCs.

### Current Workarounds

**1. Extreme DC/Bonus Manipulation** (Preferred)
```python
# Guaranteed FAIL: DC 16, target has WIS -5 (max: 20-5=15 < 16)
caster.spellcasting.spell_dc_bonus.self_static.add_value_modifier(
    NumericalModifier.create(source_entity_uuid=caster.uuid, name="Test DC Boost", value=1)
)

# Guaranteed PASS: +18 bonus vs DC 15 (min: 1+18=19 > 15)
tough_config = EntityConfig(
    ability_scores=AbilityScoresConfig(constitution=AbilityConfig(ability_score=30)),  # +10
    saving_throws=SavingThrowSetConfig(
        constitution_saving_throw=SavingThrowConfig(proficiency=True, bonus=6)  # +2+6=+8
    ),
    proficiency_bonus=2,
)
# Total: +10 + 2 + 6 = +18, nat 1 gives 19 > 15
```

**2. Force Attack Hit/Miss** (Existing utilities in `dnd/utils/test_utils.py`)
```python
from dnd.utils import force_attack_hit, force_attack_miss, force_attack_crit

# For attacks only - adds ±100 modifier
mod_uuid = force_attack_hit(attacker)  # +100 to attack roll
mod_uuid = force_attack_miss(attacker)  # -100 to attack roll
mod_uuid = force_attack_crit(attacker)  # AUTOCRIT modifier
```

### Future: Dice Seeding/Mocking

What we need but don't have:

```python
# Ideal API for deterministic tests
with dice_override([20, 5, 3]):  # Next 3 rolls return these values
    result = entity.roll_d20(...)  # Returns 20
    damage = weapon.roll_damage()  # Returns 5, then 3

# Or seed-based
with dice_seed(42):  # Reproducible random sequence
    result = entity.roll_d20(...)

# Or direct roll injection
roll = DiceRoll.create_fixed(natural=20, total=25)  # Skip actual roll
outcome = determine_attack_outcome(roll, ac)
```

**Implementation options**:
1. Thread-local dice queue that `random.randint` draws from
2. Dependency injection of random source into Dice class
3. Mock/patch `random.randint` in tests (fragile, but works)

---

## Proposed Refactoring

### Option 1: Separate Outcome Types (Cleanest)

Create distinct outcome types for each roll type:

```python
class AttackOutcome(str, Enum):
    HIT = "Hit"
    MISS = "Miss"
    CRIT = "Crit"
    CRIT_MISS = "Crit Miss"  # Auto-miss on nat 1

class SaveOutcome(str, Enum):
    SUCCESS = "Success"
    FAILURE = "Failure"
    # No crits for saves in 5e RAW

class CheckOutcome(str, Enum):
    SUCCESS = "Success"
    FAILURE = "Failure"
    # No crits for checks in 5e RAW
```

With separate resolution functions:

```python
def determine_attack_outcome(roll, ac, crit_threshold=20) -> AttackOutcome:
    # Nat 1 = CRIT_MISS (auto-miss)
    # Nat 20+ = CRIT (auto-hit + crit)
    # Otherwise compare total vs AC

def determine_save_outcome(roll, dc, nat1_auto_fail=False) -> SaveOutcome:
    # Optional BG3-style nat 1 auto-fail
    # Compare total vs DC, no crits

def determine_check_outcome(roll, dc, nat1_auto_fail=False) -> CheckOutcome:
    # Optional BG3-style nat 1 auto-fail
    # Compare total vs DC, no crits
```

### Option 2: Generic D20Outcome with RollType Context

Single outcome type with roll-type-aware resolution:

```python
class D20Outcome(str, Enum):
    SUCCESS = "Success"      # Hit, passed save, passed check
    FAILURE = "Failure"      # Miss, failed save, failed check
    CRITICAL_SUCCESS = "Critical Success"  # Crit (attacks only in RAW)
    CRITICAL_FAILURE = "Critical Failure"  # Auto-fail (attacks only in RAW)

def resolve_d20(roll, target, roll_type, options=None) -> D20Outcome:
    """
    options could include:
    - nat1_auto_fail: bool (default False for saves/checks, True for attacks)
    - nat20_auto_success: bool
    - crit_threshold: int (only for attacks)
    """
```

### Option 3: Configuration-Based (Most Flexible)

```python
class D20Rules(BaseModel):
    nat1_auto_fail: bool = False
    nat20_auto_success: bool = False
    crit_threshold: int = 20
    crit_enabled: bool = True

# Presets
ATTACK_RULES_5E = D20Rules(nat1_auto_fail=True, nat20_auto_success=True, crit_enabled=True)
SAVE_RULES_5E = D20Rules()  # No auto-fail/success, no crits
SAVE_RULES_BG3 = D20Rules(nat1_auto_fail=True, nat20_auto_success=True)
```

---

## Dice Manipulation Infrastructure

The engine has a complete system for intercepting and modifying dice rolls via events.

### Event Types for Dice Manipulation

| Event Type | Event Class | Phase | Use Case |
|------------|-------------|-------|----------|
| `DAMAGE_ROLLED` | `DamageRolledEvent` | EFFECT | Reroll/modify damage dice |
| `SAVING_THROW` | `SavingThrowEvent` | EFFECT | Reroll failed saves |
| `SKILL_CHECK` | `SkillCheckEvent` | EFFECT | Reroll failed checks |
| `DICE_ROLL` | (unused) | - | Reserved for future generic d20 manipulation |

### DamageRolledEvent Structure

```python
class DamageRolledEvent(Event):
    """Fired after damage dice rolled, before applied."""

    # Context (read-only)
    weapon_slot: WeaponSlot
    attack_outcome: AttackOutcome
    damages: List[Damage]

    # IMMUTABLE: Never modified
    original_rolls: List[DiceRoll]

    # MUTABLE: Handlers replace entries here
    final_rolls: List[DiceRoll]

    # AUDIT: Track all changes
    roll_modifications: List[Tuple[str, int, int, int, str]]
    # (handler_name, roll_index, old_total, new_total, reason)

    def replace_roll(self, index, new_roll, handler_name, reason):
        """Helper for handlers to replace a roll and track the change."""
```

### Great Weapon Fighting Implementation

Full pattern from `dnd/classes/fighter.py`:

```python
def great_weapon_fighting_processor(
    event: DamageRolledEvent,
    source_entity_uuid: UUID
) -> Optional[DamageRolledEvent]:
    """Rerolls 1s and 2s on damage dice for two-handed melee weapons."""

    # 1. Check ownership
    if event.source_entity_uuid != source_entity_uuid:
        return None

    # 2. Check weapon eligibility (two-handed/versatile melee)
    weapon = entity.equipment._get_weapon_by_slot(event.weapon_slot)
    if not (is_melee and (has_two_handed or has_versatile)):
        return None

    # 3. Process each roll
    for i, original_roll in enumerate(event.final_rolls):
        results = original_roll.results
        if any(r <= 2 for r in results):
            # Reroll low dice
            new_results = [random.randint(1, dice_size) if r <= 2 else r for r in results]
            new_roll = create_modified_dice_roll(original_roll, new_results)
            event.replace_roll(i, new_roll, "Great Weapon Fighting", f"Rerolled {rerolled}")

    return event
```

### Indomitable (Save Reroll) Implementation

Pattern from `dnd/classes/fighter.py`:

```python
def indomitable_processor(
    event: SavingThrowEvent,
    source_entity_uuid: UUID
) -> Optional[Event]:
    """Reroll failed saving throws."""

    # 1. Check it's our save and it failed
    if event.target_entity_uuid != source_entity_uuid:
        return None
    if event.result is not False:  # Not failed
        return None

    # 2. Check and consume resource
    if not entity.action_economy.can_afford_resource("indomitable", 1):
        return None
    entity.action_economy.consume_resource("indomitable", 1)

    # 3. Reroll (must use new result per RAW)
    new_roll = entity.roll_d20(save_bonus, RollType.SAVE)
    new_outcome = determine_attack_outcome(new_roll, dc)
    new_success = new_outcome not in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]

    # 4. Return modified event
    return event.model_copy(update={
        "dice_roll": new_roll,
        "result": new_success,
        "modified": True,
        "status_message": f"Indomitable! Reroll: {new_roll.total}"
    })
```

### Dice Processor Utilities

`dnd/classes/dice_processor_utils.py` provides reusable roll modification functions:

**Deterministic (for testing/special abilities):**
```python
maximize_all(roll, dice_size)      # All max: [6,6,6] for d6s
minimize_all(roll)                  # All 1s
set_all_to(roll, value)            # All same value
substitute_value(roll, from, to)   # Replace specific value
floor_results(roll, minimum)        # No result below min (Elemental Adept)
ceiling_results(roll, maximum)      # No result above max
```

**Stochastic (random element):**
```python
reroll_below_and_substitute(roll, threshold, dice_size)  # GWF pattern
reroll_below_keep_best(roll, threshold, dice_size)       # Halfling Lucky
reroll_ones_once(roll, dice_size)                        # Savage Attacker
```

**Core utility:**
```python
def create_modified_dice_roll(original: DiceRoll, new_results: List[int]) -> DiceRoll:
    """Create new DiceRoll with different results but same metadata."""
    return DiceRoll(
        dice_uuid=original.dice_uuid,
        results=new_results,
        total=sum(new_results) + original.bonus,
        bonus=original.bonus,
        # ... preserve other metadata
    )
```

### Implemented Features Using This System

| Feature | Class | Event Type | Phase |
|---------|-------|------------|-------|
| Great Weapon Fighting | Fighter | DAMAGE_ROLLED | EFFECT |
| Indomitable | Fighter | SAVING_THROW | EFFECT |
| Protection | Fighter | ATTACK | EXECUTION |
| Brutal Critical | Barbarian | - | Built into `Dice.crit_extra_dice` |

### What's Missing for Tests

The dice processor utils work on `DiceRoll` objects **after** they're created. For deterministic tests, we need to control the roll **before** it happens:

1. **Pre-roll control**: Seed RNG or inject specific values
2. **Post-roll manipulation**: Use `dice_processor_utils` (exists but limited)
3. **Outcome override**: Force hit/miss via extreme modifiers (current workaround)

---

## Migration Path

1. **Phase 1**: Add `SaveOutcome`/`CheckOutcome` types, but keep `AttackOutcome` compatibility
2. **Phase 2**: Create `determine_save_outcome()` and `determine_check_outcome()`
3. **Phase 3**: Update `Entity.saving_throw()` and `Entity.skill_check()` to use new functions
4. **Phase 4**: Add `nat1_auto_fail` configuration option for BG3-style house rules
5. **Phase 5**: Deprecate `AttackOutcome` usage for non-attack rolls

---

## Related Files

| File | Purpose |
|------|---------|
| `dnd/core/dice.py` | `Dice`, `DiceRoll`, `AttackOutcome`, `RollType` |
| `dnd/core/events.py` | `DamageRolledEvent`, `SavingThrowEvent`, `SkillCheckEvent` |
| `dnd/entity.py` | `determine_attack_outcome()`, `saving_throw()`, `skill_check()` |
| `dnd/classes/fighter.py` | `GreatWeaponFighting`, `Indomitable`, `create_modified_dice_roll()` |
| `dnd/classes/dice_processor_utils.py` | Dice manipulation utilities (maximize, minimize, reroll patterns) |
| `dnd/classes/barbarian.py` | Brutal Critical (uses `crit_extra_dice`) |
| `dnd/utils/test_utils.py` | `force_attack_hit/miss/crit` utilities |
| `examples/test_tier1_spells.py` | Tests affected by nat 1/20 edge cases |
| `claude_docs/IMPLEMENTATION_GUIDE.md` | Event handler patterns |
