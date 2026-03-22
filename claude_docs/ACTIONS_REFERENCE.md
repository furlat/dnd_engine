# Non-Spell Actions Reference

Complete catalog of all non-spell actions in the engine, with file locations, SRD descriptions, costs, and full hierarchical event chains.

---

## Master Conditional Event Chain Diagrams

These diagrams show the complete branching event trees for the engine's core mechanics. Every possible path is shown.

### Attack (Full Tree)

```
AttackEvent(DECLARATION)
 │
 ├─ _validate(): range check, LOS check
 │   └─ INVALID → CANCEL (no further events)
 │
 └─ AttackEvent(EXECUTION)
     ├─ Cross-propagate: attack_bonus.set_from_target(ac)
     ├─ [if ranged + long range] Add DISADVANTAGE modifier
     ├─ [if ranged + threatened] Add DISADVANTAGE modifier
     └─ Roll d20 + attack_bonus vs AC
         │
         ├─ MISS (d20 < AC):
         │   └─ AttackEvent(EFFECT) → handlers react to miss
         │       └─ AttackEvent(COMPLETION) → combat log
         │
         ├─ CRIT_MISS (natural 1):
         │   └─ AttackEvent(EFFECT) → AttackEvent(COMPLETION)
         │
         ├─ HIT (d20 ≥ AC):
         │   └─ [damage chain below]
         │
         └─ CRIT (natural 20 or ≥ crit_threshold):
             └─ [damage chain below, with extra crit dice]

     ── Damage Chain (HIT or CRIT) ──

     AttackEvent(EFFECT, is_last=False)
      │
      ├─ For each damage type on weapon:
      │   └─ DamageRollResultEvent(DECLARATION)
      │       │  original_rolls = rolled dice
      │       └─ DamageRollResultEvent(EFFECT)
      │           ├─ [handler] Great Weapon Fighting → reroll 1s and 2s
      │           ├─ [handler] Savage Attacker → reroll all, keep best
      │           ├─ [handler] Brutal Critical → add extra dice on crit
      │           └─ DamageRollResultEvent(COMPLETION) → final_rolls locked
      │
      └─ target.receive_damage(total)
          └─ TakeDamageEvent(DECLARATION)
              └─ TakeDamageEvent(EFFECT)
                  ├─ Apply resistance → damage halved
                  ├─ Apply vulnerability → damage doubled
                  ├─ Apply immunity → damage = 0
                  │
                  ├─ [handler] DeathWard → if HP would drop to 0, set to 1 instead (once)
                  ├─ [handler] RelentlessRage → CON save DC 10+5n to stay at 1 HP
                  │   └─ SavingThrowEvent(CON)
                  │       ├─ SUCCESS → HP set to 1, survive
                  │       └─ FAIL → HP drops to 0
                  │
                  ├─ [handler] Concentration CON save (DC = max(10, dmg/2))
                  │   └─ SavingThrowEvent(CON)
                  │       ├─ SUCCESS → concentration maintained
                  │       └─ FAIL → CONDITION_REMOVAL(Concentrating)
                  │           └─ Forward cleanup: all linked spell effects removed
                  │               └─ Each: CONDITION_REMOVAL → sub-conditions cascade
                  │
                  └─ Death check:
                      ├─ HP > 0 → TakeDamageEvent(COMPLETION)
                      └─ HP ≤ 0 → DeathEvent(DECLARATION)
                          └─ Dead condition applied
                              └─ Sub-condition: Incapacitated
                              └─ Light sources cleaned up
                          └─ DeathEvent(COMPLETION)

     AttackEvent(EFFECT, is_first=False) → post-damage handlers
      └─ AttackEvent(COMPLETION) → combat log + costs applied
```

### Saving Throw (Full Tree)

```
SavingThrowEvent(DECLARATION)
 │
 └─ SavingThrowEvent(EXECUTION)
     └─ Roll d20 + save_bonus
         │
         ├─ [handler] Indomitable → if FAIL, spend resource to reroll
         │   └─ New d20 roll, take better result
         │
         ├─ [handler] Lucky → spend luck point, roll second d20, choose either
         │
         ├─ [handler] Bless → add +1d4 to result
         ├─ [handler] Bane → subtract 1d4 from result
         ├─ [handler] Guidance (ability checks only) → add +1d4
         │
         └─ D20RollResultEvent(EFFECT) → final result locked
             │
             ├─ Natural 1 → auto-FAIL (regardless of modifiers)
             ├─ Natural 20 → auto-SUCCESS (regardless of modifiers)
             │
             ├─ total ≥ DC → SUCCESS
             │   └─ SavingThrowEvent(EFFECT, success=True)
             │       └─ SavingThrowEvent(COMPLETION) → combat log
             │
             └─ total < DC → FAIL
                 └─ SavingThrowEvent(EFFECT, success=False)
                     └─ SavingThrowEvent(COMPLETION) → combat log
```

