# Cleric Class System

**Last Updated:** February 2026

## 1. Architecture Overview

The Cleric is the engine's first **WIS-based prepared caster** and **healer class**. Like Fighter, Barbarian, and Sorcerer, it's implemented as **conditions applied to entities** — no `Class` object exists.

**Two key innovations**:
- **Spell Preparation pattern** — prepared casters can swap spells from a class list at long rest. Reusable for Wizard, Druid, Paladin.
- **Healing Spell pattern** (Pattern 17) — uses existing `receive_healing()` / `HealEvent` / `EventType.HEAL` infrastructure.

```
Entity (Cleric)
├── ability_scores          ← WIS primary, CON secondary
├── health                  ← d8 hit dice
├── equipment               ← Mace or warhammer + shield + scale mail (chain mail for Life Domain)
├── action_economy          ← Spell slots (full caster table) + channel_divinity resource
├── spellcasting            ← ability="wisdom"
├── active_conditions
│   ├── "Spell Preparation Feature" → manages prepared spell list (L1+)
│   ├── "Channel Divinity Feature"  → resource + Turn Undead + domain action (L2+)
│   ├── "Disciple of Life"          → healing bonus handler (L1, Life Domain)
│   ├── "Blessed Healer"            → self-heal on healing others (L6, Life Domain)
│   ├── "Divine Strike"             → extra weapon damage handler (L8, Life Domain)
│   └── "Supreme Healing"           → max healing dice (L17, Life Domain)
└── registered_actions
    ├── Standard: Move, Dash, Dodge, Disengage, DropConcentration
    ├── Weapon: Mace/Warhammer attack
    ├── Cantrips: Sacred Flame, Guidance, etc.
    ├── Prepared Spells: Cure Wounds, Bless, Hold Person, etc.
    ├── Domain Spells (always prepared): Bless, Cure Wounds, Lesser Restoration, etc.
    ├── Channel Divinity: Turn Undead, Preserve Life
    └── Shield of Faith, etc. (bonus action spells)
```

### Proficiencies

- **Armor**: Light armor, medium armor, shields. Life Domain adds heavy armor.
- **Weapons**: Simple weapons
- **Saving Throws**: Wisdom, Charisma
- **Skills**: Choose 2 from History, Insight, Medicine, Persuasion, Religion

### Files

| File | Purpose |
|------|---------|
| `dnd/classes/cleric.py` | All conditions + actions (DiscipleOfLife, ChannelDivinityFeature, TurnUndead, Turned, BlessedHealer, DivineStrike, SupremeHealing, PreserveLife) |
| `dnd/classes/cleric_factory.py` | `ClericConfig` + `create_cleric()` factory |
| `dnd/classes/spell_preparation.py` | `SpellPreparationFeature` condition (reusable for Wizard, Druid, Paladin) |
| `examples/test_cleric_factory.py` | Tests |

---

## 2. Spell Preparation System

**Why a new system**: Sorcerers have fixed known spells set at factory creation. Clerics, Wizards, Druids, and Paladins **prepare** from a class spell list, swapping spells at long rest. This system must be reusable across all prepared caster classes.

**Design**: `SpellPreparationFeature` is a BaseCondition on the entity that manages which spells are currently registered as action templates.

```python
class SpellPreparationFeature(BaseCondition):
    name: str = "Spell Preparation Feature"
    class_spell_list: List[str]        # All spell names available to this class
    always_prepared: List[str]         # Domain/subclass spells (bonus, don't count against limit)
    prepared_spell_names: List[str]    # Currently prepared spells (chosen by player)
    max_prepared: int                  # WIS mod + level (set by factory, minimum 1)
    cantrip_names: List[str]          # Always registered, never count against limit

    def _apply(declaration_event):
        # 1. Register cantrips via register_spells_by_name()
        # 2. Register always_prepared spells via register_spells_by_name()
        # 3. Register prepared_spell_names spells via register_spells_by_name()
        # Return standard 5-tuple (no modifiers, no handlers, no sub-conditions)

    def prepare_spells(new_prepared: List[str]):
        # Validate: len(new_prepared) ≤ max_prepared
        # Validate: all names in class_spell_list
        # Validate: entity has spell slots for each spell's level
        # Unregister old prepared spells (not cantrips, not always_prepared)
        # Register new prepared spells via register_spells_by_name()
        # Update self.prepared_spell_names

    def cleanup_own_state():
        # Unregister all spells this feature registered (cantrips + always_prepared + prepared)
        # Uses entity.unregister_action(name) for each
```

