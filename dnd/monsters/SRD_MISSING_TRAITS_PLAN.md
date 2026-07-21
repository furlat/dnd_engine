# SRD Monster Trait Completion Plan

This document inventories the SRD monster/NPC traits implemented for the
SRD-derived validation roster in `dnd/monsters/srd_roster.py`.

The goal is not to approximate these traits with inflated stats. The goal is to
implement the mechanics through the engine primitives so AI validation sees real
legal actions, real event consequences, real conditions, real resources, and real
subjective outcomes.

## Scope

The current SRD roster has broad creature coverage and preserves:

- ability scores;
- hit dice, hit points, armor, and movement;
- creature type, size, darkvision, and basic immunities;
- carried weapons and legal attack rows;
- spellcasting where spell equivalents already exist;
- Shield and Counterspell reactions for Mage.

The roster now installs the traits listed below through `dnd/monsters/traits.py`.
The acceptance notes remain as regression targets for future deeper tests and
rule refinements.

Current note:

- Gnoll Bite is represented as a natural attack action, not as an equipped
  off-hand weapon. This keeps the SRD shield loadout intact while still making
  Bite and Rampage executable through normal attack events.

## Implemented Trait Index

| Trait | Monsters | Mechanical Family | Priority |
|---|---|---:|---:|
| Dark Devotion | Cultist, Cult Fanatic | saving throw advantage | P2 |
| Pack Tactics | Tribal Warrior, Kobold, Wolf, Dire Wolf, Thug | attack advantage | P1 |
| Sunlight Sensitivity | Kobold | contextual attack/perception disadvantage | P2 |
| Undead Fortitude | Zombie, Ogre Zombie | damage/death interception | P1 |
| Keen Hearing and Smell | Wolf, Dire Wolf | perception advantage | P3 |
| Keen Hearing and Sight | Scout | perception advantage | P3 |
| Multiattack | Scout, Thug, Spy, Bandit Captain, Cult Fanatic, Knight, Veteran | action template/action economy | P1 |
| Aggressive | Orc | bonus-action movement | P1 |
| Martial Advantage | Hobgoblin | once-per-turn bonus damage | P1 |
| Rampage | Gnoll | kill-triggered bonus action move+attack | P2 |
| Cunning Action | Spy | bonus-action Dash/Disengage/Hide | P1 |
| Sneak Attack | Spy | once-per-turn conditional bonus damage | P1 |
| Surprise Attack | Bugbear | first-round hidden/surprise bonus damage | P3 |
| Bite Prone Rider | Wolf, Dire Wolf | hit rider + saving throw + condition | P1 |
| Claws Paralysis Rider | Ghoul | hit rider + saving throw + repeat save | P1 |
| Reckless | Berserker | voluntary advantage/exposure | P1 |
| Parry | Bandit Captain, Knight | reaction AC bonus | P1 |
| Divine Eminence | Priest | bonus-action slot spend + melee damage buff | P2 |
| Brave | Knight | saving throw advantage | P2 |
| Leadership | Knight | limited-use support aura | P3 |

## By Monster

### Cultist

Implemented:

- `Dark Devotion`: advantage on saving throws against being charmed or frightened.

Acceptance:

- Saving throws against Charmed/Frightened source effects include advantage.
- Other saving throws are unchanged.
- Subjective action/condition logs show normal condition application outcomes.

### Tribal Warrior

Implemented:

- `Pack Tactics`: advantage on attack rolls when an ally is within 5 feet of the target and is not incapacitated.

Acceptance:

- Melee and thrown/ranged weapon attacks gain advantage only when the positional ally condition is true.
- Incapacitated allies do not satisfy the condition.

### Kobold

Implemented:

- `Pack Tactics`.
- `Sunlight Sensitivity`: disadvantage on attack rolls and sight-based Perception checks while in sunlight.

Acceptance:

- Pack Tactics works as above.
- Sunlight disadvantage triggers from tile/light state, not map-name hardcoding.
- Dark rooms and non-sunlight light do not incorrectly apply the penalty unless the engine light model represents them as sunlight.

### Zombie

Implemented:

- `Undead Fortitude`: when damage reduces the zombie to 0 HP, make CON save DC `5 + damage taken`; on success remain at 1 HP unless damage was radiant or critical.

Acceptance:

- Ordinary lethal damage can leave the zombie at 1 HP.
- Radiant damage bypasses the trait.
- Critical hits bypass the trait.
- The combat log exposes the save and survival/failure result.

### Wolf

Implemented:

- `Keen Hearing and Smell`.
- `Pack Tactics`.
- `Bite prone rider`: target makes STR save DC 11 or gains Prone.

Acceptance:

- Bite hit triggers a Strength saving throw.
- Failed save applies `Prone`.
- Success leaves target standing.
- Rider is child-linked to the bite action in combat logs.

### Scout

Implemented:

- `Keen Hearing and Sight`.
- `Multiattack`: two melee attacks or two ranged attacks.

Acceptance:

- Scout can select a multiattack row when it has an action.
- The row executes two legal attacks against selected targets.
- If the first attack changes legality, the second attack validates independently.

### Thug

Implemented:

- `Pack Tactics`.
- `Multiattack`: two mace attacks.

Acceptance:

- Pack Tactics advantage works only with the ally-adjacent condition.
- Multiattack spends one action and resolves two attacks.

### Orc

Implemented:

- `Aggressive`: bonus action move up to speed toward a visible hostile creature.

Acceptance:

- Appears as a legal bonus-action movement row only when a visible enemy exists.
- Destination choices are constrained to reduce distance to the selected hostile.
- It spends bonus action and movement or uses a clear movement-equivalent cost contract.

