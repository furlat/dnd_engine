# Sorcerer Class System

**Last Updated:** February 2026

## 1. Architecture Overview

The Sorcerer is the engine's first full spellcaster class. Like Fighter and Barbarian, it's implemented as **conditions applied to entities** — no `Class` object exists.

**Key innovation**: The **Action Override pattern** — metamagic modifies spell templates in-place via temporary `alt_*` fields, rather than creating new spell objects.

```
Entity (Sorcerer)
├── ability_scores          ← CHA primary, CON secondary
├── health                  ← d6 hit dice
├── equipment               ← Dagger or quarterstaff (no armor proficiency)
├── action_economy          ← Spell slots (full caster table) + sorcery_points resource
├── spellcasting            ← ability="charisma"
├── active_conditions
│   ├── "Draconic Resilience"    → HP bonus + contextual AC modifier (L1)
│   ├── "Sorcery Points Feature" → resource + metamagic actions + Font of Magic (L2+)
│   ├── "Elemental Affinity"     → damage resistance (L6+)
│   └── "MetamagicActive"        → TEMPORARY: modifies spell templates, auto-removed on cast
└── registered_actions
    ├── Standard: Move, Dash, Dodge, Disengage, DropConcentration
    ├── Weapon: Dagger/Quarterstaff attack
    ├── Spells: Fire Bolt, Magic Missile, Fireball, etc.
    ├── Metamagic: Quickened Spell, Twinned Spell, Distant Spell
    ├── Font of Magic: Convert L1 Slot to SP, Convert SP to L1 Slot, ...
    └── Shield (reaction)
```

### Files

| File | Purpose |
|------|---------|
| `dnd/classes/sorcerer.py` | All conditions + actions (DraconicResilience, ElementalAffinity, MetamagicActive, SorceryPointsFeature, metamagic actions, Font of Magic) |
| `dnd/classes/sorcerer_factory.py` | `SorcererConfig` + `create_sorcerer()` factory |
| `examples/test_sorcerer_factory.py` | 77 tests across 18 categories |

---

## 2. The Action Override Pattern (Metamagic)

This is the core design contribution of the Sorcerer implementation. Instead of creating alternate spell objects, metamagic **temporarily modifies existing templates** via override fields.

### Alt Fields

**On BaseAction** (`dnd/core/base_actions.py`):

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `alt_cost_type` | `Optional[str]` | `None` | Replace primary action cost type |
| `alt_extra_costs` | `List[Cost]` | `[]` | Additional costs appended at cast time |
| `alt_target_type` | `Optional[TargetType]` | `None` | Replace target type |
| `alt_target_count` | `Optional[int]` | `None` | Multi-target count override |

**On SpellAction** (`dnd/actions.py`):

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `alt_range` | `Optional[int]` | `None` | Override spell range |
| `alt_skip_slot` | `bool` | `False` | Skip spell slot cost |

### Effective Properties

When alt fields are set, the action system uses them instead of base values:

```python
# BaseAction
@property
def effective_target_type(self) -> TargetType:
    return self.alt_target_type if self.alt_target_type is not None else self.target_type

@property
def effective_costs(self) -> List[Cost]:
    costs = self.costs[:]
    if self.alt_cost_type is not None:
        costs = [c.model_copy(update={"cost_type": self.alt_cost_type}) ...]
    if self.alt_skip_slot:
        # Remove spell slot cost
    costs.extend(self.alt_extra_costs)
    return costs

# SpellAction
@property
def effective_range(self) -> int:
    return self.alt_range if self.alt_range is not None else self.spell_range.normal
```

### Helper Functions

`dnd/actions_functional.py` provides two helpers:

```python
apply_action_overrides(entity, filter_fn, overrides) -> List[UUID]
    # Sets override fields on templates matching filter_fn
    # Returns modified UUIDs for cleanup tracking

clear_action_overrides(entity, template_uuids) -> None
    # Resets ALL alt fields to defaults on specified templates
    # Defaults: alt_cost_type=None, alt_extra_costs=[], alt_target_type=None,
    #           alt_target_count=None, alt_range=None, alt_skip_slot=False
```

