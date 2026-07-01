# Conditions Reference

Complete catalog of all conditions in the engine. Includes file locations, SRD descriptions, modifier effects, sub-conditions, event handlers, and linkage mechanics.

---

## Core D&D 5e Conditions

### Combat State Markers (Internal)

#### HasAttacked
- **File**: `dnd/conditions.py:31`
- **Type**: Internal marker
- **Duration**: 1 round
- **Description**: Applied when entity uses an attack action. Triggers ExtraAttacksGranted for fighters.
- **Modifiers**: None (pure marker)

#### HasTakenDamage
- **File**: `dnd/conditions.py:60`
- **Type**: Internal marker
- **Duration**: 1 round
- **Description**: Applied when entity takes damage. Prevents Rage from ending (maintenance check).
- **Modifiers**: None (pure marker)

---

### Standard Conditions

#### Blinded
- **File**: `dnd/conditions.py:185`
- **SRD**: A blinded creature can't see and automatically fails any ability check that requires sight. Attack rolls against the creature have advantage, and the creature's attack rolls have disadvantage.
- **Modifiers**:
  - `attack_bonus.self_static`: DISADVANTAGE (own attacks)
  - `ac_bonus.to_target_static`: ADVANTAGE (attacks against this creature)
  - Sight-requiring skills: AUTOMISS
- **Sub-conditions**: None

#### Charmed
- **File**: `dnd/conditions.py:218`
- **SRD**: A charmed creature can't attack the charmer or target them with harmful abilities. The charmer has advantage on social ability checks against the creature.
- **Modifiers**:
  - `attack_bonus.self_contextual`: ContextualAutoHitModifier → AUTOMISS when targeting charmer (callable checks target UUID == charmer UUID)
  - Social skills `to_target_contextual`: ContextualAdvantageModifier → ADVANTAGE for charmer on social checks
- **Event Handlers**: None (contextual logic is in the modifier callables, not separate handlers)

#### Deafened
- **File**: `dnd/conditions.py:307`
- **SRD**: A deafened creature can't hear and automatically fails any ability check that requires hearing.
- **Modifiers**: AUTOMISS on hearing-requiring skills

#### Frightened
- **File**: `dnd/conditions.py:377`
- **SRD**: A frightened creature has disadvantage on ability checks and attack rolls while the source of its fear is within line of sight. The creature can't willingly move closer to the source of its fear.
- **Modifiers** (all contextual — only active when frightener is in `senses.entities`):
  - `attack_bonus.self_contextual`: ContextualAdvantageModifier → DISADVANTAGE when frightener visible
  - All skills `self_contextual`: ContextualAdvantageModifier → DISADVANTAGE when frightener visible
  - `action_economy.movement.self_contextual`: max constraint = 0 when frightener visible (callable checks `frightener_uuid in senses.entities`)
- **Event Handlers**: None (all logic in contextual modifier callables)

#### Grappled
- **File**: `dnd/conditions.py:441`
- **SRD**: A grappled creature's speed becomes 0, and it can't benefit from any bonus to its speed.
- **Modifiers**: `movement.self_static`: max constraint = 0

#### Incapacitated
- **File**: `dnd/conditions.py:462`
- **SRD**: An incapacitated creature can't take actions or reactions.
- **Modifiers**:
  - `action_economy.actions.self_static`: set to 0
  - `action_economy.bonus_actions.self_static`: set to 0
  - `action_economy.reactions.self_static`: set to 0
  - `action_economy.movement.self_static`: set to 0

#### Invisible
- **File**: `dnd/conditions.py:494`
- **SRD**: An invisible creature is impossible to see without the aid of magic or a special sense. The creature has advantage on attack rolls. Attack rolls against it have disadvantage.
- **Modifiers**:
  - `attack_bonus.self_static`: ADVANTAGE (unseen attacker)
  - Observers' attacks: DISADVANTAGE (contextual, based on senses)
- **BaseBlock flags**: `is_invisible = True`
- **Note**: Three variants exist sharing `name="Invisible"`:
  - `Invisible` (base, permanent)
  - `InvisibilityEffect` (spell, breaks on attack/spell)
  - `GreaterInvisibilityEffect` (spell, Stealth check to maintain)

#### Paralyzed
- **File**: `dnd/conditions.py:555`
- **SRD**: A paralyzed creature is incapacitated and can't move or speak. It automatically fails STR and DEX saves. Attack rolls against it have advantage. Any attack that hits within 5ft is a critical hit.
- **Modifiers**:
  - STR/DEX saves: auto-fail (AUTOMISS)
  - `ac_bonus.to_target_static`: ADVANTAGE (attacks against)
  - Melee within 5ft: AUTOCRIT
- **Sub-conditions**: Incapacitated
- **Event Handlers**: Auto-crit handler for melee within 5ft

#### Petrified
- **File**: `dnd/conditions.py` (implements Paralyzed-like effects + damage resistance)
- **SRD**: A petrified creature is transformed, along with nonmagical objects, into a solid substance. Weight increases ×10, stops aging. Incapacitated, can't move/speak, unaware. Auto-fail STR/DEX saves. Resistance to all damage. Immune to poison and disease.
- **Sub-conditions**: Incapacitated
- **Modifiers**: All damage RESISTANCE, poison IMMUNITY

