# Chapter 03 Plan: Values And Modifiers

## Status

Published to the local Astro webbook for human browser review.

Public page:

- `src/content/manual/03-values-and-modifiers.mdx`

Private draft prepared:

- `engine_book/drafts/03-values-and-modifiers.mdx`

Diagram assets prepared:

- `values-and-modifiers.svg`
- `values-and-modifiers.excalidraw`

Prepared test file:

- `tests/manual/test_03_values_and_modifiers.py`

Focused test run:

- `uv run pytest tests/manual/test_03_values_and_modifiers.py`
- Result: 4 passed.

Working public file, after review:

- `src/content/manual/03-values-and-modifiers.mdx`

## Reader Promise

By the end of the chapter, the reader should understand:

- Why D&D numbers in NeuroDragon are not plain integers.
- How `ModifiableValue` stores a base value and rule contributions.
- The difference between raw `score` and `normalized_score`.
- How static modifiers, constraints, advantage, critical, auto-hit, damage type,
  size, and resistance states aggregate.
- How contextual modifiers read source, target, and context.
- How a value can temporarily import target-exported modifiers with
  `set_from_target()`.
- Why later dice, event, action, condition, and combat chapters read values
  instead of reimplementing bonus math.

The chapter should feel like opening the numeric layer under an actor sheet. It
should not explain event handlers, dice result processors, condition lifecycle,
or full combat flow yet.

## Evidence Studied From Source

Current-source evidence read for this plan:

- `dnd/core/values.py`
- `dnd/core/modifiers.py`
- `dnd/core/base_object.py`
- `dnd/blocks/abilities.py`
- `dnd/utils/test_utils.py`
- `tests/manual/test_03_values_and_modifiers.py`

Evidence conclusions below come from source inspection and focused tests, not
old prose.

## Source Facts To Teach

### BaseValue And ModifiableValue

`BaseValue` is the UUID-addressable value root. It stores value identity,
source/target identity, context, score normalizer, generation metadata, and its
own value registry family.

`ModifiableValue` is the public value object used by actor blocks and rule
systems. It contains six channel fields:

- `self_static`
- `self_contextual`
- `to_target_static`
- `to_target_contextual`
- `from_target_static`
- `from_target_contextual`

`self_*` channels contribute to the value's owner.

`to_target_*` channels are exported by this value for another entity that is
targeting the owner.

`from_target_*` channels are populated by `set_from_target()` when a value
imports the current target's exported channels.

### Score And Normalized Score

`score` aggregates raw numerical modifier values.

`normalized_score` aggregates normalized numerical values. Normalizers are how
the engine represents D&D transformations such as ability score -> ability
modifier.

Focused test evidence:

- A value named `strength Ability Score` with base score 16 and normalizer
  `(score - 10) // 2` has `score == 16`.
- The same value has `normalized_score == 3`.

When that value combines with an attack bonus that has base 1 and a Magic
Weapon modifier +1:

- raw `score == 18`,
- `normalized_score == 5`,
- `get_breakdown()` shows STR +3, Base +1, Magic Weapon +1.

### Static Modifier Buckets

`StaticValue` stores always-on modifier buckets:

- `value_modifiers`
- `min_constraints`
- `max_constraints`
- `advantage_modifiers`
- `critical_modifiers`
- `auto_hit_modifiers`
- `size_modifiers`
- `damage_type_modifiers`
- `resistance_modifiers`

Minimum and maximum constraints clamp the channel score. A movement value with
base 30 and a static max constraint 0 has score 0. This is the simple way to
teach effects like "speed becomes 0" without explaining conditions yet.

Advantage modifiers aggregate by signed value:

- advantage = +1,
- disadvantage = -1,
- positive total means advantage,
- negative total means disadvantage,
- zero means no advantage state.

Critical modifiers have precedence:

- `NOCRIT` wins over `AUTOCRIT`.

Auto-hit modifiers have precedence:

- `AUTOMISS` wins over `AUTOHIT`.

Resistance modifiers aggregate by damage type:

- immunity = +2,
- resistance = +1,
- none = 0,
- vulnerability = -1.

Final resistance state by sum:

- greater than 1 -> immunity,
- exactly 1 -> resistance,
- exactly 0 -> none,
- less than 0 -> vulnerability.

Focused test evidence:

- Fire resistance alone yields resistance.
- Fire resistance plus fire vulnerability yields none.
- Adding fire immunity to those two yields immunity.

### Contextual Modifier Buckets

`ContextualValue` stores callable modifiers evaluated against:

- source entity UUID,
- target entity UUID,
- context dictionary,
- optional event lineage UUID for cache keys.

The normal contextual aggregation path uses `evaluate()`. It catches callable
exceptions and treats failed or inactive modifiers as `None`.

Focused test evidence:

- A ranged attack bonus with base 5 and a contextual `High Ground` callable
  stays 5 when context is missing or false.
- Setting context to `{"has_high_ground": True}` makes the score 7.
- `get_full_breakdown()` can show cached contextual breakdown entries after
  the value has been evaluated.

This chapter should teach contextual modifiers without teaching event lineage.
Lineage belongs to the event chapter.

### Target Propagation

`set_target_entity()` records the entity currently being targeted and propagates
that target identity into the value's channels.

`set_from_target(target_value)` imports the target value's exported
`to_target_static` and `to_target_contextual` channels into this value's
`from_target_static` and `from_target_contextual` channels.

`reset_from_target()` clears imported target channels.

Focused test evidence:

- A hero attack bonus starts at 5 and has no advantage.
- A blinded goblin's defense exports advantage and +2 to attackers through
  `to_target_static`.
- After `hero_attack.set_from_target(goblin_defense)`, the hero attack score is
  7 and has advantage.
- After `hero_attack.reset_from_target()`, the hero attack score returns to 5
  and has no advantage.

This chapter should describe target propagation as a value mechanism. The
condition chapter later explains which conditions put modifiers in those
channels.

## Concepts Allowed In This Chapter

Allowed:

- value
- base value
- modifier
- score
- normalized score
- score normalizer
- static modifier
- contextual modifier
- context dictionary
- advantage/disadvantage aggregation
- critical and auto-hit override states
- resistance/vulnerability/immunity aggregation
- self channel
- target-exported channel
- imported target channel
- target propagation
- display breakdown
- combining values

Allowed as future landmarks only:

- dice
- event lineage
- conditions
- attacks
- Armor Class
- spell DC
- saving throw bonus

## Concepts Forbidden In This Chapter

Do not teach:

- dice rolling
- event phases
- event handlers
- result processors
- condition lifecycle
- action templates
- attack validation
- damage application
- full AC calculation
- concentration
- pathfinding
- server/API DTOs

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

### 1. Why Values Exist

Start from the game:

D&D numbers are rarely just numbers. A character sheet gives a base score, then
equipment, conditions, positioning, class features, target state, and the
current scene can add, clamp, or alter how the number behaves.

NeuroDragon makes that explicit with values and modifiers.

### 2. The Six Channels

Teach the `ModifiableValue` channel table:

| Channel | Meaning |
| --- | --- |
| `self_static` | Always-on modifiers affecting the owner. |
| `self_contextual` | Conditional modifiers affecting the owner. |
| `to_target_static` | Always-on modifiers exported to entities targeting the owner. |
| `to_target_contextual` | Conditional modifiers exported to entities targeting the owner. |
| `from_target_static` | Imported static modifiers from the current target. |
| `from_target_contextual` | Imported contextual modifiers from the current target. |

### 3. Where The Imports Come From

This import map must appear before code:

| Symbol | Import | Why it appears |
| --- | --- | --- |
| `Optional` | `from typing import Optional` | Types the contextual callable's optional target/context. |
| `UUID`, `uuid4` | `from uuid import UUID, uuid4` | Creates tutorial actor IDs and types callable arguments. |
| `AdvantageModifier`, `AdvantageStatus` | `from dnd.core.modifiers import AdvantageModifier, AdvantageStatus` | Teaches advantage/disadvantage aggregation. |
| `AutoHitModifier`, `AutoHitStatus` | `from dnd.core.modifiers import AutoHitModifier, AutoHitStatus` | Teaches hit override aggregation. |
| `CriticalModifier`, `CriticalStatus` | `from dnd.core.modifiers import CriticalModifier, CriticalStatus` | Teaches critical override aggregation. |
| `DamageType` | `from dnd.core.modifiers import DamageType` | Identifies resistance damage types. |
| `NumericalModifier` | `from dnd.core.modifiers import NumericalModifier` | Adds flat numerical bonuses and constraints. |
| `ResistanceModifier`, `ResistanceStatus` | `from dnd.core.modifiers import ResistanceModifier, ResistanceStatus` | Teaches resistance/vulnerability/immunity aggregation. |
| `ContextualNumericalModifier`, `ModifiableValue` | `from dnd.core.values import ContextualNumericalModifier, ModifiableValue` | Creates tutorial values and contextual modifiers. |

