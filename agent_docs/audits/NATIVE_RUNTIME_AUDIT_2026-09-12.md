# Native runtime audit — 2026-09-12

Status: assigned-scope source scan complete; findings are design review, not implementation authorization. No runtime tests/profiles or production/test edits were performed after the audit hard stop. Only this audit note was written. The pending native performance patch is reassessed below and is not presumed accepted.

## Scope and method

Assigned `dnd/` excluding `dnd/content_system/`, `dnd/core/content/`, `dnd/content/`, and `dnd/ai/`. Every Python file below was read as text and parsed with Python AST. The scan inventories validators, raises/assertions, copy/codec/reflection/hash calls, and cache/revision/signature/digest/rollback/checkpoint text. Counts locate owners for semantic reading; they do not establish defects. Targeted owner reads and history evidence are recorded separately.

Coverage: 139 Python files, 101,727 lines, no AST parse failures. The four additional non-Python files were also read: authored_catalog.json parsed successfully (deployments/encounters/rosters/schema_version); the three Markdown documents were reviewed for declared scope and historical-plan status. Their existence does not authorize any work.

## Findings

### Assessment and priority

There are concrete survivors of defensive and audit-oriented design in this scope. They are not all runtime costs, and they are not all dispensable. The clearest cleanup candidates are import-time authentication of trusted presentation data, fixed inventory-size gates, and connector identity proofs repeated in several forms. The largest measured native costs remain construction of general-purpose Tile value graphs and repeated structural queries during perception. The source scan does **not** justify deleting interception, ownership cleanup, subjective grants, or complete event histories.

Priority here orders design review, not a queued implementation plan:

| Priority | Finding | Evidence level | Current classification |
|---|---|---|---|
| 1 | Trusted visual ledger authenticates/re-audits itself on presentation import | Exact runtime caller + complete owner read | Move/remove audit portion candidate; retain actual layer data |
| 1 | UUID/revision/digest/full-field connector proofs overlap | Exact creation, validation, command and mutation owners | Redundant protocol/mechanism candidate; removal changes carried contract |
| 1 | Constructors register provisional objects; local failure cleanup spreads through rules | Exact constructors and plain dictionary-admission callers | Structural simplification candidate; expected cancellation/removal is still necessary |
| 1 | Every Tile eagerly creates four complete modifiable-value graphs | Existing measured startup attribution + exact constructors | Major representation choice to reconsider; no replacement designed |
| 2 | BaseBlock repeats field discovery; setup validates inputs at several nested levels | Existing measured small costs + direct call paths | Demonstrated redundant work; not the main measured bottleneck |
| 2 | Boundary membership queries build/sort snapshots discarded by caller | Existing native-turn profile + exact consumers | Allocation/query simplification candidate without new cache |
| 2 | Frozen contact leaves are deep-copied during sensory reduction | Exact leaf schema + reducer caller | Redundant leaf-copy candidate; enclosing history containers must detach |
| 2 | Hard-coded roster population blocks legitimate content additions | Exact import owner, including our own update | Unnecessary count gate; uniqueness/configuration closure is distinct |
| 3 | Preview caches serialize/sort complete facts to derive cache keys | Exact discovery consumers; no isolated cost measurement | Investigate tradeoff only; cache removal not justified |
| 3 | Reflection and compatibility-style probing survive in finite typed owners | Exhaustive direct-call inventory + targeted reads | Local clarity/ownership debt; not established performance bottleneck |

### N01 — a trusted visual ledger performs a historical audit during presentation loading

`dnd/items/authored_variant_inventory.py:345` reads the bundled ledger and runs `AuthoredItemVariantLedger.model_validate_json` at import. The after-validator at `:229` counts categories/variants, serializes the complete normalized inventory, recomputes SHA-256 (`:32`, `:239`), checks historical raw-ID collision evidence (`:309`), and scans factory/slot ownership. The stored inventory digest has no runtime consumer outside this self-comparison. The source provenance hash field at `:208` is metadata, not a source-file integrity check.

The **actual current runtime caller is presentation**, `game/animation_data.py:17`, `:50`, and `:102`, which uses categories and equipment layers. Native authored item builders now use cold direct definitions; this is not evidence that every native turn hashes item data. Other consumers are import/devtools/tests. Full owner read: all 376 lines.

Judgment: the self-authentication, historical collision proof, and fixed source counts need not be on the ordinary shipped-data import path. Actual category/layer mappings and unambiguous bindings remain useful. This resembles the rejected source-audit mechanism but is a separate surviving artifact; no replacement hash/cache is proposed. No isolated timing for this ledger was measured in this audit. Source origin: `d0d17c8` (2026-07-26, authored content v1); this file is unchanged from `16a6bfe` to pre-audit HEAD.

### N02 — connector commands carry several proofs of the same current facts

`dnd/core/traversal_connectors.py:132` serializes UUID, definition, endpoints and revision into SHA-256. `TraversalConnector.create` at `:172` computes it; `validate_runtime` at `:223` rebuilds the definition and recomputes it immediately. The definition was already validated. `TraversalConnectorCommand` at `:245` carries UUID, revision, digest and oriented endpoints.

`dnd/actions.py:1156` emits that command, `:1198` embeds revision/digest/coordinates into a generated template name, and `_current_connector` at `:1217` compares revision and digest **as well as** authored ID, kind, presentation key, movement/action costs, provocation, bidirectionality, source position and endpoint elevations. GridMap already owns replacement/enabling and increments the connector's revision (`dnd/core/gridmap.py:949`, `:990`); immutable connector values are indexed by UUID.

Judgment: there is a real stale-command concern when an actual connector changes, but revision+identity+current oriented support validation and digest/full-field equality substantially overlap. The SHA is not an authentication secret. This is a concrete mechanism to simplify, not merely a name matching a pattern. It requires reviewing the serialized discovery/event contract, not just deleting `_connector_digest`. Current turn benchmarks did not exercise connector traversal; no speed claim. Full connector module read (287 lines), complete create/validate/command owners, complete GridMap connector mutation and action selection/check paths. Introduced on current ancestry at `205fd67` (2026-08-30), already in `16a6bfe`.