### Key Design Decisions

- Cantrips and always-prepared spells are **separate** from the preparation limit
- `prepare_spells()` is the only API for changing prepared spells at runtime
- Spell templates are **registered/unregistered** — no new "prepared" flag on SpellAction needed
- Uses existing `register_spells_by_name()` from `dnd/actions_functional.py` for registration
- Uses existing `entity.unregister_action(name)` for cleanup
- Separate file (`spell_preparation.py`) because it's reusable across classes

### For Cleric

`max_prepared = WIS modifier + cleric level` (minimum 1).

Life Domain spells from the domain table are `always_prepared` — they don't count against the preparation limit.

### Life Domain Spells (Always Prepared)

| Cleric Level | Domain Spells |
|--------------|---------------|
| 1 | Bless, Cure Wounds |
| 3 | Lesser Restoration, Spiritual Weapon |
| 5 | Beacon of Hope, Revivify |
| 7 | Death Ward, Guardian of Faith |
| 9 | Mass Cure Wounds, Raise Dead |

### Cleric Spell List (Full)

All Cleric spells from the SRD. See `CLERIC_SPELL_ANALYSIS.md` for the complete 105-spell breakdown by level.

---

## 3. Life Domain Features

The SRD only includes the Life Domain. All text below is verbatim SRD with implementation notes.

### Bonus Proficiency (Level 1)

> "When you choose this domain at 1st level, you gain proficiency with heavy armor."

**Implementation**: Factory equips chain mail (AC 16) instead of scale mail when `domain="life"`. With shield: AC 18.

### Disciple of Life (Level 1)

> "Also starting at 1st level, your healing spells are more effective. Whenever you use a spell of 1st level or higher to restore hit points to a creature, the creature regains additional hit points equal to 2 + the spell's level."

**Implementation**: `DiscipleOfLife` condition registers an EventHandler on `EventType.HEAL` at `EventPhase.EXECUTION`.

**Requires**: Add `spell_level: int = 0` field to `HealEvent` in `dnd/core/events.py`. Healing spells pass their `cast_at_level` when calling `receive_healing()`. Also add `spell_level` parameter to `entity.receive_healing()`.

```python
class DiscipleOfLife(BaseCondition):
    name: str = "Disciple of Life"

    def _apply(self, declaration_event):
        target = Entity.get(self.target_entity_uuid)
        handler = EventHandler(
            name="Disciple of Life",
            source_entity_uuid=self.target_entity_uuid,
            event_processor=disciple_of_life_processor,
            trigger_conditions=[Trigger(
                name="disciple_of_life_heal",
                event_type=EventType.HEAL,
                event_phase=EventPhase.EXECUTION,
                event_source_entity_uuid=self.target_entity_uuid,  # I'm the healer
            )],
        )
        target.add_event_handler(handler)  # NOT EventQueue — auto-registers

        effect_event = declaration_event.phase_to(EventPhase.EFFECT, ...)
        return [], [handler.uuid], [], [], effect_event

def disciple_of_life_processor(event, source_entity_uuid):
    # Only boost leveled spells (spell_level ≥ 1)
    if event.spell_level >= 1:
        bonus = 2 + event.spell_level
        return event.model_copy(update={"total_healing": event.total_healing + bonus})
    return event
```

**Key**: Fires at EXECUTION phase (before EFFECT) so `total_healing` is boosted before `health.heal()` is called. Filters by `event_source_entity_uuid` so only this Cleric's healing spells get the bonus.

### Preserve Life (Level 2, Channel Divinity)