Do not include reset helpers in the public import map.

### 4. Score And Normalized Score

Show the ability-score normalizer and the strength value:

```python
def ability_score_normalizer(score: int) -> int:
    return (score - 10) // 2
```

Then teach `score == 16` and `normalized_score == 3`.

### 5. Combining Values And Display Breakdown

Show combining a strength value with an attack bonus value. Explain that
`combine_values()` produces a new value with merged channels and generation
metadata. Show `get_breakdown()` output.

### 6. Static Channels

Use examples from the test file:

- movement max constraint 0,
- advantage plus disadvantage cancellation,
- `NOCRIT` over `AUTOCRIT`,
- `AUTOMISS` over `AUTOHIT`,
- fire resistance/vulnerability/immunity aggregation.

### 7. Contextual Channels

Define the `high_ground_bonus(...)` callable visibly before use. Show:

- base 5 attack bonus,
- no context -> 5,
- high-ground context -> 7,
- false context -> 5.

### 8. Target Propagation

Show hero attack and blinded goblin defense. Explain:

- the goblin exports modifiers through `to_target_static`,
- the hero imports them with `set_from_target()`,
- the import is temporary and cleared by `reset_from_target()`.

### 9. What Comes Next

Next chapter: dice.

Values explain what number is being rolled with. Dice explain how the uncertain
roll is produced before events and later systems can react to the result.

## Diagram Requirement

Create a fresh diagram:

- `values-and-modifiers.svg`
- `values-and-modifiers.excalidraw`

Visual shape:

- Center: `ModifiableValue`
- Left/top self channels: `self_static`, `self_contextual`
- Right/top exported channels: `to_target_static`, `to_target_contextual`
- Bottom imported channels: `from_target_static`, `from_target_contextual`
- Modifier families: numerical, constraints, advantage, critical, auto-hit,
  resistance
- Small arrow from target value to imported target channels

Caption:

> A modifiable value gathers its own modifiers, can export effects to entities
> targeting its owner, and can temporarily import the target's exported effects
> during a rule calculation.

## Test Requirement

The test file must remain a real pytest file:

- `tests/manual/test_03_values_and_modifiers.py`

It must include:

- visible imports,
- visible tutorial callables,
- no wrappers around examples,
- no imports from `examples`,
- no imports from `tests.engine_book`,
- no `iter_example_tests`,
- behavior names instead of EB numbers.

Required focused tests:

- `test_base_values_modifiers_normalization_and_breakdown()`
- `test_static_channels_collect_constraints_roll_states_and_resistances()`
- `test_contextual_modifiers_read_the_current_context()`
- `test_target_propagation_imports_outgoing_modifiers_then_resets_them()`

Run focused only:

```bash
uv run pytest tests/manual/test_03_values_and_modifiers.py
```

Do not run the full test suite.

## Public Acceptance Gate

Before publishing the page:

- Opening chapter has been human-reviewed.
- Chapters 01 and 02 have been accepted or published in sequence.
- Chapter 03 includes the import map before code.
- Every code symbol is imported or defined before use.
- No public note/test/parity links.
- No hidden helpers in public snippets.
- No event handler, event phase, action template, dice result processor, or
  condition lifecycle terminology before introduced.
- Diagram renders at desktop and narrow widths.
- Focused pytest file passes.
- Astro build passes.
- Route returns `200`.
- Public hygiene scan finds no `engine_book`, `tests/`, `parity`, `notes/`,
  `TODO`, `placeholder`, or old helper names.