#### Poisoned
- **File**: `dnd/conditions.py:628`
- **SRD**: A poisoned creature has disadvantage on attack rolls and ability checks.
- **Modifiers**:
  - `attack_bonus.self_static`: DISADVANTAGE
  - All skill checks: DISADVANTAGE (self_static)

#### Prone
- **File**: `dnd/conditions.py:655`
- **SRD**: A prone creature's only movement option is to crawl. The creature has disadvantage on attack rolls. An attack roll against it has advantage if the attacker is within 5ft; otherwise disadvantage.
- **Modifiers**:
  - `attack_bonus.self_static`: DISADVANTAGE (own attacks)
  - `ac_bonus.to_target_contextual`: ADVANTAGE if attacker ≤5ft, DISADVANTAGE if >5ft (uses `prone_distance_advantage` callable)
- **Event Handlers**: None in `_apply()` itself. Auto-stand is registered externally by `setup_standard_actions()` via `_create_prone_auto_stand_handler()` — fires at TURN_START EFFECT, consumes half movement, removes Prone.

#### Restrained
- **File**: `dnd/conditions.py:773`
- **SRD**: A restrained creature's speed becomes 0. Attack rolls against it have advantage. The creature has disadvantage on DEX saves. Its attack rolls have disadvantage.
- **Modifiers**:
  - `movement.self_static`: max constraint = 0
  - `attack_bonus.self_static`: DISADVANTAGE
  - `ac_bonus.to_target_static`: ADVANTAGE (attacks against)
  - DEX saves: DISADVANTAGE (self_static)

#### Stunned
- **File**: `dnd/conditions.py:729`
- **SRD**: A stunned creature is incapacitated, can't move, and can speak only falteringly. Auto-fails STR and DEX saves. Attack rolls against it have advantage.
- **Modifiers**:
  - STR/DEX saves: AUTOMISS (auto-fail)
  - `ac_bonus.to_target_static`: ADVANTAGE (attacks have advantage)
  - Note: Unlike Paralyzed, Stunned does NOT grant auto-crit within 5ft
- **Sub-conditions**: Incapacitated

#### Unconscious
- **File**: `dnd/conditions.py:811`
- **SRD**: An unconscious creature is incapacitated, can't move or speak, and is unaware. It drops what it's holding and falls prone. Auto-fails STR/DEX saves. Attacks have advantage. Melee within 5ft is auto-crit.
- **Modifiers** (combines Paralyzed + Prone patterns):
  - STR/DEX saves: AUTOMISS (auto-fail)
  - `ac_bonus.to_target_static`: ADVANTAGE (all attacks have advantage)
  - `ac_bonus.to_target_contextual`: AUTOCRIT within 5ft (uses `Paralyzed.paralyzed_distance_critical`)
  - `ac_bonus.to_target_contextual`: ADVANTAGE ≤5ft / DISADVANTAGE >5ft (uses `Prone.prone_distance_advantage`)
- **Sub-conditions**: Incapacitated

#### Dead
- **File**: `dnd/conditions.py:874`
- **Description**: Entity cannot act. Removes from encounter.
- **Sub-conditions**: Incapacitated
- **Modifiers**: None (action economy handled by Incapacitated sub-condition)
- **Side effects**: Calls `grid.cleanup_block_light_sources(target_entity_uuid)` to remove light sources
- **Duration**: Permanent

---

### Action Status Conditions

#### Dashing
- **File**: `dnd/conditions.py:280`
- **Duration**: 1 round
- **Description**: Applied by Dash action. Grants extra movement equal to base speed.
- **Modifiers**: `movement.self_static`: +base_movement feet

#### Dodging
- **File**: `dnd/conditions.py:329`
- **Duration**: 1 round
- **Description**: Applied by Dodge action. Attackers have disadvantage, advantage on DEX saves.
- **Modifiers**:
  - `equipment.ac_bonus.to_target_static`: DISADVANTAGE (attackers have disadvantage)
  - `saving_throws.dexterity.bonus.self_static`: ADVANTAGE (on DEX saves)

#### Disengaging
- **File**: `dnd/conditions.py:356`
- **Duration**: 1 round
- **Description**: Applied by Disengage action. Movement doesn't provoke opportunity attacks.
- **Modifiers**: None (checked by OA handler)

#### NoReactions
- **File**: `dnd/conditions.py:1297`
- **Duration**: Varies
- **Description**: Applied by Shocking Grasp and other effects. Cannot take reactions.
- **Modifiers**: `reactions.self_static`: max constraint = 0

---

### Concentration & Stealth

#### Concentrating
- **File**: `dnd/conditions.py:999`
- **Description**: Tracks concentration on a spell. Limited to one spell at a time. Breaks on damage (CON save), new concentration spell, death, or incapacitation.
- **Modifiers**: None (tracking condition)
- **Linked conditions**: Spell effect conditions on targets (via `add_linked_condition`)
- **Child removal policy**: `"last"` — auto-removes when last linked spell effect is removed
- **Event Handlers**: Single handler with two triggers:
  - `TAKE_DAMAGE` (EFFECT) → CON save DC = max(10, damage/2), removes on fail
  - `DEATH` (EFFECT) → auto-removes without save
- **Special**: Multi-slot support via `concentration_slots` dict and `drop_slot()` method