### N03 — provisional registration drives repeated defensive cleanup in rules

`dnd/core/base_object.py:61` registers an object during construction. BaseBlock (`dnd/core/base_block.py:251`) and Entity (`dnd/entity.py:633`) add their own registry/presence setup. Condition application tracks admitted modifiers, handlers, children and cross-block links (`dnd/core/base_conditions.py:409`); generic uncommitted cleanup lives at `:692` and `dnd/core/base_block.py:841`/`:1208`.

The repetitive **local** exception scaffolding is visible in `dnd/classes/rage.py:379`, `:395`, `:410`, `:430`: construct a new modifier, try to add it, catch `BaseException`, unregister it, then record its UUID. The concrete `StaticValue.add_advantage_modifier` implementation (`dnd/core/values.py:272`) is a dictionary assignment plus UUID return. That local call has no D&D cancellation/interception path. Thus at least those per-modifier exception wrappers defend arbitrary execution/allocation failure rather than a rules outcome. The same pattern surrounds handler admission (`rage.py:347`, `dnd/classes/sorcerer.py:1086`), whose actual binding/queue admission is more involved and must be distinguished.

Judgment: eager constructor side effects followed by manual compensation are a larger design issue than one validator micro-optimization. A coherent owner-admission design could make portions unnecessary. That is **not** a finding that all cleanup is wrong: condition cancellation before commitment, concentration removal, child/linked condition lifetimes, spatial footprint replacement and committed-vs-unpublished state all have real native users. For example `dnd/spatial/area_conditions.py:297`, `:330`, `:484`, `:638` preserve displaced footprint mechanics; `dnd/game.py:16`/`:34` distinguishes membership commitment from later publication failure. Removing these wholesale would change existing behavior. No fault-injection test is treated as proof that every local wrapper is needed.

Scope of evidence: complete BaseObject, Game, runtime reset and selected full condition admission/cleanup/footprint owners; exhaustive `except BaseException` scan across all 139 files. No exception mechanism was added or removed. General uncommitted cleanup enters at `205fd67` (2026-08-30); the repetitive Rage owner-admission form at `1e65f61` (2026-09-02), both before `16a6bfe`. No isolated runtime cost measured.

### N04 — general-purpose modifier graphs are eagerly allocated for every terrain cell

`dnd/core/base_tiles.py:319`/`:351` constructs four independent `ModifiableValue` roots; each root constructs static/contextual self and target channels plus base modifier ownership. Zero-cost swimming/burrowing still get their own graphs and disabling constraints. The four modes and modifier support are real capabilities: hazards/conditions can change terrain movement. The choice to allocate all general-purpose registered graphs for every untouched cell is an implementation representation, not a D&D requirement.

Prior saved smoke profile (`.runtime/startup-profile/smoke.prof`, summarized in `agent_docs/STARTUP_PROFILE_2026-09-12.md`) attributes 16,384 of 16,480 `ModifiableValue.create` calls to 4,096 Tile creations, with 1.534s cumulative profiled time in those calls. It is a nested attribution, not an independent wall-time saving. Registry ownership and per-cell mutable independence cannot be replaced by shared mutable defaults to obtain a win.

Judgment: a serious performance design review should address cold/default versus modified terrain representation, rather than declaring completion after small validation changes. No alternative has been designed, benchmarked or authorized here; no new lazy framework is proposed. The four-graph design already exists at `2cc3f36` (2026-04-22), and values/base_tiles/gridmap are unchanged between `16a6bfe` and pre-patch HEAD.

### N05 — repeated model/setup validation has identifiable smaller redundancies

- `dnd/core/base_block.py:197` scans every Pydantic field using `getattr`. `set_values_and_blocks_source` at `:209` calls it, propagates source/target/context, then `validate_values_and_blocks_source_and_target` at `:220` rechecks source identity, and `populate_blocks_and_values` at `:241` repeats the entire field scan. The intervening source check does not introduce new fields. The second scan is directly redundant; preserving actual discovery/propagation does not require retaining two scans. Existing smoke profile: 8,496 scans, about .148s cumulative, not the leading cost. Scan structure introduced by `d80dab2` (2026-07-01); inherited at `16a6bfe`.
- `dnd/world_authoring.py:604` validates complete Tile inputs before creating an edit root. `GridMap.set_tile` (`dnd/core/gridmap.py:464`) repeats validation, and `Tile.create` (`dnd/core/base_tiles.py:336`) repeats it again before allocation. These public entry points each have a reason to reject bad authoring input; nested trusted calls need not all redo the same scalar checks. Prior smoke profile: 8,192 calls to the tile-input validator, .023s cumulative. Do not confuse this small repeated check with the four value graphs.
- Tile replacement/detachment validates a complete owned movement graph in `GridMap.validate_tile_detachment` (`dnd/core/gridmap.py:661`) and `release_tile_owned_movement_graph` (`dnd/core/base_tiles.py:622`), and world authoring preflights detachment too (`dnd/world_authoring.py:654`). Live entities/conditions/objects/connectors referencing a Tile are genuine reasons to reject detachment. The graph authentication performs repeated registry/UUID scans; this is a consolidation candidate in a reviewed owner boundary, not permission to free live shared state. Graph validator added at `24f293d` (2026-09-03).

The native audit did not modify these owners. The pending StaticValue guard is assessed separately below.

### N06 — repeated boundary traversal constructs facts the caller discards

`SpatialSensesSystem._collect_boundary_evidence` (`dnd/blocks/sensory.py:916`) walks four directions for every admitted optical/nonvisual position. Each evidence record contains position, visual/nonvisual route and sense modes; those are real perception facts, not redundant observer-independent decoration.

Pre-patch `GridMap.get_boundary_route_layers` (`dnd/core/gridmap.py:2935`) constructs an entire WorldEdgeView (`:2893`) to decide whether the exit layer allows observing an entry object. Full key validation, both endpoint structures and movement-surface facts are built even when no entry object exists. The pending patch narrows that query; it is not yet an accepted final design.

