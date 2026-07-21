# SRD Trait Implementation Map

This document maps each SRD monster trait in the validation roster to the
closest existing engine implementation and the implemented strategy.

The central rule is: implement traits as engine mechanics, not as policy
exceptions. The AI should discover them through legal actions, modifiers,
conditions, combat logs, subjective observations, and decision epochs.

Status:

- The reusable trait mechanics live in `dnd/monsters/traits.py`.
- The SRD roster wires them through `dnd/monsters/srd_roster.py`.
- Regression coverage lives in `tests/manual/test_53_srd_monster_traits.py`.
- Gnoll Bite is a natural attack action rather than equipment, so spear, shield,
  Bite, and Rampage can coexist without slot compromises.

## Existing Engine Building Blocks

### Event Handlers

Closest files:

- `dnd/core/events.py`
- `dnd/reactions.py`
- `dnd/classes/barbarian.py`
- `dnd/classes/fighter.py`
- `dnd/spells/enchantment.py`
- `dnd/spells/transmutation.py`

Use for:

- conditional attack advantage;
- once-per-turn damage riders;
- reaction AC changes;
- repeat saves;
- death interception;
- turn-start/turn-end cleanup.

Pattern:

```python
handler = EventHandler(
    name="Trait Name",
    source_entity_uuid=entity.uuid,
    event_processor=processor,
    trigger_conditions=[
        Trigger(
            name="Trait Trigger",
            event_type=EventType.DAMAGE_ROLL_RESULT,
            event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=entity.uuid,
        )
    ],
)
entity.add_event_handler(handler)
```

### Conditions

Closest files:

- `dnd/conditions.py`
- `dnd/classes/barbarian.py`
- `dnd/classes/rage.py`
- `dnd/spells/enchantment.py`
- `dnd/spells/abjuration.py`
- `dnd/monsters/skeleton_abilities.py`

Use for:

- temporary self buffs;
- temporary target debuffs;
- linked repeat-save effects;
- aura-style support;
- state markers that reset at turn boundaries;
- once-per-turn usage locks.

### Action Templates

Closest files:

- `dnd/actions.py`
- `dnd/actions_functional.py`
- `dnd/classes/barbarian.py`
- `dnd/classes/fighter.py`
- `dnd/spells/transmutation.py`
- `dnd/monsters/bestiary.py`
- `dnd/monsters/skeleton_abilities.py`

Use for:

- Aggressive;
- Cunning Action;
- Multiattack;
- Divine Eminence;
- Leadership;
- Rampage follow-up actions.

### Spell And Save Riders

Closest files:

- `dnd/actions.py`
- `dnd/spells/enchantment.py`
- `dnd/spells/conjuration.py`
- `dnd/spells/necromancy.py`

Use for:

- Wolf/Dire Wolf prone rider;
- Ghoul paralysis rider;
- repeat saves;
- condition application as child events of an attack.

### Reaction Handlers

Closest files:

- `dnd/reactions.py`
- `dnd/spells/abjuration.py`
- `dnd/items/test_reactions.py`

Use for:

- Parry;
- Shield-like AC decisions;
- future monster reactions.

## Trait Families

## Pack Tactics

Traits:

- Tribal Warrior: Pack Tactics.
- Kobold: Pack Tactics.
- Wolf: Pack Tactics.
- Dire Wolf: Pack Tactics.
- Thug: Pack Tactics.

Nearest existing behavior:

- `Marked` in `dnd/monsters/skeleton_abilities.py` adds attacker advantage
  through target AC modifier channels.
- `Prone` in `dnd/conditions.py` uses contextual attacker advantage based on
  attacker distance.
- Attack modifier propagation in `dnd/actions.py` already pulls target-side
  contextual modifiers into the attacking roll.

Implementation plan:

1. Add `PackTacticsFeature(BaseCondition)` or `register_pack_tactics(entity)`.
2. Register an attack-roll contextual advantage modifier on the actor's own
   attack bonus or a handler around `ATTACK`/`D20_ROLL_RESULT`.
3. Condition function checks:
   - event source is the trait owner;
   - target exists;
   - at least one allied entity is within 5 feet of target;
   - allied entity is not incapacitated/dead;
   - optional: ally is perceivable enough for the trait if desired by engine policy.
4. Return `AdvantageModifier("Pack Tactics", ADVANTAGE)`.

Preferred design:

- Use an `EventHandler` at `EventType.ATTACK`, `EventPhase.DECLARATION` or
  `D20_ROLL_RESULT` if event context exposes the target cleanly.
