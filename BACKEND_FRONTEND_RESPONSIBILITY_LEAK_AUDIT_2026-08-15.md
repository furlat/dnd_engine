# Backend / frontend responsibility leak audit

Date: 2026-08-15

## Scope and method

This is a fresh, read-only audit of the active first-party backend and engine source. It was derived from Python and JSON code/data, symbol searches, route tracing, model definitions, projection paths, persistence paths, generated contracts, and tests. Existing Markdown reports were not used as evidence.

Excluded from the source inventory:

- `sdk_deprecated/`
- `to_archive/`
- virtual environments, caches, and Git internals
- existing Markdown documents
- the frontend repository itself

The report treats a field as a frontend responsibility leak when at least one of these is true:

1. It names a concrete renderer asset, layer, clip, frame, tint, VFX route, audio route, or UI grouping.
2. It exists only to tell a renderer how to display an otherwise complete semantic fact.
3. A frontend asset or choreography change changes backend content identity, persistence identity, or replay compatibility.
4. A core backend operation cannot succeed unless a renderer-oriented projection is successfully produced.
5. Backend tooling imports and freezes a frontend asset registry into engine-owned data.

This deliberately does **not** classify every client-consumed fact as a leak. The server legitimately owns authoritative mechanics, authorization, subjective visibility, semantic events, legal actions, affected targets, and save/replay facts.

## Verdict

Yes: frontend responsibility is deeply embedded in the backend. It is not primarily an image-file problem. There are no active first-party raster binaries in `dnd/`, `server/`, `devtools/`, or `content_data/`. The real problem is that renderer identities and animation decisions are modeled as engine state, content identity, map persistence, game-creation requirements, and replication protocol.

There are twelve distinct leak surfaces:

| # | Surface | Severity | Correct treatment |
|---|---|---:|---|
| 1 | Direct terrain sprite filenames | High | Delete after map-save migration; replace with semantic terrain facts |
| 2 | Entity and creature appearance blocks | High | Remove from engine; move renderer taxonomy to frontend |
| 3 | Character-creator appearance catalog | High | Split cosmetics from mechanical premade-character definitions |
| 4 | Item/equipment render identities and map glyphs | High | Remove renderer fields; retain mechanical equipment facts |
| 5 | Content presentation, UI ordering, and asset digests | Critical | Extract as a frontend-owned manifest; separate mechanical hashes |
| 6 | NeuroClient asset ledgers and importers | Critical | Delete from backend after the frontend owns its registry |
| 7 | Spell VFX/asset-discovery metadata | Medium | Split VFX routes from spell rules; retain damage/range/area semantics |
| 8 | Traversal presentation keys in mechanics/digests | Medium | Remove presentation key; retain connector mechanics and semantic kind |
| 9 | Subjective animation/presentation graph | Critical | Replace with privacy-safe semantic observation frames |
| 10 | Game-creation visual-preview subprocess | Critical | Remove from compose/start path; let frontend construct visual previews |
| 11 | Map-editor renderer palette and visual persistence | High | Keep mechanical authoring API; remove renderer schema after migration |
| 12 | Battlefield `preview` mixing layout and display | High, mixed | Split and rename; do not delete wholesale because it carries mechanics |

The two largest concentrations are different kinds of problem:

- About 29,046 lines of backend ledgers/generated code/importers mirror frontend asset inventories.
- About 6,790 lines in the central replication contract, mapper, and presentation graph make the server an animation director.

The first is the safest major deletion once content hashes are decoupled. The second is the most important architectural correction, but has the widest protocol and test blast radius.

## Current responsibility flow

The problematic path is effectively:

```text
NeuroClient asset inventory
    -> backend import tools
    -> backend JSON ledgers / generated Python
    -> engine ContentPresentation / item / appearance models
    -> mechanical content and preset digests
    -> renderer-complete world projection
    -> server-built animation graph
    -> frontend renderer
```

The desired path is:

```text
engine semantic state/events
    -> server authorization + subjective filtering
    -> privacy-safe semantic world/event protocol
    -> frontend-owned asset manifest and choreography
    -> renderer
```

## 1. Direct image and sprite leakage

### Confirmed active filename literals

- `dnd/core/base_tiles.py:577` and `:582`: `floor.png`
- `dnd/core/base_tiles.py:588`: `wall.png`
- `dnd/core/base_tiles.py:601`: `water.png`
- `dnd/core/base_tiles.py:628`: `rough.png`
- `dnd/scenarios/battlefield_catalog.py:748`: `gap.png`
- `server/world_projection.py:470` and `:646`: fallback `floor.png`

There are no active `.jpg` or `.jpeg` references and no active first-party `.png`, `.jpg`, `.jpeg`, or `.webp` binaries in the audited backend directories. The 521 `.webp` references discussed later are paths inside a backend ledger, not files served by this repository.

### Ownership chain

- `dnd/core/base_tiles.py:49` stores `Tile.sprite_name` in a mechanical tile.
- `dnd/core/gridmap.py:387`, `:444`, `:1884`, and `:1899` accept and copy it through map mutation.
- `server/world_contracts.py:464` defines `APITile`; `:471` calls `visual_key` a canonical terrain sprite key.
- `server/world_projection.py:470` and `:646` copy `sprite_name` into `visual_key` and invent a filename fallback.
- `server/mapeditor_support.py:1190` reverses the direction and loads persisted `APITile.visual_key` back into engine `sprite_name`.

