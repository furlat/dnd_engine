# First Public Unit Plan

## Status

Draft published to the Astro webbook as
`src/content/manual/00-neurodragon-dev-manual.mdx`.

Self-review polish completed:

- Added explicit reader roles.
- Split the vocabulary glossary into themed tables.
- Tightened negative framing in the public prose.
- Added mobile table readability polish in the Astro chapter layout.
- Added page-level horizontal overflow guards and mobile diagram constraints.
- Verified a desktop screenshot and a calibrated narrow screenshot through
  headless Chrome.

Route verified:

- `http://127.0.0.1:4327/manual/00-neurodragon-dev-manual/`

Human browser review is still pending. Do not continue into the first
implementation chapter until this opening chapter has been reviewed for format,
tone, and reading experience.

## Decision

The first rebuilt public unit should be one substantial opening chapter:

`00-neurodragon-dev-manual.mdx`

Working title:

**NeuroDragon Dev Manual**

Subtitle:

**A developer dungeon master manual for a Dungeons & Dragons videogame engine.**

This first unit combines the previous ideas of "what NeuroDragon is" and
"D&D vocabulary for engine developers" into one long-form reading experience.
The opening should establish the central idea before sending the reader onward.
It should feel like the first chapter of a real manual.

## Purpose

The chapter should make a reader understand the project before seeing engine
internals. It should be positive, direct, and forward-facing:

- NeuroDragon is a tactical D&D-style videogame engine.
- The engine plays the dungeon master role in software.
- The game built on top of the engine has an arena, actors, turns, actions,
  equipment, spells, encounters, sessions, controllers, and client-facing API
  state.
- The manual teaches how D&D concepts become runtime systems.
- The manual will introduce imports and code only after the concept exists.

The chapter must not be framed around what the project is not. It can explain
boundaries, but its main posture is "this is the thing, here is how to think
with it."

## Evidence Already Checked For This Plan

The first chapter should be drafted from current code and local rules evidence,
not from old public prose.

Evidence read for this planning pass:

- `engine_book/webbook_rebuild_plan.md`
- `engine_book/notes/01_object_identity_and_registries.md`
- `engine_book/notes/06_entity_composition.md`
- `engine_book/notes/18_encounters_turns_controllers_and_apis.md`
- `interactive_ruleset/Gameplay/Combat.md`
- `server/event_server.py`
- `server/session.py`
- `server/api_models.py`
- `dnd/maps/arena_layout.py`
- `dnd/controller.py`
- `cli/orchestrator.py`

Evidence still required before publishing the page:

- `interactive_ruleset/Gameplay/Abilities.md`
- `interactive_ruleset/Gamemastering/Conditions.md`
- `interactive_ruleset/Equipment/Weapons.md`
- `interactive_ruleset/Equipment/Armor.md`
- `dnd/entity.py` sections for entity composition and creation.
- `dnd/actions_functional.py` sections for action discovery.
- `dnd/encounter.py` sections for encounter lifecycle.

The page is conceptual, so it does not need code snippets yet. It does need to
avoid making claims that these files do not support.

## Reader Promise

By the end of the first public unit, the reader should be able to say:

- What NeuroDragon is.
- What role the engine plays during a turn.
- What a player, designer, gameplay programmer, and engine programmer each care
  about.
- What D&D nouns will recur throughout the manual.
- What the game built above the engine exposes to clients and controllers.
- Why later chapters start from objects, values, dice, and events before combat,
  spells, classes, and APIs.

## Forbidden Concepts For The Opening Chapter

The opening chapter may mention some implementation names as future landmarks,
but it must not teach their mechanics yet.

Do not explain:

- UUID lookup contracts.
- Registry families.
- `ModifiableValue` channel mechanics.
- Event phases.
- `EventHandler` trigger matching.
- Dice result processors.
- Condition cleanup internals.
- Action template internals.
- Spatial handlers.
- Test parity.
- Notes, private planning files, or source archaeology.

Allowed future-landmark language:

- "Later, this actor becomes an `Entity`."
- "Later, ongoing effects become conditions."
- "Later, the manual shows the event record behind a turn."