### Lifecycle

```
1. Player uses metamagic action (e.g., QuickenedSpell)
   → Deducts SP cost
   → Applies MetamagicActive condition

2. MetamagicActive._apply() sets alt fields on matching spell templates
   → Registers CAST_SPELL handler for auto-removal

3. Player casts spell — system uses effective_* properties
   → Spell resolves with modified parameters

4. CAST_SPELL event fires at EFFECT phase
   → MetamagicActive auto-remove handler triggers
   → Entity.remove_condition("MetamagicActive")
   → cleanup_own_state() calls clear_action_overrides()
   → All alt fields reset to defaults
```

### Why Not Create New Spell Objects?

- **Memory efficient**: One template per spell, not N variants per metamagic combination
- **Composable**: Different metamagics set different alt fields without conflicts
- **Clean**: Auto-cleanup via condition removal resets everything
- **System-consistent**: Uses the same condition lifecycle as every other feature

---

## 3. MetamagicActive Condition

The bridge between metamagic actions and spell templates. Applied as a condition on the sorcerer, auto-removed after casting.

### Three Metamagic Types

#### Quickened Spell (2 SP)

**Filter**: SpellActions with `"actions"` cost type (excludes bonus action spells like Healing Word)

**Override**: `alt_cost_type = "bonus_actions"`

**Effect**: Spell costs a bonus action instead of an action. BG3-style: no cantrip restriction — player can cast a quickened cantrip as bonus action, then a leveled spell as action.

```python
# Uses the apply_action_overrides helper
self._modified_uuids = apply_action_overrides(
    target,
    filter_fn=lambda a: isinstance(a, SpellAction) and any(
        c.cost_type == "actions" for c in a.costs
    ),
    overrides={"alt_cost_type": "bonus_actions"},
)
```

#### Twinned Spell (1 SP base + spell level - 1 extra)

**Filter**: SpellActions with `target_type == TargetType.ENTITY` (single-target only — excludes AoE, SELF, MULTI_ENTITY)

**Overrides**:
- `alt_target_type = TargetType.MULTI_ENTITY`
- `alt_target_count = 2`
- `alt_extra_costs` = SP cost of `max(0, spell_level - 1)`

**SRD SP cost**: Total = 1 (activation) + max(0, level-1) (at cast) = max(1, level). Cantrips cost 1, L1 costs 1, L2 costs 2, L3 costs 3.

```python
# Manual loop (not helper) because cost varies per template
self._modified_uuids = []
for template in target.registered_actions:
    if isinstance(template, SpellAction) and template.target_type == TargetType.ENTITY:
        template.alt_target_type = TargetType.MULTI_ENTITY
        template.alt_target_count = 2
        extra_sp = max(0, template.spell_level - 1)
        if extra_sp > 0:
            template.alt_extra_costs = [Cost(
                name="Twinned Spell SP",
                cost_type="actions", cost=0,
                resource_name="sorcery_points", resource_cost=extra_sp,
                evaluator=entity_action_economy_cost_evaluator,
                resource_evaluator=entity_resource_cost_evaluator,
            )]
        self._modified_uuids.append(template.uuid)
```

#### Distant Spell (1 SP)

**Filter**: All SpellActions, with behavior depending on range type

**Overrides**:
- `RangeType.RANGE` spells: `alt_range = spell_range.normal * 2` (double range)
- `RangeType.REACH` spells: `alt_range = 30` (touch becomes 30ft)
- SELF range: not modified

```python
self._modified_uuids = []
for template in target.registered_actions:
    if isinstance(template, SpellAction):
        if template.spell_range.type == RangeType.RANGE:
            template.alt_range = template.spell_range.normal * 2
            self._modified_uuids.append(template.uuid)
        elif template.spell_range.type == RangeType.REACH:
            template.alt_range = 30
            self._modified_uuids.append(template.uuid)
```

### Auto-Removal Handler

MetamagicActive registers an EventHandler on `CAST_SPELL` at `EFFECT` phase. When any spell is cast by this entity, the handler calls `remove_condition("MetamagicActive")`, which triggers `cleanup_own_state()` → `clear_action_overrides()`.