#### ConcentrationActionMarker
- **File**: `dnd/conditions.py:1272`
- **Description**: Tracks action-grant concentration spells (Call Lightning, Sunbeam). Manages bonus action spell templates.
- **Modifiers**: None
- **Event Handlers**: Action deregistration on removal

#### Hidden
- **File**: `dnd/conditions.py:1338`
- **Description**: Hidden from observers. Applied by Hide action. Grants unseen attacker advantage. Breaks on many triggers.
- **Modifiers**: `attack_bonus.self_contextual`: ADVANTAGE (unseen attacker, via contextual callable)
- **BaseBlock flags**: `stealth_dc` = Stealth check result
- **Event Handlers**: Reveal handler with 8 trigger types:
  1. `ATTACK` (EFFECT) — source is hidden entity
  2. `TAKE_DAMAGE` (EFFECT) — target is hidden entity
  3. `CONDITION_APPLICATION` (EFFECT) — target is hidden entity (e.g., Incapacitated)
  4. `CAST_SPELL` (EFFECT) — source is hidden entity
  5. `BASE_ACTION` (EFFECT) — source is hidden entity (filtered by NON_REVEALING_ACTIONS)
  6. `SPATIAL_LIGHT_CHANGED` (EFFECT) — any light change
  7. `SPATIAL_ENTITY_ENTERED` (EFFECT) — hidden entity enters new cell
  8. `MOVEMENT_COLLISION` (EFFECT) — collision with another entity
- **Special**: `creation_lineage_uuid` prevents self-triggering; `NON_REVEALING_ACTIONS` whitelist (Dash, Dodge, Disengage, Hide, Stand Up, Drop Prone)

#### InvisibilityEffect
- **File**: `dnd/conditions.py:1494`
- **Description**: Spell-based invisibility. Breaks on attack or spell cast.
- **Modifiers**: ADVANTAGE on own attacks, is_invisible flag
- **Event Handlers**: Reveal handler (attack/spell cast removes condition)
- **Source**: Invisibility spell

#### GreaterInvisibilityEffect
- **File**: `dnd/conditions.py:1600`
- **Description**: BG3-style Greater Invisibility. On non-whitelisted action, rolls Stealth check vs escalating DC (base 15) to maintain.
- **Modifiers**: Same as InvisibilityEffect
- **Event Handlers**: Action handler with DC escalation
- **Source**: Greater Invisibility spell

---

## Tile & Zone Conditions

#### TileEffectCondition
- **File**: `dnd/tile_conditions.py:45`
- **Type**: Base class for tile conditions
- **Applied to**: Tiles (target_entity_uuid = tile.uuid)
- **Description**: Base class for all conditions applied to tiles by zone spells.

#### ZoneControlCondition
- **File**: `dnd/tile_conditions.py:122`
- **Type**: Zone spell infrastructure
- **Applied to**: Caster entity
- **Description**: Controls a zone of tile effects. Manages affected positions, spatial handlers (entry/exit/turn), difficult terrain, light modifiers, and tile markers.
- **Features**:
  - `affected_positions: Set[Tuple[int, int]]`
  - Entry/exit/turn-start spatial handlers (O(1) lookup)
  - Terrain modifiers (difficult terrain)
  - Light modifiers (zone illumination)
  - Tile markers (ZoneMarkerCondition for display)
  - Globe of Invulnerability filtering
- **Linked conditions**: Spell effects on targets
- **Spatial handlers**: Registered at each affected position

---

## Spell Effect Conditions

### Evocation Spell Effects

#### RayOfFrostEffect
- **File**: `dnd/spells/evocation.py:177`
- **Source**: Ray of Frost cantrip
- **Effect**: -10ft speed to target (tracked via `affected_target_uuid` on caster condition)
- **Duration**: 1 round

#### GuidingBoltMarked
- **File**: `dnd/spells/evocation.py:2263`
- **Source**: Guiding Bolt
- **Effect**: Next attack against target has ADVANTAGE
- **Duration**: Until next attack or 1 round

#### LightEffect
- **File**: `dnd/spells/evocation.py:3755`
- **Source**: Light cantrip
- **Effect**: Object emits bright light (20ft) + dim light (20ft)
- **Modifiers**: Light level on object

#### SunburstBlindedEffect
- **File**: `dnd/spells/evocation.py:1824`
- **Source**: Sunburst
- **Effect**: Blinded (1 round)
- **Sub-conditions**: Blinded

#### PrismaticRestrained
- **File**: `dnd/spells/evocation.py:3297`
- **Source**: Prismatic Spray (Indigo ray)
- **Effect**: Restrained
- **Sub-conditions**: Restrained

#### DivineWordEffect
- **File**: `dnd/spells/evocation.py:4521`
- **Source**: Divine Word
- **Effect**: HP-dependent (Stunned / Blinded+Deafened / Prone)

---

### Enchantment Spell Effects

#### HoldPersonEffect
- **File**: `dnd/spells/enchantment.py:207`
- **Source**: Hold Person
- **Effect**: Paralysis on humanoid. Repeat WIS save at TURN_END.
- **Sub-conditions**: Paralyzed (which includes Incapacitated)
- **Linked to**: Concentrating on caster (reverse link, policy="last")
- **Event Handlers**: Repeat save at turn end

#### HoldMonsterEffect
- **File**: `dnd/spells/enchantment.py:470`
- **Source**: Hold Monster
- **Effect**: Same as HoldPersonEffect but works on any creature type
- **Sub-conditions**: Paralyzed

