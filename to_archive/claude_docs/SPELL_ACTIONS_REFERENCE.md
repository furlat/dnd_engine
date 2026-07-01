# Spell Actions Reference

Complete catalog of all spell actions in the engine, organized by level and school. Includes file locations, SRD descriptions, targeting, concentration, and full hierarchical event chains.

---

## Master Conditional Event Chain Diagrams

### Spell Attack (Hit/Miss/Crit)

```
SpellEvent(DECLARATION) → validate range + LOS
 └─ SpellEvent(EXECUTION)
     └─ Roll d20 + spell_attack_bonus vs target AC
         │
         ├─ MISS (d20 < AC):
         │   └─ SpellEvent(EFFECT) → no damage
         │       └─ SpellEvent(COMPLETION) → combat log "miss"
         │
         ├─ CRIT_MISS (natural 1):
         │   └─ SpellEvent(EFFECT) → SpellEvent(COMPLETION)
         │
         ├─ HIT (d20 ≥ AC):
         │   └─ Roll damage dice + spell_damage_bonus
         │       └─ target.receive_damage()
         │           └─ TakeDamageEvent → [see Attack damage chain in ACTIONS_REFERENCE.md]
         │       └─ SpellEvent(COMPLETION)
         │
         └─ CRIT (natural 20):
             └─ Roll damage dice (doubled) + spell_damage_bonus
                 └─ target.receive_damage() → TakeDamageEvent chain
                 └─ SpellEvent(COMPLETION)
```

### Spell Save (Success/Fail + Damage/Condition)

```
SpellEvent(EXECUTION)
 └─ Per target (convolution for AoE/multi-target):
     └─ SavingThrowEvent(ability) vs spell_save_dc
         │
         ├─ SUCCESS (roll ≥ DC):
         │   ├─ [damage spell] → half damage (Fireball, Lightning Bolt, etc.)
         │   │   └─ TakeDamageEvent(total / 2)
         │   ├─ [condition spell] → no effect (Hold Person, Fear, etc.)
         │   └─ [some spells] → no damage at all (Sacred Flame)
         │
         └─ FAIL (roll < DC):
             ├─ [damage spell] → full damage
             │   └─ TakeDamageEvent(total)
             │       └─ Death check, concentration check, etc.
             ├─ [condition spell] → condition applied
             │   └─ ConditionApplicationEvent → spell effect condition
             │       ├─ May include sub-conditions (Hold Person → Paralyzed → Incapacitated)
             │       └─ May register repeat save handler (turn end)
             │           └─ Each turn: SavingThrowEvent
             │               ├─ SUCCESS → CONDITION_REMOVAL → reverse link check
             │               └─ FAIL → condition persists
             └─ [damage + condition] → full damage + condition
                 ├─ TakeDamageEvent
                 └─ ConditionApplicationEvent
```

### Concentration Spell Setup (Full Tree)

```
SpellEvent(EXECUTION)
 │
 ├─ [if caster already concentrating]:
 │   └─ remove_condition("Concentrating") → old spell effects cleaned up
 │       └─ Full condition removal cascade (see ACTIONS_REFERENCE.md)
 │
 ├─ ConditionApplicationEvent → Concentrating on caster
 │   └─ Registers CON save handler for TAKE_DAMAGE
 │
 ├─ Apply spell effect (save-based or auto):
 │   ├─ On SAVE: no spell effect → caster is concentrating on nothing
 │   └─ On FAIL: ConditionApplicationEvent → SpellEffect on target
 │       └─ Link: Concentrating.add_linked_condition(target, effect)
 │           ├─ Forward: if concentration breaks → effect removed
 │           └─ Reverse: if effect removed → check child_removal_policy
 │               └─ policy="last" + no siblings → Concentrating auto-removed
 │
 └─ SpellEvent(COMPLETION)

 ── During spell lifetime: ──

 On caster takes damage:
   └─ CON save DC max(10, dmg/2)
       ├─ SUCCESS → maintained
       └─ FAIL → Concentrating removed → all linked effects cascade-removed

 On caster casts new concentration spell:
   └─ Old Concentrating removed first → cascade cleanup

 On caster dies/incapacitated:
   └─ Concentrating auto-removed → cascade cleanup

 On target saves (repeat save):
   └─ SpellEffect removed → reverse link → Concentrating removed (if last child)
```

### Zone Spell (Full Tree)

```
SpellEvent(EXECUTION)
 │
 ├─ ConditionApplicationEvent → ZoneControlCondition on caster
 │   ├─ Calculate affected_positions (sphere/cube/cone/line)
 │   ├─ Register SpatialHandlers at each position (O(1) lookup)
 │   ├─ Apply difficult terrain markers at positions
 │   ├─ Apply light modifiers if applicable
 │   └─ Apply ZoneMarkerCondition on each tile (display/pathfinding)
 │
 ├─ [initial cast] For each entity already in zone:
 │   └─ Zone entry effect (save, damage, condition — spell-specific)
 │
 ├─ ConditionApplicationEvent → Concentrating on caster (linked)
 │
 └─ SpellEvent(COMPLETION)

 ── During zone lifetime: ──

 On entity enters zone cell:
   └─ SPATIAL_ENTITY_ENTERED event
       └─ SpatialHandler fires (O(1) position lookup):
           ├─ Spike Growth: 2d4 piercing per 5ft (no save)
           ├─ Web: DEX save → Restrained on fail
           ├─ Grease: DEX save → Prone on fail
           ├─ Spirit Guardians: WIS save → 3d8 radiant (half on save) + slowed
           ├─ Cloudkill: HP≤5 instant death, else CON save → 5d8 poison
           └─ Silence: blocks verbal-component spell casting

 On caster moves (mobile zones like Spirit Guardians):
   └─ Zone center updated
       └─ EventQueue.update_spatial_handler_positions(delta)
           ├─ New cells added
           └─ Old cells removed

 On concentration breaks:
   └─ ZoneControlCondition removed
       └─ All SpatialHandlers deregistered
       └─ Terrain markers removed
       └─ Light modifiers removed
       └─ Tile markers removed
```

### Generic Spell Event Chain Template

Every spell follows this base pattern:

```
SpellEvent(DECLARATION) → _validate() → check range/LOS/targets
 └─ SpellEvent(EXECUTION) → _validate() again + _apply()
     └─ Per-target convolution (if multi-target/AoE):
         ├─ SavingThrowEvent / AttackEvent (child events)
         ├─ TakeDamageEvent / HealingEvent (damage/healing)
         └─ ConditionApplicationEvent (effects applied)
     └─ SpellEvent(EFFECT)
         └─ SpellEvent(COMPLETION) → combat log generated via callback
```

Each phase can be intercepted by handlers (except COMPLETION, which skips handlers).

---

## Cantrips (Level 0)

### Fire Bolt
- **File**: `dnd/spells/evocation.py:56`
- **School**: Evocation | **Target**: ENTITY | **Range**: 120ft
- **Concentration**: No
- **SRD**: You hurl a mote of fire at a creature or object within range. Make a ranged spell attack. On a hit, the target takes 1d10 fire damage. Scales: 2d10 at L5, 3d10 at L11, 4d10 at L17.

**Event Chain**:
```
SpellEvent(DECLARATION) → validate LOS + range
 └─ SpellEvent(EXECUTION) → spell attack (d20 vs AC)
     ├─ On MISS: SpellEvent(EFFECT) → COMPLETION
     └─ On HIT: roll 1d10 fire + spell damage bonus
         └─ TakeDamageEvent(EFFECT) → apply damage
             ├─ HP > 0: COMPLETION
             └─ HP ≤ 0: DeathEvent → Dead condition
```

---

### Sacred Flame
- **File**: `dnd/spells/evocation.py:357`
- **School**: Evocation | **Target**: ENTITY | **Range**: 60ft
- **Concentration**: No
- **SRD**: Flame-like radiance descends on a creature. Target must succeed on a DEX save or take 1d8 radiant damage. Cover gives no benefit. Scales with caster level.