> "Starting at 2nd level, you can use your Channel Divinity to heal the badly injured. As an action, you present your holy symbol and evoke healing energy that can restore a number of hit points equal to five times your cleric level. Choose any creatures within 30 feet of you, and divide those hit points among them. This feature can restore a creature to no more than half of its hit point maximum. You can't use this feature on an undead or a construct."

**Implementation**: `PreserveLifeAction` is a BaseAction. Similar to `SecondWind` in `dnd/classes/fighter.py` (action that heals), but multi-target with distribution logic.

```python
class PreserveLifeAction(BaseAction):
    name: str = "Preserve Life"
    target_type: TargetType = TargetType.SELF  # Affects area around caster
    cleric_level: int = 1
    costs: List[Cost]  # 1 action + 1 channel_divinity resource

    def _apply(self, execution_event):
        caster = Entity.get(self.source_entity_uuid)
        healing_pool = 5 * self.cleric_level

        # Get all allies within 30ft
        # Filter: creature_type != CreatureType.UNDEAD and != CreatureType.CONSTRUCT
        # For each valid ally (sorted by lowest HP %):
        #   heal_amount = min(remaining_pool, max_hp // 2 - current_hp)
        #   if heal_amount > 0: target.receive_healing(heal_amount, ...)
        #   remaining_pool -= heal_amount
```

**Costs**: `Cost(cost_type="actions", cost=1)` + `Cost(resource_name="channel_divinity", resource_cost=1)`

### Blessed Healer (Level 6)

> "Beginning at 6th level, the healing spells you cast on others heal you as well. When you cast a spell of 1st level or higher that restores hit points to a creature other than you, you regain hit points equal to 2 + the spell's level."

**Implementation**: EventHandler on `EventType.HEAL` at `EventPhase.EFFECT`.

```python
def blessed_healer_processor(event, source_entity_uuid):
    caster = Entity.get(source_entity_uuid)
    # Check: source is self, target is NOT self, spell_level ≥ 1
    if (event.source_entity_uuid == source_entity_uuid
        and event.target_entity_uuid != source_entity_uuid
        and event.spell_level >= 1):
        # Self-heal (fires its own HealEvent sub-chain)
        caster.receive_healing(
            2 + event.spell_level, source_entity_uuid,
            source_description="Blessed Healer",
            parent_event=event.uuid
        )
    return event
```

**Key**: Fires at EFFECT phase (after EXECUTION where Disciple of Life boosted the healing). Self-heal uses `parent_event=event.uuid` for correct combat log nesting.

### Divine Strike (Level 8, upgraded at Level 14)

> "At 8th level, you gain the ability to infuse your weapon strikes with divine energy. Once on each of your turns when you hit a creature with a weapon attack, you can cause the attack to deal an extra 1d8 radiant damage to the target. When you reach 14th level, the extra damage increases to 2d8."

**Implementation**: EventHandler on `EventType.DAMAGE_ROLL_RESULT` at `EventPhase.EFFECT`. Same pattern as Divine Smite in `dnd/classes/paladin.py`, but:
- **No spell slot cost** (free)
- **Once per turn** (not per attack) — uses context flag, reset on TURN_START handler
- **Simpler** overall

```python
class DivineStrike(BaseCondition):
    name: str = "Divine Strike"
    extra_dice: int = 1  # 1d8 at L8, 2d8 at L14+

    def _apply(self, declaration_event):
        target = Entity.get(self.target_entity_uuid)

        # Handler on DAMAGE_ROLL_RESULT at EFFECT
        # Processor checks:
        #   1. action_category == ActionCategory.ATTACK (weapon attack, not spell)
        #   2. attack_outcome is HIT or CRIT (not miss)
        #   3. Not yet used this turn (check event.context["divine_strike_used"])
        # If all pass:
        #   Roll extra_dice × d8 radiant
        #   Append to event.damages
        #   Set event.context["divine_strike_used"] = True

        # Handler on TURN_START at EFFECT to reset the once-per-turn flag
        # (Clears divine_strike_used from context)

        return [], [damage_handler.uuid, turn_handler.uuid], [], [], effect_event
```