### Movement Step (Full Tree)

```
StepMovementEvent(EFFECT) [per cell, use_register=False]
 │
 └─ step_event.post(use_register=True) [SINGLE registration point]
     │
     ├─ [handler] Opportunity Attack (if leaving threatened area):
     │   ├─ Check: not ally, not Disengaging, from_pos threatened, to_pos NOT
     │   └─ If triggers: Attack(use_register=False) → full AttackEvent chain
     │       └─ OA does NOT cancel movement (non-interrupting)
     │
     ├─ [handler] Intercept (if entering charge destination):
     │   └─ Interceptor charges + attacks → full AttackEvent chain
     │       └─ Movement may be blocked if interceptor occupies cell
     │
     ├─ [handler] Zone entry effects (SpatialHandler):
     │   ├─ Spike Growth → 2d4 piercing damage per step
     │   ├─ Web → DEX save or Restrained
     │   ├─ Grease → DEX save or Prone
     │   ├─ Spirit Guardians → WIS save, 3d8 radiant (half on save)
     │   └─ Cloudkill → HP check + CON save, 5d8 poison
     │
     ├─ [if canceled by handler] → break movement loop
     │
     └─ [if not canceled]:
         └─ Entity.update_entity_position()
             ├─ SPATIAL_ENTITY_LEFT(from_pos)
             └─ SPATIAL_ENTITY_ENTERED(to_pos)
         └─ Re-check walkability (map may have changed)
             ├─ Still walkable → continue to next cell
             └─ Blocked → break movement loop

 [After all steps, in finally block]:
 └─ entity.update_entity_senses() → full Dijkstra recompute
```

### Condition Application (Full Tree)

```
entity.add_condition(condition)
 │
 ├─ [if condition.name already active]:
 │   └─ Depends on condition's stacking rules (usually replaces)
 │
 └─ condition._apply(declaration_event) → returns 5-tuple:
     │
     ├─ modifiers: List[(ModifiableValue.uuid, modifier.uuid)]
     │   └─ Each modifier added to appropriate channel
     │
     ├─ handler_uuids: List[UUID]
     │   └─ EventHandlers registered with EventQueue
     │
     ├─ sub_condition_uuids: List[UUID]
     │   └─ Child conditions on SAME entity (e.g., Paralyzed → Incapacitated)
     │       └─ Recursive: each sub-condition goes through add_condition()
     │
     ├─ spatial_handler_uuids: List[UUID]
     │   └─ SpatialHandlers registered at grid positions
     │
     └─ effect_event: Optional[Event]
         └─ ConditionApplicationEvent(EFFECT) → COMPLETION
```

### Condition Removal (Full Tree)

```
entity.remove_condition(name)
 │
 ├─ Pop from active_conditions + active_conditions_by_uuid (BEFORE recursion)
 │
 └─ _remove_condition_tree(condition):
     │
     ├─ Step 1: Recurse into sub_conditions (same block)
     │   └─ For each sub-condition UUID:
     │       └─ remove_condition_by_uuid() → _remove_condition_tree() [recursive]
     │
     ├─ Step 2: Recurse into linked_conditions (OTHER blocks)
     │   └─ For each (target_block_uuid, condition_uuid):
     │       └─ target_block.remove_condition_by_uuid() → _remove_condition_tree()
     │
     ├─ Step 3: condition.cleanup_own_state()
     │   └─ Remove own modifiers from ModifiableValues
     │   └─ Remove own EventHandlers from EventQueue
     │   └─ Remove own SpatialHandlers from EventQueue
     │
     └─ Step 4: Notify parent via reverse link (parent_link)
         ├─ parent_link is None → done
         ├─ parent already mid-removal (popped) → skip (prevents infinite loop)
         └─ parent exists:
             └─ Check child_removal_policy:
                 ├─ "none" → do nothing
                 ├─ "any" → remove parent immediately
                 └─ "last" → count remaining siblings
                     ├─ siblings remain → do nothing
                     └─ no siblings left → remove parent
                         └─ e.g., Concentrating auto-removed when last spell effect gone
```

### Concentration Break (Full Tree)

```
TakeDamageEvent(EFFECT) on a concentrating caster
 │
 └─ Concentration handler fires:
     └─ SavingThrowEvent(CON) DC = max(10, damage/2)
         │
         ├─ SUCCESS → concentration maintained, no further events
         │
         └─ FAIL → remove_condition("Concentrating")
             └─ _remove_condition_tree(Concentrating):
                 │
                 ├─ linked_conditions → spell effects on targets
                 │   └─ For each (target_uuid, effect_uuid):
                 │       └─ target.remove_condition_by_uuid(effect_uuid)
                 │           └─ Spell effect removed (e.g., HoldPersonEffect)
                 │               └─ Sub-conditions cascade (e.g., Paralyzed → Incapacitated)
                 │
                 └─ cleanup_own_state() on Concentrating
                     └─ Remove CON save handler from EventQueue

 Also triggers on:
 ├─ DeathEvent(EFFECT) → auto-removes without save
 ├─ New concentration spell cast → old Concentrating removed first
 └─ DropConcentration action → voluntary removal
```