**Event Chain**:
```
SpellEvent(EXECUTION) → validate LOS + range
 └─ SavingThrowEvent(DEX) vs spell DC
     ├─ On SAVE: no damage → COMPLETION
     └─ On FAIL: roll 1d8 radiant + bonus
         └─ TakeDamageEvent → apply damage → possible death
```

---

### Ray of Frost
- **File**: `dnd/spells/evocation.py:221`
- **School**: Evocation | **Target**: ENTITY | **Range**: 60ft
- **Concentration**: No
- **SRD**: A frigid beam of blue-white light streaks toward a creature. On hit, 1d8 cold damage and speed reduced by 10ft until start of your next turn.

**Event Chain**:
```
SpellEvent(EXECUTION) → spell attack (d20 vs AC)
 ├─ On MISS: COMPLETION
 └─ On HIT: roll 1d8 cold
     ├─ TakeDamageEvent → apply damage
     └─ ConditionApplicationEvent → RayOfFrostEffect on caster
         └─ -10ft speed modifier applied to target (tracked via affected_target_uuid)
```

---

### Poison Spray
- **File**: `dnd/spells/conjuration.py:285`
- **School**: Conjuration | **Target**: ENTITY | **Range**: 10ft
- **Concentration**: No
- **SRD**: You extend your hand toward a creature within range and project a puff of noxious gas. Target must succeed on a CON save or take 1d12 poison damage.

**Event Chain**:
```
SpellEvent(EXECUTION) → validate range
 └─ SavingThrowEvent(CON) vs spell DC
     ├─ On SAVE: no damage → COMPLETION
     └─ On FAIL: roll 1d12 poison → TakeDamageEvent → possible death
```

---

### Acid Splash
- **File**: `dnd/spells/conjuration.py:383`
- **School**: Conjuration | **Target**: MULTI_ENTITY (up to 2) | **Range**: 60ft
- **Concentration**: No
- **SRD**: You hurl a bubble of acid. Choose one or two creatures within 60ft. Target must succeed on DEX save or take 1d6 acid damage.

**Event Chain**:
```
SpellEvent(EXECUTION) → validate range + LOS for all targets
 └─ Per target (convolution):
     └─ SavingThrowEvent(DEX) vs spell DC
         ├─ On SAVE: half damage
         └─ On FAIL: full 1d6 acid → TakeDamageEvent
```

---

### Chill Touch
- **File**: `dnd/spells/necromancy.py:222`
- **School**: Necromancy | **Target**: ENTITY | **Range**: 120ft
- **Concentration**: No
- **SRD**: You create a ghostly, skeletal hand. On hit, 1d8 necrotic damage, target can't regain HP until your next turn. If target is undead, it also has disadvantage on attacks against you.

**Event Chain**:
```
SpellEvent(EXECUTION) → spell attack (d20 vs AC)
 ├─ On MISS: COMPLETION
 └─ On HIT: roll 1d8 necrotic
     ├─ TakeDamageEvent → apply damage
     ├─ ConditionApplicationEvent → ChillTouchEffect on caster (1 round)
     │   └─ Linked: NoHealing condition on target (prevents healing)
     └─ If undead: contextual DISADVANTAGE on target's attacks vs caster
```

---

### Shocking Grasp
- **File**: `dnd/spells/evocation.py:2112`
- **School**: Evocation | **Target**: ENTITY | **Range**: Touch (5ft)
- **Concentration**: No
- **SRD**: Lightning springs from your hand. Make a melee spell attack. On hit, 1d8 lightning damage and target can't take reactions until start of its next turn.

**Event Chain**:
```
SpellEvent(EXECUTION) → melee spell attack (d20 vs AC)
 ├─ On MISS: COMPLETION
 └─ On HIT: roll 1d8 lightning
     ├─ TakeDamageEvent → apply damage
     └─ ConditionApplicationEvent → NoReactions on target (1 round)
```

---

### Eldritch Blast
- **File**: `dnd/spells/evocation.py:2498`
- **School**: Evocation | **Target**: MULTI_ENTITY | **Range**: 120ft
- **Concentration**: No
- **SRD**: A beam of crackling energy streaks toward a creature. Make a ranged spell attack. On hit, 1d10 force damage. Multiple beams at higher levels.

**Event Chain**:
```
SpellEvent(EXECUTION)
 └─ Per blast (convolution, scales with level):
     └─ Spell attack (d20 vs AC)
         ├─ On MISS: next blast
         └─ On HIT: roll 1d10 force → TakeDamageEvent
```

---

### True Strike
- **File**: `dnd/spells/evocation.py:3524`
- **School**: Evocation | **Target**: SELF
- **Concentration**: No
- **SRD**: You extend your hand and point. Your next attack roll against the target has advantage.

**Event Chain**:
```
SpellEvent(EFFECT) → register_true_strike() handler
 └─ Next attack: handler fires, adds ADVANTAGE, auto-removes
```

---

### Guidance
- **File**: `dnd/spells/divination.py:269`
- **School**: Divination | **Target**: ENTITY (touch) | **Range**: 5ft
- **Concentration**: Yes
- **SRD**: You touch one willing creature. Once before the spell ends, the target can roll a d4 and add it to one ability check.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ ConditionApplicationEvent → GuidanceEffect on target
     └─ Next ability check: D20RollResultEvent fires
         └─ GuidanceEffect handler adds +1d4, then auto-removes
```

---

### Light
- **File**: `dnd/spells/evocation.py:3791`
- **School**: Evocation | **Target**: ENTITY | **Range**: 60ft
- **Concentration**: No
- **SRD**: You touch one object. The object sheds bright light in a 20-foot radius and dim light for an additional 20 feet.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ ConditionApplicationEvent → LightEffect on target object
     └─ SPATIAL_LIGHT_CHANGED event → senses update for observers
```

---

### Resistance
- **File**: `dnd/spells/abjuration.py:1908`
- **School**: Abjuration | **Target**: ENTITY (touch) | **Range**: 5ft
- **Concentration**: Yes
- **SRD**: You touch one willing creature. Once before the spell ends, the target can roll a d4 and add it to one saving throw.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ ConditionApplicationEvent → ResistanceEffect on target
     └─ Next saving throw: handler adds +1d4, auto-removes
```

---

## Level 1 Spells

### Magic Missile
- **File**: `dnd/spells/evocation.py:476`
- **School**: Evocation | **Target**: MULTI_ENTITY (3 darts, +1/upcast) | **Range**: 120ft
- **Concentration**: No
- **SRD**: You create three glowing darts of magical force. Each dart hits automatically and deals 1d4+1 force damage. You can direct them at one or several creatures.

**Event Chain**:
```
SpellEvent(EXECUTION)
 └─ Per dart (convolution, allow_same_target=True):
     └─ No attack roll (auto-hit)
         └─ Roll 1d4+1 force → TakeDamageEvent → possible death
```

---

### Burning Hands
- **File**: `dnd/spells/evocation.py:916`
- **School**: Evocation | **Target**: POSITION_AOE (15ft cone) | **Range**: Self
- **Concentration**: No
- **SRD**: As you hold your hands with thumbs touching, a thin sheet of flames shoots forth. Each creature in a 15-foot cone must make a DEX save. 3d6 fire damage on fail, half on save.

**Event Chain**:
```
SpellEvent(EXECUTION) → cone AoE from caster
 └─ Per target in cone (convolution):
     └─ SavingThrowEvent(DEX) vs spell DC
         ├─ On SAVE: half of 3d6 fire
         └─ On FAIL: full 3d6 fire
             └─ TakeDamageEvent → possible death