### Supreme Healing (Level 17)

> "Starting at 17th level, when you would normally roll one or more dice to restore hit points with a spell, you instead use the highest number possible for each die. For example, instead of restoring 2d6 hit points to a creature, you restore 12."

**Implementation**: Two possible approaches:

1. **Spell-side check** (simpler): Healing spells check `"Supreme Healing" in caster.active_conditions` and use `die_type * num_dice` instead of rolling.
2. **Handler on HEAL at EXECUTION** (more composable): Replace `total_healing` with max possible value. But this requires knowing the dice formula, which isn't on HealEvent.

**Recommended**: Approach 1. In each healing spell's `_apply()`:
```python
if "Supreme Healing" in caster.active_conditions:
    total = num_dice * die_type_max + modifier  # e.g., 2*8 + 3 = 19
else:
    total = healing_dice.roll.total
```

---

## 4. Channel Divinity System

Resource-based feature using the same pattern as `SecondWindFeature` in `dnd/classes/fighter.py`.

### Resource

`"channel_divinity"` with `RechargeType.SHORT_REST`:

| Level | Uses per Rest |
|-------|---------------|
| 2-5 | 1 |
| 6-17 | 2 |
| 18-20 | 3 |

### Pattern

Same as `SecondWindFeature` in `dnd/classes/fighter.py`:

1. `ChannelDivinityFeature` condition calls `target.action_economy.add_resource("channel_divinity", max_uses, RechargeType.SHORT_REST)` in `_apply()`
2. Registers action templates: `TurnUndeadAction` + domain-specific action (`PreserveLifeAction` for Life Domain)
3. Each action includes `Cost(resource_name="channel_divinity", resource_cost=1)`

```python
class ChannelDivinityFeature(BaseCondition):
    name: str = "Channel Divinity Feature"
    max_uses: int = 1
    destroy_cr_threshold: float = -1  # Passed to TurnUndeadAction
    cleric_level: int = 1             # Passed to PreserveLifeAction

    def _apply(self, declaration_event):
        target = Entity.get(self.target_entity_uuid)
        target.action_economy.add_resource("channel_divinity", self.max_uses, RechargeType.SHORT_REST)

        turn_undead = TurnUndeadAction(
            source_entity_uuid=self.target_entity_uuid,
            destroy_cr_threshold=self.destroy_cr_threshold,
            template=True,
        )
        target.register_action(turn_undead)

        preserve_life = PreserveLifeAction(
            source_entity_uuid=self.target_entity_uuid,
            cleric_level=self.cleric_level,
            template=True,
        )
        target.register_action(preserve_life)

        effect_event = declaration_event.phase_to(EventPhase.EFFECT, ...)
        return [], [], [], [], effect_event

    def cleanup_own_state(self):
        target = Entity.get(self.target_entity_uuid)
        target.action_economy.remove_resource("channel_divinity")
        target.unregister_action("Turn Undead")
        target.unregister_action("Preserve Life")
```

### Turn Undead Action

```python
class TurnUndeadAction(BaseAction):
    name: str = "Turn Undead"
    target_type: TargetType = TargetType.SELF  # Affects area around caster
    destroy_cr_threshold: float = -1  # -1 = no destroy. Set by factory based on level.
    costs: List[Cost]  # 1 action + 1 channel_divinity resource

    def _apply(self, execution_event):
        caster = Entity.get(self.source_entity_uuid)

        # 1. Get all visible entities within 30ft
        # 2. Filter: creature_type == CreatureType.UNDEAD
        # 3. Each makes WIS save vs caster.spell_save_dc()
        # 4. On failure:
        #    - If CR ≤ destroy_cr_threshold → instant death (Entity.kill() or set HP to 0)
        #    - Else → apply Turned condition (duration_rounds=10)
```

### Destroy Undead (Scaling)

| Cleric Level | Destroys Undead CR ≤ |
|--------------|----------------------|
| 5 | 1/2 |
| 8 | 1 |
| 11 | 2 |
| 14 | 3 |
| 17 | 4 |