**Non-spell actions do NOT consume metamagic.** Only `CAST_SPELL` events trigger removal. Using Dash, Dodge, Attack, etc. leaves MetamagicActive intact.

### Stacking Prevention

All metamagic actions check `"MetamagicActive" in entity.active_conditions` in both `pre_validate()` (hides from UI) and `_validate()` (blocks execution). Only one metamagic can be active at a time.

---

## 4. Font of Magic

Two-way conversion between spell slots and sorcery points. Registered per slot level by `SorceryPointsFeature`.

### ConvertSlotToSP

- **Cost**: 1 bonus action + 1 spell slot of specified level
- **Effect**: Gain SP equal to slot level
- **Cap**: SP cannot exceed maximum (= sorcerer level)
- **Levels**: One action per available slot level (L1-L5)

### ConvertSPToSlot

- **Cost**: 1 bonus action + X SP (from table below)
- **Effect**: Restore 1 spell slot (removes a cost modifier)
- **Pre-validate**: Entity must have base slots at this level
- **Levels**: One action per available slot level (L1-L5)

**SP-to-Slot Cost Table** (`SP_TO_SLOT_COST`):

| Slot Level | SP Cost |
|------------|---------|
| 1 | 2 |
| 2 | 3 |
| 3 | 5 |
| 4 | 6 |
| 5 | 7 |

### Registration Logic

`SorceryPointsFeature._apply()` only registers FoM actions for slot levels where the entity has base capacity:

```python
for slot_level in range(1, 6):
    slot_value = target.action_economy._get_spell_slot_value(slot_level)
    base_mod = slot_value.get_base_modifier()
    if base_mod and base_mod.normalized_value > 0:
        target.register_action(ConvertSlotToSP(..., slot_level=slot_level))
        target.register_action(ConvertSPToSlot(..., slot_level=slot_level))
```

A L5 sorcerer with slots {1: 4, 2: 3, 3: 2} gets FoM actions for L1, L2, L3 only — no L4 or L5 actions.

---

## 5. SorceryPointsFeature

The master feature condition that orchestrates the Sorcerer's resource system. Applied at L2+.

### What It Registers

1. **Resource**: `"sorcery_points"` with maximum = sorcerer level, `RechargeType.LONG_REST`
2. **Metamagic actions**: For each choice in `metamagic_choices`, registers the corresponding action template (via `METAMAGIC_ACTIONS` lookup)
3. **Font of Magic actions**: For each spell slot level with base > 0, registers both `ConvertSlotToSP` and `ConvertSPToSlot`

### Cleanup (_remove)

Inverse of _apply:
1. Removes `"sorcery_points"` resource
2. Unregisters all metamagic actions by name (uses static name dict, not class instantiation)
3. Unregisters all Font of Magic actions (L1-L5, both directions)
4. Removes active `MetamagicActive` if present

```python
# Static name lookup avoids Pydantic instantiation issue
metamagic_names = {
    "quickened": "Quickened Spell",
    "twinned": "Twinned Spell",
    "distant": "Distant Spell",
}
```

---

## 6. Draconic Bloodline

### DraconicResilience (L1)

**Two effects:**
- `+hp_bonus` to max HP (= sorcerer level, set by factory)
- AC = 13 + DEX when unarmored (contextual modifier: +3 to AC when no armor equipped)

Uses `ContextualNumericalModifier` on `equipment.ac_bonus.self_contextual` — same pattern as Barbarian's Unarmored Defense and Fighter's Defense style.

```python
def draconic_resilience_ac_check(source_entity_uuid, ...):
    entity = Entity.get(source_entity_uuid)
    if entity.equipment.body_armor and body_armor.type != ArmorType.CLOTH:
        return None  # Wearing armor — doesn't apply
    return NumericalModifier.create(name="Draconic Resilience AC", value=3, ...)
```

### ElementalAffinity (L6)

**Effect**: Resistance to ancestry damage type

Uses `ResistanceModifier` on `health.damage_reduction.self_static`. Configurable via `damage_type` field (default Fire).