Separately `GridMap.get_boundary_objects_at` (`:2786`) obtains a sorted immutable band tuple from `Tile.get_boundary_object_bands` (`dnd/core/base_tiles.py:158`), then discards ordering into a set; a height-specific lookup reconstructs a dictionary from that tuple. This is redundant allocation in an exact runtime caller. Direct defensive membership snapshots can preserve the owner's semantics without stored caches or a second spatial representation.

Prior native-only profile (`.runtime/performance-recovery/native-profile-before.prof/.txt`): 266 `recompute_observer` calls / 6.218s cumulative; 266 boundary-evidence calls / 3.581s; 180,772 route queries / 3.418s; 255,997 full world-edge queries / 3.517s; 971,378 band-snapshot queries / 1.610s. These times **overlap** and include profiler overhead. No new profile was run in this audit.

A broad route/contact cache is not automatically safe under the existing revisions: an unblocking/nonstructural object's placement/removal can change membership with an empty revision-channel set (`dnd/core/gridmap.py:2415`, `:2637`); orientation updates also do not bump channel revisions. A new cache would require extra invalidation ownership. The audit favors examining direct redundant work first. Boundary-evidence/world-edge design enters current ancestry at `205fd67` (2026-08-30); it is not the same as April's simpler coordinate contacts.

### N07 — deep-copy immutable leaves, not all sensory snapshots

`dnd/types/senses.py:35` defines frozen `PerceivedContact` with only immutable tuples, integers, booleans and enum leaves. `reduce_senses_snapshot` (`dnd/blocks/sensory.py:348`) nevertheless deep-copies every changed entity/object contact (`:376`, `:386`). Sharing these frozen leaves is different from sharing the mutable dictionaries that own the historical snapshot. The current reducer must still return detached sets/maps so latest reduction cannot overwrite playback history.

`SenseMode` at `dnd/types/senses.py:22` is **not frozen**. Its copies at `dnd/blocks/sensory.py:400` therefore cannot be classified the same way without an explicit value contract change. `SensesSnapshot`'s frozen dataclass likewise contains mutable sets/maps; frozen alone does not make the entire graph immutable.

The contact-copy pattern predates the current public projection work; the recovery changed initialization/Protocol support and caller integration. No measurable saving is claimed. This is a concrete narrow copy candidate, not justification for disabling event/snapshot detachment globally.

### N08 — hard-coded population gates preserve a previous work scope at runtime

`dnd/monsters/srd_roster.py:1504` builds the canonical declarations at import and requires exactly 28 IDs, as well as unique IDs/names/orders and matching configuration helpers. Matching IDs to actual builders and rejecting ambiguity are useful closure checks. Exactly 28 is not a game rule; adding a legitimate creature currently requires editing the data **and** this fixed gate.

We participated in preserving this pattern: `7365184` (2026-09-10, creature/equipment/movement coverage) changed the previous 27 guard to 28 for Dretch. That should not be treated as good design because the existing tests required the count. Removing the fixed count while retaining appropriate declaration closure is a candidate, not implemented here. Measured cost is not the issue; maintenance coupling is.

Related authoring-time checks include the exact learned-reaction handler dependency loop in `dnd/spells/reaction_spell_content.py:208` and catalog metadata validators in `dnd/spells/content_metadata.py`. Their actual relationships are meaningful, but validating static known declarations on every import belongs in the broader content-assembly review. No new monster framework or spell-by-spell work is implied.

### N09 — preview cache keys and reflection require discrimination

`dnd/entity.py:4934` builds an AoE definition key with `model_dump_json(..., fallback=repr)`. `_prepare_aoe_caches` (`:4969`) re-sorts visible positions and contact metadata; `_prepare_position_preview_cache` (`:5462`) rebuilds sorted visibility, walkability, entity/object and collision facts alongside map/path revisions. These are real action-discovery callers (`:6136`, `:6377`), not dead utilities. Their cache keys have broad mutable inputs. It is possible to spend significant work determining whether a cache is reusable, but this audit has not isolated that cost or proved a simpler key preserves current semantics. Source owner added before rollback (`3fdc402`, 2026-07-21, for shape-key owner). Keep this an open measured-design question, not another speculative cache project.

The complete direct reflection-call inventory follows the file table. Some are finite-field accessors (`abilities.py:310`, `skills.py:365`, equipment slots); some are compatibility-style probing where a known typed owner should suffice (`base_actions.py:78`, `:1372`, `entity.py:4577`); some attach/read spell metadata through class namespaces (`spells/content_metadata.py:207`). This conflicts with the repository's desired explicit DAG/data style in places, but does not by itself establish broken gameplay. We should not replace it with another dynamic adapter system.

`Entity.get_target_entity(copy=True)` (`dnd/entity.py:1531`) has a deep-copy branch, but the only source caller found uses the default live lookup (`:1589`). It is not an explanation for measured turn slowness. `ContextualModifier.cached_results` (`dnd/core/modifiers.py:357`) stores results **after executing the callable each time**; it is consulted by breakdown/log/rule-evidence readers (`values.py:2069`, `:2100`, `actions.py:1537`, `conditions.py:2399`). Calling it a computation cache and deleting it would misunderstand its purpose. Its broad exception-to-None behavior at `modifiers.py:343` can hide a rule failure behind a log; it is a separate explicit semantics choice, not a proven cause of this performance problem.

## Machinery examined that is not established as unnecessary