Factory sets `destroy_cr_threshold` on the `TurnUndeadAction` based on level. Before L5: `-1` (no destroy).

### Turned Condition

Similar to `Frightened` in `dnd/conditions.py`. The Turned creature:
- Must use its turns to Dash directly away from the turner
- Can't willingly move within 30ft of turner
- Can't take reactions
- **Ends immediately if creature takes any damage**

```python
class Turned(BaseCondition):
    name: str = "Turned"
    duration_rounds: int = 10  # 1 minute

    def _apply(self, declaration_event):
        target = Entity.get(self.target_entity_uuid)

        # Sub-condition: Frightened (reuses its disadvantage modifiers + speed constraints)
        frightened = Frightened(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            parent_condition=self.uuid,
        )
        target.add_condition(frightened, parent_event=declaration_event)

        # Handler on TAKE_DAMAGE at EFFECT: auto-remove Turned when damaged
        damage_handler = EventHandler(
            name="Turned Damage Break",
            source_entity_uuid=self.target_entity_uuid,
            event_processor=turned_damage_break_processor,
            trigger_conditions=[Trigger(
                name="turned_damage_break",
                event_type=EventType.TAKE_DAMAGE,
                event_phase=EventPhase.EFFECT,
                event_target_entity_uuid=self.target_entity_uuid,
            )],
        )
        target.add_event_handler(damage_handler)

        # Max constraint: no reactions (set reactions to max 0)
        # Duration tracking via advance_duration()

        return modifiers, [damage_handler.uuid], [frightened.uuid], [], effect_event
```

**Frightened condition** (existing, from `dnd/conditions.py`) provides:
- Disadvantage on attack rolls and ability checks while frightener is visible (contextual modifiers)
- Can't willingly move closer to frightener (contextual max constraint on movement)

Turned adds: forced Dash away, no reactions, damage-ends-it.

---

## 5. Healing Spell Pattern (Pattern 17)

### Existing Infrastructure (Already in Engine)

| Component | Location | Status |
|-----------|----------|--------|
| `entity.receive_healing(amount, source_uuid, source_description, parent_event)` | `dnd/entity.py:973` | ✅ EXISTS |
| `HealEvent` with `total_healing`, `actual_healing`, `was_blocked`, `source_description` | `dnd/core/events.py:2375` | ✅ EXISTS |
| `EventType.HEAL` | `dnd/core/events.py` | ✅ EXISTS |
| `health.heal(amount)` — handles HP cap, healing_blocked | `dnd/blocks/health.py` | ✅ EXISTS |
| `health.is_healing_blocked()` — checks flag (set by Chill Touch NoHealing condition) | `dnd/blocks/health.py` | ✅ EXISTS |
| `CombatLogEntryType.HEAL` with `HealLogData` | `dnd/core/combat_log.py` | ✅ EXISTS |
| `HealEvent.generate_combat_log()` | `dnd/core/events.py` | ✅ EXISTS |
| `spell_level` field on HealEvent | — | ❌ NEEDS ADDING |
| `spell_level` parameter on `receive_healing()` | — | ❌ NEEDS ADDING |

### Event Flow

```
receive_healing(amount, source_uuid, description, parent_event, spell_level=0)
├── HealEvent DECLARATION (spell_level stored on event)
├── HealEvent EXECUTION    ← Disciple of Life handler modifies total_healing here
├── HealEvent EFFECT       ← Blessed Healer handler triggers self-heal here
├── Check healing_blocked → set was_blocked=True OR apply health.heal(amount)
├── Calculate actual_healing = hp_after - hp_before
├── HealEvent COMPLETION   → combat log generated (via callback, no handlers)
└── Return actual_healing
```

### What Needs Adding

1. `spell_level: int = 0` field on `HealEvent` in `dnd/core/events.py`
2. `spell_level: int = 0` parameter on `entity.receive_healing()` in `dnd/entity.py`
3. Pass `spell_level` through when creating `HealEvent`

This lets Disciple of Life and Blessed Healer know the spell level without inspecting the call stack.

