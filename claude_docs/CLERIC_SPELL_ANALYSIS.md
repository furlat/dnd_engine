# Cleric Spell Analysis for D&D Engine

**Last Updated:** February 2026

## Overview

This document analyzes all **105 Cleric spells** from D&D 5e SRD for implementation difficulty in the D&D Engine. It reflects the current state after implementing AoE, concentration, zone spells, the lighting system (Layer 2), stealth/invisibility (Layer 1), and reaction casting.

*Note: 12 cross-class spells were already implemented from the Sorcerer spell list. 7 Cleric-specific spells added in Batch 1 (Guardian of Faith, Command, Guidance, Light, Continual Flame, Silence, Enhance Ability). 10 healing/restoration spells added in Batch 2 (Cure Wounds, Healing Word, Prayer of Healing, Mass Healing Word, Mass Cure Wounds, Heal, Mass Heal, Regenerate, Lesser Restoration, Greater Restoration).*

### Spell Count by Level

| Level | Count |
|-------|-------|
| Cantrips | 7 |
| Level 1 | 15 |
| Level 2 | 17 |
| Level 3 | 19 |
| Level 4 | 8 |
| Level 5 | 13 |
| Level 6 | 10 |
| Level 7 | 8 |
| Level 8 | 4 |
| Level 9 | 4 |
| **Total** | **105** |

### Currently Implemented Spells (29)

| Spell | Level | School | Type | Notes |
|-------|-------|--------|------|-------|
| Sacred Flame | 0 | Evocation | DEX Save | Cantrip scaling ✓ |
| Guidance | 0 | Divination | Touch Buff | +1d4 one ability check, one-use, concentration ✓ |
| Light | 0 | Evocation | Touch Light | 20ft bright + 20ft dim anchored to entity ✓ |
| Bless | 1 | Enchantment | Multi-target Buff | +1d4 attacks/saves, concentration (Pattern 16) ✓ |
| Bane | 1 | Enchantment | Multi-target CHA Save | -1d4 attacks/saves, concentration (Pattern 16) ✓ |
| Guiding Bolt | 1 | Evocation | Attack + Mark | 4d6 radiant, next attack adv (Pattern 1 + mark) ✓ |
| Command | 1 | Enchantment | WIS Save | Grovel/Halt/Flee, upcasts +1 target ✓ |
| Cure Wounds | 1 | Evocation | Touch Heal | 1d8+WIS HP, upcasts +1d8/level (Pattern 17) ✓ |
| Healing Word | 1 | Evocation | Ranged Heal | Bonus action, 60ft, 1d4+WIS, upcasts +1d4 (Pattern 17) ✓ |
| Hold Person | 2 | Enchantment | WIS Save | Paralyzed, concentration (Pattern 5) ✓ |
| Blindness/Deafness | 2 | Necromancy | CON Save | Blinded or Deafened ✓ |
| Continual Flame | 2 | Evocation | Permanent Light | 20ft bright + 20ft dim persistent object ✓ |
| Silence | 2 | Illusion | Zone | 20ft sphere, blocks verbal spells, deafens ✓ |
| Prayer of Healing | 2 | Evocation | Multi-target Heal | 6 targets, 2d8+WIS, upcasts +1d8 (Pattern 17) ✓ |
| Lesser Restoration | 2 | Abjuration | Condition Removal | Remove blinded/deafened/paralyzed/poisoned (Pattern 18) ✓ |
| Spirit Guardians | 3 | Conjuration | Zone | 15ft follows caster, 3d8 WIS save (Pattern 8) ✓ |
| Daylight | 3 | Evocation | Light Zone | 60ft bright light (Pattern 13) ✓ |
| Protection from Energy | 3 | Abjuration | Buff | Single type resistance (Pattern 5) ✓ |
| Mass Healing Word | 3 | Evocation | Multi-target Heal | Bonus action, 6 targets, 1d4+WIS (Pattern 17) ✓ |
| Guardian of Faith | 4 | Conjuration | Stationary Zone | DEX save 20 radiant, 60 damage budget ✓ |
| Insect Plague | 5 | Conjuration | Zone | 20ft sphere, CON save 4d10 (Pattern 8) ✓ |
| Flame Strike | 5 | Evocation | Cylinder AoE | 4d6 fire + 4d6 radiant, DEX save ✓ |
| Mass Cure Wounds | 5 | Evocation | AoE Heal | 30ft sphere, 6 targets, 3d8+WIS (Pattern 17) ✓ |
| Greater Restoration | 5 | Abjuration | Condition Removal | Remove charmed/frightened/stunned/etc. (Pattern 18) ✓ |
| True Seeing | 6 | Divination | Buff | Truesight 120ft ✓ |
| Heal | 6 | Evocation | Mega Heal | Flat 70 HP + remove blinded/deafened (Pattern 17+18) ✓ |
| Fire Storm | 7 | Evocation | Multi-cube AoE | 10 cubes, 7d10 fire (Pattern 3) ✓ |
| Regenerate | 7 | Transmutation | Heal + Regen | 4d8+15 instant + 1 HP/round for 10 rounds (Pattern 17) ✓ |
| Mass Heal | 9 | Evocation | Mega Multi-heal | 700 HP pool + condition removal (Pattern 17+18) ✓ |

*Cross-class: 12 shared with Sorcerer/Wizard. 7 Cleric-specific in Batch 1. 10 healing/restoration in Batch 2.*

---

## Implementation Patterns Catalog

These patterns document the tricks and techniques already used in the codebase. Recognizing which pattern a spell uses determines its difficulty rating.

### Critical: Event Relationship Pattern (parent_event)

**All sub-events must link to their parent event** via the `parent_event` parameter. This ensures:
1. Combat log entries nest correctly (sub-events appear as `sub_entries` of parent)
2. No orphan events that trigger duplicate combat log callbacks
3. Clear event hierarchy for debugging

**Rule:** Only events with `parent_event=None` trigger the combat log callback. Child events need `parent_event` set.

**Signature differences by method:**

| Method | `parent_event` Type | Pattern |
|--------|---------------------|---------|
| `Entity.add_condition()` | `Event` object | `parent_event=effect_event` or `parent_event=event` |
| `Entity.receive_damage()` | `UUID` | `parent_event=event.uuid` |
| `Entity.receive_healing()` | `UUID` | `parent_event=event.uuid` |
| `Entity.create_saving_throw_request()` | `UUID` | `parent_event=event.uuid` |

