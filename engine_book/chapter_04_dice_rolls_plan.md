# Chapter 04 Plan: Dice Rolls

## Status

Published to the local Astro webbook for human browser review.

Public page:

- `src/content/manual/04-dice-rolls.mdx`

Prepared test file:

- `tests/manual/test_04_dice_rolls.py`

Focused test run:

- `uv run pytest tests/manual/test_04_dice_rolls.py`
- Result: 5 passed.

## Reader Promise

By the end of the chapter, the reader should understand:

- Why dice are separate from values.
- How `Dice` describes a dice expression.
- How `DiceRoll` stores a concrete roll result.
- How d20 rolls store selected results, bonus, total, source, and target.
- How advantage and disadvantage keep both d20 faces.
- How critical damage rolls add extra dice.
- Which roll shapes are rejected by validation.
- Why the next chapter can introduce events around roll results.

This chapter should stay focused on raw dice and roll records. It should not
teach event handlers, result processors, attack validation, action templates, or
condition lifecycle yet.

## Evidence Studied From Source

Current-source evidence read for this plan:

- `dnd/core/dice.py`
- `dnd/entity.py` d20 call sites at a surface level
- `dnd/actions.py` damage roll call sites at a surface level
- `tests/manual/test_04_dice_rolls.py`

Evidence conclusions below come from source inspection and focused tests, not
old prose.

## Source Facts To Teach

### Dice

`Dice` describes a dice expression:

- `count`
- `value`
- `bonus`
- `roll_type`
- optional `attack_outcome` for damage rolls
- `crit_extra_dice`

`Dice` registers itself in `Dice._registry`.

`Dice.roll` is a cached computed property. Reading it produces one `DiceRoll`;
reading it again returns the same object.

`Dice.source_entity_uuid` and `Dice.target_entity_uuid` come from the bonus
value.

### DiceRoll

`DiceRoll` stores one concrete result:

- `roll_uuid`
- `dice_uuid`
- `roll_type`
- `results`
- `total`
- `bonus`
- `advantage_status`
- `critical_status`
- `auto_hit_status`
- `source_entity_uuid`
- optional `target_entity_uuid`
- optional `attack_outcome`

`DiceRoll` registers itself in `DiceRoll._registry`.

### D20 Rolls

Non-damage/healing rolls must use one die. In practice, attack, save, and check
rolls use `count=1`, `value=20`.

Without advantage or disadvantage, a d20 roll stores the selected result as a
single-item list, such as `[13]`.

The total is selected d20 face plus `bonus.normalized_score`.

Focused test evidence:

- d20 result 13 with bonus 5 has total 18.
- `roll is d20.roll` because the roll property is cached.
- `Dice.get(...)` and `DiceRoll.get(...)` recover the expression and result.

### Advantage And Disadvantage

If the bonus value has advantage, the dice expression rolls two d20s, stores
both faces, and totals the higher face plus the normalized bonus.

If the bonus value has disadvantage, it stores both faces and totals the lower
face plus the normalized bonus.

Focused test evidence:

- Advantage rolls `[4, 17]` with bonus 5 and totals 22.
- Disadvantage rolls `[16, 3]` with bonus 5 and totals 8.

### Roll-State Snapshots

`DiceRoll` stores the advantage, critical, and auto-hit state captured from the
bonus value when the roll is created.

This chapter should say these states are recorded on the roll. It should not
teach outcome resolution yet.

Focused test evidence:

- A d20 roll with `AUTOCRIT` and `AUTOHIT` modifiers records
  `critical_status == AUTOCRIT` and `auto_hit_status == AUTOHIT`.

### Damage Rolls

Damage rolls require an `attack_outcome`. Non-damage rolls must not provide an
attack outcome.

For damage and healing rolls, `results` stores each die face and `total` is
the sum of die faces plus `bonus.normalized_score`.

When `attack_outcome == AttackOutcome.CRIT`, `Dice._roll()` doubles the base
number of dice and adds `crit_extra_dice`.

Focused test evidence:

- `2d6 + 3` on a normal hit with rolls `[2, 5]` totals 10.
- `1d8 + 3` on a crit with `crit_extra_dice=1` rolls three dice and with
  `[1, 8, 4]` totals 16.

### Validation

Pydantic validation rejects:

- non-damage/healing rolls with `count > 1`,
- damage rolls without `attack_outcome`,
- non-damage rolls with `attack_outcome`,
- unsupported die values outside `4, 6, 8, 10, 12, 20`.

## Concepts Allowed In This Chapter

Allowed:

- dice expression
- concrete roll result
- `Dice`
- `DiceRoll`
- `RollType`
- `AttackOutcome`
- d20
- damage dice
- healing dice as a roll type, without details
- advantage/disadvantage dice selection
- normalized bonus
- cached roll
- roll registry
- critical damage dice
- deterministic examples with `unittest.mock.patch`

Allowed as future landmarks only:

- d20 result events
- damage result events
- attack outcome resolution
- combat logs

## Concepts Forbidden In This Chapter

