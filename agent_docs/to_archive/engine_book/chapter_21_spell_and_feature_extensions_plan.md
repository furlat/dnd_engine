# Chapter 21 Plan: Spell And Feature Extensions

## Reader Promise

Show how a custom feature grants a custom spell without introducing a second
runtime path. The reader should understand that a feature-like condition can
register a `SpellAction` template, discovery can expose the custom spell, spell
execution produces a `SpellEvent`, and the spell effect cleans up through
ordinary condition-owned modifiers.

## Concepts Introduced

- Feature-granted spell template.
- Custom `SpellAction` subclass.
- Spell target filtering with `include_self` and `valid_target_filter`.
- Spell event identity fields such as `spell_id`, `spell_level`, and
  `cast_at_level`.
- Feature condition cleanup that unregisters the spell template.

## Concepts Forbidden

- Parallel rules profiles or alternate SRD runtime modes.
- Internal-only test wrapper language.
- Hidden snippets that are not exact public examples.
- New spell slot mechanics beyond the already introduced cantrip/slot model.

## Required Visual

- A feature-to-spell-to-event-to-effect diagram showing ownership boundaries:
  feature owns template registration, spell owns event resolution, effect
  condition owns the modifier.

## Source Files Verified

- `dnd/actions.py` for `SpellAction` and `SpellEvent`.
- `dnd/actions_functional.py` for registration, discovery, and execution by
  index.
- `dnd/core/base_actions.py` for target filters and action metadata.
- `dnd/entity.py` for action template registration and discovery.
- `dnd/classes/fighter.py` and `dnd/classes/sorcerer.py` for feature conditions
  that register resources/actions and clean them up.
- `dnd/core/base_conditions.py` for `ConditionCategory` values.

## Public Example Contract

- One named MDX flow: `spell-feature-extension-flow`.
- The visible public code defines `AegisSparkEffect`, `AegisSpark`,
  `AegisTrainingFeature`, actor construction, scene construction, and discovery
  lookup.
- Later public snippets assert feature registration/removal, target discovery,
  spell event execution, condition-owned AC modifier cleanup, and scene
  composition.

## Verification

- Focused manual tests:
  `uv run pytest tests/manual/test_21_spell_and_feature_extensions.py`
- Exact public snippet execution:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
- Combined manual gate:
  explicit manual files 01-21 plus `tests/book_examples/test_public_mdx_snippets.py`.