| Owner family | Actual user/caller and distinction |
|---|---|
| Event identity, lineage and history | `events.py:507` completes descendants before aggregating completion metadata; `:2272` stores all phase versions and parent links. Complete subjective playback depends on those facts. They are not an accidental second rendering queue. |
| Event-time identity/location grants | `events.py:2280` copies grant sets and merges inherited identity while location uses actual current observations. The user explicitly required these existing rules. No masking/subjectivity redesign is an audit outcome. |
| Committed vs interceptable publication | `events.py:2047` declaration publication, `:2069` equipment preflight, `:2155` committed fact delivery protect different real boundaries. Equipment uses preflight at `blocks/equipment.py:1544`; birth uses completed fact publication (`entity.py:1244`). Committed handler deep copies prevent mutation of already committed records; unregistered declarations permit expected cancellation. |
| Batch and passive callback protection | `events.py:1797` batches passive notifications but leaves native handlers immediate. Exception logging for passive callbacks prevents a subscriber from undoing authoritative gameplay. A flushed batch is not a successful action. |
| Entity/Game/GridMap ownership | `game.py:16`, `entity.py:648`, `gridmap.py:2043` distinguish registry existence, composed birth, deployment and committed membership. Historical rule outcomes must not be rolled back merely because later publication fails. This differs from per-modifier defensive scaffolding in N03. |
| Condition graphs and modifiers | Conditions own exact modifier/handler UUIDs, subconditions and cross-block links (`base_conditions.py:409`); removal traverses those (`base_block.py:1018`). Hold, paralysis, concentration and auras exercise real state lifetimes. Name/source/UUID indexes are access indexes over those owners, not a reason to invent a second rules reducer. |
| Cost and action validation | `base_actions.py:1779`, action-economy/resource owners, Move/Step and reaction code check real affordability, target eligibility and changed state before the relevant phase. Revalidation after an actual OA/condition is not the hypothetical retroactive cancellation concern previously rejected by the user. |
| Spatial caches and indexes | GridMap channel revisions (`gridmap.py:377`), occupancy revision (`:357`), FOV/path caches, and indexed observer candidates (`blocks/sensory.py:1035`) serve actual world/perception queries. The audit did not find a second multithreaded simulation loop in this scope. |
| Reset | Complete `runtime_reset.py` read: clears shared engine registries, event systems and map for an actual new session; it does not construct a server/worker. The optional rectangle is explicit. Per-session isolation remains necessary while registries are global. |
| Terminal summary hashing | `analytics/models.py:546`/`:564` serializes/hashes final reports, not each turn. Actual server storage validates the digest (`server/game_directory/repository.py:5268`). It is not the rejected import-time source audit; whether terminal archival integrity is wanted belongs to that product/storage scope. |
| Optional timing and controller continuation | Complete `action_timing.py`, `core/action_execution.py`, `controller.py` read. ContextVars carry optional instrumentation or current movement continuation scope. They are not threads; the real AI consumer is outside this agent's ownership. |
| Pure schemas and helpers | `dnd/types/`, geometry/elevation/material/light helpers, movement legality, dice/score bounds and finite enums express actual values/units. Strict authoring/serialized-input checks should not be classified as redundant solely by counting validators. |

## Pending native performance patch: reassessment

The audit did not change or validate the pending three-file patch. It has 24 added/20 removed production lines at the audit boundary:

1. `values.py:185`: return early for incoming StaticValue and iterate three outgoing dictionaries without list concatenation. It preserves the current self-target error on outgoing buckets. This is a local redundant-work removal, not an answer to the four-graph representation cost. No new post-audit test or benchmark validates it.
2. `base_tiles.py:131`: five empty PrivateAttr factories become literal empty defaults, which the installed Pydantic copies per instance. Installed source evidence: `pydantic/_internal/_fields.py:705` delegates no-factory defaults to `smart_deepcopy`; `_utils.py:335` uses builtin empty-collection `.copy()`. This relies on an unobvious library behavior to avoid repeated factory signature inspection. It does not share mutable Tile state under that implementation, but it remains a narrowly motivated workaround rather than a broader simplification of Tile ownership. Earlier skill/test approval is not a reason to keep it automatically.
3. `gridmap.py:2964`: boundary-contact query avoids a full WorldEdgeView and irrelevant entry structural contributions. It still constructs and discards an AdjacentEdgeKey solely to preserve exact input-validation behavior. That remnant illustrates why preserving every previous defensive check is not the same as choosing the cleanest boundary. No cache or new invalidation owner was added. Whether the public query should validate there is a design decision for the whole audit; no further change is authorized.

The six added test cases are also pending work; they are evidence about selected behavior, not authority that these choices are globally correct. The user's hard stop takes precedence over continuing them.

## Coverage, source history and remaining unknowns

All 139 Python files were inventoried, read by the static scanner, AST parsed and scanned for validators/assertions/raises, copy/codec/reflection/hash calls, and cache/rollback/revision vocabulary. A second pass walked import nodes (no direct threading/multiprocessing/asyncio/network library imports in this assigned scope), class/function owner docstrings, and all `except BaseException` locations. Four non-Python files were read; the JSON parsed successfully. This is **not a claim of line-by-line human review of all 101,727 lines**. Complete smaller-owner reads and complete targeted methods of large owners are listed in the findings; low-signal files received static/owner-summary coverage rather than exhaustive rule re-derivation.

The 139 files divide into: 16 root modules, 3 analytics, 13 blocks, 7 classes, 37 core, 3 extensions, 8 items, 2 maps, 10 monsters, 4 origins, 5 scenarios, 6 spatial, 16 spells, 9 types. The inventory below records every path and scan count. The AST inventory intentionally counts explicit method/function copying calls, not every `dict(...)`/`set(...)` materialization; N05/N06/N07 cover important concrete allocations found in targeted reads.

Compared with `16a6bfe`, 14 assigned native files changed before this pending performance patch: equipment, sensory, base_actions, base_object, dice, events, entity, consumables, multiattack_definitions, srd_roster, traits, battlefield_catalog, divination and types/senses. Their recovery changes concern event passive decode/registry separation, complete initialization and stance after-values, lineage shape, finite new creature/item data, and actual True Seeing source/self-target fixes. The major generic validation, connector, value and spatial machinery discussed above already survived the rollback baseline. April `2cc3f36` is useful to date some old costs, but its perception/world representation differs; raw speed comparisons are not feature-equivalence claims.

Remaining unknowns are bounded: isolated cost of the visual-ledger audit and connector proofs; cost/benefit of broad preview signatures; exact savings/behavior of the unaccepted native patch; and how best to simplify construction/admission while preserving supported modifiers and conditions. No new server run, native test, benchmark, profile, or speculative mechanics fix was performed. Authored content/registration internals and AI consumers are intentionally assigned to other reviewers; cross-scope callers are cited only to establish where an owned mechanism is used. This audit is input to a whole-codebase decision, not permission to implement a cleanup queue.

## Complete file inventory