The chapter must not use those terms as if the reader already understands them.

## Public Chapter Structure

### 1. Opening Scene

Start with a concrete play moment:

A player controls a hero in an arena. The hero chooses an action. The engine
checks whose turn it is, what the hero can see, whether the target is reachable,
what resources are available, what the dice say, what changes in the world, and
what the client should display.

This scene should name the core loop before any code appears:

1. Intent enters the runtime.
2. The engine validates the intent.
3. The engine resolves the rules.
4. The world state changes.
5. The client receives state and narrative.

### 2. What NeuroDragon Is

This section should use declarative, positive language.

NeuroDragon is:

- A D&D-style tactical videogame engine.
- A runtime for actors, map cells, actions, dice, effects, items, spells,
  encounters, and player-facing state.
- A software dungeon master that applies one chosen videogame ruleset.
- A content platform for designers and developers to add actors, features,
  items, spells, maps, and encounters.

Avoid a defensive list of "not a tabletop simulator" or "not a rules clone."
If a boundary is needed, state it as a design choice: "The engine chooses a
single videogame behavior when tabletop rules leave judgment to a human DM."

### 3. The Engine As Dungeon Master

Explain the responsibilities of the runtime in player-facing language:

| Dungeon Master Responsibility | NeuroDragon Runtime Responsibility |
| --- | --- |
| Hear what a player wants to do. | Receive an action request from a controller or API client. |
| Decide whether the action is possible. | Validate turn ownership, costs, range, map state, visibility, and targets. |
| Resolve uncertain outcomes. | Roll dice and apply bonuses, penalties, advantage, and resistance. |
| Update the world. | Change HP, positions, conditions, inventory, equipment, and encounter state. |
| Tell the table what happened. | Emit events, combat logs, API DTOs, and client state. |

This table is central. It should be visually polished and readable.

### 4. The Game Built On Top

Introduce the higher-level game surfaces early so readers understand where the
manual is going.

Mention, without deep implementation:

- The standard arena fixture: floor, darkness, directional wall and door,
  difficult terrain, water, spike zone, torches, potions, and a lever.
- Encounters: initiative order, rounds, turns, factions, and encounter end.
- Controllers: human, Codex, AI, and pass controllers.
- Sessions: players own entities, join games, and act on the active turn.
- API state: entities, grid, visibility, available actions, combat logs,
  equipment, spells, map editor snapshots, and event streams.
- Authoring: maps, objects, saved maps, scenarios, monsters, class factories,
  spells, and features.

This section should make the manual feel like it covers the whole product, not
only engine primitives.

### 5. D&D Vocabulary For Developers

Teach game nouns in a compact but substantial glossary. Each row should have:

- Term.
- Game meaning.
- Why it matters to the engine.
- Where the detailed chapter will appear later.

Required terms:

- Actor/creature.
- Ability score and modifier.
- Skill.
- Saving throw.
- Action.
- Bonus action.
- Reaction.
- Movement.
- Turn.
- Round.
- Encounter.
- Armor class.
- Hit points.
- Damage.
- Healing.
- Condition.
- Spell.
- Equipment.
- Item.
- Visibility/perception.
- Faction.

Do not teach engine class mechanics in this section. Use future references only:
"later this is represented by..."

### 6. One Videogame Ruleset

State the rules stance clearly:

- SRD markdown is reference material.
- NeuroDragon implements one coherent videogame ruleset.
- When tabletop rules require a human GM, the engine chooses explicit runtime
  behavior.
- BG3-style choices are engine truth where they have been selected.
- The manual compares to SRD to explain origin and divergence, but it does not
  present alternate runtime modes.

This is also where to introduce examples:

- Shove is a videogame-style bonus action with passive target resistance.
- Forced movement and voluntary movement are distinct because reactions such as
  opportunity attacks depend on that distinction.
- Equipment uses a videogame loadout model, including separate melee and ranged
  sets.

Keep this high level. The mechanical proof belongs in later chapters.

### 7. How The Manual Teaches Code

This is the only process section allowed in the public opening, and it must be
reader-facing rather than rebuild-meta.