---

## Core Movement & Control Actions

### Move
- **File**: `dnd/actions.py:166`
- **Cost**: Movement (terrain-dependent, 5ft per cell base)
- **Category**: MOVEMENT
- **Target**: POSITION_PATH
- **SRD**: On your turn, you can move a distance up to your speed. Your movement can include jumping, climbing, and swimming.

**Event Chain**:
```
MovementEvent(DECLARATION)
 └─ phase_to(EXECUTION) → path validation
     └─ For each cell in path:
         └─ StepMovementEvent(EFFECT)
             ├─ [handler] Opportunity Attack → AttackEvent chain (if leaving threat)
             ├─ [handler] Intercept reaction (if entering charge destination)
             ├─ [handler] Zone effects (Spike Growth damage, Web STR save, etc.)
             └─ Entity.update_entity_position()
                 ├─ SPATIAL_ENTITY_LEFT event
                 └─ SPATIAL_ENTITY_ENTERED event
     └─ phase_to(EFFECT) → post-movement
         └─ phase_to(COMPLETION)
```
**Branches**:
- `prefer_safe=True` (default): uses `safe_paths` to avoid hazardous tiles when available
- Each step can be interrupted by OA, Intercept, or environment changes (door closed mid-move)
- Walkability re-checked after each step event (map may have changed)

---

### Jump
- **File**: `dnd/actions.py:1782`
- **Cost**: 1 bonus action + Movement (flat 5ft/cell, ignores terrain costs)
- **Category**: MOVEMENT
- **Target**: POSITION_LOS
- **SRD**: Your STR score determines how far you can jump. Long jump = STR score in feet (with 10ft running start).

**Event Chain**:
```
JumpEvent(DECLARATION)
 └─ phase_to(EXECUTION) → validate range, visibility, walkability at destination
     └─ For each cell in straight-line path:
         └─ StepMovementEvent(EFFECT)
             ├─ [handler] Opportunity Attack (if leaving threat)
             └─ Entity.update_entity_position() → spatial events
     └─ phase_to(EFFECT)
         └─ phase_to(COMPLETION)
```
**Key differences from Move**: Uses LOS (not pathfinding), flat 5ft/cell cost (no terrain), intermediate cells not checked for walkability (airborne). Range = 15ft + STR bonus, multiplied by Jump spell.

---

### Dash
- **File**: `dnd/actions.py:1177`
- **Cost**: 1 action
- **Category**: ABILITY
- **Target**: SELF
- **SRD**: You gain extra movement equal to your speed (after modifiers) for the current turn.

**Event Chain**:
```
ActionEvent(DECLARATION)
 └─ phase_to(EXECUTION)
     └─ phase_to(EFFECT)
         └─ ConditionApplicationEvent → Dashing condition (1 round)
             └─ +base_movement feet to movement (self_static modifier)
     └─ phase_to(COMPLETION)
```

---

### Dodge
- **File**: `dnd/actions.py:1243`
- **Cost**: 1 action
- **Category**: ABILITY
- **Target**: SELF
- **SRD**: Until the start of your next turn, any attack roll made against you has disadvantage (if you can see the attacker), and you make DEX saving throws with advantage.

**Event Chain**:
```
ActionEvent(DECLARATION)
 └─ phase_to(EXECUTION)
     └─ phase_to(EFFECT)
         └─ ConditionApplicationEvent → Dodging condition (1 round)
             ├─ DISADVANTAGE on attacks against (to_target_static)
             └─ ADVANTAGE on DEX saves (self_static)
     └─ phase_to(COMPLETION)
```

---

### Disengage
- **File**: `dnd/actions.py:1316`
- **Cost**: 1 action
- **Category**: ABILITY
- **Target**: SELF
- **SRD**: Your movement doesn't provoke opportunity attacks for the rest of the turn.

**Event Chain**:
```
ActionEvent(DECLARATION)
 └─ phase_to(EXECUTION)
     └─ phase_to(EFFECT)
         └─ ConditionApplicationEvent → Disengaging condition (1 round)
             └─ OA handler checks for Disengaging: skips OA
     └─ phase_to(COMPLETION)
```

---

### Hide
- **File**: `dnd/actions.py:1453`
- **Cost**: 1 action
- **Category**: ABILITY
- **Target**: SELF
- **SRD**: You make a Dexterity (Stealth) check. Until you are discovered or stop hiding, that check's total is contested by the Perception of any creature that actively searches for you.