```

---

### Thunderwave
- **File**: `dnd/spells/evocation.py:1176`
- **School**: Evocation | **Target**: POSITION_AOE (15ft sphere centered on caster)
- **Concentration**: No
- **SRD**: A wave of thunderous force sweeps out from you. Each creature in a 15-foot cube must make a CON save. On fail, 2d8 thunder damage and pushed 10ft away. On save, half damage and not pushed.

**Event Chain**:
```
SpellEvent(EXECUTION) → sphere centered on caster
 └─ Per target in area (convolution):
     └─ SavingThrowEvent(CON) vs spell DC
         ├─ On SAVE: half 2d8 thunder, no push
         └─ On FAIL: full 2d8 thunder + push
             ├─ TakeDamageEvent → apply damage
             └─ ForcedMovementEvent → pushed 10ft away (no OA)
```

---

### Healing Word
- **File**: `dnd/spells/evocation.py:4028`
- **School**: Evocation | **Target**: ENTITY | **Range**: 60ft
- **Cost**: Bonus action
- **Concentration**: No
- **SRD**: A creature of your choice that you can see within range regains hit points equal to 1d4 + your spellcasting ability modifier.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ Roll 1d4 + spell ability mod
     └─ HealRollResultEvent (handlers can intercept)
         └─ HealingEvent → target gains HP
```

---

### Cure Wounds
- **File**: `dnd/spells/evocation.py:3964`
- **School**: Evocation | **Target**: ENTITY (touch) | **Range**: Touch
- **Concentration**: No
- **SRD**: A creature you touch regains hit points equal to 1d8 + your spellcasting ability modifier. Has no effect on undead or constructs.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ Roll 1d8 + spell ability mod
     └─ HealRollResultEvent → HealingEvent → target gains HP
```

---

### Grease
- **File**: `dnd/spells/conjuration.py:764`
- **School**: Conjuration | **Target**: POSITION_AOE (10ft square) | **Range**: 60ft
- **Concentration**: Yes
- **SRD**: Slick grease covers the ground in a 10-foot square. When the area appears, each creature must succeed on a DEX save or fall prone. A creature that enters or ends turn must also save.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ ConditionApplicationEvent → GreaseZone (ZoneControlCondition) on caster
     └─ SpatialHandler registered for SPATIAL_ENTITY_ENTERED
         └─ On entry: SavingThrowEvent(DEX) vs spell DC
             ├─ On SAVE: no effect
             └─ On FAIL: ConditionApplicationEvent → Prone
```

---

### Mage Armor
- **File**: `dnd/spells/abjuration.py:405`
- **School**: Abjuration | **Target**: ENTITY (touch) | **Range**: Touch
- **Concentration**: No | **Duration**: 8 hours
- **SRD**: You touch a willing creature who isn't wearing armor, and a protective magical force surrounds it. The target's base AC becomes 13 + DEX modifier.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ ConditionApplicationEvent → MageArmorCondition on target
     └─ Sets AC = 13 + DEX (if no armor worn)
```

---

### Shield of Faith
- **File**: `dnd/spells/abjuration.py:1997`
- **School**: Abjuration | **Target**: ENTITY | **Range**: 60ft
- **Cost**: Bonus action
- **Concentration**: Yes
- **SRD**: A shimmering field appears around a creature, granting +2 bonus to AC for the duration.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ ConditionApplicationEvent → ShieldOfFaithEffect on target (+2 AC)
 └─ ConditionApplicationEvent → Concentrating on caster (linked)
```

---

### Sanctuary
- **File**: `dnd/spells/abjuration.py:2268`
- **School**: Abjuration | **Target**: ENTITY | **Range**: 30ft
- **Cost**: Bonus action
- **Concentration**: Yes
- **SRD**: You ward a creature. Until the spell ends, any creature who targets the warded creature with an attack must first make a WIS save. On fail, the creature must choose a new target or lose the attack.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ ConditionApplicationEvent → SanctuaryEffect on target
     └─ When attacked: AttackEvent(DECLARATION)
         └─ SanctuaryEffect handler fires:
             └─ SavingThrowEvent(WIS) for attacker vs spell DC
                 ├─ On SAVE: attack proceeds normally
                 └─ On FAIL: AttackEvent cancelled
```

---

### Sleep
- **File**: `dnd/spells/enchantment.py:959`
- **School**: Enchantment | **Target**: MULTI_ENTITY (ascending HP order) | **Range**: 90ft
- **Concentration**: No
- **SRD**: You send creatures into a magical slumber. Roll 5d8; the total is how many HP of creatures this spell can affect. Creatures within 20ft of a point are affected in ascending order of current HP.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ Roll 5d8 total HP pool
 └─ Sort targets by HP ascending
 └─ Per creature (until pool exhausted):
     └─ If creature HP ≤ remaining pool:
         ├─ ConditionApplicationEvent → SleepEffect (Unconscious)
         └─ Decrement pool by creature HP
```

---

### Bane
- **File**: `dnd/spells/enchantment.py:1435`
- **School**: Enchantment | **Target**: MULTI_ENTITY (up to 3) | **Range**: 30ft
- **Concentration**: Yes
- **SRD**: Up to three creatures must make CHA saves. On fail, whenever a target makes an attack roll or saving throw, it must roll a d4 and subtract the number.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ Per target (convolution):
     └─ SavingThrowEvent(CHA) vs spell DC
         ├─ On SAVE: no effect
         └─ On FAIL: ConditionApplicationEvent → BaneEffect
             └─ -1d4 on attacks and saves (handler-based subtraction)
```

---

### Bless
- **File**: `dnd/spells/enchantment.py:1521`
- **School**: Enchantment | **Target**: MULTI_ENTITY (up to 3 allies) | **Range**: 30ft
- **Concentration**: Yes
- **SRD**: You bless up to three creatures. Whenever a target makes an attack roll or saving throw, it can roll a d4 and add the number.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ Per target (convolution):
     └─ ConditionApplicationEvent → BlessEffect
         └─ +1d4 on attacks and saves (handler-based addition)
```

---

### Charm Person
- **File**: `dnd/spells/enchantment.py:28`
- **School**: Enchantment | **Target**: MULTI_ENTITY (humanoids, +1/upcast) | **Range**: 30ft
- **Concentration**: No | **Duration**: 1 hour
- **SRD**: You attempt to charm a humanoid. It must make a WIS save, with advantage if you or your companions are fighting it. On fail, it is charmed by you.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ Per target (convolution, humanoid only):
     ├─ If fighting caster: add ADVANTAGE to save
     └─ SavingThrowEvent(WIS) vs spell DC
         ├─ On SAVE: no effect
         └─ On FAIL: ConditionApplicationEvent → Charmed
```

---

### Command
- **File**: `dnd/spells/enchantment.py:1748`
- **School**: Enchantment | **Target**: ENTITY | **Range**: 60ft
- **Concentration**: No
- **SRD**: You speak a one-word command. Target makes WIS save or follows the command on its next turn.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ SavingThrowEvent(WIS) vs spell DC
     ├─ On SAVE: no effect
     └─ On FAIL (command-dependent):
         ├─ "Grovel": ConditionApplicationEvent → CommandGrovelEffect (Prone)
         ├─ "Halt": ConditionApplicationEvent → CommandHaltEffect (speed=0)
         └─ "Flee": ConditionApplicationEvent → CommandFleeEffect (Dash away)
```

---

### False Life
- **File**: `dnd/spells/necromancy.py:30`
- **School**: Necromancy | **Target**: SELF
- **Concentration**: No | **Duration**: 1 hour
- **SRD**: Bolstering yourself with a necromantic facsimile of life, you gain 1d4+4 temporary hit points.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ Roll 1d4+4 (+5/upcast) → health.add_temporary_hit_points()
```

---

### Inflict Wounds
- **File**: `dnd/spells/necromancy.py:1467`
- **School**: Necromancy | **Target**: ENTITY | **Range**: Touch
- **Concentration**: No
- **SRD**: Make a melee spell attack. On hit, the target takes 3d10 necrotic damage.

**Event Chain**:
```
SpellEvent(EXECUTION) → melee spell attack (d20 vs AC)
 ├─ On MISS: COMPLETION
 └─ On HIT: roll 3d10 necrotic → TakeDamageEvent → possible death