`V` = validator functions; `R` = raise statements; `A` = asserts; `C` = copying calls; `J` = codec/model-validation calls; `F` = reflection calls; `H` = hash-related AST call nodes (nested hash/hexdigest expressions count separately); `K` = lines mentioning cache/revision/signature/digest/rollback/checkpoint. These are textual/AST evidence, not severity.

| File | Lines | V | R | A | C | J | F | H | K |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dnd/__init__.py | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/action_dispatch.py | 97 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/action_timing.py | 44 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/actions.py | 5090 | 1 | 3 | 1 | 6 | 19 | 0 | 0 | 9 |
| dnd/actions_functional.py | 768 | 0 | 21 | 0 | 2 | 0 | 4 | 0 | 0 |
| dnd/analytics/__init__.py | 73 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4 |
| dnd/analytics/game_summary.py | 1876 | 0 | 2 | 0 | 1 | 1 | 8 | 0 | 3 |
| dnd/analytics/models.py | 585 | 1 | 1 | 0 | 0 | 2 | 0 | 1 | 9 |
| dnd/blocks/__init__.py | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/blocks/abilities.py | 387 | 0 | 3 | 0 | 0 | 0 | 2 | 0 | 0 |
| dnd/blocks/action_economy.py | 1228 | 0 | 33 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/blocks/appearance.py | 175 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| dnd/blocks/base_item.py | 945 | 2 | 6 | 0 | 2 | 0 | 0 | 0 | 5 |
| dnd/blocks/creature_proficiencies.py | 280 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/blocks/equipment.py | 1779 | 1 | 12 | 0 | 5 | 0 | 8 | 0 | 0 |
| dnd/blocks/health.py | 811 | 2 | 13 | 0 | 0 | 0 | 0 | 0 | 2 |
| dnd/blocks/inventory.py | 277 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/blocks/saving_throws.py | 326 | 0 | 1 | 0 | 0 | 0 | 2 | 0 | 0 |
| dnd/blocks/sensory.py | 1243 | 0 | 4 | 0 | 7 | 0 | 0 | 3 | 14 |
| dnd/blocks/skills.py | 419 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| dnd/blocks/spellcasting.py | 737 | 4 | 25 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/classes/__init__.py | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/classes/barbarian.py | 1598 | 0 | 2 | 0 | 2 | 2 | 0 | 0 | 0 |
| dnd/classes/feats.py | 144 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| dnd/classes/fighter.py | 1816 | 0 | 1 | 0 | 1 | 2 | 0 | 0 | 0 |
| dnd/classes/paladin.py | 179 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/classes/rage.py | 1257 | 0 | 11 | 0 | 1 | 3 | 0 | 0 | 0 |
| dnd/classes/sorcerer.py | 1573 | 0 | 23 | 0 | 1 | 0 | 0 | 0 | 0 |
| dnd/conditions.py | 2466 | 0 | 26 | 1 | 0 | 1 | 0 | 0 | 0 |
| dnd/controller.py | 311 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/core/__init__.py | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/core/action_execution.py | 109 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/core/action_types.py | 97 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/core/aoe.py | 493 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 12 |
| dnd/core/base_actions.py | 2419 | 10 | 38 | 0 | 11 | 4 | 2 | 0 | 0 |
| dnd/core/base_block.py | 1406 | 3 | 12 | 0 | 1 | 0 | 1 | 0 | 0 |
| dnd/core/base_conditions.py | 1060 | 4 | 9 | 3 | 0 | 0 | 0 | 0 | 0 |
| dnd/core/base_object.py | 196 | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/core/base_tiles.py | 644 | 1 | 24 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/core/combat_log.py | 826 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| dnd/core/condition_types.py | 56 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/core/creature_types.py | 58 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/core/damage.py | 135 | 1 | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/core/dice.py | 368 | 2 | 5 | 0 | 0 | 0 | 0 | 0 | 4 |
| dnd/core/dijkstra.py | 217 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/core/effect_types.py | 54 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/core/elevation.py | 39 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/core/equipment_types.py | 108 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/core/events.py | 5542 | 11 | 62 | 2 | 19 | 7 | 3 | 1 | 1 |
| dnd/core/feature_grants.py | 32 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/core/geometry.py | 354 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 12 |
| dnd/core/gridmap.py | 4453 | 0 | 82 | 6 | 12 | 0 | 0 | 0 | 282 |
| dnd/core/item_types.py | 150 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/core/language_types.py | 32 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/core/life_types.py | 25 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/core/modifiers.py | 732 | 1 | 19 | 0 | 0 | 0 | 0 | 0 | 5 |
| dnd/core/naming.py | 12 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/core/positioning.py | 24 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/core/presentation_geometry.py | 101 | 1 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/core/proficiency_types.py | 79 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/core/progression.py | 231 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/core/saving_throw_types.py | 69 | 2 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/core/shadowcast.py | 166 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| dnd/core/spell_execution.py | 95 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/core/traversal_connectors.py | 287 | 4 | 9 | 0 | 0 | 3 | 0 | 2 | 15 |
| dnd/core/values.py | 2330 | 5 | 17 | 0 | 2 | 0 | 0 | 0 | 13 |
| dnd/core/world_edges.py | 194 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/creature_transforms.py | 362 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/encounter.py | 1448 | 0 | 29 | 0 | 4 | 0 | 0 | 0 | 0 |
| dnd/entity.py | 6955 | 4 | 79 | 2 | 28 | 3 | 9 | 0 | 133 |
| dnd/extensions/__init__.py | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/extensions/aegis_spark.py | 191 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/extensions/field_focus.py | 221 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/game.py | 54 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/items/__init__.py | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/items/authored_variant_inventory.py | 376 | 4 | 22 | 0 | 0 | 3 | 0 | 2 | 6 |
| dnd/items/consumables.py | 1178 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/items/environment.py | 349 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/items/environment_interactables.py | 421 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 |
| dnd/items/spell_items.py | 624 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 |
| dnd/items/torches.py | 680 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 |
| dnd/items/visual_variants.py | 14 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/maps/__init__.py | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/maps/arena_layout.py | 166 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/monsters/__init__.py | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/monsters/bestiary.py | 878 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 |
| dnd/monsters/bestiary_content.py | 630 | 0 | 0 | 0 | 0 | 8 | 0 | 0 | 0 |
| dnd/monsters/circus_fighter.py | 150 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/monsters/circus_fighter_conditions.py | 544 | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/monsters/configured_srd_creatures.py | 235 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 |
| dnd/monsters/multiattack_definitions.py | 258 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/monsters/skeleton_abilities.py | 293 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/monsters/srd_roster.py | 1679 | 0 | 2 | 0 | 1 | 2 | 0 | 0 | 0 |
| dnd/monsters/traits.py | 1539 | 0 | 0 | 0 | 5 | 1 | 1 | 0 | 0 |
| dnd/origins/__init__.py | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/origins/dragonborn.py | 263 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| dnd/origins/half_orc.py | 65 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/origins/halfling.py | 50 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/reactions.py | 107 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/runtime_reset.py | 64 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/scenarios/__init__.py | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/scenarios/battlefield_catalog.py | 1209 | 0 | 21 | 0 | 1 | 0 | 0 | 0 | 15 |
| dnd/scenarios/encounter_assembler.py | 548 | 0 | 16 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/scenarios/encounter_catalog.py | 105 | 0 | 5 | 0 | 0 | 4 | 0 | 0 | 0 |
| dnd/scenarios/encounter_compatibility.py | 417 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 1 |
| dnd/spatial/__init__.py | 42 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/spatial/area_conditions.py | 1353 | 1 | 34 | 1 | 0 | 0 | 0 | 0 | 7 |
| dnd/spatial/environmental_conditions.py | 1187 | 0 | 6 | 1 | 0 | 0 | 0 | 0 | 0 |
| dnd/spatial/memberships.py | 281 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/spatial/restraints.py | 296 | 0 | 1 | 0 | 0 | 1 | 0 | 0 | 0 |
| dnd/spatial/transitions.py | 145 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/spells/__init__.py | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/spells/abjuration.py | 3515 | 0 | 5 | 8 | 2 | 1 | 2 | 0 | 0 |
| dnd/spells/base.py | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/spells/catalog_content.py | 951 | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/spells/conjuration.py | 4866 | 0 | 3 | 1 | 0 | 0 | 0 | 0 | 0 |
| dnd/spells/content_metadata.py | 446 | 3 | 14 | 0 | 0 | 0 | 3 | 0 | 0 |
| dnd/spells/divination.py | 442 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| dnd/spells/effect_ids.py | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/spells/enchantment.py | 1936 | 0 | 3 | 9 | 2 | 0 | 0 | 0 | 1 |
| dnd/spells/evocation.py | 5006 | 0 | 1 | 8 | 4 | 0 | 0 | 0 | 0 |
| dnd/spells/illusion.py | 1489 | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 0 |
| dnd/spells/infernal.py | 323 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/spells/necromancy.py | 2476 | 0 | 0 | 12 | 0 | 0 | 1 | 0 | 0 |
| dnd/spells/reaction_spell_content.py | 235 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/spells/spell_utils.py | 78 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| dnd/spells/transmutation.py | 2196 | 0 | 1 | 2 | 0 | 1 | 0 | 0 | 0 |
| dnd/subjective_combat_log.py | 913 | 0 | 0 | 0 | 7 | 0 | 0 | 0 | 5 |
| dnd/tile_conditions.py | 66 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/types/__init__.py | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/types/abilities.py | 46 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/types/character_progression.py | 190 | 0 | 12 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/types/character_receipts.py | 221 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/types/materials.py | 42 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/types/senses.py | 116 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/types/spatial_effects.py | 103 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/types/world.py | 47 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/types/world_placement.py | 103 | 2 | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| dnd/world_authoring.py | 813 | 0 | 47 | 0 | 1 | 0 | 0 | 0 | 2 |