### Canonical Implementation: Cure Wounds

```python
class CureWounds(SpellAction):
    name: str = "Cure Wounds"
    spell_level: int = 1
    spell_school: str = "evocation"
    target_type: TargetType = TargetType.ENTITY
    spell_range: Range = Range(type=RangeType.REACH, normal=5)  # Touch

    def _apply(self, execution_event: SpellEvent):
        target = Entity.get(self.target_entity_uuid)
        caster = Entity.get(self.source_entity_uuid)

        # Roll healing: (cast_at_level)d8 + WIS modifier
        num_dice = self.cast_at_level  # 1d8 at L1, 2d8 at L2, etc.
        wis_mod = caster.ability_scores.get_ability("wisdom").modifier
        healing_dice = Dice(die_type=DieType.D8, num_dice=num_dice, modifier=wis_mod)
        healing_roll = healing_dice.roll
        total = healing_roll.total

        effect_event = execution_event.phase_to(EventPhase.EFFECT, ...)

        # Healing via event system — fires HealEvent chain
        # Disciple of Life can boost total_healing at EXECUTION phase
        actual = target.receive_healing(
            total, caster.uuid,
            source_description=f"Cure Wounds: {num_dice}d8({healing_roll.results})+{wis_mod}",
            parent_event=effect_event.uuid,
            spell_level=self.cast_at_level  # NEW parameter for Disciple of Life
        )

        return effect_event.phase_to(EventPhase.COMPLETION, ...)
```

### Healing Spell Variants

| Spell | Dice | Range | Cost | Target Type | Upcast |
|-------|------|-------|------|-------------|--------|
| Cure Wounds | (level)d8+WIS | Touch (5ft) | Action | ENTITY | +1d8/level |
| Healing Word | (level)d4+WIS | 60ft | Bonus Action | ENTITY | +1d4/level |
| Mass Healing Word | 1d4+WIS | 60ft | Bonus Action | MULTI_ENTITY (6) | +1d4/level |
| Mass Cure Wounds | (level-2)d8+WIS | 60ft | Action | POSITION_AOE (30ft sphere, up to 6) | +1d8/level |
| Heal | 70 HP flat | 60ft | Action | ENTITY | +10/level above 6 |
| Mass Heal | 700 HP pool | 60ft | Action | Multi-target distribution | — |
| Prayer of Healing | 2d8+WIS | 30ft | 10min cast | MULTI_ENTITY (6) | +1d8/level |
| Regenerate | 4d8+15 + 1/round | Touch | Action | ENTITY | — |

All follow the same core pattern: roll dice → call `target.receive_healing()` with `spell_level` parameter.

---

## 6. Level Progression

### Feature Levels

| Level | Feature | Type | Implementation |
|-------|---------|------|----------------|
| 1 | Spellcasting (WIS, full caster) | Block config | SpellcastingConfig(ability="wisdom") |
| 1 | Disciple of Life | Modifier condition | Handler on HEAL at EXECUTION: +2+spell_level bonus |
| 1 | Heavy Armor (Life Domain) | Equipment | Factory equips chain mail |
| 2 | Channel Divinity 1/rest | Feature condition | Resource + Turn Undead + Preserve Life actions |
| 4 | ASI | Via factory | +2 ability points |
| 5 | Destroy Undead (CR 1/2) | TurnUndead param | destroy_cr_threshold=0.5 |
| 6 | Blessed Healer | Modifier condition | Handler on HEAL at EFFECT: self-heal 2+spell_level |
| 6 | Channel Divinity 2/rest | Resource update | max_uses=2 |
| 8 | ASI | Via factory | +2 ability points |
| 8 | Divine Strike (1d8) | Attack handler condition | Handler on DAMAGE_ROLL_RESULT: +1d8 radiant |
| 8 | Destroy Undead (CR 1) | TurnUndead param | destroy_cr_threshold=1 |
| 10 | Divine Intervention | Special | Roll ≤ level → DM intervention (out of scope) |
| 11 | Destroy Undead (CR 2) | TurnUndead param | destroy_cr_threshold=2 |
| 12 | ASI | Via factory | +2 ability points |
| 14 | Divine Strike (2d8) | Upgrade | extra_dice=2 |
| 14 | Destroy Undead (CR 3) | TurnUndead param | destroy_cr_threshold=3 |
| 16 | ASI | Via factory | +2 ability points |
| 17 | Supreme Healing | Modifier condition | Max dice on healing spells |
| 17 | Destroy Undead (CR 4) | TurnUndead param | destroy_cr_threshold=4 |
| 18 | Channel Divinity 3/rest | Resource update | max_uses=3 |
| 19 | ASI | Via factory | +2 ability points |

