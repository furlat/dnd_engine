# Chapter 14 Plan: Spell Families And Implemented Spells

## Public Chapter Purpose

Chapter 13 teaches the shared spellcasting substrate: slots, spell numbers,
registered spell templates, spell events, and concentration cleanup. Chapter 14
teaches how the implemented spell catalog uses that substrate in play.

The public chapter should read as a developer field guide to spell behavior
families. It should not be a copied catalog dump, a parity matrix, or a list of
old test notes. The reader should leave knowing how to inspect a spell, choose a
runtime pattern for a new spell, and recognize the major implemented families.

## Teaching Order

1. Spell catalog identity: level dictionaries, `ALL_SPELLS`, class metadata.
2. Target and outcome families: self, entity, multi-entity, position, and AoE.
3. Offensive spells: spell attack, saving throw, and auto-hit multi-target.
4. Recovery and protection: healing, Mage Armor, and restoration-style cleanup.
5. Mobility and temporary HP: Misty Step and False Life.
6. Durable map magic: zone conditions, tile markers, spatial handlers, and
   concentration links.
7. State-changing illusions and enchantments: Mirror Image, Sleep, and the
   condition tree those spells create.

## Public Example Contract

Add one strict public example group:

- `spell-family-patterns`

The public page will include visible imports and setup in an open
`book-imports` details panel. The example should define the arena reset, caster
factory, target factory, save modifiers, and direct HP adjustment helpers in the
page itself. It must not import old example files or engine-book test helpers.

Example sections:

- EB-14-001: catalog rows and runtime metadata.
- EB-14-002: Fire Bolt, Sacred Flame, and Magic Missile.
- EB-14-003: Cure Wounds, Healing Word, Mage Armor, and Lesser Restoration.
- EB-14-004: Misty Step and False Life.
- EB-14-005: Spike Growth zone ownership and concentration cleanup.
- EB-14-006: Mirror Image and Sleep as condition-producing spells.

## Test Contract

Add `tests/manual/test_14_spell_families.py` as real focused tests, not a
wrapper around examples. The tests should mirror the public examples closely but
remain readable pytest checks.

Update `tests/book_examples/test_public_mdx_snippets.py` so Chapter 14 is a
strict migrated chapter with expected `spell-family-patterns` public examples.

Focused verification command:

```bash
uv run pytest tests/manual/test_14_spell_families.py tests/book_examples/test_public_mdx_snippets.py
```

Final checkpoint command should add Chapter 14 to the combined manual run.

## Public Prose Constraints

- Explain the chosen videogame runtime as the engine truth.
- Refer to D&D/SRD spell language as the tabletop source vocabulary only when
  useful for comparison.
- Avoid internal note paths, parity wording, old helper names, and test-runner
  language in the public page.
- Keep imports visible and open.
- Every Python fence in the public chapter must be `book-example`.
- The diagram should use `/diagrams/spell-families.svg`.