Other owned source/document files:

- `dnd/monsters/SRD_MISSING_TRAITS_PLAN.md`
- `dnd/monsters/SRD_TRAIT_IMPLEMENTATION_MAP.md`
- `dnd/scenarios/authored_catalog.json`
- `dnd/scenarios/README.md`

## Pattern locations for targeted review

### dnd/actions.py

- copy: `559:self.model_copy`, `1179:self.model_copy`, `1809:profile.model_copy`, `4744:self.model_copy`, `4762:base_cost.model_copy`, `4764:cost.model_copy`
- codec: `403:data.model_dump`, `672:BaseCost.model_validate`, `710:BaseCost.model_validate`, `1268:BaseCost.model_validate`, `1665:data.model_dump`, `1722:BaseCost.model_validate`, `2266:BaseCost.model_validate`, `2344:BaseCost.model_validate`, `2425:BaseCost.model_validate`, `2512:BaseCost.model_validate`, `2689:BaseCost.model_validate`, `2817:BaseCost.model_validate`, `2874:BaseCost.model_validate`, `2961:MovementLogData(entity_name=source_name, entity_uuid=str(self.source_entity_uuid), start_position=self.start_position, end_position=self.end_position, path=self.path or [self.start_position, self.end_position], distance_feet=self.jump_distance, movement_cost=self.jump_distance).model_dump`, `3193:BaseCost.model_validate`, `3639:BaseCost.model_validate`, `4006:data.model_dump`, `4173:data.model_dump`, `4787:BaseCost.model_validate`

### dnd/actions_functional.py

- copy: `343:action.model_copy`, `502:target.model_copy`
- reflect: `309:getattr`, `738:setattr`, `765:setattr`, `767:setattr`

### dnd/analytics/game_summary.py

- copy: `740:summary.model_copy`
- codec: `1261:AttackLogData.model_validate`
- reflect: `140:getattr`, `140:getattr`, `140:setattr`, `432:getattr`, `432:getattr`, `432:setattr`, `803:getattr`, `817:getattr`

### dnd/analytics/models.py

- codec: `555:summary.model_dump`, `556:json.dumps`
- hash: `573:sha256`

### dnd/blocks/abilities.py

- reflect: `310:getattr`, `359:getattr`

### dnd/blocks/appearance.py

- codec: `167:(config or AppearanceConfig()).model_dump`

### dnd/blocks/base_item.py

- copy: `780:state.model_copy`, `828:template.model_copy`

### dnd/blocks/equipment.py