Promise:

- Imports are shown before code uses them.
- Examples build one tutorial scene over time.
- Helpers are defined before use.
- Examples show setup, action, and observed result.
- Tests verify examples privately, but public prose reads like a manual.

Do not mention previous mistakes, note links, parity rows, or internal planning.

### 8. Reading Path

End with the dependency ladder in human language:

1. The game and its vocabulary.
2. Runtime identity and actors.
3. Values, modifiers, and dice.
4. Events and reactions.
5. Conditions, world, movement, and perception.
6. Actions, combat, equipment, and items.
7. Spells, classes, monsters, and encounters.
8. Sessions, APIs, map authoring, and extension tutorials.

This should feel like an invitation, not a task list.

## Required Visuals

### Visual 1: Engine As Dungeon Master

Format: Excalidraw source plus exported SVG.

Purpose: Show the runtime loop.

Nodes:

- Player or AI controller.
- Action request.
- NeuroDragon engine as software DM.
- Rule resolution.
- World state.
- Client/API response.
- Combat log/event stream.

Caption:

"NeuroDragon receives intent, resolves rules, mutates the world, and returns a
client-readable outcome."

### Visual 2: Vocabulary Map

Format: Excalidraw source plus exported SVG.

Purpose: Show how game nouns relate before engine classes appear.

Center:

- Actor.

Surrounding clusters:

- Intent: action, bonus action, reaction, movement.
- Uncertainty: ability, skill, save, dice.
- Consequences: damage, healing, condition, spell.
- World: grid, visibility, equipment, item.
- Encounter: turn, round, faction, objective.

Caption:

"The manual teaches game nouns first, then shows how NeuroDragon represents
them."

### Visual 3: Manual Reading Path

Format: Excalidraw source plus exported SVG.

Purpose: Give the reader a curriculum.

Sequence:

Game -> Actor -> Values -> Dice -> Events -> Conditions -> World -> Actions ->
Combat -> Content -> Game/API.

Caption:

"The book follows dependency order so each subsystem appears after the reader
has the concepts it needs."

## Existing Visual Asset Policy

The opening page should use the existing banner art without color swapping. The
banners are already dark-mode safe.

Do not use purely decorative diagram clutter. Every visual must teach one
relationship.

## Layout Requirements

The page should be substantial enough to read pleasantly.

Target shape:

- One hero/header area.
- Three main diagrams.
- Two to three polished tables.
- Long-form prose between visuals.
- No note/test/source link blocks.
- No small card grid as the main reading experience.
- No forced click-through to understand the first chapter.

The page should leave a hint of the next section visible in the first viewport
on both desktop and mobile.

## Code Policy For The Opening

The opening chapter should include no substantial Python code. It is the
conceptual gateway.

Allowed:

- A tiny command block only if needed later for running the site or tests, but
  this first unit probably does not need it.

Forbidden:

- Hidden imports.
- Test helper references.
- Source links as explanatory crutches.
- Pasted test bodies.

The import-map standard begins in the first implementation chapter:

`01-runtime-identity-and-registries.mdx`

## Acceptance Gate For This First Unit

Before publishing `00-neurodragon-dev-manual.mdx`, verify:

- The page contains no private note/test/parity links.
- The page uses positive presentation more than negation.
- Every technical term is either plain D&D vocabulary or explicitly marked as a
  future implementation concept.
- There are no unexplained handlers, registries, modifiers, or event phases.
- SRD is described as reference material, not as a second runtime mode.
- The page includes the engine-as-DM table.
- The vocabulary table includes all required terms.
- The reading path appears at the end.
- Diagrams render and are captioned.
- Tables are styled and readable in the browser.
- Astro build passes.

## Follow-Up After The First Unit

After browser review of the opening chapter, the next public unit should be:

`01-runtime-identity-and-registries.mdx`

That page is where code begins. It must include:

- A visible import map.
- A complete tutorial setup.
- A real explanation of UUID identity and registries.
- No mention of handlers, conditions, dice processors, or action templates.

The first code chapter should be planned separately before it is written.