---

## 7. Level Progression

### Feature Levels

| Level | Feature | Type | Implementation |
|-------|---------|------|----------------|
| 1 | Draconic Resilience | Modifier condition | HP + contextual AC |
| 2 | Sorcery Points (2 SP) | Feature condition | Resource + Font of Magic actions |
| 3 | Metamagic (2 choices) | Actions via SorceryPointsFeature | Quickened/Twinned/Distant |
| 4 | ASI | Via factory | +2 ability points |
| 6 | Elemental Affinity | Modifier condition | Damage resistance |
| 8 | ASI | Via factory | +2 ability points |
| 10 | Metamagic (3rd choice) | Via factory config | Additional metamagic option |
| 12 | ASI | Via factory | +2 ability points |
| 16 | ASI | Via factory | +2 ability points |
| 17 | Metamagic (4th choice) | Via factory config | Additional metamagic option |
| 19 | ASI | Via factory | +2 ability points |

### Sorcery Points Scaling

SP = sorcerer level (0 at L1, unlocks at L2):

| Level | SP | Metamagic Known |
|-------|----|----|
| 1 | 0 | 0 |
| 2 | 2 | 0 |
| 3 | 3 | 2 |
| 5 | 5 | 2 |
| 10 | 10 | 3 |
| 17 | 17 | 4 |
| 20 | 20 | 4 |

### Spell Slot Table (Full Caster)

Same as Wizard. Key levels:

| Level | L1 | L2 | L3 | L4 | L5 | L6 | L7 | L8 | L9 |
|-------|----|----|----|----|----|----|----|----|-----|
| 1 | 2 | | | | | | | | |
| 3 | 4 | 2 | | | | | | | |
| 5 | 4 | 3 | 2 | | | | | | |
| 7 | 4 | 3 | 3 | 1 | | | | | |
| 9 | 4 | 3 | 3 | 3 | 1 | | | | |
| 11 | 4 | 3 | 3 | 3 | 2 | 1 | | | |
| 15 | 4 | 3 | 3 | 3 | 2 | 1 | 1 | 1 | |
| 17 | 4 | 3 | 3 | 3 | 2 | 1 | 1 | 1 | 1 |
| 20 | 4 | 3 | 3 | 3 | 3 | 2 | 2 | 1 | 1 |

### HP Calculation

`HP = d6_average * level + CON_modifier * level + draconic_resilience_bonus`

Where d6_average uses `(6/2 + 1) = 4` per level (average mode) and draconic_resilience_bonus = level.

Example L5 with CON 14 (+2): `(4 * 5) + (2 * 5) + 5 = 20 + 10 + 5 = 35 base` + first level max = 37.

### AC Calculation

- **No armor**: 13 + DEX modifier (Draconic Resilience)
- **With armor**: Armor AC (Draconic Resilience contextual check returns None)

---

## 8. Factory

### SorcererConfig

```python
from dnd.classes.sorcerer_factory import SorcererConfig, create_sorcerer

config = SorcererConfig(
    level=5,
    name="Draconic Sorcerer",
    position=(5, 5),
    faction="heroes",

    # Ability scores (8-15 range, point buy)
    base_strength=8,
    base_dexterity=14,
    base_constitution=13,
    base_intelligence=10,
    base_wisdom=12,
    base_charisma=15,

    # L1 racial bonuses
    bonus_plus_2="charisma",     # CHA 15 → 17
    bonus_plus_1="constitution", # CON 13 → 14

    # Subclass
    origin=SorcererOriginChoice.DRACONIC_BLOODLINE,
    draconic_damage_type="Fire",

    # Metamagic (required at L3+, count must match level)
    metamagic_choices=["quickened", "twinned"],

    # ASI (required at reached ASI levels)
    asi_4=[("charisma", 2)],   # CHA 17 → 19

    # Equipment
    equipment_preset="dagger",

    # Spells (optional — defaults to curated list)
    spell_names=None,
)

sorcerer = create_sorcerer(config)
```

### Config Validators