```

---

### Jump (Spell)
- **File**: `dnd/spells/transmutation.py:1176`
- **School**: Transmutation | **Target**: ENTITY (touch)
- **Concentration**: No | **Duration**: 1 minute
- **SRD**: You touch a creature. The creature's jump distance is tripled until the spell ends.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ ConditionApplicationEvent → JumpEffect on target (×3 jump distance)
```

---

### Expeditious Retreat
- **File**: `dnd/spells/transmutation.py:1318`
- **School**: Transmutation | **Target**: SELF
- **Cost**: Bonus action
- **Concentration**: Yes
- **SRD**: You can take the Dash action as a bonus action on each of your turns until the spell ends.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ ConditionApplicationEvent → ExpeditiousRetreatEffect on caster
     └─ Grants repeatable BonusDash action (bonus action each turn)
```

---

### Aid
- **File**: `dnd/spells/abjuration.py:2093`
- **School**: Abjuration | **Target**: MULTI_ENTITY (up to 3) | **Range**: 30ft
- **Concentration**: No | **Duration**: 8 hours
- **SRD**: Your spell bolsters your allies with toughness. Choose up to three creatures. Each target's HP maximum and current HP increase by 5.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ Per target (convolution):
     └─ ConditionApplicationEvent → AidEffect (+5 max HP, +5 temp HP)
```

---

### Fog Cloud
- **File**: `dnd/spells/conjuration.py:2125`
- **School**: Conjuration | **Target**: POSITION_AOE (20ft sphere) | **Range**: 120ft
- **Concentration**: Yes
- **SRD**: You create a 20-foot-radius sphere of fog. The area is heavily obscured.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ ConditionApplicationEvent → FogCloudZone (ZoneControlCondition)
     └─ Modifies visibility: heavy obscurement at all affected positions
         └─ SPATIAL_LIGHT_CHANGED → senses recalculated for all observers
```

---

## Level 2 Spells

### Scorching Ray
- **File**: `dnd/spells/evocation.py:610`
- **School**: Evocation | **Target**: MULTI_ENTITY (3 rays, +1/upcast) | **Range**: 120ft
- **Concentration**: No
- **SRD**: You create three rays of fire and hurl them. You can hurl them at one or several targets. Make a ranged spell attack for each ray. On hit, 2d6 fire damage.

**Event Chain**:
```
SpellEvent(EXECUTION)
 └─ Per ray (convolution, allow_same_target=True):
     └─ Spell attack (d20 vs AC)
         ├─ On MISS: next ray
         └─ On HIT: roll 2d6 fire → TakeDamageEvent
```

---

### Hold Person
- **File**: `dnd/spells/enchantment.py:340`
- **School**: Enchantment | **Target**: ENTITY (humanoid) | **Range**: 60ft
- **Concentration**: Yes
- **SRD**: Choose a humanoid. Target must make a WIS save or be paralyzed. At the end of each turn, it can make another WIS save to end the effect.

**Event Chain**:
```
SpellEvent(EXECUTION)
 ├─ ConditionApplicationEvent → Concentrating on caster (BEFORE save!)
 │   └─ Breaks existing concentration if any
 └─ SpellEvent(EFFECT)
     └─ SavingThrowEvent(WIS) vs spell DC
         │
         ├─ On SAVE: no spell effect applied
         │   └─ Caster IS still concentrating (on nothing, until new spell or voluntary drop)
         │
         └─ On FAIL:
             └─ ConditionApplicationEvent → HoldPersonEffect on target
                 ├─ Sub-condition: Paralyzed
                 │   ├─ Sub-condition: Incapacitated (actions/bonus/reactions/movement = 0)
                 │   ├─ Auto-fail STR/DEX saves (AUTOMISS)
                 │   └─ Melee within 5ft: AUTOCRIT (to_target_contextual)
                 ├─ Link: Concentrating.add_linked_condition(target, HoldPersonEffect)
                 └─ Registers repeat save handler (TURN_END):
                     └─ SavingThrowEvent(WIS) each turn end
                         ├─ FAIL → condition persists
                         └─ SUCCESS → remove HoldPersonEffect
                             └─ Reverse link (policy="last") → auto-remove Concentrating
```
**Critical**: Concentration is applied BEFORE the save roll. If target saves, caster is concentrating on nothing.

---

### Shatter
- **File**: `dnd/spells/evocation.py:1408`
- **School**: Evocation | **Target**: POSITION_AOE (10ft sphere) | **Range**: 60ft
- **Concentration**: No
- **SRD**: A sudden loud ringing noise erupts. Each creature in a 10-foot-radius sphere must make a CON save. 3d8 thunder damage on fail, half on save.

**Event Chain**:
```
SpellEvent(EXECUTION) → sphere at position
 └─ Per target (convolution):
     └─ SavingThrowEvent(CON) vs spell DC
         ├─ On SAVE: half 3d8 thunder
         └─ On FAIL: full 3d8 thunder → TakeDamageEvent
```

---

### Blur
- **File**: `dnd/spells/illusion.py:64`
- **School**: Illusion | **Target**: SELF
- **Concentration**: Yes
- **SRD**: Your body becomes blurred. For the duration, any creature has disadvantage on attack rolls against you.

**Event Chain**:
```
SpellEvent(EFFECT)
 ├─ ConditionApplicationEvent → BlurEffect on caster
 │   └─ DISADVANTAGE on attacks against (to_target_static)
 └─ ConditionApplicationEvent → Concentrating (linked)
```

---

### Misty Step
- **File**: `dnd/spells/conjuration.py:538`
- **School**: Conjuration | **Target**: POSITION | **Range**: 30ft
- **Cost**: Bonus action
- **Concentration**: No
- **SRD**: Briefly surrounded by silvery mist, you teleport up to 30 feet to an unoccupied space you can see.

**Event Chain**:
```
SpellEvent(EXECUTION) → validate destination visible + walkable
 └─ ForcedMovementEvent → teleport caster (no OA triggered)
     └─ Entity.update_entity_position() → spatial events
```

---

### Blindness/Deafness
- **File**: `dnd/spells/necromancy.py:659`
- **School**: Necromancy | **Target**: ENTITY | **Range**: 30ft
- **Concentration**: No
- **SRD**: You can blind or deafen a foe. Choose one creature. Target must make a CON save or be blinded or deafened (your choice). Repeat save at end of each turn.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ SavingThrowEvent(CON) vs spell DC
     ├─ On SAVE: no effect
     └─ On FAIL: ConditionApplicationEvent → BlindnessDeafnessEffect
         └─ Sub-condition: Blinded OR Deafened (chosen at cast)
         └─ Repeat save handler (TURN_END): on success → remove
```

---

### Spike Growth
- **File**: `dnd/spells/transmutation.py:109`
- **School**: Transmutation | **Target**: POSITION_AOE (20ft sphere) | **Range**: 150ft
- **Concentration**: Yes
- **SRD**: The ground in a 20-foot radius becomes twisted with spikes. The area becomes difficult terrain. When a creature moves through, it takes 2d4 piercing damage for every 5 feet.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ ConditionApplicationEvent → SpikeGrowthZone (ZoneControlCondition) on caster
     ├─ Difficult terrain marker (perception DC = spell DC to detect)
     └─ SpatialHandler for SPATIAL_ENTITY_ENTERED:
         └─ On entry: roll 2d4 piercing per 5ft → TakeDamageEvent
