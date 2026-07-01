# NeuroDragon Dev Manual Reset Plan

## Status

Superseded by `engine_book/webbook_rebuild_plan.md`.

The public Astro topic pages have been deleted again. This file is retained as
historical planning material only; do not treat the chapter list below as the
current public manual state.

## Current Reset State

The generated Astro topic pages were removed from the manual content collection.
The public webbook should be treated as empty until the rebuilt reader journey is
approved and the first substantial chapter is intentionally published.

This file remains the planning gate for the restart. Do not restore old topic
pages or partial chapters just because notes or tests exist. Notes are
evidence. Tests are verification. The public manual is a teaching sequence.

## Purpose

The current web manual draft is being discarded because it teaches from the
wrong direction. It exposed parity notes, test helper names, unexplained
handlers, and low-level implementation fragments before the reader had a mental
model for the game or the engine.

This plan defines the replacement manual before any topic pages are rewritten.
The manual must read like a real developer dungeon master manual: it teaches how
Dungeons & Dragons becomes a videogame runtime, how NeuroDragon organizes that
runtime, and how a developer can safely extend it.

## Non-Negotiable Reader Contract

- The manual explains NeuroDragon on its own terms: what it is, how it works,
  and how players, designers, and engineers should reason about it.
- The manual never starts a chapter with internals that depend on concepts the
  reader has not learned yet.
- A technical term must be introduced in plain language before it is used as an
  assumed concept. For example, `EventHandler` cannot appear as an explanation
  until the manual has already taught `Event`, event phases, triggers, and the
  queue.
- Every code example shows its imports, setup, action, and observed result, or
  explicitly says it is a focused excerpt from a previously introduced setup.
- Every chapter that uses code includes a "Where The Imports Come From" section
  before the first substantial snippet. This section maps each imported symbol
  to its module and its role in the example.
- Public examples do not use unexplained parity-test helpers such as
  `make_bonus`, `make_damage_roll`, `fixed_randint`, `completed_events`, or
  `RegistryProbe`.
- If a helper improves readability, the manual defines it as tutorial code
  before using it, explains why it exists, and keeps it small enough for a
  reader to understand.
- Note links, test links, parity links, and internal research anchors do not
  render in the customer-facing manual. Evidence remains in the repository, not
  in the reading experience.
- Source links may exist in private planning and parity material, but public
  prose must not make the reader click away to understand the concept on the
  page.
- Tables, code blocks, diagrams, and callouts must be formatted as first-class
  teaching material.
- Excalidraw/SVG diagrams are used for relationships that are hard to hold in
  prose: registries, ownership, event flow, value channels, action discovery,
  condition cleanup, map/senses, and combat pipeline.

## Reader Journey

The manual must feel like a campaign book for developers. The reader should
first understand the world they are building, then the actor model, then the
rules machinery, then the extension points.

The preferred narrative arc is:

1. **Meet the game.** NeuroDragon runs a tactical D&D-style videogame. The
   engine plays the dungeon master role: it validates choices, resolves rules,
   updates state, and tells the client what happened.
2. **Meet the runtime objects.** Before rules can happen, the engine needs
   addressable objects: entities, values, blocks, items, events, and map cells.
3. **Meet the actor.** A creature is an `Entity` with abilities, skills, saves,
   health, inventory, equipment, senses, resources, actions, and conditions.
4. **Meet the rule machinery.** Modifiers, dice, events, handlers, and
   conditions explain how a written rule becomes deterministic software.
5. **Meet the world.** The grid, movement, terrain, light, stealth, visibility,
   and spatial effects explain how tactical positioning works.
6. **Meet combat and actions.** Action discovery, costs, attacks, shove,
   spellcasting, damage, healing, reactions, and combat logs become readable
   after the prior machinery exists.
7. **Meet content authoring.** Items, spells, classes, monsters, encounters, and
   APIs show how to build the actual game on top of the engine.

The notes and parity tests remain evidence, but they are not the reading order.
The reading order is the developer's learning path.

## Concept Dependency Rules

These gates prevent the next draft from jumping ahead:

