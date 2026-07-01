# NeuroDragon Dev Manual First Pass Spec

## Status

Historical only. Superseded by `engine_book/webbook_rebuild_plan.md`.

The public Astro topic pages have been deleted again. This file records an old
first-pass attempt and must not be used as the current publishing plan.

## Scope

This spec covers the first restart pass only:

1. `00-what-neurodragon-is.mdx`
2. `01-how-to-read-and-run-examples.mdx`

The pass stops after these two chapters for browser review. No runtime
foundation topic page should be restored before these two pages establish the
reader contract, visual format, and code-example standard.

## Editorial Goal

The first pass should make a reader feel oriented before they see engine
internals. The manual should answer:

- What kind of game is NeuroDragon?
- What role does the engine play?
- What kind of developer is this manual written for?
- How will examples be written?
- Where do imports come from?
- How does the reader run focused checks without turning the manual into a test
  index?

## Site State Before First Pass

Current intended state:

- The Astro manual content folder is empty.
- The dynamic manual route may remain, but it must only render real content from
  the collection.
- The root page builds.
- Topic pages return 404 until the first restart pages are written.
- `ExampleBlock` does not render note/test/source anchors.
- `ManualChapter` has table styling ready for future content.

Before adding chapters, verify the manual route at
`/home/tommaso/Dev/neurodragon_dev_manual/src/pages/manual/[...slug].astro` is
simple and content-driven. It must not invent manual paths when the collection
is empty.

## Chapter 00 Brief: What NeuroDragon Is

### Working Frontmatter

```yaml
title: "What NeuroDragon Is"
subtitle: "A Dungeons & Dragons videogame engine where the runtime plays the dungeon master."
order: 0
part: "Orientation"
rules: []
```

No visible evidence links. No `note` or `test` frontmatter unless private
tooling truly needs it later.

### Reader Outcomes

By the end of the chapter, the reader should understand:

- NeuroDragon is a tactical videogame engine inspired by Dungeons & Dragons.
- The engine acts as the dungeon master in software: it validates intent,
  resolves rules, updates state, and exposes outcomes.
- The manual teaches both game meaning and implementation, but it introduces
  implementation only after the reader has the concept.
- Designers, gameplay programmers, and engine developers can read the same
  manual at different depths.

### Allowed Vocabulary

Allowed:

- Dungeons & Dragons
- tactical videogame
- player
- designer
- developer
- actor
- rule
- action
- state
- client
- runtime
- dungeon master as metaphor

Avoid:

- UUID
- registry
- `BaseObject`
- `ModifiableValue`
- `Event`
- handler
- trigger
- condition as an implementation class
- action template
- dice result processor

### Section Order

1. **What You Are Building**
   - Introduce NeuroDragon as a tactical D&D videogame engine.
   - Explain that the engine is built for rules-rich play: actors, actions,
     resources, visibility, items, spells, turns, and encounters.

2. **The Engine As Dungeon Master**
   - Explain the metaphor positively.
   - The engine receives intent, checks whether it is legal, resolves rules,
     updates the world, and reports the outcome.
   - Keep this player/designer-friendly.

3. **Three Reader Roles**
   - Designer: understands game systems and tuning.
   - Gameplay programmer: adds actions, spells, items, monsters, class features.
   - Engine developer: works on primitives, state flow, APIs, and infrastructure.

4. **What The Manual Teaches**
   - Introduce the curriculum arc in prose:
     game vocabulary -> runtime identity -> actor model -> rule machinery ->
     world/perception -> actions/combat -> content authoring -> APIs.
   - Do not list every future chapter as a dry table. Make it readable.

5. **How The Manual Relates To D&D Rules**
   - Explain SRD/reference material as source vocabulary and comparison material.
   - Explain that NeuroDragon has one videogame ruleset, not runtime profiles.
   - Phrase this as "the manual names the chosen implementation" rather than
     negating alternate modes.

6. **What Comes Next**
   - The next chapter teaches how to read examples and run focused checks.

### Required Diagram

Create:

- `/public/diagrams/engine-as-dungeon-master.svg`
- `/public/diagrams/engine-as-dungeon-master.excalidraw`

Diagram content:

```text
Player / AI intent
        ↓
NeuroDragon engine
  validate -> resolve -> update -> explain
        ↓
Client state, combat log, available next choices
```

Style:

- Same quiet Types Farm-inspired visual language as existing diagrams.
- No decorative gradients.
- Caption should teach the relationship: "The engine is the software dungeon
  master: it turns intent into state and readable outcomes."

### Code Policy