- copy: `175:state.model_copy`, `297:state.model_copy`, `431:state.model_copy`, `1337:copy.deepcopy`, `1356:copy.deepcopy`
- reflect: `778:getattr`, `842:getattr`, `1105:getattr`, `1118:setattr`, `1487:setattr`, `1626:setattr`, `1673:getattr`, `1688:setattr`

### dnd/blocks/saving_throws.py

- reflect: `296:hasattr`, `298:getattr`

### dnd/blocks/sensory.py

- copy: `269:mode.model_copy`, `378:contact.model_copy`, `388:contact.model_copy`, `401:mode.model_copy`, `406:mode.model_copy`, `477:mode.model_copy`, `596:mode.model_copy`
- hash: `106:hash`, `364:hash`, `408:hash`

### dnd/blocks/skills.py

- reflect: `365:getattr`

### dnd/classes/barbarian.py

- copy: `313:binding.model_copy`, `929:event.dice_roll.model_copy`
- codec: `1335:BaseCost.model_validate`, `1479:BaseCost.model_validate`

### dnd/classes/fighter.py

- copy: `1341:self.model_copy`
- codec: `744:BaseCost.model_validate`, `973:BaseCost.model_validate`

### dnd/classes/rage.py

- copy: `52:parent_binding.model_copy`
- codec: `577:BaseCost.model_validate`, `699:BaseCost.model_validate`, `1104:BaseCost.model_validate`

### dnd/classes/sorcerer.py

- copy: `59:parent_binding.model_copy`

### dnd/conditions.py

- codec: `2418:SkillCheckLogData(entity_name=entity_name, entity_uuid=str(entity.uuid), skill='stealth', dc=dc, roll=roll_display, bonus_breakdown=stealth_bonus_breakdown, advantage_breakdown=stealth_advantage_breakdown, success=success).model_dump`

### dnd/core/base_actions.py

- copy: `1103:cost.model_copy`, `1130:cost.model_copy`, `1291:self.aoe_shape.model_copy`, `1432:self.model_copy`, `1470:self.model_copy`, `1757:event.model_copy`, `1823:declaration_event.model_copy`, `1837:declaration_event.model_copy`, `1860:execution_event.model_copy`, `1887:execution_event.model_copy`, `1936:execution_event.model_copy`
- codec: `658:BaseCost.model_validate`, `692:BaseCost.model_validate`, `798:data.model_dump`, `837:data.model_dump`
- reflect: `78:getattr`, `1372:getattr`

### dnd/core/base_block.py

- copy: `430:self._attached_light_sources.copy`
- reflect: `200:getattr`

### dnd/core/combat_log.py

- codec: `646:self.model_dump`

### dnd/core/events.py

- copy: `580:self.model_copy`, `616:self.model_copy`, `757:self.model_copy`, `785:self.model_copy`, `881:self.model_copy`, `2009:current_event.model_copy`, `2043:event.model_copy`, `2066:published.model_copy`, `2172:event.model_copy`, `2182:committed.model_copy`, `2197:event.model_copy`, `2250:result.model_copy`, `2255:result.model_copy`, `2601:positions.copy`, `2606:actual_positions.copy`, `2620:positions.copy`, `2687:new_positions.copy`, `2690:new_positions.copy`, `2774:cls._spatial_handlers_by_position[event_key].get(position, []).copy`
- codec: `3049:data.model_dump`, `3174:data.model_dump`, `4734:RollModificationLogData(roll_type=self.roll_type.value.lower(), modifications=facts).model_dump`, `5115:DamageTakenLogData(target_name=target_name, damage=0, damage_type=damage_type_str, source_name=source_name, effect_id=self.effect_id, blocked=True, blocked_reason=reason).model_dump`, `5151:DamageTakenLogData(target_name=target_name, damage=damage, damage_type=damage_type_str, source_name=source_name, effect_id=self.effect_id).model_dump`, `5249:HealLogData(entity_name=target_name, entity_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else '', amount=0, source_description=self.source_description).model_dump`, `5272:HealLogData(entity_name=target_name, entity_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else '', amount=amount, source_description=self.source_description).model_dump`
- reflect: `1973:getattr`, `1975:getattr`, `1977:getattr`
- hash: `1192:hash`

### dnd/core/gridmap.py

- copy: `244:current_event.model_copy`, `252:current_event.model_copy`, `266:self._pending_events.copy`, `267:self._pending_committed_events.copy`, `283:self._cell_subscribers.get(position, set()).copy`, `306:cells.copy`, `316:self._entity_subscriptions.get(entity_uuid, set()).copy`, `1005:previous.definition().model_copy`, `2577:cancellation.model_copy`, `2586:cancellation.model_copy`, `3556:execution.model_copy`, `4432:self._tiles.copy`

### dnd/core/traversal_connectors.py

- codec: `140:definition.model_dump`, `141:endpoint.model_dump`, `144:json.dumps`
- hash: `149:hashlib.sha256`, `149:hashlib.sha256(encoded).hexdigest`

### dnd/core/values.py

- copy: `1855:contextual.model_copy`, `1867:static.model_copy`

### dnd/encounter.py

- copy: `468:self.initiative_order.copy`, `800:self.initiative_order.copy`, `1142:result.model_copy`, `1155:result.model_copy`

### dnd/entity.py

- copy: `1544:target_entity.model_copy`, `1817:roll_result.model_copy`, `2175:roll_event.model_copy`, `2386:proficiency_bonus.model_copy`, `2396:self.proficiency_bonus.model_copy`, `2419:proficiency_bonus.model_copy`, `2447:proficiency_bonus.model_copy`, `2465:bonuses[0].combine_values(list(bonuses)[1:]).model_copy`, `2477:source_bonuses[0].combine_values(list(source_bonuses)[1:]).model_copy`, `2490:bonuses[0].combine_values([bonuses[1]]).model_copy`, `2512:source_bonuses[0].combine_values([source_bonuses[1]]).model_copy`, `2532:bonuses[0].combine_values(list(bonuses)[1:]).model_copy`, `2544:source_bonuses[0].combine_values(list(source_bonuses)[1:]).model_copy`, `3084:take_damage_event.model_copy`, `3193:heal_event.model_copy`, `3202:heal_event.model_copy`, `3860:new_dc.model_copy`, `3919:dc_modifier.model_copy`, `4754:template.model_copy`, `5436:template.model_copy`, `5449:candidate.model_copy`, `5699:template.model_copy`, `6092:template.model_copy`, `6254:shape_template.model_copy`, `6306:template.model_copy`, `6624:use_shape_template.model_copy`, `6671:use_template.model_copy`, `6725:use_template.model_copy`
- codec: `4603:BaseCost.model_validate`, `4938:shape.model_dump_json`, `5337:contract.model_dump_json`
- reflect: `890:getattr`, `4577:getattr`, `4579:getattr`, `4613:getattr`, `4614:getattr`, `4615:getattr`, `5243:getattr`, `5652:getattr`, `6410:getattr`