### Spell Slot Table (Full Caster, same as Sorcerer)

| Level | L1 | L2 | L3 | L4 | L5 | L6 | L7 | L8 | L9 |
|-------|----|----|----|----|----|----|----|----|-----|
| 1 | 2 | | | | | | | | |
| 2 | 3 | | | | | | | | |
| 3 | 4 | 2 | | | | | | | |
| 4 | 4 | 3 | | | | | | | |
| 5 | 4 | 3 | 2 | | | | | | |
| 6 | 4 | 3 | 3 | | | | | | |
| 7 | 4 | 3 | 3 | 1 | | | | | |
| 8 | 4 | 3 | 3 | 2 | | | | | |
| 9 | 4 | 3 | 3 | 3 | 1 | | | | |
| 10 | 4 | 3 | 3 | 3 | 2 | | | | |
| 11 | 4 | 3 | 3 | 3 | 2 | 1 | | | |
| 13 | 4 | 3 | 3 | 3 | 2 | 1 | 1 | | |
| 15 | 4 | 3 | 3 | 3 | 2 | 1 | 1 | 1 | |
| 17 | 4 | 3 | 3 | 3 | 2 | 1 | 1 | 1 | 1 |
| 18 | 4 | 3 | 3 | 3 | 3 | 1 | 1 | 1 | 1 |
| 19 | 4 | 3 | 3 | 3 | 3 | 2 | 1 | 1 | 1 |
| 20 | 4 | 3 | 3 | 3 | 3 | 2 | 2 | 1 | 1 |

### Cantrips Known

| Level | Cantrips |
|-------|----------|
| 1 | 3 |
| 4 | 4 |
| 10 | 5 |

### HP Calculation

`HP = d8_average * level + CON_modifier * level`

Where d8_average = (8/2 + 1) = 5 per level (average mode).

Example L5 with CON 14 (+2): `(5 * 5) + (2 * 5) = 25 + 10 = 35 base` + first level max = 36.

### AC Calculation

- **Life Domain**: Chain mail (AC 16) or chain mail + shield (AC 18)
- **Other domains**: Scale mail (AC 14 + DEX max 2) + shield = AC 16 + DEX(max 2)

---

## 7. Factory

### ClericConfig

```python
from dnd.classes.cleric_factory import ClericConfig, create_cleric

config = ClericConfig(
    level=5,
    name="Life Cleric",
    position=(5, 5),
    faction="heroes",

    # Ability scores (8-15 range, point buy)
    base_strength=10,
    base_dexterity=12,
    base_constitution=14,
    base_intelligence=8,
    base_wisdom=15,
    base_charisma=13,

    # L1 racial bonuses
    bonus_plus_2="wisdom",       # WIS 15 → 17
    bonus_plus_1="constitution", # CON 14 → 15

    # Domain (only "life" in SRD)
    domain="life",

    # ASI (required at reached ASI levels)
    asi_4=[("wisdom", 2)],  # WIS 17 → 19

    # Equipment
    equipment_preset="mace_shield",  # or "warhammer_shield"

    # Spells (optional — defaults to curated list per level)
    cantrip_names=None,
    prepared_spell_names=None,
)

cleric = create_cleric(config)
```

### Config Validators

Same pattern as `SorcererConfig`:

| Validator | What It Checks |
|-----------|---------------|
| `validate_different_bonuses` | `bonus_plus_2 != bonus_plus_1` |
| `validate_asis_for_level` | ASIs required at reached levels (4, 8, 12, 16, 19), each totals +2 |
| `validate_domain` | Must be "life" (only SRD domain) |
| `validate_prepared_count` | If `prepared_spell_names` provided, count ≤ WIS mod + level |

### Factory Flow

```
create_cleric(config)
├── calculate_final_ability_scores()  → base + L1 bonuses + ASIs (cap 20)
├── get_proficiency_bonus()           → 2 + (level-1)//4
├── Build EntityConfig:
│   ├── AbilityScoresConfig (WIS primary)
│   ├── HealthConfig(hit_dice_value=8, count=level, mode="average")
│   ├── ActionEconomyConfig(spell_slots=full_caster_table[level])
│   ├── SpellcastingConfig(ability="wisdom")
│   ├── SavingThrowSetConfig(proficient=["wisdom", "charisma"])
│   └── SkillSetConfig(proficient=[2 chosen skills])
├── Entity.create()
├── setup_standard_actions()
├── apply_equipment()                 → Mace/warhammer + shield + scale mail/chain mail
├── apply_cleric_features()           → DiscipleOfLife + ChannelDivinityFeature + etc.
├── Apply SpellPreparationFeature     → cantrips + always_prepared + prepared
└── register_shield_reaction()        → If Shield spell prepared
```

### Default Spell List by Level

| Level | Spells Added |
|-------|-------------|
| 1 | Sacred Flame, Guidance (cantrips), Bless*, Cure Wounds*, Guiding Bolt, Healing Word |
| 3 | + Lesser Restoration*, Spiritual Weapon*, Hold Person |
| 5 | + Beacon of Hope*, Revivify*, Spirit Guardians |
| 7 | + Death Ward*, Guardian of Faith* |
| 9 | + Mass Cure Wounds*, Raise Dead*, Flame Strike |

*Domain spells (always prepared, don't count against limit)

---

## 8. Not Yet Implemented

| Feature | Level | Notes |
|---------|-------|-------|
| Other Divine Domains | 1+ | Only Life Domain in SRD |
| Divine Intervention | 10 | Roll ≤ level → DM intervention (GM adjudication, out of scope) |
| Ritual Casting | 1+ | Cast ritual-tagged spells without slot (10min extra casting time) |
| Spell preparation UI | — | Server/CLI needs UI for spell swapping at long rest |

---

## 9. Test Coverage (Target)

~70 tests across categories in `examples/test_cleric_factory.py`:

| Category | Tests | What |
|----------|-------|------|
| CF-A | 5 | Factory basics — stats, HP, AC, spell slots, proficiencies |
| CF-B | 4 | Spell preparation — prepare/swap, domain always-prepared, limit enforcement |
| CF-C | 5 | Channel Divinity — Turn Undead WIS save, Destroy Undead CR check, uses/rest |
| CF-D | 5 | Cure Wounds — basic heal, upcast, WIS mod, healing blocked, HP cap |
| CF-E | 4 | Healing Word — bonus action, range, upcast scaling |
| CF-F | 4 | Disciple of Life — +2+level bonus on healing spells, not on cantrips |
| CF-G | 3 | Blessed Healer — self-heal when healing others, NOT on self-heal |
| CF-H | 4 | Divine Strike — extra radiant, once per turn, L14 upgrade |
| CF-I | 5 | Spiritual Weapon — summon, strike, move+attack, duration, NOT concentration |
| CF-J | 4 | Shield of Faith — +2 AC, concentration, bonus action |
| CF-K | 3 | Command — Grovel/Flee/Halt effects |
| CF-L | 4 | Aid — +5 max HP, 3 targets, upcast scaling |
| CF-M | 3 | Lesser Restoration — remove blinded/poisoned/paralyzed |
| CF-N | 4 | Config validation — ASI, domain, spell limits |
| CF-O | 5 | Combat integration — healing + damage, Turn Undead, concentration |
| CF-P | 3 | Feature removal cleanup |

### Running Tests

```bash
python examples/test_cleric_factory.py    # All cleric tests
```