- If target context propagation is cleaner, use contextual self modifier on
  attack bonus.

Tests:

- no ally adjacent: normal roll;
- ally adjacent: advantage;
- ally incapacitated: normal roll;
- ranged attack with adjacent ally to target: advantage still applies.

## Sunlight Sensitivity

Trait:

- Kobold: Sunlight Sensitivity.

Nearest existing behavior:

- `Blinded`, `Poisoned`, `Frightened`, and `Prone` condition modifiers in
  `dnd/conditions.py`.
- Light and visibility data in `dnd.blocks.sensory` and grid/senses systems.

Implementation plan:

1. Add `SunlightSensitivityFeature`.
2. Add contextual disadvantage to attack rolls when the actor is in sunlight.
3. Add contextual disadvantage to sight-based Perception checks when in sunlight.
4. The first implementation may only trigger when the tile/light system exposes
   a stable sunlight marker. If the engine only distinguishes bright/dim/dark,
   add a TODO note and do not over-trigger on ordinary torchlight.

Tests:

- sunlight tile: attacks at disadvantage;
- dark tile: no disadvantage;
- Perception relying on sight: disadvantage;
- non-sight checks: no disadvantage.

## Dark Devotion And Brave

Traits:

- Cultist: Dark Devotion.
- Cult Fanatic: Dark Devotion.
- Knight: Brave.

Nearest existing behavior:

- Saving throw modifier channels in `dnd/blocks/saving_throws.py`.
- Contextual modifiers in `dnd/core/values.py`.
- `Frightened` and `Charmed` condition classes in `dnd/conditions.py`.
- `ResistanceEffect` and other save-related spell conditions in `dnd/spells`.

Implementation plan:

1. Add `register_save_advantage_against_conditions`.
2. For each relevant saving throw block, add contextual advantage modifier.
3. Context checks the incoming event or effect context for the condition being
   resisted:
   - Dark Devotion: Charmed or Frightened.
   - Brave: Frightened.
4. If current save events do not expose the attempted condition, add explicit
   context on condition-causing spell/action save requests.

Tests:

- Fear/Hypnotic-style frightened save has advantage for Brave.
- Charm save has advantage for Dark Devotion.
- Fireball Dexterity save does not gain advantage.

## Undead Fortitude

Traits:

- Zombie: Undead Fortitude.
- Ogre Zombie: Undead Fortitude.

Nearest existing behavior:

- Damage and death events in `dnd/entity.py` and `dnd/core/events.py`.
- Death Ward in `dnd/spells/abjuration.py`.
- Hit point manipulation in `dnd/blocks/health.py`.
- Damage application logs in `dnd/core/combat_log.py`.

Implementation plan:

1. Add `UndeadFortitudeFeature(BaseCondition)` with an event handler.
2. Trigger on damage application or lethal damage before final death is emitted.
3. Check:
   - target is trait owner;
   - incoming damage reduced HP to 0;
   - damage type is not radiant;
   - hit was not critical.
4. Roll CON save DC `5 + damage_taken`.
5. On success, set HP to 1 and cancel/suppress death continuation.
6. On failure, allow death.

Critical design question:

- The exact interception point must be chosen carefully. If the engine emits
  `TAKE_DAMAGE`, `DAMAGE_APPLIED`, and `DEATH` separately, the cleanest point is
  before `DeathEvent` is finalized but after damage amount is known.

Tests:

- ordinary lethal slashing damage: can survive at 1 HP;
- radiant lethal damage: cannot survive;
- critical lethal damage: cannot survive;
- failed save: death proceeds;
- combat log contains fortitude save result.

## Keen Hearing And Smell / Keen Hearing And Sight

Traits:

- Wolf: Keen Hearing and Smell.
- Dire Wolf: Keen Hearing and Smell.
- Scout: Keen Hearing and Sight.

Nearest existing behavior:

- Skill contextual modifiers in `dnd/blocks/skills.py`.
- Skill sensory requirement lists:
  - `skills_requiring_sight`;
  - `skills_requiring_hearing`.

Implementation plan:

1. Add `KeenSenseFeature(BaseCondition)`.
2. Add contextual advantage to Perception checks.
3. Context checks whether the Perception check relies on hearing, smell, or
   sight.
4. If smell is not represented in check context yet, add a small context
   convention:
   - `{"sense_modes": {"hearing", "smell"}}`;
   - or `{"perception_mode": "hearing"}`.

Tests:

- hearing Perception gains advantage.
- sight Perception gains advantage only for Scout.
- unrelated Perception without matching sense does not.

## Multiattack

Traits:

- Scout: two melee or two ranged attacks.
- Thug: two mace attacks.
- Spy: two melee attacks.
- Bandit Captain: three melee attacks or two ranged dagger attacks.
- Cult Fanatic: two melee attacks.
- Knight: two melee attacks.
- Veteran: two longsword attacks plus shortsword when drawn.

Nearest existing behavior:

- Fighter Extra Attack in `dnd/classes/fighter.py`.
- Haste action limitation in `dnd/spells/transmutation.py`.
- Attack action target validation in `dnd/actions.py`.
- `BaseAction.apply()` and action-cost system in `dnd/core/base_actions.py`.

Implementation plan:

1. Add generic `MultiattackAction(BaseAction)` in `dnd/monsters/traits.py`.
2. It owns an ordered list of attack clauses:
   - weapon slot or weapon name;
   - repeat count;
   - optional target chooser constraints.
3. Validation checks at least the first attack has legal target.
4. Apply:
   - spend one action once;
   - resolve each attack as a child `Attack`;
   - validate each child immediately before execution;
   - skip or cancel remaining attacks if no legal target remains depending on
     selected engine policy.
5. Register variants where SRD gives alternatives:
   - `Scout Multiattack: Shortsword`;
   - `Scout Multiattack: Longbow`;
   - `Bandit Captain Multiattack: Melee`;
   - `Bandit Captain Multiattack: Ranged`;
   - or one row with target options if row serialization supports it well.

Tests:

- one action consumed for all attacks;
- two/three attack events emitted;
- target death after first attack does not produce illegal second attack;
- Veteran extra shortsword requires off-hand shortsword.

## Aggressive

Trait:

- Orc: Aggressive.

Nearest existing behavior:

- `Move`, `Dash`, and `Jump` in `dnd/actions.py`.
- `BonusDash` and `ExpeditiousRetreatEffect` in `dnd/spells/transmutation.py`.
- Goblin Nimble Escape registration in `dnd/monsters/bestiary.py`.

Implementation plan:

1. Add `AggressiveMoveAction(BaseAction)`.
2. Target type is position.
3. Valid positions are reachable with movement up to speed and must reduce path
   or grid distance to a visible hostile.
4. Cost: bonus action plus movement, or bonus action and a special movement
   budget equivalent to speed. Prefer reusing movement to keep path costs honest.
5. Register only on Orc.

Tests:

- no visible hostile: no legal row;
- visible hostile: only closer positions are legal;
- spends bonus action;
- respects blockers/water/pathing through normal movement validation.

## Martial Advantage

Trait:

- Hobgoblin: Martial Advantage.

Nearest existing behavior:

- Damage roll result handlers in Fighter Great Weapon Fighting and other class
  features.
- Damage dice mutation in `DamageRollResultEvent`.
- Once-per-turn marker conditions in class features and Mark Cooldown.

Implementation plan:

1. Add `MartialAdvantageFeature(BaseCondition)`.
2. Register handler on `DAMAGE_ROLL_RESULT` for source entity.
3. Check:
   - weapon attack hit;
   - target within 5 feet of an ally of source;
   - ally is not incapacitated;
   - source has not used Martial Advantage this turn.
4. Add `2d6` damage of same damage type or an extra damage entry.
5. Add `Martial Advantage Used` marker that clears at turn start or turn end.

Tests:

- adjacent ally: +2d6 once;
- second hit same turn: no extra dice;
- no adjacent ally: no extra dice;
- spell damage: no extra dice.

## Sneak Attack

Trait:

- Spy: Sneak Attack.

Nearest existing behavior:

- Same as Martial Advantage for damage injection.
- Attack advantage state is available on attack/d20 events.
- Positional ally checks from Pack Tactics.

Implementation plan:

1. Add `SneakAttackFeature(BaseCondition)`.
2. Handler on weapon hit damage roll.
3. Check:
   - once per turn;
   - finesse or ranged weapon if we follow full 5e requirement;
   - attack has advantage OR target has adjacent non-incapacitated enemy of target
     allied with spy;
   - attack does not have disadvantage.
4. Add `2d6` damage.
5. Add turn-reset marker.

Tests:

- advantage enables damage;
- ally adjacency enables damage;
- disadvantage blocks damage;
- once per turn.

## Brute

Implemented behavior:

- Bugbear weapons use base dice and `Brute` now adds the extra melee weapon die
  through a damage-roll handler.
- This removes the earlier loadout approximation and makes Brute visible as a
  feature condition.

Nearest existing behavior:

- Damage roll extra dice in damage handlers.

Implementation:

1. Normalize Bugbear Morningstar to `1d8`.
2. Register `Brute` as a reusable `BonusDamageFeature`.
3. Apply to Bugbear and future Gladiator-style creatures.

Tests:

- melee weapon hit adds one die;
- ranged weapon hit does not unless monster text says included;
- critical behavior follows engine policy for extra dice.

## Surprise Attack

Trait:

- Bugbear: Surprise Attack.

Nearest existing behavior:

- Hidden/Invisible reveal on action in `dnd/actions.py`.
- Initiative/round state in `dnd/encounter.py`.
- Unseen attacker advantage logic in weapon fixtures.

Implementation plan:

1. First define the engine's videogame equivalent of "surprised."
2. Suggested v1:
   - round number is 1;
   - target did not perceive bugbear before attack;
   - bugbear was hidden or otherwise unseen by target at declaration.
3. Handler on weapon hit damage roll adds `2d6`.
4. Use a per-target or per-turn marker according to final policy.

Tests:

- hidden first-round hit: +2d6;
- visible first-round hit: no bonus;
- hidden second-round hit: no bonus.

## Bite Prone Rider

Traits:

- Wolf: Bite prone rider, STR DC 11.
- Dire Wolf: Bite prone rider, STR DC 13.

Nearest existing behavior:

- `Shove` applies Prone.
- `CommandGrovelEffect` applies Prone.
- Grease/Web style save and prone conditions in `dnd/spells/conjuration.py`.

Implementation plan:

1. Add `register_bite_prone_rider(entity, dc)`.
2. Handler observes completed bite hit or damage result.
3. Trigger Strength saving throw against DC.
4. Failed save applies `Prone` with parent event.

Tests:

- failed save applies Prone;
- successful save does not;
- non-bite attack does not trigger.

## Ghoul Claws Paralysis Rider

Trait:

- Ghoul: Claws paralysis rider.

Nearest existing behavior:

- `HoldPersonEffect` and `HoldMonsterEffect` in `dnd/spells/enchantment.py`.
- `Paralyzed` in `dnd/conditions.py`.
- Repeat save handlers in enchantment/necromancy spells.

Implementation plan:

1. Add `GhoulClawsParalysisEffect(BaseCondition)`.
2. On claw hit, target makes CON save DC 10.
3. Failed save applies ghoul effect with `Paralyzed` sub-condition.
4. Effect registers end-of-turn repeat save.
5. On success, remove effect and sub-condition.
6. Exclude undead by `CreatureType.UNDEAD`.
7. Elf exclusion requires race/lineage support. If unavailable, document as
   pending lineage data.

Tests:

- failed save applies effect and Paralyzed;
- end-turn save removes both;
- undead target is immune to rider;
- claw miss does nothing.

## Reckless

Trait:

- Berserker: Reckless.

Nearest existing behavior:

- `RecklessAttack`, `RecklessAttacking`, and `RecklessAttackFeature` in
  `dnd/classes/barbarian.py`.

Implementation plan:

1. Reuse Barbarian Reckless Attack directly if SRD semantics match enough.
2. Add `register_reckless_trait(entity)`.
3. This helper registers the existing `RecklessAttack` action or a monster-named
   wrapper around it.
4. Update metadata to represented.

Tests:

- Berserker has Reckless row.
- Using it grants outgoing melee advantage and incoming advantage.
- It is blocked while incapacitated through existing action validation.

## Cunning Action

Trait:

- Spy: Cunning Action.

Nearest existing behavior:

- Goblin Nimble Escape in `dnd/monsters/bestiary.py`.
- `BonusDash` from Expeditious Retreat in `dnd/spells/transmutation.py`.
- Base `Dash`, `Disengage`, and `Hide` in `dnd/actions.py`.

Implementation plan:

1. Add `register_cunning_action(entity)`.
2. Register:
   - bonus-action Dash;
   - bonus-action Disengage;
   - bonus-action Hide.
3. Use action names like:
   - `Cunning Action: Dash`;
   - `Cunning Action: Disengage`;
   - `Cunning Action: Hide`.

Tests:

- all three rows appear;
- each spends bonus action;
- ordinary action-cost versions remain distinct.

## Rampage

Trait:

- Gnoll: Rampage.

Nearest existing behavior:

- Turn-scoped marker conditions.
- Reaction-like event handlers.
- Frenzied Strike in `dnd/classes/rage.py` for bonus-action attack pattern.

Implementation plan:

1. Add `RampageFeature`.
2. Handler listens for melee attack reducing target to 0 HP.
3. Apply `RampageAvailable` condition until end of current turn.
4. Condition registers `Rampage Bite` action and optional `Rampage Move`.
5. Action spends bonus action.