### dnd/items/authored_variant_inventory.py

- codec: `32:json.dumps`, `240:self.inventory.model_dump`, `345:AuthoredItemVariantLedger.model_validate_json`
- hash: `39:hashlib.sha256`, `39:hashlib.sha256(encoded).hexdigest`

### dnd/items/environment_interactables.py

- copy: `238:super().to_item_presentation_state(stack_count=stack_count).model_copy`

### dnd/items/spell_items.py

- copy: `143:template.model_copy`

### dnd/items/torches.py

- copy: `272:super().to_item_presentation_state(stack_count=stack_count).model_copy`, `554:super().to_item_presentation_state(stack_count=stack_count).model_copy`

### dnd/monsters/bestiary.py

- codec: `556:GOBLIN_APPEARANCE.model_dump`
- reflect: `557:setattr`

### dnd/monsters/bestiary_content.py

- codec: `304:CreatureBuildContext.model_validate`, `349:CreatureBuildContext.model_validate`, `384:CreatureBuildContext.model_validate`, `431:CreatureBuildContext.model_validate`, `480:CreatureBuildContext.model_validate`, `521:CreatureBuildContext.model_validate`, `557:CreatureBuildContext.model_validate`, `593:CreatureBuildContext.model_validate`

### dnd/monsters/configured_srd_creatures.py

- copy: `115:base.descriptor.presentation.model_copy`
- codec: `158:CreatureBuildContext.model_validate`

### dnd/monsters/srd_roster.py

- copy: `1356:context.model_copy`
- codec: `150:MultiattackConfigurationDefinition.model_validate`, `1485:CreatureBuildContext.model_validate`

### dnd/monsters/traits.py

- copy: `538:first.model_copy`, `539:profile.model_copy`, `541:first.model_copy`, `613:profile.model_copy`, `1381:roll.model_copy`
- codec: `631:BaseCost.model_validate`
- reflect: `1495:getattr`

### dnd/origins/dragonborn.py

- codec: `145:BaseCost.model_validate`

### dnd/scenarios/battlefield_catalog.py

- copy: `253:standard.model_copy`

### dnd/scenarios/encounter_catalog.py

- codec: `27:json.loads`, `48:EncounterRosterRecipe.model_validate`, `58:EncounterDeploymentSpec.model_validate`, `67:EncounterRecipe.model_validate`

### dnd/scenarios/encounter_compatibility.py

- copy: `215:static_report.model_copy`, `261:static_report.model_copy`

### dnd/spatial/restraints.py

- codec: `79:BaseCost.model_validate`

### dnd/spells/abjuration.py

- copy: `2453:effective.model_copy`, `3039:roll.model_copy`
- codec: `136:data.model_dump`
- reflect: `1580:getattr`, `2438:getattr`

### dnd/spells/content_metadata.py

- reflect: `212:getattr`, `220:setattr`, `226:getattr`

### dnd/spells/divination.py

- copy: `321:effective.model_copy`

### dnd/spells/enchantment.py

- copy: `1232:effective.model_copy`, `1247:effective.model_copy`

### dnd/spells/evocation.py

- copy: `3176:bludg_roll.model_copy`, `3177:cold_roll.model_copy`, `3932:fire_roll.model_copy`, `3933:radiant_roll.model_copy`

### dnd/spells/necromancy.py

- reflect: `2270:getattr`

### dnd/spells/spell_utils.py

- copy: `64:original_roll.model_copy`

### dnd/spells/transmutation.py

- codec: `1317:BaseCost.model_validate`

### dnd/subjective_combat_log.py

- copy: `101:projected.model_copy`, `270:log.model_copy`, `321:log.model_copy`, `350:original.model_copy`, `351:projected.model_copy`, `448:projected.model_copy`, `650:log.model_copy`

### dnd/world_authoring.py

- copy: `512:previous.definition().model_copy`


## Requested cross-review of the root audit

The root asked for an independent challenge of three cross-scope findings. Source-only check concurs with the distinction, not a blanket dead-code claim:

- `dnd/content_system/condition_effect_population.py:1915` classifies every spell and builds profiles; `:1987` also replaces `APPLIES_CONDITION` dependencies. Those are real cold-assembly outputs. Current `BehaviorBinder.bind_child`/`_bind_declared` (`dnd/content_system/behavior_bindings.py:100`, `:218`) admit class/kind/primitive identity and do not consult those dependency edges or outcome profiles. `dnd/core/content/runtime.py:258` still describes a reviewed dependency-edge requirement, but the present binder implementation does not implement that statement. The table is a parallel maintenance description, not a second active condition-rule executor. Removal would still touch cold registry validation/declaration and server catalog consumers.
- `tests/conftest.py:7` eagerly imports bootstrap and `:11` installs it through a session autouse fixture. A pure replay/unit test collected below this conftest therefore inherits full native content startup. That is a test-process cost and isolation issue, not evidence that passive production replay requires bootstrap.
- `tests/architecture/test_content_recovery_cr0_evidence.py:872` checks frozen manifest shape/counts, hashes governing/implementation plan documents at `:886`, and hashes the maintained-node list at `:945`. Its own module docstring says production never loads the manifest. These preserve historical audit evidence; changing a plan's prose or adding real content must not be mistaken for a gameplay regression merely because a pinned historical assertion fails.

No cross-scope code or tests were edited or executed.
