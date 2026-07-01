# Engine Book Goal

## Objective

Create a complete, bottom-up NeuroDragon developer manual and a matching test
coverage system. The manual must explain both Dungeons & Dragons as played
through the D&D engine and the videogame built on top of that engine.

The manual must be forward-facing. It should explain what NeuroDragon is, how
it works, what runtime truth each subsystem owns, and how players, designers,
gameplay programmers, client developers, and agent authors should understand
it. Avoid framing the book mainly through negation or through what the engine
is not.

The manual must stand on its own terms. Each chapter should first teach the
game concept and the product experience it enables, then the engine objects and
runtime flow that make it true. It should not read like a defense of design
choices, a conversion log, a parity checklist, or a set of notes cleaned up for
publication.

The public manual is a webbook, not an internal notes folder. It must be
customer-facing, polished, navigable, and pleasant to read. Planning notes,
verification notes, parity bookkeeping, and internal reasoning belong in
`engine_book/` or tests, not in public chapter prose.

The public manual must not be structured as a collection of note links, test
links, or progress artifacts. Runtime source links are useful for inspection,
but they are not a substitute for explanation. A reader should learn the idea
from the page itself, then optionally inspect source code, diagrams, or public
tutorial surfaces for more detail.

The book must teach the game built on top of the engine as well as the engine
itself. A reader should come away understanding both how Dungeons & Dragons is
played through NeuroDragon and how this videogame runtime represents players,
maps, scenarios, encounters, clients, controllers, agents, and authored content.

Think of the public manual as the developer-facing dungeon master manual for
NeuroDragon. It should teach how the software runs the table: what the player
sees, what the designer authors, what the engine adjudicates, and what the
client or agent receives. The tone should be confident and constructive, not a
list of caveats or a record of how the page was produced.

The book must explain the engine from first principles, starting at the lowest primitives and building upward through every major subsystem:

1. Values, modifiers, dice, rolls, and result processors.
2. Objects, registries, blocks, entities, and ownership.
3. Events, event phases, handlers, spatial handlers, combat logs, and lifecycle callbacks.
4. Conditions, duration, cleanup, subconditions, linked conditions, and concentration.
5. Actions, costs, action discovery, templates, execution, reactions, and multi-target/AoE convolution.
6. Combat mechanics: attacks, AC, damage, healing, death, saves, skill checks, advantage, criticals, resistances, factions, opportunity attacks, and movement.
7. Grid, tiles, terrain, pathfinding, spatial events, directional blocking, light, senses, stealth, invisibility, and perception.
8. Equipment, inventory, items, usable items, stackables, environmental objects, and lifecycle hooks.
9. Spellcasting infrastructure, spell actions, spell slots, concentration spells, zones, reactions, save spells, attack spells, healing spells, and implemented spell catalog.
10. Class and feature systems for implemented classes and features.
11. Encounters, turns, controllers, CLI/server/API surfaces, serialization, combat logs, and frontend-facing event contracts where relevant.
12. Map editor authoring surfaces, entity-free map snapshots, objective layers, saves, and handoff boundaries.
13. Scenario packages, arena modes, live replication, controller automation, tactical agent interfaces, and agent decision patterns.

The work must also create or organize full test coverage with 1:1 parity
between the examples shown in the public webbook and executable tests in the
repository. Existing example coverage is the minimum baseline, not the target
ceiling.

Executable tutorial snippets must be real tutorial code. They may use imported
scene constructors only when those constructors are themselves documented as
public tutorial or product surfaces and the chapter explains what they build.
The public examples must not be thin references to abstracted test scripts,
unexplained helper methods, or hidden setup that a reader cannot inspect.
Assertions are verification, not the reader-facing explanation. Runnable
examples should print or otherwise expose compact, deterministic readouts of
the behavior they teach, and the public page should show the corresponding
output whenever the example is meant to demonstrate runtime behavior.