Tests:

- kill with melee grants temporary row;
- kill with ranged/spell does not;
- row disappears after turn;
- no bonus action means no usable row.

## Parry

Traits:

- Bandit Captain: Parry +2.
- Knight: Parry +2.

Nearest existing behavior:

- `register_shield_reaction` in `dnd/spells/abjuration.py`.
- Opportunity attack reaction in `dnd/reactions.py`.
- reaction fixtures in `dnd/items/test_reactions.py`.

Implementation plan:

1. Add `register_parry_reaction(entity, ac_bonus=2)`.
2. Handler listens to incoming melee `ATTACK` resolution before final hit.
3. Check:
   - attack would hit without Parry;
   - source can see attacker;
   - source wields melee weapon;
   - source has reaction.
4. Add temporary AC modifier or mutate event target AC for that attack.
5. Spend reaction.

Tests:

- hit becomes miss when +2 AC crosses threshold;
- hit remains hit if +2 is insufficient;
- ranged attack does not trigger;
- no reaction means no trigger.

## Divine Eminence

Trait:

- Priest: Divine Eminence.

Nearest existing behavior:

- Divine Smite in `dnd/classes/paladin.py`.
- bonus-action self buffs in `dnd/classes/rage.py`.
- spell slot resource handling in `dnd/blocks/action_economy.py`.
- temporary damage conditions in class/spell features.

Implementation plan:

1. Add `DivineEminenceAction`.
2. Legal target is self.
3. Target options represent available spell slot levels.
4. On apply:
   - spend bonus action;
   - spend selected spell slot;
   - apply `DivineEminenceActive(slot_level)` until turn end.
5. Active condition handler adds radiant dice to melee weapon damage rolls:
   - `3d6` for level 1;
   - `+1d6` per slot level above 1.

Tests:

- no slots: no legal row;
- level 1 slot: +3d6 radiant on melee hit;
- level 2 slot: +4d6 radiant;
- ranged/spell attacks do not gain damage;
- condition expires at turn end.

## Leadership

Trait:

- Knight: Leadership.

Nearest existing behavior:

- Bless and Necrotic Bless in `dnd/spells/enchantment.py` and
  `dnd/spells/necromancy.py`.
- Mark Target concentration/linkage in `dnd/monsters/skeleton_abilities.py`.
- resource system in `dnd/blocks/action_economy.py`.

Implementation plan:

1. Add `LeadershipAction`.
2. Add one-use resource or cooldown condition.
3. Apply `LeadershipAura` to the knight for 10 rounds.
4. Aura grants allies within 30 feet a d4 to attack rolls and saving throws.
5. Check incapacitation on the knight; remove aura when incapacitated.
6. Decide whether hearing/understanding is represented. V1 can require ally
   perceives knight or skip language until language data exists.

Tests:

- action applies aura and consumes use;
- ally attack/save within 30 feet gains d4;
- ally outside 30 feet does not;
- incapacitating knight ends aura.

## Multiattack And Extra Attack Relationship

Important design note:

Do not model SRD monster Multiattack as Fighter Extra Attack unless the engine
policy explicitly wants that. Fighter Extra Attack changes the Attack action's
available economy. Monster Multiattack is a separate stat-block action with
specific attack composition.

Preferred approach:

- `MultiattackAction` belongs in `dnd/monsters/traits.py`.
- It composes existing `Attack` actions as children.
- It consumes one action.
- It appears as its own row in decision epochs.

## Metadata Maintenance Plan

When adding or changing a trait:

1. Add tests.
2. Register the trait in relevant SRD factory.
3. Keep `represented_traits` and `pending_traits` honest.
4. Run:

```bash
uv run pytest tests/manual/test_53_srd_monster_traits.py -q
uv run pytest tests/manual/test_51_srd_monster_roster.py -q
uv run pyright dnd/monsters/traits.py dnd/monsters/srd_roster.py
```

## Suggested Implementation Order

1. Cunning Action and Aggressive.
2. Reckless reuse for Berserker.
3. Pack Tactics.
4. Bite prone riders.
5. Ghoul paralysis rider.
6. Parry.
7. Multiattack.
8. Martial Advantage and Sneak Attack.
9. Undead Fortitude.
10. Divine Eminence.
11. Brave and Dark Devotion.
12. Keen senses.
13. Rampage.
14. Leadership.
15. Surprise Attack.

This order gives the tournament harness immediate tactical variety while keeping
the higher-risk lifecycle/death and aura work isolated.