This is a complete round trip: renderer filename -> engine tile -> server DTO -> saved map -> engine tile. It is not a harmless response decoration.

### Hard-cut guidance

Retain semantic terrain facts such as name/kind, walkability, movement cost, hazard, elevation, and surface kind. Delete filename identity. Before deleting `visual_key`, migrate any saved map documents to a semantic terrain kind; otherwise the renderer key may be the only discriminator in old saves.

## 2. Entity and creature appearance is an engine block

`dnd/blocks/appearance.py` is 189 lines of explicitly gameplay-inert renderer state implemented as a `BaseBlock`. Both `AppearanceConfig` and `Appearance` duplicate the following fields:

- `portrait_key`
- `presentation_kind` (`layered` or `placeholder`)
- `visual_scale` and `visual_scale_x`
- `placeholder_tint`
- `body_category` (`NakedBody`, `NakedBody2`, `NakedBody3`)
- `skin_tint`
- `head_category` (`Head1`, `Head9`, `Head10`, `Head16`, `Head17`, `Head22`)
- `hair_tint`
- `has_beard`
- `beard_tint`

The file's own module documentation says this data is passive and gameplay-inert. Nonetheless:

- `dnd/entity.py:218` puts `AppearanceConfig` in `EntityConfig`.
- `dnd/entity.py:328` puts the live `Appearance` block in every entity.
- `dnd/entity.py:212` and `:337` separately add `sprite_name`; the active code only copies it during creation, making it a particularly safe deletion candidate.
- `dnd/monsters/bestiary.py` hard-codes goblin, skeleton, and caster body/head/scale/RGB combinations.
- `dnd/monsters/srd_roster.py` decides whether creatures use the NeuroClient layered paper-doll renderer or a green placeholder.
- `dnd/monsters/circus_fighter.py` exposes `sprite_name` in creature construction.
- `server/world_contracts.py:241` duplicates the taxonomy as `APIAppearance`.
- `server/world_contracts.py:337` describes `APIEntitySummary` as renderer-complete.
- `server/world_projection.py:216` and `:360` project this renderer identity.

The engine should know creature size and other mechanical anatomy. It should not know renderer strategy, paper-doll category names, placeholder color, or sprite scale.

## 3. Character creation embeds the frontend's cosmetic option system

`dnd/content_system/character_appearance.py` is a 605-line character-creator/render taxonomy. It owns:

- display labels and stable option/value IDs for beard, body, build, hair, head, skin, and stature
- RGB palettes
- frontend-facing head values mapped to renderer keys such as `Head1`
- defaults, migrations, ordering, and option constraints
- builtin character appearance selections
- resolution into the engine `AppearanceConfig`

This remains live after database removal because the DB-free premade-character path uses it:

- `dnd/core/content/durable_characters.py:444` and `:462` define appearance selection models inside the durable character contract.
- `dnd/core/content/durable_characters.py:1399-1602` includes appearance in revision payloads and character state.
- `dnd/core/content/premade_characters.py:39` makes appearance mandatory on a premade character.
- `dnd/content_system/builtin_character_builds.py` validates, defaults, and materializes builtin appearance selections.
- `dnd/player_character_body.py`, `dnd/premade_characters.py`, and `dnd/classes/content_factories.py` participate in materialization.

Premade characters are legitimate and should remain. Their mechanical build—origin, class, level, ability scores, proficiencies, spells, and equipment—must be separable from cosmetic selection. Deleting the durable-character module would be the wrong cut; removing cosmetic taxonomy and cosmetic hashing from it is the correct cut.

## 4. Core items and equipment are renderer-aware

### Renderer models in the mechanics layer

- `dnd/core/item_types.py:19`: `EquippedVisualPolicy`
- `dnd/core/item_types.py:26`: `ItemPresentationKind`
- `dnd/core/item_types.py:117`: `ItemPresentationState`
- `dnd/core/item_types.py:142-143`: `visual_item_name` and `visual_variant_id`
- `dnd/core/equipment_types.py:24`: `VisualLoadoutSlot`
- `dnd/core/equipment_types.py:42`: `EquipmentRenderLayer`
- `dnd/blocks/base_item.py:141-148`: `map_char`, `visual_item_name`, and `visual_variant_id` on every item
- `dnd/blocks/base_item.py:221-222`: renderer fallback and variant snapshot
- `dnd/blocks/base_item.py:528`: glyph copied into a spatial-change event

Concrete item factories hard-code frontend registry names and variant IDs. Confirmed carriers include:

- `dnd/items/weapons.py`
- `dnd/items/armors.py`
- `dnd/items/spell_items.py`
- `dnd/items/acolyte_gear.py`
- `dnd/items/consumables.py`
- `dnd/items/torches.py`
- `dnd/items/environment.py`
- `dnd/items/environment_content.py`
- `dnd/items/environment_interactables.py`
- `dnd/monsters/srd_roster_items.py`
- `dnd/monsters/circus_fighter_items.py`
- `dnd/extensions/field_focus.py`
- `dnd/spells/conjuration.py`