| Concept | First Allowed Chapter | Before That Chapter |
| --- | --- | --- |
| Registry lookup | Objects, Identity, And Registries | Use "the engine can recover live objects by ID" in prose only. |
| Modifiers and channels | Values, Modifiers, And Context | Use "bonuses and penalties" in player-facing prose only. |
| Events | Events Before Handlers | Use "the engine records what happened" in prose only. |
| Handlers and triggers | Events Before Handlers, after phases and queue storage | Do not mention handlers in values, registries, or intro chapters. |
| Dice result processors | Dice And Roll Result Events | Teach raw dice first; processors come second. |
| Conditions | Conditions | Earlier chapters may say "ongoing effects" without implementation detail. |
| Spatial handlers | Grid/Movement or Conditions, whichever introduces the concrete use | Earlier chapters may say "zone effects" only. |
| Action templates | Action Discovery And Costs | Earlier chapters may say "available actions" only. |
| Combat logs | Events Before Handlers introduces completion logs; Core Combat Flow uses them fully | Intro may say "the client receives a readable outcome." |
| Spell concentration | Spellcasting Core | Condition chapter may teach linked cleanup with a non-spell toy example first. |

When writing, every paragraph should pass this question: "Has the manual already
taught the noun I am asking the reader to understand?"

## Running Tutorial Cast

To make examples feel like one coherent story, the manual should reuse a small
cast instead of inventing fresh names in every snippet:

- `hero`: the player-side tutorial actor.
- `goblin`: the first enemy target.
- `cleric`: a healer used once healing and spellcasting are introduced.
- `training_dummy`: a non-hostile target for pure mechanics.
- `arena`: a small `GridMap` rectangle used for movement, senses, and combat.

The cast starts simple. Early chapters may use UUIDs and values before full
entities exist, but as soon as entities are introduced, examples should return
to the same cast. This makes later examples feel like expanding a playable
scenario rather than running isolated test cases.

## Manual Teaching Order

The manual needs a curriculum, not a dump of subsystem notes. The sequence below
is the required dependency ladder.

### Part 0: Orientation

1. **What NeuroDragon Is**
   - Explain the game: D&D-inspired tactical videogame runtime.
   - Explain the developer-as-DM idea.
   - Explain that rules become deterministic software procedures.
   - Introduce the three reader roles: player-facing designer, engine developer,
     and gameplay programmer.
   - No code beyond a small repository map.

2. **How To Read And Run Examples**
   - Show the project layout.
   - Show how to activate the environment and run focused tests.
   - Show the standard tutorial setup imports.
   - Explain global state reset patterns without making the reader memorize
     test internals.
   - Define the snippet convention: complete snippets, focused excerpts, and
     observed result blocks.

3. **D&D Vocabulary For Engine Developers**
   - Creature, entity, ability score, skill, saving throw, action, bonus action,
     reaction, movement, turn, round, condition, spell, equipment, damage,
     healing, perception, and encounter.
   - Keep this player-facing and practical before code.
   - This chapter defines game nouns only; it does not explain engine classes.

### Part 1: Runtime Foundations

4. **Objects, Identity, And Registries**
   - Define UUID identity before any lookup-heavy code.
   - Explain `BaseObject`, `BaseValue`, `BaseBlock`, and `Entity` registries.
   - Show imports and a complete small entity/value/block setup.
   - Avoid fake probe classes in public examples unless the probe class is fully
     shown and explained as a teaching tool.
   - Reader outcome: understand how live objects are named and recovered.
   - Do not mention event handlers, conditions, action templates, or dice.

5. **Values, Modifiers, And Context**
   - Define what a modifiable value is in game terms.
   - Explain numerical modifiers, advantage, critical, auto-hit, resistance, and
     damage type modifiers.
   - Teach self channels before target channels.
   - Teach contextual modifiers only after static modifiers are clear.
   - Reader outcome: understand how D&D bonuses and situational effects compose
     without overwriting each other.
   - Do not mention handlers or the event queue; say "later systems read this
     value" when needed.

6. **Events Before Handlers**
   - Define an event as a versioned causal record.
   - Teach phases, lineage, parent/child structure, queue storage, and
     completion.
   - Only after that define handlers as subscriptions to specific event phases.
   - Reader outcome: understand why the engine records each state transition
     before learning any specific rule reaction.

7. **Dice And Roll Result Events**
   - Teach raw dice first: `Dice`, `DiceRoll`, `RollType`, advantage selection,
     critical damage.
   - Then connect dice to result events and handlers.
   - Demonstrate deterministic examples with `unittest.mock.patch`, shown in the
     snippet.
   - Reader outcome: understand how a roll becomes an auditable result that
     gameplay features can alter.

### Part 2: The Actor Model

8. **Entity Composition**
   - Explain the entity as the playable/AI actor container.
   - Cover ability scores, skills, saves, health, action economy, equipment,
     inventory, senses, spellcasting, faction, and conditions at a map level.

9. **Blocks, Ownership, Context, And Cleanup**
   - Explain `BaseBlock` as a container for values, handlers, and conditions.
   - Teach cleanup before complex conditions.

