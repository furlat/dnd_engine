# NeuroDragon Dev Manual Webbook Rebuild Plan

## Current Verification Checkpoint

2026-06-30:

- Public snippet ownership is enforced by
  `tests/book_examples/test_public_mdx_snippets.py`.
- The suite extracts the exact `python book-example` fences from the public MDX,
  concatenates repeated fences with the same example name in page order, resets
  engine globals between examples, captures stdout, and compares the assembled
  source's actual output to the published `Result` transcript.
- Collapsed `book-imports` panels are part of the executable source. The suite
  now also proves every visible `ExampleBlock` owns executed Python and every
  executed Python fence lives inside exactly one `ExampleBlock`.
- Verification passed: `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
  collected 158 items and passed.
- Public prose cleanup pass removed remaining broad negation-heavy wording from
  Chapters 00-27 outside code fences.
- Astro build passed in `/home/tommaso/Dev/neurodragon_dev_manual`: 29 pages
  built.
- Public hygiene scan for test/private-note/meta leakage returned no matches.
- Running local web routes returned 200 for `/` and all 28 manual chapters at
  `http://127.0.0.1:4327`.

2026-07-01 public snippet output-parity and Chapter 08 checkpoint:

- Replaced the old public-example verification rule that required visible body
  assertions with stdout-to-`Result` transcript parity in
  `tests/book_examples/test_public_mdx_snippets.py`.
- Cleaned Chapters 01-08 public body snippets so reader-facing code prints
  tutorial output without `assert`, `expected_*lines`, or `AssertionError`
  scaffolding.
- Moved Chapter 08 `## First Run: Build And Measure A Corridor` below play
  meaning, board ownership, source-rule relationship, movement contract,
  chapter map, authoring guide, and code surfaces.
- Removed Chapter 08 from `CODE_FIRST_CHAPTERS`, added it to the open first-run
  import panel group, and added it to the assert-free public-body gate.
- Verification passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` with
  `280 passed`.
- Focused Chapter 08 manual tests passed:
  `uv run pytest tests/manual/test_08_world_model_and_movement.py -q` with
  `6 passed`.
- Astro build passed in `/home/tommaso/Dev/neurodragon_dev_manual` and built
  29 pages.
- Concept-first audit now reports `concept_first_count 18` and
  `example_first_remaining_count 9`, with Chapters 09-17 still staged for the
  same structural migration.

2026-07-01 Chapter 09 concept-first and assert-free public snippet checkpoint:

- Moved Chapter 09 `## First Run: Print A Turn Menu` below play meaning,
  command state, ruling role, the action runtime contract, turn choice surface,
  player-choice binding, source-rule relationship, chapter map, authoring
  guide, and code surfaces.
- Removed Chapter 09 from `CODE_FIRST_CHAPTERS`, kept its first setup panel
  open through `FIRST_RUN_OPEN_PANEL_CHAPTERS`, and added it to the
  assert-free public-code gate.
- Cleaned Chapter 09 public code so action examples print tutorial transcripts
  without public `assert`, `expected_*lines`, or `AssertionError` scaffolding.
- Focused public slice passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_actions_chapter_frontloads_choice_contract tests/book_examples/test_public_mdx_snippets.py::test_actions_chapter_examples_show_reader_visible_output tests/book_examples/test_public_mdx_snippets.py::test_assert_free_chapters_keep_verification_out_of_reader_code tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "09-action-discovery-and-costs or actions_chapter or assert_free"`
  with `11 passed, 157 deselected`.
- Focused Chapter 09 manual tests passed:
  `uv run pytest tests/manual/test_09_action_discovery_and_costs.py -q` with
  `8 passed`.
- Full public snippet suite passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` with
  `280 passed`.
- Astro build passed in `/home/tommaso/Dev/neurodragon_dev_manual` and built
  29 pages.
- Concept-first audit now reports `concept_first_count 19` and
  `example_first_remaining_count 8`, with Chapters 10-17 still staged for the
  same structural migration.

2026-07-01 Chapter 10 concept-first and assert-free public snippet checkpoint:

- Moved Chapter 10 `## First Run: Resolve One Hit` below play meaning, outcome
  state, ruling role, combat runtime contract, combat spine, selected-choice
  result flow, source-rule relationship, combat resolution contract, chapter
  map, authoring guide, and code surfaces.
- Removed Chapter 10 from `CODE_FIRST_CHAPTERS`, kept its first setup panel
  open through `FIRST_RUN_OPEN_PANEL_CHAPTERS`, and added it to the
  assert-free public-code gate.
- Cleaned Chapter 10 public code so combat examples print tutorial transcripts
  without public `assert`, `expected_*lines`, or `AssertionError` scaffolding.
- Focused public slice passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_combat_chapter_frontloads_resolution_contract tests/book_examples/test_public_mdx_snippets.py::test_combat_chapter_examples_show_reader_visible_output tests/book_examples/test_public_mdx_snippets.py::test_assert_free_chapters_keep_verification_out_of_reader_code tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "10-combat-resolution or combat_chapter or assert_free"`
  with `9 passed, 159 deselected`.
- Focused Chapter 10 manual tests passed:
  `uv run pytest tests/manual/test_10_combat_resolution.py -q` with
  `6 passed`.
- Full public snippet suite passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` with
  `280 passed`.
- Astro build passed in `/home/tommaso/Dev/neurodragon_dev_manual` and built
  29 pages.
- Concept-first audit now reports `concept_first_count 20` and
  `example_first_remaining_count 7`, with Chapters 11-17 still staged for the
  same structural migration.

2026-07-01 Chapter 11 concept-first and assert-free public snippet checkpoint:

- Moved Chapter 11 `## First Run: Track One Object` below play meaning, object
  state, ruling role, D&D gear translation, source-rule relationship, chapter
  map, item ownership contract, authoring guide, and code surfaces.
- Removed Chapter 11 from `CODE_FIRST_CHAPTERS`, kept its first setup panel
  open through `FIRST_RUN_OPEN_PANEL_CHAPTERS`, and added it to the
  assert-free public-code gate.
- Cleaned Chapter 11 public code so item examples print tutorial transcripts
  without public `assert`, `expected_*lines`, or `AssertionError` scaffolding,
  while preserving state-changing calls for looting, inventory storage, and
  equipment changes as normal tutorial statements.
- Focused public slice passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_items_chapter_frontloads_ownership_contract tests/book_examples/test_public_mdx_snippets.py::test_items_chapter_examples_show_reader_visible_output tests/book_examples/test_public_mdx_snippets.py::test_assert_free_chapters_keep_verification_out_of_reader_code tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "11-equipment-inventory-and-items or items_chapter or assert_free"`
  with `9 passed, 159 deselected`.
- Focused Chapter 11 manual tests passed:
  `uv run pytest tests/manual/test_11_equipment_inventory_and_items.py -q` with
  `6 passed`.

Later 2026-06-30 forward-facing prose checkpoint:

- Rewrote targeted negation-framed public prose in Chapters 09, 14, 15, and
  20 so the manual describes action discovery, spell families, character
  content, and content extensions as positive engine/game contracts.
- Extended `tests/book_examples/test_public_mdx_snippets.py` to reject the
  retired wording: `not just names in a list`, `not as a separate rules
  island`, `discovery is not execution`, `rather than a detached runtime mode`,
  and `Instead of painting the room`.
- Updated the chapter contract tests so the positive replacement text is
  guarded directly.
- Verification passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_manual_avoids_internal_meta_language tests/book_examples/test_public_mdx_snippets.py::test_actions_chapter_frontloads_choice_contract tests/book_examples/test_public_mdx_snippets.py::test_spell_families_chapter_frontloads_family_contract tests/book_examples/test_public_mdx_snippets.py::test_class_features_chapter_frontloads_character_content_contract tests/book_examples/test_public_mdx_snippets.py::test_content_extension_chapter_frontloads_extension_contract -q`
  with `5 passed`.
- Affected exact public snippets passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "09-action-discovery-and-costs or 14-spell-families-and-implemented-spells or 15-class-features-factories-and-feats or 20-content-extension-basics" -q`
  with `24 passed, 124 deselected`.
- Affected deeper manual tests passed:
  `uv run pytest tests/manual/test_09_action_discovery_and_costs.py tests/manual/test_14_spell_families.py tests/manual/test_15_class_features.py tests/manual/test_20_content_extension_basics.py -q`
  with `23 passed`.
- Full public snippet suite passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` with
  `234 passed`.
- Astro build passed in `/home/tommaso/Dev/neurodragon_dev_manual` and built
  29 pages.

Later 2026-06-30 Chapter 27 full visible-output cleanup checkpoint:

- Reworked Chapter 27 public examples so every decision-pattern snippet prints
  reader-visible output before asserting exact expected lines.
- Added `fixed_dice_faces` to the public Chapter 27 source surface and to
  attack-executing snippets so behavior-tree, factory, composite, and utility
  agent damage numbers are deterministic.
- Added the missing focused parity test for `agent-decision-surfaces` and
  converted the Chapter 27 focused tests to visible transcripts for decision
  surfaces, behavior-tree priority, melee factory behavior, `MoveAndAttack`,
  interrupt detection, utility ranking, and utility-agent execution.
- Added
  `tests/book_examples/test_public_mdx_snippets.py::test_agent_decision_chapter_examples_show_reader_visible_output`
  so Chapter 27 must keep seven output blocks, seven public transcript prints,
  exact transcript assertions, deterministic dice imports, and no helper/meta
  wording.
- Updated `engine_book/completion_matrix.md` and
  `engine_book/parity_matrix.md` with Chapter 27 visible-output evidence.
- Verification passed:
  `uv run pytest tests/manual/test_27_agent_decision_patterns.py -q` with
  `9 passed`.
- Exact Chapter 27 public snippets passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "27-agent-decision-patterns"`
  with `7 passed, 158 deselected`.
- Chapter 27 public-content slice passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k "27-agent-decision-patterns or agent_decision_chapter"`
  with `9 passed, 269 deselected`.
- Full public snippet suite passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` with
  `278 passed`.
- Astro build passed in `/home/tommaso/Dev/neurodragon_dev_manual` and built
  29 pages.

Later 2026-06-30 Chapter 01 concept-first structure checkpoint:

- Moved `## First Run: Create And Inspect Identity` below the Chapter 01
  conceptual path: play meaning, smallest runtime contract, runtime addressing,
  D&D reference translation, source relationship, chapter map, authoring guide,
  and code surfaces now appear before the first executable example.
- Kept the first Chapter 01 setup panel open so the first import surface remains
  visible when the tutorial begins.
- Removed Chapter 01 from the staged `CODE_FIRST_CHAPTERS` test bucket and added
  `FIRST_RUN_OPEN_PANEL_CHAPTERS` so open import panels and concept-first order
  are tracked separately.
- Updated
  `tests/book_examples/test_public_mdx_snippets.py::test_identity_chapter_frontloads_dnd_reference_translation`
  to guard the new Chapter 01 order.
- Updated `engine_book/completion_matrix.md` so current Chapter 01 evidence no
  longer describes the page as code-first.
- Verification passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_identity_chapter_frontloads_dnd_reference_translation tests/book_examples/test_public_mdx_snippets.py::test_identity_chapter_examples_show_reader_visible_output tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "01-runtime-identity-and-registries or identity_chapter"`
  with `8 passed, 159 deselected`.
- Focused Chapter 01 manual tests passed:
  `uv run pytest tests/manual/test_01_runtime_identity_and_registries.py -q`
  with `6 passed`.
- Structural public guards passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k "identity_chapter or public_technical_chapters or book_import_panels or srd_relationship or ruling_role"`
  with `16 passed, 262 deselected`.
- Full public snippet suite passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` with
  `278 passed`.
- Astro build passed in `/home/tommaso/Dev/neurodragon_dev_manual` and built
  29 pages.

Later 2026-06-30 Chapter 02 concept-first structure checkpoint:

- Moved `## First Run: Create And Inspect An Actor` below the Chapter 02
  conceptual path: play meaning, ruling role, entity shape, product-loop role,
  D&D creature translation, source relationship, chapter map, authoring guide,
  and code surfaces now appear before the first executable example.
- Kept the first Chapter 02 setup panel open so the first actor-construction
  import surface remains visible when the tutorial begins.
- Removed Chapter 02 from the staged `CODE_FIRST_CHAPTERS` test bucket and
  added it to `FIRST_RUN_OPEN_PANEL_CHAPTERS`, keeping open first imports
  separate from concept-first ordering.
- Updated
  `tests/book_examples/test_public_mdx_snippets.py::test_entity_chapter_frontloads_creature_translation`
  to guard the new Chapter 02 order.
- Updated `engine_book/completion_matrix.md` so current Chapter 02 evidence no
  longer describes the page as code-first.
- Verification passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_entity_chapter_frontloads_creature_translation tests/book_examples/test_public_mdx_snippets.py::test_entity_chapter_examples_show_reader_visible_output tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "02-entity-anatomy or entity_chapter"`
  with `4 passed, 163 deselected`.
- Focused Chapter 02 manual tests passed:
  `uv run pytest tests/manual/test_02_entity_anatomy.py -q` with `5 passed`.
- Structural public guards passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k "entity_chapter or public_technical_chapters or book_import_panels or srd_relationship or ruling_role"`
  with `18 passed, 260 deselected`.
- Full public snippet suite passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` with
  `278 passed`.
- Astro build passed in `/home/tommaso/Dev/neurodragon_dev_manual` and built
  29 pages.

Later 2026-06-30 Chapter 03 concept-first structure checkpoint:

- Moved `## First Run: Create And Inspect A Value` below the Chapter 03
  conceptual path: play meaning, value-ledger explanation, product-loop role,
  ruling role, D&D rule translation, source relationship, the value/modifier
  contract, chapter map, authoring guide, and code surfaces now appear before
  the first executable example.
- Kept the first Chapter 03 setup panel open so the first value-construction
  import surface remains visible when the tutorial begins.
- Removed Chapter 03 from the staged `CODE_FIRST_CHAPTERS` test bucket and
  added it to `FIRST_RUN_OPEN_PANEL_CHAPTERS`, keeping open first imports
  separate from concept-first ordering.
- Updated
  `tests/book_examples/test_public_mdx_snippets.py::test_values_chapter_frontloads_product_math_bridge`
  to guard the new Chapter 03 order.
- Updated `engine_book/completion_matrix.md` so current Chapter 03 evidence no
  longer describes the page as code-first.
- Verification passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_values_chapter_frontloads_product_math_bridge tests/book_examples/test_public_mdx_snippets.py::test_values_chapter_examples_show_reader_visible_output tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "03-values-and-modifiers or values_chapter"`
  with `7 passed, 160 deselected`.
- Focused Chapter 03 manual tests passed:
  `uv run pytest tests/manual/test_03_values_and_modifiers.py -q` with
  `5 passed`.
- Structural public guards passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k "values_chapter or public_technical_chapters or book_import_panels or srd_relationship or ruling_role"`
  with `16 passed, 262 deselected`.
- Full public snippet suite passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` with
  `278 passed`.
- Astro build passed in `/home/tommaso/Dev/neurodragon_dev_manual` and built
  29 pages.

Later 2026-06-30 Chapter 04 concept-first structure checkpoint:

- Moved `## First Run: Roll And Inspect A D20` below the Chapter 04
  conceptual path: play meaning, dice/roll-record vocabulary,
  product-loop role, ruling role, D&D dice translation, source relationship,
  the dice expression/roll-record contract, chapter map, authoring guide, and
  code surfaces now appear before the first executable example.
- Kept the first Chapter 04 setup panel open so the first dice-construction
  import surface remains visible when the tutorial begins.
- Removed Chapter 04 from the staged `CODE_FIRST_CHAPTERS` test bucket and
  added it to `FIRST_RUN_OPEN_PANEL_CHAPTERS`, keeping open first imports
  separate from concept-first ordering.
- Updated
  `tests/book_examples/test_public_mdx_snippets.py::test_dice_chapter_frontloads_product_roll_bridge`
  to guard the new Chapter 04 order.
- Updated `engine_book/completion_matrix.md` so current Chapter 04 evidence no
  longer describes the page as code-first.
- Verification passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_dice_chapter_frontloads_product_roll_bridge tests/book_examples/test_public_mdx_snippets.py::test_dice_chapter_examples_show_reader_visible_output tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "04-dice-rolls or dice_chapter"`
  with `8 passed, 159 deselected`.
- Focused Chapter 04 manual tests passed:
  `uv run pytest tests/manual/test_04_dice_rolls.py -q` with `6 passed`.
- Structural public guards passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k "dice_chapter or public_technical_chapters or book_import_panels or srd_relationship or ruling_role"`
  with `16 passed, 263 deselected`.

Later 2026-06-30 Chapter 05 concept-first structure checkpoint:

- Moved `## First Run: Create And Inspect A Lineage` below the Chapter 05
  conceptual path: play meaning, event-record vocabulary, product-loop role,
  ruling role, game-moment-to-lineage translation, event/queue contract,
  lifecycle contract, authoring guide, and code surfaces now appear before the
  first executable example.
- Kept the first Chapter 05 setup panel open so the first event-construction
  import surface remains visible when the tutorial begins.
- Removed Chapter 05 from the staged `CODE_FIRST_CHAPTERS` test bucket and
  added it to `FIRST_RUN_OPEN_PANEL_CHAPTERS`, keeping open first imports
  separate from concept-first ordering.
- Updated
  `tests/book_examples/test_public_mdx_snippets.py::test_event_chapter_frontloads_product_timeline_bridge`
  and
  `tests/book_examples/test_public_mdx_snippets.py::test_event_lifecycle_frontloads_phase_contract`
  to guard the new Chapter 05 order.
- Updated `engine_book/completion_matrix.md` so current Chapter 05 evidence no
  longer describes the page as code-first.
- Verification passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_event_chapter_frontloads_product_timeline_bridge tests/book_examples/test_public_mdx_snippets.py::test_event_lifecycle_frontloads_phase_contract tests/book_examples/test_public_mdx_snippets.py::test_event_lifecycle_examples_show_reader_visible_output tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "05-event-lifecycle or event_lifecycle or event_chapter"`
  with `9 passed, 159 deselected`.
- Focused Chapter 05 manual tests passed:
  `uv run pytest tests/manual/test_05_event_lifecycle.py -q` with `6 passed`.
- Structural public guards passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k "event_chapter or event_lifecycle or public_technical_chapters or book_import_panels or srd_relationship or ruling_role"`
  with `17 passed, 262 deselected`.

Later 2026-06-30 Chapter 06 concept-first structure checkpoint:

- Moved `## First Run: Register And Fire A Handler` below the Chapter 06
  conceptual path: play meaning, active timing role, ruling role, D&D
  timed-rule translation, three reaction surfaces, reaction dispatch contract,
  voluntary-step versus forced-movement policy, authoring guide, and code
  surfaces now appear before the first executable example.
- Preserved the important movement policy: opportunity-style reactions stay
  tied to `STEP_MOVEMENT`, while `FORCED_MOVEMENT` remains a separate surface
  that can still update spatial state and trigger position-based effects.
- Kept the first Chapter 06 setup panel open so the first handler-construction
  import surface remains visible when the tutorial begins.
- Removed Chapter 06 from the staged `CODE_FIRST_CHAPTERS` test bucket and
  added it to `FIRST_RUN_OPEN_PANEL_CHAPTERS`, keeping open first imports
  separate from concept-first ordering.
- Updated
  `tests/book_examples/test_public_mdx_snippets.py::test_reactions_chapter_frontloads_timing_contract`
  to guard the new Chapter 06 order.
- Updated `engine_book/completion_matrix.md` so current Chapter 06 evidence no
  longer describes the page as code-first.
- Verification passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_reactions_chapter_frontloads_timing_contract tests/book_examples/test_public_mdx_snippets.py::test_reactions_chapter_examples_show_reader_visible_output tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "06-reactions-to-events or reactions_chapter"`
  with `9 passed, 158 deselected`.
- Focused Chapter 06 manual tests passed:
  `uv run pytest tests/manual/test_06_reactions_to_events.py -q` with
  `7 passed`.
- Structural public guards passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k "reactions_chapter or runtime_response_and_choice or public_technical_chapters or book_import_panels or srd_relationship or ruling_role"`
  with `16 passed, 263 deselected`.

2026-07-01 Chapter 07 concept-first structure checkpoint:

- Moved `## First Run: Apply And Clean Up A Condition` below the Chapter 07
  conceptual path: play meaning, ongoing-state role, ruling role,
  D&D-condition-to-owned-artifact translation, condition/block contract,
  cleanup traversal contract, authoring guide, and code surfaces now appear
  before the first executable example.
- Kept the first Chapter 07 setup panel open so the first
  condition-construction import surface remains visible when the tutorial
  begins.
- Removed Chapter 07 from the staged `CODE_FIRST_CHAPTERS` test bucket and
  added it to `FIRST_RUN_OPEN_PANEL_CHAPTERS`, keeping open first imports
  separate from concept-first ordering.
- Updated
  `tests/book_examples/test_public_mdx_snippets.py::test_conditions_chapter_frontloads_ownership_contract`
  to guard the new Chapter 07 order.
- Updated `engine_book/completion_matrix.md` so current Chapter 07 evidence no
  longer describes the page as code-first.
- Verification passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_conditions_chapter_frontloads_ownership_contract tests/book_examples/test_public_mdx_snippets.py::test_conditions_chapter_examples_show_reader_visible_output tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "07-conditions-and-cleanup or conditions_chapter"`
  with `9 passed, 158 deselected`.
- Focused Chapter 07 manual tests passed:
  `uv run pytest tests/manual/test_07_conditions_and_cleanup.py -q` with
  `7 passed`.
- Structural public guards passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k "conditions_chapter or public_technical_chapters or book_import_panels or srd_relationship or ruling_role"`
  with `16 passed, 263 deselected`.

Later 2026-06-30 public result-panel checkpoint:

- Replaced the plain `Output:` marker before every public transcript with a
  rendered `<p className="example-output-label">Result</p>` label across the
  MDX manual, so example output reads as its own tutorial result surface.
- Added result-panel styling in
  `/home/tommaso/Dev/neurodragon_dev_manual/src/layouts/ManualChapter.astro`,
  including a distinct label, accent rule, left border, and dark terminal-style
  output block.
- Added
  `tests/book_examples/test_public_mdx_snippets.py::test_public_text_transcripts_are_result_panels`
  so every strict public chapter must keep one `Result` label per text
  transcript fence and cannot regress to stale `Output:` paragraphs.
- Updated the public snippet evidence in `engine_book/completion_matrix.md`
  from 278 to 279 tests.
- Verification passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` with
  `279 passed`.
- Focused layout/result guards passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_manual_layout_styles_tables_code_and_import_panels tests/book_examples/test_public_mdx_snippets.py::test_public_text_transcripts_are_result_panels -q`
  with `2 passed`.
- Astro build passed in `/home/tommaso/Dev/neurodragon_dev_manual` and built
  29 pages.

Later 2026-06-30 Chapter 01 smallest-contract checkpoint:

- Added `## The Smallest Runtime Contract` to Chapter 01 before the broader
  registry flow, so the reader first learns the low-level identity vocabulary:
  `uuid`, `name`, `source_entity_uuid`, `target_entity_uuid`, registry
  publication, and lookup family.
- Extended
  `tests/book_examples/test_public_mdx_snippets.py::test_identity_chapter_frontloads_dnd_reference_translation`
  so that smallest-contract section stays before `## Identity As Runtime
  Addressing`, before D&D reference translation, before source surfaces, and
  before executable examples.
- Verification passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_identity_chapter_frontloads_dnd_reference_translation -q`
  with `1 passed`.
- Chapter 01 exact public snippets passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "01-runtime-identity-and-registries" -q`
  with `5 passed, 143 deselected`.
- Chapter 01 deeper manual tests passed:
  `uv run pytest tests/manual/test_01_runtime_identity_and_registries.py -q`
  with `4 passed`.

Later 2026-06-30 Chapter 03 value/modifier contract checkpoint:

- Added `## The Value And Modifier Contract` to Chapter 03 before the chapter
  map, authoring guide, source surfaces, channels, and examples.
- The new section teaches the bottom of the rule-number stack: a
  `ModifiableValue` owns the calculation surface, base contribution, channels,
  aggregates, and breakdowns; a modifier owns one named rule contribution,
  payload type, optional target identity, contextual callable, and cleanup UUID.
- Extended
  `tests/book_examples/test_public_mdx_snippets.py::test_values_chapter_frontloads_product_math_bridge`
  so this contract stays after the source-rule relationship and before the
  chapter map, authoring guide, source surfaces, channel guide, placement
  guide, and examples.
- Verification passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_values_chapter_frontloads_product_math_bridge -q`
  with `1 passed`.
- Chapter 03 exact public snippets passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "03-values-and-modifiers" -q`
  with `4 passed, 144 deselected`.
- Chapter 03 deeper manual tests passed:
  `uv run pytest tests/manual/test_03_values_and_modifiers.py -q` with
  `4 passed`.

Later 2026-06-30 Chapter 04 dice expression/result contract checkpoint:

- Added `## The Dice Expression And Roll Record Contract` to Chapter 04 before
  the chapter map, authoring guide, source surfaces, roll-record guide, and
  examples.
- The new section teaches the dice layer as two owned surfaces: `Dice` owns the
  expression, category, attached value, damage outcome, critical extras,
  validation, and cached result production; `DiceRoll` owns result identity,
  expression identity, faces, total, bonus, roll-state snapshot, source/target
  identity, and damage context.
- Corrected the public roll category prose from nonexistent
  `RollType.SAVING_THROW` to the engine enum `RollType.SAVE`.
- Extended
  `tests/book_examples/test_public_mdx_snippets.py::test_dice_chapter_frontloads_product_roll_bridge`
  so the dice contract stays after the source-rule relationship and before the
  chapter map, authoring guide, source surfaces, roll guide, and examples, and
  so the public prose uses `RollType.SAVE`.
- Verification passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_dice_chapter_frontloads_product_roll_bridge -q`
  with `1 passed`.
- Chapter 04 exact public snippets passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "04-dice-rolls" -q`
  with `5 passed, 143 deselected`.
- Chapter 04 deeper manual tests passed:
  `uv run pytest tests/manual/test_04_dice_rolls.py -q` with `5 passed`.

Later 2026-06-30 Chapter 05 event record/queue contract checkpoint:

- Added `## The Event Record And Queue Contract` to Chapter 05 before the
  lifecycle contract, authoring guide, source surfaces, and examples.
- The new section teaches the event layer as two owned surfaces: `Event` owns
  one stored version of a game occurrence, identity, phase, lineage, causal
  children, resolved parent/child lineages, and final narration; `EventQueue`
  owns storage, indexes, active pre-completion dispatch, completion observation,
  passive callbacks, cursors, and event-tree lookup.
- Extended
  `tests/book_examples/test_public_mdx_snippets.py::test_event_chapter_frontloads_product_timeline_bridge`
  so the event record/queue contract stays after game-moment translation and
  before the lifecycle contract, authoring guide, source surfaces, and
  examples.
- Verification passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_event_chapter_frontloads_product_timeline_bridge -q`
  with `1 passed`.
- Chapter 05 exact public snippets passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "05-event-lifecycle" -q`
  with `5 passed, 143 deselected`.
- Chapter 05 deeper manual tests passed:
  `uv run pytest tests/manual/test_05_event_lifecycle.py -q` with `5 passed`.

Later 2026-06-30 Chapter 06 reaction dispatch contract checkpoint:

- Added `## The Reaction Dispatch Contract` to Chapter 06 before the broader
  reaction contract, authoring guide, source surfaces, and examples.
- The new section teaches the reaction layer as four owned dispatch surfaces:
  `Trigger` owns event matching, `EventHandler` owns trigger lists and
  processor callbacks, `SpatialHandler` owns position-indexed timing, and
  `EventQueue` owns handler indexes, dispatch, processor-return semantics, and
  the completion boundary.
- Extended
  `tests/book_examples/test_public_mdx_snippets.py::test_reactions_chapter_frontloads_timing_contract`
  so the dispatch contract stays after the three reaction surfaces and before
  the reaction contract, authoring guide, source surfaces, and examples.
- Verification passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_reactions_chapter_frontloads_timing_contract -q`
  with `1 passed`.
- Chapter 06 exact public snippets passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "06-reactions-to-events" -q`
  with `6 passed, 142 deselected`.
- Chapter 06 deeper manual tests passed:
  `uv run pytest tests/manual/test_06_reactions_to_events.py -q` with
  `6 passed`.

Later 2026-06-30 Chapter 07 condition/block ownership contract checkpoint:

- Added `## The Condition And Block Contract` to Chapter 07 before the broader
  condition contract, authoring guide, source surfaces, and examples.
- The new section teaches the condition layer as two cooperating owners:
  `BaseCondition` owns the named state, application artifacts, exact cleanup
  UUIDs, linked-condition reverse links, duration, and own-artifact cleanup;
  `BaseBlock` owns active-condition indexes, condition-capable state,
  application entry, tree removal, UUID removal, and duration progression.
- Extended
  `tests/book_examples/test_public_mdx_snippets.py::test_conditions_chapter_frontloads_ownership_contract`
  so the condition/block contract stays after D&D condition translation and
  before the condition contract, authoring guide, source surfaces, and
  examples.
- Verification passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_conditions_chapter_frontloads_ownership_contract -q`
  with `1 passed`.
- Chapter 07 exact public snippets passed:
  `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "07-conditions-and-cleanup" -q`
  with `6 passed, 142 deselected`.
- Chapter 07 deeper manual tests passed:
  `uv run pytest tests/manual/test_07_conditions_and_cleanup.py -q` with
  `5 passed`.

Later 2026-06-30 checkpoint:

- Public import/setup panels now use the reader-facing label
  **Code setup: imports and scene** throughout the manual.
- Chapter 00 explains how to read runnable tutorial examples: run the setup
  panel first, then the visible code below it; together they form one example.
- The public snippet suite now guards that orientation language and blocks stale
  import-panel labels and generic setup-panel boilerplate.
- Verification passed: `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
  collected 159 items and passed.
- Astro build passed again in `/home/tommaso/Dev/neurodragon_dev_manual`: 29
  pages built.
- Public hygiene scan returned no matches, and all 29 local routes returned 200
  from `http://127.0.0.1:4327`.

Later 2026-06-30 prose checkpoint:

- Replaced repeated chapter boilerplate such as "Each example has a Code setup"
  and "Open it to see import paths" with chapter-specific source guidance in
  Chapters 03 and 11-27.
- The new guidance ties setup panels to the actual chapter subject: values,
  items, perception, spellcasting, spell families, character features, monsters,
  encounters, sessions, map authoring, extensions, scenarios, arena mode,
  controllers, replication, and agent decisions.
- The public snippet suite now blocks the repeated setup-panel boilerplate,
  generic panel invitation, and generic deterministic-setup wording.
- Verification passed: `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
  collected 159 items and passed.
- Astro build passed again in `/home/tommaso/Dev/neurodragon_dev_manual`: 29
  pages built.
- Expanded public hygiene scan returned no matches, and all 29 local routes
  returned 200 from `http://127.0.0.1:4327`.

Later 2026-06-30 source-guidance checkpoint:

- Replaced public setup-disclosure jargon with **setup panel** language in
  Chapter 00 and Chapter 07.
- Replaced the vague `Local setup` source-table rows for `ApiClient` in
  Chapters 18 and 19 with `Defined in the code setup panel`, so reader-owned
  tutorial code has a visible source.
- Reframed "local setup function" as a scene-building function in the opening
  chapter.
- The public snippet suite now blocks vague setup-source language in public
  manual files.
- Verification passed: `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
  collected 159 items and passed.
- Astro build passed again in `/home/tommaso/Dev/neurodragon_dev_manual`: 29
  pages built.
- Expanded public hygiene scan returned no matches, and all 29 local routes
  returned 200 from `http://127.0.0.1:4327`.

Later 2026-06-30 narrative-continuity checkpoint:

- Added reader-facing **What Comes Next** closing sections to Chapters 11 and
  12, which previously ended directly after their final example block.
- Chapter 11 now connects inventory/equipment/map objects to the perception
  layer: visible objects, target rows, light, hidden state, and invisibility.
- Chapter 12 now connects observer-local knowledge to spellcasting: visible
  targets, spell slots, attacks, saves, events, and lasting magical effects.
- The public snippet suite now verifies that no converted public chapter ends
  directly on `</ExampleBlock>`; each chapter must close with reader-facing
  prose.
- Verification passed: `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
  collected 160 items and passed.
- Astro build passed again in `/home/tommaso/Dev/neurodragon_dev_manual`: 29
  pages built.
- Expanded public hygiene scan returned no matches, and all 29 local routes
  returned 200 from `http://127.0.0.1:4327`.

Later 2026-06-30 definition-heavy setup checkpoint:

- Audited setup panels that define five or more local functions/classes before
  the visible example code.
- Expanded the encounter combat-log setup panel in Chapter 17 so the reset,
  actor-pair, ordered-encounter, auto-hit, and cleanup functions are explained
  before use.
- Expanded the client API setup panels in Chapter 18 so `ApiClient`, runtime
  reset, actor creation, session join, target-row lookup, action execution, and
  stream cursor functions are explained as tutorial scene pieces.
- Expanded the map-editor setup panels in Chapter 19 so the authoring client,
  map reset, snapshot readers, map creation, tile patching, object placement,
  deletion setup, and save/load round trip are explained before use.
- The public snippet suite now verifies that setup panels with five or more
  local definitions include at least 60 words of setup explanation before the
  first executable code fence.
- Verification passed: `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
  collected 161 items and passed.
- Astro build passed again in `/home/tommaso/Dev/neurodragon_dev_manual`: 29
  pages built.
- Expanded public hygiene scan returned no matches, and all 29 local routes
  returned 200 from `http://127.0.0.1:4327`.

Later 2026-06-30 play-framing checkpoint:

- Audited public chapters for player/designer-facing language and found the
  advanced extension and agent chapters were technically correct but too
  implementation-forward.
- Added **What This Means In Play** sections to Chapters 21, 26, and 27.
- Chapter 21 now frames Aegis Spark as a player-visible protective spell and a
  designer-owned feature/spell/effect ownership pattern.
- Chapter 26 now frames the tactical interface as the same subjective choice
  surface a player sees, exposed to an agent designer without bypassing engine
  rules.
- Chapter 27 now frames behavior trees, composites, and utility scoring as
  recognizable tactical player behavior implemented through legal engine
  choices.
- The public snippet suite now verifies those advanced chapters keep
  player/designer play framing.
- Verification passed: `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
  collected 162 items and passed.
- Astro build passed again in `/home/tommaso/Dev/neurodragon_dev_manual`: 29
  pages built.
- Expanded public hygiene scan returned no matches, and all 29 local routes
  returned 200 from `http://127.0.0.1:4327`.

Later 2026-06-30 foundation play-framing checkpoint:

- Audited the early runtime-foundation chapters and found several low-level
  pages were still framed mainly as machinery instead of player/designer-facing
  game systems.
- Added **What This Means In Play** sections to Chapters 01, 04, 05, and 06.
- Chapter 01 now explains UUID identity as the reason heroes, targets, items,
  conditions, and spell effects stay coherent across clicks, turns, logs, and
  client updates.
- Chapter 04 now explains dice as visible uncertainty for players and reusable
  result records for designers.
- Chapter 05 now explains events as the client-visible record of game moments
  and as designer-facing cause/effect lineage.
- Chapter 06 now explains reactions as timed board responses and as the
  designer vocabulary for phase, result, and spatial timing.
- Replaced a stale public setup-panel label in Chapter 01 with **Code setup:
  imports and scene**.
- The public snippet suite now verifies these foundation chapters keep
  player/designer play framing.
- Verification passed: `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
  collected 162 items and passed.
- Astro build passed again in `/home/tommaso/Dev/neurodragon_dev_manual`: 29
  pages built.
- Expanded public hygiene scan returned no matches, and all 29 local routes
  returned 200 from `http://127.0.0.1:4327`.

Later 2026-06-30 middle-foundation play-framing checkpoint:

- Added **What This Means In Play** sections to Chapters 02, 03, 07, 08, 09,
  and 10.
- Chapter 02 now frames entities as the player-visible creature/character and
  the designer composition boundary for actor content.
- Chapter 03 now frames values as explainable player-facing numbers and as the
  designer placement map for bonuses, caps, resistances, and contextual effects.
- Chapter 07 now frames conditions as named ongoing states in play and
  ownership packages for designers.
- Chapter 08 now frames the world model as the tactical board players move on
  and the authoring surface for terrain, borders, hazards, and zones.
- Chapter 09 now frames action discovery as the player turn menu and the
  designer contract that turns authored content into selectable choices.
- Chapter 10 now frames combat resolution as selected buttons becoming results
  and as the shared designer pipeline for combat content.
- The public snippet suite's play-framing guard now covers Chapters 01-10 plus
  the advanced extension/agent chapters already enrolled.
- Verification passed: `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
  collected 162 items and passed.
- Astro build passed again in `/home/tommaso/Dev/neurodragon_dev_manual`: 29
  pages built.
- Expanded public hygiene scan returned no matches, and all 29 local routes
  returned 200 from `http://127.0.0.1:4327`.

Later 2026-06-30 full-manual play-framing checkpoint:

- Added **What This Means In Play** sections to Chapters 11-20 and 22-25, so
  every published technical chapter from 01 through 27 now opens its subject
  with player-facing meaning and designer-facing responsibility before the
  chapter map.
- Chapter 11 now frames items as physical board objects and as one reusable
  ownership/location/action model.
- Chapter 12 now frames perception as the player's visible and targetable world
  and as the designer contract for observer-local knowledge.
- Chapters 13 and 14 now frame spellcasting as player choices and spell
  families as runtime behavior patterns.
- Chapters 15 and 16 now frame classes, features, monsters, and presets as
  player-readable identity plus reusable actor packages.
- Chapters 17-20 now frame encounters, client APIs, map authoring, and content
  extension as the game-running and product-authoring layers above the engine.
- Chapters 22-25 now frame scenario packages, the standard arena, controllers,
  and live replication as complete videogame-mode surfaces.
- The public snippet suite's play-framing guard now covers Chapters 01-27.
- Verification passed: `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
  collected 162 items and passed.
- Astro build passed again in `/home/tommaso/Dev/neurodragon_dev_manual`: 29
  pages built.
- Expanded public hygiene scan returned no matches, and all 29 local routes
  returned 200 from `http://127.0.0.1:4327`.

Later 2026-06-30 narrative-bridge checkpoint:

- Audited the public manual for chapter-ending continuity and found Chapters
  13-16 and 19-27 did not consistently close with a clear reader bridge into
  the next layer.
- Renamed Chapter 13's closing section to **What Comes Next** and added its
  bridge from spellcasting core into spell families.
- Added **What Comes Next** closing sections to Chapters 14, 15, 16, and 19
  through 27.
- The new bridges connect spell families to class content, classes to monster
  presets, monsters to encounters, map authoring to content extension, custom
  content to spell/feature extension, scenarios to the standard arena,
  controllers to live replication, replication to agents, and final agent
  patterns back to the complete manual arc.
- The public snippet suite now verifies that every technical chapter from 01
  through 27 includes a **What Comes Next** bridge.
- Verification passed: `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
  collected 163 items and passed.
- Astro build passed again in `/home/tommaso/Dev/neurodragon_dev_manual`: 29
  pages built.
- Expanded public hygiene scan returned no matches, and all 29 local routes
  returned 200 from `http://127.0.0.1:4327`.

Later 2026-06-30 source-table guard checkpoint:

- Audited the public chapter source-orientation sections and confirmed every
  technical chapter has a **Code Surfaces In This Chapter** section before its
  first executable example.
- Standardized the source-table explanation column across Chapters 02 and
  11-27 to **What it teaches here**, replacing generic role/build wording.
- The public snippet suite now verifies every technical chapter from 01 through
  27 introduces code surfaces before examples, uses a source table with a
  tutorial explanation column, and does not fall back to generic `Role` table
  wording.
- Verification passed: `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
  collected 164 items and passed.
- Astro build passed again in `/home/tommaso/Dev/neurodragon_dev_manual`: 29
  pages built.
- Expanded public hygiene scan returned no matches, and all 29 local routes
  returned 200 from `http://127.0.0.1:4327`.

Later 2026-06-30 visible-import guidance checkpoint:

- Audited exact public snippet imports against the visible **Code Surfaces In
  This Chapter** sections.
- Added source-table rows for public names that readers see in example code but
  that were not yet introduced by the chapter tables, including event timing
  names, deterministic dice surfaces, actor factories, spell-family state,
  class-feature roll state, encounter lifecycle states, arena equipment slots,
  stream cursors, and agent behavior/utility primitives.
- Adjusted older function table labels such as `register_spell(...)`,
  `get_available_actions(...)`, `create_fighter(...)`, and
  `execute_use_action(...)` so the visible table names match the exact names
  used by tutorial code.
- The public snippet suite now parses the exact MDX code fences with `ast` and
  verifies that every visible name imported from `dnd`, `server`, or `ai`
  appears in that chapter's visible code-surface section.
- Verification passed: `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
  collected 165 items and passed.
- Astro build passed again in `/home/tommaso/Dev/neurodragon_dev_manual`: 29
  pages built.
- Expanded public hygiene scan returned no matches, and all 29 local routes
  returned 200 from `http://127.0.0.1:4327`.

Later 2026-06-30 local setup-name checkpoint:

- Audited local functions and classes defined inside collapsed setup panels and
  used by visible example code.
- Added exact-name setup prose in the foundation chapters now enrolled in the
  audit: Chapters 01, 02, 07, and 08.
- Chapter 01 now names `TutorialMarker`, `TutorialToken`, and
  `reset_identity_state()` before visible registry examples call them.
- Chapter 02 now names `create_tutorial_hero()` in the setup panel that defines
  the tutorial actor.
- Chapter 07 now names `TutorialActor`, `create_tutorial_actor()`, and
  `GuardedCondition` where condition examples use those local tutorial pieces.
- Chapter 08 now names `reset_world_state()` in each grid setup panel before
  the visible map examples call it.
- The public snippet suite now includes an enrolled guard proving that local
  function/class names defined in setup panels and used by visible code are
  named in that setup panel's prose.
- Verification passed: `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
  collected 166 items and passed.
- Astro build passed again in `/home/tommaso/Dev/neurodragon_dev_manual`: 29
  pages built.
- Expanded public hygiene scan returned no matches, and all 29 local routes
  returned 200 from `http://127.0.0.1:4327`.

Later 2026-06-30 local setup-name gameplay checkpoint:

- Extended the local setup-name audit from the foundation chapters into the
  first gameplay-system tranche: Chapters 09, 10, 11, and 12.
- Chapter 09 setup panels now name `reset_action_state()`,
  `create_tutorial_actor()`, `find_action()`, and `find_attack_action()` before
  visible action-discovery examples call them.
- Chapter 10 setup panels now name `reset_combat_tutorial_state()`,
  `make_melee_attack_auto_hit()`, `make_melee_attack_auto_crit()`,
  `clear_melee_attack_modifier()`, and `create_strong_actor()` before visible
  combat examples call them.
- Chapter 11 setup panels now name `reset_item_tutorial_state()`,
  `create_tutorial_actor()`, `put_in_inventory()`, and
  `create_tutorial_hand_crossbow()` before visible item/equipment examples call
  them.
- Chapter 12 setup panels now name `reset_perception_tutorial_state()`,
  `create_perception_actor()`, and `completed_sensory_updates()` before visible
  perception examples call them.
- The public snippet suite's enrolled local-name guard now covers Chapters 01,
  02, and 07-12.
- Verification passed: `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
  collected 166 items and passed.
- Astro build passed again in `/home/tommaso/Dev/neurodragon_dev_manual`: 29
  pages built.
- Expanded public hygiene scan returned no matches, and all 29 local routes
  returned 200 from `http://127.0.0.1:4327`.

Later 2026-06-30 local setup-name content checkpoint:

- Extended the local setup-name audit into the content and encounter tranche:
  Chapters 13, 14, 15, 16, and 17.
- Chapter 13 setup panels now name `reset_spell_tutorial_state()`,
  `create_spell_actor()`, and `find_action()` before visible spellcasting
  examples call them.
- Chapter 14 setup panels now name `reset_spell_family_state()`,
  `create_spell_family_actor()`, `assert_completed_spell()`,
  `penalize_saving_throw()`, and `set_current_normal_hp()` before visible
  spell-family examples call them.
- Chapter 15 setup panels now name `reset_class_feature_state()` and
  `create_feature_target()` before visible class-feature examples call them.
- Chapter 16 setup panels now name `reset_monster_preset_state()`,
  `action_template_names()`, `equipped_item_name()`, `has_darkvision()`,
  `get_inventory_item()`, and `inventory_item_names()` before visible monster
  and preset examples call them.
- Chapter 17 setup panels now name `reset_encounter_tutorial_state()`,
  `RecordingController`, `create_encounter_pair()`, and
  `start_ordered_encounter()` before visible encounter examples call them.
- The public snippet suite's enrolled local-name guard now covers Chapters 01,
  02, and 07-17.
- Verification passed: `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
  collected 166 items and passed.
- Astro build passed again in `/home/tommaso/Dev/neurodragon_dev_manual`: 29
  pages built.
- Expanded public hygiene scan returned no matches, and all 29 local routes
  returned 200 from `http://127.0.0.1:4327`.

Later 2026-06-30 full local setup-name checkpoint:

- Extended the local setup-name audit through the remaining public chapters:
  Chapters 18-27.
- Chapter 18 setup panels now name `ApiClient`, `reset_client_api_state()`,
  `create_api_pair()`, `start_api_game()`, `create_joined_client_game()`, and
  `execute_manual_attack()` before visible client/API examples call them.
- Chapter 19 setup panels now name `create_authoring_client()`,
  `create_tutorial_editor_map()`, `patch_tutorial_room()`, `tile_at()`,
  `place_tutorial_objects()`, and `layer_cell()` before visible map-authoring
  examples call them.
- Chapters 20 and 21 setup panels now name `reset_content_extension_state()`
  and `reset_spell_feature_state()` before visible extension examples call
  them.
- Chapters 22-27 were audited and already explained their visible local setup
  names clearly enough for enrollment.
- The public snippet suite's local setup-name guard now covers every published
  technical chapter with executable examples: Chapters 01, 02, and 07-27.
- Verification passed: `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
  collected 166 items and passed.
- Astro build passed again in `/home/tommaso/Dev/neurodragon_dev_manual`: 29
  pages built.
- Expanded public hygiene scan returned no matches, and all 29 local routes
  returned 200 from `http://127.0.0.1:4327`.

Later 2026-06-30 complete local setup-name guard checkpoint:

- Audited Chapters 03-06 with the same AST-based local definition and visible
  name-use scan used by the public snippet suite.
- Chapters 03-06 define no local functions or classes inside their code setup
  panels that are later called by visible snippets, so no public prose patch was
  needed.
- Added Chapters 03-06 to the local setup-name guard. The guard now covers
  every published technical chapter with executable examples: Chapters 01-27.
- Verification passed: `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
  collected 166 items and passed.
- Astro build passed again in `/home/tommaso/Dev/neurodragon_dev_manual`: 29
  pages built.
- Expanded public hygiene scan returned no matches, and all 29 local routes
  returned 200 from `http://127.0.0.1:4327`.

Later 2026-06-30 full runtime import source-table checkpoint:

- Audited every public `python book-example` fence for imported `dnd`, `server`,
  and `ai` runtime names, including imports that appear only inside collapsed
  code setup panels.
- Expanded the source tables in Chapters 09-21 so scene construction, reset,
  actor-configuration, map, controller, server, and extension surfaces all have
  visible module addresses before their examples use them.
- Strengthened `tests/book_examples/test_public_mdx_snippets.py` so every
  runtime import used by public examples must appear in the chapter's **Code
  Surfaces In This Chapter** section, not only imports used by visible snippets
  outside setup panels.
- Verification passed: `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
  collected 166 items and passed.
- Astro build passed again in `/home/tommaso/Dev/neurodragon_dev_manual`: 29
  pages built.
- Expanded public hygiene scan returned no matches, and all 29 local routes
  returned 200 from `http://127.0.0.1:4327`.

Later 2026-06-30 precise runtime source-map checkpoint:

- Removed vague wildcard source-table paths such as `dnd.core.*` and
  `dnd.blocks.*` from the public manual.
- Corrected older source-table rows whose symbols were attached to the wrong
  module, including item `Range`/`RangeType`, class-feature roll statuses,
  controller `manhattan_distance`, and agent behavior-tree/composite symbols.
- Strengthened `tests/book_examples/test_public_mdx_snippets.py` so each
  imported `dnd`, `server`, and `ai` symbol must appear on a source-table row
  that also contains the actual module imported by the executable MDX snippet.
- Added a guard that blocks wildcard runtime paths and vague labels such as
  "Runtime reset modules" in source tables.
- Verification passed: `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
  collected 167 items and passed.
- Astro build passed again in `/home/tommaso/Dev/neurodragon_dev_manual`: 29
  pages built.
- Expanded public hygiene scan returned no matches, and all 29 local routes
  returned 200 from `http://127.0.0.1:4327`.

Later 2026-06-30 local tutorial symbol source-map checkpoint:

- Audited visible snippets for locally defined function/class names that were
  introduced in code setup panels but absent from chapter-level source tables.
- Added source-table rows for local tutorial symbols in Chapters 01, 02, and
  07-21, including reset functions, scene builders, row selectors, small local
  classes, and local event readers.
- Strengthened `tests/book_examples/test_public_mdx_snippets.py` so every
  visible local function/class defined in a code setup panel must also be named
  in the chapter's **Code Surfaces In This Chapter** section.
- Verification passed: `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
  collected 168 items and passed.
- Astro build passed again in `/home/tommaso/Dev/neurodragon_dev_manual`: 29
  pages built.
- Expanded public hygiene scan returned no matches, and all 29 local routes
  returned 200 from `http://127.0.0.1:4327`.

Later 2026-06-30 continuous chapter reading checkpoint:

- Added a bottom chapter runway to the Astro manual layout so each chapter links
  directly to the previous and next chapter in reading order.
- The runway uses the ordered content collection, preserves the existing
  chapter list, and gives first/last chapters a return path to the manual table.
- Added a public snippet-suite guard that checks the manual layout still exposes
  the chapter reading sequence, previous chapter link, and next chapter link.
- Verification passed: `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
  collected 169 items and passed.
- Astro build passed again in `/home/tommaso/Dev/neurodragon_dev_manual`: 29
  pages built.
- Expanded public hygiene scan returned no matches.
- Local route verification returned 200 for all 29 routes and confirmed the
  rendered `/manual/05-event-lifecycle/` page links to Chapters 04 and 06.

Later 2026-06-30 landing reading-path checkpoint:

- Added a forward-facing **Reading Path** section to the home page that presents
  the manual as a sequence from table rules, to runtime state, to play
  consequences, to game-facing systems, to agent automation.
- The section explicitly connects D&D ideas, engine objects, player/client
  systems, designer systems, and agent-facing tactical systems before the table
  of contents.
- Expanded public hygiene coverage to include the home page and manual
  navigation component.
- Added a public snippet-suite guard that checks the landing page keeps the
  reading path and its four major steps.
- Verification passed: `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
  collected 170 items and passed.
- Astro build passed again in `/home/tommaso/Dev/neurodragon_dev_manual`: 29
  pages built.
- Expanded public hygiene scan returned no matches.
- Local route verification returned 200 for all 29 routes and confirmed the
  rendered home page includes the reading path.

Later 2026-06-30 runnable example presentation checkpoint:

- Updated the shared `ExampleBlock` component so every example is visibly framed
  as a **Runnable Tutorial Example** instead of an anonymous code fragment.
- Added a compact example reading order strip: **Setup**, **Execute**,
  **Observe**. This matches the code setup panel plus the visible action/result
  snippets without using internal test language.
- Added a public snippet-suite guard that checks the example component keeps
  the runnable tutorial framing and avoids test wording.
- Verification passed: `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
  collected 171 items and passed.
- Astro build passed again in `/home/tommaso/Dev/neurodragon_dev_manual`: 29
  pages built.
- Expanded public hygiene scan returned no matches.
- Local route verification returned 200 for all 29 routes and confirmed the
  rendered `/manual/04-dice-rolls/` page includes the example tutorial flow.

Later 2026-06-30 foundation tone-polish checkpoint:

- Audited public prose outside code fences for remaining negative or weak
  framing in the foundation chapters.
- Replaced "tiny" and repeated "small" tutorial wording in Chapters 01, 05, and
  07 with forward-facing "focused" language, so foundation examples read as
  deliberate teaching scenes rather than throwaway scaffolding.
- Added public hygiene guards that block "tiny" wording and specific weak setup
  phrases such as "small local classes", "small runtime scene", and
  "small condition-bearing".
- Verification passed: `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
  collected 171 items and passed.
- Astro build passed again in `/home/tommaso/Dev/neurodragon_dev_manual`: 29
  pages built.
- Expanded public hygiene scan returned no matches, and all 29 local routes
  returned 200 from `http://127.0.0.1:4327`.

## Current State

The previous public Astro webbook topic pages have been deleted. The manual has
restarted from the planning structure in this file instead of the previous
generated draft.

One public opening chapter exists:

- `src/content/manual/00-neurodragon-dev-manual.mdx`

Chapters 01-27 are now published into the local Astro webbook for human browser
review:

- Chapter 01 plan: `engine_book/chapter_01_runtime_identity_plan.md`
- Chapter 01 public page:
  `src/content/manual/01-runtime-identity-and-registries.mdx`
- Chapter 01 draft source:
  `engine_book/drafts/01-runtime-identity-and-registries.mdx`
- Chapter 01 test: `tests/manual/test_01_runtime_identity_and_registries.py`
- Chapter 01 diagram assets: `runtime-identity-and-registries.svg` and
  `runtime-identity-and-registries.excalidraw`
- Chapter 01 strict example status: uses named public snippets for runtime
  object lookup, runtime object publishing, registry families, entity position
  lookup, and value subclass lookup, now framed inside EB-01-001 through
  EB-01-005.
- Chapter 01 prose quality status: reframed as forward-facing runtime
  addressing, replaced the old defensive registry framing with positive lookup
  contracts, and moved imports/setup into visible ExampleBlock sections.
  Latest pass added a chapter-level symbol/import map, explained the
  `reset_identity_state()` tutorial setup before use, and reframed
  registration timing as publishing live runtime state rather than opt-out
  behavior. Current setup-prose pass adds reader-facing explanations inside
  each collapsed import panel and uses `runtime-object-publishing` as the exact
  public example name for publishing live runtime objects.
- Chapter 02 plan: `engine_book/chapter_02_entity_anatomy_plan.md`
- Chapter 02 public page: `src/content/manual/02-entity-anatomy.mdx`
- Chapter 02 draft source: `engine_book/drafts/02-entity-anatomy.mdx`
- Chapter 02 test: `tests/manual/test_02_entity_anatomy.py`
- Chapter 02 diagram assets: `entity-anatomy.svg` and
  `entity-anatomy.excalidraw`
- Chapter 02 strict example status: converted from generic whole-chapter flow
  to named `entity-anatomy-tutorial` public snippets inside EB-02-001 through
  EB-02-004.
- Chapter 02 prose quality status: reframed `Entity` as the live D&D
  videogame actor, described child blocks as active game state, and replaced
  defensive inspection wording with a forward-facing actor anatomy model.
  Latest pass added a chapter-level symbol/import map and explicitly framed
  `create_tutorial_hero()` as the visible tutorial constructor for Aria rather
  than an external scene source. Current pass moved the constructor and imports
  into a **Code setup: imports and scene** panel and made the visible behavior
  block create Aria and inspect entity metadata.
- Chapter 03 plan: `engine_book/chapter_03_values_and_modifiers_plan.md`
- Chapter 03 public page: `src/content/manual/03-values-and-modifiers.mdx`
- Chapter 03 draft source: `engine_book/drafts/03-values-and-modifiers.mdx`
- Chapter 03 test: `tests/manual/test_03_values_and_modifiers.py`
- Chapter 03 diagram assets: `values-and-modifiers.svg` and
  `values-and-modifiers.excalidraw`
- Chapter 03 strict example status: public snippets now execute as four
  localized examples: `values-score-and-breakdown`,
  `values-static-rule-state`, `values-contextual-modifiers`, and
  `values-target-propagation`, each scoped to EB-03-001 through EB-03-004
  with its own import/setup panel.
- Chapter 03 prose quality status: reframed `ModifiableValue` as a D&D rule
  ledger, clarified self/target/context channels as gameplay surfaces, and
  replaced defensive number-plumbing wording with forward-facing rule
  explanation. Latest pass added a visible D&D-rule-to-value placement map and
  a chapter-level symbol/import map before the channel machinery. Current
  setup-prose pass explains the remaining static, contextual, and target-
  propagation import panels before their executable code appears.
- Chapter 04 plan: `engine_book/chapter_04_dice_rolls_plan.md`
- Chapter 04 public page: `src/content/manual/04-dice-rolls.mdx`
- Chapter 04 test: `tests/manual/test_04_dice_rolls.py`
- Chapter 04 diagram assets: `dice-roll-pipeline.svg` and
  `dice-roll-pipeline.excalidraw`
- Chapter 04 strict example status: public snippets now execute as five
  localized examples: `dice-cached-d20`, `dice-advantage-disadvantage`,
  `dice-roll-state-snapshot`, `dice-damage-and-critical`, and
  `dice-expression-validation`, each scoped to EB-04-001 through EB-04-005
  with its own import/setup panel.
- Chapter 04 prose quality status: reframed dice as visible uncertainty and
  `DiceRoll` as the stable roll record used by logs, animation, replay, events,
  and later combat resolution. Latest pass added a visible D&D-dice-to-engine
  record map and a chapter-level symbol/import map before the first dice
  example. Current setup-prose pass explains the remaining advantage,
  roll-state, damage, and validation import panels before their executable
  code appears.
- Chapter 05 plan: `engine_book/chapter_05_event_lifecycle_plan.md`
- Chapter 05 public page: `src/content/manual/05-event-lifecycle.mdx`
- Chapter 05 test: `tests/manual/test_05_event_lifecycle.py`
- Chapter 05 diagram assets: `event-lifecycle-records.svg` and
  `event-lifecycle-records.excalidraw`
- Chapter 05 strict example status: public snippets now execute as five
  localized examples: `event-lineage-phases`, `event-cancellation`,
  `event-parent-child-lineage`, `event-completion-combat-log`, and
  `event-passive-observation`, each scoped to EB-05-001 through EB-05-005
  with its own import/setup panel.
- Chapter 05 prose quality status: reframed events as game occurrence records,
  explained phase versions and lineage as a forward lifecycle, and clarified
  completion as the point where child trees and combat-log output become stable.
  Latest pass added a visible game-moment-to-event-lineage map and a
  chapter-level event/combat-log import map before the phase ladder. Current
  setup-prose pass explains the cancellation, parent/child lineage, completion
  combat-log, and passive-observation import panels before their executable
  code appears.
- Chapter 06 plan: `engine_book/chapter_06_reactions_to_events_plan.md`
- Chapter 06 public page: `src/content/manual/06-reactions-to-events.mdx`
- Chapter 06 test: `tests/manual/test_06_reactions_to_events.py`
- Chapter 06 diagram assets: `event-reaction-surfaces.svg` and
  `event-reaction-surfaces.excalidraw`
- Chapter 06 strict example status: public snippets now execute as six
  localized examples: `event-triggered-handler`,
  `event-quiet-timing-windows`, `event-cancel-and-stop`,
  `event-d20-result-processor`, `event-spatial-entry-handler`, and
  `event-movement-surfaces`, each scoped to EB-06-001 through EB-06-006 with
  its own import/setup panel.
- Chapter 06 prose quality status: reframed event handlers, result processors,
  spatial handlers, and movement reactions as timed game-rule responses, with
  completion as the final observation boundary and voluntary movement separated
  from forced displacement. Latest pass added a visible reaction-surface
  decision table and a chapter-level reaction/event import map before the first
  handler example. Current setup-prose pass explains the quiet timing,
  cancellation, d20 replacement, spatial entry, and movement-surface import
  panels before their executable code appears.
- Chapter 07 plan: `engine_book/chapter_07_conditions_and_cleanup_plan.md`
- Chapter 07 public page: `src/content/manual/07-conditions-and-cleanup.mdx`
- Chapter 07 test: `tests/manual/test_07_conditions_and_cleanup.py`
- Chapter 07 diagram assets: `condition-cleanup-tree.svg` and
  `condition-cleanup-tree.excalidraw`
- Chapter 07 strict example status: public snippets now execute as six
  localized examples: `condition-bearing-actor`,
  `condition-owned-modifier`, `condition-owned-handler`,
  `condition-subcondition-tree`, `condition-linked-cleanup`, and
  `condition-duration-expiry`, each scoped to EB-07-001 through EB-07-006 with
  its own import/setup panel.
- Chapter 07 prose quality status: reframed conditions as owned ongoing D&D
  rule packages, clarified application/removal ownership, and explained
  modifier, handler, same-block child, linked-child, and duration cleanup as
  one removal contract. Latest pass added a visible D&D-condition-to-owned-
  artifact map and a chapter-level condition/cleanup import map before the
  first custom condition class. Current setup-prose pass explains the modifier,
  handler, same-block subcondition, linked-condition, and duration-expiry import
  panels before their executable code appears.
- Chapter 08 plan: `engine_book/chapter_08_world_model_and_movement_plan.md`
- Chapter 08 public page: `src/content/manual/08-world-model-and-movement.mdx`
- Chapter 08 test: `tests/manual/test_08_world_model_and_movement.py`
- Chapter 08 diagram assets: `world-model-movement.svg` and
  `world-model-movement.excalidraw`
- Chapter 08 strict example status: public snippets now execute as five
  localized examples: `world-terrain-costs`, `world-directional-border`,
  `world-entity-spatial-events`, `world-forced-movement`, and
  `world-batch-map-creation`, each scoped to EB-08-001 through EB-08-005 with
  its own import/setup panel.
- Chapter 08 prose quality status: reframed the map as the tactical board,
  clarified tiles, path costs, position indexes, and spatial events, and
  explicitly separated voluntary `STEP_MOVEMENT` timing from forced
  `FORCED_MOVEMENT` displacement while preserving spatial enter/leave effects.
  Latest pass added a visible tactical-movement-to-map-state map and a
  chapter-level world/movement import map before the terrain examples. Current
  setup-prose pass explains the directional-border, entity-spatial-event,
  forced-movement, and batch-map-creation import panels before their
  executable code appears.
- Chapter 09 public page: `src/content/manual/09-action-discovery-and-costs.mdx`
- Chapter 09 test: `tests/manual/test_09_action_discovery_and_costs.py`
- Chapter 09 diagram assets: `action-discovery-and-costs.svg` and
  `action-discovery-and-costs.excalidraw`
- Chapter 09 strict example status: public snippets now execute as seven
  localized examples: `action-template-instantiation`,
  `action-discovery-menu`, `action-execute-by-index`,
  `action-object-inventory-routing`, `action-cost-override`,
  `action-target-pools`, and `action-safe-movement-path`, each scoped to
  EB-09-001 through EB-09-007 with its own import/setup panel.
- Chapter 09 prose quality status: reframed actions as player turn choices,
  discovery as an indexed menu contract, execution as target binding plus
  successful cost payment, and item/object/hazard examples as engine-provided
  choice rows. Latest pass added a visible player-choice-to-engine-action map
  and a chapter-level action API/import map before the template examples.
  Current setup-prose pass explains each collapsed import panel's scene
  construction and local row-selection functions so the exact public snippets
  read as tutorial examples rather than unexplained scaffolding, and Chapter 09
  is now enrolled in the staged exact-snippet panel-prose guard.
- Chapter 10 public page: `src/content/manual/10-combat-resolution.mdx`
- Chapter 10 test: `tests/manual/test_10_combat_resolution.py`
- Chapter 10 diagram assets: `core-combat-flow.svg` and
  `core-combat-flow.excalidraw`
- Chapter 10 strict example status: public snippets now execute as five
  localized examples: `combat-invalid-attack-costs`,
  `combat-hit-damage-healing`, `combat-critical-damage-dice`,
  `combat-voluntary-movement-reaction`, and
  `combat-videogame-shove-forced-movement`, each scoped to EB-10-001 through
  EB-10-005 with its own import/setup panel.
- Chapter 10 prose quality status: reframed combat as selected action
  resolution, clarified validation-before-cost-spending, damage/healing event
  surfaces, opportunity reactions on voluntary movement, and the single
  videogame Shove implementation as bonus-action forced movement. Latest pass
  added a visible selected-combat-choice-to-engine-result map and a
  chapter-level combat action/import map before the first combat example.
  Current setup-prose pass explains the invalid-attack, hit/damage/healing,
  critical-hit, voluntary-movement reaction, and videogame Shove panels before
  their executable code appears, including the local roll-state modifier
  functions and the simple actor constructor used by the public snippets.
- Chapter 11 public page:
  `src/content/manual/11-equipment-inventory-and-items.mdx`
- Chapter 11 test: `tests/manual/test_11_equipment_inventory_and_items.py`
- Chapter 11 diagram assets: `equipment-inventory-items.svg` and
  `equipment-inventory-items.excalidraw`
- Chapter 11 strict example status: public snippets now execute as five
  localized examples: `items-floor-inventory-drop`,
  `items-stack-atomic-capacity`, `items-equipment-hooks`,
  `items-loadout-displacement`, and `items-usable-and-environment-actions`,
  each scoped to EB-11-001 through EB-11-005 with its own import/setup panel.
- Chapter 11 prose quality status: reframed items as one-location physical
  objects, clarified inventory atomicity and usable item actions, and documented
  order-based two-handed melee displacement while preserving separate
  melee/ranged videogame loadouts. Latest pass added a visible physical-object
  lifecycle map, a chapter-level item/equipment import map, and an explicit
  loadout-result table before the displacement example. Current setup-prose
  pass explains the floor/inventory/drop, stack capacity, equipment hook,
  loadout displacement, and item-action panels before their executable code
  appears, including reset scope, actor construction, inventory boundaries, and
  the property-based hand-crossbow weapon.
- Chapter 12 public page:
  `src/content/manual/12-perception-light-stealth-and-invisibility.mdx`
- Chapter 12 test:
  `tests/manual/test_12_perception_light_stealth_and_invisibility.py`
- Chapter 12 diagram assets: `senses-light-visibility-pipeline.svg` and
  `senses-light-visibility-pipeline.excalidraw`
- Chapter 12 strict example status: public snippets now execute as six
  localized examples: `senses-geometry-light-filter`,
  `senses-special-light`, `senses-reactive-light-update`,
  `senses-stealth-invisibility-filter`, `senses-subjective-paths`, and
  `senses-hidden-invisible-layers`, each scoped to EB-12-001 through EB-12-006
  with its own import/setup panel.
- Chapter 12 prose quality status: reframed senses as observer-local truth,
  clarified geometry-before-light subscriptions, effective light and special
  senses, sensory update events via public lookup, stealth/invisibility filters,
  subjective path previews, and independent Hidden/Invisible layers. Latest
  pass added a player-facing awareness map, chapter-level perception/import
  map, and runnable tutorial-source wording for the import panels. Current
  setup-prose pass explains the geometry/light, special-sense, reactive-update,
  stealth/invisibility, subjective-path, and stacked-concealment panels before
  their executable code appears, including reset scope, actor construction,
  event lookup, direct perceivability state, and real condition application.
- Chapter 13 public page: `src/content/manual/13-spellcasting-core.mdx`
- Chapter 13 test: `tests/manual/test_13_spellcasting_core.py`
- Chapter 13 diagram assets: `spellcasting-core.svg` and
  `spellcasting-core.excalidraw`
- Chapter 13 strict example status: public snippets now execute as six
  localized examples: `spell-slots-resource-reset`,
  `spell-numbers-modifier-composition`, `spell-discovery-slot-variants`,
  `spell-fire-bolt-resolution`, `spell-magic-missile-multitarget`, and
  `spell-concentration-linked-cleanup`, each scoped to EB-13-001 through
  EB-13-006 with its own import/setup panel.
- Chapter 13 prose quality status: reframed spellcasting as the shared
  action/resource/event/condition pipeline, clarified slots as action-economy
  resources, spell numbers as entity spell-number methods, slot variants in
  discovery, spell events, multi-target spell aggregation, and concentration
  linked-effect cleanup. Latest pass added a cast-flow chapter map, chapter-
  level spellcasting/import map, and runnable tutorial-source wording for the
  import panels. Current setup-prose pass explains the slot-resource,
  spell-number, discovery, Fire Bolt, Magic Missile, and concentration cleanup
  panels before their executable code appears, including actor construction,
  action-row lookup, fixed dice, repeated target selection, and linked
  condition cleanup.
- Chapter 14 plan: `engine_book/chapter_14_spell_families_plan.md`
- Chapter 14 public page:
  `src/content/manual/14-spell-families-and-implemented-spells.mdx`
- Chapter 14 test: `tests/manual/test_14_spell_families.py`
- Chapter 14 diagram assets: `spell-families.svg` and
  `spell-families.excalidraw`
- Chapter 14 strict example status: public snippets now execute as six
  localized examples: `spell-catalog-runtime-metadata`,
  `spell-family-offense`, `spell-family-recovery-protection`,
  `spell-family-mobility-temp-hp`, `spell-family-spatial-zone`, and
  `spell-family-condition-effects`, each scoped to EB-14-001 through EB-14-006
  with its own import/setup panel.
- Chapter 14 prose quality status: reframed implemented spells as runtime
  behavior families, clarified catalog identity, attack/save/auto-hit damage,
  healing and protection, movement and temporary HP, spatial zones, and
  condition-producing spell effects. Latest pass added a designer-facing spell
  family map, chapter-level spell-family/import map, and runnable
  tutorial-source wording for the import panels. Current setup-prose pass
  explains the catalog, offensive-family, recovery/protection,
  mobility/temp-HP, spatial-zone, and condition-effect panels before their
  executable code appears, including catalog metadata, fixed dice, save
  penalties, HP staging, zone movement, and Sleep's HP-pool targeting.
- Chapter 15 plan: `engine_book/chapter_15_class_features_plan.md`
- Chapter 15 public page:
  `src/content/manual/15-class-features-factories-and-feats.mdx`
- Chapter 15 test: `tests/manual/test_15_class_features.py`
- Chapter 15 diagram assets: `class-features-factories.svg` and
  `class-features-factories.excalidraw`
- Chapter 15 strict example status: public snippets now execute as five
  localized examples: `class-factory-playable-actors`,
  `class-fighter-resource-actions`, `class-barbarian-frenzy-cleanup`,
  `class-sorcerer-metamagic-overrides`, and `class-lucky-d20-policy`, each
  scoped to EB-15-001 through EB-15-005 with its own import/setup panel.
- Chapter 15 prose quality status: reframed classes as authored character
  content, clarified factories as playable actor assembly, and explained
  feature-owned resources, actions, mode conditions, spell-template overrides,
  and feat-style d20 handlers. Latest pass added a character-building map,
  chapter-level class-feature/import map, and runnable tutorial-source wording
  for the import panels. Current setup-prose pass explains the factory,
  fighter-resource, barbarian-frenzy, sorcerer-metamagic, and Lucky panels
  before their executable code appears, including factory-attached conditions,
  short-rest resources, rage cleanup, template overrides, and d20 event policy.
- Chapter 16 plan: `engine_book/chapter_16_monsters_preset_actors_plan.md`
- Chapter 16 public page:
  `src/content/manual/16-monsters-and-preset-actors.mdx`
- Chapter 16 test: `tests/manual/test_16_monsters_preset_actors.py`
- Chapter 16 diagram assets: `monsters-preset-actors.svg` and
  `monsters-preset-actors.excalidraw`
- Chapter 16 strict example status: public snippets now execute as five
  localized examples: `monster-base-stat-blocks`,
  `monster-goblin-nimble-escape`, `monster-generic-caster-preset`,
  `monster-skeleton-role-presets`, and `monster-mark-target-concentration`,
  each scoped to EB-16-001 through EB-16-005 with its own import/setup panel.
- Chapter 16 prose quality status: reframed monsters and presets as authored
  encounter actors, clarified monster factories as stat-block-to-entity
  composition, and explained base monsters, generic caster presets, skeleton
  roles, and concentration-linked monster abilities. Latest pass added an
  encounter-actor authoring map, chapter-level monster/preset import map, and
  runnable tutorial-source wording for the import panels. Current setup-prose
  pass explains the base monster, Nimble Escape, generic caster, skeleton role,
  and Mark Target panels before their executable code appears, including
  stat-block readers, bonus-action variants, caster inventory support, role
  loadouts, and concentration-linked cleanup.
- Chapter 17 plan: `engine_book/chapter_17_encounters_turns_controllers_plan.md`
- Chapter 17 public page:
  `src/content/manual/17-encounters-turns-and-controllers.mdx`
- Chapter 17 test: `tests/manual/test_17_encounters_turns_controllers.py`
- Chapter 17 diagram assets: `encounters-turns-controllers.svg` and
  `encounters-turns-controllers.excalidraw`
- Chapter 17 strict example status: public snippets now execute as five
  localized examples: `encounter-start-end-state`,
  `encounter-turn-round-advance`, `encounter-advance-until-human`,
  `encounter-combat-log-capture`, and `encounter-faction-survival-ending`,
  each scoped to EB-17-001 through EB-17-005 with its own import/setup panel.
- Chapter 17 prose quality status: reframed encounters as the videogame table
  manager, clarified combatants, initiative, turn context, controller input
  boundaries, combat-log capture, and faction-survival encounter ending. Latest
  pass added a playable-time map, chapter-level encounter/controller import
  map, and runnable tutorial-source wording for the import panels. Current
  setup-prose pass explains the start/end, turn/round, external-input,
  combat-log, and faction-ending panels before their executable code appears,
  including recording controllers, deterministic initiative, pass-to-human
  advancement, temporary auto-hit setup, log listeners, and death checks.
- Chapter 18 plan: `engine_book/chapter_18_sessions_api_client_contract_plan.md`
- Chapter 18 public page:
  `src/content/manual/18-sessions-apis-and-client-payloads.mdx`
- Chapter 18 test: `tests/manual/test_18_sessions_api_client_contract.py`
- Chapter 18 diagram assets: `sessions-api-client-contract.svg` and
  `sessions-api-client-contract.excalidraw`
- Chapter 18 strict example status: public snippets now execute as five
  localized examples: `client-session-join`, `client-state-turn-actions`,
  `client-execute-indexed-action`, `client-events-combat-log-cursors`, and
  `client-spell-catalog-metadata`, each scoped to EB-18-001 through EB-18-005
  with its own import/setup panel.
- Chapter 18 prose quality status: reframed the server layer as the client
  contract around the encounter loop, clarified sessions, game ownership,
  state/current-turn/action payloads, indexed action execution, event/log
  cursors, SSE frame IDs, and spell catalog metadata. Latest pass added a
  client-contract chapter map, a code-surface table, and public `sim.reset()`
  setup in the runnable import panels. Current setup-prose pass explains the
  session/join, state/actions, indexed action, cursor, and spell-catalog panels
  before their executable code appears, including the in-process ASGI client,
  simulation reset, joined-game setup, target-index lookup, deterministic
  attack execution, cursor polling, stream frames, and design-time catalog
  payloads.
- Chapter 19 plan: `engine_book/chapter_19_map_editor_scenario_authoring_plan.md`
- Chapter 19 public page:
  `src/content/manual/19-map-editor-and-scenario-authoring.mdx`
- Chapter 19 test: `tests/manual/test_19_map_editor_scenario_authoring.py`
- Chapter 19 diagram assets: `map-editor-scenario-authoring.svg` and
  `map-editor-scenario-authoring.excalidraw`
- Chapter 19 strict example status: public snippets now execute as six
  localized examples: `map-editor-catalog-scratch-map`,
  `map-editor-tile-patches`, `map-editor-objects-layers`,
  `map-editor-object-deletion`, `map-editor-save-load`, and
  `map-editor-preset-handoff`, each scoped to EB-19-001 through EB-19-006 with
  its own import/setup panel.
- Chapter 19 client status: the public snippet and focused manual check use a
  local HTTPX/ASGI `ApiClient` wrapper instead of FastAPI's deprecated
  `TestClient` import.
- Chapter 19 prose quality status: reframed the map editor as entity-free
  scenario authoring, clarified catalog entries, map snapshots, terrain and
  directional-border patches, placed objects, objective walkability/visibility/
  light layers, saved map documents, preset maps, and clean transition from a
  running game into authoring mode. Latest pass added an authoring workflow
  chapter map, chapter-level code-surface table, and standalone exact snippets
  for each editor operation. Current setup-prose pass explains the catalog and
  scratch-map, tile-patch, object-layer, object-deletion, save/load, and preset
  handoff panels before their executable code appears, including the
  in-process authoring client, fresh-state reset, tile and layer readers,
  temporary save directory, and transition between play mode and authoring mode.
- Chapter 20 plan: `engine_book/chapter_20_content_extension_basics_plan.md`
- Chapter 20 public page:
  `src/content/manual/20-content-extension-basics.mdx`
- Chapter 20 test: `tests/manual/test_20_content_extension_basics.py`
- Chapter 20 diagram assets: `content-extension-basics.svg` and
  `content-extension-basics.excalidraw`
- Chapter 20 strict example status: public snippets now execute as six
  localized examples: `content-extension-module-surfaces`,
  `content-extension-condition-lifecycle`,
  `content-extension-registered-action`, `content-extension-inventory-item`,
  `content-extension-floor-object`, and `content-extension-factories`, each
  scoped to EB-20-001 through EB-20-006 with its own import/setup panel.
- Chapter 20 prose quality status: introduced extension as positive content
  composition, using a Field Focus content pack to clarify custom conditions,
  action templates, item-provided actions, actor factories, scene factories,
  discovery, execution, action costs, and condition cleanup. Latest pass moved
  the pack into the real `dnd.extensions.field_focus` module, added an
  extension workflow chapter map and code-surface table, and made each public
  example import the concrete extension symbols it uses. Current setup-prose
  pass explains the module boundary, condition lifecycle, registered action,
  inventory item, floor object, and factory panels before their executable code
  appears, including the registry reset, map setup, discovery rows, item UUID
  routing, senses refresh, and reusable scene factory package.
- Chapter 21 plan:
  `engine_book/chapter_21_spell_and_feature_extensions_plan.md`
- Chapter 21 public page:
  `src/content/manual/21-spell-and-feature-extensions.mdx`
- Chapter 21 test:
  `tests/manual/test_21_spell_and_feature_extensions.py`
- Chapter 21 diagram assets: `spell-feature-extension-flow.svg` and
  `spell-feature-extension-flow.excalidraw`
- Chapter 21 strict example status: public snippets now execute as five
  localized examples: `spell-feature-module-surfaces`,
  `spell-feature-registers-spell`, `spell-feature-discovery-targets`,
  `spell-feature-execute-cleanup`, and `spell-feature-factory-scene`, each
  scoped to EB-21-001 through EB-21-005 with its own import/setup panel.
- Chapter 21 prose quality status: introduced feature-granted spell extension
  through Aegis Training and Aegis Spark, clarifying custom `SpellAction`
  templates, `SpellEvent` execution, self-or-ally target discovery, feature
  cleanup, and condition-owned modifier cleanup. Latest pass moved the spell
  pack into the real `dnd.extensions.aegis_spark` module, added a
  feature-granted-spell workflow map and code-surface table, and made each
  public example import the concrete extension symbols it uses. Current
  setup-prose pass explains the Aegis module boundary, feature-owned spell
  registration, self-or-ally target discovery, `SpellEvent` resolution,
  condition cleanup, and reusable scene factory panels before their executable
  code appears.
- Chapter 22 plan:
  `engine_book/chapter_22_playable_scenario_packages_plan.md`
- Chapter 22 public page:
  `src/content/manual/22-playable-scenario-packages.mdx`
- Chapter 22 test:
  `tests/manual/test_22_playable_scenario_packages.py`
- Chapter 22 diagram assets: `playable-scenario-package.svg` and
  `playable-scenario-package.excalidraw`
- Chapter 22 strict example status: public snippets now execute as five
  localized examples: `scenario-package-surfaces`,
  `scenario-package-factory-state`, `scenario-package-advance-human`,
  `scenario-package-execute-action`, and `scenario-package-faction-ending`,
  each scoped to EB-22-001 through EB-22-005 with its own import/setup panel.
- Chapter 22 prose quality status: introduced playable scenario packaging as
  the product boundary around map state, actors, controllers, encounter state,
  turn handoff, indexed action execution, combat-log capture, and faction
  survival ending. Latest pass moved the Gatehouse scenario into the real
  `dnd.scenarios.gatehouse` module, added a playable-scenario workflow map and
  code-surface table, and made each public example import the concrete
  scenario symbols it uses. Current setup-prose pass explains the Gatehouse
  package surface, running encounter factory, automated-turn handoff,
  selected-action execution, temporary auto-hit modifier, combat-log capture,
  and faction-survival ending panels before their executable code appears.
- Chapter 23 plan:
  `engine_book/chapter_23_standard_arena_game_modes_plan.md`
- Chapter 23 public page:
  `src/content/manual/23-standard-arena-game-modes.mdx`
- Chapter 23 test:
  `tests/manual/test_23_standard_arena_game_modes.py`
- Chapter 23 diagram assets: `standard-arena-game-modes.svg` and
  `standard-arena-game-modes.excalidraw`
- Chapter 23 strict example status: public snippets now execute as six
  localized examples: `arena-mode-surfaces`, `arena-build-standard`,
  `arena-select-hero-kit`, `arena-control-mode`, `arena-start-join`, and
  `arena-live-payloads`, each scoped to EB-23-001 through EB-23-006 with its
  own import/setup panel.
- Chapter 23 client status: the public snippets and focused manual check use
  `ArenaApiClient` from the real `server.arena_mode` module to call the same
  FastAPI routes a browser uses.
- Chapter 23 prose quality status: introduced the standard arena as the
  concrete game assembly over the engine, clarifying environment composition,
  class-selected hero kits, monster-side actors, AI/Codex control modes,
  human session joining, and live client state payloads. Latest pass added a
  chapter map, code-surface table, and the real `server.arena_mode` surface for
  reset, route calls, actor lookup, item inspection, and joined human sessions.
  Current setup-prose pass explains the arena mode surface, in-process API
  client, actor/object/item/action readers, standard arena construction, hero
  kit selection, PvP-style controller swap, human start/join flow, and live
  payload panels before their executable code appears.
- Chapter 24 plan:
  `engine_book/chapter_24_built_in_controllers_plan.md`
- Chapter 24 public page:
  `src/content/manual/24-built-in-controllers-and-automated-turns.mdx`
- Chapter 24 test:
  `tests/manual/test_24_built_in_controllers.py`
- Chapter 24 diagram assets: `built-in-controllers-and-automated-turns.svg`
  and `built-in-controllers-and-automated-turns.excalidraw`
- Chapter 24 strict example status: public snippets now execute as seven
  localized examples: `controller-catalogue-surfaces`,
  `controller-external-input`, `controller-pass-turn`,
  `controller-melee-attack`, `controller-melee-move`,
  `controller-no-visible-enemy`, and `controller-agent-runner`, each scoped to
  EB-24-001 through EB-24-007 with its own import/setup panel.
- Chapter 24 prose quality status: introduced the built-in controller
  catalogue as the videogame input contract, clarifying human/Codex input
  pauses, pass-through turns, melee AI action selection, no-visible-enemy pass
  behavior, and delegated agent-runner turns. Latest pass moved the controller
  catalogue arena into the real `dnd.scenarios.controller_catalogue` module,
  added a chapter map and code-surface table, and made each public example
  import the concrete controller scenario symbols it uses. Current setup-prose
  pass explains the controller catalogue scene, outside-input handoff,
  pass-turn lifecycle, melee attack choice, movement toward visible enemies,
  no-visible-enemy decline, and agent-runner delegation panels before their
  executable code appears.
- Chapter 25 plan:
  `engine_book/chapter_25_live_replication_streams_plan.md`
- Chapter 25 public page:
  `src/content/manual/25-live-replication-streams.mdx`
- Chapter 25 test:
  `tests/manual/test_25_live_replication_streams.py`
- Chapter 25 diagram assets: `live-replication-streams.svg` and
  `live-replication-streams.excalidraw`
- Chapter 25 strict example status: public snippets now execute as seven
  localized examples: `stream-surface`, `stream-sync-frame`,
  `stream-cursor-replay`, `stream-live-fanout`,
  `stream-completion-before-log`, `stream-heartbeat-frame`, and
  `stream-bounded-eviction`, each scoped to EB-25-001 through EB-25-007 with
  its own import/setup panel.
- Chapter 25 prose quality status: introduced live replication as the
  cursor-based publication layer over engine events and combat logs,
  clarifying sync frames, cursor replay, live fan-out, completion-before-log
  ordering, heartbeat frames, and bounded subscriber eviction. Latest pass
  moved the live stream scene into the real `server.live_replication` module,
  added a chapter map and code-surface table, and made each public example
  import the concrete stream symbols it uses. Current setup-prose pass explains
  the live stream bridge, cursor-aware payloads, repeatable stream encounter,
  sync frame, cursor replay, live fan-out, completion-before-log ordering,
  heartbeat frame, and bounded-subscriber eviction panels before their
  executable code appears.
- Chapter 26 plan:
  `engine_book/chapter_26_agent_tactical_interface_plan.md`
- Chapter 26 public page:
  `src/content/manual/26-agent-tactical-interface.mdx`
- Chapter 26 test:
  `tests/manual/test_26_agent_tactical_interface.py`
- Chapter 26 diagram assets: `agent-tactical-interface.svg` and
  `agent-tactical-interface.excalidraw`
- Chapter 26 strict example status: public snippets now execute as seven
  localized examples: `agent-interface-surface`, `agent-tactical-snapshot`,
  `agent-action-options`, `agent-tactical-queries`, `agent-expected-value`,
  `agent-execute-choice`, and `agent-base-runner`, each scoped to EB-26-001
  through EB-26-007 with its own import/setup panel.
- Chapter 26 prose quality status: introduced the local agent tactical
  interface as the decision surface over the running game, clarifying
  `TacticalState`, action and target option translation, named tactical
  queries, expected-value scoring, indexed execution, state refresh, and the
  minimal `BaseAgent` turn-runner pattern. Latest pass moved the training
  scene and minimal agent into the real
  `dnd.scenarios.agent_tactical_training` module, added a chapter map and
  code-surface table, and made each public example import the concrete
  tactical-interface symbols it uses. Current setup-prose pass explains the
  local interface, tactical models, repeatable training scene, subjective
  snapshot, action and target rows, tactical queries, expected-value math,
  selected-action execution, temporary auto-hit modifier, and minimal agent
  runner panels before their executable code appears.
- Chapter 27 plan:
  `engine_book/chapter_27_agent_decision_patterns_plan.md`
- Chapter 27 public page:
  `src/content/manual/27-agent-decision-patterns.mdx`
- Chapter 27 test:
  `tests/manual/test_27_agent_decision_patterns.py`
- Chapter 27 diagram assets: `agent-decision-patterns.svg` and
  `agent-decision-patterns.excalidraw`
- Chapter 27 strict example status: public snippets now execute as seven
  localized examples: `agent-decision-surfaces`, `agent-bt-priority`,
  `agent-melee-fighter-factory`, `agent-move-and-attack`,
  `agent-interrupt-detection`, `agent-utility-ranking`, and
  `agent-utility-runner`, each scoped to EB-27-001 through EB-27-007 with its
  own import/setup panel.
- Chapter 27 prose quality status: introduced agent decision patterns over
  tactical state, clarifying behavior-tree priority flow, ready-made melee
  fighter behavior, composite move-and-attack tactics, interrupt detection,
  utility scoring, and utility-agent execution. Latest pass moved the decision
  scenes into the real `dnd.scenarios.agent_decision_training` module, added a
  chapter map and code-surface table, and made each public example import the
  concrete decision-pattern symbols it uses. Current setup-prose pass explains
  the decision scene surface, melee-only agents, behavior-tree branch order,
  ready-made melee fighter behavior, composite move-and-attack tactics,
  interrupt categories, utility scoring, temporary auto-hit modifiers, and
  utility-agent execution panels before their executable code appears.
- Exact public snippet tests: `tests/book_examples/test_public_mdx_snippets.py`
- Public prose cleanup status: public manual pages no longer mention private
  notes, parity, placeholders, `pytest`, `test_items`, or behind-the-scenes
  verification language. Validation examples use plain tutorial assertions.
  Latest global pass removed copy-instruction wording, fixture language, and
  defensive `not-X` phrasing from Chapters 01, 02, 09, and 12-21; Chapter 17's
  duplicated encounter-state sentence was repaired. Current source-map pass
  renamed example panels to **Code setup: imports and scene**, reframed chapter
  intros around import paths and scene construction, removed stale public
  `note`/`test` schema fields, and replaced `http://testserver` example URLs
  with `http://neurodragon.local`. Current dice pass added
  `dnd.core.dice.fixed_dice_faces(...)` as the public deterministic dice
  walkthrough surface and migrated Chapters 04, 06, 10, 13, 14, and 15 away
  from public `unittest.mock.patch(...)` and local dice monkey-patching helpers.
  Current Chapter 09 pass tightened setup-panel prose around executable scene
  construction and row-selection functions without changing the tested snippets.
  Current Chapter 10 pass tightened setup-panel prose around the combat scenes,
  local roll-state modifier functions, and Shove actor construction while
  enrolling Chapter 10 in the staged panel-prose guard.
  Current Chapter 11 pass tightened setup-panel prose around item locations,
  stack atomicity, equipment hooks, property-based loadout displacement, and
  item-bound actions while enrolling Chapter 11 in the staged panel-prose
  guard.
  Current Chapter 12 pass tightened setup-panel prose around observer-local
  perception scenes, light and special-sense setup, sensory update lookup,
  stealth/invisibility state, subjective paths, and stacked concealment while
  enrolling Chapter 12 in the staged panel-prose guard.
  Current Chapter 13 pass tightened setup-panel prose around spell slot
  resources, spell-number composition, action discovery rows, deterministic
  spell attacks, Magic Missile aggregation, and concentration cleanup while
  enrolling Chapter 13 in the staged panel-prose guard.
  Current Chapter 14 pass tightened setup-panel prose around spell catalog
  metadata, offensive family resolution, recovery and protection state, mobility
  and temporary HP, spatial zones, and condition-producing spells while
  enrolling Chapter 14 in the staged panel-prose guard.
  Current Chapter 15 pass tightened setup-panel prose around class factories,
  fighter feature resources, barbarian Frenzy cleanup, sorcerer metamagic
  overrides, and Lucky's d20 result policy while enrolling Chapter 15 in the
  staged panel-prose guard.
  Current Chapter 16 pass tightened setup-panel prose around monster stat-block
  readers, goblin Nimble Escape variants, generic caster presets, skeleton role
  presets, and Mark Target concentration cleanup while enrolling Chapter 16 in
  the staged panel-prose guard.
  Current Chapter 17 pass tightened setup-panel prose around encounter
  lifecycle, turn contexts, external input boundaries, combat-log capture, and
  faction-survival ending while enrolling Chapter 17 in the staged panel-prose
  guard.
  Current Chapter 18 pass tightened setup-panel prose around the API client
  scene, session ownership, state/action payloads, indexed action execution,
  event and combat-log cursors, and spell catalog metadata while enrolling
  Chapter 18 in the staged panel-prose guard.
  Current Chapter 19 pass tightened setup-panel prose around map-editor catalog
  setup, scratch maps, tile patches, placed objects and objective layers, object
  deletion, save/load round trips, and preset handoff while enrolling Chapter 19
  in the staged panel-prose guard.
  Current Chapter 20 pass tightened setup-panel prose around Field Focus module
  surfaces, condition lifecycle, registered action execution, inventory item
  routing, nearby floor-object discovery, and reusable actor/scene factories
  while enrolling Chapter 20 in the staged panel-prose guard.
  Current Chapter 21 pass tightened setup-panel prose around Aegis Spark module
  surfaces, feature-owned spell registration, self-or-ally discovery,
  `SpellEvent` resolution and cleanup, and reusable scene factories while
  enrolling Chapter 21 in the staged panel-prose guard.
  Current Chapter 22 pass tightened setup-panel prose around Gatehouse scenario
  surfaces, active encounter creation, automated pass turns, human handoff,
  indexed action execution, temporary auto-hit modifiers, combat-log capture,
  and faction-survival ending while enrolling Chapter 22 in the staged
  panel-prose guard.
  Current Chapter 23 pass tightened setup-panel prose around standard arena
  surfaces, route calls, named readers, environment and actor assembly, hero kit
  selection, monster-side controller modes, human session joining, and live
  client payloads while enrolling Chapter 23 in the staged panel-prose guard.
  Current Chapter 24 pass tightened setup-panel prose around controller
  catalogue surfaces, outside-input handoff, pass-turn lifecycle, melee AI
  attack and movement choices, no-visible-enemy decline, and agent-runner
  delegation while enrolling Chapter 24 in the staged panel-prose guard.
  Current Chapter 25 pass tightened setup-panel prose around live stream
  surfaces, cursor-aware payloads, repeatable attack publication, sync frames,
  cursor replay, live fan-out, completion-before-log ordering, heartbeat
  frames, and bounded subscriber eviction while enrolling Chapter 25 in the
  staged panel-prose guard.
  Current Chapter 26 pass tightened setup-panel prose around the local tactical
  interface, live training scene, subjective snapshots, action/target rows,
  tactical queries, expected-value math, selected-action execution, temporary
  auto-hit modifiers, and minimal agent runners while enrolling Chapter 26 in
  the staged panel-prose guard.
  Current Chapter 27 pass tightened setup-panel prose around decision scenes,
  melee-only agents, behavior-tree branch order, ready-made melee fighter
  behavior, composite move-and-attack tactics, interrupt categories, utility
  scoring, temporary auto-hit modifiers, and utility-agent execution while
  enrolling Chapter 27 in the staged panel-prose guard.
  Current whole-manual guard pass added executable checks that every chapter
  with import panels remains enrolled in the panel-prose guard and that
  public manual source files avoid private-note, test-harness, fixture, helper,
  parity, placeholder, stale panel-label, `testserver`, local dice-shim, and
  mock-patching language.
  Current positive-language pass rewrote remaining high-value negation-heavy
  public prose in Chapters 21, 23, 24, 25, 26, and 27, replacing
  `not`/`without`/`instead of` framing with forward descriptions of target
  discovery, ready arena state, pass controllers, cursor replay, bounded live
  delivery, tactical EV scoring, and melee-fighter priorities.

Focused manual tests currently prepared:

- `uv run pytest tests/manual/test_01_runtime_identity_and_registries.py tests/manual/test_02_entity_anatomy.py tests/manual/test_03_values_and_modifiers.py tests/manual/test_04_dice_rolls.py tests/manual/test_05_event_lifecycle.py tests/manual/test_06_reactions_to_events.py tests/manual/test_07_conditions_and_cleanup.py tests/manual/test_08_world_model_and_movement.py tests/manual/test_09_action_discovery_and_costs.py tests/manual/test_10_combat_resolution.py tests/manual/test_11_equipment_inventory_and_items.py tests/manual/test_12_perception_light_stealth_and_invisibility.py tests/manual/test_13_spellcasting_core.py tests/manual/test_14_spell_families.py tests/manual/test_15_class_features.py tests/manual/test_16_monsters_preset_actors.py tests/manual/test_17_encounters_turns_controllers.py tests/manual/test_18_sessions_api_client_contract.py tests/manual/test_19_map_editor_scenario_authoring.py tests/manual/test_20_content_extension_basics.py tests/manual/test_21_spell_and_feature_extensions.py tests/manual/test_22_playable_scenario_packages.py tests/manual/test_23_standard_arena_game_modes.py tests/manual/test_24_built_in_controllers.py tests/manual/test_25_live_replication_streams.py tests/manual/test_26_agent_tactical_interface.py tests/manual/test_27_agent_decision_patterns.py`
- Result: 140 passed.
- Combined manual and exact public snippet check:
  `uv run pytest tests/manual/test_01_runtime_identity_and_registries.py tests/manual/test_02_entity_anatomy.py tests/manual/test_03_values_and_modifiers.py tests/manual/test_04_dice_rolls.py tests/manual/test_05_event_lifecycle.py tests/manual/test_06_reactions_to_events.py tests/manual/test_07_conditions_and_cleanup.py tests/manual/test_08_world_model_and_movement.py tests/manual/test_09_action_discovery_and_costs.py tests/manual/test_10_combat_resolution.py tests/manual/test_11_equipment_inventory_and_items.py tests/manual/test_12_perception_light_stealth_and_invisibility.py tests/manual/test_13_spellcasting_core.py tests/manual/test_14_spell_families.py tests/manual/test_15_class_features.py tests/manual/test_16_monsters_preset_actors.py tests/manual/test_17_encounters_turns_controllers.py tests/manual/test_18_sessions_api_client_contract.py tests/manual/test_19_map_editor_scenario_authoring.py tests/manual/test_20_content_extension_basics.py tests/manual/test_21_spell_and_feature_extensions.py tests/manual/test_22_playable_scenario_packages.py tests/manual/test_23_standard_arena_game_modes.py tests/manual/test_24_built_in_controllers.py tests/manual/test_25_live_replication_streams.py tests/manual/test_26_agent_tactical_interface.py tests/manual/test_27_agent_decision_patterns.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 175 passed.

Exact public snippet tests currently prepared:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py`
- Result: 156 passed in the latest exact snippet-only check after adding
  whole-manual import-panel coverage and public meta-language guards, and 160
  passed when combined with the affected Chapter 27 focused manual tests.
  The snippet test reads the MDX pages directly and executes the named
  `book-example` snippets used in Chapters 00-27.
- Guard coverage: public Python fences must be enrolled in exact snippet
  execution, executable examples must assert behavior, and `book-imports`
  panels must live inside `ExampleBlock`, stay collapsed by default, and
  contain executable public code. All 27 chapters with import panels are
  enrolled in the staged panel-prose guard, and public manual files are
  scanned for internal/test/meta language leaks.
- Strict status: all migrated public chapters now use named `book-example`
  snippets; no chapter remains in generic `chapter-public-flow` mode.
- Chapter 10 focused checkpoint:
  `uv run pytest tests/manual/test_10_combat_resolution.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 159 passed after enrolling Chapter 10 in the staged exact-snippet
  panel-prose guard and explaining the invalid-attack, hit/damage/healing,
  critical-hit, voluntary-movement reaction, and videogame Shove setup panels.
- Chapter 11 focused checkpoint:
  `uv run pytest tests/manual/test_11_equipment_inventory_and_items.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 159 passed after enrolling Chapter 11 in the staged exact-snippet
  panel-prose guard and explaining the floor/inventory/drop, stack capacity,
  equipment hook, loadout displacement, and item-action setup panels.
- Chapter 12 focused checkpoint:
  `uv run pytest tests/manual/test_12_perception_light_stealth_and_invisibility.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 160 passed after enrolling Chapter 12 in the staged exact-snippet
  panel-prose guard and explaining the geometry/light, special-sense,
  reactive-update, stealth/invisibility, subjective-path, and
  stacked-concealment setup panels.
- Chapter 13 focused checkpoint:
  `uv run pytest tests/manual/test_13_spellcasting_core.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 160 passed after enrolling Chapter 13 in the staged exact-snippet
  panel-prose guard and explaining the slot-resource, spell-number, discovery,
  Fire Bolt, Magic Missile, and concentration cleanup setup panels.
- Chapter 14 focused checkpoint:
  `uv run pytest tests/manual/test_14_spell_families.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 160 passed after enrolling Chapter 14 in the staged exact-snippet
  panel-prose guard and explaining the catalog, offensive-family,
  recovery/protection, mobility/temp-HP, spatial-zone, and condition-effect
  setup panels.
- Chapter 15 focused checkpoint:
  `uv run pytest tests/manual/test_15_class_features.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 159 passed after enrolling Chapter 15 in the staged exact-snippet
  panel-prose guard and explaining the factory, fighter-resource,
  barbarian-frenzy, sorcerer-metamagic, and Lucky setup panels.
- Chapter 16 focused checkpoint:
  `uv run pytest tests/manual/test_16_monsters_preset_actors.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 159 passed after enrolling Chapter 16 in the staged exact-snippet
  panel-prose guard and explaining the base monster, Nimble Escape, generic
  caster, skeleton role, and Mark Target setup panels.
- Chapter 17 focused checkpoint:
  `uv run pytest tests/manual/test_17_encounters_turns_controllers.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 159 passed after enrolling Chapter 17 in the staged exact-snippet
  panel-prose guard and explaining the start/end, turn/round, external-input,
  combat-log, and faction-ending setup panels.
- Chapter 18 focused checkpoint:
  `uv run pytest tests/manual/test_18_sessions_api_client_contract.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 159 passed after enrolling Chapter 18 in the staged exact-snippet
  panel-prose guard and explaining the session/join, state/actions, indexed
  action, cursor, and spell-catalog setup panels.
- Chapter 19 focused checkpoint:
  `uv run pytest tests/manual/test_19_map_editor_scenario_authoring.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 160 passed after enrolling Chapter 19 in the staged exact-snippet
  panel-prose guard and explaining the catalog/scratch-map, tile-patch,
  object-layer, object-deletion, save/load, and preset-handoff setup panels.
- Chapter 20 focused checkpoint:
  `uv run pytest tests/manual/test_20_content_extension_basics.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 160 passed after enrolling Chapter 20 in the staged exact-snippet
  panel-prose guard and explaining the module-surface, condition-lifecycle,
  registered-action, inventory-item, floor-object, and factory setup panels.
- Chapter 21 focused checkpoint:
  `uv run pytest tests/manual/test_21_spell_and_feature_extensions.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 159 passed after enrolling Chapter 21 in the staged exact-snippet
  panel-prose guard and explaining the module-surface, feature-registration,
  discovery-target, spell-resolution, and factory-scene setup panels.
- Chapter 22 focused checkpoint:
  `uv run pytest tests/manual/test_22_playable_scenario_packages.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 159 passed after enrolling Chapter 22 in the staged exact-snippet
  panel-prose guard and explaining the scenario-surface, factory-state,
  advance-human, execute-action, and faction-ending setup panels.
- Chapter 23 focused checkpoint:
  `uv run pytest tests/manual/test_23_standard_arena_game_modes.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 159 passed after enrolling Chapter 23 in the staged exact-snippet
  panel-prose guard and explaining the arena-surface, build-standard,
  hero-kit, control-mode, start-join, and live-payload setup panels.
- Chapter 24 focused checkpoint:
  `uv run pytest tests/manual/test_24_built_in_controllers.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 160 passed after enrolling Chapter 24 in the staged exact-snippet
  panel-prose guard and explaining the catalogue-surface, external-input,
  pass-turn, melee-attack, melee-move, no-visible-enemy, and agent-runner setup
  panels.
- Chapter 25 focused checkpoint:
  `uv run pytest tests/manual/test_25_live_replication_streams.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 160 passed after enrolling Chapter 25 in the staged exact-snippet
  panel-prose guard and explaining the stream-surface, sync-frame,
  cursor-replay, live-fanout, completion-before-log, heartbeat-frame, and
  bounded-eviction setup panels.
- Chapter 26 focused checkpoint:
  `uv run pytest tests/manual/test_26_agent_tactical_interface.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 160 passed after enrolling Chapter 26 in the staged exact-snippet
  panel-prose guard and explaining the interface-surface, tactical-snapshot,
  action-options, tactical-queries, expected-value, execute-choice, and
  base-runner setup panels.
- Chapter 27 focused checkpoint:
  `uv run pytest tests/manual/test_27_agent_decision_patterns.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 160 passed after enrolling Chapter 27 in the staged exact-snippet
  panel-prose guard and explaining the decision-surface, behavior-tree,
  melee-fighter, move-and-attack, interrupt-detection, utility-ranking, and
  utility-runner setup panels.
- Agent training module relocation checkpoint:
  `uv run pytest tests/manual/test_26_agent_tactical_interface.py tests/manual/test_27_agent_decision_patterns.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 165 passed after moving the agent training and decision scene
  surfaces out of ignored `/ai` modules and into visible
  `dnd.scenarios.agent_tactical_training` and
  `dnd.scenarios.agent_decision_training` modules.
- Chapter 01 quality checkpoint:
  `uv run pytest tests/manual/test_01_runtime_identity_and_registries.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 157 passed after adding setup-panel explanations to every Chapter 01
  import panel and renaming the publishing example to
  `runtime-object-publishing`.
- Chapter 02 quality checkpoint:
  `uv run pytest tests/manual/test_02_entity_anatomy.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 110 passed after adding the visible symbol/import map and clarifying
  the tutorial actor constructor.
- Chapter 03 quality checkpoint:
  `uv run pytest tests/manual/test_03_values_and_modifiers.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 158 passed after adding setup explanations to the remaining Chapter
  03 import panels and adding a staged exact-snippet guard that requires
  panel prose before code for Chapters 01-03.
- Chapter 04 quality checkpoint:
  `uv run pytest tests/manual/test_04_dice_rolls.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 159 passed after adding setup explanations to the remaining Chapter
  04 import panels and extending the staged exact-snippet panel-prose guard
  to Chapters 01-04.
- Chapter 05 quality checkpoint:
  `uv run pytest tests/manual/test_05_event_lifecycle.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 159 passed after adding setup explanations to the remaining Chapter
  05 import panels and extending the staged exact-snippet panel-prose guard
  to Chapters 01-05.
- Chapter 06 quality checkpoint:
  `uv run pytest tests/manual/test_06_reactions_to_events.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 160 passed after adding setup explanations to the remaining Chapter
  06 import panels and extending the staged exact-snippet panel-prose guard
  to Chapters 01-06.
- Chapter 07 quality checkpoint:
  `uv run pytest tests/manual/test_07_conditions_and_cleanup.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 159 passed after adding setup explanations to the remaining Chapter
  07 import panels and extending the staged exact-snippet panel-prose guard
  to Chapters 01-07.
- Chapter 08 quality checkpoint:
  `uv run pytest tests/manual/test_08_world_model_and_movement.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 159 passed after adding setup explanations to the remaining Chapter
  08 import panels and extending the staged exact-snippet panel-prose guard
  to Chapters 01-08.
- Chapter 09 quality checkpoint:
  `uv run pytest tests/manual/test_09_action_discovery_and_costs.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 160 passed after enrolling Chapter 09 in the staged exact-snippet
  panel-prose guard and verifying its existing setup-panel explanations.
- Chapter 10 quality checkpoint:
  `uv run pytest tests/manual/test_10_combat_resolution.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 159 passed after enrolling Chapter 10 in the staged exact-snippet
  panel-prose guard and explaining the invalid-attack, hit/damage/healing,
  critical-hit, voluntary-movement reaction, and videogame Shove setup panels.
- Chapter 11 quality checkpoint:
  `uv run pytest tests/manual/test_11_equipment_inventory_and_items.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 159 passed after enrolling Chapter 11 in the staged exact-snippet
  panel-prose guard and explaining the floor/inventory/drop, stack capacity,
  equipment hook, loadout displacement, and item-action setup panels.
- Chapter 12 quality checkpoint:
  `uv run pytest tests/manual/test_12_perception_light_stealth_and_invisibility.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 160 passed after enrolling Chapter 12 in the staged exact-snippet
  panel-prose guard and explaining the geometry/light, special-sense,
  reactive-update, stealth/invisibility, subjective-path, and
  stacked-concealment setup panels.
- Chapter 13 quality checkpoint:
  `uv run pytest tests/manual/test_13_spellcasting_core.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 160 passed after enrolling Chapter 13 in the staged exact-snippet
  panel-prose guard and explaining the slot-resource, spell-number, discovery,
  Fire Bolt, Magic Missile, and concentration cleanup setup panels.
- Chapter 14 quality checkpoint:
  `uv run pytest tests/manual/test_14_spell_families.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 160 passed after enrolling Chapter 14 in the staged exact-snippet
  panel-prose guard and explaining the catalog, offensive-family,
  recovery/protection, mobility/temp-HP, spatial-zone, and condition-effect
  setup panels.
- Chapter 15 quality checkpoint:
  `uv run pytest tests/manual/test_15_class_features.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 159 passed after enrolling Chapter 15 in the staged exact-snippet
  panel-prose guard and explaining the factory, fighter-resource,
  barbarian-frenzy, sorcerer-metamagic, and Lucky setup panels.
- Chapter 16 quality checkpoint:
  `uv run pytest tests/manual/test_16_monsters_preset_actors.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 159 passed after enrolling Chapter 16 in the staged exact-snippet
  panel-prose guard and explaining the base monster, Nimble Escape, generic
  caster, skeleton role, and Mark Target setup panels.
- Chapter 17 quality checkpoint:
  `uv run pytest tests/manual/test_17_encounters_turns_controllers.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 159 passed after enrolling Chapter 17 in the staged exact-snippet
  panel-prose guard and explaining the start/end, turn/round, external-input,
  combat-log, and faction-ending setup panels.
- Chapter 24 quality checkpoint:
  `uv run pytest tests/manual/test_24_built_in_controllers.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 141 passed after adding the built-in-controller chapter map,
  code-surface table, real `dnd.scenarios.controller_catalogue` surface, and
  seven standalone exact snippets.
- Chapter 25 quality checkpoint:
  `uv run pytest tests/manual/test_25_live_replication_streams.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 147 passed after adding the live-replication chapter map,
  code-surface table, real `server.live_replication` surface, and seven
  standalone exact snippets.
- Chapter 26 quality checkpoint:
  `uv run pytest tests/manual/test_26_agent_tactical_interface.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 153 passed after adding the agent-interface chapter map,
  code-surface table, real `dnd.scenarios.agent_tactical_training` surface,
  and seven standalone exact snippets.
- Chapter 27 quality checkpoint:
  `uv run pytest tests/manual/test_27_agent_decision_patterns.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 159 passed after adding the agent-decision chapter map,
  code-surface table, real `dnd.scenarios.agent_decision_training` surface, and
  seven standalone exact snippets.
- Current affected API/client checkpoint:
  `uv run pytest tests/manual/test_18_sessions_api_client_contract.py tests/book_examples/test_public_mdx_snippets.py`
- Result: 159 passed after Chapter 18's exact client/API snippets were verified
  directly from the MDX page and the staged panel-prose guard was extended to
  the session, state/action, indexed execution, cursor, and catalog panels.

Astro build:

- `npm run build`
- Result: 29 pages built.
- Latest verification checkpoint: exact public MDX snippet execution passed
  with 156 tests after the positive-language pass; the targeted scan for
  negation-heavy wording in Chapters 21 and 23-27 returned zero matches; public
  hygiene scans returned no matches for private/test/meta wording, note/test
  schema fields, stale panel phrasing, public `unittest.mock` dice control,
  `http://testserver`, stale helper or opt-out naming, unregistered Python
  fences, TODO/TBD, or placeholder wording; Astro generated all 29 static
  pages; the six affected manual routes returned `200`.

Public route checks currently return `200` for:

- `/`
- `/manual/00-neurodragon-dev-manual/`
- `/manual/01-runtime-identity-and-registries/`
- `/manual/02-entity-anatomy/`
- `/manual/03-values-and-modifiers/`
- `/manual/04-dice-rolls/`
- `/manual/05-event-lifecycle/`
- `/manual/06-reactions-to-events/`
- `/manual/07-conditions-and-cleanup/`
- `/manual/08-world-model-and-movement/`
- `/manual/09-action-discovery-and-costs/`
- `/manual/10-combat-resolution/`
- `/manual/11-equipment-inventory-and-items/`
- `/manual/12-perception-light-stealth-and-invisibility/`
- `/manual/13-spellcasting-core/`
- `/manual/14-spell-families-and-implemented-spells/`
- `/manual/15-class-features-factories-and-feats/`
- `/manual/16-monsters-and-preset-actors/`
- `/manual/17-encounters-turns-and-controllers/`
- `/manual/18-sessions-apis-and-client-payloads/`
- `/manual/19-map-editor-and-scenario-authoring/`
- `/manual/20-content-extension-basics/`
- `/manual/21-spell-and-feature-extensions/`
- `/manual/22-playable-scenario-packages/`
- `/manual/23-standard-arena-game-modes/`
- `/manual/24-built-in-controllers-and-automated-turns/`
- `/manual/25-live-replication-streams/`
- `/manual/26-agent-tactical-interface/`
- `/manual/27-agent-decision-patterns/`
- `/diagrams/condition-cleanup-tree.svg`
- `/diagrams/action-discovery-and-costs.svg`
- `/diagrams/core-combat-flow.svg`
- `/diagrams/equipment-inventory-items.svg`
- `/diagrams/senses-light-visibility-pipeline.svg`
- `/diagrams/spellcasting-core.svg`
- `/diagrams/spell-families.svg`
- `/diagrams/class-features-factories.svg`
- `/diagrams/monsters-preset-actors.svg`
- `/diagrams/encounters-turns-controllers.svg`
- `/diagrams/sessions-api-client-contract.svg`
- `/diagrams/map-editor-scenario-authoring.svg`
- `/diagrams/content-extension-basics.svg`
- `/diagrams/spell-feature-extension-flow.svg`
- `/diagrams/playable-scenario-package.svg`
- `/diagrams/standard-arena-game-modes.svg`
- `/diagrams/built-in-controllers-and-automated-turns.svg`
- `/diagrams/live-replication-streams.svg`
- `/diagrams/agent-tactical-interface.svg`
- `/diagrams/agent-decision-patterns.svg`

Notes, tests, and source files remain research material. They are not public
manual pages.

## Why The Previous Draft Failed

The previous draft taught the engine in the wrong order. It referenced concepts
such as handlers, test parity, helper functions, and implementation fragments
before the reader had learned the game model, runtime identity, registries,
values, dice, or events.

The public result felt like thin topic notes instead of a readable developer
manual. Readers had to click around to assemble context, tables were not treated
as designed teaching material, and examples sometimes looked like test harnesses
rather than tutorial code.

This rebuild must fix the teaching sequence before any page prose is restored.

## Manual Identity

Working title: **NeuroDragon Dev Manual**

The manual is a developer dungeon master manual. A tabletop dungeon master
interprets player intent, applies rules, updates the world, and narrates the
result. NeuroDragon does that in software: it validates intent, resolves rules,
changes state, and exposes the outcome to the game client.

The manual must therefore teach two things together:

- The D&D-style game concept a developer is modeling.
- The exact NeuroDragon runtime surface that implements that concept.

It must not read like internal notes, a test index, a parity matrix, or a
codebase dump.

## Reader Contract

Every public chapter must be pleasant to read from top to bottom. The reader
should not need to click hidden links, inspect tests, or read source files to
understand the concept being taught on the page.

Public pages must:

- Introduce each noun before relying on it.
- Start from game meaning, then runtime model, then code.
- Show import paths before substantial snippets.
- Use real tutorial examples with visible setup.
- Keep tests and evidence private unless they are explicitly part of a developer
  workflow section.
- Present tables, callouts, diagrams, and code blocks as designed content.
- Use diagrams heavily when relationships are easier to see than to describe.
- Explain SRD relationships as source-rule comparison, not as a second runtime
  mode.
- Document one videogame ruleset: the NeuroDragon/BG3-style engine truth.

Public pages must not:

- Mention handler behavior before events, phases, triggers, and queues are
  already defined.
- Mention parity, `tests/engine_book`, private notes, or research breadcrumbs.
- Use fake helper names from tests unless the helper is fully defined and taught
  in the same chapter.
- Force the reader to jump between small pages for a single conceptual unit.
- Publish placeholders, planning prose, TODOs, or meta commentary about the
  rebuild work.

## Definition Ladder

This is the hard dependency order. A chapter may only use a concept as assumed
knowledge after the manual has introduced it in a prior layer.

| Layer | Teaches | May Not Depend On |
| --- | --- | --- |
| 0. Game Promise And Vocabulary | NeuroDragon, developer-as-DM, videogame ruleset, client/runtime boundary, creature, actor, ability, skill, save, action, turn, condition, spell, item, encounter | UUIDs, events, modifiers, handlers |
| 1. Runtime Identity | Object identity, UUIDs, registries, lookup, ownership at a plain level | Dice, conditions, action templates |
| 2. Actor Anatomy | `Entity` as the playable/AI actor container and its blocks | Handler internals, combat pipeline |
| 3. Values And Modifiers | Scores, bonuses, penalties, advantage, resistance, contextual values | Event handlers |
| 4. Dice | Raw dice, roll objects, deterministic examples, critical damage basics | Result processors |
| 5. Events | Event records, phases, lineage, parent/child events, queue storage, completion logs | Handlers until the event model is clear |
| 6. Reactions To Events | Triggers, handlers, result processors, spatial handlers | Conditions not yet defined as lifecycle objects |
| 7. Conditions And Cleanup | Applying ongoing effects, modifier tracking, subconditions, linked cleanup | Spell concentration until spellcasting exists |
| 8. World Model | Grid, tiles, terrain, movement, forced movement, voluntary movement | Full combat flow |
| 9. Actions | Templates, discovery, targets, costs, resources, item/environment actions | Attack internals before action basics |
| 10. Combat | Attack, AC, damage, healing, shove, reactions, logs | Spell families |
| 11. Equipment And Items | Loadouts, two-handed displacement, inventory, usable items, objects | Class factory details |
| 12. Perception | Senses, light, stealth, invisibility, revealed state | Spell-specific edge cases |
| 13. Spellcasting | Spell actions, slots, DCs, concentration, AoE, spell result events | High-level spell catalog before mechanics for individual spells |
| 14. Character Content | Classes, features, feats, monsters, factories | API/session details |
| 15. Running The Game | Encounters, turns, controllers, sessions, client state, scenario authoring | New engine primitives |
| 16. Extending The Engine | Add a condition, action, item, spell, feature, monster, and scenario | Anything not previously introduced |

## First Public Reading Arc

The first rebuilt release should be a long-form orientation arc, not a pile of
small topic pages. It should make the reader comfortable before code-heavy
material appears.

### 00. NeuroDragon Dev Manual

Goal: establish the product, developer-dungeon-master metaphor, and D&D
vocabulary before engine internals.

Must cover:

- NeuroDragon as a tactical D&D-style videogame engine.
- The engine as the software dungeon master.
- Player intent entering the runtime and resolved state returning to the client.
- One ruleset only: NeuroDragon's videogame implementation.
- What this manual teaches.
- Creature/actor, action, bonus action, reaction, movement, turn, round.
- Ability score, ability modifier, skill, saving throw.
- Attack, armor class, hit points, damage, healing.
- Condition, spell, item, equipment, visibility, encounter.

Must avoid:

- Registries, UUIDs, handlers, modifiers, dice internals, tests, and source
  archaeology.

Primary visual:

- A simple flow diagram: player/client intent -> engine DM -> rule resolution ->
  world state and narrated outcome.
- A vocabulary map showing actor, intent, roll, effect, world, and encounter.

### 01. Runtime Identity And Registries

Goal: explain how the runtime names and recovers live objects.

Must cover:

- UUID identity.
- `BaseObject`, `BaseValue`, `BaseBlock`, and `Entity` registries.
- Why registries exist in a game runtime.
- Position indexing only at the level needed to understand entities on a grid.

Must avoid:

- Event handlers, conditions, action templates, dice processors.

Primary visual:

- Registry family diagram with separate indexes and lookup arrows.

### 02. Entity Anatomy

Goal: make a creature concrete before individual subsystems are explained.

Must cover:

- Entity as actor container.
- Ability scores, skills, saves, health, equipment, inventory, senses, action
  economy, spellcasting, faction, active conditions.
- What each block is responsible for at a one-paragraph level.

Must avoid:

- Deep cleanup mechanics, event subscriptions, class factories.

Primary visual:

- Entity composition diagram.

### 03. Values And Modifiers

Goal: teach how numbers and roll states are built from small rule contributions.

Must cover:

- `ModifiableValue`.
- Numerical modifiers.
- Advantage/disadvantage.
- Critical and auto-hit status.
- Resistances, vulnerabilities, immunities.
- Static vs contextual modifiers.
- Self effects before target-propagated effects.

Must avoid:

- Event handlers. Say "later systems read the resolved value" until events are
  introduced.

Primary visual:

- Value-channel diagram with self channels and target channels.

### 04. Dice

Goal: teach raw rolling before roll-result modification.

Must cover:

- Dice notation and dice objects.
- D20 roll shape.
- Damage roll shape.
- Advantage selection.
- Deterministic examples with visible `patch` usage.

Must avoid:

- Result processors until the end of the chapter as a bridge to events.

Primary visual:

- Roll pipeline diagram: dice expression -> raw rolls -> selected value ->
  total.

### 05. Events

Goal: teach the causal record before any reaction system.

Must cover:

- Event as declared intent and resolved effect record.
- Phases: declaration, execution, effect, completion.
- Lineage and parent/child events.
- Queue storage.
- Completion logs as observation after rule resolution.

Must avoid:

- Starting with handlers. Handlers appear only after events are fully defined.

Primary visual:

- Event lifecycle timeline.

### 06. Reactions To Events

Goal: now, and only now, introduce handlers and processors.

Must cover:

- Trigger matching.
- Event handlers.
- Dice/result processors.
- Spatial handlers.
- Voluntary vs forced movement as a rule distinction.

Must avoid:

- Presenting handlers as the first explanation of the engine.

Primary visual:

- Subscription diagram: event queue -> trigger match -> handler -> event/result.

## Chapter Build Protocol

Each chapter must be planned before being written. The plan should list:

- Reader promise.
- Concepts introduced for the first time.
- Concepts forbidden in this chapter.
- Required visuals.
- Source files to verify from first principles.
- SRD/rules markdown to compare.
- Tests or examples that will verify the public examples.

Then the chapter can be written.

## Chapter Page Structure

Use this structure by default:

1. **What You Are Learning**
   - Three to five concrete outcomes.

2. **Game Meaning**
   - Explain the D&D/videogame concept in plain language.

3. **NeuroDragon Model**
   - Explain the engine objects that implement the concept.

4. **Where The Imports Come From**
   - A table mapping symbols to modules and why they appear.

5. **Tutorial Scene**
   - Complete setup for the examples.

6. **Walkthrough**
   - One concept at a time, with prose before code.

7. **Rules Relationship**
   - Explain SRD comparison and NeuroDragon's chosen videogame behavior.

8. **What Comes Next**
   - Name the next concept in the dependency ladder.

## Code Example Standard

Public examples must be tutorial examples, not pasted tests.

Required:

- Imports visible the first time symbols appear.
- Setup visible before behavior.
- Helper functions defined before use.
- Deterministic dice shown with direct `unittest.mock.patch` usage.
- Assertions only when they read as observed behavior.
- Names like `hero`, `goblin`, `training_dummy`, `arena`, and `attack_bonus`.

Forbidden in public examples unless fully defined and explained in the same
chapter:

- `make_bonus`
- `make_damage_roll`
- `make_d20_roll`
- `fixed_randint`
- `completed_damage_events`
- `improved_event`
- `worse_event`
- `RegistryProbe`
- Any reference that only makes sense inside `tests/engine_book`

## Visual Standard

The manual should use visuals aggressively, but each visual must teach a
relationship the prose alone would make heavy.

Preferred visual forms:

- Excalidraw for conceptual diagrams and object relationships.
- SVG exported from Excalidraw or hand-authored when stable.
- Tables for comparison and responsibilities.
- Callouts for engine policy choices, especially SRD vs videogame behavior.

Visuals must not be decorative filler. They need a caption that states what the
reader should learn from them.

## Tables And Layout Standard

Tables are first-class content. They must be readable on desktop and mobile.

Each table needs:

- Clear column names.
- Enough spacing to scan.
- No code wrapping that makes rows unreadable.
- A plain-language sentence before the table explaining what comparison it
  answers.

## Quality Gates Before Publishing Any Chapter

A chapter can enter the Astro site only when all checks pass:

- The chapter does not use undefined concepts.
- The chapter does not expose private notes, parity language, or test paths.
- The first substantial code block has visible imports.
- All helper functions/classes in public snippets are defined in public prose.
- The examples are backed by focused tests, but the public page is not a test
  index.
- SRD relationship is explained as comparison only.
- NeuroDragon's actual single ruleset is stated without alternate runtime modes.
- Tables render cleanly.
- Diagrams render cleanly and have meaningful captions.
- The page is long enough to read pleasantly as a manual chapter.
- The page can be understood without leaving the page.

## Immediate Next Step

The first rebuilt unit has been decided in
`engine_book/first_public_unit_plan.md`.

The first opening draft now exists as
`src/content/manual/00-neurodragon-dev-manual.mdx` in the Astro webbook and is
served at:

- `http://127.0.0.1:4327/manual/00-neurodragon-dev-manual/`

The opening has received a self-review polish pass for reader roles, glossary
scanning, table behavior, mobile overflow behavior, screenshot inspection, and
positive framing.

Next, review that opening chapter in the browser for format, tone, and reading
experience. Do not restore the deleted topic pages or continue to lower-level
implementation chapters until the opening chapter has been reviewed.

While waiting for that review, the first implementation chapter has been
planned privately in:

- `engine_book/chapter_01_runtime_identity_plan.md`

Chapter 01's clean manual pytest file has also been prepared and passed:

- `tests/manual/test_01_runtime_identity_and_registries.py`

That work is preparation only. It does not publish Chapter 01.

## Checkpoint: Executable Imports & Scene Contract

The public webbook now treats manual snippets as executable source, not
freestyle prose code. Each named Python example starts with a collapsed
`Imports & Scene` disclosure beside the example, and the visible code that
follows is concatenated with that disclosure in MDX page order.

The focused guard in `tests/book_examples/test_public_mdx_snippets.py` now
checks that:

- Every public Python fence in converted chapters is marked as a book example.
- Every executed book example begins inside its local `Imports & Scene` panel.
- Collapsed panels are inside the visible `ExampleBlock`, remain closed by
  default, and still participate in execution.
- Every executed example includes assertions.
- The code is compiled and executed from the exact MDX fences.

The public presentation was also updated:

- Example chips now read `Imports`, `Resolve`, `Assert`.
- The old `Code setup: imports and scene` label was removed from public pages.
- Tables inside `Imports & Scene` disclosures no longer inherit the full-width
  article table layout.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `172 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Chapter 05 Phase Contract

Chapter 05 now teaches the event lifecycle contract before introducing code
surfaces or examples. The new `The Lifecycle Contract` section explains each
phase as a runtime promise:

- Declaration gives an attempted game moment an address.
- Execution resolves legality, resources, targets, and procedure.
- Effect is where state change and active rule responses belong.
- Completion is final observation for stable logs, streams, replay cursors, and
  client synchronization.
- Cancel preserves an ended attempt with a reason.

The book-example guard now enforces that Chapter 05 presents this phase
contract before `Code Surfaces In This Chapter` and before the first executable
example.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `173 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Chapter 06 Reaction Timing Contract

Chapter 06 now teaches reactions as a timing model before introducing code
surfaces or examples. The new `The Reaction Contract` section explains the four
choices every reaction rule makes:

- Event surface: the kind of occurrence being answered.
- Phase: the lifecycle promise that must be true when the rule runs.
- Match scope: source, target, broad event match, or map position.
- Processor result: observe, modify, replace, cancel, or leave unchanged.

The section also states the tactical movement policy before any movement code:
voluntary steps publish `STEP_MOVEMENT`, shove/push/pull displacement publishes
`FORCED_MOVEMENT`, and forced displacement may still produce spatial entry/exit
effects while opportunity-style reactions remain tied to voluntary steps.

The book-example guard now enforces that Chapter 06 presents this timing
contract before `Code Surfaces In This Chapter` and before the first executable
example.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `174 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Chapter 07 Condition Ownership Contract

Chapter 07 now teaches conditions as owned runtime packages before introducing
code surfaces or examples. The new `The Condition Contract` section explains
the five questions every condition rule answers:

- Who owns the state.
- What application creates.
- What the condition remembers.
- Who walks the cleanup tree.
- How expiry enters the same removal path.

The section also clarifies the division of responsibility: a condition class
describes the game rule it contributes, while the owning block drives traversal
through same-block subconditions, linked conditions on other blocks, reverse
parent links, and exact runtime artifacts.

The book-example guard now enforces that Chapter 07 presents this ownership
contract before `Code Surfaces In This Chapter` and before the first executable
example.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `175 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Chapter 08 World Movement Contract

Chapter 08 now teaches the world model as a movement contract before
introducing code surfaces or examples. The new `The World Movement Contract`
section explains the five questions every movement rule answers:

- Which cells exist.
- What a cell costs.
- Whether an edge can be crossed.
- Where the actor moved.
- Why the actor moved.

The section also states the division of responsibility: `GridMap` owns board
facts, tiles, bounds, position indexes, and spatial events; movement actions,
shoves, spells, and effects supply the parent event that explains why an actor
moved. It keeps the voluntary-step and forced-displacement distinction visible
while also explaining that both surfaces can publish spatial entry for hazards
and zones.

The book-example guard now enforces that Chapter 08 presents this movement
contract before `Code Surfaces In This Chapter` and before the first executable
example.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `176 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Chapter 09 Action Choice Contract

Chapter 09 now teaches action discovery as the player-choice contract before
introducing code surfaces or examples. The new `The Action Choice Contract`
section explains the five questions every action choice answers:

- Who is acting.
- What produced the choice.
- What the choice costs.
- What the choice can target.
- What happens when the selected row resolves.

The section also states the discovery/execution split in player-facing terms:
discovery builds the current command menu and stable target indices, while
execution receives the selected row, validates it again, emits events, applies
effects, and spends costs only after success.

The book-example guard now enforces that Chapter 09 presents this choice
contract before `Code Surfaces In This Chapter` and before the first executable
example.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `177 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Chapter 10 Combat Resolution Contract

Chapter 10 now teaches combat resolution as the consequence contract before
introducing code surfaces or examples. The new `The Combat Resolution Contract`
section explains the six questions every combat rule answers:

- What was attempted.
- Whether the attempt is legal.
- Which roll decides the outcome.
- What state changes.
- Which events describe the consequence.
- When the action economy cost is paid.

The section presents combat as the runtime answer to the player-facing question
"what happened?" It keeps attacks, saving throws, damage rolls, HP changes,
healing, dying and death state, movement, forced movement, and reaction timing
in one consequence pipeline that remains both D&D-readable and videogame-ready.

The book-example guard now enforces that Chapter 10 presents this combat
contract before `Code Surfaces In This Chapter` and before the first executable
example.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `178 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Chapter 11 Item Ownership Contract

Chapter 11 now teaches equipment, inventory, and usable objects as one item
ownership contract before introducing code surfaces or examples. The new `The
Item Ownership Contract` section explains the six questions every item rule
answers:

- Where the item is.
- Who can move it.
- What happens when it stacks.
- What happens when it equips.
- What happens to displaced gear.
- What happens when the item is used.

The section also states the videogame loadout rule directly: the engine keeps
one melee set and one ranged set, melee hand conflicts are resolved by
order-based displacement, `TWO_HANDED` melee weapons displace off-hand melee
gear and are displaced by later off-hand melee gear, and ranged slots remain
separate so sword-and-shield can coexist with a bow or dual hand crossbows.

The book-example guard now enforces that Chapter 11 presents this ownership
contract before `Code Surfaces In This Chapter` and before the first executable
example.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `179 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Chapter 12 Visibility Contract

Chapter 12 now teaches perception, light, stealth, and invisibility as one
observer-local visibility contract before introducing code surfaces or examples.
The new `The Visibility Contract` section explains the six questions every
visibility rule answers:

- Which cells are geometrically relevant.
- Which cells are actually visible.
- Which actors and objects appear.
- What the player can remember.
- Which paths the UI can preview.
- How the client learns about change.

The section presents the actual perception pipeline: geometric FOV establishes
subscriptions, effective light filters visible cells per observer, perceivability
filters entities and objects through stealth DC, invisibility, object flags, and
special senses, and `SensoryUpdateEvent` carries observer-specific deltas for
light, movement, death, conditions, objects, and perceivability changes.

The book-example guard now enforces that Chapter 12 presents this visibility
contract before `Code Surfaces In This Chapter` and before the first executable
example.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `180 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Chapter 13 Spellcasting Contract

Chapter 13 now teaches spellcasting as the magic-facing action contract before
introducing code surfaces or examples. The new `The Spellcasting Contract`
section explains the seven questions every spellcasting rule answers:

- Which spell the actor can cast.
- Which resource pays for it.
- Which casting number is used.
- How the row appears to the player.
- What event records the cast.
- How many targets resolve.
- How a lasting spell ends.

The section presents the shared casting machinery directly: spell classes
register as action templates, cantrips are slotless, leveled spells spend
`spell_slot_1` through `spell_slot_9`, `SpellcastingBlock.spellcasting_ability`
selects attack and save numbers, action discovery creates slot-specific rows,
`SpellAction.apply()` creates `SpellEvent`, and the caster-owned
`Concentrating` condition links to active spell effects for cleanup.

The book-example guard now enforces that Chapter 13 presents this spellcasting
contract before `Code Surfaces In This Chapter` and before the first executable
example.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `181 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Chapter 14 Spell Family Contract

Chapter 14 now teaches the implemented spell catalog as runtime spell families
before introducing code surfaces or examples. The new `The Spell Family
Contract` section explains the seven questions every spell family answers:

- What player intention it serves.
- What target shape it uses.
- Who rolls or resists.
- What changes immediately.
- What lasts after the cast.
- Who cleans it up.
- How tooling finds it.

The section presents the catalog as a route from fantasy name to implementation:
spell level and school organize the catalog, while family shape explains damage,
healing, protection, movement, temporary HP, spatial control, condition pressure,
targeting, immediate state, lasting state, cleanup ownership, and metadata used
by tools and controllers.

The book-example guard now enforces that Chapter 14 presents this spell-family
contract before `Code Surfaces In This Chapter` and before the first executable
example.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `182 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Chapter 15 Character Content Contract

Chapter 15 now teaches classes, factories, and feat-style features as owned
character content before introducing code surfaces or examples. The moved and
expanded `The Character Content Contract` section explains the seven questions
every character-content rule answers:

- Which build choice grants it.
- What resource it owns.
- What button it adds.
- What passive state it adds.
- What mode it can enter.
- What engine timing it watches.
- How it cleans up.

The section presents factories as the complete character assembly route:
configs choose level, style, subclass/path, metamagic, spells, ASIs, and gear;
features own action-economy resources, registered action templates, modifiers,
event handlers, result processors, spell-template overrides, and active mode
conditions; removing the owning feature condition removes the runtime state it
attached.

The book-example guard now enforces that Chapter 15 presents this
character-content contract before `Code Surfaces In This Chapter` and before
the first executable example.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `183 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Chapter 16 Preset Actor Contract

Chapter 16 now teaches monsters and preset actors as complete playable entity
recipes before introducing code surfaces or examples. The new `The Preset Actor
Contract` section explains the seven questions every preset actor rule answers:

- What creature role it serves in play.
- Which entity state it creates.
- Which gear or natural weapons define attacks.
- Which actions appear on the actor's turn.
- Which board state the actor enters.
- How the client reads the actor.
- How designers vary the actor safely.

The section presents monster factories as ordinary runtime composition:
stat-block vocabulary becomes `EntityConfig`, ability scores, hit points,
equipment, movement, senses, faction, position, action templates, spells,
inventory, conditions, and event handlers. It also states the important runtime
boundary: a monster or preset actor does not use a separate monster runtime; the
factory output is immediately usable by encounters and controllers through the
same entity, action, condition, equipment, spell, sense, inventory, and event
systems used by all actors.

The book-example guard now enforces that Chapter 16 presents this preset actor
contract before `Code Surfaces In This Chapter` and before the first executable
example.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `184 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Chapter 17 Running-Game Contract

Chapter 17 now teaches encounters, turns, and controllers as the playable
runtime loop before introducing code surfaces or examples. The expanded `The
Running-Game Contract` section explains the seven questions every encounter
rule answers:

- Who is in the fight.
- How action order is created.
- What opens a turn.
- Who supplies the choice.
- How a choice resolves.
- Where the result is published.
- How the scene ends.

The section presents `Encounter` as the developer-DM clock around the rest of
the engine: actors keep ownership of stats, equipment, actions, conditions,
spells, inventory, and senses, while the encounter owns combatant rows,
initiative order, turn boundaries, controller input boundaries, event-log
capture, listener notification, death checks, and faction-survival ending.

Chapter 17 now also includes `Encounter Authoring Guide` before the code
surfaces. The guide gives a concrete scene-building sequence: choose live
actors, assign controllers, establish initiative, open the scene, open turns,
route choices through encounter execution, publish completed event logs, and
close the scene through death checks plus faction survival.

The book-example guard now enforces that Chapter 17 presents this running-game
contract and authoring guide before `Code Surfaces In This Chapter` and before
the first executable example.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `185 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Chapter 18 Client Contract

Chapter 18 now teaches sessions, APIs, and client payloads as a playable
network contract before introducing code surfaces or examples. The expanded
`The Client Contract` section explains the seven questions every client-facing
rule answers:

- Who is asking.
- Which actors the client can control.
- What the client should draw.
- Whose input is needed now.
- Which choices are legal.
- How a choice is submitted.
- What changed afterward.

The section presents the API as an authority-preserving play protocol:
`PlayerSession` gives the client identity, `GameSession` maps sessions to
entities, `/state` serializes the renderable scene, current-turn and ping
payloads expose input boundaries, available-action payloads expose legal action
and target rows, `/action/execute` submits the selected template and target
index through validation, and `ActionResult`, `/events`, `/combat-log`, stream
IDs, and catalogs publish consequences and UI metadata.

Chapter 18 now also includes `Client Surface Authoring Guide` before the code
surfaces. The guide gives a concrete client-feature sequence: create a
participant identity, join the active game, render from snapshots, show turn
ownership, build controls from available-action rows, submit the chosen row,
advance from event/combat-log cursors, and fill menus from catalogs.

The book-example guard now enforces that Chapter 18 presents this client
contract and authoring guide before `Code Surfaces In This Chapter` and before
the first executable example.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `186 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Chapter 19 Authoring Contract

Chapter 19 now teaches map editing and scenario authoring as a designer-facing
payload workflow before introducing code surfaces or examples. The expanded
`The Authoring Contract` section explains the seven questions every
map-authoring rule answers:

- What the designer can choose from.
- Which map is open.
- How tile rules are painted.
- How play objects are placed.
- How placed objects are removed.
- What tools can inspect objectively.
- How the design persists and enters play.

The section presents the map editor as the authoring loop before initiative:
catalog choices open scratch or preset maps, snapshots expose bounds, tiles,
and floor objects, tile patches apply terrain/light/borders, object routes
instantiate catalog entries and loot, objective walkability/visibility/light
layers support tooling, and save routes persist reloadable map documents that
playable modes can later use as encounter foundations.

Chapter 19 now also includes `Map Authoring Guide` before the code surfaces.
The guide gives a concrete scenario-space sequence: choose the palette, open a
scratch or preset authoring document, paint tile rules, place objects and loot,
inspect objective layers, revise placements, save the document, and hand the
space to playable modes.

The book-example guard now enforces that Chapter 19 presents this authoring
contract and authoring guide before `Code Surfaces In This Chapter` and before
the first executable example.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `187 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Chapter 20 Extension Contract

Chapter 20 now teaches content extension basics as a bottom-up content-authoring
contract before introducing code surfaces or examples. The expanded `The
Extension Contract` section explains the seven questions every content-extension
rule answers:

- Where the content lives.
- What state can last.
- What the player can choose.
- How the content travels.
- How designers reuse it.
- How it becomes a playable scene.
- How the runtime trusts it.

The section presents Field Focus as one complete content pack: an importable
module exposes condition, action, item, actor, and scene factory surfaces;
`BaseCondition` owns lasting modifiers and cleanup; `BaseAction` owns validation
and costs; `UsableItem` carries action templates through inventory and floor
object discovery; factories create ordinary actors and scenes; and discovery,
indexed execution, event completion, condition cleanup, inventory state, and
action costs keep the extension inside the existing engine contracts.

Chapter 20 now also includes `Content Extension Authoring Guide` before the
code surfaces. The guide gives a concrete content-pack sequence: name the
module, model lasting state as a condition, model player intent as an action,
package portable use as a usable item, attach content to actors, compose a
teaching scene, and verify discovery plus cleanup through normal engine
surfaces.

The book-example guard now enforces that Chapter 20 presents this extension
contract and authoring guide before `Code Surfaces In This Chapter` and before
the first executable example.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `188 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Chapter 21 Spell-Feature Contract

Chapter 21 now teaches spell and feature extensions as a feature-granted spell
contract before introducing code surfaces or examples. The expanded `The
Spell-Feature Contract` section explains the seven questions every
spell-feature extension answers:

- Where the spell pack lives.
- What lasting state the spell creates.
- What the castable choice is.
- Who grants the spell.
- Who can be targeted.
- How the cast resolves.
- How the design can be reused.

The section presents Aegis Spark as one complete feature-granted spell path:
the module exposes an effect condition, spell action, feature owner, actor
factory, and scene factory; `AegisSparkEffect` owns the Armor Class modifier and
cleanup; `AegisSpark` defines spell level, school, target type, range,
validation, and application; `AegisTrainingFeature` registers and unregisters
the template; discovery exposes self-or-ally target rows; and indexed execution
creates a `SpellEvent`, applies the effect, spends the action, and publishes
completion state.

Chapter 21 now also includes `Spell-Feature Authoring Guide` before the code
surfaces. The guide gives a concrete learned-magic sequence: name the
spell-feature pack, model lingering spell state, model the castable spell,
model the training owner, define legal targets through discovery, resolve the
cast through spell execution, and compose trained scenes.

The book-example guard now enforces that Chapter 21 presents this
spell-feature contract and authoring guide before `Code Surfaces In This
Chapter` and before the first executable example.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `189 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Chapter 22 Scenario Package Contract

Chapter 22 now teaches playable scenario packages as ready-to-run game modes
before introducing code surfaces or examples. The expanded `The Scenario
Package Contract` section explains the seven questions every playable-scenario
rule answers:

- Where the package lives.
- What world state is prepared.
- Which actors enter play.
- Who controls those actors.
- How the scene starts.
- How input handoff works.
- How results and endings resolve.

The section presents Gatehouse as one complete playable bundle: the module
exposes the scenario return bundle, controllers, reset routine, scene factory,
and utilities; the reset routine clears registries, events, encounters,
controllers, and map state; the scene factory creates actors, factions,
controllers, initiative order, and an active encounter; `advance_until_player()`
runs automated turns to the input boundary; and `execute_action()`, combat logs,
death checks, and faction survival resolve the scene.

Chapter 22 now also includes `Scenario Package Authoring Guide` before the
code surfaces. The guide gives a concrete ready-to-run room sequence: name the
scenario package, reset into the scenario space, create the actor cast, assign
controller ownership, start the encounter, advance to input, execute selected
intent, and end by scene state.

The book-example guard now enforces that Chapter 22 presents this scenario
package contract and authoring guide before `Code Surfaces In This Chapter`
and before the first executable example.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `190 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Chapter 23 Arena Mode Contract

Chapter 23 now teaches the standard arena as a runnable game-mode contract
before introducing code surfaces or examples. The expanded `The Arena Mode
Contract` section explains the seven questions every arena-mode rule answers:

- What mode is being started.
- Which arena space is built.
- Which hero kit enters play.
- Which opposing side enters play.
- Who controls each side.
- How the mode becomes live.
- What client state proves it works.

The section presents the standard arena as one complete product recipe:
`setup_arena_combat()` chooses the mode shape, selected hero class, opposing
side, and control mode; the standard arena builder creates grid, terrain,
walls, a door, lights, floor objects, hazards, and spawn positions; the hero
kit selection creates fighter, sorcerer, or barbarian content; skeleton
factories create the monster side; human and PvP modes assign controllers; and
the start/session/status/state/action routes expose the live arena to clients.

Chapter 23 now also includes `Arena Mode Authoring Guide` before the code
surfaces. The guide gives a concrete shipped-mode sequence: build the arena
space, select the hero kit, compose the opposing side, choose the control mode,
start the live loop, let the player claim the hero, publish playable state, and
reuse the product recipe for future modes.

The book-example guard now enforces that Chapter 23 presents this arena-mode
contract and authoring guide before `Code Surfaces In This Chapter` and before
the first executable example.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `191 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Chapter 24 Controller Turn Contract

Chapter 24 now teaches built-in controllers as turn-ownership contracts before
introducing code surfaces or examples. The expanded `The Controller Turn
Contract` section explains the eight questions every controller rule answers:

- Which actor is active.
- Who owns the decision.
- What information reaches the controller.
- When the game waits.
- What automation can choose.
- How an automated pass resolves.
- How tactical AI acts.
- How an agent runner takes over.

The section presents controllers as one decision-routing layer over the same
encounter engine: the encounter owns initiative order, round state, turn state,
action execution, combat logs, death checks, and handoff; `controller_type`
selects the decision source; `TurnContext` carries budgets and visible actors;
human and Codex controllers return waiting states; automated controllers choose
ordinary `BaseAction` instances; pass-style controllers close the turn
boundary; `MeleeAIController` chooses attack or movement from normal action
discovery; and `AIAgentController` delegates one turn to a bound runner.

Chapter 24 now also includes `Controller Authoring Guide` before the code
surfaces. The guide gives a concrete turn-policy sequence: identify the active
actor owner, provide turn context, use outside-input controllers for players,
use pass controllers for passive actors, use built-in AI for simple tactics,
use agent controllers for full-turn delegation, and keep execution inside the
encounter.

The book-example guard now enforces that Chapter 24 presents this controller
turn contract and authoring guide before `Code Surfaces In This Chapter` and
before the first executable example.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `192 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Chapter 25 Live Replication Contract

Chapter 25 now teaches live replication as a resumable client-delivery
contract before introducing code surfaces or examples. The expanded `The Live
Replication Contract` section explains the eight questions every
live-replication rule answers:

- What histories exist.
- Which cursors describe them.
- What a new stream receives.
- How reconnect catches up.
- How live changes are delivered.
- How event and combat-log order is preserved.
- How quiet streams stay aligned.
- What protects server memory.

The section presents replication as one delivery layer over the engine's
published histories: `EventQueue` records precise engine events; the active
`Encounter` records combat-log narration; `make_stream_id()` joins event and
combat-log cursors; `/events/subscribe` starts with sync and serves replay,
live, session, heartbeat, and eviction frames; `DndEventStream` listens to
event and combat-log callbacks; combat-log payloads tied to unfinished
lineages wait for completion; heartbeat frames carry current cursors during
idle periods; and bounded subscriptions evict slow readers with a structured
reason.

Chapter 25 now also includes a `Live Replication Authoring Guide` before the
code-surface table. The guide gives the build sequence for event history,
combat-log history, stream IDs, sync frames, replay, live fan-out, heartbeat
frames, and bounded subscriber queues, then summarizes the live-client work
pattern as persisting records, exposing cursor pairs, replaying missed records,
publishing new records, sending quiet-interval heartbeats, and bounding every
subscriber queue.

The book-example guard now enforces that Chapter 25 presents this live
replication contract and authoring guide before `Code Surfaces In This
Chapter` and before the first executable example.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `193 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Chapter 26 Agent Tactical Contract

Chapter 26 now teaches the agent tactical interface as a structured
decision-surface contract before introducing code surfaces or examples. The
expanded `The Agent Tactical Contract` section explains the eight questions
every agent-interface rule answers:

- Who is deciding.
- What the actor can perceive.
- What resources remain.
- Which choices are legal.
- How targets are selected.
- How combat is scored.
- How intent executes.
- How an agent owns a turn.

The section presents agents as tactical clients over the same game rules:
`LocalGameInterface.get_tactical_state()` reads the controlled actor by UUID;
`TacticalState` carries self state, visible enemies, visible allies, action
economy, resources, threat state, and concentration state; action discovery
becomes grouped `ActionOption` lists; `TargetOption` preserves engine target
indexes and target/path/combat data; `AttackData`, `SpellData`, and expected
value functions expose combat scoring; `LocalGameInterface.execute()` sends
entity UUID, template name, target index, extra targets, and path preference
through indexed engine execution; and `BaseAgent.run_turn()` reads one state
before calling `take_turn()`.

Chapter 26 now also includes a `Tactical Interface Authoring Guide` before the
code-surface table. The guide gives the build sequence for controlled actor
resolution, subjective board serialization, spendable resources, legal choice
rows, target indexes, combat math, indexed execution, and reusable agent turn
ownership, then summarizes the agent-turn work pattern as reading the active
actor, publishing the actor's subjective view, keeping discovered rows
executable, scoring choices, routing intent through the engine, and refreshing
state after consequences resolve.

The book-example guard now enforces that Chapter 26 presents this agent
tactical contract and authoring guide before `Code Surfaces In This Chapter`
and before the first executable example.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `194 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Chapter 27 Agent Decision Contract

Chapter 27 now teaches agent decision patterns as repeatable turn-behavior
contracts before introducing code surfaces or examples. The expanded `The
Agent Decision Contract` section explains the eight questions every
agent-decision rule answers:

- What state is being considered.
- How priorities are expressed.
- How a tree mutates the game.
- How a reusable tactic is packaged.
- How a tactic can replan.
- How options are ranked.
- How a utility agent plays.
- What keeps behavior inside the rules.

The section presents decision patterns as reusable play vocabulary over the
agent tactical interface: behavior trees use `Selector`, `Sequence`,
`Condition`, and `BTAction` nodes; `BTAction` executes through `GameInterface`
and refreshes `BTContext.state`; composites such as `MoveAndAttack` package
multi-step movement-refresh-attack tactics; `detect_interrupts()` compares
before state, action result, and after state for important tactical changes;
`UtilityAI` ranks affordable action-target pairs with weighted scorers; and
`UtilityAgent` repeatedly refreshes state, executes the best positive-scoring
option, and stops inside a bounded loop.

Chapter 27 now also includes a `Decision Pattern Authoring Guide` before the
code-surface table. The guide gives the build sequence for tactical-state
input, ordered priorities, behavior-tree action mutations, named tactics,
consequence-aware replanning, utility scoring, bounded agent loops, and
discovered-row execution, then summarizes the authored-behavior work pattern
as reading a tactical snapshot, choosing a decision style, keeping mutations
inside interface actions, refreshing after consequences, comparing choices
with explicit scores, and executing only discovered rows.

The book-example guard now enforces that Chapter 27 presents this agent
decision contract and authoring guide before `Code Surfaces In This Chapter`
and before the first executable example.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `195 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Whole-Manual Public Framing Audit

A whole-manual audit found remaining public table rows that described local
example symbols as being `Defined in this chapter's Imports & Scene panels`.
Those rows now use the forward-facing source label `Chapter-local example code`
across the current manual set, so source tables describe where the reader gets
the symbol without centering the documentation container itself.

The same audit also found a few remaining negation-framed prose sentences. The
manual now phrases those as positive contracts:

- Event phases are promises about what the engine can do with a record.
- Monster presets enter the ordinary actor runtime.
- The API is the client-facing view over the engine.
- The arena is a game-mode recipe over existing runtime contracts.
- Agents are turn owners inside the engine rules.
- Agent decision patterns stay attached to discovered choices and the ordinary
  execution path.

The public-snippet guard now forbids the old source-table panel phrase and the
targeted negation frames that were removed during this audit.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `195 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Stricter public hygiene scan passed, including the new forbidden phrases.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Completion-Evidence Audit Pass

The completion audit re-derived the active manual requirements and inspected
the current webbook state instead of relying on previous checkpoints.

Evidence collected:

- The current manual has 28 MDX chapters, from orientation through agent
  decision patterns.
- Non-orientation chapters all include `What This Means In Play`,
  `Code Surfaces In This Chapter`, `What Comes Next`, at least one executable
  example block, and a local `Imports & Scene` disclosure.
- Chapters 05-27 all include a contract section before code surfaces and
  before executable examples.
- The current manual contains 151 public example blocks and 368 enrolled
  `book-example` Python fences.
- Public source tables no longer use either the singular or plural
  `Defined in this chapter's Imports & Scene panel(s)` wording; those names now
  use `Chapter-local example code`.
- The public-snippet guard now forbids the singular/plural stale source-table
  wording and the targeted negation-framed phrases removed during the audit.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `195 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Source Rule Touchpoints And Exact Snippet Gate

The manual now makes the D&D-facing rule context visible at the chapter header
level without introducing a second runtime ruleset. Each chapter declares a
`rules` frontmatter list that names the source-rule ideas taught in that
chapter, and `ManualChapter.astro` renders those values as `Source Rule
Touchpoints` above the chapter body.

The public-snippet gate also gained explicit checks for this requirement:

- Every public MDX chapter must declare non-empty source-rule touchpoints.
- The chapter layout must render the declared touchpoints.
- The existing executable-snippet path continues to assemble the exact MDX
  `book-example` fences, including the collapsed `Imports & Scene` code, and
  execute that source directly.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `197 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Continuing Tutorial Scene Disclosure

The chapter 02 actor-anatomy walkthrough intentionally uses one live actor
scene across several public example blocks. That is a valid tutorial shape, but
the previous component label made every example look like it should contain a
fresh imports panel.

The webbook now distinguishes those cases:

- `ExampleBlock` supports a `mode="continuing"` display mode.
- Standalone examples show the flow `Imports`, `Resolve`, `Assert`.
- Continuing examples show the flow `Continuing Scene`, `Inspect`, `Assert`.
- Chapter 02 marks the later Aria examples as continuing scenes and introduces
  each continuation with nearby reader-facing prose.
- The public-snippet gate now fails any ExampleBlock without a local
  `Imports & Scene` panel unless it is explicitly declared as continuing and
  introduced by nearby prose.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `198 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Bottom-Up D&D Translation For Identity And Actors

The early runtime foundation now frontloads source-rule translation before
showing code surfaces. This keeps the manual from beginning with implementation
objects alone and makes the first technical chapters explain what D&D-facing
idea the engine is modeling.

Changes made:

- Chapter 01 now includes `How D&D References Become Runtime Identity`, mapping
  acting creatures, targets, source entities, target entities, condition
  cleanup, and grid-cell references to UUID-backed runtime identity.
- Chapter 02 now includes `How A D&D Creature Becomes An Entity`, mapping
  creature-sheet ideas such as ability scores, skills, saves, HP, resources,
  equipment, senses, spellcasting, and faction into the entity-owned block
  shape.
- The public-snippet gate now asserts that both sections appear before
  `Code Surfaces In This Chapter` and before the first executable example.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `200 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: All Chapter-Local Tutorial Code Is Source-Listed

The exact-snippet audit now covers local tutorial definitions inside collapsed
`Imports & Scene` panels, not only local names that are visibly called later.
This closes a remaining discoverability gap where tutorial scene builders and
combat controls could exist in executable setup without a public source-table
entry.

Changes made:

- Chapter 18 now source-lists `create_session_and_join_hero`,
  `make_melee_attack_auto_hit`, and `clear_melee_attack_modifier` alongside
  the other chapter-local API tutorial code.
- Chapter 19 now source-lists `reset_map_authoring_state` alongside the other
  chapter-local map-authoring tutorial code.
- The public book-example gate now extracts every local `class` and `def`
  declared in enrolled import panels and requires each name to appear in that
  chapter's `Code Surfaces In This Chapter` section.

Verification completed:

- A focused audit confirmed all import-panel local definitions are listed in
  source tables.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `201 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Chapter Maps Across The Foundation Path

The early manual chapters now match the later webbook structure: every
technical chapter frames the learning path before listing code surfaces and
before showing executable examples. This makes the book read more like a
bottom-up manual and less like isolated code examples.

Changes made:

- Added `Chapter Map` sections to chapters 01-10.
- Each new map connects a reader-facing game or runtime question to the engine
  surface that chapter will teach.
- The public book-example gate now requires every technical chapter to flow
  from `What This Means In Play` to `Chapter Map` to `Code Surfaces In This
  Chapter` to executable examples.
- The gate also requires each chapter map to contain a real implementation-side
  table.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `202 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Sequential What Comes Next Bridges

The manual now has explicit sequential bridges between chapters. Each
technical chapter's `What Comes Next` section names the actual next chapter
title and explains why the next layer follows from the current one.

Changes made:

- Updated chapters 01-26 so their closing bridge names the next chapter title
  exactly.
- Corrected the chapter 08 bridge, which previously pointed to perception even
  though the next chapter is `Action Discovery And Costs`.
- Preserved the final chapter as the current manual arc close.
- The public book-example gate now verifies that each technical chapter names
  the actual next title in source order, and that the final chapter closes the
  current manual arc.

Verification completed:

- A focused bridge audit confirmed every chapter 01-26 names the actual next
  title and chapter 27 closes the current manual arc.
- A focused inline-code audit confirmed no `What Comes Next` title is split
  across Markdown lines.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `202 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Import Panels Explain Their Local Definitions

The collapsed `Imports & Scene` panels now explain every local class/function
they define before the code fence. This tightens the tutorial guarantee: a
reader who opens setup code sees not only import paths and executable setup,
but also the purpose of each local scene routine or class.

Changes made:

- Chapter 18 panels now name and explain `ApiClient`,
  `reset_client_api_state`, `create_api_pair`, `start_api_game`,
  `create_session_and_join_hero`, `create_joined_client_game`,
  `attack_target_index`, `make_melee_attack_auto_hit`,
  `clear_melee_attack_modifier`, and `execute_manual_attack` where those names
  are defined.
- Chapter 19 map-authoring panels now name and explain `ApiClient` and
  `reset_map_authoring_state` where those names are defined.
- The public book-example gate now requires every local `class` or `def`
  declared in an enrolled import panel to be named in that panel's prose before
  the first code fence.

Verification completed:

- A focused import-panel audit confirmed all local definitions are named in
  panel prose.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `203 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Post-Example Capability Summaries

Every technical chapter now closes its executable examples with a concrete
reader capability summary before moving to the next-chapter bridge. This helps
the webbook read as a cumulative manual: the examples do not end as isolated
assertions, they end by naming what the reader can now build, inspect, or
extend.

Changes made:

- Added `What You Can Do Now` sections to chapters 01-27.
- Each section appears after the final `ExampleBlock` and before `What Comes
  Next`.
- Each section introduces the capabilities with `After this chapter you can:`
  and lists at least three concrete outcomes.
- The public book-example gate now enforces this placement and minimum
  capability-list shape.

Verification completed:

- A focused structural audit confirmed all 27 technical chapters have the
  capability section in the correct location with at least three bullets.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `204 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Table And Code Readability Guard

The webbook layout already had explicit table, code, preformatted block, and
`Imports & Scene` panel styling. This pass added a small shared-layout
improvement and a regression guard so those reader-facing treatments do not
silently disappear.

Changes made:

- Inline code inside table headers and table cells now wraps with
  `overflow-wrap: anywhere`, which protects wide source tables that contain
  long module names, symbols, and route-like code spans.
- The public book-example gate now asserts that the manual chapter layout keeps
  table formatting, striped table rows, horizontal overflow for narrow screens,
  inline code styling, preformatted code styling, import-panel styling, and
  open/closed import-panel markers.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `205 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Chapter-Local Source Labels Instead Of Panel Meta

The public source tables no longer describe local tutorial symbols as being
defined inside the `Imports & Scene` panel. The panel is the display mechanism;
the source table should tell the reader whether a symbol comes from an engine
module, API route, or chapter-local example code.

Changes made:

- Chapter 18 changed `ApiClient` from `Defined in the Imports & Scene panel` to
  `Chapter-local example code`.
- Chapter 19 changed `ApiClient` from `Defined in the Imports & Scene panel` to
  `Chapter-local example code`.
- The public hygiene gate now forbids both `Defined in the Imports & Scene
  panel` and `Defined in this chapter's Imports & Scene panel(s)`.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `200 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Running Game Product Hinge

The Running The Game part now has a stronger transition from engine mechanics
to playable product behavior. Chapter 17 is the first chapter in that part and
now explicitly explains how previously introduced engine pieces become a live
encounter loop.

Changes made:

- Chapter 17 now includes `How Engine Pieces Become A Running Game` before the
  running-game contract and code surfaces.
- The new section maps live entities, registered actions/spells/items/monster
  abilities, values, dice, conditions, senses, events, combat logs,
  controllers, factions, and HP state into their running-game roles.
- The public-snippet gate now asserts that this product hinge appears before
  the chapter contract, source table, and executable examples.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `200 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Example Deep Links

The public example blocks now behave like stable book sections, not anonymous
code panels. Each visible example ID links to its own section anchor, and the
book-example gate verifies that those anchors remain unique across the manual.

Changes made:

- `ExampleBlock.astro` derives a stable lowercase anchor from each example ID.
- The example section uses that anchor as its DOM id.
- The visible example ID in the block header is now a self-link to that anchor.
- The book-example gate asserts all 151 public ExampleBlock IDs are unique.
- The same gate asserts the component keeps the self-link behavior.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `206 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Controller Pass Language

Chapter 24 now presents controller outcomes as positive runtime states instead
of absence-based behavior. External-input controllers are described as reserving
the decision for a human or Codex owner, pass controllers are described as
explicit pass participants, and melee AI uses an empty-target-list pass signal.

Changes made:

- Reworded the controller contract table so waiting, automated action choice,
  tactical pursuit, and pass behavior are all named as explicit controller
  outcomes.
- Reworded the controller source table so `MeleeAIController` chooses attack,
  movement, or the pass signal.
- Renamed the public example heading from `Pass When There Is No Visible Enemy`
  to `Pass With An Empty Target List`.
- Replaced absence-framed prose such as `no action`, `no visible enemy`,
  `no-op`, and `no autonomous engine action` with waiting/pass vocabulary.
- Added a chapter-specific regression guard that strips code fences and checks
  the public prose keeps this positive pass language.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `207 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Chapter 24 positive pass wording scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Running-Game Authority Language

The running-game chapters now present encounter ending, client action
submission, and quiet stream synchronization as owned engine contracts instead
of negation-framed behavior.

Changes made:

- Chapter 17 now says the engine owns the dungeon-master decision that closes a
  videogame combat scene, with faction survival as the encounter policy.
- Chapter 17 now describes `PassController` as an explicit-pass controller
  rather than a no-action controller.
- Chapter 18 now says the engine authors legal action rows and stable target
  indices, while clients render and submit those engine-provided choices.
- Chapter 18 now describes `attack_target_index()` as preserving the
  engine-provided target index.
- Chapter 25 now describes heartbeats as quiet-interval cursor synchronization.
- Chapter 25 now describes bounded eviction as a queue-capacity rule.
- Added focused guards for Chapters 17, 18, and 25 that strip code fences and
  reject the old negation-heavy public prose.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `210 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Running-game positive framing scans passed.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: D&D Rule Bridges For Items And Perception

Chapters 11 and 12 now translate their D&D-facing concepts into engine state
before the chapter map and runtime contract. This makes the manual read from
game language into implementation, instead of jumping straight from play prose
to machinery.

Changes made:

- Chapter 11 now includes `How D&D Gear Becomes Item State` before the chapter
  map.
- The gear bridge maps carried objects, weapons, shields, armor, consumables,
  environment objects, and videogame loadouts to item ownership, equipment
  slots, equip hooks, use actions, map objects, and melee/ranged loadout state.
- Chapter 12 now includes `How D&D Senses Become Observer State` before the
  chapter map.
- The perception bridge maps line of sight, light, hidden creatures,
  invisibility, memory, and legal UI choices to field of view, effective light,
  stealth DC, special senses, `senses.seen`, and observer-local target/path
  caches.
- The public book-example gate now asserts both bridges exist in the correct
  order and preserve the key D&D-to-engine translations.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `210 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: D&D Reaction Timing Bridge

Chapter 06 now translates D&D reaction timing language into engine event
responses before introducing the implementation surfaces. This keeps the
chapter anchored in gameplay timing before it names handlers, result events,
and spatial handlers.

Changes made:

- Added `How D&D Timed Rules Become Event Responses` before `The Three Reaction
  Surfaces`.
- The new bridge maps reaction moments, wards, roll-changing features, hazards,
  opportunity-style movement reactions, and forced displacement to
  `EventHandler`, result events, `SpatialHandler`, `STEP_MOVEMENT`, and
  `FORCED_MOVEMENT`.
- The voluntary/forced movement split is stated positively: paid movement steps
  use `STEP_MOVEMENT`, while shove/push/pull movement uses `FORCED_MOVEMENT`
  and still updates spatial state.
- The public book-example gate now asserts the bridge order and the key
  D&D-to-engine timing translations.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `210 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: D&D Spellcasting Bridge

Chapter 13 now translates D&D spellcasting vocabulary into runtime magic state
before the chapter map and spellcasting contract. This keeps cantrips, slots,
spell attacks, save DCs, spell events, and concentration anchored in game
language before the manual names engine classes and examples.

Changes made:

- Added `How D&D Spellcasting Becomes Runtime Magic` before the chapter map.
- The bridge maps known spells, cantrips, leveled spell slots, casting numbers,
  spell resolution, and concentration spells to action templates,
  spell-action rows, `ActionEconomy` slot values, `SpellcastingBlock`
  composition, `SpellEvent`/child events, and the caster-owned
  `Concentrating` condition.
- The public book-example gate now asserts the section order and the key
  D&D-to-engine spellcasting translations.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `210 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: D&D Spell Family Bridge

Chapter 14 now translates D&D spell names into runtime spell families before
the chapter map and family contract. This keeps named magic grounded in player
fantasy while making the videogame behavior explicit before catalog surfaces,
spell classes, and executable examples appear.

Changes made:

- Added `How D&D Spell Names Become Runtime Families` before the chapter map.
- The bridge maps ranged spell attacks, saving throw spells, auto-hit spells,
  healing/protection, teleportation and zone magic, lasting conditions, and
  catalog names to the engine families that resolve them.
- The public book-example gate now asserts the section order and the key
  D&D-to-engine spell-family translations.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `210 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: D&D Character Feature Bridge

Chapter 15 now translates D&D character choices into runtime feature state
before the chapter map and character-content contract. This keeps class,
subclass, feat, rest, and feature identity visible before factories, resources,
actions, handlers, and cleanup rules appear.

Changes made:

- Added `How D&D Character Choices Become Runtime State` before the chapter
  map.
- The bridge maps class level, limited-use features, active feature buttons,
  passive modifiers, event timing, temporary modes, and rest recharge to the
  engine surfaces that implement them.
- The public book-example gate now asserts the section order and the key
  D&D-to-engine character-feature translations.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `210 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: D&D Monster Stat-Block Bridge

Chapter 16 now translates D&D monster stat-block vocabulary into runtime actor
state before the chapter map and preset-actor contract. This keeps creature
identity, stat numbers, defenses, actions, gear, encounter roles, and encounter
entry visible before factory and preset implementation surfaces appear.

Changes made:

- Added `How D&D Monster Stat Blocks Become Runtime Actors` before the chapter
  map.
- The bridge maps identity, core stat numbers, senses and defenses, attacks and
  monster actions, gear and loot, combat roles, and encounter participation to
  the engine surfaces that implement them.
- The public book-example gate now asserts the section order and the key
  D&D-to-engine monster/preset translations.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `210 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: D&D Encounter-Time Bridge

Chapter 17 now translates D&D combat time into a running encounter before the
chapter map, product-loop explanation, and running-game contract. This keeps
initiative, rounds, turns, active choices, action resolution, ongoing effects,
combat logs, and encounter ending visible before implementation surfaces
appear.

Changes made:

- Added `How D&D Combat Becomes A Running Encounter` before the chapter map.
- The bridge maps participating creatures, initiative order, rounds and turns,
  controller choices, action/event resolution, turn-boundary refresh, combat
  logs, and faction-survival ending to the encounter runtime.
- The public book-example gate now asserts the section order and the key
  D&D-to-engine encounter-time translations.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `210 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: D&D Table-To-Client Session Bridge

Chapter 18 now translates the shared D&D table view into a client session and
API contract before the chapter map and client contract. This keeps player
identity, actor ownership, visible board state, turn ownership, legal choices,
action execution, shared history, and content menus visible before endpoint and
payload surfaces appear.

Changes made:

- Added `How A D&D Table Becomes A Client Session` before the chapter map.
- The bridge maps joining the game, controlling actors, reading board state,
  identifying the active owner, choosing legal actions, executing the selected
  action, following event/combat-log history, and loading spell catalog metadata
  to the API/runtime contract.
- The public book-example gate now asserts the section order and the key
  D&D-to-client session translations.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `210 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: D&D Place-To-Authoring Document Bridge

Chapter 19 now translates D&D places into map-editor authoring documents before
the chapter map and authoring contract. This keeps terrain, props, room shape,
movement and visibility rules, objective layers, saved maps, and later playable
handoff visible before editor routes and payload models appear.

Changes made:

- Added `How D&D Places Become Authoring Documents` before the chapter map.
- The bridge maps palette choices, scratch/preset map creation, terrain and
  border painting, object placement, objective layer inspection, save/load
  documents, and playable handoff to the map-editor API workflow.
- The public book-example gate now asserts the section order and the key
  D&D-to-authoring translations.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `210 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: D&D Content-Idea Extension Bridge

Chapter 20 now translates D&D/content ideas into extension surfaces before the
chapter map and extension contract. This keeps named effects, player intent,
portable tools, reusable actors, training scenes, discovery, and cleanup
visible before module and code-surface details appear.

Changes made:

- Added `How D&D Content Ideas Become Engine Extensions` before the chapter
  map.
- The bridge maps named effects, chosen actions, usable items, actor factories,
  scene factories, controller/client discovery, and ending effects to the
  extension runtime.
- The public book-example gate now asserts the section order and the key
  D&D-to-extension translations.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `210 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: D&D Feature-Magic Extension Bridge

Chapter 21 now translates feature-granted magic into spell-extension surfaces
before the chapter map and spell-feature contract. This keeps learned special
magic, spell-menu discovery, self-or-ally targeting, spell resolution,
lingering ward state, feature cleanup, and reusable scenes visible before
module and code-surface details appear.

Changes made:

- Added `How D&D Feature Magic Becomes A Spell Extension` before the chapter
  map.
- The bridge maps feature-learned spells, spell action rows, target discovery,
  indexed casting, ward effects, feature removal, and actor/scene reuse to the
  Aegis Spark extension runtime.
- The public book-example gate now asserts the section order and the key
  D&D-to-spell-feature translations.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `210 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: D&D Adventure-Room Scenario Bridge

Chapter 22 now translates D&D adventure-room setup into scenario package
behavior before the chapter map and scenario package contract. This keeps map
state, actors, ownership, initiative, automation handoff, selected actions,
combat logs, and victory/defeat visible before module and code-surface details
appear.

Changes made:

- Added `How D&D Adventure Rooms Become Scenario Packages` before the chapter
  map.
- The bridge maps authored rooms, heroes and enemies, controller ownership,
  initiative start, automated turn advancement, indexed action execution,
  combat-log history, and faction-survival ending to the Gatehouse scenario
  package.
- The public book-example gate now asserts the section order and the key
  D&D-to-scenario package translations.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `210 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: D&D Arena-Mode Bridge

Chapter 23 now translates D&D arena play into a standard game mode before the
chapter map and arena-mode contract. This keeps battlefield format, hero-kit
selection, monster role mix, control mode, session join, live client payloads,
and reusable mode assembly visible before route and code-surface details
appear.

Changes made:

- Added `How D&D Arena Play Becomes A Game Mode` before the chapter map.
- The bridge maps battlefield setup, class-selected hero kits, skeleton monster
  roles, human/AI/Codex control modes, `/simulation/start-human`, session join,
  live board payloads, and reuse patterns to the standard arena runtime.
- The public book-example gate now asserts the section order and the key
  D&D-to-arena-mode translations.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `210 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Exact Public Snippet Contract

The webbook now treats displayed Python snippets as executable manual surface
area. Every strict manual chapter marks each public `book-example` fence as
either `part="imports"` or `part="body"`, and the book-example gate verifies
that those roles match the rendered page structure.

Changes made:

- Standardized all public manual Python `book-example` fences so import-scene
  code and body code are explicit across Chapters 01 through 27.
- Updated the opening orientation chapter to describe each substantial example
  as one runnable program with a collapsed `Imports & Scene` disclosure and a
  body read together in page order.
- Updated the example component flow labels to `Imports & Scene`, `Run`, and
  `Assert`.
- Added public book-example tests that fail when an executable fence omits its
  role, when an import-scene/body role disagrees with its page location, or
  when an executed example does not begin with imports before body code.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `212 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: D&D Controller Turn-Ownership Bridge

Chapter 24 now translates D&D turn ownership into controller behavior before
the chapter map and controller-turn contract. This keeps initiative ownership,
decision ownership, turn context, human waiting states, explicit passes,
automated actions, agent delegation, and action/event resolution visible before
the controller catalogue appears.

Changes made:

- Added `How D&D Turn Ownership Becomes Controller Choice` before the chapter
  map.
- The bridge maps active creatures, decision owners, chooser context,
  human/Codex waiting, explicit pass turns, built-in automated choices,
  tactical agent runners, and encounter advancement to controller behavior.
- The public book-example gate now asserts the section order and the key
  D&D-to-controller translations.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `212 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: D&D Consequence Stream Bridge

Chapter 25 now translates resolved D&D play consequences into live replication
behavior before the chapter map and live-replication contract. This keeps
shared table state, exact event history, combat-log narration, sync frames,
cursor replay, live fan-out, heartbeat frames, and bounded delivery visible
before stream implementation surfaces appear.

Changes made:

- Added `How D&D Consequences Become Live Streams` before the chapter map.
- The bridge maps initiative changes, movement, attacks, casting, object use,
  narrated outcomes, client joins, reconnects, live viewers, quiet intervals,
  and subscriber backpressure to stream behavior.
- The public book-example gate now asserts the section order and the key
  D&D-to-live-stream translations.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `212 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: D&D Tactical-State Bridge

Chapter 26 now translates a live D&D turn into tactical state before the
chapter map and agent tactical contract. This keeps the acting creature,
subjective perception, remaining resources, legal action rows, target rows,
combat probability, execution, and agent turn ownership visible before tactical
interface implementation surfaces appear.

Changes made:

- Added `How A D&D Turn Becomes Tactical State` before the chapter map.
- The bridge maps controlled creatures, visible enemies and allies, action
  economy, movement, spell slots, grouped action options, target options,
  expected-value math, interface execution, and `BaseAgent.run_turn()` to
  tactical interface behavior.
- The public book-example gate now asserts the section order and the key
  D&D-to-tactical-interface translations.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `212 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: D&D Tactical-Judgment Bridge

Chapter 27 now translates D&D tactical judgment into agent behavior patterns
before the chapter map and agent decision contract. This keeps ordered
priorities, action leaves, named tactics, board-change reactions,
action-target ranking, focused pressure, complete automated turns, and engine
execution visible before decision-pattern implementation surfaces appear.

Changes made:

- Added `How D&D Tactical Judgment Becomes Agent Behavior` before the chapter
  map.
- The bridge maps behavior trees, `BTAction`, `MoveAndAttack`,
  `detect_interrupts()`, `UtilityAI`, `DamageScorer`, `FocusFireScorer`,
  `UtilityAgent`, and `LocalGameInterface` to tactical judgment in play.
- The public book-example gate now asserts the section order and the key
  D&D-to-agent-decision translations.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `212 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Whole-Book Forward-Framing Audit

The manual received a structure and hygiene audit against the current full-book
objective. The audit confirmed that every non-orientation chapter now has a
player/designer framing section, a D&D/game-facing `How ...` bridge, a chapter
map, code surfaces before examples, executable public examples, capability
summary, and next-step bridge.

Changes made:

- Rewrote the remaining negation-framed perception sentence in Chapter 12 from
  global-visibility negation into positive observer-owned game truth.
- Added a targeted public hygiene guard for the removed
  `not a single global visibility flag` wording.
- Re-ran the chapter-structure inventory and confirmed Chapters 01 through 27
  each expose at least one D&D/game-facing `How ...` bridge before
  implementation surfaces.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `212 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Scene Constructor Explanation

The orientation chapter now explains why later examples import named scene
constructors. This addresses the remaining reader-facing concern that setup
imports could feel like unexplained magic in product and agent chapters.

Changes made:

- Expanded `How This Manual Teaches Code` to describe `create_gatehouse_scenario()`,
  `create_stream_scene()`, and `create_agent_scene()` as public tutorial scene
  surfaces.
- The new prose explains that scene constructors create ordinary entities,
  maps, encounters, sessions, streams, controllers, and agents, and that readers
  can apply the same pattern in their own scenario modules.
- The public book-example gate now asserts that this scene-constructor
  explanation remains in the orientation chapter.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `212 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Landing Page Builder Outcomes

The landing page now connects the reading path to concrete developer outcomes.
This strengthens the full-book promise that the manual prepares a reader to
extend the engine and ship game content, rather than only browsing subsystem
chapters.

Changes made:

- Added a `Builder Outcomes` section to the landing page.
- The new section names four end-to-end outcomes: authoring a new rule,
  assembling a playable scene, exposing the game to clients, and automating
  tactical turns.
- The public book-example gate now asserts that the landing page keeps this
  builder-outcomes framing.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `212 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Orientation Build Path

The orientation chapter now gives readers a full build path from foundational
runtime concepts to playable content, client surfaces, and automated tactical
turns. This makes the manual itself explain how the chapters add up to building
with NeuroDragon.

Changes made:

- Added `The Build Path` to the orientation chapter.
- The new table maps developer moves to manual chapters and concrete outcomes:
  naming live objects, turning timing into runtime behavior, offering playable
  choices, authoring game content, assembling a game mode, and automating
  tactical play.
- The public book-example gate now asserts that the orientation chapter keeps
  this build-path framing.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `212 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Tutorial Observation Language

The public manual now describes example results as engine observations,
outcomes, state reads, and payloads rather than test-suite assertions. The
examples still execute exact Python checks through the book-example test gate,
but the customer-facing prose now reads like a developer manual.

Changes made:

- Replaced public prose references to `assertion` and `assertions` across the
  orientation, identity, event, movement, perception, spellcasting, spell
  catalog, class factory, monster preset, encounter, and map-authoring
  chapters.
- Kept Python `assert` statements and `AssertionError` branches inside runnable
  examples where they validate behavior as normal code.
- Added a public hygiene guard that rejects prose-level `assertion` and
  `assertions` wording while allowing executable validation code.
- Strengthened the orientation gate so it preserves the scene-constructor
  language for running actions, inspecting state, and observing outcomes.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `212 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed with the new `assertion(s)` rule.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Example Frame Presentation

The public example component now presents snippets as a tutorial sequence
instead of a test sequence. The code contract remains exact: each Imports &
Scene panel and each visible body fence still joins into one executable public
snippet, but the visible webbook frame now uses product-facing language.

Changes made:

- Replaced the old example flow labels with `Imports & Scene`, `Execute`, and
  `Observe`; continuing examples now read `Continuing Scene`, `Execute`, and
  `Observe`.
- Restyled the `ExampleBlock` sequence as numbered tutorial steps instead of
  pill labels.
- Restyled collapsed Imports & Scene disclosures with an accent rail, hover
  state, focus-visible state, and clearer body spacing.
- Added `ExampleBlock.astro` to the public hygiene scan and rejected the old
  capital `Assert` flow label.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `212 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed with the `assertion(s)` and `Assert`
  wording guards.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Bottom-Up Source Links

The first three technical chapters now make their import surfaces directly
inspectable. Their Code Surfaces tables keep the module names visible and link
runtime paths to anchored GitHub source on the current branch, so readers can
move from manual prose to the implementation without note links or hidden
setup.

Changes made:

- Added branch-pinned GitHub source links to the Code Surfaces tables in
  chapters 01, 02, and 03.
- Linked the bottom-up surfaces for identity, entity construction, block
  configuration, values, and modifier classes to the relevant source lines.
- Corrected the Chapter 03 contextual modifier example to import
  `ContextualNumericalModifier` from its defining runtime module,
  `dnd.core.modifiers`.
- Added a guarded audited-chapter set requiring anchored source links for
  runtime import paths in the first three technical chapters.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py` passed with
  `213 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Dice Event Source Links

The bottom-up source-link convention now extends through dice, event lifecycle,
and reaction timing. Chapters 04, 05, and 06 show the same module names used by
their snippets, but those module names now click through to anchored source on
the current branch.

Changes made:

- Added anchored GitHub source links to the Chapter 04 Code Surfaces table for
  dice expressions, roll records, roll categories, attack outcomes,
  deterministic dice faces, value bonuses, and roll-state modifiers.
- Added anchored GitHub source links to the Chapter 05 Code Surfaces table for
  base events, phases, event types, the queue, and combat-log entries.
- Added anchored GitHub source links to the Chapter 06 Code Surfaces table for
  triggers, handlers, queue registration, d20 result replacement, spatial
  handlers, movement event surfaces, weapon slots, dice, and value bonuses.
- Expanded the audited source-link guard to chapters 04, 05, and 06, bringing
  the guarded bottom-up source-link path to chapters 01 through 06.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `213 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Runtime Foundations Ruling Roles

Chapters 02 through 05 now carry the opening chapter's ruling-loop mental model
through the first engine foundation arc. Entity anatomy, values/modifiers,
dice, and event lifecycle each state the exact question they answer for the
software dungeon master before the chapter moves into source tables and
examples.

Changes made:

- Added a Chapter 02 "Ruling Role" section that frames `Entity` as the actor
  packet opened by later rulings: identity, creature-sheet blocks, resources,
  senses, and mutable actor state.
- Added a Chapter 03 "Ruling Role" section that frames values as current-number
  explanations: base number, static rules, contextual rules, target-facing
  effects, and client-visible breakdowns.
- Added a Chapter 04 "Ruling Role" section that frames dice as the uncertainty
  step: roll type, bonus source, rolled faces, selected total, and stable roll
  identity.
- Added a Chapter 05 "Ruling Role" section that frames events as the timeline
  record: declared intent, active phase, state change, causal child effects,
  queues, callbacks, and client-readable history.
- Added a verifier that locks Chapters 02, 03, 04, and 05 to the new ruling-role
  structure before their Chapter Map, Code Surfaces, and examples.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `214 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Runtime Response Choice Ruling Roles

Chapters 06 through 09 now continue the ruling-loop spine from event records
into timed responses, ongoing state, tactical board state, and player-visible
choices. These chapters now state their software dungeon master role before
their deeper contracts, source tables, and executable examples.

Changes made:

- Added a Chapter 06 "Ruling Role" section that frames reactions as the
  response-window layer: event timing, source/target/position filters,
  processors, spatial timing, and completion boundaries.
- Added a Chapter 07 "Ruling Role" section that frames conditions as durable
  game-state memory: named state, owned artifacts, later rule visibility,
  cleanup paths, and composable identities.
- Added a Chapter 08 "Ruling Role" section that frames the world model as the
  shared board ledger: cells, terrain, borders, position indexes, spatial
  events, and movement reasons.
- Added a Chapter 09 "Ruling Role" section that frames actions as the turn-menu
  layer: available attempts, legal targets, costs, selected execution, and
  compact client commands.
- Added a verifier that locks Chapters 06, 07, 08, and 09 to the new ruling-role
  structure before Chapter Map, Code Surfaces, and executable examples.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `215 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Combat Object Awareness Ruling Roles

Chapters 10 through 12 now continue the ruling-loop spine through combat
consequences, physical object continuity, and observer-local knowledge. The
manual now connects the early choice/action layer to the systems that decide
what happened, what objects physically mean, and what the player can know.

Changes made:

- Added a Chapter 10 "Ruling Role" section that frames combat as the
  consequence pipeline: legality, decisive rolls, HP/movement/resource changes,
  reaction windows, completion events, and combat narration.
- Added a Chapter 11 "Ruling Role" section that frames equipment, inventory,
  and items as physical object continuity: location, contribution, interaction,
  loadout coherence, use state, and payload state.
- Added a Chapter 12 "Ruling Role" section that frames perception as the
  knowledge layer: visible cells, revealed actors/objects, memory, legal choice
  safety, and sensory update deltas.
- Added a verifier that locks Chapters 10, 11, and 12 to the new ruling-role
  structure before Chapter Map, Code Surfaces, and executable examples.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `216 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Magic Character Content Ruling Roles

Chapters 13 through 15 now continue the ruling-loop spine into magic and
authored character identity. The manual now explains spellcasting as magic
choice, spell families as magic effect, and class features as character
identity before diving into each chapter's existing contracts, source surfaces,
and examples.

Changes made:

- Added a Chapter 13 "Ruling Role" section that frames spellcasting as the
  magic-choice pipeline: registered spell templates, slot resources,
  spellcasting numbers, spell events, and concentration ownership.
- Added a Chapter 14 "Ruling Role" section that frames spell families as
  magic-effect patterns: fantasy intention, target/resistance shape, immediate
  state changes, lasting state, and catalog discovery.
- Added a Chapter 15 "Ruling Role" section that frames class features as
  character identity: build choices, resources, feature actions, passive rules,
  modes, rest rhythms, and feature cleanup.
- Rewrote a Chapter 15 sentence caught by the public hygiene guard so the class
  feature prose stays forward-facing instead of negation-framed.
- Added a verifier that locks Chapters 13, 14, and 15 to the new ruling-role
  structure before Chapter Map, Code Surfaces, and executable examples.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `217 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Opening Prose Ruling Loop

The manual now starts with a stronger forward-facing mental model. The
orientation chapter frames NeuroDragon as the software dungeon master for a
tactical D&D videogame, then introduces the repeated ruling loop that every
later subsystem serves. Chapter 01 now reads as the first engine layer in that
loop: stable runtime identity for actors, values, events, effects, logs,
payloads, and later cleanup.

Changes made:

- Rewrote the opening orientation paragraphs to present NeuroDragon as rules
  authority, state machine, play surface, and software dungeon master.
- Added a "The Ruling Loop" section that explains the repeated questions the
  engine answers: who is acting, what can be perceived, which choices are
  legal, what the choice costs, how uncertainty resolves, and what changed.
- Tightened "How This Manual Teaches Code" so source tables, Imports & Scene
  panels, and body snippets are explained as one reader-facing tutorial
  system.
- Updated the orientation verifier to lock the improved example-reading
  language.
- Rewrote the start of Chapter 01 so runtime identity is presented as the
  engine's first ruling requirement, not just as a registry mechanism.
- Added a "A Reference's Journey" table showing how the same UUID travels
  through controller/API requests, action validation, event declaration,
  effects, payloads, combat logs, and cleanup.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `213 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Extension Product Agent Source Links

The source-link convention now covers the remaining webbook chapters: content
extension packs, feature/spell extension packs, playable scenario packages,
standard arena game modes, built-in controllers, live replication streams,
agent tactical interfaces, and agent decision patterns. The guarded source-link
path now spans chapters 01 through 27.

Changes made:

- Added anchored GitHub source links to the Chapter 20 Code Surfaces table for
  the Field Focus condition, action, usable item factory, actor factory,
  training-scene factory, action readers, inventory reader, actor/monster
  surfaces, action timing/targeting enums, reset surfaces, and action
  discovery/execution APIs.
- Added anchored GitHub source links to the Chapter 21 Code Surfaces table for
  the Aegis Spark condition, spell action, training feature, actor factory,
  scene factory, action reader, actor surface, timing/targeting enums, reset
  surfaces, action discovery/execution APIs, and spell event type.
- Added anchored GitHub source links to the Chapter 22 Code Surfaces table for
  the Gatehouse scenario bundle, scenario controllers, scenario reset, scenario
  factory, deterministic attack modifiers, encounter lifecycle, and damage
  taxonomy.
- Added anchored GitHub source links to the Chapter 23 Code Surfaces table for
  arena setup, simulation state, encounter state, entities, loadout slots,
  standard arena routes, arena client, runtime reset, actor/item/action
  readers, and the joined human arena workflow.
- Added anchored GitHub source links to the Chapter 24 Code Surfaces table for
  human, Codex, pass, melee AI, and agent controllers; turn context; concrete
  actions; actor and monster surfaces; turn state; loadout slots; and the
  controller-catalogue training scene.
- Added anchored GitHub source links to the Chapter 25 Code Surfaces table for
  event/combat-log routes, SSE subscription route, stream bridge, event
  cursor state, typed stream payloads, bounded subscriptions, SSE frame
  formatting, stream IDs, and live-replication training routines.
- Added anchored GitHub source links to the Chapter 26 Code Surfaces table for
  the local game interface, tactical state/action/target models, probability
  and expected-value functions, base agent runner, tactical training scene,
  first-attack agent, and deterministic attack modifiers.
- Added anchored GitHub source links to the Chapter 27 Code Surfaces table for
  decision-training scenes, behavior-tree control and leaf nodes, BT runtime
  state, composite tactics, interrupt detection, local game interface,
  tactical result/entity records, example behavior-tree agent construction,
  behavior-tree leaves, utility scorers, utility selector, and utility agent.
- Expanded the audited source-link guard through chapters 20, 21, 22, 23, 24,
  25, 26, and 27, so every manual chapter with runtime examples is now part of
  the anchored-source audit.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `213 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Monsters Running Game Authoring Source Links

The source-link convention now covers monster presets, encounters,
sessions/API payloads, and map-editor authoring. Chapters 16, 17, 18, and 19
keep their public runtime names visible and link them to anchored source on the
current branch, carrying the inspectable path from authored actors into the
running videogame loop and scenario-authoring tools.

Changes made:

- Added anchored GitHub source links to the Chapter 16 Code Surfaces table for
  entity state, monster factories, skeleton role presets, monster abilities,
  loadout slots, event history, senses, reset surfaces, creature/damage
  taxonomy, monster condition traits, usable items, and spell-protection reset
  state.
- Added anchored GitHub source links to the Chapter 17 Code Surfaces table for
  encounters, encounter/turn state, combatant rows, controller context,
  controller classes, entities, event history, reset surfaces, deterministic
  combat modifiers, damage taxonomy, and monster factories.
- Added anchored GitHub source links to the Chapter 18 Code Surfaces table for
  the FastAPI app, simulation state, API reset, event cursors, encounters,
  controllers, actors, monster factories, deterministic combat modifiers,
  reset surfaces, stream framing, player types, game sessions, and the central
  client routes.
- Added anchored GitHub source links to the Chapter 19 Code Surfaces table for
  the FastAPI app, simulation state, authoring reset, entity/encounter
  boundaries, controllers, reset surfaces, map-editor payload models, and
  the central map-editor routes.
- Expanded the audited source-link guard through chapters 16, 17, 18, and 19,
  so the guarded bottom-up source-link path now spans chapters 01 through 19.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `213 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Conditions Movement Actions Source Links

The source-link convention now covers the next gameplay layer: conditions,
world movement, and action discovery. Chapters 07, 08, and 09 keep their
public module names visible while linking those names to source anchors on the
current branch.

Changes made:

- Added anchored GitHub source links to the Chapter 07 Code Surfaces table for
  condition owners, condition classes, event timing records, condition-owned
  handlers, modifiable values, and numerical modifiers.
- Added anchored GitHub source links to the Chapter 08 Code Surfaces table for
  the grid map, movement modes, terrain factories, spatial event timing,
  voluntary movement, forced movement, and reset surfaces.
- Added anchored GitHub source links to the Chapter 09 Code Surfaces table for
  action classes, action discovery helpers, override helpers, action
  categories, actor/config builders, registry reset surfaces, monster
  factories, public item factories, damage taxonomy, and hazard filters.
- Expanded the audited source-link guard through chapters 07, 08, and 09, so
  the guarded bottom-up source-link path now spans chapters 01 through 09.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `213 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Combat Equipment Perception Source Links

The source-link convention now covers combat resolution, equipment/items, and
perception. Chapters 10, 11, and 12 keep their public import names visible and
link them to anchored source on the current branch, carrying the inspectable
bottom-up path through the first full player-facing gameplay loop.

Changes made:

- Added anchored GitHub source links to the Chapter 10 Code Surfaces table for
  combat actions, standard action setup, actor construction, combat configs,
  weapon slots, events, deterministic dice, roll-state modifiers, actor size,
  monster factories, and opportunity reaction registration.
- Added anchored GitHub source links to the Chapter 11 Code Surfaces table for
  base items, inventory, equipment config, weapons, actor configs, reset
  surfaces, equipment slots, ranges, equipment values, stock item factories,
  public healing-potion factory access, door objects, and item-action
  execution.
- Added anchored GitHub source links to the Chapter 12 Code Surfaces table for
  senses, light and special-sense models, grid/FOV state, actor construction,
  reset surfaces, entity sense recomputation, sensory update events,
  concealment conditions, and direct perceivability state changes.
- Expanded the audited source-link guard through chapters 10, 11, and 12, so
  the guarded bottom-up source-link path now spans chapters 01 through 12.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `213 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Spells Classes Source Links

The source-link convention now covers spellcasting, spell families, and class
features. Chapters 13, 14, and 15 keep their public import names visible and
link them to anchored source on the current branch, carrying the inspectable
path into authored content.

Changes made:

- Added anchored GitHub source links to the Chapter 13 Code Surfaces table for
  spellcasting config, spell-slot resources, caster/target construction, spell
  registration, action discovery, spell actions/events, action metadata,
  event history, reset surfaces, deterministic dice, combat-log entry types,
  public spell catalogs, and concentration state.
- Added anchored GitHub source links to the Chapter 14 Code Surfaces table for
  spell catalogs, caster construction, spell-family actor configs, target
  metadata, spell events, reset surfaces, deterministic dice, creature and
  damage taxonomy, representative spell families, zone conditions, active
  spell effects, restoration conditions, and spell-protection reset state.
- Corrected the Chapter 14 `PowerWordKill` source mapping to point at
  `dnd.spells.enchantment`, matching the codebase.
- Added anchored GitHub source links to the Chapter 15 Code Surfaces table for
  class actor factories, fighter/barbarian/sorcerer config, feature actions,
  rage and metamagic state, Lucky feat policies, spell templates, dice/result
  events, value ledgers, roll-state taxonomy, reset surfaces, and spell
  protection state.
- Expanded the audited source-link guard through chapters 13, 14, and 15, so
  the guarded bottom-up source-link path now spans chapters 01 through 15.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `213 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Snippet Start Exact Execution

The public snippet contract now makes the import and scene code visibly part of
each runnable example. The collapsed panel label is `Snippet Start: Imports
And Scene`, so readers see that the disclosure is the beginning of the same
snippet rather than an external reference section.

Changes made:

- Renamed the reader-facing example disclosure label across the manual and
  `ExampleBlock.astro` from `Imports & Scene` to `Snippet Start: Imports And
  Scene`.
- Tightened `tests/book_examples/test_public_mdx_snippets.py` so
  `BookExample.source` executes only the exact public fence contents joined in
  page order. Source-location comments are no longer injected into the executed
  Python.
- Kept source locations available through `BookExample.locations` for failure
  messages without changing executed code.
- Re-ran the whole manual snippet gate from chapter 00 through chapter 27.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `217 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Running Game Authoring Ruling Roles

Chapters 16 through 19 now continue the ruling-loop spine through authored
opposition, playable time, client participation, and prepared spaces. Each
chapter names the ruling question it answers before the chapter map, code
surfaces, and runnable examples.

Changes made:

- Added `Ruling Role` to Chapter 16, explaining monsters and preset actors as
  the answer to encounter opposition: creature identity, stats, actions,
  defenses, inventory, role behavior, and ordinary actor consumption.
- Added `Ruling Role` to Chapter 17, explaining encounters as the answer to
  playable time: combatants, active turn, controller input, turn boundaries,
  logs, and faction-survival completion.
- Added `Ruling Role` to Chapter 18, explaining sessions and APIs as the
  answer to the client contract: participant identity, actor ownership,
  renderable state, legal choices, command submission, cursors, and streams.
- Added `Ruling Role` to Chapter 19, explaining map authoring as the answer to
  prepared space: scratch and preset maps, terrain/object rules, objective
  layers, persistence, and later playable handoff.
- Added verifier coverage in
  `tests/book_examples/test_public_mdx_snippets.py` to assert the prose
  phrases and section order for all four chapters.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `218 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual`.
- Strict public hygiene scan passed.
- Local route smoke check returned 200 for 29 routes from
  `http://127.0.0.1:4327`.

## Checkpoint: Goal Refresh And Completion Matrix

The goal now explicitly treats the manual as a public webbook for the game and
engine, not as a transformed notes folder. The target is a forward-facing
developer manual that explains Dungeons & Dragons as a videogame runtime,
teaches where imports and public symbols come from, and uses real executable
tutorial snippets instead of hidden test helpers or abstract parity wrappers.

Changes made:

- Updated `engine_book/goal.md` to include public webbook requirements, exact
  public snippet requirements, the Scenario/MapEditor boundary, architecture
  audit requirements, and final satisfaction criteria for snippets, SRD
  mapping, tests, hygiene, and webbook UX.
- Added `engine_book/completion_matrix.md` as the goal-level tracker for prose,
  snippets, exact snippet execution, deeper tests, SRD mapping, source links,
  legacy-example parity, hygiene, architecture audit, and navigation.
- Recorded current evidence conservatively: snippet execution, production build,
  route smoke, and nav order are verified for the current public webbook, while
  prose depth, SRD mapping, deeper tests, legacy parity, and code hygiene remain
  partial or needing audit.

Verification completed:

- Documentation artifact verification confirmed the goal links the completion
  matrix and that the matrix includes all 28 public chapters plus cross-cutting
  gates.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `219 passed`.

Residual completion caveat:

- The current evidence proves the visible manual set is structured,
  executable, source-oriented, and public-hygiene-clean. A final product
  acceptance pass should still be treated as a human editorial review because
  "manual in full" includes judgment about depth, tone, and completeness of the
  whole book experience, not only executable gates.

## Checkpoint: Chapter 01 Ruling Role And Visible Reset

Chapter 01 now matches the rest of the runtime-foundation spine. It explicitly
names identity as the answer to the ruling loop's reference question before the
chapter map, code surfaces, and examples.

Changes made:

- Added a `Ruling Role` section to Chapter 01 explaining identity as the answer
  to "which exact thing are we talking about?"
- Added a ruling-role guard for Chapter 01 in
  `tests/book_examples/test_public_mdx_snippets.py`.
- Removed `reset_combat_state` from Chapter 01 public snippets and the Chapter
  01 Code Surfaces table. The snippets now define their focused
  `reset_identity_state()` functions visibly in the `Snippet Start: Imports And
  Scene` panels.
- Updated `tests/manual/test_01_runtime_identity_and_registries.py` to use the
  same local-reset style as the public examples.
- Updated `engine_book/completion_matrix.md` with the Chapter 01 evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `219 passed`.
- `uv run pytest tests/manual/test_01_runtime_identity_and_registries.py -q`
  passed with `4 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 04 Full Visible-Output Cleanup

Chapter 04 no longer leaves the post-first-run dice examples as assertion-only
code. Each dice example now prints and displays the roll record behavior it
teaches: cached d20 identity, advantage/disadvantage face selection,
critical/auto-hit snapshots, normal and critical damage rolls, and validation
rejections.

Changes made:

- Updated
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/04-dice-rolls.mdx`
  so `dice-cached-d20`, `dice-advantage-disadvantage`,
  `dice-roll-state-snapshot`, `dice-damage-and-critical`, and
  `dice-expression-validation` each print and display observed output.
- Updated `tests/manual/test_04_dice_rolls.py` so every Chapter 04 dice
  example has a focused stdout assertion.
- Added
  `tests/book_examples/test_public_mdx_snippets.py::test_dice_chapter_examples_show_reader_visible_output`
  to guard against Chapter 04 regressing to assertion-only public examples.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` with the Chapter 04 visible-output
  transcript status.

Verification completed:

- `uv run pytest tests/manual/test_04_dice_rolls.py -q` passed with
  `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k '04-dice or dice_chapter'`
  passed with `7 passed, 247 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `255 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 03 Full Visible-Output Cleanup

Chapter 03 no longer leaves the value walkthroughs as assertion-only code
after the opening Armor Class ledger. Each public value example now prints a
reader-facing transcript and asserts the same lines: score normalization,
combined value breakdowns, static constraints and roll-state aggregation,
contextual high-ground evaluation, and target-facing propagation are all
visible as runtime output.

Changes made:

- Updated
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/03-values-and-modifiers.mdx`
  so `values-score-and-breakdown`, `values-static-rule-state`,
  `values-contextual-modifiers`, and `values-target-propagation` each print
  and display observed output.
- Updated `tests/manual/test_03_values_and_modifiers.py` so every Chapter 03
  value example has a focused stdout assertion.
- Added
  `tests/book_examples/test_public_mdx_snippets.py::test_values_chapter_examples_show_reader_visible_output`
  to guard against Chapter 03 regressing to assertion-only public examples.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` with the Chapter 03 visible-output
  transcript status.

Verification completed:

- `uv run pytest tests/manual/test_03_values_and_modifiers.py -q` passed with
  `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k '03-values or values_chapter'`
  passed with `6 passed, 247 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `254 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 02 Full Visible-Output Cleanup

Chapter 02 no longer leaves the continuing Aria walkthrough as assertion-only
code. The actor anatomy tour now prints reader-facing transcripts for actor
metadata, block ownership, character-sheet values, HP, turn resources, named
resource recharge, spellcasting, appearance, and block-tree discovery. The
focused tests assert those same transcripts so the public output remains tied
to the real engine state.

Changes made:

- Updated
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/02-entity-anatomy.mdx`
  so `entity-anatomy-tutorial` prints and displays observed output throughout
  the continuing Aria scene.
- Updated `tests/manual/test_02_entity_anatomy.py` so each actor anatomy
  section has a focused stdout assertion.
- Added
  `tests/book_examples/test_public_mdx_snippets.py::test_entity_chapter_examples_show_reader_visible_output`
  to guard against Chapter 02 regressing to assertion-only public examples.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` with the Chapter 02 visible-output
  transcript status.

Verification completed:

- `uv run pytest tests/manual/test_02_entity_anatomy.py -q` passed with
  `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k '02-entity or entity_chapter'`
  passed with `5 passed, 247 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `253 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 01 Full Visible-Output Cleanup

Chapter 01 no longer leaves the post-first-run examples as assertion-only
test code. Every identity example now prints a compact reader-facing
transcript and shows the matching output block in the public page, while the
focused tests assert the same lines. This keeps the page useful as a tutorial:
readers can see what object lookup, publication, registry-family separation,
entity position tracking, and value subclass lookup actually return.

Changes made:

- Updated `runtime-object-lookup`, `runtime-object-publishing`,
  `registry-families`, `entity-position-lookup`, and
  `value-subclass-lookup` in
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/01-runtime-identity-and-registries.mdx`
  with printed transcripts and visible `Output:` blocks.
- Updated `tests/manual/test_01_runtime_identity_and_registries.py` so each
  Chapter 01 identity example has a focused stdout assertion.
- Added
  `tests/book_examples/test_public_mdx_snippets.py::test_identity_chapter_examples_show_reader_visible_output`
  to guard against Chapter 01 regressing to assertion-only public examples.
- Updated `engine_book/goal.md`, `engine_book/parity_matrix.md`, and
  `engine_book/completion_matrix.md` with the new visible-output requirement
  and Chapter 01 status.

Verification completed:

- `uv run pytest tests/manual/test_01_runtime_identity_and_registries.py -q`
  passed with `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k '01-runtime or identity'`
  passed with `7 passed, 244 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `252 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Agent Scoring As Decision Policy

Chapters 26 and 27 now explain tactical scoring as a choice-ranking surface
before engine execution. The manual keeps agent authors grounded in legal
engine rows while making the ownership boundary explicit: scores help an agent
choose, then `LocalGameInterface.execute()` routes the selected template and
target index through validation, costs, events, damage, logs, and refreshed
tactical state.

Changes made:

- Added `## Tactical Scores Guide Selection` to
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/26-agent-tactical-interface.mdx`
  before the first tactical-interface example.
- Clarified the Chapter 26 expected-value example so EV functions compare
  options from the tactical snapshot before execution resolves the game result.
- Added `## Utility Scores Express Priority` to
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/27-agent-decision-patterns.mdx`
  before the first decision-pattern example.
- Clarified the Chapter 27 utility-ranking example so the selected score is the
  agent's priority while execution still runs through the live game interface.
- Extended
  `tests/book_examples/test_public_mdx_snippets.py::test_agent_tactical_chapter_frontloads_tactical_contract`
  and
  `tests/book_examples/test_public_mdx_snippets.py::test_agent_decision_chapter_frontloads_decision_contract`
  to guard those public explanations.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 26/27
  evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_live_replication_chapter_frontloads_stream_contract tests/book_examples/test_public_mdx_snippets.py::test_agent_tactical_chapter_frontloads_tactical_contract tests/book_examples/test_public_mdx_snippets.py::test_agent_decision_chapter_frontloads_decision_contract -q`
  passed with `3 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "25-live-replication-streams or 26-agent-tactical-interface or 27-agent-decision-patterns" -q`
  passed with `21 passed, 127 deselected`.
- `uv run pytest tests/manual/test_25_live_replication_streams.py tests/manual/test_26_agent_tactical_interface.py tests/manual/test_27_agent_decision_patterns.py -q`
  passed with `24 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `234 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 02 Product Actor Bridge

Chapter 02 now connects entity anatomy to the running videogame more directly.
The page explains not only which blocks an actor owns, but also how clients,
controllers, designers, scenarios, encounters, tools, and agents gather around
the same entity-owned object graph.

Changes made:

- Added `Actor State In The Game Loop` before the D&D creature-to-entity
  translation, making the player, designer, client, and runtime payoff explicit
  before the code surfaces.
- Added a public-content guard that checks this product bridge appears before
  the code examples.
- Removed `reset_combat_state` from
  `tests/manual/test_02_entity_anatomy.py`; the focused test now uses a local
  reset path built from the engine surfaces it actually touches.
- Updated `engine_book/completion_matrix.md` with the Chapter 02 evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `219 passed`.
- `uv run pytest tests/manual/test_02_entity_anatomy.py -q` passed with
  `4 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 03 Product Math Bridge

Chapter 03 now frames values as the game's explainable math layer before it
teaches individual modifier channels. The page explains how values support
player-facing explanations, designer-authored rule placement, client rendering,
combat and spell calculations, logs, and agent evaluation.

Changes made:

- Added `Value State In The Game Loop` before the ruling-role section, with a
  product-facing table for player, designer, client, and agent questions.
- Added a public-content guard that verifies the product math bridge appears
  before the D&D rule translation, code surfaces, and examples.
- Removed `reset_combat_state` from
  `tests/manual/test_03_values_and_modifiers.py`; the focused test now clears
  only the object and value registries it touches.
- Updated `engine_book/completion_matrix.md` with the Chapter 03 evidence and
  the current exact-snippet count.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `220 passed`.
- `uv run pytest tests/manual/test_03_values_and_modifiers.py -q` passed with
  `4 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 04 Product Roll Bridge

Chapter 04 now frames dice as the game's uncertainty ledger before it teaches
individual roll expressions. The page explains how roll records support
player-facing explanations, client animation, combat logs, result processors,
streams, and agent evaluation.

Changes made:

- Added `Dice State In The Game Loop` before the ruling-role section, with a
  product-facing table for player, designer, client, and later processor
  questions.
- Added a public-content guard that verifies the product roll bridge appears
  before the D&D dice translation, code surfaces, and examples.
- Removed `reset_combat_state` from `tests/manual/test_04_dice_rolls.py`; the
  focused test now clears only the object, value, dice, and dice-roll
  registries it touches.
- Updated `engine_book/completion_matrix.md` with the Chapter 04 evidence and
  the current exact-snippet count.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `221 passed`.
- `uv run pytest tests/manual/test_04_dice_rolls.py -q` passed with
  `5 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 05 Product Timeline Bridge

Chapter 05 now frames events as the game's timeline ledger before it teaches
individual event phases. The page explains how event records support
player-facing explanations, client animation, timing windows, combat logs,
streams, encounters, tools, and agent inspection.

Changes made:

- Added `Event State In The Game Loop` before the ruling-role section, with a
  product-facing table for actor intent, response timing, world changes,
  narration, and later inspection.
- Added a public-content guard that verifies the product timeline bridge
  appears before the game-moment translation, lifecycle contract, code
  surfaces, and examples.
- Removed `reset_combat_state` from `tests/manual/test_05_event_lifecycle.py`;
  the focused test now resets `EventQueue`, clears the object registry, and
  resets the combat-log callback directly.
- Updated `engine_book/completion_matrix.md` with the Chapter 05 evidence and
  the current exact-snippet count.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `uv run pytest tests/manual/test_05_event_lifecycle.py -q` passed with
  `5 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 06 Product Timing Bridge

Chapter 06 now frames reactions as the game's active timing layer before it
teaches handlers, result processors, spatial handlers, and movement-surface
policy. The page explains how reaction records support player-facing
explanations, designer-authored timing rules, client explanation, zones,
features, encounters, and agent evaluation.

Changes made:

- Added `Reaction State In The Game Loop` before the ruling-role section, with
  a product-facing table for outcome changes, legal response windows, client
  explanation, designer-authored rules, and agent reasoning.
- Extended the Chapter 06 public-content guard to verify that this bridge
  appears before the D&D timing translation, reaction surfaces, contract, code
  surfaces, and examples.
- Removed `reset_combat_state` from `tests/manual/test_06_reactions_to_events.py`;
  the focused test now resets `EventQueue` and clears only the object, value,
  dice, and dice-roll registries it touches.
- Preserved the voluntary-step versus forced-movement policy in prose and tests:
  `STEP_MOVEMENT` remains the opportunity-style surface, while
  `FORCED_MOVEMENT` stays separate.
- Updated `engine_book/completion_matrix.md` with the Chapter 06 evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `uv run pytest tests/manual/test_06_reactions_to_events.py -q` passed with
  `6 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 07 Product Condition Bridge

Chapter 07 now frames conditions as the game's ongoing-state ledger before it
teaches condition ownership, artifacts, and cleanup. The page explains how
active conditions support player-facing state, designer-authored durable rules,
client status display, combat, movement, senses, spells, zones, encounters, and
agent evaluation.

Changes made:

- Added `Condition State In The Game Loop` before the ruling-role section, with
  a product-facing table for active state, owned artifacts, client display,
  designer-authored states, and agent reasoning.
- Extended the Chapter 07 public-content guard to verify that this bridge
  appears before the D&D condition translation, condition contract, code
  surfaces, and examples.
- Removed `reset_combat_state` from
  `tests/manual/test_07_conditions_and_cleanup.py`; the focused test now resets
  `EventQueue` and clears the object, block, condition, and value registries it
  touches.
- Updated `engine_book/completion_matrix.md` with the Chapter 07 evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `uv run pytest tests/manual/test_07_conditions_and_cleanup.py -q` passed with
  `5 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 08 Product Board Bridge

Chapter 08 now frames the world model as the game's tactical truth layer before
it teaches map-state surfaces, movement contracts, and executable grid
examples. The page explains how board state supports path preview, movement
costs, edge constraints, occupancy, spatial events, terrain, hazards, zones,
perception, clients, agents, and authoring tools.

Changes made:

- Added `Board State In The Game Loop` before the ruling-role section, with a
  product-facing table for legal standing space, route cost, blocked edges,
  movement changes, reactive systems, and map-authoring changes.
- Extended the Chapter 08 public-content guard to verify that this bridge
  appears before the D&D board-state ruling, map-state translation, movement
  contract, code surfaces, and examples.
- Removed `reset_combat_state` from the Chapter 08 public snippets and from
  `tests/manual/test_08_world_model_and_movement.py`; the examples now reset
  `EventQueue`, clear the object, block, and value registries, reset
  `GridMap`, and clear the combat-log callback directly.
- Preserved the voluntary-step versus forced-movement policy: `STEP_MOVEMENT`
  remains the paid movement surface, while `FORCED_MOVEMENT` remains the push,
  pull, and shove displacement surface that still publishes spatial entry.
- Updated `engine_book/completion_matrix.md` with the Chapter 08 evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `uv run pytest tests/manual/test_08_world_model_and_movement.py -q` passed
  with `5 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 09 Product Command Bridge

Chapter 09 now frames action discovery as the game's command-menu layer before
it teaches ruling questions, grouped action rows, indexed execution, costs,
objects, inventory actions, overrides, target pools, and safe movement paths.
The page explains how action rows support player buttons, client commands,
controllers, agents, item use, object use, cost preview, validation, and event
execution.

Changes made:

- Added `Command State In The Game Loop` before the ruling-role section, with a
  product-facing table for visible buttons, target rows, command costs, client
  intent, item/object actions, and controller/agent comparison.
- Extended the Chapter 09 public-content guard to verify that this bridge
  appears before the ruling role, player-choice translation, action contract,
  code surfaces, and examples.
- Removed `reset_combat_state` from the Chapter 09 public snippets and from
  `tests/manual/test_09_action_discovery_and_costs.py`; the examples now reset
  `EventQueue`, clear object, block, condition, value, and entity registries,
  reset `GridMap`, and create the tutorial arena directly.
- Kept the local row-selection helpers visible in the snippets and prose so the
  tutorial shows how a controller selects rows by template name or category.
- Updated `engine_book/completion_matrix.md` with the Chapter 09 evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `uv run pytest tests/manual/test_09_action_discovery_and_costs.py -q` passed
  with `6 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 10 Product Outcome Bridge

Chapter 10 now frames combat resolution as the game's consequence layer before
it teaches ruling questions, the combat spine, selected-choice outcomes, the
combat contract, and executable combat examples. The page explains how combat
state supports validation, decisive rolls, HP and death state, healing,
movement, reactions, forced displacement, cost payment, combat logs, clients,
designers, and agents.

Changes made:

- Added `Outcome State In The Game Loop` before the ruling-role section, with a
  product-facing table for resolved or canceled commands, decisive rolls, actor
  state changes, reactions, narration, and designer extension points.
- Extended the Chapter 10 public-content guard to verify that this bridge
  appears before the ruling role, combat spine, selected-choice translation,
  combat contract, code surfaces, and examples.
- Removed `reset_combat_state` from the Chapter 10 public snippets and from
  `tests/manual/test_10_combat_resolution.py`; the examples now reset
  `EventQueue`, clear object, block, condition, value, and entity registries,
  reset `GridMap`, and create the tutorial arena directly.
- Preserved the chosen videogame combat policy: BG3-style `Shove` remains the
  public shove behavior, uses `FORCED_MOVEMENT`, and does not trigger
  opportunity attacks; voluntary `STEP_MOVEMENT` remains the opportunity-style
  timing surface.
- Updated `engine_book/completion_matrix.md` with the Chapter 10 evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `uv run pytest tests/manual/test_10_combat_resolution.py -q` passed with
  `5 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 11 Product Object Bridge

Chapter 11 now frames equipment, inventory, and items as the game's
physical-object layer before it teaches ruling questions, D&D gear translation,
item ownership, equipment slots, loadout displacement, and executable item
examples. The page explains how object state supports location, ownership,
carrying, equipping, use actions, stack counts, object visibility, client
payloads, and coherent videogame loadouts.

Changes made:

- Added `Object State In The Game Loop` before the ruling-role section, with a
  product-facing table for object location, ownership, player interactions,
  active item effects, loadout coherence, and client rendering.
- Extended the Chapter 11 public-content guard to verify that this bridge
  appears before the ruling role, D&D gear translation, chapter map, item
  ownership contract, code surfaces, and examples.
- Removed `reset_combat_state` from the Chapter 11 public snippets and from
  `tests/manual/test_11_equipment_inventory_and_items.py`; the examples now
  reset `EventQueue`, clear object, block, condition, value, and entity
  registries, reset `GridMap`, and create the tutorial map directly.
- Preserved the chosen videogame loadout policy: newer valid equips displace
  conflicting melee gear based on `WeaponProperty.TWO_HANDED`, while melee and
  ranged loadouts remain independent.
- Updated `engine_book/completion_matrix.md` with the Chapter 11 evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `uv run pytest tests/manual/test_11_equipment_inventory_and_items.py -q`
  passed with `5 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 12 Product Awareness Bridge

Chapter 12 now frames perception, light, stealth, and invisibility as the
game's player-knowledge layer before it teaches ruling questions, D&D senses,
observer state, the visibility contract, and executable perception examples.
The page explains how awareness state supports visible cells, legal targets,
remembered cells, path previews, observer-specific sensory updates, hidden DC,
invisibility, magical darkness, and special senses.

Changes made:

- Added `Awareness State In The Game Loop` before the ruling-role section, with
  a product-facing table for visible cells, UI targets, memory, path previews,
  observer-specific updates, and hidden/invisible layers.
- Extended the Chapter 12 public-content guard to verify that this bridge
  appears before the ruling role, D&D senses translation, chapter map,
  visibility contract, code surfaces, and examples.
- Removed `reset_combat_state` from the Chapter 12 public snippets and from
  `tests/manual/test_12_perception_light_stealth_and_invisibility.py`; the
  examples now reset `EventQueue`, clear object, block, condition, value, and
  entity registries, reset `GridMap`, create the tutorial map, and assign tile
  light directly.
- Preserved the observer-owned visibility policy: hidden DC, invisibility,
  light, magical darkness, and special senses resolve per observer, and
  subjective paths do not leak imperceivable blockers.
- Updated `engine_book/completion_matrix.md` with the Chapter 12 evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `uv run pytest tests/manual/test_12_perception_light_stealth_and_invisibility.py -q`
  passed with `6 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 13 Product Spell Bridge And Setup Label

Chapter 13 now frames spellcasting as the game's magical-action layer before it
teaches ruling questions, D&D spellcasting translation, action-template
registration, spell slots, caster numbers, spell events, multi-target spell
resolution, and concentration cleanup. The page explains how spell state
supports player spell rows, slot costs, spell attack/save math, event trees,
combat-log output, active effects, and client-visible concentration state.

Changes made:

- Added `Spell State In The Game Loop` before the ruling-role section, with a
  product-facing table for magical command rows, cast resources, spell numbers,
  spell events, lasting state, and client-visible spell results.
- Removed `reset_combat_state` from the Chapter 13 public snippets and from
  `tests/manual/test_13_spellcasting_core.py`; the examples now reset
  `EventQueue`, clear object, block, condition, value, and entity registries,
  reset `GridMap`, and create the tutorial map directly.
- Updated the Chapter 13 code-surface table so reset state is described through
  the engine registries and map surfaces used by the visible tutorial code.
- Migrated public `book-imports` summaries and `ExampleBlock.astro` from the
  old setup label to `Code setup: imports and scene`.
- Extended the public snippet guard to verify the Chapter 13 product spell
  bridge, setup-panel label, and absence of the hidden reset helper.
- Updated `engine_book/completion_matrix.md` with the Chapter 13 evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `uv run pytest tests/manual/test_13_spellcasting_core.py -q` passed with
  `6 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 14 Product Spell-Family Bridge

Chapter 14 now frames spell families as the game's reusable magic-behavior
patterns before it teaches ruling questions, D&D spell-name translation,
catalog metadata, spell attack families, save families, auto-hit spells,
healing, protection, movement, temporary hit points, zones, illusions, and
condition-producing spells. The page explains how family state supports player
spell-card expectations, decisive roll ownership, immediate spell outcomes,
lasting effects, reusable content design, and client explanation.

Changes made:

- Added `Spell Family State In The Game Loop` before the ruling-role section,
  with a product-facing table for player choice shape, decisive numbers,
  immediate outcomes, lasting state, designer reuse, and client explanation.
- Extended the Chapter 14 public-content guard to verify the product bridge,
  ordering before the ruling role, visible setup panels, D&D-to-runtime family
  translation, and absence of the hidden reset helper.
- Preserved the existing Chapter 14 tutorial snippets and focused manual tests,
  which already reset `EventQueue`, `SpellProtectionRegistry`, object, block,
  condition, value, entity, and `GridMap` state directly.
- Updated `engine_book/completion_matrix.md` with the Chapter 14 evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `uv run pytest tests/manual/test_14_spell_families.py -q` passed with
  `6 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 15 Product Character-State Bridge

Chapter 15 now frames class features, factories, and feats as the game's
character-building layer before it teaches ruling questions, D&D character
choice translation, factory assembly, class resources, feature-granted actions,
passive modifiers, temporary modes, metamagic overrides, result processors, and
rest cleanup. The page explains how character state supports player-readable
class identity, resources, action bars, active modes, feature ownership, and
client-facing character sheets.

Changes made:

- Added `Character State In The Game Loop` before the ruling-role section, with
  a product-facing table for class feel, spendable resources, action-bar
  buttons, passive rules, temporary modes, and client explanation.
- Extended the Chapter 15 public-content guard to verify the product bridge,
  ordering before the ruling role, visible setup panels, D&D-to-runtime
  character translation, and absence of the hidden reset helper.
- Preserved the existing Chapter 15 tutorial snippets and focused manual tests,
  which already reset `EventQueue`, `SpellProtectionRegistry`, object, block,
  condition, value, entity, and `GridMap` state directly.
- Updated `engine_book/completion_matrix.md` with the Chapter 15 evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `uv run pytest tests/manual/test_15_class_features.py -q` passed with
  `5 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 16 Product Monster-State Bridge

Chapter 16 now frames monsters and preset actors as the game's authored
opposition layer before it teaches ruling questions, D&D stat-block
translation, monster factory composition, base monsters, Nimble Escape,
spellcaster presets, skeleton role presets, Mark Target, and new-preset
authoring. The page explains how monster state supports player-readable
threats, legal entity state, monster turn choices, combat roles, lasting
monster effects, encounter setup, clients, and tactical agents.

Changes made:

- Added `Monster State In The Game Loop` before the ruling-role section, with a
  product-facing table for readable threats, legal runtime state, monster
  actions, role distinction, lasting monster state, and encounter/client
  consumption.
- Extended the Chapter 16 public-content guard to verify the product bridge,
  ordering before the ruling role, visible setup panels, D&D stat-block
  translation, preset actor contract, and absence of the hidden reset helper.
- Preserved the existing Chapter 16 tutorial snippets and focused manual tests,
  which already reset `EventQueue`, `SpellProtectionRegistry`, object, block,
  condition, value, entity, and `GridMap` state directly.
- Updated `engine_book/completion_matrix.md` with the Chapter 16 evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `uv run pytest tests/manual/test_16_monsters_preset_actors.py -q` passed
  with `5 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 17 Product Encounter-State Bridge

Chapter 17 now frames encounters, turns, and controllers as the game's
running-scene layer before it teaches ruling questions, D&D combat translation,
initiative, turn boundaries, controller input, combat logs, automated advance,
and faction-survival ending. The page explains how encounter state supports
current actor display, playable time, controller ownership, selected actions,
event history, dead actors, active effects, client state, and encounter
results.

Changes made:

- Added `Encounter State In The Game Loop` before the ruling-role section, with
  a product-facing table for combatants, current turn, controller ownership,
  shared action history, client display, and scene ending.
- Extended the Chapter 17 public-content guard to verify the product bridge,
  ordering before the ruling role, visible setup panels, D&D-to-runtime combat
  translation, the running-game contract, and absence of the hidden reset
  helper.
- Preserved the existing Chapter 17 tutorial snippets and focused manual tests,
  which already reset `EventQueue`, `SpellProtectionRegistry`, object, block,
  condition, value, entity, controller, encounter, and `GridMap` state directly.
- Updated `engine_book/completion_matrix.md` with the Chapter 17 evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `uv run pytest tests/manual/test_17_encounters_turns_controllers.py -q`
  passed with `5 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Goal Manual-Writing Standard Update

The goal now names the public-writing problem directly: the manual must not
explain itself through negation, private notes, hidden imports, or abstract test
fixtures. It must teach Dungeons & Dragons as played through NeuroDragon, the
videogame built on top of the engine, and the runtime surfaces that a developer
uses to expand that game.

Changes made:

- Added `Manual Writing Standard` to `engine_book/goal.md`.
- Made the required chapter order explicit: D&D concept, NeuroDragon game
  experience, engine runtime truth, source/import surfaces, and runnable
  examples with assertions.
- Added a term-introduction rule so chapters cannot talk about handlers,
  registries, scenario packages, streams, agents, or similar concepts before
  they have been taught or clearly inherited from earlier chapters.
- Clarified that imports may be collapsible for reading flow, but must remain
  visible, learnable, and explained as part of the tutorial surface.
- Clarified that public examples must be tutorial code, not private pytest
  helpers, abstract parity fixtures, unexplained scene wrappers, or test scripts
  disguised as documentation.
- Reaffirmed that public pages may link to source and polished diagrams, but
  must not use notes, tests, completion matrices, or rebuild checkpoints as the
  public explanation of a feature.

Verification completed:

- Goal/documentation-only edit; no runtime tests were needed.

## Checkpoint: Chapter 19 Product Authoring-State Bridge

Chapter 19 now frames map editor and scenario authoring as the game's
prepared-space layer before it teaches ruling questions, D&D place translation,
catalogs, scratch and preset maps, tile painting, object placement, objective
layers, saved documents, and the handoff from authoring to play. The page
explains how authored state supports grid bounds, terrain, movement rules,
visibility rules, light, object placement, loot placement, saved documents, and
the later scenario step that adds actors and turns.

Changes made:

- Added `Authoring State In The Game Loop` before the ruling-role section, with
  a product-facing table for prepared places, tile painting, object placement,
  objective rendering, persistence, and gameplay handoff.
- Removed the public `reset_combat_state` import and call from all Chapter 19
  setup snippets. The visible `reset_map_authoring_state()` recipe now clears
  `EventQueue`, combat-log callbacks, perceiver/reveal computers,
  `SpellProtectionRegistry`, object/block/condition/value registries, entity
  registries, controller and encounter registries, `GridMap`, and server
  simulation state directly.
- Updated `tests/manual/test_19_map_editor_scenario_authoring.py` to use the
  same explicit reset recipe instead of the shared reset utility.
- Extended the Chapter 19 public-content guard to verify the product bridge,
  ordering before the ruling role, visible setup panels, D&D-to-runtime
  authoring translation, authoring contract, and absence of the hidden reset
  helper.
- Updated `engine_book/completion_matrix.md` with the Chapter 19 evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `uv run pytest tests/manual/test_19_map_editor_scenario_authoring.py -q`
  passed with `6 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 20 Product Extension-State Bridge

Chapter 20 now frames content extension as the game's new-rule composition
layer before it teaches D&D content translation, importable content packs,
custom conditions, action templates, usable items, actor factories, scene
factories, action discovery, item-use discovery, and cleanup. The page explains
how extension state supports lasting rules, player choices, portable tools,
reusable actors, reusable scenes, client/controller action rows, and clean
runtime recovery.

Changes made:

- Added `Extension State In The Game Loop` before the D&D-to-extension bridge,
  with a product-facing table for lasting rules, player choices, portable
  item-carried rules, actor/scene reuse, client/controller consumption, and
  cleanup.
- Removed the public `reset_combat_state` import and call from all Chapter 20
  setup snippets. The visible `reset_content_extension_state()` recipe now
  clears `EventQueue`, combat-log callbacks, perceiver/reveal computers,
  `SpellProtectionRegistry`, object/block/condition/value registries, entity
  registries, and `GridMap` before creating the tutorial arena.
- Updated `tests/manual/test_20_content_extension_basics.py` to use the same
  explicit reset recipe instead of the shared reset utility.
- Extended the Chapter 20 public-content guard to verify the product bridge,
  ordering before the D&D content bridge, visible setup panels,
  D&D-to-runtime extension translation, extension contract, and absence of the
  hidden reset helper.
- Updated `engine_book/completion_matrix.md` with the Chapter 20 evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `uv run pytest tests/manual/test_20_content_extension_basics.py -q` passed
  with `6 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 21 Product Spell-Feature-State Bridge

Chapter 21 now frames feature-granted spell content as the game's learned-magic
composition layer before it teaches D&D feature magic, feature-owned spell
templates, spell actions, target discovery, `SpellEvent` resolution, effect
conditions, cleanup, and reusable actor/scene factories. The page explains how
spell-feature state supports learned spells, turn-menu choices, self-or-ally
targeting, casting events, persistent ward state, and feature teardown.

Changes made:

- Added `Spell-Feature State In The Game Loop` before the D&D feature-magic
  bridge, with a product-facing table for training ownership, action-menu
  exposure, target filtering, spell execution, lingering effect state, and
  training cleanup.
- Removed the public `reset_combat_state` import and call from all Chapter 21
  setup snippets. The visible `reset_spell_feature_state()` recipe now clears
  `EventQueue`, combat-log callbacks, perceiver/reveal computers,
  `SpellProtectionRegistry`, object/block/condition/value registries, entity
  registries, and `GridMap` before creating the tutorial arena.
- Updated `tests/manual/test_21_spell_and_feature_extensions.py` to use the
  same explicit reset recipe instead of the shared reset utility.
- Extended the Chapter 21 public-content guard to verify the product bridge,
  ordering before the D&D feature-magic bridge, visible setup panels,
  D&D-to-runtime spell-feature translation, spell-feature contract, and absence
  of the hidden reset helper.
- Updated `engine_book/completion_matrix.md` with the Chapter 21 evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `uv run pytest tests/manual/test_21_spell_and_feature_extensions.py -q`
  passed with `5 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 22 Product Scenario-State Bridge

Chapter 22 now frames playable scenario packages as the game's ready-to-run
adventure-room layer before it teaches D&D adventure-room translation, scenario
factories, actors, factions, controllers, encounter start, turn handoff,
indexed action execution, combat logs, and faction-survival endings. The page
explains how scenario state supports room setup, actor state, control
ownership, current-turn ownership, external input boundaries, result logging,
and victory or defeat.

Changes made:

- Added `Scenario State In The Game Loop` before the D&D adventure-room bridge,
  with a product-facing table for the room being played, actors, controllers,
  turn ownership, input handoff, action resolution, and scene ending.
- Expanded the Gatehouse scenario setup prose so `reset_playable_scenario_state`
  and `create_gatehouse_scenario` read as public scenario-package surfaces
  rather than unexplained fixtures.
- Removed the internal `reset_combat_state` dependency from
  `dnd/scenarios/gatehouse.py`; `reset_playable_scenario_state()` now owns its
  explicit reset recipe directly.
- Extended the Chapter 22 public-content guard to verify the product bridge,
  ordering before the D&D adventure-room bridge, visible setup panels,
  D&D-to-runtime scenario translation, scenario contract, and absence of the
  hidden reset helper in the public chapter.
- Updated `engine_book/completion_matrix.md` with the Chapter 22 evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `uv run pytest tests/manual/test_22_playable_scenario_packages.py -q` passed
  with `5 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 23 Product Arena-State Bridge

Chapter 23 now frames the standard arena as the game's reference playable mode
before it teaches D&D arena translation, map assembly, hero-kit selection,
monster-side composition, controller assignment, session join, live state
payloads, and available action payloads. The page explains how arena state
supports battlefield setup, selected hero kits, opposing roles, control mode,
player session ownership, client rendering, and reusable game-mode assembly.

Changes made:

- Added `Arena State In The Game Loop` before the D&D arena-play bridge, with a
  product-facing table for the active battlefield, selected hero, opposing
  monster side, control ownership, player join flow, client payloads, and
  designer reuse.
- Updated the Chapter 23 code-surface prose so `reset_standard_arena_runtime`
  names the exact runtime state it clears rather than reading like a private
  test helper.
- Removed the internal `reset_combat_state` dependency from
  `server/arena_mode.py`; `reset_standard_arena_runtime()` now owns its explicit
  reset recipe directly.
- Extended the Chapter 23 public-content guard to verify the product bridge,
  ordering before the D&D arena-play bridge, visible setup panels,
  D&D-to-runtime arena translation, arena contract, and absence of the hidden
  reset helper in the public chapter.
- Updated `engine_book/completion_matrix.md` with the Chapter 23 evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `uv run pytest tests/manual/test_23_standard_arena_game_modes.py -q` passed
  with `5 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 24 Product Controller-State Bridge

Chapter 24 now frames built-in controllers and automated turns as the game's
decision-ownership layer before it teaches D&D turn ownership, controller
types, turn contexts, outside-input pauses, pass behavior, melee automation,
agent delegation, and encounter handoff. The page explains how controller state
supports active-actor ownership, current turn context, pause boundaries,
explicit pass turns, built-in tactics, delegated agent turns, and encounter
authority.

Changes made:

- Added `Controller State In The Game Loop` before the D&D turn-ownership
  bridge, with a product-facing table for active creature ownership, turn
  context, pause behavior, passive turns, built-in automation, agent takeover,
  and encounter authority.
- Updated the Chapter 24 code-surface prose so
  `reset_controller_catalogue_state` names the exact runtime state it clears
  rather than reading like a private test helper.
- Removed the internal `reset_combat_state` dependency from
  `dnd/scenarios/controller_catalogue.py`; `reset_controller_catalogue_state()`
  now owns its explicit reset recipe directly.
- Extended the Chapter 24 public-content guard to verify the product bridge,
  ordering before the D&D turn-ownership bridge, visible setup panels,
  D&D-to-runtime controller translation, controller contract, positive pass
  language, and absence of the hidden reset helper in the public chapter.
- Updated `engine_book/completion_matrix.md` with the Chapter 24 evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `uv run pytest tests/manual/test_24_built_in_controllers.py -q` passed with
  `6 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 25 Product Stream-State Bridge

Chapter 25 now frames live replication streams as the game's change-delivery
layer before it teaches D&D consequence publication, event cursors, combat-log
cursors, sync frames, replay, live fan-out, completion/log ordering,
heartbeats, and bounded subscriber delivery. The page explains how stream
state supports exact engine-event history, readable combat narration, resumable
client progress, first connection, reconnect catch-up, live delivery, quiet
interval synchronization, and queue-depth protection.

Changes made:

- Added `Stream State In The Game Loop` before the D&D consequence bridge, with
  a product-facing table for event history, combat-log narration, cursor pairs,
  sync, replay, live fan-out, heartbeat frames, and bounded subscription
  eviction.
- Updated the Chapter 25 chapter map and code-surface prose so
  `reset_live_stream_state` names the exact runtime state it clears and reads
  as a stream scene surface rather than an implicit test fixture.
- Removed the internal `reset_combat_state` dependency from
  `server/live_replication.py`; `reset_live_stream_state()` now owns its
  explicit stream reset recipe directly before reattaching stream callbacks.
- Extended the Chapter 25 public-content guard to verify the product bridge,
  ordering before the D&D consequence bridge, stream-state language, visible
  reset surface, and absence of the hidden reset helper in the public chapter.
- Added a focused Chapter 25 reset guard that inspects
  `reset_live_stream_state()` and verifies it clears stream callbacks,
  registries, encounter/controller state, and map state before attaching the
  live stream bridge.
- Updated `engine_book/completion_matrix.md` with the Chapter 25 evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `uv run pytest tests/manual/test_25_live_replication_streams.py -q` passed
  with `7 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 26 Product Agent-State Bridge

Chapter 26 now frames the tactical interface as the game's agent-facing
decision layer before it teaches D&D turn translation, tactical snapshots,
action rows, target rows, tactical queries, expected-value scoring, execution,
and `BaseAgent` turn ownership. The page explains how agent-facing state
supports controlled actor identity, subjective perception, spendable resources,
legal choices, target-index preservation, comparable tactical scoring, ordinary
engine execution, and reusable agent turn runners.

Changes made:

- Added `Agent State In The Game Loop` before the D&D tactical-state bridge,
  with a product-facing table for controlled actor identity, visible enemies
  and allies, resources, legal action groups, target indexes, tactical scoring,
  action execution, and reusable agent turns.
- Updated the Chapter 26 chapter map and code-surface prose so
  `reset_agent_interface_state` names the exact runtime state it clears and
  reads as an agent training-scene surface rather than an implicit test helper.
- Removed the internal `reset_combat_state` dependency from
  `dnd/scenarios/agent_tactical_training.py`; `reset_agent_interface_state()`
  now owns its explicit reset recipe directly.
- Extended the Chapter 26 public-content guard to verify the product bridge,
  ordering before the D&D tactical-state bridge, visible reset surface,
  tactical-interface contract, and absence of the hidden reset helper in the
  public chapter.
- Added a focused Chapter 26 reset guard that inspects
  `reset_agent_interface_state()` and verifies it clears event callbacks,
  registries, encounter/controller state, and map state before building an
  agent training scene.
- Updated `engine_book/completion_matrix.md` with the Chapter 26 evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `uv run pytest tests/manual/test_26_agent_tactical_interface.py -q` passed
  with `7 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 27 Product Decision-State Bridge

Chapter 27 now frames agent decision patterns as the game's behavior-selection
layer before it teaches D&D tactical judgment, behavior trees, behavior-tree
actions, composite tactics, interrupt detection, utility scoring, focused
pressure, utility-agent turn loops, and execution through the tactical
interface. The page explains how decision state supports tactical snapshot
input, ordered priorities, coherent multi-step tactics, board-change
recognition, ranked action-target options, ordinary engine execution, reusable
agent loops, and engine authority.

Changes made:

- Added `Decision State In The Game Loop` before the D&D tactical-judgment
  bridge, with a product-facing table for tactical input, behavior-tree
  priorities, composite tactics, interrupt detection, utility scoring,
  interface execution, reusable agent loops, and engine authority.
- Updated the Chapter 27 chapter map, code-surface table, and first setup panel
  so decision scenes explicitly reuse the Chapter 26
  `reset_agent_interface_state` surface before building decision encounters.
- Added `reset_agent_interface_state` to the first public Chapter 27 snippet so
  the inherited reset surface is visible to the reader instead of implied by a
  scene factory.
- Extended the Chapter 27 public-content guard to verify the product bridge,
  ordering before the D&D tactical-judgment bridge, visible inherited reset
  surface, decision contract, and absence of the hidden reset helper in the
  public chapter.
- Added a focused Chapter 27 scene guard that inspects the decision-scene
  module, verifies it does not call `reset_combat_state`, and proves both
  decision scene factories call the documented tactical reset surface.
- Updated `engine_book/completion_matrix.md` with the Chapter 27 evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `uv run pytest tests/manual/test_27_agent_decision_patterns.py -q` passed
  with `7 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Orientation Reader Contract

Chapter 00 and the landing page now explain how the public manual should be
read before the reader enters the technical chapters. The opening chapter
already described NeuroDragon as the software dungeon master, the ruling loop,
the videogame ruleset, runnable examples, and the bottom-up build path; this
pass added a clearer contract for how every technical chapter moves from game
idea to usable code.

Changes made:

- Added `What Each Chapter Gives You` to Chapter 00, with a reader-facing table
  for play meaning, runtime state, D&D bridge, code surfaces, runnable tutorial
  example, and next layer.
- Added a short teaching-contract paragraph that names the sequence: understand
  the game moment, identify the owning runtime state, read the code surface,
  and run the tutorial scene.
- Added a landing-page `Chapter Contract` section titled `From Play Meaning To
  Usable Code`, with three reader moves: read the play moment, find the runtime
  owner, and use the code surface.
- Extended the public snippet/content guard so Chapter 00 and the landing page
  must keep that reader contract.
- Updated `engine_book/completion_matrix.md` with the orientation evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 01 Identity Tutorial Thread

Chapter 01 now makes the first technical chapter read more clearly as a
continuous tutorial sequence. The page already explained runtime identity as
the address system for live objects, D&D references, ruling-loop lookup, and
registry families; this pass tightened the first code layer so the examples
climb from root object identity through actor and value lookup contracts.

Changes made:

- Corrected the code-surface framing from "two registry families" to "three
  registry families" so the prose matches the object, value, block, and entity
  lookup surfaces taught by the examples.
- Added a five-step identity thread table that names the progression: root
  object lookup, publication control, registry-family choice, actor position
  identity, and value subclass contracts.
- Added an `Identity Authoring Guide` before the code-surface table, covering
  live object identity, publication timing, lookup families, source and target
  ownership, actor position lookup, and lookup-contract behavior.
- Replaced the public tutorial docstring wording `Small concrete object...`
  with `Concrete marker object...` in the Chapter 01 snippets and focused test.
- Extended the Chapter 01 public-content guard to require the five-step
  identity thread, the new authoring guide, and rejection of the weak tutorial
  docstring wording.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 01
  evidence.

Verification completed:

- `uv run pytest tests/manual/test_01_runtime_identity_and_registries.py -q`
  passed with `4 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 02 Actor Anatomy Tutorial Thread

Chapter 02 now carries the identity work from Chapter 01 directly into playable
actor state. The page explains that `Entity` is the first actor-shaped object
stored under a runtime UUID, then shows how that one actor object answers
character-sheet, map, resource, spellcasting, and client-display questions.

Changes made:

- Added a UUID-to-actor bridge in the opening section so `Entity` is presented
  as the concrete object graph opened by later actor UUIDs.
- Added a four-move Aria tutorial thread under `Chapter Map`: create the actor
  from config, read the character sheet, inspect combat and presentation state,
  and walk the actor tree.
- Added an `Entity Authoring Guide` before the code-surface table, covering
  actor metadata, ability scores, training, durability, turn resources, magic,
  presentation, and actor-tree inspection.
- Tightened setup-panel prose so the imports and `create_tutorial_hero()`
  scene constructor are explained without repetitive setup-label wording.
- Polished the focused Chapter 02 tutorial actor docstring.
- Extended the public-content guard so Chapter 02 must keep the UUID-to-actor
  bridge, four-move tutorial thread, entity authoring guide, and improved setup
  wording.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 02
  evidence.

Verification completed:

- `uv run pytest tests/manual/test_02_entity_anatomy.py -q` passed with
  `4 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 03 Value Tutorial Thread

Chapter 03 now carries Chapter 02 actor anatomy into the value layer. The page
explains that `Entity` owns the actor-shaped object graph, while
`ModifiableValue` owns the explainable numbers inside that graph: ability
scores, movement, spell bonuses, equipment bonuses, damage responses, and other
rule-derived totals.

Changes made:

- Added an actor-state-to-value bridge in `Values As Rule Ledgers`, making the
  handoff from Chapter 02 explicit before value channels appear.
- Added a four-move value tutorial thread under `Chapter Map`: create a
  Strength score and attack bonus, aggregate static rule state, evaluate high
  ground, and attack a blinded target.
- Added a pre-surface `Value Authoring Guide` that teaches owning values,
  channel choice, named modifiers, contextual rules, target-facing exports,
  one-calculation target imports, and readable breakdowns before the source
  table appears.
- Replaced weaker `small` wording with more professional value-ledger language.
- Aligned the focused Chapter 03 test import path for
  `ContextualNumericalModifier` with the public tutorial snippet import path.
- Extended the public-content guard so Chapter 03 must keep the actor-to-value
  bridge, four-move tutorial thread, pre-surface value authoring guide, and
  cleaned-up wording.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 03
  evidence.

Verification completed:

- `uv run pytest tests/manual/test_03_values_and_modifiers.py -q` passed with
  `4 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 04 Dice Tutorial Thread

Chapter 04 now carries Chapter 03 values into the dice layer. The page explains
that a `ModifiableValue` keeps bonuses and roll state explainable, then `Dice`
attaches that value ledger to an expression and `DiceRoll` turns uncertain faces
into one registered result record.

Changes made:

- Added a value-ledger-to-roll-record bridge in the opening section so the
  handoff from Chapter 03 is explicit before dice examples begin.
- Added a five-move dice tutorial thread under `Chapter Map`: roll one cached
  d20, compare advantage and disadvantage, capture roll-state flags, roll
  damage and critical damage, and reject invalid expressions.
- Added a pre-surface `Dice Authoring Guide` that teaches bonus values, roll
  categories, dice expressions, damage outcome data, cached results,
  display/replay fields, and deterministic walkthroughs before the source table
  appears.
- Extended the public-content guard so Chapter 04 must keep the value-to-dice
  bridge, five-move tutorial thread, and pre-surface dice authoring guide.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 04
  evidence.

Verification completed:

- `uv run pytest tests/manual/test_04_dice_rolls.py -q` passed with
  `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 05 Event Tutorial Thread

Chapter 05 now carries Chapter 04 dice records into the event layer. The page
explains that stable `DiceRoll` records answer local uncertainty, while events
give those records a place in the game timeline with actor identity, targets,
effects, cancellation reasons, child effects, and completion logs.

Changes made:

- Added a dice-roll-to-event-timeline bridge in `Events As Game Occurrence
  Records` so the handoff from Chapter 04 is explicit before event lifecycle
  mechanics appear.
- Added a five-move event tutorial thread under `Chapter Map`: advance one
  lineage through phases, cancel a locked-door intent, connect spell and damage
  events, generate completion narration, and observe stored versions passively.
- Moved the `Event Authoring Guide` before the code-surface table so the
  chapter now teaches intent, execution, effect, cancellation, child events,
  completion narration, and passive observation before import paths appear.
- Polished the focused Chapter 05 tutorial event docstring.
- Extended the public-content guard so Chapter 05 must keep the dice-to-event
  bridge, five-move tutorial thread, and pre-surface authoring guide.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 05
  evidence.

Verification completed:

- `uv run pytest tests/manual/test_05_event_lifecycle.py -q` passed with
  `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 06 Reaction Tutorial Thread

Chapter 06 now carries Chapter 05 event phases into timed rule responses. The
page explains that event lifecycle gives the timeline of a game occurrence,
while reactions define which rules may hear a specific event version, what they
may change, and why completion remains final observation instead of rule
rewriting.

Changes made:

- Added an event-phase-to-reaction-window bridge in the opening section so the
  handoff from Chapter 05 is explicit before reaction surfaces appear.
- Added a six-move reaction tutorial thread under `Chapter Map`: ring an alarm
  for one matching event, keep quiet timing windows quiet, cancel a warded
  action, replace a low attack roll, trigger thorns by position, and separate
  voluntary steps from forced displacement.
- Moved the `Reaction Authoring Guide` after the reaction contract and before
  the code-surface table so the chapter teaches timing surfaces after the
  contract and before import paths.
- Extended the public-content guard so Chapter 06 must keep the event-to-
  reaction bridge, six-move tutorial thread, contract-before-guide order, and
  pre-surface authoring guide.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 06
  evidence.

Verification completed:

- `uv run pytest tests/manual/test_06_reactions_to_events.py -q` passed with
  `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 07 Condition Tutorial Thread

Chapter 07 now carries Chapter 06 reactions into durable owned rule state. The
page explains that timed reactions answer a mutable event window, while
conditions own the value changes, event listeners, linked effects, and cleanup
map that keep an ongoing state real across later rulings.

Changes made:

- Added a reaction-to-condition-ownership bridge in the opening section so the
  handoff from Chapter 06 is explicit before condition lifecycle mechanics
  appear.
- Added a six-move condition tutorial thread under `Chapter Map`: create a
  condition-bearing actor, apply Guarded, listen while active, remove a
  same-block child tree, link two blocks, and expire by duration.
- Moved the `Condition Authoring Guide` before the code-surface table so the
  chapter teaches owned modifiers, handlers, children, links, durations, and
  effect events before import paths appear.
- Polished the focused Chapter 07 tutorial actor docstring.
- Extended the public-content guard so Chapter 07 must keep the reaction-to-
  condition bridge, six-move tutorial thread, and pre-surface authoring guide.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 07
  evidence.

Verification completed:

- `uv run pytest tests/manual/test_07_conditions_and_cleanup.py -q` passed with
  `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 08 World Tutorial Thread

Chapter 08 now carries Chapter 07 condition ownership into tactical board
state. The page explains that conditions can own spatial listeners and
durations, while the world model supplies the tiles, costs, borders, position
indexes, voluntary steps, forced displacement, and spatial change events those
rules listen to.

Changes made:

- Added a condition-spatial-rule-to-world-board bridge in the opening section
  so the handoff from Chapter 07 is explicit before map mechanics appear.
- Added a five-move world tutorial thread under `Chapter Map`: measure a
  corridor with difficult terrain, block one edge, move one actor by step, push
  one actor by force, and build a room quietly.
- Moved the `Tactical Board Authoring Guide` before the code-surface table so
  the chapter teaches terrain, borders, position indexes, movement cause,
  spatial events, and setup-versus-runtime edits before import paths appear.
- Extended the public-content guard so Chapter 08 must keep the condition-to-
  world bridge, five-move tutorial thread, and pre-surface authoring guide.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 08
  evidence.

Verification completed:

- `uv run pytest tests/manual/test_08_world_model_and_movement.py -q` passed
  with `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 09 Command Tutorial Thread

Chapter 09 now carries Chapter 08 board state into player-facing command
choices. The page explains that positions, path costs, spatial events,
voluntary steps, and forced displacement become action rows when combined with
actor state, senses, items, resources, features, and available targets.

Changes made:

- Added a board-state-to-command-menu bridge in the opening section so the
  handoff from Chapter 08 is explicit before action discovery mechanics appear.
- Added a seven-move command tutorial thread under `Chapter Map`: instantiate
  Dash from a template, discover a turn menu, execute Dash by index, pick up and
  drink a potion, override Dash cost, filter target pools, and prefer a safe
  movement path.
- Reworded the Chapter 09 code-surface introduction so setup panels are framed
  as visible tutorial surfaces rather than hidden collapsed machinery.
- Moved the `Action Authoring Guide` before the code-surface table so command
  authoring is taught before import paths appear.
- Extended the public-content guard so Chapter 09 must keep the board-to-
  command bridge, seven-move tutorial thread, pre-surface authoring guide, and
  setup-panel wording cleanup.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 09
  evidence.

Verification completed:

- `uv run pytest tests/manual/test_09_action_discovery_and_costs.py -q` passed
  with `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 10 Combat Tutorial Thread

Chapter 10 now carries Chapter 09 command choices into combat consequences.
The page explains that the command menu supplies templates, target rows,
indexed execution, object routing, and movement-path metadata, while combat
resolution turns one selected command into validation, rolls, HP changes,
reactions, movement, costs, and event history.

Changes made:

- Added a command-to-consequence bridge in the opening section so the handoff
  from Chapter 09 is explicit before combat mechanics appear.
- Added a five-move combat tutorial thread under `Chapter Map`: swing at a
  target outside reach, land a hit and heal damage, force a critical hit, walk
  out of reach, and shove a target.
- Cleaned extra setup-panel whitespace in the public Chapter 10 snippets and
  focused Chapter 10 test.
- Moved the `Combat Authoring Guide` before the code-surface table so the
  consequence pipeline is taught before import paths appear.
- Extended the public-content guard so Chapter 10 must keep the command-to-
  consequence bridge, five-move tutorial thread, and pre-surface authoring
  guide.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 10
  evidence.

Verification completed:

- `uv run pytest tests/manual/test_10_combat_resolution.py -q` passed with
  `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 11 Item Tutorial Thread

Chapter 11 now carries Chapter 10 combat consequences into physical object
state. The page explains that selected actions become validation, rolls, HP
changes, reactions, movement, costs, and event history, while weapons, armor,
shields, potions, doors, and loose loot provide persistent item records that
combat, action discovery, perception, and client payloads can address.

Changes made:

- Added a combat-consequence-to-physical-object bridge in the opening section
  so the handoff from Chapter 10 is explicit before item ownership mechanics
  appear.
- Added a five-move item tutorial thread under `Chapter Map`: place, loot, and
  drop a key; merge potion stacks and reject an overweight insert; equip sword,
  shield, and armor then unequip the sword; resolve two-handed melee
  displacement while keeping ranged gear parallel; and drink a potion while
  opening a door through the same item-use path.
- Cleaned extra setup-panel whitespace in the public Chapter 11 snippets.
- Moved the `Item Authoring Guide` before the code-surface table so physical
  object authoring is taught before import paths appear.
- Extended the public-content guard so Chapter 11 must keep the combat-to-item
  bridge, five-move tutorial thread, and pre-surface authoring guide.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 11
  evidence.

Verification completed:

- `uv run pytest tests/manual/test_11_equipment_inventory_and_items.py -q`
  passed with `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 12 Perception Tutorial Thread

Chapter 12 now carries Chapter 11 physical object state into observer-specific
knowledge. The page explains that item ownership, equipment slots, loadout
displacement, inventory consumables, and map objects all exist in objective
world state, while perception decides which cells, actors, objects, and paths a
specific player can see, target, remember, or route around.

Changes made:

- Added a physical-object-to-observer-knowledge bridge in the opening section
  so the handoff from Chapter 11 is explicit before perception mechanics
  appear.
- Added a six-move perception tutorial thread under `Chapter Map`: subscribe to
  a dark corridor before seeing the far cell; swap darkvision, Devil's Sight,
  and truesight on one observer; light a subscribed target cell; raise stealth
  DC, lower it, then turn on invisibility; preview a path past an unseen blocker
  and then reveal it with truesight; and stack Hidden and Invisible before
  revealing only the stealth layer.
- Cleaned extra setup-panel whitespace in the public Chapter 12 snippets.
- Moved the `Visibility Authoring Guide` before the code-surface table so
  observer-local knowledge authoring is taught before import paths appear.
- Extended the public-content guard so Chapter 12 must keep the item-to-
  perception bridge, six-move tutorial thread, and pre-surface authoring guide.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 12
  evidence.

Verification completed:

- `uv run pytest tests/manual/test_12_perception_light_stealth_and_invisibility.py -q`
  passed with `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 13 Spellcasting Tutorial Thread

Chapter 13 now carries Chapter 12 observer-local knowledge into magical
choices. The page explains that visible cells, visible entities, visible
objects, subjective paths, light, stealth, and invisibility feed the spell rows,
targets, and areas exposed by action discovery, while spellcasting adds slots,
caster numbers, spell events, damage, multi-target records, and concentration
cleanup after the player chooses a spell.

Changes made:

- Added an observer-knowledge-to-magical-choice bridge in the opening section
  so the handoff from Chapter 12 is explicit before spellcasting mechanics
  appear.
- Added a six-move spellcasting tutorial thread under `Chapter Map`: spend a
  first-level spell slot and run turn reset; compose spell attack, save DC,
  damage, and critical values; register Fire Bolt, Magic Missile, and Haste and
  discover their rows; cast Fire Bolt with fixed dice; cast Magic Missile into
  one target; and cast Haste before removing concentration.
- Cleaned extra setup-panel whitespace in the public Chapter 13 snippets.
- Moved the `Spell Authoring Guide` before the code-surface table so
  spellcasting authoring is taught before import paths appear.
- Extended the public-content guard so Chapter 13 must keep the perception-to-
  spellcasting bridge, six-move tutorial thread, and pre-surface authoring
  guide.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 13
  evidence.

Verification completed:

- `uv run pytest tests/manual/test_13_spellcasting_core.py -q` passed with
  `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 14 Spell-Family Tutorial Thread

Chapter 14 now carries Chapter 13 spellcasting machinery into implemented
runtime families. The page explains that slots, caster numbers, registered spell
rows, spell events, multi-target records, and concentration cleanup are the
casting machinery, while the catalog turns D&D spell names into reusable
behavior patterns for damage, saves, auto-hit darts, protection, movement,
zones, and conditions.

Changes made:

- Added a spellcasting-machinery-to-runtime-family bridge in the opening section
  so the handoff from Chapter 13 is explicit before catalog mechanics appear.
- Added a six-move spell-family tutorial thread under `Chapter Map`: read
  representative spells from the catalog; resolve Fire Bolt, Sacred Flame, and
  Magic Missile; cast Cure Wounds, Healing Word, Mage Armor, and Lesser
  Restoration; cast Misty Step and False Life; cast Spike Growth, enter its
  area, then remove concentration; and cast Mirror Image and Sleep.
- Cleaned extra setup-panel whitespace in the public Chapter 14 snippets.
- Moved the `Spell Family Authoring Guide` before the code-surface table so
  spell-family authoring is taught before import paths appear.
- Extended the public-content guard so Chapter 14 must keep the spellcasting-
  to-family bridge, six-move tutorial thread, and pre-surface authoring guide.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 14
  evidence.

Verification completed:

- `uv run pytest tests/manual/test_14_spell_families.py -q` passed with
  `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 15 Character-Content Tutorial Thread

Chapter 15 now carries Chapter 14 spell families into authored character
identity. The page explains that damage, saves, auto-hit darts, protection,
movement, zones, and condition effects become capabilities owned by specific
actors through class choices, feature resources, and feature conditions.

Changes made:

- Added a spell-family-to-character-identity bridge in the opening section so
  the handoff from Chapter 14 is explicit before class-feature mechanics
  appear.
- Added a five-move character-content tutorial thread under `Chapter Map`:
  create fighter, barbarian, and sorcerer actors from factories; spend Second
  Wind and Action Surge, then short rest; enter Berserker Frenzy and remove
  Rage; apply Quickened Spell to Fire Bolt; and attach Lucky before processing
  d20 results.
- Cleaned extra setup-panel whitespace in the public Chapter 15 snippets.
- Moved the `Character Content Authoring Guide` before the code-surface table
  so class and feature authoring is taught before import paths appear.
- Extended the public-content guard so Chapter 15 must keep the spell-family-
  to-character bridge, five-move tutorial thread, and pre-surface authoring
  guide.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 15
  evidence.

Verification completed:

- `uv run pytest tests/manual/test_15_class_features.py -q` passed with
  `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 16 Preset-Actor Tutorial Thread

Chapter 16 now carries Chapter 15 authored character identity into authored
opposition and support actors. The page explains that factories, feature
resources, class actions, feature-owned conditions, spell-template overrides,
and feat policies become the same recipe shape for monsters and presets, which
enter the entity, action, equipment, spell, item, condition, perception, and
encounter systems as live actors.

Changes made:

- Added a character-identity-to-preset-actor bridge in the opening section so
  the handoff from Chapter 15 is explicit before monster factory mechanics
  appear.
- Added a five-move preset-actor tutorial thread under `Chapter Map`: create
  goblin and skeleton stat-block actors; inspect goblin Nimble Escape; create a
  generic caster preset; create skeleton warrior, archer, and warlock roles;
  and use Mark Target before removing concentration.
- Cleaned extra setup-panel whitespace in the public Chapter 16 snippets.
- Moved the `Preset Actor Authoring Guide` before the code-surface table so
  monster and preset authoring is taught before import paths appear.
- Extended the public-content guard so Chapter 16 must keep the character-to-
  preset bridge, five-move tutorial thread, and pre-surface authoring guide.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 16
  evidence.

Verification completed:

- `uv run pytest tests/manual/test_16_monsters_preset_actors.py -q` passed with
  `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 17 Encounter Tutorial Thread

Chapter 17 now carries Chapter 16 preset actors into running encounter time.
The page explains that monsters and presets become live actors with stats,
actions, spells, gear, inventory, senses, conditions, and special abilities,
while an encounter wraps those live entities as combatants, assigns
controllers, opens turns, records completed events, and decides the result of
the scene.

Changes made:

- Added a preset-actor-to-running-encounter bridge in the opening section so
  the handoff from Chapter 16 is explicit before encounter lifecycle mechanics
  appear.
- Added a five-move encounter tutorial thread under `Chapter Map`: start an
  ordered encounter and end it manually; start and end turns across a round
  boundary; advance through a pass-controlled monster to a human hero; execute
  an attack through the encounter; and drop one faction before running death
  checks.
- Cleaned extra setup-panel whitespace in the public Chapter 17 snippets.
- Extended the public-content guard so Chapter 17 must keep the preset-to-
  encounter bridge and five-move tutorial thread.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 17
  evidence.

Verification completed:

- `uv run pytest tests/manual/test_17_encounters_turns_controllers.py -q`
  passed with `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 18 Client-Contract Tutorial Thread

Chapter 18 now carries Chapter 17 running encounter time into client sessions
and API payloads. The page explains that combatants, initiative, turn contexts,
controller boundaries, combat logs, and faction-survival endings become a
client contract where sessions identify connected participants, ownership maps
controlled actors, state payloads render the scene, action rows expose legal
choices, and cursors describe what changed after commands resolve.

Changes made:

- Added a running-encounter-to-client-contract bridge in the opening section so
  the handoff from Chapter 17 is explicit before session and API mechanics
  appear.
- Added a five-move client-contract tutorial thread under `Chapter Map`: create
  a session, join the game, and ping turn ownership; read state, current turn,
  and available actions; execute the discovered melee attack by target index;
  read events, combat logs, and an SSE frame; and read spell catalog metadata.
- Cleaned extra setup-panel whitespace in the public Chapter 18 snippets.
- Extended the public-content guard so Chapter 18 must keep the encounter-to-
  client bridge and five-move tutorial thread.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 18
  evidence.

Verification completed:

- `uv run pytest tests/manual/test_18_sessions_api_client_contract.py -q`
  passed with `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 19 Authoring-Room Tutorial Thread

Chapter 19 now carries Chapter 18 client-contract thinking into map editor and
scenario authoring. The page explains that the previous chapter's sessions,
ownership, state payloads, action rows, and cursors are the running-game client
contract, then introduces authoring clients as command senders that shape the
place before actors, turns, controllers, initiative, and combat logs enter it.

Changes made:

- Added a Chapter 18 client-contract-to-authoring-client bridge in the opening
  section so map editing is presented as the preparation-side API contract.
- Rebuilt the `Chapter Map` as a six-move authored-room tutorial thread:
  choose the palette and open a blank room; paint terrain, light, and a
  directional border; place a door and lit torch, then read objective layers;
  delete placed objects; save, reload, list, and delete the room; and open a
  preset arena before moving back from play to authoring.
- Cleaned extra setup-panel whitespace in the public Chapter 19 snippets.
- Extended the public-content guard so Chapter 19 must keep the Chapter 18
  bridge and six-move authored-room thread.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 19
  evidence.

Verification completed:

- `uv run pytest tests/manual/test_19_map_editor_scenario_authoring.py -q`
  passed with `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 20 Field-Focus Tutorial Thread

Chapter 20 now carries Chapter 19 authored-space thinking into content
extension. The page explains that the previous chapter prepared catalog
choices, map snapshots, tile patches, placed objects, objective layers, saved
documents, and handoffs into play; this chapter prepares authored rules by
giving a new tactical idea the same runtime life as built-in content.

Changes made:

- Added a Chapter 19 authored-space-to-authored-rule bridge in the opening
  section so content extension is presented as the next authoring layer.
- Rebuilt the `Chapter Map` as a six-move Field Focus content-pack tutorial
  thread: inspect the public module shape; apply and remove the condition;
  register and execute the action; package the action in a carried item; expose
  the item as a nearby floor object; and compose the actor plus training scene
  factories.
- Cleaned extra setup-panel whitespace in the public Chapter 20 snippets.
- Extended the public-content guard so Chapter 20 must keep the Chapter 19
  bridge and six-move Field Focus thread.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 20
  evidence.

Verification completed:

- `uv run pytest tests/manual/test_20_content_extension_basics.py -q` passed
  with `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 21 Aegis-Spark Tutorial Thread

Chapter 21 now carries Chapter 20 content-pack thinking into learned magic. The
page explains that Field Focus was a condition/action/item/actor/scene pack,
then shows the same extension discipline applied to a feature that teaches a
spell, a spell action that enters discovery and execution, and an effect
condition that owns the ward left behind.

Changes made:

- Added a Chapter 20 content-pack-to-learned-magic bridge in the opening
  section so spell and feature extension is presented as a specialization of
  the content-pack pattern.
- Rebuilt the `Chapter Map` as a five-move Aegis Spark tutorial thread:
  inspect the public spell-feature module shape; let the feature grant and
  remove the spell template; discover self-or-ally targets; resolve the spell
  as a real `SpellEvent`; and compose the trained caster scene.
- Cleaned extra setup-panel whitespace in the public Chapter 21 snippets.
- Extended the public-content guard so Chapter 21 must keep the Chapter 20
  bridge and five-move Aegis Spark thread.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 21
  evidence.

Verification completed:

- `uv run pytest tests/manual/test_21_spell_and_feature_extensions.py -q`
  passed with `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 22 Gatehouse Tutorial Thread

Chapter 22 now carries Chapter 21 learned-content thinking into playable
scenario packaging. The page explains that Aegis Training, Aegis Spark, and the
effect condition were reusable authored content, then shows how a scenario
packages authored pieces into a startable room with map state, actors,
controllers, initiative, turn handoff, selected intent, combat logs, and an
ending rule.

Changes made:

- Added a Chapter 21 learned-content-to-playable-room bridge in the opening
  section so scenario packages are presented as the product boundary where
  authored content becomes a running room.
- Rebuilt the `Chapter Map` as a five-move Gatehouse scenario tutorial thread:
  import the scenario package; build the running Gatehouse scenario; advance to
  the human turn; execute the selected player action; and end the scene by
  faction survival.
- Cleaned extra setup-panel whitespace in the public Chapter 22 snippets.
- Extended the public-content guard so Chapter 22 must keep the Chapter 21
  bridge and five-move Gatehouse thread.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 22
  evidence.

Verification completed:

- `uv run pytest tests/manual/test_22_playable_scenario_packages.py -q`
  passed with `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 23 Standard-Arena Tutorial Thread

Chapter 23 now carries Chapter 22 Gatehouse scenario thinking into the built-in
reference game mode. The page explains that Gatehouse was one startable room
with package surface, encounter state, automated handoff, selected action
execution, and faction-survival ending, then shows how the standard arena uses
the same scenario shape with a richer board, class-selected hero kits,
monster-side roles, sessions, control modes, and client payloads.

Changes made:

- Added a Chapter 22 Gatehouse-scenario-to-standard-arena bridge in the opening
  section so the standard arena reads as the shipped reference mode built from
  scenario-package contracts.
- Rebuilt the `Chapter Map` as a six-move standard arena tutorial thread:
  import the arena mode surface; build the standard arena directly; select the
  hero kit; switch monster-side control; start human mode and join the hero;
  and read the live arena payloads.
- Cleaned extra setup-panel whitespace in the public Chapter 23 snippets.
- Extended the public-content guard so Chapter 23 must keep the Chapter 22
  bridge and six-move standard arena thread.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 23
  evidence.

Verification completed:

- `uv run pytest tests/manual/test_23_standard_arena_game_modes.py -q` passed
  with `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 24 Controller-Decision Tutorial Thread

Chapter 24 now carries Chapter 23 standard-arena thinking into turn decision
ownership. The page explains that the arena is the live mode with map, hero
kit, monster side, sessions, control modes, and client payloads, then zooms
into the active turn boundary where controllers decide whether play waits for
a person, waits for Codex, passes, selects a simple engine action, or hands one
complete turn to an agent runner.

Changes made:

- Added a Chapter 23 standard-arena-to-turn-ownership bridge in the opening
  section so controllers read as the decision layer inside a running mode.
- Rebuilt the `Chapter Map` as a seven-move controller-decision tutorial
  thread: import the controller catalogue; stop for human or Codex input; pass
  as the chosen turn behavior; choose a weapon attack; move toward a visible
  enemy; pass with an empty target list; and delegate a full turn to an agent
  runner.
- Cleaned extra setup-panel whitespace in the public Chapter 24 snippets.
- Extended the public-content guard so Chapter 24 must keep the Chapter 23
  bridge and seven-move controller-decision thread.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 24
  evidence.

Verification completed:

- `uv run pytest tests/manual/test_24_built_in_controllers.py -q` passed with
  `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 25 Live-Replication Tutorial Thread

Chapter 25 now carries Chapter 24 controller-decision thinking into stream
delivery. The page explains that human/Codex waiting, pass turns, melee AI
actions, empty-target pass behavior, and delegated agent turns produce durable
records after they resolve, then shows how event history and combat-log history
are delivered to browsers, tools, and agents through cursor-addressed frames.

Changes made:

- Added a Chapter 24 controller-decision-to-stream-delivery bridge in the
  opening section so live replication reads as the delivery layer for resolved
  turn choices.
- Rebuilt the `Chapter Map` as a seven-move live-replication tutorial thread:
  import the live stream surface; send a sync frame; replay from saved cursors;
  fan out live frames; release logs after completion; keep idle clients
  synchronized; and bound slow subscribers.
- Reframed stream ownership positively: rules, turns, and outcomes stay with
  the encounter and event engine while the stream publishes durable records.
- Cleaned extra setup-panel whitespace in the public Chapter 25 snippets.
- Extended the public-content guard so Chapter 25 must keep the Chapter 24
  bridge, seven-move stream thread, and positive ownership wording.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 25
  evidence.

Verification completed:

- `uv run pytest tests/manual/test_25_live_replication_streams.py -q` passed
  with `7 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 26 Agent-Tactical Tutorial Thread

Chapter 26 now carries Chapter 25 live-replication thinking into agent tactical
state. The page explains that replicated events, combat logs, cursors, and
heartbeats make the running encounter readable, then uses that same encounter
truth at decision time: a local agent receives one actor's subjective turn,
chooses from legal action rows, scores tactical options, and executes back
through the engine.

Changes made:

- Added a Chapter 25 live-replication-to-agent-state bridge in the opening
  section so the agent interface reads as the decision layer above synchronized
  play.
- Rebuilt the `Chapter Map` as a seven-move agent tactical tutorial thread:
  import the public tactical surface; read the actor snapshot; inspect legal
  action rows; ask tactical queries; score combat choices; execute one selected
  row; and wrap the turn in a minimal agent.
- Kept `reset_agent_interface_state()` explicit in the public page as a
  training-scene reset surface that clears registries, callbacks, encounters,
  controllers, and map state before examples.
- Cleaned extra setup-panel whitespace in the public Chapter 26 snippets.
- Extended the public-content guard so Chapter 26 must keep the Chapter 25
  bridge, seven-move tactical thread, tactical contract, and reset-surface
  explanation.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 26
  evidence.

Verification completed:

- `uv run pytest tests/manual/test_26_agent_tactical_interface.py -q` passed
  with `7 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 27 Agent-Decision Tutorial Thread

Chapter 27 now carries Chapter 26 tactical-state thinking into behavior
selection. The page explains that the tactical interface supplies visible
creatures, resources, legal action rows, target indexes, and combat math, then
shows how behavior trees, composites, and utility scoring turn that state into
legal engine choices.

Changes made:

- Added a Chapter 26 tactical-state-to-decision-behavior bridge in the opening
  section so decision patterns read as the behavior layer above the tactical
  snapshot.
- Rebuilt the `Chapter Map` as a seven-move behavior-selection tutorial
  thread: import the decision surface; run priority logic; use a factory
  behavior; chain a named tactic; detect board changes; rank action-target
  pairs; and run a utility agent.
- Reframed decision ownership positively: the decision layer gives designers a
  play-style language by selecting among permissions already exposed by
  tactical state.
- Kept `reset_agent_interface_state()` explicit in the public page as the
  inherited tactical-interface reset surface for decision scenes.
- Cleaned extra setup-panel whitespace in the public Chapter 27 snippets.
- Extended the public-content guard so Chapter 27 must keep the Chapter 26
  bridge, seven-move behavior-selection thread, positive decision-layer
  wording, decision contract, and reset-surface explanation.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 27
  evidence.

Verification completed:

- `uv run pytest tests/manual/test_27_agent_decision_patterns.py -q` passed
  with `7 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Public Prose Hygiene Guard

The public manual received a focused hygiene pass for internal artifact leaks
and stale negation-framed prose. The scan found no public references to
`engine_book`, note folders, pytest, parity records, fixtures, or internal
planning artifacts. The remaining useful edits were public-prose wording
changes where old sentences still explained a subsystem through contrast.

Changes made:

- Reframed Chapter 03 values so the engine positively owns both the final
  total and the rule path that produced it.
- Reframed Chapter 06 reactions as mutable event-time rule answers.
- Reframed Chapter 15 classes as authored character recipes.
- Reframed Chapter 23 standard arena as a shipped assembly of encounter, map,
  actors, controllers, sessions, and payloads.
- Reframed Chapter 24 controllers as the decision-supply layer while the
  encounter owns the authoritative game clock.
- Reframed Chapter 26 tactical scoring and interface prose so agents read
  decision data while validation, costs, events, and consequences remain
  engine-owned.
- Extended `PUBLIC_MANUAL_FORBIDDEN_PATTERNS` to block the retired phrases:
  `does not merely compute the total`, `A reaction is not after-the-fact
  commentary`, `not a parallel rules system`, `not just an encounter`,
  `controller never replaces the ruleset`, `without giving it direct control
  over engine internals`, and `expected damage without changing the rules`.
- Updated `engine_book/completion_matrix.md` so public note/meta hygiene is
  marked guarded for the current scope rather than complete for the whole
  manual goal.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- A direct `rg` scan for the retired phrases returned no public manual matches.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: SRD Rule Mapping Gate

The manual goal now has a concrete internal SRD relationship map instead of
only scattered chapter notes and public frontmatter labels. The map connects
each public chapter to the local SRD markdown under `interactive_ruleset/`,
records whether the chapter is `source-vocabulary`, `srd-aligned`,
`engine-adaptation`, or `product-extension`, and names the current videogame
ruleset policy points that should stay visible while writing.

Changes made:

- Added `engine_book/srd_rule_mapping.md` with one row for every public manual
  chapter from `00-neurodragon-dev-manual.mdx` through
  `27-agent-decision-patterns.mdx`.
- Mapped source-rule chapters to local files such as
  `interactive_ruleset/Gameplay/Abilities.md`,
  `interactive_ruleset/Gameplay/Combat.md`,
  `interactive_ruleset/Gamemastering/Conditions.md`,
  `interactive_ruleset/Equipment/Weapons.md`, spell files, class files, and
  monster files.
- Mapped product chapters such as sessions, map authoring, scenarios,
  controllers, streams, and agents as videogame systems built on SRD-shaped
  play rather than new tabletop rules.
- Recorded policy points that previously caused confusion: single videogame
  ruleset, no parallel SRD/BG3 profiles, BG3-style Shove, voluntary versus
  forced movement reactions, separate melee/ranged loadouts, additive
  advantage state, Great Weapon Fighting source text, and faction-survival
  encounter ending.
- Added `tests/engine_book/test_srd_rule_mapping.py` to verify every public
  chapter has exactly one mapping row, every frontmatter rule touchpoint is
  repeated in the mapping, every referenced `interactive_ruleset/` path exists,
  and the key policy phrases remain explicit.
- Updated `engine_book/completion_matrix.md` so D&D/SRD relationship mapping
  is now `mapped-for-current-scope`, with public editorial visibility still
  called out as unfinished.

Verification completed:

- `uv run pytest tests/engine_book/test_srd_rule_mapping.py -q` passed with
  `4 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.

## Checkpoint: Public SRD Ruleset Anchor

The public manual now exposes the SRD relationship policy in Chapter 00 instead
of keeping it only in internal mapping files. The orientation chapter explains
that the local SRD markdown is the source-reference corpus for Dungeons &
Dragons vocabulary and procedures, while NeuroDragon implements one coherent
videogame ruleset.

Changes made:

- Expanded Chapter 00's `One Videogame Ruleset` section to name local SRD
  markdown as the source-reference corpus for ability scores, d20 rolls,
  advantage, saves, conditions, weapons, armor, actions, turns, spells,
  monsters, and encounter structure.
- Added a public relationship table for `Source vocabulary`, `SRD-shaped
  behavior`, `Engine adaptation`, and `Product extension`, so readers can
  understand how chapters relate to source rules without opening internal
  planning notes.
- Expanded the policy table with the chosen videogame/BG3-style Shove,
  voluntary versus forced movement timing, separate melee/ranged loadouts,
  advantage state through the value ledger, Great Weapon Fighting source text,
  and faction-survival encounter ending.
- Extended the Chapter 00 public-content guard in
  `tests/book_examples/test_public_mdx_snippets.py` so the SRD anchor and
  policy table stay visible in the public orientation.
- Updated `engine_book/completion_matrix.md` from `mapped-for-current-scope` to
  `mapped-and-publicly-anchored`, while keeping per-chapter SRD visibility as
  unfinished.

Verification completed:

- `uv run pytest tests/engine_book/test_srd_rule_mapping.py -q` passed with
  `4 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `222 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: High-Risk Public SRD Policy Sections

The public manual now teaches source-rule relationship policy inside the
chapters where ruleset confusion is most likely to matter: values, dice,
movement, combat, equipment, and encounters. These sections translate the
internal SRD mapping into reader-facing prose while preserving one videogame
ruleset.

Changes made:

- Added `Source Rule Relationship` to Chapter 03, explaining SRD-shaped ability
  modifiers, checks, saves, advantage/disadvantage, damage responses, and the
  engine's inspectable value ledger.
- Added `Source Rule Relationship` to Chapter 04, explaining SRD-shaped d20 and
  damage rolls plus the Great Weapon Fighting source-text choice.
- Added `Source Rule Relationship` to Chapter 08, explaining movement,
  difficult terrain, spaces, borders, voluntary movement, forced movement, and
  opportunity-attack timing.
- Added `Source Rule Relationship` to Chapter 10, explaining combat vocabulary,
  the one combat pipeline, and the chosen videogame/BG3-style Shove behavior.
- Added `Source Rule Relationship` to Chapter 11, explaining SRD equipment
  vocabulary and the videogame loadout adaptation with separate melee and
  ranged sets.
- Added `Source Rule Relationship` to Chapter 17, explaining SRD initiative,
  rounds, turns, and the videogame faction-survival encounter ending policy.
- Added a public-content guard that verifies these six high-risk chapters keep
  their source-rule sections before examples and preserve the key policy
  phrases.
- Updated `engine_book/completion_matrix.md` from
  `mapped-and-publicly-anchored` to
  `mapped-and-high-risk-publicly-visible`, while leaving full per-chapter SRD
  editorial review open.

Verification completed:

- `uv run pytest tests/engine_book/test_srd_rule_mapping.py -q` passed with
  `4 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `223 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Core Public SRD Relationship Sections

The source-rule relationship is now visible across the full core rules arc,
not only in the policy-sensitive chapters. Chapters 01-17 now teach how their
D&D/SRD source material becomes NeuroDragon runtime truth before presenting the
chapter map, code surfaces, or executable examples.

Changes made:

- Added `Source Rule Relationship` to Chapter 01, explaining runtime identity
  as source vocabulary for actors, targets, items, spells, conditions, events,
  and logs.
- Added `Source Rule Relationship` to Chapter 02, explaining how SRD creature
  vocabulary becomes a composed `Entity` surface.
- Added `Source Rule Relationship` to Chapter 05, explaining how D&D
  procedures become event lineages.
- Added `Source Rule Relationship` to Chapter 06, explaining reaction timing,
  opportunity attacks, reaction spells, and the completion/log boundary.
- Added `Source Rule Relationship` to Chapter 07, explaining conditions as
  owned runtime packages for modifiers, handlers, subconditions, linked
  conditions, spatial handlers, and cleanup.
- Added `Source Rule Relationship` to Chapter 09, explaining actions, bonus
  actions, reactions, movement, object interaction, and the command-menu
  adaptation.
- Added `Source Rule Relationship` to Chapters 12-16, covering perception,
  spellcasting, spell families, class/feat content, monsters, and preset
  actors.
- Added `test_core_rule_chapters_explain_srd_relationship` to
  `tests/book_examples/test_public_mdx_snippets.py`, proving these sections
  stay before chapter maps, source surfaces, and examples while preserving
  required public phrases.
- Updated `engine_book/completion_matrix.md` so D&D/SRD mapping is now
  `mapped-and-core-publicly-visible`; Chapters 01-17 are marked
  `publicly-visible-current-scope` for their D&D/SRD relationship cells.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `224 passed`.
- `uv run pytest tests/engine_book/test_srd_rule_mapping.py -q` passed with
  `4 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Product Extension Public Rule Relationship Sections

The product/game-mode chapters now explain how their systems extend
SRD-shaped play instead of presenting sessions, maps, content packs,
scenarios, arenas, controllers, streams, and agents as detached technical
surfaces. Chapter 00 carries the global source-reference policy; Chapters
01-17 now cover source-rule engine behavior; Chapters 18-27 now cover product
extensions layered on the one videogame ruleset.

Changes made:

- Added `Source Rule Relationship` to Chapter 18, explaining sessions, APIs,
  payloads, action rows, execution requests, cursors, and catalogs as the
  client contract over authoritative turns and results.
- Added `Source Rule Relationship` to Chapter 19, explaining MapEditor as the
  entity-free authoring boundary for tactical spaces, tiles, borders, lights,
  placed objects, objective layers, saves, and loads.
- Added `Source Rule Relationship` to Chapter 20, explaining content packs as
  authored composition of value, event, condition, item, action, and
  perception systems.
- Added `Source Rule Relationship` to Chapter 21, explaining feature-granted
  spells through Aegis Training and Aegis Spark.
- Added `Source Rule Relationship` to Chapter 22, explaining playable scenario
  packages as reusable game modes with map state, actors, factions,
  controllers, encounter start, action execution, logs, and faction-survival
  ending.
- Added `Source Rule Relationship` to Chapter 23, explaining the standard
  arena as a product package over the combat loop.
- Added `Source Rule Relationship` to Chapter 24, explaining controllers as
  automated turn ownership that chooses legal engine-authored rows.
- Added `Source Rule Relationship` to Chapter 25, explaining live replication
  as cursor and frame delivery over the authoritative event and combat-log
  timeline.
- Added `Source Rule Relationship` to Chapter 26, explaining tactical state as
  the agent-facing decision surface over legal actions, target rows, resources,
  perception, and combat math.
- Added `Source Rule Relationship` to Chapter 27, explaining behavior trees,
  composites, interruption checks, utility scoring, and reusable agents as
  decision patterns over legal engine action rows.
- Added `test_product_extension_chapters_explain_srd_relationship` to
  `tests/book_examples/test_public_mdx_snippets.py`, proving Chapters 18-27
  keep those sections before chapter maps, source surfaces, and examples.
- Updated `engine_book/completion_matrix.md` so D&D/SRD mapping is now
  `mapped-and-publicly-visible-current-scope`; Chapters 18-27 are marked with
  public current-scope visibility for SRD/product-extension relationship.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `225 passed`.
- `uv run pytest tests/engine_book/test_srd_rule_mapping.py -q` passed with
  `4 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Architecture Surface Classification Audit

The newer scenario, arena, controller, live-stream, MapEditor, and agent
surfaces now have an explicit internal classification instead of being treated
as final architecture by inertia. The audit separates core engine architecture,
product/game-mode architecture, public tutorial support, generated/cache
output, and risky surfaces that need review.

Changes made:

- Added `engine_book/architecture_surface_audit.md`.
- Classified `dnd.controller` as core engine architecture for encounter turn
  ownership.
- Classified `dnd.maps.arena_layout`, `server.event_stream`,
  `server.event_server` arena routes, `server.mapeditor_support`,
  `server.api_models` MapEditor schemas, MapEditor itself, and the stable parts
  of the AI package as product/game-mode architecture.
- Classified `dnd.scenarios.gatehouse`, controller catalogue scenes, agent
  training scenes, `server.arena_mode`, and `server.live_replication` scene
  helpers as public tutorial support or mixed product/tutorial surfaces.
- Classified `data/mapeditor/maps/*.json` and MapEditor build/generated/cache
  directories as generated/cache output to remove or curate with approval.
- Flagged risks: `ai/interface.py` late imports, MapEditor catalog references
  to `dnd.items.test_items`, tutorial scenes living under `dnd.scenarios`, the
  large `server/event_server.py` route monolith, local saved map JSON output,
  and remaining AI docstring/comment/Pydantic hygiene gaps.
- Added `tests/engine_book/test_architecture_surface_audit.py` to verify the
  audit defines required labels, covers required surfaces, and preserves known
  risks.
- Updated `engine_book/completion_matrix.md` so architecture classification is
  `classified-with-risks-current-scope` and the architecture audit queue names
  concrete decisions instead of generic `needs-audit` placeholders.

Verification completed:

- `uv run pytest tests/engine_book/test_architecture_surface_audit.py -q`
  passed with `3 passed`.
- `uv run pytest tests/engine_book/test_srd_rule_mapping.py -q` passed with
  `4 passed`.

## Checkpoint: AI Local Interface Adapter Boundary

The agent tactical interface now has a cleaner dependency boundary. The public
`LocalGameInterface` adapter still lives in `ai.interface`, but it no longer
uses function-local engine imports. It imports D&D engine dependencies at
module scope, translates live `Entity` state into `TacticalState`, and routes
selected template/index rows through `execute_by_index`.

Changes made:

- Rewrote `ai/interface.py` with module-scope imports for `Entity`,
  `execute_by_index`, `BaseObject`, `AvailableActionInfo`, `ActionCategory`,
  `TargetType`, `WeaponSlot`, and `spell_slot_cost_type`.
- Split the large tactical-state method into explicit adapter helpers for
  visible entity snapshots, action economy, threat state, spell slots,
  resources, action grouping, HP maximums, and action-row conversion.
- Removed the old function-local imports from `get_tactical_state()`,
  `execute()`, and `_info_to_action_option()`.
- Added `test_local_game_interface_uses_top_level_engine_imports` to
  `tests/manual/test_26_agent_tactical_interface.py`, which parses
  `ai.interface` and fails if imports appear inside functions.
- Updated `engine_book/architecture_surface_audit.md` so
  `ai.interface.LocalGameInterface` is classified as product/game-mode
  architecture rather than a risky adapter needing dependency-boundary review.
- Updated `engine_book/completion_matrix.md` so the agent tactical interface
  risk is now metadata/comment/docstring/expected-value hygiene, not late
  imports.

Verification completed:

- `uv run pytest tests/manual/test_26_agent_tactical_interface.py -q` passed
  with `8 passed`.
- `uv run pytest tests/manual/test_27_agent_decision_patterns.py -q` passed
  with `7 passed`.

## Checkpoint: AI Tactical Model Metadata Hygiene

The agent-facing tactical model contract now matches the manual goal's code
quality bar for Pydantic model metadata. This covers the public data shapes
used by Chapter 26 and Chapter 27 examples; it does not yet complete the
broader AI primitive and example-agent hygiene pass.

Changes made:

- Rewrote `ai/models.py` so the tactical Pydantic models use explicit
  `Field(description=...)` metadata for every public field.
- Converted useful explanations to Google-style docstrings and removed casual
  inline comments from `ai.models`.
- Preserved compatibility defaults for `SpellData.spell_level` and
  `ActionEconomy` budgets after the metadata rewrite.
- Kept expected-value functions documented as agent scoring heuristics rather
  than authoritative engine combat resolution.
- Added `test_tactical_models_use_public_field_descriptions` to
  `tests/manual/test_26_agent_tactical_interface.py`, which guards field
  descriptions, compatibility defaults, and the no-inline-comment policy for
  `ai.models`.
- Updated `engine_book/architecture_surface_audit.md` and
  `engine_book/completion_matrix.md` so the remaining AI risk is primitive and
  agent hygiene, not tactical model metadata.

Verification completed:

- `uv run pytest tests/manual/test_26_agent_tactical_interface.py -q` passed
  with `9 passed`.
- `uv run pytest tests/manual/test_27_agent_decision_patterns.py -q` passed
  with `7 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `225 passed`.
- `uv run pytest tests/engine_book/test_architecture_surface_audit.py -q`
  passed with `3 passed`.

## Checkpoint: AI Decision Primitive Hygiene

The decision-layer code used by Chapter 27 now matches the manual goal's code
quality bar for the current public agent surface. Behavior trees, state
machines, utility scoring, composites, and agent runners keep their public
names and behavior while replacing comment scaffolding with docstrings and
explicit contracts.

Changes made:

- Rewrote `ai/primitives/behavior_tree.py` with Google-style docstrings,
  explicit predicate/action type aliases, and no inline comment scaffolding.
- Rewrote `ai/primitives/state_machine.py` with `ANY_STATE` for global
  transitions and documented context, state, transition, and machine behavior.
- Rewrote `ai/primitives/utility.py` with documented scorers and
  `Field(description=...)` metadata for `ScoredOption`.
- Rewrote `ai/composites.py` with documented interrupt detection and
  `Field(description=...)` metadata for `CompositeResult`.
- Rewrote `ai/agents/base.py`, `ai/agents/examples.py`, and `ai/__init__.py`
  to remove comment scaffolding while preserving existing public function
  names and turn-loop behavior.
- Added `test_decision_layer_uses_docstrings_and_field_descriptions` to
  `tests/manual/test_27_agent_decision_patterns.py`, guarding no inline
  comments or ellipsis stubs across the public decision-layer modules,
  preserving `MAX_TURN_ITERATIONS` and `ANY_STATE`, and requiring Pydantic
  field descriptions for decision-layer models.
- Updated `engine_book/architecture_surface_audit.md` and
  `engine_book/completion_matrix.md` so the remaining agent risk is
  expected-value policy and future behavior coverage, not current primitive
  comment/docstring/Pydantic hygiene.

Verification completed:

- `uv run pytest tests/manual/test_27_agent_decision_patterns.py -q` passed
  with `8 passed`.
- `uv run pytest tests/manual/test_26_agent_tactical_interface.py -q` passed
  with `9 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `225 passed`.
- `uv run pytest tests/engine_book/test_architecture_surface_audit.py -q`
  passed with `3 passed`.
- `uv run python examples/ai/test_ai_framework.py` passed.
- `uv run pytest examples/ai/test_ai_framework.py -q` passed with
  `10 passed`.

## Checkpoint: Agent Chapter Source Anchor Repair

After the AI tactical and decision-layer rewrites, the public Chapter 26 and
Chapter 27 source tables needed to be reconciled with the new local symbol
locations. The tables still link to the current branch on GitHub, but now the
line anchors are guarded against drifting away from the public symbol names.

Changes made:

- Updated Chapter 26 source-table anchors for `LocalGameInterface`,
  `TacticalState`, `ActionOption`, `TargetOption`, `hit_chance`,
  `crit_chance`, `attack_ev`, `action_ev`, and `BaseAgent`.
- Updated Chapter 27 source-table anchors for behavior-tree nodes, composites,
  tactical models, the local game interface, ready behavior constructors,
  utility scorers, and `UtilityAgent`.
- Added `test_ai_code_surface_anchors_point_to_named_symbols` to
  `tests/book_examples/test_public_mdx_snippets.py`. The guard resolves each
  audited AI GitHub source link back to the local file and verifies that the
  linked line is a `class` or `def` for one of the symbols shown in the table
  row.
- Updated `engine_book/completion_matrix.md` so the public MDX suite evidence
  records `226 passed` and the source-anchor guard.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `226 passed`.
- `uv run pytest tests/manual/test_26_agent_tactical_interface.py -q` passed
  with `9 passed`.
- `uv run pytest tests/manual/test_27_agent_decision_patterns.py -q` passed
  with `8 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Foundation Helper Docstrings

The helper-opacity pass has started from the bottom of the public manual.
Chapters 01-06 now require public tutorial helper definitions to explain
themselves inside the executable code, not only in surrounding prose.

Changes made:

- Added docstrings to the Chapter 02 `create_tutorial_hero()` helper.
- Added docstrings to Chapter 03's `ability_score_normalizer()` and
  `high_ground_bonus()` helper functions.
- Added docstrings to Chapter 05's `TutorialLogEvent` and `remember_event()`.
- Added docstrings to Chapter 06 event processors:
  `alarm_processor()`, `effect_processor()`, `completion_processor()`,
  `ward_processor()`, `later_processor()`, `focus_processor()`,
  `thorn_processor()`, and `opportunity_like_processor()`.
- Added `HELPER_DOCSTRING_AUDITED_CHAPTERS` and
  `test_audited_public_helpers_have_docstrings` to
  `tests/book_examples/test_public_mdx_snippets.py`. The guard currently
  covers Chapters 01-06 and fails when a public `book-example` Python fence
  defines a top-level `def` or `class` without a docstring.
- Updated `engine_book/completion_matrix.md` so the public MDX suite evidence
  records `227 passed` and helper-opacity status names the staged Chapters
  01-06 guard.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_audited_public_helpers_have_docstrings -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `227 passed`.
- `uv run pytest tests/manual/test_02_entity_anatomy.py tests/manual/test_03_values_and_modifiers.py tests/manual/test_05_event_lifecycle.py tests/manual/test_06_reactions_to_events.py -q`
  passed with `19 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Gameplay Helper Docstrings

The helper-opacity pass now covers the next bottom-up gameplay band. Chapters
07-12 still use visible setup helpers inside the public MDX snippets, but those
helpers now explain the tutorial state they create before they mutate runtime
registries, build actors, create loadouts, or collect sensory events.

Changes made:

- Added docstrings to Chapter 09 action setup helpers:
  `reset_action_state()`, `create_tutorial_actor()`, `find_action()`, and
  `find_attack_action()`.
- Added docstrings to Chapter 10 combat setup helpers:
  `reset_combat_tutorial_state()`, `make_melee_attack_auto_hit()`,
  `make_melee_attack_auto_crit()`, `clear_melee_attack_modifier()`, and
  `create_strong_actor()`.
- Added docstrings to Chapter 11 item and loadout helpers:
  `reset_item_tutorial_state()`, `create_tutorial_actor()`,
  `put_in_inventory()`, and `create_tutorial_hand_crossbow()`.
- Added docstrings to Chapter 12 perception helpers:
  `reset_perception_tutorial_state()`, `create_perception_actor()`, and
  `completed_sensory_updates()`.
- Extended `HELPER_DOCSTRING_AUDITED_CHAPTERS` in
  `tests/book_examples/test_public_mdx_snippets.py` to cover Chapters 07-12.
- Updated `engine_book/completion_matrix.md` so the exact public snippet
  evidence and visible-import/helper-opacity status reflect the Chapters 01-12
  guard.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_audited_public_helpers_have_docstrings -q`
  passed with `1 passed`.
- `uv run pytest tests/manual/test_07_conditions_and_cleanup.py tests/manual/test_08_world_model_and_movement.py tests/manual/test_09_action_discovery_and_costs.py tests/manual/test_10_combat_resolution.py tests/manual/test_11_equipment_inventory_and_items.py tests/manual/test_12_perception_light_stealth_and_invisibility.py -q`
  passed with `32 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `227 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Full Manual Helper Docstring Guard

The helper-opacity guard now covers the full current public manual. Every
top-level `def` or `class` defined inside an executable public Python
`book-example` fence from Chapters 01-27 must explain itself with a docstring.
This does not finish the editorial rewrite, but it closes one specific failure
mode: public examples can no longer introduce helper surfaces as unexplained
test-style plumbing.

Changes made:

- Added tutorial-facing docstrings to Chapter 13 spellcasting helpers:
  `reset_spell_tutorial_state()`, `create_spell_actor()`, and `find_action()`.
- Added docstrings to Chapter 14 spell-family helpers:
  `reset_spell_family_state()`, `create_spell_family_actor()`,
  `penalize_saving_throw()`, `set_current_normal_hp()`, and
  `assert_completed_spell()`.
- Added docstrings to Chapter 15 class-feature helpers:
  `reset_class_feature_state()`, `create_feature_target()`, and
  `make_d20_event()`.
- Added docstrings to Chapter 16 monster helper surfaces:
  `reset_monster_preset_state()`, `action_template_names()`,
  `equipped_item_name()`, `has_darkvision()`, `get_inventory_item()`, and
  `inventory_item_names()`.
- Added docstrings to Chapter 17 encounter helpers:
  `RecordingController`, `reset_encounter_tutorial_state()`,
  `create_encounter_pair()`, `start_ordered_encounter()`,
  `make_melee_attack_auto_hit()`, `clear_melee_attack_modifier()`, and
  `listener()`.
- Added docstrings to Chapter 18 API helpers:
  `ApiClient`, `reset_client_api_state()`, `create_api_pair()`,
  `start_api_game()`, `create_session_and_join_hero()`,
  `create_joined_client_game()`, `make_melee_attack_auto_hit()`,
  `clear_melee_attack_modifier()`, `attack_target_index()`, and
  `execute_manual_attack()`.
- Added docstrings to Chapter 19 MapEditor helpers:
  `ApiClient`, `reset_map_authoring_state()`, `tile_at()`,
  `layer_cell()`, `create_authoring_client()`,
  `create_tutorial_editor_map()`, `patch_tutorial_room()`, and
  `place_tutorial_objects()`.
- Added docstrings to Chapter 20 and 21 reset helpers:
  `reset_content_extension_state()` and `reset_spell_feature_state()`.
- Extended `HELPER_DOCSTRING_AUDITED_CHAPTERS` in
  `tests/book_examples/test_public_mdx_snippets.py` to include Chapters 13-27,
  so all current public manual chapters from 01-27 are guarded.
- Replaced the new API client docstring wording from `Tiny in-process...` to
  `In-process...` after the public meta-language guard caught the banned term.
- Updated `engine_book/completion_matrix.md` so the exact snippet and visible
  helper evidence reflect Chapters 01-27 coverage.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_audited_public_helpers_have_docstrings -q`
  passed with `1 passed`.
- `uv run pytest tests/manual/test_13_spellcasting_core.py tests/manual/test_14_spell_families.py tests/manual/test_15_class_features.py tests/manual/test_16_monsters_preset_actors.py tests/manual/test_17_encounters_turns_controllers.py tests/manual/test_18_sessions_api_client_contract.py tests/manual/test_19_map_editor_scenario_authoring.py tests/manual/test_20_content_extension_basics.py tests/manual/test_21_spell_and_feature_extensions.py -q`
  passed with `49 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `227 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Code Surface Source Link Resolution Guard

The Code Surfaces tables now have a stronger proof layer. Runtime import rows
already needed branch-pinned GitHub source links; the public snippet suite now
also resolves those links back to the local worktree and fails if a link points
to a missing file, an out-of-range line, or a blank line. This protects the
reader-facing source map from drifting into decorative or stale links.

Changes made:

- Corrected stale Code Surfaces anchors in Chapters 22-27 after recent
  tutorial/product support modules shifted line numbers:
  `dnd.scenarios.gatehouse`, `server.arena_mode`,
  `dnd.scenarios.controller_catalogue`, `server.live_replication`, and
  `dnd.scenarios.agent_tactical_training`.
- Added `test_code_surface_source_links_resolve_to_local_lines` to
  `tests/book_examples/test_public_mdx_snippets.py`.
- The new guard resolves all audited `https://github.com/furlat/dnd_engine/...`
  Code Surfaces links against the local repository and verifies the anchored
  line is present and nonblank.
- Updated `engine_book/completion_matrix.md` so the exact public snippet
  evidence records `228 passed` and the visible import/source-surface status
  names local-line anchor resolution.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_code_surface_source_links_resolve_to_local_lines tests/book_examples/test_public_mdx_snippets.py::test_audited_code_surfaces_link_to_repo_source tests/book_examples/test_public_mdx_snippets.py::test_ai_code_surface_anchors_point_to_named_symbols -q`
  passed with `3 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `228 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Public Webbook Parity Matrix Guard

The internal parity matrix now names the current Astro webbook as the
reader-facing source of executable examples. The older engine-book component
matrix remains as deep subsystem and legacy-example coverage history, but the
public MDX exact-snippet parity layer is now explicit and guarded.

Changes made:

- Added a `Public Webbook Exact-Snippet Parity` section to
  `engine_book/parity_matrix.md`.
- Recorded every current public manual chapter from
  `00-neurodragon-dev-manual.mdx` through
  `27-agent-decision-patterns.mdx`.
- Listed every current public `book-example` name from
  `tests/book_examples/test_public_mdx_snippets.py` in that parity section.
- Added `test_parity_matrix_tracks_public_webbook_examples` to
  `tests/book_examples/test_public_mdx_snippets.py`, so adding, removing, or
  renaming a public MDX example now requires the parity matrix to follow.
- Updated `engine_book/completion_matrix.md` and this rebuild plan to record
  the new 229-test evidence count.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_parity_matrix_tracks_public_webbook_examples -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `229 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Visible Body Assertion Guard

The exact public snippet suite now proves that examples teach behavior in the
visible tutorial body, not only inside the collapsed setup panel. This closes a
specific loophole in the manual goal: an example cannot satisfy parity by
placing all meaningful checks inside import/setup code while the reader sees a
body that only calls opaque setup.

Changes made:

- Added `example_body_source()` to
  `tests/book_examples/test_public_mdx_snippets.py`.
- Added `test_book_examples_assert_visible_body_behavior`, which requires each
  assembled public `book-example` to contain at least one `assert` in fences
  marked `part="body"`.
- Updated `engine_book/completion_matrix.md` and
  `engine_book/parity_matrix.md` so current exact-snippet evidence records the
  new 230-test proof layer.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_book_examples_assert_visible_body_behavior -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `230 passed`.

## Checkpoint: Tutorial Product Source Anchor Guard

The Code Surfaces source-link guard now checks the tutorial/product helper
rows that support the later manual chapters. A source row for scenario, arena,
live-replication, or public controller helpers must land on the actual
`def`/`class` line for the symbol named in the row, not merely on a nonblank
line in the right file. This tightens the reader-facing contract for the
manual's newer product surfaces.

Changes made:

- Added
  `test_tutorial_product_code_surface_anchors_point_to_named_symbols` to
  `tests/book_examples/test_public_mdx_snippets.py`.
- Corrected stale Code Surfaces anchors in Chapters 22-25 for
  `dnd.scenarios.gatehouse`, `server.arena_mode`,
  `dnd.scenarios.controller_catalogue`, `server.live_replication`, and
  `dnd.scenarios.agent_tactical_training`.
- Corrected Chapter 27's deterministic combat-helper imports so public
  snippets import `make_melee_attack_auto_hit()` and
  `clear_melee_attack_modifier()` from
  `dnd.scenarios.agent_tactical_training`, matching the source table.
- Updated `engine_book/completion_matrix.md` and
  `engine_book/parity_matrix.md` so current exact-snippet evidence records the
  new 231-test proof layer.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_runtime_imports_used_by_examples_are_introduced tests/book_examples/test_public_mdx_snippets.py::test_tutorial_product_code_surface_anchors_point_to_named_symbols -q`
  passed with `2 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `231 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 03 Modifier Placement Guide

Chapter 03 now teaches where a designer should place a value rule before it
starts the examples. The new `Modifier Placement Guide` sits after the six
value channels and before `Score And Normalized Score`, mapping authored
rules to `self_static`, `self_contextual`, target-facing channels,
`set_from_target(...)`, combined values, and breakdown APIs.

Changes made:

- Added `## Modifier Placement Guide` to the public Chapter 03 page.
- Explained that conditions, items, spells, class features, terrain effects,
  and monster abilities should add named modifiers to the value that owns the
  rule relationship.
- Extended `test_values_chapter_frontloads_product_math_bridge` so it checks
  the guide appears in the teaching order before the first example.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 03
  evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_values_chapter_frontloads_product_math_bridge -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "03-values-and-modifiers" -q`
  passed with `4 passed, 144 deselected`.
- `uv run pytest tests/manual/test_03_values_and_modifiers.py -q` passed with
  `4 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `233 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Typed Reset Helpers In Public Tutorial Snippets

The public tutorial reset helpers now use explicit dimension and return
annotations wherever a snippet exposes `width` and `height` defaults. This
keeps setup code in the customer-facing manual aligned with the professional
tutorial style used by the earlier chapters: the helper is still visible, but
its signature reads as deliberate tutorial code rather than loose test glue.

Changes made:

- Updated Chapter 18's repeated `reset_client_api_state(...)` definitions to
  use `width: int = 16`, `height: int = 10`, and `-> None`.
- Updated Chapter 20's repeated `reset_content_extension_state(...)`
  definitions to use `width: int = 8`, `height: int = 6`, and `-> None`.
- Updated Chapter 21's repeated `reset_spell_feature_state(...)` definitions
  to use `width: int = 8`, `height: int = 6`, and `-> None`.
- Added
  `tests/book_examples/test_public_mdx_snippets.py::test_public_reset_helpers_use_typed_dimensions`
  so public reset helpers with `width` or `height` defaults keep explicit
  parameter and return annotations.
- Updated `engine_book/completion_matrix.md` with the refreshed public-snippet
  evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_reset_helpers_use_typed_dimensions tests/book_examples/test_public_mdx_snippets.py::test_sessions_chapter_frontloads_client_contract tests/book_examples/test_public_mdx_snippets.py::test_content_extension_chapter_frontloads_extension_contract tests/book_examples/test_public_mdx_snippets.py::test_spell_feature_chapter_frontloads_spell_feature_contract -q`
  passed with `4 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "18-sessions-apis-and-client-payloads or 20-content-extension-basics or 21-spell-and-feature-extensions" -q`
  passed with `16 passed, 132 deselected`.
- `uv run pytest tests/manual/test_18_sessions_api_client_contract.py tests/manual/test_20_content_extension_basics.py tests/manual/test_21_spell_and_feature_extensions.py -q`
  passed with `16 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `234 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 06 Reaction Authoring Guide

Chapter 06 now presents reaction timing as an authoring decision before the
examples. The `Reaction Authoring Guide` now sits after the reaction contract
and before the code-surface table, mapping timed rules to event handlers,
result events, spatial handlers, voluntary step movement, and forced movement.

Changes made:

- Renamed and sharpened the public Chapter 06 surface-selection section as
  `## Reaction Authoring Guide`.
- Reframed the table as `Rule being authored | Use this surface | Result`.
- Preserved the important movement policy: opportunity-style reactions listen
  to voluntary `STEP_MOVEMENT`, while `FORCED_MOVEMENT` remains separate even
  though it can update spatial state.
- Extended `test_reactions_chapter_frontloads_timing_contract` so it checks the
  reaction contract appears before the guide and the guide appears before the
  code-surface table and first example.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 06
  evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_reactions_chapter_frontloads_timing_contract -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "06-reactions-to-events" -q`
  passed with `6 passed, 142 deselected`.
- `uv run pytest tests/manual/test_06_reactions_to_events.py -q` passed with
  `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `233 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 05 Event Authoring Guide

Chapter 05 now teaches how to author an event lineage before it introduces
import paths or phase examples. The `Event Authoring Guide` sits before the
Code Surfaces table, mapping authored game moments to declaration, execution,
effect, cancellation, child events, completion narration, and passive
observation.

Changes made:

- Moved `## Event Authoring Guide` before the public Chapter 05 Code Surfaces
  table.
- Explained that values own rule numbers, dice own roll results, and events
  own the cause-and-effect record that turns those local results into a game
  moment.
- Extended `test_event_chapter_frontloads_product_timeline_bridge` so it checks
  the guide appears before Code Surfaces and before the first example.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 05
  evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_event_chapter_frontloads_product_timeline_bridge -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "05-event-lifecycle" -q`
  passed with `5 passed, 143 deselected`.
- `uv run pytest tests/manual/test_05_event_lifecycle.py -q` passed with
  `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `233 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 04 Roll Record Guide

Chapter 04 now teaches how to author a roll record before it starts the
examples. The new `Roll Record Guide` sits after the Code Surfaces table and
before the first d20 walkthrough, mapping authored roll moments to the value
ledger, `RollType`, d20 expressions, damage expressions, cached `DiceRoll`
records, and deterministic walkthrough faces.

Changes made:

- Added `## Roll Record Guide` to the public Chapter 04 page.
- Explained that value modifiers own bonus and roll-state changes, dice
  expressions own uncertainty, damage expressions carry `AttackOutcome`, and
  the produced `DiceRoll` is the shared record for events, combat, display,
  and later rule processors.
- Extended `test_dice_chapter_frontloads_product_roll_bridge` so it checks the
  guide appears after Code Surfaces and before the first example.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 04
  evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_dice_chapter_frontloads_product_roll_bridge -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "04-dice-rolls" -q`
  passed with `5 passed, 143 deselected`.
- `uv run pytest tests/manual/test_04_dice_rolls.py -q` passed with
  `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `233 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Defined-In-Chapter Symbol Parity Guard

The public source-table contract now proves that chapter-defined symbols are
real public setup code. A name listed under `Defined in this chapter` must be
declared in the chapter's `Code setup: imports and scene` Python, and every
function or class declared in those setup panels must appear in a
`Defined in this chapter` source-table row.

Changes made:

- Added `defined_in_chapter_symbols()` to
  `tests/book_examples/test_public_mdx_snippets.py`.
- Strengthened `test_all_import_panel_local_definitions_are_introduced` so it
  requires local definitions to appear specifically in `Defined in this
  chapter` source rows.
- Added `test_defined_in_chapter_symbols_are_import_panel_definitions` so the
  source table cannot claim a chapter-defined symbol that is not actually
  defined in public setup code.
- Updated `engine_book/completion_matrix.md` and
  `engine_book/parity_matrix.md` so the current proof layer records the new
  233-test evidence count.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_all_import_panel_local_definitions_are_introduced tests/book_examples/test_public_mdx_snippets.py::test_defined_in_chapter_symbols_are_import_panel_definitions tests/book_examples/test_public_mdx_snippets.py::test_visible_local_names_used_by_examples_are_introduced -q`
  passed with `3 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `233 passed`.
- No Astro build was required for this checkpoint because only the verification
  and tracking files changed.

## Checkpoint: Reader-Facing Defined-In-Chapter Descriptions

The `Defined in this chapter` source-table rows now describe what their symbols
do directly. They no longer begin their descriptions with `Local ...`, which
made public tutorial symbols feel like scaffolding rather than part of the
manual's taught code surface.

Changes made:

- Rewrote `Defined in this chapter` Code Surfaces descriptions in Chapters 01,
  02, and 07-21 so rows begin with the runtime role: scene objects, actor
  factories, reset paths, readers, controllers, combat controls, API scene
  builders, and authoring clients.
- Added
  `test_defined_in_chapter_rows_use_reader_facing_descriptions` to
  `tests/book_examples/test_public_mdx_snippets.py`.
- Updated `engine_book/completion_matrix.md` and
  `engine_book/parity_matrix.md` so the current exact-snippet evidence records
  the new 232-test proof layer.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_defined_in_chapter_rows_use_reader_facing_descriptions tests/book_examples/test_public_mdx_snippets.py::test_public_manual_avoids_internal_meta_language tests/book_examples/test_public_mdx_snippets.py::test_visible_local_names_used_by_examples_are_introduced tests/book_examples/test_public_mdx_snippets.py::test_all_import_panel_local_definitions_are_introduced -q`
  passed with `4 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `232 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Reader-Facing Local Symbol Labels

The public Code Surfaces tables no longer describe locally defined tutorial
symbols with internal `Chapter-local example code` wording. The rows now use
the reader-facing label `Defined in this chapter`, while the row description
and the Code setup panel explain what each local symbol builds or reads. This
keeps local scene constructors visible without making the public manual sound
like a test inventory.

Changes made:

- Replaced `Chapter-local example code` with `Defined in this chapter` across
  public manual Code Surfaces rows in Chapters 01, 02, 07-21.
- Added a public prose-hygiene ban for stale `chapter-local example code`
  wording in `tests/book_examples/test_public_mdx_snippets.py`.
- Updated `engine_book/completion_matrix.md` and
  `engine_book/parity_matrix.md` so the current proof layer records the
  reader-facing local-symbol label guard.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_manual_avoids_internal_meta_language tests/book_examples/test_public_mdx_snippets.py::test_all_import_panel_local_definitions_are_introduced tests/book_examples/test_public_mdx_snippets.py::test_enrolled_import_panels_explain_visible_local_names -q`
  passed with `3 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `231 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 07 Condition Authoring Guide

Chapter 07 now teaches how to write a condition before it introduces import
paths or condition examples. The public section presents a forward-facing
recipe for ongoing state: name the player-visible state, choose the owning
block, return owned modifier UUIDs, return condition-owned handler UUIDs,
compose same-block children, link effects across blocks, use duration expiry,
and publish an effect event.

Changes made:

- Moved `## Condition Authoring Guide` in
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/07-conditions-and-cleanup.mdx`
  before the Code Surfaces table and before `EB-07-001`.
- Extended
  `tests/book_examples/test_public_mdx_snippets.py::test_conditions_chapter_frontloads_ownership_contract`
  so the guide remains before the first example and keeps the concrete
  condition-authoring responsibilities visible.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 07
  evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_conditions_chapter_frontloads_ownership_contract -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "07-conditions-and-cleanup" -q`
  passed with `6 passed, 142 deselected`.
- `uv run pytest tests/manual/test_07_conditions_and_cleanup.py -q` passed
  with `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `233 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 08 Tactical Board Authoring Guide

Chapter 08 now teaches how to author tactical board state before it introduces
import paths or world-model examples. The public section presents the board as
reusable game state first, then separates the cause of movement into voluntary
step events and forced-movement events.

Changes made:

- Moved `## Tactical Board Authoring Guide` in
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/08-world-model-and-movement.mdx`
  before the Code Surfaces table and before `EB-08-001`.
- Extended
  `tests/book_examples/test_public_mdx_snippets.py::test_world_chapter_frontloads_movement_contract`
  so the guide remains before the first example and keeps the terrain, border,
  position-index, movement-cause, spatial-event, and setup-versus-runtime edit
  responsibilities visible.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 08
  evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_world_chapter_frontloads_movement_contract -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "08-world-model-and-movement" -q`
  passed with `5 passed, 143 deselected`.
- `uv run pytest tests/manual/test_08_world_model_and_movement.py -q` passed
  with `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `233 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 09 Action Authoring Guide

Chapter 09 now teaches how to author a player-facing command before the first
action example. The new public section presents actions as discoverable,
targeted, executable, and paid command rows that can serve the UI, a
controller, an API client, or an agent through the same indexed contract.

Changes made:

- Moved `## Action Authoring Guide` in
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/09-action-discovery-and-costs.mdx`
  so it now sits before the Code Surfaces table and before `EB-09-001`.
- Extended
  `tests/book_examples/test_public_mdx_snippets.py::test_actions_chapter_frontloads_choice_contract`
  so the guide remains before the Code Surfaces table and first example, and
  keeps the command source, template, category, target-row, cost, indexed
  execution, item/object routing, and override responsibilities visible.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 09
  evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_actions_chapter_frontloads_choice_contract -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "09-action-discovery-and-costs" -q`
  passed with `7 passed, 141 deselected`.
- `uv run pytest tests/manual/test_09_action_discovery_and_costs.py -q` passed
  with `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `233 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 10 Combat Authoring Guide

Chapter 10 now teaches how to author combat content before the first combat
example. The new public section presents combat as the shared consequence
pipeline from a selected command into validation, rolls, state changes,
events, movement reason, cost payment, and narration.

Changes made:

- Moved `## Combat Authoring Guide` in
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/10-combat-resolution.mdx`
  so it now sits before the Code Surfaces table and before `EB-10-001`.
- Extended
  `tests/book_examples/test_public_mdx_snippets.py::test_combat_chapter_frontloads_resolution_contract`
  so the guide remains before the Code Surfaces table and first example, and
  keeps validation, value/dice uncertainty, owned state changes, event
  publication, movement reason, post-success cost payment, and standard
  videogame Shove visible.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 10
  evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_combat_chapter_frontloads_resolution_contract -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "10-combat-resolution" -q`
  passed with `5 passed, 143 deselected`.
- `uv run pytest tests/manual/test_10_combat_resolution.py -q` passed with
  `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `233 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 11 Item Authoring Guide

Chapter 11 now teaches how to author physical game objects before the first
item example. The new public section presents items as persistent objects with
one authoritative location that can move through floor placement, inventory,
equipment, usable actions, and map-object state.

Changes made:

- Moved `## Item Authoring Guide` in
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/11-equipment-inventory-and-items.mdx`
  so it now sits before the Code Surfaces table and before `EB-11-001`.
- Extended
  `tests/book_examples/test_public_mdx_snippets.py::test_items_chapter_frontloads_ownership_contract`
  so the guide remains before the Code Surfaces table and first example, and
  keeps persistent identity, single-location ownership, atomic storage,
  equipment hooks, videogame loadouts, object use actions, post-success
  charge/stack updates, and inspectable map objects visible.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 11
  evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_items_chapter_frontloads_ownership_contract -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "11-equipment-inventory-and-items" -q`
  passed with `5 passed, 143 deselected`.
- `uv run pytest tests/manual/test_11_equipment_inventory_and_items.py -q`
  passed with `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `233 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 12 Visibility Authoring Guide

Chapter 12 now teaches how to author observer-local visibility before the first
perception example. The new public section presents visibility as knowledge
layered over an objective board: the map owns what exists, while each actor's
`Senses` block owns what that actor can see, target, remember, path through, or
detect through special senses.

Changes made:

- Moved `## Visibility Authoring Guide` in
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/12-perception-light-stealth-and-invisibility.mdx`
  so it now sits before the Code Surfaces table and before `EB-12-001`.
- Extended
  `tests/book_examples/test_public_mdx_snippets.py::test_perception_chapter_frontloads_visibility_contract`
  so the guide remains before the Code Surfaces table and first example, and
  keeps objective board facts, FOV subscriptions, observer-specific light,
  perceivability filters, observer caches, sensory update events, independent
  concealment layers, and subjective paths visible.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 12
  evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_perception_chapter_frontloads_visibility_contract -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "12-perception-light-stealth-and-invisibility" -q`
  passed with `6 passed, 142 deselected`.
- `uv run pytest tests/manual/test_12_perception_light_stealth_and_invisibility.py -q`
  passed with `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `233 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 13 Spell Authoring Guide

Chapter 13 now teaches how to author spellcasting behavior before the first
spellcasting example. The new public section presents spells as actions with
magic-specific resources, caster numbers, event identity, child outcomes, and
optional lasting condition ownership.

Changes made:

- Moved `## Spell Authoring Guide` in
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/13-spellcasting-core.mdx`
  so it now sits before the Code Surfaces table and before `EB-13-001`.
- Extended
  `tests/book_examples/test_public_mdx_snippets.py::test_spellcasting_chapter_frontloads_spellcasting_contract`
  so the guide remains before the Code Surfaces table and first example, and
  keeps caster numbers, slot resources, registered templates,
  perception-shaped target rows, spell events, child target outcomes,
  caster/slot scaling, and concentration ownership visible.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 13
  evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_spellcasting_chapter_frontloads_spellcasting_contract -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "13-spellcasting-core" -q`
  passed with `6 passed, 142 deselected`.
- `uv run pytest tests/manual/test_13_spellcasting_core.py -q` passed with
  `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `233 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 14 Spell Family Authoring Guide

Chapter 14 now teaches how to author spell families before the first
spell-family example. The new public section presents a spell family as the
runtime behavior pattern behind a D&D spell name: target shape, roll or save
ownership, immediate outcome, lasting state, cleanup owner, catalog address,
and representative executable example.

Changes made:

- Moved `## Spell Family Authoring Guide` in
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/14-spell-families-and-implemented-spells.mdx`
  so it now sits before the Code Surfaces table and before `EB-14-001`.
- Extended
  `tests/book_examples/test_public_mdx_snippets.py::test_spell_families_chapter_frontloads_family_contract`
  so the guide remains before the Code Surfaces table and first example, and
  keeps fantasy verb, target shape, roll/save/direct resolution, immediate
  result, lasting state, cleanup owner, catalog registration, and
  representative executable examples visible.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 14
  evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_spell_families_chapter_frontloads_family_contract -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "14-spell-families-and-implemented-spells" -q`
  passed with `6 passed, 142 deselected`.
- `uv run pytest tests/manual/test_14_spell_families.py -q` passed with
  `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `233 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 15 Character Content Authoring Guide

Chapter 15 now teaches how to author class features, factories, and feats
before the first character-content example. The new public section presents
character content as owned actor state that enters through ordinary resources,
actions, values, events, conditions, rest rules, and cleanup paths.

Changes made:

- Moved `## Character Content Authoring Guide` in
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/15-class-features-factories-and-feats.mdx`
  so it now sits before the Code Surfaces table and before `EB-15-001`.
- Extended
  `tests/book_examples/test_public_mdx_snippets.py::test_class_features_chapter_frontloads_character_content_contract`
  so the guide remains before the Code Surfaces table and first example, and
  keeps factory recipes, limited-use resources, feature actions, passive
  conditions, temporary modes, event timing surfaces, rest/reset behavior, and
  ownership removal visible.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 15
  evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_class_features_chapter_frontloads_character_content_contract -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "15-class-features-factories-and-feats" -q`
  passed with `5 passed, 143 deselected`.
- `uv run pytest tests/manual/test_15_class_features.py -q` passed with
  `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `233 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 16 Preset Actor Authoring Guide

Chapter 16 now teaches how to author monsters and preset actors before the
first preset-actor example. The new public section presents monsters and
presets as complete entity recipes that can enter the ordinary action, item,
spell, condition, perception, and encounter surfaces.

Changes made:

- Moved `## Preset Actor Authoring Guide` in
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/16-monsters-and-preset-actors.mdx`
  so it now sits before the Code Surfaces table and before `EB-16-001`.
- Extended
  `tests/book_examples/test_public_mdx_snippets.py::test_monsters_chapter_frontloads_preset_actor_contract`
  so the guide remains before the Code Surfaces table and first example, and
  keeps battlefield roles, live entity state, senses and defenses, attacks and
  special actions, gear and loot, condition-owned unusual behavior, composable
  role variants, and encounter-ready placement visible.
- Rewrote one negation-framed sentence caught by the public hygiene guard so it
  positively describes preset actors as prepared entities using the shared
  runtime surfaces.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 16
  evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_monsters_chapter_frontloads_preset_actor_contract -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "16-monsters-and-preset-actors" -q`
  passed with `5 passed, 143 deselected`.
- `uv run pytest tests/manual/test_16_monsters_preset_actors.py -q` passed
  with `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `233 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 08 Board Ownership Contract

Chapter 08 now teaches the lowest world-model ownership split before the
tactical-board reference table, Code Surfaces table, and first grid example.
The new public section presents world state as four cooperating owners:
`Tile` owns one cell's costs, borders, light, and conditions; `GridMap` owns
tile storage, indexes, pathing, subscriptions, light sources, and spatial
event emission; movement parent events own the rules reason for voluntary
steps versus forced displacement; and `EventQueue` spatial dispatch owns
position-indexed reactions to board changes.

Changes made:

- Added `## The Board Ownership Contract` to
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/08-world-model-and-movement.mdx`
  before `## The Tactical Board`, `## How Tactical Movement Becomes Map State`,
  `## The World Movement Contract`, source surfaces, and `EB-08-001`.
- Rephrased the grid/action boundary positively: the grid owns cells, costs,
  borders, indexes, and spatial change records; the movement cause lives on
  the parent event.
- Extended
  `tests/book_examples/test_public_mdx_snippets.py::test_world_chapter_frontloads_movement_contract`
  so the board ownership contract stays in the reader's first pass and keeps
  the `Tile`, `GridMap`, movement-parent-event, and spatial-dispatch surfaces
  visible.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 08
  evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_world_chapter_frontloads_movement_contract -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "08-world-model-and-movement" -q`
  passed with `5 passed, 143 deselected`.
- `uv run pytest tests/manual/test_08_world_model_and_movement.py -q` passed
  with `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `234 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 09 Action Runtime Contract

Chapter 09 now teaches the small action objects before the turn-menu grouping,
choice contract, Code Surfaces table, and first action example. The new public
section presents the command path as five runtime surfaces: `BaseAction`
templates for reusable actor capabilities, `Cost` records for affordability
and post-success payment, `AvailableActionInfo` rows for command-menu entries,
`AvailableTarget` rows for indexed arguments, and executable `BaseAction`
instances for one-shot event lifecycle execution.

Changes made:

- Added `## The Action Runtime Contract` to
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/09-action-discovery-and-costs.mdx`
  before `## The Turn Choice Surface`, `## How A Player Choice Becomes An
  Engine Action`, `## The Action Choice Contract`, source surfaces, and
  `EB-09-001`.
- Extended
  `tests/book_examples/test_public_mdx_snippets.py::test_actions_chapter_frontloads_choice_contract`
  so the action runtime contract stays in the reader's first pass and keeps
  template, cost, discovered-row, target-row, and executable-instance surfaces
  visible.
- Updated `engine_book/completion_matrix.md` with the refreshed Chapter 09
  evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_actions_chapter_frontloads_choice_contract -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "09-action-discovery-and-costs" -q`
  passed with `7 passed, 141 deselected`.
- `uv run pytest tests/manual/test_09_action_discovery_and_costs.py -q` passed
  with `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `234 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 01 Code-First Output Pivot

Chapter 01 now starts with a runnable identity example before the reference
tables, source-rule relationship, chapter map, authoring guide, and code
surface table. This responds to the public-manual format problem: the first
chapter now shows code creating an object, inspecting runtime state, printing
readable output, and then verifying the observed result.

Changes made:

- Added `## First Run: Create And Inspect Identity` to
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/01-runtime-identity-and-registries.mdx`
  immediately after the diagram.
- Added `EB-01-000` / `identity-first-run`, with the first setup panel open by
  default, visible object creation code, a printed inspection payload, and a
  matching visible output block.
- Updated Chapter 01's chapter map from five moves to six moves, adding the
  first runtime object step.
- Updated `tests/book_examples/test_public_mdx_snippets.py` so Chapter 01 is
  explicitly allowed and required to be code-first, while later chapters remain
  on the older reference-first order until they are deliberately migrated.
- Updated `tests/manual/test_01_runtime_identity_and_registries.py` with a
  focused output test for the first runtime object.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` with the new public example and current
  verification evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_identity_chapter_frontloads_dnd_reference_translation -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "01-runtime-identity-and-registries" -q`
  passed with `6 passed, 144 deselected`.
- `uv run pytest tests/manual/test_01_runtime_identity_and_registries.py -q`
  passed with `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `235 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 02 Code-First Actor Readout

Chapter 02 now follows the code-first format established in Chapter 01. It
starts with a runnable actor creation example before the player/designer
framing, SRD relationship, chapter map, authoring guide, and source table. The
first example creates an `Entity` directly, prints the actor's runtime shape,
and verifies the same readout.

Changes made:

- Added `## First Run: Create And Inspect An Actor` to
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/02-entity-anatomy.mdx`
  immediately after the diagram.
- Added `EB-02-000` / `entity-first-run`, with the first setup panel open by
  default, visible `Entity.create(...)` code, printed actor readout output, and
  assertions matching the observed result.
- Updated Chapter 02's chapter map from four moves to five moves, adding the
  first actor readout step.
- Added `CODE_FIRST_CHAPTERS` to
  `tests/book_examples/test_public_mdx_snippets.py` so Chapters 01 and 02 can
  enforce the code-first order while later chapters remain reference-first
  until migrated deliberately.
- Updated Chapter 02 Code Surfaces rows so all runtime imports and local setup
  names used by the new first example are introduced.
- Updated `tests/manual/test_02_entity_anatomy.py` with a focused output test
  for the first actor readout.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` with the new public example and current
  verification evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_entity_chapter_frontloads_creature_translation -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "02-entity-anatomy" -q`
  passed with `2 passed, 148 deselected`.
- `uv run pytest tests/manual/test_02_entity_anatomy.py -q` passed with
  `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `236 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 03 Code-First Value Output

Chapter 03 now follows the visible-output format established in Chapters 01 and
02. It starts with a runnable Armor Class value example before the
player/designer framing, source-rule relationship, chapter map, authoring
guide, and source table. The first example creates a `ModifiableValue`, adds
named `NumericalModifier` rules, prints the final score and breakdown names,
and verifies the same readout in focused tests.

Changes made:

- Added `## First Run: Create And Inspect A Value` to
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/03-values-and-modifiers.mdx`
  immediately after the diagram.
- Added `EB-03-000` / `values-first-run`, with the first setup panel open by
  default, visible value authoring code, printed Armor Class breakdown output,
  and assertions matching the observed result.
- Updated Chapter 03's chapter map from four moves to five moves, adding the
  first value-ledger readout step.
- Added Chapter 03 to `CODE_FIRST_CHAPTERS` in
  `tests/book_examples/test_public_mdx_snippets.py`.
- Updated Chapter 03 Code Surfaces rows so `BaseObject`, `BaseValue`, and the
  local `reset_value_state` helper are introduced for the new first example.
- Updated `tests/manual/test_03_values_and_modifiers.py` with a focused output
  test for the first value readout.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` with the new public example and current
  verification evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_values_chapter_frontloads_product_math_bridge -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "03-values-and-modifiers" -q`
  passed with `5 passed, 146 deselected`.
- `uv run pytest tests/manual/test_03_values_and_modifiers.py -q` passed with
  `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `237 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 04 Code-First Dice Output

Chapter 04 now follows the visible-output format for dice. It starts with a
runnable deterministic d20 example before the player/designer framing,
source-rule relationship, chapter map, authoring guide, and source table. The
first example creates a bonus value, rolls a `Dice` expression with a fixed
face, prints the resulting `DiceRoll` fields, and verifies cache and lookup
behavior in focused tests.

Changes made:

- Added `## First Run: Roll And Inspect A D20` to
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/04-dice-rolls.mdx`
  immediately after the diagram.
- Added `EB-04-000` / `dice-first-run`, with the first setup panel open by
  default, visible dice authoring code, printed d20 output, and assertions
  matching the observed result.
- Updated Chapter 04's chapter map from five moves to six moves, adding the
  first roll-record readout step.
- Added Chapter 04 to `CODE_FIRST_CHAPTERS` in
  `tests/book_examples/test_public_mdx_snippets.py`.
- Updated Chapter 04 Code Surfaces rows so `BaseObject`, `BaseValue`, and the
  local `reset_dice_state` helper are introduced for the new first example.
- Updated `tests/manual/test_04_dice_rolls.py` with a focused output test for
  the first dice readout.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` with the new public example and expected
  verification evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_dice_chapter_frontloads_product_roll_bridge -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "04-dice-rolls" -q`
  passed with `6 passed, 146 deselected`.
- `uv run pytest tests/manual/test_04_dice_rolls.py -q` passed with
  `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `238 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 05 Full Visible-Output Cleanup

Chapter 05 no longer leaves the post-first-run event examples as assertion-only
code. Each event example now prints and displays the event behavior it teaches:
phase/index history, cancellation reason, parent-child event tree resolution,
completion combat-log parent/sub-entry narration, and passive callback
observation.

Changes made:

- Updated
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/05-event-lifecycle.mdx`
  so `event-lineage-phases`, `event-cancellation`,
  `event-parent-child-lineage`, `event-completion-combat-log`, and
  `event-passive-observation` each print and display observed output.
- Updated `tests/manual/test_05_event_lifecycle.py` so every Chapter 05 event
  example has a focused stdout assertion.
- Added
  `tests/book_examples/test_public_mdx_snippets.py::test_event_lifecycle_examples_show_reader_visible_output`
  to guard against Chapter 05 regressing to assertion-only public examples.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` with the Chapter 05 visible-output
  transcript status.

Verification completed:

- `uv run pytest tests/manual/test_05_event_lifecycle.py -q` passed with
  `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k '05-event-lifecycle or event_lifecycle'`
  passed with `8 passed, 248 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `256 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 05 Code-First Event Output

Chapter 05 now follows the visible-output format for events. It starts with a
runnable event-lineage example before the player/designer framing, source-rule
relationship, chapter map, authoring guide, and source table. The first example
creates an `Event`, advances it through execution, effect, and completion,
prints the queue history, and verifies phase, lineage, and lookup behavior in
focused tests.

Changes made:

- Added `## First Run: Create And Inspect A Lineage` to
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/05-event-lifecycle.mdx`
  immediately after the diagram.
- Added `EB-05-000` / `event-first-run`, with the first setup panel open by
  default, visible event authoring code, printed lineage output, and assertions
  matching the observed result.
- Updated Chapter 05's chapter map from five moves to six moves, adding the
  first event-lineage readout step.
- Added Chapter 05 to `CODE_FIRST_CHAPTERS` in
  `tests/book_examples/test_public_mdx_snippets.py`.
- Updated Chapter 05 Code Surfaces rows so `BaseObject` and the local
  `reset_event_state` helper are introduced for the new first example.
- Updated `tests/manual/test_05_event_lifecycle.py` with a focused output test
  for the first event readout.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` with the new public example and expected
  verification evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_event_chapter_frontloads_product_timeline_bridge -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "05-event-lifecycle" -q`
  passed with `6 passed, 147 deselected`.
- `uv run pytest tests/manual/test_05_event_lifecycle.py -q` passed with
  `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `239 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 06 Full Visible-Output Cleanup

Chapter 06 no longer leaves the post-first-run reaction examples as
assertion-only code. Each reaction example now prints and displays the timing
behavior it teaches: trigger matching, quiet disabled/completion windows,
cancel short-circuiting, d20 result replacement, spatial position-index
dispatch, and voluntary-step versus forced-movement separation.

Changes made:

- Updated
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/06-reactions-to-events.mdx`
  so `event-triggered-handler`, `event-quiet-timing-windows`,
  `event-cancel-and-stop`, `event-d20-result-processor`,
  `event-spatial-entry-handler`, and `event-movement-surfaces` each print and
  display observed output.
- Updated `tests/manual/test_06_reactions_to_events.py` so every Chapter 06
  reaction example has a focused stdout assertion.
- Added
  `tests/book_examples/test_public_mdx_snippets.py::test_reactions_chapter_examples_show_reader_visible_output`
  to guard against Chapter 06 regressing to assertion-only public examples.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` with the Chapter 06 visible-output
  transcript status.

Verification completed:

- `uv run pytest tests/manual/test_06_reactions_to_events.py -q` passed with
  `7 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k '06-reactions-to-events'`
  passed with `7 passed, 158 deselected`.
- `uv run pytest tests/manual/test_06_reactions_to_events.py tests/book_examples/test_public_mdx_snippets.py -q -k '06-reactions-to-events or reactions_chapter'`
  passed with `9 passed, 255 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `257 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 06 Code-First Reaction Output

Chapter 06 now follows the visible-output format for reactions. It starts with
a runnable event-handler example before the player/designer framing,
source-rule relationship, chapter map, authoring guide, and source table. The
first example registers an `EventHandler`, sends one nonmatching event and one
matching event through the queue, prints the quiet miss and modified alarm
result, and verifies handler source ownership in focused tests.

Changes made:

- Added `## First Run: Register And Fire A Handler` to
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/06-reactions-to-events.mdx`
  immediately after the diagram.
- Added `EB-06-000` / `reaction-first-run`, with the first setup panel open by
  default, visible handler authoring code, printed handler output, and
  assertions matching the observed result.
- Updated Chapter 06's chapter map from six moves to seven moves, adding the
  first handler readout step.
- Added Chapter 06 to `CODE_FIRST_CHAPTERS` in
  `tests/book_examples/test_public_mdx_snippets.py`.
- Updated Chapter 06 Code Surfaces rows so `BaseObject` and the local
  `reset_reaction_state` helper are introduced for the new first example.
- Updated `tests/manual/test_06_reactions_to_events.py` with a focused output
  test for the first reaction readout.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` with the new public example and expected
  verification evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_reactions_chapter_frontloads_timing_contract -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "06-reactions-to-events" -q`
  passed with `7 passed, 147 deselected`.
- `uv run pytest tests/manual/test_06_reactions_to_events.py -q` passed with
  `7 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `240 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 07 Full Visible-Output Cleanup

Chapter 07 no longer leaves the post-first-run condition examples as
assertion-only code. Each condition example now prints and displays the
lifecycle behavior it teaches: condition-bearing block setup, owned modifier
indexes, condition-owned handler cleanup, same-block subcondition cleanup,
linked forward/reverse cleanup, and duration expiry through normal removal.

Changes made:

- Updated
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/07-conditions-and-cleanup.mdx`
  so `condition-bearing-actor`, `condition-owned-modifier`,
  `condition-owned-handler`, `condition-subcondition-tree`,
  `condition-linked-cleanup`, and `condition-duration-expiry` each print and
  display observed output.
- Updated `tests/manual/test_07_conditions_and_cleanup.py` so every Chapter 07
  condition example has a focused stdout assertion, including the actor setup
  example.
- Added
  `tests/book_examples/test_public_mdx_snippets.py::test_conditions_chapter_examples_show_reader_visible_output`
  to guard against Chapter 07 regressing to assertion-only public examples.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` with the Chapter 07 visible-output
  transcript status.

Verification completed:

- `uv run pytest tests/manual/test_07_conditions_and_cleanup.py -q` passed with
  `7 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k '07-conditions-and-cleanup'`
  passed with `7 passed, 158 deselected`.
- `uv run pytest tests/manual/test_07_conditions_and_cleanup.py tests/book_examples/test_public_mdx_snippets.py -q -k '07-conditions-and-cleanup or conditions_chapter'`
  passed with `9 passed, 256 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `258 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 07 Code-First Condition Output

Chapter 07 now follows the visible-output format for conditions. It starts with
a runnable condition lifecycle example before the player/designer framing,
source-rule relationship, chapter map, authoring guide, and source table. The
first example creates a condition-bearing `BaseBlock`, applies a
`GuardedCondition`, prints active indexes, guard score, owned modifier count,
and cleanup result, then verifies the state leaves cleanly.

Changes made:

- Added `## First Run: Apply And Clean Up A Condition` to
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/07-conditions-and-cleanup.mdx`
  immediately after the diagram.
- Added `EB-07-000` / `condition-first-run`, with the first setup panel open by
  default, visible condition authoring code, printed condition lifecycle output,
  and assertions matching the observed result.
- Updated Chapter 07's chapter map from six moves to seven moves, adding the
  first condition application and cleanup readout step.
- Added Chapter 07 to `CODE_FIRST_CHAPTERS` in
  `tests/book_examples/test_public_mdx_snippets.py`.
- Updated Chapter 07 Code Surfaces rows so `BaseObject`, `BaseValue`,
  `EventQueue`, and the local `reset_condition_state` helper are introduced
  for the new first example.
- Updated `tests/manual/test_07_conditions_and_cleanup.py` with a focused
  output test for the first condition readout.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` with the new public example and expected
  verification evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_conditions_chapter_frontloads_ownership_contract -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "07-conditions-and-cleanup" -q`
  passed with `7 passed, 148 deselected`.
- `uv run pytest tests/manual/test_07_conditions_and_cleanup.py -q` passed with
  `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `241 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 08 Full Visible-Output Cleanup

Chapter 08 no longer leaves the post-first-run world examples as assertion-only
code. Each world example now prints and displays the board behavior it teaches:
terrain/path lookup, directional border tile-change events, entity position
indexes and spatial enter/leave events, forced-movement spatial parenting, and
quiet batch map creation versus eventful runtime edits.

Changes made:

- Updated
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/08-world-model-and-movement.mdx`
  so `world-terrain-costs`, `world-directional-border`,
  `world-entity-spatial-events`, `world-forced-movement`, and
  `world-batch-map-creation` each print and display observed output.
- Updated `tests/manual/test_08_world_model_and_movement.py` so every Chapter
  08 world example has a focused stdout assertion.
- Added
  `tests/book_examples/test_public_mdx_snippets.py::test_world_chapter_examples_show_reader_visible_output`
  to guard against Chapter 08 regressing to assertion-only public examples.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` with the Chapter 08 visible-output
  transcript status.

Verification completed:

- `uv run pytest tests/manual/test_08_world_model_and_movement.py -q` passed
  with `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k '08-world-model-and-movement'`
  passed with `6 passed, 159 deselected`.
- `uv run pytest tests/manual/test_08_world_model_and_movement.py tests/book_examples/test_public_mdx_snippets.py -q -k '08-world-model-and-movement or world_chapter'`
  passed with `8 passed, 257 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `259 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 08 Code-First World Output

Chapter 08 now follows the visible-output format for the tactical board. It
starts with a runnable corridor/pathfinding example before the player/designer
framing, source-rule relationship, chapter map, authoring guide, and source
table. The first example builds a five-cell corridor, places difficult terrain
in the middle, prints bounds, tile count, movement-mode costs, route cost, and
the path, then verifies the same grid state in focused tests.

Changes made:

- Added `## First Run: Build And Measure A Corridor` to
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/08-world-model-and-movement.mdx`
  immediately after the diagram.
- Added `EB-08-000` / `world-first-run`, with the first setup panel open by
  default, visible grid authoring code, printed pathfinding output, and
  assertions matching the observed result.
- Updated Chapter 08's chapter map from five moves to six moves, adding the
  first corridor readout step.
- Added Chapter 08 to `CODE_FIRST_CHAPTERS` in
  `tests/book_examples/test_public_mdx_snippets.py`.
- Updated `tests/manual/test_08_world_model_and_movement.py` with a focused
  output test for the first world-model readout.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` with the new public example and expected
  verification evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_world_chapter_frontloads_movement_contract -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "08-world-model-and-movement" -q`
  passed with `6 passed, 150 deselected`.
- `uv run pytest tests/manual/test_08_world_model_and_movement.py -q` passed
  with `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `242 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 09 Full Visible-Output Cleanup

Chapter 09 now uses the reader-visible output standard across the whole action
chapter, not only the opening example. Every public action example still asserts
the engine invariant, but it also prints a transcript that the page shows in an
adjacent `Output:` block. The focused tests assert the printed stdout, and the
public MDX guard now prevents the chapter from sliding back into assert-only
tutorial snippets.

Changes made:

- Updated
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/09-action-discovery-and-costs.mdx`
  so all eight action examples print concrete output:
  first command menu, template instantiation, grouped discovery, indexed Dash
  execution, object/inventory item routing, temporary cost override, target
  pools, and safe-path movement.
- Updated `tests/manual/test_09_action_discovery_and_costs.py` so all eight
  Chapter 09 focused examples assert their exact stdout transcript.
- Added
  `test_actions_chapter_examples_show_reader_visible_output()` to
  `tests/book_examples/test_public_mdx_snippets.py` so the public page must
  keep eight visible output blocks and the key action transcript lines.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` to track Chapter 09 as visible-output
  guarded, with the public MDX suite now at 260 tests.

Verification completed:

- `uv run pytest tests/manual/test_09_action_discovery_and_costs.py -q` passed
  with `8 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "09-action-discovery-and-costs"`
  passed with `8 passed, 157 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k "09-action-discovery-and-costs or actions_chapter"`
  passed with `12 passed, 248 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `260 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 09 Code-First Action Output

Chapter 09 now follows the visible-output format for action discovery. It
starts with a runnable command-menu example before the player/designer framing,
source-rule relationship, chapter map, authoring guide, and source table. The
first example creates a Scout and nearby Skeleton, prints grouped action rows,
Dash cost, movement and attack target previews, executes Dash by index, and
prints the post-cost state.

Changes made:

- Added `## First Run: Print A Turn Menu` to
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/09-action-discovery-and-costs.mdx`
  immediately after the diagram.
- Added `EB-09-000` / `action-first-run`, with the first setup panel open by
  default, visible actor/menu code, printed command-menu output, and assertions
  matching the observed result.
- Updated Chapter 09's chapter map from seven moves to eight moves, adding the
  first command-menu readout step.
- Added Chapter 09 to `CODE_FIRST_CHAPTERS` in
  `tests/book_examples/test_public_mdx_snippets.py`.
- Updated `tests/manual/test_09_action_discovery_and_costs.py` with a focused
  output test for the first action-menu readout.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` with the new public example and expected
  verification evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_actions_chapter_frontloads_choice_contract -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "09-action-discovery-and-costs" -q`
  passed with `8 passed, 149 deselected`.
- `uv run pytest tests/manual/test_09_action_discovery_and_costs.py -q` passed
  with `7 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `243 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 10 Full Visible-Output Cleanup

Chapter 10 now uses the reader-visible output standard across the whole combat
chapter. Every public combat example still asserts the engine invariant, but it
also prints a transcript that appears beside the code in the webbook. The
focused tests assert those stdout transcripts, and the public MDX guard now
prevents Chapter 10 from regressing into assertion-only combat snippets.

Changes made:

- Updated
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/10-combat-resolution.mdx`
  so all six combat examples print concrete output: first hit/damage/heal,
  invalid attack cancellation before costs, hit damage plus healing events,
  critical damage dice, voluntary movement opportunity attack, and videogame
  Shove forced movement.
- Updated `tests/manual/test_10_combat_resolution.py` so all six Chapter 10
  focused examples assert their exact stdout transcript.
- Added
  `test_combat_chapter_examples_show_reader_visible_output()` to
  `tests/book_examples/test_public_mdx_snippets.py` so the public page must
  keep six visible output blocks and the key combat transcript lines.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` to track Chapter 10 as visible-output
  guarded, with the public MDX suite now at 261 tests.

Verification completed:

- `uv run pytest tests/manual/test_10_combat_resolution.py -q` passed with
  `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "10-combat-resolution"`
  passed with `6 passed, 159 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k "10-combat-resolution or combat_chapter"`
  passed with `8 passed, 253 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `261 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 10 Code-First Combat Output

Chapter 10 now follows the visible-output format for combat consequences. It
starts with a runnable hit/damage/heal example before the player/designer
framing, source-rule relationship, chapter map, authoring guide, and source
table. The first example creates a Goblin attacker and Skeleton target, forces
a deterministic hit, prints the outcome, damage roll, HP change, action
spending, healing, and completion-event counts, then verifies the same
consequence state in focused tests.

Changes made:

- Added `## First Run: Resolve One Hit` to
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/10-combat-resolution.mdx`
  immediately after the diagram.
- Added `EB-10-000` / `combat-first-run`, with the first setup panel open by
  default, visible combat setup code, printed hit/damage/heal output, and
  assertions matching the observed result.
- Updated Chapter 10's chapter map from five moves to six moves, adding the
  first combat-consequence readout step.
- Added Chapter 10 to `CODE_FIRST_CHAPTERS` in
  `tests/book_examples/test_public_mdx_snippets.py`.
- Updated `tests/manual/test_10_combat_resolution.py` with a focused output
  test for the first combat readout.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` with the new public example and expected
  verification evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_combat_chapter_frontloads_resolution_contract -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_combat_object_awareness_chapters_explain_their_ruling_role -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "10-combat-resolution" -q`
  passed with `6 passed, 152 deselected`.
- `uv run pytest tests/manual/test_10_combat_resolution.py -q` passed with
  `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `244 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 11 Full Visible-Output Cleanup

Chapter 11 now uses the reader-visible output standard across the whole item
chapter. Every public item example still asserts the engine invariant, but it
also prints a transcript that appears beside the code in the webbook. The
focused tests assert those stdout transcripts, and the public MDX guard now
prevents Chapter 11 from regressing into assertion-only item snippets.

Changes made:

- Updated
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/11-equipment-inventory-and-items.mdx`
  so all six item examples print concrete output: first floor/inventory/drop
  lifecycle, explicit floor/inventory/drop ownership, atomic stack merging and
  overweight rejection, equipment hooks, order-based two-handed melee
  displacement with parallel ranged loadouts, and item-bound potion/door
  actions.
- Updated `tests/manual/test_11_equipment_inventory_and_items.py` so all six
  Chapter 11 focused examples assert their exact stdout transcript.
- Added
  `test_items_chapter_examples_show_reader_visible_output()` to
  `tests/book_examples/test_public_mdx_snippets.py` so the public page must
  keep six visible output blocks and the key item transcript lines.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` to track Chapter 11 as visible-output
  guarded, with the public MDX suite now at 262 tests.

Verification completed:

- `uv run pytest tests/manual/test_11_equipment_inventory_and_items.py -q`
  passed with `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "11-equipment-inventory-and-items"`
  passed with `6 passed, 159 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k "11-equipment-inventory-and-items or items_chapter"`
  passed with `8 passed, 254 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `262 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 11 Code-First Item Output

Chapter 11 now follows the visible-output format for physical objects. It
starts with a runnable item-location example before the player/designer
framing, source-rule relationship, chapter map, authoring guide, and source
table. The first example creates a Silver Key on the floor, loots it into an
actor inventory, prints the carried state and actor-following position, drops
it back onto the map, and verifies the same item identity and location fields
in focused tests.

Changes made:

- Added `## First Run: Track One Object` to
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/11-equipment-inventory-and-items.mdx`
  immediately after the diagram.
- Added `EB-11-000` / `items-first-run`, with the first setup panel open by
  default, visible item/actor setup code, printed floor/inventory/drop output,
  and assertions matching the observed result.
- Updated Chapter 11's chapter map from five moves to six moves, adding the
  first physical-object location readout step.
- Added Chapter 11 to `CODE_FIRST_CHAPTERS` in
  `tests/book_examples/test_public_mdx_snippets.py`.
- Updated `tests/manual/test_11_equipment_inventory_and_items.py` with a
  focused output test for the first item lifecycle readout.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` with the new public example and expected
  verification evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_items_chapter_frontloads_ownership_contract -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_combat_object_awareness_chapters_explain_their_ruling_role -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "11-equipment-inventory-and-items" -q`
  passed with `6 passed, 153 deselected`.
- `uv run pytest tests/manual/test_11_equipment_inventory_and_items.py -q`
  passed with `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `245 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 12 Full Visible-Output Cleanup

Chapter 12 now uses the reader-visible output standard across the whole
perception chapter. Every public perception example still asserts the engine
invariant, but it also prints an observer-local transcript beside the code in
the webbook. The focused tests assert those stdout transcripts, and the public
MDX guard now prevents Chapter 12 from regressing into assertion-only
perception snippets.

Changes made:

- Updated
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/12-perception-light-stealth-and-invisibility.mdx`
  so all seven perception examples print concrete output: first dark-cell
  reveal, geometric FOV versus light-filtered visibility, special-sense light
  policy, reactive sensory updates, stealth and invisibility target filters,
  subjective paths around unseen blockers, and independent Hidden/Invisible
  concealment layers.
- Updated `tests/manual/test_12_perception_light_stealth_and_invisibility.py`
  so all seven Chapter 12 focused examples assert their exact stdout
  transcript.
- Added
  `test_perception_chapter_examples_show_reader_visible_output()` to
  `tests/book_examples/test_public_mdx_snippets.py` so the public page must
  keep seven visible output blocks and the key perception transcript lines.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` to track Chapter 12 as visible-output
  guarded, with the public MDX suite now at 263 tests.

Verification completed:

- `uv run pytest tests/manual/test_12_perception_light_stealth_and_invisibility.py -q`
  passed with `7 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "12-perception-light-stealth-and-invisibility"`
  passed with `7 passed, 158 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k "12-perception-light-stealth-and-invisibility or perception_chapter"`
  passed with `9 passed, 254 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `263 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 12 Code-First Perception Output

Chapter 12 now follows the visible-output format for observer-local knowledge.
It starts with a runnable visibility example before the player/designer
framing, source-rule relationship, chapter map, authoring guide, and source
table. The first example creates an observer and a target in a dark corridor,
prints geometric subscription versus visible target state, lights the target
cell, then prints the updated visible-cell, visible-entity, memory, and sensory
update state.

Changes made:

- Added `## First Run: Reveal A Dark Target Cell` to
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/12-perception-light-stealth-and-invisibility.mdx`
  immediately after the diagram.
- Added `EB-12-000` / `senses-first-run`, with the first setup panel open by
  default, visible observer/map setup code, printed observer-knowledge output,
  and assertions matching the observed result.
- Updated Chapter 12's chapter map from six moves to seven moves, adding the
  first observer-knowledge readout step.
- Added Chapter 12 to `CODE_FIRST_CHAPTERS` in
  `tests/book_examples/test_public_mdx_snippets.py`.
- Updated `tests/manual/test_12_perception_light_stealth_and_invisibility.py`
  with a focused output test for the first perception readout.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` with the new public example and expected
  verification evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_perception_chapter_frontloads_visibility_contract -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_combat_object_awareness_chapters_explain_their_ruling_role -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "12-perception-light-stealth-and-invisibility" -q`
  passed with `7 passed, 153 deselected`.
- `uv run pytest tests/manual/test_12_perception_light_stealth_and_invisibility.py -q`
  passed with `7 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `246 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 13 Full Visible-Output Cleanup

Chapter 13 now uses the reader-visible output standard across the whole
spellcasting chapter. Every public spellcasting example still asserts the
engine invariant, but it also prints a transcript beside the code in the
webbook. The focused tests assert those stdout transcripts, and the public MDX
guard now prevents Chapter 13 from regressing into assertion-only spell
snippets.

Changes made:

- Updated
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/13-spellcasting-core.mdx`
  so all seven spellcasting examples print concrete output: first discovered
  Fire Bolt cast, spell slot spend/reset lifecycle, spell number composition,
  cantrip and slot-variant discovery, Fire Bolt resolution, Magic Missile
  multi-target resolution, and Haste concentration cleanup.
- Updated `tests/manual/test_13_spellcasting_core.py` so all seven Chapter 13
  focused examples assert their exact stdout transcript.
- Added
  `test_spellcasting_chapter_examples_show_reader_visible_output()` to
  `tests/book_examples/test_public_mdx_snippets.py` so the public page must
  keep seven visible output blocks and the key spellcasting transcript lines.
- Standardized the first Chapter 13 output block from `Expected output:` to
  `Output:` so it matches the rest of the webbook.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` to track Chapter 13 as visible-output
  guarded, with the public MDX suite now at 264 tests.

Verification completed:

- `uv run pytest tests/manual/test_13_spellcasting_core.py -q` passed with
  `7 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "13-spellcasting-core"`
  passed with `7 passed, 158 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k "13-spellcasting-core or spellcasting_chapter"`
  passed with `9 passed, 255 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `264 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 26 Full Visible-Output Cleanup

Chapter 26 now uses the reader-visible output standard across the whole agent
tactical interface chapter. Every public tactical example still asserts the
runtime invariant, but it also prints a concise tactical transcript beside the
code in the webbook. The focused tests assert those stdout transcripts, and
the public MDX guard prevents Chapter 26 from regressing into assertion-only
agent-interface snippets.

Changes made:

- Updated
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/26-agent-tactical-interface.mdx`
  so all seven tactical examples print concrete output: interface surfaces,
  tactical snapshots, action and target rows, tactical queries, EV scoring,
  deterministic selected-action execution, and a minimal agent runner.
- Added `fixed_dice_faces` to the Chapter 26 Code Surfaces table and to the
  two execution examples so both the attack d20 and damage die are
  deterministic.
- Added a focused EB-26-001 surface test and updated
  `tests/manual/test_26_agent_tactical_interface.py` so all seven public
  Chapter 26 examples assert their exact stdout transcript and align one-to-one
  with the public examples. The no-late-import, Pydantic field-description, and
  reset/source ownership guards also print their own focused transcripts.
- Added `test_agent_tactical_chapter_examples_show_reader_visible_output()` to
  `tests/book_examples/test_public_mdx_snippets.py` so the public page must
  keep seven visible output blocks and the key tactical transcript lines.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` to track Chapter 26 as visible-output
  guarded, with the public MDX suite now at 277 tests.

Verification completed:

- `uv run pytest tests/manual/test_26_agent_tactical_interface.py -q`
  passed with `10 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "26-agent-tactical-interface"`
  passed with `7 passed, 158 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k "26-agent-tactical-interface or agent_tactical_chapter"`
  passed with `9 passed, 268 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `277 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 25 Full Visible-Output Cleanup

Chapter 25 now uses the reader-visible output standard across the whole live
replication chapter. Every public stream example still asserts the runtime
invariant, but it also prints a concise cursor/frame transcript beside the code
in the webbook. The focused tests assert those stdout transcripts, and the
public MDX guard prevents Chapter 25 from regressing into assertion-only stream
snippets.

Changes made:

- Updated
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/25-live-replication-streams.mdx`
  so all seven stream examples print concrete output: stream surfaces, sync
  frame, cursor replay, live fan-out, completion-before-log ordering,
  heartbeat cursors, and bounded subscriber eviction.
- Added a focused EB-25-001 surface test and updated
  `tests/manual/test_25_live_replication_streams.py` so all seven public
  Chapter 25 examples assert their exact stdout transcript and align one-to-one
  with the public examples. The focused reset/source ownership guard also
  prints its own reset transcript.
- Added `test_live_replication_chapter_examples_show_reader_visible_output()`
  to `tests/book_examples/test_public_mdx_snippets.py` so the public page must
  keep seven visible output blocks and the key stream transcript lines.
- Kept the existing quiet-period wording guard active while adding the visible
  output examples.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` to track Chapter 25 as visible-output
  guarded, with the public MDX suite now at 276 tests.

Verification completed:

- `uv run pytest tests/manual/test_25_live_replication_streams.py -q`
  passed with `8 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "25-live-replication-streams"`
  passed with `7 passed, 158 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k "25-live-replication-streams or live_replication_chapter"`
  passed with `10 passed, 266 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `276 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 24 Full Visible-Output Cleanup

Chapter 24 now uses the reader-visible output standard across the whole
built-in controller chapter. Every public controller example still asserts the
runtime invariant, but it also prints a concise turn-routing transcript beside
the code in the webbook. The focused tests assert those stdout transcripts, and
the public MDX guard prevents Chapter 24 from regressing into assertion-only
controller snippets.

Changes made:

- Updated
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/24-built-in-controllers-and-automated-turns.mdx`
  so all seven controller examples print concrete output: catalogue surfaces,
  human/Codex wait handoff, explicit pass turns, adjacent melee attack choice,
  pursuit movement, empty-target pass signal, and agent-runner delegation.
- Added a focused EB-24-001 surface test and updated
  `tests/manual/test_24_built_in_controllers.py` so all seven Chapter 24
  examples assert their exact stdout transcript and align one-to-one with the
  seven public examples.
- Added `test_controller_chapter_examples_show_reader_visible_output()` to
  `tests/book_examples/test_public_mdx_snippets.py` so the public page must
  keep seven visible output blocks and the key controller transcript lines.
- Kept the existing positive-pass-language guard active while adding the
  visible output examples.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` to track Chapter 24 as visible-output
  guarded, with the public MDX suite now at 275 tests.

Verification completed:

- `uv run pytest tests/manual/test_24_built_in_controllers.py -q`
  passed with `7 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "24-built-in-controllers-and-automated-turns"`
  passed with `7 passed, 158 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k "24-built-in-controllers-and-automated-turns or controller_chapter"`
  passed with `10 passed, 265 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `275 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 23 Full Visible-Output Cleanup

Chapter 23 now uses the reader-visible output standard across the whole
standard-arena chapter. Every public arena example still asserts the runtime
invariant, but it also prints a concise transcript beside the code in the
webbook. The focused tests assert those stdout transcripts, and the public MDX
guard prevents Chapter 23 from regressing into assertion-only arena snippets.

Changes made:

- Updated
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/23-standard-arena-game-modes.mdx`
  so all six arena examples print concrete output: arena helper surfaces,
  direct arena construction, hero-kit selection, PvP/Codex control mode,
  human-mode start plus session join, and live state/visibility/hero payloads.
- Added a focused EB-23-001 surface test and updated
  `tests/manual/test_23_standard_arena_game_modes.py` so all six Chapter 23
  examples assert their exact stdout transcript and align one-to-one with the
  six public examples.
- Added `test_arena_mode_chapter_examples_show_reader_visible_output()` to
  `tests/book_examples/test_public_mdx_snippets.py` so the public page must
  keep six visible output blocks and the key arena transcript lines.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` to track Chapter 23 as visible-output
  guarded, with the public MDX suite now at 274 tests.

Verification completed:

- `uv run pytest tests/manual/test_23_standard_arena_game_modes.py -q`
  passed with `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "23-standard-arena-game-modes"`
  passed with `6 passed, 159 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k "23-standard-arena-game-modes or arena_mode_chapter"`
  passed with `8 passed, 266 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `274 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 22 Full Visible-Output Cleanup

Chapter 22 now uses the reader-visible output standard across the whole
Gatehouse playable-scenario chapter. Every public scenario example still
asserts the engine invariant, but it also prints a concise runtime transcript
beside the code in the webbook. The focused tests assert those stdout
transcripts, and the public MDX guard prevents Chapter 22 from regressing into
assertion-only scenario snippets.

Changes made:

- Updated
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/22-playable-scenario-packages.mdx`
  so all five scenario examples print concrete output: package surfaces,
  active Gatehouse encounter state, automated pass-to-human handoff,
  deterministic indexed attack plus combat-log capture, and faction-survival
  ending.
- Updated `tests/manual/test_22_playable_scenario_packages.py` so all five
  Chapter 22 focused examples assert their exact stdout transcript and align
  one-to-one with the five public examples.
- Added `test_playable_scenario_chapter_examples_show_reader_visible_output()`
  to `tests/book_examples/test_public_mdx_snippets.py` so the public page must
  keep five visible output blocks and the key Gatehouse transcript lines.
- Made the scenario action example use `fixed_dice_faces(12, 4)` so the attack
  event, damage, HP, and combat-log transcript is deterministic.
- Added `fixed_dice_faces` to the Chapter 22 Code Surfaces table so the
  deterministic dice import is explained where the reader first needs it.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` to track Chapter 22 as visible-output
  guarded, with the public MDX suite now at 273 tests.

Verification completed:

- `uv run pytest tests/manual/test_22_playable_scenario_packages.py -q`
  passed with `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "22-playable-scenario-packages"`
  passed with `5 passed, 160 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k "22-playable-scenario-packages or playable_scenario_chapter"`
  passed with `7 passed, 266 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `273 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 21 Full Visible-Output Cleanup

Chapter 21 now uses the reader-visible output standard across the whole Aegis
Spark spell-feature chapter. Every public learned-magic example still asserts
the engine invariant, but it also prints a concise runtime transcript beside
the code in the webbook. The focused tests assert those stdout transcripts, and
the public MDX guard prevents Chapter 21 from regressing into assertion-only
spell-feature snippets.

Changes made:

- Updated
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/21-spell-and-feature-extensions.mdx`
  so all five spell-feature examples print concrete output: Aegis module
  surfaces, feature-owned spell registration and cleanup, self-or-ally target
  discovery, SpellEvent resolution plus ward cleanup, and trained scene
  composition.
- Updated `tests/manual/test_21_spell_and_feature_extensions.py` so all five
  Chapter 21 focused examples assert their exact stdout transcript and align
  one-to-one with the five public examples.
- Added `test_spell_feature_chapter_examples_show_reader_visible_output()` to
  `tests/book_examples/test_public_mdx_snippets.py` so the public page must
  keep five visible output blocks and the key Aegis Spark transcript lines.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` to track Chapter 21 as visible-output
  guarded, with the public MDX suite now at 272 tests.

Verification completed:

- `uv run pytest tests/manual/test_21_spell_and_feature_extensions.py -q`
  passed with `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "21-spell-and-feature-extensions"`
  passed with `5 passed, 160 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k "21-spell-and-feature-extensions or spell_feature_chapter"`
  passed with `7 passed, 265 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `272 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 20 Full Visible-Output Cleanup

Chapter 20 now uses the reader-visible output standard across the whole Field
Focus content-extension chapter. Every public content-pack example still
asserts the engine invariant, but it also prints a concise runtime transcript
beside the code in the webbook. The focused tests assert those stdout
transcripts, and the public MDX guard prevents Chapter 20 from regressing into
assertion-only extension snippets.

Changes made:

- Updated
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/20-content-extension-basics.mdx`
  so all six content-extension examples print concrete output: module
  surfaces, Field Focus condition lifecycle, registered action
  discovery/execution, carried Field Kit item-use, nearby floor-object
  item-use, and actor/scene factory composition.
- Updated `tests/manual/test_20_content_extension_basics.py` so all six
  Chapter 20 focused examples assert their exact stdout transcript and align
  one-to-one with the six public examples.
- Added `test_content_extension_chapter_examples_show_reader_visible_output()`
  to `tests/book_examples/test_public_mdx_snippets.py` so the public page must
  keep six visible output blocks and the key Field Focus transcript lines.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` to track Chapter 20 as visible-output
  guarded, with the public MDX suite now at 271 tests.

Verification completed:

- `uv run pytest tests/manual/test_20_content_extension_basics.py -q` passed
  with `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "20-content-extension-basics"`
  passed with `6 passed, 159 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k "20-content-extension-basics or content_extension_chapter"`
  passed with `8 passed, 263 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `271 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 19 Full Visible-Output Cleanup

Chapter 19 now uses the reader-visible output standard across the whole
MapEditor and scenario-authoring chapter. Every public authoring example still
asserts the engine invariant, but it also prints a concise payload transcript
beside the code in the webbook. The focused tests assert those stdout
transcripts, and the public MDX guard prevents Chapter 19 from regressing into
assertion-only map-editor snippets.

Changes made:

- Updated
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/19-map-editor-and-scenario-authoring.mdx`
  so all six authoring examples print concrete output: catalog-backed scratch
  map creation, terrain/light/border patches, placed-object effects on
  objective layers, UUID and position deletion, save/load/list/delete
  roundtrip, and preset-to-running-game-to-authoring handoff.
- Updated `tests/manual/test_19_map_editor_scenario_authoring.py` so all six
  Chapter 19 focused examples assert their exact stdout transcript and align
  one-to-one with the six public examples.
- Added `test_map_editor_chapter_examples_show_reader_visible_output()` to
  `tests/book_examples/test_public_mdx_snippets.py` so the public page must
  keep six visible output blocks and the key authoring transcript lines.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` to track Chapter 19 as visible-output
  guarded, with the public MDX suite now at 270 tests.

Verification completed:

- `uv run pytest tests/manual/test_19_map_editor_scenario_authoring.py -q`
  passed with `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "19-map-editor-and-scenario-authoring"`
  passed with `6 passed, 159 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k "19-map-editor-and-scenario-authoring or map_editor_chapter"`
  passed with `8 passed, 262 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `270 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 18 Full Visible-Output Cleanup

Chapter 18 now uses the reader-visible output standard across the whole
client/API chapter. Every public session, state, action, cursor, and catalog
example still asserts the engine invariant, but it also prints a concise
payload transcript beside the code in the webbook. The focused tests assert
those stdout transcripts, and the public MDX guard prevents Chapter 18 from
regressing into assertion-only API snippets.

Changes made:

- Updated
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/18-sessions-apis-and-client-payloads.mdx`
  so all five client/API examples print concrete output: session creation and
  game join, state/turn/action payload reading, deterministic indexed attack
  execution, event and combat-log cursor reading with SSE framing, and spell
  catalog metadata.
- Updated `tests/manual/test_18_sessions_api_client_contract.py` so all five
  Chapter 18 focused examples assert their exact stdout transcript.
- Added `test_sessions_chapter_examples_show_reader_visible_output()` to
  `tests/book_examples/test_public_mdx_snippets.py` so the public page must
  keep five visible output blocks and the key client-contract transcript
  lines.
- Made the API attack examples use `fixed_dice_faces(12, 4)` so the damage,
  HP, event-cursor, and combat-log transcript is deterministic.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` to track Chapter 18 as visible-output
  guarded, with the public MDX suite now at 269 tests.

Verification completed:

- `uv run pytest tests/manual/test_18_sessions_api_client_contract.py -q`
  passed with `5 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "18-sessions-apis-and-client-payloads"`
  passed with `5 passed, 160 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k "18-sessions-apis-and-client-payloads or sessions_chapter"`
  passed with `8 passed, 261 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `269 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 17 Full Visible-Output Cleanup

Chapter 17 now uses the reader-visible output standard across the whole
running-encounter chapter. Every public encounter example still asserts the
engine invariant, but it also prints a transcript beside the code in the
webbook. The focused tests assert those stdout transcripts, and the public MDX
guard now prevents Chapter 17 from regressing into assertion-only encounter
snippets.

Changes made:

- Updated
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/17-encounters-turns-and-controllers.mdx`
  so all six encounter examples print concrete output: first encounter
  turn/log capture, encounter start/end controller callbacks, turn lifecycle
  and round advancement, automated advance to a human controller, deterministic
  combat-log listener capture, and faction-survival death-check ending.
- Updated `tests/manual/test_17_encounters_turns_controllers.py` so all six
  Chapter 17 focused examples assert their exact stdout transcript.
- Added `test_encounters_chapter_examples_show_reader_visible_output()` to
  `tests/book_examples/test_public_mdx_snippets.py` so the public page must
  keep six visible output blocks and the key running-game transcript lines.
- Standardized the first Chapter 17 output block from `Expected output:` to
  `Output:` so it matches the cleaned webbook chapters.
- Made the combat-log capture example use `fixed_dice_faces(12, 4)` so its
  damage and HP transcript is deterministic.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` to track Chapter 17 as visible-output
  guarded, with the public MDX suite now at 268 tests.

Verification completed:

- `uv run pytest tests/manual/test_17_encounters_turns_controllers.py -q`
  passed with `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "17-encounters-turns-and-controllers"`
  passed with `6 passed, 159 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k "17-encounters-turns-and-controllers or encounters_chapter"`
  passed with `8 passed, 260 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `268 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 16 Full Visible-Output Cleanup

Chapter 16 now uses the reader-visible output standard across the whole
preset-actor chapter. Every public monster/preset example still asserts the
engine invariant, but it also prints a transcript beside the code in the
webbook. The focused tests assert those stdout transcripts, and the public MDX
guard now prevents Chapter 16 from regressing into assertion-only preset-actor
snippets.

Changes made:

- Updated
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/16-monsters-and-preset-actors.mdx`
  so all six preset-actor examples print concrete output: first stat-block
  actor state, base goblin/skeleton factory state and immunity gates, Goblin
  Nimble Escape action-cost conversion, generic caster spell/gear/potion
  wiring, skeleton warrior/archer/warlock role composition, and Mark Target
  concentration-owned cleanup.
- Updated `tests/manual/test_16_monsters_preset_actors.py` so all six Chapter
  16 focused examples assert their exact stdout transcript.
- Added `test_monsters_chapter_examples_show_reader_visible_output()` to
  `tests/book_examples/test_public_mdx_snippets.py` so the public page must
  keep six visible output blocks and the key preset-actor transcript lines.
- Standardized the first Chapter 16 output block from `Expected output:` to
  `Output:` so it matches the cleaned webbook chapters.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` to track Chapter 16 as visible-output
  guarded, with the public MDX suite now at 267 tests.

Verification completed:

- `uv run pytest tests/manual/test_16_monsters_preset_actors.py -q` passed
  with `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "16-monsters-and-preset-actors"`
  passed with `6 passed, 159 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k "16-monsters-and-preset-actors or monsters_chapter"`
  passed with `8 passed, 259 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `267 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 15 Full Visible-Output Cleanup

Chapter 15 now uses the reader-visible output standard across the whole
character-content chapter. Every public class-feature example still asserts the
engine invariant, but it also prints a transcript beside the code in the
webbook. The focused tests assert those stdout transcripts, and the public MDX
guard now prevents Chapter 15 from regressing into assertion-only class-feature
snippets.

Changes made:

- Updated
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/15-class-features-factories-and-feats.mdx`
  so all six character-content examples print concrete output: first
  factory-built actor state, class factory feature/resource/button wiring,
  Fighter Second Wind and Action Surge spend/rest flow, Berserker Frenzy
  condition ownership and cleanup, Quickened Spell template override and
  cleanup, and Lucky feat d20 rewrite/ignored-roll/cleanup behavior.
- Updated `tests/manual/test_15_class_features.py` so all six Chapter 15
  focused examples assert their exact stdout transcript.
- Added
  `test_class_features_chapter_examples_show_reader_visible_output()` to
  `tests/book_examples/test_public_mdx_snippets.py` so the public page must
  keep six visible output blocks and the key class-feature transcript lines.
- Standardized the first Chapter 15 output block from `Expected output:` to
  `Output:` so it matches the cleaned webbook chapters.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` to track Chapter 15 as visible-output
  guarded, with the public MDX suite now at 266 tests.

Verification completed:

- `uv run pytest tests/manual/test_15_class_features.py -q` passed with
  `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "15-class-features-factories-and-feats"`
  passed with `6 passed, 159 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k "15-class-features-factories-and-feats or class_features_chapter"`
  passed with `8 passed, 258 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `266 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 14 Full Visible-Output Cleanup

Chapter 14 now uses the reader-visible output standard across the whole
spell-family chapter. Every public spell-family example still asserts the
engine invariant, but it also prints a transcript beside the code in the
webbook. The focused tests assert those stdout transcripts, and the public MDX
guard now prevents Chapter 14 from regressing into assertion-only spell-family
snippets.

Changes made:

- Updated
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/14-spell-families-and-implemented-spells.mdx`
  so all seven spell-family examples print concrete output: first
  catalog-to-outcome comparison, representative catalog metadata, offensive
  attack/save/auto-hit families, recovery/protection/restoration state,
  Misty Step and False Life state changes, Spike Growth zone ownership and
  cleanup, and Mirror Image/Sleep condition behavior.
- Updated `tests/manual/test_14_spell_families.py` so all seven Chapter 14
  focused examples assert their exact stdout transcript.
- Added
  `test_spell_family_chapter_examples_show_reader_visible_output()` to
  `tests/book_examples/test_public_mdx_snippets.py` so the public page must
  keep seven visible output blocks and the key spell-family transcript lines.
- Standardized the first Chapter 14 output block from `Expected output:` to
  `Output:` so it matches the rest of the webbook.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` to track Chapter 14 as visible-output
  guarded, with the public MDX suite now at 265 tests.

Verification completed:

- `uv run pytest tests/manual/test_14_spell_families.py -q` passed with
  `7 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -q -k "14-spell-families-and-implemented-spells"`
  passed with `7 passed, 158 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q -k "14-spell-families-and-implemented-spells or spell_family"`
  passed with `8 passed, 257 deselected`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `265 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 13 Code-First Spellcasting Output

Chapter 13 now follows the visible-output format for spellcasting. It starts
with a runnable discovered-spell example before the player/designer framing,
source-rule relationship, chapter map, authoring guide, and source table. The
first example creates a Pyromancer, registers Fire Bolt and Magic Missile,
discovers the spell rows, selects the Fire Bolt target by index, casts through
`execute_by_index()`, prints attack/save numbers, discovered rows, target
distance, spell event state, attack and damage rolls, HP delta, action cost,
slot preservation, and combat-log type.

Changes made:

- Added `## First Run: Cast A Discovered Spell` to
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/13-spellcasting-core.mdx`
  immediately after the diagram.
- Added `EB-13-000` / `spell-first-run`, with the first setup panel open by
  default, visible spellcasting setup code, printed discovered-cast output, and
  assertions matching the observed result.
- Updated Chapter 13's chapter map from six moves to seven moves, adding the
  first discovered-cantrip readout step.
- Added Chapter 13 to `CODE_FIRST_CHAPTERS` in
  `tests/book_examples/test_public_mdx_snippets.py`.
- Updated `tests/manual/test_13_spellcasting_core.py` with a focused output
  test for the first spellcasting readout.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` with the new public example and expected
  verification evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_spellcasting_chapter_frontloads_spellcasting_contract -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_magic_and_character_chapters_explain_their_ruling_role -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "13-spellcasting-core" -q`
  passed with `7 passed, 154 deselected`.
- `uv run pytest tests/manual/test_13_spellcasting_core.py -q` passed with
  `7 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `247 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 14 Code-First Spell-Family Output

Chapter 14 now follows the visible-output format for spell families. It starts
with a runnable catalog-to-outcome comparison before the player/designer
framing, source-rule relationship, chapter map, authoring guide, and source
table. The first example reads Fire Bolt, Sacred Flame, and Magic Missile from
`ALL_SPELLS`, prints their attack/save/auto-hit family metadata, then casts
each one into the same target with deterministic dice so the output shows
rolls, damage, HP deltas, and first-level slot spending.

Changes made:

- Added `## First Run: Compare Three Offensive Families` to
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/14-spell-families-and-implemented-spells.mdx`
  immediately after the diagram.
- Added `EB-14-000` / `spell-family-first-run`, with the first setup panel open
  by default, visible spell-family setup code, printed catalog/outcome output,
  and assertions matching the observed result.
- Updated Chapter 14's chapter map from six moves to seven moves, adding the
  first attack/save/auto-hit family comparison step.
- Added Chapter 14 to `CODE_FIRST_CHAPTERS` in
  `tests/book_examples/test_public_mdx_snippets.py`.
- Updated `tests/manual/test_14_spell_families.py` with a focused output test
  for the first spell-family readout.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` with the new public example and expected
  verification evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_spell_families_chapter_frontloads_family_contract -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_magic_and_character_chapters_explain_their_ruling_role -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "14-spell-families-and-implemented-spells" -q`
  passed with `7 passed, 155 deselected`.
- `uv run pytest tests/manual/test_14_spell_families.py -q` passed with
  `7 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `248 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 15 Code-First Character-Content Output

Chapter 15 now follows the visible-output format for class features and
factories. It starts with a runnable factory-built actor readout before the
player/designer framing, source-rule relationship, chapter map, authoring
guide, and source table. The first example creates a level-five fighter,
Berserker barbarian, and sorcerer from their real factory configs, then prints
the feature conditions, class resources, feature buttons, spell slots, and
registered spell templates attached to those actors.

Changes made:

- Added `## First Run: Build Three Playable Classes` to
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/15-class-features-factories-and-feats.mdx`
  immediately after the diagram.
- Added `EB-15-000` / `class-first-run`, with the first setup panel open by
  default, visible class-factory setup code, printed actor-state output, and
  assertions matching the observed result.
- Updated Chapter 15's chapter map from five moves to six moves, adding the
  first factory-built actor readout step.
- Added Chapter 15 to `CODE_FIRST_CHAPTERS` in
  `tests/book_examples/test_public_mdx_snippets.py`.
- Updated `tests/manual/test_15_class_features.py` with a focused output test
  for the first character-content readout.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` with the new public example and expected
  verification evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_class_features_chapter_frontloads_character_content_contract -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_magic_and_character_chapters_explain_their_ruling_role -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "15-class-features-factories-and-feats" -q`
  passed with `6 passed, 157 deselected`.
- `uv run pytest tests/manual/test_15_class_features.py -q` passed with
  `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `249 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 16 Code-First Monster Output

Chapter 16 now follows the visible-output format for monsters and preset
actors. It starts with a runnable stat-block actor readout before the
player/designer framing, source-rule relationship, chapter map, authoring
guide, and source table. The first example creates a goblin, skeleton, and
darkvision-disabled skeleton from real monster factories, then prints HP, AC,
loadout, action rows, senses, damage traits, condition-immunity gates, and
immunity cancellation results.

Changes made:

- Added `## First Run: Turn Stat Blocks Into Actors` to
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/16-monsters-and-preset-actors.mdx`
  immediately after the diagram.
- Added `EB-16-000` / `monster-first-run`, with the first setup panel open by
  default, visible monster factory setup code, printed stat-block actor output,
  and assertions matching the observed result.
- Updated Chapter 16's chapter map from five moves to six moves, adding the
  first stat-block actor readout step.
- Added Chapter 16 to `CODE_FIRST_CHAPTERS` in
  `tests/book_examples/test_public_mdx_snippets.py`.
- Updated `tests/manual/test_16_monsters_preset_actors.py` with a focused
  output test for the first monster readout.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` with the new public example and expected
  verification evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_monsters_chapter_frontloads_preset_actor_contract -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_running_game_authoring_chapters_explain_their_ruling_role -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "16-monsters-and-preset-actors" -q`
  passed with `6 passed, 158 deselected`.
- `uv run pytest tests/manual/test_16_monsters_preset_actors.py -q` passed
  with `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `250 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.

## Checkpoint: Chapter 17 Code-First Encounter Output

Chapter 17 now follows the visible-output format for encounters, turns, and
controllers. It starts with a runnable encounter turn before the player/designer
framing, source-rule relationship, chapter map, running-game contract,
authoring guide, and source table. The first example creates adjacent hero and
monster actors, starts a deterministic encounter, opens the hero turn, prints
controller context, executes an encounter-owned attack, then prints damage and
combat-log capture.

Changes made:

- Added `## First Run: Open A Turn And Record An Attack` to
  `/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual/17-encounters-turns-and-controllers.mdx`
  immediately after the diagram.
- Added `EB-17-000` / `encounter-first-run`, with the first setup panel open by
  default, visible encounter setup code, printed turn/log output, and
  assertions matching the observed result.
- Updated Chapter 17's chapter map from five moves to six moves, adding the
  first turn-and-combat-log readout step.
- Added Chapter 17 to `CODE_FIRST_CHAPTERS` in
  `tests/book_examples/test_public_mdx_snippets.py`.
- Updated `tests/manual/test_17_encounters_turns_controllers.py` with a
  focused output test for the first encounter readout.
- Added `fixed_dice_faces` to the Chapter 17 Code Surfaces table.
- Updated `engine_book/parity_matrix.md` and
  `engine_book/completion_matrix.md` with the new public example and expected
  verification evidence.

Verification completed:

- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_encounters_chapter_frontloads_running_game_contract -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_running_game_authoring_chapters_explain_their_ruling_role -q`
  passed with `1 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py::test_public_book_example_executes -k "17-encounters-turns-and-controllers" -q`
  passed with `6 passed, 159 deselected`.
- `uv run pytest tests/manual/test_17_encounters_turns_controllers.py -q`
  passed with `6 passed`.
- `uv run pytest tests/book_examples/test_public_mdx_snippets.py -q` passed
  with `251 passed`.
- `npm run build` passed in `/home/tommaso/Dev/neurodragon_dev_manual` and
  built 29 pages.