Imports are part of the teaching surface. The book must show readers where
runtime symbols come from, why those modules are the intended public surfaces,
and how imported values fit into the layer being taught. Imports may live in
collapsible setup panels for readability, but they must never become hidden
magic or require readers to reverse-engineer a test harness.

Examples must build a continuous bottom-up narrative. Early examples should
introduce the smallest runtime ideas; later examples should reuse those ideas
to build complete gameplay situations. The book should feel like a developer
manual that prepares a contributor to use and expand the codebase, not like a
set of disconnected test fixtures.

The goal also includes a code documentation hygiene pass: remove unprofessional, stale, misleading, or noisy comments from the codebase; standardize useful docstrings to Google style; and make Pydantic model fields consistently use `Field(...)` with clear descriptions where appropriate. Google style applies to docstrings, not comments.

## Public Webbook Requirements

The public manual currently lives as an Astro webbook at:

- `/home/tommaso/Dev/neurodragon_dev_manual`

The engine workspace remains the planning, verification, and source-study
workspace. The public webbook must satisfy these requirements:

- Title: `NeuroDragon Dev Manual`.
- Explain D&D concepts as playable videogame runtime concepts.
- Explain the game built on top of the engine: encounters, sessions, clients,
  map authoring, scenarios, arena mode, controllers, streams, and agents.
- Remove note-link style writing from public pages. Public pages may link to
  runtime source code, public tutorial surfaces, and diagrams, but should not
  send readers into rough planning notes as the primary experience.
- Public pages must explain the feature directly. Source links are for
  inspection after the explanation, not the explanation itself.
- Do not link to `engine_book/notes/`, completion matrices, parity matrices, or
  rebuild checkpoints from public pages as explanation. Those files are
  internal work surfaces.
- Do not use test files, parity records, completion matrices, notes, or rebuild
  checkpoints as the public explanation for a feature. Those artifacts prove
  the manual internally; they are not the manual.
- Keep imports visible and learnable. Each substantial example should expose a
  local **Code setup: imports and scene** panel or an equivalent reader-facing
  surface that shows imports, scene construction, and local definitions.
- Every imported runtime name used by a chapter should be introduced through
  code-surface tables, prose, source links, or the snippet-start panel.
- Each chapter should make clear which imports are engine primitives, product
  gameplay surfaces, tutorial scenario surfaces, or test-only internals that
  must not appear in public snippets.
- Examples should build a continuous tutorial narrative from primitives to full
  game loops. A reader should finish the book knowing how to use and extend the
  codebase.
- Examples should be written as tutorial code a reader can learn from. They
  must not be public wrappers around hidden pytest helpers, vague
  `make_scene()` calls, or unexplained shared reset utilities.
- Use diagrams heavily where relationships matter. Excalidraw sources are
  acceptable and preferred for editable architecture diagrams.
- Webbook navigation must preserve numeric chapter order even when chapter
  section labels repeat.
- Public prose must avoid internal verification language such as test harness,
  parity bookkeeping, private notes, or meta commentary about the writing
  process.

## Public Manual Quality Bar

The manual must be written as a complete product manual, not as a converted
notes folder. Every page should help a reader build a mental model of
NeuroDragon as a playable D&D videogame runtime and as an extensible engine.

Required qualities:

- Lead with what the system is and what experience it creates. Avoid opening
  pages by explaining what the system is not.
- Write in affirmative product language. The page should teach the ruling,
  runtime object, player experience, and extension point directly instead of
  being framed as a list of caveats, exclusions, or corrections.
- Describe D&D rules through the NeuroDragon ruleset: player-facing behavior,
  designer-facing authoring choices, and engine-facing runtime state.
- Explain the videogame built on top of the engine, including scenarios,
  sessions, controllers, streams, agents, map authoring, and arena modes when
  those layers appear.
- Introduce every technical term before using it. If a chapter mentions
  handlers, registries, payloads, streams, agents, scenario packages, or any
  other engine concept, the chapter must either define it locally or rely on an
  earlier chapter that already taught it.