Examples include `Club` plus variant `10000004`, `Dagger`, `Quarterstaff`, `Common Clothes`, `Traveler's Clothes`, `Crown`, `Melee10`, and many numeric sub-item IDs. These are renderer registry contracts, not D&D mechanics.

### ASCII/map glyph protocol

`map_char` is also presentation state, even though it is not graphical:

- item subclasses define glyphs in `dnd/blocks/equipment.py`, `dnd/items/consumables.py`, `dnd/items/environment.py`, `dnd/items/environment_content.py`, `dnd/items/environment_interactables.py`, `dnd/items/spell_items.py`, `dnd/items/torches.py`, `dnd/extensions/field_focus.py`, and `dnd/spells/conjuration.py`.
- `dnd/core/gridmap.py:2093-2100` copies the glyph during placement.
- `dnd/core/events.py:3625` stores it as `SpatialChangeEvent.object_map_char`.
- `server/world_contracts.py:630` stores it on `APIFloorObject`.
- `server/player_replication_contract.py:204` stores it on subjective floor objects.
- `server/objective_state.py` includes it in the objective object projection.

Retain item identity, mechanics, equipped slot, inventory ownership, charges, stack count, active weapon set, and armor calculations. Delete concrete renderer names, variants, layers, tints, and glyphs unless a separately scoped text-client protocol is intentionally retained.

## 5. The content system owns a complete presentation system

`dnd/core/content/descriptors.py` mixes domain metadata and frontend presentation in the same descriptor:

- `EquipmentSpritePresentation`: equipment slot, render layer, sprite key, RGB tint
- `ContentPresentation`: `icon_key`, `portrait_key`, `sprite_key`, `visual_variant_key`, `tint_rgb`, `vfx_profile`, `audio_key`, `ui_group`, and equipment sprites
- `ContentOrdering`: `sort_group` and `sort_order`
- `ContentDescriptorSpec`: display name, description, tags, visibility, relations, presentation, and ordering

Display name, description, semantic tags, visibility, and related content references can legitimately belong to game content. Asset routes, UI grouping, UI ordering, renderer layers, VFX, audio, and tints do not.

### Presentation changes alter backend identity

- `dnd/content_system/bootstrap.py:16-90` hashes the full descriptor into `content_set_digest`.
- `dnd/core/content/recipe_presets.py:56-70` hashes the full descriptor into `preset_contract_hash`.
- `server/content_catalog.py` creates an independently hashed safe-presentation catalog and includes it in `catalog_digest`.
- `server/world_contracts.py:82-99` defines presentation hash references and spatial-effect render payloads.
- `server/world_projection.py:88-170` resolves and hashes item presentation for transport.

Therefore changing an icon, tint, UI group, or sprite can change the global installed-content identity and named recipe-preset identity. This contaminates game creation, save compatibility, caches, and replay identity with frontend assets.

One nuance matters: `dnd/core/content/registration.py:66` computes `definition_contract_hash` from factory/definition schemas and does **not** hash the descriptor. The contamination is in `content_set_digest`, recipe-preset hashes, catalog hashes, safe-presentation hashes, and any artifact that embeds those—not in every definition contract hash.

### Correct split

The backend content registry should own semantic identity and mechanics. A frontend-owned presentation manifest may map stable semantic `ContentRef`/content IDs to icons, portraits, sprites, layers, audio, VFX, and UI arrangement. Mechanical compatibility hashes must not change when that manifest changes.

## 6. Frontend asset inventories are copied into the backend

The backend carries approximately 29,046 lines of asset-integration material:

| File | Lines | Contents |
|---|---:|---|
| `content_data/ledgers/neuroclient_authored_item_visuals.json` | 7,692 | 77 renderer categories and 205 visual variants |
| `content_data/ledgers/content_icon_bindings.json` | 13,714 | 671 definition bindings and 205 recipe-preset bindings |
| `content_data/ledgers/neuroclient_game_icon_asset_index.json` | 2,617 | 521 `.webp` asset paths, hashes, and style identity |
| `dnd/core/content/icon_bindings_generated.py` | 2,699 | generated Python bindings |
| `devtools/import_neuroclient_content_icon_bindings.py` | 1,731 | reviewed NeuroClient icon importer |
| `devtools/import_neuroclient_item_visual_inventory.py` | 593 | NeuroClient renderer-map importer |

The icon importer hard-codes the `fantasy-classic-v1` style and validates a 521-asset manifest. The item importer records its source as `NeuroClient/app/src/render/data/defaultItemVisualMap.json`. Runtime composition does not read the frontend live, but that does not remove the coupling; it freezes the frontend registry into backend-owned ledgers and generated code.

Runtime consumers include:

- `dnd/content_system/icon_bindings.py`
- `dnd/core/content/descriptors.py`
- `dnd/items/authored_variant_inventory.py`
- `dnd/items/authored_presentations.py`
- `dnd/items/authored_variant_presets.py`
- `dnd/items/apparel_presets.py`
- `dnd/items/visual_variants.py`

This entire asset-import/binding subsystem is a coherent deletion candidate after mechanical content/preset hashes no longer include presentation.

## 7. Spell rules are mixed with design-time VFX metadata

`dnd/spells/content_metadata.py:146` defines `SpellCatalogMetadata`, which combines rules/catalog facts with:

- `delivery`
- `projectile_type`
- `recommended_asset_tags`
- `vfx_profile` through content presentation helpers

The mix is propagated through:

- `dnd/spells/catalog_content.py`
- `dnd/content_system/spell_catalog_composition.py`
- `server/api_models.py:548` (`SpellCatalogVfx`)
- `server/spell_catalog.py`
- `server/event_server.py:1447` (`GET /catalog/spells`), whose documentation explicitly calls it design-time VFX/rules metadata

Concrete spell/action fields appear in:

- `dnd/actions.py:5339`, `:5764`, and event construction around `:6435`
- `dnd/spells/conjuration.py`
- `dnd/spells/evocation.py`
- `dnd/spells/illusion.py`
- `dnd/spells/necromancy.py`
- `dnd/spells/transmutation.py`
- `dnd/spells/infernal.py`
- `dnd/spells/reaction_spell_content.py`

Delete projectile visual types, VFX route hints, and asset-search tags from the engine/server catalog. Retain spell range, target type, damage type, school, save, attack roll, area shape, area dimensions, affected cells/entities, duration, concentration, and emitted semantic effects. Several `spell_damage_type` descriptions say “for VFX,” but damage type itself is gameplay semantics and must not be deleted.

## 8. Traversal connectors authenticate presentation facts as mechanics

`dnd/core/traversal_connectors.py` is mostly legitimate mechanical map state: endpoints, costs, directionality, enabled state, and provocation policy. The leak is narrower:

- `TraversalConnectorKind` is documented as a presentation family on which mechanics do not branch.
- `TraversalConnectorDefinition.presentation_key` is renderer routing data.
- `presentation_key` is included in the connector digest and copied into live discovery and event facts.
- `dnd/scenarios/battlefield_catalog.py` hard-codes keys such as `traversal.ladder`, `traversal.rope`, and `traversal.lift`.
- `dnd/core/combat_log.py`, `server/world_projection.py`, and `server/player_replication/mapper.py` propagate it.

Keep a semantic connector kind if it is meaningful to players and authoring. Remove the separate presentation key from mechanical digests and let the frontend map the semantic kind to visuals.

## 9. The server is an animation director

This is the largest live server-side boundary violation.

### Contract size and responsibilities

- `server/player_replication_contract.py`: 2,481 lines
- `server/player_replication/mapper.py`: 4,136 lines
- `server/player_replication/presentation.py`: 173 lines

`SubjectiveReplicatedWorld` is explicitly renderer-complete and requires a visual loadout for each projected entity. The contract defines visual equipment layers, loadout replacement patches, a separate presentation cursor, a frame-closed parent/child graph, and 18 concrete cue types plus the cue base:

- movement
- action
- attack
- spell
- item action
- forced movement
- shove
- counterspell
- damage
- heal
- lifecycle cause
- life-state change
- condition
- door
- light
- spatial effect
- equipment
- encounter

Many cue facts are useful semantic observations. The boundary breaks when the backend makes exact renderer decisions:

- `PresentationProjectile` is a closed renderer dispatch enum.
- `PresentationWeaponSlot` and `ActorVisualSlot` name renderer layers such as `weapon`, `weaponGlow`, and `offhand`.
- `ItemActionPresentationCue.actor_clip` is fixed to `Taunt`.
- `ShovePresentationCue.actor_clip` is fixed to `Kick`.
- `ForcedMovementPresentationCue.target_clip` is fixed to `TakeDamage`.
- the contract transports effect/contact/brace frames, playback speed, hidden visual slots, and duration in milliseconds.
- `server/player_replication/mapper.py:3726-3769` hard-codes frames 8, 7, and 5 and speeds 1.0, 1.35, and 1.25.
- `server/player_replication/mapper.py:3898` computes frontend duration as `max(260, round(rendered_distance * 220))`.
- `server/player_replication/mapper.py:2138` turns every ranged attack into `PresentationProjectile.BOLT`.
- `server/player_replication/presentation.py` orders the graph for playback.

### Dependent server infrastructure

Presentation state is not isolated to the mapper. It is persisted and validated by:

- `server/player_replication/journal.py`
- `server/player_replication/runtime.py`
- `server/player_replication/world_projection.py`
- `server/player_replay.py`
- `server/player_replay_capture.py`
- `server/objective_diagnostics_contracts.py`
- `server/subjective_parity_diagnostics.py`
- `server/event_server.py`

The server also caches corpse visual loadouts, validates presentation cursor continuity, emits presentation-reset states, and exposes renderer parity diagnostics.

### Correct boundary

The server must continue to authorize observers and hide undiscovered entities, cells, reactions, targets, and effects. It should emit privacy-safe semantic observations: who moved, from/to/path, what action occurred, source/target, hit/miss, damage/heal, damage type, condition changes, equipment changes, door/light changes, and causal/event ordering. The frontend should select clips, frame timing, projectiles, VFX, layers, easing, duration, and graph playback.

Removing privacy/subjective projection together with animation would be an architectural regression. Remove choreography, not information security.

## 10. Game creation requires a visual-preview subprocess

The current create-game flow owns a second renderer-oriented process:

- `server/game_creation_preview.py`: 338 lines of retained subprocess, stdin/stdout protocol, threads, timeouts, cache, prewarm, and shutdown
- `server/game_creation_preview_worker.py`: 134 lines that materialize an encounter and projects renderer DTOs
- `server/game_creation_preview_contracts.py`: 90 lines of production renderer-preview models
- `server/event_server.py:1313` prewarms the process during server lifespan
- `server/event_server.py:3400-3430` makes `/game-creation/compose` build a visual preview before returning
- `server/event_server.py:3434-3454` exposes `/game-creation/preview`
- `server/api_models.py:1043` makes preview part of `GameCreationComposeResponse`

The preview worker returns `APIEntitySummary` plus `EntityVisualLoadout`. A valid normalized encounter composition can therefore fail because a renderer preview child fails. That is an inverted dependency.

Keep recipe normalization, compatibility checks, semantic roster/member facts, and game start. Remove the visual subprocess and the mandatory visual preview from compose. The frontend can preview its own assets from semantic character/content identity without causing a second engine process to exist.

## 11. The map editor is a mixed backend/frontend subsystem

The active server has 16 `/mapeditor/*` routes covering catalog, map snapshots, saves, tile edits, connector edits, object edits, walkability, visibility, and light.

Mechanical map authoring belongs on the backend when the backend is authoritative for topology and rules. The following parts are frontend leakage:

- `server/api_models.py:668` defines `MapEditorCatalogEntry` with `group`, `category`, `stability`, `placement`, `map_char`, `visual_item_name`, open-ended UI `flags`, `actions`, and `default_state`.
- `server/api_models.py:701` defines `MapEditorContentCatalogEntry` with full `ContentPresentation` and `ContentOrdering`.
- `server/mapeditor_support.py:447-530` constructs and sorts the presentation-aware palette.
- `server/mapeditor_support.py:1394-1435` builds explicit glyph/visual/presentation rows.
- map save/load persists `APITile.visual_key` and restores it as `Tile.sprite_name`.

Keep tile/object/connector placement commands, validation, walkability, vision, light, elevation, object state, and persistence. Remove frontend palette arrangement and concrete asset keys after saved maps have a semantic migration.

## 12. Battlefield `preview` cannot be blindly deleted

`dnd/core/content/battlefields.py` defines:

- `BattlefieldPreviewCell`
- `BattlefieldPreviewObject`
- `BattlefieldElevationCell`
- `BattlefieldPreview`
- `BattlefieldDefinition.preview`

The names imply disposable UI preview data, and some of it is duplicated presentation data: object labels, presentation kinds, and static layout repeated by imperative runtime builders. However, `dnd/scenarios/battlefield_catalog.py:740+` uses `definition.preview.cells`, `elevation_cells`, and `connectors` to build the elevation proving ground's actual mechanical map. Deleting `preview` wholesale would delete authoritative gaps, elevation, and traversal connectors.

The correct refactor is to extract a neutral `BattlefieldLayout` (or equivalent) containing one authoritative set of cells, terrain mechanics, elevation, connectors, and object recipes/state. Runtime construction and catalog projection should use that. Frontend-only labels and display families should move out. This also removes the current risk that duplicated preview and builder data drift apart.

## Generated and diagnostic fallout

These are secondary carriers rather than independent product responsibilities:

- `server/event_contract.generated.json` is 19,651 lines and currently contains item presentation, projectile type, connector presentation key, map glyph, visual policy, and presentation-geometry leaf types because engine events contain those fields.
- `devtools/generate_event_contract.py` still contains TypeScript naming/type-rendering helpers even though its active output is the server JSON manifest.
- `server/subjective_parity_diagnostics.py` and `server/objective_diagnostics_contracts.py` compare renderer-complete state and expose `/diagnostics/subjective-parity`.
- `server/player_replay.py` and `server/player_replay_capture.py` archive presentation cursor/graph state.
- `dnd/scenarios/authored_catalog.json` embeds battlefield preview/layout and content digests and must be regenerated after the schema split.

The event contract, diagnostics, replay, and authored catalog all have legitimate purposes. Regenerate or simplify them after removing frontend fields; do not delete them merely because they currently contain contaminated models.

## Things that look like frontend responsibility but should remain

The following were reviewed and are not deletion candidates as such:

- **Subjective visibility, fog, light, and hidden-information filtering.** These enforce game knowledge and security.
- **Available actions and valid targets.** `AvailableActionsResult` contains authoritative legality, resources, target indices, paths, hazards, opportunity-attack exposure, and affected entities/cells.
- **AoE target/position preview.** It computes authoritative affected cells and entities under the current rules and observer knowledge.
- **Area geometry.** `dnd/core/presentation_geometry.py` is badly named, but its immutable cone/line/cube/cylinder/sphere geometry records the actual declared spell area for events and replay. Rename it to semantic event/area geometry; retain it.
- **Damage types and spell schools.** They are game semantics even where comments mention VFX.
- **Entity/content/item IDs and `ContentRef`.** Stable semantic identity is precisely what lets a frontend own presentation mappings.
- **Display names, descriptions, rules text, and narrative combat logs.** These are authored game content, not renderer implementation.
- **Equipment slots, inventory, armor class, charges, stacks, and active weapon set.** These are mechanics. Only derived render loadouts/layers are frontend work.
- **Map commands and mechanical map persistence.** Only sprite/glyph/palette fields leak.
- **Game summaries, game event archives, and semantic replay.** These are useful backend responsibilities and should survive.
- **`visual_access` in sensory rules.** It is a creature perception mechanic, not a renderer flag.
- **Structural wall/door kind and open state.** These are semantic topology facts even if a model is named `StructuralEdgeAppearance`.
- **Semantic causal ordering.** A frontend needs ordered observable events, but it does not need the backend to build a playback graph.
- **Premade characters.** Keep their mechanical builds and detach cosmetic renderer data.