### Hobgoblin

Implemented:

- `Martial Advantage`: once per turn, add 2d6 damage on a weapon hit if target is within 5 feet of a non-incapacitated hobgoblin ally.

Acceptance:

- Bonus damage applies only once per turn.
- It applies after a weapon hit, not on misses or spells.
- It requires the ally-adjacent condition at hit resolution.

### Gnoll

Implemented:

- `Rampage`: after reducing a creature to 0 HP with melee attack on its turn, bonus action move up to half speed and make a bite attack.

Acceptance:

- Trigger occurs only on the gnoll's own turn.
- Trigger occurs only from melee attack reducing target to 0 HP.
- Granted action is temporary and consumes bonus action.
- If no bite target or movement target is legal, no illegal row appears.

### Spy

Implemented:

- `Cunning Action`: bonus-action Dash, Disengage, or Hide.
- `Sneak Attack`: once per turn, +2d6 damage when the spy has advantage or an ally is within 5 feet of target and the spy does not have disadvantage.
- `Multiattack`: two melee attacks.

Acceptance:

- Cunning Action rows use bonus action and do not duplicate ordinary action-cost rows.
- Sneak Attack checks advantage/disadvantage and ally adjacency at hit resolution.
- Sneak Attack applies once per turn.
- Multiattack resolves two legal shortsword attacks for one action.

### Bugbear

Implemented:

- `Surprise Attack`: if the bugbear surprises a creature and hits during the first round, target takes +2d6 damage.

Acceptance:

- Requires a model of surprise/undetected opener.
- Applies only during round 1.
- Applies only once per surprised target or according to the SRD rule text chosen for this engine.

### Dire Wolf

Implemented:

- `Keen Hearing and Smell`.
- `Pack Tactics`.
- `Bite prone rider`: target makes STR save DC 13 or gains Prone.

Acceptance:

- Same as Wolf, with DC 13 and large creature stats.

### Ghoul

Implemented:

- `Claws paralysis rider`: target makes CON save DC 10 or is Paralyzed for 1 minute; target repeats save at end of each turn.

Acceptance:

- Claw hit triggers CON save.
- Failed save applies a ghoul-specific effect that owns `Paralyzed` as a sub-condition.
- Repeat save runs at end of target turns.
- Elves and undead are excluded if the engine can represent lineage/type checks; undead exclusion must be implemented because creature type exists.

### Berserker

Implemented:

- `Reckless`: at start of its turn, can gain advantage on melee weapon attack rolls during that turn; attacks against it have advantage until start of its next turn.

Acceptance:

- Uses a self action or turn-start decision row.
- Advantage applies only to melee weapon attacks by the berserker.
- Incoming attacks gain advantage until the next turn start.

### Bandit Captain

Implemented:

- `Multiattack`: three melee attacks, or two ranged dagger attacks.
- `Parry`: reaction adds +2 AC against one melee attack that would hit.

Acceptance:

- Multiattack presents separate melee/ranged variants or one row with legal target structure.
- Parry is a reaction handler gated by seeing attacker, wielding melee weapon, melee attack would hit, and reaction availability.

### Cult Fanatic

Implemented:

- `Dark Devotion`.
- `Multiattack`: two melee attacks.

Acceptance:

- Dark Devotion works as above.
- Multiattack spends one action and resolves two dagger attacks.

### Priest

Implemented:

- `Divine Eminence`: bonus action expend a spell slot; melee attacks deal +3d6 radiant until end of turn, +1d6 per slot level above 1.

Acceptance:

- Legal only when a spell slot is available and bonus action remains.
- Applies a temporary self condition expiring at turn end.
- Next melee weapon hits during that turn add radiant damage.
- Slot level is explicit in row or target/options.

### Ogre Zombie

Implemented:

- `Undead Fortitude`.

Acceptance:

- Same as Zombie, with Ogre Zombie stats.

### Knight

Implemented:

- `Brave`: advantage on saving throws against being frightened.
- `Leadership`: recharge after rest; for 1 minute allies within 30 feet that can hear/understand add d4 to attack rolls and saving throws.
- `Parry`: reaction adds +2 AC against one melee attack that would hit.
- `Multiattack`: two melee attacks.

Acceptance:

- Brave works only against Frightened effects.
- Leadership applies a limited-duration aura/support condition.
- Leadership affects allies, not self unless SRD wording permits.
- Parry and Multiattack work as above.

### Veteran

Implemented:

- `Multiattack`: two longsword attacks; if shortsword drawn, also shortsword attack.

Acceptance:

- One action resolves the correct number of attacks based on equipped melee slots.
- The shortsword extra attack only appears when the off-hand shortsword is present.

## Cross-Cutting Work

### Trait Registry

Add `dnd/monsters/traits.py` as the reusable SRD trait home.

Each public helper should be shaped like:

```python
def register_pack_tactics(entity: Entity, trait_name: str = "Pack Tactics") -> None:
    """Register Pack Tactics on an entity."""
```

Factory functions in `srd_roster.py` should call these helpers directly.

### Metadata State

Keep `represented_traits` and `pending_traits` in `SRD_MONSTER_SPECS` aligned
with the mechanics actually installed by each factory.

### Test Requirements

Add `tests/manual/test_53_srd_monster_traits.py` with focused tests for:

- attack advantage traits;
- once-per-turn bonus damage traits;
- reaction traits;
- action template traits;
- hit riders and repeat saves;
- undead fortitude;
- metadata parity.

Do not depend on long AI-vs-AI runs for correctness. Self-play only validates
that the policy can consume the resulting affordances.