- Treat imports as part of the lesson. A reader should know where a symbol
  comes from, why that module is the right public surface, and what layer of
  the engine or game it belongs to.
- Treat helpers as part of the lesson. If a public snippet uses a helper, the
  chapter must show the helper body or present it as a named public tutorial or
  product surface with prose explaining what game state it creates.
- Prefer anchored runtime source links and polished diagrams for inspection.
  Do not make readers follow note links, pytest files, parity tables, or
  planning records to understand the feature.
- Use diagrams where relationships matter. Editable Excalidraw sources are a
  preferred format for architecture and ownership diagrams; generated images
  can be planned with prompts when illustration is useful.

## Tutorial Example Quality Bar

Public examples must read like tutorial code a developer would actually learn
from. They are allowed to be tested, but they must not look or behave like
private test harnesses wearing documentation clothes.

Requirements:

- Each example must have visible imports and visible scene construction, either
  directly in the example or in the chapter's **Code setup: imports and scene**
  panel.
- The setup panel must teach the imports and scene, not merely hide them. It
  should name the actor, map, item, event, or subsystem being created and why
  it matters for the example.
- Helper functions are allowed only when their bodies are visible in the public
  page or when they are documented public tutorial/product surfaces with source
  links and prose explaining what they construct.
- Avoid abstract names such as `make_scene()` when they hide important state.
  Prefer domain names that teach the game situation, such as
  `create_gatehouse_duel()` or `create_tutorial_spellcaster()`, and explain the
  actors, map, items, or resources they create.
- Tests must execute the public examples; public examples must not be written
  as calls into private pytest fixtures, parity helpers, or test-only wrappers.
- The tested artifact is the tutorial code itself. The public snippet runner
  may provide execution plumbing, but it must not inject hidden domain setup or
  replace tutorial code with abstract helper calls.
- Every executable example must include assertions that match the behavior the
  prose just taught.
- Assertions must not be the only visible payoff. Public examples that teach
  runtime behavior should print a stable transcript or payload-style readout,
  show that output in the page, and assert the same transcript in focused
  tests or exact snippet parity.
- Example order matters. The examples should build a narrative from primitives
  to full play: identity, values, dice, events, conditions, movement, actions,
  combat, items, spells, encounters, clients, scenarios, controllers, and
  agents.
- Public snippets should prepare a contributor to use and extend the codebase,
  not merely prove that a hidden script can run.

## Manual Writing Standard

Each public chapter must read like a finished developer manual page for the
game and engine, not like a cleaned-up internal note. The page should present
the subsystem positively: what it is, what experience it creates, what runtime
truth it owns, and how readers can use or extend it.

Every chapter must teach in this order unless there is a documented reason not
to:

1. The Dungeons & Dragons concept as a player or designer understands it.
2. The NeuroDragon videogame experience built from that concept.
3. The engine objects, values, events, and state transitions that make the
   experience true.
4. The concrete source surfaces and imports a developer uses.
5. Runnable examples that demonstrate the behavior with visible assertions.

Terms must be introduced before they are used. A chapter should not discuss
handlers, registries, blocks, scenario packages, streams, payloads, agents, or
other engine concepts as if the reader already knows them unless an earlier
chapter has already taught the concept and the current page clearly builds on
that layer.

Imports are part of the teaching surface. If a snippet imports a symbol, the
chapter must make clear where that symbol lives and why this is the right
surface to use. Imports may be placed in collapsible setup panels for reading
flow, but they are never allowed to become hidden magic.

Public examples must be tutorial examples. They should be small enough to read,
complete enough to run, and direct enough that a developer can adapt them into
real engine or game code. Do not publish examples that are merely calls into
private pytest helpers, abstract parity fixtures, unexplained `make_scene()`
wrappers, or test scripts disguised as documentation.