## Data-loss and compatibility traps

1. **Saved maps:** `APITile.visual_key` is persisted and loaded back into engine state. Migrate to semantic terrain/object kinds before deletion.
2. **Durable/premade character revisions:** appearance selections are included in revision payloads. Removing them changes character identity. The database may be disposable, but checked-in/generated premade artifacts still need regeneration.
3. **Content identity:** presentation is included in `content_set_digest` and recipe-preset hashes. Splitting it invalidates catalog/game-creation identities and any save or replay that authenticates them.
4. **Replays:** subjective replay frames contain presentation cursors and cue graphs. Old renderer-complete replays will not validate against a semantic-only schema unless migrated or intentionally abandoned.
5. **Battlefields:** `preview` contains authoritative mechanical layout for at least the elevation proving ground. Split it before deletion.
6. **Frontend protocol:** compose responses, world DTOs, map editor responses, and replication frames currently promise renderer-complete fields. Backend deletion and frontend adoption need one coordinated protocol cut, not compatibility facades.

Because the database can be wiped, database/schema migration is not the hard part. Checked-in JSON artifacts, saved map documents, replay files, hashes, and frontend protocol assumptions are the real compatibility surface.

## Recommended hard-cut order

### Cut A: remove dead/direct render identifiers

- Delete `Entity.sprite_name` and its construction parameters.
- Replace tile filenames with semantic terrain kinds.
- Remove `map_char` from engine items/events/world DTOs unless a text-client requirement is explicitly retained.
- Remove connector `presentation_key`; keep semantic connector kind and mechanics.
- Remove spell projectile/VFX/asset-tag fields; keep semantic spell facts.

Do the map-save translation before deleting tile `visual_key`.

### Cut B: extract the asset/content presentation product

- Delete the three ledgers, two NeuroClient importers, generated icon bindings, and runtime binding validators from the backend.
- Split `ContentPresentation` and `ContentOrdering` out of mechanical content descriptors.
- Make mechanical content/preset digests independent of presentation.
- Remove presentation payloads from content and map-editor APIs.

This is the cleanest large hard cut and eliminates roughly 29,000 lines of frozen frontend integration before touching gameplay replication.

### Cut C: detach character and item cosmetics

- Remove the `Appearance` engine block and `APIAppearance`.
- Remove frontend body/head/tint option catalogs from durable character mechanics.
- Keep premade character mechanics; let frontend identity map to its own cosmetic profile.
- Remove item render names/variants/layers/policies while retaining item/equipment mechanics.

### Cut D: replace presentation replication with semantic observation

- Remove visual loadouts, presentation cursors, playback graphs, renderer enums, clips, frames, speeds, and duration decisions.
- Preserve subjective authorization/filtering and ordered semantic event facts.
- Convert replay capture to semantic subjective observation frames.
- Delete renderer-parity diagnostics or redefine parity around semantic projection.

### Cut E: remove creation preview process and normalize mixed layout data

- Remove preview prewarm/process/protocol/routes and the mandatory compose preview.
- Split `BattlefieldPreview` into authoritative mechanical layout plus frontend presentation.
- Strip renderer palette and visual keys from map persistence.

## Complete confirmed first-party file inventory

The following inventory lists active files that either own confirmed frontend state or directly transport, hash, persist, generate, or diagnose it. Files containing mixed responsibilities should be edited, not necessarily deleted.

### Core/entity/character appearance

- `dnd/blocks/appearance.py`
- `dnd/entity.py`
- `dnd/content_system/character_appearance.py`
- `dnd/content_system/builtin_character_builds.py`
- `dnd/core/content/durable_characters.py`
- `dnd/core/content/premade_characters.py`
- `dnd/classes/content_factories.py`
- `dnd/player_character_body.py`
- `dnd/premade_characters.py`
- `dnd/monsters/bestiary.py`
- `dnd/monsters/srd_roster.py`
- `dnd/monsters/circus_fighter.py`
- `dnd/monsters/configured_srd_creatures.py`

### Tiles, maps, glyphs, and battlefield layout

- `dnd/core/base_block.py`
- `dnd/core/base_tiles.py`
- `dnd/core/gridmap.py`
- `dnd/core/events.py`
- `dnd/core/content/battlefields.py`
- `dnd/core/traversal_connectors.py`
- `dnd/core/combat_log.py`
- `dnd/scenarios/battlefield_catalog.py`
- `dnd/scenarios/authored_catalog.json`
- `server/mapeditor_support.py`
- `server/objective_state.py`
- `server/api_models.py`
- `server/world_contracts.py`
- `server/world_projection.py`

### Item/equipment renderer identity