**Event Chain**:
```
ActionEvent(DECLARATION)
 └─ phase_to(EXECUTION) → rolls d20 + Stealth bonus
     └─ SkillCheckEvent(EFFECT) as child → logs roll result
     └─ phase_to(EFFECT)
         └─ ConditionApplicationEvent → Hidden condition
             ├─ Sets stealth_dc on block (= Stealth roll total)
             ├─ Grants unseen attacker ADVANTAGE (self_contextual)
             └─ Registers reveal handler (8 trigger types):
                 ├─ ATTACK, TAKE_DAMAGE, CAST_SPELL, BASE_ACTION at EFFECT
                 ├─ CONDITION_APPLICATION (Incapacitated only) at EFFECT
                 ├─ SPATIAL_LIGHT_CHANGED, SPATIAL_ENTITY_ENTERED, MOVEMENT_COLLISION
                 └─ Checks NON_REVEALING_ACTIONS whitelist + creation_lineage_uuid
     └─ phase_to(COMPLETION)
```
**Note**: Hide does NOT check light levels — it just rolls Stealth. Light-based perception filtering happens in Senses, not here.
**Reveal triggers**: Attack, take damage, cast spell, non-whitelisted action, incapacitated, light change, entity collision. `creation_lineage_uuid` prevents self-triggering.

---

### DropConcentration
- **File**: `dnd/actions.py:1381`
- **Cost**: Free (0 cost)
- **Category**: ABILITY
- **Target**: SELF
- **SRD**: You can end concentration at any time (no action required).

**Event Chain**:
```
ActionEvent(DECLARATION)
 └─ phase_to(EXECUTION) → validate Concentrating condition exists
     └─ phase_to(EFFECT)
         └─ Remove Concentrating condition
             └─ CONDITION_REMOVAL event
                 └─ Forward cleanup: removes all linked spell effects on targets
                     └─ Each spell effect: CONDITION_REMOVAL → sub-conditions cascade
     └─ phase_to(COMPLETION)
```

---

## Combat Actions

### Attack
- **File**: `dnd/actions.py:785`
- **Cost**: 1 action (off-hand: 1 bonus action)
- **Category**: ATTACK
- **Target**: ENTITY
- **SRD**: Make a melee or ranged weapon attack. Roll d20 + ability modifier + proficiency bonus vs target's AC.

**Event Chain**:
```
AttackEvent(DECLARATION)
 └─ validate_range() → melee reach or ranged normal/long range
 └─ phase_to(EXECUTION)
     ├─ Cross-propagate modifiers: attack_bonus.set_from_target(ac)
     ├─ Add ranged disadvantage if applicable (long range, threatened)
     └─ Roll d20 + attack_bonus vs AC → determine outcome
         │
         ├─ On MISS / CRIT_MISS:
         │   └─ phase_to(EFFECT) → phase_to(COMPLETION)
         │
         └─ On HIT / CRIT:
             └─ phase_to(EFFECT, is_last=False)
                 ├─ For each damage type:
                 │   └─ DamageRollResultEvent(DECLARATION)
                 │       ├─ [handler] Great Weapon Fighting → reroll 1s and 2s
                 │       ├─ [handler] Savage Attacker → reroll all damage dice
                 │       └─ phase_to(EFFECT) → phase_to(COMPLETION)
                 │
                 └─ target.receive_damage()
                     └─ TakeDamageEvent(DECLARATION)
                         ├─ phase_to(EFFECT)
                         │   ├─ Apply resistance/vulnerability/immunity
                         │   ├─ [handler] RelentlessRage → CON save to survive
                         │   └─ [handler] Concentration CON save (DC = max(10, dmg/2))
                         │       └─ SavingThrowEvent → on fail: CONDITION_REMOVAL (concentration breaks)
                         ├─ Check death:
                         │   ├─ HP > 0: phase_to(COMPLETION)
                         │   └─ HP ≤ 0: DeathEvent(DECLARATION) → Dead condition → COMPLETION
                         └─ phase_to(COMPLETION)
             └─ phase_to(EFFECT, is_first=False) → post-damage
                 └─ phase_to(COMPLETION) → costs applied
```

---

### ExtraAttack
- **File**: `dnd/classes/fighter.py:1265`
- **Cost**: 0 actions + 1 extra_attacks resource
- **Category**: ATTACK
- **Target**: ENTITY
- **SRD**: Beginning at 5th level, you can attack twice instead of once whenever you take the Attack action on your turn.

**Event Chain**: Same as Attack (reuses `attack_consequences()`). Prerequisite: `ExtraAttacksGranted` condition must be active (set by HasAttacked handler after first attack action).

---

### Shove
- **File**: `dnd/actions.py:2231`
- **Cost**: 1 bonus action
- **Category**: ABILITY
- **Target**: ENTITY
- **SRD**: You can shove a creature to knock it prone or push it away from you. Contested Athletics vs Athletics/Acrobatics.