Public pages should link to source code and polished diagrams when that helps
the reader inspect implementation. They should not rely on notes-folder links,
test files, completion matrices, or rebuild checkpoints as the explanation of
the feature.

## Reader Acceptance Gate

The public manual is accepted by reader experience before internal bookkeeping.
A chapter can have passing tests and still fail this goal if it does not teach
the reader how the game and engine work.

Each public chapter must satisfy this reader gate:

- The page opens from the positive idea: what Dungeons & Dragons concept is
  being represented, what the NeuroDragon videogame experience is, and what
  responsibility the engine takes on.
- The page defines its technical vocabulary before using it. A reader should
  not meet handlers, registries, payloads, tactical state, scenario packages,
  or similar terms as unexplained machinery.
- The page explains the subsystem directly in prose. Links to source code,
  diagrams, and SRD references support inspection; they do not replace the
  explanation.
- The page does not send readers to notes, tests, parity tables, completion
  matrices, or rebuild logs to understand the feature.
- Imports are presented as part of the lesson. The reader sees where symbols
  come from, which layer they belong to, and why that surface is the one to
  use.
- Example setup is visible and named in domain terms. If a helper creates a
  duel, a map, a spellcaster, a scenario, or a client session, the page says
  that directly and shows or source-links the public surface that performs it.
- The executable examples build a tutorial narrative. They should make a
  reader more able to write or extend NeuroDragon code, not merely prove that
  a hidden fixture can call the runtime.
- Assertions in public snippets demonstrate the behavior just taught in the
  prose.
- The chapter closes with what the reader can now do and how that layer
  prepares the next layer.

For practical review, every chapter should answer these questions without
requiring private context:

1. What can a player or designer now understand about the game?
2. What runtime objects and events make that behavior true?
3. What code surface should a developer import from?
4. What complete, runnable example demonstrates the idea?
5. What test proves the exact public example still works?

## Exact Public Snippet Requirements

The public MDX snippets are authoritative examples. They must be executed
directly from the webbook source by the book-example test layer.

Requirements:

- Public Python fences must be marked with `book-example` metadata.
- Fences that form one example must execute in page order.
- The exact public fence contents should be executed without injecting hidden
  wrapper code into the runtime source.
- Imports and scene construction must be visible in the public page.
- Imported scenario or scene constructors are allowed only when they are
  documented and source-linked as public tutorial or product surfaces.
- Helper functions are allowed in public examples only when they are defined in
  the visible snippet or introduced as documented public tutorial/product
  surfaces. A reader must be able to see what the helper constructs, why it
  exists, and what behavior the example is asserting.
- Runtime reset/setup must be explicit enough for the reader to understand the
  state being cleared or created. Do not hide important setup behind private
  test-only helpers.
- Each executable example must include meaningful assertions about the behavior
  being taught.
- Reader-facing examples should also show useful runtime output: object
  summaries, lookup results, payload fields, event timelines, combat results,
  or other compact transcripts that make the behavior visible before the
  assertion locks it.
- The current exact public snippet runner lives at:
  `tests/book_examples/test_public_mdx_snippets.py`.