#### SleepEffect
- **File**: `dnd/spells/enchantment.py:882`
- **Source**: Sleep
- **Effect**: Unconscious (no save, HP-pool based)
- **Sub-conditions**: Unconscious
- **Removal**: When target takes damage

#### PowerWordStunEffect
- **File**: `dnd/spells/enchantment.py:1119`
- **Source**: Power Word Stun
- **Effect**: Stunned (no initial save, HP threshold)
- **Sub-conditions**: Stunned
- **Event Handlers**: Repeat CON save at turn end

#### BaneEffect
- **File**: `dnd/spells/enchantment.py:1343`
- **Source**: Bane
- **Effect**: -1d4 penalty on attack rolls and saving throws
- **Modifiers**: Handler-based d4 subtraction on D20_ROLL_RESULT

#### BlessEffect
- **File**: `dnd/spells/enchantment.py:1389`
- **Source**: Bless
- **Effect**: +1d4 bonus on attack rolls and saving throws
- **Modifiers**: Handler-based d4 addition on D20_ROLL_RESULT

#### CommandGrovelEffect
- **File**: `dnd/spells/enchantment.py:1589`
- **Source**: Command ("Grovel")
- **Effect**: Falls prone at end of turn
- **Duration**: 1 round

#### CommandHaltEffect
- **File**: `dnd/spells/enchantment.py:1624`
- **Source**: Command ("Halt")
- **Effect**: Speed = 0
- **Modifiers**: `movement.self_static`: max constraint = 0

#### CommandFleeEffect
- **File**: `dnd/spells/enchantment.py:1659`
- **Source**: Command ("Flee")
- **Effect**: Must Dash away from caster
- **Duration**: 1 round

---

### Abjuration Spell Effects

#### ShieldBuff
- **File**: `dnd/spells/abjuration.py:49`
- **Source**: Shield (reaction spell)
- **Effect**: +5 AC until start of next turn
- **Modifiers**: `ac_bonus.self_static`: +5 NumericalModifier
- **Duration**: 1 round (non-concentration)

#### MageArmorCondition
- **File**: `dnd/spells/abjuration.py:284`
- **Source**: Mage Armor
- **Effect**: AC = 13 + DEX (when not wearing armor)
- **Duration**: 8 hours

#### ProtectionFromEnergyEffect
- **File**: `dnd/spells/abjuration.py:487`
- **Source**: Protection from Energy
- **Effect**: RESISTANCE to chosen damage type
- **Modifiers**: ResistanceModifier for selected type

#### StoneskinEffect
- **File**: `dnd/spells/abjuration.py:628`
- **Source**: Stoneskin
- **Effect**: Damage reduction for nonmagical BPS (handler reduces by 10)
- **Event Handlers**: TAKE_DAMAGE handler reduces nonmagical physical damage

#### GlobeZone
- **File**: `dnd/spells/abjuration.py:866`
- **Source**: Globe of Invulnerability
- **Effect**: Blocks spells ≤5th level from outside
- **Event Handlers**: Intercepts spell events from outside the zone

#### BanishedCondition
- **File**: `dnd/spells/abjuration.py:1117`
- **Source**: Banishment
- **Effect**: Removes entity from battlefield. Repeat CHA save at turn end.
- **Event Handlers**: Repeat save, return on success

#### ProtectionFromPoisonEffect
- **File**: `dnd/spells/abjuration.py:1515`
- **Source**: Protection from Poison
- **Effect**: Poison IMMUNITY

#### DeathWardEffect
- **File**: `dnd/spells/abjuration.py:1623`
- **Source**: Death Ward
- **Effect**: First time target drops to 0 HP, it drops to 1 HP instead
- **Event Handlers**: TAKE_DAMAGE handler, single-use

#### FreedomOfMovementEffect
- **File**: `dnd/spells/abjuration.py:1749`
- **Source**: Freedom of Movement
- **Effect**: Unaffected by difficult terrain, grapple, restrain, paralysis
- **Modifiers**: Immunity to movement-restricting conditions

#### ResistanceEffect
- **File**: `dnd/spells/abjuration.py:1873`
- **Source**: Resistance cantrip
- **Effect**: +1d4 to one saving throw (one-use, then auto-removes)

#### ShieldOfFaithEffect
- **File**: `dnd/spells/abjuration.py:1958`
- **Source**: Shield of Faith
- **Effect**: +2 AC
- **Modifiers**: `ac_bonus.self_static`: +2 NumericalModifier

#### AidEffect
- **File**: `dnd/spells/abjuration.py:2049`
- **Source**: Aid
- **Effect**: +5 max HP and current HP (+5 per upcast above 2nd)

#### SanctuaryEffect
- **File**: `dnd/spells/abjuration.py:2145`
- **Source**: Sanctuary
- **Effect**: Attacker must make WIS save or can't attack target
- **Event Handlers**: ATTACK at DECLARATION, WIS save for attacker

#### BeaconOfHopeEffect
- **File**: `dnd/spells/abjuration.py:2323`
- **Source**: Beacon of Hope
- **Effect**: Advantage on WIS saves and death saves, maximize healing received

#### AntimagicSuppression
- **File**: `dnd/spells/abjuration.py:2471`
- **Source**: Antimagic Field
- **Effect**: Suppresses magical effects on the target