**Event Chain**:
```
ShoveEvent(DECLARATION)
 └─ Validate: adjacency (≤5ft), weight limit (STR×12), visibility, LOS
 └─ phase_to(EXECUTION)
     │
     ├─ If ally: auto-succeed (contest_success=True, no roll)
     │
     └─ If enemy: Contested check (raw roll_d20, NOT SkillCheckEvent)
         ├─ Source rolls d20 + Athletics bonus (active roll)
         └─ Target passive DC = 10 + max(Athletics, Acrobatics) + advantage modifier
     │
     └─ phase_to(EFFECT, contest_success=...)
         │
         ├─ On FAIL: phase_to(COMPLETION)
         │
         └─ On SUCCESS:
             ├─ knock_prone=True:
             │   └─ ConditionApplicationEvent → Prone condition
             │       ├─ DISADVANTAGE on own attacks (self_static)
             │       ├─ Contextual to_target: ADVANTAGE ≤5ft, DISADVANTAGE >5ft
             │       └─ Auto-stand on own turn if movement available (setup_standard_actions)
             │
             └─ knock_prone=False (push):
                 └─ Calculate push direction + distance (5ft + 5ft/STR mod, max 20ft)
                     └─ ForcedMovementEvent(DECLARATION)
                         └─ ForcedMovementEvent(COMPLETION)
                             └─ Entity.update_entity_position() → spatial events (NO OA)
     └─ phase_to(COMPLETION) → costs applied
```
**Note**: Shove uses raw `roll_d20()` for the contest, NOT the full SkillCheckEvent system. No handlers can intercept the contest roll.

---

### PickUp
- **File**: `dnd/actions.py:3266`
- **Cost**: Free (0 cost)
- **Category**: ABILITY
- **Target**: OBJECT
- **SRD**: You can pick up items within reach as a free interaction.

**Event Chain**:
```
ActionEvent(DECLARATION)
 └─ Validate: item exists, is_pickable, within 5ft, inventory has space
 └─ phase_to(EXECUTION) → phase_to(EFFECT)
     └─ entity.loot_item(item)
         ├─ SPATIAL_OBJECT_REMOVED event
         └─ Item added to inventory
 └─ phase_to(COMPLETION)
```

---

### AttackObject
- **File**: `dnd/actions.py:3314`
- **Cost**: 1 action
- **Category**: ATTACK
- **Target**: OBJECT
- **SRD**: You can attack a breakable object (door, chest, etc.) with your weapon.

**Event Chain**:
```
ActionEvent(DECLARATION)
 └─ Validate: object exists, is_breakable, is_targetable, within 5ft
 └─ phase_to(EXECUTION)
     └─ Auto-hit: roll weapon damage (no to-hit roll)
 └─ phase_to(EFFECT)
     └─ item.receive_damage(total, damage_type, source_uuid)
         ├─ HP > 0: item damaged
         └─ HP ≤ 0: item destroyed, removed from GridMap
 └─ phase_to(COMPLETION)
```

---

### Drop (Item)
- **File**: `dnd/actions.py:3370`
- **Cost**: Free (0 cost)
- **Category**: ABILITY
- **Target**: POSITION_LOS
- **SRD**: You can drop an item at your feet or an adjacent tile.

**Event Chain**:
```
ActionEvent(DECLARATION)
 └─ Validate: item in inventory, position within 5ft
 └─ phase_to(EXECUTION) → phase_to(EFFECT)
     └─ entity.drop_item(item_uuid, position)
         ├─ Remove from inventory
         └─ SPATIAL_OBJECT_PLACED event → senses update
 └─ phase_to(COMPLETION)
```

---

## Reactions

### Opportunity Attack
- **File**: `dnd/reactions.py:9`
- **Cost**: 1 reaction
- **Category**: ATTACK
- **Trigger**: STEP_MOVEMENT at EFFECT phase
- **SRD**: When a hostile creature you can see moves out of your reach, you can use your reaction to make one melee attack.

**Event Chain**:
```
StepMovementEvent(EFFECT) [enemy leaving threatened area]
 └─ OA handler checks:
     ├─ Not same entity, not ally, not Disengaging
     └─ from_pos in threatened AND to_pos NOT in threatened
         └─ Create Attack(use_register=False)
             └─ AttackEvent chain (full attack → damage → possible death)
 └─ Movement continues (OA does NOT cancel movement)
```

---

### DodgeRoll (Homebrew)
- **File**: `dnd/items/test_reactions.py:279`
- **Cost**: 1 reaction
- **Trigger**: ATTACK at EXECUTION phase (when attacked)
- **Description**: Move up to 2 cells away from attacker, impose disadvantage on the attack.

**Event Chain**:
```
AttackEvent(EXECUTION) [being attacked]
 └─ DodgeRoll handler fires:
     ├─ Calculate flee direction (away from attacker)
     ├─ For up to 2 cells: check walkability → Entity.update_entity_position()
     └─ If moved: add DISADVANTAGE to attack_bonus
 └─ Attack continues with modified bonus
```

---