- `dnd/blocks/base_item.py`
- `dnd/blocks/equipment.py`
- `dnd/core/action_types.py`
- `dnd/core/base_actions.py`
- `dnd/core/equipment_types.py`
- `dnd/core/item_types.py`
- `dnd/items/acolyte_gear.py`
- `dnd/items/apparel_presets.py`
- `dnd/items/armors.py`
- `dnd/items/authored_presentations.py`
- `dnd/items/authored_variant_inventory.py`
- `dnd/items/authored_variant_presets.py`
- `dnd/items/consumables.py`
- `dnd/items/environment.py`
- `dnd/items/environment_content.py`
- `dnd/items/environment_interactables.py`
- `dnd/items/spell_items.py`
- `dnd/items/torches.py`
- `dnd/items/visual_variants.py`
- `dnd/items/weapons.py`
- `dnd/extensions/field_focus.py`
- `dnd/monsters/bestiary_items.py`
- `dnd/monsters/circus_fighter_items.py`
- `dnd/monsters/srd_roster_items.py`

### Content presentation declarations and hashing

- `dnd/core/content/descriptors.py`
- `dnd/core/content/icon_bindings_generated.py`
- `dnd/core/content/recipe_presets.py`
- `dnd/content_system/bootstrap.py`
- `dnd/content_system/icon_bindings.py`
- `dnd/content_system/acolyte_starting_holdings.py`
- `dnd/content_system/action_definitions.py`
- `dnd/content_system/character_origin_definitions.py`
- `dnd/content_system/condition_definitions.py`
- `dnd/content_system/dragonborn_origin_definitions.py`
- `dnd/content_system/origin_feature_definitions.py`
- `dnd/content_system/reaction_definitions.py`
- `dnd/content_system/starting_apparel_definitions.py`
- `dnd/content_system/starting_equipment_definitions.py`
- `dnd/classes/barbarian_progression_definitions.py`
- `dnd/classes/permanent_feature_definitions.py`
- `dnd/classes/progression_definitions.py`
- `dnd/classes/sorcerer_progression_definitions.py`
- `dnd/classes/sorcerer_structural_feature_definitions.py`
- `dnd/classes/structural_feature_definitions.py`
- `dnd/conditions.py`
- `dnd/monsters/bestiary_content.py`
- `dnd/monsters/multiattack_definitions.py`
- `dnd/origins/dragonborn.py`
- `dnd/origins/half_orc.py`
- `dnd/origins/halfling.py`
- `dnd/spatial_effect_content.py`
- `server/content_catalog.py`

### Spell VFX and presentation declarations

- `dnd/actions.py`
- `dnd/content_system/spell_catalog_composition.py`
- `dnd/spells/catalog_content.py`
- `dnd/spells/content_metadata.py`
- `dnd/spells/abjuration.py`
- `dnd/spells/conjuration.py`
- `dnd/spells/enchantment.py`
- `dnd/spells/evocation.py`
- `dnd/spells/illusion.py`
- `dnd/spells/infernal.py`
- `dnd/spells/necromancy.py`
- `dnd/spells/reaction_spell_content.py`
- `dnd/spells/transmutation.py`
- `server/spell_catalog.py`

`dnd/spells/abjuration.py` and `dnd/spells/enchantment.py` mostly carry presentation through shared content helpers or misleading VFX descriptions. Mechanical damage types and spell behavior in these files remain.

### Asset ledgers, importers, and generated bindings

- `content_data/ledgers/content_icon_bindings.json`
- `content_data/ledgers/neuroclient_authored_item_visuals.json`
- `content_data/ledgers/neuroclient_game_icon_asset_index.json`
- `devtools/import_neuroclient_content_icon_bindings.py`
- `devtools/import_neuroclient_item_visual_inventory.py`
- `dnd/core/content/icon_bindings_generated.py`

### Replication, presentation, replay, and diagnostics

- `dnd/core/content/runtime.py` (`EffectiveHandlerPresentation`, used to feed the presentation mapper)
- `server/player_replication_contract.py`
- `server/player_replication/mapper.py`
- `server/player_replication/presentation.py`
- `server/player_replication/world_projection.py`
- `server/player_replication/journal.py`
- `server/player_replication/runtime.py`
- `server/player_replay.py`
- `server/player_replay_capture.py`
- `server/subjective_parity_diagnostics.py`
- `server/objective_diagnostics_contracts.py`
- `server/timeline_contracts.py` (presentation-barrier terminology/dependency)
- `server/event_server.py`

### Game-creation preview

- `server/game_creation_preview.py`
- `server/game_creation_preview_worker.py`
- `server/game_creation_preview_contracts.py`
- `server/api_models.py`
- `server/event_server.py`

### Generated wire contract

- `server/event_contract.generated.json`
- `server/event_contract.py`
- `devtools/generate_event_contract.py`

## Direct test blast-radius inventory

These tests directly mention one or more confirmed renderer/presentation fields or subsystems. They are not all obsolete: many should be rewritten to assert the retained semantic boundary. This list is intentionally separated from deletion recommendations.

### Architecture/engine tests