- Focused verification should include:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q`.
- The snippet runner is an internal proof mechanism. It must execute the public
  examples exactly, but public prose should not depend on the reader knowing how
  the pytest harness works.

## Scenario And MapEditor Boundary

Scenario packages are now an important design axis. They are acceptable as a
future engine/content concept, but their boundary must remain clear.

MapEditor is a separate WSL-side project at:

- `/home/tommaso/Dev/MapEditor`

The intended boundary is:

- MapEditor authors entity-free spaces.
- Scenario packages consume authored spaces and add play.

MapEditor-owned truth should include:

- grid bounds;
- tiles and terrain;
- directional borders;
- floor objects;
- light;
- walkability;
- visibility blockers;
- saved map documents;
- generated/rendered visual layers and asset references, when those exist.

Scenario-owned truth should include:

- spawn points and actor placement;
- actors, monsters, factions, and loadouts;
- controllers and player/session ownership;
- encounter creation and initiative setup;
- turn handoff rules;
- victory, defeat, and encounter-ending rules;
- scripted setup rules and product-mode packaging.

Do not integrate MapEditor and scenario packages prematurely. First document
the boundary and audit what the current `dnd.scenarios` package is doing.
Later integration should make saved map documents or authored map packages
feed scenario factories cleanly.

## Architecture Audit Requirement

The current worktree includes newly introduced surfaces such as `dnd.scenarios`,
content extensions, scenario packages, arena mode, live replication, map editor
support, and agent-facing APIs. These must not be treated as final architecture
merely because they exist.

Before declaring the manual or engine state complete, classify each new surface
as one of:

- core engine architecture;
- product/game-mode architecture;
- public tutorial support;
- temporary manual scaffolding;
- generated/cache output to remove;
- risky or accidental change needing review.

For each surface, decide whether it should remain where it is, move to a
tutorial/example package, become a first-class engine concept, or be deleted.

## Completion Matrix Requirement

Create and maintain a completion matrix for the full goal. The matrix must
track each subsystem/chapter against at least these columns:

- public manual prose complete;
- D&D/SRD rule relationship mapped;
- source-code surfaces linked;
- exact public snippets present;
- exact public snippets executed by `tests/book_examples`;
- deeper subsystem tests present;
- legacy examples represented or intentionally retained as script baselines;
- code comments/docstrings/Pydantic field metadata reviewed;
- known issues recorded;
- webbook UX/navigation verified.

The goal is not complete until the matrix shows every required subsystem as
complete or explicitly out of scope with Tommaso's approval.

## Rules Corpus

The engine book must relate implemented mechanics to the markdown rules material in the repository, especially:

- `interactive_ruleset/Gameplay/*.md`
- `interactive_ruleset/Gamemastering/*.md`
- `interactive_ruleset/Equipment/*.md`
- `interactive_ruleset/Classes/*.md`
- `interactive_ruleset/Spells/*.md`
- `interactive_ruleset/Monsters/*.md`
- `interactive_ruleset/Treasure/*.md`
- `interactive_ruleset/feats_srd5_2.md`

When a chapter explains a D&D concept, it must state one of:

- `SRD-aligned`: the engine follows the referenced SRD rule.
- `Engine adaptation`: the engine intentionally adapts or simplifies the SRD rule.
- `Not implemented`: the SRD rule exists but is not implemented.
- `Engine extension`: the engine includes behavior beyond the SRD material.

Do not quote large SRD passages. Summarize the rule, cite the local markdown file path, and explain how the engine models it.

## Bottom-Up Order

The work must proceed from lowest-level engine primitives to higher-level gameplay.

Do not start with spells, classes, or encounters before documenting and testing the primitives they rely on.

The expected order is:

1. Primitive data models and registries.
2. Modifiers and values.
3. Dice and roll-result events.
4. Event system and combat logs.
5. Blocks and entity composition.
6. Conditions and cleanup.
7. Action system.
8. Core combat and movement.
9. Spatial grid, terrain, lighting, senses, and stealth.
10. Equipment and item systems.
11. Spellcasting core.
12. Individual spell families and zones.
13. Class features and factories.
14. Encounters, controllers, APIs, serialization, and client-facing contracts.

Each layer must explicitly explain which lower layers it depends on.

## 1:1 Book Example And Test Parity

Every executable code example in the public webbook must have a corresponding
test or test section. For MDX webbook examples, the preferred proof is direct
execution from the public MDX source through `tests/book_examples`.

For each example, maintain a parity record with:

- Book chapter path.
- Example ID.
- Test file path.
- Test function or script section.
- Engine components exercised.
- SRD/rules references, if any.
- Current status: `covered`, `partial`, `missing`, or `intentionally-not-tested`.

An example is not considered finished until:

1. The book text explains the concept.
2. The code example is runnable or clearly marked pseudocode.
3. Imports, scene setup, and local definitions are visible or linked as public
   tutorial/product surfaces.
4. A matching test exists.
5. The test asserts the behavior shown in the book.
6. The parity record links them together.

## Test Coverage Requirements

Tests must be focused and runnable one file at a time. Exact public webbook
snippet execution belongs under `tests/book_examples/`. Additional deeper
engine/component coverage should live under appropriate focused pytest folders
such as `tests/manual/`, `tests/engine_book/`, or more specific subsystem test
folders as the test structure is cleaned up. The legacy `examples/test_*.py`
scripts remain an executable regression baseline until their behavior is
represented more professionally.

The final coverage must preserve at least parity with the behavior covered by the existing `examples/test_*.py` files, then go substantially deeper. Existing tests should be treated as the floor: every behavior currently protected by examples must remain represented, and each subsystem should gain lower-level, clearer, more granular tests where current coverage is missing, overly broad, script-like, stochastic, or only indirectly asserted.

Follow repository testing rules:

- Do not run the full pytest suite.
- Do not run server tests in batch.
- Prefer commands like `uv run python examples/test_<feature>.py` for legacy
  example scripts, `uv run pytest -q tests/book_examples/<file>.py` for exact
  public webbook snippets, and focused `uv run pytest -q tests/.../<file>.py`
  for deeper subsystem coverage.
- If using existing examples, preserve their style unless there is a deliberate migration plan.
- If new tests are needed, place them where they best match existing examples and naming patterns.

Coverage must include:

- Unit-like tests for primitive values, modifiers, dice, and event processing.
- Lifecycle tests for events, handlers, conditions, cleanup, and combat logs.
- Integration tests for entities, actions, movement, attacks, damage, healing, and death.
- Spatial tests for grid, pathfinding, terrain, light, senses, stealth, and invisibility.
- Item and equipment tests.
- Spell and class feature tests.
- Contract tests for serialization/API/event payloads where the book documents external behavior.

Where randomness is involved, tests should use deterministic helpers when possible. Retry loops are acceptable only when they match existing local patterns and have clear failure behavior.

For each subsystem, the test plan must identify:

- Existing example tests that already cover behavior.
- Existing example tests that should be preserved as regression tests.
- Gaps where deeper primitive or integration tests are needed.
- Book examples that need new parity tests.
- Areas where existing examples are too stochastic or script-like and need stronger deterministic coverage.
- Which legacy example behaviors have been represented in the `uv` pytest
  parity layer and which still remain as script-only regression baselines.
- Public snippets that still rely on tutorial-opaque helpers, hidden setup, or
  non-reader-facing imports, and the plan to replace them with clean tutorial
  code.

The exact-snippet layer is necessary but not sufficient. A snippet proving one
manual example runs does not replace deeper component tests for values, events,
conditions, movement, equipment, spells, encounters, APIs, map editor,
scenarios, streams, controllers, or agents.

## Code Documentation Hygiene Requirements

As the engine is studied from first principles, clean up docstrings, remove comments, and improve model metadata in the touched subsystems.

This hygiene track must be done carefully and incrementally, subsystem by subsystem, alongside the book chapters and tests.

Requirements:

- Remove comments that are unprofessional, misleading, obsolete, redundant, or merely narrate obvious code.
- Do not add new comments as documentation. Use Google-style docstrings for public modules, classes, methods, and functions where explanation is needed.
- If an existing comment captures a real invariant or design constraint, convert it into an appropriate docstring or book text instead of preserving it as a comment.
- Standardize docstrings to Google style:
  - Short summary line.
  - Optional explanatory paragraph.
  - `Args:` for parameters.
  - `Returns:` for return values.
  - `Raises:` for meaningful exceptions.
- Do not bulk-rewrite docstrings or remove comments without understanding the code they describe.
- Do not treat existing comments or docstrings as authoritative while rewriting them.
- For Pydantic models, prefer explicit `Field(...)` declarations with clear `description=` text for public model fields.
- Field descriptions should explain domain meaning, not restate the variable name.
- Avoid churn in purely private/internal variables unless their metadata is exposed or useful for serialization/API contracts.
- Preserve behavior. Comment/docstring/Field-description changes must not alter runtime semantics.

This track is complete only when each documented subsystem has had its comments, docstrings, and Pydantic field metadata reviewed as part of the same bottom-up pass.

## Book Structure Requirements

The public book should live in the Astro webbook project. Engine-book planning,
source study, parity bookkeeping, and completion tracking should live under
`engine_book/`.

Current structure:

- `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/`: public MDX
  webbook chapters.
- `/home/tommaso/Dev/neurodragon_dev_manual/src/components/`: webbook
  components such as runnable example framing and navigation.
- `engine_book/goal.md`: this goal and satisfaction criteria.
- `engine_book/outline.md`: complete chapter plan.
- `engine_book/parity_matrix.md`: example-to-test tracking table.
- `engine_book/completion_matrix.md`: goal-level completion matrix across
  prose, snippets, deeper tests, SRD mapping, source links, hygiene, and UX.
- `engine_book/glossary.md`: canonical vocabulary.
- `engine_book/notes/`: research notes that should not be treated as public
  manual pages.
- `engine_book/chapter_*_plan.md`: chapter planning files.
- `engine_book/webbook_rebuild_plan.md`: public webbook rebuild checkpoints.
- `tests/book_examples/`: pytest/uv tests that execute public MDX examples
  directly from the webbook source.
- `tests/manual/`, `tests/engine_book/`, or subsystem-specific test folders:
  deeper focused coverage as the professional test migration proceeds.

Chapters should be written as polished developer manual prose, not marketing
fluff and not internal notes. They should teach real engine use and expansion.

Every chapter should include:

- Purpose of the subsystem.
- Relevant source files.
- Main data models and methods.
- Event flow, if applicable.
- SRD/rules relationship, if applicable.
- Minimal example.
- Known limitations, engine adaptations, or intentional deviations.
- A forward bridge showing how the chapter prepares the reader for the next
  layer of the engine or game.

Public chapters should also include:

- a forward-facing ruling-role or equivalent explanation of what question the
  software dungeon master is answering;
- visible imports and scene setup for executable examples;
- source links for imported public runtime symbols;
- post-example capability summaries that tell the reader what they can now do.
- no note links, progress links, parity links, or test-harness links as a
  substitute for explanation.

The matching tests, parity records, and source-study notes remain required, but
they belong in the internal verification layer:

- `tests/book_examples/` executes exact public MDX snippets.
- `tests/manual/` and subsystem test folders provide deeper behavior coverage.
- `engine_book/parity_matrix.md` links public examples to their proof.
- `engine_book/completion_matrix.md` tracks chapter readiness.

The public webbook may cite runtime source files and public tutorial/scenario
surfaces. It should not ask the reader to understand the book by following
links into `engine_book/notes/`, pytest wrappers, or completion bookkeeping.

## Source Of Truth Priority

The engine book must be written from first principles by studying actual code behavior.

Do not trust existing docs, README text, architecture notes, or code comments as authoritative. Treat them only as hypotheses and navigation aids. Every claim about the engine must be verified against implementation code and, where possible, executable tests or direct examples.

When sources disagree, use this priority:

1. Current code behavior.
2. Existing executable examples/tests.
3. Current `AGENTS.md` architecture rules.
4. Current `claude_docs/` implementation references.
5. `interactive_ruleset/` SRD/rules markdown.
6. Older README or archived docs.

If documentation and code disagree, record the discrepancy instead of silently smoothing it over.

Code comments are not proof. If comments and implementation differ, document the implementation and flag the comment as stale or misleading.

## Satisfaction Criteria

This goal is complete only when all of the following are true:

1. `engine_book/outline.md` defines a complete bottom-up book structure.
2. Every major engine subsystem has a chapter or an explicit planned chapter.
3. Every chapter cites relevant source files and relevant SRD/rules files when applicable.
4. Every executable book example has a matching test.
5. `engine_book/parity_matrix.md` shows no unexplained `missing` entries.
6. Low-level systems are documented before dependent high-level systems.
7. The test suite additions or mappings cover all documented behaviors.
8. Existing example-test behavior remains represented at minimum parity, and new/deeper tests cover lower-level mechanics that existing examples only exercise indirectly.
9. Existing example tests remain runnable one file at a time.
9.1. Exact public webbook snippets are runnable through focused
`uv run pytest tests/book_examples/...` commands.
9.2. Deeper engine-book or subsystem parity is runnable through focused
`uv run pytest tests/engine_book/...`, `uv run pytest tests/manual/...`, or
similar one-file commands as those suites are organized.
10. Any discovered unrelated failing tests or bugs are recorded in `KNOWN_ISSUES.md` rather than silently fixed.
11. The final result lets a new contributor understand both how the engine works and how its D&D rules behavior is verified.
12. No chapter relies on pre-existing docs or comments without independent verification from code and tests.
13. Comments in covered subsystems are removed or converted into appropriate Google-style docstrings/book text.
14. Pydantic public model fields in covered subsystems have useful `Field(..., description=...)` metadata where appropriate.
15. The public Astro webbook builds successfully and all chapter routes render.
16. Public navigation preserves numeric chapter order.
17. Public pages avoid internal note links, hidden setup, and verification meta language.
18. Public snippets expose imports and scene setup through a reader-facing surface.
19. Public snippets avoid unexplained test-only helpers and form a coherent
    bottom-up tutorial narrative.
20. Public snippets show meaningful runtime output or payload readouts instead
    of relying on assertion-only code as the reader-facing result.
21. The exact public MDX snippet runner passes.
22. Scenario packages and MapEditor have a documented boundary.
23. Newly introduced architecture surfaces have been classified and either
    accepted, moved, postponed, or removed.
24. The completion matrix proves manual prose, snippets, tests, SRD mapping,
    source links, hygiene, and UX status for every required subsystem.
24. Public chapters teach both sides of the product: D&D as played through the
    engine and the videogame runtime built above it.
25. Public chapters explain imports, public code surfaces, and helper functions
    before relying on them in snippets.
26. Public snippets are tutorial code executed by tests, not wrappers around
    private pytest helpers, parity machinery, or unexplained setup scripts.
27. Public source links point to runtime code, public tutorial/product
    surfaces, SRD source references, or polished diagrams, not internal note
    files as the reader's explanation path.
28. The manual reads as a forward-facing developer manual, not a negation-led
    defense of architecture choices or a cleaned-up progress log.

## Non-Goals

- Do not rewrite the engine as part of writing the book unless a defect blocks test parity and Tommaso approves the implementation direction.
- Do not perform broad refactors just to make documentation easier.
- Do not replace the existing example test style wholesale.
- Do not perform purely mechanical comment churn across the entire repository without subsystem-level review.
- Do not run full-suite `pytest`.
- Do not use git checkout, rollback, reset, commit, or other git mutation.

## Initial Next Steps

1. Create or update the completion matrix for every chapter/subsystem.
2. Triage the current worktree into engine architecture, product architecture,
   tutorial support, temporary scaffolding, generated output, and risky changes.
3. Continue the public manual bottom-up, strengthening each chapter from
   structured draft into finished developer-manual prose.
4. Keep the exact public MDX snippet runner passing.
5. Add deeper focused subsystem tests beyond snippet execution.
6. Inventory SRD/rules markdown for each chapter as it is completed.
7. Audit scenario package and MapEditor boundaries before adding integrations.
8. During each subsystem pass, review comments/docstrings/Pydantic field
   metadata in the same low-level files.