### Intercept (Homebrew)
- **File**: `dnd/items/test_reactions.py:173` (PrepareIntercept action)
- **Cost**: 1 action + movement (preparation); 1 reaction (trigger)
- **Category**: ABILITY
- **Target**: POSITION_LOS (charge destination)
- **Description**: Declare a charge destination. When an enemy enters that cell, charge there first, occupy it, and make a melee attack.

**Event Chain**:
```
PrepareIntercept(DECLARATION) [preparation phase]
 └─ Validate: straight line, 1-5 cells, all walkable, movement available
 └─ phase_to(EFFECT)
     └─ Consume movement + apply Intercepting condition (1 round)

--- Later, when enemy enters charge_destination ---

StepMovementEvent(EFFECT) [enemy entering the cell]
 └─ Intercept handler fires:
     ├─ Interceptor charges to cell → Entity.update_entity_position()
     └─ Interceptor makes melee Attack → full AttackEvent chain
 └─ Enemy movement continues (may be blocked by interceptor occupying cell)
```

---

## Fighter Class Actions

### SecondWind
- **File**: `dnd/classes/fighter.py:710`
- **Cost**: 1 bonus action + 1 `second_wind` resource (1/short rest)
- **Category**: ABILITY
- **Target**: SELF
- **SRD**: You have a limited well of stamina. On your turn, you can use a bonus action to regain hit points equal to 1d10 + your fighter level.

**Event Chain**:
```
ActionEvent(DECLARATION)
 └─ Validate: not at full HP, resource available
 └─ phase_to(EFFECT)
     └─ Roll 1d10 + fighter_level
         └─ entity.receive_healing(total) → HealingEvent
 └─ phase_to(COMPLETION) → costs applied
```

---

### ActionSurge
- **File**: `dnd/classes/fighter.py:927`
- **Cost**: 0 actions + 1 `action_surge` resource (1-2/long rest)
- **Category**: ABILITY
- **Target**: SELF
- **SRD**: Starting at 2nd level, you can push yourself beyond your normal limits for a moment. On your turn, you can take one additional action.

**Event Chain**:
```
ActionEvent(DECLARATION)
 └─ Validate: resource available, not already ActionSurging this turn
 └─ phase_to(EFFECT)
     └─ ConditionApplicationEvent → ActionSurging condition
         └─ +1 NumericalModifier to actions
         └─ Also serves as once-per-turn marker (no explicit duration,
            removed by TurnEnd handler)
 └─ phase_to(COMPLETION) → costs applied (0 actions + 1 resource)
```

---

## Barbarian Class Actions

### Rage
- **File**: `dnd/classes/rage.py:390`
- **Cost**: 1 bonus action + 1 `rage` resource
- **Category**: ABILITY
- **Target**: SELF
- **SRD**: In battle, you fight with primal ferocity. On your turn, you can enter a rage as a bonus action. While raging, you gain bonus melee damage and resistance to physical damage.

**Event Chain**:
```
ActionEvent(DECLARATION)
 └─ Validate: not in heavy armor, not already raging, have rage resource
 └─ phase_to(EFFECT)
     └─ ConditionApplicationEvent → Raging condition
         ├─ ADVANTAGE on Athletics (self_static) + STR saves (self_static)
         ├─ +2/3/4 melee damage bonus (self_contextual, checks NOT heavy armor)
         ├─ RESISTANCE to bludgeoning/piercing/slashing (health.damage_reduction)
         └─ Registers 3 handlers:
             ├─ Maintenance: turn end, if no HasAttacked/HasTakenDamage → Raging removed
             ├─ Armor: ends rage if heavy armor equipped
             └─ Death: ends rage if entity dies
 └─ phase_to(COMPLETION) → costs applied
```

---

### EndRage
- **File**: `dnd/classes/rage.py:516`
- **Cost**: 1 bonus action
- **Category**: ABILITY
- **Target**: SELF
- **SRD**: Your rage lasts for 1 minute, or until you choose to end it as a bonus action.

**Event Chain**:
```
ActionEvent(DECLARATION)
 └─ Validate: Raging or Frenzied condition exists
 └─ phase_to(EFFECT)
     └─ CONDITION_REMOVAL → Raging removed
         └─ Cascades: Frenzied removed (sub-condition)
             └─ All rage damage bonuses + resistance removed
 └─ phase_to(COMPLETION)
```

---

### Frenzy
- **File**: `dnd/classes/rage.py:899`
- **Cost**: 1 bonus action + 1 `rage` resource
- **Category**: ABILITY
- **Target**: SELF
- **SRD** (Berserker Path): Starting when you choose this path at 3rd level, you can go into a frenzy when you rage. You can make a single melee weapon attack as a bonus action on each of your turns.

**Event Chain**:
```
ActionEvent(DECLARATION)
 └─ Validate: not already raging/frenzied, have rage resource
 └─ phase_to(EFFECT)
     ├─ ConditionApplicationEvent → Raging condition (parent)
     └─ ConditionApplicationEvent → Frenzied condition (sub-condition of Raging)
         └─ Grants FrenziedStrike action template
 └─ phase_to(COMPLETION)
```