```

---

### Web
- **File**: `dnd/spells/conjuration.py:1110`
- **School**: Conjuration | **Target**: POSITION_AOE (20ft cube) | **Range**: 60ft
- **Concentration**: Yes
- **SRD**: You conjure a mass of thick, sticky webbing. Each creature that starts its turn in or enters the webs must make a DEX save or be restrained. A restrained creature can use its action to make a STR check to free itself.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ ConditionApplicationEvent → WebZone (ZoneControlCondition) on caster
     └─ SpatialHandler for SPATIAL_ENTITY_ENTERED:
         └─ On entry: SavingThrowEvent(DEX) vs spell DC
             ├─ On SAVE: difficult terrain only
             └─ On FAIL: ConditionApplicationEvent → WebRestrained
                 └─ STR save escape handler: action to attempt STR save → remove on success
```

---

### Darkness
- **File**: `dnd/spells/conjuration.py:2232`
- **School**: Conjuration | **Target**: POSITION | **Range**: 60ft
- **Concentration**: Yes
- **SRD**: Magical darkness spreads from a point. A 15-foot-radius sphere of darkness. Nonmagical light can't illuminate it.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ ConditionApplicationEvent → DarknessZone on caster
     └─ Sets light_level = 0 at all affected tiles
         └─ SPATIAL_LIGHT_CHANGED → senses update (can't see in/out without darkvision)
```

---

### Invisibility
- **File**: `dnd/spells/illusion.py:734`
- **School**: Illusion | **Target**: ENTITY (touch)
- **Concentration**: Yes | **Duration**: 1 hour
- **SRD**: A creature you touch becomes invisible. The spell ends if the target attacks or casts a spell.

**Event Chain**:
```
SpellEvent(EFFECT)
 ├─ ConditionApplicationEvent → InvisibilityEffect on target
 │   ├─ Sets is_invisible = True
 │   ├─ SPATIAL_PERCEIVABILITY_CHANGED → observers can't see target
 │   └─ Reveal handler (ATTACK/CAST_SPELL/BASE_ACTION):
 │       └─ On reveal: CONDITION_REMOVAL → visible again
 └─ ConditionApplicationEvent → Concentrating on caster (linked)
```

---

### Mirror Image
- **File**: `dnd/spells/illusion.py:1023`
- **School**: Illusion | **Target**: SELF
- **Concentration**: No | **Duration**: 1 minute
- **SRD**: Three illusory duplicates appear in your space. Each time a creature targets you with an attack, roll a d20. On high roll, attack targets a duplicate instead, destroying it.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ ConditionApplicationEvent → MirrorImageEffect (3 duplicates)
     ├─ Adds +9 AC (3 × +3 per duplicate) via ac_bonus.self_static
     └─ Registers attack miss handler:
         └─ On each AttackEvent with outcome=MISS:
             ├─ Decrement duplicate count (3→2→1→0)
             ├─ Update AC modifier (9→6→3→0)
             └─ If duplicates = 0: remove MirrorImageEffect
```
**Note**: AC-based mechanic, not d20-based. Duplicates boost AC; when an attack misses (because of the boosted AC), a duplicate is consumed.

---

### Protection from Energy
- **File**: `dnd/spells/abjuration.py:532`
- **School**: Abjuration | **Target**: ENTITY (touch)
- **Concentration**: Yes | **Duration**: 1 hour
- **SRD**: Choose acid, cold, fire, lightning, or thunder. The target has resistance to that damage type for the duration.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ ConditionApplicationEvent → ProtectionFromEnergyEffect
     └─ RESISTANCE modifier for chosen damage type
```

---

### Darkvision (Spell)
- **File**: `dnd/spells/transmutation.py:961`
- **School**: Transmutation | **Target**: ENTITY (touch)
- **Concentration**: Yes
- **SRD**: You touch a willing creature to grant it the ability to see in the dark. The creature has darkvision out to 60 feet.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ ConditionApplicationEvent → DarkvisionEffect on target
     └─ Adds DARKVISION sense mode (60ft)
         └─ SPATIAL_PERCEIVABILITY_CHANGED → senses recalculated
```

---

### See Invisibility
- **File**: `dnd/spells/divination.py:60`
- **School**: Divination | **Target**: SELF
- **Concentration**: No | **Duration**: 10 rounds
- **SRD**: For the duration, you see invisible creatures and objects as if they were visible.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ ConditionApplicationEvent → SeeInvisibilityEffect on caster
     └─ Adds SEE_INVISIBLE sense mode
         └─ SPATIAL_PERCEIVABILITY_CHANGED → senses recalculated
```

---

### Enhance Ability
- **File**: `dnd/spells/transmutation.py:1410`
- **School**: Transmutation | **Target**: ENTITY (touch)
- **Concentration**: Yes | **Duration**: 1 hour
- **SRD**: You touch a creature and bestow upon it a magical enhancement. Choose one ability. The target has advantage on ability checks with the chosen ability.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ ConditionApplicationEvent → EnhanceAbilityEffect on target
     └─ ADVANTAGE on checks for chosen ability (handler-based)
```

---

### Enlarge/Reduce
- **File**: `dnd/spells/transmutation.py:1566`
- **School**: Transmutation | **Target**: ENTITY | **Range**: 30ft
- **Concentration**: Yes
- **SRD**: You cause a creature to grow larger or smaller. Enlarge: +1d4 weapon damage, advantage on STR checks/saves. Reduce: -1d4 weapon damage, disadvantage on STR checks/saves.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ ConditionApplicationEvent → EnlargeReduceEffect
     ├─ Enlarge: +1d4 damage, STR +4, speed +5ft
     └─ Reduce: -1d4 damage, STR -4, speed -5ft
```

---

### Silence
- **File**: `dnd/spells/illusion.py:1279`
- **School**: Illusion | **Target**: POSITION_AOE (20ft sphere) | **Range**: 120ft
- **Concentration**: Yes
- **SRD**: For the duration, no sound can be created within or pass through a 20-foot-radius sphere. Creatures inside are immune to thunder damage and deafened. Casting spells with verbal components is impossible.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ ConditionApplicationEvent → SilenceZone (ZoneControlCondition)
     └─ Handler intercepts CAST_SPELL inside zone:
         └─ If spell has verbal component: cancel spell
```

---

### Gust of Wind
- **File**: `dnd/spells/evocation.py:2764`
- **School**: Evocation | **Target**: POSITION_AOE (60ft line × 10ft)
- **Concentration**: Yes
- **SRD**: A line of strong wind 60 feet long and 10 feet wide blasts from you. Each creature that starts its turn in the line must succeed on a STR save or be pushed 15 feet away.

**Event Chain**:
```
SpellEvent(EXECUTION) → line AoE
 └─ Per creature in line (convolution):
     └─ SavingThrowEvent(STR) vs spell DC
         ├─ On SAVE: no push
         └─ On FAIL: ForcedMovementEvent → pushed 15ft away (no OA)
```

---

## Level 3 Spells

### Fireball
- **File**: `dnd/spells/evocation.py:770`
- **School**: Evocation | **Target**: POSITION_AOE (20ft sphere) | **Range**: 150ft
- **Concentration**: No
- **SRD**: A bright streak flashes from your pointing finger and blossoms into a fiery explosion. Each creature in a 20-foot-radius sphere must make a DEX save. 8d6 fire damage on fail, half on save.

**Event Chain**:
```
SpellEvent(EXECUTION) → sphere at position
 └─ Per target in sphere (convolution):
     └─ SavingThrowEvent(DEX) vs spell DC
         ├─ On SAVE: half 8d6 fire
         └─ On FAIL: full 8d6 fire
             └─ TakeDamageEvent → possible death
                 └─ [handler] Concentration save if target concentrating
```

---

### Lightning Bolt
- **File**: `dnd/spells/evocation.py:1046`
- **School**: Evocation | **Target**: POSITION_AOE (100ft line × 5ft)
- **Concentration**: No
- **SRD**: A stroke of lightning forming a 100-foot-long, 5-foot-wide line blasts out from you. Each creature must make a DEX save. 8d6 lightning damage on fail, half on save.

**Event Chain**:
```
SpellEvent(EXECUTION) → line from caster
 └─ Per target in line (convolution):
     └─ SavingThrowEvent(DEX) vs spell DC
         ├─ On SAVE: half 8d6 lightning
         └─ On FAIL: full 8d6 lightning → TakeDamageEvent
```

---

### Call Lightning
- **File**: `dnd/spells/conjuration.py:147`
- **School**: Conjuration | **Target**: ENTITY | **Range**: 120ft
- **Concentration**: Yes
- **SRD**: A storm cloud appears. On cast and each turn (action), you call down a bolt dealing 3d10 lightning damage (DEX save half).

**Event Chain**:
```
SpellEvent(EXECUTION) [initial strike]
 ├─ SavingThrowEvent(DEX) → roll 3d10 lightning (half on save)
 │   └─ TakeDamageEvent → apply damage
 ├─ ConditionApplicationEvent → Concentrating on caster
 └─ Grants CallLightningStrike action (repeatable each turn)
     └─ Each turn: same save + damage chain
```

---

### Spirit Guardians
- **File**: `dnd/spells/conjuration.py:1958`
- **School**: Conjuration | **Target**: SELF (15ft radius zone)
- **Concentration**: Yes
- **SRD**: You call forth spirits to protect you. They flit around you to a distance of 15 feet. When a hostile creature enters or starts its turn in the area, it takes 3d8 radiant damage (WIS save half). Speed halved in the area.

**Event Chain**:
```
SpellEvent(EFFECT)
 ├─ ConditionApplicationEvent → SpiritGuardiansZone (ZoneControlCondition)
 │   └─ SpatialHandler for SPATIAL_ENTITY_ENTERED:
 │       └─ On enemy entry: SavingThrowEvent(WIS) vs spell DC
 │           ├─ On SAVE: half 3d8 radiant
 │           └─ On FAIL: full 3d8 radiant → TakeDamageEvent
 │               └─ ConditionApplicationEvent → SpiritGuardiansSlowed (half speed)
 └─ Zone moves with caster (spatial handlers updated on movement)
```

---

### Slow
- **File**: `dnd/spells/transmutation.py:528`
- **School**: Transmutation | **Target**: POSITION_AOE (40ft cube) | **Range**: 120ft
- **Concentration**: Yes
- **SRD**: Up to six creatures must make WIS saves. On fail: speed halved, -2 AC, -2 DEX saves, no reactions, can use either action or bonus action (not both), limited to one attack.

**Event Chain**:
```
SpellEvent(EXECUTION) → cube at position
 └─ Per target (convolution):
     └─ SavingThrowEvent(WIS) vs spell DC
         ├─ On SAVE: no effect
         └─ On FAIL: ConditionApplicationEvent → SlowedEffect
             ├─ -50% speed, -2 AC, -2 DEX saves
             ├─ No reactions, action/bonus lockout
             └─ Repeat save handler (TURN_END): on success → remove
```

---

### Haste
- **File**: `dnd/spells/transmutation.py:838`
- **School**: Transmutation | **Target**: ENTITY | **Range**: 30ft
- **Concentration**: Yes
- **SRD**: Choose a willing creature. Its speed is doubled, it gains +2 to AC, advantage on DEX saves, and an additional action each turn. When the spell ends, the target is lethargic (can't move or act) until end of next turn.

**Event Chain**:
```
SpellEvent(EFFECT)
 ├─ ConditionApplicationEvent → HasteEffect on target
 │   ├─ ×2 speed, +2 AC, ADVANTAGE on DEX saves
 │   └─ Extra action per turn (Attack/Dash/Disengage/Hide/Use Object only)
 └─ ConditionApplicationEvent → Concentrating on caster (linked)
     └─ On concentration break or spell end:
         └─ HasteEffect removed
             └─ ConditionApplicationEvent → Lethargy (can't move/act, 1 round)
```

---

### Fear
- **File**: `dnd/spells/illusion.py:229`
- **School**: Illusion | **Target**: POSITION_AOE (30ft cone) | **Range**: Self
- **Concentration**: Yes
- **SRD**: Each creature in a 30-foot cone must succeed on a WIS save or become frightened. While frightened, it must Dash away on its turn. Repeat save at end of turn if out of LOS.

**Event Chain**:
```
SpellEvent(EXECUTION) → cone from caster
 └─ Per target in cone (convolution):
     └─ SavingThrowEvent(WIS) vs spell DC
         ├─ On SAVE: no effect
         └─ On FAIL: ConditionApplicationEvent → FearEffect
             └─ Sub-condition: Frightened (directed at caster)
             └─ Repeat save handler (TURN_END):
                 ├─ If can see caster: no save (fear persists)
                 └─ If can't see: WIS save → on success, remove
```

---

### Hypnotic Pattern
- **File**: `dnd/spells/illusion.py:426`
- **School**: Illusion | **Target**: POSITION_AOE (30ft cube) | **Range**: 120ft
- **Concentration**: Yes
- **SRD**: You create a twisting pattern of colors. Each creature must make a WIS save or become charmed and incapacitated. The effect ends if it takes damage or another creature uses an action to shake it.

**Event Chain**:
```
SpellEvent(EXECUTION) → cube at position
 └─ Per target (convolution):
     └─ SavingThrowEvent(WIS) vs spell DC
         ├─ On SAVE: no effect
         └─ On FAIL: ConditionApplicationEvent → HypnoticPatternEffect
             ├─ Sub-condition: Incapacitated
             └─ Sub-condition: Charmed
             └─ Repeat save handler (TURN_START): on success → remove
```

---

### Daylight
- **File**: `dnd/spells/conjuration.py:2337`
- **School**: Conjuration | **Target**: POSITION | **Range**: 60ft
- **Concentration**: No | **Duration**: 1 hour
- **SRD**: A 60-foot-radius sphere of light spreads from a point. The area is brightly lit. Dispels magical darkness.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ ConditionApplicationEvent → DaylightZone
     └─ Sets light_level = maximum at affected positions
         └─ SPATIAL_LIGHT_CHANGED → senses update
```

---

## Level 4 Spells

### Ice Storm
- **File**: `dnd/spells/evocation.py:2875`
- **School**: Evocation | **Target**: POSITION_AOE (40ft sphere) | **Range**: 300ft
- **Concentration**: No
- **SRD**: A hail of rock-hard ice pounds to the ground. Each creature takes 2d8 bludgeoning + 4d6 cold damage (DEX save half). The area becomes difficult terrain.

**Event Chain**:
```
SpellEvent(EXECUTION) → sphere at position
 └─ Per target (convolution):
     └─ SavingThrowEvent(DEX) vs spell DC
         ├─ On SAVE: half (2d8 bludg + 4d6 cold)
         └─ On FAIL: full damage → TakeDamageEvent
 └─ Area becomes difficult terrain
```

---

### Cone of Cold
- **File**: `dnd/spells/evocation.py:1696`
- **School**: Evocation | **Target**: POSITION_AOE (60ft cone) | **Range**: Self
- **Concentration**: No
- **SRD**: A blast of cold air erupts from your hands. Each creature in a 60-foot cone must make a CON save. 8d8 cold damage on fail, half on save.

**Event Chain**: Same pattern as Fireball but CON save, 8d8 cold, cone shape.

---

### Stoneskin
- **File**: `dnd/spells/abjuration.py:671`
- **School**: Abjuration | **Target**: ENTITY (touch)
- **Concentration**: Yes | **Duration**: 1 hour
- **SRD**: The target's flesh becomes as hard as stone. The target has resistance to nonmagical bludgeoning, piercing, and slashing damage.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ ConditionApplicationEvent → StoneskinEffect on target
     └─ RESISTANCE to nonmagical bludgeoning/piercing/slashing
```

---

### Banishment
- **File**: `dnd/spells/abjuration.py:1211`
- **School**: Abjuration | **Target**: ENTITY | **Range**: 60ft
- **Concentration**: Yes
- **SRD**: You attempt to send one creature to another plane. Target must make CHA save or be banished. Repeat save at end of each turn.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ SavingThrowEvent(CHA) vs spell DC
     ├─ On SAVE: no effect
     └─ On FAIL: ConditionApplicationEvent → BanishedCondition
         ├─ Entity removed from GridMap
         └─ Repeat save handler (TURN_END):
             └─ On SUCCESS: entity returns, condition removed
```

---

### Hold Monster
- **File**: `dnd/spells/enchantment.py:576`
- **School**: Enchantment | **Target**: ENTITY | **Range**: 90ft
- **Concentration**: Yes
- **SRD**: Choose a creature. Target must make WIS save or be paralyzed. At end of each turn, repeat save. (Like Hold Person but any creature type.)

**Event Chain**: Same as Hold Person but no creature type restriction. Uses `HoldMonsterEffect` → Paralyzed sub-condition.

---

### Guardian of Faith
- **File**: `dnd/spells/conjuration.py:3573`
- **School**: Conjuration | **Target**: POSITION | **Range**: 30ft
- **Concentration**: No | **Duration**: 8 hours
- **SRD**: A Large spectral guardian appears in an unoccupied space. When a hostile creature enters the space, the guardian makes a melee attack.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ Guardian object placed on GridMap
     └─ SpatialHandler for SPATIAL_ENTITY_ENTERED:
         └─ On hostile entry: attack roll (d20 vs AC)
             ├─ On MISS: no damage
             └─ On HIT: radiant damage → TakeDamageEvent
```

---

### Disintegrate
- **File**: `dnd/spells/transmutation.py:1025`
- **School**: Transmutation | **Target**: ENTITY | **Range**: 60ft
- **Concentration**: No
- **SRD**: A thin green ray springs from your pointing finger. Make a ranged spell attack. On hit, 10d6+40 force damage. If this reduces the target to 0 HP, it is disintegrated.

**Event Chain**:
```
SpellEvent(EXECUTION) → ranged spell attack (d20 vs AC)
 ├─ On MISS: COMPLETION
 └─ On HIT: roll 10d6+40 force
     └─ TakeDamageEvent → apply damage
         ├─ HP > 0: COMPLETION
         └─ HP ≤ 0: target disintegrated (body vaporized, removed from GridMap)
```

---

## Level 5 Spells

### Cloudkill
- **File**: `dnd/spells/conjuration.py:1456`
- **School**: Conjuration | **Target**: POSITION_AOE (20ft sphere) | **Range**: 120ft
- **Concentration**: Yes
- **SRD**: You create a 20-foot-radius sphere of poisonous, yellow-green fog. Each creature that starts its turn there or enters must make a CON save. 5d8 poison damage on fail, half on save.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ ConditionApplicationEvent → CloudkillZone on caster
     └─ SpatialHandler for SPATIAL_ENTITY_ENTERED + TURN_START:
         └─ On entry/turn start in zone:
             ├─ If HP ≤ 5: instant death
             └─ SavingThrowEvent(CON) vs spell DC
                 ├─ On SAVE: half 5d8 poison
                 └─ On FAIL: full 5d8 poison → TakeDamageEvent
```

---

### Sunbeam
- **File**: `dnd/spells/evocation.py:3119`
- **School**: Evocation | **Target**: POSITION_AOE (60ft line, repeatable) | **Range**: Self
- **Concentration**: Yes
- **SRD**: A beam of brilliant light flashes out in a 5-foot-wide, 60-foot-long line. Each creature must make a CON save. 6d8 radiant damage on fail, half on save. You can create a new line each turn.

**Event Chain**:
```
SpellEvent(EXECUTION) [initial cast]
 ├─ ConditionApplicationEvent → Concentrating
 └─ Grants SunbeamStrike action (repeatable each turn)
     └─ Each turn (1 action):
         └─ Line from caster → per target:
             ├─ If undead: DISADVANTAGE on save
             └─ SavingThrowEvent(CON) vs spell DC
                 ├─ On SAVE: half 6d8 radiant
                 └─ On FAIL: full 6d8 radiant + possible blinded
```

---

### Greater Restoration
- **File**: `dnd/spells/abjuration.py:1380`
- **School**: Abjuration | **Target**: ENTITY (touch)
- **Concentration**: No
- **SRD**: You imbue a creature with positive energy to undo one debilitating effect: reduce exhaustion by one level, end charmed/petrified, end a curse, end an ability score reduction, or end an HP maximum reduction.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ Remove one named condition from target
     └─ ConditionRemovalEvent → condition removed + cascade cleanup
```

---

## Level 6 Spells

### Circle of Death
- **File**: `dnd/spells/evocation.py:1552`
- **School**: Evocation | **Target**: POSITION_AOE (30ft sphere) | **Range**: 150ft
- **Concentration**: No
- **SRD**: A sphere of negative energy ripples out in a 60-foot-radius sphere. Each creature must make a CON save. 8d6 necrotic damage on fail, half on save.

**Event Chain**: Same pattern as Fireball but CON save, 8d6 necrotic, 30ft sphere.

---

### Chain Lightning
- **File**: `dnd/spells/evocation.py:3186`
- **School**: Evocation | **Target**: ENTITY + chained targets | **Range**: 150ft
- **Concentration**: No
- **SRD**: You create a bolt of lightning that arcs toward a target. Three bolts leap from the target to up to three other targets within 30 feet. Each must make DEX save. 10d8 lightning damage on fail, half on save.

**Event Chain**:
```
SpellEvent(EXECUTION)
 ├─ Primary target: spell attack → 10d8 lightning → TakeDamageEvent
 └─ Per chained target (up to 3, within 30ft):
     └─ SavingThrowEvent(DEX) vs spell DC
         ├─ On SAVE: half damage
         └─ On FAIL: full damage → TakeDamageEvent
```

---

### Globe of Invulnerability
- **File**: `dnd/spells/abjuration.py:1055`
- **School**: Abjuration | **Target**: SELF (15ft sphere)
- **Concentration**: Yes
- **SRD**: An immobile, faintly shimmering barrier springs into existence in a 10-foot radius around you. Any spell of 5th level or lower cast from outside can't affect creatures or objects within.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ ConditionApplicationEvent → GlobeZone on caster
     └─ Handler intercepts spell events:
         ├─ Spell from outside targeting inside: cancelled
         └─ Spell from inside targeting outside: allowed
```

---

### Eyebite
- **File**: `dnd/spells/necromancy.py:1269`
- **School**: Necromancy | **Target**: SELF (grants action)
- **Concentration**: Yes
- **SRD**: For the spell's duration, your eyes become an inky void. As an action each turn, you can target one creature within 60 feet. Choose Asleep, Panicked, or Sickened effect.

**Event Chain**:
```
SpellEvent(EFFECT)
 ├─ ConditionApplicationEvent → Concentrating
 └─ Grants EyebiteStrike action (repeatable)
     └─ Each turn (1 action): choose target + effect
         ├─ Asleep: ConditionApplicationEvent → EyebiteAsleepEffect (Unconscious)
         ├─ Panicked: ConditionApplicationEvent → EyebitePanickedEffect (Frightened)
         └─ Sickened: ConditionApplicationEvent → SickenedCondition
```

---

## Level 7 Spells

### Prismatic Spray
- **File**: `dnd/spells/evocation.py:3378`
- **School**: Evocation | **Target**: POSITION_AOE (cone) | **Range**: Self
- **Concentration**: No
- **SRD**: Eight multicolored rays of light flash from your hand. Each creature in a 60-foot cone is struck by a random ray, determined by d8 roll.

**Event Chain**:
```
SpellEvent(EXECUTION) → cone from caster
 └─ Per creature in cone:
     └─ Roll d8 for ray color:
         ├─ Red (1): 10d6 fire (no save)
         ├─ Orange (2): 10d6 acid (DEX save half)
         ├─ Yellow (3): 10d6 lightning (DEX save half)
         ├─ Green (4): 10d6 poison (DEX save half)
         ├─ Blue (5): 10d6 cold (DEX save half)
         ├─ Indigo (6): 10d6 force (DEX save half)
         ├─ Violet (7): 10d6 force + Blinded (DEX save avoids blind)
         └─ Special (8): roll twice, apply both
```

---

### Regenerate
- **File**: `dnd/spells/transmutation.py:2049`
- **School**: Transmutation | **Target**: ENTITY (touch)
- **Concentration**: Yes
- **SRD**: You touch a creature. For the duration, the target regains 1 HP at the start of each of its turns. Additionally, the target regains 4d8+15 HP when you cast this spell.

**Event Chain**:
```
SpellEvent(EFFECT)
 ├─ Immediate healing: 4d8+15 → HealingEvent
 └─ ConditionApplicationEvent → RegeneratingEffect on target
     └─ Each TURN_START: roll 4d8+15 → HealingEvent
```

---

### Finger of Death
- **File**: `dnd/spells/necromancy.py:1340`
- **School**: Necromancy | **Target**: ENTITY | **Range**: 60ft
- **Concentration**: No
- **SRD**: You send negative energy coursing through a creature. Target must make a CON save. 7d8+30 necrotic damage on fail, half on save. A humanoid killed by this spell rises as a zombie.

**Event Chain**:
```
SpellEvent(EXECUTION)
 └─ SavingThrowEvent(CON) vs spell DC
     ├─ On SAVE: half 7d8+30 necrotic
     └─ On FAIL: full 7d8+30 necrotic → TakeDamageEvent
         └─ If HP ≤ 0: death + zombie creation
```

---

### Divine Word
- **File**: `dnd/spells/evocation.py:4652`
- **School**: Evocation | **Target**: ENTITY | **Range**: 30ft
- **Concentration**: No
- **SRD**: You utter a divine word, imbued with power. Effect depends on target's current HP.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ Check target HP:
     ├─ < 20 HP: SavingThrowEvent(CHA) → on fail: Stunned
     ├─ 20-30 HP: SavingThrowEvent(CHA) → on fail: Blinded + Deafened
     └─ 30+ HP: SavingThrowEvent(CHA) → on fail: Prone
```

---

## Level 8 Spells

### Sunburst
- **File**: `dnd/spells/evocation.py:1926`
- **School**: Evocation | **Target**: POSITION_AOE (60ft sphere) | **Range**: 150ft
- **Concentration**: No
- **SRD**: Brilliant sunlight flashes in a 60-foot radius. Each creature must make a CON save. 12d6 radiant damage on fail, half on save. Blinds creatures that fail.

**Event Chain**:
```
SpellEvent(EXECUTION) → sphere at position
 └─ Per target (convolution):
     ├─ If undead: DISADVANTAGE on save
     └─ SavingThrowEvent(CON) vs spell DC
         ├─ On SAVE: half 12d6 radiant, no blind
         └─ On FAIL: full 12d6 radiant + Blinded (1 round)
             ├─ TakeDamageEvent → apply damage
             └─ ConditionApplicationEvent → SunburstBlindedEffect
```

---

### Antimagic Field
- **File**: `dnd/spells/abjuration.py:2849`
- **School**: Abjuration | **Target**: SELF (10ft sphere)
- **Concentration**: Yes | **Duration**: 1 hour
- **SRD**: A 10-foot-radius invisible sphere of antimagic surrounds you. Within the sphere, spells can't be cast, magical effects are suppressed, and magic items become mundane.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ ConditionApplicationEvent → AntimagicFieldZone on caster
     └─ Handlers intercept:
         ├─ CAST_SPELL inside field: cancelled (affects caster too)
         ├─ CONDITION_APPLICATION (magical): cancelled
         └─ Item use (magical): cancelled
```

---

## Level 9 Spells

### Power Word Kill
- **File**: `dnd/spells/enchantment.py:702`
- **School**: Enchantment | **Target**: ENTITY | **Range**: 60ft
- **Concentration**: No
- **SRD**: You utter a word of power that can compel one creature you can see to die instantly. If the creature has 100 HP or fewer, it dies. Otherwise, the spell has no effect.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ Check target HP:
     ├─ HP ≤ 100: instant death (no save)
     │   └─ Set HP to 0 → DeathEvent → Dead condition → removed from combat
     └─ HP > 100: no effect → COMPLETION
```

---

### Power Word Stun
- **File**: `dnd/spells/enchantment.py:1119`
- **School**: Enchantment | **Target**: ENTITY | **Range**: 60ft
- **Concentration**: No
- **SRD**: You speak a word of power that overwhelms the mind of one creature. If it has 150 HP or fewer, it is stunned. At the end of each turn, it can make a CON save to end the effect.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ Check target HP:
     ├─ HP ≤ 150: ConditionApplicationEvent → PowerWordStunEffect (Stunned)
     │   └─ Repeat save handler (TURN_END): CON save → on success, remove
     └─ HP > 150: no effect
```

---

### Mass Heal
- **File**: `dnd/spells/evocation.py:4419`
- **School**: Evocation | **Target**: MULTI_ENTITY (up to 6) | **Range**: 60ft
- **Concentration**: No
- **SRD**: A flood of healing energy flows from you into injured creatures around you. Each regains up to 700 HP. Also cures diseases, blindness, and deafness.

**Event Chain**:
```
SpellEvent(EFFECT)
 └─ Per target (convolution):
     └─ Roll 4d8+40 healing → HealingEvent → target gains HP
         └─ Optionally: ConditionRemovalEvent (disease/poison)
```

---

## Spell Registration & Lookup

```python
from dnd.actions_functional import register_spell, register_spells_by_name
register_spell(entity, FireBolt, caster_level=5)
register_spells_by_name(entity, ["Hold Person", "Fireball"], caster_level=5)
```

Dictionaries in `dnd/spells/__init__.py`: `CANTRIPS`, `LEVEL_1_SPELLS` through `LEVEL_9_SPELLS`, `ALL_SPELLS`.

---

## Special Spell Mechanics

### Concentration
- One spell at a time. New concentration spell → old one ends.
- CON save on damage: DC = max(10, damage/2). Fail → concentration breaks.
- Forward cleanup: `Concentrating.linked_conditions` → removes all spell effects.
- Reverse cleanup: `child_removal_policy="last"` → auto-removes `Concentrating` when last effect removed.

### Zone Spells (Spatial Handler Pattern)
1. Apply `ZoneControlCondition` to caster
2. Register `SpatialHandler` at affected positions (O(1) lookup)
3. On `SPATIAL_ENTITY_ENTERED` / `SPATIAL_ENTITY_LEFT`: processor fires
4. Zone moves with caster (updates spatial handler positions)
5. Zone disappears when concentration breaks

### Save-Based vs Attack-Based
- **Spell Attack**: d20 vs AC, crit on 20, uses `spell_attack_bonus`
- **Spell Save**: d20 + save mod vs DC (8 + proficiency + spellcasting ability), no crit

### Multi-Target Convolution
- `MULTI_ENTITY` / `POSITION_AOE`: `BaseAction.apply()` loops per target
- Each iteration creates separate child event for combat log aggregation
- `allow_same_target=True`: same creature can be targeted multiple times (Magic Missile, Scorching Ray)

### Shield (Reaction Spell)
- **File**: `dnd/spells/abjuration.py:49`
- **Cost**: 1 reaction + 1st-level spell slot (triggered when hit by attack)
- **Implementation**: NOT a SpellAction — registered as an EventHandler via `register_shield_reaction(entity)`.
- **Trigger**: ATTACK_D20_ROLL_RESULT at EFFECT phase (event_target = caster)
- **Mechanism**: Handler directly modifies the d20 roll event, adding +5 to AC for that single attack. No condition is applied. Checks `has_spell_slot()` before firing and consumes a 1st-level slot.