No Python code in Chapter 00. A small repository map is allowed only if it helps
transition into Chapter 01.

### Browser Acceptance

- Hero/banner remains present.
- Chapter reads as a full article, not a stub.
- No empty tables.
- No note/test/source links.
- No internal planning language.
- Search check: no `EventHandler`, `ModifiableValue`, `BaseObject`, `registry`,
  `pytest`, `make_bonus`, `fixed_randint`.

## Chapter 01 Brief: How To Read And Run Examples

### Working Frontmatter

```yaml
title: "How To Read And Run Examples"
subtitle: "The project layout, import style, and focused checks used throughout the manual."
order: 1
part: "Orientation"
rules: []
```

### Reader Outcomes

By the end of the chapter, the reader should understand:

- Where the engine, tests, manual site, rules reference, and examples live.
- How the manual formats code examples.
- How import tables work.
- How to run focused `uv` checks for one chapter or one concept.
- How deterministic examples will be written when randomness matters later.

### Allowed Vocabulary

Allowed:

- repository
- package
- module
- import
- example
- focused check
- `uv`
- `pytest`
- tutorial scene
- deterministic dice as a future convention

Avoid:

- Teaching registries, values, events, handlers, dice processors, conditions,
  action templates, spell slots, or combat flow.

### Section Order

1. **What This Chapter Gives You**
   - Set expectation: this is the operating manual for the manual.

2. **Where The Pieces Live**
   - Include a table:

| Path | Role |
| --- | --- |
| `dnd/` | Engine package. |
| `tests/engine_book/` | Focused checks that prove manual examples. |
| `engine_book/` | Planning, notes, and private manual evidence. |
| `interactive_ruleset/` | Local D&D/SRD reference material. |
| `/home/tommaso/Dev/neurodragon_dev_manual` | WSL-native Astro webbook site. |

3. **How Examples Are Written**
   - Explain complete snippets vs focused excerpts.
   - Explain that imports appear before symbols are used.
   - Explain that examples build one tutorial cast over time.
   - Explain that assertions mean "observed result" in the manual.

4. **Where The Imports Come From**
   - This chapter should introduce the import-map convention with a toy table,
     even if it does not use engine imports yet:

| Symbol | Import | Why it appears |
| --- | --- | --- |
| `patch` | `from unittest.mock import patch` | Used later to make random rolls deterministic. |
| `uuid4` | `from uuid import uuid4` | Used later when the manual introduces object identity. |

   - Make clear these are examples of the convention, not concepts being taught
     yet.

5. **Running Focused Checks**
   - Show commands that are safe in this repo:

```bash
uv run pytest tests/engine_book/test_chapter_01_registries.py
```

```bash
uv run pytest tests/engine_book/test_chapter_03_dice_events.py -k d20
```

   - Explain that the manual uses focused checks for chapter parity.
   - Avoid telling readers to run the entire suite.

6. **Deterministic Examples**
   - Introduce the future convention:

```python
from unittest.mock import patch

with patch("random.randint", side_effect=[12]):
    ...
```

   - Explain that later dice chapters will use this exact shape so the result is
     readable and repeatable.

7. **What Comes Next**
   - The next chapter introduces D&D vocabulary for engine developers.

### Required Diagram

Create:

- `/public/diagrams/manual-reading-path.svg`
- `/public/diagrams/manual-reading-path.excalidraw`

Diagram content:

```text
Rules vocabulary -> Engine object -> Tutorial snippet -> Focused check -> Extension pattern
```

Caption:

"Each chapter turns one game idea into one engine concept, one readable example,
and one focused check."

### Browser Acceptance

- Tables are visibly formatted.
- Code blocks are readable and not cramped.
- No note/test/source links.
- No hidden imports in code examples.
- The `uv` commands are correct for the current `pyproject.toml`.
- Search check: no `EventHandler`, `ModifiableValue`, `BaseObject`,
  `DamageRollResultEvent`, `make_bonus`, `fixed_randint`, `completed_events`.

## First Pass Review Checklist

Run these before asking for review:

```bash
npm run build
```

```bash
curl -I http://127.0.0.1:4327/manual/00-what-neurodragon-is/
curl -I http://127.0.0.1:4327/manual/01-how-to-read-and-run-examples/
```

Manual text checks:

```bash
rg -n "note=|test=|Evidence|Anchors|make_bonus|fixed_randint|EventHandler|ModifiableValue|BaseObject" \
  /home/tommaso/Dev/neurodragon_dev_manual/src/content/manual
```

The first two chapters pass only when the search returns no public-content
violations, except for terms intentionally allowed in Chapter 01's future-import
convention table.