---

### FrenziedStrike
- **File**: `dnd/classes/rage.py:775`
- **Cost**: 1 bonus action
- **Category**: ATTACK
- **Target**: ENTITY
- **SRD**: While frenzied, you can make a single melee weapon attack as a bonus action.

**Event Chain**: Same as Attack (reuses `attack_consequences()`). Prerequisite: Frenzied condition active.

---

### RecklessAttack
- **File**: `dnd/classes/barbarian.py:209`
- **Cost**: Free (0 cost)
- **Category**: ABILITY
- **Target**: SELF
- **SRD**: Starting at 2nd level, when you make your first attack on your turn, you can decide to attack recklessly. You have advantage on melee attacks, but attack rolls against you have advantage until your next turn.

**Event Chain**:
```
ActionEvent(DECLARATION)
 └─ Validate: not already RecklessAttacking this turn
 └─ phase_to(EFFECT)
     └─ ConditionApplicationEvent → RecklessAttacking condition (1 round)
         ├─ ADVANTAGE on own melee attacks (melee_attack_bonus.self_static)
         └─ ADVANTAGE on attacks against (ac_bonus.to_target_static)
 └─ phase_to(COMPLETION)
```

---

### IntimidatingPresence
- **File**: `dnd/classes/barbarian.py:1272`
- **Cost**: 1 action
- **Category**: ABILITY
- **Target**: ENTITY
- **SRD** (Berserker Path, L10): You can use your action to frighten someone. Choose one creature within 30ft. If it can see or hear you, it must make a WIS save (DC = 8 + proficiency + CHA) or be frightened until end of your next turn.

**Event Chain**:
```
ActionEvent(DECLARATION)
 └─ Validate: target within 30ft, visible, not immune (saved within 24h)
 └─ phase_to(EXECUTION)
     └─ SavingThrowEvent (WIS) → target rolls save vs DC
         │
         ├─ On FAIL: ConditionApplicationEvent → Frightened (1 round)
         │   └─ Registers auto-end handler: if >60ft or breaks LOS at turn end
         │
         └─ On SUCCESS: IntimidatingPresenceImmunity condition (24h, prevents re-use)
 └─ phase_to(COMPLETION)
```

---

### ExtendIntimidatingPresence
- **File**: `dnd/classes/barbarian.py:1434`
- **Cost**: 1 action
- **Category**: ABILITY
- **Target**: ENTITY
- **SRD**: On subsequent turns, you can extend the duration of this effect by using your action.

**Event Chain**:
```
ActionEvent(DECLARATION)
 └─ Validate: target within 30ft, visible, is Frightened by THIS barbarian
 └─ phase_to(EFFECT)
     └─ Reset Frightened.duration to 1 round
 └─ phase_to(COMPLETION)
```

---

### Retaliation (Passive Reaction)
- **File**: `dnd/classes/barbarian.py:1120`
- **Cost**: 1 reaction
- **Category**: ATTACK
- **Trigger**: TAKE_DAMAGE at EFFECT phase (when damaged by adjacent enemy)
- **SRD** (Berserker Path, L14): When you take damage from a creature within 5 feet of you, you can use your reaction to make a melee weapon attack against that creature.

**Event Chain**:
```
TakeDamageEvent(EFFECT) [damaged by adjacent enemy]
 └─ Retaliation handler checks:
     ├─ Source within 5ft, is enemy, reaction available
     └─ Create Attack → full AttackEvent chain
```

---

## Sorcerer Class Actions

### QuickenedSpell
- **File**: `dnd/classes/sorcerer.py:262`
- **Cost**: 0 actions + 2 sorcery_points
- **Category**: ABILITY
- **Target**: SELF
- **SRD**: When you cast a spell that has a casting time of 1 action, you can spend 2 sorcery points to change the casting time to 1 bonus action.

**Event Chain**:
```
ActionEvent(DECLARATION)
 └─ phase_to(EFFECT)
     └─ ConditionApplicationEvent → MetamagicActive("quickened", 1 round)
         └─ Next spell cast: alt_cost_type = "bonus_actions"
 └─ phase_to(COMPLETION)
```

---

### TwinnedSpell
- **File**: `dnd/classes/sorcerer.py:316`
- **Cost**: 0 actions + 1 sorcery_point
- **Category**: ABILITY
- **Target**: SELF
- **SRD**: When you cast a spell that targets only one creature and doesn't have a range of self, you can spend sorcery points to target a second creature in range.

**Event Chain**:
```
ActionEvent(DECLARATION)
 └─ phase_to(EFFECT)
     └─ ConditionApplicationEvent → MetamagicActive("twinned", 1 round)
         └─ Next spell cast: alt_target_type = MULTI_ENTITY, alt_target_count = 2
 └─ phase_to(COMPLETION)
```

---