### Existing Patterns (1-16)

See `SORCERER_SPELL_ANALYSIS.md` for full documentation of Patterns 1-16:

| Pattern | Name | Canonical Spell | Key Mechanic |
|---------|------|----------------|--------------|
| 1 | Single-Target Attack Spell | Fire Bolt | spell_attack_bonus → d20 → damage |
| 2 | Single-Target Save Spell | Sacred Flame | spell_save_dc → save → damage |
| 3 | AoE Save Spell | Fireball | POSITION_AOE → convolution loop → save per target |
| 4 | Self-Buff Spell | Mage Armor | Apply condition with modifiers on self |
| 5 | Target Buff/Debuff Spell | Hold Person | Apply condition on target, concentration |
| 6 | Granted Action Spell | Call Lightning | Condition registers new action, concentration |
| 7 | Forced Movement Spell | Thunderwave | FORCED_MOVEMENT event (no OA) |
| 8 | Zone Spell | Spirit Guardians | SpatialHandler + ZoneControlCondition |
| 9 | HP-Threshold Spell | Power Word Kill | Check HP → instant effect |
| 10 | Reaction Spell | Shield | Reaction cost, handler on ATTACK at DECLARATION |
| 11 | Melee Spell Attack | Shocking Grasp | RangeType.REACH, melee spell attack bonus |
| 12 | Multi-Beam Spell | Scorching Ray | Loop of attack rolls, one per beam |
| 13 | Light/Obscurement Zone | Darkness | Zone with `light_level_override` on tiles |
| 14 | Invisibility Spell | Invisibility | InvisibilityEffect condition, auto-reveal |
| 15 | Greater Invisibility | Greater Invisibility | Stealth check vs escalating DC |
| 16 | D20 Roll Manipulation | Bless | Handler on D20_ROLL_RESULT to add/subtract dice |

### NEW Pattern 17: Healing Spell ✅ IMPLEMENTED

Uses `Healing` class (analogous to `Damage`) + `entity.receive_healing()` which fires `HealEvent`. Supports upcasting, spellcasting modifier bonus, `healing_blocked` check, combat log.

**Canonical: Cure Wounds** (see `dnd/spells/evocation.py`)

```python
# Healing class in dnd/core/events.py — analogous to Damage
healing = _create_healing(caster, self.cast_at_level, 8, "Cure Wounds")
healing_roll = healing.get_dice().roll  # Dice with RollType.HEAL

actual = target.receive_healing(
    healing_roll.total, caster.uuid,
    source_description=f"Cure Wounds: {healing_roll.total}",
    parent_event=effect_event.uuid,    # UUID!
    spell_level=self.cast_at_level     # For Disciple of Life
)
```