- `tests/architecture/test_dependency_boundaries.py`
- `tests/architecture/test_source_model_hygiene.py`
- `tests/engine/test_cold_presentation_facts.py`
- `tests/engine/test_combat_actions.py`
- `tests/engine/test_condition_transform_ownership.py`
- `tests/engine/test_elevation_performance_contract.py`
- `tests/engine/test_elevation_proving_battlefield.py`
- `tests/engine/test_encounter_apis.py`
- `tests/engine/test_equipment_replication_facts.py`
- `tests/engine/test_life_state_ownership.py`
- `tests/engine/test_manual_10_standard_conditions.py`
- `tests/engine/test_manual_20_encounters_turns_controllers_apis.py`
- `tests/engine/test_manual_21_arena_game_sessions_client_state.py`
- `tests/engine/test_objective_state.py`
- `tests/engine/test_spell_families.py`
- `tests/engine/test_spellcasting.py`
- `tests/engine/test_standard_conditions.py`
- `tests/engine/test_traversal_connectors.py`

### Manual/integration tests

- `tests/manual/game_creation_test_support.py`
- `tests/manual/test_02_entity_anatomy.py`
- `tests/manual/test_11_equipment_inventory_and_items.py`
- `tests/manual/test_14_spell_families.py`
- `tests/manual/test_18_sessions_api_client_contract.py`
- `tests/manual/test_19_map_editor_scenario_authoring.py`
- `tests/manual/test_20_content_extension_basics.py`
- `tests/manual/test_37_authored_encounter_mechanics.py`
- `tests/manual/test_95_creature_presentation_contract.py`
- `tests/manual/test_96_game_creation_api.py`
- `tests/manual/test_113_subjective_replication_routes.py`
- `tests/manual/test_117_player_replication_contract.py`
- `tests/manual/test_120_player_replication_journal.py`
- `tests/manual/test_120_subjective_world_projection.py`
- `tests/manual/test_121_canonical_presentation_mapper.py`
- `tests/manual/test_122_canonical_replication_runtime.py`
- `tests/manual/test_123_subjective_player_replay.py`
- `tests/manual/test_125_active_weapon_stance.py`
- `tests/manual/test_125_haste_restricted_action.py`
- `tests/manual/test_125_subjective_objective_render_parity.py`
- `tests/manual/test_131_advanced_item_world_legacy_contract.py`
- `tests/manual/test_131_tier1_spell_legacy_gaps.py`
- `tests/manual/test_133_new_spells_batch4_legacy_contract.py`
- `tests/manual/test_139_condition_presentation_contract.py`
- `tests/manual/test_143_condition_removal_legacy_contract.py`
- `tests/manual/test_147_mapeditor_legacy_contract.py`
- `tests/manual/test_165_item_content_identity.py`
- `tests/manual/test_166_club_content_factory.py`
- `tests/manual/test_167_srd_weapon_content_factories.py`
- `tests/manual/test_168_content_catalog_contract.py`
- `tests/manual/test_169_neurodragon_weapon_content_factories.py`
- `tests/manual/test_170_neurodragon_consumable_content_factories.py`
- `tests/manual/test_177_content_recipe_presets.py`
- `tests/manual/test_178_authored_item_visual_inventory.py`
- `tests/manual/test_178_remaining_possession_item_roots.py`
- `tests/manual/test_178_spell_catalog_content_identity.py`
- `tests/manual/test_179_player_item_transport_identity.py`
- `tests/manual/test_180_environment_content_identity.py`
- `tests/manual/test_180_srd_creature_possession_bindings.py`
- `tests/manual/test_181_action_content_identity.py`
- `tests/manual/test_181_affordance_content_identity.py`
- `tests/manual/test_182_mapeditor_content_recipe_hard_cut.py`
- `tests/manual/test_183_content_icon_bindings.py`
- `tests/manual/test_189_game_creation_visual_preview.py`
- `tests/manual/test_193_game_creation_composition.py`
- `tests/manual/test_durable_character_revision_contracts.py`
- `tests/manual/test_neurodragon_apparel_content_factories.py`
- `tests/manual/test_neurodragon_spell_item_content_factories.py`
- `tests/manual/test_srd_armor_content_factories.py`

### Progression/sequence tests

- `tests/progression/test_barbarian_berserker_materialization.py`
- `tests/progression/test_builtin_character_origins.py`
- `tests/progression/test_character_appearance.py`
- `tests/progression/test_character_build_validation.py`
- `tests/progression/test_dependency_neutral_progression_foundation.py`
- `tests/progression/test_dragonborn_origin_runtime.py`
- `tests/progression/test_structural_class_feature_definitions.py`
- `tests/transition_sequences/emit_acid_splash_presentation_sequence.py`

The broad test search also matches some legitimate semantic uses of words such as `visual`, `presentation`, or `preview`. During implementation, classify each test against the keep/split/delete boundary above rather than deleting this list mechanically.

## Final architectural conclusion

The backend is currently three systems at once:

1. a game-rules engine,
2. an authoritative subjective-information server,
3. a frontend asset registry and animation director.

The first two belong together. The third does not.

The clean boundary is not “the backend never sends anything visualizable.” It is: the backend sends stable semantic identity and authorized observed facts, while the frontend owns concrete assets and choreography. That boundary preserves multiplayer/privacy correctness, game summaries, saves, semantic replay, premade characters, and map mechanics while removing the renderer product embedded in the engine and server.