### DistantSpell
- **File**: `dnd/classes/sorcerer.py:370`
- **Cost**: 0 actions + 1 sorcery_point
- **Category**: ABILITY
- **Target**: SELF
- **SRD**: When you cast a spell that has a range of 5 feet or greater, you can spend 1 sorcery point to double the range.

**Event Chain**:
```
ActionEvent(DECLARATION)
 └─ phase_to(EFFECT)
     └─ ConditionApplicationEvent → MetamagicActive("distant", 1 round)
         └─ Next spell cast: alt_range = range × 2
 └─ phase_to(COMPLETION)
```

---

### ConvertSlotToSP (Font of Magic)
- **File**: `dnd/classes/sorcerer.py:440`
- **Cost**: 1 bonus action + 1 spell slot (L1-L5)
- **Category**: ABILITY
- **Target**: SELF
- **SRD**: You can use your sorcery points to gain additional spell slots, or sacrifice spell slots to gain additional sorcery points.

**Event Chain**:
```
ActionEvent(DECLARATION)
 └─ phase_to(EFFECT)
     └─ Increment sorcery_points by slot level (capped at max)
 └─ phase_to(COMPLETION)
```

---

### ConvertSPToSlot (Font of Magic)
- **File**: `dnd/classes/sorcerer.py:493`
- **Cost**: 1 bonus action + X sorcery_points (L1=2, L2=3, L3=5, L4=6, L5=7)
- **Category**: ABILITY
- **Target**: SELF
- **SRD**: As a bonus action, you can expend sorcery points to create a spell slot.

**Event Chain**:
```
ActionEvent(DECLARATION)
 └─ phase_to(EFFECT)
     └─ Decrement sorcery_points, increment spell_slot_X
 └─ phase_to(COMPLETION)
```

---

## Item Use Actions

All item use actions follow the generic pattern:
```
ActionEvent(DECLARATION)
 └─ Validate item-specific preconditions
 └─ phase_to(EXECUTION) → phase_to(EFFECT) → item-specific effect
 └─ phase_to(COMPLETION) → charge consumed
```

| Action | File | Cost | Effect |
|--------|------|------|--------|
| OpenDoorAction | `dnd/items/test_items.py` | Free | Remove door blocking from tile → SPATIAL_OBJECT_CHANGED |
| CloseDoorAction | `dnd/items/test_items.py` | Free | Add door blocking to tile → SPATIAL_OBJECT_CHANGED |
| InteractDoorAction | `dnd/items/test_items.py` | Free | Toggle door open/closed |
| PullLeverAction | `dnd/items/test_items.py` | Free | Toggle lever state (environmental) |
| LootAllAction | `dnd/items/test_items.py` | Free | Transfer all items from chest to inventory |
| DrinkPotionAction | `dnd/items/test_items.py` | 1 action | Heal via potion → HealingEvent |
| DrinkHastePotionAction | `dnd/items/test_items.py` | 1 action | Apply HasteEffect condition |
| DrinkGreaterInvisibilityPotionAction | `dnd/items/test_items.py` | 1 action | Apply GreaterInvisibilityEffect |
| ApplyCoatAction | `dnd/items/test_items.py` | Free | Apply WeaponCoatCondition to equipped weapon |
| IgniteTorchAction | `dnd/items/test_items.py` | Free | Activate light source → SPATIAL_LIGHT_CHANGED |
| ExtinguishTorchAction | `dnd/items/test_items.py` | Free | Deactivate light source → SPATIAL_LIGHT_CHANGED |
| IgniteWallTorchAction | `dnd/items/test_items.py` | Free | Activate wall-mounted light |
| ExtinguishWallTorchAction | `dnd/items/test_items.py` | Free | Deactivate wall light |

---

## Generic Event Chain Summary

| Event Type | Triggered By | Common Handlers |
|------------|-------------|-----------------|
| STEP_MOVEMENT | Move/Jump each cell | OA, Intercept, zone effects |
| ATTACK | Any attack action | Range/LOS validation, damage chain |
| DAMAGE_ROLL_RESULT | After damage dice rolled | GWF reroll, Savage Attacker |
| TAKE_DAMAGE | After damage applied | RelentlessRage, Concentration save |
| CONDITION_APPLICATION | Condition added | Modifier application |
| CONDITION_REMOVAL | Condition removed | Cleanup, reverse links |
| SAVING_THROW | Save needed | Indomitable reroll |
| SKILL_CHECK | Skill check needed | Athletics/Stealth contests |
| SPATIAL_ENTITY_ENTERED | Entity enters cell | Zone spell handlers |
| SPATIAL_ENTITY_LEFT | Entity leaves cell | Zone exit handlers |
| SPATIAL_OBJECT_PLACED | Item placed on ground | Senses update |
| SPATIAL_OBJECT_REMOVED | Item picked up/destroyed | Senses update |
| FORCED_MOVEMENT | Shove push, Thunderwave | Spatial events (NO OA) |