10. **Conditions**
    - First teach condition lifecycle generally.
    - Then teach standard D&D conditions.
    - Then teach linked conditions, subconditions, concentration cleanup, and
      spatial handlers.

### Part 3: World And Perception

11. **Grid, Tiles, Terrain, And Movement**
    - Define the world grid and positions.
    - Explain voluntary movement, step movement, forced movement, terrain costs,
      spatial enter/leave events, and collision.
    - Be explicit that forced movement is different from voluntary movement for
      opportunity-attack style reactions.

12. **Senses, Light, Stealth, And Visibility**
    - Explain what the actor knows, what the client may show, and how hidden or
      invisible entities become perceivable.

### Part 4: Actions And Combat

13. **Action Discovery And Costs**
    - Explain action templates, available action results, target lists, and
      action economy costs.

14. **Core Combat Flow**
    - Attack validation, target modifier propagation, d20 roll, outcome, damage
      roll result processors, damage application, combat logs.
    - Shove and other videogame-standard actions belong here after the reader
      knows movement and events.

15. **Equipment, Inventory, And Items**
    - Explain equipment slots, BG3-style separate melee/ranged loadouts,
      two-handed displacement behavior, inventory storage, item use actions, and
      environmental objects.

### Part 5: Magic, Classes, And Game Content

16. **Spellcasting Core**
    - Spell actions, slots, DCs, attack bonuses, saves, AoE, concentration, and
      spell result events.

17. **Spell Families**
    - Present implemented spells by gameplay role, not file order.

18. **Class Features, Feats, And Factories**
    - Explain feature registration, resources, handlers, action overrides, and
      factory construction.

19. **Monsters And Preset Actors**
    - Explain content construction patterns and how monsters become entities.

### Part 6: Running The Game

20. **Encounters, Turns, Controllers, And APIs**
    - Explain the engine as the game master.
    - Cover encounter lifecycle, faction survival, turn order, API event streams,
      and client-facing state.

21. **Arena Game, Sessions, And Client State**
    - Explain the actual playable arena built on top of the engine.
    - Cover standard arena setup, hero class fixture, skeleton role enemies,
      environment objects, human/AI/Codex controller modes, game sessions,
      client state payloads, available actions, action results, event cursors,
      and combat-log cursors.

22. **Map Editor And Scenario Authoring**
    - Explain map/editor state as a separate authoring surface.
    - Cover terrain, directional barriers, doors, floor objects, saved maps,
      walkability, visibility, and light payloads.

23. **Extending NeuroDragon**
    - Add a new condition.
    - Add a new action.
    - Add a new item.
    - Add a new spell.
    - Add a new class feature.
    - Each extension tutorial uses the same pattern: design intent, imports,
      implementation, test, and observed runtime behavior.

## Chapter Template

Every chapter should follow this structure unless there is a strong reason to
deviate:

1. **What You Are Learning**
   - Three to five concrete reader outcomes.

2. **D&D Meaning**
   - Explain the tabletop/game concept in plain language.

3. **NeuroDragon Model**
   - Explain the engine objects and why they exist.

4. **Where The Imports Come From**
   - Show a compact table mapping symbol, module, and role.
   - Include only imports used in that chapter.

5. **Imports And Setup**
   - Show exact imports for the chapter examples.
   - Establish any shared tutorial scene.

6. **Walkthrough**
   - Build examples in order.
   - Each example should introduce one new concept.

7. **Extension Guidance**
   - Show where a developer would plug in new behavior.

8. **Rules Relationship**
   - Explain how the implementation relates to SRD and videogame choices in
     prose, without presenting alternate runtime modes.

9. **What Comes Next**
   - Name the next prerequisite layer.

## Chapter Acceptance Gate

Before a chapter is allowed onto the Astro site, it must pass this checklist:

- The chapter starts with reader outcomes, not implementation trivia.
- Every concept used in headings has already been defined in this or an earlier
  chapter.
- The first code example includes imports or follows a clearly introduced setup
  from the same chapter.
- Every symbol in a code example is either imported in the chapter, built in the
  snippet, or explicitly introduced in prose immediately before the snippet.
- The chapter has no visible note/test/parity links.
- The chapter has no public examples using forbidden test helpers.
- Any table renders correctly on desktop and mobile.
- Any diagram has a plain-language caption explaining the relationship it
  teaches.
- The chapter ends by telling the reader what concept comes next.
- A private parity check maps the examples to tests, but the page itself reads
  like a manual.

## Code Example Standard

Examples must look like tutorial code, not test bodies pasted into MDX.

Required:

- Imports are visible the first time a symbol appears in a chapter.
- Setup is explicit: entities, values, map, equipment, handlers, and resources
  are introduced before use.