Do not teach:

- event phases
- event handlers
- result processors
- condition lifecycle
- action templates
- attack validation
- armor class comparison
- saving throw request flow
- skill check request flow
- damage application
- combat logs

Do not use hidden helpers from old tests.

Forbidden public names:

- `EB-*`
- parity
- `tests/engine_book`
- private notes
- `make_bonus`
- `make_damage_roll`
- `make_d20_roll`
- `fixed_randint`
- `completed_damage_events`

## Public Page Shape

### 1. Why Dice Exist

Start from the game:

Values tell the engine what number modifies a roll. Dice create the uncertain
result. The concrete `DiceRoll` records what happened so later systems can read
it.

### 2. Dice And DiceRoll

Show a table comparing `Dice` and `DiceRoll`.

### 3. Where The Imports Come From

This import map must appear before code:

| Symbol | Import | Why it appears |
| --- | --- | --- |
| `patch` | `from unittest.mock import patch` | Makes tutorial rolls deterministic. |
| `uuid4` | `from uuid import uuid4` | Creates source actor IDs. |
| `pytest` | `import pytest` | Shows validation failures in the tutorial tests. |
| `ValidationError` | `from pydantic import ValidationError` | Pydantic error type raised by invalid dice expressions. |
| `AttackOutcome`, `Dice`, `DiceRoll`, `RollType` | `from dnd.core.dice import AttackOutcome, Dice, DiceRoll, RollType` | Creates dice expressions and reads roll records. |
| `AdvantageModifier`, `AdvantageStatus` | `from dnd.core.modifiers import AdvantageModifier, AdvantageStatus` | Demonstrates advantage and disadvantage. |
| `AutoHitModifier`, `AutoHitStatus` | `from dnd.core.modifiers import AutoHitModifier, AutoHitStatus` | Shows roll-state capture. |
| `CriticalModifier`, `CriticalStatus` | `from dnd.core.modifiers import CriticalModifier, CriticalStatus` | Shows roll-state capture and critical damage context. |
| `ModifiableValue` | `from dnd.core.values import ModifiableValue` | Supplies the roll bonus and roll-state channels. |

### 4. A Deterministic D20

Show d20 expression with bonus 5 and `patch("dnd.core.dice.random.randint",
return_value=13)`.

Teach cached roll identity and registries.

### 5. Advantage And Disadvantage

Show advantage `[4, 17]` totals 22 and disadvantage `[16, 3]` totals 8.

### 6. Roll-State Snapshots

Show critical/auto-hit flags recorded on `DiceRoll`, but avoid outcome logic.

### 7. Damage Dice And Critical Dice

Show normal damage and critical damage. Explain that critical damage dice are
chosen by `attack_outcome`, not by the d20 roll in this raw dice chapter.

### 8. Validation

Show rejected roll shapes with `pytest.raises(ValidationError, ...)`.

### 9. What Comes Next

Next chapter: events.

Dice create the result. Events carry declared intent, effect, lineage, and later
completion logs around those results.

## Diagram Requirement

Create a fresh diagram:

- `dice-roll-pipeline.svg`
- `dice-roll-pipeline.excalidraw`

Visual shape:

- `ModifiableValue` bonus feeds `Dice`
- `Dice` contains count, value, roll type, attack outcome
- `random.randint` produces raw faces
- advantage/disadvantage selects one d20 face for total
- damage keeps all dice and sums them
- `DiceRoll` records result, total, statuses, source/target

Caption:

> A dice expression combines a random face with a modifiable bonus and records a
> concrete DiceRoll that later rule systems can inspect.

## Test Requirement

The test file must remain a real pytest file:

- `tests/manual/test_04_dice_rolls.py`

It must include:

- visible imports,
- visible deterministic `patch` calls,
- no wrappers around examples,
- no imports from `examples`,
- no imports from `tests.engine_book`,
- no `iter_example_tests`,
- behavior names instead of EB numbers.

Required focused tests:

- `test_d20_roll_records_result_bonus_total_and_identity()`
- `test_advantage_and_disadvantage_keep_both_d20_faces()`
- `test_roll_state_snapshots_include_critical_and_auto_hit_flags()`
- `test_damage_rolls_require_attack_outcome_and_critical_rolls_more_dice()`
- `test_dice_validation_keeps_roll_shapes_explicit()`

Run focused only:

```bash
uv run pytest tests/manual/test_04_dice_rolls.py
```

Do not run the full test suite.

## Public Acceptance Gate

Before publishing or keeping the page public:

- Chapter 04 includes the import map before code.
- Every code symbol is imported or defined before use.
- No public note/test/parity links.
- No hidden helpers in public snippets.
- No event handler, event phase, action template, result processor, or
  condition lifecycle terminology before introduced.
- Diagram renders at desktop and narrow widths.
- Focused pytest file passes.
- Astro build passes.
- Route returns `200`.
- Public hygiene scan finds no `engine_book`, `tests/`, `parity`, `notes/`,
  `TODO`, `placeholder`, or old helper names.