| Validator | What It Checks |
|-----------|---------------|
| `validate_different_bonuses` | `bonus_plus_2 != bonus_plus_1` |
| `validate_metamagic_for_level` | Metamagic count matches `get_metamagic_count(level)`, valid options, no duplicates |
| `validate_asis_for_level` | ASIs required at reached levels, each totals +2 |

### Factory Flow

```
create_sorcerer(config)
├── calculate_final_ability_scores()  → base + L1 bonuses + ASIs (cap 20)
├── get_proficiency_bonus()           → 2 + (level-1)//4
├── Build EntityConfig                → AbilityScores, Health(d6), ActionEconomy(spell_slots), Spellcasting(CHA)
├── Entity.create()
├── setup_standard_actions()          → Move, Dash, Dodge, Disengage, DropConcentration + weapon attacks
├── apply_equipment()                 → Dagger or quarterstaff
├── apply_sorcerer_features()         → DraconicResilience + SorceryPointsFeature + ElementalAffinity
├── register_spells_by_name()         → Default curated list or custom override
└── register_shield_reaction()        → Shield as reaction spell
```

### Default Spell List by Level

| Level | Spells Added |
|-------|-------------|
| 1 | Fire Bolt, Ray of Frost (cantrips), Magic Missile |
| 2 | + Burning Hands |
| 3 | + Hold Person, Scorching Ray |
| 5 | + Fireball, Lightning Bolt |
| 7 | + Ice Storm |
| 9 | + Cloudkill |

---

## 9. Not Yet Implemented

### SRD Sorcerer Features

| Level | Feature | Notes |
|-------|---------|-------|
| 14 | Dragon Wings | Fly speed (movement modifier) |
| 18 | Draconic Presence | AoE frighten/charm (like Intimidating Presence) |
| 20 | Sorcerous Restoration | Regain 4 SP on short rest |

### Additional Metamagic Options

| Option | Implementation Approach |
|--------|------------------------|
| Empowered | Handler on `DAMAGE_ROLL_RESULT` — reroll damage dice |
| Heightened | Override on save events — impose disadvantage |
| Careful | Override on AoE — allies auto-succeed saves |
| Subtle | Skip verbal/somatic components (stealth casting) |
| Extended | Double spell duration (duration tracking needed first) |

### Wild Magic Origin

Not started. Would involve random effects table, Tides of Chaos, Wild Magic Surge.

---

## 10. Test Coverage

77 tests across 18 categories in `examples/test_sorcerer_factory.py`:

| Category | Tests | What |
|----------|-------|------|
| SF-A | 5 | Factory basics — stats, HP, AC, spell slots, validation |
| SF-B | 4 | Sorcery points — scaling, consumption, blocking |
| SF-C | 4 | Quickened — template mod, cast flow, cleanup |
| SF-D | 3 | Twinned — multi-target, concentration, cleanup |
| SF-E | 2 | Distant — range doubling, template restore |
| SF-F | 3 | Font of Magic — slot↔SP, insufficient SP |
| SF-G | 3 | Draconic — HP, AC, resistance |
| SF-H | 5 | Quickened extended — same-turn combos, filtering |
| SF-I | 6 | Twinned extended — SP scaling, AoE/SELF filter, concentration |
| SF-J | 5 | Distant extended — varied ranges, touch→30ft |
| SF-K | 5 | Metamagic interactions — stacking, persistence, miss cleanup |
| SF-L | 6 | Font of Magic extended — L2/L3 conversions, SP cap |
| SF-M | 5 | Draconic extended — HP scaling, armor AC, resistance |
| SF-N | 5 | Config edge cases — L10, custom spells, presets |
| SF-O | 4 | Spell slot table verification |
| SF-P | 4 | Resource & action discovery |
| SF-Q | 3 | Feature removal cleanup |
| SF-R | 5 | Combat integration — full turns, concentration, Shield, death |

### Running Tests

```bash
python examples/test_sorcerer_factory.py       # All 77 sorcerer tests
python examples/test_action_overrides.py        # 31 action override unit tests
python examples/test_action_overrides_exec.py   # 20 action override execution tests
```