#### AntimagicFieldZone
- **File**: `dnd/spells/abjuration.py:2529`
- **Source**: Antimagic Field
- **Effect**: 10ft zone that cancels all magic (spells, conditions, items)
- **Event Handlers**: Intercepts CAST_SPELL, CONDITION_APPLICATION

---

### Transmutation Spell Effects

#### SlowedEffect
- **File**: `dnd/spells/transmutation.py:208`
- **Source**: Slow
- **Effect**: Half speed, -2 AC, -2 DEX saves, no reactions, action/bonus lockout, one attack/turn
- **Modifiers**: Multiple (speed, AC, DEX saves, reactions, action economy)
- **Event Handlers**: Repeat WIS save at turn end, action/bonus lockout handler

#### HasteEffect
- **File**: `dnd/spells/transmutation.py:648`
- **Source**: Haste
- **Effect**: ×2 speed, +2 AC, ADVANTAGE on DEX saves, extra action per turn
- **Modifiers**: Speed doubler, AC +2, DEX save advantage
- **Event Handlers**: Extra action granter
- **Special**: On removal → applies Lethargy (can't move/act, 1 round)

#### DarkvisionEffect
- **File**: `dnd/spells/transmutation.py:923`
- **Source**: Darkvision spell
- **Effect**: Adds DARKVISION sense mode (60ft)
- **Triggers**: SPATIAL_PERCEIVABILITY_CHANGED on application

#### JumpEffect
- **File**: `dnd/spells/transmutation.py:1143`
- **Source**: Jump spell
- **Effect**: Triple jump distance
- **Modifiers**: Jump distance multiplier

#### ExpeditiousRetreatEffect
- **File**: `dnd/spells/transmutation.py:1287`
- **Source**: Expeditious Retreat
- **Effect**: Grants repeatable Dash as bonus action
- **Event Handlers**: Bonus action Dash template registered

#### EnhanceAbilityEffect
- **File**: `dnd/spells/transmutation.py:1361`
- **Source**: Enhance Ability
- **Effect**: ADVANTAGE on checks for chosen ability
- **Event Handlers**: Handler adds advantage on matching ability checks

#### EnlargeReduceEffect
- **File**: `dnd/spells/transmutation.py:1494`
- **Source**: Enlarge/Reduce
- **Effect**: Enlarge: +1d4 damage, STR +4, speed +5ft. Reduce: -1d4 damage, STR -4, speed -5ft.

#### RegeneratingEffect
- **File**: `dnd/spells/transmutation.py:1991`
- **Source**: Regenerate
- **Effect**: 4d8+15 HP healing at each turn start
- **Event Handlers**: TURN_START handler rolls healing

---

### Conjuration Spell Effects

#### WebRestrained
- **File**: `dnd/spells/conjuration.py:891`
- **Source**: Web
- **Effect**: Restrained. Can use action for STR save to escape.
- **Sub-conditions**: Restrained
- **Event Handlers**: STR save escape action

#### SpiritGuardiansTriggered
- **File**: `dnd/spells/conjuration.py:1601`
- **Source**: Spirit Guardians
- **Effect**: Damage applied on zone entry (3d8 radiant, WIS save half)

#### SpiritGuardiansSlowed
- **File**: `dnd/spells/conjuration.py:1652`
- **Source**: Spirit Guardians
- **Effect**: Half speed while in zone

#### NauseatedCondition
- **File**: `dnd/spells/conjuration.py:2895`
- **Source**: Stinking Cloud / other
- **Effect**: Disadvantage on attacks and ability checks (sickened-like)

#### GuardianWarded
- **File**: `dnd/spells/conjuration.py:3389`
- **Source**: Guardian of Faith / Warding Bond
- **Effect**: Damage mitigation from guardian spirit

#### HeroesFeastBuff
- **File**: `dnd/spells/conjuration.py:3646`
- **Source**: Heroes' Feast
- **Effect**: Temp HP, advantage on WIS saves, immunity to poison/frightened

---

### Necromancy Spell Effects

#### NoHealing
- **File**: `dnd/spells/necromancy.py:103`
- **Source**: Chill Touch
- **Effect**: Prevents all HP restoration
- **Event Handlers**: Blocks healing events

#### ChillTouchEffect
- **File**: `dnd/spells/necromancy.py:141`
- **Source**: Chill Touch
- **Effect**: Tracks NoHealing on target + undead disadvantage vs caster
- **Linked conditions**: NoHealing on target
- **Duration**: 1 round

#### BlindnessDeafnessEffect
- **File**: `dnd/spells/necromancy.py:549`
- **Source**: Blindness/Deafness
- **Effect**: Blinded OR Deafened (chosen at cast)
- **Sub-conditions**: Blinded or Deafened
- **Event Handlers**: Repeat CON save at turn end

#### SickenedCondition
- **File**: `dnd/spells/necromancy.py:907`
- **Source**: Various necromancy spells
- **Effect**: Disadvantage on attacks and saves

#### EyebiteAsleepEffect
- **File**: `dnd/spells/necromancy.py:1004`
- **Source**: Eyebite (Asleep)
- **Effect**: Unconscious
- **Sub-conditions**: Unconscious

#### EyebitePanickedEffect
- **File**: `dnd/spells/necromancy.py:1068`
- **Source**: Eyebite (Panicked)
- **Effect**: Frightened, must Dash away
- **Sub-conditions**: Frightened

#### AbilityCurseEffect
- **File**: `dnd/spells/necromancy.py:1677`
- **Source**: Bestow Curse
- **Effect**: Disadvantage on ability checks with chosen ability

#### AttackCurseEffect
- **File**: `dnd/spells/necromancy.py:1727`
- **Source**: Bestow Curse
- **Effect**: Disadvantage on attack rolls against caster

#### InactionCurseEffect
- **File**: `dnd/spells/necromancy.py:1778`
- **Source**: Bestow Curse
- **Effect**: WIS save at turn start or lose action

#### DamageCurseEffect
- **File**: `dnd/spells/necromancy.py:1920`
- **Source**: Bestow Curse
- **Effect**: Extra necrotic damage on caster's attacks against target

---

### Illusion Spell Effects

#### BlurEffect
- **File**: `dnd/spells/illusion.py:27`
- **Source**: Blur
- **Effect**: Attackers have DISADVANTAGE
- **Modifiers**: `ac_bonus.to_target_static`: DISADVANTAGE

#### FearEffect
- **File**: `dnd/spells/illusion.py:125`
- **Source**: Fear
- **Effect**: Frightened + must Dash away
- **Sub-conditions**: Frightened
- **Event Handlers**: Repeat save at turn end (only if can't see caster)

#### HypnoticPatternEffect
- **File**: `dnd/spells/illusion.py:338`
- **Source**: Hypnotic Pattern
- **Effect**: Charmed + Incapacitated
- **Sub-conditions**: Charmed, Incapacitated
- **Event Handlers**: Repeat WIS save at turn start

#### ColorSprayEffect
- **File**: `dnd/spells/illusion.py:542`
- **Source**: Color Spray
- **Effect**: Blinded (HP-pool based, like Sleep)

#### MirrorImageEffect
- **File**: `dnd/spells/illusion.py:897`
- **Source**: Mirror Image
- **Effect**: AC-based, not d20-based. Adds +9 AC (3 duplicates × +3 each). When an attack misses (due to boosted AC), one duplicate is consumed and AC drops by 3. Condition removed when all duplicates gone.
- **Modifiers**: `ac_bonus.self_static`: +9 NumericalModifier (dynamically updated: 9→6→3→0)
- **Event Handlers**: ATTACK miss handler — decrements duplicates on miss, updates AC modifier

#### _SilenceDeafened
- **File**: `dnd/spells/illusion.py:1241`
- **Source**: Silence zone
- **Effect**: Deafened while in Silence zone

---

### Divination Spell Effects

#### SeeInvisibilityEffect
- **File**: `dnd/spells/divination.py:23`
- **Source**: See Invisibility
- **Effect**: SEE_INVISIBLE sense mode
- **Duration**: 10 rounds

#### TrueSeeingEffect
- **File**: `dnd/spells/divination.py:102`
- **Source**: True Seeing
- **Effect**: TRUESIGHT sense mode (120ft range)
- **Duration**: 10 rounds

#### GuidanceEffect
- **File**: `dnd/spells/divination.py:225`
- **Source**: Guidance cantrip
- **Effect**: +1d4 to one ability check (one-use, auto-removes after firing)
- **Event Handlers**: D20_ROLL_RESULT handler, fires once

---

## Class Feature Conditions

### Fighter Features (`dnd/classes/fighter.py`)

#### FightingStyleArchery
- **File**: `:80` | **Level**: 1
- **Effect**: +2 ranged attack bonus
- **Modifiers**: `attack_bonus.self_static`: +2 for ranged attacks

#### FightingStyleDefense
- **File**: `:159` | **Level**: 1
- **Effect**: +1 AC while wearing armor
- **Modifiers**: `ac_bonus.self_static`: +1

#### FightingStyleDueling
- **File**: `:256` | **Level**: 1
- **Effect**: +2 damage when wielding single melee weapon
- **Event Handlers**: DAMAGE_ROLL_RESULT, adds +2 damage contextually

#### GreatWeaponFighting
- **File**: `:379` | **Level**: 1
- **Effect**: Reroll damage dice of 1 or 2 (two-handed weapons)
- **Event Handlers**: DAMAGE_ROLL_RESULT, rerolls low dice

#### FightingStyleProtection
- **File**: `:540` | **Level**: 1
- **Effect**: +1 AC to adjacent allies when wielding shield
- **Event Handlers**: Applies AC bonus to allies within 5ft

#### FightingStyleTwoWeaponFighting
- **File**: `:644` | **Level**: 1
- **Effect**: Add ability modifier to off-hand damage
- **Event Handlers**: DAMAGE_ROLL_RESULT for off-hand attacks

#### SecondWindFeature
- **File**: `:812` | **Level**: 1
- **Effect**: Registers SecondWind action (1d10+level healing, bonus action, 1/short rest)

#### ActionSurging
- **File**: `:883` | **Level**: 2
- **Duration**: 1 round
- **Effect**: +1 action this turn (marker condition)
- **Modifiers**: `action_economy.actions.self_static`: +1

#### ActionSurgeFeature
- **File**: `:1017` | **Level**: 2
- **Effect**: Registers ActionSurge action

#### ImprovedCritical
- **File**: `:1088` | **Level**: 3 (Champion)
- **Effect**: Critical hit on 19-20
- **Modifiers**: Lowers crit threshold to 19

#### ExtraAttacksGranted
- **File**: `:1150` | **Level**: 5
- **Duration**: 1 round
- **Effect**: Marker that enables ExtraAttack actions

#### ExtraAttackFeature
- **File**: `:1389` | **Level**: 5
- **Effect**: Registers ExtraAttack action + HasAttacked handler

#### Indomitable
- **File**: `:1559` | **Level**: 9
- **Effect**: Reroll failed saving throw (1/long rest, scales to 3/long rest at L17)
- **Event Handlers**: SAVING_THROW at EFFECT, rerolls on fail

#### SuperiorCritical
- **File**: `:1622` | **Level**: 15 (Champion)
- **Effect**: Critical hit on 18-20
- **Modifiers**: Lowers crit threshold to 18

#### Survivor
- **File**: `:1743` | **Level**: 18 (Champion)
- **Effect**: Regain 5 + CON mod HP at turn start if below half HP
- **Event Handlers**: TURN_START handler

---

### Barbarian Features (`dnd/classes/barbarian.py`, `dnd/classes/rage.py`)

#### Raging
- **File**: `rage.py:264` | **Level**: 1
- **Effect**: +2/3/4 melee damage, RESISTANCE to bludgeoning/piercing/slashing
- **Modifiers**: Damage bonus (scales with level), physical damage resistance
- **Event Handlers**: Maintenance handler (ends rage if no attack/damage taken last round)

#### RageFeature
- **File**: `rage.py:612` | **Level**: 1
- **Effect**: Registers Rage action

#### RecklessAttacking
- **File**: `barbarian.py:140` | **Level**: 2
- **Duration**: 1 round
- **Effect**: ADVANTAGE on own attacks, ADVANTAGE on attacks against
- **Modifiers**:
  - `attack_bonus.self_static`: ADVANTAGE
  - `ac_bonus.to_target_static`: ADVANTAGE

#### RecklessAttackFeature
- **File**: `barbarian.py:272` | **Level**: 2
- **Effect**: Registers RecklessAttack action

#### DangerSense
- **File**: `barbarian.py:366` | **Level**: 2
- **Effect**: ADVANTAGE on DEX saves when you can see the source
- **Modifiers**: DEX saves: contextual ADVANTAGE

#### FastMovement
- **File**: `barbarian.py:449` | **Level**: 5
- **Effect**: +10ft speed when not in heavy armor
- **Modifiers**: `movement.self_static`: +10

#### MindlessRage
- **File**: `barbarian.py:519` | **Level**: 6
- **Effect**: Immune to Charmed and Frightened while raging
- **Event Handlers**: Blocks Charmed/Frightened condition application during rage

#### FeralInstinct
- **File**: `barbarian.py:583` | **Level**: 7
- **Effect**: ADVANTAGE on initiative rolls
- **Modifiers**: Initiative: ADVANTAGE

#### BrutalCritical
- **File**: `barbarian.py:644` | **Level**: 9/13/17
- **Effect**: +1/2/3 extra weapon damage dice on critical hits
- **Event Handlers**: DAMAGE_ROLL_RESULT, adds dice on crit

#### RelentlessRage
- **File**: `barbarian.py:770` | **Level**: 11
- **Effect**: When reduced to 0 HP while raging, CON save (DC 10, +5 each use) to drop to 1 HP instead
- **Event Handlers**: TAKE_DAMAGE handler, CON save to survive

#### PersistentRage
- **File**: `barbarian.py:850` | **Level**: 15
- **Effect**: Rage doesn't end from maintenance check (only ends on long rest or voluntary)
- **Modifiers**: Overrides rage maintenance handler

#### Retaliation
- **File**: `barbarian.py:1120` | **Level**: 14 (Berserker)
- **Effect**: Reaction melee attack when damaged by creature within 5ft
- **Event Handlers**: TAKE_DAMAGE at EFFECT, makes melee attack

#### IndomitableMight
- **File**: `barbarian.py:942` | **Level**: 18
- **Effect**: STR checks minimum result = 10
- **Modifiers**: STR check minimum value modifier

#### PrimalChampion
- **File**: `barbarian.py:989` | **Level**: 20
- **Effect**: STR +4, CON +4, unlimited rage uses

#### Frenzied
- **File**: `rage.py:707` | **Level**: 3 (Berserker)
- **Effect**: Bonus action melee attack while raging (grants FrenziedStrike template)
- **Parent condition**: Raging (sub-condition)

#### FrenzyFeature
- **File**: `rage.py:1026` | **Level**: 3 (Berserker)
- **Effect**: Registers Frenzy action

#### IntimidatingPresenceFeature
- **File**: `barbarian.py:1548` | **Level**: 10 (Berserker)
- **Effect**: Registers IntimidatingPresence and ExtendIntimidatingPresence actions

#### IntimidatingPresenceImmunity
- **File**: `barbarian.py:1168` | **Level**: 10 (Berserker)
- **Duration**: 24 hours
- **Effect**: Marker preventing re-use of Intimidating Presence on this target

---

### Sorcerer Features (`dnd/classes/sorcerer.py`)

#### DraconicResilience
- **File**: `:43` | **Level**: 1 (Draconic Origin)
- **Effect**: AC = 13 + DEX (natural armor), resistance to draconic damage type

#### ElementalAffinity
- **File**: `:100` | **Level**: 6 (Draconic Origin)
- **Effect**: +CHA modifier to damage for spells matching draconic element
- **Event Handlers**: DAMAGE_ROLL_RESULT, adds CHA mod for matching damage type

#### MetamagicActive
- **File**: `:144`
- **Duration**: No explicit duration — removed by CAST_SPELL event handler when next spell is cast
- **Effect**: Active metamagic modifier. Stores `metamagic_type` ("quickened", "twinned", "distant") and applies action overrides to next spell.
- **Types**:
  - `quickened`: `alt_cost_type = "bonus_actions"`
  - `twinned`: `alt_target_type = MULTI_ENTITY, alt_target_count = 2`
  - `distant`: `alt_range = range × 2`

#### SorceryPointsFeature
- **File**: `:563`
- **Effect**: Tracks sorcery points resource, registers ConvertSlotToSP and ConvertSPToSlot actions

---

### Feat Conditions (`dnd/classes/feats.py`)

#### LuckyFeature
- **File**: `:65`
- **Effect**: 3 luck points per long rest. Can reroll any d20 (attack, save, ability check) and choose either result.
- **Event Handlers**: D20_ROLL_RESULT handler, spends luck point to reroll

---

## Monster & NPC Conditions

### Skeleton Abilities (`dnd/monsters/skeleton_abilities.py`)

#### Marked
- **File**: `:29`
- **Effect**: Skeleton mark target — bonus damage on attacks against marked target

#### MarkCooldown
- **File**: `:98`
- **Effect**: Prevents re-marking same target (cooldown timer)

### Circus Fighter (`dnd/monsters/circus_fighter_conditions.py`)

#### DualWielder
- **File**: `:143`
- **Effect**: Dual wield fighting feature (extra off-hand attack)

#### ElementalWeaponMastery
- **File**: `:164`
- **Effect**: Adds elemental damage to weapon attacks

#### ElementalAffinity (Monster)
- **File**: `:185`
- **Effect**: Elemental damage bonus (different from Sorcerer's)

#### CircusPerformer
- **File**: `:217`
- **Effect**: Trick abilities (acrobatic combat maneuvers)

#### Tired
- **File**: `:349`
- **Effect**: Tiredness/exhaustion marker (reduced stats)

---

## Item & Reaction Conditions

#### WeaponCoatCondition
- **File**: `dnd/items/test_items.py:727`
- **Effect**: Weapon coating that adds bonus damage or effects to weapon attacks
- **Duration**: Limited hits or time

#### Intercepting
- **File**: `dnd/items/test_reactions.py:145`
- **Duration**: 1 round
- **Effect**: Stores charge destination for Intercept reaction. When enemy enters the cell, interceptor charges and attacks.
- **Event Handlers**: STEP_MOVEMENT handler at the charge destination position

#### DodgeRollFeature
- **File**: `dnd/items/test_reactions.py:353`
- **Effect**: Registers DodgeRoll reaction (move away from attacker, impose disadvantage)
- **Event Handlers**: ATTACK at EXECUTION phase

---

## Condition Architecture Summary

### Sub-conditions vs Linked Conditions

| Type | Location | Example | Cleanup |
|------|----------|---------|---------|
| **Sub-conditions** | Same entity | Paralyzed → Incapacitated | Parent removal cascades to children |
| **Linked conditions** | Other entities/tiles | Concentrating → HoldPersonEffect | Forward: parent removes linked. Reverse: policy-based parent notification |

### Modifier Placement Guide

| Effect | Channel | Example |
|--------|---------|---------|
| Affects own rolls | `self_static` | Poisoned: disadvantage on attacks |
| Affects own rolls conditionally | `self_contextual` | Frightened: only when frightener visible |
| Affects attackers always | `to_target_static` | Blinded: attackers have advantage |
| Affects attackers conditionally | `to_target_contextual` | Prone: melee=advantage, ranged=disadvantage |
| Numerical bonus/penalty | `self_static.add_value_modifier()` | Dashing: +movement |
| Max constraint | `self_static.add_max_constraint()` | Grappled: speed = 0 |
| Damage resistance | `health.damage_resistances` | Raging: RESISTANCE to BPS |

### _apply() Return Tuple

Every condition's `_apply()` returns:
```python
Tuple[
    List[Tuple[UUID, UUID]],  # (modifiable_value_uuid, modifier_uuid) pairs
    List[UUID],               # event_handler_uuids
    List[UUID],               # sub_condition_uuids
    List[UUID],               # spatial_handler_uuids
    Optional[Event]           # effect completion event
]
```

### Condition Count Summary

| Category | Count |
|----------|-------|
| Core D&D conditions | 25 |
| Tile/Zone infrastructure | 2 |
| Evocation spell effects | 6 |
| Enchantment spell effects | 9 |
| Abjuration spell effects | 16 |
| Transmutation spell effects | 8 |
| Conjuration spell effects | 6 |
| Necromancy spell effects | 10 |
| Illusion spell effects | 6 |
| Divination spell effects | 3 |
| Fighter features | 15 |
| Barbarian features | 18 |
| Sorcerer features | 4 |
| Feats | 1 |
| Monster/NPC | 7 |
| Items/Reactions | 3 |
| **Total** | **~139** |
