# Chapter 15 Plan: Class Features, Factories, And Feats

## Public Chapter Purpose

Chapter 15 teaches how character content is layered on top of the runtime
surfaces already documented: entities, values, action economy, events, actions,
conditions, equipment, spellcasting, and spell families.

The public chapter should explain class features as live engine packages. A
feature can add resources, register actions, add modifiers, register event
handlers, register spell templates, or add cleanup-owned conditions. Factories
assemble those features into a playable actor.

## Teaching Order

1. Factories create playable actors by combining ability scores, HP, equipment,
   actions, resources, and level-gated feature conditions.
2. Fighter shows resource-granted actions: Second Wind and Action Surge.
3. Fighter also shows style/handler/modifier placement at a high level, without
   publishing the full style matrix in this chapter.
4. Barbarian shows mode-like feature state: Rage and Berserker Frenzy create a
   condition tree and action grants that clean up together.
5. Sorcerer shows spell-template mutation: Quickened Spell temporarily changes
   eligible spell templates, then the override clears after casting.
6. Feats show feature-style event policies: Lucky owns a resource and a d20
   result processor.

## Public Example Contract

Add one strict public example group:

- `class-feature-patterns`

The page will include visible imports and setup in an open `book-imports`
details panel. The examples will define the runtime reset and a small target
factory directly in the page. They must not import old example modules or
testing helper modules.

Example sections:

- EB-15-001: factories wire level-gated resources, conditions, actions, and
  spells.
- EB-15-002: Fighter Second Wind and Action Surge spend resources and recharge
  on short rest.
- EB-15-003: Barbarian Frenzy creates a Raging/Frenzied condition tree and
  cleans up granted actions.
- EB-15-004: Sorcerer Quickened Spell mutates spell templates and clears after
  the cast.
- EB-15-005: Lucky owns a long-rest resource and rewrites low own d20 rolls.

## Test Contract

Add `tests/manual/test_15_class_features.py` as focused behavior tests that
mirror the public examples.

Update `tests/book_examples/test_public_mdx_snippets.py` so Chapter 15 is a
strict migrated chapter with expected `class-feature-patterns` public examples.

Focused verification command:

```bash
uv run pytest tests/manual/test_15_class_features.py tests/book_examples/test_public_mdx_snippets.py
```

Final checkpoint command should add Chapter 15 to the combined manual run.

## Public Prose Constraints

- Explain class features as forward-facing runtime capabilities, not as
  caveats about what tabletop rules are not implemented.
- Keep SRD/tabletop relationship as vocabulary and source comparison only.
- Avoid internal notes, parity wording, hidden imports, old helper names, and
  test-runner language in the public page.
- Every Python fence must be `book-example`.
- The diagram should use `/diagrams/class-features-factories.svg`.