- Deterministic dice use `from unittest.mock import patch` and show the patch
  call directly.
- Assertions are allowed when they teach the expected result, but prose should
  explain the result immediately before or after the snippet.
- Names should be tutorial names: `hero`, `goblin`, `attack_bonus`,
  `damage_roll`, `burning_hands`, not `source_uuid`, `target_uuid`, or
  `Engine Book`.
- Imports should be grouped by module and kept close to first use. When a page
  has several examples, introduce a shared setup block and then label later
  snippets as "continuing from the setup above."
- Snippets should prefer real engine construction over fake test-only classes.
  A teaching probe class is allowed only when the chapter is explicitly about a
  base class and the probe class is fully defined in the snippet.
- Assertions should read like observed behavior. Avoid dense assertion clusters
  that only make sense as tests.

Forbidden in public examples unless defined in the same chapter:

- `make_bonus`
- `make_damage_roll`
- `make_d20_roll`
- `fixed_randint`
- `completed_damage_events`
- `improved_event`
- `worse_event`
- Probe classes that exist only in parity tests
- Any reference that only makes sense inside `tests/engine_book`

## Import Map Requirement

Every implementation chapter must include a table like this before code:

| Symbol | Import | Why it appears |
| --- | --- | --- |
| `Entity` | `from dnd.entity import Entity` | Creates actors in the tutorial scene. |
| `EntityConfig` | `from dnd.entity import EntityConfig` | Supplies initial position and block configuration. |

The table should be chapter-specific. It teaches the reader where to find the
engine surface, and it prevents hidden imports from turning the manual into a
magic trick.

## First Seven Chapter Briefs

The early manual must be especially disciplined because it creates the reader's
mental model. These briefs are the working outline for the first pass.

### 00. What NeuroDragon Is

Reader promise:

- Understand NeuroDragon as a tactical D&D videogame engine.
- Understand the engine-as-dungeon-master metaphor.
- Understand that the manual teaches both game meaning and implementation.

Allowed concepts:

- D&D, player, designer, developer, entity as "actor" in plain language,
  action, rule, state, client, runtime.

Avoid:

- UUIDs, registries, `ModifiableValue`, `Event`, handlers, conditions, and any
  code-heavy details.

Required visual:

- A high-level "developer dungeon master" diagram: player intent enters engine,
  engine resolves rules, client receives state and narrative.

### 01. How To Read And Run Examples

Reader promise:

- Know where the code lives.
- Know how examples are structured.
- Know how to run focused checks without running the entire historical suite.
- Know that tutorial snippets show imports and setup before behavior.

Allowed concepts:

- Repository layout, WSL/site split, `uv`, focused pytest files, tutorial scene,
  deterministic examples.

Avoid:

- Teaching engine internals. This chapter is about operating the manual.

Required code:

```bash
uv run pytest tests/engine_book/<focused_manual_test_file>.py
```

Only include a concrete command after the matching focused test file exists and
has been run successfully. Do not tell readers to run the full suite.

### 02. D&D Vocabulary For Engine Developers

Reader promise:

- Understand the game nouns before seeing engine classes.
- Understand the difference between an actor, an action, a resource, an effect,
  a roll, and an encounter.

Allowed concepts:

- Creature, entity as gameplay actor, ability score, skill, saving throw,
  action, bonus action, reaction, movement, condition, spell, equipment, damage,
  healing, perception, turn, round, encounter.

Avoid:

- Engine class details and code. This chapter should be readable by a designer.

Required visual:

- A game vocabulary map connecting actor, action, roll, effect, and world.

### 03. Objects, Identity, And Registries

Reader promise:

- Understand why runtime objects need stable identity.
- Understand the four registry families: objects, values, blocks, entities.
- Understand typed lookup and position indexing at a high level.

Allowed concepts:

- UUID, `BaseObject`, `BaseValue`, `BaseBlock`, `Entity`, typed lookup,
  `use_register`, entity position index.

Avoid:

- Handlers, conditions, dice, event phases, action templates.

Required import map:

| Symbol | Import | Why it appears |
| --- | --- | --- |
| `uuid4` | `from uuid import uuid4` | Creates explicit source IDs for tutorial objects. |
| `BaseObject` | `from dnd.core.base_object import BaseObject` | Shows the root object registry. |
| `BaseValue` | `from dnd.core.values import BaseValue` | Shows the value registry family. |
| `BaseBlock` | `from dnd.core.base_block import BaseBlock` | Shows the block registry family. |
| `Entity`, `EntityConfig` | `from dnd.entity import Entity, EntityConfig` | Creates an actor and shows entity lookup. |

Example policy:

- If using a probe class to teach `BaseObject`, define it in the snippet:
  `class TutorialObject(BaseObject): pass`.
- Explain that probe classes are teaching scaffolding for base-class behavior,
  not gameplay objects.

Required visual:

- Registry family diagram showing separate object/value/block/entity indexes.

### 04. Values, Modifiers, And Context

Reader promise:

- Understand how bonuses, penalties, advantage, critical status, auto-hit
  status, resistance, and contextual rules compose.
- Understand self channels before target channels.
- Understand target propagation as a later roll/action preparation step without
  mentioning handlers.

Allowed concepts:

- `ModifiableValue`, `NumericalModifier`, `AdvantageModifier`,
  `CriticalModifier`, `AutoHitModifier`, `ResistanceModifier`, static modifier,
  contextual modifier, self channel, target export/import channel.

Avoid:

- Event queue, handlers, actions, conditions as implementation objects.
  Conditions may be mentioned only as "many game effects use these modifiers."

Required visual:

- Value channel diagram with self static/contextual first, then target export
  and import.

### 05. Events Before Handlers

Reader promise:

- Understand that events are versioned records of state transition.
- Understand phases, lineage, queue storage, completion, parent/child events,
  cancellation, and combat-log boundaries.
- Only after all of that, understand a handler as a subscription to a phase.

Allowed concepts:

- `Event`, `EventType`, `EventPhase`, `EventQueue`, lineage UUID, parent event,
  child event, completion, cancel, passive callback, combat log, handler,
  trigger.

Avoid:

- Dice result processors, action templates, specific spell/class features.

Required visual:

- Lifecycle diagram: declaration -> execution -> effect -> completion, with
  handlers before completion and logs at completion.

### 06. Dice And Roll Result Events

Reader promise:

- Understand raw dice and roll results before processors.
- Understand advantage/disadvantage roll selection.
- Understand attack natural 1/20 and critical damage.
- Understand roll result events as the interception point for features.

Allowed concepts:

- `Dice`, `DiceRoll`, `RollType`, `AttackOutcome`, d20 result events, damage
  result events, healing result events, processors, deterministic dice via
  `unittest.mock.patch`.

Avoid:

- Full combat action flow except as a preview. Full attacks belong in Core
  Combat Flow.

Required import map:

- Must include `patch` from `unittest.mock`.
- Must show `Dice`, `DiceRoll`, `RollType`, `AttackOutcome`,
  `ModifiableValue`, `AdvantageModifier`, `AdvantageStatus`, and relevant event
  classes before use.

Required visual:

- Dice -> DiceRoll -> result event -> effective result -> consumer.

## First Draft Stop Point

The first restart pass should produce only chapters 00 and 01. Then stop for a
quality review before writing chapter 02. The review should check:

- Does the reader know what the manual is?
- Does the reader know how to run examples?
- Are there hidden imports?
- Is there any parity/test-note leakage?
- Are tables and diagrams visually acceptable in the browser?

After that review, continue with chapter 02 and chapter 03 as a pair, because
vocabulary and identity should reinforce one another.

Detailed page-level requirements for the first pass live in
`engine_book/manual_first_pass_spec.md`.

No chapter 02+ topic page should be created before chapters 00 and 01 pass this
review. In particular, do not publish objects, registries, modifiers, events,
dice, conditions, actions, or combat pages until the orientation chapters prove
the format.

## Evidence And Test Parity Policy

The manual and tests still need parity, but parity is an editorial constraint,
not visible content.

- Tests should prove the examples.
- The manual should not display note/test links inline.
- Internal frontmatter may keep source references if useful for tooling.
- A future private coverage report can map chapter sections to tests.
- Customer-facing pages should read as a book, not as a test index.

## Site Presentation Requirements

- Tables need full styling: readable spacing, header treatment, borders, mobile
  overflow behavior, and font choices consistent with the site.
- Code blocks should be wide enough for imports and setup without feeling like
  cramped snippets.
- Diagrams should be introduced by prose and should teach a relationship.
- The landing page should explain the manual's promise and reading path once
  topic pages exist.
- Empty or placeholder topic pages are worse than no page.

## Restart Procedure

1. Delete current topic pages from the Astro manual. **Done for the reset.**
2. Confirm the empty content collection builds and no stale topic route is
   served.
3. Fix site-level presentation issues: table styling and visible source-link
   removal.
4. Draft the first two chapters only after this plan is accepted:
   - What NeuroDragon Is
   - How To Read And Run Examples
5. Review those chapters for tone, imports, tutorial quality, and visual
   formatting before continuing.
6. Continue chapter-by-chapter in dependency order.