**Key points:**
- `Healing` class creates `Dice(roll_type=RollType.HEAL)` — proper dice system integration
- `_create_healing(caster, num_dice, die_value, name)` helper builds Healing with caster's spellcasting ability mod
- `receive_healing()` takes `event.uuid` (UUID), not Event object
- `spell_level` parameter enables Disciple of Life (+2+spell_level) and Blessed Healer hooks
- `healing_blocked` check is automatic (Chill Touch NoHealing blocks it)
- HP cap is automatic (health.heal() won't exceed max)
- Buff spells (self_or_allies) do NOT use `validate_line_of_sight` — use MageArmor pattern instead (null check + range with self-target guard)

### NEW Pattern 18: Condition Removal ✅ IMPLEMENTED

Directly calls `entity.remove_condition(condition_name)` for each valid condition. No save, no attack roll — just remove conditions.

**Canonical: Lesser Restoration** (see `dnd/spells/abjuration.py`)

```python
_LESSER_RESTORATION_CONDITIONS = {"Blinded", "Deafened", "Paralyzed", "Poisoned"}
_GREATER_RESTORATION_CONDITIONS = {"Charmed", "Poisoned", "Blinded", "Deafened", "Paralyzed", "Stunned", "Frightened"}

# In _apply():
for condition_name in _LESSER_RESTORATION_CONDITIONS:
    if condition_name in target.active_conditions:
        target.remove_condition(condition_name, parent_event=effect_event)
        break
```

**Key points:**
- Uses existing `entity.remove_condition(name, parent_event=event)` — event object, NOT UUID
- Lesser Restoration: `{Blinded, Deafened, Paralyzed, Poisoned}` — removes first found
- Greater Restoration: adds `{Charmed, Stunned, Frightened}` to the set
- Remove Curse pending (needs `is_curse` flag on conditions)

### NEW Pattern 19: Granted Bonus Action Attack (Non-Concentration)

Like Pattern 6 (Granted Action, e.g. Call Lightning) but: uses bonus action cost, is NOT concentration, has its own duration tracking via turn counter.

**Canonical: Spiritual Weapon**

```python
class SpiritualWeaponCondition(BaseCondition):
    name: str = "Spiritual Weapon"
    duration_rounds: int = 10  # 1 minute
    weapon_position: Tuple[int, int] = (0, 0)

    def _apply(self, declaration_event):
        target = Entity.get(self.target_entity_uuid)

        # Register strike action (bonus action, melee spell attack, 1d8+WIS force damage)
        strike = SpiritualWeaponStrike(
            source_entity_uuid=self.target_entity_uuid,
            template=True,
        )
        target.register_action(strike)

        # Register move action (bonus action, move weapon up to 20ft)
        move = SpiritualWeaponMove(
            source_entity_uuid=self.target_entity_uuid,
            template=True,
        )
        target.register_action(move)

        # TURN_START handler to track duration and auto-remove
        # NO Concentrating condition — Spiritual Weapon is NOT concentration

        return [], [turn_handler.uuid], [], [], effect_event

    def cleanup_own_state(self):
        target = Entity.get(self.target_entity_uuid)
        target.unregister_action("Spiritual Weapon Strike")
        target.unregister_action("Spiritual Weapon Move")
```

**Key difference from Pattern 6:** No `Concentrating` condition, no `linked_conditions`. Duration tracked internally with a TURN_START handler that decrements a counter and auto-removes the condition when expired.

---

## Spell Tables by Level

### Difficulty Categories

| Category | Meaning |
|----------|---------|
| **DONE** | Already implemented in the engine |
| **EASY** | Uses existing patterns, < 50 lines of new code |
| **MEDIUM** | New behavior but uses existing infrastructure, 50-150 lines |
| **HARD** | Requires new engine systems or complex interactions |
| **VERY HARD** | Requires major new engine systems (summoning, planes, etc.) |
| **BLOCKED** | Non-combat utility, no meaningful engine implementation |

---

### Cantrips (7)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| Sacred Flame | Evocation | DEX Save | 1d8 radiant, cantrip scaling | **DONE** | Pattern 2 ✓ |
| Guidance | Divination | Touch Buff | +1d4 to one ability check | **DONE** | Pattern 16 on SKILL_D20_ROLL_RESULT, one-use `replace_roll()`, concentration ✓ |
| Resistance | Abjuration | Touch Buff | +1d4 to one saving throw | EASY | Pattern 16 on SAVING_THROW D20_ROLL_RESULT, concentration, one-use |
| Spare the Dying | Necromancy | Touch | Stabilize at 0 HP | HARD | Needs death saves / stabilization system: entities at 0 HP don't die instantly, instead roll death saves. Spare the Dying sets stable flag, skipping death saves. Foundation for the corpse/revival system alongside Revivify. |
| Light | Evocation | Touch | Object sheds bright light 20ft + dim 20ft | **DONE** | `add_light_source(anchor_uuid=target)`, LightEffect condition, concentration ✓ |
| Mending | Transmutation | Touch | Repair single break/tear in object | EASY | BaseItem has health/damage system. Restore HP to damaged item. Touch range. Cantrip (no slot). |
| Thaumaturgy | Transmutation | Sensory | Minor magical effects (sounds, tremors, etc.) | BLOCKED | Utility, no combat effect |

**Summary**: DONE 3, EASY 2, HARD 1, BLOCKED 1

---

### Level 1 Spells (15)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| Bless | Enchantment | Multi-target Buff | +1d4 attacks/saves, 3 targets, conc | **DONE** | Pattern 16 ✓ |
| Bane | Enchantment | Multi-target CHA Save | -1d4 attacks/saves, 3 targets, conc | **DONE** | Pattern 16 ✓ |
| Guiding Bolt | Evocation | Attack + Mark | 4d6 radiant, next attack has advantage | **DONE** | Pattern 1 + mark condition ✓ |
| Cure Wounds | Evocation | Touch Heal | 1d8+WIS HP, upcasts +1d8/level | **DONE** | Pattern 17: Healing class + Dice(RollType.HEAL), touch, upcasts via cast_at_level ✓ |
| Healing Word | Evocation | Ranged Heal | Bonus action, 60ft, 1d4+WIS, upcasts +1d4 | **DONE** | Pattern 17, bonus action cost, 60ft range ✓ |
| Inflict Wounds | Necromancy | Melee Spell Attack | 3d10 necrotic, upcasts +1d10/level | EASY | Pattern 11: melee spell attack (RangeType.REACH), high single-target damage |
| Shield of Faith | Abjuration | Buff | +2 AC, bonus action, concentration | EASY | Pattern 5: NumericalModifier(+2) on equipment.ac_bonus.self_static, bonus action cost, concentration |
| Command | Enchantment | WIS Save | One-word: Grovel=prone, Flee=dash away, Drop=drop held, Halt=skip action | **DONE** | WIS save, 3 command words (Grovel/Halt/Flee), upcasts +1 target ✓ |
| Sanctuary | Abjuration | Ward | WIS save to target warded creature, breaks on attack/harmful spell | MEDIUM | Handler on ATTACK at EXECUTION: force WIS save, cancel attack on fail. Handler on ATTACK/CAST_SPELL at EFFECT: self-break check when warded creature acts offensively |
| Protection from Evil and Good | Abjuration | Buff | Specific creature types have disadvantage on attacks, can't charm/frighten/possess | MEDIUM | ContextualAdvantageModifier checking attacker.creature_type (aberration/celestial/elemental/fey/fiend/undead), concentration |
| Create or Destroy Water | Transmutation | Terrain + Condition | Create Water: 4m radius AoE, applies **Wet** condition (Vulnerability to Cold + Lightning). Destroy Water: remove water/wet from area. Upcasts: +2m radius per level. | MEDIUM | New **Wet** tile condition: `ResistanceModifier(VULNERABILITY, "cold")` + `ResistanceModifier(VULNERABILITY, "lightning")` on entities in zone. Create variant: POSITION_AOE, apply Wet to tiles + entities. Destroy variant: remove Water tiles / Wet conditions. Enables spell combos (Cold→Ice→difficult terrain+prone, Lightning→Shocked). |
| Detect Evil and Good | Divination | Sense | Know location + type of aberration/celestial/elemental/fey/fiend/undead within 30ft, bypasses stealth/invisibility for these types. Concentration. | EASY | Query `senses.entities` within 30ft, filter by `creature_type` matching set. Reveals Hidden/Invisible creatures of matching types. Uses existing `CreatureType` enum + stealth system. |
| Detect Magic | Divination | Sense | Sense presence of magic within 30ft, see aura around magical creatures/objects/effects. Concentration. | EASY | Iterate entities/tiles/objects within 30ft, check for `active_conditions` (spell-based conditions have source). Reveals magical traps (bypasses `condition_stealth_dc`). Uses existing condition + hazard systems. |
| Detect Poison and Disease | Divination | Sense | Sense presence + location of poison/disease/poisonous creatures within 30ft. Concentration. | EASY | Query entities within 30ft for `Poisoned` condition or `creature_type` with poison traits. Check tiles/objects for poison-type conditions. Uses existing condition system. |
| Purify Food and Drink | Transmutation | Utility | Purify food/water in 5ft radius, remove poison/disease | BLOCKED | No food/drink item system |

**Summary**: DONE 6, EASY 5, MEDIUM 3, BLOCKED 1

---

### Level 2 Spells (17)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| Hold Person | Enchantment | WIS Save | Paralyzed, humanoid, concentration, repeat save | **DONE** | Pattern 5 ✓ |
| Blindness/Deafness | Necromancy | CON Save | Blinded or Deafened, NOT concentration | **DONE** | Condition application ✓ |
| Aid | Abjuration | Multi-target Buff | +5 max HP to 3 targets, 8 hours, not concentration | EASY | NumericalModifier(+5) on health.max_hit_points_bonus.self_static, MULTI_ENTITY(3), upcasts +5/level. Condition with no concentration. |
| Lesser Restoration | Abjuration | Condition Removal | End one: blinded/deafened/paralyzed/poisoned | **DONE** | Pattern 18: iterates removable set, removes first found ✓ |
| Enhance Ability | Transmutation | Buff | Advantage on chosen ability's checks, concentration | EASY | AdvantageModifier on chosen ability check ModifiableValue, concentration. 6 options (Bull's STR, Cat's DEX, etc.) |
| Prayer of Healing | Evocation | Multi-target Heal | 10-min cast, 6 targets, 2d8+WIS | **DONE** | Pattern 17, MULTI_ENTITY(6), upcasts +1d8/level ✓ |
| Protection from Poison | Abjuration | Buff | Poison resistance + advantage on poison saves | EASY | ResistanceModifier(poison) on health.damage_reduction + AdvantageModifier on CON saves vs poison |
| Spiritual Weapon | Evocation | Granted Action | Bonus action summon, 1d8+WIS force, move+attack each turn | MEDIUM | **Pattern 19**: granted bonus action attack, NOT concentration, 1min duration, upcasts +1d8 per 2 levels above 2nd |
| Silence | Illusion | Zone | 20ft sphere, no sound, blocks verbal spells | **DONE** | Pattern 8 zone, blocks verbal spells, deafens in zone ✓ |
| Warding Bond | Abjuration | Buff + Link | +1 AC, +1 saves, resistance to all damage, damage mirroring | MEDIUM | Buff condition on target (NumericalModifier +1 AC, +1 saves, ResistanceModifier ALL) + handler on TAKE_DAMAGE at EFFECT: mirror damage to caster. Ends at 60ft separation. |
| Calm Emotions | Enchantment | AoE Debuff | 20ft sphere, CHA save, suppress charmed/frightened | MEDIUM | Pattern 3 AoE + temporary condition suppression (not removal — suppressed for duration) |
| Zone of Truth | Enchantment | Zone | 15ft sphere, CHA save, can't deliberately lie | BLOCKED | Social mechanic, no combat effect |
| Continual Flame | Evocation | Light | Permanent flame on object, bright 20ft + dim 20ft | **DONE** | ContinualFlameObject(BaseBlock) with persistent light source ✓ |
| Find Traps | Divination | Sense | Sense presence of traps within 120ft (general direction, not exact location) | EASY | Iterate tiles within 120ft, check `tile.is_hazardous()`/`condition_stealth_dc` — reveal traps regardless of stealth DC. Uses existing hazard system (`HazardFilter`, `condition_stealth_dc`). |
| Gentle Repose | Necromancy | Buff | Preserve corpse: extends Revivify/Raise Dead timer, prevents undead rising. Touch. | EASY | Condition on dead entity that pauses death timer. Prerequisite for revival system. Blocks Animate Dead on target. |
| Augury | Divination | Utility | Omen about future action | BLOCKED | No combat effect |
| Locate Object | Divination | Sense | Sense direction to nearest object of a kind, or specific known object, within 1000ft. Concentration. | EASY | Query `GridMap._object_positions` for matching object by name/type, return direction vector. Same pattern as Locate Creature but for objects. |

**Summary**: DONE 6, EASY 6, MEDIUM 3, BLOCKED 2

---

### Level 3 Spells (19)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| Spirit Guardians | Conjuration | Zone | 15ft sphere follows caster, 3d8 radiant/necrotic WIS save | **DONE** | Pattern 8 zone, follows caster ✓ |
| Daylight | Evocation | Light Zone | 60ft bright light sphere | **DONE** | Pattern 13 light zone ✓ |
| Protection from Energy | Abjuration | Buff | Resistance to acid/cold/fire/lightning/thunder, concentration | **DONE** | Resistance buff ✓ |
| Mass Healing Word | Evocation | Multi-target Heal | Bonus action, 6 targets, 1d4+WIS, 60ft | **DONE** | Pattern 17 + MULTI_ENTITY(6), bonus action, 60ft ✓ |
| Beacon of Hope | Abjuration | Multi-target Buff | Adv on WIS saves + death saves, max healing dice, concentration | EASY | AdvantageModifier on WIS saves + handler on HEAL at EXECUTION to replace healing rolls with max value. Concentration. |
| Remove Curse | Abjuration | Condition Removal | End one curse on creature/object | EASY | Pattern 18: remove_condition by name for curse-type conditions. Touch range. |
| Dispel Magic | Abjuration | Spell Removal | End spell effects ≤3rd auto, ability check for higher | MEDIUM | Remove spell-based conditions by level. Auto-dispel up to cast level. For higher: DC = 10 + spell level, spellcasting ability check. |
| Bestow Curse | Necromancy | WIS Save | Choose curse: disadv on ability, disadv on attacks vs caster, WIS save to take action, extra 1d8 necrotic on hit | MEDIUM | WIS save, 4 curse options each requiring different condition implementation, concentration at L3 but NOT at L5+ |
| Revivify | Necromancy | Touch | Dead <1 min, return with 1 HP, 300gp diamond material cost | HARD | Needs corpse/revival system: death timestamp tracking, corpse entity state, Entity.revive() method. Material cost tracking. Foundation for all resurrection spells. |
| Animate Dead | Necromancy | Summon | Create skeleton/zombie from corpse, obeys commands, lasts 24hrs, reassert control or it goes hostile | HARD | Use existing `create_skeleton()` from bestiary, set `faction` to match caster. Needs: control duration tracking, hostility on expiration. Upcasts: +2 undead per level above 3rd. |
| Clairvoyance | Divination | Sense | Create invisible sensor at a known point within 1 mile, choose sight or hearing. Concentration, 10 min. | MEDIUM | Create invisible sensor entity (no HP, no actions) at position. Grant caster FOV from sensor's position (second `compute_fov()` call). Uses existing senses/FOV system. |
| Create Food and Water | Conjuration | Item Creation | Create food and water items on the ground. 45 lbs food, 30 gal water. | EASY | Spawn UsableItem (food/waterskin) via `GridMap.place_object()` at caster's position. Consumable items with `is_consumable=True`. Uses existing item + object placement system. |
| Glyph of Warding | Abjuration | Trap | Inscribe glyph on surface, triggers when creature enters (explosive runes: 5d8 chosen type DEX save, or spell glyph: stores spell ≤3rd). Instant cast for combat. | MEDIUM | SpatialHandler at position with `condition_stealth_dc` for hidden trap. Trigger on SPATIAL_ENTITY_ENTERED → DEX save for explosive runes OR release stored spell. Uses existing hazard system. Upcasts: +1d8/level for runes, stores higher spells. |
| Magic Circle | Abjuration | Zone | 10ft radius circle, chosen creature types can't willingly enter/leave, disadvantage on attacks through, immune to charm/frighten/possess from inside. Instant cast for combat. | MEDIUM | Pattern 8 zone (SpatialHandler). Handler on MOVEMENT at EXECUTION: cancel if creature_type matches and crossing boundary. ContextualAdvantageModifier on attacks through circle. Uses existing `CreatureType` enum filtering. 1 hour, not concentration. |
| Meld into Stone | Transmutation | Stealth | Step into stone wall/surface, become hidden and unperceivable, 8 hours or until you leave | EASY | Condition sets `is_invisible` + high `stealth_dc` (or unperceivable). Requires adjacency to Wall tile. Uses existing Hidden/stealth system. Concentration. Damage to stone forces CON save or ejection. |
| Sending | Evocation | Communication | 25-word message, unlimited range | BLOCKED | Communication utility |
| Speak with Dead | Necromancy | Utility | Question corpse | BLOCKED | No combat effect |
| Tongues | Divination | Utility | Understand/speak all languages | BLOCKED | No combat effect |
| Water Walk | Transmutation | Movement Buff | Walk on liquid surfaces (water, mud, lava), 10 targets, 1 hour, not concentration | EASY | Condition modifies `is_walkable_for()` — Water tiles become walkable for affected entity. MULTI_ENTITY(10). Uses existing tile type system (Water tiles block movement by default). |

**Summary**: DONE 4, EASY 5, MEDIUM 6, HARD 1, BLOCKED 3

---

### Level 4 Spells (8)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| Death Ward | Abjuration | Anti-death Buff | First time HP would drop to 0 → 1 HP instead, one-use, 8 hours | EASY | Handler on TAKE_DAMAGE at EFFECT: if final_damage would kill, reduce to leave 1 HP. One-use: remove condition after trigger. |
| Freedom of Movement | Abjuration | Buff | Ignore difficult terrain, immune to grapple/restrained, escape nonmagical restraints, 1 hour | EASY | Max constraint removal on movement (ignore difficult terrain cost modifier) + immunity to Grappled/Restrained conditions |
| Banishment | Abjuration | CHA Save | Remove from plane, return on concentration end | MEDIUM | CHA save, remove entity from gridmap (store position), restore on condition cleanup. Concentration. If native to plane, returns on end. |
| Guardian of Faith | Conjuration | Stationary Zone | 10ft radius, DEX save 20 radiant, vanishes at 60 total damage dealt, 8 hours | **DONE** | BaseItem object + SpatialHandler aura, damage budget, GuardianWarded one-per-turn ✓ |
| Control Water | Transmutation | Terrain Manipulation | Move/reshape water tiles in 100ft cube. Flood: raise water 20ft. Part Water: create path through water. Redirect Flow: move water to new location. Whirlpool: 5ft deep, STR save or 2d8 bludg | MEDIUM | Move Water tiles to new positions via GridMap, or temporarily convert Water→Floor (Part Water). Whirlpool option: zone with STR save damage. Concentration. Uses existing tile type system. |
| Divination | Divination | Utility | Receive omen from deity about future action | BLOCKED | GM adjudication, no AI/dialogue system |
| Locate Creature | Divination | Sense | Know direction to nearest creature of a kind, or specific known creature, within 1000ft. Concentration, 1 hour. | EASY | Query `Entity._entity_registry` for matching creature by name/type, return direction vector from caster position. Bypasses LOS/stealth. Blocked by running water/polymorph. |
| Stone Shape | Transmutation | Terrain Manipulation | Reshape 5ft cube of stone — create passage through Wall, seal opening, create crude object | EASY | Convert Wall tile ↔ Floor tile at target position. Touch range. Instant. Uses existing tile type system in GridMap. |

**Summary**: DONE 1, EASY 4, MEDIUM 2, BLOCKED 1

---

### Level 5 Spells (13)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| Insect Plague | Conjuration | Zone | 20ft sphere, CON save, 4d10 piercing, concentration | **DONE** | Pattern 8 zone ✓ |
| Flame Strike | Evocation | Cylinder AoE | 10ft radius 40ft high, 4d6 fire + 4d6 radiant, DEX save | **DONE** | Pattern 3 cylinder AoE, dual damage types, upcasts +1d6 fire ✓ |
| Mass Cure Wounds | Evocation | AoE Heal | 30ft sphere, up to 6 targets, 3d8+WIS, 60ft range | **DONE** | Pattern 17 + POSITION_AOE(Sphere 30ft), self_or_allies filter ✓ |
| Greater Restoration | Abjuration | Condition Removal | End: charmed, poisoned, blinded, deafened, paralyzed, stunned, frightened | **DONE** | Pattern 18: broader condition set than Lesser Restoration ✓ |
| Contagion | Necromancy | Melee Spell Attack | Melee spell attack, disease: 6 options with different ability disadvantages | MEDIUM | Pattern 11 melee spell attack + disease condition with 3-save system (3 cumulative fails = permanent for 7 days, 3 cumulative saves = cured). 6 disease options each targeting different ability saves. |
| Dispel Evil and Good | Abjuration | Buff + Action | Protection aura (disadvantage for aberrations/celestials/elementals/fey/fiends/undead attacking you) + two granted actions (Break Enchantment, Dismissal) | MEDIUM | Buff condition (ContextualAdvantageModifier) + Pattern 6 granted actions. Concentration. Break Enchantment = remove charmed/frightened/possessed. Dismissal = melee CHA save or banish. |
| Raise Dead | Necromancy | Resurrection | Dead ≤10 days, returns 1 HP, -4 penalty on d20s (removed by long rests) | HARD | Death/revival system needed. Long-term debuff condition (-4 to attacks/saves/checks, reduced by 1 per long rest). 500gp diamond material cost. |
| Commune | Divination | Ritual | 3 yes/no questions to deity | BLOCKED | GM adjudication |
| Geas | Enchantment | Control + Damage | Magical command, 5d10 psychic damage once per day when acting against command. WIS save. 30 days. | MEDIUM | WIS save, apply condition. Handler on BASE_ACTION at EFFECT: if action violates command → `receive_damage(5d10, psychic)`. Simplified: flag certain action categories as forbidden. Upcasts extend duration. |
| Hallow | Evocation | Utility | 24hr cast, consecrate 60ft radius | BLOCKED | Utility (24hr cast) |
| Legend Lore | Divination | Utility | Learn about person/place/thing | BLOCKED | Utility |
| Planar Binding | Abjuration | Control | Bind celestial/elemental/fey/fiend to service, CHA save, 24 hours. Instant cast for combat. | HARD | CHA save or creature serves caster (set faction). Duration tracking. Upcasts extend duration (L6=10 days, L7=30, L8=180, L9=year+day). |
| Scrying | Divination | Sense | Remote viewing: WIS save (modified by familiarity), see target + 10ft radius. Concentration, 10 min. | MEDIUM | Like Clairvoyance but targets a creature (WIS save to resist). On fail: grant caster FOV at target's position. Uses existing senses/FOV system. Save modifiers based on familiarity level. |

**Summary**: DONE 4, EASY 0, MEDIUM 4, HARD 3, BLOCKED 2

---

### Level 6 Spells (10)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| True Seeing | Divination | Buff | Truesight 120ft, 1 hour | **DONE** | Truesight sense mode ✓ |
| Heal | Evocation | Mega Heal | 70 HP + end blindness/deafness, 60ft range | **DONE** | Pattern 17 (flat 70 HP) + Pattern 18 (remove blinded/deafened), upcasts +10/level ✓ |
| Harm | Necromancy | CON Save | 14d6 necrotic (half on save), can't reduce below 1 HP, 60ft | EASY | Pattern 2: single-target CON save, high damage. Special: min 1 HP remaining (cap final_damage). 60ft range. |
| Blade Barrier | Evocation | Wall Zone | 100ft long × 20ft high × 5ft thick wall of blades, 6d10 slashing, DEX save, concentration | MEDIUM | Pattern 8 wall zone: linear positions along a line, damage on crossing (SPATIAL_ENTITY_ENTERED) or starting turn in zone. DEX save for half. Concentration. |
| Create Undead | Necromancy | Summon | Create up to 3 ghouls from corpses, obeys commands, reassert daily or goes hostile | HARD | Same as Animate Dead but creates ghouls (need ghoul factory in bestiary). Upcasts: mummies at L8, wights at L9. Night-only casting. |
| Find the Path | Divination | Navigation | Know shortest path to a fixed destination, can't be lost. Concentration, 1 day. | EASY | We literally have Dijkstra pathfinding. `compute_paths()` from caster to destination, highlight optimal path. Concentration. |
| Forbiddance | Abjuration | Zone + Damage | Ward area (up to 40000 sqft): chosen creature types take 5d10 radiant/necrotic on entering. Blocks teleportation into area. Not concentration. | MEDIUM | Pattern 8 zone with SpatialHandler on SPATIAL_ENTITY_ENTERED: check `creature_type`, deal 5d10 damage. Handler on MOVEMENT at EXECUTION: cancel teleportation moves into zone. Instant cast for combat. |
| Heroes' Feast | Conjuration | Multi-target Buff | Feast for up to 13 creatures: cure disease/poison, immune to poison/frightened, adv on WIS saves, +2d10 max HP, 24 hours. Instant cast for combat. | EASY | Remove Poisoned/Frightened conditions (Pattern 18) + condition with: ResistanceModifier(IMMUNITY, poison), immunity to Frightened, AdvantageModifier on WIS saves, NumericalModifier(+2d10 rolled once) on health.max_hit_points_bonus. MULTI_ENTITY(13). 1000gp bowl material cost. |
| Planar Ally | Conjuration | Summon | Summon celestial/elemental/fiend, negotiates service | HARD | Create entity via bestiary factory, set faction. Needs: negotiation mechanic (simplified: just summon with duration). |
| Word of Recall | Conjuration | Teleport | Teleport caster + up to 5 willing creatures to a pre-designated sanctuary | EASY | `GridMap.move_entity()` to sanctuary position for each target. Pre-designated position stored on condition/entity. Same as Misty Step pattern but multi-target + fixed destination. |

**Summary**: DONE 2, EASY 4, MEDIUM 2, HARD 2

---

### Level 7 Spells (8)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| Fire Storm | Evocation | Multi-cube AoE | 10 × 10ft cubes, 7d10 fire, DEX save | **DONE** | Multi-position AoE ✓ |
| Regenerate | Transmutation | Heal + Regen | 4d8+15 instant heal + 1 HP per round for 10 rounds | **DONE** | Pattern 17 + RegeneratingEffect condition with TURN_START handler, self-removes after 10 rounds ✓ |
| Divine Word | Evocation | HP-threshold | Bonus action, 30ft, no save for HP effects. Effects by current HP: ≤20=death, ≤30=blind+deaf+stun 1hr, ≤40=deaf+blind 10min, ≤50=deaf 1min. Extraplanar auto-banished. | MEDIUM | HP-check table (like Pattern 9 Power Word Kill/Stun), but with 4 tiers. Bonus action cost. 30ft range. Extraplanar creatures: forced to return to home plane if they fail. |
| Resurrection | Necromancy | Resurrection | Dead ≤100 years, 1hr cast, full HP, -4 penalty on d20s | HARD | Death/revival system needed. Same -4 penalty debuff as Raise Dead. 1000gp diamond material cost. |
| Conjure Celestial | Conjuration | Summon | Summon celestial CR ≤4, obeys commands, concentration 1hr | HARD | Create celestial entity via bestiary factory (need celestial factory), set faction to caster's. Concentration. Upcasts: CR ≤5 at L8, CR ≤6 at L9. |
| Etherealness | Transmutation | Plane | Enter Border Ethereal, 8 hours | VERY HARD | Plane mechanics system |
| Plane Shift | Conjuration | Teleport/Banish | Teleport up to 9 to other plane, OR melee CHA save to banish unwilling target | VERY HARD | Plane mechanics + melee save-or-banish mode |
| Symbol | Abjuration | Trap | 1min cast, inscribe glyph, 8 effect types (death/discord/fear/hopelessness/insanity/pain/sleep/stunning) | VERY HARD | Trap system + 8 distinct effect implementations |

**Summary**: DONE 2, EASY 0, MEDIUM 1, HARD 2, VERY HARD 3

---

### Level 8 Spells (4)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| Holy Aura | Abjuration | AoE Buff | 30ft self-aura: advantage on all saves for allies, fiend/undead blinded on melee hit, concentration | MEDIUM | Self-zone condition (ContextualAdvantageModifier on saves for allies within 30ft). Handler on ATTACK at EFFECT: if attacker is fiend/undead AND melee → CON save or Blinded. Concentration. |
| Earthquake | Evocation | Massive AoE | 100ft radius, DEX save → prone, concentration, fissures + structure collapse | HARD | Massive AoE (100ft radius) + DEX save for prone + terrain destruction (fissures open, structures collapse). Ongoing concentration effects each round. |
| Antimagic Field | Abjuration | Zone | 10ft sphere on self, suppresses ALL magic, follows caster, concentration | VERY HARD | Requires magic suppression system — suppress all spell conditions, magic item properties, and spellcasting within zone. Major engine system. |
| Control Weather | Transmutation | Utility | Control weather 5-mile radius, concentration 8 hours | BLOCKED | No combat effect |

**Summary**: MEDIUM 1, HARD 1, VERY HARD 1, BLOCKED 1

---

### Level 9 Spells (4)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| Mass Heal | Evocation | Mega Multi-heal | Distribute up to 700 HP among creatures within 60ft, remove blindness/deafness | **DONE** | Pattern 17 pool distribution (700 HP) + Pattern 18 condition removal ✓ |
| True Resurrection | Necromancy | Resurrection | Dead ≤200 years, even from dust, new body if needed, full HP, 1hr cast | HARD | Death/revival system needed. Most powerful resurrection — no penalties. 25000gp material cost. |
| Gate | Conjuration | Portal | Interplanar portal 5-20ft, or summon specific named creature | VERY HARD | Plane mechanics + summoning |
| Astral Projection | Necromancy | Plane | Project to Astral Plane, up to 9 creatures, silver cord | VERY HARD | Plane mechanics system |

**Summary**: DONE 1, HARD 1, VERY HARD 2

---

## Overall Difficulty Summary

| Difficulty | Count | Percentage |
|------------|-------|------------|
| **DONE** | 29 | 28% |
| **EASY** | 28 | 27% |
| **MEDIUM** | 22 | 21% |
| **HARD** | 11 | 10% |
| **VERY HARD** | 6 | 6% |
| **BLOCKED** | 9 | 9% |
| **Total** | **105** | **100%** |

**Combat-relevant**: 96 spells (DONE through VERY HARD)
**Implementable with existing + new patterns**: 79 spells (DONE + EASY + MEDIUM) = 82% of combat-relevant
**Progress**: 29 of 96 combat-relevant implemented (30%)

---

## Systems Status

| System | Status | Spells Enabled |
|--------|--------|----------------|
| **Healing Events** | ✅ COMPLETE | `receive_healing()`, `HealEvent`, `HealLogData` all exist. Needs `spell_level` field enhancement. |
| **AoE Shapes** | ✅ COMPLETE | Flame Strike (cylinder), Mass Cure Wounds (sphere), Fire Storm (multi-cube) |
| **Concentration** | ✅ COMPLETE | Shield of Faith, Hold Person, Spirit Guardians, Silence, Blade Barrier, etc. |
| **Multi-Entity Targeting** | ✅ COMPLETE | Bless, Bane, Mass Healing Word, Aid, Mass Cure Wounds |
| **Zone Spells** | ✅ COMPLETE | Spirit Guardians, Insect Plague, Silence, Blade Barrier |
| **Condition Application** | ✅ COMPLETE | Blindness/Deafness, Hold Person, Command, Turned |
| **D20 Roll Manipulation** | ✅ COMPLETE | Bless (+1d4), Bane (-1d4), Guidance (+1d4), Resistance (+1d4) |
| **Light Level Zones** | ✅ COMPLETE | Daylight |
| **Creature Type Filtering** | ✅ COMPLETE | `CreatureType.UNDEAD` exists, `entity.creature_type` field — Turn Undead, Protection from Evil and Good |
| **Healing Modifier Hooks** | ✅ COMPLETE | `spell_level` field on `HealEvent` + `receive_healing()`, `RollType.HEAL` on dice, `Healing` class in events.py |
| **Condition Removal Spells** | ✅ COMPLETE | Lesser Restoration, Greater Restoration implemented (Pattern 18). Remove Curse pending (no curse system). |
| **Granted Bonus Actions** | ❌ NOT STARTED | Spiritual Weapon (Pattern 19 — non-concentration granted action) |
| **Spell Preparation** | ❌ NOT STARTED | `SpellPreparationFeature` condition for prepared casters |
| **Wet/Ice Terrain** | ❌ NOT STARTED | Create/Destroy Water Wet condition (Cold/Lightning vulnerability), Ice surfaces, spell combos |
| **Death/Revival** | ❌ NOT STARTED | Revivify, Raise Dead, Resurrection — needs corpse entity state, death timestamp, Entity.revive() |
| **Summoning** | ⚠️ NEEDS FACTORY PATTERN | Animate Dead (`create_skeleton()` exists), Create Undead (need ghoul factory), Conjure Celestial (need celestial factory). Core pattern: bestiary factory + set faction to caster's. Needs: control duration, hostility on expiration. |
| **Magic Suppression** | ❌ NOT STARTED | Antimagic Field — suppress all magic in zone |

---

## Implementation Priority Batches

### Batch A — Core Healing (Pattern 17) ✅ COMPLETE

**All 8 spells implemented.** `Healing` class in `events.py`, `RollType.HEAL` in dice system, `spell_level` on `HealEvent`.

| Spell | Level | Status | Notes |
|-------|-------|--------|-------|
| Cure Wounds | 1 | **DONE** | Canonical Pattern 17, touch, d8+WIS |
| Healing Word | 1 | **DONE** | Bonus action, 60ft, d4+WIS |
| Prayer of Healing | 2 | **DONE** | 6 targets, d8+WIS |
| Mass Healing Word | 3 | **DONE** | Bonus action, 6 targets, d4+WIS |
| Mass Cure Wounds | 5 | **DONE** | 30ft sphere AoE, 6 targets, d8+WIS |
| Heal | 6 | **DONE** | Flat 70 HP + condition removal |
| Regenerate | 7 | **DONE** | 4d8+15 + 1 HP/round regen |
| Mass Heal | 9 | **DONE** | 700 HP pool distribution |

Tests: `examples/test_healing_spells.py` (61 assertions).

### Batch B — Cleric Buffs

**Mostly EASY, uses existing patterns (4, 5, 16).**

| Spell | Level | Difficulty | Pattern |
|-------|-------|------------|---------|
| Shield of Faith | 1 | EASY | Pattern 5 (+2 AC buff) |
| Aid | 2 | EASY | +5 max HP, multi-target |
| Death Ward | 4 | EASY | Anti-death TAKE_DAMAGE handler |
| Freedom of Movement | 4 | EASY | Movement immunity buff |
| Beacon of Hope | 3 | EASY | Adv WIS saves + max healing |
| Protection from Poison | 2 | EASY | Resistance + save advantage |
| Enhance Ability | 2 | EASY | Ability check advantage |

### Batch C — Condition Management (Pattern 18) ✅ MOSTLY COMPLETE

**2 of 3 spells implemented.** Remove Curse pending (no curse system yet).

| Spell | Level | Status | Notes |
|-------|-------|--------|-------|
| Lesser Restoration | 2 | **DONE** | Removes blinded/deafened/paralyzed/poisoned |
| Greater Restoration | 5 | **DONE** | Removes charmed/poisoned/blinded/deafened/paralyzed/stunned/frightened |
| Remove Curse | 3 | EASY | Needs `is_curse` flag on conditions |

Tests: included in `examples/test_healing_spells.py`.

### Batch D — Cleric Damage/Control

**Uses existing patterns.**

| Spell | Level | Difficulty | Pattern |
|-------|-------|------------|---------|
| ~~Flame Strike~~ | 5 | **DONE** | ~~Pattern 3 (cylinder AoE, dual damage)~~ ✓ |
| ~~Command~~ | 1 | **DONE** | ~~WIS save, multiple behavior effects~~ ✓ |
| Inflict Wounds | 1 | EASY | Pattern 11 (melee spell attack) |
| Harm | 6 | EASY | Pattern 2 (CON save, high damage) |
| Spiritual Weapon | 2 | MEDIUM | Pattern 19 (granted bonus action) |

### Batch E — Zone/Advanced

**MEDIUM difficulty, more complex implementations.**

| Spell | Level | Difficulty | Notes |
|-------|-------|------------|-------|
| ~~Silence~~ | 2 | **DONE** | ~~Zone that blocks verbal spells~~ ✓ |
| ~~Guardian of Faith~~ | 4 | **DONE** | ~~Stationary zone with damage budget~~ ✓ |
| Warding Bond | 2 | MEDIUM | Buff + damage mirroring link |
| Blade Barrier | 6 | MEDIUM | Wall zone, crossing damage |
| Banishment | 4 | MEDIUM | CHA save, remove from play |
| Holy Aura | 8 | MEDIUM | Self-aura, save advantage, counter-attack |
| Divine Word | 7 | MEDIUM | HP-threshold multi-tier effects |

---

## Progress & Conclusion

With existing systems (AoE, concentration, zones, d20 manipulation, healing events), the Cleric spell list is **81% implementable** using existing + 3 new patterns. The main new patterns needed:

- **Pattern 17 (Healing)**: Uses existing `receive_healing()` / `HealEvent` — just needs `spell_level` field enhancement
- **Pattern 18 (Condition Removal)**: Simple `entity.remove_condition()` calls — minimal new code
- **Pattern 19 (Granted Bonus Action)**: Variant of existing Pattern 6 (Call Lightning) — non-concentration, bonus action cost

**19 of 96 combat-relevant spells implemented (20%)**
**79 of 96 implementable with current + new patterns (82%)**

---

## Batch 1 Implementation Notes (February 2026)

**Spells completed**: Flame Strike, Guidance, Light, Continual Flame, Command, Silence, Guardian of Faith — 79 integration tests, all passing.

### Difficulty Assessment vs Reality

| Spell | Estimated | Actual | Notes |
|-------|-----------|--------|-------|
| Flame Strike | EASY | EASY | Clean IceStorm clone, ~30 lines |
| Guidance | EASY | EASY | `replace_roll()` pattern, one-use handler removal. Key: handler fires on `SKILL_D20_ROLL_RESULT`, NOT `D20_ROLL_RESULT` |
| Light | EASY | MEDIUM | Light source anchoring works but needs `update_entity_senses()` after cast to refresh paths. Dark-arena testing is non-trivial. |
| Continual Flame | EASY | MEDIUM | Persistent object + light source. Gotcha: Pydantic v2 treats `_`-prefixed fields as private attrs — use regular field names. |
| Command | MEDIUM | MEDIUM | Three sub-conditions (Grovel/Halt/Flee), each different. Grovel=Prone sub-condition. Halt=Incapacitated sub-condition. Flee=TURN_START handler for forced movement. |
| Silence | MEDIUM | MEDIUM | Zone + `verbal` field on SpellAction/SpellEvent. Handler checks `isinstance(event, SpellEvent) and event.verbal` to block. Added `verbal: bool = True` to both SpellAction and SpellEvent in actions.py. |
| Guardian of Faith | MEDIUM | HARD | Most complex. BaseItem object with SpatialHandler aura, damage budget tracking, GuardianWarded one-per-turn marker condition, faction-based hostile check. Multiple registries involved. |

### Gotchas for Future Batches

1. **No `_`-prefixed fields on Pydantic models**: Pydantic v2 treats `_`-prefixed fields as `ModelPrivateAttr()` which silently fail. Just use regular field names — there's no reason to use private attrs in this codebase.

2. **BaseObject vs BaseBlock registries**: `BaseObject._registry` and `BaseBlock._registry` are separate. Objects inheriting from BaseBlock only register in `BaseBlock._registry`. Use `BaseBlock.get(uuid)` for BaseBlock subclasses, not `BaseObject.get(uuid)`.

3. **Light spell path refresh**: After casting a light spell that illuminates dark tiles, `senses.paths` is NOT automatically refreshed (paths are lazy — only recomputed at turn start or movement end). Must call `entity.update_entity_senses()` after the spell before the entity can Move to newly-visible positions.

4. **`roll_d20()` returns effective roll**: `entity.roll_d20()` returns `event.get_effective_roll()` which already includes handler modifications (e.g., Guidance +1d4 via `replace_roll()`). The raw d20 is in `roll.results[0]`, base bonus in `roll.bonus`.

5. **Testing light spells**: Use dark arena pattern: set all `tile.default_light = LightLevel.DARKNESS`, then verify `tile.resolved_light_level == LightLevel.BRIGHT_LIGHT` at expected positions. Always use Move action (not `grid.move_entity()`) for entity movement in tests.

6. **`verbal` field**: Added to both `SpellAction` and `SpellEvent` in `dnd/actions.py`. Default `True`. Silence zone handler checks this on `CAST_SPELL` events at EXECUTION phase.
