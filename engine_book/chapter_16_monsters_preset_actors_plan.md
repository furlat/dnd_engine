# Chapter 16 Plan: Monsters And Preset Actors

## Public Chapter Purpose

Chapter 16 teaches how enemies and reusable actors are authored as factories.
After class features, the reader knows how playable characters are assembled.
This chapter shows the same composition idea for monsters and encounter-ready
presets.

The public chapter should explain monsters as runtime-ready entities: ability
scores, hit dice, creature type, resistances, immunities, equipment, actions,
senses, spellcasting, inventory items, factions, and custom tactical roles.

## Teaching Order

1. Monster factories as stat-block-to-entity composition.
2. Base goblin and skeleton as D&D-shaped monster factories.
3. Goblin Nimble Escape as monster-specific action registration.
4. Skeleton poison/exhaustion immunity and undead defenses as runtime state.
5. Generic caster preset as a spell-and-inventory actor, not a class factory.
6. Skeleton warrior, archer, and warlock as game-specific combat roles.
7. Mark Target as a monster ability that creates concentration, a linked target
   condition, immunities, advantage for attackers, and cleanup.

## Public Example Contract

Add one strict public example group:

- `monster-preset-patterns`

The public page will include visible imports and setup in an open
`book-imports` details panel. The setup should define the reset helper and small
inspection helpers directly in the page. It must not import old example modules
or testing helper modules.

Example sections:

- EB-16-001: base goblin and skeleton factories encode visible monster state.
- EB-16-002: goblin Nimble Escape registers bonus-action variants.
- EB-16-003: generic caster preset wires spell slots, spells, Shield, gear, and
  potion item actions.
- EB-16-004: skeleton role presets compose equipment, spells, items, and
  custom actions.
- EB-16-005: Mark Target creates a concentration-owned target condition and
  cleans up correctly.

## Test Contract

Add `tests/manual/test_16_monsters_preset_actors.py` as focused behavior tests
that mirror the public examples.

Update `tests/book_examples/test_public_mdx_snippets.py` so Chapter 16 is a
strict migrated chapter with expected `monster-preset-patterns` public examples.

Focused verification command:

```bash
uv run pytest tests/manual/test_16_monsters_preset_actors.py tests/book_examples/test_public_mdx_snippets.py
```

Final checkpoint command should add Chapter 16 to the combined manual run.

## Public Prose Constraints

- Explain presets as forward-facing authoring tools.
- Explain SRD/tabletop monster stat blocks as source vocabulary only, not as a
  second runtime mode.
- Avoid internal notes, parity wording, hidden imports, old helper names, and
  test-runner language in the public page.
- Every Python fence must be `book-example`.
- The diagram should use `/diagrams/monsters-preset-actors.svg`.
